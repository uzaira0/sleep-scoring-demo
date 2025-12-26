"""
HDCZA (van Hees 2018) sleep detection algorithm.

HDCZA (Heuristic algorithm using Distribution of Change in Z-Angle) is an advanced
sleep period detection algorithm that automatically identifies the main Sleep Period
Time (SPT) window without requiring a sleep diary.

Algorithm Overview (9 Steps):
1. Calculate z-angle from raw tri-axial acceleration (median per 5s epoch)
2. Calculate z-angle changes (absolute differences between consecutive epochs)
3. Calculate 5-minute rolling median of z-angle changes
4. For each noon-to-noon day, calculate 10th percentile threshold
5. Multiply threshold by factor 15 (empirically derived)
6. Detect blocks where rolling median < threshold AND duration > 30 minutes
7. Merge blocks separated by < 60 minutes
8. Select longest block per day as main SPT window
9. Output SPT window (onset/offset datetimes) and epoch-level sleep scores

This algorithm is orientation-invariant and does not require manual sleep diaries,
making it ideal for large-scale research studies.

References:
    van Hees VT, Sabia S, Jones SE, et al. (2018).
    Estimating sleep parameters using an accelerometer without sleep diary.
    Scientific Reports 8: 12140.
    https://doi.org/10.1038/s41598-018-31266-z

    GGIR Package Implementation:
    https://cran.r-project.org/package=GGIR
    https://wadpac.github.io/GGIR/

"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from sleep_scoring_app.core.algorithms.sleep_wake.z_angle import (
    calculate_z_angle_from_dataframe,
    resample_to_epochs,
    split_into_noon_to_noon_days,
    validate_raw_accelerometer_data,
)
from sleep_scoring_app.core.constants import SleepPeriodDetectorType
from sleep_scoring_app.core.pipeline.types import AlgorithmDataRequirement

logger = logging.getLogger(__name__)


@dataclass
class SleepPeriodWindow:
    """
    Sleep Period Time (SPT) window detected by HDCZA.

    Attributes:
        onset: Sleep onset datetime
        offset: Sleep offset datetime
        duration_minutes: Duration of sleep period in minutes
        day_label: Noon-to-noon day identifier (date)

    """

    onset: pd.Timestamp
    offset: pd.Timestamp
    duration_minutes: float
    day_label: str

    def __str__(self) -> str:
        """String representation."""
        return f"SPT({self.day_label}): {self.onset} to {self.offset} ({self.duration_minutes:.1f}min)"


class HDCZA:
    """
    HDCZA (van Hees 2018) sleep period detection algorithm.

    This algorithm automatically detects the main Sleep Period Time (SPT) window
    from raw accelerometer data without requiring a sleep diary. It analyzes
    patterns in arm angle (z-angle) changes to identify sustained inactivity.

    Key Parameters:
        - angle_threshold_multiplier: Multiplier for threshold calculation (default: 15)
        - percentile: Percentile for threshold (default: 10)
        - min_block_duration: Minimum block duration in minutes (default: 30)
        - max_gap_duration: Maximum gap for merging blocks in minutes (default: 60)
        - epoch_length: Z-angle calculation window in seconds (default: 5)

    The algorithm outputs:
        1. Primary: Sleep Period Time window (onset/offset datetimes) for each day
        2. Secondary: Epoch-level sleep/wake scores at 60-second resolution

    Example:
        >>> from sleep_scoring_app.core.algorithms import HDCZA
        >>>
        >>> # Create algorithm with default parameters
        >>> algorithm = HDCZA()
        >>>
        >>> # Score raw GT3X data
        >>> df = algorithm.score(raw_df)
        >>> df['Sleep Score']
        0    0
        1    0
        2    1  # Inside SPT window
        ...

    """

    def __init__(
        self,
        angle_threshold_multiplier: float = 15.0,
        percentile: float = 10.0,
        min_block_duration: int = 30,
        max_gap_duration: int = 60,
        epoch_length: int = 5,
    ) -> None:
        """
        Initialize HDCZA algorithm.

        Args:
            angle_threshold_multiplier: Factor for threshold calculation.
                                       Default: 15 (as per van Hees 2018)
            percentile: Percentile for daily threshold calculation.
                       Default: 10 (10th percentile, as per van Hees 2018)
            min_block_duration: Minimum duration (minutes) for a sleep block.
                              Default: 30 minutes
            max_gap_duration: Maximum gap (minutes) between blocks to merge them.
                            Default: 60 minutes
            epoch_length: Length of z-angle calculation window in seconds.
                        Default: 5 seconds

        """
        self._angle_threshold_multiplier = angle_threshold_multiplier
        self._percentile = percentile
        self._min_block_duration = min_block_duration
        self._max_gap_duration = max_gap_duration
        self._epoch_length = epoch_length

        # Store detected SPT windows
        self._spt_windows: list[SleepPeriodWindow] = []

        # Store parameters for get_parameters()
        self._parameters = {
            "angle_threshold_multiplier": angle_threshold_multiplier,
            "percentile": percentile,
            "min_block_duration": min_block_duration,
            "max_gap_duration": max_gap_duration,
            "epoch_length": epoch_length,
        }

    @property
    def name(self) -> str:
        """Algorithm name for display."""
        return "HDCZA (van Hees 2018)"

    @property
    def identifier(self) -> str:
        """Unique algorithm identifier."""
        return SleepPeriodDetectorType.HDCZA_2018

    @property
    def description(self) -> str:
        """Brief description of the algorithm logic."""
        return (
            f"Automatic SPT detection using z-angle distribution analysis. "
            f"Threshold: P{self._percentile} x {self._angle_threshold_multiplier}. "
            f"Min block: {self._min_block_duration}min. Max gap: {self._max_gap_duration}min."
        )

    @property
    def requires_axis(self) -> str:
        """Required data type - raw tri-axial accelerometer data."""
        return "raw_triaxial"

    @property
    def data_source_type(self) -> str:
        """Data source type required by this algorithm."""
        return "raw"

    @property
    def data_requirement(self) -> AlgorithmDataRequirement:
        """Data requirement - HDCZA requires raw tri-axial accelerometer data."""
        return AlgorithmDataRequirement.RAW_DATA

    @property
    def spt_windows(self) -> list[SleepPeriodWindow]:
        """
        Get detected Sleep Period Time windows.

        Returns:
            List of SleepPeriodWindow objects, one per noon-to-noon day

        """
        return self._spt_windows.copy()

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect Sleep Period Time and score sleep/wake from raw accelerometer data.

        This algorithm requires raw accelerometer data with X, Y, Z axes.
        It will NOT work with pre-aggregated epoch count data.

        Args:
            df: DataFrame with columns:
                - timestamp: datetime
                - AXIS_X: X-axis acceleration in g
                - AXIS_Y: Y-axis acceleration in g
                - AXIS_Z: Z-axis acceleration in g

        Returns:
            DataFrame with:
                - timestamp: datetime at 60-second resolution
                - Sleep Score: 1 inside SPT window, 0 outside
                - z_angle_change: Rolling median of z-angle changes (diagnostic)

        Raises:
            ValueError: If required columns are missing or data is invalid

        """
        # Validate input data
        is_valid, errors = validate_raw_accelerometer_data(
            df,
            timestamp_col="timestamp",
            ax_col="AXIS_X",
            ay_col="AXIS_Y",
            az_col="AXIS_Z",
        )
        if not is_valid:
            msg = f"Invalid raw accelerometer data: {', '.join(errors)}"
            raise ValueError(msg)

        # Check if this is epoch data (should be rejected)
        if "Axis1" in df.columns or "Activity" in df.columns:
            msg = "HDCZA algorithm requires RAW tri-axial accelerometer data, not pre-aggregated epoch counts. Please load a GT3X file with raw data."
            raise ValueError(msg)

        logger.info(f"Running HDCZA algorithm on {len(df)} raw samples")

        # Step 1-2: Calculate z-angle from raw tri-axial data
        df_with_z = calculate_z_angle_from_dataframe(
            df,
            ax_col="AXIS_X",
            ay_col="AXIS_Y",
            az_col="AXIS_Z",
        )

        # Resample to epoch_length (5-second epochs) using median
        z_angle_epochs = resample_to_epochs(
            df_with_z,
            timestamp_col="timestamp",
            value_col="z_angle",
            epoch_seconds=self._epoch_length,
            aggregation="median",
        )

        logger.debug(f"Resampled to {len(z_angle_epochs)} {self._epoch_length}-second z-angle epochs")

        # Step 3: Calculate z-angle changes (absolute differences)
        z_angles = z_angle_epochs["z_angle"].to_numpy()
        z_angle_changes = np.abs(np.diff(z_angles))

        # Pad with NaN at beginning to maintain length
        z_angle_changes = np.concatenate([[np.nan], z_angle_changes])
        z_angle_epochs["z_angle_change"] = z_angle_changes

        # Step 4-5: Calculate 5-minute rolling median of z-angle changes
        window_epochs = int((5 * 60) / self._epoch_length)  # 5 minutes in epochs
        z_angle_epochs["rolling_median"] = z_angle_epochs["z_angle_change"].rolling(window=window_epochs, center=True).median()

        logger.debug(f"Calculated rolling median with window of {window_epochs} epochs (5 minutes)")

        # Step 6-9: Split into noon-to-noon days and detect SPT windows
        day_segments = split_into_noon_to_noon_days(z_angle_epochs, timestamp_col="timestamp")

        logger.info(f"Split data into {len(day_segments)} noon-to-noon day segments")

        # Clear previous SPT windows
        self._spt_windows = []

        # Process each day
        all_day_results = []
        for day_df in day_segments:
            if len(day_df) < 100:
                logger.warning(f"Day segment too short ({len(day_df)} epochs), skipping")
                continue

            # Detect SPT window for this day
            spt_window, day_scores = self._detect_spt_window_for_day(day_df)

            if spt_window is not None:
                self._spt_windows.append(spt_window)
                logger.info(f"Detected SPT window: {spt_window}")

            all_day_results.append(day_scores)

        # Combine all days
        if not all_day_results:
            msg = "No valid day segments found in data"
            raise ValueError(msg)

        result_df = pd.concat(all_day_results, ignore_index=True)

        # Resample to 60-second epochs for consistency with other algorithms
        result_60s = self._resample_to_60_seconds(result_df)

        logger.info(
            f"HDCZA completed: {len(result_60s)} 60-second epochs, "
            f"{len(self._spt_windows)} SPT windows detected, "
            f"{result_60s['Sleep Score'].sum()} sleep epochs ({result_60s['Sleep Score'].mean() * 100:.1f}%)"
        )

        return result_60s

    def _detect_spt_window_for_day(
        self,
        day_df: pd.DataFrame,
    ) -> tuple[SleepPeriodWindow | None, pd.DataFrame]:
        """
        Detect Sleep Period Time window for a single noon-to-noon day.

        Args:
            day_df: DataFrame for one noon-to-noon day with z_angle and rolling_median columns

        Returns:
            Tuple of (SPT window or None, DataFrame with Sleep Score column)

        """
        # Get day label (date string)
        day_start = day_df["timestamp"].iloc[0]
        day_label = day_start.strftime("%Y-%m-%d")

        # Step 6: Calculate threshold (10th percentile x 15)
        rolling_median = day_df["rolling_median"].dropna()

        if len(rolling_median) < 10:
            logger.warning(f"Not enough data for day {day_label}, marking all as wake")
            day_df["Sleep Score"] = 0
            return None, day_df

        p_value = np.percentile(rolling_median, self._percentile)
        threshold = p_value * self._angle_threshold_multiplier

        # Apply threshold bounds as per GGIR implementation (HASPT.R lines 112-116)
        # Minimum: 0.13 deg, Maximum: 0.50 deg
        # These bounds prevent threshold from being too low (when P10 ~= 0) or too high
        min_threshold = 0.13
        max_threshold = 0.50
        original_threshold = threshold
        if threshold < min_threshold:
            threshold = min_threshold
        elif threshold > max_threshold:
            threshold = max_threshold

        if threshold != original_threshold:
            logger.debug(f"Day {day_label}: threshold {original_threshold:.4f} deg clamped to {threshold:.2f} deg")

        logger.debug(
            f"Day {day_label}: threshold = {threshold:.2f} deg (P{self._percentile} = {p_value:.4f} deg x {self._angle_threshold_multiplier})"
        )

        # Step 7: Detect blocks where rolling_median < threshold
        below_threshold = day_df["rolling_median"].fillna(999) < threshold
        blocks = self._find_contiguous_blocks(below_threshold.to_numpy(), day_df["timestamp"].to_numpy())

        # Filter by minimum duration
        min_duration_seconds = self._min_block_duration * 60
        valid_blocks = [b for b in blocks if b["duration_seconds"] >= min_duration_seconds]

        logger.debug(f"Day {day_label}: found {len(blocks)} blocks, {len(valid_blocks)} meet minimum duration")

        if not valid_blocks:
            logger.warning(f"No valid sleep blocks found for day {day_label}")
            day_df["Sleep Score"] = 0
            return None, day_df

        # Step 8: Merge blocks separated by < max_gap_duration
        merged_blocks = self._merge_nearby_blocks(valid_blocks)

        logger.debug(f"Day {day_label}: {len(merged_blocks)} blocks after merging")

        # Step 9: Select longest block as main SPT window
        longest_block = max(merged_blocks, key=lambda b: b["duration_seconds"])

        spt_window = SleepPeriodWindow(
            onset=longest_block["start"],
            offset=longest_block["end"],
            duration_minutes=longest_block["duration_seconds"] / 60,
            day_label=day_label,
        )

        # Mark epochs inside SPT window as sleep
        day_df["Sleep Score"] = 0
        in_spt = (day_df["timestamp"] >= spt_window.onset) & (day_df["timestamp"] <= spt_window.offset)
        day_df.loc[in_spt, "Sleep Score"] = 1

        return spt_window, day_df

    def _find_contiguous_blocks(
        self,
        condition: np.ndarray,
        timestamps: np.ndarray,
    ) -> list[dict[str, Any]]:
        """
        Find contiguous blocks where condition is True.

        Args:
            condition: Boolean array
            timestamps: Array of timestamps (same length as condition)

        Returns:
            List of block dictionaries with start, end, duration_seconds

        """
        blocks = []

        # Find transitions
        transitions = np.diff(np.concatenate([[False], condition, [False]]).astype(int))
        starts = np.where(transitions == 1)[0]
        ends = np.where(transitions == -1)[0]

        for start_idx, raw_end_idx in zip(starts, ends, strict=False):
            # raw_end_idx is exclusive (one past the last True value)
            end_idx = raw_end_idx - 1  # Make it inclusive

            if start_idx >= len(timestamps) or end_idx >= len(timestamps):
                continue

            start_time = timestamps[start_idx]
            end_time = timestamps[end_idx]

            # Calculate duration
            if isinstance(start_time, pd.Timestamp):
                duration_seconds = (end_time - start_time).total_seconds()
            else:
                # Assume datetime64
                duration_seconds = (end_time - start_time) / np.timedelta64(1, "s")

            blocks.append(
                {
                    "start": pd.Timestamp(start_time),
                    "end": pd.Timestamp(end_time),
                    "duration_seconds": duration_seconds,
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                }
            )

        return blocks

    def _merge_nearby_blocks(
        self,
        blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Merge blocks separated by gaps less than max_gap_duration.

        Args:
            blocks: List of block dictionaries

        Returns:
            List of merged block dictionaries

        """
        if len(blocks) <= 1:
            return blocks

        # Sort blocks by start time
        sorted_blocks = sorted(blocks, key=lambda b: b["start"])

        merged = []
        current_block = sorted_blocks[0].copy()

        max_gap_seconds = self._max_gap_duration * 60

        for next_block in sorted_blocks[1:]:
            # Calculate gap between current block end and next block start
            gap_seconds = (next_block["start"] - current_block["end"]).total_seconds()

            if gap_seconds <= max_gap_seconds:
                # Merge: extend current block to include next block
                current_block["end"] = next_block["end"]
                current_block["end_idx"] = next_block["end_idx"]
                current_block["duration_seconds"] = (current_block["end"] - current_block["start"]).total_seconds()
            else:
                # Gap too large, save current block and start new one
                merged.append(current_block)
                current_block = next_block.copy()

        # Add final block
        merged.append(current_block)

        return merged

    def _resample_to_60_seconds(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Resample epoch_length results to 60-second epochs using majority vote.

        Args:
            df: DataFrame with timestamp and Sleep Score columns

        Returns:
            DataFrame resampled to 60-second epochs

        """
        # Set timestamp as index
        df_indexed = df.set_index("timestamp")

        # Resample to 60-second epochs
        # Use mean and round to get majority vote
        resampled = df_indexed["Sleep Score"].resample("60s").mean()

        # Round to get binary sleep/wake (>=0.5 becomes 1, <0.5 becomes 0)
        resampled_binary = (resampled >= 0.5).astype(int)

        # Also resample rolling_median for diagnostic purposes
        rolling_median_resampled = df_indexed["rolling_median"].resample("60s").mean()

        # Reset index
        result_df = pd.DataFrame(
            {
                "timestamp": resampled_binary.index,
                "Sleep Score": resampled_binary.to_numpy(),
                "z_angle_change": rolling_median_resampled.to_numpy(),
            }
        )

        # Remove any NaN values
        return result_df.dropna(subset=["Sleep Score"])

    def apply_rules(
        self,
        sleep_scores: list[int],
        sleep_start_marker: Any,
        sleep_end_marker: Any,
        timestamps: list[Any],
    ) -> tuple[int | None, int | None]:
        """
        Apply HDCZA detection to find sleep period boundaries.

        NOTE: HDCZA is a raw-data algorithm that does NOT use pre-classified
        sleep/wake scores. This method is provided for protocol compatibility
        but will raise an error - use detect_from_raw_data() instead.

        For HDCZA, the SPT boundaries are detected directly from raw accelerometer
        data using z-angle distribution analysis, not from pre-classified epochs.

        Args:
            sleep_scores: Not used by HDCZA (requires raw data instead)
            sleep_start_marker: Not used
            sleep_end_marker: Not used
            timestamps: Not used

        Returns:
            Tuple of (None, None) - use detect_from_raw_data() for actual detection

        Raises:
            NotImplementedError: HDCZA requires raw accelerometer data

        """
        msg = (
            "HDCZA requires raw accelerometer data, not pre-classified sleep/wake scores. "
            "Use the score() method with a DataFrame containing AXIS_X, AXIS_Y, AXIS_Z columns, "
            "then access spt_windows property for detected onset/offset times."
        )
        raise NotImplementedError(msg)

    def get_marker_labels(self, onset_time: str, offset_time: str) -> tuple[str, str]:
        """
        Get UI marker label text for HDCZA detection.

        Args:
            onset_time: Onset time in HH:MM format
            offset_time: Offset time in HH:MM format

        Returns:
            Tuple of (onset_label, offset_label) for display in UI

        """
        onset_label = f"SPT Onset at {onset_time}\nHDCZA (z-angle distribution)"
        offset_label = f"SPT Offset at {offset_time}\nHDCZA (z-angle distribution)"
        return onset_label, offset_label

    def score_array(
        self,
        activity_data: list[float] | np.ndarray,
        timestamps: list | None = None,
    ) -> list[int]:
        """
        Score sleep/wake from activity array (not supported for raw data algorithms).

        This method is part of the SleepScoringAlgorithm protocol but is not
        applicable to raw data algorithms. Use score() with a DataFrame instead.

        Args:
            activity_data: Not used
            timestamps: Not used

        Returns:
            Empty list

        Raises:
            NotImplementedError: This method requires DataFrame input with raw tri-axial data

        """
        msg = (
            "HDCZA algorithm requires RAW tri-axial accelerometer data. "
            "Use score() method with a DataFrame containing AXIS_X, AXIS_Y, AXIS_Z columns."
        )
        raise NotImplementedError(msg)

    def get_parameters(self) -> dict[str, Any]:
        """
        Get current algorithm parameters.

        Returns:
            Dictionary of parameter names and values

        """
        return self._parameters.copy()

    def set_parameters(self, **kwargs: Any) -> None:
        """
        Update algorithm parameters.

        Args:
            **kwargs: Parameter name-value pairs
                - angle_threshold_multiplier: float
                - percentile: float (0-100)
                - min_block_duration: int (minutes)
                - max_gap_duration: int (minutes)
                - epoch_length: int (seconds)

        Raises:
            ValueError: If parameter name is invalid or value is out of range

        """
        if "angle_threshold_multiplier" in kwargs:
            value = float(kwargs["angle_threshold_multiplier"])
            if value <= 0:
                msg = f"angle_threshold_multiplier must be positive, got {value}"
                raise ValueError(msg)
            self._angle_threshold_multiplier = value
            self._parameters["angle_threshold_multiplier"] = value

        if "percentile" in kwargs:
            value = float(kwargs["percentile"])
            if not 0 <= value <= 100:
                msg = f"percentile must be between 0 and 100, got {value}"
                raise ValueError(msg)
            self._percentile = value
            self._parameters["percentile"] = value

        if "min_block_duration" in kwargs:
            value = int(kwargs["min_block_duration"])
            if value <= 0:
                msg = f"min_block_duration must be positive, got {value}"
                raise ValueError(msg)
            self._min_block_duration = value
            self._parameters["min_block_duration"] = value

        if "max_gap_duration" in kwargs:
            value = int(kwargs["max_gap_duration"])
            if value <= 0:
                msg = f"max_gap_duration must be positive, got {value}"
                raise ValueError(msg)
            self._max_gap_duration = value
            self._parameters["max_gap_duration"] = value

        if "epoch_length" in kwargs:
            value = int(kwargs["epoch_length"])
            if value <= 0:
                msg = f"epoch_length must be positive, got {value}"
                raise ValueError(msg)
            self._epoch_length = value
            self._parameters["epoch_length"] = value

        # Warn about unknown parameters
        valid_params = {
            "angle_threshold_multiplier",
            "percentile",
            "min_block_duration",
            "max_gap_duration",
            "epoch_length",
        }
        invalid_params = set(kwargs.keys()) - valid_params
        if invalid_params:
            logger.warning(f"Unknown parameters ignored: {invalid_params}")
