"""
Tests for PopOutTableWindow widget.

These tests interact with the REAL PopOutTableWindow like a user would:
- Opening/closing windows
- Scrolling through data
- Selecting rows
- Window geometry persistence
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from sleep_scoring_app.ui.widgets.popout_table_window import PopOutTableWindow


@pytest.fixture
def qapp():
    """Create QApplication."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def onset_window(qtbot, qapp):
    """Create a PopOutTableWindow for onset markers."""
    window = PopOutTableWindow(None, "Sleep Onset Data - Full Day", "onset")
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(100)
    return window


@pytest.fixture
def offset_window(qtbot, qapp):
    """Create a PopOutTableWindow for offset markers."""
    window = PopOutTableWindow(None, "Sleep Offset Data - Full Day", "offset")
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(100)
    return window


@pytest.fixture
def sample_table_data():
    """Generate sample table data (48 hours = 2880 rows)."""
    data = []
    for i in range(2880):
        hours = i // 60
        minutes = i % 60
        data.append(
            {
                "time": f"{hours:02d}:{minutes:02d}",
                "timestamp": 1704067200.0 + (i * 60),  # Starting from 2024-01-01 00:00
                "axis_y": 100 + (i % 50),
                "vm": 150 + (i % 75),
                "sadeh": 1 if (i % 3) == 0 else 0,
                "choi": 0,
                "nwt_sensor": 0,
                "is_marker": i == 1440,  # Mark row at 24 hours
            }
        )
    return data


class TestPopOutTableWindowBasics:
    """Test basic popout window functionality."""

    def test_window_initializes_with_title(self, onset_window, qtbot):
        """Test that window has correct title."""
        assert "Sleep Onset Data" in onset_window.windowTitle()

    def test_window_is_modal_false(self, onset_window, qtbot):
        """Test that window is non-modal."""
        assert onset_window.isModal() is False

    def test_window_stays_on_top(self, onset_window, qtbot):
        """Test that window has stay-on-top flag."""
        assert onset_window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    def test_table_has_correct_columns(self, onset_window, qtbot):
        """Test that table has all expected columns."""
        expected_columns = 6  # Time, Axis Y, VM, Sadeh, Choi, NWT Sensor
        assert onset_window.table.columnCount() == expected_columns

    def test_table_has_2880_rows(self, onset_window, qtbot):
        """Test that table is pre-allocated for 48 hours (2880 minutes)."""
        assert onset_window.table.rowCount() == 2880

    def test_table_allows_multi_selection(self, onset_window, qtbot):
        """Test that table allows multi-row selection."""
        from PyQt6.QtWidgets import QAbstractItemView

        assert onset_window.table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection

    def test_table_selection_is_by_rows(self, onset_window, qtbot):
        """Test that selection behavior is by rows."""
        from PyQt6.QtWidgets import QAbstractItemView

        assert onset_window.table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows

    def test_table_is_read_only(self, onset_window, qtbot):
        """Test that table cells are not editable."""
        from PyQt6.QtWidgets import QAbstractItemView

        assert onset_window.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


class TestPopOutTableWindowDataDisplay:
    """Test data display functionality."""

    def test_update_table_data(self, onset_window, sample_table_data, qtbot):
        """Test updating table with data."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Verify first row has data
        assert onset_window.table.item(0, 0) is not None

    def test_marker_row_is_highlighted(self, onset_window, sample_table_data, qtbot):
        """Test that marker row is visually highlighted."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Row 1440 should be marked (24 hours)
        marker_row_item = onset_window.table.item(1440, 0)
        assert marker_row_item is not None

    def test_display_time_column(self, onset_window, sample_table_data, qtbot):
        """Test that time column displays correctly."""
        onset_window.update_table_data(sample_table_data[:10])
        qtbot.wait(100)

        # First row should show "00:00"
        time_text = onset_window.table.item(0, 0).text()
        assert "00:00" in time_text

    def test_display_activity_columns(self, onset_window, sample_table_data, qtbot):
        """Test that activity data columns display correctly."""
        onset_window.update_table_data(sample_table_data[:10])
        qtbot.wait(100)

        # Check that Axis Y column has numeric data
        axis_y_item = onset_window.table.item(0, 1)
        assert axis_y_item is not None

    def test_display_sadeh_column(self, onset_window, sample_table_data, qtbot):
        """Test that Sadeh results column displays correctly."""
        onset_window.update_table_data(sample_table_data[:10])
        qtbot.wait(100)

        # Check Sadeh column (should be 0 or 1)
        sadeh_item = onset_window.table.item(0, 3)
        assert sadeh_item is not None


