#!/usr/bin/env python3
"""
File Navigation Manager for Sleep Scoring Application.

Manages file and date navigation, dropdown population, and selection handling.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

from sleep_scoring_app.ui.store import Actions

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import FileInfo
    from sleep_scoring_app.ui.protocols import (
        AppStateInterface,
        MainWindowProtocol,
        NavigationInterface,
        ServiceContainer,
    )
    from sleep_scoring_app.ui.store import UIStore

logger = logging.getLogger(__name__)


class FileNavigationManager:
    """
    Manages file and date navigation for the main window.

    Responsibilities:
    - Populate and update date dropdown
    - Handle date selection changes
    - Navigate between dates (prev/next)
    - Navigate between files (prev/next)
    - Check for unsaved markers before navigation
    - Handle file selection from table
    """

    def __init__(
        self, store: UIStore, navigation: NavigationInterface, app_state: AppStateInterface, services: ServiceContainer, parent: MainWindowProtocol
    ) -> None:
        """
        Initialize the file navigation manager.

        Args:
            store: The UI store
            navigation: Navigation interface
            app_state: App state coordination interface
            services: Service container
            parent: Main window (still needed for some Qt-level access for now)

        """
        self.store = store
        self.navigation = navigation
        self.app_state = app_state
        self.services = services
        self.main_window = parent
        self.parent = parent

        logger.info("FileNavigationManager initialized with decoupled interfaces")

    def on_date_dropdown_changed(self, index: int) -> None:
        """Handle date dropdown selection change via Redux store."""
        if not self.navigation.available_dates or index < 0:
            return

        if index < len(self.navigation.available_dates) and index != self.navigation.current_date_index:
            # Check for unsaved markers
            if self._check_unsaved_markers():
                return

            logger.info(f"NAV MANAGER: Dispatching DATE_SELECTED ({index})")
            # MW-04 FIX: We ONLY dispatch. Connector handles the rest.
            self.store.dispatch(Actions.date_selected(index))

    def prev_date(self) -> None:
        """Navigate to previous date via Redux store."""
        if self._check_unsaved_markers():
            return

        if self.navigation.current_date_index > 0:
            logger.info("NAV MANAGER: Dispatching DATE_NAVIGATED (-1)")
            self.store.dispatch(Actions.date_navigated(-1))

    def next_date(self) -> None:
        """Navigate to next date via Redux store."""
        if self._check_unsaved_markers():
            return

        if self.navigation.current_date_index < len(self.navigation.available_dates) - 1:
            logger.info("NAV MANAGER: Dispatching DATE_NAVIGATED (1)")
            self.store.dispatch(Actions.date_navigated(1))

    def _check_unsaved_markers(self) -> bool:
        """
        Check for unsaved markers before navigation.

        Uses Redux store as the source of truth.
        """
        logger.info("=== _check_unsaved_markers (file_navigation) START ===")

        # Use the Redux store selectors
        from sleep_scoring_app.ui.store import Selectors

        has_dirty = Selectors.is_any_markers_dirty(self.parent.store.state)
        logger.info(f"Redux store is_any_markers_dirty = {has_dirty}")

        if has_dirty:
            logger.info("Prompting user about unsaved markers")
            reply = QMessageBox.question(
                self.parent,
                "Unsaved Markers",
                "You have unsaved markers. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            result = reply == QMessageBox.StandardButton.No
            logger.info(f"User chose to cancel: {result}")
            return result

        logger.info("=== _check_unsaved_markers (file_navigation) END - No unsaved markers ===")
        return False

    def refresh_file_dropdown_indicators(self) -> None:
        """Refresh file dropdown to show marker indicators."""
        # Main window always has this method
        self.parent._refresh_file_dropdown_indicators()

    def update_navigation_buttons(self) -> None:
        """Update navigation button states."""
        # Analysis tab and navigation buttons always exist after UI setup
        self.parent.analysis_tab.prev_date_btn.setEnabled(self.parent.current_date_index > 0)
        self.parent.analysis_tab.next_date_btn.setEnabled(self.parent.current_date_index < len(self.parent.available_dates) - 1)

    def on_file_selected_from_table(self, file_info: FileInfo) -> None:
        """
        Handle file selection from table widget using Redux pattern.
        This is an 'Effect' that orchestrates data loading and store updates.
        """
        if not file_info:
            return

        logger.info(f"NAV MANAGER: Processing file selection for {file_info.filename}")

        try:
            # 1. Check for unsaved changes (User interaction permitted here)
            if self._check_unsaved_markers():
                return

            # NOTE: file_selected action is ALREADY dispatched by SignalsConnector
            # DO NOT dispatch again here - it would clear dates that we're about to load

            # 2. Perform data loading
            skip_rows = self.services.config_manager.config.skip_rows
            logger.info(f"NAV MANAGER: Loading dates for {file_info.filename} (skip_rows={skip_rows})")

            # This is a pure data call to the service
            new_dates = self.services.data_service.load_selected_file(file_info, skip_rows)

            if new_dates:
                logger.info(f"NAV MANAGER: Found {len(new_dates)} dates for {file_info.filename}. First date: {new_dates[0]}")
                # 4. Dispatch DATES_LOADED to Store
                self.store.dispatch(Actions.dates_loaded(new_dates))
                logger.info("NAV MANAGER: Dispatched DATES_LOADED")
            else:
                logger.warning(f"NAV MANAGER: NO DATES FOUND for {file_info.filename} via service")
                self.store.dispatch(Actions.dates_loaded([]))

            # 5. Load auxiliary data
            # MainWindowProtocol guarantees this method exists
            self.main_window._load_diary_data_for_file()

        except Exception as e:
            logger.exception("NAV MANAGER: File selection failed")
            # Using main_window as parent for dialog is acceptable (Qt parent-child relationship)
            QMessageBox.critical(self.main_window, "File Error", f"Failed to load file:\n{e}")
