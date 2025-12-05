#!/usr/bin/env python3
"""
Database Schema Manager for Sleep Scoring Application.

Handles all table creation, index creation, and schema migration operations.
Extracted from DatabaseManager to reduce god-class complexity.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from sleep_scoring_app.core.constants import (
    DatabaseColumn,
    DatabaseTable,
    FeatureFlags,
    ImportStatus,
)
from sleep_scoring_app.utils.column_registry import (
    DataType,
    column_registry,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class DatabaseSchemaManager:
    """
    Manages database schema creation and migration operations.

    This class is designed to be used by DatabaseManager to handle all
    table creation, index creation, and schema migration logic.
    """

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """
        Initialize schema manager with validation callbacks.

        Args:
            validate_table_name: Callback to validate table names
            validate_column_name: Callback to validate column names

        """
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def get_sql_type(self, data_type: DataType) -> str:
        """Convert DataType to SQL type."""
        type_mapping = {
            DataType.STRING: "TEXT",
            DataType.INTEGER: "INTEGER",
            DataType.FLOAT: "REAL",
            DataType.BOOLEAN: "INTEGER",  # SQLite doesn't have native boolean
            DataType.DATETIME: "TEXT",  # Store as ISO string
            DataType.JSON: "TEXT",  # Store as JSON string
        }
        return type_mapping.get(data_type, "TEXT")

    def init_all_tables(self, conn: sqlite3.Connection) -> None:
        """
        Initialize all database tables and indexes.

        Args:
            conn: SQLite connection

        """
        # Validate table names
        sleep_table = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        autosave_table = self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)
        raw_activity_table = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)
        file_registry_table = self._validate_table_name(DatabaseTable.FILE_REGISTRY)
        nonwear_sensor_table = self._validate_table_name(DatabaseTable.NONWEAR_SENSOR_PERIODS)
        choi_periods_table = self._validate_table_name(DatabaseTable.CHOI_ALGORITHM_PERIODS)
        diary_data_table = self._validate_table_name(DatabaseTable.DIARY_DATA)
        diary_file_registry_table = self._validate_table_name(DatabaseTable.DIARY_FILE_REGISTRY)
        diary_raw_data_table = self._validate_table_name(DatabaseTable.DIARY_RAW_DATA)
        diary_nap_periods_table = self._validate_table_name(DatabaseTable.DIARY_NAP_PERIODS)
        diary_nonwear_periods_table = self._validate_table_name(DatabaseTable.DIARY_NONWEAR_PERIODS)
        sleep_markers_extended_table = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)
        manual_nwt_markers_table = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        # Create main table using column registry
        self._create_main_table(conn, sleep_table)
        self._create_indexes(conn, sleep_table)

        # Migrate existing sleep_metrics table to add new columns
        self._migrate_sleep_metrics_table_columns(conn, sleep_table)

        # Create autosave table only if autosave is enabled
        if FeatureFlags.ENABLE_AUTOSAVE:
            self._create_autosave_table(conn, autosave_table)
        self._create_raw_activity_table(conn, raw_activity_table)
        self._create_file_registry_table(conn, file_registry_table)
        self._create_raw_activity_indexes(conn, raw_activity_table, file_registry_table)

        # Migrate axis column names from numeric to directional (axis_1/2/3 -> axis_x/y/z)
        self._migrate_axis_column_names(conn, raw_activity_table)

        # Add missing axis columns (for older databases that don't have them)
        self._migrate_raw_activity_add_axis_columns(conn, raw_activity_table)

        # Create nonwear data tables
        self._create_nonwear_sensor_table(conn, nonwear_sensor_table)
        self._create_choi_periods_table(conn, choi_periods_table)
        self._create_nonwear_indexes(conn, nonwear_sensor_table, choi_periods_table)

        # Create diary data tables
        self._create_diary_data_table(conn, diary_data_table)
        self._create_diary_file_registry_table(conn, diary_file_registry_table)
        self._create_diary_raw_data_table(conn, diary_raw_data_table)
        self._create_diary_nap_periods_table(conn, diary_nap_periods_table)
        self._create_diary_nonwear_periods_table(conn, diary_nonwear_periods_table)
        self._create_diary_indexes(
            conn, diary_data_table, diary_file_registry_table, diary_raw_data_table, diary_nap_periods_table, diary_nonwear_periods_table
        )

        # Migrate existing diary tables to add new columns
        self._migrate_diary_table_columns(conn, diary_data_table)

        # Create extended sleep markers tables
        self._create_sleep_markers_extended_table(conn, sleep_markers_extended_table)
        self._create_manual_nwt_markers_table(conn, manual_nwt_markers_table)
        self._create_extended_markers_indexes(conn, sleep_markers_extended_table, manual_nwt_markers_table)

    def _create_main_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create main sleep metrics table using column registry."""
        # Core columns that are always present
        core_columns = [
            f"{self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT",
            f"{self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL",
            f"{self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} TEXT",  # Composite key
            f"{self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT",
            f"{self._validate_column_name(DatabaseColumn.PARTICIPANT_GROUP)} TEXT",
            f"{self._validate_column_name(DatabaseColumn.PARTICIPANT_TIMEPOINT)} TEXT",
            f"{self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} TEXT NOT NULL",
            f"{self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP",
            f"{self._validate_column_name(DatabaseColumn.UPDATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP",
            f"{self._validate_column_name(DatabaseColumn.METADATA)} TEXT",
        ]

        # Add columns from registry that have database mappings
        registry_columns = []
        excluded_columns = {
            DatabaseColumn.ID,
            DatabaseColumn.FILENAME,
            DatabaseColumn.PARTICIPANT_ID,
            DatabaseColumn.PARTICIPANT_GROUP,
            DatabaseColumn.PARTICIPANT_TIMEPOINT,
            DatabaseColumn.ANALYSIS_DATE,
            DatabaseColumn.CREATED_AT,
            DatabaseColumn.UPDATED_AT,
            DatabaseColumn.METADATA,
        }

        for column in column_registry.get_all():
            if column.database_column and column.database_column not in excluded_columns:
                sql_type = self.get_sql_type(column.data_type)
                default_clause = f" DEFAULT '{column.default_value}'" if column.default_value is not None else ""
                registry_columns.append(f"{self._validate_column_name(column.database_column)} {sql_type}{default_clause}")

        all_columns = core_columns + registry_columns

        # Add unique constraint
        unique_constraint = (
            f"UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)}, {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)})"
        )
        all_columns.append(unique_constraint)

        columns_sql = ",\n        ".join(all_columns)

        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {columns_sql}
            )
        """)

    def _create_indexes(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create database indexes."""
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_filename_date
            ON {table_name}({self._validate_column_name(DatabaseColumn.FILENAME)},
                            {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)})
        """)

        # Add index on PARTICIPANT_KEY for efficient queries
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_participant_key
            ON {table_name}({self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)})
        """)

        # Add composite index on PARTICIPANT_KEY + ANALYSIS_DATE for date-based queries
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_participant_key_date
            ON {table_name}({self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)},
                            {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)})
        """)

    def _create_autosave_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create autosave table for temporary storage."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.SLEEP_DATA)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                      {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)})
            )
        """)

    def _create_file_registry_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create file registry table for imported files."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT PRIMARY KEY,
                {self._validate_column_name(DatabaseColumn.ORIGINAL_PATH)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_GROUP)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_TIMEPOINT)} TEXT,
                {self._validate_column_name(DatabaseColumn.FILE_SIZE)} INTEGER,
                {self._validate_column_name(DatabaseColumn.FILE_HASH)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DATE_RANGE_START)} TEXT,
                {self._validate_column_name(DatabaseColumn.DATE_RANGE_END)} TEXT,
                {self._validate_column_name(DatabaseColumn.TOTAL_RECORDS)} INTEGER,
                {self._validate_column_name(DatabaseColumn.IMPORT_DATE)} TEXT DEFAULT CURRENT_TIMESTAMP,
                {self._validate_column_name(DatabaseColumn.LAST_MODIFIED)} TEXT,
                {self._validate_column_name(DatabaseColumn.STATUS)} TEXT DEFAULT '{ImportStatus.IMPORTED}'
            )
        """)

    def _create_raw_activity_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create raw activity data table for imported CSV data."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILE_HASH)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_GROUP)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_TIMEPOINT)} TEXT,
                {self._validate_column_name(DatabaseColumn.TIMESTAMP)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.AXIS_Y)} REAL NOT NULL,
                {self._validate_column_name(DatabaseColumn.AXIS_X)} REAL,
                {self._validate_column_name(DatabaseColumn.AXIS_Z)} REAL,
                {self._validate_column_name(DatabaseColumn.VECTOR_MAGNITUDE)} REAL,
                {self._validate_column_name(DatabaseColumn.IMPORT_DATE)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.TIMESTAMP)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _create_raw_activity_indexes(
        self,
        conn: sqlite3.Connection,
        raw_activity_table: str,
        file_registry_table: str,
    ) -> None:
        """Create indexes for raw activity data and file registry tables."""
        # Raw activity data indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_raw_activity_filename
            ON {raw_activity_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_raw_activity_timestamp
            ON {raw_activity_table}({self._validate_column_name(DatabaseColumn.TIMESTAMP)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_raw_activity_participant
            ON {raw_activity_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_raw_activity_file_time
            ON {raw_activity_table}({self._validate_column_name(DatabaseColumn.FILENAME)},
                                   {self._validate_column_name(DatabaseColumn.TIMESTAMP)})
        """)

        # File registry indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_file_registry_participant
            ON {file_registry_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_file_registry_status
            ON {file_registry_table}({self._validate_column_name(DatabaseColumn.STATUS)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_file_registry_hash
            ON {file_registry_table}({self._validate_column_name(DatabaseColumn.FILE_HASH)})
        """)

    def _migrate_axis_column_names(self, conn: sqlite3.Connection, table_name: str) -> None:
        """
        Migrate axis column names from numeric (axis_1/2/3) to directional (axis_x/y/z).

        This migration handles the rename from the old numeric naming convention
        to the new directional naming that matches ActiGraph's axis orientation:
        - axis_1 -> axis_y (vertical, ActiGraph Axis1)
        - axis_2 -> axis_x (lateral, ActiGraph Axis2)
        - axis_3 -> axis_z (forward, ActiGraph Axis3)
        """
        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define column renames: old_name -> new_name
        # Note: axis1 maps to axis_y (vertical), axis2 to axis_x (lateral), axis3 to axis_z (forward)
        # Handle both naming conventions: axis1/axis2/axis3 and axis_1/axis_2/axis_3
        column_renames = [
            ("axis1", self._validate_column_name(DatabaseColumn.AXIS_Y)),
            ("axis_1", self._validate_column_name(DatabaseColumn.AXIS_Y)),
            ("axis2", self._validate_column_name(DatabaseColumn.AXIS_X)),
            ("axis_2", self._validate_column_name(DatabaseColumn.AXIS_X)),
            ("axis3", self._validate_column_name(DatabaseColumn.AXIS_Z)),
            ("axis_3", self._validate_column_name(DatabaseColumn.AXIS_Z)),
        ]

        for old_name, new_name in column_renames:
            # Only rename if old column exists and new column doesn't
            if old_name in existing_columns and new_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}")
                    logger.info("Renamed column %s to %s in %s", old_name, new_name, table_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to rename column %s to %s in %s: %s", old_name, new_name, table_name, e)

    def _migrate_raw_activity_add_axis_columns(self, conn: sqlite3.Connection, table_name: str) -> None:
        """
        Add missing axis columns to raw_activity_data table.

        This migration adds axis_x, axis_z, and vector_magnitude columns if they don't exist.
        This handles databases created before these columns were added to the schema.
        """
        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define columns that should exist
        required_columns = [
            (DatabaseColumn.AXIS_X, "REAL"),
            (DatabaseColumn.AXIS_Z, "REAL"),
            (DatabaseColumn.VECTOR_MAGNITUDE, "REAL"),
        ]

        for column_name, column_type in required_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info("Added missing column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        # Column already exists, ignore
                        pass
                    else:
                        logger.warning("Failed to add column %s to %s: %s", validated_column, table_name, e)

    def _create_nonwear_sensor_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create nonwear sensor periods table (sensor data has no indices, only timestamps)."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.START_TIME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.END_TIME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)} INTEGER,
                {self._validate_column_name(DatabaseColumn.PERIOD_TYPE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.START_TIME)},
                       {self._validate_column_name(DatabaseColumn.END_TIME)})
            )
        """)

    def _create_choi_periods_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create Choi algorithm periods (wear periods) table."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.START_TIME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.END_TIME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)} INTEGER,
                {self._validate_column_name(DatabaseColumn.START_INDEX)} INTEGER,
                {self._validate_column_name(DatabaseColumn.END_INDEX)} INTEGER,
                {self._validate_column_name(DatabaseColumn.PERIOD_TYPE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.START_TIME)},
                       {self._validate_column_name(DatabaseColumn.END_TIME)})
            )
        """)

    def _create_nonwear_indexes(
        self,
        conn: sqlite3.Connection,
        nonwear_sensor_table: str,
        choi_periods_table: str,
    ) -> None:
        """Create indexes for nonwear data tables."""
        # Nonwear sensor table indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_nonwear_sensor_filename
            ON {nonwear_sensor_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_nonwear_sensor_participant
            ON {nonwear_sensor_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_nonwear_sensor_time_range
            ON {nonwear_sensor_table}({self._validate_column_name(DatabaseColumn.START_TIME)},
                                     {self._validate_column_name(DatabaseColumn.END_TIME)})
        """)

        # Choi periods table indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_choi_periods_filename
            ON {choi_periods_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_choi_periods_participant
            ON {choi_periods_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_choi_periods_time_range
            ON {choi_periods_table}({self._validate_column_name(DatabaseColumn.START_TIME)},
                                   {self._validate_column_name(DatabaseColumn.END_TIME)})
        """)

    def _create_diary_data_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create diary data table for processed diary entries with auto-calculated flags."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_GROUP)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_TIMEPOINT)} TEXT,
                {self._validate_column_name(DatabaseColumn.DIARY_DATE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.BEDTIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.WAKE_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.SLEEP_QUALITY)} TEXT,
                {self._validate_column_name(DatabaseColumn.SLEEP_ONSET_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.SLEEP_OFFSET_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.IN_BED_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_OCCURRED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME_2)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME_2)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME_3)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME_3)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_OCCURRED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.NONWEAR_REASON)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_START_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_END_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_REASON_2)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_START_TIME_2)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_END_TIME_2)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_REASON_3)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_START_TIME_3)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_END_TIME_3)} TEXT,
                {self._validate_column_name(DatabaseColumn.DIARY_NOTES)} TEXT,
                {self._validate_column_name(DatabaseColumn.NIGHT_NUMBER)} INTEGER,
                -- Auto-calculated column flags
                {self._validate_column_name(DatabaseColumn.BEDTIME_AUTO_CALCULATED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.WAKE_TIME_AUTO_CALCULATED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.SLEEP_ONSET_AUTO_CALCULATED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.SLEEP_OFFSET_AUTO_CALCULATED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.IN_BED_TIME_AUTO_CALCULATED)} INTEGER DEFAULT 0,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                {self._validate_column_name(DatabaseColumn.UPDATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                      {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                      {self._validate_column_name(DatabaseColumn.DIARY_DATE)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.DIARY_FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _create_diary_file_registry_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create diary file registry table for imported diary files."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT PRIMARY KEY,
                {self._validate_column_name(DatabaseColumn.ORIGINAL_PATH)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_GROUP)} TEXT,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_TIMEPOINT)} TEXT,
                {self._validate_column_name(DatabaseColumn.FILE_SIZE)} INTEGER,
                {self._validate_column_name(DatabaseColumn.FILE_HASH)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DATE_RANGE_START)} TEXT,
                {self._validate_column_name(DatabaseColumn.DATE_RANGE_END)} TEXT,
                {self._validate_column_name(DatabaseColumn.TOTAL_RECORDS)} INTEGER,
                {self._validate_column_name(DatabaseColumn.IMPORT_DATE)} TEXT DEFAULT CURRENT_TIMESTAMP,
                {self._validate_column_name(DatabaseColumn.LAST_MODIFIED)} TEXT,
                {self._validate_column_name(DatabaseColumn.STATUS)} TEXT DEFAULT '{ImportStatus.IMPORTED}',
                {self._validate_column_name(DatabaseColumn.ORIGINAL_COLUMN_MAPPING)} TEXT
            )
        """)

    def _create_diary_raw_data_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create diary raw data table for backup of original column data."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.FILE_HASH)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DIARY_DATE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.ORIGINAL_COLUMN_MAPPING)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.IMPORT_DATE)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                      {self._validate_column_name(DatabaseColumn.DIARY_DATE)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.DIARY_FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _create_diary_nap_periods_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create diary nap periods table for multiple naps per day."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DIARY_DATE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.NAP_INDEX)} INTEGER NOT NULL,
                {self._validate_column_name(DatabaseColumn.NAP_START_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_END_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_DURATION_MINUTES)} INTEGER,
                {self._validate_column_name(DatabaseColumn.NAP_QUALITY)} TEXT,
                {self._validate_column_name(DatabaseColumn.NAP_NOTES)} TEXT,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                {self._validate_column_name(DatabaseColumn.UPDATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                       {self._validate_column_name(DatabaseColumn.DIARY_DATE)},
                       {self._validate_column_name(DatabaseColumn.NAP_INDEX)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.DIARY_FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _create_diary_nonwear_periods_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create diary nonwear periods table for multiple nonwear periods per day."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DIARY_DATE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.NONWEAR_INDEX)} INTEGER NOT NULL,
                {self._validate_column_name(DatabaseColumn.NONWEAR_START_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_END_TIME)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_DURATION_MINUTES)} INTEGER,
                {self._validate_column_name(DatabaseColumn.NONWEAR_REASON)} TEXT,
                {self._validate_column_name(DatabaseColumn.NONWEAR_NOTES)} TEXT,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                {self._validate_column_name(DatabaseColumn.UPDATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)},
                       {self._validate_column_name(DatabaseColumn.DIARY_DATE)},
                       {self._validate_column_name(DatabaseColumn.NONWEAR_INDEX)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.DIARY_FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _create_diary_indexes(
        self,
        conn: sqlite3.Connection,
        diary_data_table: str,
        diary_file_registry_table: str,
        diary_raw_data_table: str,
        diary_nap_periods_table: str,
        diary_nonwear_periods_table: str,
    ) -> None:
        """Create indexes for diary data tables."""
        # Diary data table indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_data_filename
            ON {diary_data_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_data_participant
            ON {diary_data_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_data_date
            ON {diary_data_table}({self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_data_file_date
            ON {diary_data_table}({self._validate_column_name(DatabaseColumn.FILENAME)},
                                 {self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

        # Diary file registry indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_file_registry_participant
            ON {diary_file_registry_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_file_registry_status
            ON {diary_file_registry_table}({self._validate_column_name(DatabaseColumn.STATUS)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_file_registry_hash
            ON {diary_file_registry_table}({self._validate_column_name(DatabaseColumn.FILE_HASH)})
        """)

        # Diary raw data table indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_raw_data_filename
            ON {diary_raw_data_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_raw_data_participant
            ON {diary_raw_data_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_raw_data_date
            ON {diary_raw_data_table}({self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

        # Diary nap periods table indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nap_periods_filename
            ON {diary_nap_periods_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nap_periods_participant
            ON {diary_nap_periods_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nap_periods_date
            ON {diary_nap_periods_table}({self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nap_periods_file_date
            ON {diary_nap_periods_table}({self._validate_column_name(DatabaseColumn.FILENAME)},
                                        {self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

        # Diary nonwear periods table indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nonwear_periods_filename
            ON {diary_nonwear_periods_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nonwear_periods_participant
            ON {diary_nonwear_periods_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nonwear_periods_date
            ON {diary_nonwear_periods_table}({self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_diary_nonwear_periods_file_date
            ON {diary_nonwear_periods_table}({self._validate_column_name(DatabaseColumn.FILENAME)},
                                            {self._validate_column_name(DatabaseColumn.DIARY_DATE)})
        """)

    def _create_sleep_markers_extended_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create extended sleep markers table for multiple sleep periods."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.MARKER_INDEX)} INTEGER NOT NULL,
                {self._validate_column_name(DatabaseColumn.ONSET_TIMESTAMP)} REAL NOT NULL,
                {self._validate_column_name(DatabaseColumn.OFFSET_TIMESTAMP)} REAL NOT NULL,
                {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)} INTEGER,
                {self._validate_column_name(DatabaseColumn.MARKER_TYPE)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)},
                       {self._validate_column_name(DatabaseColumn.MARKER_INDEX)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _create_manual_nwt_markers_table(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Create manual NWT markers table (framework only)."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._validate_column_name(DatabaseColumn.ID)} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self._validate_column_name(DatabaseColumn.FILENAME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.START_TIME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.END_TIME)} TEXT NOT NULL,
                {self._validate_column_name(DatabaseColumn.DURATION_MINUTES)} INTEGER,
                {self._validate_column_name(DatabaseColumn.CREATED_BY)} TEXT,
                {self._validate_column_name(DatabaseColumn.CREATED_AT)} TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE({self._validate_column_name(DatabaseColumn.FILENAME)},
                       {self._validate_column_name(DatabaseColumn.START_TIME)},
                       {self._validate_column_name(DatabaseColumn.END_TIME)}),
                FOREIGN KEY({self._validate_column_name(DatabaseColumn.FILENAME)})
                    REFERENCES {self._validate_table_name(DatabaseTable.FILE_REGISTRY)}({self._validate_column_name(DatabaseColumn.FILENAME)})
                    ON DELETE CASCADE
            )
        """)

    def _migrate_diary_table_columns(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Add missing columns to existing diary_data tables."""
        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define new columns that need to be added
        new_columns = [
            (DatabaseColumn.NAP_ONSET_TIME_2, "TEXT"),
            (DatabaseColumn.NAP_OFFSET_TIME_2, "TEXT"),
            (DatabaseColumn.NAP_ONSET_TIME_3, "TEXT"),
            (DatabaseColumn.NAP_OFFSET_TIME_3, "TEXT"),
            (DatabaseColumn.NONWEAR_REASON_2, "TEXT"),
            (DatabaseColumn.NONWEAR_START_TIME_2, "TEXT"),
            (DatabaseColumn.NONWEAR_END_TIME_2, "TEXT"),
            (DatabaseColumn.NONWEAR_REASON_3, "TEXT"),
            (DatabaseColumn.NONWEAR_START_TIME_3, "TEXT"),
            (DatabaseColumn.NONWEAR_END_TIME_3, "TEXT"),
            # Auto-calculated column flags
            (DatabaseColumn.BEDTIME_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.WAKE_TIME_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.SLEEP_ONSET_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.SLEEP_OFFSET_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.IN_BED_TIME_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
        ]

        # Add missing columns
        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info(f"Added column {validated_column} to {table_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        # Column already exists, ignore
                        pass
                    else:
                        logger.warning(f"Failed to add column {validated_column} to {table_name}: {e}")

        # Fix data integrity: Update nap_occurred based on presence of nap times
        try:
            nap_occurred_col = self._validate_column_name(DatabaseColumn.NAP_OCCURRED)
            nap_onset_col = self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME)
            nap_offset_col = self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME)
            nap_onset_2_col = self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME_2)
            nap_offset_2_col = self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME_2)
            nap_onset_3_col = self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME_3)
            nap_offset_3_col = self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME_3)

            cursor = conn.execute(f"""
                UPDATE {table_name}
                SET {nap_occurred_col} = 1
                WHERE {nap_occurred_col} = 0
                AND ({nap_onset_col} IS NOT NULL OR {nap_offset_col} IS NOT NULL
                     OR {nap_onset_2_col} IS NOT NULL OR {nap_offset_2_col} IS NOT NULL
                     OR {nap_onset_3_col} IS NOT NULL OR {nap_offset_3_col} IS NOT NULL)
            """)

            if cursor.rowcount > 0:
                logger.info(f"Fixed {cursor.rowcount} nap_occurred values in {table_name}")

        except sqlite3.OperationalError as e:
            # Column might not exist in older schemas, ignore
            logger.debug(f"Could not fix nap_occurred values: {e}")

    def _migrate_sleep_metrics_table_columns(self, conn: sqlite3.Connection, table_name: str) -> None:
        """Add missing columns to existing sleep_metrics tables."""
        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define new columns that need to be added
        new_columns = [
            (DatabaseColumn.DAILY_SLEEP_MARKERS, "TEXT"),  # JSON column for complete marker structure
            (DatabaseColumn.NAP_ONSET_TIME_3, "TEXT"),
            (DatabaseColumn.NAP_OFFSET_TIME_3, "TEXT"),
            # Generic sleep algorithm columns for DI pattern
            (DatabaseColumn.SLEEP_ALGORITHM_NAME, "TEXT DEFAULT 'sadeh_1994'"),
            (DatabaseColumn.SLEEP_ALGORITHM_ONSET, "INTEGER"),
            (DatabaseColumn.SLEEP_ALGORITHM_OFFSET, "INTEGER"),
        ]

        # Add missing columns
        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info(f"Added column {validated_column} to {table_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        # Column already exists, ignore
                        pass
                    else:
                        logger.warning(f"Failed to add column {validated_column} to {table_name}: {e}")

        # Migrate existing sadeh_onset/sadeh_offset values to generic columns if not already done
        sleep_algo_name_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_NAME)
        sleep_algo_onset_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_ONSET)
        sleep_algo_offset_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_OFFSET)
        sadeh_onset_col = self._validate_column_name(DatabaseColumn.SADEH_ONSET)
        sadeh_offset_col = self._validate_column_name(DatabaseColumn.SADEH_OFFSET)

        try:
            # Copy sadeh_onset to sleep_algorithm_onset where not already set
            conn.execute(f"""
                UPDATE {table_name}
                SET {sleep_algo_onset_col} = {sadeh_onset_col}
                WHERE {sleep_algo_onset_col} IS NULL AND {sadeh_onset_col} IS NOT NULL
            """)

            # Copy sadeh_offset to sleep_algorithm_offset where not already set
            conn.execute(f"""
                UPDATE {table_name}
                SET {sleep_algo_offset_col} = {sadeh_offset_col}
                WHERE {sleep_algo_offset_col} IS NULL AND {sadeh_offset_col} IS NOT NULL
            """)

            # Set algorithm name to sadeh_1994_actilife for all existing records without algorithm name
            conn.execute(f"""
                UPDATE {table_name}
                SET {sleep_algo_name_col} = 'sadeh_1994_actilife'
                WHERE {sleep_algo_name_col} IS NULL
            """)

            # Also update old 'sadeh_1994' to 'sadeh_1994_actilife' for consistency
            conn.execute(f"""
                UPDATE {table_name}
                SET {sleep_algo_name_col} = 'sadeh_1994_actilife'
                WHERE {sleep_algo_name_col} = 'sadeh_1994'
            """)

            logger.debug("Migrated existing Sadeh values to generic algorithm columns")
        except sqlite3.OperationalError as e:
            logger.debug(f"Could not migrate Sadeh values to generic columns: {e}")

        # Migrate legacy algorithm_type values to new algorithm IDs
        algorithm_type_col = self._validate_column_name(DatabaseColumn.ALGORITHM_TYPE)
        try:
            # Map legacy values to new algorithm IDs
            legacy_migrations = [
                ("'Sadeh'", "'sadeh_1994_actilife'"),
                ("'Manual + Algorithm'", "'sadeh_1994_actilife'"),
                ("'Manual + Sadeh'", "'sadeh_1994_actilife'"),
                ("'Cole-Kripke'", "'cole_kripke_1992_actilife'"),
                ("'Automatic'", "'sadeh_1994_actilife'"),
                ("'Manual'", "'manual'"),
                ("'Choi'", "'choi'"),
            ]

            for old_value, new_value in legacy_migrations:
                conn.execute(f"""
                    UPDATE {table_name}
                    SET {algorithm_type_col} = {new_value}
                    WHERE {algorithm_type_col} = {old_value}
                """)

            logger.info("Migrated legacy algorithm_type values to new algorithm IDs")
        except sqlite3.OperationalError as e:
            logger.debug(f"Could not migrate legacy algorithm_type values: {e}")

    def _create_extended_markers_indexes(
        self,
        conn: sqlite3.Connection,
        sleep_markers_table: str,
        nwt_markers_table: str,
    ) -> None:
        """Create indexes for extended markers tables."""
        # Sleep markers extended indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sleep_markers_extended_filename
            ON {sleep_markers_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sleep_markers_extended_participant
            ON {sleep_markers_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sleep_markers_extended_date
            ON {sleep_markers_table}({self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sleep_markers_extended_type
            ON {sleep_markers_table}({self._validate_column_name(DatabaseColumn.MARKER_TYPE)})
        """)

        # Manual NWT markers indexes
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_manual_nwt_markers_filename
            ON {nwt_markers_table}({self._validate_column_name(DatabaseColumn.FILENAME)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_manual_nwt_markers_participant
            ON {nwt_markers_table}({self._validate_column_name(DatabaseColumn.PARTICIPANT_ID)})
        """)

        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_manual_nwt_markers_time_range
            ON {nwt_markers_table}({self._validate_column_name(DatabaseColumn.START_TIME)},
                                  {self._validate_column_name(DatabaseColumn.END_TIME)})
        """)
