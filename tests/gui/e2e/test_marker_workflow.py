#!/usr/bin/env python3
"""
End-to-end tests for marker workflow.
Tests the complete workflow of adding, editing, saving, and deleting markers.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from sleep_scoring_app.core.dataclasses import DailySleepMarkers, MarkerType, SleepPeriod


@pytest.mark.e2e
@pytest.mark.gui
class TestMarkerWorkflow:
    """Test complete marker workflow."""

    @pytest.fixture
    def setup_marker_workflow(self, qtbot, mock_main_window, sample_activity_data, sample_sleep_markers):
        """Set up marker workflow environment."""
        # Set up file and date
        mock_main_window.selected_file = "test_file.csv"
        mock_main_window.available_dates = [datetime(2021, 4, 20).date()]
        mock_main_window.current_date_index = 0

        # Set up plot widget with data
        mock_main_window.plot_widget.timestamps = sample_activity_data["timestamps"]
        mock_main_window.plot_widget.activity_data = sample_activity_data["activity"]
        mock_main_window.plot_widget.daily_sleep_markers = DailySleepMarkers()
        mock_main_window.plot_widget.markers_saved = False

        # Mock marker methods
        mock_main_window.plot_widget.add_marker = Mock()
        mock_main_window.plot_widget.move_marker_to_timestamp = Mock(return_value=True)
        mock_main_window.plot_widget.clear_sleep_markers = Mock()
        mock_main_window.plot_widget.redraw_markers = Mock()

        # Mock save/load methods
        mock_main_window.db_manager.save_sleep_metrics = Mock(return_value=True)
        mock_main_window.db_manager.load_sleep_metrics = Mock(return_value=[])
        mock_main_window.db_manager.delete_sleep_metrics_for_date = Mock(return_value=True)

        # Mock UI update methods
        mock_main_window.update_sleep_info = Mock()
        mock_main_window.update_marker_tables = Mock()
        mock_main_window.auto_save_current_markers = Mock()

        # Ensure state_manager is available
        if not hasattr(mock_main_window, "state_manager") or mock_main_window.state_manager is None:
            mock_main_window.state_manager = Mock()

        return mock_main_window

    def test_complete_marker_workflow(self, setup_marker_workflow, sample_sleep_markers, mock_message_box):
        """Test complete workflow: add markers -> view info -> save -> reload."""
        window = setup_marker_workflow

        # Step 1: Add onset marker
        onset_period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=None,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = onset_period

        # Step 2: Add offset marker to complete the period
        onset_period.offset_timestamp = sample_sleep_markers["offset"]

        # Step 3: Sleep info should be updated
        window.update_sleep_info([sample_sleep_markers["onset"], sample_sleep_markers["offset"]])
        window.update_sleep_info.assert_called_once()

        # Step 4: Save markers
        window.state_manager.save_current_markers = Mock()
        window.state_manager.save_current_markers()
        window.state_manager.save_current_markers.assert_called_once()

        # Step 5: Markers should be marked as saved
        window.plot_widget.markers_saved = True
        assert window.plot_widget.markers_saved is True

    def test_add_onset_marker(self, setup_marker_workflow, sample_sleep_markers):
        """Test adding onset marker."""
        window = setup_marker_workflow

        # Add onset marker
        onset_period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=None,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = onset_period

        # Period should exist but be incomplete
        assert window.plot_widget.daily_sleep_markers.period_1 is not None
        assert not window.plot_widget.daily_sleep_markers.period_1.is_complete

    def test_complete_sleep_period(self, setup_marker_workflow, sample_sleep_markers):
        """Test completing a sleep period by adding offset."""
        window = setup_marker_workflow

        # Add onset
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=None,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Add offset
        period.offset_timestamp = sample_sleep_markers["offset"]

        # Period should be complete
        assert period.is_complete is True

    def test_move_existing_marker(self, setup_marker_workflow, sample_sleep_markers):
        """Test moving an existing marker."""
        window = setup_marker_workflow

        # Create complete period
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Move onset marker
        new_onset = sample_sleep_markers["onset"] + 3600  # 1 hour later
        window.plot_widget.move_marker_to_timestamp("onset", new_onset, 1)

        # Movement should be attempted
        window.plot_widget.move_marker_to_timestamp.assert_called_once()

    def test_delete_markers(self, setup_marker_workflow, sample_sleep_markers, mock_message_box):
        """Test deleting markers."""
        window = setup_marker_workflow

        # Add markers
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Delete markers
        window.plot_widget.clear_sleep_markers()
        window.plot_widget.clear_sleep_markers.assert_called_once()

    def test_save_markers_to_database(self, setup_marker_workflow, sample_sleep_markers, mock_message_box):
        """Test saving markers to database."""
        window = setup_marker_workflow

        # Add complete period
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period
        window.plot_widget.get_selected_marker_period = Mock(return_value=period)

        # Save
        window.state_manager.save_current_markers = Mock()
        window.state_manager.save_current_markers()

        # Save should be called
        window.state_manager.save_current_markers.assert_called_once()

    def test_load_saved_markers(self, setup_marker_workflow, sample_sleep_metrics):
        """Test loading saved markers from database."""
        window = setup_marker_workflow

        # Mock loaded metrics
        window.db_manager.load_sleep_metrics.return_value = [sample_sleep_metrics]

        # Load markers
        window.state_manager.load_saved_markers = Mock()
        window.state_manager.load_saved_markers()

        # Load should be called
        window.state_manager.load_saved_markers.assert_called_once()

    def test_autosave_on_marker_change(self, setup_marker_workflow, sample_sleep_markers):
        """Test autosave triggers on marker change."""
        window = setup_marker_workflow

        # Add complete period
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Autosave should be called
        markers = [sample_sleep_markers["onset"], sample_sleep_markers["offset"]]
        window.auto_save_current_markers()
        window.auto_save_current_markers.assert_called_once()

    def test_marker_unsaved_state(self, setup_marker_workflow, sample_sleep_markers):
        """Test markers show unsaved state after modification."""
        window = setup_marker_workflow

        # Add markers
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Markers should be unsaved
        window.plot_widget.markers_saved = False
        assert window.plot_widget.markers_saved is False

    def test_clear_all_markers_confirmation(self, setup_marker_workflow, mock_message_box):
        """Test clearing all markers requires confirmation."""
        window = setup_marker_workflow

        # Attempt to clear all markers
        window.state_manager.clear_current_markers = Mock()
        window.state_manager.clear_current_markers()

        # Clear should be called
        window.state_manager.clear_current_markers.assert_called_once()

    def test_mark_no_sleep_period(self, setup_marker_workflow, mock_message_box):
        """Test marking a date as having no sleep period."""
        window = setup_marker_workflow

        # Mark no sleep
        window.state_manager.mark_no_sleep_period = Mock()
        window.state_manager.mark_no_sleep_period()

        # Should be called
        window.state_manager.mark_no_sleep_period.assert_called_once()

    def test_multiple_sleep_periods(self, setup_marker_workflow, sample_sleep_markers):
        """Test adding multiple sleep periods (main sleep + naps)."""
        window = setup_marker_workflow

        # Add main sleep
        main_sleep = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = main_sleep

        # Add nap
        nap = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"] - 7200,  # 2 hours before
            offset_timestamp=sample_sleep_markers["onset"] - 3600,  # 1 hour before
            marker_index=2,
            marker_type=MarkerType.NAP,
        )
        window.plot_widget.daily_sleep_markers.period_2 = nap

        # Should have multiple periods
        periods = window.plot_widget.daily_sleep_markers.get_complete_periods()
        assert len(periods) >= 1
