#!/usr/bin/env python3
"""
Unit tests for ImportService.

Tests bulk CSV import, progress tracking, file change detection,
column identification, and timestamp processing.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import pandas as pd
import pytest

from sleep_scoring_app.core.constants import ImportStatus
from sleep_scoring_app.services.import_service import ImportProgress, ImportService


class TestImportProgress:
    """Tests for ImportProgress class."""

    def test_init_defaults(self):
        """Test ImportProgress initialization with defaults."""
        progress = ImportProgress()

        assert progress.total_files == 0
        assert progress.processed_files == 0
        assert progress.total_records == 0
        assert progress.processed_records == 0
        assert progress.current_file == ""
        assert progress.errors == []
        assert progress.warnings == []

    def test_init_with_values(self):
        """Test ImportProgress initialization with values."""
        progress = ImportProgress(total_files=10, total_records=1000)

        assert progress.total_files == 10
        assert progress.total_records == 1000

    def test_file_progress_percent(self):
        """Test file progress percentage calculation."""
        progress = ImportProgress(total_files=10)
        progress.processed_files = 3

        assert progress.file_progress_percent == 30.0

    def test_file_progress_percent_zero_total(self):
        """Test file progress when no files."""
        progress = ImportProgress(total_files=0)

        assert progress.file_progress_percent == 0.0

    def test_record_progress_percent(self):
        """Test record progress percentage calculation."""
        progress = ImportProgress(total_records=1000)
        progress.processed_records = 250

        assert progress.record_progress_percent == 25.0

    def test_record_progress_percent_zero_total(self):
        """Test record progress when no records."""
        progress = ImportProgress(total_records=0)

        assert progress.record_progress_percent == 0.0

    def test_add_error(self):
        """Test adding error message."""
        progress = ImportProgress()
        progress.add_error("Test error")

        assert len(progress.errors) == 1
        assert progress.errors[0] == "Test error"

    def test_add_warning(self):
        """Test adding warning message."""
        progress = ImportProgress()
        progress.add_warning("Test warning")

        assert len(progress.warnings) == 1
        assert progress.warnings[0] == "Test warning"

    def test_add_info(self):
        """Test adding info message."""
        progress = ImportProgress()
        progress.add_info("Test info")

        assert len(progress.info_messages) == 1
        assert progress.info_messages[0] == "Test info"

    def test_nonwear_progress_percent(self):
        """Test nonwear progress percentage calculation."""
        progress = ImportProgress()
        progress.total_nonwear_files = 5
        progress.processed_nonwear_files = 2

        assert progress.nonwear_progress_percent == 40.0


class TestImportService:
    """Tests for ImportService class."""

    @pytest.fixture
    def import_service(self):
        """Create ImportService with mock database."""
        mock_db = MagicMock()
        return ImportService(database_manager=mock_db)

    @pytest.fixture
    def sample_csv_file(self, tmp_path):
        """Create sample CSV file."""
        csv_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"
        csv_file.write_text("Date,Time,Axis1,Vector Magnitude\n2024-01-10,00:00:00,100,150\n2024-01-10,00:01:00,110,160\n")
        return csv_file

    # === File Hash Tests ===

    def test_calculate_file_hash_success(self, import_service, tmp_path):
        """Test successful file hash calculation."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        file_hash = import_service.calculate_file_hash(test_file)

        assert len(file_hash) == 64  # SHA256 hex digest
        assert isinstance(file_hash, str)

    def test_calculate_file_hash_consistency(self, import_service, tmp_path):
        """Test hash calculation is consistent."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        hash1 = import_service.calculate_file_hash(test_file)
        hash2 = import_service.calculate_file_hash(test_file)

        assert hash1 == hash2

    def test_calculate_file_hash_different_files(self, import_service, tmp_path):
        """Test different files produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_bytes(b"content 1")
        file2.write_bytes(b"content 2")

        hash1 = import_service.calculate_file_hash(file1)
        hash2 = import_service.calculate_file_hash(file2)

        assert hash1 != hash2

    def test_calculate_file_hash_nonexistent_file(self, import_service):
        """Test hash calculation for nonexistent file raises error."""
        from sleep_scoring_app.core.exceptions import SleepScoringImportError

        with pytest.raises(SleepScoringImportError, match="Failed to calculate hash"):
            import_service.calculate_file_hash(Path("/nonexistent/file.csv"))

    # === Participant Info Extraction Tests ===

    @patch("sleep_scoring_app.utils.participant_extractor.extract_participant_info")
    def test_extract_participant_info_success(self, mock_extract, import_service, tmp_path):
        """Test successful participant info extraction."""
        test_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"
        test_file.touch()

        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_participant.participant_key = "1000_A_D1"
        mock_extract.return_value = mock_participant

        result = import_service.extract_participant_info(test_file)

        assert result.numerical_id == "1000"
        mock_extract.assert_called_once_with(test_file)

    @patch("sleep_scoring_app.utils.participant_extractor.extract_participant_info")
    def test_extract_participant_info_extraction_error(self, mock_extract, import_service, tmp_path):
        """Test participant info extraction handles errors."""
        from sleep_scoring_app.core.exceptions import SleepScoringImportError

        test_file = tmp_path / "invalid_filename.csv"
        test_file.touch()

        mock_extract.side_effect = ValueError("Invalid format")

        with pytest.raises(SleepScoringImportError, match="Failed to extract participant information"):
            import_service.extract_participant_info(test_file)

    # === Check File Needs Import Tests ===

    def test_check_file_needs_import_new_file(self, import_service, sample_csv_file):
        """Test checking new file that needs import."""
        import_service.db_manager._get_connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None

        with patch.object(import_service, "extract_participant_info") as mock_extract:
            mock_participant = MagicMock()
            mock_participant.participant_key = "1000_A_D1"
            mock_extract.return_value = mock_participant

            needs_import, reason = import_service.check_file_needs_import(sample_csv_file)

        assert needs_import is True
        assert reason == "New participant data"

    def test_check_file_needs_import_hash_changed(self, import_service, sample_csv_file):
        """Test checking file with changed hash."""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("old_hash", ImportStatus.IMPORTED, sample_csv_file.name)
        import_service.db_manager._get_connection.return_value.__enter__.return_value.execute.return_value = mock_cursor

        with patch.object(import_service, "extract_participant_info") as mock_extract:
            with patch.object(import_service, "calculate_file_hash", return_value="new_hash"):
                mock_participant = MagicMock()
                mock_participant.participant_key = "1000_A_D1"
                mock_extract.return_value = mock_participant

                needs_import, reason = import_service.check_file_needs_import(sample_csv_file)

        assert needs_import is True
        assert reason == "File changed"

    def test_check_file_needs_import_already_imported(self, import_service, sample_csv_file):
        """Test checking file that's already imported."""
        current_hash = hashlib.sha256(sample_csv_file.read_bytes()).hexdigest()

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (current_hash, ImportStatus.IMPORTED, sample_csv_file.name)
        import_service.db_manager._get_connection.return_value.__enter__.return_value.execute.return_value = mock_cursor

        with patch.object(import_service, "extract_participant_info") as mock_extract:
            mock_participant = MagicMock()
            mock_participant.participant_key = "1000_A_D1"
            mock_extract.return_value = mock_participant

            needs_import, reason = import_service.check_file_needs_import(sample_csv_file)

        assert needs_import is False
        assert reason == "Already imported"

    def test_check_file_needs_import_previous_error(self, import_service, sample_csv_file):
        """Test checking file with previous import error."""
        current_hash = hashlib.sha256(sample_csv_file.read_bytes()).hexdigest()

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (current_hash, ImportStatus.ERROR, sample_csv_file.name)
        import_service.db_manager._get_connection.return_value.__enter__.return_value.execute.return_value = mock_cursor

        with patch.object(import_service, "extract_participant_info") as mock_extract:
            mock_participant = MagicMock()
            mock_participant.participant_key = "1000_A_D1"
            mock_extract.return_value = mock_participant

            needs_import, reason = import_service.check_file_needs_import(sample_csv_file)

        assert needs_import is True
        assert reason == "Previous import failed"

    # === Load and Validate CSV Tests ===

    def test_load_and_validate_csv_success(self, import_service, sample_csv_file):
        """Test successful CSV loading."""
        df = import_service.csv_transformer.load_csv(sample_csv_file, skip_rows=0)

        assert df is not None
        assert len(df) == 2
        assert "Date" in df.columns

    def test_load_and_validate_csv_with_skip_rows(self, import_service, tmp_path):
        """Test CSV loading with skipped header rows."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Header1\nHeader2\nHeader3\nDate,Time,Activity\n2024-01-10,00:00:00,100\n")

        df = import_service.csv_transformer.load_csv(csv_file, skip_rows=3)

        assert df is not None
        assert len(df) == 1

    def test_load_and_validate_csv_empty_file(self, import_service, tmp_path):
        """Test loading empty CSV file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        df = import_service.csv_transformer.load_csv(csv_file, skip_rows=0)

        assert df is None

    def test_load_and_validate_csv_file_too_large(self, import_service, tmp_path):
        """Test loading CSV file that exceeds size limit."""
        csv_file = tmp_path / "large.csv"
        csv_file.touch()

        # Mock file size to exceed limit
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = import_service.max_file_size + 1

            df = import_service.csv_transformer.load_csv(csv_file, skip_rows=0)

        assert df is None

    # === Column Identification Tests ===

    def test_identify_columns_auto_detect(self, import_service):
        """Test auto-detection of columns."""
        from sleep_scoring_app.core.constants import DatabaseColumn

        df = pd.DataFrame(
            {
                "Date": ["2024-01-10"],
                "Time": ["00:00:00"],
                "Vector Magnitude": [100],
                "Axis1": [50],
            }
        )

        column_mapping = import_service.csv_transformer.identify_columns(df)

        assert column_mapping.date_col == "Date"
        assert column_mapping.time_col == "Time"
        assert column_mapping.activity_col == "Vector Magnitude"  # Prioritizes VM
        assert DatabaseColumn.AXIS_Y in column_mapping.extra_cols

    def test_identify_columns_combined_datetime(self, import_service):
        """Test identification of combined datetime column."""
        df = pd.DataFrame({"datetime": ["2024-01-10 00:00:00"], "Activity": [100]})

        column_mapping = import_service.csv_transformer.identify_columns(df)

        assert column_mapping.date_col == "datetime"
        assert column_mapping.time_col is None  # Combined datetime
        assert column_mapping.activity_col == "Activity"

    def test_identify_columns_custom_columns(self, import_service):
        """Test using custom column mapping."""
        df = pd.DataFrame({"MyDate": ["2024-01-10"], "MyTime": ["00:00:00"], "MyActivity": [100]})

        custom_columns = {"date": "MyDate", "time": "MyTime", "activity": "MyActivity"}

        column_mapping = import_service.csv_transformer.identify_columns(df, custom_columns)

        assert column_mapping.date_col == "MyDate"
        assert column_mapping.time_col == "MyTime"
        assert column_mapping.activity_col == "MyActivity"

    def test_identify_columns_custom_combined_datetime(self, import_service):
        """Test custom column with combined datetime."""
        df = pd.DataFrame({"timestamp": ["2024-01-10 00:00:00"], "counts": [100]})

        custom_columns = {
            "date": "timestamp",
            "activity": "counts",
            "datetime_combined": True,
        }

        column_mapping = import_service.csv_transformer.identify_columns(df, custom_columns)

        assert column_mapping.date_col == "timestamp"
        assert column_mapping.time_col is None
        assert column_mapping.activity_col == "counts"

    def test_identify_columns_custom_axis_mapping(self, import_service):
        """Test custom axis column mapping."""
        from sleep_scoring_app.core.constants import ActivityDataPreference, DatabaseColumn

        df = pd.DataFrame({"date": ["2024-01-10"], "y_data": [100], "x_data": [50], "z_data": [75]})

        custom_columns = {
            "date": "date",
            "activity": "y_data",
            "datetime_combined": True,
            ActivityDataPreference.AXIS_Y: "y_data",
            ActivityDataPreference.AXIS_X: "x_data",
            ActivityDataPreference.AXIS_Z: "z_data",
        }

        column_mapping = import_service.csv_transformer.identify_columns(df, custom_columns)

        assert column_mapping.extra_cols[DatabaseColumn.AXIS_Y] == "y_data"
        assert column_mapping.extra_cols[DatabaseColumn.AXIS_X] == "x_data"
        assert column_mapping.extra_cols[DatabaseColumn.AXIS_Z] == "z_data"

    def test_identify_columns_missing_required(self, import_service):
        """Test identification when required columns are missing."""
        df = pd.DataFrame({"other_column": [1, 2, 3]})

        column_mapping = import_service.csv_transformer.identify_columns(df)

        assert column_mapping.date_col is None
        assert column_mapping.time_col is None
        assert column_mapping.activity_col is None

    # === Timestamp Processing Tests ===

    def test_process_timestamps_separate_date_time(self, import_service):
        """Test processing separate date and time columns."""
        df = pd.DataFrame({"date": ["2024-01-10", "2024-01-10"], "time": ["00:00:00", "00:01:00"]})

        timestamps = import_service.csv_transformer.process_timestamps(df, "date", "time")

        assert timestamps is not None
        assert len(timestamps) == 2
        assert "2024-01-10T00:00:00" in timestamps[0]
        assert "2024-01-10T00:01:00" in timestamps[1]

    def test_process_timestamps_combined_datetime(self, import_service):
        """Test processing combined datetime column."""
        df = pd.DataFrame({"datetime": ["2024-01-10 00:00:00", "2024-01-10 00:01:00"]})

        timestamps = import_service.csv_transformer.process_timestamps(df, "datetime", None)

        assert timestamps is not None
        assert len(timestamps) == 2

    def test_process_timestamps_missing_date_column(self, import_service):
        """Test processing with missing date column."""
        df = pd.DataFrame({"time": ["00:00:00"]})

        timestamps = import_service.csv_transformer.process_timestamps(df, "date", "time")

        assert timestamps is None

    def test_process_timestamps_missing_time_column(self, import_service):
        """Test processing with missing time column."""
        df = pd.DataFrame({"date": ["2024-01-10"]})

        timestamps = import_service.csv_transformer.process_timestamps(df, "date", "time")

        assert timestamps is None

    def test_process_timestamps_invalid_format(self, import_service):
        """Test processing with invalid datetime format."""
        df = pd.DataFrame({"datetime": ["invalid", "also_invalid"]})

        timestamps = import_service.csv_transformer.process_timestamps(df, "datetime", None)

        # Should attempt inference
        assert timestamps is None or len(timestamps) == 0

    # === Import CSV File Tests ===

    def test_import_csv_file_success(self, import_service, sample_csv_file):
        """Test successful CSV file import."""
        from sleep_scoring_app.services.csv_data_transformer import ColumnMapping

        import_service.db_manager._get_connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None

        with patch.object(import_service.csv_transformer, "load_csv") as mock_load:
            with patch.object(import_service.csv_transformer, "identify_columns") as mock_identify:
                with patch.object(import_service.csv_transformer, "process_timestamps") as mock_process:
                    with patch.object(import_service, "_import_data_transaction", return_value=True):
                        # Mock CSV data
                        mock_df = pd.DataFrame({"Date": ["2024-01-10"], "Time": ["00:00"], "Activity": [100]})
                        mock_load.return_value = mock_df

                        # Mock column identification
                        mock_identify.return_value = ColumnMapping("Date", "Time", "Activity", False, {})

                        # Mock timestamp processing
                        mock_process.return_value = ["2024-01-10T00:00:00"]

                        result = import_service.import_csv_file(sample_csv_file, force_reimport=True)

        assert result is True

    def test_import_csv_file_skip_if_imported(self, import_service, sample_csv_file):
        """Test skipping file that's already imported."""
        progress = ImportProgress()

        with patch.object(import_service, "check_file_needs_import", return_value=(False, "Already imported")):
            result = import_service.import_csv_file(sample_csv_file, progress=progress)

        assert result is True
        assert len(progress.skipped_files) == 1

    def test_import_csv_file_exceeds_size_limit(self, import_service, tmp_path):
        """Test importing file that exceeds size limit."""
        large_file = tmp_path / "large.csv"
        large_file.touch()

        progress = ImportProgress()

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = import_service.max_file_size + 1

            with patch.object(import_service, "check_file_needs_import", return_value=(True, "New file")):
                result = import_service.import_csv_file(large_file, progress=progress, force_reimport=True)

        assert result is False
        assert len(progress.errors) > 0

    # === Import Directory Tests ===

    def test_import_directory_success(self, import_service, tmp_path):
        """Test successful directory import."""
        # Create test files
        for i in range(3):
            csv_file = tmp_path / f"file{i}.csv"
            csv_file.write_text("Date,Time,Activity\n2024-01-10,00:00:00,100\n")

        with patch.object(import_service, "import_csv_file", return_value=True):
            progress = import_service.import_directory(tmp_path)

        assert progress.processed_files == 3

    def test_import_directory_with_cancellation(self, import_service, tmp_path):
        """Test directory import with cancellation."""
        # Create test files
        for i in range(5):
            csv_file = tmp_path / f"file{i}.csv"
            csv_file.write_text("Date,Time,Activity\n")

        # Cancel after 2 files
        call_count = [0]

        def cancellation_check():
            call_count[0] += 1
            return call_count[0] > 2

        with patch.object(import_service, "import_csv_file", return_value=True):
            progress = import_service.import_directory(tmp_path, cancellation_check=cancellation_check)

        assert progress.processed_files < 5
        assert len(progress.warnings) > 0

    def test_import_directory_nonexistent(self, import_service):
        """Test importing from nonexistent directory."""
        progress = import_service.import_directory(Path("/nonexistent/dir"))

        assert len(progress.errors) > 0

    # === Import Files Tests ===

    def test_import_files_success(self, import_service, tmp_path):
        """Test successful import of file list."""
        files = []
        for i in range(3):
            csv_file = tmp_path / f"file{i}.csv"
            csv_file.write_text("Date,Time,Activity\n2024-01-10,00:00:00,100\n")
            files.append(csv_file)

        with patch.object(import_service, "import_csv_file", return_value=True):
            progress = import_service.import_files(files)

        assert progress.processed_files == 3

    def test_import_files_with_progress_callback(self, import_service, tmp_path):
        """Test import with progress callback."""
        files = []
        for i in range(3):
            csv_file = tmp_path / f"file{i}.csv"
            csv_file.write_text("Date,Time,Activity\n")
            files.append(csv_file)

        callback = MagicMock()

        with patch.object(import_service, "import_csv_file", return_value=True):
            import_service.import_files(files, progress_callback=callback)

        assert callback.call_count >= 3


