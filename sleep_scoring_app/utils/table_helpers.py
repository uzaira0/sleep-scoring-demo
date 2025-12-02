#!/usr/bin/env python3
"""
Table Helper Utilities
Shared table creation and management functions to eliminate code duplication.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sleep_scoring_app.core.constants import (
    TableColumn,
    TableDimensions,
    TooltipText,
)

if TYPE_CHECKING:
    from sleep_scoring_app.ui.widgets.activity_plot import ActivityPlotWidget

logger = logging.getLogger(__name__)


def _recalculate_visible_rows(table: QTableWidget) -> None:
    """Recalculate which rows to show based on current viewport size, centering on marker row."""
    container = table.parent()
    if not container:
        return

    # Get stored data from container
    data = getattr(container, "_table_data", None)
    marker_row = getattr(container, "_marker_row", None)

    if data is None or marker_row is None:
        return

    row_height = TableDimensions.ROW_HEIGHT
    viewport_height = table.viewport().height()
    table_row_count = table.rowCount()

    # Calculate how many rows can be displayed
    if viewport_height > 0 and row_height > 0:
        visible_rows = max(1, viewport_height // row_height)
    else:
        visible_rows = 9  # Fallback

    # Calculate which rows to show, centered on marker_row
    rows_before_marker = visible_rows // 2
    rows_after_marker = visible_rows - rows_before_marker - 1

    first_visible = max(0, marker_row - rows_before_marker)
    last_visible = min(len(data) - 1, marker_row + rows_after_marker)

    # Adjust if we hit the top boundary
    if marker_row - rows_before_marker < 0:
        last_visible = min(len(data) - 1, visible_rows - 1)
        first_visible = 0

    # Adjust if we hit the bottom boundary
    if marker_row + rows_after_marker >= len(data):
        first_visible = max(0, len(data) - visible_rows)
        last_visible = len(data) - 1

    # Hide all rows outside the visible range
    for row in range(table_row_count):
        if row < len(data) and first_visible <= row <= last_visible:
            table.setRowHidden(row, False)
        else:
            table.setRowHidden(row, True)


class _TableResizeFilter(QObject):
    """Event filter to handle table resize events and recalculate visible rows."""

    def __init__(self, table: QTableWidget) -> None:
        super().__init__()
        self._table = table

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            _recalculate_visible_rows(self._table)
        return False


def create_marker_data_table(title: str) -> QWidget:
    """
    Create a standardized data table widget for showing surrounding marker data.

    This consolidates the duplicate table creation logic from analysis_tab.py
    and main_window.py into a single shared function.

    Args:
        title: Title for the table (not displayed, but used for identification)

    Returns:
        QWidget containing the configured table

    """
    container = QWidget()
    container.setMinimumWidth(TableDimensions.TABLE_MIN_WIDTH)
    container.setMaximumWidth(TableDimensions.TABLE_MAX_WIDTH)
    container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

    layout = QVBoxLayout(container)
    layout.setContentsMargins(
        TableDimensions.TABLE_MARGINS, TableDimensions.TABLE_MARGINS, TableDimensions.TABLE_MARGINS, TableDimensions.TABLE_MARGINS
    )
    layout.setSpacing(TableDimensions.TABLE_SPACING)

    # Table widget (pop-out button is now created separately in analysis_tab.py)
    table = QTableWidget()
    table.setColumnCount(6)  # Full functionality with Choi and NWT restored (2025-09-08)
    table.setHorizontalHeaderLabels(
        [
            TableColumn.TIME,
            TableColumn.AXIS_Y,
            TableColumn.VM,  # Vector Magnitude column
            TableColumn.SADEH,
            TableColumn.CHOI,  # Re-enabled (2025-09-08)
            TableColumn.NWT_SENSOR,  # Re-enabled (2025-09-08)
        ]
    )
    table.setRowCount(TableDimensions.ROW_COUNT)  # 21 total elements

    # Center align all headers and add tooltips
    tooltips = [
        TooltipText.TIME_COLUMN,
        TooltipText.ACTIVITY_COLUMN,
        TooltipText.VM_COLUMN,
        TooltipText.SADEH_COLUMN,
        TooltipText.CHOI_COLUMN,
        TooltipText.NWT_SENSOR_COLUMN,
    ]

    for i, tooltip_text in enumerate(tooltips):
        header_item = table.horizontalHeaderItem(i)
        if header_item:
            header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            header_item.setToolTip(tooltip_text)

    # Configure table behavior
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Enable focus for keyboard navigation
    table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Enable multi-row selection
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)  # Select entire rows when clicked
    table.setAlternatingRowColors(True)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    # Enable right-click context menu for marker movement
    table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    # Add hover and selection styling
    from sleep_scoring_app.core.constants import UIColors

    table.setStyleSheet(f"""
        QTableWidget::item:hover {{
            background-color: {UIColors.DIARY_SELECTION_DARKER};
            color: white;
        }}
        QTableWidget::item:selected {{
            background-color: {UIColors.DIARY_SELECTION_DARKER};
            color: white;
        }}
    """)

    # Configure headers
    horizontal_header = table.horizontalHeader()
    if horizontal_header:
        horizontal_header.setMaximumHeight(TableDimensions.TABLE_HEADER_HEIGHT)
        horizontal_header.setStretchLastSection(False)
        # Use dynamic column sizing
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Time
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Axis1
        horizontal_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # VM
        horizontal_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Sadeh
        horizontal_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Choi - Re-enabled (2025-09-08)
        horizontal_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # NWT - Re-enabled (2025-09-08)

    vertical_header = table.verticalHeader()
    if vertical_header:
        vertical_header.setVisible(False)
        vertical_header.setDefaultSectionSize(TableDimensions.ROW_HEIGHT)

    # Set font
    font = table.font()
    font.setPointSize(TableDimensions.TABLE_FONT_SIZE)
    table.setFont(font)

    # Store reference to table widget for external access
    container.table_widget = table

    # Initially populate with empty data
    _populate_empty_table_rows(table)

    # Add table to layout
    layout.addWidget(table)

    # Configure size policy - table fills available space and scrolls if needed
    table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    # Install resize event filter to dynamically recalculate visible rows
    resize_filter = _TableResizeFilter(table)
    table.viewport().installEventFilter(resize_filter)
    # Keep reference to prevent garbage collection
    container._resize_filter = resize_filter

    return container


def _populate_empty_table_rows(table: QTableWidget) -> None:
    """Populate table with empty placeholder data."""
    for row in range(TableDimensions.ROW_COUNT):
        items = [
            QTableWidgetItem("--:--"),
            QTableWidgetItem("--"),
            QTableWidgetItem("--"),
            QTableWidgetItem("--"),
            QTableWidgetItem("--"),  # Choi column
            QTableWidgetItem("--"),  # NWT column - Re-added (2025-09-08)
        ]

        for col, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, col, item)


def update_marker_table(
    table_container: QWidget,
    data: list[dict[str, Any]],
    marker_bg_color: QColor,
    marker_fg_color: QColor,
    custom_table_colors: dict[str, str] | None = None,
) -> None:
    """
    Update a marker data table with surrounding marker information.

    This consolidates the duplicate table update logic from main_window.py
    into a shared function.

    Args:
        table_container: Widget containing the table
        data: List of data rows with time, activity, sadeh, choi, nwt_sensor, is_marker
        marker_bg_color: Background color for marker row
        marker_fg_color: Foreground color for marker row
        custom_table_colors: Optional dict with custom colors for onset/offset highlights

    """
    table = getattr(table_container, "table_widget", None)
    if not table:
        logger.warning("Table widget not found in container")
        return

    # Temporarily disable updates for performance
    table.setUpdatesEnabled(False)

    try:
        # Use the actual table row count instead of hardcoded ROW_COUNT
        # This allows the function to work with both embedded tables (21 rows) and pop-out tables (2880 rows)
        table_row_count = table.rowCount()

        for row in range(table_row_count):
            if row < len(data) and data:
                row_data = data[row]

                # Get or create items (reuse existing ones)
                time_item = table.item(row, 0) or QTableWidgetItem()
                axis_y_item = table.item(row, 1) or QTableWidgetItem()
                vm_item = table.item(row, 2) or QTableWidgetItem()
                sadeh_item = table.item(row, 3) or QTableWidgetItem()
                choi_item = table.item(row, 4) or QTableWidgetItem()  # Re-enabled (2025-09-08)
                nwt_item = table.item(row, 5) or QTableWidgetItem()  # Re-enabled (2025-09-08)

                # Update text content
                time_item.setText(row_data["time"])

                # Handle axis_y and vm columns
                axis_y_value = row_data.get("axis_y", row_data.get("activity", "--"))
                vm_value = row_data.get("vm", "--")
                axis_y_item.setText(str(axis_y_value) if axis_y_value != "--" else "--")
                vm_item.setText(str(vm_value) if vm_value != "--" else "--")

                # Handle sadeh results (None, 0, 1)
                sadeh_value = row_data.get("sadeh")
                if sadeh_value == 1:
                    sadeh_item.setText("S")
                elif sadeh_value == 0:
                    sadeh_item.setText("W")
                else:
                    sadeh_item.setText("--")

                # Handle choi results (None, 0, 1) - Re-enabled (2025-09-08)
                choi_value = row_data.get("choi")
                if choi_value == 1:
                    choi_item.setText("Off")
                elif choi_value == 0:
                    choi_item.setText("On")
                else:
                    choi_item.setText("--")

                # Handle NWT sensor results (None, 0, 1) - Re-enabled (2025-09-08)
                nwt_value = row_data.get("nwt_sensor")
                if nwt_value == 1:
                    nwt_item.setText("Off")
                elif nwt_value == 0:
                    nwt_item.setText("On")
                else:
                    nwt_item.setText("--")

                # Set colors based on marker status
                if row_data["is_marker"]:
                    bg_color, fg_color = marker_bg_color, marker_fg_color
                else:
                    bg_color, fg_color = QColor(255, 255, 255), QColor(0, 0, 0)

                # Apply colors, flags, and center alignment efficiently
                for item in [time_item, axis_y_item, vm_item, sadeh_item, choi_item, nwt_item]:  # Re-added choi_item, nwt_item (2025-09-08)
                    item.setBackground(bg_color)
                    item.setForeground(fg_color)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Set items if not already set
                if table.item(row, 0) != time_item:
                    table.setItem(row, 0, time_item)
                if table.item(row, 1) != axis_y_item:
                    table.setItem(row, 1, axis_y_item)
                if table.item(row, 2) != vm_item:
                    table.setItem(row, 2, vm_item)
                if table.item(row, 3) != sadeh_item:
                    table.setItem(row, 3, sadeh_item)
                if table.item(row, 4) != choi_item:
                    table.setItem(row, 4, choi_item)  # Re-enabled (2025-09-08)
                if table.item(row, 5) != nwt_item:
                    table.setItem(row, 5, nwt_item)  # Re-enabled (2025-09-08)

                # Ensure row is visible when it has data
                table.setRowHidden(row, False)

            else:
                # Empty rows - hide them
                table.setRowHidden(row, True)

        # Find the marker row index
        marker_row = None
        for row_idx, row_data in enumerate(data):
            if row_idx < table_row_count and row_data.get("is_marker"):
                marker_row = row_idx
                break

        # Store data and marker_row on container for dynamic resize updates
        table_container._table_data = data
        table_container._marker_row = marker_row

        # Calculate and apply visible rows (centered on marker)
        _recalculate_visible_rows(table)

    finally:
        # Re-enable updates
        table.setUpdatesEnabled(True)


def get_marker_surrounding_data(plot_widget: ActivityPlotWidget, marker_timestamp: float) -> list[dict[str, Any]]:
    """
    Get surrounding data (±10 minutes) for a marker timestamp using robust index finding.

    This moves the duplicate method from main_window.py to a shared location.

    Args:
        plot_widget: The activity plot widget containing data
        marker_timestamp: Timestamp of the marker

    Returns:
        List of data rows containing time, activity, sadeh, choi, nwt_sensor, is_marker

    """
    surrounding_data = []

    # Get data from plot widget
    if not hasattr(plot_widget, "timestamps") or not plot_widget.timestamps:
        logger.debug("No timestamps available in plot widget")
        return surrounding_data

    # Use the plot widget's robust closest index finding method
    marker_idx = plot_widget._find_closest_data_index(marker_timestamp)

    if marker_idx is None:
        logger.debug(f"Could not find index for timestamp {marker_timestamp}")
        return surrounding_data

    logger.debug(f"Found marker index {marker_idx} for timestamp {marker_timestamp} - retrieving {TableDimensions.ROW_COUNT} data points")

    # Get various result arrays from plot widget
    # CRITICAL FIX: Use same data source prioritization as main_window.py
    sadeh_results = getattr(plot_widget, "main_48h_sadeh_results", getattr(plot_widget, "sadeh_results", []))

    # If no Sadeh results available, trigger algorithm calculation
    if not sadeh_results and hasattr(plot_widget, "plot_algorithms") and callable(plot_widget.plot_algorithms):
        try:
            logger.debug("No Sadeh results available, triggering algorithm calculation")
            plot_widget.plot_algorithms()
            # Re-check with same prioritization after algorithm run
            sadeh_results = getattr(plot_widget, "main_48h_sadeh_results", getattr(plot_widget, "sadeh_results", []))
        except Exception as e:
            logger.exception("Failed to run algorithms for table helper: %s", e)
    choi_results = plot_widget.get_choi_results_per_minute() if hasattr(plot_widget, "get_choi_results_per_minute") else []
    nonwear_sensor_results = (
        plot_widget.get_nonwear_sensor_results_per_minute() if hasattr(plot_widget, "get_nonwear_sensor_results_per_minute") else []
    )

    # Get 21 elements around marker (10 before + marker + 10 after)
    start_idx = max(0, marker_idx - TableDimensions.ELEMENTS_AROUND_MARKER)
    end_idx = min(len(plot_widget.timestamps), marker_idx + TableDimensions.ELEMENTS_AROUND_MARKER + 1)

    for i in range(start_idx, end_idx):
        # Improved bounds checking with early continue for safety
        if i >= len(plot_widget.timestamps):
            logger.debug(f"Index {i} exceeds timestamps length {len(plot_widget.timestamps)}, skipping")
            continue

        # Check if axis_y_data exists and has valid index
        if not hasattr(plot_widget, "axis_y_data") or not plot_widget.axis_y_data:
            logger.debug("No axis_y_data available in plot widget")
            continue

        if i >= len(plot_widget.axis_y_data):
            logger.debug(f"Index {i} exceeds axis_y_data length {len(plot_widget.axis_y_data)}, skipping")
            continue

        is_marker = i == marker_idx

        # Safe bounds-checked access for all arrays
        sadeh_value = sadeh_results[i] if sadeh_results and i < len(sadeh_results) else 0
        choi_value = choi_results[i] if choi_results and i < len(choi_results) else 0
        nwt_value = nonwear_sensor_results[i] if nonwear_sensor_results and i < len(nonwear_sensor_results) else 0

        # Ensure axis_y_data value is numeric before converting to int
        try:
            activity_value = int(plot_widget.axis_y_data[i])
        except (ValueError, TypeError):
            logger.warning(f"Invalid activity value at index {i}: {plot_widget.axis_y_data[i]}")
            activity_value = 0

        surrounding_data.append(
            {
                "time": plot_widget.timestamps[i].strftime("%H:%M"),
                "timestamp": plot_widget.timestamps[i].timestamp(),  # Add Unix timestamp for click handler
                "activity": activity_value,
                "sadeh": sadeh_value,
                "choi": choi_value,
                "nwt_sensor": nwt_value,
                "is_marker": is_marker,
            }
        )

    return surrounding_data
