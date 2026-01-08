"""
Choi (2011) nonwear detection algorithm.

Ported from desktop app's core/algorithms/nonwear/choi.py.
Detects periods when accelerometer is not being worn.

References:
    Choi, L., Liu, Z., Matthews, C. E., & Buchowski, M. S. (2011).
    Validation of accelerometer wear and nonwear time classification algorithm.
    Medicine and Science in Sports and Exercise, 43(2), 357-364.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class NonwearPeriod:
    """A detected nonwear period."""

    start_index: int
    end_index: int
    duration_minutes: int


class ChoiParams:
    """Algorithm parameter constants (validated from paper)."""

    MIN_PERIOD_LENGTH = 90  # Minimum consecutive minutes for nonwear
    SPIKE_TOLERANCE = 2  # Maximum allowed non-zero minutes in window
    WINDOW_SIZE = 30  # Window size to check around spikes


class ChoiAlgorithm:
    """
    Choi (2011) nonwear detection algorithm.

    Identifies consecutive zero-count periods as potential nonwear.
    Allows small spikes (<=2 minutes) within larger zero periods.
    Validates minimum period length (90 minutes).
    """

    def __init__(self) -> None:
        """Initialize Choi algorithm with validated parameters."""
        self.min_period = ChoiParams.MIN_PERIOD_LENGTH
        self.spike_tolerance = ChoiParams.SPIKE_TOLERANCE
        self.window_size = ChoiParams.WINDOW_SIZE

    def detect(self, activity_counts: Sequence[int | float]) -> list[NonwearPeriod]:
        """
        Detect nonwear periods from activity data.

        Args:
            activity_counts: List of activity counts per epoch

        Returns:
            List of NonwearPeriod objects
        """
        n = len(activity_counts)
        if n == 0:
            return []

        counts = np.array(activity_counts, dtype=np.float64)
        periods: list[NonwearPeriod] = []
        i = 0

        while i < n:
            # Skip non-zero epochs
            if counts[i] > 0:
                i += 1
                continue

            # Found zero - start potential nonwear period
            start_idx = i
            end_idx = i

            # Extend the period, allowing small spikes
            continuation = i
            while continuation < n:
                if counts[continuation] == 0:
                    end_idx = continuation
                    continuation += 1
                    continue

                # Non-zero found - check if it's a small spike
                window_start = max(0, continuation - self.window_size)
                window_end = min(n, continuation + self.window_size)
                nonzero_count = np.sum(counts[window_start:window_end] > 0)

                if nonzero_count > self.spike_tolerance:
                    # Too many non-zero values - end period
                    break

                continuation += 1

            # Check if period is long enough
            duration = end_idx - start_idx + 1
            if duration >= self.min_period:
                periods.append(
                    NonwearPeriod(
                        start_index=start_idx,
                        end_index=end_idx,
                        duration_minutes=duration,
                    )
                )
                i = end_idx + 1
            else:
                i += 1

        # Merge adjacent periods
        return self._merge_adjacent(periods)

    def _merge_adjacent(self, periods: list[NonwearPeriod]) -> list[NonwearPeriod]:
        """Merge adjacent nonwear periods (within 1 minute)."""
        if len(periods) <= 1:
            return periods

        periods.sort(key=lambda p: p.start_index)
        merged: list[NonwearPeriod] = []
        current = periods[0]

        for next_period in periods[1:]:
            # Check if periods are adjacent (within 1 minute)
            if next_period.start_index - current.end_index <= 1:
                # Merge
                current = NonwearPeriod(
                    start_index=current.start_index,
                    end_index=max(current.end_index, next_period.end_index),
                    duration_minutes=(max(current.end_index, next_period.end_index) - current.start_index + 1),
                )
            else:
                merged.append(current)
                current = next_period

        merged.append(current)
        return merged

    def detect_mask(self, activity_counts: Sequence[int | float]) -> list[int]:
        """
        Generate per-epoch nonwear mask from activity data.

        Args:
            activity_counts: List of activity counts per epoch

        Returns:
            List of 0/1 values where 0=wearing, 1=not wearing
        """
        n = len(activity_counts)
        if n == 0:
            return []

        # Detect nonwear periods
        periods = self.detect(activity_counts)

        # Convert to mask
        mask = [0] * n
        for period in periods:
            for i in range(period.start_index, min(period.end_index + 1, n)):
                mask[i] = 1

        return mask
