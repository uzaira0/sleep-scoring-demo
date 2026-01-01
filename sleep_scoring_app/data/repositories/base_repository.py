"""Base repository class with shared utilities for database operations."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ClassVar

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.exceptions import (
    DatabaseError,
    DataIntegrityError,
    ErrorCodes,
)
from sleep_scoring_app.utils.column_registry import DataType, column_registry

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository class providing shared database utilities."""

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

    def __init__(
        self,
        db_path: Path,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """
        Initialize base repository.

        Args:
            db_path: Path to the SQLite database
            validate_table_name: Callback to validate table names
            validate_column_name: Callback to validate column names

        """
        self.db_path = db_path
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name
        self._update_valid_columns()

    def _update_valid_columns(self) -> None:
        """Update valid columns from column registry plus core columns."""
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

    def _convert_value_for_database(self, value: Any, data_type: DataType) -> Any:
        """Convert value to appropriate database format based on data type."""
        import json

        if value is None:
            return None

        if data_type == DataType.BOOLEAN:
            return 1 if value else 0
        if data_type == DataType.INTEGER:
            return int(value) if value is not None else None
        if data_type == DataType.FLOAT:
            return float(value) if value is not None else None
        if data_type == DataType.STRING:
            return str(value) if value is not None else None
        if data_type == DataType.DATETIME:
            # Keep as string for SQLite
            return str(value) if value is not None else None
        if data_type == DataType.DATE:
            # Keep as string for SQLite
            return str(value) if value is not None else None
        if data_type == DataType.JSON:
            # Serialize dicts/lists to JSON string for SQLite
            if isinstance(value, dict | list):
                return json.dumps(value)
            return str(value) if value is not None else None

        # Fallback: if value is a dict/list but data_type is unknown, serialize as JSON
        if isinstance(value, dict | list):
            return json.dumps(value)

        return value
