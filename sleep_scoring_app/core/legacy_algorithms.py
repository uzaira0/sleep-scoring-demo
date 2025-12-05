"""
LEGACY facade for sleep scoring algorithms - FULLY DEPRECATED.

⚠️ DEPRECATION WARNING:
    - run_sadeh_algorithm() is DEPRECATED - Use AlgorithmFactory and SleepScoringAlgorithm protocol instead
    - run_choi_algorithm() is DEPRECATED - Use NonwearAlgorithmFactory and NonwearDetectionAlgorithm protocol instead
    - ChoiNonwearDetector is DEPRECATED - Use NonwearAlgorithmFactory.create("choi_2011") instead

This module provides high-level wrapper classes that combine validation, error handling,
and type conversion for the framework-agnostic algorithm implementations in the
algorithms/ subpackage.

Architecture:
    - Core algorithms in algorithms/ subpackage are pure functions (sadeh.py, choi.py)
    - This facade provides object-oriented wrappers with comprehensive validation
    - Handles list<->DataFrame conversion, input validation, and error messages
    - LEGACY: Used for Choi nonwear detection until Choi gets proper DI implementation

Classes:
    SleepScoringAlgorithms: PARTIALLY DEPRECATED facade (Sadeh methods deprecated, Choi methods active)
    ChoiNonwearDetector: Pandas-based wrapper for detailed nonwear analysis (active)

NEW CODE SHOULD USE:
    from sleep_scoring_app.core.algorithms import AlgorithmFactory, NonwearAlgorithmFactory

    # For sleep scoring (Sadeh, Cole-Kripke, etc.)
    algorithm = AlgorithmFactory.create('sadeh_1994_actilife')
    results = algorithm.score_array(counts, timestamps)

    # For nonwear detection (Choi, van Hees, etc.)
    nonwear_algorithm = NonwearAlgorithmFactory.create('choi_2011')
    periods = nonwear_algorithm.detect(counts, times)

LEGACY USAGE (DEPRECATED for Sadeh):
    algorithms = SleepScoringAlgorithms()
    sadeh_results = algorithms.run_sadeh_algorithm(counts, times, threshold=-4.0)  # DEPRECATED
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from sleep_scoring_app.core.algorithms.choi import detect_nonwear as _detect_nonwear_new
from sleep_scoring_app.core.algorithms.onset_offset_factory import OnsetOffsetRuleFactory
from sleep_scoring_app.core.algorithms.sadeh import score_activity as _score_activity_new
from sleep_scoring_app.core.algorithms.sleep_rules import SleepRules as _SleepRulesNew
from sleep_scoring_app.core.exceptions import ErrorCodes, ValidationError

if TYPE_CHECKING:
    from sleep_scoring_app.core.algorithms.onset_offset_protocol import OnsetOffsetRule

logger = logging.getLogger(__name__)


class ChoiNonwearDetector:
    """
    DEPRECATED: Pandas-based wrapper for Choi nonwear detection algorithm.

    ⚠️ DEPRECATED: This class is deprecated and will be removed in a future version.

    NEW CODE SHOULD USE:
        from sleep_scoring_app.core.algorithms import NonwearAlgorithmFactory
        algorithm = NonwearAlgorithmFactory.create('choi_2011')
        periods = algorithm.detect(activity_data, timestamps)

    This class provides a convenient interface for nonwear detection from pandas DataFrames
    with flexible column naming and summary statistics generation. It delegates to the
    framework-agnostic implementation while providing a DataFrame-oriented API.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        count_column: str = "axis_y",
        timestamp_column: str = "datetime",
        participant_code: str | None = None,
        use_vector_magnitude: bool = False,
    ) -> None:
        """
        Initialize with pandas DataFrame (legacy API).

        ⚠️ DEPRECATED: Use NonwearAlgorithmFactory.create('choi_2011') instead.

        Args:
            data: DataFrame containing accelerometer counts data
            count_column: Name of the column containing activity counts
            timestamp_column: Name of the column containing timestamps
            participant_code: Participant identifier
            use_vector_magnitude: Whether to use vector magnitude for detection

        """
        import warnings

        warnings.warn(
            "ChoiNonwearDetector is deprecated. Use NonwearAlgorithmFactory.create('choi_2011') instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        self.data = data.copy()
        self.count_column = count_column
        self.timestamp_column = timestamp_column
        self.participant_code = participant_code or "unknown"
        self.use_vector_magnitude = use_vector_magnitude

    def _validate_interval(self) -> None:
        """Legacy method - now handled by new implementation."""
        pass

    def detect_nonwear_choi_algorithm(
        self,
        min_period_length: int = 90,
        spike_tolerance: int = 2,
        small_window_length: int = 30,
    ) -> list[tuple[datetime, datetime]]:
        """
        Detect nonwear periods (legacy API).

        Args:
            min_period_length: Minimum length for nonwear period (default 90 minutes)
            spike_tolerance: Maximum allowed consecutive non-zero minutes (default 2)
            small_window_length: Window size to check around spikes (default 30 minutes)

        Returns:
            List of (start_time, end_time) tuples for nonwear periods

        """
        if min_period_length != 90 or spike_tolerance != 2 or small_window_length != 30:
            logger.warning(
                "Choi algorithm parameters are now FIXED to validated values from the published paper. "
                f"Requested parameters (min_period={min_period_length}, spike_tolerance={spike_tolerance}, "
                f"window={small_window_length}) will be ignored. Using validated defaults: "
                "min_period=90, spike_tolerance=2, window=30"
            )

        periods = _detect_nonwear_new(
            activity_data=self.data[self.count_column].tolist(),
            timestamps=self.data[self.timestamp_column].tolist(),
        )

        return [(period.start_time, period.end_time) for period in periods]

    def _merge_adjacent_periods(self, periods: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
        """Legacy method - now handled internally by new implementation."""
        return periods

    def create_nonwear_summary(self, nonwear_periods: list[tuple[datetime, datetime]]) -> dict[str, Any]:
        """
        Create summary statistics (legacy API).

        Args:
            nonwear_periods: List of (start_time, end_time) tuples

        Returns:
            Dictionary with nonwear summary statistics

        """
        if not nonwear_periods:
            return {
                "participant_code": self.participant_code,
                "total_nonwear_periods": 0,
                "total_nonwear_minutes": 0,
                "total_wear_minutes": len(self.data),
                "wear_percentage": 100.0,
                "nonwear_periods": [],
            }

        total_nonwear_minutes = sum(int((end - start).total_seconds() / 60) + 1 for start, end in nonwear_periods)
        total_minutes = len(self.data)
        wear_minutes = total_minutes - total_nonwear_minutes
        wear_percentage = (wear_minutes / total_minutes * 100) if total_minutes > 0 else 0

        return {
            "participant_code": self.participant_code,
            "total_nonwear_periods": len(nonwear_periods),
            "total_nonwear_minutes": int(total_nonwear_minutes),
            "total_wear_minutes": int(wear_minutes),
            "wear_percentage": round(wear_percentage, 2),
            "nonwear_periods": [
                {
                    "start_time": start,
                    "end_time": end,
                    "duration_minutes": int((end - start).total_seconds() / 60) + 1,
                }
                for start, end in nonwear_periods
            ],
        }


class SleepScoringAlgorithms:
    """
    FULLY DEPRECATED facade for sleep scoring and nonwear detection algorithms.

    ⚠️ DEPRECATION WARNING:
        - run_sadeh_algorithm() is DEPRECATED - Use AlgorithmFactory.create() instead
        - apply_sleep_scoring_rules() is DEPRECATED - Use OnsetOffsetRuleFactory.create() instead
        - run_choi_algorithm() is DEPRECATED - Use NonwearAlgorithmFactory.create() instead

    This class provides a unified interface for running algorithms with comprehensive
    validation, error handling, and parameter management. Designed for use in GUI
    contexts where user input validation and clear error messages are essential.

    Key Features:
        - Comprehensive input validation with ValidationError exceptions
        - Automatic type conversion (list/array/DataFrame)
        - Parameter flow-through (activity_column for Choi)
        - Consistent error handling across algorithms

    DEPRECATED Methods:
        run_sadeh_algorithm: DEPRECATED - Use AlgorithmFactory and SleepScoringAlgorithm protocol
        apply_sleep_scoring_rules: DEPRECATED - Use OnsetOffsetRuleFactory and OnsetOffsetRule protocol
        run_choi_algorithm: DEPRECATED - Use NonwearAlgorithmFactory and NonwearDetectionAlgorithm protocol

    """

    def __init__(self) -> None:
        pass

    def run_choi_algorithm(
        self,
        activity_data,
        timestamps=None,
        min_period_length=90,
        spike_tolerance=2,
        small_window_length=30,
        use_vector_magnitude=False,
        activity_column="axis_y",
    ) -> list[dict[str, int]]:
        """
        DEPRECATED: Run research-grade Choi nonwear detection algorithm.

        ⚠️ DEPRECATED: This method is deprecated and will be removed in a future version.

        NEW CODE SHOULD USE:
            from sleep_scoring_app.core.algorithms import NonwearAlgorithmFactory
            algorithm = NonwearAlgorithmFactory.create('choi_2011')
            periods = algorithm.detect(activity_data, timestamps)

        """
        import warnings

        warnings.warn(
            "run_choi_algorithm() is deprecated. Use NonwearAlgorithmFactory.create('choi_2011') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if timestamps is None:
            timestamps = [datetime.now() + timedelta(minutes=i) for i in range(len(activity_data))]

        data = pd.DataFrame({activity_column: activity_data, "datetime": timestamps})

        detector = ChoiNonwearDetector(
            data=data,
            count_column=activity_column,
            timestamp_column="datetime",
            participant_code="unknown",
            use_vector_magnitude=use_vector_magnitude,
        )

        nonwear_periods = detector.detect_nonwear_choi_algorithm(
            min_period_length=min_period_length,
            spike_tolerance=spike_tolerance,
            small_window_length=small_window_length,
        )

        legacy_periods = []
        for start_time, end_time in nonwear_periods:
            start_idx = None
            end_idx = None
            for i, timestamp in enumerate(timestamps):
                if start_idx is None and timestamp >= start_time:
                    start_idx = i
                if timestamp <= end_time:
                    end_idx = i

            if start_idx is not None and end_idx is not None:
                duration_minutes = end_idx - start_idx + 1
                legacy_periods.append(
                    {
                        "start_index": start_idx,
                        "end_index": end_idx,
                        "duration_minutes": duration_minutes,
                    },
                )

        return legacy_periods

    def run_sadeh_algorithm(self, axis_y_data, timestamps, threshold: float = -4.0) -> list[int]:
        """
        DEPRECATED: Run Sadeh sleep scoring algorithm with comprehensive validation.

        ⚠️ DEPRECATED: This method is deprecated and will be removed in a future version.

        NEW CODE SHOULD USE:
            from sleep_scoring_app.core.algorithms import AlgorithmFactory
            algorithm = AlgorithmFactory.create('sadeh_1994_actilife')  # or 'sadeh_1994_original'
            results = algorithm.score_array(axis_y_data, timestamps)

        This method provides a validated interface to the Sadeh (1994) algorithm with
        extensive input validation and error handling.

        Args:
            axis_y_data: List or array of numeric activity count values (Y-axis/vertical)
            timestamps: List of timestamps (for validation, must match data length)
            threshold: Sleep/wake classification threshold.
                - 0.0: Original Sadeh (1994) paper threshold
                - -4.0: ActiLife software threshold (default)

        Returns:
            List of sleep/wake classifications (1=sleep, 0=wake)

        Raises:
            ValidationError: If input data is invalid or malformed

        """
        import warnings

        warnings.warn(
            "run_sadeh_algorithm() is deprecated. Use AlgorithmFactory.create('sadeh_1994_actilife') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if axis_y_data is None:
            msg = "axis_y_data cannot be None"
            raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

        if len(axis_y_data) == 0:
            logger.debug("Empty axis_y_data provided to Sadeh algorithm")
            return []

        if not hasattr(axis_y_data, "__len__") or not hasattr(axis_y_data, "__getitem__"):
            msg = f"axis_y_data must be a list or array-like object, got {type(axis_y_data)}"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        data_length = len(axis_y_data)
        if data_length > 1000000:
            msg = f"axis_y_data too large: {data_length} epochs. Maximum allowed: 1,000,000"
            raise ValidationError(msg, ErrorCodes.OUT_OF_RANGE)

        try:
            activity_array = np.array(axis_y_data, dtype=np.float64)
        except (ValueError, TypeError) as e:
            msg = f"axis_y_data contains non-numeric values: {e}"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT) from e

        if np.any(np.isnan(activity_array)):
            msg = "axis_y_data contains NaN (Not a Number) values"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        if np.any(np.isinf(activity_array)):
            msg = "axis_y_data contains infinite values"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        if np.any(activity_array < 0):
            negative_indices = np.where(activity_array < 0)[0]
            msg = f"axis_y_data contains negative values at indices: {negative_indices[:10].tolist()}"
            raise ValidationError(msg, ErrorCodes.OUT_OF_RANGE)

        if timestamps is not None:
            if len(timestamps) != data_length:
                msg = f"timestamps length ({len(timestamps)}) must match axis_y_data length ({data_length})"
                raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        logger.debug(f"Running Sadeh algorithm on {data_length} epochs")

        try:
            return _score_activity_new(axis_y_data, threshold=threshold)
        except ValueError as e:
            msg = str(e)
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT) from e
        except RuntimeError as e:
            msg = str(e)
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT) from e

    def apply_sleep_scoring_rules(
        self,
        sleep_markers,
        sadeh_results,
        x_data,
        onset_offset_rule: OnsetOffsetRule | None = None,
    ) -> tuple[int | None, int | None]:
        """
        DEPRECATED: Apply sleep onset/offset rules to find actual sleep boundaries.

        ⚠️ DEPRECATED: This method is deprecated and will be removed in a future version.

        NEW CODE SHOULD USE:
            from sleep_scoring_app.core.algorithms.onset_offset_factory import OnsetOffsetRuleFactory
            rule = OnsetOffsetRuleFactory.create('consecutive_3_5')  # or other rule ID
            onset_idx, offset_idx = rule.apply_rules(sleep_scores, sleep_start_marker, sleep_end_marker, timestamps)

        Uses the configured onset/offset rule and user-placed markers to identify
        the precise onset and offset times from sleep scoring results.

        Args:
            sleep_markers: List of 2 datetime markers (start, end)
            sadeh_results: List of sleep/wake classifications (1=sleep, 0=wake)
            x_data: List of timestamps corresponding to sadeh_results
            onset_offset_rule: Optional rule instance (defaults to Consecutive 3/5 if None)

        Returns:
            Tuple of (onset_index, offset_index), or (None, None) if not found

        """
        import warnings

        warnings.warn(
            "apply_sleep_scoring_rules() is deprecated. Use OnsetOffsetRuleFactory.create() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if len(sleep_markers) != 2 or not sadeh_results:
            return None, None

        sorted_markers = sorted(sleep_markers)
        sleep_start_time = sorted_markers[0]
        sleep_end_time = sorted_markers[1]

        # Use provided rule or create default
        if onset_offset_rule is None:
            onset_offset_rule = OnsetOffsetRuleFactory.create(OnsetOffsetRuleFactory.get_default_rule_id())

        return onset_offset_rule.apply_rules(
            sleep_scores=sadeh_results,
            sleep_start_marker=sleep_start_time,
            sleep_end_marker=sleep_end_time,
            timestamps=x_data,
        )
