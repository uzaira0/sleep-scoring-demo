#!/usr/bin/env python3
"""
Secure Database Manager for Sleep Scoring Application
Handles SQLite database operations with comprehensive security and validation.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from sleep_scoring_app.core.constants import (
    ActivityDataPreference,
    AlgorithmType,
    DatabaseColumn,
    DatabaseTable,
    FeatureFlags,
    MarkerType,
    ParticipantGroup,
    ParticipantTimepoint,
)
from sleep_scoring_app.core.dataclasses import (
    DailyNonwearMarkers,
    DailySleepMarkers,
    ManualNonwearPeriod,
    ParticipantInfo,
    SleepMetrics,
    SleepPeriod,
)
from sleep_scoring_app.core.exceptions import (
    DatabaseError,
    DataIntegrityError,
    ErrorCodes,
    ValidationError,
)
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.database_schema import DatabaseSchemaManager
from sleep_scoring_app.services.memory_service import resource_manager
from sleep_scoring_app.utils.column_registry import (
    DataType,
    column_registry,
)
from sleep_scoring_app.utils.resource_resolver import get_database_path

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Only show warnings and errors
logger = logging.getLogger(__name__)

# Module-level flag to track if database has been initialized (shared across all instances)
_database_initialized = False


class DatabaseManager:
    """Secure database manager with comprehensive validation and error handling."""

    # Pre-validate table and column names to prevent injection
    VALID_TABLES: ClassVar[set[str]] = {
        DatabaseTable.SLEEP_METRICS,
        DatabaseTable.AUTOSAVE_METRICS,
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
        # Raw activity data columns
        DatabaseColumn.FILE_HASH,
        DatabaseColumn.TIMESTAMP,
        DatabaseColumn.AXIS_Y,  # Vertical axis (ActiGraph Axis1)
        DatabaseColumn.AXIS_X,  # Lateral axis (ActiGraph Axis2)
        DatabaseColumn.AXIS_Z,  # Forward axis (ActiGraph Axis3)
        DatabaseColumn.VECTOR_MAGNITUDE,
        DatabaseColumn.STEPS,
        DatabaseColumn.LUX,
        DatabaseColumn.IMPORT_DATE,
        # File registry columns
        DatabaseColumn.ORIGINAL_PATH,
        DatabaseColumn.FILE_SIZE,
        DatabaseColumn.DATE_RANGE_START,
        DatabaseColumn.DATE_RANGE_END,
        DatabaseColumn.TOTAL_RECORDS,
        DatabaseColumn.LAST_MODIFIED,
        DatabaseColumn.STATUS,
        # Nonwear sensor and Choi algorithm period columns
        DatabaseColumn.START_TIME,
        DatabaseColumn.END_TIME,
        DatabaseColumn.DURATION_MINUTES,
        DatabaseColumn.START_INDEX,
        DatabaseColumn.END_INDEX,
        DatabaseColumn.PERIOD_TYPE,
        # Diary-specific columns
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
        # Auto-calculated column flags
        DatabaseColumn.BEDTIME_AUTO_CALCULATED,
        DatabaseColumn.WAKE_TIME_AUTO_CALCULATED,
        DatabaseColumn.SLEEP_ONSET_AUTO_CALCULATED,
        DatabaseColumn.SLEEP_OFFSET_AUTO_CALCULATED,
        DatabaseColumn.IN_BED_TIME_AUTO_CALCULATED,
        # Nap period table columns
        DatabaseColumn.NAP_INDEX,
        DatabaseColumn.NAP_START_TIME,
        DatabaseColumn.NAP_END_TIME,
        DatabaseColumn.NAP_DURATION_MINUTES,
        DatabaseColumn.NAP_QUALITY,
        DatabaseColumn.NAP_NOTES,
        # Nonwear period table columns
        DatabaseColumn.NONWEAR_INDEX,
        DatabaseColumn.NONWEAR_DURATION_MINUTES,
        DatabaseColumn.NONWEAR_NOTES,
        # Extended sleep marker columns
        DatabaseColumn.MARKER_INDEX,
        DatabaseColumn.MARKER_TYPE,
        DatabaseColumn.IS_MAIN_SLEEP,
        DatabaseColumn.CREATED_BY,
        # Manual nonwear marker columns
        DatabaseColumn.SLEEP_DATE,
        DatabaseColumn.START_TIMESTAMP,
        DatabaseColumn.END_TIMESTAMP,
    }

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize database manager with security validations."""
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

        # Register for cleanup
        resource_manager.register_resource(f"database_manager_{id(self)}", self, self._cleanup_resources)

        # Initialize database
        self._init_database()

    def _update_valid_columns(self) -> None:
        """Update valid columns from column registry plus core columns."""
        # Start with all the predefined valid columns from the class
        self._valid_columns = self.VALID_COLUMNS.copy()

        # Add columns from registry that have database mappings
        for column in column_registry.get_all():
            if column.database_column:
                self._valid_columns.add(column.database_column)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            yield conn
        except sqlite3.OperationalError as e:
            logger.exception("Database operation failed")
            if conn:
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
            msg = f"Database operation failed: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_CONNECTION_FAILED) from e
        except sqlite3.IntegrityError as e:
            logger.exception("Database integrity violation")
            if conn:
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
            msg = f"Database integrity violation: {e}"
            raise DataIntegrityError(msg, ErrorCodes.DB_INTEGRITY_VIOLATION) from e
        except Exception as e:
            logger.exception("Unexpected database error")
            if conn:
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
            msg = f"Unexpected database error: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e
        finally:
            if conn:
                with contextlib.suppress(sqlite3.Error):
                    conn.close()

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

        # Skip if already initialized (module-level singleton behavior)
        if _database_initialized:
            # Silently skip - no need to spam logs
            return

        logger.info("Initializing database schema for the first time")

        try:
            with self._get_connection() as conn:
                # Delegate all table/index creation to schema manager
                self._schema_manager.init_all_tables(conn)
                conn.commit()
                logger.info("Database initialized successfully")

                # Mark database as initialized to prevent redundant initialization
                _database_initialized = True

        except Exception as e:
            logger.exception("Failed to initialize database")
            msg = f"Failed to initialize database: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_CONNECTION_FAILED) from e

    def _cleanup_resources(self) -> None:
        """Clean up database resources."""
        # Close any open connections (they should be auto-closed by context manager)
        logger.info("Database resources cleaned up")

    def save_sleep_metrics(self, sleep_metrics: SleepMetrics, is_autosave: bool = False) -> bool:
        """Save sleep metrics to database with validation."""
        # Validate input
        if not isinstance(sleep_metrics, SleepMetrics):
            msg = "sleep_metrics must be SleepMetrics instance"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        # Validate required fields
        InputValidator.validate_string(sleep_metrics.filename, min_length=1, name="filename")
        InputValidator.validate_string(sleep_metrics.analysis_date, min_length=1, name="analysis_date")

        try:
            if is_autosave:
                if not FeatureFlags.ENABLE_AUTOSAVE:
                    return True  # Silently succeed if autosave is disabled
                return self._save_autosave_metrics(sleep_metrics)
            return self._save_permanent_metrics(sleep_metrics)

        except (DatabaseError, ValidationError, DataIntegrityError):
            raise  # Re-raise our custom exceptions
        except Exception as e:
            logger.exception("Unexpected error saving sleep metrics")
            msg = f"Unexpected error saving sleep metrics: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def _validate_sleep_metrics_data(self, data: dict[str, Any]) -> None:
        """Validate sleep metrics data before database insertion."""
        required_fields = [DatabaseColumn.FILENAME, DatabaseColumn.ANALYSIS_DATE]

        for field in required_fields:
            if field not in data or not data[field]:
                msg = f"Missing required field: {field}"
                raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

        # Validate filename
        InputValidator.validate_string(data[DatabaseColumn.FILENAME], min_length=1, name="filename")

        # Validate timestamps if present
        if data.get(DatabaseColumn.ONSET_TIMESTAMP) is not None:
            InputValidator.validate_timestamp(data[DatabaseColumn.ONSET_TIMESTAMP])

        if data.get(DatabaseColumn.OFFSET_TIMESTAMP) is not None:
            InputValidator.validate_timestamp(data[DatabaseColumn.OFFSET_TIMESTAMP])

    def _validate_export_data(self, data: dict[str, Any]) -> None:
        """Validate export data structure."""
        if not isinstance(data, dict):
            msg = "Export data must be a dictionary"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT)

        # Check for required export fields
        if "filename" not in data or not data["filename"]:
            msg = "Export data missing filename"
            raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

    def _save_permanent_metrics(self, metrics: SleepMetrics) -> bool:
        """Save to permanent sleep_metrics table with validation using column registry."""
        # Convert dataclass to database format using column registry
        db_data = self._metrics_to_database_dict(metrics)

        # Validate database data
        self._validate_sleep_metrics_data(db_data)

        # Validate table name
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        with self._get_connection() as conn:
            # Build dynamic query based on available data
            columns = []
            values = []
            placeholders = []

            for column_name, value in db_data.items():
                if value is not None:  # Only include non-null values
                    columns.append(self._validate_column_name(column_name))
                    values.append(value)
                    placeholders.append("?")

            columns_str = ", ".join(columns)
            placeholders_str = ", ".join(placeholders)

            conn.execute(
                f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders_str})",
                values,
            )

            conn.commit()
            logger.info("Saved permanent metrics for %s", metrics.filename)
            return True

    def _metrics_to_database_dict(self, metrics: SleepMetrics) -> dict[str, Any]:
        """Convert SleepMetrics to database dictionary using column registry."""
        db_data = {
            # Core columns always present
            DatabaseColumn.FILENAME: metrics.filename,
            DatabaseColumn.PARTICIPANT_ID: metrics.participant.numerical_id,
            DatabaseColumn.PARTICIPANT_GROUP: metrics.participant.group_str,
            DatabaseColumn.PARTICIPANT_TIMEPOINT: metrics.participant.timepoint_str,
            DatabaseColumn.ANALYSIS_DATE: metrics.analysis_date,
            DatabaseColumn.UPDATED_AT: datetime.now().isoformat(),
        }

        # Add columns from registry using their database mappings
        metrics_dict = metrics.to_dict()

        for column in column_registry.get_all():
            if column.database_column and column.database_column not in db_data:
                # Get value from metrics using column mapping
                value = self._get_metrics_value(metrics_dict, column)
                if value is not None:
                    db_data[column.database_column] = value

        return db_data

    def _get_metrics_value(self, metrics_dict: dict[str, Any], column) -> Any:
        """Get value from metrics dictionary using column definition."""
        # Try different name mappings
        possible_names = [column.name, column.export_column, column.display_name]

        for name in possible_names:
            if name and name in metrics_dict:
                value = metrics_dict[name]
                # Convert value to appropriate type if needed
                return self._convert_value_for_database(value, column.data_type)

        # Use default value if nothing found
        return column.default_value

    def _convert_value_for_database(self, value: Any, data_type: DataType) -> Any:
        """Convert value to appropriate database format."""
        if value is None:
            return None

        if data_type == DataType.JSON:
            return json.dumps(value) if not isinstance(value, str) else value
        if data_type == DataType.DATETIME:
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        if data_type == DataType.BOOLEAN:
            return 1 if value else 0

        return value

    def _save_autosave_metrics(self, metrics: SleepMetrics) -> bool:
        """Save to autosave table for temporary storage with validation."""
        # Validate table name
        table_name = self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)

        # Convert to dict for JSON storage
        export_data = metrics.to_export_dict()

        # Validate export data
        self._validate_export_data(export_data)

        try:
            sleep_data = json.dumps(export_data, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            msg = f"Cannot serialize metrics to JSON: {e}"
            raise ValidationError(msg, ErrorCodes.INVALID_INPUT) from e

        with self._get_connection() as conn:
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {table_name}
                ({self._validate_column_name(DatabaseColumn.FILENAME)},
                 {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)},
                 {self._validate_column_name(DatabaseColumn.SLEEP_DATA)})
                VALUES (?, ?, ?)
            """,
                (metrics.filename, metrics.analysis_date, sleep_data),
            )

            conn.commit()
            logger.info("Saved autosave metrics for %s", metrics.filename)
            return True

    def load_sleep_metrics_by_participant_key(self, participant_key: str, analysis_date: str | None = None) -> list[SleepMetrics]:
        """Load sleep metrics by PARTICIPANT_KEY with validation."""
        # Validate inputs
        InputValidator.validate_string(participant_key, min_length=1, name="participant_key")

        if analysis_date is not None:
            InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row  # Enable dict-like access

            if analysis_date:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (participant_key, analysis_date),
                )
            else:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} DESC,
                          {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (participant_key,),
                )

            rows = cursor.fetchall()

            # Convert database rows to SleepMetrics objects
            metrics_list = []
            for row in rows:
                metrics = self._row_to_sleep_metrics(dict(row))
                if metrics:
                    metrics_list.append(metrics)

            return metrics_list

    def load_sleep_metrics(self, filename: str | None = None, analysis_date: str | None = None) -> list[SleepMetrics]:
        """Load sleep metrics from database with validation."""
        # Validate inputs
        if filename is not None:
            InputValidator.validate_string(filename, min_length=1, name="filename")

        if analysis_date is not None:
            InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row  # Enable dict-like access

            if filename and analysis_date:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (filename, analysis_date),
                )
            elif filename:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} DESC,
                           {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """,
                    (filename,),
                )
            else:
                cursor = conn.execute(f"""
                    SELECT * FROM {table_name}
                    ORDER BY {self._validate_column_name(DatabaseColumn.UPDATED_AT)} DESC
                """)

            results = []
            for row in cursor.fetchall():
                try:
                    # Convert database row to SleepMetrics object
                    result = self._row_to_sleep_metrics(row)
                    results.append(result)
                except (ValueError, KeyError, ValidationError) as e:
                    logger.warning("Skipping invalid database row: %s", e)
                    continue

            logger.debug("Loaded %s sleep metrics records", len(results))
            return results

    def _row_to_sleep_metrics(self, row: sqlite3.Row) -> SleepMetrics:
        """Convert database row to SleepMetrics object with validation."""

        # Helper function to safely get column value
        def safe_get(column_name, default=None):
            try:
                return row[column_name]
            except (KeyError, IndexError):
                return default

        # Validate row data
        if not safe_get(DatabaseColumn.FILENAME):
            msg = "Database row missing filename"
            raise ValidationError(msg, ErrorCodes.MISSING_REQUIRED)

        # Create participant info with validation
        numerical_id = InputValidator.validate_string(
            safe_get(DatabaseColumn.PARTICIPANT_ID) or "Unknown",
            min_length=1,
            name="participant_id",
        )
        timepoint = safe_get(DatabaseColumn.PARTICIPANT_TIMEPOINT) or "BO"

        # Get group component
        group = safe_get(DatabaseColumn.PARTICIPANT_GROUP) or "G1"

        # Reconstruct full_id from all three components
        full_id = f"{numerical_id} {timepoint} {group}" if numerical_id != "UNKNOWN" else "UNKNOWN BO G1"

        participant = ParticipantInfo(
            numerical_id=numerical_id,
            full_id=full_id,
            group=group,
            timepoint=timepoint,
        )

        # Create daily sleep markers with validation - use safe_get for missing columns
        onset_timestamp = safe_get(DatabaseColumn.ONSET_TIMESTAMP)
        offset_timestamp = safe_get(DatabaseColumn.OFFSET_TIMESTAMP)

        if onset_timestamp is not None:
            onset_timestamp = InputValidator.validate_timestamp(onset_timestamp)

        if offset_timestamp is not None:
            offset_timestamp = InputValidator.validate_timestamp(offset_timestamp)

        # Create DailySleepMarkers - prioritize new JSON format, fallback to legacy
        daily_markers = DailySleepMarkers()

        # Check for new daily_sleep_markers JSON column first
        daily_markers_json = safe_get(DatabaseColumn.DAILY_SLEEP_MARKERS)
        if daily_markers_json:
            try:
                import json

                markers_data = json.loads(daily_markers_json) if isinstance(daily_markers_json, str) else daily_markers_json
                daily_markers = DailySleepMarkers.from_dict(markers_data)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to parse daily_sleep_markers JSON: %s", e)
                # Fall through to legacy handling

        # Fallback to legacy single sleep period if no JSON data or parsing failed
        if not daily_markers.get_complete_periods() and onset_timestamp is not None and offset_timestamp is not None:
            # Create a sleep period from legacy markers
            sleep_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )
            # Set as period_1 for backward compatibility
            daily_markers.period_1 = sleep_period

        return SleepMetrics(
            participant=participant,
            filename=InputValidator.validate_string(safe_get(DatabaseColumn.FILENAME), min_length=1, name="filename"),
            analysis_date=InputValidator.validate_string(
                safe_get(DatabaseColumn.ANALYSIS_DATE) or "",
                min_length=0,
                name="analysis_date",
            ),
            algorithm_type=AlgorithmType.migrate_legacy_value(safe_get(DatabaseColumn.ALGORITHM_TYPE) or AlgorithmType.SADEH_1994_ACTILIFE),
            daily_sleep_markers=daily_markers,
            onset_time=safe_get(DatabaseColumn.ONSET_TIME) or "",
            offset_time=safe_get(DatabaseColumn.OFFSET_TIME) or "",
            total_sleep_time=safe_get(DatabaseColumn.TOTAL_SLEEP_TIME),
            sleep_efficiency=safe_get(DatabaseColumn.SLEEP_EFFICIENCY),
            total_minutes_in_bed=safe_get(DatabaseColumn.TOTAL_MINUTES_IN_BED),
            waso=safe_get(DatabaseColumn.WASO),
            awakenings=safe_get(DatabaseColumn.AWAKENINGS),
            average_awakening_length=safe_get(DatabaseColumn.AVERAGE_AWAKENING_LENGTH),
            total_activity=safe_get(DatabaseColumn.TOTAL_ACTIVITY),
            movement_index=safe_get(DatabaseColumn.MOVEMENT_INDEX),
            fragmentation_index=safe_get(DatabaseColumn.FRAGMENTATION_INDEX),
            sleep_fragmentation_index=safe_get(DatabaseColumn.SLEEP_FRAGMENTATION_INDEX),
            sadeh_onset=safe_get(DatabaseColumn.SADEH_ONSET),
            sadeh_offset=safe_get(DatabaseColumn.SADEH_OFFSET),
            overlapping_nonwear_minutes_algorithm=safe_get(DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_ALGORITHM),
            overlapping_nonwear_minutes_sensor=safe_get(DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_SENSOR),
            created_at=safe_get(DatabaseColumn.CREATED_AT) or "",
            updated_at=safe_get(DatabaseColumn.UPDATED_AT) or "",
        )

    def load_autosave_metrics(self, filename: str, analysis_date: str) -> SleepMetrics | None:
        """Load autosaved metrics for specific file and date with validation."""
        if not FeatureFlags.ENABLE_AUTOSAVE:
            return None

        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT {self._validate_column_name(DatabaseColumn.SLEEP_DATA)}
                FROM {table_name}
                WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
            """,
                (filename, analysis_date),
            )

            row = cursor.fetchone()
            if row:
                try:
                    data = json.loads(row[0])
                    # Validate loaded data
                    self._validate_export_data(data)
                    # Convert back to SleepMetrics object
                    return self._dict_to_sleep_metrics(data)
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON in autosave data: %s", e)
                    return None
                except ValidationError as e:
                    logger.warning("Invalid autosave data: %s", e)
                    return None
            return None

    def _dict_to_sleep_metrics(self, data: dict[str, Any]) -> SleepMetrics:
        """Convert dictionary data to SleepMetrics object with validation."""
        # Validate input data
        self._validate_export_data(data)

        # Create participant info with validation
        participant = ParticipantInfo(
            numerical_id=InputValidator.validate_string(
                data.get("Numerical Participant ID", "Unknown"),
                min_length=1,
                name="participant_id",
            ),
            group=ParticipantGroup(data.get("Participant Group", ParticipantGroup.GROUP_1)),
            timepoint=ParticipantTimepoint(data.get("Participant Timepoint", ParticipantTimepoint.T1)),
        )

        # Create daily sleep markers with validation
        onset_timestamp = data.get("onset_timestamp")
        offset_timestamp = data.get("offset_timestamp")

        if onset_timestamp is not None:
            onset_timestamp = InputValidator.validate_timestamp(onset_timestamp)

        if offset_timestamp is not None:
            offset_timestamp = InputValidator.validate_timestamp(offset_timestamp)

        # Create DailySleepMarkers with legacy data (single sleep period)
        daily_markers = DailySleepMarkers()
        if onset_timestamp is not None and offset_timestamp is not None:
            # Create a sleep period from legacy markers
            sleep_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )
            # Set as period_1 for backward compatibility
            daily_markers.period_1 = sleep_period

        return SleepMetrics(
            participant=participant,
            filename=InputValidator.validate_string(data.get("filename", ""), min_length=1, name="filename"),
            analysis_date=data.get("Onset Date", ""),
            algorithm_type=AlgorithmType.migrate_legacy_value(data.get("Sleep Algorithm", AlgorithmType.SADEH_1994_ACTILIFE)),
            daily_sleep_markers=daily_markers,
            onset_time=data.get("Onset Time", ""),
            offset_time=data.get("Offset Time", ""),
            total_sleep_time=data.get("Total Sleep Time (TST)"),
            sleep_efficiency=data.get("Efficiency"),
            total_minutes_in_bed=data.get("Total Minutes in Bed"),
            waso=data.get("Wake After Sleep Onset (WASO)"),
            awakenings=data.get("Number of Awakenings"),
            average_awakening_length=data.get("Average Awakening Length"),
            total_activity=data.get("Total Counts"),
            movement_index=data.get("Movement Index"),
            fragmentation_index=data.get("Fragmentation Index"),
            sleep_fragmentation_index=data.get("Sleep Fragmentation Index"),
            sadeh_onset=data.get("Sadeh Algorithm Value at Sleep Onset"),
            sadeh_offset=data.get("Sadeh Algorithm Value at Sleep Offset"),
            overlapping_nonwear_minutes_algorithm=data.get("Overlapping Nonwear Minutes (Algorithm)"),
            overlapping_nonwear_minutes_sensor=data.get("Overlapping Nonwear Minutes (Sensor)"),
            updated_at=data.get("Saved At", ""),
        )

    def get_all_sleep_data_for_export(self) -> list[dict[str, Any]]:
        """Get all sleep data formatted for export with validation - multiple periods per participant."""
        try:
            metrics = self.load_sleep_metrics()

            # No external diary service dependency - we'll query directly

            # Convert SleepMetrics objects to export format - multiple periods per participant
            export_data = []
            total_participants = 0

            for metric in metrics:
                try:
                    # Integrate diary data into SleepMetrics before export
                    self._integrate_diary_data_into_metrics(metric)

                    # Integrate manual nonwear markers into SleepMetrics before export
                    self._integrate_manual_nonwear_into_metrics(metric)

                    # Get all sleep periods for this participant/date
                    period_records = metric.to_export_dict_list()
                    for record in period_records:
                        self._validate_export_data(record)
                        export_data.append(record)
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
        """Integrate diary data (nap information) into SleepMetrics object for export using direct database query."""
        try:
            # Extract participant info from the metric
            participant_key = metric.participant.participant_key

            # Parse analysis date for diary lookup
            if not metric.analysis_date:
                logger.debug("No analysis date found for %s", metric.filename)
                return

            analysis_date_str = metric.analysis_date

            # Query diary data directly from database
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""SELECT {self._validate_column_name(DatabaseColumn.NAP_OCCURRED)},
                              {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME)},
                              {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME)},
                              {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME_2)},
                              {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME_2)}
                         FROM {self._validate_table_name(DatabaseTable.DIARY_DATA)}
                         WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                           AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?""",
                    (participant_key, analysis_date_str),
                )

                row = cursor.fetchone()

                if row:
                    nap_occurred, nap_onset_time, nap_offset_time, nap_onset_time_2, nap_offset_time_2 = row

                    # Set nap data in dynamic fields for export
                    metric.set_dynamic_field("nap_occurred", nap_occurred)
                    metric.set_dynamic_field("nap_onset_time", nap_onset_time)
                    metric.set_dynamic_field("nap_offset_time", nap_offset_time)
                    metric.set_dynamic_field("nap_onset_time_2", nap_onset_time_2)
                    metric.set_dynamic_field("nap_offset_time_2", nap_offset_time_2)

                    logger.debug("Integrated diary nap data for %s on %s", participant_key, analysis_date_str)
                else:
                    logger.debug("No diary data found for %s on %s", participant_key, analysis_date_str)

        except Exception as e:
            logger.warning("Failed to integrate diary data for %s: %s", metric.filename, e)

    def _integrate_manual_nonwear_into_metrics(self, metric: SleepMetrics) -> None:
        """Integrate manual nonwear marker data into SleepMetrics object for export."""
        from datetime import datetime

        from sleep_scoring_app.core.constants import ExportColumn

        try:
            # Get filename and analysis date for lookup
            filename = metric.filename
            if not filename or not metric.analysis_date:
                return

            # Parse analysis date
            try:
                analysis_date = datetime.strptime(metric.analysis_date, "%Y-%m-%d").date()
            except ValueError:
                logger.debug("Invalid analysis date format for %s", filename)
                return

            # Load manual nonwear markers for this file/date
            daily_nonwear = self.load_manual_nonwear_markers(filename, analysis_date)

            # Get complete periods sorted by start time
            complete_periods = daily_nonwear.get_complete_periods()

            # Set count
            metric.set_dynamic_field(ExportColumn.MANUAL_NWT_COUNT, len(complete_periods))

            # Set up to 3 periods in export fields
            total_duration = 0.0
            for i, period in enumerate(complete_periods[:3], start=1):
                start_dt = datetime.fromtimestamp(period.start_timestamp)
                end_dt = datetime.fromtimestamp(period.end_timestamp)
                duration = period.duration_minutes or 0.0
                total_duration += duration

                if i == 1:
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_1_START, start_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_1_END, end_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_1_DURATION, round(duration, 1))
                elif i == 2:
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_2_START, start_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_2_END, end_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_2_DURATION, round(duration, 1))
                elif i == 3:
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_3_START, start_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_3_END, end_dt.strftime("%H:%M"))
                    metric.set_dynamic_field(ExportColumn.MANUAL_NWT_3_DURATION, round(duration, 1))

            # Set total duration
            metric.set_dynamic_field(ExportColumn.MANUAL_NWT_TOTAL_DURATION, round(total_duration, 1))

            if complete_periods:
                logger.debug(
                    "Integrated %d manual nonwear periods for %s on %s",
                    len(complete_periods),
                    filename,
                    metric.analysis_date,
                )

        except Exception as e:
            logger.warning("Failed to integrate manual nonwear data for %s: %s", metric.filename, e)

    def cleanup_old_autosaves(self, days_old: int = 7) -> int:
        """Remove autosave entries older than specified days with validation."""
        # Validate input
        days_old = InputValidator.validate_integer(days_old, min_val=1, max_val=365, name="days_old")

        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)

        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                DELETE FROM {table_name}
                WHERE {self._validate_column_name(DatabaseColumn.CREATED_AT)} < datetime('now', '-{days_old} days')
            """)

            deleted_count = cursor.rowcount
            conn.commit()
            logger.info("Cleaned up %s old autosave entries", deleted_count)
            return deleted_count

    def get_database_stats(self) -> dict[str, int]:
        """Get database statistics with validation."""
        # Validate table and column names
        sleep_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        autosave_table = self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)

        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {sleep_table}")
            total_records = cursor.fetchone()[0]

            if FeatureFlags.ENABLE_AUTOSAVE:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {autosave_table}")
                autosave_records = cursor.fetchone()[0]
            else:
                autosave_records = 0

            cursor = conn.execute(f"""
                SELECT COUNT(DISTINCT {self._validate_column_name(DatabaseColumn.FILENAME)})
                FROM {sleep_table}
            """)
            unique_files = cursor.fetchone()[0]

            return {
                "total_records": total_records,
                "autosave_records": autosave_records,
                "unique_files": unique_files,
            }

    def load_raw_activity_data(
        self,
        filename: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        activity_column: ActivityDataPreference = ActivityDataPreference.VECTOR_MAGNITUDE,
    ) -> tuple[list[datetime], list[float]]:
        """
        Load raw activity data from database for visualization.

        Args:
            filename: Name of the file to load data for
            start_time: Optional start time to filter data
            end_time: Optional end time to filter data
            activity_column: Which activity column to use (vector_magnitude or axis_y)

        Returns:
            Tuple of (timestamps, activities) lists

        """
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")

        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                # Determine which activity column to use
                if activity_column == ActivityDataPreference.VECTOR_MAGNITUDE:
                    activity_col = DatabaseColumn.VECTOR_MAGNITUDE
                elif activity_column == ActivityDataPreference.AXIS_X:
                    activity_col = DatabaseColumn.AXIS_X
                elif activity_column == ActivityDataPreference.AXIS_Z:
                    activity_col = DatabaseColumn.AXIS_Z
                else:  # ActivityDataPreference.AXIS_Y (vertical - default for Sadeh)
                    activity_col = DatabaseColumn.AXIS_Y

                # Build query with optional time filtering
                base_query = f"""
                    SELECT {self._validate_column_name(DatabaseColumn.TIMESTAMP)},
                           {self._validate_column_name(activity_col)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                """

                params = [filename]

                if start_time and end_time:
                    base_query += f"""
                        AND {self._validate_column_name(DatabaseColumn.TIMESTAMP)} >= ?
                        AND {self._validate_column_name(DatabaseColumn.TIMESTAMP)} < ?
                    """
                    params.extend([start_time.isoformat(), end_time.isoformat()])

                base_query += f" ORDER BY {self._validate_column_name(DatabaseColumn.TIMESTAMP)}"

                cursor = conn.execute(base_query, params)

                timestamps = []
                activities = []

                for row in cursor:
                    try:
                        # Parse ISO timestamp
                        timestamp_str = row[DatabaseColumn.TIMESTAMP]
                        timestamp = datetime.fromisoformat(timestamp_str)
                        activity = max(0.0, float(row[activity_col]))  # Ensure non-negative

                        timestamps.append(timestamp)
                        activities.append(activity)

                    except (ValueError, TypeError) as e:
                        logger.warning("Skipping invalid data row: %s", e)
                        continue

                logger.debug("Loaded %s activity data points for %s", len(timestamps), filename)
                return timestamps, activities

        except Exception:
            logger.exception("Failed to load raw activity data for %s", filename)
            return [], []

    def get_available_activity_columns(self, filename: str) -> list[ActivityDataPreference]:
        """
        Check which activity columns have non-null data for a file.

        Args:
            filename: Name of the file to check

        Returns:
            List of ActivityDataPreference values that have data

        """
        InputValidator.validate_string(filename, min_length=1, name="filename")
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        available = []
        column_mapping = [
            (ActivityDataPreference.AXIS_Y, DatabaseColumn.AXIS_Y),
            (ActivityDataPreference.AXIS_X, DatabaseColumn.AXIS_X),
            (ActivityDataPreference.AXIS_Z, DatabaseColumn.AXIS_Z),
            (ActivityDataPreference.VECTOR_MAGNITUDE, DatabaseColumn.VECTOR_MAGNITUDE),
        ]

        try:
            with self._get_connection() as conn:
                for pref, db_col in column_mapping:
                    # Check if column has any non-null values
                    query = f"""
                        SELECT COUNT(*) FROM {table_name}
                        WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                        AND {self._validate_column_name(db_col)} IS NOT NULL
                        LIMIT 1
                    """
                    cursor = conn.execute(query, [filename])
                    count = cursor.fetchone()[0]
                    if count > 0:
                        available.append(pref)

            logger.debug("Available activity columns for %s: %s", filename, available)
            return available

        except Exception:
            logger.exception("Failed to check available activity columns for %s", filename)
            # Default to Y-axis if check fails
            return [ActivityDataPreference.AXIS_Y]

    def get_available_files(self) -> list[dict[str, Any]]:
        """Get list of available imported files with metadata."""
        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.FILE_REGISTRY)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute(f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.FILENAME)},
                        {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                        {self._validate_column_name(DatabaseColumn.PARTICIPANT_GROUP)},
                        {self._validate_column_name(DatabaseColumn.PARTICIPANT_TIMEPOINT)},
                        {self._validate_column_name(DatabaseColumn.DATE_RANGE_START)},
                        {self._validate_column_name(DatabaseColumn.DATE_RANGE_END)},
                        {self._validate_column_name(DatabaseColumn.TOTAL_RECORDS)},
                        {self._validate_column_name(DatabaseColumn.STATUS)},
                        {self._validate_column_name(DatabaseColumn.IMPORT_DATE)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.STATUS)} = 'imported'
                    ORDER BY {self._validate_column_name(DatabaseColumn.IMPORT_DATE)} DESC
                """)

                files = []
                for row in cursor:
                    files.append(
                        {
                            "filename": row[DatabaseColumn.FILENAME],
                            "display_name": row[DatabaseColumn.FILENAME],
                            "participant_id": row[DatabaseColumn.PARTICIPANT_ID],
                            "participant_group": row[DatabaseColumn.PARTICIPANT_GROUP],
                            "participant_timepoint": row[DatabaseColumn.PARTICIPANT_TIMEPOINT],
                            "date_start": row[DatabaseColumn.DATE_RANGE_START],
                            "date_end": row[DatabaseColumn.DATE_RANGE_END],
                            "total_records": row[DatabaseColumn.TOTAL_RECORDS],
                            "status": row[DatabaseColumn.STATUS],
                            "import_date": row[DatabaseColumn.IMPORT_DATE],
                        },
                    )

                logger.debug("Found %s imported files", len(files))
                return files

        except Exception:
            logger.exception("Failed to get available files")
            return []

    def get_file_date_ranges(self, filename: str) -> list[date]:
        """Get available date ranges for a specific file."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")

        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                # First check if file exists in database
                check_cursor = conn.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                    (filename,),
                )
                record_count = check_cursor.fetchone()[0]

                if record_count == 0:
                    logger.warning("No activity records found for %s in database", filename)
                    return []

                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT DATE({self._validate_column_name(DatabaseColumn.TIMESTAMP)}) as date
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    ORDER BY date
                """,
                    (filename,),
                )

                dates = []
                for row in cursor:
                    try:
                        date_str = row[0]
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                        # Return date objects, not datetime with arbitrary time
                        dates.append(date_obj)
                    except (ValueError, TypeError) as e:
                        logger.warning("Skipping invalid date: %s", e)
                        continue

                logger.debug("Found %s unique dates for %s", len(dates), filename)
                return dates

        except Exception:
            logger.exception("Failed to get date ranges for %s", filename)
            return []

    def get_all_file_date_ranges(self) -> dict[str, int]:
        """Get date ranges for ALL files in a single query - returns dict of filename -> date count."""
        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.FILENAME)},
                        COUNT(DISTINCT DATE({self._validate_column_name(DatabaseColumn.TIMESTAMP)})) as date_count
                    FROM {table_name}
                    GROUP BY {self._validate_column_name(DatabaseColumn.FILENAME)}
                    """,
                )

                result = {}
                for row in cursor:
                    filename = row[0]
                    date_count = row[1]
                    result[filename] = date_count
                    logger.debug("Found %s unique dates for %s", date_count, filename)

                logger.info("Batch loaded date ranges for %s files", len(result))
                return result

        except Exception:
            logger.exception("Failed to get all file date ranges")
            return {}

    def get_all_file_date_ranges_batch(self) -> dict[str, tuple[str, str]]:
        """Get min/max date ranges for ALL files in a single query - returns dict of filename -> (start_date, end_date)."""
        # Validate table and column names
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.FILENAME)},
                        MIN(DATE({self._validate_column_name(DatabaseColumn.TIMESTAMP)})) as start_date,
                        MAX(DATE({self._validate_column_name(DatabaseColumn.TIMESTAMP)})) as end_date
                    FROM {table_name}
                    GROUP BY {self._validate_column_name(DatabaseColumn.FILENAME)}
                    """,
                )

                result = {}
                for row in cursor:
                    filename = row[0]
                    start_date = row[1]  # Already in YYYY-MM-DD format from SQLite DATE()
                    end_date = row[2]  # Already in YYYY-MM-DD format from SQLite DATE()
                    result[filename] = (start_date, end_date)

                logger.info("Batch loaded date ranges for %s files", len(result))
                return result

        except Exception:
            logger.exception("Failed to get all file date ranges")
            return {}

    def get_import_statistics(self) -> dict[str, Any]:
        """Get comprehensive import statistics."""
        try:
            with self._get_connection() as conn:
                # File registry stats
                cursor = conn.execute(f"""
                    SELECT
                        COUNT(*) as total_files,
                        SUM({self._validate_column_name(DatabaseColumn.TOTAL_RECORDS)}) as total_records,
                        COUNT(CASE WHEN {self._validate_column_name(DatabaseColumn.STATUS)} = 'imported' THEN 1 END) as imported_files,
                        COUNT(CASE WHEN {self._validate_column_name(DatabaseColumn.STATUS)} = 'error' THEN 1 END) as error_files,
                        COUNT(DISTINCT {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)}) as unique_participants
                    FROM {self._validate_table_name(DatabaseTable.FILE_REGISTRY)}
                """)

                file_stats = cursor.fetchone()

                # Raw activity data stats
                cursor = conn.execute(f"""
                    SELECT
                        COUNT(*) as total_activity_records,
                        COUNT(DISTINCT {self._validate_column_name(DatabaseColumn.FILENAME)}) as files_with_data,
                        MIN({self._validate_column_name(DatabaseColumn.TIMESTAMP)}) as earliest_data,
                        MAX({self._validate_column_name(DatabaseColumn.TIMESTAMP)}) as latest_data
                    FROM {self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)}
                """)

                activity_stats = cursor.fetchone()

                # Sleep metrics stats
                cursor = conn.execute(f"""
                    SELECT
                        COUNT(*) as sleep_metrics_records,
                        COUNT(DISTINCT {self._validate_column_name(DatabaseColumn.FILENAME)}) as files_with_metrics
                    FROM {self._validate_table_name(DatabaseTable.SLEEP_METRICS)}
                """)

                sleep_stats = cursor.fetchone()

                return {
                    "total_files": file_stats[0] or 0,
                    "total_records": file_stats[1] or 0,
                    "imported_files": file_stats[2] or 0,
                    "error_files": file_stats[3] or 0,
                    "unique_participants": file_stats[4] or 0,
                    "total_activity_records": activity_stats[0] or 0,
                    "files_with_data": activity_stats[1] or 0,
                    "earliest_data": activity_stats[2],
                    "latest_data": activity_stats[3],
                    "sleep_metrics_records": sleep_stats[0] or 0,
                    "files_with_metrics": sleep_stats[1] or 0,
                }

        except Exception:
            logger.exception("Failed to get import statistics")
            return {}

    def clear_all_markers(self) -> dict[str, int]:
        """Clear all sleep markers and metrics from database but preserve raw imported data."""
        try:
            # Validate table names
            sleep_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
            autosave_table = self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)

            with self._get_connection() as conn:
                # Get counts before deletion
                cursor = conn.execute(f"SELECT COUNT(*) FROM {sleep_table}")
                sleep_count = cursor.fetchone()[0]

                if FeatureFlags.ENABLE_AUTOSAVE:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {autosave_table}")
                    autosave_count = cursor.fetchone()[0]
                else:
                    autosave_count = 0

                # Clear sleep metrics table
                conn.execute(f"DELETE FROM {sleep_table}")

                # Clear autosave metrics table if autosave is enabled
                if FeatureFlags.ENABLE_AUTOSAVE:
                    conn.execute(f"DELETE FROM {autosave_table}")

                conn.commit()

                logger.info("Cleared %s sleep metrics records and %s autosave records", sleep_count, autosave_count)

                return {
                    "sleep_metrics_cleared": sleep_count,
                    "autosave_metrics_cleared": autosave_count,
                    "total_cleared": sleep_count + autosave_count,
                }

        except Exception as e:
            logger.exception("Failed to clear markers")
            msg = f"Failed to clear markers: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def clear_activity_data(self) -> dict[str, int]:
        """Clear all imported activity data including raw data, metrics, and file registry."""
        try:
            with self._get_connection() as conn:
                # Get counts before deletion
                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.RAW_ACTIVITY_DATA}")
                raw_data_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.FILE_REGISTRY}")
                file_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.SLEEP_METRICS}")
                metrics_count = cursor.fetchone()[0]

                # Clear all activity-related tables
                conn.execute(f"DELETE FROM {DatabaseTable.SLEEP_METRICS}")
                conn.execute(f"DELETE FROM {DatabaseTable.RAW_ACTIVITY_DATA}")
                conn.execute(f"DELETE FROM {DatabaseTable.FILE_REGISTRY}")
                conn.execute(f"DELETE FROM {DatabaseTable.SLEEP_MARKERS_EXTENDED}")
                if FeatureFlags.ENABLE_AUTOSAVE:
                    conn.execute(f"DELETE FROM {DatabaseTable.AUTOSAVE_METRICS}")

                conn.commit()

                total_cleared = raw_data_count + file_count + metrics_count
                logger.info("Cleared activity data: %s raw records, %s files, %s metrics", raw_data_count, file_count, metrics_count)

                return {
                    "raw_data_cleared": raw_data_count,
                    "files_cleared": file_count,
                    "metrics_cleared": metrics_count,
                    "total_cleared": total_cleared,
                }

        except Exception as e:
            logger.exception("Failed to clear activity data")
            msg = f"Failed to clear activity data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def clear_diary_data(self) -> dict[str, int]:
        """Clear all imported diary data."""
        try:
            with self._get_connection() as conn:
                # Get counts before deletion
                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_DATA}")
                diary_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_RAW_DATA}")
                raw_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_FILE_REGISTRY}")
                file_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NAP_PERIODS}")
                nap_periods_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_NONWEAR_PERIODS}")
                nonwear_periods_count = cursor.fetchone()[0]

                # Clear all diary-related tables
                conn.execute(f"DELETE FROM {DatabaseTable.DIARY_DATA}")
                conn.execute(f"DELETE FROM {DatabaseTable.DIARY_RAW_DATA}")
                conn.execute(f"DELETE FROM {DatabaseTable.DIARY_NAP_PERIODS}")
                conn.execute(f"DELETE FROM {DatabaseTable.DIARY_NONWEAR_PERIODS}")
                conn.execute(f"DELETE FROM {DatabaseTable.DIARY_FILE_REGISTRY}")

                conn.commit()

                total_cleared = diary_count + raw_count + file_count + nap_periods_count + nonwear_periods_count
                logger.info(
                    "Cleared diary data: %s diary entries, %s raw records, %s files, %s nap periods, %s nonwear periods",
                    diary_count,
                    raw_count,
                    file_count,
                    nap_periods_count,
                    nonwear_periods_count,
                )

                return {
                    "diary_entries_cleared": diary_count,
                    "raw_entries_cleared": raw_count,
                    "files_cleared": file_count,
                    "nap_periods_cleared": nap_periods_count,
                    "nonwear_periods_cleared": nonwear_periods_count,
                    "total_cleared": total_cleared,
                }

        except Exception as e:
            logger.exception("Failed to clear diary data")
            msg = f"Failed to clear diary data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def clear_nwt_data(self) -> dict[str, int]:
        """Clear all imported NWT sensor data."""
        try:
            with self._get_connection() as conn:
                # Get counts before deletion
                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.NONWEAR_SENSOR_PERIODS}")
                nwt_count = cursor.fetchone()[0]

                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.MANUAL_NWT_MARKERS}")
                manual_count = cursor.fetchone()[0]

                # Clear NWT-related tables
                conn.execute(f"DELETE FROM {DatabaseTable.NONWEAR_SENSOR_PERIODS}")
                conn.execute(f"DELETE FROM {DatabaseTable.MANUAL_NWT_MARKERS}")

                conn.commit()

                total_cleared = nwt_count + manual_count
                logger.info("Cleared NWT data: %s sensor periods, %s manual markers", nwt_count, manual_count)

                return {
                    "sensor_periods_cleared": nwt_count,
                    "manual_markers_cleared": manual_count,
                    "total_cleared": total_cleared,
                }

        except Exception as e:
            logger.exception("Failed to clear NWT data")
            msg = f"Failed to clear NWT data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def clear_study_days_data(self) -> dict[str, int]:
        """
        Clear all study days data.

        NOT YET IMPLEMENTED: This method requires the study_days table to be created first.

        When implemented, this should:
        1. Delete all rows from study_days table
        2. Return count of deleted records

        The study_days table schema should include:
        - id: Primary key
        - participant_id: Foreign key to participants
        - study_day: Integer day number (1-based)
        - date: Calendar date for the study day
        - created_at: Timestamp
        """
        try:
            # Note: Study days functionality pending database schema implementation
            logger.info("Study days data clearing not yet implemented - table does not exist")
            return {"total_cleared": 0}
        except Exception as e:
            logger.exception("Failed to clear study days data")
            msg = f"Failed to clear study days data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def clear_actilife_data(self) -> dict[str, int]:
        """Clear all ActiLife nonwear data."""
        try:
            with self._get_connection() as conn:
                # Get counts before deletion
                cursor = conn.execute(f"SELECT COUNT(*) FROM {DatabaseTable.CHOI_ALGORITHM_PERIODS}")
                choi_count = cursor.fetchone()[0]

                # Clear ActiLife-related tables
                conn.execute(f"DELETE FROM {DatabaseTable.CHOI_ALGORITHM_PERIODS}")

                conn.commit()

                logger.info("Cleared ActiLife data: %s Choi algorithm periods", choi_count)

                return {
                    "choi_periods_cleared": choi_count,
                    "total_cleared": choi_count,
                }

        except Exception as e:
            logger.exception("Failed to clear ActiLife data")
            msg = f"Failed to clear ActiLife data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def delete_imported_file(self, filename: str) -> bool:
        """Delete an imported file and all its data."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")

        try:
            with self._get_connection() as conn:
                # Begin transaction
                conn.execute("BEGIN TRANSACTION")

                try:
                    # Delete raw activity data
                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    activity_deleted = cursor.rowcount

                    # Delete file registry entry
                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.FILE_REGISTRY)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    registry_deleted = cursor.rowcount

                    conn.commit()
                    logger.info("Deleted %s: %s activity records, %s registry entries", filename, activity_deleted, registry_deleted)
                    return True

                except Exception:
                    conn.rollback()
                    logger.exception("Failed to delete %s", filename)
                    return False

        except Exception:
            logger.exception("Database connection failed when deleting %s", filename)
            return False

    def delete_sleep_metrics_for_date(self, filename: str, analysis_date: str) -> bool:
        """Delete all sleep metrics for a specific file and date."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        try:
            with self._get_connection() as conn:
                # Begin transaction
                conn.execute("BEGIN TRANSACTION")

                try:
                    # Delete from sleep metrics table
                    cursor = conn.execute(
                        f"""DELETE FROM {self._validate_table_name(DatabaseTable.SLEEP_METRICS)}
                           WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                           AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?""",
                        (filename, analysis_date),
                    )
                    sleep_deleted = cursor.rowcount

                    # Delete from autosave metrics table if autosave is enabled
                    autosave_deleted = 0
                    if FeatureFlags.ENABLE_AUTOSAVE:
                        cursor = conn.execute(
                            f"""DELETE FROM {self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)}
                               WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                               AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?""",
                            (filename, analysis_date),
                        )
                        autosave_deleted = cursor.rowcount

                    conn.commit()
                    logger.info(
                        "Deleted all markers for %s on %s: %s sleep metrics, %s autosave records",
                        filename,
                        analysis_date,
                        sleep_deleted,
                        autosave_deleted,
                    )
                    return True

                except Exception:
                    conn.rollback()
                    logger.exception("Failed to delete markers for %s on %s", filename, analysis_date)
                    return False

        except Exception:
            logger.exception("Database connection failed when deleting markers for %s on %s", filename, analysis_date)
            return False

    def save_daily_sleep_markers(self, sleep_metrics: SleepMetrics) -> bool:
        """Save daily sleep markers to extended table."""
        # Validate inputs
        InputValidator.validate_string(sleep_metrics.filename, min_length=1, name="filename")
        InputValidator.validate_string(sleep_metrics.analysis_date, min_length=1, name="analysis_date")

        table_name = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)

        try:
            with self._get_connection() as conn:
                # First, delete existing markers for this file/date
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                """,
                    (sleep_metrics.filename, sleep_metrics.analysis_date),
                )

                # Insert new markers
                for i, period in enumerate(
                    [
                        sleep_metrics.daily_sleep_markers.period_1,
                        sleep_metrics.daily_sleep_markers.period_2,
                        sleep_metrics.daily_sleep_markers.period_3,
                    ],
                    1,
                ):
                    if period is not None and period.is_complete:
                        duration_minutes = int(period.duration_minutes) if period.duration_minutes else None

                        conn.execute(
                            f"""
                            INSERT INTO {table_name} (
                                {self._validate_column_name(DatabaseColumn.FILENAME)},
                                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                                {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)},
                                {self._validate_column_name(DatabaseColumn.MARKER_INDEX)},
                                {self._validate_column_name(DatabaseColumn.ONSET_TIMESTAMP)},
                                {self._validate_column_name(DatabaseColumn.OFFSET_TIMESTAMP)},
                                {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)},
                                {self._validate_column_name(DatabaseColumn.MARKER_TYPE)}
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                sleep_metrics.filename,
                                sleep_metrics.participant.numerical_id,
                                sleep_metrics.analysis_date,
                                i,
                                period.onset_timestamp,
                                period.offset_timestamp,
                                duration_minutes,
                                period.marker_type,
                            ),
                        )

                conn.commit()
                logger.debug("Saved daily sleep markers for %s on %s", sleep_metrics.filename, sleep_metrics.analysis_date)
                return True

        except Exception:
            logger.exception("Failed to save daily sleep markers for %s on %s", sleep_metrics.filename, sleep_metrics.analysis_date)
            return False

    def load_daily_sleep_markers(self, filename: str, analysis_date: str) -> DailySleepMarkers:
        """Load daily sleep markers from extended table."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        table_name = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.MARKER_INDEX)},
                        {self._validate_column_name(DatabaseColumn.ONSET_TIMESTAMP)},
                        {self._validate_column_name(DatabaseColumn.OFFSET_TIMESTAMP)},
                        {self._validate_column_name(DatabaseColumn.MARKER_TYPE)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.MARKER_INDEX)}
                """,
                    (filename, analysis_date),
                )

                daily_markers = DailySleepMarkers()

                for row in cursor.fetchall():
                    marker_index = row[0]
                    period = SleepPeriod(onset_timestamp=row[1], offset_timestamp=row[2], marker_index=marker_index, marker_type=MarkerType(row[3]))

                    # Assign to appropriate slot
                    if marker_index == 1:
                        daily_markers.period_1 = period
                    elif marker_index == 2:
                        daily_markers.period_2 = period
                    elif marker_index == 3:
                        daily_markers.period_3 = period
                    elif marker_index == 4:
                        daily_markers.period_4 = period

                # Update classifications
                daily_markers.update_classifications()
                return daily_markers

        except Exception:
            logger.exception("Failed to load daily sleep markers for %s on %s", filename, analysis_date)
            return DailySleepMarkers()

    def save_diary_nap_periods(self, filename: str, participant_id: str, diary_date: str, nap_periods: list[dict[str, Any]]) -> bool:
        """Save nap periods for a diary entry."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(participant_id, min_length=1, name="participant_id")
        InputValidator.validate_string(diary_date, min_length=1, name="diary_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_NAP_PERIODS)

        try:
            with self._get_connection() as conn:
                # First, delete existing nap periods for this file/date
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?
                """,
                    (filename, diary_date),
                )

                # Insert new nap periods
                for i, nap_period in enumerate(nap_periods, 1):
                    if nap_period.get("start_time") or nap_period.get("end_time"):
                        # Calculate duration if both times are provided
                        duration_minutes = None
                        if nap_period.get("start_time") and nap_period.get("end_time"):
                            try:
                                # Simple duration calculation assuming same-day nap
                                from datetime import datetime

                                start = datetime.strptime(nap_period["start_time"], "%H:%M")
                                end = datetime.strptime(nap_period["end_time"], "%H:%M")
                                duration_minutes = int((end - start).total_seconds() / 60)
                            except (ValueError, TypeError):
                                duration_minutes = None

                        conn.execute(
                            f"""
                            INSERT INTO {table_name} (
                                {self._validate_column_name(DatabaseColumn.FILENAME)},
                                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                                {self._validate_column_name(DatabaseColumn.DIARY_DATE)},
                                {self._validate_column_name(DatabaseColumn.NAP_INDEX)},
                                {self._validate_column_name(DatabaseColumn.NAP_START_TIME)},
                                {self._validate_column_name(DatabaseColumn.NAP_END_TIME)},
                                {self._validate_column_name(DatabaseColumn.NAP_DURATION_MINUTES)},
                                {self._validate_column_name(DatabaseColumn.NAP_QUALITY)},
                                {self._validate_column_name(DatabaseColumn.NAP_NOTES)}
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                filename,
                                participant_id,
                                diary_date,
                                i,
                                nap_period.get("start_time"),
                                nap_period.get("end_time"),
                                duration_minutes,
                                nap_period.get("quality"),
                                nap_period.get("notes"),
                            ),
                        )

                conn.commit()
                logger.debug("Saved %s nap periods for %s on %s", len(nap_periods), filename, diary_date)
                return True

        except Exception:
            logger.exception("Failed to save nap periods for %s on %s", filename, diary_date)
            return False

    def load_diary_nap_periods(self, filename: str, diary_date: str) -> list[dict[str, Any]]:
        """Load nap periods for a diary entry."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(diary_date, min_length=1, name="diary_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_NAP_PERIODS)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.NAP_INDEX)},
                        {self._validate_column_name(DatabaseColumn.NAP_START_TIME)},
                        {self._validate_column_name(DatabaseColumn.NAP_END_TIME)},
                        {self._validate_column_name(DatabaseColumn.NAP_DURATION_MINUTES)},
                        {self._validate_column_name(DatabaseColumn.NAP_QUALITY)},
                        {self._validate_column_name(DatabaseColumn.NAP_NOTES)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.NAP_INDEX)}
                """,
                    (filename, diary_date),
                )

                nap_periods = []
                for row in cursor.fetchall():
                    nap_periods.append(
                        {
                            "index": row[DatabaseColumn.NAP_INDEX],
                            "start_time": row[DatabaseColumn.NAP_START_TIME],
                            "end_time": row[DatabaseColumn.NAP_END_TIME],
                            "duration_minutes": row[DatabaseColumn.NAP_DURATION_MINUTES],
                            "quality": row[DatabaseColumn.NAP_QUALITY],
                            "notes": row[DatabaseColumn.NAP_NOTES],
                        }
                    )

                return nap_periods

        except Exception:
            logger.exception("Failed to load nap periods for %s on %s", filename, diary_date)
            return []

    def save_diary_nonwear_periods(self, filename: str, participant_id: str, diary_date: str, nonwear_periods: list[dict[str, Any]]) -> bool:
        """Save nonwear periods for a diary entry."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(participant_id, min_length=1, name="participant_id")
        InputValidator.validate_string(diary_date, min_length=1, name="diary_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_NONWEAR_PERIODS)

        try:
            with self._get_connection() as conn:
                # First, delete existing nonwear periods for this file/date
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?
                """,
                    (filename, diary_date),
                )

                # Insert new nonwear periods
                for i, nonwear_period in enumerate(nonwear_periods, 1):
                    if nonwear_period.get("start_time") or nonwear_period.get("end_time"):
                        # Calculate duration if both times are provided
                        duration_minutes = None
                        if nonwear_period.get("start_time") and nonwear_period.get("end_time"):
                            try:
                                # Simple duration calculation assuming same-day period
                                from datetime import datetime

                                start = datetime.strptime(nonwear_period["start_time"], "%H:%M")
                                end = datetime.strptime(nonwear_period["end_time"], "%H:%M")
                                duration_minutes = int((end - start).total_seconds() / 60)
                            except (ValueError, TypeError):
                                duration_minutes = None

                        conn.execute(
                            f"""
                            INSERT INTO {table_name} (
                                {self._validate_column_name(DatabaseColumn.FILENAME)},
                                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                                {self._validate_column_name(DatabaseColumn.DIARY_DATE)},
                                {self._validate_column_name(DatabaseColumn.NONWEAR_INDEX)},
                                {self._validate_column_name(DatabaseColumn.NONWEAR_START_TIME)},
                                {self._validate_column_name(DatabaseColumn.NONWEAR_END_TIME)},
                                {self._validate_column_name(DatabaseColumn.NONWEAR_DURATION_MINUTES)},
                                {self._validate_column_name(DatabaseColumn.NONWEAR_REASON)},
                                {self._validate_column_name(DatabaseColumn.NONWEAR_NOTES)}
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                filename,
                                participant_id,
                                diary_date,
                                i,
                                nonwear_period.get("start_time"),
                                nonwear_period.get("end_time"),
                                duration_minutes,
                                nonwear_period.get("reason"),
                                nonwear_period.get("notes"),
                            ),
                        )

                conn.commit()
                logger.debug("Saved %s nonwear periods for %s on %s", len(nonwear_periods), filename, diary_date)
                return True

        except Exception:
            logger.exception("Failed to save nonwear periods for %s on %s", filename, diary_date)
            return False

    def load_diary_nonwear_periods(self, filename: str, diary_date: str) -> list[dict[str, Any]]:
        """Load nonwear periods for a diary entry."""
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(diary_date, min_length=1, name="diary_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_NONWEAR_PERIODS)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.NONWEAR_INDEX)},
                        {self._validate_column_name(DatabaseColumn.NONWEAR_START_TIME)},
                        {self._validate_column_name(DatabaseColumn.NONWEAR_END_TIME)},
                        {self._validate_column_name(DatabaseColumn.NONWEAR_DURATION_MINUTES)},
                        {self._validate_column_name(DatabaseColumn.NONWEAR_REASON)},
                        {self._validate_column_name(DatabaseColumn.NONWEAR_NOTES)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.NONWEAR_INDEX)}
                """,
                    (filename, diary_date),
                )

                nonwear_periods = []
                for row in cursor.fetchall():
                    nonwear_periods.append(
                        {
                            "index": row[DatabaseColumn.NONWEAR_INDEX],
                            "start_time": row[DatabaseColumn.NONWEAR_START_TIME],
                            "end_time": row[DatabaseColumn.NONWEAR_END_TIME],
                            "duration_minutes": row[DatabaseColumn.NONWEAR_DURATION_MINUTES],
                            "reason": row[DatabaseColumn.NONWEAR_REASON],
                            "notes": row[DatabaseColumn.NONWEAR_NOTES],
                        }
                    )

                return nonwear_periods

        except Exception:
            logger.exception("Failed to load nonwear periods for %s on %s", filename, diary_date)
            return []

    # =========================================================================
    # MANUAL NONWEAR MARKERS (User-placed nonwear periods)
    # =========================================================================

    def save_manual_nonwear_markers(
        self,
        filename: str,
        participant_id: str,
        sleep_date: str,
        daily_nonwear_markers: DailyNonwearMarkers,
    ) -> bool:
        """
        Save manual nonwear markers to database.

        Args:
            filename: The participant's data filename
            participant_id: Participant identifier
            sleep_date: The sleep date these markers belong to (YYYY-MM-DD)
            daily_nonwear_markers: Container with up to 10 nonwear periods

        Returns:
            True if save successful, False otherwise

        """
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(participant_id, min_length=1, name="participant_id")
        InputValidator.validate_string(sleep_date, min_length=1, name="sleep_date")

        table_name = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        try:
            with self._get_connection() as conn:
                # First, delete existing markers for this file/date
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.SLEEP_DATE)} = ?
                """,
                    (filename, sleep_date),
                )

                # Insert new markers (only complete periods)
                for i in range(1, 11):
                    period = daily_nonwear_markers.get_period_by_slot(i)
                    if period is not None and period.is_complete:
                        duration_minutes = int(period.duration_minutes) if period.duration_minutes else None

                        conn.execute(
                            f"""
                            INSERT INTO {table_name} (
                                {self._validate_column_name(DatabaseColumn.FILENAME)},
                                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                                {self._validate_column_name(DatabaseColumn.SLEEP_DATE)},
                                {self._validate_column_name(DatabaseColumn.MARKER_INDEX)},
                                {self._validate_column_name(DatabaseColumn.START_TIMESTAMP)},
                                {self._validate_column_name(DatabaseColumn.END_TIMESTAMP)},
                                {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)}
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                filename,
                                participant_id,
                                sleep_date,
                                i,
                                period.start_timestamp,
                                period.end_timestamp,
                                duration_minutes,
                            ),
                        )

                conn.commit()
                saved_count = len(daily_nonwear_markers.get_complete_periods())
                logger.debug(
                    "Saved %s manual nonwear markers for %s on %s",
                    saved_count,
                    filename,
                    sleep_date,
                )
                return True

        except Exception:
            logger.exception(
                "Failed to save manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            return False

    def load_manual_nonwear_markers(
        self,
        filename: str,
        sleep_date: str,
    ) -> DailyNonwearMarkers:
        """
        Load manual nonwear markers from database.

        Args:
            filename: The participant's data filename
            sleep_date: The sleep date to load markers for (YYYY-MM-DD)

        Returns:
            DailyNonwearMarkers container with loaded periods

        """
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(sleep_date, min_length=1, name="sleep_date")

        table_name = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.MARKER_INDEX)},
                        {self._validate_column_name(DatabaseColumn.START_TIMESTAMP)},
                        {self._validate_column_name(DatabaseColumn.END_TIMESTAMP)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.SLEEP_DATE)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.MARKER_INDEX)}
                """,
                    (filename, sleep_date),
                )

                daily_markers = DailyNonwearMarkers()

                for row in cursor.fetchall():
                    marker_index = row[0]
                    period = ManualNonwearPeriod(
                        start_timestamp=row[1],
                        end_timestamp=row[2],
                        marker_index=marker_index,
                    )

                    # Assign to appropriate slot (1-10)
                    daily_markers.set_period_by_slot(marker_index, period)

                loaded_count = len(daily_markers.get_complete_periods())
                if loaded_count > 0:
                    logger.debug(
                        "Loaded %s manual nonwear markers for %s on %s",
                        loaded_count,
                        filename,
                        sleep_date,
                    )

                return daily_markers

        except Exception:
            logger.exception(
                "Failed to load manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            return DailyNonwearMarkers()

    def delete_manual_nonwear_markers(
        self,
        filename: str,
        sleep_date: str,
    ) -> bool:
        """
        Delete all manual nonwear markers for a specific file and date.

        Args:
            filename: The participant's data filename
            sleep_date: The sleep date to delete markers for (YYYY-MM-DD)

        Returns:
            True if deletion successful, False otherwise

        """
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(sleep_date, min_length=1, name="sleep_date")

        table_name = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.SLEEP_DATE)} = ?
                """,
                    (filename, sleep_date),
                )

                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    logger.debug(
                        "Deleted %s manual nonwear markers for %s on %s",
                        deleted_count,
                        filename,
                        sleep_date,
                    )

                return True

        except Exception:
            logger.exception(
                "Failed to delete manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            return False

    def has_manual_nonwear_markers(
        self,
        filename: str,
        sleep_date: str,
    ) -> bool:
        """
        Check if there are any manual nonwear markers for a specific file and date.

        Args:
            filename: The participant's data filename
            sleep_date: The sleep date to check (YYYY-MM-DD)

        Returns:
            True if markers exist, False otherwise

        """
        # Validate inputs
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(sleep_date, min_length=1, name="sleep_date")

        table_name = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.SLEEP_DATE)} = ?
                """,
                    (filename, sleep_date),
                )

                count = cursor.fetchone()[0]
                return count > 0

        except Exception:
            logger.exception(
                "Failed to check manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            return False
