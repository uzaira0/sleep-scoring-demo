"""
Nonwear detection algorithm factory for dependency injection.

Provides centralized algorithm instantiation and configuration management.
This factory is the primary entry point for creating nonwear detection algorithm
instances throughout the application.

Architecture:
    - Factory pattern for algorithm instantiation
    - Configuration-aware creation
    - Registry for available algorithms with pre-configured parameters
    - Extensible for future algorithms (van Hees, etc.)

Example Usage:
    >>> from sleep_scoring_app.core.algorithms.nonwear_factory import NonwearAlgorithmFactory
    >>>
    >>> # Create default Choi algorithm
    >>> algorithm = NonwearAlgorithmFactory.create('choi_2011')
    >>>
    >>> # List available algorithms
    >>> available = NonwearAlgorithmFactory.get_available_algorithms()
    >>> # {'choi_2011': 'Choi (2011)'}
    >>>
    >>> # Detect nonwear periods
    >>> periods = algorithm.detect(activity_data, timestamps)

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from sleep_scoring_app.core.algorithms.choi import ChoiAlgorithm
from sleep_scoring_app.core.algorithms.van_hees import VanHeesNonwearAlgorithm

if TYPE_CHECKING:
    from sleep_scoring_app.core.algorithms.nonwear_detection_protocol import NonwearDetectionAlgorithm
    from sleep_scoring_app.utils.config import AppConfig

logger = logging.getLogger(__name__)


# Algorithm registry entry containing class and constructor parameters
class _AlgorithmEntry:
    """Internal registry entry for algorithm configuration."""

    def __init__(
        self,
        algorithm_class: type[NonwearDetectionAlgorithm],
        display_name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.algorithm_class = algorithm_class
        self.display_name = display_name
        self.params = params or {}


class NonwearAlgorithmFactory:
    """
    Factory for creating nonwear detection algorithm instances.

    Manages algorithm instantiation, configuration, and registration.
    Enables dependency injection throughout the application.

    Each algorithm variant is registered separately with its own identifier,
    display name, and constructor parameters.

    Class Attributes:
        _registry: Registry mapping algorithm identifiers to entry configurations

    Methods:
        create: Create a configured algorithm instance
        get_available_algorithms: List all registered algorithms
        register_algorithm: Register a new algorithm type
        get_default_algorithm_id: Get the default algorithm identifier
        is_registered: Check if an algorithm is registered

    """

    _registry: ClassVar[dict[str, _AlgorithmEntry]] = {
        "choi_2011": _AlgorithmEntry(
            algorithm_class=ChoiAlgorithm,
            display_name="Choi (2011)",
            params={
                "min_period_length": 90,
                "spike_tolerance": 2,
                "small_window_length": 30,
                "use_vector_magnitude": True,
            },
        ),
        "van_hees_2023": _AlgorithmEntry(
            algorithm_class=VanHeesNonwearAlgorithm,
            display_name="van Hees (2023)",
            params={
                "sd_criterion": 0.013,
                "range_criterion": 0.15,
                "medium_epoch_sec": 900,
                "sample_freq": 100.0,
            },
        ),
        # Future algorithms:
        # 'vanhees_2013': _AlgorithmEntry(VanHeesAlgorithm, 'van Hees (2013)', {}),
    }

    @classmethod
    def create(
        cls,
        algorithm_id: str,
        config: AppConfig | None = None,
    ) -> NonwearDetectionAlgorithm:
        """
        Create a nonwear detection algorithm instance.

        Args:
            algorithm_id: Algorithm identifier (e.g., "choi_2011")
            config: Optional application config (reserved for future use)

        Returns:
            Configured algorithm instance

        Raises:
            ValueError: If algorithm_id is not registered

        Example:
            >>> algorithm = NonwearAlgorithmFactory.create('choi_2011')
            >>> algorithm.name
            'Choi (2011)'

        """
        if algorithm_id not in cls._registry:
            available = ", ".join(cls._registry.keys())
            msg = f"Unknown nonwear algorithm '{algorithm_id}'. Available: {available}"
            raise ValueError(msg)

        entry = cls._registry[algorithm_id]

        # Create instance with pre-configured parameters
        return entry.algorithm_class(**entry.params)

    @classmethod
    def get_available_algorithms(cls) -> dict[str, str]:
        """
        Get all available algorithms.

        Returns:
            Dictionary mapping algorithm_id to display name

        Example:
            >>> NonwearAlgorithmFactory.get_available_algorithms()
            {'choi_2011': 'Choi (2011)'}

        """
        return {algorithm_id: entry.display_name for algorithm_id, entry in cls._registry.items()}

    @classmethod
    def register_algorithm(
        cls,
        algorithm_id: str,
        algorithm_class: type[NonwearDetectionAlgorithm],
        display_name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a new nonwear detection algorithm.

        Args:
            algorithm_id: Unique identifier for the algorithm
            algorithm_class: Algorithm class implementing NonwearDetectionAlgorithm protocol
            display_name: Human-readable name for UI display
            params: Constructor parameters for the algorithm

        Raises:
            ValueError: If algorithm_id already registered

        Example:
            >>> NonwearAlgorithmFactory.register_algorithm(
            ...     'custom_algo',
            ...     CustomAlgorithm,
            ...     'Custom Algorithm',
            ...     {'param1': 'value1'},
            ... )

        """
        if algorithm_id in cls._registry:
            msg = f"Nonwear algorithm '{algorithm_id}' is already registered"
            raise ValueError(msg)

        cls._registry[algorithm_id] = _AlgorithmEntry(
            algorithm_class=algorithm_class,
            display_name=display_name,
            params=params,
        )
        logger.info("Registered new nonwear detection algorithm: %s", algorithm_id)

    @classmethod
    def get_default_algorithm_id(cls) -> str:
        """
        Get the default algorithm identifier.

        Returns:
            Default algorithm ID ('choi_2011')

        """
        return "choi_2011"

    @classmethod
    def is_registered(cls, algorithm_id: str) -> bool:
        """
        Check if an algorithm is registered.

        Args:
            algorithm_id: Algorithm identifier to check

        Returns:
            True if algorithm is registered, False otherwise

        """
        return algorithm_id in cls._registry
