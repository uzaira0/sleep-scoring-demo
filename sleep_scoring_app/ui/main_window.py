#!/usr/bin/env python3
"""
Compact Main window class for Sleep Scoring Application
Coordinates between all components in a clean, modular way using service classes.
"""

from __future__ import annotations

import gc
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.core.constants import (
    FeatureFlags,
    MarkerEndpoint,
    SleepMarkerEndpoint,
)
from sleep_scoring_app.data.database import DatabaseManager
from sleep_scoring_app.services.export_service import (
    ExportManager as EnhancedExportManager,
)
from sleep_scoring_app.services.memory_service import (
    BoundedCache,
    memory_monitor,
    resource_manager,
)
from sleep_scoring_app.services.nonwear_service import NonwearDataService
from sleep_scoring_app.services.unified_data_service import UnifiedDataService
from sleep_scoring_app.ui.analysis_tab import AnalysisTab
from sleep_scoring_app.ui.connectors import connect_all_components
from sleep_scoring_app.ui.coordinators import (
    DiaryIntegrationCoordinator,
    ImportUICoordinator,
    TimeFieldCoordinator,
    UIStateCoordinator,
)
from sleep_scoring_app.ui.data_settings_tab import DataSettingsTab
from sleep_scoring_app.ui.export_tab import ExportTab
from sleep_scoring_app.ui.file_navigation import FileNavigationManager
from sleep_scoring_app.ui.marker_table import MarkerTableManager
from sleep_scoring_app.ui.services import SessionStateService
from sleep_scoring_app.ui.store import UIStore
from sleep_scoring_app.ui.study_settings_tab import StudySettingsTab
from sleep_scoring_app.ui.utils.config import ConfigManager
from sleep_scoring_app.ui.window_state import WindowStateManager

if TYPE_CHECKING:
    from PyQt6.QtGui import QCloseEvent

    from sleep_scoring_app.core.dataclasses import DailySleepMarkers, FileInfo, SleepPeriod
    from sleep_scoring_app.ui.protocols import (
        AppStateInterface,
        MainWindowProtocol,
        MarkerOperationsInterface,
        NavigationInterface,
        ServiceContainer,
    )

