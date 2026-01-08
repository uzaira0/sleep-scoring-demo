"""
Cole-Kripke (1992) sleep scoring algorithm.

Ported from desktop app's core/algorithms/sleep_wake/cole_kripke.py.
Implements the Cole-Kripke 1992 algorithm for sleep/wake classification.

References:
    Cole, R. J., Kripke, D. F., Gruen, W., Mullaney, D. J., & Gillin, J. C. (1992).
    Automatic sleep/wake identification from wrist activity. Sleep, 15(5), 461-469.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


class ColeKripkeParams:
    """Algorithm parameter constants."""

    WINDOW_SIZE = 7  # 4 previous + current + 2 future
    ACTIVITY_SCALE_ACTILIFE = 100.0  # Divide activity counts by this
    ACTIVITY_CAP_ACTILIFE = 300.0  # Maximum scaled activity value
    THRESHOLD = 1.0  # Sleep/wake classification threshold

    # Scaling factor for the weighted sum
    SCALING_FACTOR = 0.001

    # Coefficients for the weighted sum (1-minute epochs)
    COEF_LAG4 = 106  # A(t-4)
    COEF_LAG3 = 54  # A(t-3)
    COEF_LAG2 = 58  # A(t-2)
    COEF_LAG1 = 76  # A(t-1)
    COEF_CURRENT = 230  # A(t)
    COEF_LEAD1 = 74  # A(t+1)
    COEF_LEAD2 = 67  # A(t+2)


class ColeKripkeAlgorithm:
    """
    Cole-Kripke 1992 sleep scoring algorithm.

    Classifies each epoch as sleep (1) or wake (0) based on a 7-minute
    sliding window with weighted coefficients.

    Two variants are supported:
        - "actilife": Pre-scales activity by /100 and caps at 300 (default)
        - "original": Uses raw activity counts as published in the paper
    """

    def __init__(self, variant: str = "actilife") -> None:
        """
        Initialize the Cole-Kripke algorithm.

        Args:
            variant: Algorithm variant ("actilife" or "original")
        """
        self.variant = variant.lower()
        self._use_actilife_scaling = self.variant == "actilife"

    def score(self, activity_counts: Sequence[int | float]) -> list[int]:
        """
        Score epochs as sleep (1) or wake (0).

        Args:
            activity_counts: List of activity counts per epoch (Axis1/Y values)

        Returns:
            List of sleep scores (1=sleep, 0=wake)
        """
        n = len(activity_counts)
        if n == 0:
            return []

        # Convert to numpy array
        activity = np.array(activity_counts, dtype=np.float64)

        # Apply scaling based on variant
        if self._use_actilife_scaling:
            # ActiLife variant: divide by 100 and cap at 300
            scaled_activity = np.minimum(
                activity / ColeKripkeParams.ACTIVITY_SCALE_ACTILIFE,
                ColeKripkeParams.ACTIVITY_CAP_ACTILIFE,
            )
        else:
            # Original variant: use raw activity counts
            scaled_activity = activity.copy()

        # Calculate scores
        scores = self._calculate_scores(scaled_activity)
        return scores.tolist()

    def _calculate_scores(self, activity: np.ndarray) -> np.ndarray:
        """
        Calculate Cole-Kripke sleep/wake scores for activity data.

        Args:
            activity: Array of activity counts (pre-processed based on variant)

        Returns:
            Array of sleep/wake classifications (1=sleep, 0=wake)
        """
        n = len(activity)
        sleep_wake_scores = np.zeros(n, dtype=int)

        # Pad activity with zeros for boundary handling
        # 4 zeros at start (for lag), 2 zeros at end (for lead)
        padded_activity = np.pad(activity, pad_width=(4, 2), mode="constant", constant_values=0)

        # Coefficients array for vectorized multiplication
        coefficients = np.array(
            [
                ColeKripkeParams.COEF_LAG4,
                ColeKripkeParams.COEF_LAG3,
                ColeKripkeParams.COEF_LAG2,
                ColeKripkeParams.COEF_LAG1,
                ColeKripkeParams.COEF_CURRENT,
                ColeKripkeParams.COEF_LEAD1,
                ColeKripkeParams.COEF_LEAD2,
            ]
        )

        for i in range(n):
            # Extract 7-epoch window (4 lag + current + 2 lead)
            window_start = i  # Due to padding of 4, position i in padded = lag 4
            window = padded_activity[window_start : window_start + ColeKripkeParams.WINDOW_SIZE]

            # Calculate sleep index
            weighted_sum = np.dot(coefficients, window)
            sleep_index = ColeKripkeParams.SCALING_FACTOR * weighted_sum

            # Classify: SI < 1.0 = Sleep (1), SI >= 1.0 = Wake (0)
            sleep_wake_scores[i] = 1 if sleep_index < ColeKripkeParams.THRESHOLD else 0

        return sleep_wake_scores
