"""
Data layer configuration.

Configuration values that control data persistence behavior.
Separated from UI constants to maintain clean layer boundaries.
"""

from __future__ import annotations


class DataConfig:
    """Configuration for data layer behavior."""

    # Autosave feature control - disabled by default
    # Set to True to enable automatic saving of markers to autosave table
    ENABLE_AUTOSAVE = False
