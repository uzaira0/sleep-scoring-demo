"""
Store Connectors - Connect UI components to the Redux-style store.

Each connector is responsible for:
1. Subscribing to relevant state changes
2. Updating the component when state changes
3. Handling cleanup (unsubscribe) when component is destroyed

Components own their update logic - the store just notifies them of changes.

ARCHITECTURE:
- ALL state (file/date selection, view mode, window geometry, markers) → UIStore (Redux pattern)
- Persistence → QSettings (synced from store via QSettingsPersistenceConnector)

All connectors subscribe to Redux store state changes - NO POLLING.

Usage:
    # In main_window.py after creating store:
    self.store = UIStore()
    connect_all_components(self.store, self)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt

from sleep_scoring_app.core.constants import ButtonStyle, ButtonText, MarkerCategory

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import FileInfo
    from sleep_scoring_app.ui.protocols import MainWindowProtocol
    from sleep_scoring_app.ui.store import UIState, UIStore

logger = logging.getLogger(__name__)


class SaveButtonConnector:
    """Connects the save button to the Redux store marker state."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update with current state
        self._update_button_from_state(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to state changes that affect save button."""
        # Only update if dirty state or markers changed or autosave changed
        should_update = (
            old_state.sleep_markers_dirty != new_state.sleep_markers_dirty
            or old_state.nonwear_markers_dirty != new_state.nonwear_markers_dirty
            or old_state.current_sleep_markers is not new_state.current_sleep_markers
            or old_state.auto_save_enabled != new_state.auto_save_enabled
        )

        if should_update:
            logger.info(f"SAVE BUTTON CONNECTOR: Triggering update. Dirty: {new_state.sleep_markers_dirty}, AutoSave: {new_state.auto_save_enabled}")
            self._update_button_from_state(new_state)

    def _update_button_from_state(self, state: UIState) -> None:
        """Update save button appearance based on state."""
        # Protocol guarantees save_markers_btn exists
        btn = self.main_window.save_markers_btn
        if not btn:
            return

        # Visibility based on autosave setting from state
        btn.setVisible(not state.auto_save_enabled)

        # Determine state
        has_any_markers = state.current_sleep_markers is not None or state.current_nonwear_markers is not None
        is_dirty = state.sleep_markers_dirty or state.nonwear_markers_dirty

        if not has_any_markers:
            btn.setText(ButtonText.SAVE_MARKERS)
            btn.setStyleSheet(ButtonStyle.SAVE_MARKERS)
            btn.setEnabled(False)
        elif is_dirty:
            btn.setText(ButtonText.SAVE_MARKERS)
            btn.setStyleSheet(ButtonStyle.SAVE_MARKERS)
            btn.setEnabled(True)
        else:
            btn.setText(ButtonText.MARKERS_SAVED)
            btn.setStyleSheet(ButtonStyle.SAVE_MARKERS_SAVED)
            btn.setEnabled(True)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class StatusConnector:
    """Connects various status buttons (like No Sleep) to the store."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)
        logger.info("STATUS CONNECTOR: Initialized and subscribed to store")

        # Initial update
        self._update_ui(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to state changes."""
        # Log all relevant state changes for debugging
        logger.debug(
            f"STATUS CONNECTOR: State change detected. "
            f"is_no_sleep_marked: {old_state.is_no_sleep_marked} -> {new_state.is_no_sleep_marked}, "
            f"date_index: {old_state.current_date_index} -> {new_state.current_date_index}"
        )

        # Update if markers, file, date, or no_sleep flag changed
        should_update = (
            old_state.current_sleep_markers is not new_state.current_sleep_markers
            or old_state.current_file != new_state.current_file
            or old_state.current_date_index != new_state.current_date_index
            or old_state.is_no_sleep_marked != new_state.is_no_sleep_marked
        )
        if should_update:
            logger.info(f"STATUS CONNECTOR: Triggering UI update. is_no_sleep_marked={new_state.is_no_sleep_marked}")
            self._update_ui(new_state)

    def _update_ui(self, state: UIState) -> None:
        """Update 'No Sleep' button based on marker state."""
        tab = self.main_window.analysis_tab
        if not tab:
            logger.warning("STATUS CONNECTOR: analysis_tab is None, skipping update")
            return

        # Protocol guarantees no_sleep_btn exists on AnalysisTab
        btn = tab.no_sleep_btn

        # Priority: actual markers > no_sleep flag
        # If we have complete markers, show default state (user can still mark no sleep to clear them)
        if state.current_sleep_markers and state.current_sleep_markers.get_marker_count() >= 2:
            logger.info("STATUS CONNECTOR: Setting button to MARK_NO_SLEEP (has markers)")
            btn.setText(ButtonText.MARK_NO_SLEEP)
            btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)
        # If this date is marked as "no sleep" (and no markers), show that state
        elif state.is_no_sleep_marked:
            logger.info("STATUS CONNECTOR: Setting button to NO_SLEEP_MARKED")
            btn.setText(ButtonText.NO_SLEEP_MARKED)
            btn.setStyleSheet(ButtonStyle.NO_SLEEP_MARKED)
        # Otherwise, show default state (ready to mark)
        else:
            logger.info("STATUS CONNECTOR: Setting button to MARK_NO_SLEEP (default)")
            btn.setText(ButtonText.MARK_NO_SLEEP)
            btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()
        logger.info("STATUS CONNECTOR: Disconnected")


class DateDropdownConnector:
    """
    Connects the date dropdown population and color to the store.
    SOLE Authority for date dropdown UI state.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._rebuild_dropdown(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to state changes that affect dropdown."""
        # 1. Full re-build if dates changed
        if old_state.available_dates != new_state.available_dates:
            logger.info(f"DATE DROPDOWN CONNECTOR: Dates changed in STORE. New count: {len(new_state.available_dates)}")
            self._rebuild_dropdown(new_state)
            return

        # 2. Sync selection if index changed (without triggering re-dispatch)
        if old_state.current_date_index != new_state.current_date_index:
            logger.info(f"DATE DROPDOWN CONNECTOR: Index changed in STORE: {new_state.current_date_index}")
            self._sync_selection(new_state.current_date_index)

        # 3. Update colors if markers were saved, no-sleep changed, or selection changed
        should_update_colors = (
            old_state.last_markers_save_time != new_state.last_markers_save_time
            or old_state.is_no_sleep_marked != new_state.is_no_sleep_marked
            or old_state.current_date_index != new_state.current_date_index
            or old_state.sleep_markers_dirty != new_state.sleep_markers_dirty
        )
        if should_update_colors:
            logger.info(
                f"DATE DROPDOWN CONNECTOR: Updating colors. "
                f"save_time_changed={old_state.last_markers_save_time != new_state.last_markers_save_time}, "
                f"no_sleep_changed={old_state.is_no_sleep_marked != new_state.is_no_sleep_marked}"
            )
            self._update_visuals(new_state)

    def _rebuild_dropdown(self, state: UIState) -> None:
        """Build the dropdown items from state."""
        dropdown = self.main_window.date_dropdown
        # IMPORTANT: Use `is None` check, NOT `if not dropdown:`
        # QComboBox.__bool__() returns False when empty (0 items)!
        if dropdown is None:
            return

        # Block signals to prevent "dispatch in progress" recursion
        dropdown.blockSignals(True)
        try:
            dropdown.clear()
            dates = state.available_dates
            logger.info(f"DATE DROPDOWN CONNECTOR: State has {len(dates)} dates")

            if not dates:
                logger.info("DATE DROPDOWN CONNECTOR: No dates in state, disabling dropdown")
                dropdown.addItem("No dates available")
                dropdown.setEnabled(False)
                return

            logger.info(f"DATE DROPDOWN CONNECTOR: Populating {len(dates)} dates into dropdown")
            for i, d_str in enumerate(dates):
                dropdown.addItem(d_str)
                logger.debug(f"DATE DROPDOWN CONNECTOR: Added date {i}: {d_str}")

            dropdown.setEnabled(True)
            logger.info(f"DATE DROPDOWN CONNECTOR: Dropdown now has {dropdown.count()} items, enabled={dropdown.isEnabled()}")

            # Set selection from state
            if 0 <= state.current_date_index < len(dates):
                dropdown.setCurrentIndex(state.current_date_index)
                logger.info(f"DATE DROPDOWN CONNECTOR: Set index to {state.current_date_index}")
            elif dates:
                dropdown.setCurrentIndex(0)
                logger.info("DATE DROPDOWN CONNECTOR: Defaulted to index 0")

            self._update_visuals(state)
            logger.info(f"DATE DROPDOWN CONNECTOR: _rebuild_dropdown COMPLETE. Final count: {dropdown.count()}")
        finally:
            dropdown.blockSignals(False)

    def _sync_selection(self, index: int) -> None:
        """Sync widget selection with state index."""
        dropdown = self.main_window.date_dropdown
        if dropdown and 0 <= index < dropdown.count():
            dropdown.blockSignals(True)
            dropdown.setCurrentIndex(index)
            dropdown.blockSignals(False)

    def _update_visuals(self, state: UIState) -> None:
        """
        Update dropdown colors based on marker status in DB.

        IMPORTANT: Do NOT use setStyleSheet here - it would destroy the original
        styling defined in analysis_tab.py. Use setItemData for dropdown items
        and QPalette for the line edit color.
        """
        dropdown = self.main_window.date_dropdown
        # Use `is None` check - QComboBox.__bool__() returns False when empty!
        if dropdown is None:
            return
        if dropdown.count() == 0 or not state.current_file:
            return

        from pathlib import Path

        from PyQt6.QtGui import QColor, QPalette

        from sleep_scoring_app.core.constants import UIColors

        filename = Path(state.current_file).name

        try:
            metrics_list = self.main_window.export_manager.db_manager.load_sleep_metrics(filename=filename)
            status_map = {}
            for m in metrics_list:
                is_no_sleep = m.onset_time == "NO_SLEEP"
                has_markers = m.daily_sleep_markers and m.daily_sleep_markers.get_marker_count() > 0
                status_map[m.analysis_date] = "no_sleep" if is_no_sleep else "markers" if has_markers else "none"

            # Default text color for items without markers (black)
            default_color = QColor("#000000")

            dropdown.blockSignals(True)
            for i in range(dropdown.count()):
                date_str = dropdown.itemText(i)
                status = status_map.get(date_str, "none")

                if status == "no_sleep":
                    dropdown.setItemData(i, QColor(UIColors.DATE_NO_SLEEP), Qt.ItemDataRole.ForegroundRole)
                elif status == "markers":
                    dropdown.setItemData(i, QColor(UIColors.DATE_WITH_MARKERS), Qt.ItemDataRole.ForegroundRole)
                else:
                    # Reset to explicit black color (None doesn't work properly on Windows)
                    dropdown.setItemData(i, default_color, Qt.ItemDataRole.ForegroundRole)

            # Update line edit color for current selection (preserves original stylesheet)
            line_edit = dropdown.lineEdit()
            if line_edit:
                current_index = dropdown.currentIndex()
                if 0 <= current_index < dropdown.count():
                    current_color = dropdown.itemData(current_index, Qt.ItemDataRole.ForegroundRole)
                    if isinstance(current_color, QColor) and current_color.name() != default_color.name():
                        # Set line edit text color via palette (doesn't destroy stylesheet)
                        palette = line_edit.palette()
                        palette.setColor(QPalette.ColorRole.Text, current_color)
                        line_edit.setPalette(palette)
                    else:
                        # Reset to default black
                        palette = line_edit.palette()
                        palette.setColor(QPalette.ColorRole.Text, default_color)
                        line_edit.setPalette(palette)

        except Exception as e:
            logger.debug(f"CONNECTOR: Error updating visuals: {e}")
        finally:
            dropdown.blockSignals(False)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class FileManagementConnector:
    """
    Smart Container for FileManagementWidget.
    Bridges Redux state to the presentational widget.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window

        # We find the widget in the hierarchy
        self.widget = getattr(main_window.data_settings_tab, "file_management_widget", None)
        if not self.widget:
            logger.warning("FILE MGMT CONNECTOR: Presentational widget not found")
            return

        # 1. Subscribe to Store changes
        self._unsubscribe = store.subscribe(self._on_state_change)

        # 2. Connect Widget signals to Actions
        self.widget.refreshRequested.connect(self._on_refresh_requested)
        self.widget.deleteRequested.connect(self._on_delete_requested)

        # Initial data injection
        self.widget.set_files(list(store.state.available_files))

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to available_files changes in Store."""
        if old_state.available_files != new_state.available_files:
            logger.info("FILE MGMT CONNECTOR: available_files changed in Store, updating widget")
            self.widget.set_files(list(new_state.available_files))

    def _on_refresh_requested(self) -> None:
        """Dispatch Refresh action to Store."""
        # Note: The actual service call is handled by the Effect Handler (e.g. NavManager)
        # or we could call it here if we want the Connector to handle the 'Effect'.
        # Industry standard: Dispatches an action that triggers a middleware/effect.
        from sleep_scoring_app.ui.store import Actions

        self.store.dispatch(Actions.refresh_files_requested())

    def _on_delete_requested(self, filenames: list[str]) -> None:
        """Dispatch Delete action to Store."""
        from sleep_scoring_app.ui.store import Actions

        self.store.dispatch(Actions.delete_files_requested(filenames))

    def disconnect(self) -> None:
        """Cleanup."""
        self._unsubscribe()
        try:
            self.widget.refreshRequested.disconnect(self._on_refresh_requested)
            self.widget.deleteRequested.disconnect(self._on_delete_requested)
        except (TypeError, RuntimeError, AttributeError):
            pass


class FileListConnector:
    """
    Connects the file list in the UI to the Redux store.
    SOLE Authority for file selector table UI state.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_table(store.state.available_files)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to file list changes."""
        if old_state.available_files != new_state.available_files:
            logger.info(f"FILE LIST CONNECTOR: Files changed, updating table. Count: {len(new_state.available_files)}")
            self._update_table(new_state.available_files)

    def _update_table(self, files: tuple[FileInfo, ...]) -> None:
        """Update file selector table widget."""
        selector = self.main_window.file_selector
        if not selector:
            return

        # MW-04 FIX: Logic for populating the table widget from the Redux tuple
        selector.populate_files(list(files))

        # Trigger indicator update (which also happens reactively via FileTableConnector)
        # Protocol guarantees data_service exists on MainWindowProtocol
        if self.main_window.data_service:
            self._update_indicators(files)

    def _update_indicators(self, files: tuple[FileInfo, ...]) -> None:
        """Update file completion indicators in the table."""
        # For now we delegate the complex count calculation to the service
        # but the connector triggers it based on state changes.
        pass

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class FileTableConnector:
    """Connects the file table indicators to the store."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to state changes that affect file table."""
        # Update when markers are saved (completion indicator may change)
        if old_state.last_saved_file != new_state.last_saved_file:
            self._update_file_indicators()

    def _update_file_indicators(self) -> None:
        """Update file table completion indicators."""
        # Protocol guarantees data_service exists
        if self.main_window.data_service:
            # Use QTimer to avoid dispatch-in-dispatch error
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, lambda: self.main_window.data_service.load_available_files(preserve_selection=True, load_completion_counts=True))

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class PlotArrowsConnector:
    """
    Connects the plot arrows refresh to Redux store marker state changes.

    Subscribes to state and refreshes arrows when save completes (dirty → clean transition).
    NO POLLING - uses Redux subscription.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to state changes for arrow refresh."""
        # Refresh arrows when transitioning from dirty to clean (save completed)
        was_dirty = old_state.sleep_markers_dirty
        is_clean = not new_state.sleep_markers_dirty

        if was_dirty and is_clean:
            self._refresh_arrows()

    def _refresh_arrows(self) -> None:
        """Refresh sleep onset/offset arrows on plot."""
        # Protocol guarantees plot_widget exists
        plot_widget = self.main_window.plot_widget
        if not plot_widget:
            return
        selected_period = plot_widget.get_selected_marker_period()

        if selected_period and selected_period.is_complete:
            plot_widget.apply_sleep_scoring_rules(selected_period)
            logger.debug("Refreshed arrows after save")

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class SideTableConnector:
    """
    Connects the side tables in AnalysisTab to the Redux store marker state.

    Subscribes to store changes and updates tables when markers change.
    This is the SOLE source of table updates per CLAUDE.md Redux pattern:
    Widget → Connector → Store → Connector → UI

    Updates tables based on current marker_mode:
    - SLEEP mode: Shows data around selected sleep period onset/offset
    - NONWEAR mode: Shows data around selected nonwear marker start/end
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """
        React to marker, selection, or algorithm changes by updating side tables.

        Updates tables based on the CURRENT marker mode (SLEEP or NONWEAR).
        Each mode has symmetric logic: detect changes → update tables with relevant data.

        Also updates when algorithm settings change since side tables display algorithm results.
        """
        current_mode = new_state.marker_mode

        # Detect algorithm/rule changes that affect table data
        algorithm_changed = (
            old_state.sleep_algorithm_id != new_state.sleep_algorithm_id
            or old_state.onset_offset_rule_id != new_state.onset_offset_rule_id
            or old_state.nonwear_algorithm_id != new_state.nonwear_algorithm_id
            or old_state.choi_axis != new_state.choi_axis
        )

        # === SLEEP MODE ===
        if current_mode == MarkerCategory.SLEEP:
            sleep_changed = (
                old_state.current_sleep_markers is not new_state.current_sleep_markers
                or old_state.last_marker_update_time != new_state.last_marker_update_time
            )
            sleep_selection_changed = old_state.selected_period_index != new_state.selected_period_index

            if (sleep_changed or sleep_selection_changed or algorithm_changed) and new_state.current_sleep_markers:
                self._update_sleep_tables(new_state.current_sleep_markers)

        # === NONWEAR MODE ===
        elif current_mode == MarkerCategory.NONWEAR:
            nonwear_changed = (
                old_state.current_nonwear_markers is not new_state.current_nonwear_markers
                or old_state.last_marker_update_time != new_state.last_marker_update_time
            )
            nonwear_selection_changed = old_state.selected_nonwear_index != new_state.selected_nonwear_index

            if (nonwear_changed or nonwear_selection_changed or algorithm_changed) and new_state.current_nonwear_markers:
                self._update_nonwear_tables(new_state.current_nonwear_markers, new_state.selected_nonwear_index)

    def _update_sleep_tables(self, markers: Any) -> None:
        """Update side tables with data around selected sleep period onset/offset."""
        # Delegate to state_manager which handles the complex table update logic
        if self.main_window.state_manager:
            # Use visual-only update to avoid store dispatch loop
            self.main_window.state_manager.update_tables_visual_only(markers)

    def _update_nonwear_tables(self, markers: Any, selected_index: int) -> None:
        """
        Update side tables with data around selected nonwear marker start/end.

        Mirrors _update_sleep_tables exactly - uses widget's get_selected_nonwear_period().
        """
        import time

        pw = self.main_window.plot_widget
        if not pw:
            self.main_window.update_marker_tables([], [])
            return

        # Use the SAME pattern as sleep: get selected period from widget
        selected_period = pw.get_selected_nonwear_period()

        if selected_period and selected_period.is_complete:
            # Throttle updates (same as sleep)
            current_time = time.time()
            time_since_last_update = current_time - self.main_window._last_table_update_time
            if time_since_last_update > 0.05:  # 50ms throttle
                # Get data around start/end timestamps (same as sleep onset/offset)
                start_data = self.main_window._get_marker_data_cached(selected_period.start_timestamp, None)
                end_data = self.main_window._get_marker_data_cached(selected_period.end_timestamp, None)

                if start_data or end_data:
                    self.main_window.update_marker_tables(start_data, end_data)
                    self.main_window._last_table_update_time = current_time

                logger.debug(
                    "Updated tables for nonwear marker: start=%d rows, end=%d rows",
                    len(start_data) if start_data else 0,
                    len(end_data) if end_data else 0,
                )
        else:
            # No complete period selected - clear tables (same as sleep fallback)
            self.main_window.update_marker_tables([], [])

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class PopOutConnector:
    """
    Connects the pop-out windows to the Redux store marker state.

    The SOLE authority for refreshing pop-out window data.
    Refreshes visible pop-out windows when markers change.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial refresh to ensure current state is shown if windows exist
        self._refresh_popouts()

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to any marker, selection, or algorithm changes by refreshing open pop-out windows."""
        # Refresh on: marker data change, dirty flag change, file/date selection change, or algorithm change
        markers_changed = (
            old_state.current_sleep_markers is not new_state.current_sleep_markers
            or old_state.last_marker_update_time != new_state.last_marker_update_time
            or old_state.current_file != new_state.current_file
            or old_state.current_date_index != new_state.current_date_index
        )

        # Algorithm changes affect the sleep_score column in pop-out tables
        algorithm_changed = (
            old_state.sleep_algorithm_id != new_state.sleep_algorithm_id
            or old_state.nonwear_algorithm_id != new_state.nonwear_algorithm_id
            or old_state.choi_axis != new_state.choi_axis
        )

        if markers_changed or algorithm_changed:
            self._refresh_popouts()

    def _refresh_popouts(self) -> None:
        """Refresh visible pop-out windows via AnalysisTab."""
        # Protocol guarantees analysis_tab exists with these methods
        tab = self.main_window.analysis_tab
        if tab:
            # Delegate refreshing to the tab's methods which know how to fetch 48h data
            tab.refresh_onset_popout()
            tab.refresh_offset_popout()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class AutoSaveConnector:
    """Connects the auto-save checkbox, status label, and save time to the store."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_enabled_ui(store.state.auto_save_enabled)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to auto-save state changes."""
        # Handle auto-save enabled toggle
        if old_state.auto_save_enabled != new_state.auto_save_enabled:
            self._update_enabled_ui(new_state.auto_save_enabled)

        # Handle date changes - reset label to default
        if old_state.current_date_index != new_state.current_date_index:
            self._reset_to_default_label()

        # Handle save time changes (update the "Saved at HH:MM:SS" label)
        if old_state.last_markers_save_time != new_state.last_markers_save_time:
            if new_state.last_markers_save_time is not None and new_state.auto_save_enabled:
                self._update_save_time_label(new_state.last_markers_save_time)

        # Handle dirty state changes (show "Unsaved" indicator)
        old_dirty = old_state.sleep_markers_dirty or old_state.nonwear_markers_dirty
        new_dirty = new_state.sleep_markers_dirty or new_state.nonwear_markers_dirty
        if old_dirty != new_dirty and new_state.auto_save_enabled:
            if new_dirty:
                self._show_unsaved_indicator()
            # Note: When saved, _update_save_time_label will be called which overwrites the label

    def _update_enabled_ui(self, enabled: bool) -> None:
        """
        Update checkbox and status label visibility.

        NOTE: Save button visibility is handled by SaveButtonConnector.
        This connector only manages the checkbox and autosave status label.
        """
        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Update checkbox (Protocol-guaranteed attribute)
        tab.auto_save_checkbox.blockSignals(True)
        tab.auto_save_checkbox.setChecked(enabled)
        tab.auto_save_checkbox.blockSignals(False)

        # Update status label visibility (Protocol-guaranteed attribute)
        tab.autosave_status_label.setVisible(enabled)
        if enabled:
            # Reset to default when enabling
            tab.autosave_status_label.setText("Saved at N/A")
            tab.autosave_status_label.setStyleSheet("color: #333; font-size: 11px;")

    def _update_save_time_label(self, save_time: float) -> None:
        """Update the autosave status label with the save timestamp."""
        from datetime import datetime

        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Convert Unix timestamp to readable time (Protocol-guaranteed attribute)
        timestamp = datetime.fromtimestamp(save_time).strftime("%H:%M:%S")
        tab.autosave_status_label.setText(f"Saved at {timestamp}")
        tab.autosave_status_label.setStyleSheet("color: #28a745; font-size: 11px;")  # Green when saved

    def _show_unsaved_indicator(self) -> None:
        """Show 'Unsaved' indicator when markers are modified."""
        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Protocol-guaranteed attribute
        tab.autosave_status_label.setText("Unsaved changes...")
        tab.autosave_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")  # Red when unsaved

    def _reset_to_default_label(self) -> None:
        """Reset the autosave status label to default state."""
        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Protocol-guaranteed attribute
        tab.autosave_status_label.setText("Saved at N/A")
        tab.autosave_status_label.setStyleSheet("color: #333; font-size: 11px;")  # Black default

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class MarkerModeConnector:
    """Connects the marker mode radio buttons to the store."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_ui(store.state.marker_mode)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to marker mode changes."""
        if old_state.marker_mode != new_state.marker_mode:
            self._update_ui(new_state.marker_mode)

    def _update_ui(self, category: MarkerCategory) -> None:
        """Update radio buttons, plot widget mode, and deselect opposite markers."""
        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Update radio buttons (temporarily block signals)
        tab.sleep_mode_btn.blockSignals(True)
        tab.nonwear_mode_btn.blockSignals(True)

        tab.sleep_mode_btn.setChecked(category == MarkerCategory.SLEEP)
        tab.nonwear_mode_btn.setChecked(category == MarkerCategory.NONWEAR)

        tab.sleep_mode_btn.blockSignals(False)
        tab.nonwear_mode_btn.blockSignals(False)

        # Update plot widget
        pw = self.main_window.plot_widget
        if pw:
            pw.set_active_marker_category(category)

            renderer = pw.marker_renderer
            if category == MarkerCategory.SLEEP:
                # Switching TO sleep mode:
                # 1. Deselect nonwear markers
                renderer.selected_nonwear_marker_index = 0
                renderer._update_nonwear_marker_visual_state_no_auto_select()
                # 2. Auto-select first sleep marker
                renderer.auto_select_marker_set()
            elif category == MarkerCategory.NONWEAR:
                # Switching TO nonwear mode:
                # 1. Deselect sleep markers AND clear sleep arrows
                renderer.selected_marker_set_index = 0
                renderer._update_marker_visual_state_no_auto_select()
                pw.clear_sleep_onset_offset_markers()  # Remove sleep rule arrows
                # 2. Auto-select first nonwear marker
                renderer.auto_select_nonwear_marker()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class AdjacentMarkersConnector:
    """Connects the adjacent markers checkbox to the store and reloads on date changes."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._last_date_index = store.state.current_date_index
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_checkbox(store.state.show_adjacent_markers)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to adjacent markers visibility OR date index changes."""
        from PyQt6.QtCore import QTimer

        visibility_changed = old_state.show_adjacent_markers != new_state.show_adjacent_markers
        date_changed = old_state.current_date_index != new_state.current_date_index

        if visibility_changed:
            self._update_checkbox(new_state.show_adjacent_markers)
            self._toggle_markers(new_state.show_adjacent_markers)

        elif date_changed and new_state.show_adjacent_markers:
            # Date changed and markers are enabled - reload for new date
            # Use QTimer.singleShot(0) to defer until after NavigationConnector updates the plot
            logger.info(f"ADJACENT CONNECTOR: Date changed to {new_state.current_date_index}, scheduling reload")
            QTimer.singleShot(0, lambda: self._toggle_markers(True))

    def _update_checkbox(self, enabled: bool) -> None:
        """Update checkbox state without triggering signals."""
        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Protocol-guaranteed attribute
        tab.show_adjacent_day_markers_checkbox.blockSignals(True)
        tab.show_adjacent_day_markers_checkbox.setChecked(enabled)
        tab.show_adjacent_day_markers_checkbox.blockSignals(False)

    def _toggle_markers(self, enabled: bool) -> None:
        """Toggle adjacent markers display on plot."""
        if not self.main_window.plot_widget:
            return

        # AppStateInterface guarantees toggle_adjacent_day_markers exists
        self.main_window.toggle_adjacent_day_markers(enabled)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class DiaryTableConnector:
    """
    Connects the diary table to the Redux store state.

    Refreshes diary display when file selection changes.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_diary()

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to file changes by refreshing diary."""
        if old_state.current_file != new_state.current_file:
            self._update_diary()

    def _update_diary(self) -> None:
        """Refresh diary table via AnalysisTab."""
        # Protocol guarantees analysis_tab has update_diary_display method
        tab = self.main_window.analysis_tab
        if tab:
            tab.update_diary_display()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class NavigationConnector:
    """Connects date navigation changes to the UI loading logic."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._last_date_str: str | None = None
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_navigation(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to date index or available dates changes."""
        # Calculate current date string
        current_date_str = None
        if 0 <= new_state.current_date_index < len(new_state.available_dates):
            current_date_str = new_state.available_dates[new_state.current_date_index]

        # Only trigger heavy reload if the ACTUAL date changed or file changed
        file_changed = old_state.current_file != new_state.current_file
        date_changed = current_date_str != self._last_date_str

        logger.debug(
            f"NAVIGATION CONNECTOR CHECK: current_date_str={current_date_str}, _last_date_str={self._last_date_str}, file_changed={file_changed}, date_changed={date_changed}"
        )

        if file_changed or date_changed:
            logger.info(f"NAVIGATION CONNECTOR: Triggering update. File changed: {file_changed}, Date changed: {date_changed}")
            self._last_date_str = current_date_str
            self._update_navigation(new_state)

    def _update_navigation(self, state: UIState) -> None:
        """Update buttons and load data for new date index."""
        logger.info(f"NAVIGATION CONNECTOR: Updating for index {state.current_date_index} of {len(state.available_dates)} dates")

        # Sync UI components - Protocol guarantees these exist on AnalysisTabProtocol
        tab = self.main_window.analysis_tab
        if tab:
            # Update buttons (Protocol-guaranteed attributes)
            has_prev = state.current_date_index > 0
            has_next = state.current_date_index < len(state.available_dates) - 1
            tab.prev_date_btn.setEnabled(has_prev)
            tab.next_date_btn.setEnabled(has_next)

            # Update date dropdown (Protocol-guaranteed attribute)
            tab.date_dropdown.blockSignals(True)
            tab.date_dropdown.setCurrentIndex(state.current_date_index)
            tab.date_dropdown.blockSignals(False)

        # Trigger data loading - NavigationInterface guarantees load_current_date exists
        if state.current_date_index != -1:
            # FIRST: Clear old markers from widget to prevent them showing on new plot data
            # NOTE: Do NOT clear adjacent_day_markers here - AdjacentMarkersConnector handles those
            pw = self.main_window.plot_widget
            if pw:
                pw.clear_sleep_markers()
                pw.clear_nonwear_markers()
                pw.clear_sleep_onset_offset_markers()
                logger.info("NAVIGATION CONNECTOR: Cleared sleep/nonwear markers before loading new date")

            logger.info(f"NAVIGATION CONNECTOR: Triggering load_current_date() for index {state.current_date_index}")
            self.main_window.load_current_date()
            # NOTE: Marker loading is handled by MarkerLoadingCoordinator, not here
            # Connectors should NOT dispatch actions - that's a Coordinator's job

            # Update activity source dropdown enabled state
            # Protocol guarantees update_activity_source_dropdown exists on AnalysisTabProtocol
            if tab:
                tab.update_activity_source_dropdown()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class NavigationGuardConnector:
    """
    Guards date navigation by checking for unsaved markers before allowing navigation.

    This connector intercepts navigation signals from AnalysisTab and:
    1. Calls main_window._check_unsaved_markers_before_navigation()
    2. Only dispatches to the store if the check passes (user confirms or no unsaved markers)
    3. If user cancels, reverts the dropdown visual selection back to current state

    Architecture: AnalysisTab (signals) → NavigationGuardConnector → Store dispatch
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window

        # Connect to navigation signals from AnalysisTab
        tab = main_window.analysis_tab
        if tab:
            tab.prevDateRequested.connect(self._on_prev_date_requested)
            tab.nextDateRequested.connect(self._on_next_date_requested)
            tab.dateSelectRequested.connect(self._on_date_select_requested)
            logger.info("NAVIGATION GUARD CONNECTOR: Connected to AnalysisTab navigation signals")

    def _on_prev_date_requested(self) -> None:
        """Handle previous date button click with unsaved marker check."""
        logger.info("NAVIGATION GUARD CONNECTOR: prev_date_requested signal received")
        if not self.main_window._check_unsaved_markers_before_navigation():
            logger.info("NAVIGATION GUARD CONNECTOR: User canceled prev navigation")
            return

        # Check bounds and dispatch
        current_index = self.store.state.current_date_index
        if current_index > 0:
            from sleep_scoring_app.ui.store import Actions

            logger.info("NAVIGATION GUARD CONNECTOR: Dispatching date_navigated(-1)")
            self.store.dispatch(Actions.date_navigated(-1))

    def _on_next_date_requested(self) -> None:
        """Handle next date button click with unsaved marker check."""
        logger.info("NAVIGATION GUARD CONNECTOR: next_date_requested signal received")
        if not self.main_window._check_unsaved_markers_before_navigation():
            logger.info("NAVIGATION GUARD CONNECTOR: User canceled next navigation")
            return

        # Check bounds and dispatch
        current_index = self.store.state.current_date_index
        num_dates = len(self.store.state.available_dates)
        if current_index < num_dates - 1:
            from sleep_scoring_app.ui.store import Actions

            logger.info("NAVIGATION GUARD CONNECTOR: Dispatching date_navigated(1)")
            self.store.dispatch(Actions.date_navigated(1))

    def _on_date_select_requested(self, index: int) -> None:
        """Handle date dropdown selection with unsaved marker check."""
        logger.info(f"NAVIGATION GUARD CONNECTOR: date_select_requested signal received with index={index}")
        if not self.main_window._check_unsaved_markers_before_navigation():
            logger.info("NAVIGATION GUARD CONNECTOR: User canceled date selection")
            # Revert dropdown visual to current state
            self._revert_dropdown_selection()
            return

        from sleep_scoring_app.ui.store import Actions

        logger.info(f"NAVIGATION GUARD CONNECTOR: Dispatching date_selected({index})")
        self.store.dispatch_async(Actions.date_selected(index))

        # Save to session
        if self.main_window.session_manager:
            self.main_window.session_manager.save_current_date_index(index)

    def _revert_dropdown_selection(self) -> None:
        """Revert dropdown to show current state index when user cancels navigation."""
        tab = self.main_window.analysis_tab
        if tab and tab.date_dropdown:
            current_index = self.store.state.current_date_index
            tab.date_dropdown.blockSignals(True)
            tab.date_dropdown.setCurrentIndex(current_index)
            tab.date_dropdown.blockSignals(False)
            logger.info(f"NAVIGATION GUARD CONNECTOR: Reverted dropdown to index {current_index}")

    def disconnect(self) -> None:
        """Cleanup signal connections."""
        tab = self.main_window.analysis_tab
        if tab:
            try:
                tab.prevDateRequested.disconnect(self._on_prev_date_requested)
                tab.nextDateRequested.disconnect(self._on_next_date_requested)
                tab.dateSelectRequested.disconnect(self._on_date_select_requested)
            except (TypeError, RuntimeError):
                pass  # Already disconnected


class ViewModeConnector:
    """Connects the view mode (24h/48h) radio buttons to the store."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_ui(store.state.view_mode_hours)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to view mode changes."""
        if old_state.view_mode_hours != new_state.view_mode_hours:
            logger.info(f"VIEW MODE CONNECTOR: Triggering update. Hours: {new_state.view_mode_hours}")
            self._update_ui(new_state.view_mode_hours)

    def _update_ui(self, hours: int) -> None:
        """Update radio buttons and plot widget view."""
        tab = self.main_window.analysis_tab
        if not tab:
            return

        # Update radio buttons (Protocol-guaranteed attributes)
        tab.view_24h_btn.blockSignals(True)
        tab.view_48h_btn.blockSignals(True)

        tab.view_24h_btn.setChecked(hours == 24)
        tab.view_48h_btn.setChecked(hours == 48)

        tab.view_24h_btn.blockSignals(False)
        tab.view_48h_btn.blockSignals(False)

        # Update plot widget
        if self.main_window.plot_widget:
            self.main_window.plot_widget.current_view_hours = hours
            # Re-load data - NavigationInterface guarantees load_current_date exists
            logger.info(f"VIEW MODE CONNECTOR: Triggering load_current_date() for {hours}h view")
            self.main_window.load_current_date()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class SignalsConnector:
    """
    Central authority for wiring UI component signals to store actions.

    This connector does NOT subscribe to the store; it connects UI signals
    TO the store's dispatchers.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._connect_all_signals()

    def _connect_all_signals(self) -> None:
        """Connect various UI signals to store actions."""
        from sleep_scoring_app.ui.store import Actions

        # 1. File Selection Table - Protocol guarantees file_selector exists on AnalysisTabProtocol
        tab = self.main_window.analysis_tab
        if tab and tab.file_selector:
            # Connect the custom fileSelected signal to a dispatcher
            tab.file_selector.fileSelected.connect(self._on_file_selected)

    def _on_file_selected(self, row: int, file_info: FileInfo) -> None:
        """Handle file selection from UI table."""
        from sleep_scoring_app.ui.store import Actions

        logger.info(f"SIGNALS CONNECTOR: _on_file_selected called with row={row}, file={file_info.filename if file_info else None}")

        if file_info:
            # DO NOT dispatch file_selected here - it clears dates
            # Let MainWindow.on_file_selected_from_table handle everything
            # Protocol guarantees on_file_selected_from_table exists on NavigationInterface
            logger.info("SIGNALS CONNECTOR: Calling main_window.on_file_selected_from_table")
            self.main_window.on_file_selected_from_table(file_info)

    def disconnect(self) -> None:
        """Cleanup signal connections."""
        # Protocol guarantees file_selector exists on AnalysisTabProtocol
        tab = self.main_window.analysis_tab
        if tab and tab.file_selector:
            try:
                tab.file_selector.fileSelected.disconnect(self._on_file_selected)
            except (TypeError, RuntimeError):
                pass


class TimeFieldConnector:
    """
    Connects the manual time fields to the Redux store state.

    Syncs HH:MM inputs with current marker selection.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_fields()

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to marker or selection changes by updating time fields."""
        # Update if markers changed (identity or internal content via timestamp)
        markers_changed = (
            old_state.current_sleep_markers is not new_state.current_sleep_markers
            or old_state.last_marker_update_time != new_state.last_marker_update_time
        )

        if markers_changed:
            self._update_fields()

    def _update_fields(self) -> None:
        """Update time fields via MainWindow."""
        # This method is optional - may not be implemented yet
        update_fn = getattr(self.main_window, "_update_time_fields_from_selection", None)
        if update_fn:
            update_fn()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class AlgorithmConfigConnector:
    """Connects calibration and imputation settings to the UI and triggers reloads."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_ui(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to calibration or imputation changes."""
        changed = (
            old_state.auto_calibrate_enabled != new_state.auto_calibrate_enabled or old_state.impute_gaps_enabled != new_state.impute_gaps_enabled
        )

        if changed:
            self._update_ui(new_state)
            # Trigger data reload if a file is currently loaded
            if new_state.current_file:
                logger.info("Algorithm config changed, reloading current date...")
                self.main_window.load_current_date()

    def _update_ui(self, state: UIState) -> None:
        """Update checkboxes in DataSettingsTab."""
        # Protocol guarantees data_settings_tab exists on MainWindowProtocol
        tab = self.main_window.data_settings_tab
        if not tab:
            return

        # These checkboxes are optional UI elements - use getattr with default
        auto_calibrate_check = getattr(tab, "auto_calibrate_check", None)
        if auto_calibrate_check:
            auto_calibrate_check.blockSignals(True)
            auto_calibrate_check.setChecked(state.auto_calibrate_enabled)
            auto_calibrate_check.blockSignals(False)

        impute_gaps_check = getattr(tab, "impute_gaps_check", None)
        if impute_gaps_check:
            impute_gaps_check.blockSignals(True)
            impute_gaps_check.setChecked(state.impute_gaps_enabled)
            impute_gaps_check.blockSignals(False)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class CacheConnector:
    """Handles cache invalidation based on store state changes."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to state changes that require cache invalidation."""
        # Invalidate cache when markers are saved or cleared
        if old_state.last_saved_file != new_state.last_saved_file:
            if new_state.last_saved_file:
                self._invalidate_cache(new_state.last_saved_file)

        # Also invalidate on markers_cleared (when last_saved_file becomes None)
        if old_state.last_saved_file and not new_state.last_saved_file:
            self._invalidate_cache(old_state.last_saved_file)

    def _invalidate_cache(self, filename: str) -> None:
        """Invalidate marker status cache for a file."""
        # Protocol guarantees data_service exists
        if self.main_window.data_service:
            self.main_window.data_service.invalidate_marker_status_cache(filename)
            logger.debug("Invalidated marker cache for %s", filename)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class StudySettingsConnector:
    """
    Connects the StudySettingsTab to the Redux store.

    SOLE Authority for syncing Study Settings UI with the Redux state.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window

        # Find the widget
        self.tab = getattr(main_window, "study_settings_tab", None)
        if not self.tab:
            logger.warning("STUDY SETTINGS CONNECTOR: StudySettingsTab not found")
            return

        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_ui(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to study settings changes in the store."""
        # Check for any study settings changes
        fields_to_check = [
            "study_unknown_value",
            "study_valid_groups",
            "study_valid_timepoints",
            "study_default_group",
            "study_default_timepoint",
            "study_participant_id_patterns",
            "study_timepoint_pattern",
            "study_group_pattern",
            "data_paradigm",
            "sleep_algorithm_id",
            "onset_offset_rule_id",
            "night_start_hour",
            "night_end_hour",
            "nonwear_algorithm_id",
            "choi_axis",
        ]

        changed_fields = [f for f in fields_to_check if getattr(old_state, f) != getattr(new_state, f)]

        if changed_fields:
            logger.info(f"STUDY SETTINGS CONNECTOR: Settings changed: {changed_fields}")
            self._update_ui(new_state)
            self._handle_side_effects(old_state, new_state, changed_fields)

    def _update_ui(self, state: UIState) -> None:
        """Update the StudySettingsTab UI from state."""
        # Protocol guarantees _load_settings_from_state exists on StudySettingsTabProtocol
        if not self.tab:
            return

        self.tab._load_settings_from_state(state)

    def _handle_side_effects(self, old_state: UIState, new_state: UIState, changed_fields: list[str]) -> None:
        """Handle side effects of setting changes."""
        pw = self.main_window.plot_widget
        if not pw:
            return

        from sleep_scoring_app.services.algorithm_service import get_algorithm_service

        # 1. Sleep Algorithm or Onset/Offset Rule Change
        # Protocol guarantees algorithm_manager exists (can be None initially)
        if "sleep_algorithm_id" in changed_fields or "onset_offset_rule_id" in changed_fields:
            if pw.algorithm_manager:
                algo_id = new_state.sleep_algorithm_id
                rule_id = new_state.onset_offset_rule_id

                # Update algorithm
                if "sleep_algorithm_id" in changed_fields:
                    # We need the full config for the algorithm
                    config = self.main_window.config_manager.config
                    algorithm = get_algorithm_service().create_sleep_algorithm(algo_id, config)
                    pw.algorithm_manager.set_sleep_scoring_algorithm(algorithm)

                # Update rule
                if "onset_offset_rule_id" in changed_fields:
                    detector = get_algorithm_service().create_sleep_period_detector(rule_id)
                    pw.algorithm_manager.set_sleep_period_detector(detector)

                # Recalculate and update plot
                pw.algorithm_manager._algorithm_cache.clear()
                pw.algorithm_manager.plot_algorithms()

                # Clear and reapply rules to current selection
                pw.algorithm_manager.clear_sleep_onset_offset_markers()
                selected = pw.get_selected_marker_period()
                if selected and selected.is_complete:
                    pw.algorithm_manager.apply_sleep_scoring_rules(selected)

                pw.update()
                logger.info("Updated plot algorithms due to setting change")

                # Update table headers to reflect new algorithm name
                if "sleep_algorithm_id" in changed_fields:
                    if self.main_window.table_manager:
                        self.main_window.table_manager.update_table_headers_for_algorithm()

        # 2. Paradigm Change
        # Protocol guarantees data_settings_tab exists with update_loaders_for_paradigm method
        if "data_paradigm" in changed_fields:
            dst = self.main_window.data_settings_tab
            if dst:
                from sleep_scoring_app.core.constants import StudyDataParadigm

                try:
                    paradigm = StudyDataParadigm(new_state.data_paradigm)
                    dst.update_loaders_for_paradigm(paradigm)
                except Exception as e:
                    logger.exception(f"Error updating loaders for paradigm: {e}")

        # 3. Nonwear Algorithm or Choi Axis Change
        # Protocol guarantees these methods exist on PlotWidgetProtocol
        if "nonwear_algorithm_id" in changed_fields or "choi_axis" in changed_fields:
            # Clear caches
            if pw.algorithm_manager:
                pw.algorithm_manager._algorithm_cache.clear()
            pw.clear_choi_cache()

            # Reload nonwear data with the correct choi_axis data
            # This ensures the Choi algorithm uses the configured axis, not display data
            filename = new_state.current_file
            date_str = (
                new_state.available_dates[new_state.current_date_index]
                if 0 <= new_state.current_date_index < len(new_state.available_dates)
                else None
            )

            if filename and date_str:
                # Use load_nonwear_data_for_plot which loads the correct choi_axis data
                self.main_window.load_nonwear_data_for_plot()
                logger.info("Reloaded nonwear data for algorithm/axis change")
            else:
                logger.warning("Cannot reload nonwear data - no file/date selected")

            pw.update()
            logger.info("Updated nonwear detection due to setting change")

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class ConfigPersistenceConnector:
    """
    Syncs store state to the application configuration file.

    This connector listens for changes to study settings in the Redux store
    and persists them to the config file via config_manager.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        logger.info("ConfigPersistenceConnector initialized")

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """Persist study settings changes to config file."""
        if not self.main_window.config_manager:
            return

        # Fields that should be persisted to config
        fields_to_persist = [
            "study_unknown_value",
            "study_valid_groups",
            "study_valid_timepoints",
            "study_default_group",
            "study_default_timepoint",
            "study_participant_id_patterns",
            "study_timepoint_pattern",
            "study_group_pattern",
            "data_paradigm",
            "sleep_algorithm_id",
            "onset_offset_rule_id",
            "night_start_hour",
            "night_end_hour",
            "nonwear_algorithm_id",
            "choi_axis",
        ]

        # Check if any of these changed
        changes = {}
        for field in fields_to_persist:
            old_val = getattr(old_state, field)
            new_val = getattr(new_state, field)
            if old_val != new_val:
                # Convert tuples back to lists for config compatibility if needed
                if isinstance(new_val, tuple):
                    new_val = list(new_val)
                changes[field] = new_val

        if changes:
            logger.info(f"CONFIG PERSISTENCE: Persisting {len(changes)} changes to config")
            # Update config manager
            self.main_window.config_manager.update_study_settings(**changes)

            # Schedule save if autosave is enabled
            if self.main_window.autosave_coordinator:
                self.main_window.autosave_coordinator.schedule_config_save()

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class WindowGeometryConnector:
    """
    Tracks window geometry changes and dispatches them to the store.

    This connector monitors the main window for resize/move events and
    updates the store, which then persists to QSettings via QSettingsPersistenceConnector.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        from PyQt6.QtCore import QTimer

        self.store = store
        self.main_window = main_window
        self._last_geometry: tuple[int, int, int, int] | None = None
        self._last_maximized: bool = False

        # Poll geometry every 500ms (only updates store if changed)
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_geometry)
        self._timer.start(500)

        logger.info("WindowGeometryConnector initialized")

    def _check_geometry(self) -> None:
        """Check if window geometry has changed and dispatch action if so."""
        from sleep_scoring_app.ui.store import Actions

        if not self.main_window.isVisible():
            return

        # Check maximized state
        maximized = self.main_window.isMaximized()
        if maximized != self._last_maximized:
            self._last_maximized = maximized
            self.store.dispatch(Actions.window_maximized_changed(maximized))

        # Check geometry (only if not maximized - maximized geometry is not meaningful)
        if not maximized:
            geometry = self.main_window.geometry()
            current = (geometry.x(), geometry.y(), geometry.width(), geometry.height())

            if current != self._last_geometry:
                self._last_geometry = current
                self.store.dispatch(Actions.window_geometry_changed(*current))

    def disconnect(self) -> None:
        """Cleanup timer."""
        self._timer.stop()


class MarkersConnector:
    """
    Connects the marker state in Redux to the plot widget.

    Subscribes to marker changes and updates the plot widget accordingly.
    Handles clean load (dirty=False) vs manual changes (dirty=True).

    Also connects widget signals to dispatch actions (Widget → Signal → Connector → Store).
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Connect widget signals to dispatch actions (Widget → Connector → Store)
        pw = main_window.plot_widget
        if pw:
            pw.sleep_period_selection_changed.connect(self._on_sleep_selection_signal)
            pw.nonwear_selection_changed.connect(self._on_nonwear_selection_signal)
            pw.sleep_markers_changed.connect(self._on_sleep_markers_signal)
            pw.nonwear_markers_changed.connect(self._on_nonwear_markers_signal)

        # Initial update
        self._update_plot(store.state)

    # ========== Widget Signal Handlers (Widget → Connector → Store) ==========

    def _on_sleep_selection_signal(self, index: int) -> None:
        """Handle sleep period selection signal from widget. Dispatch to store."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"MARKERS CONNECTOR: Widget emitted sleep selection: {index}")
        self.store.dispatch_async(Actions.selected_period_changed(index))

    def _on_nonwear_selection_signal(self, index: int) -> None:
        """Handle nonwear selection signal from widget. Dispatch to store."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"MARKERS CONNECTOR: Widget emitted nonwear selection: {index}")
        self.store.dispatch_async(Actions.selected_nonwear_changed(index))

    def _on_sleep_markers_signal(self, markers) -> None:
        """Handle sleep markers changed signal from widget. Dispatch to store."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug("MARKERS CONNECTOR: Widget emitted sleep_markers_changed")
        self.store.dispatch(Actions.sleep_markers_changed(markers))

    def _on_nonwear_markers_signal(self, markers) -> None:
        """Handle nonwear markers changed signal from widget. Dispatch to store."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug("MARKERS CONNECTOR: Widget emitted nonwear_markers_changed")
        self.store.dispatch(Actions.nonwear_markers_changed(markers))

    # ========== Store State Change Handler (Store → Connector → Widget) ==========

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """
        React to marker state changes.

        Key distinction:
        - markers_loaded (dirty stays False): Load markers FROM Redux INTO widget
        - sleep_markers_changed (dirty becomes True): Widget already has data, just update visuals
        - selection_changed: Update marker visual state (colors) without redrawing

        We use last_marker_update_time to detect changes since the same object
        may be dispatched (identity check would fail).
        """
        # Detect if markers were updated (timestamp changed)
        markers_updated = old_state.last_marker_update_time != new_state.last_marker_update_time

        # Also detect identity changes for initial loads
        sleep_markers_identity_changed = old_state.current_sleep_markers is not new_state.current_sleep_markers
        nonwear_markers_identity_changed = old_state.current_nonwear_markers is not new_state.current_nonwear_markers

        # Detect selection changes
        sleep_selection_changed = old_state.selected_period_index != new_state.selected_period_index
        nonwear_selection_changed = old_state.selected_nonwear_index != new_state.selected_nonwear_index

        # Detect save state changes
        sleep_dirty_changed = old_state.sleep_markers_dirty != new_state.sleep_markers_dirty
        nonwear_dirty_changed = old_state.nonwear_markers_dirty != new_state.nonwear_markers_dirty

        # LOAD: Identity changed AND not dirty (from DB)
        sleep_was_loaded = sleep_markers_identity_changed and not new_state.sleep_markers_dirty
        nonwear_was_loaded = nonwear_markers_identity_changed and not new_state.nonwear_markers_dirty

        # CHANGE: Markers updated AND dirty (user interaction)
        sleep_was_changed = markers_updated and new_state.sleep_markers_dirty
        nonwear_was_changed = markers_updated and new_state.nonwear_markers_dirty

        if sleep_was_loaded or nonwear_was_loaded:
            # Markers loaded from DB - sync FROM Redux TO widget
            logger.info(f"MARKERS CONNECTOR: Markers LOADED from external source. Sleep: {sleep_was_loaded}, Nonwear: {nonwear_was_loaded}")
            self._load_markers_into_widget(new_state, sleep_was_loaded, nonwear_was_loaded)

        elif sleep_was_changed or nonwear_was_changed:
            # Markers changed by user - widget already has data, just update visual elements
            logger.info(f"MARKERS CONNECTOR: Markers CHANGED by user. Sleep: {sleep_was_changed}, Nonwear: {nonwear_was_changed}")
            self._update_visual_elements(new_state, sleep_was_changed, nonwear_was_changed)

        # SELECTION: Update visual state (colors) and widget local state when selection changes
        if sleep_selection_changed:
            logger.info("MARKERS CONNECTOR: Sleep selection CHANGED")
            self._sync_sleep_selection_to_widget(new_state)
            self._update_sleep_selection_visual_state()

        if nonwear_selection_changed:
            logger.info("MARKERS CONNECTOR: Nonwear selection CHANGED")
            self._sync_nonwear_selection_to_widget(new_state)
            self._update_nonwear_selection_visual_state()

        # SAVE STATE: Sync dirty state to widget local state
        if sleep_dirty_changed:
            self._sync_sleep_saved_state_to_widget(new_state)

        if nonwear_dirty_changed:
            self._sync_nonwear_saved_state_to_widget(new_state)

    def _update_plot(self, state: UIState) -> None:
        """Initial load - update plot widget markers based on state."""
        self._load_markers_into_widget(state, load_sleep=True, load_nonwear=True)

    def _load_markers_into_widget(self, state: UIState, load_sleep: bool, load_nonwear: bool) -> None:
        """Load markers FROM Redux INTO widget (for DB loads, date navigation)."""
        pw = self.main_window.plot_widget
        if not pw:
            return

        logger.info(f"MARKERS CONNECTOR: Loading markers into widget. Sleep: {load_sleep}, Nonwear: {load_nonwear}")

        # Block signals to prevent widget from re-emitting changes
        pw.blockSignals(True)
        try:
            # Load Sleep Markers
            if load_sleep:
                if state.current_sleep_markers:
                    pw.load_daily_sleep_markers(
                        state.current_sleep_markers,
                        markers_saved=not state.sleep_markers_dirty,
                    )
                    # Apply visual rules (arrows) if complete
                    selected_period = pw.get_selected_marker_period()
                    if selected_period and selected_period.is_complete:
                        pw.apply_sleep_scoring_rules(selected_period)
                else:
                    # Clear markers if new state has none
                    pw.clear_sleep_markers()
                    # Also clear sleep rule arrows
                    pw.clear_sleep_onset_offset_markers()

            # Load Nonwear Markers
            if load_nonwear:
                if state.current_nonwear_markers:
                    pw.load_daily_nonwear_markers(
                        state.current_nonwear_markers,
                        markers_saved=not state.nonwear_markers_dirty,
                    )
                else:
                    # Clear nonwear markers if new state has none
                    pw.clear_nonwear_markers()
        finally:
            pw.blockSignals(False)

    def _update_visual_elements(self, state: UIState, sleep_changed: bool, nonwear_changed: bool) -> None:
        """
        Update visual elements (arrows, tables) without reloading markers.

        Called when user changes markers - widget already has the data,
        just need to update dependent visual elements.
        """
        pw = self.main_window.plot_widget
        if not pw:
            return

        logger.debug(f"MARKERS CONNECTOR: Updating visuals only. Sleep: {sleep_changed}, Nonwear: {nonwear_changed}")

        if sleep_changed:
            # Update sleep scoring rule arrows for selected period
            selected_period = pw.get_selected_marker_period()
            if selected_period and selected_period.is_complete:
                pw.apply_sleep_scoring_rules(selected_period)

    def _update_sleep_selection_visual_state(self) -> None:
        """
        Update marker visual state (colors) when sleep selection changes.

        Called when selected_period_index changes.
        Updates marker colors to reflect selection without redrawing all markers.

        CRITICAL: When selection is 0 (intentional deselection), we MUST use
        _update_marker_visual_state_no_auto_select() to prevent auto-selection
        from re-selecting a marker.
        """
        pw = self.main_window.plot_widget
        if not pw:
            return

        logger.debug("MARKERS CONNECTOR: Updating sleep selection visual state")

        # Check if this is an intentional deselection (index 0)
        if self.store.state.selected_period_index == 0:
            # Use no-auto-select to prevent re-selection
            pw.marker_renderer._update_marker_visual_state_no_auto_select()
        else:
            pw.marker_renderer.update_marker_visual_state()
            # Only update arrows if a period is actually selected
            selected_period = pw.get_selected_marker_period()
            if selected_period and selected_period.is_complete:
                pw.apply_sleep_scoring_rules(selected_period)

    def _update_nonwear_selection_visual_state(self) -> None:
        """
        Update nonwear marker visual state (colors) when nonwear selection changes.

        Called when selected_nonwear_index changes.
        Updates marker colors to reflect selection without redrawing all markers.

        NOTE: Nonwear markers don't have auto-select, but we use the same pattern
        as sleep for consistency.
        """
        pw = self.main_window.plot_widget
        if not pw:
            return

        logger.debug("MARKERS CONNECTOR: Updating nonwear selection visual state")

        # Use consistent pattern with sleep markers
        if self.store.state.selected_nonwear_index == 0:
            pw.marker_renderer._update_nonwear_marker_visual_state_no_auto_select()
        else:
            pw.marker_renderer.update_nonwear_marker_visual_state()

    # ========== Sync Store State to Widget Local State ==========

    def _sync_sleep_selection_to_widget(self, state: UIState) -> None:
        """Sync sleep selection from store to widget local state."""
        pw = self.main_window.plot_widget
        if not pw:
            return
        if state.selected_period_index is not None:
            pw.set_selected_marker_set_index_from_store(state.selected_period_index)

    def _sync_nonwear_selection_to_widget(self, state: UIState) -> None:
        """Sync nonwear selection from store to widget local state."""
        pw = self.main_window.plot_widget
        if not pw:
            return
        pw.set_selected_nonwear_marker_index_from_store(state.selected_nonwear_index)

    def _sync_sleep_saved_state_to_widget(self, state: UIState) -> None:
        """Sync sleep saved state from store to widget local state."""
        pw = self.main_window.plot_widget
        if not pw:
            return
        pw.set_sleep_markers_saved_from_store(not state.sleep_markers_dirty)

    def _sync_nonwear_saved_state_to_widget(self, state: UIState) -> None:
        """Sync nonwear saved state from store to widget local state."""
        pw = self.main_window.plot_widget
        if not pw:
            return
        pw.set_nonwear_markers_saved_from_store(not state.nonwear_markers_dirty)

    def disconnect(self) -> None:
        """Cleanup subscription and signal connections."""
        self._unsubscribe()
        # Disconnect widget signals
        pw = self.main_window.plot_widget
        if pw:
            try:
                pw.sleep_period_selection_changed.disconnect(self._on_sleep_selection_signal)
                pw.nonwear_selection_changed.disconnect(self._on_nonwear_selection_signal)
                pw.sleep_markers_changed.disconnect(self._on_sleep_markers_signal)
                pw.nonwear_markers_changed.disconnect(self._on_nonwear_markers_signal)
            except (TypeError, RuntimeError):
                pass  # Already disconnected


class AlgorithmDropdownConnector:
    """Connects the activity source dropdown to the store algorithm preference."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)

        # Initial update
        self._update_ui(store.state.current_algorithm)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to algorithm changes."""
        if old_state.current_algorithm != new_state.current_algorithm:
            self._update_ui(new_state.current_algorithm)

    def _update_ui(self, algorithm: str) -> None:
        """Update dropdown selection."""
        # Protocol guarantees analysis_tab has activity_source_dropdown
        tab = self.main_window.analysis_tab
        if not tab:
            return

        dropdown = tab.activity_source_dropdown

        # Find index for this algorithm ID
        index = dropdown.findData(algorithm)
        if index != -1:
            dropdown.blockSignals(True)
            dropdown.setCurrentIndex(index)
            dropdown.blockSignals(False)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()


class SideEffectConnector:
    """
    Handles asynchronous side effects triggered by Store Actions.
    Acts as a middleware/effect handler.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)
        self._last_action_id = None

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """
        Check if a 'Requested' action was dispatched.
        In a real Redux middleware, we'd intercept the action.
        Here, we check the state for 'request flags' or simply react to the intent.
        """
        # For this refactor, we'll use a direct signal-to-effect approach
        # in the individual connectors, but this class serves as the architectural
        # home for future complex side effects.
        pass

    def handle_refresh_files(self) -> None:
        """Orchestrate file discovery and update Store."""
        # Protocol guarantees data_service exists on MainWindowProtocol
        logger.info("SIDE EFFECT: Refreshing files...")
        if self.main_window.data_service:
            # 1. Service handles the 'How'
            files = self.main_window.data_service.find_available_files_with_completion_count()

            # 2. Store handles the 'What'
            from sleep_scoring_app.ui.store import Actions

            self.store.dispatch(Actions.files_loaded(files))
            logger.info(f"SIDE EFFECT: Refresh complete. Found {len(files)} files.")

    def handle_delete_files(self, filenames: list[str]) -> None:
        """Orchestrate file deletion and refresh."""
        # Protocol guarantees data_service and export_manager exist on MainWindowProtocol
        logger.info(f"SIDE EFFECT: Deleting {len(filenames)} files...")
        if self.main_window.data_service and self.main_window.export_manager:
            # Show confirmation (UI interaction is permitted in Effect Handlers)
            from PyQt6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self.main_window,
                "Confirm Delete",
                f"Permanently delete {len(filenames)} file(s)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # 1. Service performs the operation
                self.main_window.data_service.delete_files(filenames)

                # 2. Trigger a refresh to update the list
                self.handle_refresh_files()

    def disconnect(self) -> None:
        self._unsubscribe()


