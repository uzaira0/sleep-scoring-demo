"""
Choi (2011) nonwear detection algorithm - DI-compatible implementation.

This module implements the Choi algorithm as a class following the NonwearDetectionAlgorithm
protocol for dependency injection. Uses validated parameters from the published paper.

References:
    Choi, L., Liu, Z., Matthews, C. E., & Buchowski, M. S. (2011).
    Validation of accelerometer wear and nonwear time classification algorithm.
    Medicine and Science in Sports and Exercise, 43(2), 357-364.

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.algorithms.choi import detect_nonwear as _detect_nonwear_core

if TYPE_CHECKING:
    from datetime import datetime

    import numpy as np

    from sleep_scoring_app.core.dataclasses import NonwearPeriod

logger = logging.getLogger(__name__)


class ChoiAlgorithm:
    """
    Choi (2011) nonwear detection algorithm implementation.

    Implements the NonwearDetectionAlgorithm protocol for dependency injection.
    Uses fixed validated parameters from the published research.

    Algorithm Parameters (configurable):
        min_period_length: Minimum consecutive minutes for nonwear period (default: 90)
        spike_tolerance: Maximum allowed consecutive non-zero minutes (default: 2)
        small_window_length: Window size to check around spikes (default: 30)
        use_vector_magnitude: Whether to use vector magnitude vs single axis (default: True)

    Note: While parameters are configurable, the defaults are validated values from
    the original paper and should not be changed without strong justification.
    """

    def __init__(
        self,
        min_period_length: int = 90,
        spike_tolerance: int = 2,
        small_window_length: int = 30,
        use_vector_magnitude: bool = True,
    ) -> None:
        """
        Initialize Choi algorithm with parameters.

        Args:
            min_period_length: Minimum consecutive minutes for nonwear period
            spike_tolerance: Maximum allowed consecutive non-zero minutes
            small_window_length: Window size to check around spikes
            use_vector_magnitude: Whether to use vector magnitude vs single axis

        """
        self._min_period_length = min_period_length
        self._spike_tolerance = spike_tolerance
        self._small_window_length = small_window_length
        self._use_vector_magnitude = use_vector_magnitude

        # Log warning if non-standard parameters are used
        if min_period_length != 90 or spike_tolerance != 2 or small_window_length != 30:
            logger.warning(
                "Choi algorithm initialized with non-standard parameters: "
                f"min_period={min_period_length}, spike_tolerance={spike_tolerance}, "
                f"window={small_window_length}. Standard validated values are 90, 2, 30."
            )

    @property
    def name(self) -> str:
        """Algorithm display name."""
        return "Choi (2011)"

    @property
    def identifier(self) -> str:
        """Algorithm unique identifier."""
        return "choi_2011"

    def detect(
        self,
        activity_data: list[float] | np.ndarray,
        timestamps: list[datetime],
        activity_column: str = "axis_y",
    ) -> list[NonwearPeriod]:
        """
        Detect nonwear periods from activity data.

        Args:
            activity_data: List or array of activity count values
            timestamps: List of datetime objects corresponding to activity data
            activity_column: Name of activity column for reference (ignored - for API compatibility)

        Returns:
            List of NonwearPeriod objects representing detected nonwear periods

        Raises:
            ValueError: If input data is invalid or mismatched lengths

        """
        # Delegate to core implementation
        return _detect_nonwear_core(activity_data, timestamps)

    def detect_mask(self, activity_data: list[float] | np.ndarray) -> list[int]:
        """
        Generate per-epoch nonwear mask from activity data.

        Args:
            activity_data: List or array of activity count values

        Returns:
            List of 0/1 values where 0=wearing, 1=not wearing

        Raises:
            ValueError: If input data is invalid

        """
        if activity_data is None:
            msg = "activity_data cannot be None"
            raise ValueError(msg)

        if len(activity_data) == 0:
            return []

        # Create dummy timestamps for mask generation
        from datetime import datetime, timedelta

        timestamps = [datetime(2000, 1, 1) + timedelta(minutes=i) for i in range(len(activity_data))]

        # Get nonwear periods
        periods = self.detect(activity_data, timestamps)

        # Convert to mask
        mask = [0] * len(activity_data)
        for period in periods:
            if period.start_index is not None and period.end_index is not None:
                for i in range(period.start_index, min(period.end_index + 1, len(mask))):
                    mask[i] = 1

        return mask

    def get_parameters(self) -> dict[str, Any]:
        """
        Get current algorithm parameters.

        Returns:
            Dictionary of parameter names and values

        """
        return {
            "min_period_length": self._min_period_length,
            "spike_tolerance": self._spike_tolerance,
            "small_window_length": self._small_window_length,
            "use_vector_magnitude": self._use_vector_magnitude,
        }

    def set_parameters(self, **kwargs: Any) -> None:
        """
        Update algorithm parameters.

        Args:
            **kwargs: Parameter name-value pairs

        Raises:
            ValueError: If parameter name is invalid or value is out of range

        """
        valid_params = {
            "min_period_length",
            "spike_tolerance",
            "small_window_length",
            "use_vector_magnitude",
        }

        for key, value in kwargs.items():
            if key not in valid_params:
                msg = f"Invalid parameter: {key}. Valid parameters: {valid_params}"
                raise ValueError(msg)

            if key == "min_period_length":
                if not isinstance(value, int) or value < 1:
                    msg = f"min_period_length must be positive integer, got {value}"
                    raise ValueError(msg)
                self._min_period_length = value

            elif key == "spike_tolerance":
                if not isinstance(value, int) or value < 0:
                    msg = f"spike_tolerance must be non-negative integer, got {value}"
                    raise ValueError(msg)
                self._spike_tolerance = value

            elif key == "small_window_length":
                if not isinstance(value, int) or value < 1:
                    msg = f"small_window_length must be positive integer, got {value}"
                    raise ValueError(msg)
                self._small_window_length = value

            elif key == "use_vector_magnitude":
                if not isinstance(value, bool):
                    msg = f"use_vector_magnitude must be boolean, got {value}"
                    raise ValueError(msg)
                self._use_vector_magnitude = value

        # Log warning if non-standard parameters are set
        if self._min_period_length != 90 or self._spike_tolerance != 2 or self._small_window_length != 30:
            logger.warning(
                "Choi algorithm parameters changed to non-standard values: "
                f"min_period={self._min_period_length}, spike_tolerance={self._spike_tolerance}, "
                f"window={self._small_window_length}. Standard validated values are 90, 2, 30."
            )