class TestImportServiceSignals:
    """Tests for ImportService PyQt signals."""

    def test_signals_emitted_on_file_import(self, tmp_path):
        """Test that signals are emitted during file import."""
        mock_db = MagicMock()
        service = ImportService(database_manager=mock_db)

        from sleep_scoring_app.services.csv_data_transformer import ColumnMapping

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Date,Time,Activity\n2024-01-10,00:00:00,100\n")

        file_started_signal = MagicMock()
        file_completed_signal = MagicMock()
        service.file_started.connect(file_started_signal)
        service.file_completed.connect(file_completed_signal)

        # Mock participant info extraction
        mock_participant = MagicMock()
        mock_participant.participant_key = "1000_A_D1"
        mock_participant.numerical_id = "1000"

        progress = ImportProgress()

        with patch("sleep_scoring_app.utils.participant_extractor.extract_participant_info", return_value=mock_participant):
            with patch.object(service, "calculate_file_hash", return_value="test_hash"):
                with patch.object(
                    service.csv_transformer, "load_csv", return_value=pd.DataFrame({"Date": ["2024-01-10"], "Time": ["00:00"], "Activity": [100]})
                ):
                    with patch.object(service.csv_transformer, "identify_columns", return_value=ColumnMapping("Date", "Time", "Activity", False, {})):
                        with patch.object(service.csv_transformer, "process_timestamps", return_value=["2024-01-10T00:00:00"]):
                            with patch.object(service, "_import_data_transaction", return_value=True):
                                service.import_csv_file(csv_file, progress=progress, force_reimport=True)

        assert file_started_signal.called
        assert file_completed_signal.called
