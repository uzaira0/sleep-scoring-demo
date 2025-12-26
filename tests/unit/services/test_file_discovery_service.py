#!/usr/bin/env python3
"""
Comprehensive tests for FileDiscoveryService.
Tests file finding, validation, and metadata management.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sleep_scoring_app.services.file_service import FileService as FileDiscoveryService


class TestFileDiscoveryService:
    """Tests for FileDiscoveryService class."""

    @pytest.fixture
    def mock_db_manager(self) -> MagicMock:
        """Create a mock database manager."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db_manager: MagicMock) -> FileDiscoveryService:
        """Create a service instance with mock data manager."""
        return FileDiscoveryService(db_manager=mock_db_manager)


class TestInit(TestFileDiscoveryService):
    """Tests for __init__ method."""

    def test_default_max_files(self, mock_db_manager: MagicMock) -> None:
        """Should have default max_files of 1000."""
        service = FileDiscoveryService(db_manager=mock_db_manager)
        assert service._max_files == 1000

    def test_custom_max_files(self, mock_db_manager: MagicMock) -> None:
        """Should accept custom max_files."""
        service = FileDiscoveryService(db_manager=mock_db_manager, max_files=500)
        assert service._max_files == 500

    def test_starts_with_empty_files(self, mock_db_manager: MagicMock) -> None:
        """Should start with empty available_files list."""
        service = FileDiscoveryService(db_manager=mock_db_manager)
        assert service.available_files == []


