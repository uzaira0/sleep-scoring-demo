"""
Choi (2011) nonwear detection algorithm - Framework-agnostic implementation.

This module implements the Choi algorithm for detecting periods when an accelerometer
is not being worn. The implementation uses FIXED validated parameters from the published
paper and provides a simple function-based API.

References:
    Choi, L., Liu, Z., Matthews, C. E., & Buchowski, M. S. (2011).
    Validation of accelerometer wear and nonwear time classification algorithm.
    Medicine and Science in Sports and Exercise, 43(2), 357-364.

Algorithm Details:
    - Identifies consecutive zero-count periods as potential nonwear
    - Allows small spikes (≤2 minutes) within larger zero periods
    - Validates minimum period length (default: 90 minutes)
    - Merges adjacent/overlapping periods
    - Can use single axis or vector magnitude (specified via ActivityColumn enum)

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from sleep_scoring_app.core.algorithms.types import ActivityColumn
from sleep_scoring_app.core.algorithms.utils import find_datetime_column, validate_and_collapse_epochs
from sleep_scoring_app.core.constants import NonwearDataSource
from sleep_scoring_app.core.dataclasses import NonwearPeriod

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)

MIN_PERIOD_LENGTH: int = 90
SPIKE_TOLERANCE: int = 2
WINDOW_SIZE: int = 30


def _merge_adjacent_periods(periods: list[NonwearPeriod]) -> list[NonwearPeriod]:
    """
    Merge adjacent or overlapping nonwear periods.

    Args:
        periods: List of NonwearPeriod objects

    Returns:
        List of merged NonwearPeriod objects

    """
    if not periods:
        return periods

    periods.sort(key=lambda x: x.start_time)

    merged_periods: list[NonwearPeriod] = []
    current = periods[0]

    for next_period in periods[1:]:
        if (next_period.start_time - current.end_time).total_seconds() <= 60:
            current = NonwearPeriod(
                start_time=current.start_time,
                end_time=max(current.end_time, next_period.end_time),
                participant_id=current.participant_id,
                source=current.source,
                duration_minutes=max(current.end_index, next_period.end_index) - current.start_index + 1,
                start_index=current.start_index,
                end_index=max(current.end_index, next_period.end_index),
            )
        else:
            merged_periods.append(current)
            current = next_period

    merged_periods.append(current)

    return merged_periods


def choi_detect_nonwear(
    df: pd.DataFrame,
    activity_column: ActivityColumn = ActivityColumn.VECTOR_MAGNITUDE,
) -> pd.DataFrame:
    """
    Apply Choi (2011) nonwear detection algorithm.

    Uses FIXED validated parameters from the published paper:
    - Minimum period: 90 minutes
    - Spike tolerance: 2 minutes
    - Window size: 30 minutes

    The algorithm detects periods when the accelerometer is not being worn by
    identifying extended intervals of zero or near-zero activity. This is a
    validated research algorithm with parameters that should not be modified.

    Args:
        df: DataFrame with datetime and activity columns
        activity_column: Which activity column to use (VECTOR_MAGNITUDE recommended, or AXIS_Y)

    Returns:
        Original DataFrame with new 'Choi Nonwear' column appended (1=nonwear, 0=wear)

    Raises:
        ValueError: If epochs are larger than 1 minute or required columns missing

    Validation:
        - Finds datetime/date+time columns automatically
        - Verifies 1-minute epochs (±1 second tolerance)
        - Collapses to 1-minute if epochs < 1 minute
        - Raises error if epochs > 1 minute

    Example:
        >>> import pandas as pd
        >>> from sleep_scoring_app.core.algorithms import choi_detect_nonwear, ActivityColumn
        >>> df = pd.read_csv('activity.csv')
        >>> df.head()
           datetime             Axis1  Vector Magnitude
        0  2024-01-01 00:00:00  45     52.3
        1  2024-01-01 00:01:00  32     38.1
        2  2024-01-01 00:02:00  0      0.0
        >>> df = choi_detect_nonwear(df, ActivityColumn.VECTOR_MAGNITUDE)
        >>> df.head()
           datetime             Axis1  Vector Magnitude  Choi Nonwear
        0  2024-01-01 00:00:00  45     52.3              0
        1  2024-01-01 00:01:00  32     38.1              0
        2  2024-01-01 00:02:00  0      0.0               1

    """
    if df is None or len(df) == 0:
        msg = "DataFrame cannot be None or empty"
        raise ValueError(msg)

    datetime_col = find_datetime_column(df)

    df = validate_and_collapse_epochs(df, datetime_col)

    column_name = activity_column.value
    if column_name not in df.columns:
        msg = f"DataFrame must contain '{column_name}' column. Available columns: {df.columns.tolist()}"
        raise ValueError(msg)

    counts = df[column_name].to_numpy()
    timestamps = df[datetime_col].to_numpy()

    if len(counts) == 0:
        result_df = df.copy()
        result_df["Choi Nonwear"] = []
        return result_df

    nonwear_periods: list[NonwearPeriod] = []
    i = 0

    while i < len(counts):
        if counts[i] > 0:
            i += 1
            continue

        start_idx = i
        end_idx = i

        nonwear_continuation = i

        while nonwear_continuation < len(counts):
            if counts[nonwear_continuation] == 0:
                end_idx = nonwear_continuation
                nonwear_continuation += 1
                continue

            window_start = max(0, nonwear_continuation - WINDOW_SIZE)
            window_end = min(len(counts), nonwear_continuation + WINDOW_SIZE)

            if window_end - window_start > 1000000:
                logger.warning(f"Window size too large: {window_end - window_start}, limiting to 1000000")
                window_end = window_start + 1000000

            nonzero_count = np.sum(counts[window_start:window_end] > 0)

            if nonzero_count > SPIKE_TOLERANCE:
                break

            nonwear_continuation += 1

        if end_idx - start_idx + 1 >= MIN_PERIOD_LENGTH:
            start_time = pd.to_datetime(timestamps[start_idx])
            end_time = pd.to_datetime(timestamps[end_idx])
            period = NonwearPeriod(
                start_time=start_time,
                end_time=end_time,
                participant_id="",
                source=NonwearDataSource.CHOI_ALGORITHM,
                duration_minutes=end_idx - start_idx + 1,
                start_index=start_idx,
                end_index=end_idx,
            )
            nonwear_periods.append(period)
            i = end_idx + 1
        else:
            i += 1

    merged_periods = _merge_adjacent_periods(nonwear_periods)

    nonwear_mask = np.zeros(len(df), dtype=int)
    for period in merged_periods:
        nonwear_mask[period.start_index : period.end_index + 1] = 1

    result_df = df.copy()
    result_df["Choi Nonwear"] = nonwear_mask

    return result_df


def detect_nonwear(
    activity_data: list[float] | np.ndarray,
    timestamps: list[datetime],
) -> list[NonwearPeriod]:
    """
    Legacy convenience function for backwards compatibility.

    DEPRECATED: This function maintains the old list-based API for backwards compatibility.
    New code should use choi_detect_nonwear() with DataFrame input instead.

    Args:
        activity_data: Array/list of activity count values
        timestamps: List of datetime objects for each data point

    Returns:
        List of NonwearPeriod objects

    Example:
        >>> from sleep_scoring_app.core.algorithms import detect_nonwear
        >>> from datetime import datetime, timedelta
        >>> activity_counts = [0, 0, 0, ...]
        >>> timestamps = [datetime(2024, 1, 1) + timedelta(minutes=i) for i in range(len(activity_counts))]
        >>> periods = detect_nonwear(activity_counts, timestamps)
        >>> for period in periods:
        ...     print(f"Nonwear: {period.start_time} to {period.end_time}")

    """
    if activity_data is None or timestamps is None:
        msg = "activity_data and timestamps cannot be None"
        raise ValueError(msg)

    if len(activity_data) != len(timestamps):
        msg = f"activity_data length ({len(activity_data)}) must match timestamps length ({len(timestamps)})"
        raise ValueError(msg)

    if len(activity_data) == 0:
        return []

    counts = np.array(activity_data, dtype=np.float64)

    if np.any(np.isnan(counts)):
        msg = "activity_data contains NaN (Not a Number) values"
        raise ValueError(msg)

    if np.any(np.isinf(counts)):
        msg = "activity_data contains infinite values"
        raise ValueError(msg)

    if np.any(counts < 0):
        negative_indices = np.where(counts < 0)[0]
        msg = f"activity_data contains negative values at indices: {negative_indices[:10].tolist()}"
        raise ValueError(msg)

    logger.debug(f"Running Choi algorithm on {len(counts)} epochs")

    nonwear_periods: list[NonwearPeriod] = []
    i = 0

    while i < len(counts):
        if counts[i] > 0:
            i += 1
            continue

        start_idx = i
        end_idx = i

        nonwear_continuation = i

        while nonwear_continuation < len(counts):
            if counts[nonwear_continuation] == 0:
                end_idx = nonwear_continuation
                nonwear_continuation += 1
                continue

            window_start = max(0, nonwear_continuation - WINDOW_SIZE)
            window_end = min(len(counts), nonwear_continuation + WINDOW_SIZE)

            if window_end - window_start > 1000000:
                logger.warning(f"Window size too large: {window_end - window_start}, limiting to 1000000")
                window_end = window_start + 1000000

            nonzero_count = np.sum(counts[window_start:window_end] > 0)

            if nonzero_count > SPIKE_TOLERANCE:
                break

            nonwear_continuation += 1

        if end_idx - start_idx + 1 >= MIN_PERIOD_LENGTH:
            start_time = timestamps[start_idx]
            end_time = timestamps[end_idx]
            period = NonwearPeriod(
                start_time=start_time,
                end_time=end_time,
                participant_id="",
                source=NonwearDataSource.CHOI_ALGORITHM,
                duration_minutes=end_idx - start_idx + 1,
                start_index=start_idx,
                end_index=end_idx,
            )
            nonwear_periods.append(period)
            i = end_idx + 1
        else:
            i += 1

    merged_periods = _merge_adjacent_periods(nonwear_periods)

    logger.debug(f"Choi algorithm completed successfully. Found {len(merged_periods)} nonwear periods")

    return merged_periods
