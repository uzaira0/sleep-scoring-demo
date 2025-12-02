"""
NWT (Nonwear Time) sensor correlation analysis - Framework-agnostic implementation.

This module provides functions to correlate sleep periods with nonwear sensor data,
identifying whether sleep onset/offset occurred during periods when the device
was not being worn (as detected by NWT sensors).

This is useful for validating actigraphy data quality and identifying potential
measurement artifacts in sleep studies.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


class TimeRange(NamedTuple):
    """
    Represents a time range with start and end datetime.

    Attributes:
        start_time: Beginning of the time range
        end_time: End of the time range

    """

    start_time: datetime
    end_time: datetime

    def overlaps_with(self, other: TimeRange) -> bool:
        """
        Check if this range overlaps with another range.

        Args:
            other: Another TimeRange to check for overlap

        Returns:
            True if ranges overlap, False otherwise

        """
        # Ranges overlap if neither is completely before the other
        return not (self.end_time < other.start_time or self.start_time > other.end_time)

    def contains_time(self, time: datetime) -> bool:
        """
        Check if a specific time falls within this range.

        Args:
            time: Datetime to check

        Returns:
            True if time is within range (inclusive), False otherwise

        """
        return self.start_time <= time <= self.end_time


class NWTCorrelationResult(NamedTuple):
    """
    Result of NWT correlation analysis.

    Attributes:
        onset_in_nonwear: 1 if onset occurred during nonwear, 0 if wearing, None if unknown
        offset_in_nonwear: 1 if offset occurred during nonwear, 0 if wearing, None if unknown
        total_overlapping_periods: Number of nonwear periods overlapping with sleep period
        analysis_successful: Whether the analysis completed successfully

    """

    onset_in_nonwear: int | None
    offset_in_nonwear: int | None
    total_overlapping_periods: int
    analysis_successful: bool


def check_time_in_nonwear_periods(
    time: datetime,
    nonwear_periods: list[TimeRange],
) -> bool:
    """
    Check if a specific time falls within any nonwear period.

    Args:
        time: Datetime to check
        nonwear_periods: List of TimeRange objects representing nonwear periods

    Returns:
        True if time falls within any nonwear period, False otherwise

    """
    return any(period.contains_time(time) for period in nonwear_periods)


def count_overlapping_periods(
    time_range: TimeRange,
    nonwear_periods: list[TimeRange],
) -> int:
    """
    Count how many nonwear periods overlap with a time range.

    Args:
        time_range: TimeRange to check for overlaps
        nonwear_periods: List of TimeRange objects representing nonwear periods

    Returns:
        Number of nonwear periods that overlap with the time range

    """
    return sum(1 for period in nonwear_periods if time_range.overlaps_with(period))


def correlate_sleep_with_nonwear(
    sleep_onset: datetime,
    sleep_offset: datetime,
    nonwear_periods: list[TimeRange],
) -> NWTCorrelationResult:
    """
    Correlate a sleep period with nonwear sensor data.

    This function determines whether sleep onset and offset occurred during
    periods when the accelerometer was not being worn, and counts the total
    number of nonwear periods that overlap with the sleep period.

    Args:
        sleep_onset: Datetime of sleep onset
        sleep_offset: Datetime of sleep offset
        nonwear_periods: List of TimeRange objects from NWT sensor

    Returns:
        NWTCorrelationResult with correlation metrics

    Example:
        ```python
        from datetime import datetime
        from sleep_scoring_app.core.algorithms.nwt_correlation import (
            TimeRange,
            correlate_sleep_with_nonwear
        )

        # Define sleep period
        onset = datetime(2024, 1, 1, 22, 30)
        offset = datetime(2024, 1, 2, 7, 15)

        # Define nonwear periods from sensor
        nonwear = [
            TimeRange(
                datetime(2024, 1, 1, 22, 0),
                datetime(2024, 1, 1, 22, 45)
            )
        ]

        # Correlate
        result = correlate_sleep_with_nonwear(onset, offset, nonwear)
        print(f"Onset during nonwear: {result.onset_in_nonwear}")
        print(f"Total overlaps: {result.total_overlapping_periods}")
        ```

    """
    try:
        # Check if onset time falls within any nonwear period
        onset_in_nonwear = 1 if check_time_in_nonwear_periods(sleep_onset, nonwear_periods) else 0

        # Check if offset time falls within any nonwear period
        offset_in_nonwear = 1 if check_time_in_nonwear_periods(sleep_offset, nonwear_periods) else 0

        # Count total nonwear periods overlapping with sleep period
        sleep_range = TimeRange(sleep_onset, sleep_offset)
        total_overlaps = count_overlapping_periods(sleep_range, nonwear_periods)

        return NWTCorrelationResult(
            onset_in_nonwear=onset_in_nonwear,
            offset_in_nonwear=offset_in_nonwear,
            total_overlapping_periods=total_overlaps,
            analysis_successful=True,
        )

    except Exception as e:
        logger.warning(f"Error during NWT correlation: {e}")
        return NWTCorrelationResult(
            onset_in_nonwear=None,
            offset_in_nonwear=None,
            total_overlapping_periods=0,
            analysis_successful=False,
        )


def calculate_nwt_onset(
    onset_time: datetime,
    nonwear_periods: list[TimeRange],
) -> int | None:
    """
    Check if sleep onset occurred during a nonwear period.

    Args:
        onset_time: Datetime of sleep onset
        nonwear_periods: List of TimeRange objects from NWT sensor

    Returns:
        1 if onset in nonwear period, 0 if wearing, None if analysis failed

    """
    try:
        return 1 if check_time_in_nonwear_periods(onset_time, nonwear_periods) else 0
    except Exception as e:
        logger.warning(f"Error calculating NWT onset: {e}")
        return None


def calculate_nwt_offset(
    offset_time: datetime,
    nonwear_periods: list[TimeRange],
) -> int | None:
    """
    Check if sleep offset occurred during a nonwear period.

    Args:
        offset_time: Datetime of sleep offset
        nonwear_periods: List of TimeRange objects from NWT sensor

    Returns:
        1 if offset in nonwear period, 0 if wearing, None if analysis failed

    """
    try:
        return 1 if check_time_in_nonwear_periods(offset_time, nonwear_periods) else 0
    except Exception as e:
        logger.warning(f"Error calculating NWT offset: {e}")
        return None


def calculate_total_nwt_overlaps(
    sleep_onset: datetime,
    sleep_offset: datetime,
    nonwear_periods: list[TimeRange],
) -> int | None:
    """
    Count nonwear periods overlapping with sleep period.

    Args:
        sleep_onset: Datetime of sleep onset
        sleep_offset: Datetime of sleep offset
        nonwear_periods: List of TimeRange objects from NWT sensor

    Returns:
        Number of overlapping nonwear periods, or None if analysis failed

    """
    try:
        sleep_range = TimeRange(sleep_onset, sleep_offset)
        return count_overlapping_periods(sleep_range, nonwear_periods)
    except Exception as e:
        logger.warning(f"Error calculating total NWT overlaps: {e}")
        return None
