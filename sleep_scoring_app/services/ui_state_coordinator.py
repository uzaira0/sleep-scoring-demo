#!/usr/bin/env python3
"""
UI State Coordinator Service.

Manages UI state including enable/disable controls, status updates,
and visibility toggles.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sleep_scoring_app.core.constants import ButtonStyle, ButtonText

if TYPE_CHECKING:
    from sleep_scoring_app.ui.protocols import MainWindowProtocol

logger = logging.getLogger(__name__)


class UIStateCoordinator:
    """
    Coordinates UI state changes across the main window.

    Responsibilities:
    - Enable/disable UI controls
    - Update status bar and labels
    - Manage visibility of progress components
    - Clear plot and UI state
    - Update data source status
    """

    def __init__(self, parent: MainWindowProtocol) -> None:
        """
        Initialize the UI state coordinator.

        Args:
            parent: Reference to main window for UI access

        """
        self.parent = parent
        logger.info("UIStateCoordinator initialized")

    def set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable UI controls based on folder selection status."""
        try:
            # File selection and navigation
            self.parent.file_selector.setEnabled(enabled)
            self.parent.prev_date_btn.setEnabled(enabled and self.parent.current_date_index > 0)
            self.parent.next_date_btn.setEnabled(enabled and self.parent.current_date_index < len(self.parent.available_dates) - 1)

            # View mode buttons
            self.parent.view_24h_btn.setEnabled(enabled)
            self.parent.view_48h_btn.setEnabled(enabled)

            # Manual time entry
            self.parent.onset_time_input.setEnabled(enabled)
            self.parent.offset_time_input.setEnabled(enabled)

            # Action buttons
            self.parent.save_markers_btn.setEnabled(enabled)
            self.parent.no_sleep_btn.setEnabled(enabled)
            self.parent.clear_markers_btn.setEnabled(enabled)
            self.parent.export_btn.setEnabled(enabled)

            # Plot widget
            self.parent.plot_widget.setEnabled(enabled)

            # Update folder info
            if enabled:
                self.update_folder_info_label()
        except AttributeError as e:
            logger.warning("Cannot set UI enabled state - missing widget: %s", e)

    def clear_plot_and_ui_state(self) -> None:
        """Clear plot and UI state when switching filters."""
        try:
            # Clear the plot visualization
            if self.parent.plot_widget:
                self.parent.plot_widget.clear_plot()
                self.parent.plot_widget.clear_sleep_markers()

            # Reset UI state
            self.parent.selected_file = None
            self.parent.available_dates = []
            self.parent.current_date_index = 0

            # Clear status labels
            self.parent.total_duration_label.setText("")

            # NOTE: Save button updates handled by SaveButtonConnector via Redux

            # Clear date dropdown
            self.parent.date_dropdown.clear()
            self.parent.date_dropdown.setEnabled(False)

            # Disable navigation buttons
            self.parent.prev_date_btn.setEnabled(False)
            self.parent.next_date_btn.setEnabled(False)

            logger.debug("Cleared plot and UI state for filter change")

        except AttributeError as e:
            logger.warning("Error clearing plot and UI state - missing widget: %s", e)

    def update_folder_info_label(self) -> None:
        """Update the file selection label with current file count."""
        try:
            file_count = len(self.parent.data_service.available_files)

            # Update the file selection label instead of folder info label
            if self.parent.data_service.get_database_mode():
                self.parent.file_selection_label.setText(f"File Selection ({file_count} files from database)")
            elif self.parent.data_service.get_data_folder():
                folder_name = Path(self.parent.data_service.get_data_folder()).name
                self.parent.file_selection_label.setText(f"File Selection ({file_count} files from {folder_name})")
            else:
                self.parent.file_selection_label.setText(f"File Selection ({file_count} files)")

            # Keep folder_info_label empty for compatibility
            self.parent.folder_info_label.setText("")
        except AttributeError as e:
            logger.debug("Cannot update folder info label: %s", e)

    def update_status_bar(self, message: str | None = None) -> None:
        """Update the status bar with current information."""
        try:
            if message:
                self.parent.status_bar.showMessage(message, 5000)  # Show for 5 seconds

            # Update data source label - all data is now always from database
            self.parent.data_source_label.setText("Activity: Database")

            # Update file count
            row_count = self.parent.file_selector.table.rowCount()
            self.parent.file_count_label.setText(f"Files: {row_count}")
        except AttributeError:
            # Fallback if file selector not available
            try:
                self.parent.file_count_label.setText("Files: 0")
            except AttributeError:
                pass

    def update_data_source_status(self) -> None:
        """Update the data source status label."""
        try:
            # All data is now always stored in database
            stats = self.parent.db_manager.get_database_stats()
            file_count = stats.get("unique_files", 0)
            record_count = stats.get("total_records", 0)

            status_text = f"{file_count} imported files, {record_count} total records"
            style = "color: #27ae60; font-weight: bold;"

            # Update the activity status label
            self.parent.data_settings_tab.activity_status_label.setText(status_text)
            self.parent.data_settings_tab.activity_status_label.setStyleSheet(style)

        except AttributeError as e:
            # Tab or label not available
            logger.debug("Cannot update data source status: %s", e)
        except Exception as e:
            error_text = "Status unavailable"
            try:
                self.parent.data_settings_tab.activity_status_label.setText(error_text)
                self.parent.data_settings_tab.activity_status_label.setStyleSheet("color: #e74c3c;")
            except AttributeError:
                pass
            logger.warning("Error updating data source status: %s", e)

    def toggle_adjacent_day_markers(self, show: bool) -> None:
        """Toggle display of adjacent day markers from adjacent days."""
        logger.info(f"Toggling adjacent day markers: {show}")

        if not self.parent.plot_widget:
            logger.warning("Plot widget not available for adjacent day markers")
            return

        # Store the state
        self.parent.show_adjacent_day_markers = show

        if show:
            # Load and display adjacent day markers
            self._load_and_display_adjacent_day_markers()
        else:
            # Clear adjacent day markers
            self._clear_adjacent_day_markers()

    def _load_and_display_adjacent_day_markers(self) -> None:
        """Load markers from adjacent days and display as adjacent day markers."""
        if not self.parent.available_dates or self.parent.current_date_index is None:
            logger.info("Adjacent day markers: No available dates or current date index")
            return

        current_date = self.parent.available_dates[self.parent.current_date_index]
        adjacent_day_markers = []

        logger.info(f"Loading adjacent day markers for current date: {current_date}, index: {self.parent.current_date_index}")
        logger.info(f"Total available dates: {len(self.parent.available_dates)}")

        # Load markers from day-1 (if exists)
        if self.parent.current_date_index > 0:
            prev_date = self.parent.available_dates[self.parent.current_date_index - 1]
            logger.info(f"Loading markers from previous day: {prev_date}")
            prev_markers = self._load_markers_for_date(prev_date)
            logger.info(f"Found {len(prev_markers)} markers for previous day")
            if prev_markers:
                for marker in prev_markers:
                    marker["adjacent_date"] = prev_date.strftime("%Y-%m-%d")
                    marker["is_adjacent_day"] = True
                adjacent_day_markers.extend(prev_markers)

        # Load markers from day+1 (if exists)
        if self.parent.current_date_index < len(self.parent.available_dates) - 1:
            next_date = self.parent.available_dates[self.parent.current_date_index + 1]
            logger.info(f"Loading markers from next day: {next_date}")
            next_markers = self._load_markers_for_date(next_date)
            logger.info(f"Found {len(next_markers)} markers for next day")
            if next_markers:
                for marker in next_markers:
                    marker["adjacent_date"] = next_date.strftime("%Y-%m-%d")
                    marker["is_adjacent_day"] = True
                adjacent_day_markers.extend(next_markers)

        logger.info(f"Total adjacent day markers to display: {len(adjacent_day_markers)}")

        # Display adjacent day markers on plot
        if adjacent_day_markers:
            try:
                logger.info("Displaying adjacent day markers on plot")
                self.parent.plot_widget.display_adjacent_day_markers(adjacent_day_markers)
            except AttributeError:
                logger.exception("Plot widget does not have display_adjacent_day_markers method")
        else:
            logger.info("No adjacent day markers found to display")

    def _load_markers_for_date(self, date):
        """Load sleep markers for a specific date."""
        try:
            filename = Path(self.parent.selected_file).name
            date_str = date.strftime("%Y-%m-%d")
            logger.info(f"Loading markers for file: {filename}, date: {date_str}")

            # First, let's check what dates are actually in the database
            try:
                available_dates = self.parent.db_manager.file_registry.get_available_dates_for_file(filename)
                if False:  # Keep original indentation for cursor lines (dead code)
                    cursor = None  # type: ignore
                    available_dates = [row[0] for row in cursor.fetchall()]
                    logger.info(f"Available dates in database for {filename}: {available_dates}")
            except Exception as e:
                logger.exception(f"Error checking available dates: {e}")

            # Use the same method as regular marker loading (sleep_metrics table)
            saved_data = self.parent.export_manager.db_manager.load_sleep_metrics(filename=filename, analysis_date=date_str)
            logger.info(f"Sleep metrics loaded: {len(saved_data) if saved_data else 0} records")

            # Convert sleep metrics to adjacent day marker format
            markers = []
            if saved_data:
                for record in saved_data:
                    # Get complete periods from daily_sleep_markers
                    complete_periods = record.daily_sleep_markers.get_complete_periods()
                    logger.info(f"Record has {len(complete_periods)} complete periods")

                    for period in complete_periods:
                        if period.onset_timestamp and period.offset_timestamp:
                            marker = {
                                "onset_datetime": period.onset_timestamp,
                                "offset_datetime": period.offset_timestamp,
                            }
                            markers.append(marker)
                            logger.info(f"Added adjacent day marker: onset={period.onset_timestamp}, offset={period.offset_timestamp}")

            logger.info(f"Converted to {len(markers)} adjacent day markers")
            return markers
        except Exception as e:
            logger.exception(f"Error loading markers for date {date}: {e}")
            return []

    def _clear_adjacent_day_markers(self) -> None:
        """Clear all adjacent day markers from the plot."""
        try:
            self.parent.plot_widget.clear_adjacent_day_markers()
        except AttributeError:
            logger.debug("Plot widget does not have clear_adjacent_day_markers method")
