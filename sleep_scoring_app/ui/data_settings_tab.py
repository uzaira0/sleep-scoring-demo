#!/usr/bin/env python3
"""
Data Settings Tab Component
Handles data source configuration and import functionality.

All data is stored in the database. Import operations are one-time actions
that load data from files into the database. Settings are global and apply
to all import operations.
"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.core.constants import ButtonText, DataSourceType, DevicePreset, InfoMessage, StudyDataParadigm

if TYPE_CHECKING:
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

logger = logging.getLogger(__name__)


class ColumnMappingDialog(QDialog):
    """Dialog for configuring custom column mappings for Generic CSV format."""

    def __init__(
        self,
        parent: QWidget | None = None,
        config_manager: object | None = None,
        sample_file: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.sample_file = sample_file
        self.detected_columns: list[str] = []

        self.setWindowTitle("Configure Column Mappings")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self._setup_ui()
        self._load_current_config()

        if sample_file:
            self._detect_columns_from_file()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "<b>Custom Column Mapping</b><br><br>"
            "Configure which columns contain your date, time, and activity data. "
            "Select a sample file to auto-detect available columns.<br>"
            "<span style='color: #666;'>Note: Sadeh algorithm requires Y-Axis (vertical). "
            "Choi algorithm can use Vector Magnitude or any axis.</span>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # File selection for column detection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Sample File:"))
        self.file_label = QLabel(self.sample_file.name if self.sample_file else "No file selected")
        self.file_label.setStyleSheet("color: #666;")
        file_layout.addWidget(self.file_label, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_sample_file)
        file_layout.addWidget(browse_btn)
        detect_btn = QPushButton("Detect Columns")
        detect_btn.clicked.connect(self._detect_columns_from_file)
        file_layout.addWidget(detect_btn)
        layout.addLayout(file_layout)

        # Column mapping section - Datetime
        datetime_group = QGroupBox("Datetime Columns")
        datetime_layout = QGridLayout(datetime_group)

        # Datetime format selection
        datetime_layout.addWidget(QLabel("Format:"), 0, 0)
        self.datetime_combined_check = QCheckBox("Combined datetime in single column")
        self.datetime_combined_check.stateChanged.connect(self._on_datetime_format_changed)
        datetime_layout.addWidget(self.datetime_combined_check, 0, 1, 1, 2)

        # Date column
        datetime_layout.addWidget(QLabel("Date Column:"), 1, 0)
        self.date_column_combo = QComboBox()
        self.date_column_combo.setEditable(True)
        self.date_column_combo.setMinimumWidth(200)
        datetime_layout.addWidget(self.date_column_combo, 1, 1, 1, 2)

        # Time column
        self.time_label = QLabel("Time Column:")
        datetime_layout.addWidget(self.time_label, 2, 0)
        self.time_column_combo = QComboBox()
        self.time_column_combo.setEditable(True)
        self.time_column_combo.setMinimumWidth(200)
        datetime_layout.addWidget(self.time_column_combo, 2, 1, 1, 2)

        layout.addWidget(datetime_group)

        # Axis columns section
        axis_group = QGroupBox("Activity/Axis Columns")
        axis_layout = QGridLayout(axis_group)

        # Helper to create optional combo with "(not available)" option
        def create_axis_combo() -> QComboBox:
            combo = QComboBox()
            combo.setEditable(True)
            combo.setMinimumWidth(180)
            combo.addItem("(not available)", "")
            return combo

        # Y-Axis (vertical - required for Sadeh, ActiGraph Axis1)
        axis_y_label = QLabel("Y-Axis (Vertical):")
        axis_y_label.setToolTip("Required for Sadeh algorithm. ActiGraph: Axis1")
        axis_layout.addWidget(axis_y_label, 0, 0)
        self.axis_y_combo = create_axis_combo()
        axis_layout.addWidget(self.axis_y_combo, 0, 1)
        axis_layout.addWidget(QLabel("<span style='color: #e67e22;'>*Required for Sadeh</span>"), 0, 2)

        # X-Axis (lateral - ActiGraph Axis2)
        axis_layout.addWidget(QLabel("X-Axis (Lateral):"), 1, 0)
        self.axis_x_combo = create_axis_combo()
        axis_layout.addWidget(self.axis_x_combo, 1, 1)
        axis_layout.addWidget(QLabel("<span style='color: #999;'>(optional)</span>"), 1, 2)

        # Z-Axis (forward - ActiGraph Axis3)
        axis_layout.addWidget(QLabel("Z-Axis (Forward):"), 2, 0)
        self.axis_z_combo = create_axis_combo()
        axis_layout.addWidget(self.axis_z_combo, 2, 1)
        axis_layout.addWidget(QLabel("<span style='color: #999;'>(optional)</span>"), 2, 2)

        # Vector Magnitude
        vm_label = QLabel("Vector Magnitude:")
        vm_label.setToolTip("Recommended for Choi algorithm")
        axis_layout.addWidget(vm_label, 3, 0)
        self.vector_magnitude_combo = create_axis_combo()
        axis_layout.addWidget(self.vector_magnitude_combo, 3, 1)
        axis_layout.addWidget(QLabel("<span style='color: #27ae60;'>*Recommended for Choi</span>"), 3, 2)

        layout.addWidget(axis_group)

        # Preview section
        preview_group = QGroupBox("Data Preview (first 5 rows)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(120)
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)

        # Detected columns info
        self.columns_info_label = QLabel("")
        self.columns_info_label.setStyleSheet("color: #666; font-style: italic;")
        self.columns_info_label.setWordWrap(True)
        layout.addWidget(self.columns_info_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self._save_and_accept)
        layout.addWidget(button_box)

    def _load_current_config(self) -> None:
        """Load current configuration into UI."""
        if not self.config_manager:
            return

        config = self.config_manager.config

        # Set datetime combined checkbox
        self.datetime_combined_check.setChecked(config.datetime_combined)
        self._on_datetime_format_changed()

        # Set datetime column values if they exist
        if config.custom_date_column:
            self.date_column_combo.setCurrentText(config.custom_date_column)
        if config.custom_time_column:
            self.time_column_combo.setCurrentText(config.custom_time_column)

        # Set axis column values if they exist
        if config.custom_axis_y_column:
            self.axis_y_combo.setCurrentText(config.custom_axis_y_column)
        if config.custom_axis_x_column:
            self.axis_x_combo.setCurrentText(config.custom_axis_x_column)
        if config.custom_axis_z_column:
            self.axis_z_combo.setCurrentText(config.custom_axis_z_column)
        if config.custom_vector_magnitude_column:
            self.vector_magnitude_combo.setCurrentText(config.custom_vector_magnitude_column)

    def _on_datetime_format_changed(self) -> None:
        """Handle datetime format checkbox change."""
        is_combined = self.datetime_combined_check.isChecked()
        self.time_label.setVisible(not is_combined)
        self.time_column_combo.setVisible(not is_combined)

        # Update date label
        if is_combined:
            self.date_column_combo.setToolTip("Column containing combined date and time")
        else:
            self.date_column_combo.setToolTip("Column containing date only")

    def _browse_sample_file(self) -> None:
        """Browse for a sample CSV file."""
        start_dir = str(self.sample_file.parent) if self.sample_file else str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sample CSV File",
            start_dir,
            "CSV Files (*.csv);;All Files (*.*)",
        )
        if file_path:
            self.sample_file = Path(file_path)
            self.file_label.setText(self.sample_file.name)
            self.file_label.setStyleSheet("color: #333;")
            self._detect_columns_from_file()

    def _detect_columns_from_file(self) -> None:
        """Detect columns from the sample file."""
        if not self.sample_file or not self.sample_file.exists():
            return

        try:
            # Read first few lines to detect columns
            with open(self.sample_file, encoding="utf-8", errors="ignore") as f:
                # Detect delimiter
                sample = f.read(8192)
                f.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
                except csv.Error:
                    dialect = csv.excel

                reader = csv.reader(f, dialect)
                lines = []
                for i, row in enumerate(reader):
                    if i >= 20:  # Read first 20 lines to find header
                        break
                    lines.append(row)

            # Find the header row (first row with mostly non-numeric strings)
            header_row_idx = 0
            for i, row in enumerate(lines):
                non_numeric = sum(1 for c in row if c and not self._is_numeric(c))
                if non_numeric >= len(row) * 0.5 and len(row) >= 3:
                    header_row_idx = i
                    break

            # Get columns from header row
            if lines:
                self.detected_columns = [c.strip() for c in lines[header_row_idx] if c.strip()]
                self._populate_column_combos()
                self._update_preview(lines, header_row_idx, dialect)

                # Show detected columns
                self.columns_info_label.setText(
                    f"Detected {len(self.detected_columns)} columns: {', '.join(self.detected_columns[:10])}"
                    + ("..." if len(self.detected_columns) > 10 else "")
                )

                # Auto-select likely columns
                self._auto_select_columns()

        except Exception as e:
            logger.exception("Error detecting columns from file")
            QMessageBox.warning(self, "Detection Error", f"Failed to detect columns: {e}")

    def _is_numeric(self, value: str) -> bool:
        """Check if a string value is numeric."""
        try:
            float(value.replace(",", ""))
            return True
        except ValueError:
            return False

    def _populate_column_combos(self) -> None:
        """Populate column combo boxes with detected columns."""
        # Save current selections
        current_date = self.date_column_combo.currentText()
        current_time = self.time_column_combo.currentText()
        current_axis_y = self.axis_y_combo.currentText()
        current_axis_x = self.axis_x_combo.currentText()
        current_axis_z = self.axis_z_combo.currentText()
        current_vm = self.vector_magnitude_combo.currentText()

        # Datetime combos - just add columns directly
        for combo in [self.date_column_combo, self.time_column_combo]:
            combo.clear()
            combo.addItems(self.detected_columns)

        # Axis combos - add "(not available)" option first, then columns
        for combo in [self.axis_y_combo, self.axis_x_combo, self.axis_z_combo, self.vector_magnitude_combo]:
            combo.clear()
            combo.addItem("(not available)", "")
            combo.addItems(self.detected_columns)

        # Restore selections if they exist in new columns
        if current_date in self.detected_columns:
            self.date_column_combo.setCurrentText(current_date)
        if current_time in self.detected_columns:
            self.time_column_combo.setCurrentText(current_time)
        if current_axis_y in self.detected_columns:
            self.axis_y_combo.setCurrentText(current_axis_y)
        if current_axis_x in self.detected_columns:
            self.axis_x_combo.setCurrentText(current_axis_x)
        if current_axis_z in self.detected_columns:
            self.axis_z_combo.setCurrentText(current_axis_z)
        if current_vm in self.detected_columns:
            self.vector_magnitude_combo.setCurrentText(current_vm)

    def _auto_select_columns(self) -> None:
        """Auto-select likely column names based on common patterns."""
        columns_lower = {c.lower(): c for c in self.detected_columns}

        # Date patterns
        date_patterns = ["date", "datetime", "timestamp", "time"]
        for pattern in date_patterns:
            for col_lower, col_orig in columns_lower.items():
                if pattern in col_lower:
                    self.date_column_combo.setCurrentText(col_orig)
                    # Check if it's likely a combined datetime
                    if "datetime" in col_lower or "timestamp" in col_lower:
                        self.datetime_combined_check.setChecked(True)
                    break
            else:
                continue
            break

        # Time patterns (only if not combined)
        if not self.datetime_combined_check.isChecked():
            time_patterns = ["time"]
            for pattern in time_patterns:
                for col_lower, col_orig in columns_lower.items():
                    if col_lower == pattern or col_lower.endswith("time"):
                        self.time_column_combo.setCurrentText(col_orig)
                        break
                else:
                    continue
                break

        # Y-Axis patterns (ActiGraph: Axis1 = Y-axis vertical, GENEActiv/Axivity: y)
        for col_lower, col_orig in columns_lower.items():
            if col_lower == "y" or "axis_y" in col_lower or "axis y" in col_lower or "axisy" in col_lower:
                self.axis_y_combo.setCurrentText(col_orig)
                break

        # X-Axis patterns (ActiGraph: Axis2 = X-axis lateral, GENEActiv/Axivity: x)
        for col_lower, col_orig in columns_lower.items():
            if col_lower == "x" or "axis2" in col_lower or "axis 2" in col_lower:
                self.axis_x_combo.setCurrentText(col_orig)
                break

        # Z-Axis patterns (ActiGraph: Axis3 = Z-axis forward, GENEActiv/Axivity: z)
        for col_lower, col_orig in columns_lower.items():
            if col_lower == "z" or "axis3" in col_lower or "axis 3" in col_lower:
                self.axis_z_combo.setCurrentText(col_orig)
                break

        # Vector Magnitude patterns
        vm_patterns = ["vector magnitude", "vectormagnitude", "vm", "svm", "magnitude"]
        for col_lower, col_orig in columns_lower.items():
            if any(p in col_lower for p in vm_patterns):
                self.vector_magnitude_combo.setCurrentText(col_orig)
                break

    def _update_preview(self, lines: list[list[str]], header_idx: int, dialect) -> None:
        """Update the preview table with sample data."""
        if not lines or header_idx >= len(lines):
            return

        headers = lines[header_idx]
        data_rows = lines[header_idx + 1 : header_idx + 6]  # Next 5 rows

        self.preview_table.clear()
        self.preview_table.setColumnCount(min(len(headers), 8))  # Limit to 8 columns
        self.preview_table.setRowCount(len(data_rows))
        self.preview_table.setHorizontalHeaderLabels(headers[: min(len(headers), 8)])

        for row_idx, row in enumerate(data_rows):
            for col_idx, value in enumerate(row[: min(len(row), 8)]):
                item = QTableWidgetItem(value)
                self.preview_table.setItem(row_idx, col_idx, item)

        self.preview_table.resizeColumnsToContents()

    def _get_combo_value(self, combo: QComboBox) -> str:
        """Get combo value, returning empty string for '(not available)'."""
        text = combo.currentText().strip()
        return "" if text == "(not available)" else text

    def _save_and_accept(self) -> None:
        """Save configuration and accept dialog."""
        if not self.config_manager:
            self.accept()
            return

        # Get values
        date_col = self.date_column_combo.currentText().strip()
        time_col = self.time_column_combo.currentText().strip()
        is_combined = self.datetime_combined_check.isChecked()

        # Get axis columns
        axis_y_col = self._get_combo_value(self.axis_y_combo)
        axis_x_col = self._get_combo_value(self.axis_x_combo)
        axis_z_col = self._get_combo_value(self.axis_z_combo)
        vm_col = self._get_combo_value(self.vector_magnitude_combo)

        # Validate datetime columns
        if not date_col:
            QMessageBox.warning(self, "Validation Error", "Please select a date column.")
            return

        if not is_combined and not time_col:
            QMessageBox.warning(self, "Validation Error", "Please select a time column.")
            return

        # Warn if Y-Axis not set (required for Sadeh - vertical axis)
        if not axis_y_col:
            reply = QMessageBox.warning(
                self,
                "Missing Y-Axis",
                "Y-Axis (vertical) column is not set. The Sadeh algorithm requires Y-Axis data.\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save to config
        config = self.config_manager.config
        config.custom_date_column = date_col
        config.custom_time_column = time_col if not is_combined else ""
        config.datetime_combined = is_combined
        config.custom_axis_y_column = axis_y_col
        config.custom_axis_x_column = axis_x_col
        config.custom_axis_z_column = axis_z_col
        config.custom_vector_magnitude_column = vm_col
        self.config_manager.save_config()

        logger.info(
            "Column mapping saved: date=%s, time=%s, combined=%s, axis_y=%s, axis_x=%s, axis_z=%s, vm=%s",
            date_col,
            time_col,
            is_combined,
            axis_y_col,
            axis_x_col,
            axis_z_col,
            vm_col,
        )

        self.accept()


class DataSettingsTab(QWidget):
    """
    Data Settings Tab for configuring data sources and imports.

    All data is stored in the database. Import operations load data from files
    into the database as a one-time operation. Settings are global and apply
    to all import operations.
    """

    def __init__(self, parent: SleepScoringMainWindow) -> None:
        super().__init__(parent)
        self.parent = parent  # Reference to main window
        self.setup_ui()
        # Filter loaders based on current paradigm after UI is fully set up
        self.update_loaders_for_paradigm()

    def setup_ui(self) -> None:
        """Create the data settings tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Initialize import components
        self._init_import_components()

        # Create scroll area with always-visible scrollbars
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Create content widget that will be scrollable
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # Add explanation header
        header_label = QLabel(
            "<b>Data Configuration</b><br>"
            "Configure settings for data import. All data is stored in the database for fast loading. "
            "Duplicate files are automatically detected and skipped during import.",
        )
        header_label.setWordWrap(True)
        header_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        content_layout.addWidget(header_label)

        # Current Paradigm indicator (link to Study Settings to change it)
        paradigm_indicator = self._create_paradigm_indicator()
        content_layout.addWidget(paradigm_indicator)

        # Activity Data Section
        activity_group = self._create_activity_data_section()
        content_layout.addWidget(activity_group)

        # NWT Sensor Data Section
        nwt_group = self._create_nwt_data_section()
        content_layout.addWidget(nwt_group)

        # Diary Data Section
        diary_group = self._create_diary_data_section()
        content_layout.addWidget(diary_group)

        content_layout.addStretch()

        # Set the content widget in the scroll area
        scroll_area.setWidget(content_widget)

        # Add scroll area to main layout
        layout.addWidget(scroll_area)

    def _init_import_components(self) -> None:
        """Initialize import service components."""
        from sleep_scoring_app.services.import_service import ImportService

        # Initialize import service
        self.import_service = ImportService(self.parent.db_manager)
        self.import_worker = None
        self.progress_timer = QTimer()

    def _init_file_management(self) -> None:
        """Initialize file management widget."""
        try:
            from sleep_scoring_app.services.file_management_service import FileManagementServiceImpl
            from sleep_scoring_app.ui.widgets.file_management_widget import FileManagementWidget

            # Create file management service
            file_service = FileManagementServiceImpl(self.parent.db_manager)

            # Create widget
            self.file_management_widget = FileManagementWidget(file_service, parent=self)

            # Connect signals
            self.file_management_widget.filesDeleted.connect(self._on_files_deleted)

            logger.info("File management widget initialized")
        except Exception as e:
            logger.exception("Failed to initialize file management widget")
            # Don't create widget if initialization fails
            if hasattr(self, "file_management_widget"):
                delattr(self, "file_management_widget")

    def _on_files_deleted(self, filenames: list[str]) -> None:
        """
        Handle files deleted signal.

        Clears caches, refreshes the Analysis tab file list, and handles
        the case where the currently selected file was deleted.

        Args:
            filenames: List of deleted file names

        """
        logger.info("Files deleted: %s", filenames)

        # Clear cache in unified data service for each deleted file
        if hasattr(self.parent, "data_service"):
            for filename in filenames:
                self.parent.data_service.clear_file_cache(filename)

        # Check if the currently selected file was deleted
        current_file_deleted = False
        if hasattr(self.parent, "selected_file") and self.parent.selected_file:
            from pathlib import Path

            current_filename = Path(self.parent.selected_file).name
            if current_filename in filenames:
                current_file_deleted = True
                logger.info("Currently selected file %s was deleted", current_filename)

        # Reload the file list in the Analysis tab (this updates the FileSelectionTable)
        if hasattr(self.parent, "load_available_files"):
            # Don't preserve selection if the current file was deleted
            self.parent.load_available_files(preserve_selection=not current_file_deleted)

        # If current file was deleted, clear the plot and reset UI state
        if current_file_deleted:
            self._handle_current_file_deleted()

    def _handle_current_file_deleted(self) -> None:
        """Handle cleanup when the currently selected file is deleted."""
        try:
            # Clear selected file reference
            if hasattr(self.parent, "selected_file"):
                self.parent.selected_file = None

            # Clear available dates
            if hasattr(self.parent, "available_dates"):
                self.parent.available_dates = []

            # Clear the plot widget
            if hasattr(self.parent, "plot_widget") and self.parent.plot_widget is not None:
                self.parent.plot_widget.clear_plot()

            # Clear date dropdown
            if hasattr(self.parent, "date_dropdown") and self.parent.date_dropdown is not None:
                self.parent.date_dropdown.clear()

            # Update status bar
            if hasattr(self.parent, "update_status_bar"):
                self.parent.update_status_bar()

            logger.info("Cleared UI state after current file deletion")
        except Exception as e:
            logger.warning("Error during file deletion cleanup: %s", e)

    def _create_paradigm_indicator(self) -> QWidget:
        """Create a paradigm indicator showing current paradigm with link to change it."""
        indicator_widget = QWidget()
        indicator_layout = QHBoxLayout(indicator_widget)
        indicator_layout.setContentsMargins(0, 10, 0, 10)

        # Get current paradigm
        try:
            paradigm_value = self.parent.config_manager.config.data_paradigm
            paradigm = StudyDataParadigm(paradigm_value)
        except (ValueError, AttributeError):
            paradigm = StudyDataParadigm.get_default()

        # Create indicator label
        self.paradigm_indicator_label = QLabel()
        self._update_paradigm_indicator_label(paradigm)
        indicator_layout.addWidget(self.paradigm_indicator_label)

        # Add button to change paradigm (links to Study Settings tab)
        change_paradigm_btn = QPushButton("Change Data Paradigm...")
        change_paradigm_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        change_paradigm_btn.setToolTip("Go to Study Settings to change the Data Paradigm")
        change_paradigm_btn.clicked.connect(self._go_to_study_settings)
        indicator_layout.addWidget(change_paradigm_btn)

        indicator_layout.addStretch()

        return indicator_widget

    def _update_paradigm_indicator_label(self, paradigm: StudyDataParadigm) -> None:
        """Update the paradigm indicator label text and style."""
        if paradigm == StudyDataParadigm.EPOCH_BASED:
            text = "📊 <b>Current Data Paradigm:</b> Epoch-Based (CSV with activity counts)"
            bg_color = "#e8f5e9"
            border_color = "#4caf50"
        else:
            text = "📈 <b>Current Data Paradigm:</b> Raw Accelerometer (GT3X / Raw CSV)"
            bg_color = "#e3f2fd"
            border_color = "#2196f3"

        self.paradigm_indicator_label.setText(text)
        self.paradigm_indicator_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                padding: 10px 15px;
                background-color: {bg_color};
                border-left: 4px solid {border_color};
                border-radius: 4px;
            }}
        """)
        self.paradigm_indicator_label.setWordWrap(True)

    def _go_to_study_settings(self) -> None:
        """Switch to Study Settings tab."""
        if hasattr(self.parent, "tab_widget"):
            # Find the Study Settings tab index
            for i in range(self.parent.tab_widget.count()):
                if self.parent.tab_widget.tabText(i) == "Study Settings":
                    self.parent.tab_widget.setCurrentIndex(i)
                    break

    def _create_section_separator(self) -> QFrame:
        """Create a horizontal line separator."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("QFrame { color: #87CEEB; }")  # Light blue color
        return line

    def _create_path_label(self, initial_text: str = "") -> QLabel:
        """
        Create a path label with proper size constraints to prevent layout expansion.

        The label uses elided text to handle long paths gracefully.
        """
        label = QLabel(initial_text or InfoMessage.NO_DIRECTORY_SELECTED)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        label.setMinimumWidth(100)
        label.setMaximumWidth(350)
        label.setStyleSheet("QLabel { color: #555; }")
        return label

    def _set_path_label_text(self, label: QLabel, full_path: str) -> None:
        """
        Set text on a path label with elision for long paths.

        Shows the full path in a tooltip on hover.
        """
        if not full_path or full_path == InfoMessage.NO_DIRECTORY_SELECTED:
            label.setText(InfoMessage.NO_DIRECTORY_SELECTED)
            label.setToolTip("")
            label.setStyleSheet("QLabel { color: #999; }")
            return

        metrics = QFontMetrics(label.font())
        # Use a reasonable width for elision (account for padding)
        available_width = label.maximumWidth() - 10
        elided = metrics.elidedText(full_path, Qt.TextElideMode.ElideMiddle, available_width)
        label.setText(elided)
        label.setToolTip(full_path)  # Show full path on hover
        label.setStyleSheet("QLabel { color: #333; }")

    def _create_activity_data_section(self) -> QGroupBox:
        """Create Activity Data section with global settings and import."""
        # Make title paradigm-aware
        try:
            paradigm_value = self.parent.config_manager.config.data_paradigm
            paradigm = StudyDataParadigm(paradigm_value)
        except (ValueError, AttributeError):
            paradigm = StudyDataParadigm.get_default()

        # Set title based on paradigm
        if paradigm == StudyDataParadigm.EPOCH_BASED:
            title = "Activity Data (CSV/Excel with epoch counts)"
        else:
            title = "Activity Data (GT3X or raw CSV files)"

        self.activity_group = QGroupBox(title)
        activity_layout = QVBoxLayout(self.activity_group)

        # Global Settings Grid
        settings_grid = QGridLayout()

        # Data Source Type dropdown (DI pattern)
        settings_grid.addWidget(QLabel("Data Source Type:"), 0, 0)
        self.data_source_combo = QComboBox()

        # Populate from factory - filtered by current paradigm
        # Note: update_loaders_for_paradigm() is called after combo is set up
        # to properly filter based on the current paradigm setting
        from sleep_scoring_app.io.sources.loader_factory import DataSourceFactory

        # Initial population with all loaders (will be filtered by paradigm)
        available_loaders = DataSourceFactory.get_available_loaders()
        for loader_id, display_name in available_loaders.items():
            self.data_source_combo.addItem(display_name, loader_id)

        # Set current value from config (block signals during initialization)
        self.data_source_combo.blockSignals(True)
        current_loader_id = self.parent.config_manager.config.data_source_type_id
        for i in range(self.data_source_combo.count()):
            if self.data_source_combo.itemData(i) == current_loader_id:
                self.data_source_combo.setCurrentIndex(i)
                break
        self.data_source_combo.blockSignals(False)

        self.data_source_combo.currentIndexChanged.connect(self._on_data_source_changed)
        self.data_source_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.data_source_combo.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        settings_grid.addWidget(self.data_source_combo, 0, 1)

        # Device Preset dropdown with auto-detect
        settings_grid.addWidget(QLabel("Device Preset:"), 1, 0)
        self.device_preset_combo = QComboBox()
        device_display_names = {
            DevicePreset.ACTIGRAPH: "ActiGraph",
            DevicePreset.GENEACTIV: "GENEActiv",
            DevicePreset.AXIVITY: "Axivity",
            DevicePreset.ACTIWATCH: "Actiwatch",
            DevicePreset.MOTIONWATCH: "MotionWatch",
            DevicePreset.GENERIC_CSV: "Generic CSV",
        }
        for preset in DevicePreset:
            self.device_preset_combo.addItem(device_display_names[preset], preset.value)

        # Set current value from config
        current_preset = self.parent.config_manager.config.device_preset
        for i in range(self.device_preset_combo.count()):
            if self.device_preset_combo.itemData(i) == current_preset:
                self.device_preset_combo.setCurrentIndex(i)
                break

        self.device_preset_combo.currentIndexChanged.connect(self._on_device_preset_changed)
        self.device_preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.device_preset_combo.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        settings_grid.addWidget(self.device_preset_combo, 1, 1)

        # Auto-detect device button
        self.device_autodetect_btn = QPushButton("Auto-detect")
        self.device_autodetect_btn.clicked.connect(self._autodetect_device_format)
        settings_grid.addWidget(self.device_autodetect_btn, 1, 2)

        # Configure Columns button (enabled only for Generic CSV)
        self.configure_columns_btn = QPushButton("Configure Columns...")
        self.configure_columns_btn.setEnabled(current_preset == DevicePreset.GENERIC_CSV.value)
        self.configure_columns_btn.clicked.connect(self._open_column_mapping_dialog)
        settings_grid.addWidget(self.configure_columns_btn, 1, 3)

        # Epoch length
        settings_grid.addWidget(QLabel("Epoch Length (seconds):"), 2, 0)
        self.epoch_length_spin = QSpinBox()
        self.epoch_length_spin.setRange(1, 300)
        self.epoch_length_spin.setValue(self.parent.config_manager.config.epoch_length)
        self.epoch_length_spin.valueChanged.connect(self.parent.on_epoch_length_changed)
        self.epoch_length_spin.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        settings_grid.addWidget(self.epoch_length_spin, 2, 1)

        # Auto-detect button for Epoch Length
        self.epoch_autodetect_btn = QPushButton("Auto-detect")
        self.epoch_autodetect_btn.clicked.connect(self._autodetect_epoch_length)
        settings_grid.addWidget(self.epoch_autodetect_btn, 2, 2)

        # Skip rows
        settings_grid.addWidget(QLabel("Skip Rows:"), 3, 0)
        self.skip_rows_spin = QSpinBox()
        self.skip_rows_spin.setRange(0, 100)
        self.skip_rows_spin.setValue(self.parent.config_manager.config.skip_rows)
        self.skip_rows_spin.valueChanged.connect(self.parent.on_skip_rows_changed)
        self.skip_rows_spin.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        settings_grid.addWidget(self.skip_rows_spin, 3, 1)

        # Auto-detect button for Skip Rows
        self.skip_rows_autodetect_btn = QPushButton("Auto-detect")
        self.skip_rows_autodetect_btn.clicked.connect(self._autodetect_skip_rows)
        settings_grid.addWidget(self.skip_rows_autodetect_btn, 3, 2)

        # Auto-detect all button
        self.autodetect_all_btn = QPushButton("Auto-detect All")
        self.autodetect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.autodetect_all_btn.clicked.connect(self._autodetect_all)
        settings_grid.addWidget(self.autodetect_all_btn, 3, 3)

        activity_layout.addLayout(settings_grid)

        # CSV-specific options section (placeholder for future CSV-only settings)
        # Note: Skip Rows is now in the main settings section with auto-detect
        self.csv_options_widget = QWidget()
        csv_options_layout = QGridLayout(self.csv_options_widget)
        csv_options_layout.setContentsMargins(20, 10, 0, 10)
        # Currently empty - CSV uses Skip Rows from main settings
        csv_options_layout.setColumnStretch(0, 1)

        activity_layout.addWidget(self.csv_options_widget)
        # Hide CSV options widget since it's empty
        self.csv_options_widget.setVisible(False)

        # GT3X-specific options section
        self.gt3x_options_widget = QWidget()
        gt3x_options_layout = QGridLayout(self.gt3x_options_widget)
        gt3x_options_layout.setContentsMargins(20, 10, 0, 10)

        gt3x_options_layout.addWidget(QLabel("GT3X Epoch Length (seconds):"), 0, 0)
        self.gt3x_epoch_length_spin = QSpinBox()
        self.gt3x_epoch_length_spin.setRange(1, 300)
        self.gt3x_epoch_length_spin.blockSignals(True)
        self.gt3x_epoch_length_spin.setValue(self.parent.config_manager.config.gt3x_epoch_length)
        self.gt3x_epoch_length_spin.blockSignals(False)
        self.gt3x_epoch_length_spin.valueChanged.connect(self._on_gt3x_epoch_length_changed)
        self.gt3x_epoch_length_spin.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.gt3x_epoch_length_spin.setToolTip("Epoch length for GT3X data processing")
        gt3x_options_layout.addWidget(self.gt3x_epoch_length_spin, 0, 1)

        gt3x_options_layout.addWidget(QLabel("Return Raw Data:"), 1, 0)
        self.gt3x_return_raw_check = QCheckBox()
        self.gt3x_return_raw_check.blockSignals(True)
        self.gt3x_return_raw_check.setChecked(self.parent.config_manager.config.gt3x_return_raw)
        self.gt3x_return_raw_check.blockSignals(False)
        self.gt3x_return_raw_check.stateChanged.connect(self._on_gt3x_return_raw_changed)
        self.gt3x_return_raw_check.setToolTip("Return raw acceleration data instead of activity counts")
        gt3x_options_layout.addWidget(self.gt3x_return_raw_check, 1, 1)
        gt3x_options_layout.setColumnStretch(2, 1)

        activity_layout.addWidget(self.gt3x_options_widget)

        # Update visibility based on current selection
        self._update_data_source_visibility()

        # Column mapping status (for Generic CSV)
        self.column_mapping_status = QLabel()
        self.column_mapping_status.setStyleSheet("color: #666; font-size: 10px; padding-left: 5px;")
        self._update_column_mapping_status()
        activity_layout.addWidget(self.column_mapping_status)

        # Import section separator
        activity_layout.addWidget(self._create_section_separator())

        # Import controls
        import_label = QLabel("<b>Import Activity Data:</b>")
        activity_layout.addWidget(import_label)

        import_layout = QHBoxLayout()
        import_layout.addWidget(QLabel("Files:"))

        self.activity_import_files_label = self._create_path_label()
        import_layout.addWidget(self.activity_import_files_label)

        self.activity_browse_btn = QPushButton("Select Files...")
        self.activity_browse_btn.clicked.connect(self.parent.browse_activity_files)
        import_layout.addWidget(self.activity_browse_btn)

        self.activity_import_btn = QPushButton("Import")
        self.activity_import_btn.setEnabled(False)
        self.activity_import_btn.setToolTip("Select CSV files to enable import")
        self.activity_import_btn.clicked.connect(self.parent.start_activity_import)
        self.activity_import_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
            }
            QPushButton:enabled:hover {
                background-color: #229954;
            }
        """)
        import_layout.addWidget(self.activity_import_btn)

        activity_layout.addLayout(import_layout)

        # Progress components - initially hidden
        self.activity_progress_label = QLabel(InfoMessage.READY_TO_IMPORT)
        self.activity_progress_label.setVisible(False)
        activity_layout.addWidget(self.activity_progress_label)

        self.activity_progress_bar = QProgressBar()
        self.activity_progress_bar.setRange(0, 100)
        self.activity_progress_bar.setMinimumHeight(20)
        self.activity_progress_bar.setVisible(False)
        activity_layout.addWidget(self.activity_progress_bar)

        # Status label
        self.activity_status_label = QLabel()
        activity_layout.addWidget(self.activity_status_label)

        # File Management Section
        activity_layout.addWidget(self._create_section_separator())
        file_mgmt_label = QLabel("<b>Manage Imported Files:</b>")
        activity_layout.addWidget(file_mgmt_label)

        # Initialize file management widget
        self._init_file_management()
        if hasattr(self, "file_management_widget"):
            activity_layout.addWidget(self.file_management_widget)

        # Clear buttons row
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()

        self.clear_markers_btn = QPushButton(ButtonText.CLEAR_MARKERS)
        self.clear_markers_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #d68910;
            }
        """)
        self.clear_markers_btn.setToolTip("Clear all sleep markers and metrics (preserves imported data)")
        self.clear_markers_btn.clicked.connect(self.parent.clear_all_markers)
        clear_layout.addWidget(self.clear_markers_btn)

        clear_activity_btn = self._create_clear_button(
            ButtonText.CLEAR_ACTIVITY_DATA,
            "Clear all imported activity data, sleep markers, and metrics",
            self._clear_activity_data,
        )
        clear_layout.addWidget(clear_activity_btn)

        activity_layout.addLayout(clear_layout)

        return self.activity_group

    def _create_nwt_data_section(self) -> QGroupBox:
        """Create NWT Sensor Data section."""
        nwt_group = QGroupBox("NWT Sensor Data (Nonwear Detection)")
        nwt_layout = QVBoxLayout(nwt_group)

        # Import section
        import_label = QLabel("<b>Import NWT Data:</b>")
        nwt_layout.addWidget(import_label)

        import_layout = QHBoxLayout()
        import_layout.addWidget(QLabel("Files:"))

        self.nwt_import_files_label = self._create_path_label()
        import_layout.addWidget(self.nwt_import_files_label)

        self.nwt_browse_btn = QPushButton("Select Files...")
        self.nwt_browse_btn.clicked.connect(self.parent.browse_nonwear_files)
        import_layout.addWidget(self.nwt_browse_btn)

        self.nwt_import_btn = QPushButton("Import")
        self.nwt_import_btn.setEnabled(False)
        self.nwt_import_btn.setToolTip("Select NWT sensor data files to enable import")
        self.nwt_import_btn.clicked.connect(self.parent.start_nonwear_import)
        self.nwt_import_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
            }
            QPushButton:enabled:hover {
                background-color: #229954;
            }
        """)
        import_layout.addWidget(self.nwt_import_btn)

        nwt_layout.addLayout(import_layout)

        # Progress components - initially hidden
        self.nwt_progress_label = QLabel("Ready to import NWT data")
        self.nwt_progress_label.setVisible(False)
        nwt_layout.addWidget(self.nwt_progress_label)

        self.nwt_progress_bar = QProgressBar()
        self.nwt_progress_bar.setRange(0, 100)
        self.nwt_progress_bar.setMinimumHeight(20)
        self.nwt_progress_bar.setVisible(False)
        nwt_layout.addWidget(self.nwt_progress_bar)

        # Clear button
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()

        clear_nwt_btn = self._create_clear_button(
            ButtonText.CLEAR_NWT_DATA,
            "Clear all imported NWT sensor data",
            self._clear_nwt_data,
        )
        clear_layout.addWidget(clear_nwt_btn)

        nwt_layout.addLayout(clear_layout)

        return nwt_group

    def _create_diary_data_section(self) -> QGroupBox:
        """Create Diary Data section."""
        diary_group = QGroupBox("Sleep Diary Data (.xlsx/.csv files)")
        diary_layout = QVBoxLayout(diary_group)

        # Import section
        diary_layout.addWidget(self._create_section_separator())
        import_label = QLabel("<b>Import Diary Data:</b>")
        diary_layout.addWidget(import_label)

        # File selection
        import_file_row = QHBoxLayout()
        import_file_row.addWidget(QLabel("Files:"))

        self.diary_import_files_label = QLabel("No files selected")
        self.diary_import_files_label.setStyleSheet("color: #666;")
        self.diary_import_files_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.diary_import_files_label.setMinimumWidth(100)
        self.diary_import_files_label.setMaximumWidth(350)
        import_file_row.addWidget(self.diary_import_files_label)

        self.diary_import_browse_btn = QPushButton("Browse...")
        self.diary_import_browse_btn.clicked.connect(self._select_diary_import_files)
        import_file_row.addWidget(self.diary_import_browse_btn)

        self.diary_import_btn = QPushButton("Import")
        self.diary_import_btn.clicked.connect(self._import_diary_data)
        self.diary_import_btn.setEnabled(False)
        self.diary_import_btn.setToolTip("Select diary files to enable import")
        self.diary_import_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
            }
            QPushButton:enabled:hover {
                background-color: #229954;
            }
        """)
        import_file_row.addWidget(self.diary_import_btn)

        diary_layout.addLayout(import_file_row)

        # Progress bar
        self.diary_progress = QProgressBar()
        self.diary_progress.setVisible(False)
        diary_layout.addWidget(self.diary_progress)

        # Status label
        self.diary_status_label = QLabel("")
        self.diary_status_label.setStyleSheet("color: #666; font-size: 10px;")
        self.diary_status_label.setWordWrap(True)
        diary_layout.addWidget(self.diary_status_label)

        # Clear button
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()

        clear_diary_btn = self._create_clear_button(
            ButtonText.CLEAR_DIARY_DATA,
            "Clear all imported diary data",
            self._clear_diary_data,
        )
        clear_layout.addWidget(clear_diary_btn)

        diary_layout.addLayout(clear_layout)

        # Store selected files
        self.selected_diary_files: list[Path] = []

        return diary_group

    def _create_clear_button(self, text: str, tooltip: str, click_handler) -> QPushButton:
        """Create a standardized clear button with consistent styling."""
        button = QPushButton(text)
        button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        button.setToolTip(tooltip)
        button.clicked.connect(click_handler)
        return button

    def _update_column_mapping_status(self) -> None:
        """Update the column mapping status label."""
        config = self.parent.config_manager.config

        if config.device_preset != DevicePreset.GENERIC_CSV.value:
            self.column_mapping_status.setText("")
            self.column_mapping_status.setVisible(False)
            return

        self.column_mapping_status.setVisible(True)

        if config.custom_activity_column:
            if config.datetime_combined:
                status = f"Columns: datetime={config.custom_date_column}, activity={config.custom_activity_column}"
            else:
                status = f"Columns: date={config.custom_date_column}, time={config.custom_time_column}, activity={config.custom_activity_column}"
            self.column_mapping_status.setText(f"✓ {status}")
            self.column_mapping_status.setStyleSheet("color: #27ae60; font-size: 10px; padding-left: 5px;")
        else:
            self.column_mapping_status.setText("⚠ Column mapping not configured - click 'Configure Columns...'")
            self.column_mapping_status.setStyleSheet("color: #e67e22; font-size: 10px; padding-left: 5px;")

    # Settings change handlers
    def _on_device_preset_changed(self, index: int) -> None:
        """Handle device preset selection change."""
        preset = self.device_preset_combo.itemData(index)

        # Enable/disable Configure Columns button based on preset
        self.configure_columns_btn.setEnabled(preset == DevicePreset.GENERIC_CSV.value)

        # Update column mapping status
        self._update_column_mapping_status()

        # Update config
        self.parent.config_manager.config.device_preset = preset
        self.parent.config_manager.save_config()
        logger.info("Device preset changed to: %s", preset)

    def _on_data_source_changed(self, index: int) -> None:
        """Handle data source type selection change."""
        loader_id = self.data_source_combo.itemData(index)
        if self.parent and self.parent.config_manager:
            self.parent.config_manager.config.data_source_type_id = loader_id
            self.parent.config_manager.save_config()
            logger.info("Data source type changed to: %s", loader_id)

        # Update visibility of data source specific sections
        self._update_data_source_visibility()

    def _update_data_source_visibility(self) -> None:
        """Update visibility of data source specific option sections."""
        current_index = self.data_source_combo.currentIndex()
        loader_id = self.data_source_combo.itemData(current_index)

        is_csv = loader_id == DataSourceType.CSV
        is_gt3x = loader_id == DataSourceType.GT3X

        self.csv_options_widget.setVisible(is_csv)
        self.gt3x_options_widget.setVisible(is_gt3x)

    def update_loaders_for_paradigm(self, paradigm: StudyDataParadigm | None = None) -> None:
        """
        Update the data source loader combo based on current paradigm.

        Args:
            paradigm: The paradigm to filter loaders for. If None, reads from config.

        This method filters the available loaders:
        - EPOCH_BASED: Only shows CSV loader (for pre-epoched CSV/Excel files)
        - RAW_ACCELEROMETER: Shows both CSV and GT3X loaders

        """
        from sleep_scoring_app.io.sources.loader_factory import DataSourceFactory

        # Get current paradigm if not provided
        if paradigm is None:
            try:
                paradigm_value = self.parent.config_manager.config.data_paradigm
                paradigm = StudyDataParadigm(paradigm_value)
            except (ValueError, AttributeError):
                paradigm = StudyDataParadigm.get_default()

        # Store current selection to try to restore it
        current_loader_id = self.data_source_combo.currentData()

        # Block signals during update
        self.data_source_combo.blockSignals(True)
        self.data_source_combo.clear()

        # Get all available loaders
        available_loaders = DataSourceFactory.get_available_loaders()

        # Filter loaders based on paradigm
        if paradigm == StudyDataParadigm.EPOCH_BASED:
            # Epoch-based: only CSV loader (GT3X requires raw processing)
            filtered_loaders = {k: v for k, v in available_loaders.items() if k == DataSourceType.CSV}
        else:
            # Raw accelerometer: all loaders available
            filtered_loaders = available_loaders

        # Populate combo with filtered loaders
        for loader_id, display_name in filtered_loaders.items():
            self.data_source_combo.addItem(display_name, loader_id)

        # Try to restore previous selection if still available
        restored = False
        if current_loader_id:
            for i in range(self.data_source_combo.count()):
                if self.data_source_combo.itemData(i) == current_loader_id:
                    self.data_source_combo.setCurrentIndex(i)
                    restored = True
                    break

        # If previous selection not available, select first item
        if not restored and self.data_source_combo.count() > 0:
            self.data_source_combo.setCurrentIndex(0)
            # Update config with new loader
            new_loader_id = self.data_source_combo.itemData(0)
            if self.parent and self.parent.config_manager:
                self.parent.config_manager.config.data_source_type_id = new_loader_id
                self.parent.config_manager.save_config()

        self.data_source_combo.blockSignals(False)

        # Update visibility of loader-specific options
        self._update_data_source_visibility()

        # Update paradigm indicator
        if hasattr(self, "paradigm_indicator_label"):
            self._update_paradigm_indicator_label(paradigm)

        # Update Activity Data GroupBox title
        if hasattr(self, "activity_group"):
            if paradigm == StudyDataParadigm.EPOCH_BASED:
                self.activity_group.setTitle("Activity Data (CSV/Excel with epoch counts)")
            else:
                self.activity_group.setTitle("Activity Data (GT3X or raw CSV files)")

        logger.info("Updated data source loaders for paradigm: %s", paradigm.get_display_name())

    def _on_gt3x_epoch_length_changed(self, value: int) -> None:
        """Handle GT3X epoch length spinner change."""
        if self.parent and self.parent.config_manager:
            self.parent.config_manager.config.gt3x_epoch_length = value
            self.parent.config_manager.save_config()
            logger.debug("GT3X epoch length changed to: %s", value)

    def _on_gt3x_return_raw_changed(self, state: int) -> None:
        """Handle GT3X return raw checkbox change."""
        if self.parent and self.parent.config_manager:
            self.parent.config_manager.config.gt3x_return_raw = bool(state)
            self.parent.config_manager.save_config()
            logger.debug("GT3X return raw changed to: %s", bool(state))

    def _open_column_mapping_dialog(self) -> None:
        """Open the column mapping configuration dialog."""
        # Try to get a sample file from selected files or import directory
        sample_file = None
        if hasattr(self.parent, "_selected_activity_files") and self.parent._selected_activity_files:
            # Use one of the selected files
            csv_files = [f for f in self.parent._selected_activity_files if f.suffix.lower() == ".csv"]
            if csv_files:
                sample_file = random.choice(csv_files)
        elif self.parent.config_manager.config.import_activity_directory:
            # Fall back to import directory
            folder = Path(self.parent.config_manager.config.import_activity_directory)
            csv_files = list(folder.glob("*.csv"))
            if csv_files:
                sample_file = random.choice(csv_files)

        dialog = ColumnMappingDialog(
            parent=self,
            config_manager=self.parent.config_manager,
            sample_file=sample_file,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_column_mapping_status()

    def _autodetect_device_format(self) -> None:
        """Auto-detect device format from CSV file."""
        from sleep_scoring_app.services.format_detector import FormatDetector

        # Get sample CSV files
        csv_files = self._get_sample_csv_files()
        if not csv_files:
            QMessageBox.warning(self, "No CSV Files", "Please select CSV files first.")
            return

        sample_file = random.choice(csv_files)
        detector = FormatDetector()

        try:
            device_preset, confidence = detector.detect_device_format(sample_file)

            confidence_pct = int(confidence * 100)
            color = "#27ae60" if confidence >= 0.7 else "#f39c12" if confidence >= 0.5 else "#e74c3c"

            # Get display name
            device_names = {
                DevicePreset.ACTIGRAPH: "ActiGraph",
                DevicePreset.GENEACTIV: "GENEActiv",
                DevicePreset.AXIVITY: "Axivity",
                DevicePreset.ACTIWATCH: "Actiwatch",
                DevicePreset.MOTIONWATCH: "MotionWatch",
                DevicePreset.GENERIC_CSV: "Generic CSV",
            }
            device_name = device_names.get(device_preset, str(device_preset))

            reply = QMessageBox.question(
                self,
                "Device Format Detected",
                f"Detected: <b>{device_name}</b><br>"
                f"Confidence: <span style='color:{color}'><b>{confidence_pct}%</b></span><br><br>"
                f"Sample file: {sample_file.name}<br><br>"
                "Apply this value?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Find and select the detected preset
                for i in range(self.device_preset_combo.count()):
                    if self.device_preset_combo.itemData(i) == device_preset.value:
                        self.device_preset_combo.setCurrentIndex(i)
                        break

        except Exception as e:
            QMessageBox.critical(self, "Detection Error", f"Failed to detect device format: {e}")
            logger.exception("Failed to detect device format")

    def _autodetect_epoch_length(self) -> None:
        """Auto-detect epoch length from CSV file."""
        from sleep_scoring_app.services.format_detector import FormatDetector

        # Get sample CSV files
        csv_files = self._get_sample_csv_files()
        if not csv_files:
            QMessageBox.warning(self, "No CSV Files", "Please select CSV files first.")
            return

        sample_file = random.choice(csv_files)
        detector = FormatDetector()

        try:
            skip_rows = self.skip_rows_spin.value()
            epoch_length, confidence = detector.detect_epoch_length(sample_file, skip_rows)

            confidence_pct = int(confidence * 100)
            color = "#27ae60" if confidence >= 0.9 else "#f39c12" if confidence >= 0.7 else "#e74c3c"

            reply = QMessageBox.question(
                self,
                "Epoch Length Detected",
                f"Detected: <b>{epoch_length} seconds</b><br>"
                f"Confidence: <span style='color:{color}'><b>{confidence_pct}%</b></span><br><br>"
                f"Sample file: {sample_file.name}<br><br>"
                "Apply this value?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.epoch_length_spin.setValue(epoch_length)

        except Exception as e:
            QMessageBox.critical(self, "Detection Error", f"Failed to detect epoch length: {e}")
            logger.exception("Failed to detect epoch length")

    def _autodetect_skip_rows(self) -> None:
        """Auto-detect number of rows to skip."""
        from sleep_scoring_app.services.format_detector import FormatDetector

        # Get sample CSV files
        csv_files = self._get_sample_csv_files()
        if not csv_files:
            QMessageBox.warning(self, "No CSV Files", "Please select CSV files first.")
            return

        sample_file = random.choice(csv_files)
        detector = FormatDetector()

        try:
            skip_rows, confidence = detector.detect_header_rows(sample_file)

            confidence_pct = int(confidence * 100)
            color = "#27ae60" if confidence >= 0.9 else "#f39c12" if confidence >= 0.7 else "#e74c3c"

            reply = QMessageBox.question(
                self,
                "Header Rows Detected",
                f"Detected: <b>{skip_rows} header rows</b><br>"
                f"Confidence: <span style='color:{color}'><b>{confidence_pct}%</b></span><br><br>"
                f"Sample file: {sample_file.name}<br><br>"
                "Apply this value?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.skip_rows_spin.setValue(skip_rows)

        except Exception as e:
            QMessageBox.critical(self, "Detection Error", f"Failed to detect header rows: {e}")
            logger.exception("Failed to detect header rows")

    def _autodetect_all(self) -> None:
        """Auto-detect all settings at once."""
        from sleep_scoring_app.services.format_detector import FormatDetector

        # Get sample CSV files
        csv_files = self._get_sample_csv_files()
        if not csv_files:
            QMessageBox.warning(self, "No CSV Files", "Please select CSV files first.")
            return

        sample_file = random.choice(csv_files)
        detector = FormatDetector()

        results = []

        try:
            # Detect all three
            skip_rows, skip_conf = detector.detect_header_rows(sample_file)
            epoch_length, epoch_conf = detector.detect_epoch_length(sample_file, skip_rows)
            device_preset, device_conf = detector.detect_device_format(sample_file)

            # Get device display name
            device_names = {
                DevicePreset.ACTIGRAPH: "ActiGraph",
                DevicePreset.GENEACTIV: "GENEActiv",
                DevicePreset.AXIVITY: "Axivity",
                DevicePreset.ACTIWATCH: "Actiwatch",
                DevicePreset.MOTIONWATCH: "MotionWatch",
                DevicePreset.GENERIC_CSV: "Generic CSV",
            }
            device_name = device_names.get(device_preset, str(device_preset))

            def conf_color(conf: float) -> str:
                if conf >= 0.8:
                    return "#27ae60"
                if conf >= 0.6:
                    return "#f39c12"
                return "#e74c3c"

            message = (
                f"<b>Auto-Detection Results</b><br><br>"
                f"Sample file: {sample_file.name}<br><br>"
                f"<b>Device:</b> {device_name} "
                f"<span style='color:{conf_color(device_conf)}'>[{int(device_conf * 100)}%]</span><br>"
                f"<b>Skip Rows:</b> {skip_rows} "
                f"<span style='color:{conf_color(skip_conf)}'>[{int(skip_conf * 100)}%]</span><br>"
                f"<b>Epoch Length:</b> {epoch_length}s "
                f"<span style='color:{conf_color(epoch_conf)}'>[{int(epoch_conf * 100)}%]</span><br><br>"
                f"Apply these values?"
            )

            reply = QMessageBox.question(
                self,
                "Auto-Detection Results",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Apply all values
                self.skip_rows_spin.setValue(skip_rows)
                self.epoch_length_spin.setValue(epoch_length)
                for i in range(self.device_preset_combo.count()):
                    if self.device_preset_combo.itemData(i) == device_preset.value:
                        self.device_preset_combo.setCurrentIndex(i)
                        break

        except Exception as e:
            QMessageBox.critical(self, "Detection Error", f"Auto-detection failed: {e}")
            logger.exception("Auto-detection failed")

    def _get_sample_csv_files(self) -> list[Path]:
        """Get CSV files for sampling - from selected files or fallback to directories."""
        # Try selected activity files first
        if hasattr(self.parent, "_selected_activity_files") and self.parent._selected_activity_files:
            csv_files = [f for f in self.parent._selected_activity_files if f.suffix.lower() == ".csv"]
            if csv_files:
                return csv_files

        # Fall back to config import directory
        if self.parent.config_manager.config.import_activity_directory:
            folder = Path(self.parent.config_manager.config.import_activity_directory)
            if folder.exists():
                csv_files = list(folder.glob("*.csv"))
                if csv_files:
                    return csv_files

        # Fall back to config data folder
        if self.parent.config_manager.config.data_folder:
            folder = Path(self.parent.config_manager.config.data_folder)
            if folder.exists():
                csv_files = list(folder.glob("*.csv"))
                if csv_files:
                    return csv_files

        return []

    # Diary import methods
    def _select_diary_import_files(self) -> None:
        """Select diary files for import to database."""
        # Start from last used diary directory or home directory
        start_dir = self.parent.config_manager.config.diary_import_directory or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Diary Files to Import",
            start_dir,
            "Excel and CSV files (*.xlsx *.xls *.csv);;Excel files (*.xlsx *.xls);;CSV files (*.csv)",
        )

        if files:
            self.selected_diary_files = [Path(f) for f in files]
            if len(files) == 1:
                self.diary_import_files_label.setText(f"1 file: {Path(files[0]).name}")
            else:
                self.diary_import_files_label.setText(f"{len(files)} files selected")
            self.diary_import_files_label.setStyleSheet("color: #333;")
            self.diary_import_btn.setEnabled(True)

            # Save the directory of the first selected file for next time
            first_file_dir = str(Path(files[0]).parent)
            self.parent.config_manager.config.diary_import_directory = first_file_dir
            self.parent.config_manager.save_config()
        else:
            self.selected_diary_files = []
            self.diary_import_files_label.setText("No files selected")
            self.diary_import_files_label.setStyleSheet("color: #666;")
            self.diary_import_btn.setEnabled(False)

    def _import_diary_data(self) -> None:
        """Import diary data using selected files."""
        if not self.selected_diary_files:
            self._show_diary_status("No files selected", error=True)
            return

        # Start import process
        self.diary_import_btn.setEnabled(False)
        self.diary_progress.setVisible(True)
        self.diary_progress.setRange(0, 0)  # Indeterminate progress
        self._show_diary_status("Starting import...")

        try:
            # Use the simplified diary service for import
            if hasattr(self.parent, "data_service") and hasattr(self.parent.data_service, "diary_service"):
                result = self.parent.data_service.diary_service.import_diary_files(
                    self.selected_diary_files,
                    progress_callback=self._on_diary_import_progress,
                )

                # Show results
                if result.successful_files:
                    success_msg = f"Successfully imported {len(result.successful_files)} files with {result.total_entries_imported} entries"
                    self._show_diary_status(success_msg)

                    # Show success confirmation dialog
                    QMessageBox.information(
                        self,
                        "Import Successful",
                        f"Successfully imported {len(result.successful_files)} diary file(s) with {result.total_entries_imported} entries.",
                    )

                    # Clear selections after successful import
                    self.selected_diary_files = []
                    self.diary_import_files_label.setText("No files selected")
                    self.diary_import_files_label.setStyleSheet("color: #666;")
                else:
                    self._show_diary_status("Import failed - no files processed successfully", error=True)

                if result.failed_files:
                    # Format error messages more clearly
                    error_messages = []
                    for file_path, error_msg in result.failed_files[:3]:  # Show first 3 errors
                        file_name = Path(file_path).name
                        error_messages.append(f"{file_name}: {error_msg}")

                    error_details = "; ".join(error_messages)
                    if len(result.failed_files) > 3:
                        error_details += f" (and {len(result.failed_files) - 3} more)"

                    self._show_diary_status(f"Some files failed: {error_details}", error=True)
            elif not hasattr(self.parent, "data_service"):
                self._show_diary_status("Main data service not initialized", error=True)
                logger.error("Parent window missing data_service attribute")
            elif not hasattr(self.parent.data_service, "diary_service"):
                self._show_diary_status("Diary service not initialized in data service", error=True)
                logger.error("data_service missing diary_service attribute")
            else:
                self._show_diary_status("Data service not available", error=True)
                logger.error("Unknown data service availability issue")

        except Exception as e:
            logger.exception("Diary import failed with exception: %s", e)
            self._show_diary_status(f"Import error: {e!s}", error=True)

        finally:
            self.diary_import_btn.setEnabled(bool(self.selected_diary_files))
            self.diary_progress.setVisible(False)

    def _on_diary_import_progress(self, message: str, current: int, total: int) -> None:
        """Handle diary import progress updates."""
        self._show_diary_status(message)
        if total > 0:
            self.diary_progress.setRange(0, total)
            self.diary_progress.setValue(current)

    def _show_diary_status(self, message: str, error: bool = False) -> None:
        """Show status message for diary import."""
        self.diary_status_label.setText(message)
        if error:
            self.diary_status_label.setStyleSheet("color: #d32f2f; font-size: 10px;")
        else:
            self.diary_status_label.setStyleSheet("color: #666; font-size: 10px;")

    # Clear data methods
    def _clear_activity_data(self) -> None:
        """Clear all imported activity data from database."""
        reply = QMessageBox.question(
            self,
            "Clear Activity Data",
            "Are you sure you want to clear all imported activity data?\n\n"
            "This will remove:\n"
            "- All activity file records\n"
            "- All sleep markers and metrics\n"
            "- This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.parent.db_manager.clear_activity_data()
                QMessageBox.information(self, "Success", "Activity data cleared successfully!")
                self.parent.load_available_files(preserve_selection=False)
                logger.info("Activity data cleared by user")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear activity data: {e}")
                logger.exception("Failed to clear activity data")

    def _clear_nwt_data(self) -> None:
        """Clear all imported NWT sensor data from database."""
        reply = QMessageBox.question(
            self,
            "Clear NWT Data",
            "Are you sure you want to clear all NWT sensor data?\n\nThis action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.parent.db_manager.clear_nwt_data()
                QMessageBox.information(self, "Success", "NWT data cleared successfully!")
                logger.info("NWT data cleared by user")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear NWT data: {e}")
                logger.exception("Failed to clear NWT data")

    def _clear_diary_data(self) -> None:
        """Clear all imported diary data from database."""
        reply = QMessageBox.question(
            self,
            "Clear Diary Data",
            "Are you sure you want to clear all imported diary data?\n\n"
            "This will remove:\n"
            "- All diary entries\n"
            "- All raw diary import data\n"
            "- This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.parent.db_manager.clear_diary_data()
                QMessageBox.information(self, "Success", "Diary data cleared successfully!")
                logger.info("Diary data cleared by user")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear diary data: {e}")
                logger.exception("Failed to clear diary data")
