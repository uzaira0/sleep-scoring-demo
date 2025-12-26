"""
van Hees (2023) nonwear detection algorithm - DI-compatible implementation.

This module implements the van Hees 2023 nonwear detection algorithm for raw
accelerometer data in g-units. The algorithm uses 15-minute epochs and checks
standard deviation and range criteria across all three axes.

Key Differences from Choi Algorithm:
    - Works on raw accelerometer data in g-units (not activity counts)
    - Uses 15-minute "medium epochs" instead of 1-minute epochs
    - Per-axis nonwear scoring (0-3) instead of binary wear/nonwear
    - Different statistical criteria (SD and range thresholds)

References:
    van Hees, V. T., et al. (2023). GGIR: A research community-driven open source
    R package for generating physical activity and sleep outcomes from multi-day
    raw accelerometer data. Journal for the Measurement of Physical Behaviour.

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

from sleep_scoring_app.core.constants import NonwearAlgorithm

if TYPE_CHECKING:
    from datetime import datetime

    from sleep_scoring_app.core.dataclasses import NonwearPeriod

logger = logging.getLogger(__name__)


class VanHeesNonwearAlgorithm:
    """
    van Hees (2023) nonwear detection algorithm implementation.

    Implements the NonwearDetectionAlgorithm protocol for dependency injection.
    Designed for raw accelerometer data in g-units.

    Algorithm Parameters (configurable):
        sd_criterion: Standard deviation threshold for nonwear (default: 0.013 g)
        range_criterion: Range threshold for nonwear (default: 0.15 g)
        medium_epoch_sec: Epoch size in seconds (default: 900 = 15 minutes)
        sample_freq: Sample frequency in Hz (default: 100 Hz for wGT3X-BT)

    Output:
        - Nonwear scores per epoch: 0 (wear), 1 (1 axis), 2 (2 axes), 3 (all 3 axes)
        - Epochs flagged as nonwear (score >= 2) are considered nonwear periods

    Note: This algorithm expects raw accelerometer data in g-units, not activity counts.
    For activity count data, use the Choi algorithm instead.
    """

    def __init__(
        self,
        sd_criterion: float = 0.013,
        range_criterion: float = 0.15,
        medium_epoch_sec: int = 900,
        sample_freq: float = 100.0,
    ) -> None:
        """
        Initialize van Hees algorithm with parameters.

        Args:
            sd_criterion: Standard deviation threshold for nonwear (g-units)
            range_criterion: Range threshold for nonwear (g-units)
            medium_epoch_sec: Epoch size in seconds (default: 15 minutes)
            sample_freq: Sample frequency in Hz

        """
        self._sd_criterion = sd_criterion
        self._range_criterion = range_criterion
        self._medium_epoch_sec = medium_epoch_sec
        self._sample_freq = sample_freq

        # Log warning if non-standard parameters are used
        if sd_criterion != 0.013 or range_criterion != 0.15 or medium_epoch_sec != 900:
            logger.warning(
                "van Hees algorithm initialized with non-standard parameters: "
                f"sd_criterion={sd_criterion}, range_criterion={range_criterion}, "
                f"medium_epoch_sec={medium_epoch_sec}. Standard validated values are 0.013, 0.15, 900."
            )

    @property
    def name(self) -> str:
        """Algorithm display name."""
        return "van Hees (2023)"

    @property
    def identifier(self) -> str:
        """Algorithm unique identifier."""
        return NonwearAlgorithm.VAN_HEES_2023

    def detect(
        self,
        activity_data: list[float] | np.ndarray,
        timestamps: list[datetime],
        activity_column: str = "axis_y",
    ) -> list[NonwearPeriod]:
        """
        Detect nonwear periods from raw accelerometer data.

        Args:
            activity_data: Raw accelerometer data in g-units. Can be:
                - 1D array/list: Single axis data
                - 2D array: (n_samples, 3) for x, y, z axes
            timestamps: List of datetime objects corresponding to activity data
            activity_column: Name of activity column for reference (for metadata only)

        Returns:
            List of NonwearPeriod objects representing detected nonwear periods

        Raises:
            ValueError: If input data is invalid or mismatched lengths

        """
        # Input validation
        if activity_data is None:
            msg = "activity_data cannot be None"
            raise ValueError(msg)

        if timestamps is None:
            msg = "timestamps cannot be None"
            raise ValueError(msg)

        # Convert to numpy array
        data = np.asarray(activity_data)

        # Handle 1D data (single axis) - treat as Y axis
        if data.ndim == 1:
            logger.warning(
                "van Hees algorithm received 1D data. Expected 3-axis raw data. Creating synthetic 3-axis data with zeros for X and Z axes."
            )
            # Create (n_samples, 3) array with Y axis data and zeros for X/Z
            data = np.column_stack([np.zeros(len(data)), data, np.zeros(len(data))])

        # Validate shape
        if data.ndim != 2 or data.shape[1] != 3:
            msg = f"Expected 2D array with shape (n_samples, 3), got shape {data.shape}"
            raise ValueError(msg)

        # Validate timestamps length matches data
        if len(timestamps) != len(data):
            msg = f"Timestamps length ({len(timestamps)}) must match data length ({len(data)})"
            raise ValueError(msg)

        # Detect nonwear using core algorithm
        nonwear_scores = self._detect_nonwear_scores(data)

        # Convert scores to NonwearPeriod objects
        return self._scores_to_periods(nonwear_scores, timestamps)

    def detect_mask(self, activity_data: list[float] | np.ndarray) -> list[int]:
        """
        Generate per-epoch nonwear mask from activity data.

        For van Hees algorithm, epochs with nonwear score >= 2 (2+ axes nonwear)
        are considered nonwear.

        Args:
            activity_data: Raw accelerometer data in g-units (1D or 2D array)

        Returns:
            List of 0/1 values where 0=wearing, 1=not wearing

        Raises:
            ValueError: If input data is invalid

        """
        if activity_data is None:
            msg = "activity_data cannot be None"
            raise ValueError(msg)

        # Convert to numpy array
        data = np.asarray(activity_data)

        if len(data) == 0:
            return []

        # Handle 1D data
        if data.ndim == 1:
            data = np.column_stack([np.zeros(len(data)), data, np.zeros(len(data))])

        # Validate shape
        if data.ndim != 2 or data.shape[1] != 3:
            msg = f"Expected 2D array with shape (n_samples, 3), got shape {data.shape}"
            raise ValueError(msg)

        # Detect nonwear scores
        nonwear_scores = self._detect_nonwear_scores(data)

        # Convert to binary mask (score >= 2 = nonwear)
        return [1 if score >= 2 else 0 for score in nonwear_scores]

    def _detect_nonwear_scores(self, data: np.ndarray) -> np.ndarray:
        """
        Core nonwear detection algorithm.

        Args:
            data: Raw accelerometer data (n_samples, 3) in g-units

        Returns:
            Array of nonwear scores (0-3) per medium epoch

        """
        n_samples = len(data)
        medium_epoch_size = int(self._medium_epoch_sec * self._sample_freq)
        n_medium_epochs = n_samples // medium_epoch_size

        if n_medium_epochs == 0:
            return np.array([], dtype=int)

        nonwear_scores = np.zeros(n_medium_epochs, dtype=int)

        # Process each medium epoch
        for h in range(n_medium_epochs):
            epoch_start = h * medium_epoch_size
            epoch_end = (h + 1) * medium_epoch_size
            epoch_data = data[epoch_start:epoch_end]

            # Check each axis for nonwear criteria
            axes_nonwear = 0

            for axis_idx in range(3):
                axis_data = epoch_data[:, axis_idx]

                # Calculate range
                data_range = np.ptp(axis_data)  # peak-to-peak (max - min)

                # Check range criterion first (faster)
                if data_range < self._range_criterion:
                    # Calculate standard deviation (only if range criterion met)
                    sd_val = np.std(axis_data, ddof=1)

                    # Both criteria must be met for nonwear
                    if sd_val < self._sd_criterion:
                        axes_nonwear += 1

            nonwear_scores[h] = axes_nonwear

        return nonwear_scores

    def _scores_to_periods(
        self,
        nonwear_scores: np.ndarray,
        timestamps: list[datetime],
    ) -> list[NonwearPeriod]:
        """
        Convert nonwear scores to NonwearPeriod objects.

        Consecutive epochs with score >= 2 (2+ axes nonwear) are merged into periods.

        Args:
            nonwear_scores: Array of nonwear scores (0-3) per medium epoch
            timestamps: Original sample timestamps

        Returns:
            List of NonwearPeriod objects

        """
        from sleep_scoring_app.core.constants import NonwearDataSource
        from sleep_scoring_app.core.dataclasses import NonwearPeriod

        if len(nonwear_scores) == 0:
            return []

        medium_epoch_size = int(self._medium_epoch_sec * self._sample_freq)
        periods = []

        # Find consecutive nonwear epochs (score >= 2)
        in_period = False
        period_start_idx = None
        period_start_epoch = None

        for epoch_idx, score in enumerate(nonwear_scores):
            is_nonwear = score >= 2

            if is_nonwear and not in_period:
                # Start new period
                in_period = True
                period_start_idx = epoch_idx * medium_epoch_size
                period_start_epoch = epoch_idx

            elif not is_nonwear and in_period:
                # End current period
                period_end_idx = epoch_idx * medium_epoch_size - 1
                period_end_epoch = epoch_idx - 1

                # Create NonwearPeriod - ensure indices are valid
                if period_start_idx is None:
                    in_period = False
                    continue

                start_time = timestamps[period_start_idx]
                end_time = timestamps[min(period_end_idx, len(timestamps) - 1)]
                duration_minutes = (period_end_epoch - period_start_epoch + 1) * (self._medium_epoch_sec // 60)

                period = NonwearPeriod(
                    start_time=start_time,
                    end_time=end_time,
                    participant_id="",  # Will be filled by caller
                    source=NonwearDataSource.VAN_HEES_2023,
                    duration_minutes=duration_minutes,
                    start_index=period_start_idx,
                    end_index=period_end_idx,
                )
                periods.append(period)

                in_period = False

        # Handle period extending to end of data
        if in_period and period_start_idx is not None:
            period_end_idx = len(timestamps) - 1
            period_end_epoch = len(nonwear_scores) - 1

            start_time = timestamps[period_start_idx]
            end_time = timestamps[period_end_idx]
            duration_minutes = (period_end_epoch - period_start_epoch + 1) * (self._medium_epoch_sec // 60)

            period = NonwearPeriod(
                start_time=start_time,
                end_time=end_time,
                participant_id="",
                source=NonwearDataSource.VAN_HEES_2023,
                duration_minutes=duration_minutes,
                start_index=period_start_idx,
                end_index=period_end_idx,
            )
            periods.append(period)

        return periods

    def get_parameters(self) -> dict[str, Any]:
        """
        Get current algorithm parameters.

        Returns:
            Dictionary of parameter names and values

        """
        return {
            "sd_criterion": self._sd_criterion,
            "range_criterion": self._range_criterion,
            "medium_epoch_sec": self._medium_epoch_sec,
            "sample_freq": self._sample_freq,
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
            "sd_criterion",
            "range_criterion",
            "medium_epoch_sec",
            "sample_freq",
        }

        for key, value in kwargs.items():
            if key not in valid_params:
                msg = f"Invalid parameter: {key}. Valid parameters: {valid_params}"
                raise ValueError(msg)

            if key == "sd_criterion":
                if not isinstance(value, int | float) or value <= 0:
                    msg = f"sd_criterion must be positive number, got {value}"
                    raise ValueError(msg)
                self._sd_criterion = float(value)

            elif key == "range_criterion":
                if not isinstance(value, int | float) or value <= 0:
                    msg = f"range_criterion must be positive number, got {value}"
                    raise ValueError(msg)
                self._range_criterion = float(value)

            elif key == "medium_epoch_sec":
                if not isinstance(value, int) or value < 1:
                    msg = f"medium_epoch_sec must be positive integer, got {value}"
                    raise ValueError(msg)
                self._medium_epoch_sec = value

            elif key == "sample_freq":
                if not isinstance(value, int | float) or value <= 0:
                    msg = f"sample_freq must be positive number, got {value}"
                    raise ValueError(msg)
                self._sample_freq = float(value)

        # Log warning if non-standard parameters are set
        if self._sd_criterion != 0.013 or self._range_criterion != 0.15 or self._medium_epoch_sec != 900:
            logger.warning(
                "van Hees algorithm parameters changed to non-standard values: "
                f"sd_criterion={self._sd_criterion}, range_criterion={self._range_criterion}, "
                f"medium_epoch_sec={self._medium_epoch_sec}. Standard validated values are 0.013, 0.15, 900."
            )
