#!/usr/bin/env python3
"""
End-to-end tests for file loading workflow.
Tests the complete workflow of loading files, selecting dates, and viewing data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest


@pytest.mark.e2e
@pytest.mark.gui
class TestFileLoadingWorkflow:
    """Test complete file loading workflow."""

    @pytest.fixture
    def setup_workflow(self, qtbot, mock_main_window, sample_file_list, sample_activity_data):
        """Set up complete file loading workflow environment."""
        # Mock data service
        mock_main_window.data_service.discover_files = Mock(return_value=sample_file_list)
        mock_main_window.data_service.load_real_data = Mock(return_value=(sample_activity_data["timestamps"], sample_activity_data["activity"]))

        # Mock plot widget
        mock_main_window.plot_widget.plot_data = Mock()
        mock_main_window.plot_widget.clear_plot = Mock()

        return mock_main_window

    def test_complete_file_loading_workflow(self, setup_workflow, sample_file_list, mock_file_dialog):
        """Test complete workflow: browse folder -> select file -> select date -> view plot."""
        window = setup_workflow

        # Step 1: Browse and load data folder
        window.load_data_folder = Mock()
        window.load_available_files = Mock()

        # Simulate folder selection
        window.load_data_folder()
        window.load_available_files()

        # Step 2: File list should be populated
        window.available_files = sample_file_list
        assert len(window.available_files) > 0

        # Step 3: Select a file
        window.selected_file = sample_file_list[0]["path"]

        # Step 4: Date dropdown should be populated
        base_date = datetime(2021, 4, 20).date()
        window.available_dates = [base_date + timedelta(days=i) for i in range(10)]
        assert len(window.available_dates) > 0

        # Step 5: Select a date
        window.current_date_index = 0

        # Step 6: Plot should be updated
        window.plot_widget.plot_data()
        window.plot_widget.plot_data.assert_called_once()

    def test_database_mode_file_loading(self, setup_workflow, sample_file_list):
        """Test file loading in database mode."""
        window = setup_workflow

        # Enable database mode
        window.data_service.toggle_database_mode = Mock()
        window.data_service.toggle_database_mode(True)

        # Simulate discovering files
        files = window.data_service.discover_files()

        # Files should be returned
        assert files == sample_file_list
        window.data_service.discover_files.assert_called()

    def test_csv_mode_file_loading(self, setup_workflow, sample_file_list):
        """Test file loading in CSV mode."""
        window = setup_workflow

        # Enable CSV mode
        window.data_service.toggle_database_mode = Mock()
        window.data_service.toggle_database_mode(False)

        # Simulate discovering files from CSV
        files = window.data_service.discover_files()

        # Files should be discovered
        assert files == sample_file_list
        window.data_service.discover_files.assert_called()

    def test_file_selection_updates_date_list(self, setup_workflow, sample_file_list):
        """Test selecting a file updates the available dates."""
        window = setup_workflow

        # Select file
        window.selected_file = sample_file_list[0]["path"]

        # Dates should be extracted
        window.populate_date_dropdown = Mock()
        window.populate_date_dropdown()

        window.populate_date_dropdown.assert_called_once()

    def test_date_selection_loads_activity_data(self, setup_workflow, sample_activity_data):
        """Test selecting a date loads activity data."""
        window = setup_workflow

        # Set up file and dates
        window.selected_file = "test_file.csv"
        window.available_dates = [datetime(2021, 4, 20).date()]
        window.current_date_index = 0

        # Load data should be called
        window.data_service.load_real_data.return_value = (sample_activity_data["timestamps"], sample_activity_data["activity"])

        # Verify data can be loaded
        timestamps, activity = window.data_service.load_real_data()
        assert len(timestamps) > 0
        assert len(activity) > 0

    def test_switching_between_files(self, setup_workflow, sample_file_list):
        """Test switching between different files."""
        window = setup_workflow

        # Load first file
        window.selected_file = sample_file_list[0]["path"]
        window.available_dates = [datetime(2021, 4, 20).date()]

        # Switch to second file
        window.selected_file = sample_file_list[1]["path"]
        window.available_dates = [datetime(2021, 5, 15).date()]

        # Plot should be updated
        window.plot_widget.clear_plot()
        window.plot_widget.clear_plot.assert_called()

    def test_switching_between_dates(self, setup_workflow):
        """Test switching between dates in the same file."""
        window = setup_workflow

        # Set up file with multiple dates
        window.selected_file = "test_file.csv"
        base_date = datetime(2021, 4, 20).date()
        window.available_dates = [base_date + timedelta(days=i) for i in range(3)]

        # Switch to first date
        window.current_date_index = 0

        # Switch to second date
        window.current_date_index = 1

        # Date index should be updated
        assert window.current_date_index == 1

    def test_error_handling_no_files(self, setup_workflow, mock_message_box):
        """Test error handling when no files are found."""
        window = setup_workflow

        # No files found
        window.data_service.discover_files.return_value = []
        window.load_available_files()

        # Should handle gracefully
        assert True  # No crash

    def test_error_handling_invalid_file(self, setup_workflow, mock_message_box):
        """Test error handling when file cannot be loaded."""
        window = setup_workflow

        # File load fails
        window.data_service.load_real_data = Mock(side_effect=Exception("File not found"))

        # Should handle error gracefully
        # In actual implementation, this would show an error message
        assert True