# Configure logging - use WARNING for production, DEBUG if SLEEP_SCORING_DEBUG env var is set
_log_level = logging.DEBUG if os.getenv("SLEEP_SCORING_DEBUG") else logging.WARNING
logging.basicConfig(level=_log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SleepScoringMainWindow(QMainWindow):
    """Main application window that coordinates all components."""

    # Signals for loading progress updates (for splash screen)
    loading_progress = pyqtSignal(str)
    loading_complete = pyqtSignal()  # Emitted when all loading is done

    def _update_splash(self, message: str) -> None:
        """Update splash screen with progress message."""
        try:
            # Try to access global splash from main module
            import sys

            main_module = sys.modules.get("__main__")
            if main_module and hasattr(main_module, "_global_splash"):  # KEEP: Module-level dynamic attribute
                splash = main_module._global_splash
                app = main_module._global_app
                if splash and app:
                    from PyQt6.QtCore import Qt

                    splash.showMessage(
                        f"Sleep Scoring App\n\n{message}",
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                        Qt.GlobalColor.white,
                    )
                    app.processEvents()
        except Exception as e:
            logger.debug("Splash screen update failed (expected if no splash): %s", e)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sleep Scoring App - Activity Data Visualization")
        self.setGeometry(100, 100, 1280, 720)
        self.setContentsMargins(20, 10, 20, 10)

        # PHASE 1: Initialize core Redux store (Single Source of Truth)
        # This MUST happen first because properties below delegate to self.store
        self.store = UIStore()

        # Internal data state (those that don't belong in Redux yet)
        self.main_48h_data: Any = None
        self._cached_metrics: Any = None
        self._pending_markers: Any = None
        self._marker_index_cache: dict = {}
        self._last_table_update_time: float = 0.0
        self._last_style_update_time: float = 0.0

        # Update splash directly if available
        self._update_splash("Initializing database...")

        # PHASE 3: Initialize core services
        self.db_manager = DatabaseManager(resource_manager=resource_manager)
        self.config_manager = ConfigManager()

        # Initialize config - use defaults if config doesn't exist or is invalid
        if not self.config_manager.is_config_valid() or self.config_manager.config is None:
            from sleep_scoring_app.core.dataclasses import AppConfig

            self.config_manager.config = AppConfig.create_default()

        # Initialize export output path from config
        self.export_output_path = self.config_manager.config.export_directory

        # Initialize Redux store state from config
        self.store.initialize_from_config(self.config_manager.config)

        # Initialize unified data service (headless - no store dependency)
        self.data_service = UnifiedDataService(self.db_manager)
        self.data_manager = self.data_service.data_manager
        self.export_manager = EnhancedExportManager(self.db_manager)
        self.nonwear_service = NonwearDataService(self.db_manager)

        # Initialize import service (headless, used by ImportUICoordinator)
        from sleep_scoring_app.services.import_service import ImportService

        self.import_service = ImportService(self.db_manager)

        # Initialize marker service (headless, used by connectors)
        from sleep_scoring_app.services.marker_service import MarkerService

        self.marker_service = MarkerService(self.db_manager)

        # Initialize window managers with decoupled interfaces
        # Cast self to protocol types - class implements all required protocol methods
        nav = cast("NavigationInterface", self)
        marker_ops = cast("MarkerOperationsInterface", self)
        app_state = cast("AppStateInterface", self)
        services = cast("ServiceContainer", self)
        parent = cast("MainWindowProtocol", self)

        self.state_manager = WindowStateManager(
            store=self.store, navigation=nav, marker_ops=marker_ops, app_state=app_state, services=services, parent=parent
        )
        self.session_service = SessionStateService()
        self.nav_manager = FileNavigationManager(store=self.store, navigation=nav, app_state=app_state, services=services, parent=parent)
        self.table_manager = MarkerTableManager(
            store=self.store,
            navigation=nav,
            marker_ops=marker_ops,
            app_state=app_state,
            services=services,
            parent=parent,
            get_sleep_algorithm_name=self.get_sleep_algorithm_display_name,
        )
        self.diary_coordinator = DiaryIntegrationCoordinator(
            store=self.store, navigation=nav, marker_ops=marker_ops, services=services, parent=parent
        )
        # Note: time_coordinator initialized after UI setup (needs time input fields)

        # Initialize coordinators
        self.import_coordinator = ImportUICoordinator(parent, services=services)
        self.ui_state_coordinator = UIStateCoordinator(parent, store=self.store)

        # Initialize algorithm-data compatibility helper
        from sleep_scoring_app.ui.algorithm_compatibility_ui import AlgorithmCompatibilityUIHelper

        self.compatibility_helper = AlgorithmCompatibilityUIHelper(self)

        # Cache for loaded metrics to avoid redundant database queries
        self._cached_metrics = None

        # Apply saved window size
        self.resize(
            self.config_manager.config.window_width,
            self.config_manager.config.window_height,
        )

        # Data state
        self.current_view_mode = 48  # 24 or 48 hours - default to 48
        self.main_48h_data = None  # Always store 48h dataset

        # Bounded cache for 48-hour data windows per date
        # max_size=20: Typical user browses ~10-15 dates per session, 20 provides headroom
        # max_memory_mb=500: Each 48h dataset ~20-30MB, allows ~15-20 cached datasets
        self.current_date_48h_cache = BoundedCache(max_size=20, max_memory_mb=500)

        # Initialize autosave coordinator (subscribes to Redux store)
        from sleep_scoring_app.ui.coordinators import AutosaveCoordinator

        self.autosave_coordinator = AutosaveCoordinator(
            store=self.store,
            config_manager=self.config_manager,
            db_manager=self.db_manager,
            save_sleep_markers_callback=self._autosave_sleep_markers_to_db,
            save_nonwear_markers_callback=self._autosave_nonwear_markers_to_db,
        )

        # Initialize marker loading coordinator (handles async marker loading on navigation)
        from sleep_scoring_app.ui.coordinators.marker_loading_coordinator import MarkerLoadingCoordinator

        self.marker_loading_coordinator = MarkerLoadingCoordinator(
            store=self.store,
            db_manager=self.db_manager,
        )

        # Register for resource cleanup
        resource_manager.register_resource(f"main_window_{id(self)}", self, self._cleanup_resources)

        # Initialize UI components
        self._update_splash("Setting up user interface...")
        self.setup_ui()

        # Wire up UIStore connectors (must be after setup_ui so components exist)
        self._store_connector_manager = connect_all_components(self.store, cast("MainWindowProtocol", self))

        # Clean up old temporary files
        self._cleanup_old_temp_files()

        # Load saved data folder if it exists (for CSV mode) or enable UI for database mode
        if self.data_service.get_database_mode():
            # In database mode, enable UI but load files on demand
            # Load files synchronously with completion counts during startup
            self._update_splash("Loading file list from database...")
            self.load_available_files(preserve_selection=False, load_completion_counts=True)
            self._update_splash("Files loaded, enabling UI...")
            self.set_ui_enabled(True)
        elif self.config_manager.config.data_folder and os.path.exists(self.config_manager.config.data_folder):
            # In CSV mode, load from data folder if available
            self._update_splash("Scanning data folder...")
            self.data_service.set_data_folder(self.config_manager.config.data_folder)
            self.load_available_files(preserve_selection=False, load_completion_counts=True)
            self.set_ui_enabled(True)
        else:
            # In CSV mode without folder, disable UI until folder is selected
            self.set_ui_enabled(False)

        # Load all saved markers on startup (asynchronously to avoid lag)
        self._update_splash("Loading saved markers...")
        QTimer.singleShot(200, self.load_all_saved_markers_on_startup)

        # Restore session state (must happen after UI is set up)
        self._update_splash("Restoring session...")
        self._restore_session()

        # Emit loading complete signal
        self._update_splash("Loading complete!")
        self.loading_complete.emit()

    # === REDUX DELEGATION PROPERTIES (Single Source of Truth) ===

    @property
    def current_date_index(self) -> int:
        """Get current date index from Redux store."""
        return self.store.state.current_date_index

    @current_date_index.setter
    def current_date_index(self, value: int) -> None:
        """Update current date index in Redux store."""
        from sleep_scoring_app.ui.store import Actions

        if value != self.store.state.current_date_index:
            self.store.dispatch(Actions.date_selected(value))

    @property
    def selected_file(self) -> str | None:
        """Get selected filename from Redux store."""
        return self.store.state.current_file

    @selected_file.setter
    def selected_file(self, value: str | None) -> None:
        """
        Update selected file in Redux store.

        CRITICAL: Always stores just the filename, not the full path.
        The database uses filename as the key, so current_file MUST be filename-only.
        """
        from pathlib import Path

        from sleep_scoring_app.ui.store import Actions

        # Always extract just the filename - database uses filename as key
        filename = Path(value).name if value else None
        if filename != self.store.state.current_file and filename is not None:
            self.store.dispatch(Actions.file_selected(filename))

    @property
    def available_files(self) -> list[FileInfo]:
        """Get available files from Redux store."""
        return list(self.store.state.available_files)

    @available_files.setter
    def available_files(self, value: list[FileInfo]) -> None:
        """Update available files in Redux store."""
        from sleep_scoring_app.ui.store import Actions

        self.store.dispatch(Actions.files_loaded(value))

    @property
    def available_dates(self) -> list:
        """Get available dates from Redux store (robust conversion to date objects)."""
        from datetime import date, datetime

        dates = []
        for d_str in self.store.state.available_dates:
            try:
                # Robust parsing: handle both pure date and full ISO timestamp
                if "T" in d_str:
                    dates.append(datetime.fromisoformat(d_str).date())
                else:
                    dates.append(date.fromisoformat(d_str))
            except (ValueError, TypeError):
                logger.exception(f"Failed to parse date string from state: {d_str}")
        return dates

    @available_dates.setter
    def available_dates(self, value: list) -> None:
        """Update available dates in Redux store."""
        from sleep_scoring_app.ui.store import Actions

        # Normalize to YYYY-MM-DD strings for consistent Redux storage
        date_strs = []
        for d in value:
            if hasattr(d, "strftime"):  # KEEP: Duck typing for date/datetime objects
                date_strs.append(d.strftime("%Y-%m-%d"))
            else:
                date_strs.append(str(d)[:10])  # Fallback for ISO strings

        if tuple(date_strs) != self.store.state.available_dates:
            self.store.dispatch(Actions.dates_loaded(date_strs))

    @property
    def plot_widget(self) -> Any | None:
        """Get plot widget from analysis tab."""
        # analysis_tab is guaranteed to exist after setup_ui()
        # This property is only called from UI event handlers, never during init
        return getattr(self.analysis_tab, "plot_widget", None) if self.analysis_tab else None

    @property
    def onset_table(self) -> Any | None:
        """Get onset table from analysis tab."""
        # analysis_tab is guaranteed to exist after setup_ui()
        return getattr(self.analysis_tab, "onset_table", None) if self.analysis_tab else None

    @property
    def offset_table(self) -> Any | None:
        """Get offset table from analysis tab."""
        # analysis_tab is guaranteed to exist after setup_ui()
        return getattr(self.analysis_tab, "offset_table", None) if self.analysis_tab else None

    def _restore_session(self) -> None:
        """Restore last session state on startup directly into Redux."""
        logger.info("MAIN WINDOW: _restore_session() START")
        from sleep_scoring_app.ui.store import Actions

        # 1. Restore window geometry (standard Qt stuff)
        self.session_service.restore_window_geometry(self)

        # 2. Restore file selection
        last_file_path = self.session_service.get_current_file()
        if last_file_path and self.available_files:
            logger.info(f"MAIN WINDOW: Attempting to restore file: {last_file_path}")
            # Find the matching FileInfo (dataclass, not dict)
            matching_file = None
            last_file_name = Path(last_file_path).name
            for file_info in self.available_files:
                # FileInfo is a dataclass - use attribute access, not .get()
                if str(file_info.source_path) == last_file_path or file_info.filename == last_file_name:
                    matching_file = file_info
                    break

            if matching_file:
                # Dispatch selection to Redux
                logger.info(f"MAIN WINDOW: Restoring file selection to {matching_file.filename}")
                self.store.dispatch(Actions.file_selected(matching_file.filename))
                self.selected_file = last_file_path  # Update the path property

                # CRITICAL: Load dates for the file BEFORE trying to restore date index
                cfg = self.config_manager.config
                skip_rows = cfg.skip_rows if cfg else 0
                new_dates = self.data_service.load_selected_file(matching_file, skip_rows)
                if new_dates:
                    logger.info(f"MAIN WINDOW: Loaded {len(new_dates)} dates for restored file")
                    self.store.dispatch(Actions.dates_loaded(new_dates))
                else:
                    logger.warning("MAIN WINDOW: No dates found for restored file")

                # Restore date index (only if we have dates)
                date_index = self.session_service.get_current_date_index()
                # Validate index against actual available dates
                if new_dates and 0 <= date_index < len(new_dates):
                    logger.info(f"MAIN WINDOW: Restoring date index to {date_index}")
                    self.store.dispatch(Actions.date_selected(date_index))
            else:
                logger.info("MAIN WINDOW: Last file no longer exists in available files")

        # 3. Restore view mode
        view_mode = self.session_service.get_view_mode()
        logger.info(f"MAIN WINDOW: Restoring view mode to {view_mode}h")
        self.store.dispatch(Actions.view_mode_changed(view_mode))

        # 4. Restore tab
        tab_index = self.session_service.get_current_tab()
        if 0 <= tab_index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(tab_index)

        # 5. Restore splitter layout states
        if self.analysis_tab:
            states = self.session_service.get_splitter_states()
            self.analysis_tab.restore_splitter_states(*states)

        logger.info("MAIN WINDOW: _restore_session() COMPLETE")

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change - save to session."""
        # session_service is guaranteed to exist after __init__ Phase 2
        self.session_service.save_current_tab(index)

    def setup_ui(self) -> None:
        """Create the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(15, 10, 15, 10)

        # Create tab widget
        self.tab_widget = QTabWidget()
        # Connect tab change signal to save session
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Create tab components with decoupled interfaces
        # Use casts to satisfy protocol type requirements
        nav = cast("NavigationInterface", self)
        marker_ops = cast("MarkerOperationsInterface", self)
        app_state = cast("AppStateInterface", self)
        services = cast("ServiceContainer", self)

        # Note: Tabs use self directly for QWidget parent, but internal code may need MainWindowProtocol
        self.data_settings_tab = DataSettingsTab(store=self.store, app_state=app_state, services=services, parent=self)  # type: ignore[arg-type]
        self.study_settings_tab = StudySettingsTab(
            store=self.store, navigation=nav, marker_ops=marker_ops, app_state=app_state, services=services, parent=self
        )  # type: ignore[arg-type]
        self.analysis_tab = AnalysisTab(store=self.store, navigation=nav, marker_ops=marker_ops, app_state=app_state, services=services, parent=self)  # type: ignore[arg-type]
        self.export_tab = ExportTab(store=self.store, marker_ops=marker_ops, app_state=app_state, services=services, parent=self)  # type: ignore[arg-type]

        # Connect table click handlers for marker movement
        self._connect_table_click_handlers()

        # Add tabs to tab widget
        self.tab_widget.addTab(self.study_settings_tab, "Study Settings")
        self.tab_widget.addTab(self.data_settings_tab, "Data Settings")
        self.tab_widget.addTab(self.analysis_tab, "Analysis")
        self.tab_widget.addTab(self.export_tab, "Export")

        # Start on Study Settings tab if no folder loaded
        self.tab_widget.setCurrentIndex(0)

        layout.addWidget(self.tab_widget)

        # Create status bar
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.setStyleSheet("""
                QStatusBar {
                    background-color: #f0f0f0;
                    border-top: 1px solid #d0d0d0;
                    padding: 2px;
                }
            """)

            # Create permanent status widgets
            self.algorithm_compat_label = QLabel("")
            self.algorithm_compat_label.setStyleSheet("padding: 0 10px; font-weight: bold;")
            self.algorithm_compat_label.setToolTip("Algorithm compatibility status")
            status_bar.addPermanentWidget(self.algorithm_compat_label)

        # Create references to UI elements from tabs for backward compatibility
        self._setup_ui_references()

        # Connect plot widget UI feedback signals to main window handlers
        # NOTE: Marker data signals (sleep_markers_changed, nonwear_markers_changed)
        # are handled by MarkersConnector which dispatches to Redux.
        # Table updates happen via SideTableConnector reacting to Redux state.
        # This follows the CLAUDE.md Redux pattern: Widget → Connector → Store → Connector → UI
        if self.plot_widget:
            self.plot_widget.error_occurred.connect(self.handle_plot_error)
            self.plot_widget.marker_limit_exceeded.connect(self.handle_marker_limit_exceeded)

    def _setup_ui_references(self) -> None:
        """Create references to commonly accessed UI elements."""
        logger.info("MAIN WINDOW: _setup_ui_references START")
        # Direct references to frequently accessed components only
        self.file_selector = self.analysis_tab.file_selector
        self.date_dropdown = self.analysis_tab.date_dropdown
        logger.info(f"MAIN WINDOW: date_dropdown set to: {self.date_dropdown}")

        # Time input widgets (from analysis_tab)
        self.onset_time_input = self.analysis_tab.onset_time_input
        self.offset_time_input = self.analysis_tab.offset_time_input
        self.total_duration_label = self.analysis_tab.total_duration_label

        # Tables (from analysis_tab)
        self.diary_table_widget = getattr(self.analysis_tab, "diary_table_widget", None)

        # Action Buttons (from analysis_tab)
        self.save_markers_btn = getattr(self.analysis_tab, "save_markers_btn", None)
        self.no_sleep_btn = getattr(self.analysis_tab, "no_sleep_btn", None)
        self.clear_markers_btn = getattr(self.analysis_tab, "clear_markers_btn", None)
        self.export_btn = getattr(self.export_tab, "export_btn", None)
        self.auto_save_checkbox = getattr(self.analysis_tab, "auto_save_checkbox", None)
        self.autosave_status_label = getattr(self.analysis_tab, "autosave_status_label", None)

        # Marker Mode Controls (from analysis_tab)
        self.sleep_mode_btn = getattr(self.analysis_tab, "sleep_mode_btn", None)
        self.nonwear_mode_btn = getattr(self.analysis_tab, "nonwear_mode_btn", None)
        self.marker_mode_group = getattr(self.analysis_tab, "marker_mode_group", None)
        self.show_manual_nonwear_checkbox = getattr(self.analysis_tab, "show_manual_nonwear_checkbox", None)

        # Navigation Buttons (from analysis_tab)
        self.prev_date_btn = getattr(self.analysis_tab, "prev_date_btn", None)
        self.next_date_btn = getattr(self.analysis_tab, "next_date_btn", None)
        self.view_24h_btn = getattr(self.analysis_tab, "view_24h_btn", None)
        self.view_48h_btn = getattr(self.analysis_tab, "view_48h_btn", None)
        self.activity_source_dropdown = getattr(self.analysis_tab, "activity_source_dropdown", None)
        self.weekday_label = getattr(self.analysis_tab, "weekday_label", None)
        self.show_adjacent_day_markers_checkbox = getattr(self.analysis_tab, "show_adjacent_day_markers_checkbox", None)

        # Initialize time field coordinator now that UI fields are available
        self.time_coordinator = TimeFieldCoordinator(
            store=self.store,
            onset_time_input=self.onset_time_input,
            offset_time_input=self.offset_time_input,
            total_duration_label=self.total_duration_label,
            update_callback=self.set_manual_sleep_times,
        )

    # Delegate methods removed - handled by Connectors and Redux state transitions

    def load_available_files(self, preserve_selection: bool = True, load_completion_counts: bool = False) -> None:
        """Load available data files into the Redux state."""
        # data_service is initialized in __init__ before this method can be called
        if self.data_service:
            # Service is headless - we provide a callback to dispatch to store
            def on_files_loaded(files):
                from sleep_scoring_app.ui.store import Actions

                self.store.dispatch(Actions.files_loaded(files))

            self.data_service.load_available_files(load_completion_counts, on_files_loaded)

    def load_current_date(self) -> None:
        """Load data for the currently selected file and date index."""
        logger.info("MAIN WINDOW: load_current_date() START")

        try:
            if not self.selected_file:
                logger.warning("MAIN WINDOW: Cannot load date - no file selected")
                return

            if self.current_date_index < 0:
                logger.warning("MAIN WINDOW: Cannot load date - index < 0")
                return

            # Service is headless - pass required parameters explicitly
            state = self.store.state
            current_file = state.current_file
            if current_file is None:
                logger.warning("MAIN WINDOW: Cannot load date - no file in state")
                return

            logger.info("MAIN WINDOW: Triggering data_service.load_current_date()")
            result = self.data_service.load_current_date(
                self.current_date_48h_cache,
                list(state.available_dates),
                state.current_date_index,
                current_file,
            )

            # 2. Update visuals if load was successful
            if result:
                timestamps, activity_data = result
                state = self.store.state

                # Update weekday label from Store state
                current_date = None
                if 0 <= state.current_date_index < len(state.available_dates):
                    date_str = state.available_dates[state.current_date_index]
                    from datetime import date

                    current_date = date.fromisoformat(date_str)
                    weekday_str = current_date.strftime("%A")
                    # AnalysisTab always creates weekday_label in _create_navigation_controls()
                    self.analysis_tab.weekday_label.setText(f"Day: {weekday_str}")

                # UPDATE THE PLOT with loaded data
                # Use len() checks for numpy array compatibility (truthiness is ambiguous)
                has_data = timestamps is not None and len(timestamps) > 0 and activity_data is not None and len(activity_data) > 0
                if self.plot_widget and has_data:
                    logger.info(f"MAIN WINDOW: Updating plot with {len(timestamps)} data points")
                    self.plot_widget.update_data_and_view_only(timestamps, activity_data, state.view_mode_hours, current_date=current_date)

                    # Load nonwear data after plot data is updated
                    self.load_nonwear_data_for_plot()

            logger.info("MAIN WINDOW: load_current_date() COMPLETE")
        except Exception as e:
            logger.exception(f"MAIN WINDOW ERROR in load_current_date: {e}")

    def set_view_mode(self, hours) -> None:
        """Switch between 24h and 48h view modes WITHOUT reloading data or clearing markers."""
        # The data service handles all state updates atomically including UI button states
        self.data_service.set_view_mode(hours)
        # Save to session
        self.session_service.save_view_mode(hours)

    def change_view_range_only(self, hours) -> None:
        """Change view range without reloading data - preserves sleep markers."""
        self.data_service.change_view_range_only(hours)

    def filter_to_24h_view(self, timestamps_48h, activity_data_48h, target_date) -> tuple[list, list]:
        """Filter 48h dataset to 24h noon-to-noon view."""
        return self.data_service.filter_to_24h_view(timestamps_48h, activity_data_48h, target_date)

    def load_nonwear_data_for_plot(self) -> None:
        """Load nonwear sensor and Choi algorithm data for current file and display on plot."""
        try:
            # Need plot widget with data loaded
            if not self.plot_widget or not self.plot_widget.timestamps:
                logger.debug("Cannot load nonwear data - no plot data available")
                return

            if not self.selected_file:
                logger.debug("Cannot load nonwear data - no file selected")
                return

            from sleep_scoring_app.core.constants import ActivityDataPreference, NonwearDataSource
            from sleep_scoring_app.core.nonwear_data import ActivityDataView, NonwearData

            # Get Choi activity column from config FIRST
            config = self.config_manager.config
            choi_column = config.choi_axis if config else None
            preferred_column = config.preferred_activity_column if config else None

            # Determine what data to use for Choi algorithm
            # If choi_column matches display column, use plot data; otherwise load specific column
            if choi_column == preferred_column:
                # Choi column matches display - use existing plot data
                choi_timestamps = list(self.plot_widget.timestamps)
                choi_counts = list(self.plot_widget.activity_data) if self.plot_widget.activity_data else []
                logger.debug("Using display data for Choi (column=%s)", choi_column)
            else:
                # Choi column differs from display - load the specific column data
                target_date = self.available_dates[self.current_date_index] if self.available_dates and self.current_date_index != -1 else None
                if target_date:
                    # Map choi_column string to ActivityDataPreference enum
                    choi_pref = ActivityDataPreference(choi_column) if choi_column else ActivityDataPreference.VECTOR_MAGNITUDE
                    result = self.data_service.load_activity_data_only(
                        filename=Path(self.selected_file).name if self.selected_file else "",
                        target_date=target_date,
                        activity_column=choi_pref,
                        hours=48,
                    )
                    if result:
                        choi_timestamps, choi_counts = result
                        logger.info("Loaded Choi-specific data for column=%s (%d points)", choi_column, len(choi_counts))
                    else:
                        # Fallback to plot data if loading fails
                        choi_timestamps = list(self.plot_widget.timestamps)
                        choi_counts = list(self.plot_widget.activity_data) if self.plot_widget.activity_data else []
                        logger.warning("Failed to load Choi-specific column, using display data")
                else:
                    choi_timestamps = list(self.plot_widget.timestamps)
                    choi_counts = list(self.plot_widget.activity_data) if self.plot_widget.activity_data else []
                    logger.warning("No target date available, using display data for Choi")

            # Create activity view with the correct Choi data
            # Use just the filename (not full path) for database queries
            current_filename = Path(self.selected_file).name if self.selected_file else ""
            activity_view = ActivityDataView.create(
                timestamps=choi_timestamps,
                counts=choi_counts,
                filename=current_filename,
            )

            # Load sensor periods from database
            raw_sensor_periods = self.nonwear_service.get_nonwear_periods_for_file(
                filename=current_filename,
                source=NonwearDataSource.NONWEAR_SENSOR,
            )

            logger.debug("Loaded %d sensor periods for %s", len(raw_sensor_periods), self.selected_file)

            # Create NonwearData object - now activity_view contains the correct Choi axis data
            # Convert string column to ActivityDataPreference enum
            choi_pref_for_nonwear = ActivityDataPreference(choi_column) if choi_column else ActivityDataPreference.VECTOR_MAGNITUDE
            nonwear_data = NonwearData.create_for_activity_view(
                activity_view=activity_view,
                raw_sensor_periods=raw_sensor_periods,
                nonwear_service=self.nonwear_service,
                choi_activity_column=choi_pref_for_nonwear,
            )

            # Set on plot widget
            self.plot_widget.set_nonwear_data(nonwear_data)

            logger.info("Loaded nonwear data: %d sensor periods, %d choi periods", len(nonwear_data.sensor_periods), len(nonwear_data.choi_periods))

        except Exception as e:
            logger.exception("Failed to load nonwear data for plot: %s", e)

    def _get_cached_metrics(self) -> list:
        """Get cached metrics, loading from database if not already cached."""
        if self._cached_metrics is None:
            try:
                self._cached_metrics = self.export_manager.db_manager.load_sleep_metrics()
            except Exception:
                self._cached_metrics = []
        return self._cached_metrics

    def _invalidate_metrics_cache(self) -> None:
        """Invalidate the metrics cache (call when data changes)."""
        self._cached_metrics = None

        # Refresh export tab data summary (export_tab created in setup_ui)
        if self.export_tab is not None:
            self.export_tab.refresh_data_summary()

    def _get_axis_y_data_for_sadeh(self) -> list[float]:
        """
        Get axis_y data specifically for Sadeh algorithm.

        ARCHITECTURE: Uses Redux store as single source of truth.
        ActivityDataConnector loads ALL columns with SAME timestamps,
        preventing the alignment bugs that occurred when loading columns separately.
        """
        # Get axis_y from Redux store - single source of truth
        state = self.store.state
        if state.axis_y_data and state.activity_timestamps:
            logger.info(
                "Using axis_y from STORE: %d points (guaranteed aligned with timestamps)",
                len(state.axis_y_data),
            )
            return list(state.axis_y_data)

        # Store is empty - this should not happen if ActivityDataConnector is working
        logger.warning("axis_y not in store - ActivityDataConnector may not have loaded data yet")
        return []

    def _get_file_completion_count(self, filename: str) -> tuple[int, int]:
        """Get file completion count as (completed/total) - returns tuple (completed_count, total_count)."""
        return self.data_service.get_file_completion_count(filename)

    def set_activity_data_preferences(self, preferred: str, choi: str) -> None:
        """
        Set the activity data preferences for the application.

        This method updates both the runtime configuration and the persisted settings.

        Args:
            preferred: The column to use for main activity display (e.g., 'axis_y', 'vm')
            choi: The column to use for the Choi nonwear algorithm

        """
        try:
            logger.info(f"Setting activity preferences - Preferred: {preferred}, Choi: {choi}")

            # Update configuration via services
            config = self.config_manager.config if self.config_manager else None
            if config:
                config.preferred_activity_column = preferred
                config.choi_axis = choi
                self.config_manager.save_config()

            # Update plot widget if it exists
            if self.plot_widget:
                # The switcher will handle the heavy lifting of reloading data
                pass

        except Exception as e:
            logger.exception(f"Error setting activity preferences: {e}")

    def get_activity_data_preferences(self) -> tuple[str, str]:
        """Get current activity data column preferences."""
        return self.data_service.get_activity_column_preferences()

    def _restore_file_selection(self, previous_selection, previous_date_index) -> None:
        """Restore file selection after file list refresh."""
        self.data_service.restore_file_selection(previous_selection, previous_date_index)

    def on_file_selected_from_table(self, file_info: FileInfo) -> None:
        """Handle file selection from table widget."""
        if not file_info:
            logger.warning("MAIN WINDOW: on_file_selected_from_table called with None file_info")
            return

        logger.info(f"MAIN WINDOW: on_file_selected_from_table START for: {file_info.filename}")

        # Guard: Skip if same file is already selected (prevents clearing markers)
        if self.store.state.current_file == file_info.filename:
            logger.info("MAIN WINDOW: Same file already selected, skipping reload")
            return

        # Check for unsaved markers before switching files
        if not self._check_unsaved_markers_before_navigation():
            logger.info("MAIN WINDOW: File switch cancelled - unsaved markers")
            return

        # 1. Dispatch file_selected to Redux (this is the ONLY place it should be dispatched)
        from sleep_scoring_app.ui.store import Actions

        logger.info("MAIN WINDOW: Dispatching file_selected action")
        self.store.dispatch(Actions.file_selected(file_info.filename))

        # 2. Update the path property
        self.selected_file = str(file_info.source_path) if file_info.source_path else file_info.filename
        logger.info(f"MAIN WINDOW: Updated selected_file to: {self.selected_file}")

        # 3. Load dates for this file (CRITICAL - must happen AFTER file_selected dispatch)
        config = self.config_manager.config
        skip_rows = config.skip_rows if config else 0
        logger.info(f"MAIN WINDOW: Loading dates via data_service (skip_rows={skip_rows})")
        new_dates = self.data_service.load_selected_file(file_info, skip_rows)

        if new_dates:
            logger.info(f"MAIN WINDOW: Loaded {len(new_dates)} dates, dispatching dates_loaded")
            self.store.dispatch(Actions.dates_loaded(new_dates))
        else:
            logger.warning(f"MAIN WINDOW: NO DATES returned from data_service for {file_info.filename}")
            self.store.dispatch(Actions.dates_loaded([]))

        logger.info("MAIN WINDOW: on_file_selected_from_table COMPLETE")

        # 6. Update activity source dropdown (enable it now that data is loaded)
        # analysis_tab is always created in _init_tabs() before this method is called
        if self.analysis_tab:
            self.analysis_tab.update_activity_source_dropdown()

        # 4. Update session
        self.session_service.save_current_file(self.selected_file)

        # 5. Update compatibility checking
        if file_info.source_path:
            self.compatibility_helper.on_file_loaded(str(file_info.source_path))

    def on_date_dropdown_changed(self, index: int) -> None:
        """Handle date dropdown selection change via Redux."""
        if 0 <= index < len(self.available_dates) and index != self.current_date_index:
            # Check for unsaved markers
            if not self._check_unsaved_markers_before_navigation():
                # Connector will handle visual revert if state doesn't change
                return

            logger.info(f"MAIN WINDOW: Date dropdown changed to {index}, dispatching to Redux")
            from sleep_scoring_app.ui.store import Actions

            self.store.dispatch(Actions.date_selected(index))

            # Save to session
            self.session_service.save_current_date_index(index)

    def _check_unsaved_markers_before_navigation(self) -> bool:
        """
        Check if there are unsaved markers and handle user interaction.
        Returns True if navigation should proceed, False if it should be canceled.
        """
        logger.info("=== _check_unsaved_markers_before_navigation (main_window) START ===")

        # Check if there are any complete markers placed (from Redux store - single source of truth)
        sleep_markers = self.store.state.current_sleep_markers
        has_complete_markers = sleep_markers and sleep_markers.get_complete_periods()
        logger.info(f"has_complete_markers: {has_complete_markers}")

        # Check if markers are NOT saved (use Redux store dirty flags as source of truth)
        markers_dirty = self.store.state.sleep_markers_dirty or self.store.state.nonwear_markers_dirty
        logger.info(f"markers_dirty: {markers_dirty}")

        # Check for incomplete sleep marker being placed
        # PlotWidgetProtocol guarantees these attributes exist after setup_ui()
        plot = self.plot_widget
        if plot is None:
            return True  # No plot widget means no incomplete markers
        has_incomplete_sleep_marker = plot.current_marker_being_placed is not None

        # Check for incomplete nonwear marker being placed
        has_incomplete_nonwear_marker = plot._current_nonwear_marker_being_placed is not None

        # Warn about incomplete markers separately (they will be lost)
        if has_incomplete_sleep_marker or has_incomplete_nonwear_marker:
            incomplete_type = "sleep" if has_incomplete_sleep_marker else "nonwear"
            reply = QMessageBox.warning(
                self,
                "Incomplete Marker",
                f"You have an incomplete {incomplete_type} marker (only onset/start placed).\n\n"
                "This marker will be lost if you navigate away.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            # User wants to continue, cancel the incomplete markers
            if has_incomplete_sleep_marker:
                plot.current_marker_being_placed = None
                plot.marker_renderer.redraw_markers()
            if has_incomplete_nonwear_marker:
                plot._current_nonwear_marker_being_placed = None
                plot.marker_renderer.redraw_nonwear_markers()

        # If there are unsaved complete markers AND autosave is disabled (manual mode), show warning dialog
        # When autosave is enabled, it will auto-save via auto_save_current_markers() below
        if has_complete_markers and markers_dirty and not self.store.state.auto_save_enabled:
            # Create a custom message box with HTML for colored text
            msg = QMessageBox(self)
            msg.setWindowTitle("Unsaved Markers")
            msg.setIcon(QMessageBox.Icon.Warning)

            # Get current date for the message
            current_date = self.available_dates[self.current_date_index] if self.available_dates else None
            date_str = current_date.strftime("%Y-%m-%d") if current_date else "current date"

            msg.setText(f"You have unsaved markers for {date_str}.\nWhat would you like to do?")

            # Create custom buttons
            save_button = msg.addButton("Save Markers and Proceed", QMessageBox.ButtonRole.AcceptRole)
            dont_save_button = msg.addButton("Do Not Save Markers and Proceed", QMessageBox.ButtonRole.DestructiveRole)
            msg.addButton(QMessageBox.StandardButton.Cancel)

            msg.setDefaultButton(save_button)

            msg.exec()

            clicked_button = msg.clickedButton()

            if clicked_button == save_button:
                # Save markers and proceed
                self.save_current_markers()
                return True

            if clicked_button == dont_save_button:
                # Show confirmation dialog for not saving
                confirm_msg = QMessageBox.question(
                    self,
                    "Confirm Discard Markers",
                    f"Are you sure you want to discard the unsaved markers for {date_str}?\n\nThis action cannot be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if confirm_msg == QMessageBox.StandardButton.Yes:
                    # User confirmed, proceed without saving
                    return True
                # User canceled the confirmation, don't navigate
                return False

            # Cancel button or dialog closed
            return False

        # Autosave is enabled - force immediate save before navigation to prevent data loss
        # This ensures any pending debounced saves are executed synchronously
        if markers_dirty and self.store.state.auto_save_enabled:
            logger.info("Forcing immediate save before navigation (autosave enabled, markers dirty)")
            # Force the autosave coordinator to save immediately (bypasses debounce timer)
            if self.autosave_coordinator is not None:
                self.autosave_coordinator.force_save()
            else:
                # Fallback to direct save if coordinator not available
                self.auto_save_current_markers()

        return True

    def prev_date(self) -> None:
        """
        Navigate to previous date.

        NOTE: This method exists for Protocol compatibility.
        Navigation is normally handled by NavigationGuardConnector via button signals.
        """
        # Check for unsaved markers before proceeding
        if not self._check_unsaved_markers_before_navigation():
            return  # User canceled the navigation

        try:
            if self.current_date_index > 0:
                # Dispatch to store - ActivityDataConnector handles data loading
                from sleep_scoring_app.ui.store import Actions

                self.store.dispatch(Actions.date_navigated(-1))
                # NOTE: NavigationConnector updates dropdown, ActivityDataConnector loads data
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return

    def next_date(self) -> None:
        """
        Navigate to next date.

        NOTE: This method exists for Protocol compatibility.
        Navigation is normally handled by NavigationGuardConnector via button signals.
        """
        # Check for unsaved markers before proceeding
        if not self._check_unsaved_markers_before_navigation():
            return  # User canceled the navigation

        try:
            if self.current_date_index < len(self.available_dates) - 1:
                # Dispatch to store - ActivityDataConnector handles data loading
                from sleep_scoring_app.ui.store import Actions

                self.store.dispatch(Actions.date_navigated(1))
                # NOTE: NavigationConnector updates dropdown, ActivityDataConnector loads data
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return

    def handle_sleep_markers_changed(self, daily_sleep_markers: DailySleepMarkers) -> None:
        """Handle sleep marker changes - combines both info update and table update."""
        self.state_manager.handle_sleep_markers_changed(daily_sleep_markers)

    def handle_nonwear_markers_changed(self, daily_nonwear_markers) -> None:
        """
        Handle nonwear marker changes - dispatches action to store.
        The autosave coordinator will pick up the dirty state and save.
        """
        from sleep_scoring_app.ui.store import Actions

        self.store.dispatch(Actions.nonwear_markers_changed(daily_nonwear_markers))

    def handle_plot_error(self, error_message: str) -> None:
        """
        Handle errors from the activity plot widget.

        Args:
            error_message: The error message to display.

        """
        logger.error("Plot error: %s", error_message)
        if (status_bar := self.statusBar()) is not None:
            status_bar.showMessage(f"Error: {error_message}", 5000)

    def handle_marker_limit_exceeded(self, error_message: str) -> None:
        """
        Handle marker limit exceeded errors.

        Args:
            error_message: The error message to display.

        """
        logger.warning("Marker limit exceeded: %s", error_message)
        QMessageBox.warning(self, "Marker Limit Exceeded", error_message)

    def handle_nonwear_marker_selected(self, nonwear_period) -> None:
        """
        Handle nonwear marker selection - update side tables with start/end data.

        Args:
            nonwear_period: The selected ManualNonwearPeriod, or None if deselected.

        """
        if nonwear_period is None or not nonwear_period.is_complete:
            # Clear tables when no nonwear marker is selected
            self.update_marker_tables([], [])
            return

        try:
            # Get data around the start and end timestamps (similar to onset/offset for sleep)
            start_data = self._get_marker_data_cached(nonwear_period.start_timestamp, None)
            end_data = self._get_marker_data_cached(nonwear_period.end_timestamp, None)

            # Update the tables - reusing the onset/offset tables for start/end
            self.update_marker_tables(start_data, end_data)

            logger.debug(
                "Updated tables for nonwear marker %d: start=%s, end=%s",
                nonwear_period.marker_index,
                len(start_data),
                len(end_data),
            )

        except Exception as e:
            logger.warning("Error updating tables for nonwear marker selection: %s", e)

    def _autosave_sleep_markers_to_db(self, daily_sleep_markers: DailySleepMarkers) -> None:
        """
        Lightweight autosave of sleep markers to the database.

        PERFORMANCE: Only saves marker positions (onset/offset timestamps).
        Skips all expensive operations:
        - No algorithm result fetching (Choi, sensor, Sadeh)
        - No metrics calculation (WASO, TST, sleep efficiency, etc.)

        Full metrics are calculated at EXPORT time, not on every marker drag.
        """
        try:
            # Get main sleep period - just need the marker positions
            main_sleep = daily_sleep_markers.get_main_sleep()
            if not main_sleep or not main_sleep.is_complete:
                return

            if not self.selected_file:
                return

            # Get current date
            current_date = self.available_dates[self.current_date_index] if self.available_dates else datetime.now()
            analysis_date = current_date.strftime("%Y-%m-%d")
            filename = Path(self.selected_file).name

            # Create MINIMAL SleepMetrics with just marker positions
            # No expensive calculations - metrics will be computed at export time
            from sleep_scoring_app.core.dataclasses_markers import SleepMetrics
            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            # Extract participant info from filename (timepoint, group, numerical ID)
            participant = extract_participant_info(filename)

            # Get current algorithm and rule from store state
            from sleep_scoring_app.core.constants import AlgorithmType, SleepPeriodDetectorType

            algorithm_id = self.store.state.sleep_algorithm_id
            rule_id = self.store.state.onset_offset_rule_id

            # Convert algorithm ID to enum
            try:
                algorithm_type = AlgorithmType(algorithm_id) if algorithm_id else AlgorithmType.SADEH_1994_ACTILIFE
            except ValueError:
                algorithm_type = AlgorithmType.SADEH_1994_ACTILIFE

            # Convert timestamps to time strings
            onset_time_str = ""
            offset_time_str = ""
            if main_sleep.onset_timestamp:
                onset_time_str = datetime.fromtimestamp(main_sleep.onset_timestamp).strftime("%H:%M")
            if main_sleep.offset_timestamp:
                offset_time_str = datetime.fromtimestamp(main_sleep.offset_timestamp).strftime("%H:%M")

            sleep_metrics = SleepMetrics(
                participant=participant,
                filename=filename,
                analysis_date=analysis_date,
                daily_sleep_markers=daily_sleep_markers,
                algorithm_type=algorithm_type,
                sleep_algorithm_name=algorithm_id,
                sleep_period_detector_id=rule_id or SleepPeriodDetectorType.CONSECUTIVE_ONSET3S_OFFSET5S,
                onset_time=onset_time_str,
                offset_time=offset_time_str,
                updated_at=datetime.now().isoformat(),
            )

            # Save directly to database - lightweight path
            self.db_manager.save_sleep_metrics(sleep_metrics)
            logger.debug("Autosaved markers for %s (lightweight)", filename)

            # Invalidate marker status cache
            if self.state_manager:
                self.state_manager.invalidate_marker_status_cache(filename)

            # NOTE: markers_saved() is dispatched by AutosaveCoordinator after ALL saves complete

        except Exception as e:
            logger.warning("Error in _autosave_sleep_markers_to_db: %s", e)

    def _autosave_nonwear_markers_to_db(self, daily_nonwear_markers) -> None:
        """
        Autosaves nonwear markers to the database.
        This method is a callback for the AutosaveCoordinator.
        """
        try:
            # Get current file and date
            if not self.selected_file:
                return

            # Validate bounds before accessing
            if not self.available_dates or self.current_date_index < 0 or self.current_date_index >= len(self.available_dates):
                return

            current_date = self.available_dates[self.current_date_index]
            filename = Path(self.selected_file).name

            # Extract participant info
            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            participant_info = extract_participant_info(filename)
            participant_id = participant_info.numerical_id

            # Save nonwear markers to database
            self.db_manager.save_manual_nonwear_markers(
                filename=filename,
                participant_id=participant_id,
                sleep_date=current_date,
                daily_nonwear_markers=daily_nonwear_markers,
            )
            logger.debug("Autosaved nonwear markers for %s on %s", filename, current_date)

            # NOTE: markers_saved() is dispatched by AutosaveCoordinator after ALL saves complete

        except Exception as e:
            logger.warning("Error in _autosave_nonwear_markers_to_db: %s", e)

    def update_sleep_info(self, sleep_period: SleepPeriod | None) -> None:
        """
        Update sleep information display with protection against update loops.

        Args:
            sleep_period: The SleepPeriod to display info for, or None to clear.

        """
        # Check if we're in the middle of a field-to-marker update to prevent loops
        if getattr(self, "_updating_from_fields", False):
            logger.debug("Skipping field update - currently updating from fields to prevent loop")
            return

        # Don't update fields if user is actively editing them
        if self._is_user_editing_time_fields():
            logger.debug("Skipping field update - user is actively editing")
            # Still update the info label though
            self._update_sleep_info_label_only(sleep_period)
            return

        # Set flag to prevent recursive updates
        self._updating_from_markers = True
        try:
            if sleep_period is None:
                # Clear everything
                self.total_duration_label.setText("")
                self.onset_time_input.clear()
                self.offset_time_input.clear()
            elif sleep_period.onset_timestamp is None:
                # No markers at all
                self.total_duration_label.setText("")
                self.onset_time_input.clear()
                self.offset_time_input.clear()
            elif not sleep_period.is_complete:
                # Only onset, no offset yet
                start_time = datetime.fromtimestamp(sleep_period.onset_timestamp)
                self.total_duration_label.setText("")
                self.onset_time_input.setText(start_time.strftime("%H:%M"))
                self.offset_time_input.clear()
            else:
                # Complete period with both onset and offset
                # is_complete guarantees both timestamps are not None
                assert sleep_period.onset_timestamp is not None
                assert sleep_period.offset_timestamp is not None
                start_time = datetime.fromtimestamp(sleep_period.onset_timestamp)
                end_time = datetime.fromtimestamp(sleep_period.offset_timestamp)

                # Update total duration label
                if sleep_period.duration_hours is not None:
                    self.total_duration_label.setText(f"Total Duration: {sleep_period.duration_hours:.1f} hours")
                else:
                    self.total_duration_label.setText("Total Duration: --")

                # Update manual input fields with visual feedback
                self.onset_time_input.setText(start_time.strftime("%H:%M"))
                self.offset_time_input.setText(end_time.strftime("%H:%M"))

                # Add subtle visual feedback to show fields were synced from markers
                self._apply_synced_field_style()
        finally:
            # Always clear the flag
            self._updating_from_markers = False

    def _is_user_editing_time_fields(self) -> bool:
        """Check if user is actively editing either time field."""
        # Check if either field has focus
        onset_has_focus = self.onset_time_input.hasFocus()
        offset_has_focus = self.offset_time_input.hasFocus()
        return onset_has_focus or offset_has_focus

    def _update_sleep_info_label_only(self, sleep_period: SleepPeriod | None) -> None:
        """Update only the duration label without touching the input fields."""
        if sleep_period is None or not sleep_period.is_complete:
            self.total_duration_label.setText("")
        elif sleep_period.duration_hours is not None:
            self.total_duration_label.setText(f"Total Duration: {sleep_period.duration_hours:.1f} hours")
        else:
            self.total_duration_label.setText("Total Duration: --")

    def _apply_synced_field_style(self) -> None:
        """Apply visual style to indicate fields were synced from markers."""
        from PyQt6.QtCore import QTimer

        # PERFORMANCE: Throttle style updates during rapid marker changes (drag)
        if False:  # Dead code: _last_style_update_time initialized in Phase 1
            self._last_style_update_time = 0

        import time

        current_time = time.time()
        if current_time - self._last_style_update_time < 0.5:  # Max once per 500ms
            return
        self._last_style_update_time = current_time

        # Apply a subtle background color (removed invalid 'transition' property causing Qt warnings)
        synced_style = """
            QLineEdit {
                background-color: #f0f8ff;
            }
        """

        self.onset_time_input.setStyleSheet(synced_style)
        self.offset_time_input.setStyleSheet(synced_style)

        # Clear the style after a short delay
        QTimer.singleShot(500, self._clear_synced_field_style)

    def _clear_synced_field_style(self) -> None:
        """Clear the synced field style to return to normal."""
        from sleep_scoring_app.core.constants import UIColors

        normal_style = f"""
            QLineEdit:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
        """

        self.onset_time_input.setStyleSheet(normal_style)
        self.offset_time_input.setStyleSheet(normal_style)

    def update_marker_tables(self, onset_data, offset_data) -> None:
        """Update the data tables with surrounding marker information."""
        self.table_manager.update_marker_tables(onset_data, offset_data)

    def _connect_table_click_handlers(self) -> None:
        """Connect click handlers for marker tables to enable row click to move marker."""
        try:
            # Connect onset table right-click handler for marker movement
            if self.onset_table is not None and hasattr(self.onset_table, "table_widget"):  # KEEP: Table duck typing
                table = self.onset_table.table_widget
                table.customContextMenuRequested.connect(lambda pos: self._on_onset_table_right_clicked(pos))
                logger.debug("Connected onset table right-click handler")

            # Connect offset table right-click handler for marker movement
            if self.offset_table is not None and hasattr(self.offset_table, "table_widget"):  # KEEP: Table duck typing
                table = self.offset_table.table_widget
                table.customContextMenuRequested.connect(lambda pos: self._on_offset_table_right_clicked(pos))
                logger.debug("Connected offset table right-click handler")

        except Exception as e:
            logger.exception(f"Failed to connect table click handlers: {e}")

    def _on_onset_table_right_clicked(self, pos) -> None:
        """Handle right-click on onset table row to move onset marker."""
        if self.onset_table is None:
            return
        table = self.onset_table.table_widget
        item = table.itemAt(pos)
        if not item:
            return

        row = item.row()
        # Clear selection to prevent highlighting on right-click
        table.clearSelection()
        self._move_marker_from_table_click(SleepMarkerEndpoint.ONSET, row)

    def _on_offset_table_right_clicked(self, pos) -> None:
        """Handle right-click on offset table row to move offset marker."""
        if self.offset_table is None:
            return
        table = self.offset_table.table_widget
        item = table.itemAt(pos)
        if not item:
            return

        row = item.row()
        # Clear selection to prevent highlighting on right-click
        table.clearSelection()
        self._move_marker_from_table_click(SleepMarkerEndpoint.OFFSET, row)

    def _get_marker_data_cached(self, marker_timestamp: float, cached_idx: int | None = None) -> list[dict[str, Any]]:
        """Get marker surrounding data using cached index for better performance during drag operations."""
        return self.table_manager.get_marker_data_cached(marker_timestamp, cached_idx)

    def _get_full_48h_data_for_popout(self, marker_timestamp: float | None = None) -> list[dict[str, Any]]:
        """Get all 2880 rows of 48-hour data for pop-out tables (full day view)."""
        return self.table_manager.get_full_48h_data_for_popout(marker_timestamp)

    def _move_marker_from_table_click(self, marker_type: str, row: int) -> None:
        """Move a marker based on table row click."""
        self.table_manager.move_marker_from_table_click(marker_type, row)

    def move_marker_to_timestamp(self, marker_type: str, timestamp: float) -> None:
        """
        Move a marker to a specific timestamp (for pop-out table clicks).

        This method checks the active marker category and moves either sleep or nonwear markers.
        For sleep markers: marker_type is "onset" or "offset"
        For nonwear markers: marker_type is mapped from "onset"/"offset" to "start"/"end"

        Args:
            marker_type: "onset" or "offset" (mapped to "start"/"end" for nonwear)
            timestamp: Unix timestamp to move the marker to

        """
        from sleep_scoring_app.core.constants import MarkerCategory

        try:
            # Check if we have plot widget and it's ready
            if self.plot_widget is None:  # Guaranteed after setup_ui
                logger.warning("Plot widget not available for marker movement")
                return

            # Check active marker category
            active_category = self.plot_widget.get_active_marker_category()

            if active_category == MarkerCategory.NONWEAR:
                # Move nonwear marker
                # Map onset/offset to start/end for nonwear markers
                nonwear_marker_type = MarkerEndpoint.START if marker_type == SleepMarkerEndpoint.ONSET else MarkerEndpoint.END

                selected_period = self.plot_widget.marker_renderer.get_selected_nonwear_period()
                period_slot = selected_period.marker_index if selected_period else None

                if not selected_period:
                    logger.warning("No nonwear period selected to move marker for")
                    return

                logger.debug(f"Moving nonwear {nonwear_marker_type} marker for period {period_slot}")

                success = self.plot_widget.move_nonwear_marker_to_timestamp(nonwear_marker_type, timestamp, period_slot)

                if success:
                    logger.info(f"Successfully moved nonwear {nonwear_marker_type} marker for period {period_slot} to timestamp {timestamp}")
                else:
                    logger.warning(f"Failed to move nonwear {nonwear_marker_type} marker for period {period_slot} to timestamp {timestamp}")

            else:
                # Move sleep marker (default behavior)
                selected_period = None
                period_slot = None

                if hasattr(self.plot_widget, "get_selected_marker_period"):  # KEEP: Plot widget duck typing
                    selected_period = self.plot_widget.get_selected_marker_period()
                    if selected_period:
                        # Use the marker_index from the selected period
                        period_slot = selected_period.marker_index
                        logger.debug(f"Moving {marker_type} marker for period {period_slot} ({selected_period.marker_type.value})")

                # Move the marker to the target timestamp
                # Pass the period_slot to move the correct period (main sleep or nap)
                success = self.plot_widget.move_marker_to_timestamp(marker_type, timestamp, period_slot)

                if success:
                    logger.info(f"Successfully moved {marker_type} marker for period {period_slot} to timestamp {timestamp}")
                    # Auto-save after successful movement
                    self.auto_save_current_markers()
                else:
                    logger.warning(f"Failed to move {marker_type} marker for period {period_slot} to timestamp {timestamp}")

        except Exception as e:
            logger.error(f"Error moving {marker_type} marker to timestamp: {e}", exc_info=True)

    def _find_timestamp_by_time_string(self, time_str: str) -> float | None:
        """
        Find timestamp that matches a time string (HH:MM format).

        Args:
            time_str: Time string in HH:MM format

        Returns:
            Unix timestamp or None if not found

        """
        try:
            # PlotWidgetProtocol guarantees timestamps exists after setup_ui()
            plot = self.plot_widget
            if plot is None or not plot.timestamps:
                return None

            # Parse the time string
            try:
                hour, minute = map(int, time_str.split(":"))
            except ValueError:
                logger.warning(f"Invalid time string format: {time_str}")
                return None

            # Search through timestamps to find matching hour and minute
            for ts in plot.timestamps:
                if ts.hour == hour and ts.minute == minute:
                    # Convert datetime to unix timestamp
                    return ts.timestamp()

            logger.warning(f"No timestamp found matching time {time_str}")
            return None

        except Exception as e:
            logger.exception(f"Error finding timestamp for time string {time_str}: {e}")
            return None

    def _create_sleep_period_from_timestamps(
        self, onset_timestamp: float | None, offset_timestamp: float | None, is_main_sleep: bool = False
    ) -> SleepPeriod | None:
        """Create a sleep period from timestamps."""
        return self.state_manager.create_sleep_period_from_timestamps(onset_timestamp, offset_timestamp, is_main_sleep)

    def _create_onset_marker_from_diary(self, onset_timestamp: float) -> None:
        """
        Create or update only the onset marker.

        Uses Redux store as single source of truth (per CLAUDE.md).

        Args:
            onset_timestamp: Unix timestamp for sleep onset

        """
        try:
            from sleep_scoring_app.core.dataclasses import SleepPeriod
            from sleep_scoring_app.core.dataclasses_markers import DailySleepMarkers
            from sleep_scoring_app.ui.store import Actions

            # Get markers from Redux store (SINGLE SOURCE OF TRUTH)
            markers = self.store.state.current_sleep_markers
            if markers is None:
                markers = DailySleepMarkers()

            main_sleep = markers.get_main_sleep()

            plot = self.plot_widget
            if plot is None:
                logger.warning("Plot widget not available for onset marker from diary")
                return

            if main_sleep:
                # Update existing period's onset
                main_sleep.onset_timestamp = onset_timestamp
                if not main_sleep.offset_timestamp:
                    # Period is incomplete, set it as current marker being placed
                    plot.current_marker_being_placed = main_sleep
            else:
                # Create new incomplete period
                new_period = SleepPeriod(onset_timestamp=onset_timestamp, offset_timestamp=None, marker_index=1)
                markers.period_1 = new_period
                plot.current_marker_being_placed = new_period

            markers.update_classifications()

            # Dispatch to Redux - connector will update widget
            self.store.dispatch(Actions.sleep_markers_changed(markers))
            plot.redraw_markers()

        except Exception as e:
            logger.error(f"Error creating onset marker from diary: {e}", exc_info=True)

    def _create_offset_marker_from_diary(self, offset_timestamp: float) -> None:
        """
        Create or update only the offset marker.

        Uses Redux store as single source of truth (per CLAUDE.md).

        Args:
            offset_timestamp: Unix timestamp for sleep offset

        """
        try:
            from sleep_scoring_app.core.dataclasses_markers import DailySleepMarkers
            from sleep_scoring_app.ui.store import Actions

            # Get markers from Redux store (SINGLE SOURCE OF TRUTH)
            markers = self.store.state.current_sleep_markers
            if markers is None:
                markers = DailySleepMarkers()

            plot = self.plot_widget
            if plot is None:
                logger.warning("Plot widget not available for offset marker from diary")
                return

            # Check if there's an incomplete period to complete
            current_period = plot.current_marker_being_placed
            if current_period:
                # Complete the current period
                current_period.offset_timestamp = offset_timestamp

                # Find slot for this period if not already assigned
                if not current_period.marker_index:
                    if not markers.period_1:
                        markers.period_1 = current_period
                        current_period.marker_index = 1
                    elif not markers.period_2:
                        markers.period_2 = current_period
                        current_period.marker_index = 2
                    elif not markers.period_3:
                        markers.period_3 = current_period
                        current_period.marker_index = 3
                    elif not markers.period_4:
                        markers.period_4 = current_period
                        current_period.marker_index = 4

                plot.current_marker_being_placed = None
            else:
                # Check if main sleep exists and needs offset
                main_sleep = markers.get_main_sleep()
                if main_sleep and not main_sleep.offset_timestamp:
                    main_sleep.offset_timestamp = offset_timestamp
                else:
                    logger.warning("No incomplete period to add offset marker to")
                    return

            markers.update_classifications()

            # Dispatch to Redux - connector will update widget
            self.store.dispatch(Actions.sleep_markers_changed(markers))
            plot.redraw_markers()
            self.auto_save_current_markers()

        except Exception as e:
            logger.error(f"Error creating offset marker from diary: {e}", exc_info=True)

    def _find_index_in_timestamps(self, timestamps: list, target_timestamp: float) -> int | None:
        """Find the index of the closest timestamp to the target timestamp."""
        if not timestamps:
            return None

        target_dt = datetime.fromtimestamp(target_timestamp)
        best_idx = None
        min_diff = float("inf")

        for i, ts in enumerate(timestamps):
            time_diff = abs((target_dt - ts).total_seconds())
            if time_diff < min_diff:
                min_diff = time_diff
                best_idx = i
            # Stop if very close match found
            if time_diff < 30:
                break

        return best_idx

    def _force_table_update(self) -> None:
        """Force a final table update after marker dragging completes."""
        if self._pending_markers:
            # Get the most recent marker state and update tables one final time
            selected_period = getattr(self.plot_widget, "get_selected_marker_period", lambda: None)()
            if selected_period and selected_period.is_complete:
                # Use cached method for final update too
                onset_idx = self._marker_index_cache.get(selected_period.onset_timestamp)
                offset_idx = self._marker_index_cache.get(selected_period.offset_timestamp)

                onset_data = self._get_marker_data_cached(selected_period.onset_timestamp, onset_idx)
                offset_data = self._get_marker_data_cached(selected_period.offset_timestamp, offset_idx)

                if onset_data or offset_data:
                    self.update_marker_tables(onset_data, offset_data)

    def set_manual_sleep_times(self) -> None:
        """Set sleep markers manually based on time input with loop prevention and validation."""
        # Get current date from store
        state = self.store.state
        if not state.available_dates or state.current_date_index < 0:
            logger.warning("No date selected, cannot set manual times")
            return

        current_date_str = state.available_dates[state.current_date_index]

        # Parse the date string
        try:
            base_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.exception(f"Could not parse date: {current_date_str}")
            return

        # Get times from input fields
        onset_text = self.onset_time_input.text().strip()
        offset_text = self.offset_time_input.text().strip()

        if not onset_text or not offset_text:
            logger.debug("Both onset and offset times required")
            return

        # Parse times to timestamps
        onset_timestamp = self._parse_time_to_timestamp(onset_text, base_date)
        if onset_timestamp is None:
            logger.warning(f"Invalid onset time format: {onset_text}")
            self._restore_field_from_marker(SleepMarkerEndpoint.ONSET)
            return

        # For offset, if time is earlier than onset, assume next day
        offset_timestamp = self._parse_time_to_timestamp(offset_text, base_date)
        if offset_timestamp is None:
            logger.warning(f"Invalid offset time format: {offset_text}")
            self._restore_field_from_marker(SleepMarkerEndpoint.OFFSET)
            return

        # Handle overnight sleep (offset before onset means next day)
        if offset_timestamp <= onset_timestamp:
            next_day = base_date + timedelta(days=1)
            new_offset = self._parse_time_to_timestamp(offset_text, next_day)
            if new_offset is not None:
                offset_timestamp = new_offset

        # Update the sleep period
        self._update_selected_sleep_period(onset_timestamp, offset_timestamp)
        logger.info(f"Manual sleep times set: {onset_text} - {offset_text}")

    def _parse_time_to_timestamp(self, time_text: str, base_date: datetime | date) -> float | None:
        """Parse time text (HH:MM) to timestamp, handling validation."""
        try:
            # Support multiple formats
            time_text = time_text.strip()

            # Try HH:MM format
            if ":" in time_text:
                parts = time_text.split(":")
                if len(parts) != 2:
                    return None
                hour, minute = map(int, parts)
            # Try HHMM format
            elif len(time_text) == 4 and time_text.isdigit():
                hour = int(time_text[:2])
                minute = int(time_text[2:])
            else:
                return None

            # Validate ranges
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None

            # Create datetime object - handle both date and datetime
            if isinstance(base_date, date) and not isinstance(base_date, datetime):
                dt = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute, second=0))
            else:
                dt = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return dt.timestamp()

        except (ValueError, AttributeError):
            return None

    def _restore_field_from_marker(self, field_type: str) -> None:
        """Restore field value from current marker."""
        # PlotWidgetProtocol guarantees get_selected_marker_period exists after setup_ui()
        plot = self.plot_widget
        if plot is None:
            return
        selected_period = plot.get_selected_marker_period()
        if not selected_period:
            return

        if field_type == SleepMarkerEndpoint.ONSET and selected_period.onset_timestamp:
            onset_time = datetime.fromtimestamp(selected_period.onset_timestamp)
            self.onset_time_input.setText(onset_time.strftime("%H:%M"))
        elif field_type == SleepMarkerEndpoint.OFFSET and selected_period.offset_timestamp:
            offset_time = datetime.fromtimestamp(selected_period.offset_timestamp)
            self.offset_time_input.setText(offset_time.strftime("%H:%M"))

    def _update_selected_sleep_period(self, onset_timestamp: float, offset_timestamp: float) -> None:
        """
        Update the currently selected sleep period with new timestamps.

        Uses Redux store as single source of truth (per CLAUDE.md).
        """
        from sleep_scoring_app.ui.store import Actions

        # Get markers from Redux store (SINGLE SOURCE OF TRUTH)
        markers = self.store.state.current_sleep_markers
        if markers is None:
            return

        plot = self.plot_widget
        if plot is None:
            return

        # Get the currently selected period from widget (widget owns selection state)
        # PlotWidgetProtocol guarantees get_selected_marker_period exists
        selected_period = plot.get_selected_marker_period()

        if selected_period:
            # Update existing selected period
            selected_period.onset_timestamp = onset_timestamp
            selected_period.offset_timestamp = offset_timestamp
            # Reclassify and dispatch to Redux
            markers.update_classifications()
            self.store.dispatch(Actions.sleep_markers_changed(markers))
            plot.redraw_markers()
        else:
            # No selected period, create new one using the traditional method
            plot.sleep_markers = [onset_timestamp, offset_timestamp]
            plot.redraw_markers()

    def _update_selected_sleep_period_onset(self, onset_timestamp: float) -> None:
        """Update or create sleep period with just onset."""
        plot = self.plot_widget
        if plot is None:
            return
        if not hasattr(plot, "add_sleep_marker"):  # KEEP: Plot widget duck typing
            # Fallback to old method
            plot.sleep_markers = [onset_timestamp]
            plot.redraw_markers()
        else:
            # Use new marker system
            plot.add_sleep_marker(onset_timestamp)

    def save_current_markers(self) -> None:
        """Save current markers permanently."""
        self.state_manager.save_current_markers()

    def clear_current_markers(self) -> None:
        """Clear current markers from both display and database (including both autosave and permanent markers)."""
        self.state_manager.clear_current_markers()

    def clear_plot_and_ui_state(self) -> None:
        """Clear plot and UI state when switching filters."""
        self.ui_state_coordinator.clear_plot_and_ui_state()

    def mark_no_sleep_period(self) -> None:
        """Mark current date as having no sleep period."""
        self.state_manager.mark_no_sleep_period()

    # NOTE: toggle_adjacent_day_markers DELETED - AdjacentMarkersConnector handles it directly

    def load_saved_markers(self) -> None:
        """Load saved markers for current file and date."""
        self.state_manager.load_saved_markers()
        # Also load nonwear markers
        self.load_saved_nonwear_markers()

    def load_saved_nonwear_markers(self) -> None:
        """Load saved nonwear markers for current file and date."""
        try:
            if not self.selected_file:
                return

            # Validate bounds before accessing
            if not self.available_dates or self.current_date_index < 0 or self.current_date_index >= len(self.available_dates):
                return

            current_date = self.available_dates[self.current_date_index]
            filename = Path(self.selected_file).name

            # Load nonwear markers from database
            daily_nonwear_markers = self.db_manager.load_manual_nonwear_markers(
                filename=filename,
                sleep_date=current_date,
            )

            # Load into plot widget
            plot = self.plot_widget
            if plot is not None and hasattr(plot, "load_daily_nonwear_markers"):  # KEEP: Plot widget duck typing
                plot.load_daily_nonwear_markers(daily_nonwear_markers, markers_saved=True)
                logger.debug("Loaded nonwear markers for %s on %s", filename, current_date)

        except Exception as e:
            logger.warning("Error loading nonwear markers: %s", e)

    def load_all_saved_markers_on_startup(self) -> None:
        """
        Load all saved markers from database on application startup.

        NOTE: This is now a no-op. MarkerLoadingCoordinator automatically loads
        markers when file/date state changes are dispatched to the Redux store.
        Keeping this method for backwards compatibility with existing callers.
        """
        logger.info("MAIN WINDOW: load_all_saved_markers_on_startup() - handled by MarkerLoadingCoordinator")

    def _load_diary_data_for_file(self) -> None:
        """Load diary data for the currently selected file."""
        self.diary_coordinator.load_diary_data_for_file()

    def auto_save_current_markers(self) -> None:
        """
        Auto-save current markers before changing date/file.

        Uses the SAME save path as manual save for consistency.
        """
        # Get daily_sleep_markers from plot widget
        daily_sleep_markers = getattr(self.plot_widget, "daily_sleep_markers", None)
        if not daily_sleep_markers:
            return

        main_sleep = daily_sleep_markers.get_main_sleep()
        if not main_sleep or not main_sleep.is_complete or not self.selected_file:
            return

        if not FeatureFlags.ENABLE_AUTOSAVE:
            return

        # Delegate to the autosave callback which now uses the same path as manual save
        self._autosave_sleep_markers_to_db(daily_sleep_markers)

    def set_ui_enabled(self, enabled) -> None:
        """Enable or disable UI controls based on folder selection status."""
        self.ui_state_coordinator.set_ui_enabled(enabled)

    def update_folder_info_label(self) -> None:
        """Update the file selection label with current file count."""
        self.ui_state_coordinator.update_folder_info_label()

    # Add placeholder methods for configuration and import functionality
    def on_epoch_length_changed(self, value) -> None:
        """Handle epoch length setting change."""
        self.config_manager.update_epoch_length(value)

    def on_skip_rows_changed(self, value) -> None:
        """Handle skip rows setting change."""
        self.config_manager.update_skip_rows(value)

    def on_data_source_changed(self, use_database: bool) -> None:
        """Handle data source selection change for activity data."""
        try:
            # Update the data manager
            self.data_manager.toggle_database_mode(use_database)

            # Save preference to config
            self.config_manager.update_data_source_preference(use_database)

            # Update status bar
            self.update_status_bar()
        except Exception:
            logger.exception("Error changing data source")

    def update_status_bar(self, message: str | None = None) -> None:
        """Update the status bar with a temporary message."""
        try:
            if message:
                self.statusBar().showMessage(message, 5000)  # Show for 5 seconds
        except AttributeError:
            pass

    def get_sleep_algorithm_display_name(self) -> str:
        """
        Get the display name for the configured sleep algorithm.

        CRITICAL: Must read from STORE state, not config_manager.config!
        When study settings change, ConfigPersistenceConnector updates config AFTER
        other connectors have already reacted to the state change. Reading from config
        would return stale values.
        """
        try:
            # Read from store state (single source of truth)
            algorithm_id = self.store.state.sleep_algorithm_id
            if algorithm_id:
                from sleep_scoring_app.services.algorithm_service import get_algorithm_service

                available = get_algorithm_service().get_available_sleep_algorithms()
                if algorithm_id in available:
                    return available[algorithm_id]
        except Exception as e:
            logger.warning("Failed to get sleep algorithm name: %s", e)

        return "Sadeh"

    def update_data_source_status(self) -> None:
        """
        Update the data source status label.

        This method directly updates the widget based on database stats.
        It's acceptable to have this on MainWindow since it:
        1. Reads from db_manager (service)
        2. Updates a simple label (not complex state)
        3. Is triggered by import/clear operations (not Redux state changes)
        """
        try:
            stats = self.db_manager.get_database_stats()
            file_count = stats.get("unique_files", 0)
            record_count = stats.get("total_records", 0)

            status_text = f"{file_count} imported files, {record_count} total records"
            style = "color: #27ae60; font-weight: bold;"

            self.data_settings_tab.activity_status_label.setText(status_text)
            self.data_settings_tab.activity_status_label.setStyleSheet(style)

        except AttributeError as e:
            logger.debug("Cannot update data source status: %s", e)
        except Exception as e:
            try:
                self.data_settings_tab.activity_status_label.setText("Status unavailable")
                self.data_settings_tab.activity_status_label.setStyleSheet("color: #e74c3c;")
            except AttributeError:
                pass
            logger.warning("Error updating data source status: %s", e)

    def browse_data_folder(self) -> None:
        """Browse for CSV data folder (does not automatically load files)."""
        self.import_coordinator.browse_data_folder()

    def browse_activity_files(self) -> None:
        """Browse for activity data files (multi-select)."""
        self.import_coordinator.browse_activity_files()

    def browse_nonwear_files(self) -> None:
        """Browse for nonwear sensor files (multi-select)."""
        self.import_coordinator.browse_nonwear_files()

    def start_activity_import(self) -> None:
        """Start the activity data import process."""
        self.import_coordinator.start_activity_import()

    def start_nonwear_import(self) -> None:
        """Start the nonwear sensor data import process."""
        self.import_coordinator.start_nonwear_import()

    def update_activity_progress(self, progress) -> None:
        """Update activity import progress."""
        self.import_coordinator.update_activity_progress(progress)

    def update_nonwear_progress(self, progress) -> None:
        """Update nonwear import progress."""
        self.import_coordinator.update_nonwear_progress(progress)

    def activity_import_finished(self, progress) -> None:
        """Handle activity import completion."""
        self.import_coordinator.activity_import_finished(progress)

    def nonwear_import_finished(self, progress) -> None:
        """Handle nonwear import completion."""
        self.import_coordinator.nonwear_import_finished(progress)

    def load_data_folder(self) -> None:
        """Load data folder and enable UI."""
        self.import_coordinator.load_data_folder()

    def clear_all_markers(self) -> None:
        """Clear all sleep markers and metrics from database (preserves imported data)."""
        self.state_manager.clear_all_markers()

    def save_export_options(self) -> None:
        """Save export options to config."""
        if self.export_tab is not None:
            tab = self.export_tab
            self.config_manager.update_export_options(
                tab.include_headers_checkbox.isChecked(),
                tab.include_metadata_checkbox.isChecked(),
            )
            # Save nonwear separate file option
            config = self.config_manager.config
            if hasattr(tab, "separate_nonwear_file_checkbox") and config is not None:  # KEEP: Tab duck typing
                config.export_nonwear_separate = tab.separate_nonwear_file_checkbox.isChecked()
                self.config_manager.save_config()

    def browse_export_output_directory(self) -> None:
        """Handle directory selection for export."""
        # Start from saved export directory, then current export path, then current working directory
        config = self.config_manager.config
        start_dir = (config.export_directory if config else None) or self.export_output_path or str(Path.cwd())
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if directory:
            self.export_output_path = directory
            if self.export_tab and hasattr(self.export_tab, "export_output_label"):  # KEEP: Tab duck typing
                self.export_tab.export_output_label.setText(directory)
            # Save to config
            self.config_manager.update_export_directory(directory)

    def perform_direct_export(self) -> None:
        """Perform export directly from the tab without modal dialog."""
        # Ensure export directory exists
        Path(self.export_output_path).mkdir(parents=True, exist_ok=True)

        # Get data based on selected data source
        if self.data_manager.use_database:
            # Database mode - get all data from database
            all_sleep_metrics = self.export_manager.db_manager.load_sleep_metrics()

            if not all_sleep_metrics:
                QMessageBox.warning(
                    self,
                    "No Data",
                    "No data found in database. Please:\n\n"
                    "1. Import CSV files using the Import tab, OR\n"
                    "2. Switch to 'CSV Files' mode in Data Settings and place some markers, OR\n"
                    "3. Use the Analysis tab to create sleep markers first",
                )
                return
        else:
            # CSV mode - can only export if there are markers saved to database
            all_sleep_metrics = self.export_manager.db_manager.load_sleep_metrics()

            if not all_sleep_metrics:
                QMessageBox.warning(
                    self,
                    "No Sleep Markers",
                    "No sleep markers found to export. In CSV mode, you need to:\n\n"
                    "1. Go to the Analysis tab\n"
                    "2. Select a CSV file and date\n"
                    "3. Place sleep markers or mark 'No Sleep'\n"
                    "4. Save the markers\n\n"
                    "Alternatively, switch to 'Database' mode in Data Settings to export imported data.",
                )
                return

        try:
            # Save current preferences
            self.config_manager.update_export_grouping(self.export_grouping_group.checkedId())

            # Check if nonwear should be exported separately
            export_nonwear_separate = hasattr(
                self, "separate_nonwear_file_checkbox"
            )  # KEEP: Optional UI element and self.separate_nonwear_file_checkbox.isChecked()

            # Perform the export directly with data
            result = self.export_manager.perform_direct_export(
                all_sleep_metrics,
                self.export_grouping_group.checkedId(),
                self.export_output_path,
                self.selected_export_columns,
                self.include_headers_checkbox.isChecked(),
                self.include_metadata_checkbox.isChecked(),
                export_nonwear_separate=export_nonwear_separate,
            )

            # Display results with warnings and errors
            if result.success:
                data_source = "database" if self.data_manager.use_database else "CSV markers"
                message_parts = [f"Successfully exported {result.files_exported} file(s) from {data_source} to:\n{self.export_output_path}"]

                if result.files_with_issues > 0:
                    message_parts.append(f"\n{result.files_with_issues} file(s) had issues during export.")

                if result.warnings:
                    message_parts.append(f"\n\nWarnings ({len(result.warnings)}):")
                    for warning in result.warnings[:5]:  # Show first 5 warnings
                        message_parts.append(f"  - {warning}")
                    if len(result.warnings) > 5:
                        message_parts.append(f"  ... and {len(result.warnings) - 5} more warnings")

                if result.errors:
                    message_parts.append(f"\n\nErrors ({len(result.errors)}):")
                    for error in result.errors[:5]:  # Show first 5 errors
                        message_parts.append(f"  - {error}")
                    if len(result.errors) > 5:
                        message_parts.append(f"  ... and {len(result.errors) - 5} more errors")

                # Choose appropriate message box type
                if result.errors:
                    QMessageBox.warning(
                        self,
                        "Export Completed with Errors",
                        "\n".join(message_parts),
                    )
                elif result.warnings:
                    QMessageBox.information(
                        self,
                        "Export Completed with Warnings",
                        "\n".join(message_parts),
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Export Complete",
                        "\n".join(message_parts),
                    )
            else:
                # Export completely failed
                message_parts = ["Export operation failed."]

                if result.errors:
                    message_parts.append(f"\n\nErrors ({len(result.errors)}):")
                    for error in result.errors[:10]:  # Show more errors on failure
                        message_parts.append(f"  - {error}")
                    if len(result.errors) > 10:
                        message_parts.append(f"  ... and {len(result.errors) - 10} more errors")

                if result.warnings:
                    message_parts.append(f"\n\nWarnings ({len(result.warnings)}):")
                    for warning in result.warnings[:5]:
                        message_parts.append(f"  - {warning}")
                    if len(result.warnings) > 5:
                        message_parts.append(f"  ... and {len(result.warnings) - 5} more warnings")

                message_parts.append("\n\nCheck the console for full details.")

                QMessageBox.critical(
                    self,
                    "Export Failed",
                    "\n".join(message_parts),
                )

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Export failed with error: {e}")

    def _cleanup_old_temp_files(self) -> None:
        """Clean up old temporary export files."""
        try:
            export_dir = Path.cwd() / "sleep_data_exports"
            if export_dir.exists():
                # Find all temp files older than 1 day
                cutoff_time = datetime.now() - timedelta(days=1)

                for temp_file in export_dir.glob("export_temp_*.csv"):
                    try:
                        file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        if file_time < cutoff_time:
                            temp_file.unlink()
                            logger.debug("Cleaned up old temp file: %s", temp_file.name)
                    except Exception as e:
                        logger.debug("Could not clean up temp file %s: %s", temp_file.name, e)
        except Exception as e:
            logger.warning("Error cleaning up temp files: %s", e)

    def _hide_progress_components(self) -> None:
        """Hide activity progress components after import completion."""
        try:
            if hasattr(self, "data_settings_tab"):  # KEEP: Cleanup during shutdown
                tab = self.data_settings_tab
                if hasattr(tab, "activity_progress_label"):  # KEEP: Tab duck typing  # KEEP: Tab duck typing
                    tab.activity_progress_label.setVisible(False)
                if hasattr(tab, "activity_progress_bar"):  # KEEP: Tab duck typing
                    tab.activity_progress_bar.setVisible(False)
        except Exception as e:
            logger.warning("Error hiding activity progress components: %s", e)

    def _hide_nonwear_progress_components(self) -> None:
        """Hide nonwear progress components after import completion."""
        try:
            if hasattr(self, "data_settings_tab"):  # KEEP: Cleanup during shutdown
                tab = self.data_settings_tab
                if hasattr(tab, "nwt_progress_label"):  # KEEP: Tab duck typing
                    tab.nwt_progress_label.setVisible(False)
                if hasattr(tab, "nwt_progress_bar"):  # KEEP: Tab duck typing
                    tab.nwt_progress_bar.setVisible(False)
        except Exception as e:
            logger.warning("Error hiding nonwear progress components: %s", e)

    def _cleanup_resources(self) -> None:
        """Clean up resources before shutdown."""
        try:
            # Disconnect store connectors
            if self._store_connector_manager is not None:
                self._store_connector_manager.disconnect_all()

            # Clean up analysis tab
            if hasattr(self, "analysis_tab") and self.analysis_tab:  # KEEP: Cleanup during shutdown
                if hasattr(self.analysis_tab, "cleanup_tab"):  # KEEP: Optional cleanup method
                    self.analysis_tab.cleanup_tab()

            # Clean up plot widget (if not already cleaned by analysis tab)
            if hasattr(self, "plot_widget") and self.plot_widget:  # KEEP: Cleanup during shutdown
                if hasattr(self.plot_widget, "cleanup_widget"):  # KEEP: Plot widget duck typing
                    self.plot_widget.cleanup_widget()

            # Clear data caches
            self.current_date_48h_cache.clear()
            self.main_48h_data = None
            plot = self.plot_widget
            if plot is not None and hasattr(plot, "main_48h_axis_y_data"):  # KEEP: Plot widget duck typing
                plot.main_48h_axis_y_data = None

            # Clear available data
            self.available_files.clear()
            self.available_dates.clear()

            # Force garbage collection
            gc.collect()

            logger.debug("Main window resources cleaned up")
        except Exception as e:
            logger.warning("Error cleaning up main window resources: %s", e)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """Handle window close event with proper cleanup."""
        try:
            # Force save all pending changes through autosave coordinator
            if self.autosave_coordinator is not None:  # Guaranteed after Phase 2
                self.autosave_coordinator.force_save()

            # Auto-save current markers (legacy - will be replaced by autosave coordinator)
            self.auto_save_current_markers()

            # Save session state - session_service guaranteed after Phase 2
            current_file = Path(self.selected_file).name if self.selected_file else None
            self.session_service.save_all(
                current_file=current_file,
                date_index=self.current_date_index,
                view_mode=self.current_view_mode,
                current_tab=self.tab_widget.currentIndex(),
                window=self,
            )

            # Save splitter layout states
            if self.analysis_tab:
                states = self.analysis_tab.save_splitter_states()
                self.session_service.save_splitter_states(*states)

            # Clean up autosave coordinator
            if self.autosave_coordinator is not None:  # Guaranteed after Phase 2
                self.autosave_coordinator.cleanup()

            # Clean up resources
            self._cleanup_resources()

            # Check memory usage
            memory_stats = memory_monitor.check_memory_usage()
            if memory_stats.get("status") == "warning":
                memory_monitor.force_garbage_collection()

            event.accept()
        except Exception as e:
            logger.warning("Error during window close: %s", e)
            event.accept()  # Always accept to prevent hanging
