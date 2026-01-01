#!/usr/bin/env python3
"""
Comprehensive unit tests for DiaryRepository.

Tests diary nap/nonwear period save, load, delete, and export operations.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.exceptions import DatabaseError, ValidationError

if TYPE_CHECKING:
    from sleep_scoring_app.data.database import DatabaseManager
    from sleep_scoring_app.data.repositories.diary_repository import DiaryRepository


# ============================================================================
# Fixtures for diary file registration (satisfies FK constraints)
# ============================================================================


@pytest.fixture
def registered_diary_file(test_db: DatabaseManager) -> str:
    """
    Register a diary file in diary_file_registry to satisfy FK constraints.

    Returns the filename for use in tests.
    """
    filename = "DIARY-1001.csv"
    with sqlite3.connect(test_db.db_path) as conn:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {DatabaseTable.DIARY_FILE_REGISTRY}
            (filename, original_path, participant_id, file_hash)
            VALUES (?, ?, ?, ?)
            """,
            (filename, "/path/to/diary.csv", "1001", "hash123"),
        )
        conn.commit()
    return filename


@pytest.fixture
def sample_nap_periods() -> list[dict[str, Any]]:
    """Create sample nap periods for diary."""
    return [
        {"start_time": "14:00", "end_time": "15:00", "quality": 3, "notes": "Afternoon nap"},
        {"start_time": "17:30", "end_time": "18:00", "quality": 2, "notes": None},
    ]


@pytest.fixture
def sample_nonwear_periods() -> list[dict[str, Any]]:
    """Create sample nonwear periods for diary."""
    return [
        {"start_time": "18:00", "end_time": "19:30", "reason": "Shower", "notes": None},
        {"start_time": "21:00", "end_time": "21:30", "reason": "Charging", "notes": "Forgot to put on"},
    ]


# ============================================================================
# TestSaveDiaryNapPeriods - Save Operations
# ============================================================================


