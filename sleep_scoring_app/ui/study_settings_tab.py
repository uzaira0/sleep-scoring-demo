#!/usr/bin/env python3
"""
Study Settings Tab Component
Handles study configuration parameters like groups, timepoints, and defaults.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTime, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.core.constants import ActivityDataPreference, SadehVariant

if TYPE_CHECKING:
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow

logger = logging.getLogger(__name__)


class DragDropListWidget(QListWidget):
    """Custom list widget with drag-and-drop reordering and inline editing."""

    items_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        # Enable inline editing on double-click
        self.itemDoubleClicked.connect(self._edit_item)

        # Track changes for validation and auto-save
        self.model().rowsMoved.connect(self.items_changed.emit)
        self.model().rowsInserted.connect(self.items_changed.emit)
        self.model().rowsRemoved.connect(self.items_changed.emit)
        self.itemChanged.connect(self.items_changed.emit)  # For inline edits

    def _edit_item(self, item: QListWidgetItem) -> None:
        """Enable inline editing for an item."""
        if item:
            # Get the current text
            current_text = item.text()

            # Open input dialog for editing
            text, ok = QInputDialog.getText(
                self,
                "Edit Item",
                "Edit item name:",
                text=current_text,
            )

            if ok and text.strip():
                new_text = text.strip().upper()

                # Check for duplicates (excluding current item)
                existing_items = []
                for i in range(self.count()):
                    if i != self.row(item):
                        existing_items.append(self.item(i).text())

                if new_text not in existing_items:
                    item.setText(new_text)
                    self.items_changed.emit()
                    logger.debug("Edited item: %s -> %s", current_text, new_text)
                else:
                    QMessageBox.information(self, "Duplicate Item", f"Item '{new_text}' already exists.")

    def add_item_with_validation(self, text: str) -> bool:
        """Add an item with duplicate validation."""
        text = text.strip().upper()

        # Check for duplicates
        existing_items = [self.item(i).text() for i in range(self.count())]
        if text in existing_items:
            return False

        self.addItem(text)
        self.items_changed.emit()
        return True

    def get_all_items(self) -> list[str]:
        """Get all items as a list of strings."""
        return [self.item(i).text() for i in range(self.count())]


class StudySettingsTab(QWidget):
    """Study Settings Tab for configuring study parameters."""

    # Signals for when groups/timepoints lists change (for real-time dropdown updates)
    groups_changed = pyqtSignal(list)
    timepoints_changed = pyqtSignal(list)

    def __init__(self, parent: SleepScoringMainWindow) -> None:
        super().__init__(parent)
        self.parent = parent  # Reference to main window
        self.setup_ui()
        self._connect_signals()

    def setup_ui(self) -> None:
        """Create the study settings tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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
            "<b>Study Configuration</b><br>"
            "Configure study parameters such as default groups, timepoints, valid values, and "
            "regex patterns for participant information extraction. These settings affect how "
            "participant information is extracted and displayed.",
        )
        header_label.setWordWrap(True)
        header_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        content_layout.addWidget(header_label)

        # Regex Patterns Section (Top Priority)
        regex_patterns_group = self._create_regex_patterns_section()
        content_layout.addWidget(regex_patterns_group)

        # Live ID Testing Section
        id_testing_group = self._create_id_testing_section()
        content_layout.addWidget(id_testing_group)

        # Study Parameters Section (Unknown Value Placeholder only)
        study_params_group = self._create_study_parameters_section()
        content_layout.addWidget(study_params_group)

        # Valid Groups/Timepoints Section
        valid_values_group = self._create_valid_values_section()
        content_layout.addWidget(valid_values_group)

        # Default Selection Section
        default_selection_group = self._create_default_selection_section()
        content_layout.addWidget(default_selection_group)

        # Algorithm Configuration Section
        algorithm_config_group = self._create_algorithm_configuration_section()
        content_layout.addWidget(algorithm_config_group)

        # Action buttons
        buttons_layout = self._create_action_buttons()
        content_layout.addLayout(buttons_layout)

        content_layout.addStretch()

        # Set the content widget in the scroll area
        scroll_area.setWidget(content_widget)

        # Add scroll area to main layout
        layout.addWidget(scroll_area)

        # Load current settings
        self._load_current_settings()

    def _connect_signals(self) -> None:
        """Connect internal signals for dynamic updates."""
        # Connect list widget changes to update default dropdowns
        self.valid_groups_list.items_changed.connect(self._update_group_dropdown)
        self.valid_timepoints_list.items_changed.connect(self._update_timepoint_dropdown)

        # Connect signals for external listeners (avoid lambda for memory safety)
        self.valid_groups_list.items_changed.connect(self._emit_groups_changed)
        self.valid_timepoints_list.items_changed.connect(self._emit_timepoints_changed)

        # Connect list widget changes to auto-save to config
        self.valid_groups_list.items_changed.connect(self._save_valid_groups)
        self.valid_timepoints_list.items_changed.connect(self._save_valid_timepoints)

        # Connect text field changes to auto-save to config (with debouncing)
        self.unknown_value_edit.textChanged.connect(self._on_unknown_value_changed)
        self.id_pattern_edit.textChanged.connect(self._on_id_pattern_changed)
        self.timepoint_pattern_edit.textChanged.connect(self._on_timepoint_pattern_changed)
        self.group_pattern_edit.textChanged.connect(self._on_group_pattern_changed)

        # Connect pattern changes to live testing (if testing UI exists)
        if hasattr(self, "test_id_input"):
            # Connect pattern field changes
            self.id_pattern_edit.textChanged.connect(self._update_id_test_results)
            self.timepoint_pattern_edit.textChanged.connect(self._update_id_test_results)
            self.group_pattern_edit.textChanged.connect(self._update_id_test_results)

            # Connect dropdown changes
            self.default_group_combo.currentTextChanged.connect(self._update_id_test_results)
            self.default_timepoint_combo.currentTextChanged.connect(self._update_id_test_results)

            # Connect validation list changes
            self.valid_groups_list.items_changed.connect(self._update_id_test_results)
            self.valid_timepoints_list.items_changed.connect(self._update_id_test_results)

    def _create_regex_patterns_section(self) -> QGroupBox:
        """Create the regex patterns configuration section."""
        group_box = QGroupBox("Participant Information Patterns")
        layout = QVBoxLayout(group_box)

        # Description
        description_label = QLabel(
            "Configure regex patterns used to extract participant IDs, timepoints, and groups from filenames. "
            "Patterns are validated in real-time with visual feedback."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("QLabel { color: #666; font-style: italic; margin-bottom: 10px; }")
        layout.addWidget(description_label)

        # Create form layout for regex patterns
        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(15)
        form_layout.setVerticalSpacing(10)

        # ID Regex Pattern
        self.id_pattern_edit = QLineEdit()
        self.id_pattern_edit.setPlaceholderText("Enter regex pattern to extract participant IDs")
        self.id_pattern_edit.setToolTip(
            "Regex pattern to match participant IDs in filenames.\nExample: r'^(\\d{4,})[_-]' matches '4000_data.csv' and extracts '4000'"
        )
        self.id_pattern_edit.setMaximumWidth(400)
        self.id_pattern_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.id_pattern_edit.textChanged.connect(self._validate_id_pattern)
        id_label = QLabel("ID Pattern:")
        id_label.setToolTip("Primary regex pattern for extracting participant IDs")
        form_layout.addRow(id_label, self.id_pattern_edit)

        # Timepoint Regex Pattern
        self.timepoint_pattern_edit = QLineEdit()
        self.timepoint_pattern_edit.setPlaceholderText("Enter regex pattern to extract timepoint codes")
        self.timepoint_pattern_edit.setToolTip(
            "Regex pattern to match timepoints in filenames.\nExample: r'([A-Z0-9]+)' matches 'BO', 'P1', 'P2' in filenames"
        )
        self.timepoint_pattern_edit.setMaximumWidth(400)
        self.timepoint_pattern_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.timepoint_pattern_edit.textChanged.connect(self._validate_timepoint_pattern)
        timepoint_label = QLabel("Timepoint Pattern:")
        timepoint_label.setToolTip("Regex pattern for extracting timepoint codes")
        form_layout.addRow(timepoint_label, self.timepoint_pattern_edit)

        # Group Regex Pattern
        self.group_pattern_edit = QLineEdit()
        self.group_pattern_edit.setPlaceholderText("Enter regex pattern to extract group identifiers")
        self.group_pattern_edit.setToolTip("Regex pattern to match groups in filenames.\nExample: r'g[123]' matches 'g1', 'g2', 'g3' in filenames")
        self.group_pattern_edit.setMaximumWidth(400)
        self.group_pattern_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.group_pattern_edit.textChanged.connect(self._validate_group_pattern)
        group_label = QLabel("Group Pattern:")
        group_label.setToolTip("Regex pattern for extracting group identifiers")
        form_layout.addRow(group_label, self.group_pattern_edit)

        layout.addLayout(form_layout)

        # Validation timer for real-time feedback
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_all_patterns)

        # Initialize auto-save timers for text field debouncing
        self._pattern_save_timer = QTimer()
        self._pattern_save_timer.setSingleShot(True)
        self._timepoint_save_timer = QTimer()
        self._timepoint_save_timer.setSingleShot(True)
        self._group_save_timer = QTimer()
        self._group_save_timer.setSingleShot(True)

        return group_box

    def _create_id_testing_section(self) -> QGroupBox:
        """Create the live ID testing section."""
        group_box = QGroupBox("Live ID Pattern Testing")
        layout = QVBoxLayout(group_box)

        # Description
        description_label = QLabel(
            "Test your regex patterns by entering a participant ID or filename. See real-time feedback about pattern matching and validation."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("QLabel { color: #666; font-style: italic; margin-bottom: 10px; }")
        layout.addWidget(description_label)

        # Input section
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Test ID:"))

        self.test_id_input = QLineEdit()
        self.test_id_input.setPlaceholderText("Enter ID or filename to test patterns...")
        self.test_id_input.textChanged.connect(self._update_id_test_results)
        input_layout.addWidget(self.test_id_input)

        layout.addLayout(input_layout)

        # Results display
        self.test_results_display = QTextEdit()
        self.test_results_display.setMaximumHeight(120)
        self.test_results_display.setReadOnly(True)
        self.test_results_display.setStyleSheet("""
            QTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #f8f9fa;
                font-family: monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.test_results_display)

        # Initialize with empty state
        self._update_id_test_results()

        return group_box

    def _create_study_parameters_section(self) -> QGroupBox:
        """Create the study parameters configuration section."""
        group_box = QGroupBox("Study Parameters")
        layout = QVBoxLayout(group_box)

        # Unknown Value Placeholder
        unknown_layout = QHBoxLayout()
        unknown_layout.addWidget(QLabel("Unknown Value Placeholder:"))

        self.unknown_value_edit = QLineEdit()
        self.unknown_value_edit.setPlaceholderText("Enter value to use when information cannot be extracted")
        self.unknown_value_edit.setToolTip("Text to display when participant information cannot be determined")
        self.unknown_value_edit.setMaximumWidth(200)
        self.unknown_value_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        unknown_layout.addWidget(self.unknown_value_edit)
        unknown_layout.addStretch()
        layout.addLayout(unknown_layout)

        return group_box

    def _create_valid_values_section(self) -> QGroupBox:
        """Create the valid groups and timepoints configuration section."""
        group_box = QGroupBox("Valid Groups and Timepoints")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QHBoxLayout(group_box)
        layout.setSpacing(20)

        # Valid Groups Section
        groups_layout = QVBoxLayout()
        groups_label = QLabel("<b>Valid Groups</b>")
        groups_label.setStyleSheet("QLabel { color: #2c3e50; margin-bottom: 5px; }")
        groups_layout.addWidget(groups_label)

        # Create help text
        groups_help = QLabel("Drag to reorder • Double-click to edit")
        groups_help.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; font-style: italic; }")
        groups_layout.addWidget(groups_help)

        self.valid_groups_list = DragDropListWidget()
        self.valid_groups_list.setMaximumHeight(120)
        self.valid_groups_list.setMinimumHeight(120)
        self.valid_groups_list.setToolTip(
            "Groups that are considered valid for this study.\n"
            "• Drag items to reorder\n"
            "• Double-click to edit\n"
            "• Used for validation and dropdown options"
        )
        self.valid_groups_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #3498db;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e8f4fd;
            }
        """)
        groups_layout.addWidget(self.valid_groups_list)

        # Groups action buttons
        groups_buttons_layout = QHBoxLayout()
        self.add_group_button = QPushButton("Add")
        self.add_group_button.clicked.connect(self._add_group)
        self.add_group_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)

        self.edit_group_button = QPushButton("Edit")
        self.edit_group_button.clicked.connect(self._edit_selected_group)
        self.edit_group_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5dade2;
            }
            QPushButton:pressed {
                background-color: #2980b9;
            }
        """)

        self.remove_group_button = QPushButton("Remove")
        self.remove_group_button.clicked.connect(self._remove_group)
        self.remove_group_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ec7063;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)

        groups_buttons_layout.addWidget(self.add_group_button)
        groups_buttons_layout.addWidget(self.edit_group_button)
        groups_buttons_layout.addWidget(self.remove_group_button)
        groups_buttons_layout.addStretch()
        groups_layout.addLayout(groups_buttons_layout)

        layout.addLayout(groups_layout)

        # Valid Timepoints Section
        timepoints_layout = QVBoxLayout()
        timepoints_label = QLabel("<b>Valid Timepoints</b>")
        timepoints_label.setStyleSheet("QLabel { color: #2c3e50; margin-bottom: 5px; }")
        timepoints_layout.addWidget(timepoints_label)

        # Create help text
        timepoints_help = QLabel("Drag to reorder • Double-click to edit")
        timepoints_help.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; font-style: italic; }")
        timepoints_layout.addWidget(timepoints_help)

        self.valid_timepoints_list = DragDropListWidget()
        self.valid_timepoints_list.setMaximumHeight(120)
        self.valid_timepoints_list.setMinimumHeight(120)
        self.valid_timepoints_list.setToolTip(
            "Timepoints that are considered valid for this study.\n"
            "• Drag items to reorder\n"
            "• Double-click to edit\n"
            "• Used for validation and dropdown options"
        )
        self.valid_timepoints_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #3498db;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e8f4fd;
            }
        """)
        timepoints_layout.addWidget(self.valid_timepoints_list)

        # Timepoints action buttons
        timepoints_buttons_layout = QHBoxLayout()
        self.add_timepoint_button = QPushButton("Add")
        self.add_timepoint_button.clicked.connect(self._add_timepoint)
        self.add_timepoint_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)

        self.edit_timepoint_button = QPushButton("Edit")
        self.edit_timepoint_button.clicked.connect(self._edit_selected_timepoint)
        self.edit_timepoint_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5dade2;
            }
            QPushButton:pressed {
                background-color: #2980b9;
            }
        """)

        self.remove_timepoint_button = QPushButton("Remove")
        self.remove_timepoint_button.clicked.connect(self._remove_timepoint)
        self.remove_timepoint_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ec7063;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)

        timepoints_buttons_layout.addWidget(self.add_timepoint_button)
        timepoints_buttons_layout.addWidget(self.edit_timepoint_button)
        timepoints_buttons_layout.addWidget(self.remove_timepoint_button)
        timepoints_buttons_layout.addStretch()
        timepoints_layout.addLayout(timepoints_buttons_layout)

        layout.addLayout(timepoints_layout)

        return group_box

    def _create_default_selection_section(self) -> QGroupBox:
        """Create the default selection section with intelligent dropdowns."""
        group_box = QGroupBox("Default Selection")
        layout = QHBoxLayout(group_box)

        # Default Group Selection
        group_layout = QVBoxLayout()
        group_layout.addWidget(QLabel("Default Group:"))

        self.default_group_combo = QComboBox()
        self.default_group_combo.setToolTip(
            "Default group to use when participant group cannot be determined from filename. Populated from valid groups defined above."
        )
        self.default_group_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.default_group_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.default_group_combo.setMinimumWidth(180)
        self.default_group_combo.currentTextChanged.connect(self._on_default_group_changed)
        group_layout.addWidget(self.default_group_combo)

        layout.addLayout(group_layout)

        # Default Timepoint Selection
        timepoint_layout = QVBoxLayout()
        timepoint_layout.addWidget(QLabel("Default Timepoint:"))

        self.default_timepoint_combo = QComboBox()
        self.default_timepoint_combo.setToolTip(
            "Default timepoint to use when participant timepoint cannot be determined from filename. Populated from valid timepoints defined above."
        )
        self.default_timepoint_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.default_timepoint_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.default_timepoint_combo.setMinimumWidth(180)
        self.default_timepoint_combo.currentTextChanged.connect(self._on_default_timepoint_changed)
        timepoint_layout.addWidget(self.default_timepoint_combo)

        layout.addLayout(timepoint_layout)

        # Add stretch to push everything to the left
        layout.addStretch()

        return group_box

    def _create_algorithm_configuration_section(self) -> QGroupBox:
        """Create the algorithm configuration section."""
        group_box = QGroupBox("Algorithm Configuration")
        layout = QVBoxLayout(group_box)
        layout.setSpacing(15)

        # Sadeh Variant Selection
        sadeh_layout = QVBoxLayout()

        sadeh_label = QLabel("<b>Sadeh Algorithm Variant:</b>")
        sadeh_label.setStyleSheet("QLabel { color: #2c3e50; margin-bottom: 5px; }")
        sadeh_layout.addWidget(sadeh_label)

        # Radio buttons
        self.sadeh_button_group = QButtonGroup(self)

        self.sadeh_original_radio = QRadioButton("Original Paper 1994 (threshold = 0)")
        self.sadeh_original_radio.setToolTip("Original Sadeh (1994) paper threshold. Use for cross-device comparisons or replication studies.")
        self.sadeh_button_group.addButton(self.sadeh_original_radio, 0)
        sadeh_layout.addWidget(self.sadeh_original_radio)

        self.sadeh_actilife_radio = QRadioButton("ActiLife (threshold = -4)")
        self.sadeh_actilife_radio.setToolTip("ActiGraph's ActiLife software threshold. Use for ActiGraph device data.")
        self.sadeh_button_group.addButton(self.sadeh_actilife_radio, 1)
        sadeh_layout.addWidget(self.sadeh_actilife_radio)

        # Explanation label
        sadeh_help = QLabel(
            "The original Sadeh (1994) paper used threshold = 0 for sleep/wake classification. "
            "ActiGraph's ActiLife software uses threshold = -4 to account for differences in activity "
            "count scaling between devices. Use ActiLife for ActiGraph data, Original for cross-device "
            "comparisons or replication studies."
        )
        sadeh_help.setWordWrap(True)
        sadeh_help.setStyleSheet(
            "QLabel { color: #7f8c8d; font-size: 11px; font-style: italic; "
            "background-color: #ecf0f1; padding: 8px; border-radius: 4px; border-left: 3px solid #3498db; }"
        )
        sadeh_layout.addWidget(sadeh_help)

        layout.addLayout(sadeh_layout)

        # Night Hours Configuration
        night_hours_layout = QVBoxLayout()

        night_hours_label = QLabel("<b>Night Hours Definition:</b>")
        night_hours_label.setStyleSheet("QLabel { color: #2c3e50; margin-bottom: 5px; }")
        night_hours_layout.addWidget(night_hours_label)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Start:"))

        self.night_start_time = QTimeEdit()
        self.night_start_time.setDisplayFormat("HH:mm")
        self.night_start_time.setToolTip("Start of night period (default: 22:00)")
        self.night_start_time.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        time_layout.addWidget(self.night_start_time)

        time_layout.addWidget(QLabel("End:"))

        self.night_end_time = QTimeEdit()
        self.night_end_time.setDisplayFormat("HH:mm")
        self.night_end_time.setToolTip("End of night period (default: 07:00)")
        self.night_end_time.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        time_layout.addWidget(self.night_end_time)

        time_layout.addStretch()
        night_hours_layout.addLayout(time_layout)

        # Info label
        night_help = QLabel("Used for night period classification in sleep analysis")
        night_help.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; font-style: italic; }")
        night_hours_layout.addWidget(night_help)

        layout.addLayout(night_hours_layout)

        # Choi Algorithm Axis Selection
        choi_layout = QVBoxLayout()

        choi_label = QLabel("<b>Choi Algorithm Axis (Nonwear Detection):</b>")
        choi_label.setStyleSheet("QLabel { color: #2c3e50; margin-bottom: 5px; }")
        choi_layout.addWidget(choi_label)

        choi_row = QHBoxLayout()
        self.choi_axis_combo = QComboBox()

        choi_axis_display_names = {
            ActivityDataPreference.VECTOR_MAGNITUDE: "Vector Magnitude (Recommended)",
            ActivityDataPreference.AXIS_Y: "Y-Axis (Vertical)",
            ActivityDataPreference.AXIS_X: "X-Axis (Lateral)",
            ActivityDataPreference.AXIS_Z: "Z-Axis (Forward)",
        }
        for axis in ActivityDataPreference:
            self.choi_axis_combo.addItem(choi_axis_display_names[axis], axis.value)

        self.choi_axis_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.choi_axis_combo.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        choi_row.addWidget(self.choi_axis_combo)
        choi_row.addStretch()
        choi_layout.addLayout(choi_row)

        # Info label
        choi_help = QLabel(
            "Select which activity axis the Choi nonwear detection algorithm should use. Vector Magnitude is recommended for most devices."
        )
        choi_help.setWordWrap(True)
        choi_help.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; font-style: italic; }")
        choi_layout.addWidget(choi_help)

        layout.addLayout(choi_layout)

        # Connect signals for auto-save
        self.sadeh_button_group.buttonClicked.connect(self._on_sadeh_variant_changed)
        self.night_start_time.timeChanged.connect(self._on_night_hours_changed)
        self.night_end_time.timeChanged.connect(self._on_night_hours_changed)
        self.choi_axis_combo.currentIndexChanged.connect(self._on_choi_axis_changed)

        return group_box

    def _create_action_buttons(self) -> QHBoxLayout:
        """Create the action buttons layout."""
        layout = QHBoxLayout()

        # Import/Export config buttons
        self.import_config_button = QPushButton("Import Config...")
        self.import_config_button.clicked.connect(self._import_config)
        self.import_config_button.setStyleSheet("QPushButton { padding: 8px; }")
        self.import_config_button.setToolTip("Import study configuration from a file")

        self.export_config_button = QPushButton("Export Config...")
        self.export_config_button.clicked.connect(self._export_config)
        self.export_config_button.setStyleSheet("QPushButton { padding: 8px; }")
        self.export_config_button.setToolTip("Export study configuration to share with collaborators")

        layout.addWidget(self.import_config_button)
        layout.addWidget(self.export_config_button)

        layout.addStretch()

        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self._apply_settings)
        self.apply_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")

        layout.addWidget(self.apply_button)

        return layout

    def _import_config(self) -> None:
        """Open the config import dialog."""
        from sleep_scoring_app.ui.config_dialog import ConfigImportDialog

        dialog = ConfigImportDialog(self, self.parent.config_manager)
        if dialog.exec() == ConfigImportDialog.DialogCode.Accepted:
            # Reload settings in UI after import
            self._load_current_settings()

    def _export_config(self) -> None:
        """Open the config export dialog."""
        from sleep_scoring_app.ui.config_dialog import ConfigExportDialog

        dialog = ConfigExportDialog(self, self.parent.config_manager)
        dialog.exec()

    def _load_current_settings(self) -> None:
        """Load current settings from configuration."""
        try:
            config = self.parent.config_manager.config

            # Set unknown value
            self.unknown_value_edit.setText(config.study_unknown_value)

            # Load valid groups
            self.valid_groups_list.clear()
            for group in config.study_valid_groups:
                self.valid_groups_list.addItem(group)

            # Load valid timepoints
            self.valid_timepoints_list.clear()
            for timepoint in config.study_valid_timepoints:
                self.valid_timepoints_list.addItem(timepoint)

            # Update default dropdowns after loading the lists
            self._update_group_dropdown()
            self._update_timepoint_dropdown()

            # Set default group selection (only if it's a real value, not empty)
            current_group = config.study_default_group
            if current_group:
                group_index = self.default_group_combo.findText(current_group)
                if group_index >= 0:
                    self.default_group_combo.setCurrentIndex(group_index)
                # If not found, keep placeholder selected

            # Set default timepoint selection (only if it's a real value, not empty)
            current_timepoint = config.study_default_timepoint
            if current_timepoint:
                timepoint_index = self.default_timepoint_combo.findText(current_timepoint)
                if timepoint_index >= 0:
                    self.default_timepoint_combo.setCurrentIndex(timepoint_index)
                # If not found, keep placeholder selected

            # Load regex patterns
            if hasattr(config, "study_participant_id_patterns") and config.study_participant_id_patterns:
                # Use the first ID pattern as the primary one
                self.id_pattern_edit.setText(config.study_participant_id_patterns[0])

            # Load basic patterns from config (no defaults unless user set them)
            self.timepoint_pattern_edit.setText(config.study_timepoint_pattern)
            self.group_pattern_edit.setText(config.study_group_pattern)

            # Validate all patterns after loading
            self._validate_all_patterns()

            # Load algorithm configuration
            if hasattr(self, "sadeh_actilife_radio"):
                if config.sadeh_variant == SadehVariant.ACTILIFE:
                    self.sadeh_actilife_radio.setChecked(True)
                else:
                    self.sadeh_original_radio.setChecked(True)

                # Block signals during load to prevent save-on-load feedback loop
                self.night_start_time.blockSignals(True)
                self.night_end_time.blockSignals(True)
                self.night_start_time.setTime(QTime(config.night_start_hour, 0))
                self.night_end_time.setTime(QTime(config.night_end_hour, 0))
                self.night_start_time.blockSignals(False)
                self.night_end_time.blockSignals(False)

            # Load Choi axis setting
            if hasattr(self, "choi_axis_combo"):
                current_axis = config.choi_axis
                for i in range(self.choi_axis_combo.count()):
                    if self.choi_axis_combo.itemData(i) == current_axis:
                        self.choi_axis_combo.setCurrentIndex(i)
                        break

            logger.debug("Study settings loaded from configuration")

        except Exception as e:
            logger.exception("Error loading study settings: %s", e)
            QMessageBox.warning(self, "Configuration Error", f"Error loading study settings: {e}")

    def _update_group_dropdown(self) -> None:
        """Update the default group dropdown with current list values."""
        current_selection = self.default_group_combo.currentText()
        self.default_group_combo.clear()

        # Get current items from the list
        items = self.valid_groups_list.get_all_items()
        if items:
            # Add placeholder option first
            self.default_group_combo.addItem("-- Select Default Group --")
            self.default_group_combo.addItems(items)

            # Try to restore previous selection (skip placeholder)
            index = self.default_group_combo.findText(current_selection)
            if index > 0:  # Must be greater than 0 to skip placeholder
                self.default_group_combo.setCurrentIndex(index)
            else:
                # Keep placeholder selected - don't auto-select first real item
                self.default_group_combo.setCurrentIndex(0)
        else:
            # Add placeholder when no items (keep enabled so user knows they need to add groups)
            self.default_group_combo.addItem("-- No groups defined --")
            # Keep enabled so user can see that they need to add groups

    def _update_timepoint_dropdown(self) -> None:
        """Update the default timepoint dropdown with current list values."""
        current_selection = self.default_timepoint_combo.currentText()
        self.default_timepoint_combo.clear()

        # Get current items from the list
        items = self.valid_timepoints_list.get_all_items()
        if items:
            # Add placeholder option first
            self.default_timepoint_combo.addItem("-- Select Default Timepoint --")
            self.default_timepoint_combo.addItems(items)

            # Try to restore previous selection (skip placeholder)
            index = self.default_timepoint_combo.findText(current_selection)
            if index > 0:  # Must be greater than 0 to skip placeholder
                self.default_timepoint_combo.setCurrentIndex(index)
            else:
                # Keep placeholder selected - don't auto-select first real item
                self.default_timepoint_combo.setCurrentIndex(0)
        else:
            # Add placeholder when no items (keep enabled so user knows they need to add timepoints)
            self.default_timepoint_combo.addItem("-- No timepoints defined --")
            # Keep enabled so user can see that they need to add timepoints

    def _update_default_group_dropdown(self, groups: list[str]) -> None:
        """Update the default group dropdown when groups change via signal."""
        self._update_group_dropdown()

    def _update_default_timepoint_dropdown(self, timepoints: list[str]) -> None:
        """Update the default timepoint dropdown when timepoints change via signal."""
        self._update_timepoint_dropdown()

    def _edit_selected_group(self) -> None:
        """Edit the currently selected group."""
        current_item = self.valid_groups_list.currentItem()
        if current_item:
            self.valid_groups_list._edit_item(current_item)
        else:
            QMessageBox.information(self, "No Selection", "Please select a group to edit.")

    def _edit_selected_timepoint(self) -> None:
        """Edit the currently selected timepoint."""
        current_item = self.valid_timepoints_list.currentItem()
        if current_item:
            self.valid_timepoints_list._edit_item(current_item)
        else:
            QMessageBox.information(self, "No Selection", "Please select a timepoint to edit.")

    def _add_group(self) -> None:
        """Add a new group to the valid groups list with enhanced validation."""
        text, ok = QInputDialog.getText(
            self,
            "Add Group",
            "Enter group name (e.g., G1, G2, etc.):",
            text="G",
        )

        if ok and text.strip():
            group_text = text.strip().upper()

            # Enhanced validation
            if not group_text:
                QMessageBox.warning(self, "Invalid Input", "Group name cannot be empty.")
                return

            if len(group_text) > 10:
                QMessageBox.warning(self, "Invalid Input", "Group name is too long (max 10 characters).")
                return

            success = self.valid_groups_list.add_item_with_validation(group_text)
            if success:
                logger.debug("Added group: %s", group_text)
                # Signal is automatically emitted by DragDropListWidget
            else:
                QMessageBox.information(self, "Duplicate Group", f"Group '{group_text}' already exists.")

    def _remove_group(self) -> None:
        """Remove selected group from the valid groups list with confirmation."""
        current_row = self.valid_groups_list.currentRow()
        if current_row >= 0:
            item = self.valid_groups_list.item(current_row)
            if item:
                # Confirm removal
                reply = QMessageBox.question(
                    self,
                    "Confirm Removal",
                    f"Are you sure you want to remove group '{item.text()}'?\n\n⚠️  This may cause configuration validation to fail if no groups remain.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    removed_item = self.valid_groups_list.takeItem(current_row)
                    if removed_item:
                        logger.debug("Removed group: %s", removed_item.text())
                        # Explicitly emit signal since takeItem() might not trigger model signals
                        self.valid_groups_list.items_changed.emit()
        else:
            QMessageBox.information(self, "No Selection", "Please select a group to remove.")

    def _add_timepoint(self) -> None:
        """Add a new timepoint to the valid timepoints list with enhanced validation."""
        text, ok = QInputDialog.getText(
            self,
            "Add Timepoint",
            "Enter timepoint name (e.g., BO, P1, P2, etc.):",
            text="P",
        )

        if ok and text.strip():
            timepoint_text = text.strip().upper()

            # Enhanced validation
            if not timepoint_text:
                QMessageBox.warning(self, "Invalid Input", "Timepoint name cannot be empty.")
                return

            if len(timepoint_text) > 10:
                QMessageBox.warning(self, "Invalid Input", "Timepoint name is too long (max 10 characters).")
                return

            success = self.valid_timepoints_list.add_item_with_validation(timepoint_text)
            if success:
                logger.debug("Added timepoint: %s", timepoint_text)
                # Signal is automatically emitted by DragDropListWidget
            else:
                QMessageBox.information(self, "Duplicate Timepoint", f"Timepoint '{timepoint_text}' already exists.")

    def _remove_timepoint(self) -> None:
        """Remove selected timepoint from the valid timepoints list with confirmation."""
        current_row = self.valid_timepoints_list.currentRow()
        if current_row >= 0:
            item = self.valid_timepoints_list.item(current_row)
            if item:
                # Confirm removal
                reply = QMessageBox.question(
                    self,
                    "Confirm Removal",
                    f"Are you sure you want to remove timepoint '{item.text()}'?\n\n⚠️  This may cause configuration validation to fail if no timepoints remain.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    removed_item = self.valid_timepoints_list.takeItem(current_row)
                    if removed_item:
                        logger.debug("Removed timepoint: %s", removed_item.text())
                        # Explicitly emit signal since takeItem() might not trigger model signals
                        self.valid_timepoints_list.items_changed.emit()
        else:
            QMessageBox.information(self, "No Selection", "Please select a timepoint to remove.")

    @pyqtSlot(str)
    def _on_default_group_changed(self, text: str) -> None:
        """Handle default group selection changes."""
        # Skip placeholder selections
        if text and not text.startswith("--"):
            try:
                # Immediately save to config when changed
                self.parent.config_manager.update_study_settings(default_group=text)
                logger.debug("Default group changed to: %s", text)
            except Exception as e:
                logger.exception("Error saving default group: %s", e)

    @pyqtSlot(str)
    def _on_default_timepoint_changed(self, text: str) -> None:
        """Handle default timepoint selection changes."""
        # Skip placeholder selections
        if text and not text.startswith("--"):
            try:
                # Immediately save to config when changed
                self.parent.config_manager.update_study_settings(default_timepoint=text)
                logger.debug("Default timepoint changed to: %s", text)
            except Exception as e:
                logger.exception("Error saving default timepoint: %s", e)

    def _apply_settings(self) -> None:
        """Apply the current settings to configuration."""
        try:
            # Get current values
            default_group = self.default_group_combo.currentText()
            default_timepoint = self.default_timepoint_combo.currentText()
            unknown_value = self.unknown_value_edit.text().strip()

            # Get valid groups and timepoints using the new list methods
            valid_groups = self.valid_groups_list.get_all_items()
            valid_timepoints = self.valid_timepoints_list.get_all_items()

            # STRICT VALIDATION - All fields must be properly configured
            validation_errors = []

            if not valid_groups:
                validation_errors.append("• At least one valid group must be specified.")

            if not valid_timepoints:
                validation_errors.append("• At least one valid timepoint must be specified.")

            if not unknown_value:
                validation_errors.append("• Unknown value placeholder must be specified.")

            # Get regex patterns
            id_pattern = self.id_pattern_edit.text().strip()
            timepoint_pattern = self.timepoint_pattern_edit.text().strip()
            group_pattern = self.group_pattern_edit.text().strip()

            # Require at least ID pattern for participant extraction
            if not id_pattern:
                validation_errors.append("• ID pattern is required for participant extraction.")

            # Validate regex patterns before saving
            if id_pattern:
                try:
                    re.compile(id_pattern)
                except re.error as e:
                    validation_errors.append(f"• ID Pattern invalid: {e}")

            if timepoint_pattern:
                try:
                    re.compile(timepoint_pattern)
                except re.error as e:
                    validation_errors.append(f"• Timepoint Pattern invalid: {e}")

            if group_pattern:
                try:
                    re.compile(group_pattern)
                except re.error as e:
                    validation_errors.append(f"• Group Pattern invalid: {e}")

            # Validate default selections (skip placeholder texts)
            if not default_group or default_group.startswith("--"):
                validation_errors.append("• Default group must be selected from valid groups.")

            if not default_timepoint or default_timepoint.startswith("--"):
                validation_errors.append("• Default timepoint must be selected from valid timepoints.")

            # Check that defaults are in the valid lists (only if they're real selections)
            if default_group and not default_group.startswith("--") and default_group not in valid_groups:
                validation_errors.append(f"• Default group '{default_group}' is not in the valid groups list.")

            if default_timepoint and not default_timepoint.startswith("--") and default_timepoint not in valid_timepoints:
                validation_errors.append(f"• Default timepoint '{default_timepoint}' is not in the valid timepoints list.")

            # Show all validation errors at once
            if validation_errors:
                error_message = "Configuration is incomplete. Please fix the following issues:\n\n" + "\n".join(validation_errors)
                error_message += "\n\n⚠️  All fields must be properly configured to ensure reliable participant extraction."
                QMessageBox.warning(self, "Configuration Incomplete", error_message)
                return

            # Prepare participant ID patterns list - NO FALLBACKS, only user-defined patterns
            participant_id_patterns = []
            if id_pattern:
                participant_id_patterns.append(id_pattern)

            # Update configuration
            self.parent.config_manager.update_study_settings(
                default_group=default_group,
                default_timepoint=default_timepoint,
                valid_groups=valid_groups,
                valid_timepoints=valid_timepoints,
                unknown_value=unknown_value,
                group_pattern=group_pattern,
                timepoint_pattern=timepoint_pattern,
                participant_id_patterns=participant_id_patterns,
            )

            QMessageBox.information(self, "Settings Applied", "Study settings have been saved successfully.")
            logger.info("Study settings applied successfully")

        except Exception as e:
            logger.exception("Error applying study settings: %s", e)
            QMessageBox.critical(self, "Error", f"Error applying study settings: {e}")

    # ============================================================================
    # AUTO-SAVE METHODS FOR GUI ELEMENTS
    # ============================================================================

    def _save_valid_groups(self) -> None:
        """Auto-save valid groups list to config when changed."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                valid_groups = self.valid_groups_list.get_all_items()
                self.parent.config_manager.update_study_settings(valid_groups=valid_groups)
                logger.debug("Auto-saved valid groups: %s", valid_groups)
        except Exception as e:
            logger.exception("Error auto-saving valid groups: %s", e)

    def _emit_groups_changed(self) -> None:
        """Emit groups changed signal (helper to avoid lambda memory leak)."""
        self.groups_changed.emit(self.valid_groups_list.get_all_items())

    def _emit_timepoints_changed(self) -> None:
        """Emit timepoints changed signal (helper to avoid lambda memory leak)."""
        self.timepoints_changed.emit(self.valid_timepoints_list.get_all_items())

    def _save_valid_timepoints(self) -> None:
        """Auto-save valid timepoints list to config when changed."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                valid_timepoints = self.valid_timepoints_list.get_all_items()
                self.parent.config_manager.update_study_settings(valid_timepoints=valid_timepoints)
                logger.debug("Auto-saved valid timepoints: %s", valid_timepoints)
        except Exception as e:
            logger.exception("Error auto-saving valid timepoints: %s", e)

    @pyqtSlot()
    def _on_unknown_value_changed(self) -> None:
        """Handle unknown value text field changes with debounced auto-save."""
        # Use the existing validation timer for debouncing
        self.validation_timer.stop()
        try:
            self.validation_timer.timeout.disconnect()
        except TypeError:
            pass  # No connections to disconnect
        self.validation_timer.timeout.connect(self._save_unknown_value)
        self.validation_timer.start(1000)  # 1 second debounce

    def _save_unknown_value(self) -> None:
        """Auto-save unknown value to config."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                unknown_value = self.unknown_value_edit.text().strip()
                self.parent.config_manager.update_study_settings(unknown_value=unknown_value)
                logger.debug("Auto-saved unknown value: %s", unknown_value)
        except Exception as e:
            logger.exception("Error auto-saving unknown value: %s", e)
        finally:
            # Reconnect the validation timeout
            try:
                self.validation_timer.timeout.disconnect()
            except TypeError:
                pass  # No connections to disconnect
            self.validation_timer.timeout.connect(self._validate_all_patterns)

    @pyqtSlot()
    def _on_id_pattern_changed(self) -> None:
        """Handle ID pattern text field changes with debounced auto-save."""
        self._pattern_save_timer.stop()
        try:
            self._pattern_save_timer.timeout.disconnect()
        except TypeError:
            pass  # No connections to disconnect
        self._pattern_save_timer.timeout.connect(self._save_id_pattern)
        self._pattern_save_timer.start(1000)  # 1 second debounce

    def _save_id_pattern(self) -> None:
        """Auto-save ID pattern to config."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                id_pattern = self.id_pattern_edit.text().strip()
                # Save as participant_id_patterns list
                participant_id_patterns = [id_pattern] if id_pattern else []
                self.parent.config_manager.update_study_settings(participant_id_patterns=participant_id_patterns)
                logger.debug("Auto-saved ID pattern: %s", id_pattern)
        except Exception as e:
            logger.exception("Error auto-saving ID pattern: %s", e)

    @pyqtSlot()
    def _on_timepoint_pattern_changed(self) -> None:
        """Handle timepoint pattern text field changes with debounced auto-save."""
        self._timepoint_save_timer.stop()
        try:
            self._timepoint_save_timer.timeout.disconnect()
        except TypeError:
            pass  # No connections to disconnect
        self._timepoint_save_timer.timeout.connect(self._save_timepoint_pattern)
        self._timepoint_save_timer.start(1000)  # 1 second debounce

    def _save_timepoint_pattern(self) -> None:
        """Auto-save timepoint pattern to config."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                timepoint_pattern = self.timepoint_pattern_edit.text().strip()
                self.parent.config_manager.update_study_settings(timepoint_pattern=timepoint_pattern)
                logger.debug("Auto-saved timepoint pattern: %s", timepoint_pattern)
        except Exception as e:
            logger.exception("Error auto-saving timepoint pattern: %s", e)

    @pyqtSlot()
    def _on_group_pattern_changed(self) -> None:
        """Handle group pattern text field changes with debounced auto-save."""
        self._group_save_timer.stop()
        try:
            self._group_save_timer.timeout.disconnect()
        except TypeError:
            pass  # No connections to disconnect
        self._group_save_timer.timeout.connect(self._save_group_pattern)
        self._group_save_timer.start(1000)  # 1 second debounce

    def _save_group_pattern(self) -> None:
        """Auto-save group pattern to config."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                group_pattern = self.group_pattern_edit.text().strip()
                self.parent.config_manager.update_study_settings(group_pattern=group_pattern)
                logger.debug("Auto-saved group pattern: %s", group_pattern)
        except Exception as e:
            logger.exception("Error auto-saving group pattern: %s", e)

    # ============================================================================
    # REGEX PATTERN VALIDATION METHODS
    # ============================================================================

    def _validate_pattern(self, pattern: str, line_edit: QLineEdit, pattern_type: str) -> bool:
        """
        Validate a regex pattern and provide visual feedback.

        Args:
            pattern: The regex pattern to validate
            line_edit: The QLineEdit widget containing the pattern
            pattern_type: Type of pattern for error messages

        Returns:
            True if pattern is valid, False otherwise

        """
        if not pattern.strip():
            # Empty pattern - neutral styling
            line_edit.setStyleSheet("")
            line_edit.setToolTip(f"{pattern_type} pattern (empty)")
            return True

        try:
            # Test compile the regex
            re.compile(pattern)

            # Valid pattern - green border
            line_edit.setStyleSheet("QLineEdit { border: 2px solid #4CAF50; background-color: #f0fff0; }")
            line_edit.setToolTip(f"{pattern_type} pattern - Valid regex")
            return True

        except re.error as e:
            # Invalid pattern - red border
            line_edit.setStyleSheet("QLineEdit { border: 2px solid #f44336; background-color: #fff0f0; }")
            line_edit.setToolTip(f"{pattern_type} pattern - Invalid regex: {e}")
            return False

    def _validate_id_pattern(self) -> None:
        """Validate the ID pattern with debounced timing."""
        self.validation_timer.start(300)  # 300ms debounce

    def _validate_timepoint_pattern(self) -> None:
        """Validate the timepoint pattern with debounced timing."""
        self.validation_timer.start(300)  # 300ms debounce

    def _validate_group_pattern(self) -> None:
        """Validate the group pattern with debounced timing."""
        self.validation_timer.start(300)  # 300ms debounce

    def _validate_all_patterns(self) -> None:
        """Validate all regex patterns and update visual feedback."""
        try:
            # Validate each pattern
            self._validate_pattern(self.id_pattern_edit.text(), self.id_pattern_edit, "ID")

            self._validate_pattern(self.timepoint_pattern_edit.text(), self.timepoint_pattern_edit, "Timepoint")

            self._validate_pattern(self.group_pattern_edit.text(), self.group_pattern_edit, "Group")

            # Update live test results when patterns change
            if hasattr(self, "test_id_input"):
                self._update_id_test_results()

        except Exception as e:
            logger.exception("Error validating patterns: %s", e)

    def _update_config_patterns_for_testing(self) -> None:
        """Temporarily update config patterns for live testing without saving."""
        try:
            # Get current patterns from UI
            id_pattern = self.id_pattern_edit.text().strip()
            timepoint_pattern = self.timepoint_pattern_edit.text().strip()
            group_pattern = self.group_pattern_edit.text().strip()

            # Get current validation lists
            valid_groups = self.valid_groups_list.get_all_items() if hasattr(self, "valid_groups_list") else []
            valid_timepoints = self.valid_timepoints_list.get_all_items() if hasattr(self, "valid_timepoints_list") else []
            default_group = self.default_group_combo.currentText() if hasattr(self, "default_group_combo") else "Unknown"
            default_timepoint = self.default_timepoint_combo.currentText() if hasattr(self, "default_timepoint_combo") else "Unknown"

            # Temporarily update config for testing (doesn't save to disk)
            config = self.parent.config_manager.config

            # If config is None, create a temporary one for testing
            if config is None:
                from sleep_scoring_app.core.dataclasses import AppConfig

                config = AppConfig.create_default()
                # Store it temporarily in the config manager
                self.parent.config_manager.config = config

            # Update patterns if they're provided
            if id_pattern:
                config.study_participant_id_patterns = [id_pattern]
            if timepoint_pattern:
                config.study_timepoint_pattern = timepoint_pattern
            if group_pattern:
                config.study_group_pattern = group_pattern

            # Update validation lists
            if valid_groups:
                config.study_valid_groups = valid_groups
            if valid_timepoints:
                config.study_valid_timepoints = valid_timepoints
            if default_group:
                config.study_default_group = default_group
            if default_timepoint:
                config.study_default_timepoint = default_timepoint

            # Pattern cache invalidation is no longer needed - extraction is now stateless

        except Exception as e:
            logger.exception("Error updating config patterns for testing: %s", e)

    def _update_id_test_results(self) -> None:
        """Update the live ID test results display using actual extract_participant_info."""
        try:
            if not hasattr(self, "test_results_display"):
                return

            test_input = self.test_id_input.text().strip() if hasattr(self, "test_id_input") else ""

            if not test_input:
                self.test_results_display.setHtml("""
                    <div style="color: #666; font-style: italic;">
                        Enter an ID or filename above to see extraction results...
                    </div>
                """)
                return

            # First, update the config with current patterns to test them live
            self._update_config_patterns_for_testing()

            # Use function-based extraction for testing
            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            try:
                # Get the current config (should be updated by _update_config_patterns_for_testing)
                config = self.parent.config_manager.config

                # Test with new function-based approach
                participant_info = extract_participant_info(test_input, config)

                # Get current validation lists
                valid_groups = self.valid_groups_list.get_all_items() if hasattr(self, "valid_groups_list") else []
                valid_timepoints = self.valid_timepoints_list.get_all_items() if hasattr(self, "valid_timepoints_list") else []
                default_group = self.default_group_combo.currentText() if hasattr(self, "default_group_combo") else "Unknown"
                default_timepoint = self.default_timepoint_combo.currentText() if hasattr(self, "default_timepoint_combo") else "Unknown"

                results_html = f"""
                    <div style="font-family: monospace; font-size: 12px;">
                        <b>Test ID:</b> "{test_input}"<br><br>
                        <b>Extraction Results:</b><br>
                """

                # ID result
                id_value = participant_info.numerical_id
                if id_value and id_value not in (default_group, "Unknown"):
                    color = "#28a745"  # green
                    icon = "✓"
                    status = f'"{id_value}" (matched pattern)'
                else:
                    color = "#dc3545"  # red
                    icon = "✗"
                    status = "not extracted"

                results_html += f"""
                    <span style="color: {color};">{icon} ID:</span> {status}<br>
                """

                # Group result
                group_value = participant_info.group
                if group_value.upper() in [g.upper() for g in valid_groups]:
                    color = "#28a745"  # green
                    icon = "✓"
                    status = f'"{group_value}" (✓ valid group)'
                elif group_value == default_group:
                    color = "#ffc107"  # yellow
                    icon = "⚠"
                    status = f'"{group_value}" (⚠ Could not extract group from input, using default value)'
                else:
                    color = "#ffc107"  # yellow
                    icon = "⚠"
                    status = f'"{group_value}" (✗ Could not extract group from input, using default value)'

                results_html += f"""
                    <span style="color: {color};">{icon} Group:</span> {status}<br>
                """

                # Timepoint result
                timepoint_value = participant_info.timepoint
                if timepoint_value.upper() in [tp.upper() for tp in valid_timepoints]:
                    color = "#28a745"  # green
                    icon = "✓"
                    status = f'"{timepoint_value}" (✓ valid timepoint)'
                elif timepoint_value == default_timepoint:
                    color = "#ffc107"  # yellow
                    icon = "⚠"
                    status = f'"{timepoint_value}" (⚠ Could not extract timepoint from input, using default value)'
                else:
                    color = "#ffc107"  # yellow
                    icon = "⚠"
                    status = f'"{timepoint_value}" (✗ Could not extract timepoint from input, using default value)'

                results_html += f"""
                    <span style="color: {color};">{icon} Timepoint:</span> {status}<br><br>
                """

                # Summary based on confidence
                confidence = participant_info.confidence
                if confidence >= 0.8:
                    summary_color = "#28a745"
                    summary_icon = "✓"
                    summary_text = f"High confidence extraction ({confidence:.1%})"
                elif confidence >= 0.5:
                    summary_color = "#ffc107"
                    summary_icon = "⚠"
                    summary_text = f"Medium confidence extraction ({confidence:.1%})"
                else:
                    summary_color = "#dc3545"
                    summary_icon = "✗"
                    summary_text = f"Low confidence extraction ({confidence:.1%})"

                results_html += f"""
                    <b><span style="color: {summary_color};">{summary_icon} Overall:</span></b> {summary_text}
                """

                results_html += "</div>"

            except Exception as extract_error:
                # Show extraction error
                results_html = f"""
                    <div style="color: #dc3545; font-family: monospace; font-size: 12px;">
                        <b>Extraction Error:</b><br>
                        {extract_error}
                    </div>
                """

            self.test_results_display.setHtml(results_html)

        except Exception as e:
            logger.exception("Error updating ID test results: %s", e)
            if hasattr(self, "test_results_display"):
                self.test_results_display.setHtml(f"""
                    <div style="color: #dc3545;">
                        Error testing patterns: {e}
                    </div>
                """)

    def _reset_patterns_to_defaults(self) -> None:
        """Reset all regex patterns to their default values."""
        reply = QMessageBox.question(
            self,
            "Reset Patterns",
            "Are you sure you want to reset all regex patterns to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Set default patterns
                self.id_pattern_edit.setText(r"^(\d{4,})[_-]")
                self.timepoint_pattern_edit.setText(r"([A-Z0-9]+)")
                self.group_pattern_edit.setText(r"g[123]")

                # Validate all patterns
                self._validate_all_patterns()

                logger.debug("Regex patterns reset to defaults")

            except Exception as e:
                logger.exception("Error resetting patterns: %s", e)
                QMessageBox.critical(self, "Error", f"Error resetting patterns: {e}")

    def _on_sadeh_variant_changed(self) -> None:
        """Handle Sadeh variant radio button changes."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                if self.sadeh_actilife_radio.isChecked():
                    variant = SadehVariant.ACTILIFE
                else:
                    variant = SadehVariant.ORIGINAL

                self.parent.config_manager.config.sadeh_variant = variant
                self.parent.config_manager.save_config()
                logger.debug("Auto-saved Sadeh variant: %s", variant)

                # Clear algorithm cache and trigger recalculation
                if hasattr(self.parent, "plot_widget") and self.parent.plot_widget:
                    pw = self.parent.plot_widget
                    if hasattr(pw, "algorithm_manager"):
                        pw.algorithm_manager._algorithm_cache.clear()
                        pw.algorithm_manager.plot_algorithms()
                    # Reapply sleep scoring rules if markers exist
                    if hasattr(pw, "marker_renderer") and hasattr(pw, "daily_sleep_markers"):
                        selected = pw.get_selected_marker_period()
                        if selected and selected.is_complete:
                            pw.algorithm_manager.apply_sleep_scoring_rules(selected)
                    pw.update()
                    logger.info("Recalculated Sadeh algorithm with new threshold")
        except Exception as e:
            logger.exception("Error auto-saving Sadeh variant: %s", e)

    def _on_night_hours_changed(self) -> None:
        """Handle night hours time changes."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                start_hour = self.night_start_time.time().hour()
                end_hour = self.night_end_time.time().hour()

                self.parent.config_manager.config.night_start_hour = start_hour
                self.parent.config_manager.config.night_end_hour = end_hour
                self.parent.config_manager.save_config()
                logger.debug("Auto-saved night hours: %d:00 - %d:00", start_hour, end_hour)
        except Exception as e:
            logger.exception("Error auto-saving night hours: %s", e)

    def _on_choi_axis_changed(self, index: int) -> None:
        """Handle Choi axis selection change."""
        try:
            if self.parent and self.parent.config_manager and self.parent.config_manager.config:
                axis = self.choi_axis_combo.itemData(index)
                self.parent.config_manager.config.choi_axis = axis
                self.parent.config_manager.save_config()
                logger.info("Choi algorithm axis changed to: %s", axis)

                # Load the correct column data for Choi and recalculate
                if hasattr(self.parent, "plot_widget") and self.parent.plot_widget:
                    pw = self.parent.plot_widget

                    # Clear caches
                    if hasattr(pw, "algorithm_manager"):
                        pw.algorithm_manager._algorithm_cache.clear()
                    if hasattr(pw, "clear_choi_cache"):
                        pw.clear_choi_cache()

                    # Load data for the selected axis column from database
                    choi_data = None
                    if hasattr(self.parent, "data_service") and hasattr(self.parent, "current_file_info"):
                        filename = self.parent.current_file_info.get("filename") if self.parent.current_file_info else None
                        current_date = (
                            self.parent.available_dates[self.parent.current_date_index]
                            if hasattr(self.parent, "current_date_index") and self.parent.available_dates
                            else None
                        )
                        if filename and current_date:
                            result = self.parent.data_service.data_manager.load_activity_data_only(
                                filename, current_date, activity_column=axis, hours=48
                            )
                            if result:
                                _, choi_data = result
                                logger.info("Loaded %d points for Choi column %s", len(choi_data), axis)

                    # Use loaded data or fall back to current activity_data
                    data_for_choi = choi_data if choi_data else getattr(pw, "activity_data", None)
                    if data_for_choi and hasattr(pw, "update_choi_overlay_only"):
                        pw.update_choi_overlay_only(data_for_choi)

                    pw.update()
                    logger.info("Recalculated Choi algorithm with new activity column: %s", axis)
        except Exception as e:
            logger.exception("Error saving Choi axis setting: %s", e)
