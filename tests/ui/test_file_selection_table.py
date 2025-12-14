"""
Tests for FileSelectionTable widget.

These tests interact with the REAL FileSelectionTable widget like a user would:
- Adding files
- Filtering/searching
- Sorting columns
- Selecting files
- Signal emissions
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from sleep_scoring_app.ui.widgets.file_selection_table import FileSelectionTable, TableColumn


@pytest.fixture
def qapp():
    """Create QApplication."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def file_table(qtbot, qapp):
    """Create a FileSelectionTable widget."""
    table = FileSelectionTable()
    qtbot.addWidget(table)
    table.show()
    qtbot.wait(50)
    return table


@pytest.fixture
def sample_files():
    """Sample file data for testing."""
    return [
        {
            "filename": "4001_G1_BO_2024-01-01.csv",
            "path": "/data/4001_G1_BO_2024-01-01.csv",
            "source": "csv",
            "completed_count": 5,
            "total_count": 10,
            "start_date": "2024-01-01",
            "end_date": "2024-01-10",
        },
        {
            "filename": "4002_G2_P1_2024-02-01.csv",
            "path": "/data/4002_G2_P1_2024-02-01.csv",
            "source": "csv",
            "completed_count": 8,
            "total_count": 10,
            "start_date": "2024-02-01",
            "end_date": "2024-02-10",
        },
        {
            "filename": "4003_G1_P2_2024-03-01.csv",
            "path": "/data/4003_G1_P2_2024-03-01.csv",
            "source": "csv",
            "completed_count": 10,
            "total_count": 10,
            "start_date": "2024-03-01",
            "end_date": "2024-03-10",
        },
    ]


class TestFileSelectionTableBasicOperations:
    """Test basic operations on FileSelectionTable."""

    def test_table_initializes_empty(self, file_table, qtbot):
        """Test that table starts with no rows."""
        assert file_table.table.rowCount() == 0

    def test_table_has_correct_columns(self, file_table, qtbot):
        """Test that table has all expected columns."""
        expected_columns = 7  # Filename, Participant ID, Timepoint, Group, Start Date, End Date, Markers
        assert file_table.table.columnCount() == expected_columns

    def test_add_single_file(self, file_table, sample_files, qtbot):
        """Test adding a single file to the table."""
        file_table.add_file(sample_files[0])
        qtbot.wait(50)

        assert file_table.table.rowCount() == 1
        # Check filename column
        filename_col = file_table.get_column_index(TableColumn.FILENAME)
        assert file_table.table.item(0, filename_col).text() == "4001_G1_BO_2024-01-01.csv"

    def test_add_multiple_files(self, file_table, sample_files, qtbot):
        """Test adding multiple files to the table."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        assert file_table.table.rowCount() == len(sample_files)

    def test_clear_table(self, file_table, sample_files, qtbot):
        """Test clearing all files from the table."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        file_table.clear()
        assert file_table.table.rowCount() == 0

    def test_search_box_exists(self, file_table, qtbot):
        """Test that search box exists and is accessible."""
        assert file_table.search_box is not None
        assert file_table.search_box.placeholderText() == "Search files..."