class TestSaveDiaryNapPeriods:
    """Tests for save_diary_nap_periods method."""

    def test_saves_complete_nap_periods(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """Saves complete nap periods to database."""
        repo = test_db.diary

        result = repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=sample_nap_periods,
        )

        assert result is True

        # Verify saved
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NAP_PERIODS} WHERE filename = ?",
                (registered_diary_file,),
            )
            count = cursor.fetchone()[0]
            assert count == 2

    def test_replaces_existing_nap_periods(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """Deletes existing nap periods before inserting new ones."""
        repo = test_db.diary

        # First save
        repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=sample_nap_periods,
        )

        # Second save with only one nap
        single_nap = [{"start_time": "14:00", "end_time": "15:00"}]
        repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=single_nap,
        )

        # Should have replaced, not duplicated
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NAP_PERIODS} WHERE filename = ? AND diary_date = ?",
                (registered_diary_file, "2024-01-15"),
            )
            count = cursor.fetchone()[0]
            assert count == 1

    def test_validates_filename(self, test_db: DatabaseManager, sample_nap_periods: list[dict]):
        """ValidationError if filename is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.save_diary_nap_periods(
                filename="",
                participant_id="1001",
                diary_date="2024-01-15",
                nap_periods=sample_nap_periods,
            )

    def test_validates_participant_id(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """ValidationError if participant_id is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.save_diary_nap_periods(
                filename=registered_diary_file,
                participant_id="",
                diary_date="2024-01-15",
                nap_periods=sample_nap_periods,
            )

    def test_validates_diary_date(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """ValidationError if diary_date is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.save_diary_nap_periods(
                filename=registered_diary_file,
                participant_id="1001",
                diary_date="",
                nap_periods=sample_nap_periods,
            )

    def test_skips_empty_nap_periods(self, test_db: DatabaseManager, registered_diary_file: str):
        """Nap periods without start_time or end_time are skipped."""
        repo = test_db.diary

        empty_naps = [
            {"quality": 3, "notes": "No times"},  # No start/end
            {"start_time": "14:00", "end_time": "15:00"},  # Valid
        ]

        repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=empty_naps,
        )

        # Only the valid one should be saved
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NAP_PERIODS} WHERE filename = ?",
                (registered_diary_file,),
            )
            count = cursor.fetchone()[0]
            assert count == 1

    def test_raises_on_db_error(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """DatabaseError raised on database failure."""
        repo = test_db.diary

        original_path = repo.db_path
        repo.db_path = Path("/nonexistent/path/db.sqlite")

        with pytest.raises(DatabaseError):
            repo.save_diary_nap_periods(
                filename=registered_diary_file,
                participant_id="1001",
                diary_date="2024-01-15",
                nap_periods=sample_nap_periods,
            )

        repo.db_path = original_path


# ============================================================================
# TestLoadDiaryNapPeriods - Load Operations
# ============================================================================


class TestLoadDiaryNapPeriods:
    """Tests for load_diary_nap_periods method."""

    def test_loads_saved_nap_periods(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """Returns saved nap periods."""
        repo = test_db.diary

        # Save first
        repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=sample_nap_periods,
        )

        # Load
        loaded = repo.load_diary_nap_periods(filename=registered_diary_file, diary_date="2024-01-15")

        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert loaded[0]["start_time"] == "14:00"
        assert loaded[0]["end_time"] == "15:00"

    def test_returns_empty_list_if_none(self, test_db: DatabaseManager, registered_diary_file: str):
        """Returns empty list if no data."""
        repo = test_db.diary

        loaded = repo.load_diary_nap_periods(filename=registered_diary_file, diary_date="2024-01-15")

        assert isinstance(loaded, list)
        assert len(loaded) == 0

    def test_orders_by_index(self, test_db: DatabaseManager, registered_diary_file: str, sample_nap_periods: list[dict]):
        """Results are ordered by nap_index."""
        repo = test_db.diary

        repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=sample_nap_periods,
        )

        loaded = repo.load_diary_nap_periods(filename=registered_diary_file, diary_date="2024-01-15")

        # First nap should come before second
        assert loaded[0]["index"] == 1
        assert loaded[1]["index"] == 2

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.load_diary_nap_periods(filename="", diary_date="2024-01-15")

    def test_validates_diary_date(self, test_db: DatabaseManager, registered_diary_file: str):
        """ValidationError if diary_date is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.load_diary_nap_periods(filename=registered_diary_file, diary_date="")


# ============================================================================
# TestSaveDiaryNonwearPeriods - Save Operations
# ============================================================================


class TestSaveDiaryNonwearPeriods:
    """Tests for save_diary_nonwear_periods method."""

    def test_saves_complete_nonwear_periods(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """Saves complete nonwear periods to database."""
        repo = test_db.diary

        result = repo.save_diary_nonwear_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nonwear_periods=sample_nonwear_periods,
        )

        assert result is True

        # Verify saved
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NONWEAR_PERIODS} WHERE filename = ?",
                (registered_diary_file,),
            )
            count = cursor.fetchone()[0]
            assert count == 2

    def test_replaces_existing_nonwear_periods(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """Deletes existing nonwear periods before inserting new ones."""
        repo = test_db.diary

        # First save
        repo.save_diary_nonwear_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nonwear_periods=sample_nonwear_periods,
        )

        # Second save with only one period
        single_period = [{"start_time": "18:00", "end_time": "19:00", "reason": "Bath"}]
        repo.save_diary_nonwear_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nonwear_periods=single_period,
        )

        # Should have replaced, not duplicated
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NONWEAR_PERIODS} WHERE filename = ? AND diary_date = ?",
                (registered_diary_file, "2024-01-15"),
            )
            count = cursor.fetchone()[0]
            assert count == 1

    def test_validates_filename(self, test_db: DatabaseManager, sample_nonwear_periods: list[dict]):
        """ValidationError if filename is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.save_diary_nonwear_periods(
                filename="",
                participant_id="1001",
                diary_date="2024-01-15",
                nonwear_periods=sample_nonwear_periods,
            )

    def test_validates_participant_id(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """ValidationError if participant_id is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.save_diary_nonwear_periods(
                filename=registered_diary_file,
                participant_id="",
                diary_date="2024-01-15",
                nonwear_periods=sample_nonwear_periods,
            )

    def test_validates_diary_date(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """ValidationError if diary_date is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.save_diary_nonwear_periods(
                filename=registered_diary_file,
                participant_id="1001",
                diary_date="",
                nonwear_periods=sample_nonwear_periods,
            )

    def test_raises_on_db_error(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """DatabaseError raised on database failure."""
        repo = test_db.diary

        original_path = repo.db_path
        repo.db_path = Path("/nonexistent/path/db.sqlite")

        with pytest.raises(DatabaseError):
            repo.save_diary_nonwear_periods(
                filename=registered_diary_file,
                participant_id="1001",
                diary_date="2024-01-15",
                nonwear_periods=sample_nonwear_periods,
            )

        repo.db_path = original_path


# ============================================================================
# TestLoadDiaryNonwearPeriods - Load Operations
# ============================================================================


class TestLoadDiaryNonwearPeriods:
    """Tests for load_diary_nonwear_periods method."""

    def test_loads_saved_nonwear_periods(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """Returns saved nonwear periods."""
        repo = test_db.diary

        # Save first
        repo.save_diary_nonwear_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nonwear_periods=sample_nonwear_periods,
        )

        # Load
        loaded = repo.load_diary_nonwear_periods(filename=registered_diary_file, diary_date="2024-01-15")

        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert loaded[0]["start_time"] == "18:00"
        assert loaded[0]["reason"] == "Shower"

    def test_returns_empty_list_if_none(self, test_db: DatabaseManager, registered_diary_file: str):
        """Returns empty list if no data."""
        repo = test_db.diary

        loaded = repo.load_diary_nonwear_periods(filename=registered_diary_file, diary_date="2024-01-15")

        assert isinstance(loaded, list)
        assert len(loaded) == 0

    def test_orders_by_index(self, test_db: DatabaseManager, registered_diary_file: str, sample_nonwear_periods: list[dict]):
        """Results are ordered by nonwear_index."""
        repo = test_db.diary

        repo.save_diary_nonwear_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nonwear_periods=sample_nonwear_periods,
        )

        loaded = repo.load_diary_nonwear_periods(filename=registered_diary_file, diary_date="2024-01-15")

        # First period should come before second
        assert loaded[0]["index"] == 1
        assert loaded[1]["index"] == 2

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.load_diary_nonwear_periods(filename="", diary_date="2024-01-15")

    def test_validates_diary_date(self, test_db: DatabaseManager, registered_diary_file: str):
        """ValidationError if diary_date is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.load_diary_nonwear_periods(filename=registered_diary_file, diary_date="")


# ============================================================================
# TestClearDiaryData - Clear Operations
# ============================================================================


class TestClearDiaryData:
    """Tests for clear_diary_data method."""

    def test_clears_all_diary_data(
        self,
        test_db: DatabaseManager,
        registered_diary_file: str,
        sample_nap_periods: list[dict],
        sample_nonwear_periods: list[dict],
    ):
        """Deletes all diary data from all tables."""
        repo = test_db.diary

        # Save some data
        repo.save_diary_nap_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nap_periods=sample_nap_periods,
        )
        repo.save_diary_nonwear_periods(
            filename=registered_diary_file,
            participant_id="1001",
            diary_date="2024-01-15",
            nonwear_periods=sample_nonwear_periods,
        )

        deleted = repo.clear_diary_data()

        # Should have deleted from at least one table (diary_file_registry cascades to others)
        assert deleted >= 1

        # Verify data is actually cleared
        loaded_naps = repo.load_diary_nap_periods(filename=registered_diary_file, diary_date="2024-01-15")
        loaded_nonwear = repo.load_diary_nonwear_periods(filename=registered_diary_file, diary_date="2024-01-15")
        assert len(loaded_naps) == 0
        assert len(loaded_nonwear) == 0

    def test_returns_delete_count(self, test_db: DatabaseManager):
        """Returns total number of deleted rows."""
        repo = test_db.diary

        # No data to delete
        deleted = repo.clear_diary_data()

        assert deleted == 0


