"""
Configuration dataclasses for sleep scoring algorithms.

This module provides immutable configuration objects for algorithms that have
configurable parameters. Note that Sadeh and Choi algorithms use FIXED parameters
from their published papers and are not configurable.

All configurations use dataclasses for type safety and clear documentation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SleepRulesConfig:
    """
    Configuration for sleep onset/offset rule application.

    These rules identify the precise sleep onset and offset times based on
    consecutive sleep minutes detected by the Sadeh algorithm.

    Attributes:
        onset_consecutive_minutes: Consecutive sleep minutes for onset (default: 3)
        offset_consecutive_minutes: Consecutive sleep minutes before wake for offset (default: 5)
        search_extension_minutes: Minutes to extend search beyond markers (default: 5)
        require_wake_after_offset: Require wake minute after offset period (default: True)

    """

    onset_consecutive_minutes: int = 3
    offset_consecutive_minutes: int = 5
    search_extension_minutes: int = 5
    require_wake_after_offset: bool = True
