#!/usr/bin/env python3
"""
Diary Integration Manager for Sleep Scoring Application.

Manages diary data loading and marker population.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from sleep_scoring_app.ui.protocols import (
        MainWindowProtocol,
        MarkerOperationsInterface,
        NavigationInterface,
        ServiceContainer,
    )
    from sleep_scoring_app.ui.store import UIStore

logger = logging.getLogger(__name__)


class DiaryIntegrationManager:
    """
    Manages diary data integration with the main window.

    Responsibilities:
    - Load diary data for selected files
    - Set sleep markers from diary table clicks
    - Handle diary-to-marker coordinate mapping
    - Validate diary data before marker placement
    """

    def __init__(
        self,
        store: UIStore,
        navigation: NavigationInterface,
        marker_ops: MarkerOperationsInterface,
        services: ServiceContainer,
        parent: MainWindowProtocol,
    ) -> None:
        """
        Initialize the diary integration manager.

        Args:
            store: The UI store
            navigation: Navigation interface
            marker_ops: Marker operations interface
            services: Service container
            parent: Main window (still needed for some Qt-level access for now)

        """
        self.store = store
        self.navigation = navigation
        self.marker_ops = marker_ops
        self.services = services
        self.main_window = parent  # Keep for Qt-level access (dialogs, plot_widget)

        logger.info("DiaryIntegrationManager initialized with decoupled interfaces")

    def load_diary_data_for_file(self) -> None:
        """Load diary data for the currently selected file."""
        try:
            # Use main window reference only for tab access
            if self.main_window.analysis_tab:
                self.main_window.analysis_tab.update_diary_display()
        except Exception as e:
            logger.exception(f"Error loading diary data: {e}")
            # Don't raise exception since diary data is optional

    def set_markers_from_diary_column(self, row: int, column_type) -> None:
        """
        Set sleep markers from a specific diary table column click.

        Args:
            row: The row index that was clicked in the diary table
            column_type: DiaryTableColumn enum indicating which column was clicked

        """
        try:
            from sleep_scoring_app.core.dataclasses import MarkerType, SleepPeriod
            from sleep_scoring_app.ui.analysis_tab import DiaryTableColumn

            # Check if we have necessary components (protocol-guaranteed attributes)
            if not self.main_window.plot_widget:
                logger.warning("Plot widget not available for marker setting")
                return

            if not self.services.data_service:
                logger.warning("Data service not available for diary data")
                return

            # Get the diary entries - pass current_file from store
            current_file = self.store.state.current_file
            if not current_file:
                logger.warning("No current file selected for diary data lookup")
                return

            diary_entries = self.services.data_service.load_diary_data_for_current_file(current_file)
            if not diary_entries or row >= len(diary_entries):
                logger.warning(f"No diary data available for row {row}")
                return

            # Get the diary entry for this row
            diary_entry = diary_entries[row]

            # Get the diary date from the entry
            diary_date_str = diary_entry.diary_date
            if not diary_date_str:
                logger.warning("No diary date in entry")
                return

            # Parse the diary date (format: YYYY-MM-DD)
            try:
                diary_date = (
                    datetime.strptime(diary_date_str.split()[0], "%Y-%m-%d")
                    if " " in diary_date_str
                    else datetime.strptime(diary_date_str, "%Y-%m-%d")
                )
                logger.info(f"Diary entry date: {diary_date.date()}")
            except ValueError as e:
                logger.exception(f"Invalid diary date format: {diary_date_str} - {e}")
                return

            # Check if the diary date matches the current date being viewed
            # MainWindowProtocol guarantees available_dates and current_date_index attributes exist
            if self.navigation.available_dates and self.navigation.current_date_index is not None:
                current_date = self.navigation.available_dates[self.navigation.current_date_index]
                logger.info(f"Current plot date: {current_date}")

                # Convert current_date to date object for comparison
                # Duck typing: Handle both date and datetime objects (justified - stdlib types)
                if hasattr(current_date, "date"):  # KEEP: Duck typing date/datetime
                    current_date_only = current_date.date()
                else:
                    current_date_only = current_date

                # If dates don't match, ask user if they want to switch
                if diary_date.date() != current_date_only:
                    reply = QMessageBox.question(
                        self.parent,
                        "Date Mismatch",
                        f"The diary entry is for {diary_date.date()} but you're currently viewing {current_date_only}.\n\n"
                        f"Would you like to switch to {diary_date.date()} to place the markers?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )

                    if reply == QMessageBox.StandardButton.Yes:
                        # Check for unsaved markers before switching dates
                        if not self.main_window._check_unsaved_markers_before_navigation():
                            logger.info("User canceled date switch due to unsaved markers")
                            return  # User canceled due to unsaved markers

                        # Find and switch to the diary date
                        try:
                            date_index = self.navigation.available_dates.index(diary_date.date())
                            # Dispatch to store - ActivityDataConnector will handle data loading
                            from sleep_scoring_app.ui.store import Actions

                            self.store.dispatch(Actions.date_navigated(date_index - self.navigation.current_date_index))
                            # NOTE: DO NOT call load_current_date() - ActivityDataConnector handles it
                            logger.info(f"Switched to date {diary_date.date()} from diary via store dispatch")
                        except ValueError:
                            logger.warning(f"Date {diary_date.date()} not found in available dates")
                            QMessageBox.warning(
                                self.parent, "Date Not Available", f"The date {diary_date.date()} is not available in the current data file."
                            )
                            return
                    else:
                        logger.info("User chose not to switch dates")
                        return

            # Helper function to validate and convert time to timestamp
            def convert_time_to_timestamp(time_str: str | None, is_overnight: bool = False) -> float | None:
                if not time_str or time_str in ("--:--", ""):
                    return None

                timestamp = self.navigation._parse_time_to_timestamp(time_str, diary_date)
                if timestamp is None:
                    return None

                # Handle overnight times
                if is_overnight:
                    timestamp += 24 * 3600

                # Check if within data range - but don't reject markers outside range
                # The diary data might be for a different day than what's currently displayed
                # PlotWidgetProtocol guarantees data_start_time and data_end_time attributes exist (may be None)
                data_start = self.main_window.plot_widget.data_start_time
                data_end = self.main_window.plot_widget.data_end_time

                # Convert to timestamps for comparison
                data_start_ts = data_start.timestamp() if data_start else None
                data_end_ts = data_end.timestamp() if data_end else None

                if data_start_ts is not None and data_end_ts is not None and not (data_start_ts <= timestamp <= data_end_ts):
                    logger.warning(f"Time {time_str} is outside current data view range, but allowing placement")
                    # Still return the timestamp - let the plot widget handle validation

                return timestamp

            # Determine which markers to set based on column clicked
            onset_ts = None
            offset_ts = None
            is_main_sleep = False
            period_slot = None
            marker_description = ""

            logger.debug("Diary column clicked: %s", column_type)

            if column_type in (DiaryTableColumn.SLEEP_ONSET, DiaryTableColumn.SLEEP_OFFSET):
                # Main sleep markers - ALWAYS SET BOTH ONSET AND OFFSET TOGETHER
                is_main_sleep = True
                period_slot = 1  # Main sleep typically goes in slot 1
                marker_description = "main sleep"
                logger.info("Main sleep column clicked, loading both onset and offset times")

                # Get BOTH onset and offset times from diary
                onset_time = diary_entry.sleep_onset_time
                offset_time = diary_entry.sleep_offset_time

                # Convert both times if available
                if onset_time and onset_time != "--:--":
                    onset_ts = convert_time_to_timestamp(onset_time)

                    # Check if auto-adjustment for early morning is enabled in config
                    auto_adjust_enabled = False
                    if self.services.config_manager and self.services.config_manager.config:
                        auto_adjust_enabled = self.services.config_manager.config.diary_auto_adjust_early_morning

                    if auto_adjust_enabled:
                        # Check if onset is in early morning hours (midnight to 6 AM) - likely next day
                        # Parse the hour from the onset time
                        try:
                            onset_hour = int(onset_time.split(":")[0])
                            # If onset is between midnight and 6 AM, it's likely the next day
                            if 0 <= onset_hour < 6:
                                onset_ts = convert_time_to_timestamp(onset_time, is_overnight=True)
                                logger.info(f"Auto-adjusted onset to next day for early morning time: {onset_time}")
                        except (ValueError, IndexError):
                            pass  # Keep original timestamp if parsing fails

                    logger.info(f"Setting main sleep onset from diary: {onset_time}")

                if offset_time and offset_time != "--:--":
                    offset_ts = convert_time_to_timestamp(offset_time)
                    # Check for overnight sleep
                    if onset_ts and offset_ts and offset_ts <= onset_ts:
                        offset_ts = convert_time_to_timestamp(offset_time, is_overnight=True)
                        logger.info("Adjusted main sleep offset for overnight sleep")
                    logger.info(f"Setting main sleep offset from diary: {offset_time}")

            elif column_type in (DiaryTableColumn.NAP_1_START, DiaryTableColumn.NAP_1_END):
                # Nap 1 markers - ALWAYS SET BOTH ONSET AND OFFSET TOGETHER
                is_main_sleep = False
                marker_description = "nap 1"

                # Check if main sleep exists - use Redux store (SINGLE SOURCE OF TRUTH)
                markers = self.store.state.current_sleep_markers
                main_sleep = markers.get_main_sleep() if markers else None
                if not main_sleep:
                    QMessageBox.warning(
                        self.parent,
                        "Marker Order",
                        "Please set the main sleep period before adding nap periods.\n\nClick on the Sleep Onset or Sleep Offset columns first.",
                    )
                    return

                # Nap 1 ALWAYS goes in slot 2
                period_slot = 2

                # Get BOTH nap 1 onset and offset times from diary
                nap_onset_time = diary_entry.nap_onset_time
                nap_offset_time = diary_entry.nap_offset_time

                # Convert both times if available
                if nap_onset_time and nap_onset_time != "--:--":
                    onset_ts = convert_time_to_timestamp(nap_onset_time)
                    logger.info(f"Setting nap 1 onset from diary: {nap_onset_time}")

                if nap_offset_time and nap_offset_time != "--:--":
                    offset_ts = convert_time_to_timestamp(nap_offset_time)
                    logger.info(f"Setting nap 1 offset from diary: {nap_offset_time}")

            elif column_type in (DiaryTableColumn.NAP_2_START, DiaryTableColumn.NAP_2_END):
                # Nap 2 markers - ALWAYS SET BOTH ONSET AND OFFSET TOGETHER
                is_main_sleep = False
                marker_description = "nap 2"

                # Check if main sleep exists - use Redux store (SINGLE SOURCE OF TRUTH)
                markers = self.store.state.current_sleep_markers
                main_sleep = markers.get_main_sleep() if markers else None
                if not main_sleep:
                    QMessageBox.warning(
                        self.parent,
                        "Marker Order",
                        "Please set the main sleep period before adding nap periods.\n\nClick on the Sleep Onset or Sleep Offset columns first.",
                    )
                    return

                # Nap 2 ALWAYS goes in slot 3
                period_slot = 3

                # Get BOTH nap 2 onset and offset times from diary
                nap_onset_time = diary_entry.nap_onset_time_2
                nap_offset_time = diary_entry.nap_offset_time_2

                # Convert both times if available
                if nap_onset_time and nap_onset_time != "--:--":
                    onset_ts = convert_time_to_timestamp(nap_onset_time)
                    logger.info(f"Setting nap 2 onset from diary: {nap_onset_time}")

                if nap_offset_time and nap_offset_time != "--:--":
                    offset_ts = convert_time_to_timestamp(nap_offset_time)
                    logger.info(f"Setting nap 2 offset from diary: {nap_offset_time}")

            elif column_type in (DiaryTableColumn.NAP_3_START, DiaryTableColumn.NAP_3_END):
                # Nap 3 markers - ALWAYS SET BOTH ONSET AND OFFSET TOGETHER
                is_main_sleep = False
                marker_description = "nap 3"

                # Check if main sleep exists - use Redux store (SINGLE SOURCE OF TRUTH)
                markers = self.store.state.current_sleep_markers
                main_sleep = markers.get_main_sleep() if markers else None
                if not main_sleep:
                    QMessageBox.warning(
                        self.parent,
                        "Marker Order",
                        "Please set the main sleep period before adding nap periods.\n\nClick on the Sleep Onset or Sleep Offset columns first.",
                    )
                    return

                # Nap 3 ALWAYS goes in slot 4
                period_slot = 4

                # Get BOTH nap 3 onset and offset times from diary
                nap_onset_time = diary_entry.nap_onset_time_3
                nap_offset_time = diary_entry.nap_offset_time_3

                # Convert both times if available
                if nap_onset_time and nap_onset_time != "--:--":
                    onset_ts = convert_time_to_timestamp(nap_onset_time)
                    logger.info(f"Setting nap 3 onset from diary: {nap_onset_time}")

                if nap_offset_time and nap_offset_time != "--:--":
                    offset_ts = convert_time_to_timestamp(nap_offset_time)
                    logger.info(f"Setting nap 3 offset from diary: {nap_offset_time}")
            else:
                logger.debug(f"Column type {column_type} does not set markers")
                return

            # Check if we have any timestamp to set
            if not onset_ts and not offset_ts:
                logger.info(f"No valid time data in diary row {row} column {column_type}")
                QMessageBox.information(self.parent, "No Data", f"No valid {marker_description} time found in this diary entry.")
                return

            # Get markers from Redux store (SINGLE SOURCE OF TRUTH)
            from sleep_scoring_app.core.dataclasses_markers import DailySleepMarkers
            from sleep_scoring_app.ui.store import Actions

            markers = self.store.state.current_sleep_markers
            if markers is None:
                markers = DailySleepMarkers()

            # Get or create the period in the specified slot
            period = markers.get_period_by_slot(period_slot)

            if period:
                # Update existing period
                if onset_ts:
                    period.onset_timestamp = onset_ts
                if offset_ts:
                    period.offset_timestamp = offset_ts

                # Validate onset/offset order
                if period.onset_timestamp and period.offset_timestamp:
                    if period.offset_timestamp <= period.onset_timestamp:
                        logger.warning("Offset would be before onset, not updating")
                        QMessageBox.warning(self.parent, "Invalid Time Order", "The offset time must be after the onset time.")
                        return
                    # Period is now complete, clear current_marker_being_placed if it matches
                    if self.main_window.plot_widget.current_marker_being_placed == period:
                        self.main_window.plot_widget.current_marker_being_placed = None
                        logger.info("Cleared current_marker_being_placed after completing period")

                logger.info(f"Updated existing {marker_description} period in slot {period_slot}")
            else:
                # Create new period
                marker_type_to_use = MarkerType.MAIN_SLEEP if is_main_sleep else MarkerType.NAP
                logger.warning(f"CREATING NEW PERIOD: is_main_sleep={is_main_sleep}, marker_type={marker_type_to_use}, slot={period_slot}")
                logger.warning(f"onset_ts={onset_ts}, offset_ts={offset_ts}")

                period = SleepPeriod(onset_timestamp=onset_ts, offset_timestamp=offset_ts, marker_index=period_slot, marker_type=marker_type_to_use)

                logger.warning(f"Created SleepPeriod object: marker_type={period.marker_type}, marker_index={period.marker_index}")

                # Assign to slot in Redux markers (SINGLE SOURCE OF TRUTH)
                if period_slot == 1:
                    markers.period_1 = period
                    logger.info("Assigned to period_1")
                elif period_slot == 2:
                    markers.period_2 = period
                    logger.info("Assigned to period_2")
                elif period_slot == 3:
                    markers.period_3 = period
                    logger.info("Assigned to period_3")
                elif period_slot == 4:
                    markers.period_4 = period
                    logger.info("Assigned to period_4")

                logger.info(f"Created new {marker_description} period in slot {period_slot}")

            # Dispatch to Redux - connector will update widget
            self.store.dispatch(Actions.sleep_markers_changed(markers))

            # Apply sleep scoring rules if complete
            if period and period.is_complete:
                # Auto-select the completed marker set FIRST
                self.main_window.plot_widget.selected_marker_set_index = period_slot
                self.main_window.plot_widget._update_marker_visual_state()  # Update visual highlighting
                logger.info(f"Auto-selected marker set {period_slot} after diary completion")

                # First redraw the markers to show them visually
                # Set flag to prevent redraw_markers from auto-applying rules
                self.main_window.plot_widget._skip_auto_apply_rules = True
                self.main_window.plot_widget.redraw_markers()
                self.main_window.plot_widget._skip_auto_apply_rules = False

                # Then apply sleep scoring rules (arrows) AFTER the markers are drawn
                # This ensures the arrows are added on top of the freshly drawn markers
                self.main_window.plot_widget.apply_sleep_scoring_rules(period)
                logger.info(f"Applied sleep scoring rules for {marker_description} period")

                # Update sleep scoring rules to ensure arrows are visible (protocol-guaranteed method)
                self.main_window.plot_widget._update_sleep_scoring_rules()
                logger.info("Called _update_sleep_scoring_rules to ensure arrows are visible")
            elif period:
                # Set as current marker being placed if incomplete
                self.main_window.plot_widget.current_marker_being_placed = period
                logger.info("Set incomplete period as current marker being placed")
                # Redraw markers for incomplete period
                self.main_window.plot_widget.redraw_markers()

            # Auto-save
            self.marker_ops.auto_save_current_markers()

            logger.info(f"Successfully set {marker_description} marker(s) from diary column {column_type}")

        except Exception as e:
            logger.error(f"Error setting markers from diary column {column_type} row {row}: {e}", exc_info=True)
            QMessageBox.critical(self.parent, "Error", f"Failed to set markers from diary: {e!s}")

    def set_markers_from_diary_row(self, row: int) -> None:
        """
        Set sleep markers from a diary table row.

        Args:
            row: The row index that was clicked in the diary table

        """
        try:
            # Check if we have necessary components (protocol-guaranteed attributes)
            if not self.main_window.plot_widget:
                logger.warning("Plot widget not available for marker setting")
                return

            if not self.services.data_service:
                logger.warning("Data service not available for diary data")
                return

            # Get the diary entries - pass current_file from store
            current_file = self.store.state.current_file
            if not current_file:
                logger.warning("No current file selected for diary data lookup")
                return

            diary_entries = self.services.data_service.load_diary_data_for_current_file(current_file)
            if not diary_entries or row >= len(diary_entries):
                logger.warning(f"No diary data available for row {row}")
                return

            # Get the diary entry for this row
            diary_entry = diary_entries[row]

            # Extract all sleep and nap times
            sleep_onset_time = diary_entry.sleep_onset_time
            sleep_offset_time = diary_entry.sleep_offset_time
            nap1_onset_time = diary_entry.nap_onset_time  # Nap 1 onset
            nap1_offset_time = diary_entry.nap_offset_time  # Nap 1 offset
            nap2_onset_time = diary_entry.nap_onset_time_2  # Nap 2 onset
            nap2_offset_time = diary_entry.nap_offset_time_2  # Nap 2 offset

            # Get the diary date from the entry
            diary_date_str = diary_entry.diary_date
            if not diary_date_str:
                logger.warning("No diary date in entry")
                return

            # Parse the diary date (format: YYYY-MM-DD)
            try:
                diary_date = (
                    datetime.strptime(diary_date_str.split()[0], "%Y-%m-%d")
                    if " " in diary_date_str
                    else datetime.strptime(diary_date_str, "%Y-%m-%d")
                )
            except ValueError as e:
                logger.exception(f"Invalid diary date format: {diary_date_str} - {e}")
                return

            # Helper function to validate and convert time to timestamp
            def convert_time_to_timestamp(time_str: str | None, is_overnight: bool = False) -> float | None:
                if not time_str or time_str == "--:--":
                    return None

                timestamp = self.navigation._parse_time_to_timestamp(time_str, diary_date)
                if timestamp is None:
                    return None

                # Handle overnight times
                if is_overnight:
                    timestamp += 24 * 3600

                # Check if within data range
                # PlotWidgetProtocol guarantees data_start_time and data_end_time attributes exist (may be None)
                data_start = self.main_window.plot_widget.data_start_time
                data_end = self.main_window.plot_widget.data_end_time

                # Convert to timestamps for comparison
                data_start_ts = data_start.timestamp() if data_start else None
                data_end_ts = data_end.timestamp() if data_end else None

                if data_start_ts is not None and data_end_ts is not None and not (data_start_ts <= timestamp <= data_end_ts):
                    logger.warning(f"Time {time_str} is outside data range for current view")
                    return None

                return timestamp

            # Convert all times to timestamps
            sleep_onset_ts = convert_time_to_timestamp(sleep_onset_time)
            sleep_offset_ts = convert_time_to_timestamp(sleep_offset_time)

            # Handle overnight main sleep
            if sleep_onset_ts and sleep_offset_ts and sleep_offset_ts <= sleep_onset_ts:
                sleep_offset_ts = convert_time_to_timestamp(sleep_offset_time, is_overnight=True)
                logger.info("Adjusted main sleep offset for overnight sleep")

            # Convert nap times
            nap1_onset_ts = convert_time_to_timestamp(nap1_onset_time)
            nap1_offset_ts = convert_time_to_timestamp(nap1_offset_time)

            # Handle nap 1 crossing midnight (rare but possible)
            if nap1_onset_ts and nap1_offset_ts and nap1_offset_ts <= nap1_onset_ts:
                nap1_offset_ts = convert_time_to_timestamp(nap1_offset_time, is_overnight=True)
                logger.info("Adjusted nap 1 offset for overnight nap")

            nap2_onset_ts = convert_time_to_timestamp(nap2_onset_time)
            nap2_offset_ts = convert_time_to_timestamp(nap2_offset_time)

            # Handle nap 2 crossing midnight
            if nap2_onset_ts and nap2_offset_ts and nap2_offset_ts <= nap2_onset_ts:
                nap2_offset_ts = convert_time_to_timestamp(nap2_offset_time, is_overnight=True)
                logger.info("Adjusted nap 2 offset for overnight nap")

            # Create sleep periods
            periods_created = []

            # Create main sleep period if available
            if sleep_onset_ts or sleep_offset_ts:
                period_info = self.main_window._create_sleep_period_from_timestamps(sleep_onset_ts, sleep_offset_ts, is_main_sleep=True)
                if period_info:
                    periods_created.append(("Main sleep", period_info))

            # Create nap 1 period if available
            if nap1_onset_ts or nap1_offset_ts:
                period_info = self.main_window._create_sleep_period_from_timestamps(nap1_onset_ts, nap1_offset_ts, is_main_sleep=False)
                if period_info:
                    periods_created.append(("Nap 1", period_info))

            # Create nap 2 period if available
            if nap2_onset_ts or nap2_offset_ts:
                period_info = self.main_window._create_sleep_period_from_timestamps(nap2_onset_ts, nap2_offset_ts, is_main_sleep=False)
                if period_info:
                    periods_created.append(("Nap 2", period_info))

            if periods_created:
                # Update classifications after all periods are created - use Redux store
                from sleep_scoring_app.ui.store import Actions

                markers = self.store.state.current_sleep_markers
                if markers:
                    markers.update_classifications()
                    # Dispatch to Redux - connector will update widget
                    self.store.dispatch(Actions.sleep_markers_changed(markers))
                self.main_window.plot_widget.redraw_markers()

                # Auto-save
                self.marker_ops.auto_save_current_markers()

                # Log what was created
                for period_name, _ in periods_created:
                    logger.info(f"Created {period_name} markers from diary")
            else:
                logger.warning("No valid timestamps could be created from diary times")

        except Exception as e:
            logger.error(f"Error setting markers from diary row {row}: {e}", exc_info=True)
