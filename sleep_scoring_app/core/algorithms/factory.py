"""
Sleep scoring algorithm factory for dependency injection.

Provides centralized algorithm instantiation and configuration management.
This factory is the primary entry point for creating sleep scoring algorithm
instances throughout the application.

Architecture:
    - Factory pattern for algorithm instantiation
    - Configuration-aware creation
    - Registry for available algorithms with pre-configured parameters
    - Extensible for future algorithms

Example Usage:
    >>> from sleep_scoring_app.core.algorithms.factory import AlgorithmFactory
    >>>
    >>> # Create default algorithm (Sadeh ActiLife)
    >>> algorithm = AlgorithmFactory.create('sadeh_1994_actilife')
    >>>
    >>> # Create Sadeh Original
    >>> algorithm = AlgorithmFactory.create('sadeh_1994_original')
    >>>
    >>> # List available algorithms
    >>> available = AlgorithmFactory.get_available_algorithms()
    >>> # {'sadeh_1994_original': 'Sadeh (1994) Original', ...}

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.algorithms.cole_kripke import ColeKripkeAlgorithm
from sleep_scoring_app.core.algorithms.sadeh import SadehAlgorithm
from sleep_scoring_app.core.algorithms.sleep_scoring_protocol import SleepScoringAlgorithm

if TYPE_CHECKING:
    from sleep_scoring_app.utils.config import AppConfig

logger = logging.getLogger(__name__)


# Algorithm registry entry containing class and constructor parameters
class _AlgorithmEntry:
    """Internal registry entry for algorithm configuration."""

    def __init__(
        self,
        algorithm_class: type[SleepScoringAlgorithm],
        display_name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.algorithm_class = algorithm_class
        self.display_name = display_name
        self.params = params or {}


class AlgorithmFactory:
    """
    Factory for creating sleep scoring algorithm instances.

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

    """

    _registry: dict[str, _AlgorithmEntry] = {
        "sadeh_1994_original": _AlgorithmEntry(
            algorithm_class=SadehAlgorithm,
            display_name="Sadeh (1994) Original",
            params={"threshold": 0.0, "variant_name": "original"},
        ),
        "sadeh_1994_actilife": _AlgorithmEntry(
            algorithm_class=SadehAlgorithm,
            display_name="Sadeh (1994) ActiLife",
            params={"threshold": -4.0, "variant_name": "actilife"},
        ),
        "cole_kripke_1992": _AlgorithmEntry(
            algorithm_class=ColeKripkeAlgorithm,
            display_name="Cole-Kripke (1992)",
            params={},
        ),
        # Future algorithms:
        # 'sazonov_2004': _AlgorithmEntry(SazonovAlgorithm, 'Sazonov (2004)', {}),
    }

    @classmethod
    def create(
        cls,
        algorithm_id: str,
        config: AppConfig | None = None,
    ) -> SleepScoringAlgorithm:
        """
        Create a sleep scoring algorithm instance.

        Args:
            algorithm_id: Algorithm identifier (e.g., "sadeh_1994_actilife")
            config: Optional application config (reserved for future use)

        Returns:
            Configured algorithm instance

        Raises:
            ValueError: If algorithm_id is not registered

        Example:
            >>> algorithm = AlgorithmFactory.create('sadeh_1994_actilife')
            >>> algorithm.name
            'Sadeh (1994) ActiLife'

        """
        if algorithm_id not in cls._registry:
            available = ", ".join(cls._registry.keys())
            msg = f"Unknown algorithm '{algorithm_id}'. Available: {available}"
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
            >>> AlgorithmFactory.get_available_algorithms()
            {'sadeh_1994_original': 'Sadeh (1994) Original', ...}

        """
        return {algorithm_id: entry.display_name for algorithm_id, entry in cls._registry.items()}

    @classmethod
    def register_algorithm(
        cls,
        algorithm_id: str,
        algorithm_class: type[SleepScoringAlgorithm],
        display_name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a new sleep scoring algorithm.

        Args:
            algorithm_id: Unique identifier for the algorithm
            algorithm_class: Algorithm class implementing SleepScoringAlgorithm protocol
            display_name: Human-readable name for UI display
            params: Constructor parameters for the algorithm

        Raises:
            ValueError: If algorithm_id already registered

        Example:
            >>> AlgorithmFactory.register_algorithm(
            ...     'custom_algo',
            ...     CustomAlgorithm,
            ...     'Custom Algorithm',
            ...     {'param1': 'value1'},
            ... )

        """
        if algorithm_id in cls._registry:
            msg = f"Algorithm '{algorithm_id}' is already registered"
            raise ValueError(msg)

        cls._registry[algorithm_id] = _AlgorithmEntry(
            algorithm_class=algorithm_class,
            display_name=display_name,
            params=params,
        )
        logger.info("Registered new sleep scoring algorithm: %s", algorithm_id)

    @classmethod
    def get_default_algorithm_id(cls) -> str:
        """
        Get the default algorithm identifier.

        Returns:
            Default algorithm ID ('sadeh_1994_actilife')

        """
        return "sadeh_1994_actilife"

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

    @classmethod
    def get_algorithm_threshold(cls, algorithm_id: str) -> float | None:
        """
        Get the threshold parameter for an algorithm if applicable.

        Args:
            algorithm_id: Algorithm identifier

        Returns:
            Threshold value if algorithm has one, None otherwise

        """
        if algorithm_id not in cls._registry:
            return None

        entry = cls._registry[algorithm_id]
        return entry.params.get("threshold")
