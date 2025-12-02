#!/usr/bin/env python3
"""
File Selection Table Widget
A sortable, filterable table for selecting files with detailed participant information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)


class TableColumn(StrEnum):
    """Table column identifiers."""

    FILENAME = "filename"
    PARTICIPANT_ID = "participant_id"
    TIMEPOINT = "timepoint"
    GROUP = "group"
    START_DATE = "start_date"
    END_DATE = "end_date"
    MARKERS = "markers"


@dataclass
class ColumnDefinition:
    """Definition for a table column."""

    id: TableColumn
    header: str
    width_mode: QHeaderView.ResizeMode
    width_hint: int | None = None
    extractor: Callable[[dict[str, Any]], str] | None = None
    formatter: Callable[[Any], str] | None = None
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter


class FileSelectionTable(QWidget):
    """A table widget for file selection with filtering and sorting capabilities."""

    # Signal emitted when a file is selected (row index, file_info)
    fileSelected = pyqtSignal(int, object)

    # Column definitions - easily extensible
    COLUMN_DEFINITIONS: ClassVar[list[ColumnDefinition]] = [
        ColumnDefinition(
            id=TableColumn.FILENAME,
            header="Filename",
            width_mode=QHeaderView.ResizeMode.Stretch,
            extractor=lambda info: info.get("filename", ""),
        ),
        ColumnDefinition(
            id=TableColumn.PARTICIPANT_ID,
            header="Participant ID",
            width_mode=QHeaderView.ResizeMode.ResizeToContents,
            extractor=None,  # Will use special handling for parsed participant info
        ),
        ColumnDefinition(
            id=TableColumn.TIMEPOINT,
            header="Timepoint",
            width_mode=QHeaderView.ResizeMode.ResizeToContents,
            extractor=None,  # Will use special handling for parsed participant info
        ),
        ColumnDefinition(
            id=TableColumn.GROUP,
            header="Group",
            width_mode=QHeaderView.ResizeMode.ResizeToContents,
            extractor=None,  # Will use special handling for parsed participant info
        ),
        ColumnDefinition(
            id=TableColumn.START_DATE,
            header="Start Date",
            width_mode=QHeaderView.ResizeMode.ResizeToContents,
            extractor=lambda info: info.get("start_date", ""),
        ),
        ColumnDefinition(
            id=TableColumn.END_DATE,
            header="End Date",
            width_mode=QHeaderView.ResizeMode.ResizeToContents,
            extractor=lambda info: info.get("end_date", ""),
        ),
        ColumnDefinition(
            id=TableColumn.MARKERS,
            header="Markers",
            width_mode=QHeaderView.ResizeMode.ResizeToContents,
            formatter=lambda info: f"({info.get('completed_count', 0)}/{info.get('total_count', 0)})",
        ),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._file_data = []  # Store complete file info for each row
        self._column_map = {col.id: idx for idx, col in enumerate(self.COLUMN_DEFINITIONS)}
        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search/filter box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search files...")
        self.search_box.textChanged.connect(self.filter_table)
        layout.addWidget(self.search_box)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMN_DEFINITIONS))

        # Set headers from column definitions
        headers = [col.header for col in self.COLUMN_DEFINITIONS]
        self.table.setHorizontalHeaderLabels(headers)

        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Add focus indicator
        self.table.setStyleSheet("""
            QTableWidget:focus {
                border: 2px solid #0080FF;
            }
            QTableWidget::item:focus {
                background-color: #f0f8ff;
                color: #000000;
                border: 1px solid #0080FF;
            }
            QTableWidget::item:selected {
                background-color: #1a5490;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #e6f3ff;
                color: #000000;
            }
            QTableWidget {
                selection-background-color: #1a5490;
                selection-color: white;
            }
        """)

        # Configure column widths from definitions
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)

        for idx, col_def in enumerate(self.COLUMN_DEFINITIONS):
            header.setSectionResizeMode(idx, col_def.width_mode)
            if col_def.width_hint:
                self.table.setColumnWidth(idx, col_def.width_hint)

        # Connect selection signal
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

    def add_file(self, file_info: dict[str, Any], color: QColor | None = None) -> None:
        """
        Add a file to the table.

        Args:
            file_info: Dictionary containing file information with keys:
                - filename: str
                - path: str (optional)
                - source: str (optional, 'database' or 'csv')
                - completed_count: int
                - total_count: int
                - start_date: str (optional)
                - end_date: str (optional)
                - date_range: str (optional)
            color: Optional color for the marker status text

        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Store complete file info and remember the original index
        original_index = len(self._file_data)
        self._file_data.append(file_info)

        # Extract participant info from filename
        filename = file_info.get("filename", "")
        participant_info = self._parse_participant_info(filename)

        # Merge participant info with file info for extractors
        merged_info = {**file_info, **participant_info}

        # Populate columns based on definitions
        for col_idx, col_def in enumerate(self.COLUMN_DEFINITIONS):
            # Get value using extractor or formatter
            if col_def.formatter:
                value = col_def.formatter(merged_info)
            elif col_def.extractor:
                value = col_def.extractor(merged_info)
            # Special handling for parsed participant fields
            elif col_def.id == TableColumn.PARTICIPANT_ID:
                value = participant_info.get("id", "")
            elif col_def.id == TableColumn.TIMEPOINT:
                value = participant_info.get("timepoint", "")
            elif col_def.id == TableColumn.GROUP:
                value = participant_info.get("group", "")
            else:
                value = ""

            # Create table item
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(col_def.alignment)

            # Store the original data index in the first column's item for row mapping
            if col_idx == 0:
                item.setData(Qt.ItemDataRole.UserRole, original_index)

            # Apply color to markers column if provided
            if col_def.id == TableColumn.MARKERS and color:
                item.setForeground(color)

            self.table.setItem(row, col_idx, item)

    def _parse_participant_info(self, filename: str) -> dict[str, str]:
        """Parse participant information from filename using centralized extraction logic."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        info = extract_participant_info(filename)
        return {
            "id": info.numerical_id,
            "timepoint": info.timepoint,
            "group": info.group,
        }

    def clear(self) -> None:
        """Clear all files from the table."""
        self.table.clearContents()
        self.table.setRowCount(0)
        self._file_data.clear()

    def filter_table(self, text: str) -> None:
        """Filter table rows based on search text."""
        search_text = text.lower()

        for row in range(self.table.rowCount()):
            # Check if any column contains the search text
            should_show = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    should_show = True
                    break

            # Show/hide row
            self.table.setRowHidden(row, not should_show)

    @pyqtSlot()
    def _on_selection_changed(self) -> None:
        """Handle selection changes in the table."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        # Get the row of the first selected item
        visual_row = selected_items[0].row()

        # Skip if row is hidden (filtered out)
        if self.table.isRowHidden(visual_row):
            return

        # Get the original data index from the first column's item
        first_column_item = self.table.item(visual_row, 0)
        if not first_column_item:
            return

        original_index = first_column_item.data(Qt.ItemDataRole.UserRole)
        if original_index is None or not (0 <= original_index < len(self._file_data)):
            logger.warning("Invalid original index %s for visual row %s", original_index, visual_row)
            return

        # Get the actual file info using the original index
        file_info = self._file_data[original_index]
        logger.info("File selected from table: visual_row=%s, original_index=%s, filename=%s", visual_row, original_index, file_info.get("filename"))
        self.fileSelected.emit(original_index, file_info)

    def get_file_info_for_row(self, visual_row: int) -> dict[str, Any] | None:
        """Get the file info for a specific visual row in the table."""
        if visual_row < 0 or visual_row >= self.table.rowCount():
            return None

        first_column_item = self.table.item(visual_row, 0)
        if not first_column_item:
            return None

        original_index = first_column_item.data(Qt.ItemDataRole.UserRole)
        if original_index is None or not (0 <= original_index < len(self._file_data)):
            return None

        return self._file_data[original_index]

    def get_selected_file_info(self) -> dict[str, Any] | None:
        """Get the currently selected file info."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return None

        visual_row = selected_items[0].row()
        return self.get_file_info_for_row(visual_row)

    def get_column_index(self, column_id: TableColumn) -> int:
        """Get the index of a column by its ID."""
        return self._column_map.get(column_id, -1)

    def set_date_range_for_row(self, row: int, start_date: str, end_date: str) -> None:
        """Update the date range information for a specific row."""
        if 0 <= row < self.table.rowCount():
            # Use column map to find correct indices
            start_col = self.get_column_index(TableColumn.START_DATE)
            end_col = self.get_column_index(TableColumn.END_DATE)

            if start_col >= 0:
                item = self.table.item(row, start_col)
                if item:
                    item.setText(start_date)

            if end_col >= 0:
                item = self.table.item(row, end_col)
                if item:
                    item.setText(end_date)

    def add_column(self, column_def: ColumnDefinition, position: int | None = None) -> None:
        """
        Add a new column to the table dynamically.

        Args:
            column_def: Column definition to add
            position: Position to insert column (None = end)

        """
        if position is None:
            position = len(self.COLUMN_DEFINITIONS)

        # Insert column definition
        self.COLUMN_DEFINITIONS.insert(position, column_def)

        # Rebuild column map
        self._column_map = {col.id: idx for idx, col in enumerate(self.COLUMN_DEFINITIONS)}

        # Insert column in table
        self.table.insertColumn(position)

        # Update headers
        headers = [col.header for col in self.COLUMN_DEFINITIONS]
        self.table.setHorizontalHeaderLabels(headers)

        # Configure new column
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(position, column_def.width_mode)
        if column_def.width_hint:
            self.table.setColumnWidth(position, column_def.width_hint)
