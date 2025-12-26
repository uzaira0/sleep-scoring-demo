#!/usr/bin/env python3
"""
Session state manager using QSettings (platform-native storage).
This is the PRIMARY session recovery mechanism.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow


logger = logging.getLogger(__name__)


class SessionStateManager:
    r"""
    Manages session state using QSettings (platform-native storage).

    Storage locations:
    - Windows: Registry under HKEY_CURRENT_USER\\Software\\SleepResearch\\SleepScoringApp
    - macOS: ~/Library/Preferences/com.sleepresearch.sleepscoringapp.plist
    - Linux: ~/.config/SleepResearch/SleepScoringApp.conf
    """

    # Session keys - use constants, not magic strings
    KEY_CURRENT_FILE = "session/current_file"
    KEY_DATE_INDEX = "session/current_date_index"
    KEY_VIEW_MODE = "session/view_mode_hours"
    KEY_CURRENT_TAB = "session/current_tab"
    KEY_WINDOW_GEOMETRY = "session/window_geometry"
    KEY_WINDOW_STATE = "session/window_state"

    def __init__(self) -> None:
        self._settings = QSettings("SleepResearch", "SleepScoringApp")
        logger.debug(
            "SessionStateManager initialized, storage: %s",
            self._settings.fileName(),
        )

    # ==================== Navigation State ====================

    def save_current_file(self, filename: str | None) -> None:
        """Save currently selected file."""
        if filename:
            self._settings.setValue(self.KEY_CURRENT_FILE, filename)
        else:
            self._settings.remove(self.KEY_CURRENT_FILE)
        self._settings.sync()

    def get_current_file(self) -> str | None:
        """Get last selected file, or None if not set."""
        value = self._settings.value(self.KEY_CURRENT_FILE, None)
        return str(value) if value else None

    def save_current_date_index(self, index: int) -> None:
        """Save current date index."""
        self._settings.setValue(self.KEY_DATE_INDEX, index)
        self._settings.sync()

    def get_current_date_index(self) -> int:
        """Get last date index, defaults to 0."""
        value = self._settings.value(self.KEY_DATE_INDEX, 0)
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    # ==================== View State ====================

    def save_view_mode(self, hours: int) -> None:
        """Save current view mode (24/48 hours)."""
        self._settings.setValue(self.KEY_VIEW_MODE, hours)
        # Don't sync here - less critical

    def get_view_mode(self) -> int:
        """Get last view mode, defaults to 24."""
        value = self._settings.value(self.KEY_VIEW_MODE, 24)
        try:
            hours = int(value)  # type: ignore[arg-type]
            # Validate - only 24 or 48 are valid
            return hours if hours in (24, 48) else 24
        except (TypeError, ValueError):
            return 24

    def save_current_tab(self, tab_index: int) -> None:
        """Save current tab index."""
        self._settings.setValue(self.KEY_CURRENT_TAB, tab_index)
        # Don't sync here - less critical

    def get_current_tab(self) -> int:
        """Get last tab index, defaults to 0."""
        value = self._settings.value(self.KEY_CURRENT_TAB, 0)
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    # ==================== Window State ====================

    def save_window_geometry(self, window: QMainWindow) -> None:
        """Save window geometry and state."""
        self._settings.setValue(self.KEY_WINDOW_GEOMETRY, window.saveGeometry())
        self._settings.setValue(self.KEY_WINDOW_STATE, window.saveState())
        self._settings.sync()

    def restore_window_geometry(self, window: QMainWindow) -> bool:
        """
        Restore window geometry and state.

        Returns True if geometry was restored, False if using defaults.
        Validates that window is on-screen before restoring.
        """
        geometry = self._settings.value(self.KEY_WINDOW_GEOMETRY)
        state = self._settings.value(self.KEY_WINDOW_STATE)

        if geometry is None:
            logger.debug("No saved geometry, using defaults")
            return False

        # Restore geometry
        window.restoreGeometry(geometry)

        # Validate window is on a visible screen
        if not self._is_window_visible(window):
            logger.warning("Saved geometry is off-screen, resetting to default")
            window.setGeometry(100, 100, 1200, 800)
            return False

        # Restore window state (toolbars, docks, etc.)
        if state:
            window.restoreState(state)

        logger.debug("Restored window geometry")
        return True

    def _is_window_visible(self, window: QMainWindow) -> bool:
        """Check if window is visible on any screen."""
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            return True  # Can't check, assume OK

        window_rect = window.geometry()
        screens = app.screens()

        return any(screen.availableGeometry().intersects(window_rect) for screen in screens)

    # ==================== Batch Operations ====================

    def save_all(
        self,
        current_file: str | None,
        date_index: int,
        view_mode: int,
        current_tab: int,
        window: QMainWindow,
    ) -> None:
        """Save all session state at once (for app close)."""
        if current_file:
            self._settings.setValue(self.KEY_CURRENT_FILE, current_file)
        self._settings.setValue(self.KEY_DATE_INDEX, date_index)
        self._settings.setValue(self.KEY_VIEW_MODE, view_mode)
        self._settings.setValue(self.KEY_CURRENT_TAB, current_tab)
        self._settings.setValue(self.KEY_WINDOW_GEOMETRY, window.saveGeometry())
        self._settings.setValue(self.KEY_WINDOW_STATE, window.saveState())
        self._settings.sync()
        logger.info("Saved all session state")

    def clear_session(self) -> None:
        """Clear all session state (for explicit reset)."""
        self._settings.remove("session")
        self._settings.sync()
        logger.info("Cleared session state")

    def clear_file_selection(self) -> None:
        """Clear just the file selection (when file no longer exists)."""
        self._settings.remove(self.KEY_CURRENT_FILE)
        self._settings.remove(self.KEY_DATE_INDEX)
        self._settings.sync()
