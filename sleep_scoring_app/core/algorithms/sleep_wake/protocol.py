"""
Sleep scoring algorithm protocol for dependency injection.

This protocol defines the interface that all sleep scoring algorithms must implement.
Enables swappable algorithms without changing core application logic.

Architecture:
    - Protocol defines the contract for sleep scoring algorithms
    - Implementations: SadehAlgorithm, ColeKripkeAlgorithm (future), etc.
    - Factory creates instances based on configuration
    - Services accept protocol type, not concrete implementations

Example Usage:
    >>> from sleep_scoring_app.core.algorithms import AlgorithmFactory
    >>>
    >>> # Create algorithm from factory
    >>> algorithm = AlgorithmFactory.create('sadeh_1994')
    >>>
    >>> # Use protocol type for dependency injection
    >>> def process_data(algorithm: SleepScoringAlgorithm, data: pd.DataFrame):
    ...     return algorithm.score(data)

References:
    - Sadeh, A., et al. (1994). Activity-based sleep-wake identification.
    - Cole, R. J., et al. (1992). Automatic sleep/wake identification from wrist activity.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd

    from sleep_scoring_app.core.pipeline.types import AlgorithmDataRequirement


@runtime_checkable
class SleepScoringAlgorithm(Protocol):
    """
    Protocol for sleep scoring algorithms.

    All sleep scoring algorithms (Sadeh, Cole-Kripke, etc.) must implement this interface.
    The protocol is runtime_checkable to allow isinstance() checks for validation.

    Properties:
        name: Human-readable algorithm name for display
        identifier: Unique identifier for storage and configuration
        requires_axis: Required accelerometer axis for this algorithm
        data_source_type: Type of data required ("epoch" or "raw") - DEPRECATED
        data_requirement: Type of data required (AlgorithmDataRequirement enum)

    Methods:
        score: Score sleep/wake from DataFrame
        score_array: Score sleep/wake from array (legacy API)
        get_parameters: Get current algorithm parameters
        set_parameters: Update algorithm parameters

    """

    @property
    def name(self) -> str:
        """
        Algorithm name for display and identification.

        Returns:
            Human-readable algorithm name (e.g., "Sadeh (1994)", "Cole-Kripke (1992)")

        """
        ...

    @property
    def identifier(self) -> str:
        """
        Unique algorithm identifier for storage and configuration.

        Returns:
            Snake_case identifier (e.g., "sadeh_1994", "cole_kripke_1992")

        """
        ...

    @property
    def requires_axis(self) -> str:
        """
        Required accelerometer axis for this algorithm.

        Returns:
            Axis name: "axis_y" (vertical), "vector_magnitude", "raw_triaxial", etc.

        """
        ...

    @property
    def data_source_type(self) -> str:
        """
        Type of data source required by this algorithm.

        DEPRECATED: Use data_requirement property instead for type-safe enum.

        Returns:
            "epoch" for pre-aggregated epoch count data (60-second)
            "raw" for raw high-frequency tri-axial accelerometer data

        Note:
            - Epoch-based algorithms (Sadeh, Cole-Kripke): "epoch"
            - Raw-data algorithms (van Hees 2015, HDCZA): "raw"

        """
        ...

    @property
    def data_requirement(self) -> AlgorithmDataRequirement:
        """
        Type of data required by this algorithm (type-safe enum).

        This property enables pipeline routing and compatibility checking.
        Use this instead of data_source_type for new code.

        Returns:
            AlgorithmDataRequirement.EPOCH_DATA for epoch-based algorithms
            AlgorithmDataRequirement.RAW_DATA for raw-data algorithms

        Example:
            >>> from sleep_scoring_app.core.pipeline import AlgorithmDataRequirement
            >>> algorithm = SadehAlgorithm()
            >>> if algorithm.data_requirement == AlgorithmDataRequirement.EPOCH_DATA:
            ...     print("Requires 60-second epoch counts")

        """
        ...

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score sleep/wake from activity data.

        Args:
            df: DataFrame with datetime column and required activity column

        Returns:
            Original DataFrame with added 'Sleep Score' column (1=sleep, 0=wake)

        Raises:
            ValueError: If required columns are missing or data is invalid

        """
        ...

    def score_array(
        self,
        activity_data: list[float] | np.ndarray,
        timestamps: list | None = None,
    ) -> list[int]:
        """
        Score sleep/wake from activity array (legacy API).

        Args:
            activity_data: List or array of activity count values
            timestamps: Optional list of timestamps (for validation)

        Returns:
            List of sleep/wake classifications (1=sleep, 0=wake)

        """
        ...

    def get_parameters(self) -> dict[str, Any]:
        """
        Get current algorithm parameters.

        Returns:
            Dictionary of parameter names and values

        """
        ...

    def set_parameters(self, **kwargs: Any) -> None:
        """
        Update algorithm parameters.

        Args:
            **kwargs: Parameter name-value pairs

        Raises:
            ValueError: If parameter name is invalid or value is out of range

        """
        ...