# ============================================================================
# TestGetDiaryNapDataForExport - Export Query Operations
# ============================================================================


class TestGetDiaryNapDataForExport:
    """Tests for get_diary_nap_data_for_export method."""

    def test_returns_data_if_exists(self, test_db: DatabaseManager, registered_diary_file: str):
        """Returns nap data dict when data exists."""
        repo = test_db.diary

        # Insert test data into diary_data table
        with sqlite3.connect(test_db.db_path) as conn:
            conn.execute(
                f"""
                INSERT INTO {DatabaseTable.DIARY_DATA}
                (filename, participant_key, participant_id, diary_date,
                 nap_occurred, nap_onset_time, nap_offset_time, nap_onset_time_2, nap_offset_time_2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (registered_diary_file, "1001_T1", "1001", "2024-01-15", 1, "14:00", "15:00", "17:30", "18:00"),
            )
            conn.commit()

        result = repo.get_diary_nap_data_for_export(participant_key="1001_T1", analysis_date="2024-01-15")

        assert result is not None
        assert result["nap_occurred"] == 1
        assert result["nap_onset_time"] == "14:00"
        assert result["nap_offset_time"] == "15:00"
        assert result["nap_onset_time_2"] == "17:30"
        assert result["nap_offset_time_2"] == "18:00"

    def test_returns_none_if_not_exists(self, test_db: DatabaseManager):
        """Returns None if no data for participant/date."""
        repo = test_db.diary

        result = repo.get_diary_nap_data_for_export(participant_key="9999_T1", analysis_date="2024-01-15")

        assert result is None

    def test_validates_participant_key(self, test_db: DatabaseManager):
        """ValidationError if participant_key is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.get_diary_nap_data_for_export(participant_key="", analysis_date="2024-01-15")

    def test_validates_analysis_date(self, test_db: DatabaseManager):
        """ValidationError if analysis_date is empty."""
        repo = test_db.diary

        with pytest.raises(ValidationError):
            repo.get_diary_nap_data_for_export(participant_key="1001_T1", analysis_date="")