class TestFindAvailableFiles(TestFileDiscoveryService):
    """Tests for find_available_files method."""

    def test_returns_files_from_db_manager(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return files from data manager."""
        mock_files = [
            {"filename": "file1.csv", "path": "/data/file1.csv"},
            {"filename": "file2.csv", "path": "/data/file2.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files

        result = service.find_available_files()

        assert result == mock_files
        assert service.available_files == mock_files

    def test_limits_files_to_max(self, mock_db_manager: MagicMock) -> None:
        """Should limit files to max_files setting."""
        mock_files = [{"filename": f"file{i}.csv"} for i in range(100)]
        mock_db_manager.find_data_files.return_value = mock_files

        service = FileDiscoveryService(db_manager=mock_db_manager, max_files=50)
        result = service.find_available_files()

        assert len(result) == 50
        assert len(service.available_files) == 50

    def test_returns_all_files_under_limit(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return all files when under limit."""
        mock_files = [{"filename": f"file{i}.csv"} for i in range(100)]
        mock_db_manager.find_data_files.return_value = mock_files

        result = service.find_available_files()

        assert len(result) == 100

    def test_returns_empty_on_error(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return empty list on error."""
        mock_db_manager.find_data_files.side_effect = Exception("Test error")

        result = service.find_available_files()

        assert result == []

    def test_preserves_order(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should preserve file order from data manager."""
        mock_files = [
            {"filename": "aaa.csv"},
            {"filename": "bbb.csv"},
            {"filename": "ccc.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files

        result = service.find_available_files()

        assert [f["filename"] for f in result] == ["aaa.csv", "bbb.csv", "ccc.csv"]


class TestGetFileCount(TestFileDiscoveryService):
    """Tests for get_file_count method."""

    def test_returns_zero_initially(self, service: FileDiscoveryService) -> None:
        """Should return 0 initially."""
        assert service.get_file_count() == 0

    def test_returns_correct_count(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return correct file count."""
        mock_files = [{"filename": f"file{i}.csv"} for i in range(5)]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        assert service.get_file_count() == 5


class TestGetFileByIndex(TestFileDiscoveryService):
    """Tests for get_file_by_index method."""

    def test_returns_file_at_index(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return file at given index."""
        mock_files = [
            {"filename": "file0.csv"},
            {"filename": "file1.csv"},
            {"filename": "file2.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_index(1)

        assert result == {"filename": "file1.csv"}

    def test_returns_none_for_negative_index(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return None for negative index."""
        mock_files = [{"filename": "file.csv"}]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_index(-1)

        assert result is None

    def test_returns_none_for_out_of_bounds(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return None for out of bounds index."""
        mock_files = [{"filename": "file.csv"}]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_index(5)

        assert result is None

    def test_returns_none_for_empty_list(self, service: FileDiscoveryService) -> None:
        """Should return None when no files loaded."""
        result = service.get_file_by_index(0)
        assert result is None

    def test_returns_first_file(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return first file at index 0."""
        mock_files = [
            {"filename": "first.csv"},
            {"filename": "second.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_index(0)

        assert result["filename"] == "first.csv"

    def test_returns_last_file(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return last file at last valid index."""
        mock_files = [
            {"filename": "first.csv"},
            {"filename": "last.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_index(1)

        assert result["filename"] == "last.csv"


class TestGetFileByFilename(TestFileDiscoveryService):
    """Tests for get_file_by_filename method."""

    def test_finds_by_filename(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should find file by filename field."""
        mock_files = [
            {"filename": "file1.csv", "path": "/data/file1.csv"},
            {"filename": "file2.csv", "path": "/data/file2.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_filename("file2.csv")

        assert result is not None
        assert result["filename"] == "file2.csv"

    def test_finds_by_path_basename(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should find file by path basename."""
        mock_files = [
            {"filename": "other.csv", "path": "/data/file1.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_filename("file1.csv")

        assert result is not None
        assert result["path"] == "/data/file1.csv"

    def test_returns_none_for_not_found(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should return None when filename not found."""
        mock_files = [{"filename": "file1.csv"}]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_filename("nonexistent.csv")

        assert result is None

    def test_returns_none_for_empty_list(self, service: FileDiscoveryService) -> None:
        """Should return None when no files loaded."""
        result = service.get_file_by_filename("any.csv")
        assert result is None

    def test_handles_no_path_field(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should handle files without path field."""
        mock_files = [{"filename": "file.csv"}]  # No path field
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_filename("file.csv")

        assert result is not None
        assert result["filename"] == "file.csv"

    def test_case_sensitive(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Filename search should be case-sensitive."""
        mock_files = [{"filename": "File.csv"}]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result_exact = service.get_file_by_filename("File.csv")
        result_lower = service.get_file_by_filename("file.csv")

        assert result_exact is not None
        assert result_lower is None


class TestClearFiles(TestFileDiscoveryService):
    """Tests for clear_files method."""

    def test_clears_files(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should clear available_files list."""
        mock_files = [{"filename": "file.csv"}]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        assert service.get_file_count() == 1

        service.clear_files()

        assert service.get_file_count() == 0
        assert service.available_files == []

    def test_clear_when_already_empty(self, service: FileDiscoveryService) -> None:
        """Should handle clearing when already empty."""
        service.clear_files()  # Should not raise
        assert service.available_files == []


class TestIntegration(TestFileDiscoveryService):
    """Integration tests for FileDiscoveryService."""

    def test_find_get_clear_workflow(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should support find -> get -> clear workflow."""
        mock_files = [
            {"filename": "file1.csv"},
            {"filename": "file2.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files

        # Find files
        service.find_available_files()
        assert service.get_file_count() == 2

        # Get by index
        file1 = service.get_file_by_index(0)
        assert file1["filename"] == "file1.csv"

        # Get by name
        file2 = service.get_file_by_filename("file2.csv")
        assert file2["filename"] == "file2.csv"

        # Clear
        service.clear_files()
        assert service.get_file_count() == 0
        assert service.get_file_by_index(0) is None

    def test_multiple_find_calls(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should handle multiple find calls (refreshing file list)."""
        # First call
        mock_db_manager.find_data_files.return_value = [{"filename": "file1.csv"}]
        service.find_available_files()
        assert service.get_file_count() == 1

        # Second call with different files
        mock_db_manager.find_data_files.return_value = [
            {"filename": "file2.csv"},
            {"filename": "file3.csv"},
        ]
        service.find_available_files()
        assert service.get_file_count() == 2

        # Old file should not be found
        assert service.get_file_by_filename("file1.csv") is None


class TestEdgeCases(TestFileDiscoveryService):
    """Tests for edge cases."""

    def test_handles_file_with_special_characters(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should handle filenames with special characters."""
        mock_files = [
            {"filename": "file (1).csv"},
            {"filename": "file-2.csv"},
            {"filename": "file_3.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        assert service.get_file_by_filename("file (1).csv") is not None
        assert service.get_file_by_filename("file-2.csv") is not None
        assert service.get_file_by_filename("file_3.csv") is not None

    def test_handles_unicode_filenames(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should handle unicode filenames."""
        mock_files = [
            {"filename": "文件.csv"},
            {"filename": "файл.csv"},
        ]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        assert service.get_file_by_filename("文件.csv") is not None
        assert service.get_file_by_filename("файл.csv") is not None

    def test_handles_long_path(self, service: FileDiscoveryService, mock_db_manager: MagicMock) -> None:
        """Should handle very long file paths."""
        long_path = "/data/" + "subdir/" * 50 + "file.csv"
        mock_files = [{"filename": "file.csv", "path": long_path}]
        mock_db_manager.find_data_files.return_value = mock_files
        service.find_available_files()

        result = service.get_file_by_filename("file.csv")
        assert result is not None
        assert result["path"] == long_path

    def test_max_files_exactly_at_limit(self, mock_db_manager: MagicMock) -> None:
        """Should handle exactly max_files files."""
        mock_files = [{"filename": f"file{i}.csv"} for i in range(50)]
        mock_db_manager.find_data_files.return_value = mock_files

        service = FileDiscoveryService(db_manager=mock_db_manager, max_files=50)
        result = service.find_available_files()

        assert len(result) == 50

    def test_max_files_one_over_limit(self, mock_db_manager: MagicMock) -> None:
        """Should limit when exactly one file over limit."""
        mock_files = [{"filename": f"file{i}.csv"} for i in range(51)]
        mock_db_manager.find_data_files.return_value = mock_files

        service = FileDiscoveryService(db_manager=mock_db_manager, max_files=50)
        result = service.find_available_files()

        assert len(result) == 50
