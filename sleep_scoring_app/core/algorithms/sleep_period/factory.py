"""
Sleep period detector factory for dependency injection.

Provides centralized detector instantiation and configuration management.

This factory supports two types of sleep period detectors:
1. Epoch-based detectors (e.g., ConsecutiveEpochsSleepPeriodDetector) - work on
   pre-classified sleep/wake epoch data
2. Raw-data detectors (e.g., HDCZA) - work directly on raw accelerometer data
   and detect SPT boundaries using z-angle analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from sleep_scoring_app.core.pipeline.types import AlgorithmDataRequirement

from .config import (
    CONSECUTIVE_ONSET3S_OFFSET5S_CONFIG,
    CONSECUTIVE_ONSET5S_OFFSET10S_CONFIG,
    TUDOR_LOCKE_2014_CONFIG,
    ConsecutiveEpochsSleepPeriodDetectorConfig,
)
from .consecutive_epochs import ConsecutiveEpochsSleepPeriodDetector
from .hdcza import HDCZA

if TYPE_CHECKING:
    from .protocol import SleepPeriodDetector

logger = logging.getLogger(__name__)


@dataclass
class _DetectorEntry:
    """Internal registry entry for detector configuration."""

    detector_class: type
    display_name: str
    data_requirement: AlgorithmDataRequirement
    config: Any = None  # Optional config for ConsecutiveEpochsSleepPeriodDetector
    params: dict[str, Any] | None = None  # Optional params for HDCZA


class SleepPeriodDetectorFactory:
    """
    Factory for creating sleep period detector instances.

    Manages detector instantiation, configuration, and registration.
    Enables dependency injection throughout the application.

    Supports two categories of detectors:
    - EPOCH_DATA: Detectors that work on pre-classified sleep/wake epochs
      (e.g., Consecutive 3S/5S, Tudor-Locke 2014)
    - RAW_DATA: Detectors that work directly on raw accelerometer data
      (e.g., HDCZA)
    """

    # Registry of all available detectors
    _registry: ClassVar[dict[str, _DetectorEntry]] = {
        # =============================================================================
        # Epoch-based detectors (require pre-classified sleep/wake epoch data)
        # These work AFTER a sleep/wake algorithm has classified each epoch
        # =============================================================================
        "consecutive_onset3s_offset5s": _DetectorEntry(
            detector_class=ConsecutiveEpochsSleepPeriodDetector,
            display_name="Consecutive 3S/5S",
            data_requirement=AlgorithmDataRequirement.EPOCH_DATA,
            config=CONSECUTIVE_ONSET3S_OFFSET5S_CONFIG,
        ),
        "consecutive_onset5s_offset10s": _DetectorEntry(
            detector_class=ConsecutiveEpochsSleepPeriodDetector,
            display_name="Consecutive 5S/10S",
            data_requirement=AlgorithmDataRequirement.EPOCH_DATA,
            config=CONSECUTIVE_ONSET5S_OFFSET10S_CONFIG,
        ),
        "tudor_locke_2014": _DetectorEntry(
            detector_class=ConsecutiveEpochsSleepPeriodDetector,
            display_name="Tudor-Locke (2014)",
            data_requirement=AlgorithmDataRequirement.EPOCH_DATA,
            config=TUDOR_LOCKE_2014_CONFIG,
        ),
        # =============================================================================
        # Raw-data detectors (work directly on raw accelerometer data)
        # These bypass sleep/wake classification and detect SPT boundaries directly
        # using z-angle analysis
        # =============================================================================
        "hdcza_2018": _DetectorEntry(
            detector_class=HDCZA,
            display_name="HDCZA (van Hees 2018)",
            data_requirement=AlgorithmDataRequirement.RAW_DATA,
            params={},
        ),
    }

    # Backward compatibility mappings
    _legacy_ids: ClassVar[dict[str, str]] = {
        "consecutive_3_5": "consecutive_onset3s_offset5s",
        "consecutive_5_10": "consecutive_onset5s_offset10s",
    }

    @classmethod
    def create(
        cls,
        detector_id: str,
        config: ConsecutiveEpochsSleepPeriodDetectorConfig | None = None,
    ) -> SleepPeriodDetector:
        """
        Create a sleep period detector instance.

        Args:
            detector_id: Detector identifier (e.g., "consecutive_onset3s_offset5s", "hdcza_2018")
            config: Optional custom config (only applies to ConsecutiveEpochsSleepPeriodDetector)

        Returns:
            Configured detector instance

        Raises:
            ValueError: If detector_id is not registered

        """
        # Handle legacy IDs
        if detector_id in cls._legacy_ids:
            detector_id = cls._legacy_ids[detector_id]

        if detector_id not in cls._registry:
            available = ", ".join(cls._registry.keys())
            msg = f"Unknown sleep period detector '{detector_id}'. Available: {available}"
            raise ValueError(msg)

        entry = cls._registry[detector_id]

        # Create instance based on detector type
        if entry.detector_class == ConsecutiveEpochsSleepPeriodDetector:
            # Use custom config if provided, otherwise use preset
            final_config = config if config is not None else entry.config

            # Runtime type check to catch misuse (e.g., passing AppConfig instead)
            if final_config is not None and not isinstance(final_config, ConsecutiveEpochsSleepPeriodDetectorConfig):
                msg = (
                    f"Invalid config type for ConsecutiveEpochsSleepPeriodDetector: "
                    f"expected ConsecutiveEpochsSleepPeriodDetectorConfig, got {type(final_config).__name__}. "
                    f"Do not pass AppConfig to the factory."
                )
                raise TypeError(msg)

            return ConsecutiveEpochsSleepPeriodDetector(
                config=final_config,
                preset_name=entry.display_name,
            )
        if entry.detector_class == HDCZA:
            # HDCZA uses params, not config
            params = entry.params or {}
            return HDCZA(**params)
        # Generic fallback
        return entry.detector_class()

    @classmethod
    def get_available_detectors(cls) -> dict[str, str]:
        """
        Get all available sleep period detectors.

        Returns:
            Dictionary mapping detector_id to display name

        """
        return {detector_id: entry.display_name for detector_id, entry in cls._registry.items()}

    @classmethod
    def get_detectors_for_paradigm(cls, paradigm: str) -> dict[str, str]:
        """
        Get detectors compatible with a specific data paradigm.

        Args:
            paradigm: Data paradigm ("epoch_based" or "raw_accelerometer")

        Returns:
            Dictionary mapping detector_id to display name for compatible detectors

        """
        result = {}
        for detector_id, entry in cls._registry.items():
            if paradigm == "epoch_based":
                # Epoch paradigm: only epoch-based detectors
                if entry.data_requirement == AlgorithmDataRequirement.EPOCH_DATA:
                    result[detector_id] = entry.display_name
            # Raw paradigm: only raw-data detectors
            elif entry.data_requirement == AlgorithmDataRequirement.RAW_DATA:
                result[detector_id] = entry.display_name
        return result

    @classmethod
    def get_detector_data_requirement(cls, detector_id: str) -> AlgorithmDataRequirement | None:
        """
        Get the data requirement for a specific detector.

        Args:
            detector_id: Detector identifier

        Returns:
            AlgorithmDataRequirement enum value, or None if not found

        """
        # Handle legacy IDs
        if detector_id in cls._legacy_ids:
            detector_id = cls._legacy_ids[detector_id]

        if detector_id not in cls._registry:
            return None

        return cls._registry[detector_id].data_requirement

    # Backward compatibility alias
    get_available_rules = get_available_detectors

    @classmethod
    def get_default_detector_id(cls) -> str:
        """
        Get the default detector identifier.

        Returns:
            Default detector ID ("consecutive_onset3s_offset5s")

        """
        return "consecutive_onset3s_offset5s"

    @classmethod
    def get_default_detector_id_for_paradigm(cls, paradigm: str) -> str:
        """
        Get the default detector for a specific paradigm.

        Args:
            paradigm: Data paradigm ("epoch_based" or "raw_accelerometer")

        Returns:
            Default detector ID for the paradigm

        """
        if paradigm == "epoch_based":
            return "consecutive_onset3s_offset5s"
        # raw_accelerometer
        return "hdcza_2018"

    # Backward compatibility alias
    get_default_rule_id = get_default_detector_id

    @classmethod
    def register_detector(
        cls,
        detector_id: str,
        detector_class: type,
        display_name: str,
        data_requirement: AlgorithmDataRequirement,
        config: ConsecutiveEpochsSleepPeriodDetectorConfig | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a new sleep period detector.

        Args:
            detector_id: Unique identifier for the detector
            detector_class: Detector class
            display_name: Human-readable name for UI
            data_requirement: Data requirement (EPOCH_DATA or RAW_DATA)
            config: Configuration for ConsecutiveEpochsSleepPeriodDetector
            params: Constructor parameters for other detector types

        Raises:
            ValueError: If detector_id already registered

        """
        if detector_id in cls._registry:
            msg = f"Sleep period detector '{detector_id}' is already registered"
            raise ValueError(msg)

        cls._registry[detector_id] = _DetectorEntry(
            detector_class=detector_class,
            display_name=display_name,
            data_requirement=data_requirement,
            config=config,
            params=params,
        )
        logger.info("Registered new sleep period detector: %s", detector_id)

    # Backward compatibility alias
    register_rule = register_detector

    @classmethod
    def get_detector_description(cls, detector_id: str) -> str:
        """
        Get description for a specific detector.

        Args:
            detector_id: Detector identifier

        Returns:
            Detector description

        Raises:
            ValueError: If detector_id not registered

        """
        # Handle legacy IDs
        if detector_id in cls._legacy_ids:
            detector_id = cls._legacy_ids[detector_id]

        if detector_id not in cls._registry:
            available = ", ".join(cls._registry.keys())
            msg = f"Unknown sleep period detector '{detector_id}'. Available: {available}"
            raise ValueError(msg)

        detector = cls.create(detector_id)
        return detector.description

    @classmethod
    def is_raw_data_detector(cls, detector_id: str) -> bool:
        """
        Check if a detector requires raw accelerometer data.

        Args:
            detector_id: Detector identifier

        Returns:
            True if detector requires raw data, False otherwise

        """
        requirement = cls.get_detector_data_requirement(detector_id)
        return requirement == AlgorithmDataRequirement.RAW_DATA