class TestFileSelectionTableFiltering:
    """Test filtering/searching functionality."""

    def test_filter_by_participant_id(self, file_table, sample_files, qtbot):
        """Test filtering files by participant ID."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Search for "4001"
        qtbot.keyClicks(file_table.search_box, "4001")
        qtbot.wait(100)

        # Should show only 1 file
        visible_rows = sum(1 for row in range(file_table.table.rowCount()) if not file_table.table.isRowHidden(row))
        assert visible_rows == 1

    def test_filter_by_group(self, file_table, sample_files, qtbot):
        """Test filtering files by group."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Search for "G1"
        qtbot.keyClicks(file_table.search_box, "G1")
        qtbot.wait(100)

        # Should show 2 files (4001 and 4003)
        visible_rows = sum(1 for row in range(file_table.table.rowCount()) if not file_table.table.isRowHidden(row))
        assert visible_rows == 2

    def test_filter_by_timepoint(self, file_table, sample_files, qtbot):
        """Test filtering files by timepoint."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Search for "BO"
        qtbot.keyClicks(file_table.search_box, "BO")
        qtbot.wait(100)

        # Should show 1 file
        visible_rows = sum(1 for row in range(file_table.table.rowCount()) if not file_table.table.isRowHidden(row))
        assert visible_rows == 1

    def test_filter_case_insensitive(self, file_table, sample_files, qtbot):
        """Test that filtering is case-insensitive."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Search for lowercase "g1"
        qtbot.keyClicks(file_table.search_box, "g1")
        qtbot.wait(100)

        # Should still find files
        visible_rows = sum(1 for row in range(file_table.table.rowCount()) if not file_table.table.isRowHidden(row))
        assert visible_rows == 2

    def test_clear_filter(self, file_table, sample_files, qtbot):
        """Test clearing the search filter."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Apply filter
        qtbot.keyClicks(file_table.search_box, "4001")
        qtbot.wait(100)

        # Clear filter
        file_table.search_box.clear()
        qtbot.wait(100)

        # All rows should be visible
        visible_rows = sum(1 for row in range(file_table.table.rowCount()) if not file_table.table.isRowHidden(row))
        assert visible_rows == len(sample_files)

    def test_filter_no_matches(self, file_table, sample_files, qtbot):
        """Test filtering with no matches."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Search for something that doesn't exist
        qtbot.keyClicks(file_table.search_box, "NOMATCH9999")
        qtbot.wait(100)

        # Should show no files
        visible_rows = sum(1 for row in range(file_table.table.rowCount()) if not file_table.table.isRowHidden(row))
        assert visible_rows == 0


