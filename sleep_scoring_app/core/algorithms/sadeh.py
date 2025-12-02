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
