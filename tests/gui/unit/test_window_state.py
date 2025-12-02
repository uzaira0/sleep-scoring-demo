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
        assert state_manager.markers_saved is True
        assert state_manager.unsaved_changes_exist is False
        assert isinstance(state_manager._marker_status_cache, dict)
        assert state_manager._metrics_cache is None
        assert isinstance(state_manager._marker_index_cache, dict)

    def test_invalidate_marker_status_cache_specific_file(self, state_manager):
        """Test cache invalidation for specific file."""
        # Add cache entry
        state_manager._marker_status_cache["test_file.csv"] = {"status": "complete"}
        state_manager._marker_status_cache["other_file.csv"] = {"status": "incomplete"}

        # Invalidate specific file
        state_manager.invalidate_marker_status_cache("test_file.csv")

        assert "test_file.csv" not in state_manager._marker_status_cache
        assert "other_file.csv" in state_manager._marker_status_cache

    def test_invalidate_marker_status_cache_all_files(self, state_manager):
        """Test cache invalidation for all files."""
        # Add cache entries
        state_manager._marker_status_cache["file1.csv"] = {"status": "complete"}
        state_manager._marker_status_cache["file2.csv"] = {"status": "incomplete"}

        # Invalidate all
        state_manager.invalidate_marker_status_cache(None)

        assert len(state_manager._marker_status_cache) == 0

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
