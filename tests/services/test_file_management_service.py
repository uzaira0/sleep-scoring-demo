#!/usr/bin/env python3
"""
Tests for FileManagementService
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sleep_scoring_app.core.constants import DeleteStatus
from sleep_scoring_app.core.dataclasses import BatchDeleteResult, DeleteResult, ImportedFileInfo
from sleep_scoring_app.services.file_management_service import FileManagementServiceImpl


class TestFileManagementService:
    """Test suite for FileManagementService."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db_manager):
        """Create a FileManagementService instance."""
        return FileManagementServiceImpl(mock_db_manager)

    def test_get_imported_files_success(self, service, mock_db_manager):
        """Test getting imported files successfully."""
        # Setup mock data
        mock_files = [
            {
                "filename": "test1.csv",
                "participant_id": "P001",
                "date_start": "2025-01-01",
                "date_end": "2025-01-10",
                "total_records": 1000,
                "import_date": "2025-01-15",
            },
            {
                "filename": "test2.csv",
                "participant_id": "P002",
                "date_start": "2025-01-05",
                "date_end": "2025-01-15",
                "total_records": 2000,
                "import_date": "2025-01-16",
            },
        ]

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = []  # No metrics

        # Execute
        result = service.get_imported_files()

        # Verify
        assert len(result) == 2
        assert isinstance(result[0], ImportedFileInfo)
        assert result[0].filename == "test1.csv"
        assert result[0].participant_id == "P001"
        assert result[0].has_metrics is False

    def test_get_imported_files_with_metrics(self, service, mock_db_manager):
        """Test getting files that have associated metrics."""
        mock_files = [
            {
                "filename": "test1.csv",
                "participant_id": "P001",
                "date_start": "2025-01-01",
                "date_end": "2025-01-10",
                "total_records": 1000,
                "import_date": "2025-01-15",
            },
        ]

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = [MagicMock()]  # Has metrics

        result = service.get_imported_files()

        assert result[0].has_metrics is True

    def test_delete_file_success(self, service, mock_db_manager):
        """Test successful file deletion."""
        mock_files = [
            {
                "filename": "test1.csv",
                "participant_id": "P001",
                "total_records": 1000,
            },
        ]

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = []
        mock_db_manager.delete_imported_file.return_value = True

        result = service.delete_file("test1.csv")

        assert result.status == DeleteStatus.SUCCESS
        assert result.filename == "test1.csv"
        assert result.records_deleted == 1000
        mock_db_manager.delete_imported_file.assert_called_once_with("test1.csv")

    def test_delete_file_not_found(self, service, mock_db_manager):
        """Test deleting a file that doesn't exist."""
        mock_db_manager.get_available_files.return_value = []

        result = service.delete_file("nonexistent.csv")

        assert result.status == DeleteStatus.NOT_FOUND
        assert result.filename == "nonexistent.csv"
        assert "not found" in result.error_message.lower()

    def test_delete_file_with_metrics(self, service, mock_db_manager):
        """Test deleting a file that has metrics."""
        mock_files = [
            {
                "filename": "test1.csv",
                "participant_id": "P001",
                "total_records": 1000,
            },
        ]

        mock_metrics = [MagicMock(), MagicMock()]  # 2 metrics

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = mock_metrics
        mock_db_manager.delete_imported_file.return_value = True

        result = service.delete_file("test1.csv")

        assert result.status == DeleteStatus.SUCCESS
        assert result.metrics_deleted == 2

    def test_delete_file_database_failure(self, service, mock_db_manager):
        """Test deletion when database operation fails."""
        mock_files = [
            {
                "filename": "test1.csv",
                "participant_id": "P001",
                "total_records": 1000,
            },
        ]

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = []
        mock_db_manager.delete_imported_file.return_value = False

        result = service.delete_file("test1.csv")

        assert result.status == DeleteStatus.FAILED
        assert "deletion failed" in result.error_message.lower()

    def test_delete_files_batch(self, service, mock_db_manager):
        """Test batch deletion of multiple files."""
        mock_files = [
            {"filename": "test1.csv", "participant_id": "P001", "total_records": 1000},
            {"filename": "test2.csv", "participant_id": "P002", "total_records": 2000},
        ]

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = []
        mock_db_manager.delete_imported_file.return_value = True

        result = service.delete_files(["test1.csv", "test2.csv"])

        assert isinstance(result, BatchDeleteResult)
        assert result.total_requested == 2
        assert result.successful == 2
        assert result.failed == 0
        assert len(result.results) == 2

    def test_delete_files_partial_failure(self, service, mock_db_manager):
        """Test batch deletion with some failures."""
        mock_files = [
            {"filename": "test1.csv", "participant_id": "P001", "total_records": 1000},
        ]

        mock_db_manager.get_available_files.return_value = mock_files
        mock_db_manager.load_sleep_metrics.return_value = []
        mock_db_manager.delete_imported_file.return_value = True

        # test1.csv exists, test2.csv doesn't
        result = service.delete_files(["test1.csv", "test2.csv"])

        assert result.total_requested == 2
        assert result.successful == 1
        assert result.failed == 1

    def test_check_has_metrics_true(self, service, mock_db_manager):
        """Test checking if file has metrics - true case."""
        mock_db_manager.load_sleep_metrics.return_value = [MagicMock()]

        result = service.check_has_metrics("test1.csv")

        assert result is True

    def test_check_has_metrics_false(self, service, mock_db_manager):
        """Test checking if file has metrics - false case."""
        mock_db_manager.load_sleep_metrics.return_value = []

        result = service.check_has_metrics("test1.csv")

        assert result is False

    def test_protocol_compliance(self, service):
        """Test that implementation complies with Protocol."""
        from sleep_scoring_app.services.file_management_service import FileManagementService

        assert isinstance(service, FileManagementService)
