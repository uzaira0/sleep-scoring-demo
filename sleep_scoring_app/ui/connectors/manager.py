"""
Connector manager and side effect handling.

Contains SideEffectConnector, StoreConnectorManager, and connect_all_components function.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .activity import ActivityDataConnector
from .file import FileListConnector, FileManagementConnector, FileSelectionLabelConnector, FileTableConnector
from .marker import AdjacentMarkersConnector, AutoSaveConnector, MarkerModeConnector, MarkersConnector
from .navigation import DateDropdownConnector, NavigationConnector, NavigationGuardConnector, ViewModeConnector
from .persistence import ConfigPersistenceConnector, WindowGeometryConnector
from .plot import PlotArrowsConnector, PlotClickConnector, PlotDataConnector
from .save_status import SaveButtonConnector, StatusConnector
from .settings import AlgorithmConfigConnector, AlgorithmDropdownConnector, CacheConnector, StudySettingsConnector
from .table import DiaryTableConnector, PopOutConnector, SideTableConnector
from .ui_controls import AnalysisTabConnector, SignalsConnector, TimeFieldConnector, UIControlsConnector

if TYPE_CHECKING:
    from sleep_scoring_app.ui.protocols import MainWindowProtocol
    from sleep_scoring_app.ui.store import UIState, UIStore

logger = logging.getLogger(__name__)


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
        React to pending request flags set by reducer.

        Architecture: Widget dispatches action -> Reducer sets pending flag ->
        Effect handler sees flag, performs side effect, clears flag.
        """
        from sleep_scoring_app.ui.store import Actions

        # Handle pending refresh files request
        if new_state.pending_refresh_files and not old_state.pending_refresh_files:
            self.handle_refresh_files()
            self.store.dispatch(Actions.pending_request_cleared("refresh_files"))

        # Handle pending clear activity request
        if new_state.pending_clear_activity and not old_state.pending_clear_activity:
            self.handle_clear_activity_data()
            self.store.dispatch(Actions.pending_request_cleared("clear_activity"))

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

    def handle_clear_activity_data(self) -> None:
        """Orchestrate clearing all activity data and refreshing file list."""
        logger.info("SIDE EFFECT: Clearing activity data...")
        from sleep_scoring_app.ui.store import Actions

        try:
            # 1. Service clears the data
            if self.main_window.db_manager:
                deleted_count = self.main_window.db_manager.clear_activity_data()
                logger.info(f"SIDE EFFECT: Cleared {deleted_count} activity records")

            # 2. Reset state via store - clear all related state
            self.store.dispatch(Actions.file_selected(None))
            self.store.dispatch(Actions.dates_loaded([]))
            self.store.dispatch(Actions.activity_data_cleared())
            self.store.dispatch(Actions.markers_cleared())

            # 3. Refresh file list
            self.handle_refresh_files()

        except Exception as e:
            logger.exception("Failed to clear activity data: %s", e)

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
            UIControlsConnector(self.store, self.main_window),
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
            FileSelectionLabelConnector(self.store, self.main_window),  # Updates file selection label
            ActivityDataConnector(self.store, self.main_window),  # CRITICAL: Loads unified data to store
            PlotDataConnector(self.store, self.main_window),  # CRITICAL: Updates plot from store
            PlotClickConnector(self.store, self.main_window),  # Handles plot clicks via Redux state
            NavigationConnector(self.store, self.main_window),
            NavigationGuardConnector(self.store, self.main_window),  # Intercepts nav signals
            AnalysisTabConnector(self.store, self.main_window),  # Bridges control signals to store
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
