"""
Tests for DatabaseManager class.

Tests initialization, validation, and facade pattern delegation.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from sleep_scoring_app.core.constants import (
    ActivityDataPreference,
    DatabaseColumn,
    DatabaseTable,
)
from sleep_scoring_app.core.exceptions import DatabaseError, ValidationError
from sleep_scoring_app.data.database import DatabaseManager, _database_initialized

if TYPE_CHECKING:
    from datetime import date


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path() -> Path:
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def reset_database_flag():
    """Reset global database initialized flag before each test."""
    import sleep_scoring_app.data.database as db_module

    original = db_module._database_initialized
    db_module._database_initialized = False
    yield
    db_module._database_initialized = original


@pytest.fixture
def db_manager(temp_db_path: Path, reset_database_flag) -> DatabaseManager:
    """Create a DatabaseManager instance with temp database."""
    return DatabaseManager(db_path=temp_db_path)


# ============================================================================
# Test Initialization
# ============================================================================


class TestDatabaseManagerInit:
    """Tests for DatabaseManager initialization."""

    def test_creates_instance_with_path(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Creates manager instance with provided path."""
        manager = DatabaseManager(db_path=temp_db_path)

        assert manager is not None
        assert manager.db_path == temp_db_path

    def test_creates_repositories(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Initializes all repositories."""
        manager = DatabaseManager(db_path=temp_db_path)

        assert manager.sleep_metrics is not None
        assert manager.file_registry is not None
        assert manager.nonwear is not None
        assert manager.diary is not None
        assert manager.activity is not None

    def test_creates_database_file(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Creates database file on initialization."""
        # Delete the temp file first
        temp_db_path.unlink()
        assert not temp_db_path.exists()

        manager = DatabaseManager(db_path=temp_db_path)

        # Database should be created
        assert temp_db_path.exists()

    def test_initializes_schema(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Initializes database schema on first run."""
        manager = DatabaseManager(db_path=temp_db_path)

        # Check that tables were created
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert len(tables) > 0

    def test_registers_with_resource_manager(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Registers with resource manager when provided."""
        mock_resource_manager = MagicMock()

        manager = DatabaseManager(
            db_path=temp_db_path,
            resource_manager=mock_resource_manager,
        )

        mock_resource_manager.register_resource.assert_called_once()


# ============================================================================
# Test Validation Methods
# ============================================================================


class TestDatabaseManagerValidation:
    """Tests for validation methods."""

    def test_validate_valid_table_name(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Validates valid table names."""
        result = db_manager._validate_table_name(DatabaseTable.SLEEP_METRICS)

        assert result == DatabaseTable.SLEEP_METRICS

    def test_validate_invalid_table_name_raises(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Raises ValidationError for invalid table names."""
        with pytest.raises(ValidationError) as exc_info:
            db_manager._validate_table_name("invalid_table; DROP TABLE users;")

        assert "Invalid table name" in str(exc_info.value)

    def test_validate_valid_column_name(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Validates valid column names."""
        result = db_manager._validate_column_name(DatabaseColumn.FILENAME)

        assert result == DatabaseColumn.FILENAME

    def test_validate_invalid_column_name_raises(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Raises ValidationError for invalid column names."""
        with pytest.raises(ValidationError) as exc_info:
            db_manager._validate_column_name("invalid_col; DROP TABLE users;")

        assert "Invalid column name" in str(exc_info.value)

    def test_sql_injection_prevention_table(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Prevents SQL injection in table names."""
        injection_attempts = [
            "users; DROP TABLE sleep_metrics;",
            "users' OR '1'='1",
            "users--",
            "users/**/",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValidationError):
                db_manager._validate_table_name(attempt)

    def test_sql_injection_prevention_column(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Prevents SQL injection in column names."""
        injection_attempts = [
            "id; DROP TABLE sleep_metrics;",
            "id' OR '1'='1",
            "id--",
            "id/**/",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValidationError):
                db_manager._validate_column_name(attempt)

    def test_valid_tables_constant(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """VALID_TABLES contains all DatabaseTable values."""
        expected_tables = {
            DatabaseTable.SLEEP_METRICS,
            DatabaseTable.RAW_ACTIVITY_DATA,
            DatabaseTable.FILE_REGISTRY,
            DatabaseTable.NONWEAR_SENSOR_PERIODS,
            DatabaseTable.CHOI_ALGORITHM_PERIODS,
            DatabaseTable.DIARY_DATA,
            DatabaseTable.DIARY_FILE_REGISTRY,
            DatabaseTable.DIARY_RAW_DATA,
            DatabaseTable.DIARY_NAP_PERIODS,
            DatabaseTable.DIARY_NONWEAR_PERIODS,
            DatabaseTable.SLEEP_MARKERS_EXTENDED,
            DatabaseTable.MANUAL_NWT_MARKERS,
        }

        assert expected_tables.issubset(DatabaseManager.VALID_TABLES)


# ============================================================================
# Test Facade Methods - Sleep Metrics
# ============================================================================


class TestDatabaseManagerSleepMetricsFacade:
    """Tests for sleep metrics facade methods."""

    def test_save_sleep_metrics_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """save_sleep_metrics delegates to repository."""
        mock_metrics = MagicMock()
        db_manager.sleep_metrics.save_sleep_metrics = MagicMock(return_value=True)

        result = db_manager.save_sleep_metrics(mock_metrics)

        db_manager.sleep_metrics.save_sleep_metrics.assert_called_once_with(mock_metrics)
        assert result is True

    def test_load_sleep_metrics_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """load_sleep_metrics delegates to repository."""
        db_manager.sleep_metrics.load_sleep_metrics = MagicMock(return_value=[])

        result = db_manager.load_sleep_metrics(filename="test.csv")

        db_manager.sleep_metrics.load_sleep_metrics.assert_called_once_with("test.csv", None)
        assert result == []

    def test_delete_sleep_metrics_for_date_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """delete_sleep_metrics_for_date delegates to repository."""
        db_manager.sleep_metrics.delete_sleep_metrics_for_date = MagicMock(return_value=True)

        result = db_manager.delete_sleep_metrics_for_date("test.csv", "2024-01-01")

        db_manager.sleep_metrics.delete_sleep_metrics_for_date.assert_called_once_with("test.csv", "2024-01-01")
        assert result is True

    def test_get_database_stats_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """get_database_stats delegates to repository."""
        expected_stats = {"total_records": 100}
        db_manager.sleep_metrics.get_database_stats = MagicMock(return_value=expected_stats)

        result = db_manager.get_database_stats()

        db_manager.sleep_metrics.get_database_stats.assert_called_once()
        assert result == expected_stats


# ============================================================================
# Test Facade Methods - File Registry
# ============================================================================


class TestDatabaseManagerFileRegistryFacade:
    """Tests for file registry facade methods."""

    def test_get_available_files_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """get_available_files delegates to repository."""
        expected_files = [{"filename": "test.csv"}]
        db_manager.file_registry.get_available_files = MagicMock(return_value=expected_files)

        result = db_manager.get_available_files()

        db_manager.file_registry.get_available_files.assert_called_once()
        assert result == expected_files

    def test_get_file_date_ranges_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """get_file_date_ranges delegates to repository."""
        db_manager.file_registry.get_file_date_ranges = MagicMock(return_value=[])

        result = db_manager.get_file_date_ranges("test.csv")

        db_manager.file_registry.get_file_date_ranges.assert_called_once_with("test.csv")
        assert result == []

    def test_delete_imported_file_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """delete_imported_file delegates to repository."""
        db_manager.file_registry.delete_imported_file = MagicMock(return_value=True)

        result = db_manager.delete_imported_file("test.csv")

        db_manager.file_registry.delete_imported_file.assert_called_once_with("test.csv")
        assert result is True


# ============================================================================
# Test Facade Methods - Activity Data
# ============================================================================


class TestDatabaseManagerActivityFacade:
    """Tests for activity data facade methods."""

    def test_load_raw_activity_data_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """load_raw_activity_data delegates to repository."""
        expected = ([], [])
        db_manager.activity.load_raw_activity_data = MagicMock(return_value=expected)

        result = db_manager.load_raw_activity_data(
            "test.csv",
            activity_column=ActivityDataPreference.VECTOR_MAGNITUDE,
        )

        db_manager.activity.load_raw_activity_data.assert_called_once_with("test.csv", None, None, ActivityDataPreference.VECTOR_MAGNITUDE)
        assert result == expected

    def test_load_all_activity_columns_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """load_all_activity_columns delegates to repository."""
        expected = {"timestamps": [], "axis_y": []}
        db_manager.activity.load_all_activity_columns = MagicMock(return_value=expected)

        result = db_manager.load_all_activity_columns("test.csv")

        db_manager.activity.load_all_activity_columns.assert_called_once_with("test.csv", None, None)
        assert result == expected

    def test_get_available_activity_columns_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """get_available_activity_columns delegates to repository."""
        expected = [ActivityDataPreference.AXIS_Y]
        db_manager.activity.get_available_activity_columns = MagicMock(return_value=expected)

        result = db_manager.get_available_activity_columns("test.csv")

        db_manager.activity.get_available_activity_columns.assert_called_once_with("test.csv")
        assert result == expected

    def test_clear_activity_data_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """clear_activity_data delegates to repository."""
        db_manager.activity.clear_activity_data = MagicMock(return_value=100)

        result = db_manager.clear_activity_data("test.csv")

        db_manager.activity.clear_activity_data.assert_called_once_with("test.csv")
        assert result == 100


# ============================================================================
# Test Facade Methods - Nonwear
# ============================================================================


class TestDatabaseManagerNonwearFacade:
    """Tests for nonwear facade methods."""

    def test_save_manual_nonwear_markers_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """save_manual_nonwear_markers delegates to repository."""
        mock_markers = MagicMock()
        db_manager.nonwear.save_manual_nonwear_markers = MagicMock(return_value=True)

        result = db_manager.save_manual_nonwear_markers("test.csv", "PART-001", "2024-01-01", mock_markers)

        db_manager.nonwear.save_manual_nonwear_markers.assert_called_once_with("test.csv", "PART-001", "2024-01-01", mock_markers)
        assert result is True

    def test_load_manual_nonwear_markers_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """load_manual_nonwear_markers delegates to repository."""
        mock_markers = MagicMock()
        db_manager.nonwear.load_manual_nonwear_markers = MagicMock(return_value=mock_markers)

        result = db_manager.load_manual_nonwear_markers("test.csv", "2024-01-01")

        db_manager.nonwear.load_manual_nonwear_markers.assert_called_once_with("test.csv", "2024-01-01")
        assert result == mock_markers

    def test_has_manual_nonwear_markers_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """has_manual_nonwear_markers delegates to repository."""
        db_manager.nonwear.has_manual_nonwear_markers = MagicMock(return_value=True)

        result = db_manager.has_manual_nonwear_markers("test.csv", "2024-01-01")

        db_manager.nonwear.has_manual_nonwear_markers.assert_called_once_with("test.csv", "2024-01-01")
        assert result is True

    def test_clear_nwt_data_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """clear_nwt_data delegates to repository."""
        db_manager.nonwear.clear_nwt_data = MagicMock(return_value=50)

        result = db_manager.clear_nwt_data()

        db_manager.nonwear.clear_nwt_data.assert_called_once()
        assert result == 50


# ============================================================================
# Test Facade Methods - Diary
# ============================================================================


class TestDatabaseManagerDiaryFacade:
    """Tests for diary facade methods."""

    def test_save_diary_nap_periods_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """save_diary_nap_periods delegates to repository."""
        nap_periods = [{"start": "14:00", "end": "15:00"}]
        db_manager.diary.save_diary_nap_periods = MagicMock(return_value=True)

        result = db_manager.save_diary_nap_periods("test.csv", "PART-001", "2024-01-01", nap_periods)

        db_manager.diary.save_diary_nap_periods.assert_called_once_with("test.csv", "PART-001", "2024-01-01", nap_periods)
        assert result is True

    def test_load_diary_nap_periods_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """load_diary_nap_periods delegates to repository."""
        expected = [{"start": "14:00", "end": "15:00"}]
        db_manager.diary.load_diary_nap_periods = MagicMock(return_value=expected)

        result = db_manager.load_diary_nap_periods("test.csv", "2024-01-01")

        db_manager.diary.load_diary_nap_periods.assert_called_once_with("test.csv", "2024-01-01")
        assert result == expected

    def test_save_diary_nonwear_periods_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """save_diary_nonwear_periods delegates to repository."""
        nonwear_periods = [{"start": "10:00", "end": "11:00"}]
        db_manager.diary.save_diary_nonwear_periods = MagicMock(return_value=True)

        result = db_manager.save_diary_nonwear_periods("test.csv", "PART-001", "2024-01-01", nonwear_periods)

        db_manager.diary.save_diary_nonwear_periods.assert_called_once_with("test.csv", "PART-001", "2024-01-01", nonwear_periods)
        assert result is True

    def test_clear_diary_data_delegates(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """clear_diary_data delegates to repository."""
        db_manager.diary.clear_diary_data = MagicMock(return_value=25)

        result = db_manager.clear_diary_data()

        db_manager.diary.clear_diary_data.assert_called_once()
        assert result == 25


# ============================================================================
# Test Clear All Markers
# ============================================================================


class TestDatabaseManagerClearAllMarkers:
    """Tests for clear_all_markers method."""

    def test_clears_sleep_metrics(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Clears sleep metrics table."""
        result = db_manager.clear_all_markers()

        assert "sleep_metrics_cleared" in result
        assert "nonwear_markers_cleared" in result
        assert "total_cleared" in result

    def test_returns_cleared_counts(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Returns dictionary with cleared counts."""
        result = db_manager.clear_all_markers()

        assert isinstance(result, dict)
        assert result["sleep_metrics_cleared"] >= 0
        assert result["nonwear_markers_cleared"] >= 0
        assert result["total_cleared"] == (result["sleep_metrics_cleared"] + result["nonwear_markers_cleared"])


# ============================================================================
# Test Update Valid Columns
# ============================================================================


class TestDatabaseManagerUpdateValidColumns:
    """Tests for _update_valid_columns method."""

    def test_includes_base_columns(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Includes base columns from VALID_COLUMNS."""
        assert DatabaseColumn.FILENAME in db_manager._valid_columns
        assert DatabaseColumn.ID in db_manager._valid_columns
        assert DatabaseColumn.TIMESTAMP in db_manager._valid_columns

    def test_includes_registry_columns(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Includes columns from column registry."""
        # Should have at least the base columns
        assert len(db_manager._valid_columns) >= len(DatabaseManager.VALID_COLUMNS)


# ============================================================================
# Test Global Initialization Flag
# ============================================================================


class TestDatabaseInitializationFlag:
    """Tests for global database initialization flag."""

    def test_flag_set_after_init(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Global flag set after successful initialization."""
        import sleep_scoring_app.data.database as db_module

        assert db_module._database_initialized is False

        DatabaseManager(db_path=temp_db_path)

        assert db_module._database_initialized is True

    def test_second_init_skips_schema(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Second initialization skips schema creation."""
        import sleep_scoring_app.data.database as db_module

        # First init
        DatabaseManager(db_path=temp_db_path)
        assert db_module._database_initialized is True

        # Second init should not fail (schema already exists)
        manager2 = DatabaseManager(db_path=temp_db_path)
        assert manager2 is not None
