"""
Data source loader factory for dependency injection.

Provides centralized data source loader instantiation and management.
This factory is the primary entry point for creating data source loader instances
throughout the application.

Architecture:
    - Factory pattern for loader instantiation
    - Registry for available loaders with pre-configured parameters
    - Extension-based automatic loader selection
    - Extensible for future data sources (GENEActiv, Axivity, etc.)

Example Usage:
    >>> from sleep_scoring_app.core.algorithms.datasource_factory import DataSourceFactory
    >>>
    >>> # Create loader by ID
    >>> csv_loader = DataSourceFactory.create('csv')
    >>>
    >>> # Automatic selection by file extension
    >>> loader = DataSourceFactory.get_loader_for_extension('.csv')
    >>>
    >>> # List available loaders
    >>> available = DataSourceFactory.get_available_loaders()
    >>> # {'csv': 'CSV/XLSX File Loader', 'gt3x': 'GT3X File Loader'}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sleep_scoring_app.core.algorithms.csv_datasource import CSVDataSourceLoader
from sleep_scoring_app.core.algorithms.datasource_protocol import DataSourceLoader
from sleep_scoring_app.core.algorithms.gt3x_datasource import GT3XDataSourceLoader

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _LoaderEntry:
    """Internal registry entry for data source loader configuration."""

    loader_class: type[DataSourceLoader]
    display_name: str


class DataSourceFactory:
    """
    Factory for creating data source loader instances.

    Manages loader instantiation, configuration, and registration.
    Enables dependency injection throughout the application.

    Each loader is registered with its own identifier and supported file extensions.

    Class Attributes:
        _registry: Registry mapping loader identifiers to entry configurations

    Methods:
        create: Create a configured loader instance
        get_available_loaders: List all registered loaders
        get_loader_for_extension: Auto-select loader by file extension
        get_default_loader_id: Get the default loader identifier
        is_registered: Check if loader is registered
        get_supported_extensions: Get all supported file extensions
        register: Register a new loader type

    """

    _registry: dict[str, _LoaderEntry] = {
        "csv": _LoaderEntry(
            loader_class=CSVDataSourceLoader,
            display_name="CSV/XLSX File Loader",
        ),
        "gt3x": _LoaderEntry(
            loader_class=GT3XDataSourceLoader,
            display_name="GT3X File Loader",
        ),
        # Future loaders:
        # 'geneactiv': _LoaderEntry(GENEActivLoader, 'GENEActiv Binary Loader'),
        # 'axivity': _LoaderEntry(AxivityLoader, 'Axivity CWA Loader'),
    }

    @classmethod
    def create(cls, loader_id: str) -> DataSourceLoader:
        """
        Create a data source loader instance.

        Args:
            loader_id: Loader identifier (e.g., "csv", "gt3x")

        Returns:
            Configured loader instance

        Raises:
            ValueError: If loader_id is not registered

        Example:
            >>> loader = DataSourceFactory.create('csv')
            >>> loader.name
            'CSV/XLSX File Loader'

        """
        if loader_id not in cls._registry:
            available = ", ".join(cls._registry.keys())
            msg = f"Unknown data source loader '{loader_id}'. Available: {available}"
            raise ValueError(msg)

        entry = cls._registry[loader_id]

        # Create instance
        return entry.loader_class()

    @classmethod
    def get_available_loaders(cls) -> dict[str, str]:
        """
        Get all available data source loaders.

        Returns:
            Dictionary mapping loader_id to display name

        Example:
            >>> DataSourceFactory.get_available_loaders()
            {'csv': 'CSV/XLSX File Loader', 'gt3x': 'GT3X File Loader'}

        """
        return {loader_id: entry.display_name for loader_id, entry in cls._registry.items()}

    @classmethod
    def get_loader_for_extension(cls, file_extension: str) -> DataSourceLoader:
        """
        Auto-select and create loader based on file extension.

        Args:
            file_extension: File extension (e.g., ".csv", ".gt3x")

        Returns:
            Appropriate loader instance for the file type

        Raises:
            ValueError: If no loader supports the extension

        Example:
            >>> loader = DataSourceFactory.get_loader_for_extension('.csv')
            >>> loader.identifier
            'csv'

        """
        # Normalize extension to lowercase with leading dot
        ext = file_extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        # Check each loader's supported extensions
        for loader_id, entry in cls._registry.items():
            loader_instance = entry.loader_class()
            if ext in loader_instance.supported_extensions:
                return loader_instance

        # No matching loader found
        supported = cls.get_supported_extensions()
        msg = f"No loader found for extension '{ext}'. Supported: {', '.join(sorted(supported))}"
        raise ValueError(msg)

    @classmethod
    def get_loader_for_file(cls, file_path: str | Path) -> DataSourceLoader:
        """
        Auto-select and create loader based on file path.

        Args:
            file_path: Path to the data file

        Returns:
            Appropriate loader instance for the file type

        Raises:
            ValueError: If no loader supports the file extension

        Example:
            >>> loader = DataSourceFactory.get_loader_for_file('/data/activity.csv')
            >>> loader.identifier
            'csv'

        """
        from pathlib import Path

        path = Path(file_path)
        return cls.get_loader_for_extension(path.suffix)

    @classmethod
    def get_default_loader_id(cls) -> str:
        """
        Get the default loader identifier.

        Returns:
            Default loader ID ('csv')

        """
        return "csv"

    @classmethod
    def is_registered(cls, loader_id: str) -> bool:
        """
        Check if a loader is registered.

        Args:
            loader_id: Loader identifier to check

        Returns:
            True if loader is registered, False otherwise

        """
        return loader_id in cls._registry

    @classmethod
    def get_supported_extensions(cls) -> set[str]:
        """
        Get all supported file extensions across all loaders.

        Returns:
            Set of all supported file extensions

        Example:
            >>> DataSourceFactory.get_supported_extensions()
            {'.csv', '.xlsx', '.xls', '.gt3x'}

        """
        extensions = set()
        for entry in cls._registry.values():
            loader_instance = entry.loader_class()
            extensions.update(loader_instance.supported_extensions)
        return extensions

    @classmethod
    def register(
        cls,
        loader_id: str,
        loader_class: type[DataSourceLoader],
        display_name: str,
    ) -> None:
        """
        Register a new data source loader.

        Args:
            loader_id: Unique identifier for the loader
            loader_class: Loader class implementing DataSourceLoader protocol
            display_name: Human-readable name for UI display

        Raises:
            ValueError: If loader_id already registered

        Example:
            >>> DataSourceFactory.register(
            ...     'custom_loader',
            ...     CustomDataSourceLoader,
            ...     'Custom Data Loader',
            ... )

        """
        if loader_id in cls._registry:
            msg = f"Data source loader '{loader_id}' is already registered"
            raise ValueError(msg)

        cls._registry[loader_id] = _LoaderEntry(
            loader_class=loader_class,
            display_name=display_name,
        )
        logger.info("Registered new data source loader: %s", loader_id)


# Module-level initialization: Register default loaders
# (Already registered in _registry dict above, but this documents the pattern)
