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
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QMessageBox

from sleep_scoring_app.core.constants import (
    AlgorithmType,
    ButtonStyle,
    ButtonText,
    FeatureFlags,
    InfoMessage,
    WindowTitle,
)
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepMetrics, SleepPeriod
from sleep_scoring_app.ui.store import Actions

if TYPE_CHECKING:
    from PyQt6.QtCore import QTimer

    from sleep_scoring_app.ui.protocols import (
        AppStateInterface,
        MainWindowProtocol,
        MarkerOperationsInterface,
        NavigationInterface,
        ServiceContainer,
    )

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

    def __init__(
        self,
        store: Any,
        navigation: NavigationInterface,
        marker_ops: MarkerOperationsInterface,
        app_state: AppStateInterface,
        services: ServiceContainer,
        parent: MainWindowProtocol,
    ) -> None:
        """
        Initialize the window state manager.

        Args:
            store: The UI store
            navigation: Navigation interface
            marker_ops: Marker operations interface
            app_state: App state coordination interface
            services: Service container
            parent: Main window (still needed for some Qt-level access for now)

        """
        self.store = store
        self.navigation = navigation
        self.marker_ops = marker_ops
        self.app_state = app_state
        self.services = services
        self.main_window = parent
        self.parent = parent

        # State tracking
        # NOTE: markers_saved is now managed EXCLUSIVELY by Redux store
        # Access via self.store.state.sleep_markers_dirty
        self.unsaved_changes_exist: bool = False

        # Performance caches
        self._marker_status_cache: dict[str, dict] = {}
        self._metrics_cache: list[SleepMetrics] | None = None

        # Table update throttling and marker index cache
        # These are initialized here instead of lazy-initialized in handle_sleep_markers_changed
        self._marker_index_cache: dict[float, int] = {}
        self._last_table_update_time: float = 0.0
        self._pending_markers: DailySleepMarkers | None = None
        self._table_update_timer: QTimer | None = None

        logger.info("WindowStateManager initialized with decoupled interfaces")

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

        # Also invalidate the data service cache and refresh file table
        if self.services.data_service is not None:
            self.services.data_service.clear_file_cache(filename)

            # Service is headless - provide callback to dispatch to store
            def on_files_loaded(files):
                from sleep_scoring_app.ui.store import Actions

                self.store.dispatch(Actions.files_loaded(files))

            self.services.data_service.load_available_files(load_completion_counts=True, on_files_loaded=on_files_loaded)

    def invalidate_metrics_cache(self) -> None:
        """Invalidate the metrics cache to force reload on next access."""
        self._metrics_cache = None
        logger.debug("Invalidated metrics cache")

        # Refresh export tab data summary via services interface
        if self.services.export_tab is not None:
            self.services.export_tab.refresh_data_summary()

    def get_cached_metrics(self) -> list[SleepMetrics]:
        """
        Get cached sleep metrics or load from database if not cached.

        Returns:
            List of all sleep metrics from database

        """
        if self._metrics_cache is None:
            self._metrics_cache = self.services.db_manager.load_sleep_metrics()
            logger.debug(f"Loaded {len(self._metrics_cache)} metrics into cache")
        return self._metrics_cache

    def save_current_markers(self) -> None:
        """
        Save currently placed markers to the database with validation.

        This method adds UI validation and feedback around the SAME save logic
        used by autosave. Both paths call _autosave_sleep_markers_to_db for consistency.

        Uses Redux store as single source of truth for markers (per CLAUDE.md).
        """
        try:
            # 1. Get markers from Redux store (SINGLE SOURCE OF TRUTH)
            state = self.store.state
            sleep_markers = state.current_sleep_markers
            nonwear_markers = state.current_nonwear_markers

            if not sleep_markers or not sleep_markers.get_complete_periods():
                QMessageBox.warning(self.main_window, WindowTitle.NO_MARKERS, InfoMessage.NO_MARKERS_TO_SAVE)
                return

            if not self.navigation.selected_file or not self.navigation.available_dates:
                QMessageBox.warning(self.main_window, "No File Selected", "Please select a file and date first.")
                return

            # Validate bounds before accessing
            date_index = self.navigation.current_date_index
            if date_index is None or date_index < 0 or date_index >= len(self.navigation.available_dates):
                QMessageBox.warning(self.main_window, "Invalid Date", "Please select a valid date first.")
                return

            main_sleep = sleep_markers.get_main_sleep()
            if not main_sleep:
                QMessageBox.warning(self.main_window, WindowTitle.NO_MARKERS, "No complete sleep period to save.")
                return

            # 2. Use SAME save path as autosave - call BOTH sleep AND nonwear save methods
            # This ensures both manual and auto save use identical logic (symmetric!)
            self.main_window._autosave_sleep_markers_to_db(sleep_markers)

            # Also save nonwear markers if they exist (same as autosave)
            if nonwear_markers and nonwear_markers.get_complete_periods():
                self.main_window._autosave_nonwear_markers_to_db(nonwear_markers)

            # 3. Update Redux state (autosave does this via AutosaveCoordinator, manual does it here)
            self.store.dispatch(Actions.markers_saved())
            self.unsaved_changes_exist = False

            # 4. UI updates handled reactively via Redux connectors

            # 5. Get info for success feedback
            current_date = self.navigation.available_dates[date_index]
            date_str = current_date.strftime("%Y-%m-%d")
            filename = Path(self.navigation.selected_file).name

            # Calculate TST and SE for display (from main_sleep period)
            tst_minutes = (main_sleep.offset_timestamp - main_sleep.onset_timestamp) / 60 if main_sleep.is_complete else 0
            se_percent = 100.0  # Simplified - full metrics calculated in autosave

            # Final success feedback (manual save only)
            QMessageBox.information(
                self.main_window,
                WindowTitle.MARKERS_SAVED,
                f"Sleep markers saved for {filename} on {date_str}\n\nSleep Period Duration: {tst_minutes:.1f} minutes",
            )
            logger.info(f"Saved markers for {filename} on {date_str}")

            # Redraw after save
            plot_widget = self.main_window.plot_widget
            selected_period = plot_widget.get_selected_marker_period()
            if selected_period:
                plot_widget.redraw_markers()
                plot_widget.apply_sleep_scoring_rules(selected_period)

        except Exception as e:
            logger.exception(f"Error saving markers: {e}")
            QMessageBox.critical(self.main_window, "Save Error", f"Failed to save sleep markers:\n{e!s}")

    def clear_current_markers(self) -> None:
        """Clear current markers from both display and database."""
        # Get current date info
        date_str = None
        date_index = self.navigation.current_date_index
        if (
            self.navigation.selected_file
            and self.navigation.available_dates
            and date_index is not None
            and 0 <= date_index < len(self.navigation.available_dates)
        ):
            current_date = self.navigation.available_dates[date_index]
            date_str = current_date.strftime("%Y-%m-%d")

        # Confirm with user
        msg_box = QMessageBox(self.main_window)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("⚠️ Clear Markers - Permanent Deletion")
        msg_box.setText(f"<b>WARNING: You are about to permanently delete all markers for {date_str if date_str else 'current date'}</b>")
        msg_box.setInformativeText(
            "This action will:\n"
            "• Delete BOTH autosaved AND permanently saved markers\n"
            "• Remove all sleep onset and offset markers\n"
            "• Remove all manual nonwear (NWT) markers\n"
            "• CANNOT BE UNDONE\n\n"
            "Are you absolutely sure you want to proceed?"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        reply = msg_box.exec()
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear visual markers (sleep AND nonwear) via services
        pw = self.services.plot_widget
        if pw:
            pw.clear_sleep_markers()
            pw.clear_nonwear_markers()

        # Clear time input fields (Protocol-guaranteed attributes)
        self.main_window.onset_time_input.clear()
        self.main_window.offset_time_input.clear()

        # Clear from database (sleep AND nonwear markers)
        filename = None
        date_index = self.navigation.current_date_index
        if (
            self.navigation.selected_file
            and self.navigation.available_dates
            and date_index is not None
            and 0 <= date_index < len(self.navigation.available_dates)
        ):
            try:
                filename = Path(self.navigation.selected_file).name
                current_date = self.navigation.available_dates[date_index]
                date_str = current_date.strftime("%Y-%m-%d")

                # Clear sleep markers via services
                success = self.services.db_manager.delete_sleep_metrics_for_date(filename, date_str)
                if success:
                    logger.info(f"Cleared sleep markers for {filename} on {date_str}")
                else:
                    logger.warning(f"Failed to clear sleep markers for {filename} on {date_str}")

                # Clear nonwear markers
                try:
                    self.services.db_manager.delete_manual_nonwear_markers(filename, date_str)
                    logger.info(f"Cleared nonwear markers for {filename} on {date_str}")
                except Exception as e:
                    logger.warning(f"Error clearing nonwear markers: {e}")
            except Exception as e:
                logger.warning(f"Error clearing markers from database: {e}")

        # Update UI via app_state interface
        self.app_state.update_sleep_info(None)
        # NOTE: Save button updates handled by SaveButtonConnector via Redux

        # Clear via Redux store (SINGLE source of truth)
        # This triggers reactive updates:
        # - StatusConnector handles no_sleep_btn state
        # - DateDropdownConnector handles dropdown colors
        self.store.dispatch(Actions.markers_cleared())

        # Invalidate caches
        if filename:
            self.invalidate_marker_status_cache(filename)
        self.invalidate_metrics_cache()

    def mark_no_sleep_period(self) -> None:
        """Mark current date as having no sleep period."""
        if not self.navigation.selected_file or not self.navigation.available_dates:
            QMessageBox.warning(self.main_window, "No File Selected", "Please select a file and date first.")
            return

        # Validate bounds before accessing
        date_index = self.navigation.current_date_index
        if date_index is None or date_index < 0 or date_index >= len(self.navigation.available_dates):
            QMessageBox.warning(self.main_window, "Invalid Date", "Please select a valid date first.")
            return

        # Get current date
        current_date = self.navigation.available_dates[date_index]
        date_str = current_date.strftime("%Y-%m-%d")

        # Confirm with user
        reply = QMessageBox.question(
            self.main_window,
            "Mark No Sleep",
            f"Mark {date_str} as having no sleep period?\n\nThis will delete existing SLEEP markers for this date and save a record indicating no sleep occurred.\n\nNWT (nonwear) markers will be preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Clear only SLEEP markers via services
            pw = self.services.plot_widget
            if pw:
                pw.clear_sleep_markers()

            # Delete existing SLEEP metrics only via services
            filename = Path(self.navigation.selected_file).name
            try:
                self.services.db_manager.delete_sleep_metrics_for_date(filename, date_str)
                logger.info(f"Deleted sleep markers for {filename} on {date_str} (NWT markers preserved)")
            except Exception as e:
                logger.exception("Error deleting existing sleep markers")
                QMessageBox.warning(self.main_window, "Error", f"Failed to delete existing sleep markers: {e}")
                return

            # Extract participant info via services
            from dataclasses import replace


            participant_info = self.services.data_manager.extract_enhanced_participant_info(self.navigation.selected_file)
            # Set the date field for this specific analysis
            participant = replace(participant_info, date=date_str)

            # Create empty daily sleep markers
            from sleep_scoring_app.core.dataclasses import DailySleepMarkers

            daily_markers = DailySleepMarkers()

            # Create sleep metrics with NO_SLEEP indicator
            from sleep_scoring_app.core.constants import SleepPeriodDetectorType, SleepStatusValue

            # Get current algorithm and rule from store state
            algorithm_id = self.store.state.sleep_algorithm_id
            rule_id = self.store.state.onset_offset_rule_id

            # Convert algorithm ID to enum
            try:
                algorithm_type = AlgorithmType(algorithm_id) if algorithm_id else AlgorithmType.SADEH_1994_ACTILIFE
            except ValueError:
                algorithm_type = AlgorithmType.SADEH_1994_ACTILIFE

            sleep_metrics = SleepMetrics(
                participant=participant,
                filename=filename,
                analysis_date=date_str,
                algorithm_type=algorithm_type,
                sleep_algorithm_name=algorithm_id,
                sleep_period_detector_id=rule_id or SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S,
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
                overlapping_nonwear_minutes_algorithm=None,
                overlapping_nonwear_minutes_sensor=None,
                updated_at=datetime.now().isoformat(),
            )

            # Save to database via services
            success = self.services.db_manager.save_sleep_metrics(sleep_metrics)

            if success:
                # Update Redux state - this triggers StatusConnector to update the button
                # Get current nonwear markers from Redux to preserve them
                from sleep_scoring_app.ui.store import Actions

                current_nonwear = self.store.state.current_nonwear_markers
                self.store.dispatch(Actions.markers_loaded(sleep=None, nonwear=current_nonwear, is_no_sleep=True))

                # Invalidate caches
                self.invalidate_marker_status_cache(filename)
                self.invalidate_metrics_cache()

                # Refresh UI via app_state
                self.app_state.update_sleep_info(None)
                self.app_state.update_marker_tables([], [])

                if pw:
                    pw.redraw_markers()

                # Final success feedback
                logger.info(f"Marked no sleep period for {filename} on {current_date}")
                QMessageBox.information(
                    self.main_window,
                    "No Sleep Marked",
                    f"Successfully marked no sleep period for {filename} on {date_str}.",
                )
            else:
                QMessageBox.warning(self.main_window, "Save Error", "Failed to save no-sleep entry to database.")

        except Exception as e:
            logger.exception(f"Error marking no sleep period: {e}")
            QMessageBox.critical(self.main_window, "Error", f"Failed to mark no sleep period: {e!s}")

    def load_saved_markers(self) -> None:
        """Load saved markers for current file and date from database."""
        try:
            logger.info("WINDOW STATE: load_saved_markers() START")
            if not self.navigation.selected_file or not self.navigation.available_dates:
                logger.warning("WINDOW STATE: Cannot load markers - no file/date selected")
                return

            # Validate index bounds before accessing
            date_index = self.navigation.current_date_index
            if date_index is None or date_index < 0 or date_index >= len(self.navigation.available_dates):
                logger.warning(f"WINDOW STATE: Invalid date index {date_index} for {len(self.navigation.available_dates)} dates")
                return

            filename = Path(self.navigation.selected_file).name
            current_date = self.navigation.available_dates[date_index]
            date_str = current_date.strftime("%Y-%m-%d")

            logger.info(f"WINDOW STATE: Loading markers for: {filename}, date: {date_str}")

            # Load from database via services interface
            metrics_list = self.services.db_manager.load_sleep_metrics(filename, date_str)
            sleep_metrics = metrics_list[0] if metrics_list else None

            logger.info(f"WINDOW STATE: DB Result: {'Found metrics' if sleep_metrics else 'No metrics found'}")

            # Also load nonwear markers
            from sleep_scoring_app.core.dataclasses_markers import DailyNonwearMarkers

            try:
                nonwear_markers = self.services.db_manager.load_manual_nonwear_markers(filename, date_str)
                periods = nonwear_markers.get_all_periods()
                if periods:
                    logger.info(f"WINDOW STATE: Loaded {len(periods)} nonwear markers")
            except Exception as e:
                logger.warning(f"WINDOW STATE: Error loading nonwear markers: {e}")
                nonwear_markers = DailyNonwearMarkers()

            if sleep_metrics:
                # Check if this is a "no sleep period" entry
                from sleep_scoring_app.core.constants import SleepStatusValue

                if sleep_metrics.onset_time == SleepStatusValue.NO_SLEEP and sleep_metrics.offset_time == SleepStatusValue.NO_SLEEP:
                    logger.info("WINDOW STATE: This is a 'no sleep period' entry")
                    self.store.dispatch_safe(Actions.markers_loaded(sleep=None, nonwear=nonwear_markers))
                    return

                # Load daily sleep markers
                if sleep_metrics.daily_sleep_markers:
                    logger.info("WINDOW STATE: Dispatching markers_loaded to Redux")
                    # dispatch_safe: sync if outside dispatch, async if inside dispatch
                    self.store.dispatch_safe(Actions.markers_loaded(sleep=sleep_metrics.daily_sleep_markers, nonwear=nonwear_markers))
                    self.unsaved_changes_exist = False
                    logger.info("WINDOW STATE: load_saved_markers() complete")
            else:
                logger.info("WINDOW STATE: No saved markers found, dispatching clean state")
                self.store.dispatch_safe(Actions.markers_loaded(sleep=None, nonwear=nonwear_markers))

        except Exception as e:
            logger.exception(f"WINDOW STATE: Error loading saved markers: {e}")

    def create_sleep_period_from_timestamps(
        self, onset_timestamp: float | None, offset_timestamp: float | None, is_main_sleep: bool = False
    ) -> SleepPeriod | None:
        """
        Create a sleep period from timestamps, handling both complete and incomplete periods.

        Uses Redux store as single source of truth (per CLAUDE.md).

        Args:
            onset_timestamp: Unix timestamp for sleep onset (or None)
            offset_timestamp: Unix timestamp for sleep offset (or None)
            is_main_sleep: Whether this should be treated as main sleep vs nap

        Returns:
            The created SleepPeriod or None if creation failed

        """
        try:
            from sleep_scoring_app.core.dataclasses import MarkerType, SleepPeriod
            from sleep_scoring_app.core.dataclasses_markers import DailySleepMarkers

            # Need at least one timestamp
            if not onset_timestamp and not offset_timestamp:
                return None

            # Get markers from Redux store (SINGLE SOURCE OF TRUTH)
            state = self.store.state
            markers = state.current_sleep_markers
            if markers is None:
                markers = DailySleepMarkers()

            # Find available slot
            slot = None
            if not markers.period_1:
                slot = 1
            elif not markers.period_2:
                slot = 2
            elif not markers.period_3:
                slot = 3
            elif not markers.period_4:
                slot = 4
            else:
                # Check if we can replace an existing period
                if is_main_sleep:
                    main_sleep = markers.get_main_sleep()
                    if main_sleep:
                        # Update existing main sleep
                        main_sleep.onset_timestamp = onset_timestamp
                        main_sleep.offset_timestamp = offset_timestamp
                        # Dispatch updated markers to Redux
                        self.store.dispatch(Actions.sleep_markers_changed(markers))
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
                markers.period_1 = new_period
            elif slot == 2:
                markers.period_2 = new_period
            elif slot == 3:
                markers.period_3 = new_period
            elif slot == 4:
                markers.period_4 = new_period

            # Dispatch updated markers to Redux (triggers connectors to update widget)
            self.store.dispatch(Actions.sleep_markers_changed(markers))

            return new_period

        except Exception as e:
            logger.error(f"Error creating sleep period from timestamps: {e}", exc_info=True)
            return None

    def update_tables_visual_only(self, daily_sleep_markers: DailySleepMarkers) -> None:
        """
        Perform visual updates of tables and sleep info WITHOUT store dispatch.
        Use this from connectors to avoid infinite loops.
        """
        import time

        current_time = time.time()
        time_since_last_update = current_time - self.main_window._last_table_update_time

        # Store current markers for delayed update via main window reference
        self.main_window._pending_markers = daily_sleep_markers

        # Use the currently selected marker set from the plot widget via services
        pw = self.services.plot_widget
        selected_period = pw.get_selected_marker_period() if pw else None

        if selected_period and selected_period.is_complete:
            # Always update sleep info immediately (lightweight)
            self.app_state.update_sleep_info(selected_period)

            # Update tables with optimized caching
            if time_since_last_update > 0.05:  # 50ms throttle
                # Use cached indices if available
                onset_idx = self.main_window._marker_index_cache.get(selected_period.onset_timestamp)
                offset_idx = self.main_window._marker_index_cache.get(selected_period.offset_timestamp)

                # Get surrounding data using cached indices via main window callback
                onset_data = self.main_window._get_marker_data_cached(selected_period.onset_timestamp, onset_idx)
                offset_data = self.main_window._get_marker_data_cached(selected_period.offset_timestamp, offset_idx)

                # Update tables only if we have data
                if onset_data or offset_data:
                    self.app_state.update_marker_tables(onset_data, offset_data)
                    self.main_window._last_table_update_time = current_time
        else:
            # Fallback to first complete period if no selection or selected period incomplete
            complete_periods = daily_sleep_markers.get_complete_periods()
            if complete_periods:
                first_period = complete_periods[0]

                # Always update sleep info immediately
                self.app_state.update_sleep_info(first_period)

                # Throttle table updates
                if time_since_last_update > 0.05:  # 50ms throttle
                    onset_idx = self.main_window._marker_index_cache.get(first_period.onset_timestamp)
                    offset_idx = self.main_window._marker_index_cache.get(first_period.offset_timestamp)

                    onset_data = self.main_window._get_marker_data_cached(first_period.onset_timestamp, onset_idx)
                    offset_data = self.main_window._get_marker_data_cached(first_period.offset_timestamp, offset_idx)

                    if onset_data or offset_data:
                        self.app_state.update_marker_tables(onset_data, offset_data)
                        self.main_window._last_table_update_time = current_time
            else:
                self.app_state.update_sleep_info(None)
                # Clear tables when no markers
                if time_since_last_update > 0.05:
                    self.app_state.update_marker_tables([], [])
                    self.main_window._last_table_update_time = current_time

        # NOTE: Delayed timer removed - SideTableConnector handles updates via Redux state

    def handle_sleep_markers_changed(self, daily_sleep_markers: DailySleepMarkers) -> None:
        """
        Handle sleep marker changes - updates "No Sleep" button state.

        NOTE: Per CLAUDE.md Redux pattern, table updates and Redux dispatch are
        now handled by Connectors:
        - MarkersConnector: Widget signals → Redux dispatch
        - SideTableConnector: Redux state → Table updates

        This method only handles UI state that can't be in a Connector
        (the "No Sleep" button state based on marker count).
        """
        logger.debug("=== handle_sleep_markers_changed ===")

        # Update "no sleep" button state based on marker count
        marker_count = daily_sleep_markers.get_marker_count() if daily_sleep_markers else 0
        if marker_count >= 2:  # We have complete markers
            self.main_window.no_sleep_btn.setText(ButtonText.MARK_NO_SLEEP)
            self.main_window.no_sleep_btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)

    def clear_all_markers(self) -> None:
        """Clear all sleep AND nonwear markers from database (preserves imported data)."""
        from PyQt6.QtWidgets import QMessageBox

        # Get current statistics
        try:
            stats = self.services.db_manager.get_database_stats()
            total_records = stats.get("total_records", 0)
            autosave_records = stats.get("autosave_records", 0) if FeatureFlags.ENABLE_AUTOSAVE else 0
            nonwear_records = stats.get("nonwear_records", 0)

            if total_records == 0 and autosave_records == 0 and nonwear_records == 0:
                QMessageBox.information(
                    self.main_window,
                    "Clear All Markers",
                    "No sleep or nonwear markers found in the database.",
                )
                return

            # Detailed confirmation dialog
            message = "Are you sure you want to clear ALL markers from the database?\n\n"
            message += "This will remove:\n"
            message += f"• {total_records} sleep metrics records\n"
            if nonwear_records > 0:
                message += f"• {nonwear_records} nonwear marker records\n"
            if FeatureFlags.ENABLE_AUTOSAVE and autosave_records > 0:
                message += f"• {autosave_records} autosave records\n"
            message += "\n"

            reply = QMessageBox.question(
                self.main_window,
                "Clear All Markers",
                message + "This action cannot be undone.\nImported raw data will be preserved.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Clear all markers (sleep + nonwear)
                result = self.services.db_manager.clear_all_markers()

                # Update UI via interfaces
                self.invalidate_metrics_cache()
                if self.services.data_service:
                    self.services.data_service.invalidate_marker_status_cache()
                # MainWindowProtocol guarantees update_data_source_status exists
                self.main_window.update_data_source_status()

                # Show success message
                total_cleared = result.get("total_cleared", 0)
                details = f"Successfully cleared {total_cleared} records from the database.\n\n"
                details += "Details:\n"
                details += f"• Sleep metrics: {result.get('sleep_metrics_cleared', 0)}\n"
                details += f"• Nonwear markers: {result.get('nonwear_markers_cleared', 0)}"

                QMessageBox.information(
                    self.main_window,
                    "Clear All Markers",
                    details,
                )

                # Refresh file indicators (Protocol-guaranteed via ImportInterface)
                self.main_window.load_available_files(preserve_selection=True)

                # Refresh current date dropdown if we have a file selected
                if self.navigation.selected_file and self.navigation.available_dates:
                    # Redux-style dropdown updates are now handled reactively
                    pass

                # Clear current plot (sleep + nonwear markers)
                pw = self.services.plot_widget
                if pw:
                    pw.clear_plot()
                    pw.clear_nonwear_markers()

        except Exception as e:
            QMessageBox.critical(self.main_window, "Clear All Markers", f"Failed to clear markers: {e}")
