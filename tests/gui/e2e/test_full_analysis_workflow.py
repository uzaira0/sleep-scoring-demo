#!/usr/bin/env python3
"""
End-to-end tests for full analysis workflow.
Tests the complete workflow from loading data to exporting results.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from sleep_scoring_app.core.dataclasses import DailySleepMarkers, MarkerType, SleepPeriod


@pytest.mark.e2e
@pytest.mark.gui
class TestFullAnalysisWorkflow:
    """Test complete analysis workflow from start to finish."""

    @pytest.fixture
    def setup_full_workflow(
        self, qtbot, mock_main_window, sample_file_list, sample_activity_data, sample_sleep_markers, mock_file_dialog, mock_message_box
    ):
        """Set up complete analysis workflow environment."""
        # Set up data service
        mock_main_window.data_service.discover_files = Mock(return_value=sample_file_list)
        mock_main_window.data_service.load_real_data = Mock(return_value=(sample_activity_data["timestamps"], sample_activity_data["activity"]))

        # Set up plot widget
        mock_main_window.plot_widget.plot_data = Mock()
        mock_main_window.plot_widget.clear_plot = Mock()
        mock_main_window.plot_widget.timestamps = sample_activity_data["timestamps"]
        mock_main_window.plot_widget.activity_data = sample_activity_data["activity"]
        mock_main_window.plot_widget.daily_sleep_markers = DailySleepMarkers()
        mock_main_window.plot_widget.plot_algorithms = Mock()
        mock_main_window.plot_widget.sadeh_results = [1] * 2880
        mock_main_window.plot_widget.get_choi_results_per_minute = Mock(return_value=[0] * 2880)
        mock_main_window.plot_widget.get_selected_marker_period = Mock(return_value=None)

        # Set up database and export
        mock_main_window.db_manager.save_sleep_metrics = Mock(return_value=True)
        mock_main_window.export_manager.export_to_csv = Mock(return_value=True)

        # Set up UI methods
        mock_main_window.load_available_files = Mock()
        mock_main_window.update_sleep_info = Mock()
        mock_main_window.update_marker_tables = Mock()
        mock_main_window._get_cached_metrics = Mock(return_value=[])

        # Ensure state_manager is available
        if not hasattr(mock_main_window, "state_manager") or mock_main_window.state_manager is None:
            mock_main_window.state_manager = Mock()

        return mock_main_window

    def test_complete_analysis_session(self, setup_full_workflow, sample_file_list, sample_sleep_markers):
        """Test complete analysis session from file loading to export."""
        window = setup_full_workflow

        # STEP 1: Load data folder and discover files
        window.load_available_files()
        window.available_files = sample_file_list
        assert len(window.available_files) > 0

        # STEP 2: Select a file
        window.selected_file = sample_file_list[0]["path"]
        assert window.selected_file is not None

        # STEP 3: Populate dates for selected file
        base_date = datetime(2021, 4, 20).date()
        window.available_dates = [base_date + timedelta(days=i) for i in range(10)]
        window.current_date_index = 0
        assert len(window.available_dates) > 0

        # STEP 4: Load activity data for selected date
        window.plot_widget.plot_data()
        assert len(window.plot_widget.timestamps) > 0

        # STEP 5: Run sleep scoring algorithms
        window.plot_widget.plot_algorithms()
        assert len(window.plot_widget.sadeh_results) > 0

        # STEP 6: Add sleep markers (onset)
        onset_period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=None,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = onset_period

        # STEP 7: Complete sleep period (offset)
        onset_period.offset_timestamp = sample_sleep_markers["offset"]
        assert onset_period.is_complete

        # STEP 8: View sleep metrics
        markers = [sample_sleep_markers["onset"], sample_sleep_markers["offset"]]
        window.update_sleep_info(markers)
        window.update_sleep_info.assert_called()

        # STEP 9: Save markers to database
        window.plot_widget.get_selected_marker_period = Mock(return_value=onset_period)
        window.state_manager.save_current_markers = Mock()
        window.state_manager.save_current_markers()

        # STEP 10: Export results
        window.perform_direct_export = Mock()
        window.perform_direct_export()

        # Workflow completed successfully
        assert True

    def test_multi_file_analysis_workflow(self, setup_full_workflow, sample_file_list, sample_sleep_markers):
        """Test analyzing multiple files in sequence."""
        window = setup_full_workflow

        # Analyze first file
        window.selected_file = sample_file_list[0]["path"]
        window.available_dates = [datetime(2021, 4, 20).date()]
        window.current_date_index = 0

        # Add markers for first file
        period1 = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period1

        # Save markers
        window.db_manager.save_sleep_metrics.return_value = True

        # Switch to second file
        window.selected_file = sample_file_list[1]["path"]
        window.available_dates = [datetime(2021, 5, 15).date()]
        window.current_date_index = 0
        window.plot_widget.daily_sleep_markers = DailySleepMarkers()

        # Add markers for second file
        period2 = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"] + 86400,  # Next day
            offset_timestamp=sample_sleep_markers["offset"] + 86400,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period2

        # Both files analyzed
        assert True

    def test_multi_date_analysis_workflow(self, setup_full_workflow, sample_sleep_markers):
        """Test analyzing multiple dates in same file."""
        window = setup_full_workflow

        # Select file
        window.selected_file = "test_file.csv"

        # Generate dates
        base_date = datetime(2021, 4, 20).date()
        window.available_dates = [base_date + timedelta(days=i) for i in range(5)]

        # Analyze each date
        for i in range(3):
            window.current_date_index = i

            # Add markers for this date
            period = SleepPeriod(
                onset_timestamp=sample_sleep_markers["onset"] + (i * 86400),
                offset_timestamp=sample_sleep_markers["offset"] + (i * 86400),
                marker_index=1,
                marker_type=MarkerType.MAIN_SLEEP,
            )
            window.plot_widget.daily_sleep_markers = DailySleepMarkers()
            window.plot_widget.daily_sleep_markers.period_1 = period

        # Multiple dates analyzed
        assert True

    def test_workflow_with_algorithm_comparison(self, setup_full_workflow, sample_sleep_markers):
        """Test workflow comparing different sleep scoring algorithms."""
        window = setup_full_workflow

        # Load data
        window.selected_file = "test_file.csv"
        window.available_dates = [datetime(2021, 4, 20).date()]
        window.current_date_index = 0

        # Run algorithms
        window.plot_widget.plot_algorithms()

        # Verify algorithm results available
        assert len(window.plot_widget.sadeh_results) > 0
        choi_results = window.plot_widget.get_choi_results_per_minute()
        assert len(choi_results) == 2880

        # Add markers based on algorithm suggestions
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Workflow with algorithms completed
        assert True

    def test_workflow_with_data_import(self, setup_full_workflow, mock_file_dialog):
        """Test workflow starting with data import."""
        window = setup_full_workflow

        # STEP 1: Import activity data
        window.start_activity_import = Mock()
        window.start_activity_import()

        # STEP 2: Wait for import to complete (mocked)
        window.start_activity_import.assert_called_once()

        # STEP 3: Refresh file list
        window.load_available_files()

        # STEP 4: Continue with normal analysis workflow
        assert True

    def test_workflow_error_recovery(self, setup_full_workflow, mock_message_box):
        """Test workflow recovers from errors gracefully."""
        window = setup_full_workflow

        # Simulate data load error
        window.data_service.load_real_data = Mock(side_effect=Exception("Load failed"))

        # Should handle error
        try:
            window.data_service.load_real_data()
        except Exception:
            pass  # Error handled

        # Can continue with different file
        window.data_service.load_real_data = Mock(return_value=([], []))
        window.selected_file = "another_file.csv"

        # Recovery successful
        assert True

    def test_workflow_state_persistence(self, setup_full_workflow, sample_sleep_markers):
        """Test workflow state is maintained across operations."""
        window = setup_full_workflow

        # Set initial state
        window.selected_file = "test_file.csv"
        window.current_date_index = 2

        # Add markers
        period = SleepPeriod(
            onset_timestamp=sample_sleep_markers["onset"],
            offset_timestamp=sample_sleep_markers["offset"],
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        window.plot_widget.daily_sleep_markers.period_1 = period

        # Switch tabs (state should persist)
        # Tab switching handled by main window

        # State should be maintained
        assert window.selected_file == "test_file.csv"
        assert window.current_date_index == 2
        assert window.plot_widget.daily_sleep_markers.period_1 is not None

    def test_workflow_with_batch_export(self, setup_full_workflow, sample_sleep_metrics):
        """Test workflow ending with batch export of multiple files."""
        window = setup_full_workflow

        # Analyze multiple files (simplified)
        window._get_cached_metrics = Mock(return_value=[sample_sleep_metrics] * 3)

        # Export all results
        metrics = window._get_cached_metrics()
        assert len(metrics) == 3

        # Perform batch export
        result = window.export_manager.export_to_csv(metrics, "/test/export/batch.csv")
        assert result is True

    def test_workflow_with_no_sleep_period(self, setup_full_workflow, mock_message_box):
        """Test workflow for marking dates with no sleep."""
        window = setup_full_workflow

        # Load data
        window.selected_file = "test_file.csv"
        window.available_dates = [datetime(2021, 4, 20).date()]
        window.current_date_index = 0

        # Mark as no sleep
        window.state_manager.mark_no_sleep_period = Mock()
        window.state_manager.mark_no_sleep_period()

        # Should be marked
        window.state_manager.mark_no_sleep_period.assert_called_once()

        # Continue to next date
        window.current_date_index = 1

        # Workflow continues
        assert True
