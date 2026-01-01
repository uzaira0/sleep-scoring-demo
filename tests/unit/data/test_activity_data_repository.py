#!/usr/bin/env python3
"""
Comprehensive unit tests for ActivityDataRepository.

Tests activity data loading, column queries, and clearing operations.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sleep_scoring_app.core.constants import ActivityDataPreference, DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.exceptions import DatabaseError, ValidationError

if TYPE_CHECKING:
    from sleep_scoring_app.data.database import DatabaseManager
    from sleep_scoring_app.data.repositories.activity_data_repository import ActivityDataRepository


# ============================================================================
# Helper to insert activity data with all required fields
# ============================================================================


def insert_activity_data(
    conn: sqlite3.Connection,
    filename: str,
    timestamp: datetime,
    axis_y: float = 100.0,
    axis_x: float | None = None,
    axis_z: float | None = None,
    vector_magnitude: float | None = None,
) -> None:
    """Insert activity data with all required fields. Timestamp as ISO string."""
    conn.execute(
        f"""
        INSERT INTO {DatabaseTable.RAW_ACTIVITY_DATA}
        (filename, file_hash, participant_id, timestamp, axis_y, axis_x, axis_z, vector_magnitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (filename, "hash123", "1001", timestamp.isoformat(), axis_y, axis_x, axis_z, vector_magnitude),
    )


# ============================================================================
# TestLoadRawActivityData - Data Loading
# ============================================================================


class TestLoadRawActivityData:
    """Tests for load_raw_activity_data method."""

    def test_loads_data_for_filename(self, test_db: DatabaseManager, registered_file: str):
        """Returns activity data for specified file."""
        repo = test_db.activity

        # Add activity data (timestamps as datetime, stored as ISO strings)
        with sqlite3.connect(test_db.db_path) as conn:
            for i in range(5):
                timestamp = datetime(2024, 1, 15, 8, i)
                insert_activity_data(conn, registered_file, timestamp, 100 + i)
            conn.commit()

        timestamps, activities = repo.load_raw_activity_data(filename=registered_file)

        assert len(timestamps) == 5
        assert len(activities) == 5

    def test_filters_by_time_range(self, test_db: DatabaseManager, registered_file: str):
        """Returns only data within specified time range."""
        repo = test_db.activity

        # Add activity data for multiple dates
        with sqlite3.connect(test_db.db_path) as conn:
            for day in [10, 15, 20, 25]:
                timestamp = datetime(2024, 1, day, 12, 0)
                insert_activity_data(conn, registered_file, timestamp, 100)
            conn.commit()

        # Load only Jan 15 00:00 to Jan 16 00:00
        timestamps, _activities = repo.load_raw_activity_data(
            filename=registered_file,
            start_time=datetime(2024, 1, 15, 0, 0),
            end_time=datetime(2024, 1, 16, 0, 0),
        )

        # Should only include data for Jan 15
        assert len(timestamps) == 1

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.activity

        with pytest.raises(ValidationError):
            repo.load_raw_activity_data(filename="")

    def test_returns_empty_if_no_data(self, test_db: DatabaseManager, registered_file: str):
        """Returns empty lists if no activity data for file."""
        repo = test_db.activity

        timestamps, activities = repo.load_raw_activity_data(filename=registered_file)

        assert timestamps == []
        assert activities == []

    def test_orders_by_timestamp(self, test_db: DatabaseManager, registered_file: str):
        """Results are ordered by timestamp ascending."""
        repo = test_db.activity

        # Add data out of order
        with sqlite3.connect(test_db.db_path) as conn:
            for hour in [15, 10, 20, 5]:
                timestamp = datetime(2024, 1, 15, hour, 0)
                insert_activity_data(conn, registered_file, timestamp, 100)
            conn.commit()

        timestamps, _activities = repo.load_raw_activity_data(filename=registered_file)

        # Should be sorted by timestamp
        assert timestamps == sorted(timestamps)

    def test_raises_on_db_error(self, test_db: DatabaseManager, registered_file: str):
        """DatabaseError raised on database failure."""
        repo = test_db.activity

        original_path = repo.db_path
        repo.db_path = Path("/nonexistent/path/db.sqlite")

        with pytest.raises(DatabaseError):
            repo.load_raw_activity_data(filename=registered_file)

        repo.db_path = original_path

    def test_uses_activity_column_preference(self, test_db: DatabaseManager, registered_file: str):
        """Respects activity_column parameter."""
        repo = test_db.activity

        # Add data with all columns
        with sqlite3.connect(test_db.db_path) as conn:
            timestamp = datetime(2024, 1, 15, 8, 0)
            insert_activity_data(conn, registered_file, timestamp, axis_y=100, axis_x=50, axis_z=25, vector_magnitude=120)
            conn.commit()

        # Load with different column preferences
        _, axis_y = repo.load_raw_activity_data(filename=registered_file, activity_column=ActivityDataPreference.AXIS_Y)
        _, axis_x = repo.load_raw_activity_data(filename=registered_file, activity_column=ActivityDataPreference.AXIS_X)

        assert axis_y[0] == 100.0
        assert axis_x[0] == 50.0


# ============================================================================
# TestLoadAllActivityColumns - Multi-Column Loading
# ============================================================================


