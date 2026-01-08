"""
Sadeh sleep scoring algorithm.

Ported from desktop app's core/algorithms/sleep_wake/sadeh.py.
Implements the Sadeh 1994 algorithm for sleep/wake classification.
"""

from __future__ import annotations

import math
from typing import Sequence


class AlgorithmParams:
    """Algorithm parameter constants."""

    SADEH_LOW_ACTIVITY_THRESHOLD = 30
    SADEH_NATS_MIN = 50
    SADEH_NATS_MAX = 100
    SADEH_ACTIVITY_CAP = 300
    SADEH_COEFFICIENT_A = 7.601
    SADEH_COEFFICIENT_B = 0.065
    SADEH_COEFFICIENT_C = 1.08
    SADEH_COEFFICIENT_D = 0.056
    SADEH_COEFFICIENT_E = 0.703
    SADEH_THRESHOLD = -4


class SadehAlgorithm:
    """
    Sadeh 1994 sleep scoring algorithm.

    Classifies each epoch as sleep (1) or wake (0) based on activity counts
    from the surrounding 11-minute window.
    """

    def __init__(self, variant: str = "actilife") -> None:
        """
        Initialize the Sadeh algorithm.

        Args:
            variant: Algorithm variant ("actilife" or "original")
        """
        self.variant = variant

    def score(self, activity_counts: Sequence[int | float]) -> list[int]:
        """
        Score epochs as sleep (1) or wake (0).

        Args:
            activity_counts: List of activity counts per epoch

        Returns:
            List of sleep scores (1=sleep, 0=wake)
        """
        n = len(activity_counts)
        if n == 0:
            return []

        results = []
        window_size = 5  # 5 epochs before and after (11-minute window)

        for i in range(n):
            # Get window bounds
            start = max(0, i - window_size)
            end = min(n, i + window_size + 1)
            window = [float(activity_counts[j]) for j in range(start, end)]

            # Calculate Sadeh variables
            avg = self._calculate_avg(window)
            nats = self._calculate_nats(window)
            sd = self._calculate_sd(window)
            lg = self._calculate_lg(activity_counts, i)

            # Apply formula
            ps = (
                AlgorithmParams.SADEH_COEFFICIENT_A
                - (AlgorithmParams.SADEH_COEFFICIENT_B * avg)
                - (AlgorithmParams.SADEH_COEFFICIENT_C * nats)
                - (AlgorithmParams.SADEH_COEFFICIENT_D * sd)
                - (AlgorithmParams.SADEH_COEFFICIENT_E * lg)
            )

            # Classify (PS > threshold = sleep)
            results.append(1 if ps > AlgorithmParams.SADEH_THRESHOLD else 0)

        return results

    def _calculate_avg(self, window: list[float]) -> float:
        """Calculate average activity in window (capped at 300)."""
        capped = [min(x, AlgorithmParams.SADEH_ACTIVITY_CAP) for x in window]
        return sum(capped) / len(capped) if capped else 0

    def _calculate_nats(self, window: list[float]) -> int:
        """Count epochs with activity between 50-100."""
        return sum(
            1
            for x in window
            if AlgorithmParams.SADEH_NATS_MIN <= x <= AlgorithmParams.SADEH_NATS_MAX
        )

    def _calculate_sd(self, window: list[float]) -> float:
        """Calculate standard deviation of activity in window."""
        if len(window) < 2:
            return 0

        capped = [min(x, AlgorithmParams.SADEH_ACTIVITY_CAP) for x in window]
        mean = sum(capped) / len(capped)
        variance = sum((x - mean) ** 2 for x in capped) / (len(capped) - 1)
        return math.sqrt(variance)

    def _calculate_lg(self, activity_counts: Sequence[int | float], index: int) -> float:
        """
        Calculate natural log of activity count at epoch.

        Uses ln(activity + 1) to handle zero values.
        """
        value = float(activity_counts[index])
        if value < AlgorithmParams.SADEH_LOW_ACTIVITY_THRESHOLD:
            value = 0
        return math.log(value + 1)
