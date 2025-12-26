#!/usr/bin/env python3
"""
Unit tests for batch scoring service.

Tests automatic sleep scoring functionality across multiple files with
diary reference data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

from sleep_scoring_app.services.batch_scoring_service import (
    _apply_sleep_rules,
    _calculate_metrics,
    _discover_activity_files,
    _extract_analysis_date,
    _extract_diary_times,
    _extract_participant_info,
    _find_closest_index,
    _find_diary_entry,
    _load_diary_file,
    _process_activity_file,
    auto_score_activity_epoch_files,
)


class TestAutoScoreActivityEpochFiles:
    """Tests for main auto_score_activity_epoch_files function."""

    @pytest.fixture
    def mock_activity_files(self, tmp_path):
        """Create mock activity CSV files."""
        files = []
        for i in range(3):
            file = tmp_path / f"P1-{1000 + i}-A-D1-P1_2024-01-{10 + i:02d}.csv"
            file.write_text("datetime,Axis1\n2024-01-10 00:00:00,100\n")
            files.append(file)
        return files

    @pytest.fixture
    def mock_diary_df(self):
        """Create mock diary DataFrame."""
        return pd.DataFrame(
            {
                "participant_id": ["1000", "1001", "1002"],
                "date": ["2024-01-10", "2024-01-11", "2024-01-12"],
                "sleep_onset_time": ["22:30", "23:00", "22:00"],
                "sleep_offset_time": ["07:00", "07:30", "06:30"],
            }
        )

    @patch("sleep_scoring_app.services.batch_scoring_service._discover_activity_files")
    @patch("sleep_scoring_app.services.batch_scoring_service._load_diary_file")
    @patch("sleep_scoring_app.services.batch_scoring_service._process_activity_file")
    def test_auto_score_success(self, mock_process, mock_load_diary, mock_discover, mock_activity_files, mock_diary_df):
        """Test successful auto-scoring of all files."""
        mock_discover.return_value = mock_activity_files
        mock_load_diary.return_value = mock_diary_df

        # Mock successful processing
        mock_metrics = MagicMock()
        mock_metrics.daily_sleep_markers.get_complete_periods.return_value = [MagicMock()]
        mock_process.return_value = mock_metrics

        results = auto_score_activity_epoch_files(
            activity_folder=str(mock_activity_files[0].parent),
            diary_file="diary.csv",
        )

        assert len(results) == 3
        assert mock_discover.call_count == 1
        assert mock_load_diary.call_count == 1
        assert mock_process.call_count == 3

    @patch("sleep_scoring_app.services.batch_scoring_service._discover_activity_files")
    @patch("sleep_scoring_app.services.batch_scoring_service._load_diary_file")
    @patch("sleep_scoring_app.services.batch_scoring_service._process_activity_file")
    def test_auto_score_with_failures(self, mock_process, mock_load_diary, mock_discover, mock_activity_files, mock_diary_df):
        """Test auto-scoring with some files failing."""
        mock_discover.return_value = mock_activity_files
        mock_load_diary.return_value = mock_diary_df

        # First file succeeds, second fails, third succeeds
        mock_metrics = MagicMock()
        mock_metrics.daily_sleep_markers.get_complete_periods.return_value = [MagicMock()]
        mock_process.side_effect = [
            mock_metrics,
            Exception("Processing error"),
            mock_metrics,
        ]

        results = auto_score_activity_epoch_files(
            activity_folder=str(mock_activity_files[0].parent),
            diary_file="diary.csv",
        )

        assert len(results) == 2  # Only successful files
        assert mock_process.call_count == 3

    @patch("sleep_scoring_app.services.batch_scoring_service._discover_activity_files")
    @patch("sleep_scoring_app.services.batch_scoring_service._load_diary_file")
    def test_auto_score_empty_folder(self, mock_load_diary, mock_discover, mock_diary_df):
        """Test auto-scoring with no activity files."""
        mock_discover.return_value = []
        mock_load_diary.return_value = mock_diary_df

        results = auto_score_activity_epoch_files(
            activity_folder="/empty/folder",
            diary_file="diary.csv",
        )

        assert len(results) == 0

    @patch("sleep_scoring_app.services.batch_scoring_service._discover_activity_files")
    @patch("sleep_scoring_app.services.batch_scoring_service._load_diary_file")
    @patch("sleep_scoring_app.services.batch_scoring_service._process_activity_file")
    def test_auto_score_with_custom_algorithm(self, mock_process, mock_load_diary, mock_discover, mock_activity_files, mock_diary_df):
        """Test auto-scoring with custom sleep algorithm."""
        mock_discover.return_value = mock_activity_files
        mock_load_diary.return_value = mock_diary_df

        mock_metrics = MagicMock()
        mock_metrics.daily_sleep_markers.get_complete_periods.return_value = [MagicMock()]
        mock_process.return_value = mock_metrics

        custom_algorithm = MagicMock()
        custom_algorithm.name = "Custom Algorithm"

        results = auto_score_activity_epoch_files(
            activity_folder=str(mock_activity_files[0].parent),
            diary_file="diary.csv",
            sleep_algorithm=custom_algorithm,
        )

        assert len(results) == 3
        # Check that custom algorithm was passed to process function
        for call in mock_process.call_args_list:
            assert call[1]["sleep_algorithm"] == custom_algorithm


class TestDiscoverActivityFiles:
    """Tests for _discover_activity_files function."""

    def test_discover_activity_files_success(self, tmp_path):
        """Test discovering activity files in folder."""
        # Create test files
        (tmp_path / "file1.csv").touch()
        (tmp_path / "file2.csv").touch()
        (tmp_path / "file3.txt").touch()  # Should be ignored

        files = _discover_activity_files(str(tmp_path))

        assert len(files) == 2
        assert all(f.suffix == ".csv" for f in files)

    def test_discover_activity_files_sorted(self, tmp_path):
        """Test that files are sorted."""
        (tmp_path / "c.csv").touch()
        (tmp_path / "a.csv").touch()
        (tmp_path / "b.csv").touch()

        files = _discover_activity_files(str(tmp_path))

        filenames = [f.name for f in files]
        assert filenames == ["a.csv", "b.csv", "c.csv"]

    def test_discover_activity_files_nonexistent_folder(self):
        """Test discovering files in nonexistent folder raises error."""
        with pytest.raises(FileNotFoundError, match="Activity folder not found"):
            _discover_activity_files("/nonexistent/folder")

    def test_discover_activity_files_empty_folder(self, tmp_path):
        """Test discovering files in empty folder."""
        files = _discover_activity_files(str(tmp_path))
        assert len(files) == 0


class TestLoadDiaryFile:
    """Tests for _load_diary_file function."""

    def test_load_diary_file_success(self, tmp_path):
        """Test loading valid diary file."""
        diary_file = tmp_path / "diary.csv"
        diary_file.write_text("participant_id,date,bedtime\n1000,2024-01-10,22:00\n")

        df = _load_diary_file(str(diary_file))

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "participant_id" in df.columns

    def test_load_diary_file_nonexistent(self):
        """Test loading nonexistent diary file raises error."""
        with pytest.raises(FileNotFoundError, match="Diary file not found"):
            _load_diary_file("/nonexistent/diary.csv")


class TestProcessActivityFile:
    """Tests for _process_activity_file function."""

    @pytest.fixture
    def activity_df(self):
        """Create sample activity DataFrame."""
        timestamps = pd.date_range("2024-01-10 00:00", periods=1440, freq="min")
        return pd.DataFrame(
            {
                "datetime": timestamps,
                "Axis1": [50 + (i % 100) for i in range(1440)],
            }
        )

    @pytest.fixture
    def diary_df(self):
        """Create sample diary DataFrame."""
        return pd.DataFrame(
            {
                "participant_id": ["1000"],
                "date": ["2024-01-10"],
                "sleep_onset_time": ["22:00"],
                "sleep_offset_time": ["07:00"],
            }
        )

    @patch("sleep_scoring_app.services.batch_scoring_service.pd.read_csv")
    @patch("sleep_scoring_app.services.batch_scoring_service.extract_participant_info")
    def test_process_activity_file_success(self, mock_extract, mock_read_csv, activity_df, diary_df, tmp_path):
        """Test successful processing of activity file."""
        activity_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"
        activity_file.touch()

        mock_read_csv.return_value = activity_df
        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_extract.return_value = mock_participant

        with patch("sleep_scoring_app.services.batch_scoring_service.AlgorithmFactory"):
            with patch("sleep_scoring_app.services.batch_scoring_service.choi_detect_nonwear"):
                result = _process_activity_file(activity_file, diary_df)

        assert result is not None
        assert result.filename == activity_file.name

    @patch("sleep_scoring_app.services.batch_scoring_service.pd.read_csv")
    def test_process_activity_file_missing_datetime_column(self, mock_read_csv, diary_df, tmp_path):
        """Test processing file without datetime column."""
        activity_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"
        activity_file.touch()

        # DataFrame without datetime column
        mock_read_csv.return_value = pd.DataFrame({"Axis1": [100, 200, 300]})

        result = _process_activity_file(activity_file, diary_df)

        assert result is None

    def test_process_activity_file_no_diary_entry(self, tmp_path):
        """Test processing file when no diary entry exists."""
        activity_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"
        timestamps = pd.date_range("2024-01-10 00:00", periods=100, freq="min")
        activity_df = pd.DataFrame({"datetime": timestamps, "Axis1": [50] * 100})

        with patch("sleep_scoring_app.services.batch_scoring_service.pd.read_csv", return_value=activity_df):
            with patch("sleep_scoring_app.services.batch_scoring_service.extract_participant_info"):
                with patch("sleep_scoring_app.services.batch_scoring_service.AlgorithmFactory"):
                    with patch("sleep_scoring_app.services.batch_scoring_service.choi_detect_nonwear"):
                        # Empty diary DataFrame
                        result = _process_activity_file(activity_file, pd.DataFrame())

        assert result is not None  # Should still process without diary


class TestExtractParticipantInfo:
    """Tests for _extract_participant_info function."""

    @patch("sleep_scoring_app.services.batch_scoring_service.extract_participant_info")
    def test_extract_participant_info_success(self, mock_extract, tmp_path):
        """Test extracting participant info from filename."""
        activity_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"

        mock_participant = MagicMock()
        mock_participant.numerical_id = "1000"
        mock_extract.return_value = mock_participant

        result = _extract_participant_info(activity_file)

        assert result.numerical_id == "1000"
        mock_extract.assert_called_once_with(activity_file.name)


class TestExtractAnalysisDate:
    """Tests for _extract_analysis_date function."""

    def test_extract_analysis_date_from_filename(self, tmp_path):
        """Test extracting date from filename."""
        activity_file = tmp_path / "P1-1000-A-D1-P1_2024-01-10.csv"
        activity_file.touch()

        date_str = _extract_analysis_date(activity_file)

        assert date_str == "2024-01-10"

    def test_extract_analysis_date_fallback_to_mtime(self, tmp_path):
        """Test fallback to file modification time."""
        activity_file = tmp_path / "participant_data.csv"
        activity_file.touch()

        date_str = _extract_analysis_date(activity_file)

        # Should return a valid date string
        assert isinstance(date_str, str)
        assert len(date_str) == 10  # YYYY-MM-DD format


class TestFindDiaryEntry:
    """Tests for _find_diary_entry function."""

    def test_find_diary_entry_success(self):
        """Test finding matching diary entry."""
        diary_df = pd.DataFrame(
            {
                "participant_id": ["1000", "1001"],
                "date": ["2024-01-10", "2024-01-10"],
                "bedtime": ["22:00", "23:00"],
            }
        )

        entry = _find_diary_entry(diary_df, "1000", "2024-01-10")

        assert entry is not None
        assert entry["participant_id"] == "1000"
        assert entry["bedtime"] == "22:00"

    def test_find_diary_entry_not_found(self):
        """Test when no matching diary entry exists."""
        diary_df = pd.DataFrame(
            {
                "participant_id": ["1000"],
                "date": ["2024-01-10"],
            }
        )

        entry = _find_diary_entry(diary_df, "9999", "2024-01-10")

        assert entry is None

    def test_find_diary_entry_missing_columns(self):
        """Test finding entry when required columns are missing."""
        diary_df = pd.DataFrame({"other_column": [1, 2, 3]})

        entry = _find_diary_entry(diary_df, "1000", "2024-01-10")

        assert entry is None


class TestExtractDiaryTimes:
    """Tests for _extract_diary_times function."""

    def test_extract_diary_times_success(self):
        """Test extracting valid diary times."""
        diary_entry = {
            "sleep_onset_time": "22:30",
            "sleep_offset_time": "07:00",
        }

        onset, offset = _extract_diary_times(diary_entry, "2024-01-10")

        assert onset == datetime(2024, 1, 10, 22, 30)
        assert offset == datetime(2024, 1, 11, 7, 0)  # Next day

    def test_extract_diary_times_cross_midnight(self):
        """Test extracting times that cross midnight."""
        diary_entry = {
            "sleep_onset_time": "23:30",
            "sleep_offset_time": "06:30",
        }

        onset, offset = _extract_diary_times(diary_entry, "2024-01-10")

        assert onset == datetime(2024, 1, 10, 23, 30)
        assert offset == datetime(2024, 1, 11, 6, 30)  # Next day

    def test_extract_diary_times_same_day(self):
        """Test extracting times on same day (nap)."""
        diary_entry = {
            "sleep_onset_time": "14:00",
            "sleep_offset_time": "16:00",
        }

        onset, offset = _extract_diary_times(diary_entry, "2024-01-10")

        assert onset == datetime(2024, 1, 10, 14, 0)
        assert offset == datetime(2024, 1, 10, 16, 0)  # Same day

    def test_extract_diary_times_missing_values(self):
        """Test extracting when times are missing."""
        diary_entry = {}

        onset, offset = _extract_diary_times(diary_entry, "2024-01-10")

        assert onset is None
        assert offset is None

    def test_extract_diary_times_invalid_format(self):
        """Test extracting invalid time format."""
        diary_entry = {
            "sleep_onset_time": "invalid",
            "sleep_offset_time": "also_invalid",
        }

        onset, offset = _extract_diary_times(diary_entry, "2024-01-10")

        assert onset is None
        assert offset is None


class TestApplySleepRules:
    """Tests for _apply_sleep_rules function."""

    @patch("sleep_scoring_app.services.batch_scoring_service.SleepPeriodDetectorFactory")
    def test_apply_sleep_rules_with_diary(self, mock_factory):
        """Test applying sleep rules with diary reference."""
        timestamps = pd.date_range("2024-01-10 00:00", periods=1440, freq="min")
        activity_df = pd.DataFrame(
            {
                "datetime": timestamps,
                "Sadeh Score": [1] * 1440,
            }
        )

        mock_detector = MagicMock()
        mock_detector.apply_rules.return_value = (100, 500)
        mock_factory.create.return_value = mock_detector
        mock_factory.get_default_detector_id.return_value = "consecutive_onset3s_offset5s"

        onset = datetime(2024, 1, 10, 22, 0)
        offset = datetime(2024, 1, 11, 7, 0)

        daily_markers = _apply_sleep_rules(activity_df, onset, offset)

        assert daily_markers.period_1 is not None
        mock_detector.apply_rules.assert_called_once()

    def test_apply_sleep_rules_without_diary(self):
        """Test applying sleep rules without diary reference."""
        timestamps = pd.date_range("2024-01-10 00:00", periods=100, freq="min")
        activity_df = pd.DataFrame(
            {
                "datetime": timestamps,
                "Sadeh Score": [1] * 100,
            }
        )

        with patch("sleep_scoring_app.services.batch_scoring_service.SleepPeriodDetectorFactory"):
            daily_markers = _apply_sleep_rules(activity_df, None, None)

        # Should process with default markers
        assert daily_markers is not None


class TestCalculateMetrics:
    """Tests for _calculate_metrics function."""

    def test_calculate_metrics_with_complete_period(self):
        """Test calculating metrics for complete sleep period."""
        from sleep_scoring_app.core.dataclasses import DailySleepMarkers, SleepPeriod

        # Create sleep period
        onset = datetime(2024, 1, 10, 22, 0).timestamp()
        offset = datetime(2024, 1, 11, 7, 0).timestamp()
        period = SleepPeriod(onset_timestamp=onset, offset_timestamp=offset, marker_index=1)

        daily_markers = DailySleepMarkers()
        daily_markers.period_1 = period

        # Create activity data
        timestamps = pd.date_range("2024-01-10 00:00", periods=1440, freq="min")
        activity_df = pd.DataFrame(
            {
                "datetime": timestamps,
                "Sadeh Score": [1] * 1440,
                "Choi Nonwear": [0] * 1440,
                "Vector Magnitude": [50] * 1440,
            }
        )

        metrics = _calculate_metrics(daily_markers, activity_df)

        assert "onset_time" in metrics
        assert "offset_time" in metrics
        assert "total_sleep_time" in metrics
        assert metrics["total_sleep_time"] is not None

    def test_calculate_metrics_incomplete_period(self):
        """Test calculating metrics for incomplete sleep period."""
        from sleep_scoring_app.core.dataclasses import DailySleepMarkers

        daily_markers = DailySleepMarkers()  # No periods

        timestamps = pd.date_range("2024-01-10 00:00", periods=100, freq="min")
        activity_df = pd.DataFrame({"datetime": timestamps, "Sadeh Score": [1] * 100})

        metrics = _calculate_metrics(daily_markers, activity_df)

        # Should return empty metrics
        assert metrics["onset_time"] == ""
        assert metrics["total_sleep_time"] is None


class TestFindClosestIndex:
    """Tests for _find_closest_index function."""

    def test_find_closest_index_exact_match(self):
        """Test finding exact timestamp match."""
        timestamps = [
            datetime(2024, 1, 10, 0, 0),
            datetime(2024, 1, 10, 1, 0),
            datetime(2024, 1, 10, 2, 0),
        ]
        target = datetime(2024, 1, 10, 1, 0)

        idx = _find_closest_index(timestamps, target)

        assert idx == 1

    def test_find_closest_index_closest_match(self):
        """Test finding closest timestamp when no exact match."""
        timestamps = [
            datetime(2024, 1, 10, 0, 0),
            datetime(2024, 1, 10, 1, 0),
            datetime(2024, 1, 10, 2, 0),
        ]
        target = datetime(2024, 1, 10, 0, 50)

        idx = _find_closest_index(timestamps, target)

        assert idx == 1  # Closer to 1:00 than 0:00

    def test_find_closest_index_empty_list(self):
        """Test finding closest index in empty list."""
        idx = _find_closest_index([], datetime(2024, 1, 10, 0, 0))

        assert idx is None

    def test_find_closest_index_single_element(self):
        """Test finding closest index with single element."""
        timestamps = [datetime(2024, 1, 10, 0, 0)]
        target = datetime(2024, 1, 10, 5, 0)

        idx = _find_closest_index(timestamps, target)

        assert idx == 0