class StoreConnectorManager:
    """Manages all store connectors."""

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self.connectors: list = []

        self._connect_all()

    def _connect_all(self) -> None:
        """Create all connectors."""
        # 1. Create Side Effect Handler
        self.effects = SideEffectConnector(self.store, self.main_window)

        # 2. Create Presentational Connectors
        self.connectors = [
            self.effects,
            SaveButtonConnector(self.store, self.main_window),
            StatusConnector(self.store, self.main_window),
            FileListConnector(self.store, self.main_window),
            FileManagementConnector(self.store, self.main_window),  # NEW
            MarkersConnector(self.store, self.main_window),
            AlgorithmDropdownConnector(self.store, self.main_window),
            DateDropdownConnector(self.store, self.main_window),
            FileTableConnector(self.store, self.main_window),
            PlotArrowsConnector(self.store, self.main_window),
            SideTableConnector(self.store, self.main_window),
            PopOutConnector(self.store, self.main_window),
            AutoSaveConnector(self.store, self.main_window),
            MarkerModeConnector(self.store, self.main_window),
            AdjacentMarkersConnector(self.store, self.main_window),
            AlgorithmConfigConnector(self.store, self.main_window),
            DiaryTableConnector(self.store, self.main_window),
            NavigationConnector(self.store, self.main_window),
            NavigationGuardConnector(self.store, self.main_window),  # Intercepts nav signals
            ViewModeConnector(self.store, self.main_window),
            SignalsConnector(self.store, self.main_window),
            TimeFieldConnector(self.store, self.main_window),
            StudySettingsConnector(self.store, self.main_window),
            CacheConnector(self.store, self.main_window),
            ConfigPersistenceConnector(self.store, self.main_window),
            WindowGeometryConnector(self.store, self.main_window),
        ]

        # 3. Special wiring: Connect the FileManagementConnector to the Effects handler
        # This is a shortcut for this architecture to avoid a full Middleware system
        for c in self.connectors:
            if isinstance(c, FileManagementConnector):
                # Monkey-patch or wire up the requests to the effect handler
                c._on_refresh_requested = self.effects.handle_refresh_files
                c._on_delete_requested = self.effects.handle_delete_files
                # Re-connect signals to new handlers
                if c.widget:
                    try:
                        c.widget.refreshRequested.disconnect()
                        c.widget.deleteRequested.disconnect()
                    except (TypeError, RuntimeError, AttributeError):
                        pass
                    c.widget.refreshRequested.connect(self.effects.handle_refresh_files)
                    c.widget.deleteRequested.connect(self.effects.handle_delete_files)

        logger.info("Connected %d components to store", len(self.connectors))

    def disconnect_all(self) -> None:
        """Disconnect all connectors (cleanup)."""
        for connector in self.connectors:
            connector.disconnect()
        self.connectors.clear()
        logger.info("Disconnected all components from store")


def connect_all_components(store: UIStore, main_window: MainWindowProtocol) -> StoreConnectorManager:
    """
    Connect all UI components to the store.

    Call this in main_window.py after creating the store.

    Args:
        store: The UI store
        main_window: The main window instance

    Returns:
        StoreConnectorManager that can be used to disconnect all connectors

    """
    return StoreConnectorManager(store, main_window)
