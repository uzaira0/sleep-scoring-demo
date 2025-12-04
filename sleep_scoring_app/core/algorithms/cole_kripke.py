"""
Cole-Kripke (1992) sleep scoring algorithm - Framework-agnostic implementation.

This module implements the Cole-Kripke algorithm for classifying minute-by-minute
activity data as sleep or wake. The implementation uses FIXED validated parameters
from the published paper and provides a simple function-based API.

References:
    Cole, R. J., Kripke, D. F., Gruen, W., Mullaney, D. J., & Gillin, J. C. (1992).
    Automatic sleep/wake identification from wrist activity. Sleep, 15(5), 461-469.

Algorithm Details:
    - Uses a 7-minute sliding window (4 previous + current + 2 future epochs)
    - Activity counts are scaled by dividing by 100 and capping at 300
    - Uses weighted sum of activity in the sliding window
    - Formula: SI = P * (W4*A4 + W3*A3 + W2*A2 + W1*A1 + W0*A0 + W-1*A-1 + W-2*A-2)
    - Classification: SI < 1.0 = Sleep (1), otherwise Wake (0)
    - ALWAYS uses Axis1 column (hardcoded in the algorithm)

Coefficients (1-minute epochs):
    - P (scaling factor): 0.001
    - W4 (lag 4): 106
    - W3 (lag 3): 54
    - W2 (lag 2): 58
    - W1 (lag 1): 76
    - W0 (current): 230
    - W-1 (lead 1): 74
    - W-2 (lead 2): 67

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from sleep_scoring_app.core.algorithms.utils import find_datetime_column, validate_and_collapse_epochs

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# Cole-Kripke algorithm constants (1-minute epochs)
WINDOW_SIZE: int = 7  # 4 previous + current + 2 future
ACTIVITY_SCALE: float = 100.0  # Divide activity counts by this
ACTIVITY_CAP: float = 300.0  # Maximum scaled activity value
THRESHOLD: float = 1.0  # Sleep/wake classification threshold

# Scaling factor
SCALING_FACTOR: float = 0.001

# Coefficients for the weighted sum (1-minute epochs)
# From Cole et al. (1992) and validated by actigraph.sleepr R package
COEF_LAG4: int = 106  # A(t-4)
COEF_LAG3: int = 54  # A(t-3)
COEF_LAG2: int = 58  # A(t-2)
COEF_LAG1: int = 76  # A(t-1)
COEF_CURRENT: int = 230  # A(t)
COEF_LEAD1: int = 74  # A(t+1)
COEF_LEAD2: int = 67  # A(t+2)


def cole_kripke_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply Cole-Kripke (1992) sleep scoring algorithm to activity data.

    Uses FIXED validated parameters from the published paper:
    - Window size: 7 minutes (4 lag + current + 2 lead)
    - Activity scaling: divide by 100, cap at 300
    - Threshold: 1.0 (SI < 1.0 = sleep)
    - Activity column: ALWAYS Axis1 (hardcoded in algorithm)

    The algorithm uses a 7-minute sliding window with weighted coefficients
    to calculate sleep/wake classifications. This is a validated research
    algorithm with parameters that should not be modified.

    Args:
        df: DataFrame with datetime column and 'Axis1' activity column

    Returns:
        Original DataFrame with new 'Sleep Score' column appended (1=sleep, 0=wake)

    Raises:
        ValueError: If epochs are larger than 1 minute or required columns missing

    Validation:
        - Finds datetime/date+time columns automatically
        - Verifies 1-minute epochs (±1 second tolerance)
        - Collapses to 1-minute if epochs < 1 minute
        - Raises error if epochs > 1 minute

    Example:
        >>> import pandas as pd
        >>> from sleep_scoring_app.core.algorithms import cole_kripke_score
        >>> df = pd.read_csv('activity.csv')
        >>> df.head()
           datetime             Axis1
        0  2024-01-01 00:00:00  45
        1  2024-01-01 00:01:00  32
        2  2024-01-01 00:02:00  0
        >>> df = cole_kripke_score(df)
        >>> df.head()
           datetime             Axis1  Sleep Score
        0  2024-01-01 00:00:00  45     1
        1  2024-01-01 00:01:00  32     1
        2  2024-01-01 00:02:00  0      1

    """
    if df is None or len(df) == 0:
        msg = "DataFrame cannot be None or empty"
        raise ValueError(msg)

    datetime_col = find_datetime_column(df)

    df = validate_and_collapse_epochs(df, datetime_col)

    if "Axis1" not in df.columns:
        msg = "DataFrame must contain 'Axis1' column. Cole-Kripke algorithm ALWAYS uses Axis1."
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

    logger.debug(f"Running Cole-Kripke algorithm on {len(activity_data)} epochs")

    # Scale and cap activity counts
    scaled_activity = np.minimum(activity_data / ACTIVITY_SCALE, ACTIVITY_CAP)

    sleep_wake_scores = _calculate_cole_kripke_scores(scaled_activity)

    logger.debug(f"Cole-Kripke algorithm completed successfully for {len(activity_data)} epochs")

    result_df = df.copy()
    result_df["Sleep Score"] = sleep_wake_scores

    return result_df


