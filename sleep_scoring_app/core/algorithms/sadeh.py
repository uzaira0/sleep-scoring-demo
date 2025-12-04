"""
Sadeh (1994) sleep scoring algorithm - Framework-agnostic implementation.

This module implements the Sadeh algorithm for classifying minute-by-minute
activity data as sleep or wake. The implementation uses FIXED validated parameters
from the published paper and provides a simple function-based API.

References:
    Sadeh, A., Sharkey, M., & Carskadon, M. A. (1994).
    Activity-based sleep-wake identification: An empirical test of
    methodological issues. Sleep, 17(3), 201-207.

Algorithm Details:
    - Uses an 11-minute sliding window (5 previous + current + 5 future epochs)
    - Missing epochs (at data boundaries) are treated as zero
    - Activity counts are capped at 300 before processing
    - Formula: PS = 7.601 - (0.065 * AVG) - (1.08 * NATS) - (0.056 * SD) - (0.703 * LG)
    - Classification: PS > -4 = Sleep (1), otherwise Wake (0)
    - ALWAYS uses Axis1 column (hardcoded in the algorithm)

Variables:
    - AVG: Arithmetic mean of 11-minute window
    - NATS: Count of epochs with activity in range [50, 100)
    - SD: Standard deviation of forward-looking 6-epoch window (ActiLife compatible)
    - LG: Natural logarithm of (current epoch + 1)

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from sleep_scoring_app.core.algorithms.utils import find_datetime_column, validate_and_collapse_epochs

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

WINDOW_SIZE: int = 11
ACTIVITY_CAP: int = 300
# THRESHOLD is now a parameter instead of constant (default -4.0 for ActiLife, 0.0 for original paper)
NATS_MIN: int = 50
NATS_MAX: int = 100

COEFFICIENT_A: float = 7.601
COEFFICIENT_B: float = 0.065
COEFFICIENT_C: float = 1.08
COEFFICIENT_D: float = 0.056
COEFFICIENT_E: float = 0.703


def sadeh_score(df: pd.DataFrame, threshold: float = -4.0) -> pd.DataFrame:
    """
    Apply Sadeh (1994) sleep scoring algorithm to activity data.

    Uses FIXED validated parameters from the published paper:
    - Window size: 11 minutes
    - Activity cap: 300 counts
    - Threshold: Configurable (default -4.0 for ActiLife, 0.0 for original paper)
    - NATS range: 50-100 counts
    - Activity column: ALWAYS Axis1 (hardcoded in algorithm)

    Note: ActiLife implementation uses threshold of -4.0, while the original
    Sadeh (1994) paper uses threshold of 0.0. Default is -4.0 for backward
    compatibility with ActiLife.

    The algorithm uses an 11-minute sliding window to calculate sleep/wake
    classifications. This is a validated research algorithm with parameters
    that should not be modified.

    Args:
        df: DataFrame with datetime column and 'Axis1' activity column

    Returns:
        Original DataFrame with new 'Sadeh Score' column appended (1=sleep, 0=wake)

    Raises:
        ValueError: If epochs are larger than 1 minute or required columns missing

    Validation:
        - Finds datetime/date+time columns automatically
        - Verifies 1-minute epochs (±1 second tolerance)
        - Collapses to 1-minute if epochs < 1 minute
        - Raises error if epochs > 1 minute

    Example:
        >>> import pandas as pd
        >>> from sleep_scoring_app.core.algorithms import sadeh_score
        >>> df = pd.read_csv('activity.csv')
        >>> df.head()
           datetime             Axis1
        0  2024-01-01 00:00:00  45
        1  2024-01-01 00:01:00  32
        2  2024-01-01 00:02:00  0
        >>> df = sadeh_score(df)
        >>> df.head()
           datetime             Axis1  Sadeh Score
        0  2024-01-01 00:00:00  45     1
        1  2024-01-01 00:01:00  32     1
        2  2024-01-01 00:02:00  0      0

    """
    if df is None or len(df) == 0:
        msg = "DataFrame cannot be None or empty"
        raise ValueError(msg)

    datetime_col = find_datetime_column(df)

    df = validate_and_collapse_epochs(df, datetime_col)

    if "Axis1" not in df.columns:
        msg = "DataFrame must contain 'Axis1' column. Sadeh algorithm ALWAYS uses Axis1."
        raise ValueError(msg)

    activity_data = df["Axis1"].to_numpy(dtype=np.float64)

    if np.any(np.isnan(activity_data)):
        msg = "Axis1 column contains NaN (Not a Number) values"
        raise ValueError(msg)

    if np.any(np.isinf(activity_data)):
        msg = "Axis1 column contains infinite values"
        raise ValueError(msg)

    if np.any(activity_data < 0):
        negative_indices = np.where(activity_data < 0)[0]
        msg = f"Axis1 column contains negative values at indices: {negative_indices[:10].tolist()}"
        raise ValueError(msg)

    logger.debug(f"Running Sadeh algorithm on {len(activity_data)} epochs")

    capped_activity = np.minimum(activity_data, ACTIVITY_CAP)

    sleep_wake_scores = np.zeros(len(capped_activity), dtype=int)

    padded_activity = np.pad(capped_activity, pad_width=5, mode="constant", constant_values=0)

    logger.info("SADEH ALGORITHM: Using FORWARD ROLLING STD (6-epoch window, ddof=1) - ActiLife compatible")
    rolling_sds = np.zeros(len(capped_activity))
    for i in range(len(capped_activity)):
        sd_window = padded_activity[i : i + 6]
        if len(sd_window) >= 2:
            rolling_sds[i] = np.std(sd_window, ddof=1)
        else:
            rolling_sds[i] = 0.0

    for i in range(len(capped_activity)):
        window_start = i
        window_end = i + WINDOW_SIZE
        window = padded_activity[window_start:window_end]

        avg = np.mean(window)

        nats = np.sum((window >= NATS_MIN) & (window < NATS_MAX))

        sd = rolling_sds[i]

        current_count = capped_activity[i]
        lg = np.log(current_count + 1)

        ps = COEFFICIENT_A - (COEFFICIENT_B * avg) - (COEFFICIENT_C * nats) - (COEFFICIENT_D * sd) - (COEFFICIENT_E * lg)

        sleep_wake_scores[i] = 1 if ps > threshold else 0

    logger.debug(f"Sadeh algorithm completed successfully for {len(capped_activity)} epochs")

    result_df = df.copy()
    result_df["Sadeh Score"] = sleep_wake_scores

    return result_df


def score_activity(activity_data: list[float] | np.ndarray, threshold: float = -4.0) -> list[int]:
    """
    Legacy convenience function for backwards compatibility.

    DEPRECATED: This function maintains the old list-based API for backwards compatibility.
    New code should use sadeh_score() with DataFrame input instead.

    Args:
        activity_data: List or array of Axis1 activity count values

    Returns:
        List of sleep/wake classifications (1=sleep, 0=wake)

    Example:
        >>> from sleep_scoring_app.core.algorithms import score_activity
        >>> activity_counts = [45, 32, 0, 12, 5, ...]
        >>> sleep_scores = score_activity(activity_counts)
        >>> sleep_scores
        [1, 1, 0, 1, 1, ...]

    """
    if activity_data is None:
        msg = "activity_data cannot be None"
        raise ValueError(msg)

    if len(activity_data) == 0:
        logger.debug("Empty activity_data provided to Sadeh algorithm")
        return []

    try:
        activity_array = np.array(activity_data, dtype=np.float64)
    except (ValueError, TypeError) as e:
        msg = f"activity_data contains non-numeric values: {e}"
        raise ValueError(msg) from e

    if np.any(np.isnan(activity_array)):
        msg = "activity_data contains NaN (Not a Number) values"
        raise ValueError(msg)

    if np.any(np.isinf(activity_array)):
        msg = "activity_data contains infinite values"
        raise ValueError(msg)

    if np.any(activity_array < 0):
        negative_indices = np.where(activity_array < 0)[0]
        msg = f"activity_data contains negative values at indices: {negative_indices[:10].tolist()}"
        raise ValueError(msg)

    logger.debug(f"Running Sadeh algorithm on {len(activity_array)} epochs")

    capped_activity = np.minimum(activity_array, ACTIVITY_CAP)

    sleep_wake_scores = np.zeros(len(capped_activity), dtype=int)

    padded_activity = np.pad(capped_activity, pad_width=5, mode="constant", constant_values=0)

    logger.info("SADEH ALGORITHM: Using FORWARD ROLLING STD (6-epoch window, ddof=1) - ActiLife compatible")
    rolling_sds = np.zeros(len(capped_activity))
    for i in range(len(capped_activity)):
        sd_window = padded_activity[i : i + 6]
        if len(sd_window) >= 2:
            rolling_sds[i] = np.std(sd_window, ddof=1)
        else:
            rolling_sds[i] = 0.0

    for i in range(len(capped_activity)):
        window_start = i
        window_end = i + WINDOW_SIZE
        window = padded_activity[window_start:window_end]

        avg = np.mean(window)
        nats = np.sum((window >= NATS_MIN) & (window < NATS_MAX))
        sd = rolling_sds[i]
        current_count = capped_activity[i]
        lg = np.log(current_count + 1)

        ps = COEFFICIENT_A - (COEFFICIENT_B * avg) - (COEFFICIENT_C * nats) - (COEFFICIENT_D * sd) - (COEFFICIENT_E * lg)

        sleep_wake_scores[i] = 1 if ps > threshold else 0

    logger.debug(f"Sadeh algorithm completed successfully for {len(capped_activity)} epochs")

    return sleep_wake_scores.tolist()


class SadehAlgorithm:
    """
    Sadeh (1994) sleep scoring algorithm - Protocol implementation.

    This class implements the SleepScoringAlgorithm protocol for dependency injection.
    The original function-based API (sadeh_score, score_activity) is preserved for
    backward compatibility.

    The Sadeh algorithm uses an 11-minute sliding window to classify each epoch
    as sleep or wake based on activity counts. It ALWAYS uses the vertical axis
    (Axis1/axis_y) regardless of configuration.

    Two variants are supported:
        - Original (threshold=0.0): As published in Sadeh et al. (1994)
        - ActiLife (threshold=-4.0): As implemented in ActiGraph's ActiLife software

    Parameters:
        threshold: Sleep/wake classification threshold
            - 0.0: Original Sadeh (1994) paper threshold
            - -4.0: ActiLife software threshold (default)
        variant_name: Optional variant name override for display/identifier

    Example:
        >>> from sleep_scoring_app.core.algorithms import SadehAlgorithm
        >>>
        >>> # Create with ActiLife threshold (default)
        >>> algorithm = SadehAlgorithm()
        >>>
        >>> # Create with original paper threshold
        >>> algorithm = SadehAlgorithm(threshold=0.0, variant_name="original")
        >>>
        >>> # Score DataFrame
        >>> df = algorithm.score(activity_df)
        >>>
        >>> # Score array (legacy API)
        >>> scores = algorithm.score_array(activity_counts)

    References:
        Sadeh, A., Sharkey, M., & Carskadon, M. A. (1994).
        Activity-based sleep-wake identification: An empirical test of
        methodological issues. Sleep, 17(3), 201-207.

    """

    def __init__(self, threshold: float = -4.0, variant_name: str | None = None) -> None:
        """
        Initialize Sadeh algorithm with configurable threshold.

        Args:
            threshold: Sleep/wake classification threshold
                - 0.0: Original Sadeh (1994) paper threshold
                - -4.0: ActiLife software threshold (default)
            variant_name: Optional variant name ("original" or "actilife") for display/identifier.
                         If None, inferred from threshold value.

        """
        self._threshold = threshold
        self._variant_name = variant_name
        self._parameters = {
            "threshold": threshold,
            "window_size": WINDOW_SIZE,
            "activity_cap": ACTIVITY_CAP,
            "nats_min": NATS_MIN,
            "nats_max": NATS_MAX,
        }

    @property
    def name(self) -> str:
        """Algorithm name for display."""
        if self._variant_name == "original" or self._threshold == 0.0:
            return "Sadeh (1994) Original"
        return "Sadeh (1994) ActiLife"

    @property
    def identifier(self) -> str:
        """Unique algorithm identifier."""
        if self._variant_name == "original" or self._threshold == 0.0:
            return "sadeh_1994_original"
        return "sadeh_1994_actilife"

    @property
    def requires_axis(self) -> str:
        """Required accelerometer axis - always axis_y (vertical) for Sadeh."""
        return "axis_y"

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score sleep/wake using Sadeh algorithm.

        Args:
            df: DataFrame with datetime column and 'Axis1' activity column

        Returns:
            Original DataFrame with added 'Sleep Score' column (1=sleep, 0=wake)

        """
        return sadeh_score(df, threshold=self._threshold)

    def score_array(
        self,
        activity_data: list[float] | np.ndarray,
        timestamps: list | None = None,
    ) -> list[int]:
        """
        Score sleep/wake from array (legacy API).

        Args:
            activity_data: List or array of activity count values
            timestamps: Optional list of timestamps (for validation, not used)

        Returns:
            List of sleep/wake classifications (1=sleep, 0=wake)

        """
        return score_activity(activity_data, threshold=self._threshold)

    def get_parameters(self) -> dict[str, float | int]:
        """
        Get current algorithm parameters.

        Returns:
            Dictionary of parameter names and values

        """
        return self._parameters.copy()

    def set_parameters(self, **kwargs: float) -> None:
        """
        Update algorithm parameters.

        Only 'threshold' is configurable for Sadeh. Other parameters are
        validated constants from the published paper and cannot be changed.

        Args:
            **kwargs: Parameter name-value pairs (only 'threshold' accepted)

        """
        if "threshold" in kwargs:
            self._threshold = float(kwargs["threshold"])
            self._parameters["threshold"] = self._threshold

        # Warn about ignored parameters (they're validated constants)
        invalid_params = set(kwargs.keys()) - {"threshold"}
        if invalid_params:
            logger.warning(
                "Sadeh algorithm parameters %s cannot be changed. They are validated constants from the published paper.",
                invalid_params,
            )
