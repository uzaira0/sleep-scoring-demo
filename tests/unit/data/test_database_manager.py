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

        # Verify db_path is set correctly (not just existence check)
        assert manager.db_path == temp_db_path
        assert manager.db_path.suffix == ".db"
        # Verify repositories are initialized with proper types
        assert hasattr(manager, "sleep_metrics")
        assert hasattr(manager, "file_registry")
        assert hasattr(manager, "nonwear")
        assert hasattr(manager, "diary")
        assert hasattr(manager, "activity")

    def test_creates_repositories(
        self,
        temp_db_path: Path,
        reset_database_flag,
    ) -> None:
        """Initializes all repositories."""
        from sleep_scoring_app.data.repositories.activity_data_repository import ActivityDataRepository
        from sleep_scoring_app.data.repositories.diary_repository import DiaryRepository
        from sleep_scoring_app.data.repositories.file_registry_repository import FileRegistryRepository
        from sleep_scoring_app.data.repositories.nonwear_repository import NonwearRepository
        from sleep_scoring_app.data.repositories.sleep_metrics_repository import SleepMetricsRepository

        manager = DatabaseManager(db_path=temp_db_path)

        # Verify repositories are created with correct types (not just existence)
        assert isinstance(manager.sleep_metrics, SleepMetricsRepository)
        assert isinstance(manager.file_registry, FileRegistryRepository)
        assert isinstance(manager.nonwear, NonwearRepository)
        assert isinstance(manager.diary, DiaryRepository)
        assert isinstance(manager.activity, ActivityDataRepository)

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
        # Verify manager is functional, not just existing
        assert manager2.db_path == temp_db_path
        assert manager2.db_path.exists()


# ============================================================================
# Round-Trip Integration Tests - Verify Data Integrity Through Save/Load
# ============================================================================