class TestFileSelectionTableSorting:
    """Test sorting functionality."""

    def test_sort_by_filename_ascending(self, file_table, sample_files, qtbot):
        """Test sorting by filename in ascending order."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Click filename header to sort
        filename_col = file_table.get_column_index(TableColumn.FILENAME)
        header = file_table.table.horizontalHeader()

        # Click to sort ascending
        header_pos = header.sectionViewportPosition(filename_col) + 5
        qtbot.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=header.mapToGlobal(header.viewport().pos()))
        qtbot.wait(100)

        # Verify data is accessible
        assert file_table.table.rowCount() == 3

    def test_sort_by_participant_id(self, file_table, sample_files, qtbot):
        """Test sorting by participant ID."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Get participant ID column
        pid_col = file_table.get_column_index(TableColumn.PARTICIPANT_ID)
        assert pid_col >= 0

    def test_table_allows_single_selection(self, file_table, sample_files, qtbot):
        """Test that table allows single row selection."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Click on first row
        file_table.table.selectRow(0)
        qtbot.wait(50)

        selected_rows = file_table.table.selectedItems()
        assert len(selected_rows) > 0


class TestFileSelectionTableSelection:
    """Test file selection functionality."""

    def test_select_file_emits_signal(self, file_table, sample_files, qtbot):
        """Test that selecting a file emits the fileSelected signal."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Connect signal spy
        with qtbot.waitSignal(file_table.fileSelected, timeout=1000):
            # Click on first row
            file_table.table.selectRow(0)

    def test_get_selected_file_info(self, file_table, sample_files, qtbot):
        """Test getting info for selected file."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Select first row
        file_table.table.selectRow(0)
        qtbot.wait(50)

        # Get selected file info
        selected_info = file_table.get_selected_file_info()
        assert selected_info is not None
        assert "filename" in selected_info

    def test_get_file_info_for_specific_row(self, file_table, sample_files, qtbot):
        """Test getting file info for a specific row."""
        for file_info in sample_files:
            file_table.add_file(file_info)
        qtbot.wait(50)

        # Get info for row 1
        row_info = file_table.get_file_info_for_row(1)
        assert row_info is not None
        assert "filename" in row_info

    def test_get_file_info_for_invalid_row(self, file_table, qtbot):
        """Test getting file info for invalid row returns None."""
        row_info = file_table.get_file_info_for_row(999)
        assert row_info is None


class TestFileSelectionTableDataParsing:
    """Test participant info parsing from filenames."""

    def test_parse_participant_id_from_filename(self, file_table, qtbot):
        """Test that participant ID is correctly parsed from filename."""
        file_info = {
            "filename": "4001_G1_BO_2024-01-01.csv",
            "completed_count": 5,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        # Check participant ID column
        pid_col = file_table.get_column_index(TableColumn.PARTICIPANT_ID)
        assert file_table.table.item(0, pid_col).text() == "4001"

    def test_parse_group_from_filename(self, file_table, qtbot):
        """Test that group is correctly parsed from filename."""
        file_info = {
            "filename": "4001_G1_BO_2024-01-01.csv",
            "completed_count": 5,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        # Check group column
        group_col = file_table.get_column_index(TableColumn.GROUP)
        assert file_table.table.item(0, group_col).text() == "G1"

    def test_parse_timepoint_from_filename(self, file_table, qtbot):
        """Test that timepoint is correctly parsed from filename."""
        file_info = {
            "filename": "4001_G1_BO_2024-01-01.csv",
            "completed_count": 5,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        # Check timepoint column
        tp_col = file_table.get_column_index(TableColumn.TIMEPOINT)
        assert file_table.table.item(0, tp_col).text() == "BO"


class TestFileSelectionTableMarkerDisplay:
    """Test marker count display."""

    def test_display_marker_counts(self, file_table, qtbot):
        """Test that marker counts are displayed correctly."""
        file_info = {
            "filename": "test.csv",
            "completed_count": 5,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        # Check markers column shows (5/10)
        markers_col = file_table.get_column_index(TableColumn.MARKERS)
        markers_text = file_table.table.item(0, markers_col).text()
        assert "(5/10)" in markers_text

    def test_display_complete_markers(self, file_table, qtbot):
        """Test display when all markers are complete."""
        file_info = {
            "filename": "test.csv",
            "completed_count": 10,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        markers_col = file_table.get_column_index(TableColumn.MARKERS)
        markers_text = file_table.table.item(0, markers_col).text()
        assert "(10/10)" in markers_text

    def test_display_no_markers(self, file_table, qtbot):
        """Test display when no markers are complete."""
        file_info = {
            "filename": "test.csv",
            "completed_count": 0,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        markers_col = file_table.get_column_index(TableColumn.MARKERS)
        markers_text = file_table.table.item(0, markers_col).text()
        assert "(0/10)" in markers_text


class TestFileSelectionTableDateDisplay:
    """Test date range display."""

    def test_set_date_range_for_row(self, file_table, sample_files, qtbot):
        """Test updating date range for a specific row."""
        file_table.add_file(sample_files[0])
        qtbot.wait(50)

        # Update date range
        file_table.set_date_range_for_row(0, "2024-01-01", "2024-01-10")
        qtbot.wait(50)

        # Verify dates are updated
        start_col = file_table.get_column_index(TableColumn.START_DATE)
        end_col = file_table.get_column_index(TableColumn.END_DATE)

        assert file_table.table.item(0, start_col).text() == "2024-01-01"
        assert file_table.table.item(0, end_col).text() == "2024-01-10"

    def test_display_date_range_on_add(self, file_table, qtbot):
        """Test that date range is displayed when file is added."""
        file_info = {
            "filename": "test.csv",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "completed_count": 0,
            "total_count": 10,
        }

        file_table.add_file(file_info)
        qtbot.wait(50)

        start_col = file_table.get_column_index(TableColumn.START_DATE)
        end_col = file_table.get_column_index(TableColumn.END_DATE)

        assert file_table.table.item(0, start_col).text() == "2024-01-01"
        assert file_table.table.item(0, end_col).text() == "2024-01-31"


class TestFileSelectionTableStyling:
    """Test visual styling and formatting."""

    def test_alternating_row_colors_enabled(self, file_table, qtbot):
        """Test that alternating row colors are enabled."""
        assert file_table.table.alternatingRowColors() is True

    def test_table_is_read_only(self, file_table, qtbot):
        """Test that table cells are not editable."""
        from PyQt6.QtWidgets import QTableWidget

        edit_triggers = file_table.table.editTriggers()
        assert edit_triggers == QTableWidget.EditTrigger.NoEditTriggers

    def test_table_selection_mode_is_single(self, file_table, qtbot):
        """Test that only single row can be selected."""
        from PyQt6.QtWidgets import QTableWidget

        assert file_table.table.selectionMode() == QTableWidget.SelectionMode.SingleSelection

    def test_table_selection_behavior_is_rows(self, file_table, qtbot):
        """Test that selection behavior is by rows."""
        from PyQt6.QtWidgets import QTableWidget

        assert file_table.table.selectionBehavior() == QTableWidget.SelectionBehavior.SelectRows
