#!/usr/bin/env python3
"""
Unit tests for WindowStateManager.
Tests state tracking, caching, and marker management.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from sleep_scoring_app.core.constants import AlgorithmType, MarkerType
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod
from sleep_scoring_app.ui.window_state import WindowStateManager


@pytest.mark.unit
@pytest.mark.gui
class TestWindowStateManager:
    """Test WindowStateManager functionality."""

    @pytest.fixture
    def state_manager(self, qt_app, mock_main_window):
        """Create WindowStateManager instance."""
        return WindowStateManager(mock_main_window)

    def test_initialization(self, state_manager):
        """Test state manager initializes with correct defaults."""
        # NOTE: markers_saved is now managed by MarkerSaveStateManager, not WindowStateManager
        # Access via parent._sleep_save_state.is_dirty (inverted - is_dirty means NOT saved)
        assert state_manager.unsaved_changes_exist is False
        assert state_manager._metrics_cache is None
        # Note: _marker_status_cache and _marker_index_cache were moved to data_service.cache_service

    def test_invalidate_marker_status_cache_specific_file(self, state_manager):
        """Test cache invalidation delegates to data service for specific file."""
        # Set up mock data_service
        state_manager.parent.data_service = Mock()
        state_manager.parent.data_service.invalidate_marker_status_cache = Mock()
        state_manager.parent.data_service.update_file_table_indicators_only = Mock()

        # Invalidate specific file
        state_manager.invalidate_marker_status_cache("test_file.csv")

        # Verify delegation
        state_manager.parent.data_service.invalidate_marker_status_cache.assert_called_once_with("test_file.csv")
        state_manager.parent.data_service.update_file_table_indicators_only.assert_called_once()

    def test_invalidate_marker_status_cache_all_files(self, state_manager):
        """Test cache invalidation delegates to data service for all files."""
        # Set up mock data_service
        state_manager.parent.data_service = Mock()
        state_manager.parent.data_service.invalidate_marker_status_cache = Mock()
        state_manager.parent.data_service.update_file_table_indicators_only = Mock()

        # Invalidate all
        state_manager.invalidate_marker_status_cache(None)

        # Verify delegation
        state_manager.parent.data_service.invalidate_marker_status_cache.assert_called_once_with(None)
        state_manager.parent.data_service.update_file_table_indicators_only.assert_called_once()

    def test_invalidate_metrics_cache(self, state_manager, sample_sleep_metrics):
        """Test metrics cache invalidation."""
        # Set cache
        state_manager._metrics_cache = [sample_sleep_metrics]

        # Invalidate
        state_manager.invalidate_metrics_cache()

        assert state_manager._metrics_cache is None

    def test_get_cached_metrics_loads_from_database(self, state_manager, sample_sleep_metrics):
        """Test cached metrics loads from database on first call."""
        state_manager.parent.db_manager.load_sleep_metrics.return_value = [sample_sleep_metrics]

        # First call should load from database
        metrics = state_manager.get_cached_metrics()

        assert len(metrics) == 1
        assert metrics[0] == sample_sleep_metrics
        state_manager.parent.db_manager.load_sleep_metrics.assert_called_once()

    def test_get_cached_metrics_uses_cache(self, state_manager, sample_sleep_metrics):
        """Test cached metrics uses cache on subsequent calls."""
        state_manager.parent.db_manager.load_sleep_metrics.return_value = [sample_sleep_metrics]

        # First call
        metrics1 = state_manager.get_cached_metrics()

        # Second call should use cache
        metrics2 = state_manager.get_cached_metrics()

        assert metrics1 == metrics2
        # Should only call database once
        assert state_manager.parent.db_manager.load_sleep_metrics.call_count == 1

    def test_create_sleep_period_from_timestamps_both_provided(self, state_manager, sample_sleep_markers):
        """Test creating sleep period with both timestamps."""
        state_manager.parent.plot_widget = Mock()
        state_manager.parent.plot_widget.daily_sleep_markers = DailySleepMarkers()

        period = state_manager.create_sleep_period_from_timestamps(sample_sleep_markers["onset"], sample_sleep_markers["offset"], is_main_sleep=True)

        assert period is not None
        assert period.onset_timestamp == sample_sleep_markers["onset"]
        assert period.offset_timestamp == sample_sleep_markers["offset"]
        assert period.marker_type == MarkerType.MAIN_SLEEP
        assert period.is_complete

    def test_create_sleep_period_from_timestamps_onset_only(self, state_manager, sample_sleep_markers):
        """Test creating sleep period with only onset timestamp."""
        state_manager.parent.plot_widget = Mock()
        state_manager.parent.plot_widget.daily_sleep_markers = DailySleepMarkers()

        period = state_manager.create_sleep_period_from_timestamps(sample_sleep_markers["onset"], None, is_main_sleep=False)

        assert period is not None
        assert period.onset_timestamp == sample_sleep_markers["onset"]
        assert period.offset_timestamp is None
        assert period.marker_type == MarkerType.NAP
        assert not period.is_complete

    def test_create_sleep_period_from_timestamps_no_timestamps(self, state_manager):
        """Test creating sleep period with no timestamps returns None."""
        state_manager.parent.plot_widget = Mock()
        state_manager.parent.plot_widget.daily_sleep_markers = DailySleepMarkers()

        period = state_manager.create_sleep_period_from_timestamps(None, None)

        assert period is None

    def test_create_sleep_period_fills_available_slots(self, state_manager, sample_sleep_markers):
        """Test sleep period creation fills slots in order."""
        state_manager.parent.plot_widget = Mock()
        daily_markers = DailySleepMarkers()
        state_manager.parent.plot_widget.daily_sleep_markers = daily_markers

        # Create first period - should go in slot 1
        period1 = state_manager.create_sleep_period_from_timestamps(sample_sleep_markers["onset"], sample_sleep_markers["offset"], is_main_sleep=True)

        assert period1.marker_index == 1
        assert daily_markers.period_1 == period1

        # Create second period - should go in slot 2
        period2 = state_manager.create_sleep_period_from_timestamps(
            sample_sleep_markers["onset"] + 3600, sample_sleep_markers["offset"] + 3600, is_main_sleep=False
        )

        assert period2.marker_index == 2
        assert daily_markers.period_2 == period2

    @patch("sleep_scoring_app.ui.window_state.QMessageBox")
    def test_clear_all_markers_no_records(self, mock_msgbox, state_manager):
        """Test clear all markers shows info dialog when no records exist."""
        # Set up mock db_manager to return empty stats
        state_manager.parent.db_manager = Mock()
        state_manager.parent.db_manager.get_database_stats.return_value = {"total_records": 0, "autosave_records": 0}

        # Call clear_all_markers
        state_manager.clear_all_markers()

        # Should show information dialog
        mock_msgbox.information.assert_called_once()

    @patch("sleep_scoring_app.ui.window_state.QMessageBox")
    def test_clear_all_markers_with_records_confirmed(self, mock_msgbox, state_manager):
        """Test clear all markers proceeds when user confirms."""
        # Set up mocks
        state_manager.parent.db_manager = Mock()
        state_manager.parent.db_manager.get_database_stats.return_value = {"total_records": 5, "autosave_records": 0}
        state_manager.parent.db_manager.clear_all_markers.return_value = {
            "total_cleared": 5,
            "sleep_metrics_cleared": 5,
            "autosave_metrics_cleared": 0,
        }
        state_manager.parent._invalidate_metrics_cache = Mock()
        state_manager.parent.data_service = Mock()
        state_manager.parent.update_data_source_status = Mock()
        state_manager.parent.load_available_files = Mock()
        state_manager.parent.selected_file = None
        state_manager.parent.available_dates = []

        # User confirms
        mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes

        # Call clear_all_markers
        state_manager.clear_all_markers()

        # Should show confirmation dialog and then clear
        mock_msgbox.question.assert_called_once()
        state_manager.parent.db_manager.clear_all_markers.assert_called_once()
        mock_msgbox.information.assert_called()  # Success message

    @patch("sleep_scoring_app.ui.window_state.QMessageBox")
    def test_clear_all_markers_cancelled(self, mock_msgbox, state_manager):
        """Test clear all markers is cancelled when user declines."""
        # Set up mocks
        state_manager.parent.db_manager = Mock()
        state_manager.parent.db_manager.get_database_stats.return_value = {"total_records": 5, "autosave_records": 0}

        # User cancels
        mock_msgbox.question.return_value = mock_msgbox.StandardButton.No

        # Call clear_all_markers
        state_manager.clear_all_markers()

        # Should show confirmation but NOT clear
        mock_msgbox.question.assert_called_once()
        state_manager.parent.db_manager.clear_all_markers.assert_not_called()
