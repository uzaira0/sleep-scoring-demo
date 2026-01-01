#!/usr/bin/env python3
"""
Secure Database Manager for Sleep Scoring Application
Refactored to use Repository pattern for better separation of concerns.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from sleep_scoring_app.core.constants import (
    ActivityDataPreference,
    DatabaseColumn,
    DatabaseTable,
)
from sleep_scoring_app.core.dataclasses import (
    DailySleepMarkers,
)
from sleep_scoring_app.core.exceptions import (
    DatabaseError,
    ErrorCodes,
    ValidationError,
)
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.database_schema import DatabaseSchemaManager
from sleep_scoring_app.data.repositories import (
    ActivityDataRepository,
    DiaryRepository,
    FileRegistryRepository,
    NonwearRepository,
    SleepMetricsRepository,
)
from sleep_scoring_app.utils.column_registry import (
    column_registry,
)
from sleep_scoring_app.utils.resource_resolver import get_database_path

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import date, datetime
    from pathlib import Path

    from sleep_scoring_app.core.dataclasses import (
        DailyNonwearMarkers,
        SleepMetrics,
    )
    from sleep_scoring_app.services.memory_service import ResourceManager

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Module-level flag to track if database has been initialized
_database_initialized = False


class DatabaseManager:
    """
    Secure database manager using Repository pattern.

    This class acts as a facade, delegating all database operations to specialized
    repository classes for better separation of concerns and maintainability.
    """

    # Pre-validate table and column names to prevent injection
    VALID_TABLES: ClassVar[set[str]] = {
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

    VALID_COLUMNS: ClassVar[set[str]] = {
        DatabaseColumn.ID,
        DatabaseColumn.FILENAME,
        DatabaseColumn.PARTICIPANT_KEY,
        DatabaseColumn.PARTICIPANT_ID,
        DatabaseColumn.PARTICIPANT_GROUP,
        DatabaseColumn.PARTICIPANT_TIMEPOINT,
        DatabaseColumn.ANALYSIS_DATE,
        DatabaseColumn.ONSET_TIMESTAMP,
        DatabaseColumn.OFFSET_TIMESTAMP,
        DatabaseColumn.ONSET_TIME,
        DatabaseColumn.OFFSET_TIME,
        DatabaseColumn.TOTAL_SLEEP_TIME,
        DatabaseColumn.SLEEP_EFFICIENCY,
        DatabaseColumn.WASO,
        DatabaseColumn.AWAKENINGS,
        DatabaseColumn.ALGORITHM_TYPE,
        DatabaseColumn.SADEH_ONSET,
        DatabaseColumn.SADEH_OFFSET,
        DatabaseColumn.SLEEP_ALGORITHM_NAME,
        DatabaseColumn.SLEEP_ALGORITHM_ONSET,
        DatabaseColumn.SLEEP_ALGORITHM_OFFSET,
        DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_ALGORITHM,
        DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_SENSOR,
        DatabaseColumn.TOTAL_ACTIVITY,
        DatabaseColumn.MOVEMENT_INDEX,
        DatabaseColumn.FRAGMENTATION_INDEX,
        DatabaseColumn.SLEEP_FRAGMENTATION_INDEX,
        DatabaseColumn.CREATED_AT,
        DatabaseColumn.UPDATED_AT,
        DatabaseColumn.METADATA,
        DatabaseColumn.SLEEP_DATA,
        DatabaseColumn.DAILY_SLEEP_MARKERS,
        DatabaseColumn.FILE_HASH,
        DatabaseColumn.TIMESTAMP,
        DatabaseColumn.AXIS_Y,
        DatabaseColumn.AXIS_X,
        DatabaseColumn.AXIS_Z,
        DatabaseColumn.VECTOR_MAGNITUDE,
        DatabaseColumn.STEPS,
        DatabaseColumn.LUX,
        DatabaseColumn.IMPORT_DATE,
        DatabaseColumn.ORIGINAL_PATH,
        DatabaseColumn.FILE_SIZE,
        DatabaseColumn.DATE_RANGE_START,
        DatabaseColumn.DATE_RANGE_END,
        DatabaseColumn.TOTAL_RECORDS,
        DatabaseColumn.LAST_MODIFIED,
        DatabaseColumn.STATUS,
        DatabaseColumn.START_TIME,
        DatabaseColumn.END_TIME,
        DatabaseColumn.DURATION_MINUTES,
        DatabaseColumn.START_INDEX,
        DatabaseColumn.END_INDEX,
        DatabaseColumn.PERIOD_TYPE,
        DatabaseColumn.DIARY_DATE,
        DatabaseColumn.BEDTIME,
        DatabaseColumn.WAKE_TIME,
        DatabaseColumn.SLEEP_QUALITY,
        DatabaseColumn.SLEEP_ONSET_TIME,
        DatabaseColumn.SLEEP_OFFSET_TIME,
        DatabaseColumn.IN_BED_TIME,
        DatabaseColumn.NAP_OCCURRED,
        DatabaseColumn.NAP_ONSET_TIME,
        DatabaseColumn.NAP_OFFSET_TIME,
        DatabaseColumn.NAP_ONSET_TIME_2,
        DatabaseColumn.NAP_OFFSET_TIME_2,
        DatabaseColumn.NAP_ONSET_TIME_3,
        DatabaseColumn.NAP_OFFSET_TIME_3,
        DatabaseColumn.NONWEAR_OCCURRED,
        DatabaseColumn.NONWEAR_REASON,
        DatabaseColumn.NONWEAR_START_TIME,
        DatabaseColumn.NONWEAR_END_TIME,
        DatabaseColumn.NONWEAR_REASON_2,
        DatabaseColumn.NONWEAR_START_TIME_2,
        DatabaseColumn.NONWEAR_END_TIME_2,
        DatabaseColumn.NONWEAR_REASON_3,
        DatabaseColumn.NONWEAR_START_TIME_3,
        DatabaseColumn.NONWEAR_END_TIME_3,
        DatabaseColumn.DIARY_NOTES,
        DatabaseColumn.NIGHT_NUMBER,
        DatabaseColumn.ORIGINAL_COLUMN_MAPPING,
        DatabaseColumn.BEDTIME_AUTO_CALCULATED,
        DatabaseColumn.WAKE_TIME_AUTO_CALCULATED,
        DatabaseColumn.SLEEP_ONSET_AUTO_CALCULATED,
        DatabaseColumn.SLEEP_OFFSET_AUTO_CALCULATED,
        DatabaseColumn.IN_BED_TIME_AUTO_CALCULATED,
        DatabaseColumn.NAP_INDEX,
        DatabaseColumn.NAP_START_TIME,
        DatabaseColumn.NAP_END_TIME,
        DatabaseColumn.NAP_DURATION_MINUTES,
        DatabaseColumn.NAP_QUALITY,
        DatabaseColumn.NAP_NOTES,
        DatabaseColumn.NONWEAR_INDEX,
        DatabaseColumn.NONWEAR_DURATION_MINUTES,
        DatabaseColumn.NONWEAR_NOTES,
        DatabaseColumn.MARKER_INDEX,
        DatabaseColumn.MARKER_TYPE,
        DatabaseColumn.PERIOD_METRICS_JSON,
        DatabaseColumn.IS_MAIN_SLEEP,
        DatabaseColumn.CREATED_BY,
        DatabaseColumn.SLEEP_DATE,
        DatabaseColumn.START_TIMESTAMP,
        DatabaseColumn.END_TIMESTAMP,
    }

    def __init__(self, db_path: Path | None = None, resource_manager: ResourceManager | None = None) -> None:
        """
        Initialize database manager with security validations.

        Args:
            db_path: Path to the database file. Uses default location if not provided.
            resource_manager: Optional resource manager for cleanup registration.
                             Injected to avoid data layer depending on services layer.

        """
        self._resource_manager = resource_manager

        # Update valid columns dynamically from registry
        self._update_valid_columns()

        if db_path:
            self.db_path = InputValidator.validate_file_path(db_path, must_exist=False, allowed_extensions={".db"})
        else:
            self.db_path = get_database_path()

        # Ensure database directory exists
        InputValidator.validate_directory_path(self.db_path.parent, must_exist=False, create_if_missing=True)

        # Initialize schema manager with validation callbacks
        self._schema_manager = DatabaseSchemaManager(
            validate_table_name=self._validate_table_name,
            validate_column_name=self._validate_column_name,
        )

        # Initialize repositories
        self.sleep_metrics = SleepMetricsRepository(
            self.db_path,
            self._validate_table_name,
            self._validate_column_name,
        )
        self.file_registry = FileRegistryRepository(
            self.db_path,
            self._validate_table_name,
            self._validate_column_name,
        )
        self.nonwear = NonwearRepository(
            self.db_path,
            self._validate_table_name,
            self._validate_column_name,
        )
        self.diary = DiaryRepository(
            self.db_path,
            self._validate_table_name,
            self._validate_column_name,
        )
        self.activity = ActivityDataRepository(
            self.db_path,
            self._validate_table_name,
            self._validate_column_name,
        )

        # Register for cleanup if resource manager was provided
        if self._resource_manager:
            self._resource_manager.register_resource(f"database_manager_{id(self)}", self, self._cleanup_resources)

        # Initialize database
        self._init_database()

    def _update_valid_columns(self) -> None:
        """Update valid columns from column registry plus core columns."""
        self._valid_columns = self.VALID_COLUMNS.copy()

        # Add columns from registry that have database mappings
        for column in column_registry.get_all():
            if column.database_column:
                self._valid_columns.add(column.database_column)

    def _validate_table_name(self, table_name: str) -> str:
        """Validate table name to prevent SQL injection."""
        if table_name not in self.VALID_TABLES:
            msg = f"Invalid table name: {table_name}"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)
        return table_name

    def _validate_column_name(self, column_name: str) -> str:
        """Validate column name to prevent SQL injection."""
        if column_name not in self._valid_columns:
            msg = f"Invalid column name: {column_name}"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)
        return column_name

    def _init_database(self) -> None:
        """Initialize database schema with security validations using column registry."""
        global _database_initialized

        if _database_initialized:
            return

        logger.info("Initializing database schema for the first time")

        try:
            from sleep_scoring_app.data.repositories.base_repository import BaseRepository

            temp_repo = BaseRepository(self.db_path, self._validate_table_name, self._validate_column_name)
            with temp_repo._get_connection() as conn:
                self._schema_manager.init_all_tables(conn)
                conn.commit()
                logger.info("Database initialized successfully")
                _database_initialized = True

        except Exception as e:
            logger.exception("Failed to initialize database")
            msg = f"Failed to initialize database: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_CONNECTION_FAILED) from e

    def _cleanup_resources(self) -> None:
        """Clean up database resources."""
        logger.info("Database resources cleaned up")

    # ==================== Facade Methods - Delegate to Repositories ====================

    # Sleep Metrics Methods
    def save_sleep_metrics(self, sleep_metrics: SleepMetrics) -> bool:
        """Save sleep metrics to database."""
        return self.sleep_metrics.save_sleep_metrics(sleep_metrics)

    def save_sleep_metrics_atomic(self, metrics: SleepMetrics) -> bool:
        """Atomically save sleep metrics to both tables."""
        return self.sleep_metrics.save_sleep_metrics_atomic(metrics)

    def load_sleep_metrics_by_participant_key(self, participant_key: str, analysis_date: str | None = None) -> list[SleepMetrics]:
        """Load sleep metrics by participant key."""
        return self.sleep_metrics.load_sleep_metrics_by_participant_key(participant_key, analysis_date)

    def load_sleep_metrics(self, filename: str | None = None, analysis_date: str | None = None) -> list[SleepMetrics]:
        """Load sleep metrics from database."""
        return self.sleep_metrics.load_sleep_metrics(filename, analysis_date)

    def get_sleep_metrics_by_filename_and_date(self, filename: str, analysis_date: str) -> SleepMetrics | None:
        """Get single sleep metrics record by filename and date."""
        return self.sleep_metrics.get_sleep_metrics_by_filename_and_date(filename, analysis_date)

    def delete_sleep_metrics_for_date(self, filename: str, analysis_date: str) -> bool:
        """Delete sleep metrics for specific file and date."""
        return self.sleep_metrics.delete_sleep_metrics_for_date(filename, analysis_date)

    def get_database_stats(self) -> dict[str, int]:
        """Get database statistics."""
        return self.sleep_metrics.get_database_stats()

    def get_all_sleep_data_for_export(self) -> list[dict[str, Any]]:
        """Get all sleep data formatted for export with integrated diary and nonwear data."""
        from datetime import datetime

        from sleep_scoring_app.core.constants import ExportColumn

        try:
            metrics = self.sleep_metrics.load_sleep_metrics()
            export_data = []
            total_participants = 0

            for metric in metrics:
                try:
                    # Integrate diary data
                    self._integrate_diary_data_into_metrics(metric)

                    # Integrate manual nonwear markers
                    self._integrate_manual_nonwear_into_metrics(metric)

                    # Get all sleep periods
                    period_records = metric.to_export_dict_list()
                    export_data.extend(period_records)
                    total_participants += 1
                except (ValueError, AttributeError, ValidationError) as e:
                    logger.warning("Skipping invalid export record for %s: %s", metric.filename, e)
                    continue

            logger.info("Prepared %s sleep periods from %s participants for export", len(export_data), total_participants)
            return export_data

        except Exception as e:
            logger.exception("Failed to prepare export data")
            msg = f"Failed to prepare export data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def _integrate_diary_data_into_metrics(self, metric: SleepMetrics) -> None:
        """Integrate diary data (nap information) into SleepMetrics for export."""
        try:
            participant_key = metric.participant.participant_key
            if not metric.analysis_date:
                logger.debug("No analysis date found for %s", metric.filename)
                return

            analysis_date_str = metric.analysis_date

            # Query diary data via DiaryRepository
            nap_data = self.diary.get_diary_nap_data_for_export(participant_key, analysis_date_str)

            if nap_data:
                metric.set_dynamic_field("nap_occurred", nap_data["nap_occurred"])
                metric.set_dynamic_field("nap_onset_time", nap_data["nap_onset_time"])
                metric.set_dynamic_field("nap_offset_time", nap_data["nap_offset_time"])
                metric.set_dynamic_field("nap_onset_time_2", nap_data["nap_onset_time_2"])
                metric.set_dynamic_field("nap_offset_time_2", nap_data["nap_offset_time_2"])
                logger.debug("Integrated diary nap data for %s on %s", participant_key, analysis_date_str)
            else:
                logger.debug("No diary data found for %s on %s", participant_key, analysis_date_str)

        except Exception as e:
            logger.warning("Failed to integrate diary data for %s: %s", metric.filename, e)

    def _integrate_manual_nonwear_into_metrics(self, metric: SleepMetrics) -> None:
        """Integrate manual nonwear marker data into SleepMetrics for export."""
        from datetime import datetime

        from sleep_scoring_app.core.constants import ExportColumn

        try:
            filename = metric.filename
            if not filename or not metric.analysis_date:
                return

            try:
                analysis_date = datetime.strptime(metric.analysis_date, "%Y-%m-%d").date()
            except ValueError:
                logger.debug("Invalid analysis date format for %s", filename)
                return

            # Load manual nonwear markers
            daily_nonwear = self.nonwear.load_manual_nonwear_markers(filename, analysis_date)
            complete_periods = daily_nonwear.get_complete_periods()

            metric.set_dynamic_field(ExportColumn.MANUAL_NWT_COUNT, len(complete_periods))

            nwt_column_map = {
                1: (ExportColumn.MANUAL_NWT_1_START, ExportColumn.MANUAL_NWT_1_END, ExportColumn.MANUAL_NWT_1_DURATION),
                2: (ExportColumn.MANUAL_NWT_2_START, ExportColumn.MANUAL_NWT_2_END, ExportColumn.MANUAL_NWT_2_DURATION),
                3: (ExportColumn.MANUAL_NWT_3_START, ExportColumn.MANUAL_NWT_3_END, ExportColumn.MANUAL_NWT_3_DURATION),
                4: (ExportColumn.MANUAL_NWT_4_START, ExportColumn.MANUAL_NWT_4_END, ExportColumn.MANUAL_NWT_4_DURATION),
                5: (ExportColumn.MANUAL_NWT_5_START, ExportColumn.MANUAL_NWT_5_END, ExportColumn.MANUAL_NWT_5_DURATION),
                6: (ExportColumn.MANUAL_NWT_6_START, ExportColumn.MANUAL_NWT_6_END, ExportColumn.MANUAL_NWT_6_DURATION),
                7: (ExportColumn.MANUAL_NWT_7_START, ExportColumn.MANUAL_NWT_7_END, ExportColumn.MANUAL_NWT_7_DURATION),
                8: (ExportColumn.MANUAL_NWT_8_START, ExportColumn.MANUAL_NWT_8_END, ExportColumn.MANUAL_NWT_8_DURATION),
                9: (ExportColumn.MANUAL_NWT_9_START, ExportColumn.MANUAL_NWT_9_END, ExportColumn.MANUAL_NWT_9_DURATION),
                10: (ExportColumn.MANUAL_NWT_10_START, ExportColumn.MANUAL_NWT_10_END, ExportColumn.MANUAL_NWT_10_DURATION),
            }

            total_duration = 0.0
            for i, period in enumerate(complete_periods[:10], start=1):
                start_dt = datetime.fromtimestamp(period.start_timestamp)
                end_dt = datetime.fromtimestamp(period.end_timestamp)
                duration = period.duration_minutes or 0.0
                total_duration += duration

                if i in nwt_column_map:
                    start_col, end_col, dur_col = nwt_column_map[i]
                    metric.set_dynamic_field(start_col, start_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(end_col, end_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(dur_col, round(duration, 1))

            metric.set_dynamic_field(ExportColumn.MANUAL_NWT_TOTAL_DURATION, round(total_duration, 1))

            if complete_periods:
                logger.debug("Integrated %d manual nonwear periods for %s on %s", len(complete_periods), filename, metric.analysis_date)

        except Exception as e:
            logger.warning("Failed to integrate manual nonwear data for %s: %s", metric.filename, e)

    # File Registry Methods
    def get_available_files(self) -> list[dict[str, Any]]:
        """Get list of available imported files."""
        return self.file_registry.get_available_files()

    def get_file_date_ranges(self, filename: str) -> list[date]:
        """Get available date ranges for a file."""
        return self.file_registry.get_file_date_ranges(filename)

    def get_all_file_date_ranges(self) -> dict[str, int]:
        """Get date ranges for all files."""
        return self.file_registry.get_all_file_date_ranges()

    def get_all_file_date_ranges_batch(self) -> dict[str, tuple[str, str]]:
        """Get min/max date ranges for all files."""
        return self.file_registry.get_all_file_date_ranges_batch()

    def get_import_statistics(self) -> dict[str, Any]:
        """Get comprehensive import statistics."""
        return self.file_registry.get_import_statistics()

    def delete_imported_file(self, filename: str) -> bool:
        """Delete imported file and all associated data."""
        return self.file_registry.delete_imported_file(filename)

    # Activity Data Methods
    def load_raw_activity_data(
        self,
        filename: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        activity_column: ActivityDataPreference = ActivityDataPreference.VECTOR_MAGNITUDE,
    ) -> tuple[list[datetime], list[float]]:
        """Load raw activity data for visualization."""
        return self.activity.load_raw_activity_data(filename, start_time, end_time, activity_column)

    def load_all_activity_columns(
        self,
        filename: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, list]:
        """
        Load ALL activity columns in ONE query with unified timestamps.

        This is the SINGLE SOURCE OF TRUTH for activity data loading.
        All columns share the SAME timestamps, preventing alignment bugs.
        """
        return self.activity.load_all_activity_columns(filename, start_time, end_time)

    def get_available_activity_columns(self, filename: str) -> list[ActivityDataPreference]:
        """Check which activity columns have data."""
        return self.activity.get_available_activity_columns(filename)

    # Nonwear Methods
    def save_manual_nonwear_markers(
        self,
        filename: str,
        participant_id: str,
        sleep_date: str,
        daily_nonwear_markers: DailyNonwearMarkers,
    ) -> bool:
        """Save manual nonwear markers."""
        return self.nonwear.save_manual_nonwear_markers(filename, participant_id, sleep_date, daily_nonwear_markers)

    def load_manual_nonwear_markers(self, filename: str, sleep_date: str) -> DailyNonwearMarkers:
        """Load manual nonwear markers."""
        return self.nonwear.load_manual_nonwear_markers(filename, sleep_date)

    def delete_manual_nonwear_markers(self, filename: str, sleep_date: str) -> bool:
        """Delete manual nonwear markers."""
        return self.nonwear.delete_manual_nonwear_markers(filename, sleep_date)

    def has_manual_nonwear_markers(self, filename: str, sleep_date: str) -> bool:
        """Check if manual nonwear markers exist."""
        return self.nonwear.has_manual_nonwear_markers(filename, sleep_date)

    # Diary Methods
    def save_diary_nap_periods(self, filename: str, participant_id: str, diary_date: str, nap_periods: list[dict[str, Any]]) -> bool:
        """Save nap periods for diary entry."""
        return self.diary.save_diary_nap_periods(filename, participant_id, diary_date, nap_periods)

    def load_diary_nap_periods(self, filename: str, diary_date: str) -> list[dict[str, Any]]:
        """Load nap periods for diary entry."""
        return self.diary.load_diary_nap_periods(filename, diary_date)

    def save_diary_nonwear_periods(self, filename: str, participant_id: str, diary_date: str, nonwear_periods: list[dict[str, Any]]) -> bool:
        """Save nonwear periods for diary entry."""
        return self.diary.save_diary_nonwear_periods(filename, participant_id, diary_date, nonwear_periods)

    def load_diary_nonwear_periods(self, filename: str, diary_date: str) -> list[dict[str, Any]]:
        """Load nonwear periods for diary entry."""
        return self.diary.load_diary_nonwear_periods(filename, diary_date)

    # Clear Data Methods - Facade methods delegating to repositories
    def clear_activity_data(self, filename: str | None = None) -> int:
        """Clear raw activity data from database."""
        return self.activity.clear_activity_data(filename)

    def clear_nwt_data(self) -> int:
        """Clear all NWT sensor data from database."""
        return self.nonwear.clear_nwt_data()

    def clear_diary_data(self) -> int:
        """Clear all diary data from database."""
        return self.diary.clear_diary_data()

    def clear_all_markers(self) -> dict[str, int]:
        """Clear all sleep AND nonwear markers from database."""
        from sleep_scoring_app.data.repositories.base_repository import BaseRepository

        cleared = {"sleep_metrics_cleared": 0, "nonwear_markers_cleared": 0, "total_cleared": 0}

        try:
            temp_repo = BaseRepository(self.db_path, self._validate_table_name, self._validate_column_name)
            with temp_repo._get_connection() as conn:
                # Clear sleep_metrics
                metrics_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
                cursor = conn.execute(f"DELETE FROM {metrics_table}")
                cleared["sleep_metrics_cleared"] = cursor.rowcount

                # Clear sleep_markers_extended
                markers_table = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)
                cursor = conn.execute(f"DELETE FROM {markers_table}")

                # Clear manual nonwear markers (sleep and nonwear markers should be treated uniformly)
                nonwear_table = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)
                cursor = conn.execute(f"DELETE FROM {nonwear_table}")
                cleared["nonwear_markers_cleared"] = cursor.rowcount

                conn.commit()
                cleared["total_cleared"] = cleared["sleep_metrics_cleared"] + cleared["nonwear_markers_cleared"]
                logger.info("Cleared all markers (sleep + nonwear): %s", cleared)
                return cleared

        except Exception as e:
            logger.exception("Failed to clear all markers")
            msg = f"Failed to clear all markers: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_DELETE_FAILED) from e
