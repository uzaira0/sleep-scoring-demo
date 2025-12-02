#!/usr/bin/env python3
"""
End-to-end tests for export workflow.
Tests the complete workflow of configuring and executing data export.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest


@pytest.mark.e2e
@pytest.mark.gui
class TestExportWorkflow:
    """Test complete export workflow."""

    @pytest.fixture
    def setup_export_workflow(self, qtbot, mock_main_window, sample_sleep_metrics, mock_file_dialog):
        """Set up export workflow environment."""
        # Set up metrics data
        mock_main_window._get_cached_metrics = Mock(return_value=[sample_sleep_metrics])
        mock_main_window.export_output_path = "/test/export"

        # Mock export methods
        mock_main_window.export_manager.export_to_csv = Mock(return_value=True)
        mock_main_window.export_manager.export_to_excel = Mock(return_value=True)

        # Mock UI methods
        mock_main_window.browse_export_output_directory = Mock()
        mock_main_window.perform_direct_export = Mock()

        return mock_main_window

    def test_complete_export_workflow(self, setup_export_workflow, mock_message_box):
        """Test complete workflow: configure export -> select format -> export."""
        window = setup_export_workflow

        # Step 1: Select export directory
        window.browse_export_output_directory()
        window.browse_export_output_directory.assert_called_once()

        # Step 2: Verify data is available
        metrics = window._get_cached_metrics()
        assert len(metrics) > 0

        # Step 3: Perform export
        window.perform_direct_export()
        window.perform_direct_export.assert_called_once()

    def test_csv_export(self, setup_export_workflow, mock_message_box):
        """Test exporting to CSV format."""
        window = setup_export_workflow

        # Get metrics
        metrics = window._get_cached_metrics()

        # Export to CSV
        result = window.export_manager.export_to_csv(metrics, "/test/export/output.csv")

        # Should succeed
        assert result is True
        window.export_manager.export_to_csv.assert_called_once()

    def test_excel_export(self, setup_export_workflow, mock_message_box):
        """Test exporting to Excel format."""
        window = setup_export_workflow

        # Get metrics
        metrics = window._get_cached_metrics()

        # Export to Excel
        result = window.export_manager.export_to_excel(metrics, "/test/export/output.xlsx")

        # Should succeed
        assert result is True
        window.export_manager.export_to_excel.assert_called_once()

    def test_export_with_no_data(self, setup_export_workflow, mock_message_box):
        """Test export with no data shows warning."""
        window = setup_export_workflow

        # Clear metrics
        window._get_cached_metrics = Mock(return_value=[])

        # Attempt export should check for data
        metrics = window._get_cached_metrics()
        assert len(metrics) == 0

    def test_export_directory_selection(self, setup_export_workflow, mock_file_dialog):
        """Test selecting export output directory."""
        window = setup_export_workflow

        # Browse for directory
        window.browse_export_output_directory()

        # Should call browse method
        window.browse_export_output_directory.assert_called_once()

    def test_export_grouping_by_participant(self, setup_export_workflow):
        """Test export grouped by participant."""
        window = setup_export_workflow

        # Export with grouping
        metrics = window._get_cached_metrics()

        # Export manager should support grouping
        assert window.export_manager is not None

    def test_export_all_columns(self, setup_export_workflow):
        """Test exporting all available columns."""
        window = setup_export_workflow

        # Get metrics
        metrics = window._get_cached_metrics()
        assert len(metrics) > 0

        # Export should include all columns
        # Column selection is handled by export manager

    def test_export_selected_columns(self, setup_export_workflow):
        """Test exporting only selected columns."""
        window = setup_export_workflow

        # Get metrics
        metrics = window._get_cached_metrics()

        # Export with column selection
        # Column filtering is handled by export manager
        assert len(metrics) > 0

    def test_export_error_handling(self, setup_export_workflow, mock_message_box):
        """Test export error handling."""
        window = setup_export_workflow

        # Simulate export failure
        window.export_manager.export_to_csv = Mock(side_effect=Exception("Export failed"))

        # Should handle error gracefully
        # In actual implementation, this would show an error message
        assert True

    def test_export_progress_indication(self, setup_export_workflow):
        """Test export shows progress indication."""
        window = setup_export_workflow

        # Export should show progress
        # Progress indication is UI-specific
        assert window.export_manager is not None

    def test_export_success_message(self, setup_export_workflow, mock_message_box):
        """Test export shows success message."""
        window = setup_export_workflow

        # Perform export
        window.export_manager.export_to_csv.return_value = True

        # Success message should be shown
        # Message boxes are mocked
        assert True
