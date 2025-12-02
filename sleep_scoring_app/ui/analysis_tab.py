#!/usr/bin/env python3
"""
Analysis Tab Component
Contains the main analysis interface with plots and controls.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable
from sleep_scoring_app.ui.widgets.popout_table_window import PopOutTableWindow
from sleep_scoring_app.utils.thread_safety import ensure_main_thread

if TYPE_CHECKING:
    from sleep_scoring_app.ui.main_window import SleepScoringMainWindow
from sleep_scoring_app.core.constants import (
    ActivityDataPreference,
    ButtonStyle,
    ButtonText,
    TooltipText,
    UIColors,
)
from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget
from sleep_scoring_app.ui.widgets.analysis_dialogs import AnalysisDialogManager
from sleep_scoring_app.utils.table_helpers import create_marker_data_table

logger = logging.getLogger(__name__)


class DiaryTableColumn(StrEnum):
    """Diary table column identifiers."""

    DATE = "date"
    BEDTIME = "bedtime"
    WAKE_TIME = "wake_time"
    SLEEP_ONSET = "sleep_onset"
    SLEEP_OFFSET = "sleep_offset"
    NAP_OCCURRED = "nap_occurred"
    NAP_1_START = "nap_1_start"
    NAP_1_END = "nap_1_end"
    NAP_2_START = "nap_2_start"
    NAP_2_END = "nap_2_end"
    NAP_3_START = "nap_3_start"
    NAP_3_END = "nap_3_end"
    NONWEAR_OCCURRED = "nonwear_occurred"
    NONWEAR_1_START = "nonwear_1_start"
    NONWEAR_1_END = "nonwear_1_end"
    NONWEAR_1_REASON = "nonwear_1_reason"
    NONWEAR_2_START = "nonwear_2_start"
    NONWEAR_2_END = "nonwear_2_end"
    NONWEAR_2_REASON = "nonwear_2_reason"
    NONWEAR_3_START = "nonwear_3_start"
    NONWEAR_3_END = "nonwear_3_end"
    NONWEAR_3_REASON = "nonwear_3_reason"


@dataclass
class DiaryColumnDefinition:
    """Definition for a diary table column."""

    id: DiaryTableColumn
    header: str
    width_mode: QHeaderView.ResizeMode
    width_hint: int | None = None
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter


class AnalysisTab(QWidget):
    """Analysis Tab containing the main analysis interface."""

    def __init__(self, parent: "SleepScoringMainWindow") -> None:
        super().__init__(parent)
        self.parent = parent  # Reference to main window

        # Pop-out table windows
        self.onset_popout_window: PopOutTableWindow | None = None
        self.offset_popout_window: PopOutTableWindow | None = None

        # Dialog manager for shortcuts and color settings
        self.dialog_manager = AnalysisDialogManager(self)

        self.setup_ui()

    def setup_ui(self) -> None:
        """Create the analysis tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area for the entire content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # Remove frame for cleaner look

        # Create content widget that will be scrollable
        content_widget = QWidget()
        content_widget.setMinimumHeight(1000)  # Force minimum height to ensure scrollbar appears
        content_layout = QVBoxLayout(content_widget)

        # Activity plot (create first so control panel can reference it)
        self.plot_widget = ActivityPlotWidget(parent=self.parent)
        # Store direct reference to main_window for config access
        self.plot_widget.main_window = self.parent
        # Connect sleep markers signal only if parent has the handler
        if hasattr(self.parent, "handle_sleep_markers_changed"):
            self.plot_widget.sleep_markers_changed.connect(self.parent.handle_sleep_markers_changed)
        else:
            logger.warning("Parent does not have handle_sleep_markers_changed method")

        # Create top-level vertical splitter to separate file selection from plot area
        top_level_splitter = QSplitter(Qt.Orientation.Vertical)

        # File selection bar
        file_bar = self._create_file_selection_bar()
        top_level_splitter.addWidget(file_bar)

        # Create widget for navigation, controls, and plot area
        plot_area_widget = QWidget()
        plot_area_layout = QVBoxLayout(plot_area_widget)
        plot_area_layout.setContentsMargins(0, 0, 0, 0)

        # Date navigation bar (centered)
        date_bar = self._create_date_navigation_bar()
        plot_area_layout.addWidget(date_bar)

        # Control bar (view mode and manual times)
        control_bar = self._create_control_bar()
        plot_area_layout.addWidget(control_bar)

        # Create vertical splitter for plot area and diary table
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Create horizontal layout for plot and data tables (top section)
        plot_and_tables_widget = QWidget()
        plot_and_tables_layout = QHBoxLayout(plot_and_tables_widget)
        plot_and_tables_layout.setContentsMargins(0, 0, 0, 0)

        # Left data table (onset/first marker) - fixed width
        # Create wrapper to place button outside table container
        onset_wrapper = QWidget()
        onset_wrapper_layout = QVBoxLayout(onset_wrapper)
        onset_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        onset_wrapper_layout.setSpacing(2)

        # Add pop-out button above the table (center-aligned)
        onset_button_layout = QHBoxLayout()
        onset_button_layout.setContentsMargins(5, 0, 5, 2)
        onset_popout_button = QPushButton("⬈ Pop Out")
        onset_popout_button.setMaximumWidth(80)
        onset_popout_button.setFixedHeight(22)
        onset_popout_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2868a8;
            }
        """)
        onset_button_layout.addStretch()
        onset_button_layout.addWidget(onset_popout_button)
        onset_button_layout.addStretch()
        onset_wrapper_layout.addLayout(onset_button_layout)

        # Add the table to the wrapper
        self.onset_table = create_marker_data_table("Sleep Onset Data")
        onset_wrapper_layout.addWidget(self.onset_table)

        plot_and_tables_layout.addWidget(onset_wrapper)

        # Connect onset pop-out button
        onset_popout_button.clicked.connect(self._on_onset_popout_clicked)

        # Center widget containing filename label and plot
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)

        # Create filename label above the plot
        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet("""
            QLabel {
                font-size: 11pt;
                font-weight: bold;
                color: #333;
                padding: 2px 5px;
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
        """)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.filename_label)

        # Add plot widget below the label
        center_layout.addWidget(self.plot_widget, stretch=1)

        # Pass the filename label reference to the plot widget
        self.plot_widget.external_filename_label = self.filename_label

        # Add center widget to the main layout - takes remaining space
        plot_and_tables_layout.addWidget(center_widget, stretch=1)

        # Right data table (offset/last marker) - fixed width
        # Create wrapper to place button outside table container
        offset_wrapper = QWidget()
        offset_wrapper_layout = QVBoxLayout(offset_wrapper)
        offset_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        offset_wrapper_layout.setSpacing(2)

        # Add pop-out button above the table (center-aligned)
        offset_button_layout = QHBoxLayout()
        offset_button_layout.setContentsMargins(5, 0, 5, 2)
        offset_popout_button = QPushButton("⬈ Pop Out")
        offset_popout_button.setMaximumWidth(80)
        offset_popout_button.setFixedHeight(22)
        offset_popout_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2868a8;
            }
        """)
        offset_button_layout.addStretch()
        offset_button_layout.addWidget(offset_popout_button)
        offset_button_layout.addStretch()
        offset_wrapper_layout.addLayout(offset_button_layout)

        # Add the table to the wrapper
        self.offset_table = create_marker_data_table("Sleep Offset Data")
        offset_wrapper_layout.addWidget(self.offset_table)

        plot_and_tables_layout.addWidget(offset_wrapper)

        # Connect offset pop-out button
        offset_popout_button.clicked.connect(self._on_offset_popout_clicked)

        # Create diary table (bottom section)
        self.diary_table_widget = self._create_diary_table()

        # Add both sections to the splitter
        main_splitter.addWidget(plot_and_tables_widget)
        main_splitter.addWidget(self.diary_table_widget)

        # Configure splitter behavior
        main_splitter.setChildrenCollapsible(False)  # Prevent complete collapse, respect minimum sizes
        main_splitter.setHandleWidth(8)  # Make the splitter handle more visible

        # Add custom styling to make splitter handle more visible
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #b0b0ff;
                border: 1px solid #7070ff;
            }
            QSplitter::handle:hover {
                background-color: #9090ff;
                border: 1px solid #5050ff;
            }
            QSplitter::handle:pressed {
                background-color: #7070ff;
                border: 1px solid #4040ff;
            }
        """)

        # Set minimum sizes for both sections
        plot_and_tables_widget.setMinimumHeight(200)  # Plot area minimum
        self.diary_table_widget.setMinimumHeight(100)  # Diary table minimum

        # Set initial splitter sizes (plot area gets more space initially)
        main_splitter.setSizes([350, 361])  # Plot area: 350px, Diary: 370px
        main_splitter.setStretchFactor(0, 1)  # Plot area is stretchable
        main_splitter.setStretchFactor(1, 0)  # Diary table maintains proportional size

        # Add the main splitter to the plot area widget
        plot_area_layout.addWidget(main_splitter, stretch=1)

        # Add the plot area widget to the top-level splitter
        top_level_splitter.addWidget(plot_area_widget)

        # Configure top-level splitter behavior
        top_level_splitter.setChildrenCollapsible(False)  # Prevent complete collapse
        top_level_splitter.setHandleWidth(8)  # Make the splitter handle more visible

        # Add custom styling to make splitter handle more visible
        top_level_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #b0b0ff;
                border: 1px solid #7070ff;
            }
            QSplitter::handle:hover {
                background-color: #9090ff;
                border: 1px solid #5050ff;
            }
            QSplitter::handle:pressed {
                background-color: #7070ff;
                border: 1px solid #4040ff;
            }
        """)

        # Set minimum sizes for both sections of top-level splitter
        file_bar.setMinimumHeight(150)  # File selection minimum
        plot_area_widget.setMinimumHeight(300)  # Plot area minimum

        # Set initial top-level splitter sizes (file selection smaller, plot area larger)
        top_level_splitter.setSizes([250, 600])  # File selection: 250px, Plot area: 600px
        top_level_splitter.setStretchFactor(0, 0)  # File selection maintains fixed proportion
        top_level_splitter.setStretchFactor(1, 1)  # Plot area is stretchable

        # Add the top-level splitter to content layout
        content_layout.addWidget(top_level_splitter, stretch=1)

        # Set the content widget in the scroll area
        scroll_area.setWidget(content_widget)

        # Add scroll area to main layout
        layout.addWidget(scroll_area)

        # Store references in parent for backward compatibility
        self.parent.plot_widget = self.plot_widget
        self.parent.onset_table = self.onset_table
        self.parent.offset_table = self.offset_table
        self.parent.diary_table_widget = self.diary_table_widget

        # Initialize the activity source dropdown with current preferences
        # Use QTimer.singleShot to ensure parent window is fully initialized
        QTimer.singleShot(0, self.update_activity_source_dropdown)

        # Set up focus handling for time fields
        self._setup_time_field_focus_handling()

        # Apply saved colors from settings (must be done after plot_widget is created)
        self._apply_colors()

    def _create_file_selection_bar(self) -> QFrame:
        """Create file selection bar with table widget."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        # File selection label with file count info
        self.file_selection_label = QLabel("File Selection")
        self.file_selection_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.file_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.file_selection_label)

        # Store folder info label reference but don't display it
        # Keep it for compatibility with main_window.py update_folder_info_label
        self.folder_info_label = QLabel("")
        self.folder_info_label.setVisible(False)  # Hide it

        # File selection table
        self.file_selector = FileSelectionTable()
        self.file_selector.setMinimumHeight(200)
        self.file_selector.setMaximumHeight(300)

        # Connect file selection signal
        def on_file_selected(row: int, file_info: dict) -> None:
            logger.info("=== ANALYSIS TAB: File selected from table row %s ===", row)
            try:
                logger.info("About to call parent.on_file_selected with file_info: %s", file_info)
                if hasattr(self.parent, "on_file_selected_from_table"):
                    self.parent.on_file_selected_from_table(file_info)
                    logger.info("parent.on_file_selected_from_table completed successfully")
                else:
                    logger.error("Parent does not have on_file_selected_from_table method")
            except Exception:
                logger.exception("=== ANALYSIS TAB ERROR in on_file_selected ===")
                import traceback

                logger.exception("Full traceback: %s", traceback.format_exc())
                raise

        self.file_selector.fileSelected.connect(on_file_selected)
        layout.addWidget(self.file_selector)

        # Store references in parent for backward compatibility
        self.parent.file_selector = self.file_selector
        self.parent.folder_info_label = self.folder_info_label
        self.parent.file_selection_label = self.file_selection_label

        return panel

    def _create_date_navigation_bar(self) -> QFrame:
        """Create centered date navigation bar."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMaximumHeight(60)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        # Add stretch to center content
        layout.addStretch()

        # Date navigation
        self.prev_date_btn = QPushButton("◀ Previous")
        self.prev_date_btn.clicked.connect(self.parent.prev_date)
        self.prev_date_btn.setEnabled(False)
        self.prev_date_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 16px;
                padding: 8px 16px;
            }}
            {ButtonStyle.FOCUS_STYLE}
        """)
        layout.addWidget(self.prev_date_btn)

        self.date_dropdown = QComboBox()
        self.date_dropdown.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 20px 8px 20px;
                font-size: 16px;
                font-weight: bold;
                min-width: 120px;
            }}
            QComboBox:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
        """)
        self.date_dropdown.setMaxVisibleItems(10)
        self.date_dropdown.currentIndexChanged.connect(self.parent.on_date_dropdown_changed)
        self.date_dropdown.setEnabled(False)

        # Center the text
        self.date_dropdown.setEditable(True)
        line_edit = self.date_dropdown.lineEdit()
        if line_edit:
            line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line_edit.setReadOnly(True)
            line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            # Override the mouse press event to show popup
            original_mouse_press = line_edit.mousePressEvent

            def mouse_press_override(event) -> None:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.date_dropdown.showPopup()
                else:
                    original_mouse_press(event)

            line_edit.mousePressEvent = mouse_press_override

        layout.addWidget(self.date_dropdown)

        self.next_date_btn = QPushButton("Next ▶")
        self.next_date_btn.clicked.connect(self.parent.next_date)
        self.next_date_btn.setEnabled(False)
        self.next_date_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 16px;
                padding: 8px 16px;
            }}
            {ButtonStyle.FOCUS_STYLE}
        """)
        layout.addWidget(self.next_date_btn)

        # Add stretch to center content
        layout.addStretch()

        # Store references in parent for backward compatibility
        self.parent.prev_date_btn = self.prev_date_btn
        self.parent.date_dropdown = self.date_dropdown
        self.parent.next_date_btn = self.next_date_btn

        return panel

    def _create_control_bar(self) -> QFrame:
        """Create control bar with two rows for better fit on smaller screens."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)

        # Use vertical layout for two rows
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(5)

        # === ROW 1: View options and display settings ===
        row1 = QHBoxLayout()
        row1.setSpacing(15)
        row1.addStretch()

        # Shortcuts button
        shortcuts_btn = QPushButton("Shortcuts")
        shortcuts_btn.setMaximumWidth(85)
        shortcuts_btn.clicked.connect(self._show_shortcuts_dialog)
        shortcuts_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 11px;
                padding: 5px 10px;
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #dee2e6;
            }}
            QPushButton:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
        """)
        row1.addWidget(shortcuts_btn)

        # Color Legend button
        legend_btn = QPushButton("Colors")
        legend_btn.setMaximumWidth(70)
        legend_btn.clicked.connect(self._show_color_legend_dialog)
        legend_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 11px;
                padding: 5px 10px;
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #dee2e6;
            }}
            QPushButton:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
        """)
        row1.addWidget(legend_btn)

        row1.addSpacing(10)

        # Activity data source selection
        row1.addWidget(QLabel("Source:"))

        self.activity_source_dropdown = QComboBox()
        self.activity_source_dropdown.addItem("Y-Axis (Vertical)", ActivityDataPreference.AXIS_Y)
        self.activity_source_dropdown.addItem("X-Axis (Lateral)", ActivityDataPreference.AXIS_X)
        self.activity_source_dropdown.addItem("Z-Axis (Forward)", ActivityDataPreference.AXIS_Z)
        self.activity_source_dropdown.addItem("Vector Magnitude", ActivityDataPreference.VECTOR_MAGNITUDE)
        self.activity_source_dropdown.setCurrentIndex(0)
        self.activity_source_dropdown.setToolTip(TooltipText.ACTIVITY_SOURCE_DROPDOWN)
        self.activity_source_dropdown.currentIndexChanged.connect(self._on_activity_source_changed)
        self.activity_source_dropdown.setEnabled(False)
        self.activity_source_dropdown.setStyleSheet(f"""
            QComboBox {{
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }}
            QComboBox:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: 1px solid #ced4da;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #666;
            }}
        """)
        row1.addWidget(self.activity_source_dropdown)

        row1.addSpacing(15)

        # Adjacent day markers checkbox
        self.show_adjacent_day_markers_checkbox = QCheckBox("Adjacent Markers")
        self.show_adjacent_day_markers_checkbox.setToolTip("Display sleep markers from adjacent days as faded, dashed lines")
        self.show_adjacent_day_markers_checkbox.setChecked(True)
        self.show_adjacent_day_markers_checkbox.toggled.connect(self._on_adjacent_day_markers_toggled)
        row1.addWidget(self.show_adjacent_day_markers_checkbox)

        row1.addSpacing(15)

        # View mode selection
        row1.addWidget(QLabel("View:"))

        self.view_24h_btn = QRadioButton("24h")
        self.view_24h_btn.setChecked(False)
        self.view_24h_btn.toggled.connect(lambda checked: self._on_view_mode_changed(24) if checked else None)
        row1.addWidget(self.view_24h_btn)

        self.view_48h_btn = QRadioButton("48h")
        self.view_48h_btn.setChecked(True)
        self.view_48h_btn.toggled.connect(lambda checked: self._on_view_mode_changed(48) if checked else None)
        row1.addWidget(self.view_48h_btn)

        self.view_mode_group = QButtonGroup()
        self.view_mode_group.addButton(self.view_24h_btn, 24)
        self.view_mode_group.addButton(self.view_48h_btn, 48)

        row1.addSpacing(15)

        # Day of Week display
        self.weekday_label = QLabel("Day: ")
        self.weekday_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        row1.addWidget(self.weekday_label)

        row1.addStretch()

        main_layout.addLayout(row1)

        # === ROW 2: Sleep times and action buttons ===
        row2 = QHBoxLayout()
        row2.setSpacing(15)
        row2.addStretch()

        # Manual time entry
        row2.addWidget(QLabel("Sleep Times:"))

        self.onset_time_input = QLineEdit()
        self.onset_time_input.setPlaceholderText("HH:MM")
        self.onset_time_input.setMaximumWidth(55)
        self.onset_time_input.setToolTip(TooltipText.ONSET_TIME_INPUT)
        self.onset_time_input.returnPressed.connect(self._on_time_field_return_pressed)
        self.onset_time_input.textChanged.connect(self._on_time_input_changed)
        self.onset_time_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 4px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
        """)
        row2.addWidget(self.onset_time_input)

        row2.addWidget(QLabel("to"))

        self.offset_time_input = QLineEdit()
        self.offset_time_input.setPlaceholderText("HH:MM")
        self.offset_time_input.setMaximumWidth(55)
        self.offset_time_input.setToolTip(TooltipText.OFFSET_TIME_INPUT)
        self.offset_time_input.returnPressed.connect(self._on_time_field_return_pressed)
        self.offset_time_input.textChanged.connect(self._on_time_input_changed)
        self.offset_time_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 4px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 2px solid {UIColors.FOCUS_BORDER};
                background-color: {UIColors.FOCUS_BACKGROUND};
            }}
        """)
        row2.addWidget(self.offset_time_input)

        # Total duration label
        self.total_duration_label = QLabel("")
        self.total_duration_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #333; padding-left: 5px;")
        self.total_duration_label.setMinimumWidth(120)
        row2.addWidget(self.total_duration_label)

        row2.addSpacing(30)

        # Save markers button
        self.save_markers_btn = QPushButton(ButtonText.SAVE_MARKERS)
        self.save_markers_btn.clicked.connect(self.parent.save_current_markers)
        self.save_markers_btn.setToolTip(TooltipText.SAVE_MARKERS)
        self.save_markers_btn.setStyleSheet(ButtonStyle.SAVE_MARKERS)
        row2.addWidget(self.save_markers_btn)

        # No Sleep button
        self.no_sleep_btn = QPushButton(ButtonText.MARK_NO_SLEEP)
        self.no_sleep_btn.clicked.connect(self.parent.mark_no_sleep_period)
        self.no_sleep_btn.setToolTip(TooltipText.MARK_NO_SLEEP)
        self.no_sleep_btn.setStyleSheet(ButtonStyle.MARK_NO_SLEEP)
        row2.addWidget(self.no_sleep_btn)

        # Clear markers button
        self.clear_markers_btn = QPushButton(ButtonText.CLEAR_MARKERS)
        self.clear_markers_btn.clicked.connect(self.parent.clear_current_markers)
        self.clear_markers_btn.setToolTip(TooltipText.CLEAR_MARKERS)
        self.clear_markers_btn.setStyleSheet(ButtonStyle.CLEAR_MARKERS_RED)
        row2.addWidget(self.clear_markers_btn)

        row2.addStretch()

        main_layout.addLayout(row2)

        # Store references in parent for backward compatibility
        self.parent.activity_source_dropdown = self.activity_source_dropdown
        self.parent.view_24h_btn = self.view_24h_btn
        self.parent.view_48h_btn = self.view_48h_btn
        self.parent.weekday_label = self.weekday_label
        self.parent.show_adjacent_day_markers_checkbox = self.show_adjacent_day_markers_checkbox
        self.parent.onset_time_input = self.onset_time_input
        self.parent.offset_time_input = self.offset_time_input
        self.parent.save_markers_btn = self.save_markers_btn
        self.parent.no_sleep_btn = self.no_sleep_btn
        self.parent.clear_markers_btn = self.clear_markers_btn
        self.parent.total_duration_label = self.total_duration_label

        return panel

    def _show_shortcuts_dialog(self) -> None:
        """Show keyboard shortcuts dialog."""
        self.dialog_manager.show_shortcuts_dialog()

    def _show_color_legend_dialog(self) -> None:
        """Show color legend dialog with color picker functionality."""
        self.dialog_manager.show_color_legend_dialog()

    def _apply_colors(self) -> None:
        """Apply the selected colors to the plot in real-time."""
        self.dialog_manager.apply_colors()

    @ensure_main_thread
    def _on_activity_source_changed_seamless(self, index: int) -> None:
        """Handle activity data source dropdown change with seamless switching."""
        if index < 0:
            return

        import time

        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        start_time = time.perf_counter()

        try:
            # Get the selected activity column preference
            selected_column = self.activity_source_dropdown.itemData(index)
            if not selected_column:
                return

            logger.info(f"Activity data source changing to: {selected_column} (seamless mode)")

            # Disable dropdown to prevent race conditions
            self.activity_source_dropdown.setEnabled(False)

            # Change cursor to indicate processing (thread-safe)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            try:
                # Step 1: Capture complete current state
                state_capture_start = time.perf_counter()
                current_state = self._capture_complete_plot_state()
                state_capture_time = time.perf_counter() - state_capture_start
                logger.debug(f"State capture took: {state_capture_time:.3f}s")

                # Step 2: Update activity data preferences
                # Display dropdown only changes display preference, NOT Choi column
                # Choi column is controlled separately by Study Settings
                choi_column = self.parent.config_manager.config.choi_axis
                self.parent.set_activity_data_preferences(selected_column, choi_column)

                # Step 3: Load new activity data only (no full reload)
                data_load_start = time.perf_counter()
                success = self._load_activity_data_seamlessly(selected_column)
                data_load_time = time.perf_counter() - data_load_start
                logger.debug(f"Data loading took: {data_load_time:.3f}s")

                if not success:
                    logger.error("Failed to load activity data seamlessly, falling back to full reload")
                    self._fallback_to_full_reload(selected_column)
                    return

                # Step 4: Update Choi algorithm overlay with new data
                choi_update_start = time.perf_counter()
                self._update_choi_overlay_seamlessly()
                choi_update_time = time.perf_counter() - choi_update_start
                logger.debug(f"Choi overlay update took: {choi_update_time:.3f}s")

                # Step 5: Restore all captured state
                state_restore_start = time.perf_counter()
                self._restore_complete_plot_state(current_state)
                state_restore_time = time.perf_counter() - state_restore_start
                logger.debug(f"State restoration took: {state_restore_time:.3f}s")

                total_time = time.perf_counter() - start_time
                logger.info(f"Seamless activity source switch completed in {total_time:.3f}s")

            finally:
                # Always restore cursor and re-enable dropdown
                QApplication.restoreOverrideCursor()
                self.activity_source_dropdown.setEnabled(True)

        except Exception as e:
            logger.exception(f"Error in seamless activity source change: {e}")
            # Fallback to original method on any error
            try:
                QApplication.restoreOverrideCursor()
                self.activity_source_dropdown.setEnabled(True)
                self._fallback_to_full_reload(selected_column)
            except Exception as fallback_error:
                logger.exception(f"Fallback reload also failed: {fallback_error}")

    def _capture_complete_plot_state(self) -> dict:
        """Capture complete plot state including view range, zoom, sleep markers, and UI state."""
        plot_widget = self.parent.plot_widget
        state = {}

        try:
            # Capture view range (zoom and pan state)
            if hasattr(plot_widget, "vb") and plot_widget.vb:
                view_range = plot_widget.vb.viewRange()
                state["view_range"] = {"x_range": view_range[0], "y_range": view_range[1]}
                logger.debug(f"Captured view range: x={view_range[0]}, y={view_range[1]}")

            # Capture sleep markers state (new daily_sleep_markers format)
            if hasattr(plot_widget, "daily_sleep_markers") and plot_widget.daily_sleep_markers:
                # Serialize the daily sleep markers
                daily_markers = plot_widget.daily_sleep_markers
                state["daily_sleep_markers"] = {
                    "period_1": self._serialize_sleep_period(daily_markers.period_1),
                    "period_2": self._serialize_sleep_period(daily_markers.period_2),
                    "period_3": self._serialize_sleep_period(daily_markers.period_3),
                    "period_4": self._serialize_sleep_period(daily_markers.period_4),
                }
                logger.debug(
                    f"Captured daily sleep markers: {len([p for p in [daily_markers.period_1, daily_markers.period_2, daily_markers.period_3, daily_markers.period_4] if p])} periods"
                )

            # Capture current view mode with safe attribute access
            if hasattr(self.parent, "data_service") and self.parent.data_service and hasattr(self.parent.data_service, "current_view_mode"):
                state["view_mode"] = self.parent.data_service.current_view_mode
                logger.debug(f"Captured view mode: {state['view_mode']}")

            # Capture UI button states with safety checks
            ui_state = {}
            if hasattr(self.parent, "view_24h_btn") and self.parent.view_24h_btn:
                ui_state["view_24h_checked"] = self.parent.view_24h_btn.isChecked()
            if hasattr(self.parent, "view_48h_btn") and self.parent.view_48h_btn:
                ui_state["view_48h_checked"] = self.parent.view_48h_btn.isChecked()
            state["ui_state"] = ui_state

            logger.debug("Complete plot state captured successfully")
            return state

        except Exception as e:
            logger.exception(f"Error capturing plot state: {e}")
            return {}

    def _load_activity_data_seamlessly(self, activity_column: ActivityDataPreference) -> bool:
        """Load new activity data without clearing existing state."""
        try:
            if not hasattr(self.parent, "available_dates") or not self.parent.available_dates:
                logger.warning("No available dates for seamless data loading")
                return False

            if not hasattr(self.parent, "current_date_index") or self.parent.current_date_index is None:
                logger.warning("No current date index for seamless data loading")
                return False

            current_date = self.parent.available_dates[self.parent.current_date_index]
            current_view_mode = getattr(self.parent.data_service, "current_view_mode", 24)

            # Get filename for database queries
            filename = None
            if hasattr(self.parent, "current_file_info") and self.parent.current_file_info:
                filename = self.parent.current_file_info.get("filename")
            elif hasattr(self.parent, "selected_file") and self.parent.selected_file:
                filename = Path(self.parent.selected_file).name

            logger.debug(f"Loading activity data: date={current_date}, column={activity_column}, filename={filename}")

            # Load 48h main data with new activity column
            timestamps_48h, activity_data_48h = self.parent.data_service.data_manager.load_real_data(
                current_date, 48, filename, activity_column=activity_column
            )

            if not timestamps_48h or not activity_data_48h:
                logger.error("Failed to load activity data with new column")
                return False

            # Update main dataset in data service
            self.parent.data_service.main_48h_data = (timestamps_48h, activity_data_48h)

            # Don't clear axis_y cache - the table needs both axis_y and VM data
            # regardless of what's being displayed in the plot

            # Update the cache with new data for this date and activity column
            cache_key = current_date.strftime("%Y-%m-%d")
            if hasattr(self.parent, "current_date_48h_cache"):
                from sleep_scoring_app.services.memory_service import estimate_object_size_mb

                data_size_mb = estimate_object_size_mb((timestamps_48h, activity_data_48h))
                self.parent.current_date_48h_cache.put(cache_key, (timestamps_48h, activity_data_48h), data_size_mb)

            # Filter to current view mode
            if current_view_mode == 24:
                timestamps, activity_data = self.parent.data_service.data_manager.filter_to_24h_view(timestamps_48h, activity_data_48h, current_date)
            else:
                timestamps, activity_data = timestamps_48h, activity_data_48h

            # Update plot widget data using seamless method
            self.parent.plot_widget.update_data_and_view_only(timestamps, activity_data, current_view_mode, current_date=current_date)

            logger.debug(f"Successfully loaded {len(timestamps)} data points with new activity column")
            return True

        except Exception as e:
            logger.exception(f"Error in seamless data loading: {e}")
            return False

    def _update_choi_overlay_seamlessly(self) -> None:
        """Update Choi algorithm overlay with new activity data."""
        try:
            # Reload nonwear data for the new activity column
            # This will update the Choi algorithm results using the new data
            self.parent.data_service.load_nonwear_data_for_plot()
            logger.debug("Choi overlay updated seamlessly")

        except Exception as e:
            logger.exception(f"Error updating Choi overlay: {e}")

    def _restore_complete_plot_state(self, state: dict) -> None:
        """Restore complete plot state including view range, zoom, and sleep markers."""
        plot_widget = self.parent.plot_widget

        # ALWAYS update sleep scoring rules after activity source change
        # This ensures the arrows are updated with the new activity data, regardless of state
        if hasattr(plot_widget, "_update_sleep_scoring_rules"):
            plot_widget._update_sleep_scoring_rules()
            logger.debug("Updated sleep scoring rules with new activity data")

        if not state:
            logger.warning("No state to restore, but sleep scoring rules updated")
            return

        try:
            # Restore view range (zoom and pan)
            if "view_range" in state:
                # Ensure vb exists before attempting to access it
                if hasattr(plot_widget, "vb") and plot_widget.vb:
                    view_range = state["view_range"]
                    try:
                        plot_widget.vb.setRange(xRange=view_range["x_range"], yRange=view_range["y_range"], padding=0)
                        logger.debug(f"Restored view range: x={view_range['x_range']}, y={view_range['y_range']}")
                    except AttributeError as e:
                        logger.warning(f"Could not restore view range - vb not accessible: {e}")
                else:
                    logger.warning("Cannot restore view range - plot_widget.vb not available")

            # Restore sleep markers (new daily_sleep_markers format)
            if state.get("daily_sleep_markers"):
                daily_markers_data = state["daily_sleep_markers"]

                # Deserialize and restore daily sleep markers
                from sleep_scoring_app.core.dataclasses import DailySleepMarkers

                restored_markers = DailySleepMarkers(
                    period_1=self._deserialize_sleep_period(daily_markers_data.get("period_1")),
                    period_2=self._deserialize_sleep_period(daily_markers_data.get("period_2")),
                    period_3=self._deserialize_sleep_period(daily_markers_data.get("period_3")),
                    period_4=self._deserialize_sleep_period(daily_markers_data.get("period_4")),
                )

                # Load markers into plot widget
                plot_widget.load_daily_sleep_markers(restored_markers, markers_saved=False)
                logger.debug("Restored daily sleep markers")

            # Restore UI button states
            if "ui_state" in state:
                ui_state = state["ui_state"]
                self.parent.view_24h_btn.setChecked(ui_state.get("view_24h_checked", True))
                self.parent.view_48h_btn.setChecked(ui_state.get("view_48h_checked", False))

            logger.debug("Complete plot state restored successfully")

        except Exception as e:
            logger.exception(f"Error restoring plot state: {e}")

    def _fallback_to_full_reload(self, selected_column: str) -> None:
        """Fallback to full reload method when seamless switching fails."""
        try:
            logger.info(f"Performing fallback full reload with activity source: {selected_column}")

            # Auto-save current markers before reloading
            if hasattr(self.parent, "auto_save_current_markers"):
                self.parent.auto_save_current_markers()

            # Full reload with new column preference
            if hasattr(self.parent, "load_current_date"):
                self.parent.load_current_date()

            # Restore saved markers for this date
            if hasattr(self.parent, "load_saved_markers"):
                self.parent.load_saved_markers()

            logger.info(f"Fallback reload completed with activity source: {selected_column}")

        except Exception as e:
            logger.exception(f"Error in fallback reload: {e}")

    # Keep original method for backward compatibility
    @pyqtSlot(int)
    def _on_activity_source_changed(self, index: int) -> None:
        """Handle activity data source dropdown change (original method, kept for compatibility)."""
        # Delegate to seamless method
        self._on_activity_source_changed_seamless(index)

    @ensure_main_thread
    def update_activity_source_dropdown(self) -> None:
        """Update the activity source dropdown to reflect current preferences and available columns."""
        try:
            # Get current preferences with safety check
            if not (hasattr(self.parent, "get_activity_data_preferences") and callable(getattr(self.parent, "get_activity_data_preferences", None))):
                logger.warning("Parent does not have get_activity_data_preferences method")
                return
            preferred_column, _choi_column = self.parent.get_activity_data_preferences()

            # Get available columns for current file
            available_columns = self._get_available_activity_columns()

            # Update each item's enabled state based on available columns
            model = self.activity_source_dropdown.model()
            for i in range(self.activity_source_dropdown.count()):
                item_data = self.activity_source_dropdown.itemData(i)
                is_available = item_data in available_columns
                # Enable/disable item in the model
                item = model.item(i)
                if item:
                    item.setEnabled(is_available)

            # Find the index for the preferred column
            for i in range(self.activity_source_dropdown.count()):
                if self.activity_source_dropdown.itemData(i) == preferred_column:
                    # Temporarily disconnect to avoid triggering change handler
                    try:
                        self.activity_source_dropdown.currentIndexChanged.disconnect()
                        self.activity_source_dropdown.setCurrentIndex(i)
                        self.activity_source_dropdown.currentIndexChanged.connect(self._on_activity_source_changed)
                    except (TypeError, RuntimeError):
                        # Handle case where signal is already disconnected or widget is being destroyed
                        self.activity_source_dropdown.setCurrentIndex(i)
                        self.activity_source_dropdown.currentIndexChanged.connect(self._on_activity_source_changed)
                    break

            # Enable the dropdown if data is available
            has_data = bool(
                hasattr(self.parent, "available_dates")
                and self.parent.available_dates
                and hasattr(self.parent, "current_date_index")
                and self.parent.current_date_index is not None
            )
            self.activity_source_dropdown.setEnabled(has_data)

        except Exception as e:
            logger.exception(f"Error updating activity source dropdown: {e}")

    def _get_available_activity_columns(self) -> list:
        """Get list of activity columns that have data for the current file."""
        try:
            # Get current filename
            filename = None
            if hasattr(self.parent, "current_file_info") and self.parent.current_file_info:
                filename = self.parent.current_file_info.get("filename")
            elif hasattr(self.parent, "selected_file") and self.parent.selected_file:
                filename = Path(self.parent.selected_file).name

            if not filename:
                # No file loaded, return all as available
                return [
                    ActivityDataPreference.AXIS_Y,
                    ActivityDataPreference.AXIS_X,
                    ActivityDataPreference.AXIS_Z,
                    ActivityDataPreference.VECTOR_MAGNITUDE,
                ]

            # Query database for available columns
            if hasattr(self.parent, "data_service") and hasattr(self.parent.data_service, "db_manager"):
                return self.parent.data_service.db_manager.get_available_activity_columns(filename)

            # Fallback to all available
            return [
                ActivityDataPreference.AXIS_Y,
                ActivityDataPreference.AXIS_X,
                ActivityDataPreference.AXIS_Z,
                ActivityDataPreference.VECTOR_MAGNITUDE,
            ]

        except Exception as e:
            logger.warning(f"Error getting available activity columns: {e}")
            return [ActivityDataPreference.AXIS_Y]

    @ensure_main_thread
    def set_activity_source_dropdown_enabled(self, enabled: bool) -> None:
        """Enable or disable the activity source dropdown."""
        self.activity_source_dropdown.setEnabled(enabled)

    def _create_diary_table(self) -> QWidget:
        """Create diary table that displays actual diary data."""
        container = QFrame()
        container.setFrameStyle(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title label
        title_label = QLabel("Sleep Diary")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 5px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Define diary column structure with proper sizing
        diary_columns = [
            DiaryColumnDefinition(DiaryTableColumn.DATE, "Date", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.BEDTIME, "In Bed Time", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.SLEEP_ONSET, "Sleep Onset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.SLEEP_OFFSET, "Sleep Offset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_OCCURRED, "# Naps", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_1_START, "Nap 1 Onset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_1_END, "Nap 1 Offset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_2_START, "Nap 2 Onset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_2_END, "Nap 2 Offset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_3_START, "Nap 3 Onset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NAP_3_END, "Nap 3 Offset", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_OCCURRED, "Nonwear", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_1_START, "NWT 1 Start", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_1_END, "NWT 1 End", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_1_REASON, "NWT 1 Reason", QHeaderView.ResizeMode.Stretch),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_2_START, "NWT 2 Start", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_2_END, "NWT 2 End", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_2_REASON, "NWT 2 Reason", QHeaderView.ResizeMode.Stretch),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_3_START, "NWT 3 Start", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_3_END, "NWT 3 End", QHeaderView.ResizeMode.ResizeToContents),
            DiaryColumnDefinition(DiaryTableColumn.NONWEAR_3_REASON, "NWT 3 Reason", QHeaderView.ResizeMode.Stretch),
        ]

        # Create diary table with dynamic column count
        table = QTableWidget(0, len(diary_columns))

        # Set headers from column definitions
        headers = [col.header for col in diary_columns]
        table.setHorizontalHeaderLabels(headers)

        # Configure table appearance
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)  # Allow single row selection

        # Add hover styling and selection styling to indicate clickable rows
        from sleep_scoring_app.core.constants import UIColors

        table.setStyleSheet(f"""
            QTableWidget::item:hover {{
                background-color: {UIColors.DIARY_SELECTION_DARKER};
                color: white;
            }}
            QTableWidget::item:selected {{
                background-color: {UIColors.DIARY_SELECTION_DARKER} !important;
                color: white !important;
            }}
            QTableWidget:item:focus {{
                background-color: {UIColors.DIARY_SELECTION_DARKER} !important;
                color: white !important;
            }}
            QTableWidget {{
                selection-background-color: {UIColors.DIARY_SELECTION_DARKER};
                selection-color: white;
            }}
            QTableWidget::item {{
                padding: 2px;
            }}
        """)

        # Hide vertical header
        vertical_header = table.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)

        # Configure column widths from definitions
        header = table.horizontalHeader()
        header.setStretchLastSection(False)

        for idx, col_def in enumerate(diary_columns):
            header.setSectionResizeMode(idx, col_def.width_mode)
            if col_def.width_hint:
                table.setColumnWidth(idx, col_def.width_hint)

        # Set font
        font = table.font()
        font.setPointSize(9)
        table.setFont(font)

        layout.addWidget(table)

        # Configure size policies
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Store reference for future use and column definitions
        container.diary_table = table
        container.diary_columns = diary_columns

        # Connect click handler for setting markers from diary
        table.itemClicked.connect(self._on_diary_row_clicked)

        return container

    def update_diary_display(self) -> None:
        """Update diary table with data for current participant."""
        if not hasattr(self.parent, "data_service"):
            self._show_diary_error("Data service not available")
            return

        try:
            # Load diary data for current file
            diary_entries = self.parent.data_service.load_diary_data_for_current_file()

            if not diary_entries:
                # Check if participant has data at all
                has_data = self.parent.data_service.check_current_participant_has_diary_data()
                if has_data:
                    self._show_diary_info("No diary data for current date range")
                else:
                    participant_id = self._get_current_participant_id()
                    if participant_id:
                        self._show_diary_error(f"No diary data found for participant {participant_id}")
                    else:
                        self._show_diary_error("Could not extract participant ID from input, using default value")
                self._clear_diary_table()
                return

            # Display the diary data
            self._populate_diary_table(diary_entries)

        except Exception as e:
            self._show_diary_error(f"Error loading diary data: {e!s}")
            self._clear_diary_table()

    def _populate_diary_table(self, diary_entries) -> None:
        """Populate diary table with actual data."""
        table = self.diary_table_widget.diary_table

        # Set row count
        table.setRowCount(len(diary_entries))

        for row, entry in enumerate(diary_entries):
            # Helper function to format date - strip time if present
            def format_date(date_str: str | None) -> str:
                if not date_str:
                    return "--"
                # Remove timestamp portion if present (anything after space)
                return date_str.split()[0] if " " in date_str else date_str

            # Helper function to format boolean values
            def format_bool(value: bool | None) -> str:
                if value is None:
                    return "--"
                return "Yes" if value else "No"

            # Helper function to format nap count from diary entry
            def format_nap_count(value: int | None) -> str:
                """Format nap count value (should already be 0-3 from diary data)."""
                if value is None:
                    return "--"
                return str(value)

            # Create table items
            items = [
                QTableWidgetItem(format_date(entry.diary_date)),
                QTableWidgetItem(entry.in_bed_time or entry.bedtime or "--:--"),  # Try in_bed_time first, fallback to bedtime
                QTableWidgetItem(entry.sleep_onset_time or "--:--"),
                QTableWidgetItem(entry.sleep_offset_time or "--:--"),
                # Nap information - show actual count from diary data
                QTableWidgetItem(format_nap_count(entry.nap_occurred)),
                QTableWidgetItem(entry.nap_onset_time or "--:--"),
                QTableWidgetItem(entry.nap_offset_time or "--:--"),
                QTableWidgetItem(entry.nap_onset_time_2 or "--:--"),
                QTableWidgetItem(entry.nap_offset_time_2 or "--:--"),
                QTableWidgetItem(entry.nap_onset_time_3 or "--:--"),
                QTableWidgetItem(entry.nap_offset_time_3 or "--:--"),
                # Nonwear information
                QTableWidgetItem(format_bool(entry.nonwear_occurred)),
                QTableWidgetItem(entry.nonwear_start_time or "--:--"),
                QTableWidgetItem(entry.nonwear_end_time or "--:--"),
                QTableWidgetItem(entry.nonwear_reason or "--"),
                QTableWidgetItem(entry.nonwear_start_time_2 or "--:--"),
                QTableWidgetItem(entry.nonwear_end_time_2 or "--:--"),
                QTableWidgetItem(entry.nonwear_reason_2 or "--"),
                QTableWidgetItem(entry.nonwear_start_time_3 or "--:--"),
                QTableWidgetItem(entry.nonwear_end_time_3 or "--:--"),
                QTableWidgetItem(entry.nonwear_reason_3 or "--"),
            ]

            # Set items in table
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # Center align all columns
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, col, item)

    def _clear_diary_table(self) -> None:
        """Clear the diary table."""
        table = self.diary_table_widget.diary_table
        table.setRowCount(0)

    def _show_diary_error(self, message: str) -> None:
        """Show error message in diary status label."""
        # Status label removed - errors can be logged instead
        logger.error(f"Diary error: {message}")

    def _show_diary_info(self, message: str) -> None:
        """Show info message in diary status label."""
        # Status label removed - info can be logged instead
        logger.info(f"Diary info: {message}")

    def _on_diary_row_clicked(self, item) -> None:
        """Handle click on diary table row to set sleep markers from diary times."""
        if not item:
            return

        column = item.column()
        row = item.row()
        logger.debug(f"Diary table clicked: row={row}, column={column}")

        # Get column type from diary_columns definition stored on the widget
        if hasattr(self, "diary_table_widget") and hasattr(self.diary_table_widget, "diary_columns"):
            if column < len(self.diary_table_widget.diary_columns):
                column_def = self.diary_table_widget.diary_columns[column]
                column_type = column_def.id

                # Only handle clicks on time columns that set markers
                marker_columns = [
                    DiaryTableColumn.SLEEP_ONSET,
                    DiaryTableColumn.SLEEP_OFFSET,
                    DiaryTableColumn.NAP_1_START,
                    DiaryTableColumn.NAP_1_END,
                    DiaryTableColumn.NAP_2_START,
                    DiaryTableColumn.NAP_2_END,
                    DiaryTableColumn.NAP_3_START,
                    DiaryTableColumn.NAP_3_END,
                ]

                if column_type in marker_columns:
                    logger.debug(f"Column {column_type} is a marker column, setting markers from diary")
                    # Use DiaryIntegrationManager for marker placement
                    if hasattr(self.parent, "diary_manager") and self.parent.diary_manager:
                        self.parent.diary_manager.set_markers_from_diary_column(row, column_type)
                    else:
                        logger.warning("DiaryIntegrationManager not available")
                else:
                    logger.warning(f"Clicked on non-marker column: {column_type}")
            else:
                logger.warning(f"Column index {column} out of range (max: {len(self.diary_table_widget.diary_columns) - 1})")
        else:
            logger.warning("Diary columns definition not found on diary_table_widget")

    def _get_current_participant_id(self) -> str | None:
        """Get participant ID from current filename."""
        if not hasattr(self.parent, "selected_file") or not self.parent.selected_file:
            return None

        from pathlib import Path

        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        filename = Path(self.parent.selected_file).name
        participant_info = extract_participant_info(filename)
        return participant_info.full_id if participant_info.numerical_id != "Unknown" else None

    @pyqtSlot(int)
    def _on_view_mode_changed(self, hours: int) -> None:
        """Handle view mode radio button change."""
        logger.debug(f"View mode changed to {hours} hours")
        self.parent.set_view_mode(hours)

    @pyqtSlot(bool)
    def _on_adjacent_day_markers_toggled(self, checked: bool) -> None:
        """Handle adjacent day markers checkbox toggle."""
        logger.info(f"Adjacent day markers toggled: {checked}")
        if hasattr(self.parent, "toggle_adjacent_day_markers"):
            self.parent.toggle_adjacent_day_markers(checked)

    @pyqtSlot()
    def _on_time_field_return_pressed(self) -> None:
        """Handle Return key press in time fields - immediate update."""
        # Call parent's set_manual_sleep_times
        if hasattr(self.parent, "set_manual_sleep_times"):
            self.parent.set_manual_sleep_times()

    @pyqtSlot()
    def _on_time_input_changed(self) -> None:
        """Update total duration label when time input fields change."""
        from datetime import datetime, timedelta

        # Get text from both fields
        onset_text = self.onset_time_input.text().strip()
        offset_text = self.offset_time_input.text().strip()

        # Only calculate if both fields have valid time format (HH:MM)
        if not onset_text or not offset_text:
            self.total_duration_label.setText("")
            return

        try:
            # Parse times
            onset_time = datetime.strptime(onset_text, "%H:%M")
            offset_time = datetime.strptime(offset_text, "%H:%M")

            # Calculate duration (handle overnight sleep)
            if offset_time <= onset_time:
                # Overnight: add 24 hours to offset time
                offset_time += timedelta(days=1)

            duration = offset_time - onset_time
            duration_hours = duration.total_seconds() / 3600

            # Update label
            self.total_duration_label.setText(f"Total Duration: {duration_hours:.1f} hours")

        except ValueError:
            # Invalid time format - clear the label
            self.total_duration_label.setText("")

    def _setup_time_field_focus_handling(self) -> None:
        """Set up focus handling for time fields to prevent update loops."""
        # Install event filters for more granular control
        from PyQt6.QtCore import QEvent, QObject

        class TimeFieldFocusHandler(QObject):
            """Handle focus events for time fields."""

            def __init__(self, parent_widget, field_name, parent=None) -> None:
                super().__init__(parent)
                self.parent_widget = parent_widget
                self.field_name = field_name
                self.initial_value = ""

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.FocusIn:
                    # Store initial value when focus gained
                    self.initial_value = obj.text()
                elif event.type() == QEvent.Type.FocusOut:
                    # Check if value changed when focus lost
                    if obj.text() != self.initial_value:
                        # Only trigger update if value actually changed
                        if hasattr(self.parent_widget.parent, "set_manual_sleep_times"):
                            # Small delay to ensure we're not in a focus change loop
                            QTimer.singleShot(50, self.parent_widget.parent.set_manual_sleep_times)
                return False  # Don't consume the event

        # Install event filters
        self.onset_filter = TimeFieldFocusHandler(self, "onset", parent=self)
        self.onset_time_input.installEventFilter(self.onset_filter)

        self.offset_filter = TimeFieldFocusHandler(self, "offset", parent=self)
        self.offset_time_input.installEventFilter(self.offset_filter)

    def _serialize_sleep_period(self, period) -> dict | None:
        """Serialize a sleep period for state capture."""
        if period is None:
            return None

        return {
            "onset_timestamp": period.onset_timestamp,
            "offset_timestamp": period.offset_timestamp,
            "marker_index": period.marker_index,
            "marker_type": period.marker_type.value if period.marker_type else None,
        }

    def _deserialize_sleep_period(self, period_data: dict | None):
        """Deserialize a sleep period for state restore."""
        if period_data is None:
            return None

        from sleep_scoring_app.core.constants import MarkerType
        from sleep_scoring_app.core.dataclasses import SleepPeriod

        marker_type = MarkerType.MAIN_SLEEP  # Default
        if period_data.get("marker_type"):
            try:
                marker_type = MarkerType(period_data["marker_type"])
            except ValueError:
                marker_type = MarkerType.MAIN_SLEEP

        return SleepPeriod(
            onset_timestamp=period_data.get("onset_timestamp"),
            offset_timestamp=period_data.get("offset_timestamp"),
            marker_index=period_data.get("marker_index", 1),
            marker_type=marker_type,
        )

    @pyqtSlot()
    def _on_onset_popout_clicked(self) -> None:
        """Handle onset table pop-out button click."""
        if self.onset_popout_window is None:
            # Create new pop-out window
            self.onset_popout_window = PopOutTableWindow(parent=self.parent, title="Sleep Onset Data - Pop Out", table_type="onset")
            # Connect right-click handler to main window for marker movement
            self.onset_popout_window.table.customContextMenuRequested.connect(lambda pos: self._on_popout_table_right_clicked("onset", pos))
            logger.info("Created onset pop-out window")

        # Show the window and bring to front
        self.onset_popout_window.show()
        self.onset_popout_window.raise_()
        self.onset_popout_window.activateWindow()

        # Populate with full 48-hour data (2880 rows) instead of just 21 rows around marker
        if hasattr(self.parent, "_get_full_48h_data_for_popout"):
            # Get the current onset marker timestamp to highlight and center on it
            onset_timestamp = None
            if hasattr(self.parent, "plot_widget") and hasattr(self.parent.plot_widget, "get_selected_marker_period"):
                selected_period = self.parent.plot_widget.get_selected_marker_period()
                if selected_period and selected_period.onset_timestamp:
                    onset_timestamp = selected_period.onset_timestamp

            # Load data with marker highlighting
            full_data = self.parent._get_full_48h_data_for_popout(marker_timestamp=onset_timestamp)
            if full_data:
                self.onset_popout_window.update_table_data(full_data)
                logger.debug(f"Populated onset pop-out with {len(full_data)} rows (full 48-hour period)")

                # Find and scroll to the highlighted marker row
                if onset_timestamp is not None:
                    for row_idx, row_data in enumerate(full_data):
                        if row_data.get("is_marker", False):
                            self.onset_popout_window.scroll_to_row(row_idx)
                            logger.debug(f"Scrolled onset pop-out to marker at row {row_idx}")
                            break

        logger.debug("Onset pop-out window shown")

    @pyqtSlot()
    def _on_offset_popout_clicked(self) -> None:
        """Handle offset table pop-out button click."""
        if self.offset_popout_window is None:
            # Create new pop-out window
            self.offset_popout_window = PopOutTableWindow(parent=self.parent, title="Sleep Offset Data - Pop Out", table_type="offset")
            # Connect right-click handler to main window for marker movement
            self.offset_popout_window.table.customContextMenuRequested.connect(lambda pos: self._on_popout_table_right_clicked("offset", pos))
            logger.info("Created offset pop-out window")

        # Show the window and bring to front
        self.offset_popout_window.show()
        self.offset_popout_window.raise_()
        self.offset_popout_window.activateWindow()

        # Populate with full 48-hour data (2880 rows) instead of just 21 rows around marker
        if hasattr(self.parent, "_get_full_48h_data_for_popout"):
            # Get the current offset marker timestamp to highlight and center on it
            offset_timestamp = None
            if hasattr(self.parent, "plot_widget") and hasattr(self.parent.plot_widget, "get_selected_marker_period"):
                selected_period = self.parent.plot_widget.get_selected_marker_period()
                if selected_period and selected_period.offset_timestamp:
                    offset_timestamp = selected_period.offset_timestamp

            # Load data with marker highlighting
            full_data = self.parent._get_full_48h_data_for_popout(marker_timestamp=offset_timestamp)
            if full_data:
                self.offset_popout_window.update_table_data(full_data)
                logger.debug(f"Populated offset pop-out with {len(full_data)} rows (full 48-hour period)")

                # Find and scroll to the highlighted marker row
                if offset_timestamp is not None:
                    for row_idx, row_data in enumerate(full_data):
                        if row_data.get("is_marker", False):
                            self.offset_popout_window.scroll_to_row(row_idx)
                            logger.debug(f"Scrolled offset pop-out to marker at row {row_idx}")
                            break

        logger.debug("Offset pop-out window shown")

    def _on_popout_table_right_clicked(self, table_type: str, pos) -> None:
        """Handle right-click on pop-out table cell - move marker to clicked row."""
        # Get the appropriate window
        window = self.onset_popout_window if table_type == "onset" else self.offset_popout_window
        if window is None:
            logger.warning(f"Pop-out window for {table_type} is None")
            return

        # Get the item at the clicked position
        item = window.table.itemAt(pos)
        if item is None:
            logger.warning(f"No item at position {pos}")
            return

        row = item.row()
        logger.info(f"Pop-out {table_type} table: Right-clicked on row {row}, moving marker")

        # Clear selection to prevent highlighting on right-click
        window.table.clearSelection()

        # Get the timestamp from the row data
        timestamp = window.get_timestamp_for_row(row)
        if timestamp is None:
            logger.warning(f"No timestamp available for row {row}")
            return

        # Move the marker using the main window's method
        if hasattr(self.parent, "move_marker_to_timestamp"):
            self.parent.move_marker_to_timestamp(table_type, timestamp)
            logger.debug(f"Moved {table_type} marker to timestamp {timestamp}")
        else:
            logger.warning("Parent does not have move_marker_to_timestamp method")

    def cleanup_tab(self) -> None:
        """Clean up tab resources to prevent memory leaks."""
        try:
            # Close pop-out windows if they exist
            if self.onset_popout_window is not None:
                self.onset_popout_window.close()
                self.onset_popout_window = None

            if self.offset_popout_window is not None:
                self.offset_popout_window.close()
                self.offset_popout_window = None

            # Disconnect signals to prevent reference cycles
            try:
                if hasattr(self, "file_selector") and self.file_selector:
                    self.file_selector.fileSelected.disconnect()
            except (TypeError, RuntimeError):
                # Signal already disconnected or object deleted
                pass

            try:
                if hasattr(self, "activity_source_dropdown") and self.activity_source_dropdown:
                    self.activity_source_dropdown.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                # Signal already disconnected or object deleted
                pass

            try:
                if hasattr(self, "date_dropdown") and self.date_dropdown:
                    self.date_dropdown.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                # Signal already disconnected or object deleted
                pass

            # Clean up plot widget if it exists
            if hasattr(self, "plot_widget") and self.plot_widget:
                if hasattr(self.plot_widget, "cleanup_widget"):
                    self.plot_widget.cleanup_widget()

            logger.debug("AnalysisTab cleanup completed")

        except Exception as e:
            logger.warning(f"Error during AnalysisTab cleanup: {e}")
