#!/usr/bin/env python3
"""
Unit tests for MarkerTableManager.
Tests table updates, pop-out windows, and marker data handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod
from sleep_scoring_app.ui.marker_table import MarkerTableManager


@pytest.mark.unit
@pytest.mark.gui
class TestMarkerTableManager:
    """Test MarkerTableManager functionality."""

    @pytest.fixture
    def table_manager(self, qt_app, mock_main_window):
        """Create MarkerTableManager instance."""
        # Set up required attributes for table manager
        mock_main_window.onset_table = Mock()
        mock_main_window.offset_table = Mock()
        mock_main_window.plot_widget = Mock()
        mock_main_window.plot_widget.custom_table_colors = None  # Must be None or dict, not Mock
        mock_main_window.analysis_tab = None
        # These need to be real dicts/lists, not Mocks
        mock_main_window.custom_table_colors = None
        mock_main_window._marker_index_cache = {}
        mock_main_window._onset_table_data = []
        mock_main_window._offset_table_data = []

        return MarkerTableManager(mock_main_window)

    def test_initialization(self, table_manager):
        """Test table manager initializes correctly."""
        assert table_manager.parent is not None

    def test_update_marker_tables_stores_data(self, table_manager, sample_marker_table_data, monkeypatch):
        """Test updating marker tables stores data for click handlers."""
        onset_data = sample_marker_table_data[:11]
        offset_data = sample_marker_table_data[10:]

        # Initialize storage as empty lists (not Mock)
        table_manager.parent._onset_table_data = []
        table_manager.parent._offset_table_data = []

        # Mock the update_marker_table function to avoid needing real table widgets
        from sleep_scoring_app.ui import marker_table as marker_table_module

        monkeypatch.setattr(marker_table_module, "update_marker_table", lambda *args, **kwargs: None)

        table_manager.update_marker_tables(onset_data, offset_data)

        assert table_manager.parent._onset_table_data == onset_data
        assert table_manager.parent._offset_table_data == offset_data

    def test_move_marker_from_table_click_onset(self, table_manager, sample_marker_table_data):
        """Test moving onset marker from table click."""
        # Setup
        table_manager.parent._onset_table_data = sample_marker_table_data
        table_manager.parent.plot_widget.move_marker_to_timestamp = Mock(return_value=True)
        table_manager.parent.plot_widget.get_selected_marker_period = Mock(return_value=None)
        table_manager.parent.auto_save_current_markers = Mock()

        # Click row 5 (not the marker row which is at index 10)
        table_manager.move_marker_from_table_click("onset", 5)

        # Verify marker movement was attempted
        table_manager.parent.plot_widget.move_marker_to_timestamp.assert_called_once()
        call_args = table_manager.parent.plot_widget.move_marker_to_timestamp.call_args
        assert call_args[0][0] == "onset"
        assert call_args[0][1] == sample_marker_table_data[5]["timestamp"]

    def test_move_marker_from_table_click_offset(self, table_manager, sample_marker_table_data):
        """Test moving offset marker from table click."""
        # Setup
        table_manager.parent._offset_table_data = sample_marker_table_data
        table_manager.parent.plot_widget.move_marker_to_timestamp = Mock(return_value=True)
        table_manager.parent.plot_widget.get_selected_marker_period = Mock(return_value=None)
        table_manager.parent.auto_save_current_markers = Mock()

        # Click row 15
        table_manager.move_marker_from_table_click("offset", 15)

        # Verify marker movement
        table_manager.parent.plot_widget.move_marker_to_timestamp.assert_called_once()
        call_args = table_manager.parent.plot_widget.move_marker_to_timestamp.call_args
        assert call_args[0][0] == "offset"

    def test_move_marker_from_table_click_marker_row_no_op(self, table_manager, sample_marker_table_data):
        """Test clicking on marker row itself is a no-op."""
        # Setup - row 10 is the marker row (is_marker=True)
        table_manager.parent._onset_table_data = sample_marker_table_data
        table_manager.parent.plot_widget.move_marker_to_timestamp = Mock()

        # Click the marker row
        table_manager.move_marker_from_table_click("onset", 10)

        # Should not attempt to move marker
        table_manager.parent.plot_widget.move_marker_to_timestamp.assert_not_called()

    def test_move_marker_from_table_click_invalid_row(self, table_manager, sample_marker_table_data):
        """Test clicking invalid row doesn't crash."""
        table_manager.parent._onset_table_data = sample_marker_table_data
        table_manager.parent.plot_widget.move_marker_to_timestamp = Mock()

        # Click row beyond data length
        table_manager.move_marker_from_table_click("onset", 999)

        # Should not attempt to move marker
        table_manager.parent.plot_widget.move_marker_to_timestamp.assert_not_called()

    def test_get_marker_data_cached_with_full_48h_data(self, table_manager, sample_activity_data):
        """Test getting marker data uses full 48hr data."""
        # Setup full 48hr data on plot widget as real lists (not Mocks)
        table_manager.parent.plot_widget.main_48h_timestamps = list(sample_activity_data["timestamps"])
        table_manager.parent.plot_widget.main_48h_activity = list(sample_activity_data["activity"])
        table_manager.parent.plot_widget.main_48h_axis_y_data = list(sample_activity_data["axis_y"])
        table_manager.parent.plot_widget.main_48h_sadeh_results = [1] * 2880
        table_manager.parent.plot_widget.get_choi_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager.parent.plot_widget.get_nonwear_sensor_results_per_minute = Mock(return_value=[0] * 2880)

        # Mock other required methods
        table_manager.parent._find_index_in_timestamps = Mock(return_value=1440)  # Middle of data
        table_manager.parent._get_axis_y_data_for_sadeh = Mock(return_value=list(sample_activity_data["axis_y"]))
        table_manager._load_vector_magnitude_data = Mock(return_value=list(sample_activity_data["vector_magnitude"]))

        marker_timestamp = sample_activity_data["timestamps"][1440].timestamp()

        # Get marker data
        data = table_manager.get_marker_data_cached(marker_timestamp)

        # Should return 21 rows (10 before + marker + 10 after)
        assert len(data) == 21

        # Middle row should be marked
        assert data[10]["is_marker"] is True
        assert data[9]["is_marker"] is False

    def test_get_marker_data_cached_uses_cached_index(self, table_manager, sample_activity_data):
        """Test getting marker data uses cached index for performance."""
        # Setup
        table_manager.parent.plot_widget.main_48h_timestamps = sample_activity_data["timestamps"]
        table_manager.parent.plot_widget.main_48h_activity = sample_activity_data["activity"]
        table_manager.parent.plot_widget.main_48h_axis_y_data = sample_activity_data["axis_y"]
        table_manager.parent.plot_widget.main_48h_sadeh_results = [1] * 2880
        table_manager.parent.plot_widget.get_choi_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager.parent.plot_widget.get_nonwear_sensor_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager.parent._find_index_in_timestamps = Mock(return_value=1440)
        table_manager.parent._get_axis_y_data_for_sadeh = Mock(return_value=sample_activity_data["axis_y"])
        table_manager._load_vector_magnitude_data = Mock(return_value=sample_activity_data["vector_magnitude"])

        marker_timestamp = sample_activity_data["timestamps"][1440].timestamp()

        # Call with cached index
        data = table_manager.get_marker_data_cached(marker_timestamp, cached_idx=1440)

        # Should not call _find_index_in_timestamps when cached index provided
        table_manager.parent._find_index_in_timestamps.assert_not_called()
        assert len(data) == 21

    def test_get_full_48h_data_for_popout(self, table_manager, sample_activity_data):
        """Test getting full 48hr data for pop-out window."""
        # Setup
        table_manager.parent.plot_widget.main_48h_timestamps = sample_activity_data["timestamps"]
        table_manager.parent.plot_widget.main_48h_activity = sample_activity_data["activity"]
        table_manager.parent.plot_widget.main_48h_axis_y_data = sample_activity_data["axis_y"]
        table_manager.parent.plot_widget.main_48h_sadeh_results = [1] * 2880
        table_manager.parent.plot_widget.get_choi_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager.parent.plot_widget.get_nonwear_sensor_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager._load_vector_magnitude_data = Mock(return_value=sample_activity_data["vector_magnitude"])

        # Get full data
        data = table_manager.get_full_48h_data_for_popout()

        # Should return all 2880 rows
        assert len(data) == 2880

        # Verify structure
        assert "time" in data[0]
        assert "timestamp" in data[0]
        assert "axis_y" in data[0]
        assert "vm" in data[0]
        assert "sadeh" in data[0]
        assert "choi" in data[0]

    def test_get_full_48h_data_for_popout_with_marker_highlight(self, table_manager, sample_activity_data):
        """Test pop-out data highlights marker row."""
        # Setup
        table_manager.parent.plot_widget.main_48h_timestamps = sample_activity_data["timestamps"]
        table_manager.parent.plot_widget.main_48h_activity = sample_activity_data["activity"]
        table_manager.parent.plot_widget.main_48h_axis_y_data = sample_activity_data["axis_y"]
        table_manager.parent.plot_widget.main_48h_sadeh_results = [1] * 2880
        table_manager.parent.plot_widget.get_choi_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager.parent.plot_widget.get_nonwear_sensor_results_per_minute = Mock(return_value=[0] * 2880)
        table_manager._load_vector_magnitude_data = Mock(return_value=sample_activity_data["vector_magnitude"])

        marker_timestamp = sample_activity_data["timestamps"][1440].timestamp()

        # Get data with marker
        data = table_manager.get_full_48h_data_for_popout(marker_timestamp=marker_timestamp)

        # Find highlighted row
        highlighted_rows = [i for i, row in enumerate(data) if row["is_marker"]]

        # Should have exactly one highlighted row
        assert len(highlighted_rows) == 1
