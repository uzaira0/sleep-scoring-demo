#!/usr/bin/env python3
"""
Window State Manager for Sleep Scoring Application.

Manages application state including:
- Current file and date selection tracking
- Marker saved/unsaved state
- Marker save/load operations
- Autosave functionality
- State caching for performance
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

from sleep_scoring_app.core.constants import (
    AlgorithmType,
    ButtonStyle,
    ButtonText,
    FeatureFlags,
    InfoMessage,
    SuccessMessage,
    WindowTitle,
)
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepMetrics, SleepPeriod

if TYPE_CHECKING:
    from PyQt6.QtCore import QTimer

    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

logger = logging.getLogger(__name__)


class WindowStateManager:
    """
    Manages application state for the main window.

    Responsibilities:
    - Track current file and date selection
    - Manage marker saved/unsaved state
    - Handle marker save/load operations
    - Perform autosave operations
    - Cache marker status for performance
    - Update UI components to reflect state changes
    """

    def __init__(self, parent: SleepScoringMainWindow) -> None:
        """
        Initialize the window state manager.

        Args:
            parent: Reference to main window for UI and service access

        """
        self.parent = parent

        # State tracking
        self.markers_saved: bool = True
        self.unsaved_changes_exist: bool = False

        # Performance caches
        self._marker_status_cache: dict[str, dict] = {}
        self._metrics_cache: list[SleepMetrics] | None = None
        self._marker_index_cache: dict[float, int] = {}

        # Table update throttling
        self._last_table_update_time: float = 0.0
        self._pending_markers: DailySleepMarkers | None = None
        self._table_update_timer: QTimer | None = None

        logger.info("WindowStateManager initialized")

    def invalidate_marker_status_cache(self, filename: str | None = None) -> None:
        """
        Invalidate the marker status cache for a specific file or all files.

        Args:
            filename: Specific filename to invalidate, or None for all files

        """
        if filename:
            self._marker_status_cache.pop(filename, None)
            logger.debug(f"Invalidated marker status cache for {filename}")
        else:
            self._marker_status_cache.clear()
            logger.debug("Cleared entire marker status cache")

    def invalidate_metrics_cache(self) -> None:
        """Invalidate the metrics cache to force reload on next access."""
        self._metrics_cache = None
        logger.debug("Invalidated metrics cache")

        # Refresh export tab data summary if it exists
        if hasattr(self.parent, "export_tab") and self.parent.export_tab is not None:
            self.parent.export_tab.refresh_data_summary()

    def get_cached_metrics(self) -> list[SleepMetrics]:
        """
        Get cached sleep metrics or load from database if not cached.

        Returns:
            List of all sleep metrics from database

        """
        if self._metrics_cache is None:
            self._metrics_cache = self.parent.db_manager.load_sleep_metrics()
            logger.debug(f"Loaded {len(self._metrics_cache)} metrics into cache")
        return self._metrics_cache

    def save_current_markers(self) -> None:
        """Save current markers permanently to database."""
        # Check if we have any complete periods
        if not hasattr(self.parent.plot_widget, "daily_sleep_markers") or not self.parent.plot_widget.daily_sleep_markers.get_complete_periods():
            QMessageBox.warning(self.parent, WindowTitle.NO_MARKERS, InfoMessage.NO_MARKERS_TO_SAVE)
            return

        if not self.parent.selected_file or not self.parent.available_dates:
            QMessageBox.warning(self.parent, "No File Selected", "Please select a file and date first.")
            return

        try:
            # Get current date
            current_date = self.parent.available_dates[self.parent.current_date_index]
            date_str = current_date.strftime("%Y-%m-%d")

            # Get algorithm results from plot widget
            sadeh_results = getattr(self.parent.plot_widget, "sadeh_results", [])
            choi_results = (
                self.parent.plot_widget.get_choi_results_per_minute() if hasattr(self.parent.plot_widget, "get_choi_results_per_minute") else []
            )
            nwt_sensor_results = (
                self.parent.plot_widget.get_nonwear_sensor_results_per_minute()
                if hasattr(self.parent.plot_widget, "get_nonwear_sensor_results_per_minute")
                else []
            )
            axis_y_data = getattr(self.parent.plot_widget, "axis_y_data", [])
            x_data = getattr(self.parent.plot_widget, "x_data", [])

            # Get main sleep period
            main_sleep = self.parent.plot_widget.daily_sleep_markers.get_main_sleep()
            if not main_sleep or not main_sleep.is_complete:
                QMessageBox.warning(self.parent, WindowTitle.NO_MARKERS, "No complete sleep period to save.")
                return

            # Convert to legacy format for calculate_sleep_metrics_object
            legacy_markers = [main_sleep.onset_timestamp, main_sleep.offset_timestamp]

            # Calculate comprehensive sleep metrics
            sleep_metrics = self.parent.data_manager.calculate_sleep_metrics_object(
                legacy_markers,
                sadeh_results,
                choi_results,
                axis_y_data,
                x_data,
                self.parent.selected_file,
                nwt_sensor_results,
            )

            if sleep_metrics:
                # Update metadata
                sleep_metrics.analysis_date = date_str
                sleep_metrics.updated_at = datetime.now().isoformat()
                sleep_metrics.filename = Path(self.parent.selected_file).name
                sleep_metrics.daily_sleep_markers = self.parent.plot_widget.daily_sleep_markers

                # Save to database
                self.parent.export_manager.save_comprehensive_sleep_metrics([sleep_metrics], AlgorithmType.COMBINED)

                # Update state
                self.parent.plot_widget.markers_saved = True
                self.markers_saved = True
                self.unsaved_changes_exist = False

                # Invalidate caches (both window_state and main_window caches)
                self.invalidate_marker_status_cache(Path(self.parent.selected_file).name)
                self.invalidate_metrics_cache()
                self.parent._invalidate_metrics_cache()  # Also invalidate main_window cache for export tab

                # Update UI
                self.parent.save_markers_btn.setText(ButtonText.MARKERS_SAVED)
                self.parent.save_markers_btn.setStyleSheet(ButtonStyle.SAVE_MARKERS_SAVED)
                self.parent.no_sleep_btn.setText(ButtonText.MARK_NO_SLEEP)
                self.parent.no_sleep_btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)

                # Refresh indicators
                if hasattr(self.parent, "_refresh_file_dropdown_indicators"):
                    self.parent._refresh_file_dropdown_indicators()
                if hasattr(self.parent, "populate_date_dropdown"):
                    self.parent.populate_date_dropdown()
                if hasattr(self.parent, "data_service"):
                    self.parent.data_service._update_date_dropdown_current_color()

                # Show success message
                QMessageBox.information(
                    self.parent,
                    "Markers Saved",
                    f"Sleep markers saved for {Path(self.parent.selected_file).name} on {date_str}\n\n"
                    "These markers will be restored when you reload this file and date.",
                )

                logger.info(f"Saved markers for {Path(self.parent.selected_file).name} on {date_str}")

                # Restore arrows after dialog
                if hasattr(self.parent.plot_widget, "daily_sleep_markers"):
                    selected_period = self.parent.plot_widget.get_selected_marker_period()
                    if selected_period and selected_period.is_complete:
                        self.parent.plot_widget.redraw_markers()
                        self.parent.plot_widget.apply_sleep_scoring_rules(selected_period)

        except Exception as e:
            logger.exception(f"Error saving markers: {e}")
            QMessageBox.critical(
                self.parent,
                "Save Failed",
                f"Failed to save markers.\n\nDetails: {e}",
            )

    def clear_current_markers(self) -> None:
        """Clear current markers from both display and database."""
        # Get current date info
        date_str = None
        if self.parent.selected_file and self.parent.available_dates:
            current_date = self.parent.available_dates[self.parent.current_date_index]
            date_str = current_date.strftime("%Y-%m-%d")

        # Confirm with user
        msg_box = QMessageBox(self.parent)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("⚠️ Clear Markers - Permanent Deletion")
        msg_box.setText(f"<b>WARNING: You are about to permanently delete all markers for {date_str if date_str else 'current date'}</b>")
        msg_box.setInformativeText(
            "This action will:\n"
            "• Delete BOTH autosaved AND permanently saved markers\n"
            "• Remove all sleep onset and offset markers\n"
            "• CANNOT BE UNDONE\n\n"
            "Are you absolutely sure you want to proceed?"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        reply = msg_box.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear visual markers
        self.parent.plot_widget.clear_sleep_markers()

        # Clear time input fields
        if hasattr(self.parent, "onset_time_input"):
            self.parent.onset_time_input.clear()
        if hasattr(self.parent, "offset_time_input"):
            self.parent.offset_time_input.clear()

        # Clear from database
        filename = None
        if self.parent.selected_file and self.parent.available_dates:
            try:
                filename = Path(self.parent.selected_file).name
                current_date = self.parent.available_dates[self.parent.current_date_index]
                date_str = current_date.strftime("%Y-%m-%d")

                success = self.parent.db_manager.delete_sleep_metrics_for_date(filename, date_str)
                if success:
                    logger.info(f"Cleared all markers for {filename} on {date_str}")
                else:
                    logger.warning(f"Failed to clear markers for {filename} on {date_str}")
            except Exception as e:
                logger.warning(f"Error clearing markers from database: {e}")

        # Update UI
        self.parent.update_sleep_info([])
        self.parent.save_markers_btn.setText(ButtonText.SAVE_MARKERS)
        self.parent.save_markers_btn.setStyleSheet(ButtonStyle.SAVE_MARKERS)
        self.parent.plot_widget.markers_saved = False
        self.parent.no_sleep_btn.setText(ButtonText.MARK_NO_SLEEP)
        self.parent.no_sleep_btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)

        # Invalidate caches (both marker status and metrics caches)
        if filename:
            self.invalidate_marker_status_cache(filename)
            if hasattr(self.parent, "data_service"):
                self.parent.data_service.verify_cache_consistency(filename)
        self.invalidate_metrics_cache()
        self.parent._invalidate_metrics_cache()  # Also invalidate main_window cache for export tab

        # Refresh UI
        if hasattr(self.parent, "_refresh_file_dropdown_indicators"):
            self.parent._refresh_file_dropdown_indicators()
        if hasattr(self.parent, "populate_date_dropdown"):
            self.parent.populate_date_dropdown()
        if hasattr(self.parent, "data_service"):
            self.parent.data_service._update_date_dropdown_current_color()

    def mark_no_sleep_period(self) -> None:
        """Mark current date as having no sleep period."""
        if not self.parent.selected_file or not self.parent.available_dates:
            QMessageBox.warning(self.parent, "No File Selected", "Please select a file and date first.")
            return

        # Get current date
        current_date = self.parent.available_dates[self.parent.current_date_index]
        date_str = current_date.strftime("%Y-%m-%d")

        # Confirm with user
        reply = QMessageBox.question(
            self.parent,
            "Mark No Sleep",
            f"Mark {date_str} as having no sleep period?\n\nThis will PERMANENTLY DELETE all existing markers for this date and save a record indicating no sleep occurred.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Clear plot markers
            self.parent.plot_widget.clear_sleep_markers()

            # Delete existing markers first
            filename = Path(self.parent.selected_file).name
            try:
                self.parent.db_manager.delete_sleep_metrics_for_date(filename, date_str)
                logger.info(f"Deleted all existing markers for {filename} on {date_str}")
            except Exception as e:
                logger.exception("Error deleting existing markers")
                QMessageBox.warning(self.parent, "Error", f"Failed to delete existing markers: {e}")
                return

            # Extract participant info
            participant_info = self.parent.data_manager.extract_enhanced_participant_info(self.parent.selected_file)

            # Create participant object
            from sleep_scoring_app.core.dataclasses import ParticipantInfo

            participant = ParticipantInfo(
                numerical_id=participant_info["numerical_participant_id"],
                full_id=participant_info["full_participant_id"],
                group=participant_info["participant_group"],
                timepoint=participant_info["participant_timepoint"],
                date=date_str,
            )

            # Create empty daily sleep markers
            from sleep_scoring_app.core.dataclasses import DailySleepMarkers

            daily_markers = DailySleepMarkers()

            # Create sleep metrics with NO_SLEEP indicator
            from sleep_scoring_app.core.constants import SleepStatusValue

            sleep_metrics = SleepMetrics(
                participant=participant,
                filename=Path(self.parent.selected_file).name,
                analysis_date=date_str,
                algorithm_type=AlgorithmType.COMBINED,
                daily_sleep_markers=daily_markers,
                onset_time=SleepStatusValue.NO_SLEEP,
                offset_time=SleepStatusValue.NO_SLEEP,
                total_sleep_time=None,
                sleep_efficiency=None,
                total_minutes_in_bed=None,
                waso=None,
                awakenings=None,
                average_awakening_length=None,
                total_activity=None,
                movement_index=None,
                fragmentation_index=None,
                sleep_fragmentation_index=None,
                sadeh_onset=None,
                sadeh_offset=None,
                choi_onset=None,
                choi_offset=None,
                total_choi_counts=None,
                updated_at=datetime.now().isoformat(),
            )

            # Save to database
            success = self.parent.db_manager.save_sleep_metrics(sleep_metrics, is_autosave=False)

            if success:
                # Update UI
                self.parent.no_sleep_btn.setText(ButtonText.NO_SLEEP_MARKED)
                self.parent.no_sleep_btn.setStyleSheet(ButtonStyle.NO_SLEEP_MARKED)

                # Invalidate caches (both window_state and main_window caches)
                self.invalidate_marker_status_cache(Path(self.parent.selected_file).name)
                self.invalidate_metrics_cache()
                self.parent._invalidate_metrics_cache()  # Also invalidate main_window cache for export tab

                # Refresh UI
                if hasattr(self.parent, "_refresh_file_dropdown_indicators"):
                    self.parent._refresh_file_dropdown_indicators()
                self.parent.update_sleep_info([])
                self.parent.update_marker_tables([], [])

                QMessageBox.information(
                    self.parent,
                    "No Sleep Period Marked",
                    f"Date {date_str} has been marked as having no sleep period.",
                )

                logger.info(f"Marked no sleep period for {Path(self.parent.selected_file).name} on {current_date}")
            else:
                QMessageBox.critical(
                    self.parent,
                    "Error",
                    "Failed to save 'no sleep period' marker to database.",
                )

        except Exception as e:
            logger.exception(f"Error marking no sleep period: {e}")
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Failed to mark no sleep period.\n\nDetails: {e}",
            )

    def load_saved_markers(self) -> None:
        """Load saved markers for current file and date from database."""
        try:
            if not self.parent.selected_file or not self.parent.available_dates:
                logger.warning("Cannot load markers - no file/date selected")
                return

            filename = Path(self.parent.selected_file).name
            current_date = self.parent.available_dates[self.parent.current_date_index]

            logger.info(f"Loading markers for: {filename}, date: {current_date}")

            # Load from database (returns list, get first item)
            metrics_list = self.parent.db_manager.load_sleep_metrics(filename, current_date.strftime("%Y-%m-%d"))
            sleep_metrics = metrics_list[0] if metrics_list else None

            if sleep_metrics:
                # Check if this is a "no sleep period" entry (indicated by onset_time and offset_time == "NO_SLEEP")
                if sleep_metrics.onset_time == "NO_SLEEP" and sleep_metrics.offset_time == "NO_SLEEP":
                    logger.info("This is a 'no sleep period' entry")
                    self.parent.plot_widget.clear_sleep_markers()
                    self.parent.no_sleep_btn.setText(ButtonText.NO_SLEEP_MARKED)
                    self.parent.no_sleep_btn.setStyleSheet(ButtonStyle.NO_SLEEP_MARKED)
                    self.parent.update_sleep_info([])
                    self.parent.update_marker_tables([], [])
                    return

                # Load daily sleep markers
                if sleep_metrics.daily_sleep_markers:
                    logger.info("Loading daily sleep markers")
                    self.parent.plot_widget.load_daily_sleep_markers(sleep_metrics.daily_sleep_markers, markers_saved=True)
                    self.parent.save_markers_btn.setText(ButtonText.MARKERS_SAVED)
                    self.parent.save_markers_btn.setStyleSheet(ButtonStyle.SAVE_MARKERS_SAVED)
                    self.markers_saved = True
                    self.unsaved_changes_exist = False
                    logger.info("Markers loaded successfully")
            else:
                logger.info(f"No saved markers found for {filename} on {current_date}")
                self.parent.plot_widget.clear_sleep_markers()

        except Exception as e:
            logger.exception(f"Error loading saved markers: {e}")

    def create_sleep_period_from_timestamps(
        self, onset_timestamp: float | None, offset_timestamp: float | None, is_main_sleep: bool = False
    ) -> SleepPeriod | None:
        """
        Create a sleep period from timestamps, handling both complete and incomplete periods.

        Args:
            onset_timestamp: Unix timestamp for sleep onset (or None)
            offset_timestamp: Unix timestamp for sleep offset (or None)
            is_main_sleep: Whether this should be treated as main sleep vs nap

        Returns:
            The created SleepPeriod or None if creation failed

        """
        try:
            from sleep_scoring_app.core.dataclasses import MarkerType, SleepPeriod

            # Need at least one timestamp
            if not onset_timestamp and not offset_timestamp:
                return None

            # Find available slot in daily_sleep_markers
            slot = None
            if not self.parent.plot_widget.daily_sleep_markers.period_1:
                slot = 1
            elif not self.parent.plot_widget.daily_sleep_markers.period_2:
                slot = 2
            elif not self.parent.plot_widget.daily_sleep_markers.period_3:
                slot = 3
            elif not self.parent.plot_widget.daily_sleep_markers.period_4:
                slot = 4
            else:
                # Check if we can replace an existing period
                # If creating main sleep, replace any existing main sleep
                if is_main_sleep:
                    main_sleep = self.parent.plot_widget.daily_sleep_markers.get_main_sleep()
                    if main_sleep:
                        # Update existing main sleep
                        main_sleep.onset_timestamp = onset_timestamp
                        main_sleep.offset_timestamp = offset_timestamp
                        if onset_timestamp and offset_timestamp:
                            self.parent.plot_widget.apply_sleep_scoring_rules(main_sleep)
                        return main_sleep

                # No available slots
                logger.warning("No available slots for new sleep period")
                return None

            # Create new sleep period
            new_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
                marker_index=slot,
                marker_type=MarkerType.MAIN_SLEEP if is_main_sleep else MarkerType.NAP,
            )

            # Assign to appropriate slot
            if slot == 1:
                self.parent.plot_widget.daily_sleep_markers.period_1 = new_period
            elif slot == 2:
                self.parent.plot_widget.daily_sleep_markers.period_2 = new_period
            elif slot == 3:
                self.parent.plot_widget.daily_sleep_markers.period_3 = new_period
            elif slot == 4:
                self.parent.plot_widget.daily_sleep_markers.period_4 = new_period

            # Apply sleep scoring rules if complete
            if new_period.is_complete:
                self.parent.plot_widget.apply_sleep_scoring_rules(new_period)
            else:
                # Set as current marker being placed if incomplete
                self.parent.plot_widget.current_marker_being_placed = new_period

            return new_period

        except Exception as e:
            logger.error(f"Error creating sleep period from timestamps: {e}", exc_info=True)
            return None

    def handle_sleep_markers_changed(self, daily_sleep_markers: DailySleepMarkers) -> None:
        """Handle sleep marker changes - combines both info update and table update."""
        # Initialize cache for marker indices if not exists
        if not hasattr(self.parent, "_marker_index_cache"):
            self.parent._marker_index_cache = {}

        # Throttle table updates during rapid changes (like dragging)
        if not hasattr(self.parent, "_last_table_update_time"):
            self.parent._last_table_update_time = 0
        if not hasattr(self.parent, "_table_update_timer"):
            from PyQt6.QtCore import QTimer

            self.parent._table_update_timer = QTimer()
            self.parent._table_update_timer.setSingleShot(True)
            self.parent._table_update_timer.timeout.connect(self.parent._force_table_update)

        import time

        current_time = time.time()
        time_since_last_update = current_time - self.parent._last_table_update_time

        # Store current markers for delayed update
        self.parent._pending_markers = daily_sleep_markers

        # Use the currently selected marker set from the plot widget
        selected_period = getattr(self.parent.plot_widget, "get_selected_marker_period", lambda: None)()
        if selected_period and selected_period.is_complete:
            # Use the selected marker set for display
            markers = [selected_period.onset_timestamp, selected_period.offset_timestamp]

            # Always update sleep info immediately (lightweight)
            self.parent.update_sleep_info(markers)

            # Update tables with optimized caching
            if time_since_last_update > 0.05:  # 50ms throttle (more responsive)
                # Use cached indices if available
                onset_idx = self.parent._marker_index_cache.get(selected_period.onset_timestamp)
                offset_idx = self.parent._marker_index_cache.get(selected_period.offset_timestamp)

                # Get surrounding data using cached indices
                onset_data = self.parent._get_marker_data_cached(selected_period.onset_timestamp, onset_idx)
                offset_data = self.parent._get_marker_data_cached(selected_period.offset_timestamp, offset_idx)

                # Update tables only if we have data
                if onset_data or offset_data:
                    self.parent.update_marker_tables(onset_data, offset_data)
                    self.parent._last_table_update_time = current_time
        else:
            # Fallback to first complete period if no selection or selected period incomplete
            complete_periods = daily_sleep_markers.get_complete_periods()
            if complete_periods:
                first_period = complete_periods[0]
                markers = [first_period.onset_timestamp, first_period.offset_timestamp]

                # Always update sleep info immediately
                self.parent.update_sleep_info(markers)

                # Throttle table updates
                if time_since_last_update > 0.05:  # 50ms throttle
                    onset_idx = self.parent._marker_index_cache.get(first_period.onset_timestamp)
                    offset_idx = self.parent._marker_index_cache.get(first_period.offset_timestamp)

                    onset_data = self.parent._get_marker_data_cached(first_period.onset_timestamp, onset_idx)
                    offset_data = self.parent._get_marker_data_cached(first_period.offset_timestamp, offset_idx)

                    if onset_data or offset_data:
                        self.parent.update_marker_tables(onset_data, offset_data)
                        self.parent._last_table_update_time = current_time
            else:
                markers = []
                self.parent.update_sleep_info(markers)
                # Clear tables when no markers
                if time_since_last_update > 0.05:
                    self.parent.update_marker_tables([], [])
                    self.parent._last_table_update_time = current_time

        # Schedule a delayed table update to ensure final state is shown
        self.parent._table_update_timer.start(100)  # 100ms delay to catch end of drag

        # Autosave on marker change (if enabled and we have valid markers and a selected file)
        if (
            FeatureFlags.ENABLE_AUTOSAVE
            and len(markers) == 2
            and self.parent.selected_file
            and self.parent.available_dates
            and not getattr(self.parent.plot_widget, "markers_saved", False)
        ):
            self.parent.autosave_on_marker_change(markers)

        # Reset save button state when markers are modified (unless they were just loaded)
        if hasattr(self.parent, "save_markers_btn") and not getattr(self.parent.plot_widget, "markers_saved", False):
            self.parent.save_markers_btn.setText(ButtonText.SAVE_MARKERS)
            self.parent.save_markers_btn.setStyleSheet(ButtonStyle.SAVE_MARKERS)
            self.parent.plot_widget.markers_saved = False

        # Reset no sleep button state when markers are present (behave consistently with save button)
        if hasattr(self.parent, "no_sleep_btn"):
            if len(markers) >= 2:  # We have complete markers
                # Reset to normal "Mark No Sleep" state since we now have markers
                self.parent.no_sleep_btn.setText(ButtonText.MARK_NO_SLEEP)
                self.parent.no_sleep_btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)
            elif len(markers) == 0:  # No markers at all
                # Could be in "No Sleep Marked" state or normal state - leave as is
                # This handles the case where user clears all markers
                pass

    def clear_all_markers(self) -> None:
        """Clear all sleep markers and metrics from database (preserves imported data)."""
        from PyQt6.QtWidgets import QMessageBox

        # Get current statistics
        try:
            stats = self.parent.db_manager.get_database_stats()
            total_records = stats.get("total_records", 0)
            autosave_records = stats.get("autosave_records", 0) if FeatureFlags.ENABLE_AUTOSAVE else 0

            if total_records == 0 and autosave_records == 0:
                QMessageBox.information(
                    self.parent,
                    "Clear All Markers",
                    "No sleep markers or metrics found in the database.",
                )
                return

            # Detailed confirmation dialog
            message = "Are you sure you want to clear all sleep markers and metrics from the database?\n\n"
            message += "This will remove:\n"
            message += f"• {total_records} sleep metrics records\n"
            if FeatureFlags.ENABLE_AUTOSAVE and autosave_records > 0:
                message += f"• {autosave_records} autosave records\n"
            message += "\n"

            reply = QMessageBox.question(
                self.parent,
                "Clear All Markers",
                message + "This action cannot be undone.\nImported raw data will be preserved.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Clear markers
                result = self.parent.db_manager.clear_all_markers()

                # Update UI
                self.parent._invalidate_metrics_cache()
                self.parent.data_service.invalidate_marker_status_cache()
                self.parent.update_data_source_status()

                # Show success message
                total_cleared = result.get("total_cleared", 0)
                details = f"Successfully cleared {total_cleared} records from the database.\n\n"
                details += "Details:\n"
                details += f"• Sleep metrics: {result.get('sleep_metrics_cleared', 0)}\n"
                if FeatureFlags.ENABLE_AUTOSAVE:
                    details += f"• Autosave records: {result.get('autosave_metrics_cleared', 0)}"

                QMessageBox.information(
                    self.parent,
                    "Clear All Markers",
                    details,
                )

                # Refresh file indicators (preserve selection)
                self.parent.load_available_files(preserve_selection=True)

                # Refresh current date dropdown if we have a file selected
                if self.parent.selected_file and self.parent.available_dates:
                    self.parent.populate_date_dropdown()
                    # Update the current date color
                    if hasattr(self.parent, "data_service"):
                        self.parent.data_service._update_date_dropdown_current_color()

                # Clear current plot if any
                if hasattr(self.parent, "plot_widget"):
                    self.parent.plot_widget.clear_plot()

        except Exception as e:
            QMessageBox.critical(self.parent, "Clear All Markers", f"Failed to clear markers: {e}")
