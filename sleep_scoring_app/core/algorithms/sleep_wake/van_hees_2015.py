"""
van Hees 2015 Sustained Inactivity Bout Detection (SIB) algorithm.

This algorithm detects sleep based on sustained periods where the z-angle
(arm angle) changes by less than a threshold amount. It was designed for
raw accelerometer data from wrist-worn devices.

Algorithm Overview:
1. Calculate z-angle from raw tri-axial acceleration (median per 5s epoch)
2. For each 5-minute window, check if z-angle changes by more than threshold
3. If change ≤ threshold for time_threshold minutes: SLEEP
4. If change > threshold: WAKE
5. Resample to 60-second epochs for consistency

This is simpler than HDCZA and serves as a baseline sleep detection algorithm
for raw accelerometer data.

References:
    van Hees VT, Sabia S, Anderson KN, et al. (2015).
    A Novel, Open Access Method to Assess Sleep Duration Using a Wrist-Worn
    Accelerometer. PLoS ONE 10(11): e0142533.
    https://doi.org/10.1371/journal.pone.0142533

    GGIR Package Implementation:
    https://cran.r-project.org/package=GGIR
    https://wadpac.github.io/GGIR/articles/chapter8_SleepFundamentalsSibs.html

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from sleep_scoring_app.core.pipeline.types import AlgorithmDataRequirement

from .z_angle import (
    calculate_z_angle_from_dataframe,
    resample_to_epochs,
    validate_raw_accelerometer_data,
)

logger = logging.getLogger(__name__)


class VanHees2015SIB:
    """
    van Hees (2015) Sustained Inactivity Bout (SIB) detection algorithm.

    This algorithm detects sleep by identifying periods where the arm angle
    (z-angle) remains relatively stable, indicating sustained inactivity.

    Key Parameters:
        - angle_threshold: Maximum z-angle change (degrees) to consider as inactive
        - time_threshold: Minimum duration (minutes) of inactivity to classify as sleep
        - epoch_length: Length of z-angle calculation window (seconds)

    The algorithm outputs sleep/wake classifications at 60-second resolution for
    consistency with other algorithms in the application.

    Example:
        >>> from sleep_scoring_app.core.algorithms import VanHees2015SIB
        >>>
        >>> # Create algorithm with default parameters
        >>> algorithm = VanHees2015SIB()
        >>>
        >>> # Score raw GT3X data
        >>> df = algorithm.score(raw_df)
        >>> df['Sleep Score']
        0    1
        1    1
        2    0
        ...

    """

    def __init__(
        self,
        angle_threshold: float = 5.0,
        time_threshold: int = 5,
        epoch_length: int = 5,
    ) -> None:
        """
        Initialize van Hees 2015 SIB algorithm.

        Args:
            angle_threshold: Maximum z-angle change (degrees) to classify as sleep.
                           Default: 5.0 degrees (as per van Hees 2015 paper)
            time_threshold: Minimum duration (minutes) of sustained inactivity.
                          Default: 5 minutes (as per van Hees 2015 paper)
            epoch_length: Length of z-angle calculation window in seconds.
                        Default: 5 seconds (as per GGIR implementation)

        """
        self._angle_threshold = angle_threshold
        self._time_threshold = time_threshold
        self._epoch_length = epoch_length

        # Store parameters for get_parameters()
        self._parameters = {
            "angle_threshold": angle_threshold,
            "time_threshold": time_threshold,
            "epoch_length": epoch_length,
        }

    @property
    def name(self) -> str:
        """Algorithm name for display."""
        return "van Hees (2015) SIB"

    @property
    def identifier(self) -> str:
        """Unique algorithm identifier."""
        return "van_hees_2015_sib"

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
        """Data requirement - Van Hees SIB requires raw tri-axial accelerometer data."""
        return AlgorithmDataRequirement.RAW_DATA

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score sleep/wake from raw tri-axial accelerometer data.

        This algorithm requires raw accelerometer data with X, Y, Z axes.
        It will NOT work with pre-aggregated epoch count data.

        Args:
            df: DataFrame with columns:
                - timestamp: datetime
                - AXIS_X: X-axis acceleration in g
                - AXIS_Y: Y-axis acceleration in g
                - AXIS_Z: Z-axis acceleration in g

        Returns:
            DataFrame with original data plus 'Sleep Score' column (1=sleep, 0=wake)
            Resampled to 60-second epochs for consistency with other algorithms.

        Raises:
            ValueError: If required columns are missing or data is not raw accelerometer data

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
            msg = (
                "van Hees 2015 SIB algorithm requires RAW tri-axial accelerometer data, "
                "not pre-aggregated epoch counts. Please load a GT3X file with raw data."
            )
            raise ValueError(msg)

        logger.info(
            f"Running van Hees 2015 SIB algorithm on {len(df)} raw samples "
            f"(angle_threshold={self._angle_threshold}°, time_threshold={self._time_threshold}min)"
        )

        # Step 1: Calculate z-angle from raw tri-axial data
        df_with_z = calculate_z_angle_from_dataframe(
            df,
            ax_col="AXIS_X",
            ay_col="AXIS_Y",
            az_col="AXIS_Z",
        )

        # Step 2: Resample to epoch_length (e.g., 5-second epochs) using median
        z_angle_epochs = resample_to_epochs(
            df_with_z,
            timestamp_col="timestamp",
            value_col="z_angle",
            epoch_seconds=self._epoch_length,
            aggregation="median",
        )

        logger.debug(f"Resampled to {len(z_angle_epochs)} {self._epoch_length}-second z-angle epochs")

        # Step 3: Calculate z-angle changes
        z_angles = z_angle_epochs["z_angle"].to_numpy()
        timestamps = z_angle_epochs["timestamp"].to_numpy()

        # Step 4: Classify sleep/wake based on z-angle stability
        sleep_scores = self._classify_sleep_wake(z_angles, timestamps)

        # Step 5: Create result DataFrame at epoch_length resolution
        result_df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "z_angle": z_angles,
                "Sleep Score": sleep_scores,
            }
        )

        # Step 6: Resample to 60-second epochs for consistency with other algorithms
        # Use majority vote: if most 5-second epochs in a 60s window are sleep, classify as sleep
        result_60s = self._resample_to_60_seconds(result_df)

        logger.info(
            f"van Hees 2015 SIB completed: {len(result_60s)} 60-second epochs, "
            f"{result_60s['Sleep Score'].sum()} sleep epochs ({result_60s['Sleep Score'].mean() * 100:.1f}%)"
        )

        return result_60s

    def _classify_sleep_wake(
        self,
        z_angles: np.ndarray,
        timestamps: np.ndarray,
    ) -> np.ndarray:
        """
        Classify each epoch as sleep or wake based on z-angle changes.

        This implements the exact GGIR HASIB vanHees2015 algorithm:
        1. Find posture changes where abs(diff(anglez)) > angle_threshold
        2. Find gaps between posture changes > time_threshold minutes
        3. Mark those gap regions as SLEEP (sustained inactivity bouts)

        Args:
            z_angles: Array of z-angle values (degrees)
            timestamps: Array of timestamps

        Returns:
            Array of sleep/wake scores (1=sleep, 0=wake)

        """
        n_epochs = len(z_angles)

        # Calculate minimum gap size in epochs
        # time_threshold is in minutes, epoch_length is in seconds
        min_gap_epochs = int(self._time_threshold * (60 / self._epoch_length))

        logger.debug(
            f"GGIR vanHees2015: angle_threshold={self._angle_threshold}°, time_threshold={self._time_threshold}min ({min_gap_epochs} epochs)"
        )

        # Initialize all as wake
        sleep_scores = np.zeros(n_epochs, dtype=int)

        # Step 1: Find posture changes (positions where abs(diff(anglez)) > threshold)
        # This matches GGIR: postch = which(abs(diff(anglez)) > j)
        z_angle_diffs = np.abs(np.diff(z_angles))
        posture_changes = np.where(z_angle_diffs > self._angle_threshold)[0]

        logger.debug(f"Found {len(posture_changes)} posture changes (z-angle diff > {self._angle_threshold}°)")

        if len(posture_changes) < 2:
            # GGIR logic: if < 10 posture changes, mark all as sleep; otherwise all wake
            if len(posture_changes) < 10:
                sleep_scores[:] = 1
                logger.debug("Few posture changes detected, marking all as sleep")
            else:
                logger.debug("Many posture changes but can't find gaps, marking all as wake")
            return sleep_scores

        # Step 2: Find gaps between consecutive posture changes > time_threshold
        # This matches GGIR: q1 = which(diff(postch) > (i * (60/epochsize)))
        gaps_between_changes = np.diff(posture_changes)
        large_gaps = np.where(gaps_between_changes > min_gap_epochs)[0]

        logger.debug(f"Found {len(large_gaps)} gaps > {self._time_threshold} minutes between posture changes")

        if len(large_gaps) == 0:
            # No sustained inactivity periods found
            logger.debug("No sustained inactivity periods found")
            return sleep_scores

        # Step 3: Mark epochs within large gaps as sleep
        # This matches GGIR: sdl1[postch[q1[gi]]:postch[q1[gi] + 1]] = 1
        for gap_idx in large_gaps:
            start_epoch = posture_changes[gap_idx]
            end_epoch = posture_changes[gap_idx + 1]
            sleep_scores[start_epoch : end_epoch + 1] = 1

        logger.debug(f"Marked {np.sum(sleep_scores)} epochs as sleep ({np.mean(sleep_scores) * 100:.1f}%)")

        return sleep_scores

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
        # Use mean and round to get majority vote (0.5 threshold)
        resampled = df_indexed["Sleep Score"].resample("60s").mean()

        # Round to get binary sleep/wake (>=0.5 becomes 1, <0.5 becomes 0)
        resampled_binary = (resampled >= 0.5).astype(int)

        # Reset index
        result_df = resampled_binary.reset_index()
        result_df.columns = ["timestamp", "Sleep Score"]

        # Remove any NaN values
        return result_df.dropna()

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
            "van Hees 2015 SIB algorithm requires RAW tri-axial accelerometer data. "
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
                - angle_threshold: float (degrees)
                - time_threshold: int (minutes)
                - epoch_length: int (seconds)

        Raises:
            ValueError: If parameter name is invalid or value is out of range

        """
        if "angle_threshold" in kwargs:
            value = float(kwargs["angle_threshold"])
            if value <= 0:
                msg = f"angle_threshold must be positive, got {value}"
                raise ValueError(msg)
            self._angle_threshold = value
            self._parameters["angle_threshold"] = value

        if "time_threshold" in kwargs:
            value = int(kwargs["time_threshold"])
            if value <= 0:
                msg = f"time_threshold must be positive, got {value}"
                raise ValueError(msg)
            self._time_threshold = value
            self._parameters["time_threshold"] = value

        if "epoch_length" in kwargs:
            value = int(kwargs["epoch_length"])
            if value <= 0:
                msg = f"epoch_length must be positive, got {value}"
                raise ValueError(msg)
            self._epoch_length = value
            self._parameters["epoch_length"] = value

        # Warn about unknown parameters
        valid_params = {"angle_threshold", "time_threshold", "epoch_length"}
        invalid_params = set(kwargs.keys()) - valid_params
        if invalid_params:
            logger.warning(f"Unknown parameters ignored: {invalid_params}")
