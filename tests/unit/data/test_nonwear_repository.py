#!/usr/bin/env python3
"""
Comprehensive unit tests for NonwearRepository.

Tests nonwear marker save, load, delete, and query operations.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.dataclasses import DailyNonwearMarkers, ManualNonwearPeriod
from sleep_scoring_app.core.exceptions import DatabaseError, ValidationError

if TYPE_CHECKING:
    from sleep_scoring_app.data.database import DatabaseManager
    from sleep_scoring_app.data.repositories.nonwear_repository import NonwearRepository


# ============================================================================
# Fixtures for nonwear markers
# ============================================================================


@pytest.fixture
def sample_nonwear_period() -> ManualNonwearPeriod:
    """Create a sample nonwear period."""
    return ManualNonwearPeriod(
        start_timestamp=datetime(2024, 1, 15, 10, 0).timestamp(),
        end_timestamp=datetime(2024, 1, 15, 12, 0).timestamp(),
        marker_index=1,
    )


@pytest.fixture
def sample_daily_nonwear_markers(sample_nonwear_period: ManualNonwearPeriod) -> DailyNonwearMarkers:
    """Create sample daily nonwear markers with one period."""
    markers = DailyNonwearMarkers()
    markers.period_1 = sample_nonwear_period
    return markers


# ============================================================================
# TestSaveManualNonwearMarkers - Save Operations
# ============================================================================


class TestSaveManualNonwearMarkers:
    """Tests for save_manual_nonwear_markers method."""

    def test_saves_complete_periods(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """Saves complete nonwear periods to database."""
        repo = test_db.nonwear

        result = repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        assert result is True

        # Verify saved
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.MANUAL_NWT_MARKERS} WHERE filename = ?",
                (registered_file,),
            )
            count = cursor.fetchone()[0]
            assert count >= 1

    def test_replaces_existing_markers(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """Deletes existing markers before inserting new ones."""
        repo = test_db.nonwear

        # First save
        repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        # Second save (should replace)
        repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        # Should not have duplicates
        with sqlite3.connect(test_db.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {DatabaseTable.MANUAL_NWT_MARKERS} WHERE filename = ? AND sleep_date = ?",
                (registered_file, "2024-01-15"),
            )
            count = cursor.fetchone()[0]
            complete_periods = sample_daily_nonwear_markers.get_complete_periods()
            assert count == len(complete_periods)

    def test_validates_filename(self, test_db: DatabaseManager, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """ValidationError if filename is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.save_manual_nonwear_markers(
                filename="",
                participant_id="1001",
                sleep_date="2024-01-15",
                daily_nonwear_markers=sample_daily_nonwear_markers,
            )

    def test_validates_participant_id(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """ValidationError if participant_id is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.save_manual_nonwear_markers(
                filename=registered_file,
                participant_id="",
                sleep_date="2024-01-15",
                daily_nonwear_markers=sample_daily_nonwear_markers,
            )

    def test_raises_on_db_error(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """DatabaseError raised on database failure."""
        repo = test_db.nonwear

        original_path = repo.db_path
        repo.db_path = Path("/nonexistent/path/db.sqlite")

        with pytest.raises(DatabaseError):
            repo.save_manual_nonwear_markers(
                filename=registered_file,
                participant_id="1001",
                sleep_date="2024-01-15",
                daily_nonwear_markers=sample_daily_nonwear_markers,
            )

        repo.db_path = original_path


# ============================================================================
# TestLoadManualNonwearMarkers - Load Operations
# ============================================================================


class TestLoadManualNonwearMarkers:
    """Tests for load_manual_nonwear_markers method."""

    def test_loads_saved_markers(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """Returns saved nonwear markers."""
        repo = test_db.nonwear

        # Save first
        repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        # Load
        loaded = repo.load_manual_nonwear_markers(filename=registered_file, sleep_date="2024-01-15")

        assert isinstance(loaded, DailyNonwearMarkers)
        complete = loaded.get_complete_periods()
        assert len(complete) >= 1

    def test_returns_empty_markers_if_none(self, test_db: DatabaseManager, registered_file: str):
        """Returns empty DailyNonwearMarkers if no data."""
        repo = test_db.nonwear

        loaded = repo.load_manual_nonwear_markers(filename=registered_file, sleep_date="2024-01-15")

        assert isinstance(loaded, DailyNonwearMarkers)
        assert len(loaded.get_complete_periods()) == 0

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.load_manual_nonwear_markers(filename="", sleep_date="2024-01-15")

    def test_validates_sleep_date(self, test_db: DatabaseManager, registered_file: str):
        """ValidationError if sleep_date is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.load_manual_nonwear_markers(filename=registered_file, sleep_date="")


# ============================================================================
# TestDeleteManualNonwearMarkers - Delete Operations
# ============================================================================


class TestDeleteManualNonwearMarkers:
    """Tests for delete_manual_nonwear_markers method."""

    def test_deletes_markers_for_date(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """Deletes markers for specific file and date."""
        repo = test_db.nonwear

        # Save first
        repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        # Delete
        result = repo.delete_manual_nonwear_markers(filename=registered_file, sleep_date="2024-01-15")

        assert result is True

        # Verify deleted
        loaded = repo.load_manual_nonwear_markers(filename=registered_file, sleep_date="2024-01-15")
        assert len(loaded.get_complete_periods()) == 0

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.delete_manual_nonwear_markers(filename="", sleep_date="2024-01-15")

    def test_validates_sleep_date(self, test_db: DatabaseManager, registered_file: str):
        """ValidationError if sleep_date is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.delete_manual_nonwear_markers(filename=registered_file, sleep_date="")


# ============================================================================
# TestHasManualNonwearMarkers - Query Operations
# ============================================================================


class TestHasManualNonwearMarkers:
    """Tests for has_manual_nonwear_markers method."""

    def test_returns_true_if_exists(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """Returns True if markers exist."""
        repo = test_db.nonwear

        # Save markers
        repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        result = repo.has_manual_nonwear_markers(filename=registered_file, sleep_date="2024-01-15")

        assert result is True

    def test_returns_false_if_not_exists(self, test_db: DatabaseManager, registered_file: str):
        """Returns False if no markers exist."""
        repo = test_db.nonwear

        result = repo.has_manual_nonwear_markers(filename=registered_file, sleep_date="2024-01-15")

        assert result is False

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.nonwear

        with pytest.raises(ValidationError):
            repo.has_manual_nonwear_markers(filename="", sleep_date="2024-01-15")


# ============================================================================
# TestClearNwtData - Clear Operations
# ============================================================================


class TestClearNwtData:
    """Tests for clear_nwt_data method."""

    def test_clears_all_nonwear_data(self, test_db: DatabaseManager, registered_file: str, sample_daily_nonwear_markers: DailyNonwearMarkers):
        """Deletes all nonwear data from all tables."""
        repo = test_db.nonwear

        # Save some markers
        repo.save_manual_nonwear_markers(
            filename=registered_file,
            participant_id="1001",
            sleep_date="2024-01-15",
            daily_nonwear_markers=sample_daily_nonwear_markers,
        )

        deleted = repo.clear_nwt_data()

        assert deleted >= 1

    def test_returns_delete_count(self, test_db: DatabaseManager):
        """Returns total number of deleted rows."""
        repo = test_db.nonwear

        # No data to delete
        deleted = repo.clear_nwt_data()

        assert deleted == 0