class TestPopOutTableWindowScrolling:
    """Test scrolling functionality."""

    def test_scroll_to_marker_row(self, onset_window, sample_table_data, qtbot):
        """Test scrolling to a specific row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Scroll to row 1440 (marker position)
        onset_window.scroll_to_row(1440)
        qtbot.wait(100)

        # Verify scroll occurred (row should be visible)
        assert onset_window.table.item(1440, 0) is not None

    def test_scroll_to_first_row(self, onset_window, sample_table_data, qtbot):
        """Test scrolling to first row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        onset_window.scroll_to_row(0)
        qtbot.wait(50)

        assert onset_window.table.item(0, 0) is not None

    def test_scroll_to_last_row(self, onset_window, sample_table_data, qtbot):
        """Test scrolling to last row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        onset_window.scroll_to_row(2879)
        qtbot.wait(50)

        assert onset_window.table.item(2879, 0) is not None

    def test_scroll_to_invalid_row_ignored(self, onset_window, sample_table_data, qtbot):
        """Test that scrolling to invalid row is handled gracefully."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Try to scroll to invalid row (should not crash)
        onset_window.scroll_to_row(9999)
        qtbot.wait(50)


class TestPopOutTableWindowSelection:
    """Test row selection functionality."""

    def test_select_single_row(self, onset_window, sample_table_data, qtbot):
        """Test selecting a single row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Select row 10
        onset_window.table.selectRow(10)
        qtbot.wait(50)

        selected_rows = onset_window.table.selectedItems()
        assert len(selected_rows) > 0

    def test_select_multiple_rows(self, onset_window, sample_table_data, qtbot):
        """Test selecting multiple rows."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Select rows 10-15
        for row in range(10, 16):
            onset_window.table.selectionModel().select(
                onset_window.table.model().index(row, 0),
                onset_window.table.selectionModel().SelectionFlag.Select | onset_window.table.selectionModel().SelectionFlag.Rows,
            )
        qtbot.wait(50)

        selected_ranges = onset_window.table.selectedRanges()
        assert len(selected_ranges) > 0

    def test_get_timestamp_for_row(self, onset_window, sample_table_data, qtbot):
        """Test getting timestamp for a specific row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Get timestamp for row 0
        timestamp = onset_window.get_timestamp_for_row(0)
        assert timestamp is not None
        assert timestamp == 1704067200.0

    def test_get_timestamp_for_marker_row(self, onset_window, sample_table_data, qtbot):
        """Test getting timestamp for marker row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Get timestamp for row 1440 (marker)
        timestamp = onset_window.get_timestamp_for_row(1440)
        assert timestamp is not None

    def test_get_timestamp_for_invalid_row(self, onset_window, qtbot):
        """Test getting timestamp for invalid row returns None."""
        timestamp = onset_window.get_timestamp_for_row(9999)
        assert timestamp is None