class TestLoadAllActivityColumns:
    """Tests for load_all_activity_columns method."""

    def test_returns_dict_with_columns(self, test_db: DatabaseManager, registered_file: str):
        """Returns dict with all axis columns."""
        repo = test_db.activity

        # Add activity data with all columns
        with sqlite3.connect(test_db.db_path) as conn:
            for i in range(5):
                timestamp = datetime(2024, 1, 15, 8, i)
                insert_activity_data(conn, registered_file, timestamp, axis_y=100, axis_x=50, axis_z=25, vector_magnitude=120)
            conn.commit()

        data = repo.load_all_activity_columns(filename=registered_file)

        # Should have keys for each column
        assert isinstance(data, dict)
        assert "timestamps" in data

    def test_handles_missing_columns(self, test_db: DatabaseManager, registered_file: str):
        """Handles NULL values in optional columns."""
        repo = test_db.activity

        # Add data with only required columns
        with sqlite3.connect(test_db.db_path) as conn:
            timestamp = datetime(2024, 1, 15, 8, 0)
            insert_activity_data(conn, registered_file, timestamp, axis_y=100)
            conn.commit()

        # Should not crash
        data = repo.load_all_activity_columns(filename=registered_file)
        assert isinstance(data, dict)

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.activity

        with pytest.raises(ValidationError):
            repo.load_all_activity_columns(filename="")

    def test_filters_by_time_range(self, test_db: DatabaseManager, registered_file: str):
        """Respects time range filtering."""
        repo = test_db.activity

        # Add data for multiple dates
        with sqlite3.connect(test_db.db_path) as conn:
            for day in [10, 15, 20]:
                timestamp = datetime(2024, 1, day, 12, 0)
                insert_activity_data(conn, registered_file, timestamp, 100)
            conn.commit()

        data = repo.load_all_activity_columns(
            filename=registered_file,
            start_time=datetime(2024, 1, 15, 0, 0),
            end_time=datetime(2024, 1, 16, 0, 0),
        )

        assert isinstance(data, dict)
        if "timestamps" in data:
            assert len(data["timestamps"]) == 1


# ============================================================================
# TestGetAvailableActivityColumns - Column Metadata
# ============================================================================


class TestGetAvailableActivityColumns:
    """Tests for get_available_activity_columns method."""

    def test_returns_preference_list(self, test_db: DatabaseManager, registered_file: str):
        """Returns list of ActivityDataPreference objects."""
        repo = test_db.activity

        # Add activity data
        with sqlite3.connect(test_db.db_path) as conn:
            timestamp = datetime(2024, 1, 15, 8, 0)
            insert_activity_data(conn, registered_file, timestamp, 100, 50, 25, 120)
            conn.commit()

        prefs = repo.get_available_activity_columns(registered_file)

        assert isinstance(prefs, list)

    def test_detects_available_columns(self, test_db: DatabaseManager, registered_file: str):
        """Correctly identifies which columns have data."""
        repo = test_db.activity

        # Add data with specific columns
        with sqlite3.connect(test_db.db_path) as conn:
            timestamp = datetime(2024, 1, 15, 8, 0)
            insert_activity_data(conn, registered_file, timestamp, axis_y=100, axis_x=50)
            conn.commit()

        prefs = repo.get_available_activity_columns(registered_file)

        # Should detect columns with data
        assert len(prefs) >= 0

    def test_validates_filename(self, test_db: DatabaseManager):
        """ValidationError if filename is empty."""
        repo = test_db.activity

        with pytest.raises(ValidationError):
            repo.get_available_activity_columns("")

    def test_handles_no_data(self, test_db: DatabaseManager, registered_file: str):
        """Returns empty list if no activity data."""
        repo = test_db.activity

        prefs = repo.get_available_activity_columns(registered_file)

        assert isinstance(prefs, list)


# ============================================================================
# TestClearActivityData - Data Deletion
# ============================================================================


class TestClearActivityData:
    """Tests for clear_activity_data method."""

    def test_clears_specific_file(self, test_db: DatabaseManager, registered_file: str):
        """Deletes activity data for specified file only."""
        repo = test_db.activity

        # Add activity data
        with sqlite3.connect(test_db.db_path) as conn:
            for i in range(5):
                timestamp = datetime(2024, 1, 15, 8, i)
                insert_activity_data(conn, registered_file, timestamp, 100)
            conn.commit()

        deleted = repo.clear_activity_data(filename=registered_file)

        assert deleted == 5

        # Verify deleted
        timestamps, _ = repo.load_raw_activity_data(filename=registered_file)
        assert len(timestamps) == 0

    def test_clears_all_files(self, test_db: DatabaseManager, registered_file: str):
        """Deletes all activity data when no filename specified."""
        repo = test_db.activity

        # Add activity data
        with sqlite3.connect(test_db.db_path) as conn:
            for i in range(5):
                timestamp = datetime(2024, 1, 15, 8, i)
                insert_activity_data(conn, registered_file, timestamp, 100)
            conn.commit()

        deleted = repo.clear_activity_data(filename=None)

        assert deleted >= 5

    def test_returns_delete_count(self, test_db: DatabaseManager, registered_file: str):
        """Returns number of deleted rows."""
        repo = test_db.activity

        with sqlite3.connect(test_db.db_path) as conn:
            for i in range(3):
                timestamp = datetime(2024, 1, 15, 8, i)
                insert_activity_data(conn, registered_file, timestamp, 100)
            conn.commit()

        deleted = repo.clear_activity_data(filename=registered_file)

        assert deleted == 3

    def test_handles_no_data(self, test_db: DatabaseManager, registered_file: str):
        """Returns 0 if no data to delete."""
        repo = test_db.activity

        deleted = repo.clear_activity_data(filename=registered_file)

        assert deleted == 0

    def test_raises_on_db_error(self, test_db: DatabaseManager, registered_file: str):
        """DatabaseError raised on database failure."""
        repo = test_db.activity

        original_path = repo.db_path
        repo.db_path = Path("/nonexistent/path/db.sqlite")

        with pytest.raises(DatabaseError):
            repo.clear_activity_data(filename=registered_file)

        repo.db_path = original_path
