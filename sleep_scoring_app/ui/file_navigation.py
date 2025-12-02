#!/usr/bin/env python3
"""
File Navigation Manager for Sleep Scoring Application.

Manages file and date navigation, dropdown population, and selection handling.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

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

    def __init__(self, parent: SleepScoringMainWindow) -> None:
        """
        Initialize the file navigation manager.

        Args:
            parent: Reference to main window for navigation controls

        """
        self.parent = parent
        logger.info("FileNavigationManager initialized")

    def populate_date_dropdown(self) -> None:
        """Populate date dropdown with available dates."""
        if hasattr(self.parent, "data_service") and self.parent.data_service:
            self.parent.data_service.populate_date_dropdown()

    def on_date_dropdown_changed(self, index: int) -> None:
        """Handle date dropdown selection change."""
        if not hasattr(self.parent, "available_dates") or not self.parent.available_dates:
            return

        if index >= 0 and index < len(self.parent.available_dates):
            if index != self.parent.current_date_index:
                # Check for unsaved markers
                if self._check_unsaved_markers():
                    return

                self.parent.current_date_index = index
                self.parent.load_current_date()
                self.parent.state_manager.load_saved_markers()

                if hasattr(self.parent, "data_service") and self.parent.data_service:
                    self.parent.data_service._update_date_dropdown_current_color()

    def prev_date(self) -> None:
        """Navigate to previous date."""
        if self._check_unsaved_markers():
            return

        if self.parent.current_date_index > 0:
            self.parent.current_date_index -= 1

            if hasattr(self.parent.analysis_tab, "date_dropdown"):
                self.parent.analysis_tab.date_dropdown.setCurrentIndex(self.parent.current_date_index)

            self.parent.load_current_date()
            self.parent.state_manager.load_saved_markers()

            if hasattr(self.parent, "data_service") and self.parent.data_service:
                self.parent.data_service._update_date_dropdown_current_color()

    def next_date(self) -> None:
        """Navigate to next date."""
        if self._check_unsaved_markers():
            return

        if self.parent.current_date_index < len(self.parent.available_dates) - 1:
            self.parent.current_date_index += 1

            if hasattr(self.parent.analysis_tab, "date_dropdown"):
                self.parent.analysis_tab.date_dropdown.setCurrentIndex(self.parent.current_date_index)

            self.parent.load_current_date()
            self.parent.state_manager.load_saved_markers()

            if hasattr(self.parent, "data_service") and self.parent.data_service:
                self.parent.data_service._update_date_dropdown_current_color()

    def _check_unsaved_markers(self) -> bool:
        """Check for unsaved markers before navigation."""
        if not hasattr(self.parent, "plot_widget") or not self.parent.plot_widget:
            return False

        if hasattr(self.parent.plot_widget, "markers_saved") and not self.parent.plot_widget.markers_saved:
            reply = QMessageBox.question(
                self.parent,
                "Unsaved Markers",
                "You have unsaved markers. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.No

        return False

    def refresh_file_dropdown_indicators(self) -> None:
        """Refresh file dropdown to show marker indicators."""
        if hasattr(self.parent, "_refresh_file_dropdown_indicators"):
            self.parent._refresh_file_dropdown_indicators()

    def update_navigation_buttons(self) -> None:
        """Update navigation button states."""
        if not hasattr(self.parent, "analysis_tab"):
            return

        if hasattr(self.parent.analysis_tab, "prev_date_btn"):
            self.parent.analysis_tab.prev_date_btn.setEnabled(self.parent.current_date_index > 0)

        if hasattr(self.parent.analysis_tab, "next_date_btn"):
            self.parent.analysis_tab.next_date_btn.setEnabled(self.parent.current_date_index < len(self.parent.available_dates) - 1)

    def on_file_selected_from_table(self, file_info: dict) -> None:
        """Handle file selection from table widget."""
        # Clear marker index cache when new file is selected for performance
        if hasattr(self.parent, "_marker_index_cache"):
            self.parent._marker_index_cache.clear()

        # CRITICAL FIX: Clear algorithm caches when file selection changes
        if hasattr(self.parent, "data_service") and self.parent.data_service:
            self.parent.data_service._clear_all_algorithm_caches()
            logger.debug("Cleared algorithm caches due to file selection change")

        try:
            logger.info("=== TABLE FILE SELECTION START: file_info=%s ===", file_info)

            # Disable activity source dropdown during file loading
            if hasattr(self.parent, "analysis_tab") and hasattr(self.parent.analysis_tab, "set_activity_source_dropdown_enabled"):
                self.parent.analysis_tab.set_activity_source_dropdown_enabled(False)

            # Check for unsaved markers before changing file
            logger.info("Step 1: Checking for unsaved markers")
            if not self.parent._check_unsaved_markers_before_navigation():
                logger.info("Step 1: User canceled file change due to unsaved markers")
                # Re-enable activity source dropdown since we're not changing files
                if hasattr(self.parent, "analysis_tab") and hasattr(self.parent.analysis_tab, "set_activity_source_dropdown_enabled"):
                    self.parent.analysis_tab.set_activity_source_dropdown_enabled(True)
                return
            logger.info("Step 1: Unsaved marker check completed successfully")

            # Validate file info
            if not file_info or not file_info.get("filename"):
                logger.error("Step 2: Invalid file info: %s", file_info)
                QMessageBox.critical(self.parent, "File Error", "Invalid file information.")
                return

            filename = file_info.get("filename")
            logger.info("Step 2: Processing file: %s", filename)

            # Store file info
            self.parent.current_file_info = file_info
            self.parent.selected_file = file_info.get("path") or filename

            # Clear cache when new file is selected
            logger.info("Step 3: Clearing caches")
            self.parent.main_48h_data = None
            if hasattr(self.parent.plot_widget, "main_48h_axis_y_data"):
                self.parent.plot_widget.main_48h_axis_y_data = None
            self.parent.current_date_48h_cache.clear()
            logger.info("Step 3: Cache clearing completed")

            # Load the file and get available dates using DataManager
            logger.info("Step 4: Preparing to load file")
            skip_rows = self.parent.skip_rows_spin.value() if hasattr(self.parent, "skip_rows_spin") else 10
            logger.info("Step 4: Loading file with skip_rows: %s", skip_rows)

            # Wrap file loading in try-catch
            try:
                logger.info("Step 5: Calling data_service.data_manager.load_selected_file")
                self.parent.available_dates = self.parent.data_service.data_manager.load_selected_file(file_info, skip_rows)
                logger.info(
                    "Step 5: File loaded successfully - available dates: %s", len(self.parent.available_dates) if self.parent.available_dates else 0
                )
            except Exception as load_error:
                logger.exception("Step 5: Failed to load file %s: %s", filename, load_error)
                import traceback

                logger.exception("Step 5: Full traceback: %s", traceback.format_exc())
                QMessageBox.critical(
                    self.parent,
                    "File Loading Error",
                    f"Could not load file:\n{filename}\n\nError: {load_error!s}",
                )
                return

            logger.info("Step 6: Checking if dates were loaded")
            if self.parent.available_dates:
                logger.info("Step 6: Dates available, proceeding with UI updates")
                # Reset date index for new file
                self.parent.current_date_index = 0
                logger.info("Step 6a: Set current_date_index to 0")

                logger.info("Step 7: Populating date dropdown")
                self.parent.populate_date_dropdown()
                logger.info("Step 7: Date dropdown populated successfully")

                # Update the current date color based on marker status
                if hasattr(self.parent, "data_service"):
                    self.parent.data_service._update_date_dropdown_current_color()

                logger.info("Step 8: Loading current date")
                self.parent.load_current_date()
                logger.info("Step 8: Current date loaded successfully")

                logger.info("Step 9: Loading saved markers")
                self.parent.load_saved_markers()
                logger.info("Step 9: Saved markers loaded successfully")

                logger.info("Step 10: Loading diary data")
                self.parent._load_diary_data_for_file()
                logger.info("Step 10: Diary data loaded successfully")

                # Update activity source dropdown to reflect current preferences
                if hasattr(self.parent, "analysis_tab") and hasattr(self.parent.analysis_tab, "update_activity_source_dropdown"):
                    self.parent.analysis_tab.update_activity_source_dropdown()
            else:
                logger.warning("Step 6: No available dates found")

            logger.info("=== TABLE FILE SELECTION COMPLETED SUCCESSFULLY ===")

        except Exception as e:
            logger.exception("=== TABLE FILE SELECTION FAILED ===")
            import traceback

            logger.exception("Full traceback: %s", traceback.format_exc())

            # Show user-friendly error
            QMessageBox.critical(
                self.parent,
                "File Selection Error",
                f"An error occurred while selecting the file:\n{e!s}",
            )

            # Reset to safe state
            self.parent.selected_file = None
            self.parent.available_dates = []
            self.parent.current_date_index = 0
            self.parent.date_dropdown.clear()
            self.parent.date_dropdown.addItem("Error loading file")
            self.parent.date_dropdown.setItemData(0, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
            self.parent.date_dropdown.setEnabled(False)
            self.parent.prev_date_btn.setEnabled(False)
            self.parent.next_date_btn.setEnabled(False)