def _calculate_cole_kripke_scores(scaled_activity: np.ndarray) -> np.ndarray:
    """
    Calculate Cole-Kripke sleep/wake scores for scaled activity data.

    Args:
        scaled_activity: Array of activity counts scaled by /100 and capped at 300

    Returns:
        Array of sleep/wake classifications (1=sleep, 0=wake)

    """
    n = len(scaled_activity)
    sleep_wake_scores = np.zeros(n, dtype=int)

    # Pad activity with zeros for boundary handling
    # 4 zeros at start (for lag), 2 zeros at end (for lead)
    padded_activity = np.pad(scaled_activity, pad_width=(4, 2), mode="constant", constant_values=0)

    # Coefficients array for vectorized multiplication
    coefficients = np.array([COEF_LAG4, COEF_LAG3, COEF_LAG2, COEF_LAG1, COEF_CURRENT, COEF_LEAD1, COEF_LEAD2])

    for i in range(n):
        # Extract 7-epoch window (4 lag + current + 2 lead)
        window_start = i  # Due to padding of 4, position i in padded = lag 4
        window = padded_activity[window_start : window_start + WINDOW_SIZE]

        # Calculate sleep index
        weighted_sum = np.dot(coefficients, window)
        sleep_index = SCALING_FACTOR * weighted_sum

        # Classify: SI < 1.0 = Sleep (1), SI >= 1.0 = Wake (0)
        sleep_wake_scores[i] = 1 if sleep_index < THRESHOLD else 0

    return sleep_wake_scores


def score_activity_cole_kripke(activity_data: list[float] | np.ndarray) -> list[int]:
    """
    Legacy convenience function for backwards compatibility.

    Args:
        activity_data: List or array of Axis1 activity count values

    Returns:
        List of sleep/wake classifications (1=sleep, 0=wake)

    Example:
        >>> from sleep_scoring_app.core.algorithms import score_activity_cole_kripke
        >>> activity_counts = [45, 32, 0, 12, 5, ...]
        >>> sleep_scores = score_activity_cole_kripke(activity_counts)
        >>> sleep_scores
        [1, 1, 1, 1, 1, ...]

    """
    if activity_data is None:
        msg = "activity_data cannot be None"
        raise ValueError(msg)

    if len(activity_data) == 0:
        logger.debug("Empty activity_data provided to Cole-Kripke algorithm")
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

    logger.debug(f"Running Cole-Kripke algorithm on {len(activity_array)} epochs")

    # Scale and cap activity counts
    scaled_activity = np.minimum(activity_array / ACTIVITY_SCALE, ACTIVITY_CAP)

    sleep_wake_scores = _calculate_cole_kripke_scores(scaled_activity)

    logger.debug(f"Cole-Kripke algorithm completed successfully for {len(activity_array)} epochs")

    return sleep_wake_scores.tolist()


class ColeKripkeAlgorithm:
    """
    Cole-Kripke (1992) sleep scoring algorithm - Protocol implementation.

    This class implements the SleepScoringAlgorithm protocol for dependency injection.
    The original function-based API (cole_kripke_score, score_activity_cole_kripke) is
    preserved for backward compatibility.

    The Cole-Kripke algorithm uses a 7-minute sliding window with weighted coefficients
    to classify each epoch as sleep or wake based on activity counts. It ALWAYS uses
    the vertical axis (Axis1/axis_y) regardless of configuration.

    Unlike Sadeh, the Cole-Kripke algorithm has NO configurable parameters - all
    values are fixed from the published paper.

    Example:
        >>> from sleep_scoring_app.core.algorithms import ColeKripkeAlgorithm
        >>>
        >>> # Create algorithm instance
        >>> algorithm = ColeKripkeAlgorithm()
        >>>
        >>> # Score DataFrame
        >>> df = algorithm.score(activity_df)
        >>>
        >>> # Score array (legacy API)
        >>> scores = algorithm.score_array(activity_counts)

    References:
        Cole, R. J., Kripke, D. F., Gruen, W., Mullaney, D. J., & Gillin, J. C. (1992).
        Automatic sleep/wake identification from wrist activity. Sleep, 15(5), 461-469.

    """

    def __init__(self) -> None:
        """Initialize Cole-Kripke algorithm (no configurable parameters)."""
        self._parameters = {
            "window_size": WINDOW_SIZE,
            "activity_scale": ACTIVITY_SCALE,
            "activity_cap": ACTIVITY_CAP,
            "threshold": THRESHOLD,
            "scaling_factor": SCALING_FACTOR,
            "coef_lag4": COEF_LAG4,
            "coef_lag3": COEF_LAG3,
            "coef_lag2": COEF_LAG2,
            "coef_lag1": COEF_LAG1,
            "coef_current": COEF_CURRENT,
            "coef_lead1": COEF_LEAD1,
            "coef_lead2": COEF_LEAD2,
        }

    @property
    def name(self) -> str:
        """Algorithm name for display."""
        return "Cole-Kripke (1992)"

    @property
    def identifier(self) -> str:
        """Unique algorithm identifier."""
        return "cole_kripke_1992"

    @property
    def requires_axis(self) -> str:
        """Required accelerometer axis - always axis_y (vertical) for Cole-Kripke."""
        return "axis_y"

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score sleep/wake using Cole-Kripke algorithm.

        Args:
            df: DataFrame with datetime column and 'Axis1' activity column

        Returns:
            Original DataFrame with added 'Sleep Score' column (1=sleep, 0=wake)

        """
        return cole_kripke_score(df)

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
        return score_activity_cole_kripke(activity_data)

    def get_parameters(self) -> dict[str, float | int]:
        """
        Get current algorithm parameters.

        Returns:
            Dictionary of parameter names and values (all read-only)

        """
        return self._parameters.copy()

    def set_parameters(self, **kwargs: float) -> None:
        """
        Update algorithm parameters.

        Cole-Kripke algorithm has NO configurable parameters. All values are
        fixed from the published paper and cannot be changed.

        Args:
            **kwargs: Parameter name-value pairs (all ignored with warning)

        """
        if kwargs:
            logger.warning(
                "Cole-Kripke algorithm has no configurable parameters. All values are fixed from the published paper. Ignoring parameters: %s",
                list(kwargs.keys()),
            )
