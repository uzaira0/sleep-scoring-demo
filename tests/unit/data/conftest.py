#!/usr/bin/env python3
"""
Shared fixtures for data layer tests.

Provides test database setup, sample data factories,
and repository instances for testing.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from sleep_scoring_app.core.constants import AlgorithmType, DatabaseColumn, DatabaseTable, MarkerType
from sleep_scoring_app.core.dataclasses import (
    DailySleepMarkers,
    ParticipantInfo,
    SleepMetrics,
    SleepPeriod,
)
from sleep_scoring_app.core.dataclasses_markers import DailyNonwearMarkers, ManualNonwearPeriod
from sleep_scoring_app.data.database import DatabaseManager

if TYPE_CHECKING:
    from sleep_scoring_app.data.repositories.base_repository import BaseRepository


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_sleep_scoring.db"


@pytest.fixture
def test_db(test_db_path: Path) -> DatabaseManager:
    """
    Create a real DatabaseManager with a temp database.

    This creates actual tables and provides a real database for integration-style tests.
    """
    # Reset the module-level initialization flag to force table creation for each test
    import sleep_scoring_app.data.database as db_module

    db_module._database_initialized = False

    db = DatabaseManager(db_path=test_db_path)
    yield db

    # Reset flag after test for isolation
    db_module._database_initialized = False


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock DatabaseManager for unit tests requiring isolation."""
    mock = MagicMock(spec=DatabaseManager)
    mock.db_path = Path("/tmp/mock.db")
    return mock


# ============================================================================
# REPOSITORY FIXTURES
# ============================================================================


@pytest.fixture
def base_repository(test_db: DatabaseManager):
    """
    Create a BaseRepository instance for testing.

    Note: BaseRepository is typically not used directly,
    but we test it through a concrete implementation.
    """
    from sleep_scoring_app.data.repositories.base_repository import BaseRepository

    return BaseRepository(
        db_path=test_db.db_path,
        validate_table_name=test_db._validate_table_name,
        validate_column_name=test_db._validate_column_name,
    )


@pytest.fixture
def sleep_metrics_repository(test_db: DatabaseManager):
    """Create SleepMetricsRepository with test database."""
    return test_db.sleep_metrics


@pytest.fixture
def file_registry_repository(test_db: DatabaseManager):
    """Create FileRegistryRepository with test database."""
    return test_db.file_registry


@pytest.fixture
def activity_data_repository(test_db: DatabaseManager):
    """Create ActivityDataRepository with test database."""
    return test_db.activity


@pytest.fixture
def nonwear_repository(test_db: DatabaseManager):
    """Create NonwearRepository with test database."""
    return test_db.nonwear


@pytest.fixture
def diary_repository(test_db: DatabaseManager):
    """Create DiaryRepository with test database."""
    return test_db.diary


# ============================================================================
# DATA FACTORIES - Participant Info
# ============================================================================


@pytest.fixture
def sample_participant_info() -> ParticipantInfo:
    """Create sample participant info."""
    return ParticipantInfo(
        numerical_id="1001",
        full_id="1001 T1 Control",
        group_str="Control",
        timepoint_str="T1",
    )


@pytest.fixture
def sample_participant_info_factory():
    """Factory for creating participant info with custom values."""

    def _create(
        numerical_id: str = "1001",
        group: str = "Control",
        timepoint: str = "T1",
    ) -> ParticipantInfo:
        return ParticipantInfo(
            numerical_id=numerical_id,
            full_id=f"{numerical_id} {timepoint} {group}",
            group_str=group,
            timepoint_str=timepoint,
        )

    return _create


# ============================================================================
# DATA FACTORIES - Sleep Periods
# ============================================================================


@pytest.fixture
def sample_sleep_period() -> SleepPeriod:
    """Create sample sleep period with valid timestamps."""
    onset = datetime(2024, 1, 15, 22, 30).timestamp()
    offset = datetime(2024, 1, 16, 6, 45).timestamp()
    return SleepPeriod(
        onset_timestamp=onset,
        offset_timestamp=offset,
        marker_index=1,
        marker_type=MarkerType.MAIN_SLEEP,
    )