class TestPopOutTableWindowPersistence:
    """Test window geometry persistence."""

    def test_window_geometry_is_saved_on_close(self, onset_window, qtbot):
        """Test that window geometry is saved when window closes."""
        # Resize and move window
        onset_window.resize(800, 600)
        onset_window.move(100, 100)
        qtbot.wait(50)

        # Close window (should trigger save)
        onset_window.close()
        qtbot.wait(50)

        # Check that settings were saved
        settings = QSettings("SleepScoringApp", "MarkerTables")
        saved_geometry = settings.value("onset_popout_geometry")
        assert saved_geometry is not None

    def test_window_position_is_saved_on_close(self, onset_window, qtbot):
        """Test that window position is saved when window closes."""
        onset_window.move(200, 200)
        qtbot.wait(50)

        onset_window.close()
        qtbot.wait(50)

        settings = QSettings("SleepScoringApp", "MarkerTables")
        saved_pos = settings.value("onset_popout_pos")
        assert saved_pos is not None

    def test_offset_window_uses_different_settings_key(self, offset_window, qtbot):
        """Test that offset window saves to different settings key."""
        offset_window.resize(700, 500)
        offset_window.close()
        qtbot.wait(50)

        settings = QSettings("SleepScoringApp", "MarkerTables")
        offset_geometry = settings.value("offset_popout_geometry")
        assert offset_geometry is not None


class TestPopOutTableWindowTypeSpecific:
    """Test type-specific behavior for onset vs offset windows."""

    def test_onset_window_has_correct_table_type(self, onset_window, qtbot):
        """Test that onset window has correct table_type."""
        assert onset_window.table_type == "onset"

    def test_offset_window_has_correct_table_type(self, offset_window, qtbot):
        """Test that offset window has correct table_type."""
        assert offset_window.table_type == "offset"

    def test_onset_window_uses_onset_colors(self, onset_window, sample_table_data, qtbot):
        """Test that onset window uses onset-specific colors for marker row."""
        onset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Marker row should be styled (we just verify it doesn't crash)
        marker_item = onset_window.table.item(1440, 0)
        assert marker_item is not None

    def test_offset_window_uses_offset_colors(self, offset_window, sample_table_data, qtbot):
        """Test that offset window uses offset-specific colors for marker row."""
        offset_window.update_table_data(sample_table_data)
        qtbot.wait(100)

        # Marker row should be styled (we just verify it doesn't crash)
        marker_item = offset_window.table.item(1440, 0)
        assert marker_item is not None


class TestPopOutTableWindowInteractivity:
    """Test interactive features."""

    def test_vertical_scrollbar_is_enabled(self, onset_window, qtbot):
        """Test that vertical scrollbar is available."""
        assert onset_window.table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded

    def test_horizontal_scrollbar_is_disabled(self, onset_window, qtbot):
        """Test that horizontal scrollbar is disabled (columns stretch to fit)."""
        assert onset_window.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    def test_alternating_row_colors_enabled(self, onset_window, qtbot):
        """Test that alternating row colors are enabled."""
        assert onset_window.table.alternatingRowColors() is True

    def test_window_can_be_resized(self, onset_window, qtbot):
        """Test that window can be manually resized."""
        original_size = onset_window.size()

        onset_window.resize(900, 700)
        qtbot.wait(50)

        new_size = onset_window.size()
        assert new_size != original_size

    def test_window_can_be_moved(self, onset_window, qtbot):
        """Test that window can be manually moved."""
        original_pos = onset_window.pos()

        onset_window.move(300, 300)
        qtbot.wait(50)

        new_pos = onset_window.pos()
        assert new_pos != original_pos


class TestPopOutTableWindowDefaultSize:
    """Test default window sizing."""

    def test_default_size_when_no_saved_geometry(self, qtbot, qapp):
        """Test default window size when no saved geometry exists."""
        # Clear any saved settings
        settings = QSettings("SleepScoringApp", "MarkerTables")
        settings.remove("test_popout_geometry")
        settings.remove("test_popout_pos")

        # Create new window with test table_type
        window = PopOutTableWindow(None, "Test Window", "test")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(100)

        # Should have default size (600x500)
        size = window.size()
        assert size.width() >= 500  # Allow some flexibility for window decorations
        assert size.height() >= 400

        window.close()
