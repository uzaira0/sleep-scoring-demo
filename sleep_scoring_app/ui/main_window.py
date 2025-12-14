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
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.core.constants import (
    AlgorithmType,
    ButtonStyle,
    ButtonText,
    FeatureFlags,
    InfoMessage,
    SleepStatusValue,
    StudyDataParadigm,
    SuccessMessage,
    TableDimensions,
    WindowTitle,
)
from sleep_scoring_app.core.dataclasses import ParticipantInfo, SleepMetrics
from sleep_scoring_app.data.database import DatabaseManager
from sleep_scoring_app.services.export_service import (
    ExportManager as EnhancedExportManager,
)
from sleep_scoring_app.services.import_worker import ImportWorker
from sleep_scoring_app.services.memory_service import (
    BoundedCache,
    memory_monitor,
    resource_manager,
)
from sleep_scoring_app.services.nonwear_service import NonwearDataService
from sleep_scoring_app.services.unified_data_service import UnifiedDataService
from sleep_scoring_app.ui.analysis_tab import AnalysisTab
from sleep_scoring_app.ui.data_settings_tab import DataSettingsTab
from sleep_scoring_app.ui.diary_integration import DiaryIntegrationManager
from sleep_scoring_app.ui.export_tab import ExportTab
from sleep_scoring_app.ui.file_navigation import FileNavigationManager
from sleep_scoring_app.ui.marker_table import MarkerTableManager
from sleep_scoring_app.ui.study_settings_tab import StudySettingsTab
from sleep_scoring_app.ui.time_fields import TimeFieldManager
from sleep_scoring_app.ui.window_state import WindowStateManager
from sleep_scoring_app.utils.config import ConfigManager
from sleep_scoring_app.utils.table_helpers import update_marker_table

