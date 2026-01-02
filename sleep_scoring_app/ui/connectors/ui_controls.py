"""
UI controls connectors.

Connects UI controls (enable/disable), analysis tab signals, file signals, and time fields to the Redux store.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import FileInfo
    from sleep_scoring_app.ui.protocols import MainWindowProtocol
    from sleep_scoring_app.ui.store import UIState, UIStore

logger = logging.getLogger(__name__)


class UIControlsConnector:
    """
    Connects UI control enable/disable state to the Redux store.

    This connector handles enabling/disabling main UI controls (navigation,
    time inputs, action buttons, plot) based on store state.
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window
        self._unsubscribe = store.subscribe(self._on_state_change)
        logger.info("UI CONTROLS CONNECTOR: Initialized")

        # Initial update
        self._update_controls(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to ui_controls_enabled state changes."""
        if old_state.ui_controls_enabled != new_state.ui_controls_enabled:
            logger.info(f"UI CONTROLS CONNECTOR: Enabled changed to {new_state.ui_controls_enabled}")
            self._update_controls(new_state)

    def _update_controls(self, state: UIState) -> None:
        """Enable or disable UI controls based on state."""
        enabled = state.ui_controls_enabled
        mw = self.main_window

        try:
            # File selection and navigation
            if mw.file_selector:
                mw.file_selector.setEnabled(enabled)
            if mw.prev_date_btn:
                # Additional navigation logic for prev/next based on date index
                can_go_prev = enabled and state.current_date_index > 0
                mw.prev_date_btn.setEnabled(can_go_prev)
            if mw.next_date_btn:
                can_go_next = enabled and state.current_date_index < len(state.available_dates) - 1
                mw.next_date_btn.setEnabled(can_go_next)

            # View mode buttons
            if mw.view_24h_btn:
                mw.view_24h_btn.setEnabled(enabled)
            if mw.view_48h_btn:
                mw.view_48h_btn.setEnabled(enabled)

            # Manual time entry
            if mw.onset_time_input:
                mw.onset_time_input.setEnabled(enabled)
            if mw.offset_time_input:
                mw.offset_time_input.setEnabled(enabled)

            # Action buttons
            if mw.save_markers_btn:
                mw.save_markers_btn.setEnabled(enabled)
            if mw.no_sleep_btn:
                mw.no_sleep_btn.setEnabled(enabled)
            if mw.clear_markers_btn:
                mw.clear_markers_btn.setEnabled(enabled)
            if mw.export_btn:
                mw.export_btn.setEnabled(enabled)

            # Plot widget
            if mw.plot_widget:
                mw.plot_widget.setEnabled(enabled)

        except AttributeError as e:
            logger.warning("UI CONTROLS CONNECTOR: Missing widget - %s", e)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()
        logger.info("UI CONTROLS CONNECTOR: Disconnected")


class AnalysisTabConnector:
    """
    Connects AnalysisTab control signals to Redux store dispatch.

    This connector bridges widget signals to store actions, following the architecture:
    Widget (emit signal) -> Connector (dispatch action) -> Store -> Connectors (update widgets)

    Signals handled:
    - activitySourceChanged -> Actions.algorithm_changed
    - viewModeChanged -> Actions.view_mode_changed
    - adjacentMarkersToggled -> Actions.adjacent_markers_toggled
    - autoSaveToggled -> Actions.auto_save_toggled
    - markerModeChanged -> Actions.marker_mode_changed
    """

    def __init__(self, store: UIStore, main_window: MainWindowProtocol) -> None:
        self.store = store
        self.main_window = main_window

        # Connect to AnalysisTab control signals
        tab = main_window.analysis_tab
        if tab:
            tab.activitySourceChanged.connect(self._on_activity_source_changed)
            tab.viewModeChanged.connect(self._on_view_mode_changed)
            tab.adjacentMarkersToggled.connect(self._on_adjacent_markers_toggled)
            tab.autoSaveToggled.connect(self._on_auto_save_toggled)
            tab.markerModeChanged.connect(self._on_marker_mode_changed)
            logger.info("ANALYSIS TAB CONNECTOR: Connected to AnalysisTab control signals")

    def _on_activity_source_changed(self, selected_data) -> None:
        """Dispatch algorithm_changed action when activity source changes."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"ANALYSIS TAB CONNECTOR: Activity source changed to {selected_data}")
        self.store.dispatch(Actions.algorithm_changed(selected_data))

    def _on_view_mode_changed(self, hours: int) -> None:
        """Dispatch view_mode_changed action when view mode changes."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"ANALYSIS TAB CONNECTOR: View mode changed to {hours}")
        # Use dispatch_async for safety (MW-04 fix)
        self.store.dispatch_async(Actions.view_mode_changed(hours))

    def _on_adjacent_markers_toggled(self, checked: bool) -> None:
        """Dispatch adjacent_markers_toggled action when checkbox changes."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"ANALYSIS TAB CONNECTOR: Adjacent markers toggled to {checked}")
        self.store.dispatch(Actions.adjacent_markers_toggled(checked))

    def _on_auto_save_toggled(self, checked: bool) -> None:
        """Dispatch auto_save_toggled action when checkbox changes."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"ANALYSIS TAB CONNECTOR: Auto-save toggled to {checked}")
        self.store.dispatch(Actions.auto_save_toggled(checked))

    def _on_marker_mode_changed(self, category) -> None:
        """Dispatch marker_mode_changed action when mode changes."""
        from sleep_scoring_app.ui.store import Actions

        logger.debug(f"ANALYSIS TAB CONNECTOR: Marker mode changed to {category}")
        self.store.dispatch(Actions.marker_mode_changed(category))

    def disconnect(self) -> None:
        """Cleanup signal connections."""
        tab = self.main_window.analysis_tab
        if tab:
            try:
                tab.activitySourceChanged.disconnect(self._on_activity_source_changed)
                tab.viewModeChanged.disconnect(self._on_view_mode_changed)
                tab.adjacentMarkersToggled.disconnect(self._on_adjacent_markers_toggled)
                tab.autoSaveToggled.disconnect(self._on_auto_save_toggled)
                tab.markerModeChanged.disconnect(self._on_marker_mode_changed)
            except (TypeError, RuntimeError):
                pass  # Already disconnected


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
        # 1. File Selection Table - Protocol guarantees file_selector exists on AnalysisTabProtocol
        tab = self.main_window.analysis_tab
        if tab and tab.file_selector:
            # Connect the custom fileSelected signal to a dispatcher
            tab.file_selector.fileSelected.connect(self._on_file_selected)

    def _on_file_selected(self, row: int, file_info: FileInfo) -> None:
        """Handle file selection from UI table."""
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
        self._update_fields(store.state)

    def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
        """React to marker or selection changes by updating time fields."""
        # Update if markers changed (identity or internal content via timestamp)
        markers_changed = (
            old_state.current_sleep_markers is not new_state.current_sleep_markers
            or old_state.last_marker_update_time != new_state.last_marker_update_time
        )

        if markers_changed:
            self._update_fields(new_state)

    def _update_fields(self, state: UIState) -> None:
        """Update time fields via MainWindow.update_sleep_info()."""
        # Get selected period from current markers
        sleep_period = None
        if state.current_sleep_markers:
            complete_periods = state.current_sleep_markers.get_complete_periods()
            if complete_periods:
                # Use selected period or first period
                idx = max(0, min(state.selected_period_index or 0, len(complete_periods) - 1))
                sleep_period = complete_periods[idx]

        # Protocol guarantees update_sleep_info exists on MainWindowProtocol
        self.main_window.update_sleep_info(sleep_period)

    def disconnect(self) -> None:
        """Cleanup subscription."""
        self._unsubscribe()