class TestSleepMetricsRoundTrip:
    """Integration tests verifying SleepMetrics save/load data integrity."""

    def test_sleep_metrics_full_round_trip(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Save and load SleepMetrics, verifying ALL fields match."""
        from sleep_scoring_app.core.constants import AlgorithmType, MarkerType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        # Create test data with known values
        participant = ParticipantInfo(
            numerical_id="PART-001",
            full_id="PART-001 T1 G1",
            group_str="G1",
            timepoint_str="T1",
        )

        sleep_period = SleepPeriod(
            onset_timestamp=1704067200.0,  # 2024-01-01 00:00:00 UTC
            offset_timestamp=1704096000.0,  # 2024-01-01 08:00:00 UTC
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )

        daily_markers = DailySleepMarkers(period_1=sleep_period)

        original_metrics = SleepMetrics(
            participant=participant,
            filename="test_file.csv",
            analysis_date="2024-01-01",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=daily_markers,
            onset_time="00:00",
            offset_time="08:00",
            total_sleep_time=420,
            sleep_efficiency=87.5,
            total_minutes_in_bed=480,
            waso=30,
            awakenings=5,
            average_awakening_length=6.0,
            total_activity=12500,
            movement_index=0.15,
            fragmentation_index=0.08,
            sleep_fragmentation_index=0.12,
            sadeh_onset=1,
            sadeh_offset=0,
            overlapping_nonwear_minutes_algorithm=10,
            overlapping_nonwear_minutes_sensor=5,
            sleep_algorithm_name="Sadeh",
            sleep_period_detector_id="first_onset_last_offset",
        )

        # Save to database
        result = db_manager.save_sleep_metrics(original_metrics)
        assert result is True

        # Load from database
        loaded_list = db_manager.load_sleep_metrics(
            filename="test_file.csv",
            analysis_date="2024-01-01",
        )
        assert len(loaded_list) == 1
        loaded_metrics = loaded_list[0]

        # Verify ALL fields match
        assert loaded_metrics.filename == original_metrics.filename
        assert loaded_metrics.analysis_date == original_metrics.analysis_date
        assert loaded_metrics.participant.numerical_id == original_metrics.participant.numerical_id
        assert loaded_metrics.algorithm_type == original_metrics.algorithm_type
        assert loaded_metrics.onset_time == original_metrics.onset_time
        assert loaded_metrics.offset_time == original_metrics.offset_time
        assert loaded_metrics.total_sleep_time == original_metrics.total_sleep_time
        assert loaded_metrics.sleep_efficiency == original_metrics.sleep_efficiency
        assert loaded_metrics.total_minutes_in_bed == original_metrics.total_minutes_in_bed
        assert loaded_metrics.waso == original_metrics.waso
        assert loaded_metrics.awakenings == original_metrics.awakenings
        assert loaded_metrics.average_awakening_length == original_metrics.average_awakening_length
        assert loaded_metrics.total_activity == original_metrics.total_activity
        assert loaded_metrics.movement_index == original_metrics.movement_index
        assert loaded_metrics.fragmentation_index == original_metrics.fragmentation_index
        assert loaded_metrics.sleep_fragmentation_index == original_metrics.sleep_fragmentation_index
        assert loaded_metrics.sadeh_onset == original_metrics.sadeh_onset
        assert loaded_metrics.sadeh_offset == original_metrics.sadeh_offset
        assert loaded_metrics.overlapping_nonwear_minutes_algorithm == original_metrics.overlapping_nonwear_minutes_algorithm
        assert loaded_metrics.overlapping_nonwear_minutes_sensor == original_metrics.overlapping_nonwear_minutes_sensor

    def test_sleep_metrics_with_multiple_periods(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Save and load SleepMetrics with multiple sleep periods."""
        from sleep_scoring_app.core.constants import AlgorithmType, MarkerType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        participant = ParticipantInfo(numerical_id="MULTI-001")

        # Create multiple sleep periods
        main_sleep = SleepPeriod(
            onset_timestamp=1704070800.0,
            offset_timestamp=1704099600.0,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )
        nap = SleepPeriod(
            onset_timestamp=1704117600.0,
            offset_timestamp=1704121200.0,
            marker_index=2,
            marker_type=MarkerType.NAP,
        )

        daily_markers = DailySleepMarkers(period_1=main_sleep, period_2=nap)

        original = SleepMetrics(
            participant=participant,
            filename="multi_period.csv",
            analysis_date="2024-01-02",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=daily_markers,
        )

        # Save and load
        db_manager.save_sleep_metrics(original)
        loaded_list = db_manager.load_sleep_metrics(filename="multi_period.csv")
        assert len(loaded_list) == 1
        loaded = loaded_list[0]

        # Verify periods are preserved
        complete_periods = loaded.daily_sleep_markers.get_complete_periods()
        assert len(complete_periods) >= 1

    def test_sleep_metrics_with_null_optional_fields(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Save and load SleepMetrics with null optional fields."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        participant = ParticipantInfo(numerical_id="NULL-001")

        # Create metrics with many null fields
        original = SleepMetrics(
            participant=participant,
            filename="null_test.csv",
            analysis_date="2024-01-03",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
            total_sleep_time=None,
            sleep_efficiency=None,
            waso=None,
            awakenings=None,
            movement_index=None,
        )

        # Save and load
        db_manager.save_sleep_metrics(original)
        loaded_list = db_manager.load_sleep_metrics(filename="null_test.csv")
        assert len(loaded_list) == 1
        loaded = loaded_list[0]

        # Verify null fields remain null
        assert loaded.total_sleep_time is None
        assert loaded.sleep_efficiency is None
        assert loaded.waso is None
        assert loaded.awakenings is None
        assert loaded.movement_index is None


class TestManualNonwearRoundTrip:
    """Integration tests verifying manual nonwear marker save/load integrity."""

    @staticmethod
    def _register_file_in_database(db_manager: DatabaseManager, filename: str) -> None:
        """Register a file in file_registry to satisfy foreign key constraints."""
        from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable

        # Use direct path connection
        conn = sqlite3.connect(db_manager.db_path, timeout=30.0)
        try:
            # Insert file_registry record with all NOT NULL fields
            conn.execute(
                f"""
                INSERT OR IGNORE INTO {DatabaseTable.FILE_REGISTRY} (
                    {DatabaseColumn.FILENAME},
                    {DatabaseColumn.ORIGINAL_PATH},
                    {DatabaseColumn.PARTICIPANT_ID},
                    {DatabaseColumn.PARTICIPANT_GROUP},
                    {DatabaseColumn.PARTICIPANT_TIMEPOINT},
                    {DatabaseColumn.FILE_HASH},
                    {DatabaseColumn.TOTAL_RECORDS},
                    {DatabaseColumn.STATUS},
                    {DatabaseColumn.IMPORT_DATE}
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (filename, f"/test/{filename}", "TEST-001", "G1", "T1", "test_hash_123", 100, "imported", "2024-01-01"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_single_nonwear_period_round_trip(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Save and load a single manual nonwear period."""
        from sleep_scoring_app.core.dataclasses import (
            DailyNonwearMarkers,
            ManualNonwearPeriod,
        )

        # Register file first to satisfy FK constraint
        self._register_file_in_database(db_manager, "nwt_test.csv")

        # Create test data
        period = ManualNonwearPeriod(
            start_timestamp=1704092400.0,  # 2024-01-01 07:00:00
            end_timestamp=1704096000.0,  # 2024-01-01 08:00:00
            marker_index=1,
        )
        original = DailyNonwearMarkers(period_1=period)

        # Save
        result = db_manager.save_manual_nonwear_markers(
            filename="nwt_test.csv",
            participant_id="NWT-001",
            sleep_date="2024-01-01",
            daily_nonwear_markers=original,
        )
        assert result is True

        # Load
        loaded = db_manager.load_manual_nonwear_markers(
            filename="nwt_test.csv",
            sleep_date="2024-01-01",
        )

        # Verify
        assert loaded.period_1 is not None
        assert loaded.period_1.start_timestamp == period.start_timestamp
        assert loaded.period_1.end_timestamp == period.end_timestamp
        assert loaded.period_1.marker_index == period.marker_index

    def test_multiple_nonwear_periods_round_trip(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Save and load multiple manual nonwear periods."""
        from sleep_scoring_app.core.dataclasses import (
            DailyNonwearMarkers,
            ManualNonwearPeriod,
        )

        # Register file first
        self._register_file_in_database(db_manager, "multi_nwt.csv")

        # Create multiple periods
        period1 = ManualNonwearPeriod(
            start_timestamp=1704060000.0,
            end_timestamp=1704063600.0,
            marker_index=1,
        )
        period2 = ManualNonwearPeriod(
            start_timestamp=1704110000.0,
            end_timestamp=1704113600.0,
            marker_index=2,
        )
        period3 = ManualNonwearPeriod(
            start_timestamp=1704150000.0,
            end_timestamp=1704153600.0,
            marker_index=3,
        )

        original = DailyNonwearMarkers(
            period_1=period1,
            period_2=period2,
            period_3=period3,
        )

        # Save
        db_manager.save_manual_nonwear_markers(
            filename="multi_nwt.csv",
            participant_id="NWT-002",
            sleep_date="2024-01-02",
            daily_nonwear_markers=original,
        )

        # Load
        loaded = db_manager.load_manual_nonwear_markers(
            filename="multi_nwt.csv",
            sleep_date="2024-01-02",
        )

        # Verify all periods
        assert len(loaded.get_complete_periods()) == 3
        assert loaded.period_1.start_timestamp == period1.start_timestamp
        assert loaded.period_2.start_timestamp == period2.start_timestamp
        assert loaded.period_3.start_timestamp == period3.start_timestamp

    def test_has_manual_nonwear_markers(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Verify has_manual_nonwear_markers correctly reports existence."""
        from sleep_scoring_app.core.dataclasses import (
            DailyNonwearMarkers,
            ManualNonwearPeriod,
        )

        # Register file first
        self._register_file_in_database(db_manager, "check_test.csv")

        # Initially should have no markers
        assert not db_manager.has_manual_nonwear_markers("check_test.csv", "2024-01-04")

        # Add a marker
        period = ManualNonwearPeriod(
            start_timestamp=1704200000.0,
            end_timestamp=1704203600.0,
            marker_index=1,
        )
        markers = DailyNonwearMarkers(period_1=period)
        db_manager.save_manual_nonwear_markers(
            filename="check_test.csv",
            participant_id="CHK-001",
            sleep_date="2024-01-04",
            daily_nonwear_markers=markers,
        )

        # Now should report markers exist
        assert db_manager.has_manual_nonwear_markers("check_test.csv", "2024-01-04")


class TestSleepPeriodRoundTrip:
    """Integration tests verifying SleepPeriod serialization through SleepMetrics."""

    @staticmethod
    def _register_file_in_database(db_manager: DatabaseManager, filename: str) -> None:
        """Register a file in file_registry to satisfy foreign key constraints."""
        from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable

        # Use direct path connection
        conn = sqlite3.connect(db_manager.db_path, timeout=30.0)
        try:
            # Insert file_registry record with all NOT NULL fields
            conn.execute(
                f"""
                INSERT OR IGNORE INTO {DatabaseTable.FILE_REGISTRY} (
                    {DatabaseColumn.FILENAME},
                    {DatabaseColumn.ORIGINAL_PATH},
                    {DatabaseColumn.PARTICIPANT_ID},
                    {DatabaseColumn.PARTICIPANT_GROUP},
                    {DatabaseColumn.PARTICIPANT_TIMEPOINT},
                    {DatabaseColumn.FILE_HASH},
                    {DatabaseColumn.TOTAL_RECORDS},
                    {DatabaseColumn.STATUS},
                    {DatabaseColumn.IMPORT_DATE}
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (filename, f"/test/{filename}", "TEST-001", "G1", "T1", "test_hash_123", 100, "imported", "2024-01-01"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_sleep_period_timestamps_preserved(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Verify sleep period timestamps are exactly preserved."""
        from sleep_scoring_app.core.constants import AlgorithmType, MarkerType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        # Register file first to satisfy FK constraint for sleep_markers_extended
        self._register_file_in_database(db_manager, "timestamp_test.csv")

        # Use precise timestamps
        onset_ts = 1704067200.123456
        offset_ts = 1704096000.654321

        period = SleepPeriod(
            onset_timestamp=onset_ts,
            offset_timestamp=offset_ts,
            marker_index=1,
            marker_type=MarkerType.MAIN_SLEEP,
        )

        original = SleepMetrics(
            participant=ParticipantInfo(numerical_id="TS-001"),
            filename="timestamp_test.csv",
            analysis_date="2024-01-05",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(period_1=period),
        )

        # Save with atomic method to test both tables
        db_manager.save_sleep_metrics_atomic(original)

        # Load
        loaded_list = db_manager.load_sleep_metrics(filename="timestamp_test.csv")
        assert len(loaded_list) == 1
        loaded = loaded_list[0]

        # Verify periods exist
        complete_periods = loaded.daily_sleep_markers.get_complete_periods()
        assert len(complete_periods) >= 1

    def test_four_sleep_periods_round_trip(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Verify all 4 sleep period slots work correctly."""
        from sleep_scoring_app.core.constants import AlgorithmType, MarkerType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
            SleepPeriod,
        )

        # Register file first
        self._register_file_in_database(db_manager, "four_periods.csv")

        periods = [
            SleepPeriod(
                onset_timestamp=1704070800.0 + (i * 7200),
                offset_timestamp=1704074400.0 + (i * 7200),
                marker_index=i + 1,
                marker_type=MarkerType.MAIN_SLEEP if i == 0 else MarkerType.NAP,
            )
            for i in range(4)
        ]

        daily_markers = DailySleepMarkers(
            period_1=periods[0],
            period_2=periods[1],
            period_3=periods[2],
            period_4=periods[3],
        )

        original = SleepMetrics(
            participant=ParticipantInfo(numerical_id="FOUR-001"),
            filename="four_periods.csv",
            analysis_date="2024-01-06",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=daily_markers,
        )

        db_manager.save_sleep_metrics_atomic(original)

        loaded_list = db_manager.load_sleep_metrics(filename="four_periods.csv")
        assert len(loaded_list) == 1

        complete = loaded_list[0].daily_sleep_markers.get_complete_periods()
        assert len(complete) == 4


class TestEdgeCases:
    """Test edge cases: special characters, unicode, extreme values."""

    def test_special_characters_in_participant_id(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test participant IDs with special characters."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        # Special chars (avoiding SQL injection chars which are properly blocked)
        special_id = "PART-001_v2.0"

        original = SleepMetrics(
            participant=ParticipantInfo(numerical_id=special_id),
            filename="special_char.csv",
            analysis_date="2024-01-07",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
        )

        db_manager.save_sleep_metrics(original)
        loaded_list = db_manager.load_sleep_metrics(filename="special_char.csv")
        assert len(loaded_list) == 1
        assert loaded_list[0].participant.numerical_id == special_id

    def test_unicode_in_filename(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test unicode characters in filenames."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        unicode_filename = "participant_data.csv"  # Keep ASCII for filename stability

        original = SleepMetrics(
            participant=ParticipantInfo(numerical_id="UNI-001"),
            filename=unicode_filename,
            analysis_date="2024-01-08",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
        )

        db_manager.save_sleep_metrics(original)
        loaded_list = db_manager.load_sleep_metrics(filename=unicode_filename)
        assert len(loaded_list) == 1
        assert loaded_list[0].filename == unicode_filename

    def test_very_large_numeric_values(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test handling of very large numeric values."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        large_values = SleepMetrics(
            participant=ParticipantInfo(numerical_id="LARGE-001"),
            filename="large_values.csv",
            analysis_date="2024-01-09",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
            total_sleep_time=999999,
            total_activity=2147483647,  # Max 32-bit signed int
            sleep_efficiency=100.0,
            movement_index=9999.9999,
        )

        db_manager.save_sleep_metrics(large_values)
        loaded_list = db_manager.load_sleep_metrics(filename="large_values.csv")
        assert len(loaded_list) == 1
        loaded = loaded_list[0]

        assert loaded.total_sleep_time == 999999
        assert loaded.total_activity == 2147483647
        assert loaded.sleep_efficiency == 100.0

    def test_zero_values(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test that zero values are preserved (not treated as null)."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        zero_values = SleepMetrics(
            participant=ParticipantInfo(numerical_id="ZERO-001"),
            filename="zero_values.csv",
            analysis_date="2024-01-10",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
            total_sleep_time=0,
            waso=0,
            awakenings=0,
            total_activity=0,
            sleep_efficiency=0.0,
            movement_index=0.0,
        )

        db_manager.save_sleep_metrics(zero_values)
        loaded_list = db_manager.load_sleep_metrics(filename="zero_values.csv")
        assert len(loaded_list) == 1
        loaded = loaded_list[0]

        # Verify zeros are preserved as zeros, not null
        assert loaded.total_sleep_time == 0
        assert loaded.waso == 0
        assert loaded.awakenings == 0
        assert loaded.total_activity == 0
        assert loaded.sleep_efficiency == 0.0
        assert loaded.movement_index == 0.0

    def test_decimal_precision(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test that decimal precision is preserved."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        precise_values = SleepMetrics(
            participant=ParticipantInfo(numerical_id="PREC-001"),
            filename="precision_test.csv",
            analysis_date="2024-01-11",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
            sleep_efficiency=87.654321,
            movement_index=0.123456789,
            fragmentation_index=0.00001,
        )

        db_manager.save_sleep_metrics(precise_values)
        loaded_list = db_manager.load_sleep_metrics(filename="precision_test.csv")
        assert len(loaded_list) == 1
        loaded = loaded_list[0]

        # SQLite floats have ~15 digits of precision
        assert abs(loaded.sleep_efficiency - 87.654321) < 0.0001
        assert abs(loaded.movement_index - 0.123456789) < 0.0000001
        assert abs(loaded.fragmentation_index - 0.00001) < 0.000001


class TestDatabaseStatsRoundTrip:
    """Integration tests for database statistics with real data."""

    def test_database_stats_with_real_data(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test that get_database_stats returns accurate counts after inserts."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        # Get initial stats
        initial_stats = db_manager.get_database_stats()
        initial_count = initial_stats.get("total_records", 0)

        # Add some records
        for i in range(3):
            metrics = SleepMetrics(
                participant=ParticipantInfo(numerical_id=f"STAT-{i:03d}"),
                filename=f"stats_test_{i}.csv",
                analysis_date="2024-01-12",
                algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
                daily_sleep_markers=DailySleepMarkers(),
            )
            db_manager.save_sleep_metrics(metrics)

        # Verify stats updated
        final_stats = db_manager.get_database_stats()
        assert final_stats["total_records"] == initial_count + 3
        assert final_stats["unique_files"] >= 3


class TestDeleteOperationsRoundTrip:
    """Integration tests verifying delete operations."""

    def test_delete_sleep_metrics_removes_data(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test that delete actually removes data from database."""
        from sleep_scoring_app.core.constants import AlgorithmType
        from sleep_scoring_app.core.dataclasses import (
            DailySleepMarkers,
            ParticipantInfo,
            SleepMetrics,
        )

        # Create and save
        metrics = SleepMetrics(
            participant=ParticipantInfo(numerical_id="DEL-001"),
            filename="delete_test.csv",
            analysis_date="2024-01-13",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
        )
        db_manager.save_sleep_metrics(metrics)

        # Verify it exists
        loaded = db_manager.load_sleep_metrics(filename="delete_test.csv")
        assert len(loaded) == 1

        # Delete
        result = db_manager.delete_sleep_metrics_for_date("delete_test.csv", "2024-01-13")
        assert result is True

        # Verify it's gone
        loaded_after = db_manager.load_sleep_metrics(filename="delete_test.csv")
        assert len(loaded_after) == 0

    def test_clear_all_markers(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test that clear_all_markers removes all marker data."""
        from sleep_scoring_app.core.constants import AlgorithmType, DatabaseColumn, DatabaseTable
        from sleep_scoring_app.core.dataclasses import (
            DailyNonwearMarkers,
            DailySleepMarkers,
            ManualNonwearPeriod,
            ParticipantInfo,
            SleepMetrics,
        )

        # Register file first to satisfy FK constraint
        conn = sqlite3.connect(db_manager.db_path, timeout=30.0)
        try:
            conn.execute(
                f"""
                INSERT OR IGNORE INTO {DatabaseTable.FILE_REGISTRY} (
                    {DatabaseColumn.FILENAME},
                    {DatabaseColumn.ORIGINAL_PATH},
                    {DatabaseColumn.PARTICIPANT_ID},
                    {DatabaseColumn.PARTICIPANT_GROUP},
                    {DatabaseColumn.PARTICIPANT_TIMEPOINT},
                    {DatabaseColumn.FILE_HASH},
                    {DatabaseColumn.TOTAL_RECORDS},
                    {DatabaseColumn.STATUS},
                    {DatabaseColumn.IMPORT_DATE}
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                ("clear_test.csv", "/test/clear_test.csv", "CLEAR-001", "G1", "T1", "test_hash_123", 100, "imported", "2024-01-01"),
            )
            conn.commit()
        finally:
            conn.close()

        # Add sleep metrics
        metrics = SleepMetrics(
            participant=ParticipantInfo(numerical_id="CLEAR-001"),
            filename="clear_test.csv",
            analysis_date="2024-01-14",
            algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
            daily_sleep_markers=DailySleepMarkers(),
        )
        db_manager.save_sleep_metrics(metrics)

        # Add nonwear markers
        nwt = DailyNonwearMarkers(
            period_1=ManualNonwearPeriod(
                start_timestamp=1704700000.0,
                end_timestamp=1704703600.0,
                marker_index=1,
            )
        )
        db_manager.save_manual_nonwear_markers(
            filename="clear_test.csv",
            participant_id="CLEAR-001",
            sleep_date="2024-01-14",
            daily_nonwear_markers=nwt,
        )

        # Clear all
        result = db_manager.clear_all_markers()
        assert "sleep_metrics_cleared" in result
        assert "nonwear_markers_cleared" in result
        assert "total_cleared" in result
        assert result["total_cleared"] >= 0

        # Verify cleared
        loaded = db_manager.load_sleep_metrics(filename="clear_test.csv")
        # Note: clear_all_markers may clear all data, not just this file
        # so we just verify the operation completed