@pytest.fixture
def sample_sleep_period_factory():
    """Factory for creating sleep periods with custom values."""

    def _create(
        onset_hour: int = 22,
        onset_minute: int = 30,
        offset_hour: int = 6,
        offset_minute: int = 45,
        base_date: date | None = None,
        marker_index: int = 1,
        marker_type: MarkerType = MarkerType.MAIN_SLEEP,
    ) -> SleepPeriod:
        if base_date is None:
            base_date = date(2024, 1, 15)

        onset = datetime.combine(base_date, datetime.min.time().replace(hour=onset_hour, minute=onset_minute))
        # If offset hour < onset hour, it's the next day
        if offset_hour < onset_hour:
            from datetime import timedelta

            offset_date = base_date + timedelta(days=1)
        else:
            offset_date = base_date
        offset = datetime.combine(offset_date, datetime.min.time().replace(hour=offset_hour, minute=offset_minute))

        return SleepPeriod(
            onset_timestamp=onset.timestamp(),
            offset_timestamp=offset.timestamp(),
            marker_index=marker_index,
            marker_type=marker_type,
        )

    return _create


# ============================================================================
# DATA FACTORIES - Daily Markers
# ============================================================================


@pytest.fixture
def sample_daily_sleep_markers(sample_sleep_period: SleepPeriod) -> DailySleepMarkers:
    """Create sample DailySleepMarkers with one period."""
    markers = DailySleepMarkers()
    markers.period_1 = sample_sleep_period
    return markers


@pytest.fixture
def sample_daily_sleep_markers_factory(sample_sleep_period_factory):
    """Factory for creating daily sleep markers with custom periods."""

    def _create(
        num_periods: int = 1,
        base_date: date | None = None,
    ) -> DailySleepMarkers:
        if base_date is None:
            base_date = date(2024, 1, 15)

        markers = DailySleepMarkers()

        if num_periods >= 1:
            markers.period_1 = sample_sleep_period_factory(
                onset_hour=22,
                offset_hour=6,
                base_date=base_date,
                marker_index=1,
                marker_type=MarkerType.MAIN_SLEEP,
            )
        if num_periods >= 2:
            markers.period_2 = sample_sleep_period_factory(
                onset_hour=14,
                onset_minute=0,
                offset_hour=15,
                offset_minute=30,
                base_date=base_date,
                marker_index=2,
                marker_type=MarkerType.NAP,
            )
        if num_periods >= 3:
            markers.period_3 = sample_sleep_period_factory(
                onset_hour=10,
                onset_minute=0,
                offset_hour=10,
                offset_minute=45,
                base_date=base_date,
                marker_index=3,
                marker_type=MarkerType.NAP,
            )

        return markers

    return _create


@pytest.fixture
def sample_daily_nonwear_markers() -> DailyNonwearMarkers:
    """Create sample DailyNonwearMarkers with one period."""
    markers = DailyNonwearMarkers()
    start = datetime(2024, 1, 15, 18, 0).timestamp()
    end = datetime(2024, 1, 15, 19, 30).timestamp()
    markers.period_1 = ManualNonwearPeriod(
        start_timestamp=start,
        end_timestamp=end,
        marker_index=1,
    )
    return markers


# ============================================================================
# DATA FACTORIES - Sleep Metrics
# ============================================================================


@pytest.fixture
def sample_sleep_metrics(
    sample_participant_info: ParticipantInfo,
    sample_daily_sleep_markers: DailySleepMarkers,
) -> SleepMetrics:
    """Create sample SleepMetrics object."""
    return SleepMetrics(
        filename="DEMO-1001.csv",
        analysis_date="2024-01-15",
        algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE,
        daily_sleep_markers=sample_daily_sleep_markers,
        participant=sample_participant_info,
        total_sleep_time=420.0,
        sleep_efficiency=87.5,
        total_minutes_in_bed=480.0,
        waso=45.0,
        awakenings=3,
        average_awakening_length=15.0,
    )