if TYPE_CHECKING:
    from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod

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
            if main_module and hasattr(main_module, "_global_splash"):
                splash = main_module._global_splash
                app = main_module._global_app
                if splash and app:
                    from PyQt6.QtCore import Qt

                    splash.showMessage(
                        f"Sleep Research Analysis Tool\n\n{message}",
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                        Qt.GlobalColor.white,
                    )
                    app.processEvents()
        except Exception:
            pass  # Silently fail if splash not available

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sleep Research Analysis Tool - Activity Data Visualization")
        self.setGeometry(100, 100, 1280, 720)
        self.setContentsMargins(20, 10, 20, 10)

        # Update splash directly if available
        self._update_splash("Initializing database...")

        # Initialize shared database manager first to avoid multiple initializations
        self.db_manager = DatabaseManager()

        # Initialize component managers with shared database
        self.config_manager = ConfigManager()

        # Initialize config - use defaults if config doesn't exist or is invalid
        if not self.config_manager.is_config_valid() or self.config_manager.config is None:
            from sleep_scoring_app.core.dataclasses import AppConfig

            # Use default config to get started
            self.config_manager.config = AppConfig.create_default()

        # Initialize export output path from config
        self.export_output_path = self.config_manager.config.export_directory

        # Initialize unified data service
        self.data_service = UnifiedDataService(self, self.db_manager)

        # Apply saved data source preference
        self.data_service.toggle_database_mode(self.config_manager.config.use_database)

        # Direct service references
        self.data_manager = self.data_service.data_manager

        self.export_manager = EnhancedExportManager(self.db_manager)

        # Initialize nonwear data service
        self.nonwear_service = NonwearDataService(self.db_manager)

        # Direct service references
        self.data_manager = self.data_service.data_manager

        # Initialize window managers
        self.state_manager = WindowStateManager(self)
        self.nav_manager = FileNavigationManager(self)
        self.table_manager = MarkerTableManager(self)
        self.diary_manager = DiaryIntegrationManager(self)
        self.time_manager = TimeFieldManager(self)

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
        self.available_files = []
        self.selected_file = None
        self.available_dates = []
        self.current_date_index = 0
        self.current_view_mode = 48  # 24 or 48 hours - default to 48
        self.main_48h_data = None  # Always store 48h dataset

        # Bounded cache for 48-hour data windows per date
        # max_size=20: Typical user browses ~10-15 dates per session, 20 provides headroom
        # max_memory_mb=500: Each 48h dataset ~20-30MB, allows ~15-20 cached datasets
        self.current_date_48h_cache = BoundedCache(max_size=20, max_memory_mb=500)

        # Register for resource cleanup
        resource_manager.register_resource(f"main_window_{id(self)}", self, self._cleanup_resources)

        # Initialize UI components
        self._update_splash("Setting up user interface...")
        self.setup_ui()

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

        # Emit loading complete signal
        self._update_splash("Loading complete!")
        self.loading_complete.emit()

    def setup_ui(self) -> None:
        """Create the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(15, 10, 15, 10)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Create tab components
        self.data_settings_tab = DataSettingsTab(parent=self)
        self.study_settings_tab = StudySettingsTab(parent=self)
        self.analysis_tab = AnalysisTab(parent=self)
        self.export_tab = ExportTab(parent=self)

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
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        self.status_bar.setStyleSheet("""
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
        self.status_bar.addPermanentWidget(self.algorithm_compat_label)

        self.data_source_label = QLabel("Data Source: Not configured")
        self.data_source_label.setStyleSheet("padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.data_source_label)

        self.file_count_label = QLabel("Files: 0")
        self.file_count_label.setStyleSheet("padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.file_count_label)

        # Create references to UI elements from tabs for backward compatibility
        self._setup_ui_references()

    def _setup_ui_references(self) -> None:
        """Create references to commonly accessed UI elements."""
        # Direct references to frequently accessed components only
        self.file_selector = self.analysis_tab.file_selector
        self.date_dropdown = self.analysis_tab.date_dropdown
        self.plot_widget = self.analysis_tab.plot_widget

    # Delegate methods to services
    def _invalidate_marker_status_cache(self, filename=None) -> None:
        """Invalidate marker status cache for a specific file or all files."""
        self.data_service.invalidate_marker_status_cache(filename)

    def _refresh_file_dropdown_indicators(self) -> None:
        """Refresh just the indicators in the file dropdown without full reload."""
        self.data_service.refresh_file_dropdown_indicators()

    def load_available_files(self, preserve_selection=True, load_completion_counts=False) -> None:
        """Load available files using DataManager with optional state preservation."""
        self.data_service.load_available_files(preserve_selection, load_completion_counts)
        # Update status bar with file count
        self.update_status_bar()
        # Update folder info label with correct file count
        self.update_folder_info_label()

    def populate_date_dropdown(self) -> None:
        """Populate date dropdown with available dates and purely visual marker indicators."""
        self.data_service.populate_date_dropdown()

    def load_current_date(self) -> None:
        """Load data for current date - always loads 48h as main dataset."""
        self.data_service.load_current_date()

    def set_view_mode(self, hours) -> None:
        """Switch between 24h and 48h view modes WITHOUT reloading data or clearing markers."""
        # The data service handles all state updates atomically including UI button states
        self.data_service.set_view_mode(hours)

    def change_view_range_only(self, hours) -> None:
        """Change view range without reloading data - preserves sleep markers."""
        self.data_service.change_view_range_only(hours)

    def filter_to_24h_view(self, timestamps_48h, activity_data_48h, target_date) -> tuple[list, list]:
        """Filter 48h dataset to 24h noon-to-noon view."""
        return self.data_service.filter_to_24h_view(timestamps_48h, activity_data_48h, target_date)

    def load_nonwear_data_for_plot(self) -> None:
        """Load nonwear sensor and Choi algorithm data for current file and display on plot."""
        self.data_service.load_nonwear_data_for_plot()

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

        # Refresh export tab data summary if it exists
        if hasattr(self, "export_tab") and self.export_tab is not None:
            self.export_tab.refresh_data_summary()

    def _get_axis_y_data_for_sadeh(self) -> list[float]:
        """Get axis_y data specifically for Sadeh algorithm using UNIFIED loading method."""
        # Get current filename and date
        current_filename = self.current_file_info.get("filename") if hasattr(self, "current_file_info") else None
        current_date = self.available_dates[self.current_date_index] if hasattr(self, "current_date_index") and self.available_dates else None

        if not current_filename or not current_date:
            logger.warning("No current filename or date for axis_y loading")
            return []

        # Use the UNIFIED loading method - single source of truth
        timestamps, axis_y_data = self.data_service.data_manager.load_axis_y_data_for_sadeh(
            current_filename,
            current_date,
            hours=48,  # Always 48hr for main data consistency
        )

        if not axis_y_data:
            logger.warning("No axis_y data available for Sadeh algorithm")
            return []

        # Store axis_y data without excessive debug logging

        # Store in plot widget for table access (single cache location)
        if hasattr(self.plot_widget, "main_48h_timestamps"):
            self.plot_widget.main_48h_axis_y_data = axis_y_data
            # CRITICAL: Also store axis_y timestamps for proper alignment
            self.plot_widget.main_48h_axis_y_timestamps = timestamps
            logger.debug("Stored %d axis_y timestamps for Sadeh alignment", len(timestamps))

        return axis_y_data

    def _get_file_completion_count(self, filename: str) -> tuple[int, int]:
        """Get file completion count as (completed/total) - returns tuple (completed_count, total_count)."""
        return self.data_service.get_file_completion_count(filename)

    def set_activity_data_preferences(self, preferred_column: str, choi_column: str) -> None:
        """
        Configure activity data column preferences.

        Args:
            preferred_column: Activity column for general plotting and data loading
            choi_column: Activity column for Choi nonwear detection algorithm

        Note: Sadeh algorithm ALWAYS uses axis_y (vertical) regardless of these settings.

        """
        from sleep_scoring_app.core.constants import ActivityDataPreference

        # Validate inputs - all ActivityDataPreference values are valid
        valid_columns = [
            ActivityDataPreference.AXIS_Y,
            ActivityDataPreference.AXIS_X,
            ActivityDataPreference.AXIS_Z,
            ActivityDataPreference.VECTOR_MAGNITUDE,
        ]
        if preferred_column not in valid_columns or choi_column not in valid_columns:
            msg = f"Column must be one of: {valid_columns}"
            raise ValueError(msg)

        # Update preferences
        self.data_service.set_activity_column_preferences(preferred_column, choi_column)

        # Don't clear axis_y cache when preferences change
        # The axis_y data remains the same regardless of display preference

        # Log the change
        logger.info(f"Activity preferences updated - preferred: {preferred_column}, Choi: {choi_column}")

    def get_activity_data_preferences(self) -> tuple[str, str]:
        """Get current activity data column preferences."""
        return self.data_service.get_activity_column_preferences()

    def _restore_file_selection(self, previous_selection, previous_date_index) -> None:
        """Restore file selection after file list refresh."""
        self.data_service.restore_file_selection(previous_selection, previous_date_index)

    def on_file_selected_from_table(self, file_info: dict) -> None:
        """Handle file selection from table widget."""
        self.nav_manager.on_file_selected_from_table(file_info)

        # Update compatibility checking with new file
        if hasattr(self, "compatibility_helper") and file_info.get("file_path"):
            self.compatibility_helper.on_file_loaded(file_info["file_path"])

    def on_date_dropdown_changed(self, index) -> None:
        """Handle date dropdown selection change."""
        if index >= 0 and index < len(self.available_dates) and index != self.current_date_index:
            # Check for unsaved markers before proceeding
            if not self._check_unsaved_markers_before_navigation():
                # User canceled, reset dropdown to current index
                self.analysis_tab.date_dropdown.blockSignals(True)  # Prevent recursive signal
                self.analysis_tab.date_dropdown.setCurrentIndex(self.current_date_index)
                self.analysis_tab.date_dropdown.blockSignals(False)
                return  # User canceled the navigation

            self.current_date_index = index
            self.load_current_date()
            # Load saved markers for this date
            self.load_saved_markers()
            # Update dropdown color for new selection
            if hasattr(self.data_service, "_update_date_dropdown_current_color"):
                self.data_service._update_date_dropdown_current_color()

    def _check_unsaved_markers_before_navigation(self) -> bool:
        """
        Check if there are unsaved markers and handle user interaction.
        Returns True if navigation should proceed, False if it should be canceled.
        """
        # Check if there are any complete markers placed
        has_complete_markers = (
            hasattr(self.plot_widget, "daily_sleep_markers")
            and self.plot_widget.daily_sleep_markers
            and self.plot_widget.daily_sleep_markers.get_complete_periods()
        )

        # Check if markers are NOT saved
        markers_not_saved = not getattr(self.plot_widget, "markers_saved", False)

        # Check for incomplete sleep marker being placed
        has_incomplete_sleep_marker = (
            hasattr(self.plot_widget, "current_marker_being_placed") and self.plot_widget.current_marker_being_placed is not None
        )

        # Check for incomplete nonwear marker being placed
        has_incomplete_nonwear_marker = (
            hasattr(self.plot_widget, "_current_nonwear_marker_being_placed") and self.plot_widget._current_nonwear_marker_being_placed is not None
        )

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
                self.plot_widget.current_marker_being_placed = None
                self.plot_widget.marker_renderer.redraw_markers()
            if has_incomplete_nonwear_marker:
                self.plot_widget._current_nonwear_marker_being_placed = None
                self.plot_widget.marker_renderer.redraw_nonwear_markers()

        # If there are unsaved complete markers, show warning dialog
        if has_complete_markers and markers_not_saved:
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

        # No unsaved markers or autosave is enabled, use existing auto-save behavior
        self.auto_save_current_markers()
        return True

    def prev_date(self) -> None:
        """Navigate to previous date."""
        # Check for unsaved markers before proceeding
        if not self._check_unsaved_markers_before_navigation():
            return  # User canceled the navigation

        try:
            if self.current_date_index > 0:
                self.current_date_index -= 1
                self.date_dropdown.setCurrentIndex(self.current_date_index)
                self.load_current_date()
                # Load saved markers for this date
                self.load_saved_markers()
                # Update the dropdown color for the new selection
                if hasattr(self, "data_service"):
                    self.data_service._update_date_dropdown_current_color()
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return

    def next_date(self) -> None:
        """Navigate to next date."""
        # Check for unsaved markers before proceeding
        if not self._check_unsaved_markers_before_navigation():
            return  # User canceled the navigation

        try:
            if self.current_date_index < len(self.available_dates) - 1:
                self.current_date_index += 1
                self.date_dropdown.setCurrentIndex(self.current_date_index)
                self.load_current_date()
                # Load saved markers for this date
                self.load_saved_markers()
                # Update the dropdown color for the new selection
                if hasattr(self, "data_service"):
                    self.data_service._update_date_dropdown_current_color()
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return

    def handle_sleep_markers_changed(self, daily_sleep_markers: DailySleepMarkers) -> None:
        """Handle sleep marker changes - combines both info update and table update."""
        self.state_manager.handle_sleep_markers_changed(daily_sleep_markers)

    def handle_nonwear_markers_changed(self, daily_nonwear_markers) -> None:
        """
        Handle nonwear marker changes - save to database immediately.

        Note: Nonwear markers are always saved immediately when placed,
        independent of the ENABLE_AUTOSAVE feature flag (which controls
        sleep marker autosaving behavior).
        """
        try:
            # Get current file and date
            if not self.selected_file or not hasattr(self, "current_date_index"):
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
            logger.debug("Auto-saved nonwear markers for %s on %s", filename, current_date)

        except Exception as e:
            logger.warning("Error auto-saving nonwear markers: %s", e)

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

    def autosave_on_marker_change(self, markers) -> None:
        """
        Autosave when markers are changed (not just when saved).

        Note: This is always enabled to match NWT marker behavior.
        Sleep markers are auto-saved to ensure data is not lost.
        """
        try:
            # Calculate comprehensive sleep metrics
            self.data_manager.extract_enhanced_participant_info(self.selected_file)

            # Get algorithm results and activity data from plot widget
            sadeh_results = getattr(self.plot_widget, "sadeh_results", [])
            choi_results = self.plot_widget.get_choi_results_per_minute() if hasattr(self.plot_widget, "get_choi_results_per_minute") else []
            nwt_sensor_results = (
                self.plot_widget.get_nonwear_sensor_results_per_minute() if hasattr(self.plot_widget, "get_nonwear_sensor_results_per_minute") else []
            )
            # For Sadeh algorithm, we MUST use axis_y data specifically
            axis_y_data = self._get_axis_y_data_for_sadeh()
            x_data = getattr(self.plot_widget, "x_data", [])

            # Calculate comprehensive sleep metrics
            sleep_metrics = self.data_manager.calculate_sleep_metrics_object(
                markers,
                sadeh_results,
                choi_results,
                axis_y_data,
                x_data,
                self.selected_file,
                nwt_sensor_results,
            )

            if sleep_metrics:
                # Add current date and file information
                current_date = self.available_dates[self.current_date_index]
                sleep_metrics.analysis_date = current_date.strftime("%Y-%m-%d")
                sleep_metrics.updated_at = datetime.now().isoformat()
                sleep_metrics.filename = Path(self.selected_file).name if self.selected_file else ""

                # Autosave to database and backup
                self.export_manager.autosave_sleep_metrics([sleep_metrics], AlgorithmType.SADEH_1994_ACTILIFE)
                logger.debug("Auto-saved markers on change for %s", Path(self.selected_file).name if self.selected_file else "unknown")

                # Invalidate marker status cache for this file
                if self.selected_file:
                    self._invalidate_marker_status_cache(Path(self.selected_file).name)

        except Exception as e:
            logger.warning("Error in autosave on marker change: %s", e)

    def update_sleep_info(self, markers) -> None:
        """Update sleep information display with protection against update loops."""
        # Check if we're in the middle of a field-to-marker update to prevent loops
        if getattr(self, "_updating_from_fields", False):
            logger.debug("Skipping field update - currently updating from fields to prevent loop")
            return

        # Don't update fields if user is actively editing them
        if self._is_user_editing_time_fields():
            logger.debug("Skipping field update - user is actively editing")
            # Still update the info label though
            self._update_sleep_info_label_only(markers)
            return

        # Set flag to prevent recursive updates
        self._updating_from_markers = True
        try:
            if len(markers) == 0:
                # Clear total duration label
                if hasattr(self, "total_duration_label"):
                    self.total_duration_label.setText("")
                # Clear manual input fields
                self.onset_time_input.clear()
                self.offset_time_input.clear()
            elif len(markers) == 1:
                start_time = datetime.fromtimestamp(markers[0])
                # Clear duration label when only one marker
                if hasattr(self, "total_duration_label"):
                    self.total_duration_label.setText("")
                # Update onset field
                self.onset_time_input.setText(start_time.strftime("%H:%M"))
                self.offset_time_input.clear()
            else:
                start_time = datetime.fromtimestamp(markers[0])
                end_time = datetime.fromtimestamp(markers[1])
                duration = self.plot_widget.get_sleep_duration()

                # Update total duration label
                if hasattr(self, "total_duration_label"):
                    if duration is not None:
                        self.total_duration_label.setText(f"Total Duration: {duration:.1f} hours")
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
        onset_has_focus = self.onset_time_input.hasFocus() if hasattr(self, "onset_time_input") else False
        offset_has_focus = self.offset_time_input.hasFocus() if hasattr(self, "offset_time_input") else False
        return onset_has_focus or offset_has_focus

    def _update_sleep_info_label_only(self, markers) -> None:
        """Update only the duration label without touching the input fields."""
        if hasattr(self, "total_duration_label"):
            if len(markers) == 0 or len(markers) == 1:
                self.total_duration_label.setText("")
            else:
                duration = self.plot_widget.get_sleep_duration()
                self.total_duration_label.setText(f"Total Duration: {duration:.1f} hours")

    def _apply_synced_field_style(self) -> None:
        """Apply visual style to indicate fields were synced from markers."""
        from PyQt6.QtCore import QTimer

        # PERFORMANCE: Throttle style updates during rapid marker changes (drag)
        if not hasattr(self, "_last_style_update_time"):
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

        if hasattr(self, "onset_time_input"):
            self.onset_time_input.setStyleSheet(synced_style)
        if hasattr(self, "offset_time_input"):
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

        if hasattr(self, "onset_time_input"):
            self.onset_time_input.setStyleSheet(normal_style)
        if hasattr(self, "offset_time_input"):
            self.offset_time_input.setStyleSheet(normal_style)

    def update_marker_tables(self, onset_data, offset_data) -> None:
        """Update the data tables with surrounding marker information."""
        self.table_manager.update_marker_tables(onset_data, offset_data)

    def _connect_table_click_handlers(self) -> None:
        """Connect click handlers for marker tables to enable row click to move marker."""
        try:
            # Connect onset table right-click handler for marker movement
            if hasattr(self, "onset_table") and hasattr(self.onset_table, "table_widget"):
                table = self.onset_table.table_widget
                table.customContextMenuRequested.connect(lambda pos: self._on_onset_table_right_clicked(pos))
                logger.debug("Connected onset table right-click handler")

            # Connect offset table right-click handler for marker movement
            if hasattr(self, "offset_table") and hasattr(self.offset_table, "table_widget"):
                table = self.offset_table.table_widget
                table.customContextMenuRequested.connect(lambda pos: self._on_offset_table_right_clicked(pos))
                logger.debug("Connected offset table right-click handler")

        except Exception as e:
            logger.exception(f"Failed to connect table click handlers: {e}")

    def _on_onset_table_right_clicked(self, pos) -> None:
        """Handle right-click on onset table row to move onset marker."""
        table = self.onset_table.table_widget
        item = table.itemAt(pos)
        if not item:
            return

        row = item.row()
        # Clear selection to prevent highlighting on right-click
        table.clearSelection()
        self._move_marker_from_table_click("onset", row)

    def _on_offset_table_right_clicked(self, pos) -> None:
        """Handle right-click on offset table row to move offset marker."""
        table = self.offset_table.table_widget
        item = table.itemAt(pos)
        if not item:
            return

        row = item.row()
        # Clear selection to prevent highlighting on right-click
        table.clearSelection()
        self._move_marker_from_table_click("offset", row)

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
            if not hasattr(self, "plot_widget") or not self.plot_widget:
                logger.warning("Plot widget not available for marker movement")
                return

            # Check active marker category
            active_category = self.plot_widget.get_active_marker_category()

            if active_category == MarkerCategory.NONWEAR:
                # Move nonwear marker
                # Map onset/offset to start/end for nonwear markers
                nonwear_marker_type = "start" if marker_type == "onset" else "end"

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

                if hasattr(self.plot_widget, "get_selected_marker_period"):
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
            if not hasattr(self.plot_widget, "timestamps") or not self.plot_widget.timestamps:
                return None

            # Parse the time string
            try:
                hour, minute = map(int, time_str.split(":"))
            except ValueError:
                logger.warning(f"Invalid time string format: {time_str}")
                return None

            # Search through timestamps to find matching hour and minute
            for ts in self.plot_widget.timestamps:
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

        Args:
            onset_timestamp: Unix timestamp for sleep onset

        """
        try:
            main_sleep = self.plot_widget.daily_sleep_markers.get_main_sleep()

            if main_sleep:
                # Update existing period's onset
                main_sleep.onset_timestamp = onset_timestamp
                if not main_sleep.offset_timestamp:
                    # Period is incomplete, set it as current marker being placed
                    self.plot_widget.current_marker_being_placed = main_sleep
            else:
                # Create new incomplete period
                from sleep_scoring_app.core.dataclasses import SleepPeriod

                new_period = SleepPeriod(onset_timestamp=onset_timestamp, offset_timestamp=None, marker_index=1)
                self.plot_widget.daily_sleep_markers.period_1 = new_period
                self.plot_widget.current_marker_being_placed = new_period

            self.plot_widget.daily_sleep_markers.update_classifications()
            self.plot_widget.redraw_markers()
            self.plot_widget.sleep_markers_changed.emit(self.plot_widget.daily_sleep_markers)

        except Exception as e:
            logger.error(f"Error creating onset marker from diary: {e}", exc_info=True)

    def _create_offset_marker_from_diary(self, offset_timestamp: float) -> None:
        """
        Create or update only the offset marker.

        Args:
            offset_timestamp: Unix timestamp for sleep offset

        """
        try:
            # Check if there's an incomplete period to complete
            if hasattr(self.plot_widget, "current_marker_being_placed") and self.plot_widget.current_marker_being_placed:
                # Complete the current period
                self.plot_widget.current_marker_being_placed.offset_timestamp = offset_timestamp

                # Find slot for this period if not already assigned
                if not self.plot_widget.current_marker_being_placed.marker_index:
                    if not self.plot_widget.daily_sleep_markers.period_1:
                        self.plot_widget.daily_sleep_markers.period_1 = self.plot_widget.current_marker_being_placed
                        self.plot_widget.current_marker_being_placed.marker_index = 1
                    elif not self.plot_widget.daily_sleep_markers.period_2:
                        self.plot_widget.daily_sleep_markers.period_2 = self.plot_widget.current_marker_being_placed
                        self.plot_widget.current_marker_being_placed.marker_index = 2
                    elif not self.plot_widget.daily_sleep_markers.period_3:
                        self.plot_widget.daily_sleep_markers.period_3 = self.plot_widget.current_marker_being_placed
                        self.plot_widget.current_marker_being_placed.marker_index = 3
                    elif not self.plot_widget.daily_sleep_markers.period_4:
                        self.plot_widget.daily_sleep_markers.period_4 = self.plot_widget.current_marker_being_placed
                        self.plot_widget.current_marker_being_placed.marker_index = 4

                self.plot_widget.current_marker_being_placed = None
            else:
                # Check if main sleep exists and needs offset
                main_sleep = self.plot_widget.daily_sleep_markers.get_main_sleep()
                if main_sleep and not main_sleep.offset_timestamp:
                    main_sleep.offset_timestamp = offset_timestamp
                else:
                    logger.warning("No incomplete period to add offset marker to")
                    return

            self.plot_widget.daily_sleep_markers.update_classifications()
            self.plot_widget.redraw_markers()
            self.plot_widget.sleep_markers_changed.emit(self.plot_widget.daily_sleep_markers)
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
        if hasattr(self, "_pending_markers") and self._pending_markers:
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
        self.time_manager.set_manual_sleep_times()

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
        selected_period = self.plot_widget.get_selected_marker_period() if hasattr(self.plot_widget, "get_selected_marker_period") else None
        if not selected_period:
            return

        if field_type == "onset" and selected_period.onset_timestamp:
            onset_time = datetime.fromtimestamp(selected_period.onset_timestamp)
            self.onset_time_input.setText(onset_time.strftime("%H:%M"))
        elif field_type == "offset" and selected_period.offset_timestamp:
            offset_time = datetime.fromtimestamp(selected_period.offset_timestamp)
            self.offset_time_input.setText(offset_time.strftime("%H:%M"))

    def _update_selected_sleep_period(self, onset_timestamp: float, offset_timestamp: float) -> None:
        """Update the currently selected sleep period with new timestamps."""
        if not hasattr(self.plot_widget, "daily_sleep_markers"):
            return

        # Get the currently selected period
        selected_period = self.plot_widget.get_selected_marker_period() if hasattr(self.plot_widget, "get_selected_marker_period") else None

        if selected_period:
            # Update existing selected period
            selected_period.onset_timestamp = onset_timestamp
            selected_period.offset_timestamp = offset_timestamp
            # Reclassify and redraw
            self.plot_widget.daily_sleep_markers.update_classifications()
            self.plot_widget.redraw_markers()
        else:
            # No selected period, create new one using the traditional method
            self.plot_widget.sleep_markers = [onset_timestamp, offset_timestamp]
            self.plot_widget.redraw_markers()

    def _update_selected_sleep_period_onset(self, onset_timestamp: float) -> None:
        """Update or create sleep period with just onset."""
        if not hasattr(self.plot_widget, "add_sleep_marker"):
            # Fallback to old method
            self.plot_widget.sleep_markers = [onset_timestamp]
            self.plot_widget.redraw_markers()
        else:
            # Use new marker system
            self.plot_widget.add_sleep_marker(onset_timestamp)

    def save_current_markers(self) -> None:
        """Save current markers permanently."""
        self.state_manager.save_current_markers()

    def clear_current_markers(self) -> None:
        """Clear current markers from both display and database (including both autosave and permanent markers)."""
        self.state_manager.clear_current_markers()

    def clear_plot_and_ui_state(self) -> None:
        """Clear plot and UI state when switching filters."""
        try:
            # Clear the plot visualization
            if hasattr(self, "plot_widget") and self.plot_widget:
                self.plot_widget.clear_plot()
                self.plot_widget.clear_sleep_markers()

            # Reset UI state
            self.selected_file = None
            self.available_dates = []
            self.current_date_index = 0

            # Clear status labels
            if hasattr(self, "total_duration_label"):
                self.total_duration_label.setText("")

            # Reset button states
            if hasattr(self, "save_markers_btn"):
                self.save_markers_btn.setText(ButtonText.SAVE_MARKERS)
                self.save_markers_btn.setStyleSheet(ButtonStyle.SAVE_MARKERS)

            # Clear date dropdown
            if hasattr(self, "date_dropdown"):
                self.date_dropdown.clear()
                self.date_dropdown.setEnabled(False)

            # Disable navigation buttons
            if hasattr(self, "prev_date_btn"):
                self.prev_date_btn.setEnabled(False)
            if hasattr(self, "next_date_btn"):
                self.next_date_btn.setEnabled(False)

            logger.debug("Cleared plot and UI state for filter change")

        except Exception as e:
            logger.warning("Error clearing plot and UI state: %s", e)

    def mark_no_sleep_period(self) -> None:
        """Mark current date as having no sleep period."""
        self.state_manager.mark_no_sleep_period()

    def toggle_adjacent_day_markers(self, show: bool) -> None:
        """Toggle display of adjacent day markers from adjacent days."""
        logger.info(f"Toggling adjacent day markers: {show}")

        if not hasattr(self, "plot_widget") or not self.plot_widget:
            logger.warning("Plot widget not available for adjacent day markers")
            return

        # Store the state
        self.show_adjacent_day_markers = show

        if show:
            # Load and display adjacent day markers
            self._load_and_display_adjacent_day_markers()
        else:
            # Clear adjacent day markers
            self._clear_adjacent_day_markers()

    def _load_and_display_adjacent_day_markers(self) -> None:
        """Load markers from adjacent days and display as adjacent day markers."""
        if not self.available_dates or self.current_date_index is None:
            logger.info("Adjacent day markers: No available dates or current date index")
            return

        current_date = self.available_dates[self.current_date_index]
        adjacent_day_markers = []

        logger.info(f"Loading adjacent day markers for current date: {current_date}, index: {self.current_date_index}")
        logger.info(f"Total available dates: {len(self.available_dates)}")

        # Load markers from day-1 (if exists)
        if self.current_date_index > 0:
            prev_date = self.available_dates[self.current_date_index - 1]
            logger.info(f"Loading markers from previous day: {prev_date}")
            prev_markers = self._load_markers_for_date(prev_date)
            logger.info(f"Found {len(prev_markers)} markers for previous day")
            if prev_markers:
                for marker in prev_markers:
                    marker["adjacent_date"] = prev_date.strftime("%Y-%m-%d")
                    marker["is_adjacent_day"] = True
                adjacent_day_markers.extend(prev_markers)

        # Load markers from day+1 (if exists)
        if self.current_date_index < len(self.available_dates) - 1:
            next_date = self.available_dates[self.current_date_index + 1]
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
            if hasattr(self.plot_widget, "display_adjacent_day_markers"):
                logger.info("Displaying adjacent day markers on plot")
                self.plot_widget.display_adjacent_day_markers(adjacent_day_markers)
            else:
                logger.error("Plot widget does not have display_adjacent_day_markers method")
        else:
            logger.info("No adjacent day markers found to display")

    def _load_markers_for_date(self, date) -> None:
        """Load sleep markers for a specific date."""
        try:
            filename = Path(self.selected_file).name
            date_str = date.strftime("%Y-%m-%d")
            logger.info(f"Loading markers for file: {filename}, date: {date_str}")

            # First, let's check what dates are actually in the database
            try:
                with self.db_manager._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT DISTINCT analysis_date FROM sleep_markers_extended WHERE filename = ? ORDER BY analysis_date", (filename,)
                    )
                    available_dates = [row[0] for row in cursor.fetchall()]
                    logger.info(f"Available dates in database for {filename}: {available_dates}")
            except Exception as e:
                logger.exception(f"Error checking available dates: {e}")

            # Use the same method as regular marker loading (sleep_metrics table)
            saved_data = self.export_manager.db_manager.load_sleep_metrics(filename=filename, analysis_date=date_str)
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
        if hasattr(self.plot_widget, "clear_adjacent_day_markers"):
            self.plot_widget.clear_adjacent_day_markers()

    def load_saved_markers(self) -> None:
        """Load saved markers for current file and date."""
        self.state_manager.load_saved_markers()
        # Also load nonwear markers
        self.load_saved_nonwear_markers()

    def load_saved_nonwear_markers(self) -> None:
        """Load saved nonwear markers for current file and date."""
        try:
            if not self.selected_file or not hasattr(self, "current_date_index"):
                return

            current_date = self.available_dates[self.current_date_index]
            filename = Path(self.selected_file).name

            # Load nonwear markers from database
            daily_nonwear_markers = self.db_manager.load_manual_nonwear_markers(
                filename=filename,
                sleep_date=current_date,
            )

            # Load into plot widget
            if hasattr(self.plot_widget, "load_daily_nonwear_markers"):
                self.plot_widget.load_daily_nonwear_markers(daily_nonwear_markers, markers_saved=True)
                logger.debug("Loaded nonwear markers for %s on %s", filename, current_date)

        except Exception as e:
            logger.warning("Error loading nonwear markers: %s", e)

    def load_all_saved_markers_on_startup(self) -> None:
        """Load all saved markers from database on application startup."""
        try:
            all_sleep_metrics = self._get_cached_metrics()
            logger.debug("Loaded %s saved records on startup from database", len(all_sleep_metrics))

            # Log summary (extract filenames directly without expensive to_export_dict() conversion)
            if all_sleep_metrics:
                files_with_data = {metrics.filename for metrics in all_sleep_metrics}
                logger.debug("Found data for %s files: %s", len(files_with_data), list(files_with_data))
        except Exception as e:
            logger.warning("Error loading saved data on startup: %s", e)

    def _load_diary_data_for_file(self) -> None:
        """Load diary data for the currently selected file."""
        self.diary_manager.load_diary_data_for_file()

    def auto_save_current_markers(self) -> None:
        """Auto-save current markers before changing date/file."""
        if hasattr(self.plot_widget, "sleep_markers") and self.plot_widget.sleep_markers and self.selected_file:
            # Calculate comprehensive sleep metrics with algorithm results
            self.data_manager.extract_enhanced_participant_info(self.selected_file)

            # Get algorithm results and activity data from plot widget
            sadeh_results = getattr(self.plot_widget, "sadeh_results", [])
            choi_results = self.plot_widget.get_choi_results_per_minute() if hasattr(self.plot_widget, "get_choi_results_per_minute") else []
            nwt_sensor_results = (
                self.plot_widget.get_nonwear_sensor_results_per_minute() if hasattr(self.plot_widget, "get_nonwear_sensor_results_per_minute") else []
            )
            # For Sadeh algorithm, we MUST use axis_y data specifically
            axis_y_data = self._get_axis_y_data_for_sadeh()
            x_data = getattr(self.plot_widget, "x_data", [])

            # Calculate comprehensive sleep metrics using the new object method
            sleep_metrics = self.data_manager.calculate_sleep_metrics_object(
                self.plot_widget.sleep_markers,
                sadeh_results,
                choi_results,
                axis_y_data,
                x_data,
                self.selected_file,
                nwt_sensor_results,
            )

            if sleep_metrics:
                # Update metadata
                current_date = self.available_dates[self.current_date_index] if self.available_dates else datetime.now()
                sleep_metrics.analysis_date = current_date.strftime("%Y-%m-%d")
                sleep_metrics.updated_at = datetime.now().isoformat()

                # Use autosave instead of regular save (if enabled)
                if FeatureFlags.ENABLE_AUTOSAVE:
                    self.export_manager.autosave_sleep_metrics([sleep_metrics], AlgorithmType.SADEH_1994_ACTILIFE)

                    # Invalidate marker status cache for this file after auto-save
                    if self.selected_file:
                        self._invalidate_marker_status_cache(Path(self.selected_file).name)

    def set_ui_enabled(self, enabled) -> None:
        """Enable or disable UI controls based on folder selection status."""
        # File selection and navigation
        self.file_selector.setEnabled(enabled)
        self.prev_date_btn.setEnabled(enabled and self.current_date_index > 0)
        self.next_date_btn.setEnabled(enabled and self.current_date_index < len(self.available_dates) - 1)

        # View mode buttons
        self.view_24h_btn.setEnabled(enabled)
        self.view_48h_btn.setEnabled(enabled)

        # Manual time entry
        if hasattr(self, "onset_time_input"):
            self.onset_time_input.setEnabled(enabled)
        if hasattr(self, "offset_time_input"):
            self.offset_time_input.setEnabled(enabled)

        # Action buttons
        if hasattr(self, "save_markers_btn"):
            self.save_markers_btn.setEnabled(enabled)
        if hasattr(self, "no_sleep_btn"):
            self.no_sleep_btn.setEnabled(enabled)
        if hasattr(self, "clear_markers_btn"):
            self.clear_markers_btn.setEnabled(enabled)
        if hasattr(self, "export_btn"):
            self.export_btn.setEnabled(enabled)

        # Plot widget
        self.plot_widget.setEnabled(enabled)

        # Update folder info
        if enabled:
            self.update_folder_info_label()

    def update_folder_info_label(self) -> None:
        """Update the file selection label with current file count."""
        file_count = len(self.data_service.available_files) if hasattr(self.data_service, "available_files") else 0

        # Update the file selection label instead of folder info label
        if hasattr(self, "file_selection_label"):
            if self.data_service.get_database_mode():
                self.file_selection_label.setText(f"File Selection ({file_count} files from database)")
            elif hasattr(self.data_service, "get_data_folder") and self.data_service.get_data_folder():
                folder_name = Path(self.data_service.get_data_folder()).name
                self.file_selection_label.setText(f"File Selection ({file_count} files from {folder_name})")
            else:
                self.file_selection_label.setText(f"File Selection ({file_count} files)")

        # Keep folder_info_label empty for compatibility
        if hasattr(self, "folder_info_label"):
            self.folder_info_label.setText("")

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
        """Update the status bar with current information."""
        if message:
            self.status_bar.showMessage(message, 5000)  # Show for 5 seconds

        # Update data source label - all data is now always from database
        self.data_source_label.setText("Activity: Database")

        # Update file count
        if hasattr(self, "file_selector") and hasattr(self.file_selector, "table"):
            row_count = self.file_selector.table.rowCount()
            self.file_count_label.setText(f"Files: {row_count}")
        else:
            self.file_count_label.setText("Files: 0")

    def update_data_source_status(self) -> None:
        """Update the data source status label."""
        try:
            # All data is now always stored in database
            stats = self.db_manager.get_database_stats()
            file_count = stats.get("unique_files", 0)
            record_count = stats.get("total_records", 0)

            status_text = f"{file_count} imported files, {record_count} total records"
            style = "color: #27ae60; font-weight: bold;"

            # Update the activity status label if it exists
            if hasattr(self, "data_settings_tab") and hasattr(self.data_settings_tab, "activity_status_label"):
                self.data_settings_tab.activity_status_label.setText(status_text)
                self.data_settings_tab.activity_status_label.setStyleSheet(style)

        except Exception as e:
            error_text = "Status unavailable"
            if hasattr(self, "data_settings_tab") and hasattr(self.data_settings_tab, "activity_status_label"):
                self.data_settings_tab.activity_status_label.setText(error_text)
                self.data_settings_tab.activity_status_label.setStyleSheet("color: #e74c3c;")
            logger.warning("Error updating data source status: %s", e)

    def browse_data_folder(self) -> None:
        """Browse for CSV data folder (does not automatically load files)."""
        # Start from last used folder or home directory
        start_dir = self.config_manager.config.data_folder or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Select Data Folder", start_dir)

        if directory:
            # Save to config but don't automatically load files
            self.config_manager.update_data_folder(directory)

    def browse_activity_files(self) -> None:
        """Browse for activity data files (multi-select)."""
        # Start from last used activity directory or home directory
        start_dir = self.config_manager.config.import_activity_directory or str(Path.home())

        # Build file filter based on current data paradigm
        file_filter = self._get_paradigm_file_filter()

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Activity Data Files",
            start_dir,
            file_filter,
        )

        if files and hasattr(self, "data_settings_tab") and hasattr(self.data_settings_tab, "activity_import_files_label"):
            # Store selected files
            self._selected_activity_files = [Path(f) for f in files]
            # Display file count
            file_count = len(files)
            display_text = f"{file_count} file(s) selected"
            self.data_settings_tab._set_path_label_text(self.data_settings_tab.activity_import_files_label, display_text)
            self.data_settings_tab.activity_import_btn.setEnabled(True)
            # Save directory of first file to config for next browse
            self.config_manager.config.import_activity_directory = str(Path(files[0]).parent)
            self.config_manager.save_config()

    def _get_paradigm_file_filter(self) -> str:
        """
        Build file filter string based on current data paradigm.

        Returns:
            File filter string for QFileDialog based on paradigm setting.
            - EPOCH_BASED: CSV and Excel files only
            - RAW_ACCELEROMETER: GT3X, CSV, and Excel files

        """
        try:
            paradigm_value = self.config_manager.config.data_paradigm
            paradigm = StudyDataParadigm(paradigm_value)
        except (ValueError, AttributeError):
            paradigm = StudyDataParadigm.get_default()

        if paradigm == StudyDataParadigm.RAW_ACCELEROMETER:
            # Raw accelerometer mode - GT3X files primary, CSV/Excel secondary
            return "Supported Files (*.gt3x *.csv *.xlsx *.xls);;GT3X Files (*.gt3x);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        # Default: EPOCH_BASED - CSV and Excel files only
        return "Epoch Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"

    def browse_nonwear_files(self) -> None:
        """Browse for nonwear sensor files (multi-select)."""
        # Start from last used nonwear directory or home directory
        start_dir = self.config_manager.config.import_nonwear_directory or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Nonwear Sensor Files",
            start_dir,
            "CSV Files (*.csv);;All Files (*)",
        )

        if files and hasattr(self, "data_settings_tab") and hasattr(self.data_settings_tab, "nwt_import_files_label"):
            # Store selected files
            self._selected_nonwear_files = [Path(f) for f in files]
            # Display file count
            file_count = len(files)
            display_text = f"{file_count} file(s) selected"
            self.data_settings_tab._set_path_label_text(self.data_settings_tab.nwt_import_files_label, display_text)
            self.data_settings_tab.nwt_import_btn.setEnabled(True)
            # Save directory of first file to config for next browse
            self.config_manager.config.import_nonwear_directory = str(Path(files[0]).parent)
            self.config_manager.save_config()

    def _validate_files_against_paradigm(self, files: list[Path]) -> tuple[list[Path], list[Path]]:
        """
        Validate selected files against the current data paradigm.

        Args:
            files: List of file paths to validate

        Returns:
            Tuple of (compatible_files, incompatible_files)

        """
        try:
            paradigm_value = self.config_manager.config.data_paradigm
            paradigm = StudyDataParadigm(paradigm_value)
        except (ValueError, AttributeError):
            paradigm = StudyDataParadigm.get_default()

        compatible_extensions = paradigm.get_compatible_file_extensions()
        compatible_files = []
        incompatible_files = []

        for file_path in files:
            ext = file_path.suffix.lower()
            if ext in compatible_extensions:
                compatible_files.append(file_path)
            else:
                incompatible_files.append(file_path)

        return compatible_files, incompatible_files

    def start_activity_import(self) -> None:
        """Start the activity data import process."""
        if not hasattr(self, "data_settings_tab"):
            return

        # Check for selected files
        if not hasattr(self, "_selected_activity_files") or not self._selected_activity_files:
            QMessageBox.warning(
                self,
                "No Files Selected",
                "Please select activity data files to import",
            )
            return

        # Validate files against current paradigm
        compatible_files, incompatible_files = self._validate_files_against_paradigm(self._selected_activity_files)

        if incompatible_files:
            # Get current paradigm for message
            try:
                paradigm_value = self.config_manager.config.data_paradigm
                paradigm = StudyDataParadigm(paradigm_value)
            except (ValueError, AttributeError):
                paradigm = StudyDataParadigm.get_default()

            paradigm_name = paradigm.get_display_name()
            compatible_exts = ", ".join(paradigm.get_compatible_file_extensions())
            incompatible_names = "\n".join(f"  - {f.name}" for f in incompatible_files[:10])
            if len(incompatible_files) > 10:
                incompatible_names += f"\n  ... and {len(incompatible_files) - 10} more"

            if compatible_files:
                # Some files are compatible - ask user what to do
                msg = (
                    f"The following files are not compatible with the current paradigm "
                    f"({paradigm_name}):\n\n{incompatible_names}\n\n"
                    f"Compatible file types: {compatible_exts}\n\n"
                    f"Do you want to import only the {len(compatible_files)} compatible file(s)?"
                )
                reply = QMessageBox.question(
                    self,
                    "Incompatible Files",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return
                # Use only compatible files
                self._selected_activity_files = compatible_files
            else:
                # No compatible files at all
                QMessageBox.warning(
                    self,
                    "Incompatible Files",
                    f"None of the selected files are compatible with the current paradigm "
                    f"({paradigm_name}).\n\n"
                    f"Compatible file types: {compatible_exts}\n\n"
                    f"Please select different files or change the data paradigm in Study Settings.",
                )
                return

        tab = self.data_settings_tab

        tab.activity_import_btn.setEnabled(False)
        tab.activity_import_btn.setText("Import in Progress...")
        tab.activity_progress_label.setText("Starting import...")
        tab.activity_progress_label.setVisible(True)
        tab.activity_progress_bar.setVisible(True)
        tab.activity_progress_bar.setValue(0)

        # Build custom columns dict if using Generic CSV
        custom_columns = None
        if self.config_manager.config.device_preset == "generic_csv":
            config = self.config_manager.config
            if config.custom_date_column:  # Only use custom columns if configured
                custom_columns = {
                    "date": config.custom_date_column,
                    "time": config.custom_time_column if not config.datetime_combined else None,
                    "activity": config.custom_activity_column or config.custom_axis_y_column,
                    "datetime_combined": config.datetime_combined,
                    # Axis columns for algorithm use (Y=vertical, X=lateral, Z=forward)
                    "axis_y": config.custom_axis_y_column,
                    "axis_x": config.custom_axis_x_column,
                    "axis_z": config.custom_axis_z_column,
                    "vector_magnitude": config.custom_vector_magnitude_column,
                }

        # Start worker thread with selected files
        self.import_worker = ImportWorker(
            tab.import_service,
            self._selected_activity_files,
            tab.skip_rows_spin.value(),
            False,  # force_reimport
            include_nonwear=False,
            custom_columns=custom_columns,
        )

        # Connect worker signals with thread-safe queued connections
        self.import_worker.progress_updated.connect(self.update_activity_progress, Qt.ConnectionType.QueuedConnection)
        self.import_worker.nonwear_progress_updated.connect(self.update_nonwear_progress, Qt.ConnectionType.QueuedConnection)
        self.import_worker.import_completed.connect(self.activity_import_finished, Qt.ConnectionType.QueuedConnection)

        # Start import
        self.import_worker.start()

    def start_nonwear_import(self) -> None:
        """Start the nonwear sensor data import process."""
        if not hasattr(self, "data_settings_tab"):
            return

        # Check for selected files
        if not hasattr(self, "_selected_nonwear_files") or not self._selected_nonwear_files:
            QMessageBox.warning(
                self,
                "No Files Selected",
                "Please select nonwear sensor files to import",
            )
            return

        tab = self.data_settings_tab
        tab.nwt_import_btn.setEnabled(False)
        tab.nwt_import_btn.setText("Import in Progress...")

        # Show progress components
        if hasattr(tab, "nwt_progress_label") and hasattr(tab, "nwt_progress_bar"):
            tab.nwt_progress_label.setText("Starting NWT import...")
            tab.nwt_progress_label.setVisible(True)
            tab.nwt_progress_bar.setVisible(True)
            tab.nwt_progress_bar.setValue(0)

        try:
            # Import NonwearImportWorker
            from sleep_scoring_app.services.nonwear_import_worker import NonwearImportWorker

            # Create and configure the nonwear import worker with selected files
            self.nonwear_import_worker = NonwearImportWorker(tab.import_service, self._selected_nonwear_files)

            # Connect signals for progress updates
            self.nonwear_import_worker.progress_updated.connect(self.update_nonwear_progress, Qt.ConnectionType.QueuedConnection)
            self.nonwear_import_worker.import_completed.connect(self.nonwear_import_finished, Qt.ConnectionType.QueuedConnection)

            # Start the async import
            self.nonwear_import_worker.start()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to start nonwear import: {e}")
            tab.nwt_import_btn.setEnabled(True)
            tab.nwt_import_btn.setText("Import NWT Data to Database")

    def update_activity_progress(self, progress) -> None:
        """Update activity import progress."""
        if hasattr(self, "data_settings_tab"):
            tab = self.data_settings_tab
            tab.activity_progress_bar.setValue(int(progress.file_progress_percent))
            tab.activity_progress_label.setText(f"Files: {progress.processed_files}/{progress.total_files}")

    def update_nonwear_progress(self, progress) -> None:
        """Update nonwear import progress."""
        if hasattr(self, "data_settings_tab"):
            tab = self.data_settings_tab
            if hasattr(tab, "nwt_progress_bar") and hasattr(tab, "nwt_progress_label"):
                tab.nwt_progress_bar.setValue(int(progress.nonwear_progress_percent))
                tab.nwt_progress_label.setText(f"NWT Files: {progress.processed_nonwear_files}/{progress.total_nonwear_files}")

    def activity_import_finished(self, progress) -> None:
        """Handle activity import completion."""
        if hasattr(self, "data_settings_tab"):
            tab = self.data_settings_tab
            tab.activity_import_btn.setEnabled(False)
            tab.activity_import_btn.setText("Import")
            tab.activity_progress_label.setText("Import completed")
            # Clear the file selection label and stored files
            tab._set_path_label_text(tab.activity_import_files_label, "No files selected")
            self.pending_activity_import_files = []
            # Hide progress components after a delay
            QTimer.singleShot(3000, lambda: self._hide_progress_components())

            if progress.errors:
                QMessageBox.warning(
                    self,
                    "Import Completed with Errors",
                    f"Import completed with {len(progress.errors)} errors.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Successfully imported {len(progress.imported_files)} files.",
                )

            # Invalidate marker status cache since new files might have markers
            self._invalidate_marker_status_cache()

            # Refresh file list
            self.load_available_files(preserve_selection=False)

            # Auto-refresh imported files table
            if hasattr(tab, "file_management_widget"):
                tab.file_management_widget.refresh_files()

    def nonwear_import_finished(self, progress) -> None:
        """Handle nonwear import completion."""
        if hasattr(self, "data_settings_tab"):
            tab = self.data_settings_tab
            tab.nwt_import_btn.setEnabled(True)
            tab.nwt_import_btn.setText("Import NWT Data to Database")

            # Update and hide progress components
            if hasattr(tab, "nwt_progress_label") and hasattr(tab, "nwt_progress_bar"):
                tab.nwt_progress_label.setText("Import completed")
                # Hide after a delay
                QTimer.singleShot(3000, lambda: self._hide_nonwear_progress_components())

            # Show results
            if progress.errors:
                QMessageBox.warning(
                    self,
                    "Import Completed with Errors",
                    f"Nonwear sensor data import completed with {len(progress.errors)} errors.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"Nonwear sensor data imported successfully. Imported {len(progress.imported_nonwear_files)} files.",
                )

            # Clear nonwear cache and refresh plot to show newly imported data
            if hasattr(self, "data_service") and hasattr(self.data_service, "nonwear_data_factory"):
                self.data_service.nonwear_data_factory.clear_cache()
            if hasattr(self, "selected_file") and self.selected_file:
                self.load_nonwear_data_for_plot()

    def load_data_folder(self) -> None:
        """Load data folder and enable UI."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select folder containing CSV data files",
            "",  # Start in current directory
            QFileDialog.Option.ShowDirsOnly,
        )

        if folder_path:
            # Set the data folder and load files
            self.data_service.set_data_folder(folder_path)

            # Only load CSV files if we're in CSV mode
            if not self.data_service.get_database_mode():
                self.load_available_files(preserve_selection=False)
            else:
                # In database mode, load files from database with completion counts
                self.load_available_files(preserve_selection=False)

            self.set_ui_enabled(True)

            # Save to config
            self.config_manager.update_data_folder(folder_path)

            # Show feedback to user
            file_count = len(self.available_files)
            if file_count > 0:
                QMessageBox.information(
                    self,
                    "Folder Loaded",
                    f"Successfully loaded {file_count} CSV file{'s' if file_count != 1 else ''} from:\n\n{folder_path}\n\n"
                    "Files are now available in the file selector dropdown.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "No Files Found",
                    f"No CSV files found in:\n\n{folder_path}\n\nPlease select a folder containing CSV data files.",
                )

    def clear_all_markers(self) -> None:
        """Clear all sleep markers and metrics from database (preserves imported data)."""
        self.state_manager.clear_all_markers()

    def save_export_options(self) -> None:
        """Save export options to config."""
        if hasattr(self, "export_tab"):
            tab = self.export_tab
            self.config_manager.update_export_options(
                tab.include_headers_checkbox.isChecked(),
                tab.include_metadata_checkbox.isChecked(),
            )
            # Save nonwear separate file option
            if hasattr(tab, "separate_nonwear_file_checkbox"):
                self.config_manager.config.export_nonwear_separate = tab.separate_nonwear_file_checkbox.isChecked()
                self.config_manager.save_config()

    def browse_export_output_directory(self) -> None:
        """Handle directory selection for export."""
        # Start from saved export directory, then current export path, then current working directory
        start_dir = self.config_manager.config.export_directory or self.export_output_path or str(Path.cwd())
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if directory:
            self.export_output_path = directory
            if hasattr(self, "export_tab") and hasattr(self.export_tab, "export_output_label"):
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
            export_nonwear_separate = hasattr(self, "separate_nonwear_file_checkbox") and self.separate_nonwear_file_checkbox.isChecked()

            # Perform the export directly with data
            success = self.export_manager.perform_direct_export(
                all_sleep_metrics,
                self.export_grouping_group.checkedId(),
                self.export_output_path,
                self.selected_export_columns,
                self.include_headers_checkbox.isChecked(),
                self.include_metadata_checkbox.isChecked(),
                export_nonwear_separate=export_nonwear_separate,
            )

            if success:
                data_source = "database" if self.data_manager.use_database else "CSV markers"
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported {len(all_sleep_metrics)} records from {data_source} to:\n{self.export_output_path}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Export operation failed. Check the console for details.",
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
            if hasattr(self, "data_settings_tab"):
                tab = self.data_settings_tab
                if hasattr(tab, "activity_progress_label"):
                    tab.activity_progress_label.setVisible(False)
                if hasattr(tab, "activity_progress_bar"):
                    tab.activity_progress_bar.setVisible(False)
        except Exception as e:
            logger.warning("Error hiding activity progress components: %s", e)

    def _hide_nonwear_progress_components(self) -> None:
        """Hide nonwear progress components after import completion."""
        try:
            if hasattr(self, "data_settings_tab"):
                tab = self.data_settings_tab
                if hasattr(tab, "nwt_progress_label"):
                    tab.nwt_progress_label.setVisible(False)
                if hasattr(tab, "nwt_progress_bar"):
                    tab.nwt_progress_bar.setVisible(False)
        except Exception as e:
            logger.warning("Error hiding nonwear progress components: %s", e)

    def _cleanup_resources(self) -> None:
        """Clean up resources before shutdown."""
        try:
            # Stop and cleanup timers
            if hasattr(self, "_table_update_timer") and self._table_update_timer:
                self._table_update_timer.stop()
                self._table_update_timer.deleteLater()
                self._table_update_timer = None

            # Clean up analysis tab
            if hasattr(self, "analysis_tab") and self.analysis_tab:
                if hasattr(self.analysis_tab, "cleanup_tab"):
                    self.analysis_tab.cleanup_tab()

            # Clean up plot widget (if not already cleaned by analysis tab)
            if hasattr(self, "plot_widget") and self.plot_widget:
                if hasattr(self.plot_widget, "cleanup_widget"):
                    self.plot_widget.cleanup_widget()

            # Clear data caches
            self.current_date_48h_cache.clear()
            self.main_48h_data = None
            if hasattr(self.plot_widget, "main_48h_axis_y_data"):
                self.plot_widget.main_48h_axis_y_data = None

            # Clear available data
            self.available_files.clear()
            self.available_dates.clear()

            # Force garbage collection
            gc.collect()

            logger.debug("Main window resources cleaned up")
        except Exception as e:
            logger.warning("Error cleaning up main window resources: %s", e)

    def closeEvent(self, event) -> None:  # Qt naming convention
        """Handle window close event with proper cleanup."""
        try:
            # Auto-save current markers
            self.auto_save_current_markers()

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
