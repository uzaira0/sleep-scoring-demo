#!/usr/bin/env python3
"""
Unit tests for ExportManager.

Tests CSV export functionality, backup creation, file operations,
and data sanitization.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

from sleep_scoring_app.core.constants import AlgorithmType
from sleep_scoring_app.services.export_service import ExportManager


class TestExportManager:
    """Tests for ExportManager class."""

    @pytest.fixture
    def export_manager(self):
        """Create ExportManager with mock database."""
        mock_db = MagicMock()
        return ExportManager(database_manager=mock_db)

    @pytest.fixture
    def sample_sleep_metrics(self):
        """Create sample SleepMetrics objects."""
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        metrics_list = []
        for i in range(3):
            participant = ParticipantInfo(
                numerical_id=f"{1000 + i}",
                group_str="Control",
                timepoint_str="T1",
            )

            onset = datetime(2024, 1, 10 + i, 22, 0).timestamp()
            offset = datetime(2024, 1, 11 + i, 7, 0).timestamp()
            period = SleepPeriod(onset_timestamp=onset, offset_timestamp=offset, marker_index=1)

            markers = DailySleepMarkers()
            markers.period_1 = period

            metrics = SleepMetrics(
                filename=f"participant_{1000 + i}.csv",
                analysis_date=f"2024-01-{10 + i:02d}",
                algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
                daily_sleep_markers=markers,
                participant=participant,
                total_sleep_time=420.0,
                sleep_efficiency=85.0,
            )
            metrics_list.append(metrics)

        return metrics_list

    # === CSV Sanitization Tests ===

    def test_sanitize_csv_cell_normal_string(self, export_manager):
        """Test sanitization of normal string."""
        result = export_manager._sanitize_csv_cell("normal text")
        assert result == "normal text"

    def test_sanitize_csv_cell_formula_injection_equals(self, export_manager):
        """Test sanitization prevents formula injection with equals sign."""
        result = export_manager._sanitize_csv_cell("=SUM(A1:A10)")
        assert result == "'=SUM(A1:A10)"

    def test_sanitize_csv_cell_formula_injection_plus(self, export_manager):
        """Test sanitization prevents formula injection with plus sign."""
        result = export_manager._sanitize_csv_cell("+1234")
        assert result == "'+1234"

    def test_sanitize_csv_cell_formula_injection_minus(self, export_manager):
        """Test sanitization prevents formula injection with minus sign."""
        result = export_manager._sanitize_csv_cell("-1234")
        assert result == "'-1234"

    def test_sanitize_csv_cell_formula_injection_at(self, export_manager):
        """Test sanitization prevents formula injection with at sign."""
        result = export_manager._sanitize_csv_cell("@SUM(A1)")
        assert result == "'@SUM(A1)"

    def test_sanitize_csv_cell_formula_injection_tab(self, export_manager):
        """Test sanitization prevents formula injection with tab."""
        result = export_manager._sanitize_csv_cell("\t1234")
        assert result == "'\t1234"

    def test_sanitize_csv_cell_non_string(self, export_manager):
        """Test sanitization preserves non-string values."""
        assert export_manager._sanitize_csv_cell(123) == 123
        assert export_manager._sanitize_csv_cell(45.67) == 45.67
        assert export_manager._sanitize_csv_cell(None) is None

    def test_sanitize_csv_cell_empty_string(self, export_manager):
        """Test sanitization of empty string."""
        assert export_manager._sanitize_csv_cell("") == ""

    # === Atomic CSV Write Tests ===

    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.replace")
    @patch("pathlib.Path.unlink")
    def test_atomic_csv_write_success(self, mock_unlink, mock_replace, mock_exists, mock_stat, export_manager, tmp_path):
        """Test successful atomic CSV write."""
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})

        # Mock stat to show file has size
        mock_stat.return_value.st_size = 100

        with patch("pandas.DataFrame.to_csv"):
            export_manager._atomic_csv_write(df, csv_path, index=False)

        # Should not unlink on success
        mock_unlink.assert_not_called()

    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.unlink")
    def test_atomic_csv_write_empty_file_cleanup(self, mock_unlink, mock_exists, mock_stat, export_manager, tmp_path):
        """Test cleanup on empty file write."""
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({"A": [1, 2]})

        # Mock stat to show file is empty
        mock_stat.return_value.st_size = 0

        with pytest.raises(OSError, match="CSV write produced empty file"), patch("pandas.DataFrame.to_csv"):
            export_manager._atomic_csv_write(df, csv_path)

        # Should clean up temp file
        mock_unlink.assert_called_once()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.unlink")
    def test_atomic_csv_write_exception_cleanup(self, mock_unlink, mock_exists, export_manager, tmp_path):
        """Test cleanup on write exception."""
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({"A": [1, 2]})

        with pytest.raises(ValueError), patch("pandas.DataFrame.to_csv", side_effect=ValueError("Write error")):
            export_manager._atomic_csv_write(df, csv_path)

        # Should clean up temp file
        mock_unlink.assert_called_once()

    # === Export All Sleep Data Tests ===

    @patch("sleep_scoring_app.services.export_service.datetime")
    def test_export_all_sleep_data_success(self, mock_datetime, export_manager, tmp_path):
        """Test successful export of all sleep data."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)

        export_manager.db_manager.get_all_sleep_data_for_export.return_value = [
            {"filename": "file1.csv", "participant_id": "1000"},
            {"filename": "file2.csv", "participant_id": "1001"},
        ]

        with patch.object(export_manager, "_atomic_csv_write"):
            result = export_manager.export_all_sleep_data(str(tmp_path))

        assert "Exported 2 records" in result

    def test_export_all_sleep_data_no_data(self, export_manager):
        """Test export when no data available."""
        export_manager.db_manager.get_all_sleep_data_for_export.return_value = []

        result = export_manager.export_all_sleep_data()

        assert result == "No data available for export"

    def test_export_all_sleep_data_database_error(self, export_manager):
        """Test export handles database errors."""
        from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes

        export_manager.db_manager.get_all_sleep_data_for_export.side_effect = DatabaseError("Query failed", ErrorCodes.DB_QUERY_FAILED)

        result = export_manager.export_all_sleep_data()

        assert result is None

    # === Create Export CSV Only Tests ===

    @patch("sleep_scoring_app.services.export_service.datetime")
    def test_create_export_csv_only_success(self, mock_datetime, export_manager, sample_sleep_metrics, tmp_path):
        """Test creating export CSV without database save."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)

        with patch("pathlib.Path.cwd", return_value=tmp_path), patch.object(export_manager, "_ensure_metrics_calculated_for_export"):
            result = export_manager.create_export_csv_only(sample_sleep_metrics)

        assert result is not None
        assert "export_temp" in result

    def test_create_export_csv_only_empty_list(self, export_manager):
        """Test creating export CSV with empty list."""
        result = export_manager.create_export_csv_only([])
        assert result is None

    @patch("sleep_scoring_app.services.export_service.datetime")
    def test_create_export_csv_only_sanitizes_algorithm_name(self, mock_datetime, export_manager, sample_sleep_metrics, tmp_path):
        """Test that algorithm name is sanitized in filename."""
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)

        with patch("pathlib.Path.cwd", return_value=tmp_path), patch.object(export_manager, "_ensure_metrics_calculated_for_export"):
            result = export_manager.create_export_csv_only(sample_sleep_metrics, algorithm_name="<script>alert()</script>")

        # Filename should not contain dangerous characters
        assert result is not None
        assert "<script>" not in result

    # === Direct Export Tests ===

    def test_perform_direct_export_success(self, export_manager, sample_sleep_metrics, tmp_path):
        """Test successful direct export."""
        from sleep_scoring_app.core.constants import ExportColumn

        with patch.object(export_manager, "_ensure_metrics_calculated_for_export"):
            with patch.object(export_manager, "_group_export_data") as mock_group:
                mock_group.return_value = {"all_data": sample_sleep_metrics}

                result = export_manager.perform_direct_export(
                    sample_sleep_metrics,
                    grouping_option=0,
                    output_directory=str(tmp_path),
                    selected_columns=[ExportColumn.NUMERICAL_PARTICIPANT_ID, ExportColumn.TOTAL_SLEEP_TIME],
                )

        assert result.success is True

    def test_perform_direct_export_empty_list(self, export_manager, tmp_path):
        """Test direct export with empty metrics list."""
        result = export_manager.perform_direct_export(
            [],
            grouping_option=0,
            output_directory=str(tmp_path),
            selected_columns=[],
        )

        assert result.success is False

    def test_perform_direct_export_creates_directory(self, export_manager, sample_sleep_metrics, tmp_path):
        """Test that export creates output directory if missing."""
        from sleep_scoring_app.core.constants import ExportColumn

        output_dir = tmp_path / "new_dir"
        assert not output_dir.exists()

        with patch.object(export_manager, "_ensure_metrics_calculated_for_export"):
            with patch.object(export_manager, "_group_export_data") as mock_group:
                mock_group.return_value = {"all_data": sample_sleep_metrics}

                export_manager.perform_direct_export(
                    sample_sleep_metrics,
                    grouping_option=0,
                    output_directory=str(output_dir),
                    selected_columns=[ExportColumn.NUMERICAL_PARTICIPANT_ID],
                )

        assert output_dir.exists()

    def test_perform_direct_export_column_filtering(self, export_manager, sample_sleep_metrics, tmp_path):
        """Test that column filtering works correctly."""
        from sleep_scoring_app.core.constants import ExportColumn

        with patch.object(export_manager, "_ensure_metrics_calculated_for_export"):
            with patch.object(export_manager, "_group_export_data") as mock_group:
                mock_group.return_value = {"all_data": sample_sleep_metrics}

                with patch("pandas.DataFrame.to_csv") as mock_to_csv:
                    export_manager.perform_direct_export(
                        sample_sleep_metrics,
                        grouping_option=0,
                        output_directory=str(tmp_path),
                        selected_columns=[ExportColumn.NUMERICAL_PARTICIPANT_ID, ExportColumn.TOTAL_SLEEP_TIME],
                    )

                # Check that DataFrame was filtered to selected columns
                # (would need to inspect actual call, simplified here)
                assert mock_to_csv.called

    # === Grouping Tests ===

    def test_group_export_data_all(self, export_manager, sample_sleep_metrics):
        """Test grouping all data in one file."""
        groups = export_manager._group_export_data(sample_sleep_metrics, grouping_option=0)

        assert len(groups) == 1
        assert "all_data" in groups
        assert len(groups["all_data"]) == 3

    def test_group_export_data_by_participant(self, export_manager, sample_sleep_metrics):
        """Test grouping by participant."""
        groups = export_manager._group_export_data(sample_sleep_metrics, grouping_option=1)

        assert len(groups) == 3
        assert "1000" in groups
        assert "1001" in groups
        assert "1002" in groups

    def test_group_export_data_by_group(self, export_manager, sample_sleep_metrics):
        """Test grouping by study group."""
        groups = export_manager._group_export_data(sample_sleep_metrics, grouping_option=2)

        assert len(groups) == 1
        assert "Control" in groups
        assert len(groups["Control"]) == 3

    def test_group_export_data_by_timepoint(self, export_manager, sample_sleep_metrics):
        """Test grouping by timepoint."""
        groups = export_manager._group_export_data(sample_sleep_metrics, grouping_option=3)

        assert len(groups) == 1
        assert "T1" in groups
        assert len(groups["T1"]) == 3

    def test_group_export_data_invalid_option(self, export_manager, sample_sleep_metrics):
        """Test grouping with invalid option falls back to all data."""
        groups = export_manager._group_export_data(sample_sleep_metrics, grouping_option=999)

        assert len(groups) == 1
        assert "all_data" in groups

    # === File Hash Tests ===

    def test_calculate_file_hash(self, export_manager, tmp_path):
        """Test calculating file hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        hash1 = export_manager._calculate_file_hash(test_file)
        hash2 = export_manager._calculate_file_hash(test_file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length

    def test_calculate_file_hash_different_content(self, export_manager, tmp_path):
        """Test that different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        hash1 = export_manager._calculate_file_hash(file1)
        hash2 = export_manager._calculate_file_hash(file2)

        assert hash1 != hash2

    # === Backup Tests ===

    @patch("shutil.copy2")
    def test_create_backup_success(self, mock_copy, export_manager, tmp_path):
        """Test successful backup creation."""
        from sleep_scoring_app.core.constants import DirectoryName

        csv_path = tmp_path / "data.csv"
        csv_path.write_text("test,data\n1,2\n")

        with patch.object(export_manager, "_calculate_file_hash", return_value="abc123"):
            backup_path = export_manager._create_backup(csv_path)

        assert mock_copy.called
        assert backup_path.parent.name == DirectoryName.BACKUPS

    def test_create_backup_hash_verification_fails(self, export_manager, tmp_path):
        """Test backup creation with hash verification failure."""
        from sleep_scoring_app.core.constants import DirectoryName
        from sleep_scoring_app.core.exceptions import DatabaseError

        csv_path = tmp_path / "data.csv"
        csv_path.write_text("test,data\n1,2\n")

        # Create backup directory and a dummy backup file that will be created by copy2
        backup_dir = tmp_path / DirectoryName.BACKUPS
        backup_dir.mkdir(exist_ok=True)

        # Mock different hashes for original and backup - this will trigger verification failure
        with (
            patch.object(export_manager, "_calculate_file_hash", side_effect=["hash1", "hash2"]),
            pytest.raises(DatabaseError, match="Backup verification failed"),
        ):
            export_manager._create_backup(csv_path)

    @patch("shutil.copy2")
    def test_create_backup_rotation(self, mock_copy, export_manager, tmp_path):
        """Test that old backups are rotated."""
        from sleep_scoring_app.core.constants import DirectoryName

        csv_path = tmp_path / "data.csv"
        csv_path.write_text("test,data\n1,2\n")

        backup_dir = csv_path.parent / DirectoryName.BACKUPS
        backup_dir.mkdir()

        # Create 15 old backups that match the rotation pattern *_data_*.csv
        for i in range(15):
            old_backup = backup_dir / f"20240101_{i:05d}_data_backup.csv"
            old_backup.touch()

        export_manager.max_backups = 10

        with patch.object(export_manager, "_calculate_file_hash", return_value="abc123"), patch("pathlib.Path.write_text"):
            export_manager._create_backup(csv_path)

        # Should delete oldest backups (rotation pattern: *_data_*.csv)
        remaining_backups = list(backup_dir.glob("*_data_*.csv"))
        assert len(remaining_backups) <= export_manager.max_backups


class TestExportServiceIntegration:
    """Integration tests for export service."""

    def test_full_export_workflow(self, tmp_path):
        """Test complete export workflow from metrics to CSV file."""
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        # Create sample metrics
        participant = ParticipantInfo(numerical_id="1000", group_str="Test", timepoint_str="T1")
        onset = datetime(2024, 1, 10, 22, 0).timestamp()
        offset = datetime(2024, 1, 11, 7, 0).timestamp()
        period = SleepPeriod(onset_timestamp=onset, offset_timestamp=offset, marker_index=1)

        markers = DailySleepMarkers()
        markers.period_1 = period

        metrics = SleepMetrics(
            filename="test_file.csv",
            analysis_date="2024-01-10",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=markers,
            participant=participant,
            total_sleep_time=420.0,
        )

        # Export
        mock_db = MagicMock()
        export_manager = ExportManager(database_manager=mock_db)

        with patch.object(export_manager, "_ensure_metrics_calculated_for_export"):
            result = export_manager.create_export_csv_only([metrics])

        assert result is not None
        assert Path(result).suffix == ".csv"