@pytest.fixture
def sample_sleep_metrics_factory(sample_participant_info_factory, sample_daily_sleep_markers_factory):
    """Factory for creating SleepMetrics with custom values."""

    def _create(
        filename: str = "DEMO-1001.csv",
        analysis_date: str = "2024-01-15",
        algorithm_type: AlgorithmType = AlgorithmType.SADEH_1994_ACTILIFE,
        participant_id: str = "1001",
        tst: float = 420.0,
        efficiency: float = 87.5,
        waso: float = 45.0,
    ) -> SleepMetrics:
        participant = sample_participant_info_factory(numerical_id=participant_id)
        markers = sample_daily_sleep_markers_factory(num_periods=1)

        return SleepMetrics(
            filename=filename,
            analysis_date=analysis_date,
            algorithm_type=algorithm_type,
            daily_sleep_markers=markers,
            participant=participant,
            total_sleep_time=tst,
            sleep_efficiency=efficiency,
            total_minutes_in_bed=480.0,
            waso=waso,
            awakenings=3,
            average_awakening_length=15.0,
        )

    return _create


# ============================================================================
# DATA FACTORIES - Diary Data
# ============================================================================


@pytest.fixture
def sample_diary_entry() -> dict:
    """Create sample diary entry dictionary."""
    return {
        "diary_date": "2024-01-15",
        "bedtime": "22:30",
        "wake_time": "06:45",
        "sleep_quality": 4,
        "sleep_onset_time": "23:00",
        "sleep_offset_time": "06:30",
        "nap_occurred": 1,
        "nap_onset_time": "14:00",
        "nap_offset_time": "15:00",
        "nonwear_occurred": False,
    }


@pytest.fixture
def sample_nap_periods() -> list[dict]:
    """Create sample nap periods for diary."""
    return [
        {"start_time": "14:00", "end_time": "15:00", "quality": 3, "notes": "Afternoon nap"},
        {"start_time": "17:30", "end_time": "18:00", "quality": 2, "notes": None},
    ]


@pytest.fixture
def sample_nonwear_periods() -> list[dict]:
    """Create sample nonwear periods for diary."""
    return [
        {"start_time": "18:00", "end_time": "19:30", "reason": "Shower", "notes": None},
        {"start_time": "21:00", "end_time": "21:30", "reason": "Charging", "notes": "Forgot to put on"},
    ]


# ============================================================================
# ACTIVITY DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_activity_data() -> dict:
    """Create sample activity data for database insertion."""
    base_time = datetime(2024, 1, 15, 0, 0)
    timestamps = []
    axis_y = []
    axis_x = []
    axis_z = []
    vector_magnitude = []

    # Generate 60 epochs (1 hour of data at 60-second epochs)
    for i in range(60):
        from datetime import timedelta

        timestamps.append(base_time + timedelta(minutes=i))
        axis_y.append(float(100 + i * 2))
        axis_x.append(float(50 + i))
        axis_z.append(float(75 + i * 1.5))
        vector_magnitude.append(float(200 + i * 3))

    return {
        "timestamps": timestamps,
        "axis_y": axis_y,
        "axis_x": axis_x,
        "axis_z": axis_z,
        "vector_magnitude": vector_magnitude,
    }


# ============================================================================
# FILE REGISTRY FIXTURES
# ============================================================================


@pytest.fixture
def sample_file_info() -> dict:
    """Create sample file registry info."""
    return {
        "filename": "DEMO-1001.csv",
        "file_hash": "abc123def456",
        "participant_id": "1001",
        "participant_group": "Control",
        "import_date": datetime.now().isoformat(),
        "original_path": "/data/participants/DEMO-1001.csv",
        "file_size": 1024000,
        "date_range_start": "2024-01-15",
        "date_range_end": "2024-01-25",
        "total_records": 14400,
        "status": "imported",
    }


@pytest.fixture
def registered_file(test_db: DatabaseManager, sample_file_info: dict) -> str:
    """
    Register a file in file_registry and return its filename.

    This fixture satisfies foreign key constraints for tables that reference file_registry.
    """
    import sqlite3

    with sqlite3.connect(test_db.db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_registry
            (filename, file_hash, participant_id, participant_group, import_date,
             original_path, file_size, date_range_start, date_range_end, total_records, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_file_info["filename"],
                sample_file_info["file_hash"],
                sample_file_info["participant_id"],
                sample_file_info["participant_group"],
                sample_file_info["import_date"],
                sample_file_info["original_path"],
                sample_file_info["file_size"],
                sample_file_info["date_range_start"],
                sample_file_info["date_range_end"],
                sample_file_info["total_records"],
                sample_file_info["status"],
            ),
        )
        conn.commit()

    return sample_file_info["filename"]
