#!/usr/bin/env python3
"""
Migration Registry for Sleep Scoring Application.

Contains all database migrations in version order.
Each migration represents a specific schema change with up/down methods.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.data.migrations import Migration

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class Migration001InitialSchema(Migration):
    """Initial schema creation with all base tables."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=1, description="Initial schema with all base tables")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Create all initial tables."""
        # Import schema manager to reuse table creation logic
        from sleep_scoring_app.data.database_schema import DatabaseSchemaManager

        schema_manager = DatabaseSchemaManager(self._validate_table_name, self._validate_column_name)

        # Create all tables (without migrations) to avoid circular dependency
        # Note: This will create tables using CREATE TABLE IF NOT EXISTS
        # so it's safe to run multiple times
        schema_manager.init_all_tables(conn, use_migrations=False)

    def down(self, conn: sqlite3.Connection) -> None:
        """Drop all tables (dangerous - use with caution)."""
        tables_to_drop = [
            DatabaseTable.MANUAL_NWT_MARKERS,
            DatabaseTable.SLEEP_MARKERS_EXTENDED,
            DatabaseTable.DIARY_NONWEAR_PERIODS,
            DatabaseTable.DIARY_NAP_PERIODS,
            DatabaseTable.DIARY_RAW_DATA,
            DatabaseTable.DIARY_DATA,
            DatabaseTable.DIARY_FILE_REGISTRY,
            DatabaseTable.CHOI_ALGORITHM_PERIODS,
            DatabaseTable.NONWEAR_SENSOR_PERIODS,
            DatabaseTable.RAW_ACTIVITY_DATA,
            DatabaseTable.FILE_REGISTRY,
            DatabaseTable.SLEEP_METRICS,
        ]

        for table in tables_to_drop:
            validated_table = self._validate_table_name(table)
            conn.execute(f"DROP TABLE IF EXISTS {validated_table}")


class Migration002AddPeriodMetricsJson(Migration):
    """Add period_metrics_json column to sleep_markers_extended table."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=2, description="Add period_metrics_json column to sleep_markers_extended")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add period_metrics_json column."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)
        column_name = self._validate_column_name(DatabaseColumn.PERIOD_METRICS_JSON)

        # Check if column already exists
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT")
            logger.info("Added %s column to %s", column_name, table_name)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove period_metrics_json column (SQLite doesn't support DROP COLUMN before 3.35.0)."""
        # SQLite limitation: Cannot drop columns in older versions
        # Would require recreating the table without the column
        logger.warning("Rollback of migration 2 not fully supported - column will remain")


class Migration003RenameAxisColumns(Migration):
    """Rename axis columns from numeric to directional (axis_1/2/3 -> axis_x/y/z)."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=3, description="Rename axis columns from numeric to directional")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Rename axis columns."""
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define column renames: old_name -> new_name
        column_renames = [
            ("axis1", self._validate_column_name(DatabaseColumn.AXIS_Y)),
            ("axis_1", self._validate_column_name(DatabaseColumn.AXIS_Y)),
            ("axis2", self._validate_column_name(DatabaseColumn.AXIS_X)),
            ("axis_2", self._validate_column_name(DatabaseColumn.AXIS_X)),
            ("axis3", self._validate_column_name(DatabaseColumn.AXIS_Z)),
            ("axis_3", self._validate_column_name(DatabaseColumn.AXIS_Z)),
        ]

        for old_name, new_name in column_renames:
            if old_name in existing_columns and new_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}")
                    logger.info("Renamed column %s to %s in %s", old_name, new_name, table_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to rename column %s to %s: %s", old_name, new_name, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Rename axis columns back to numeric."""
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Reverse the renames
        column_renames = [
            (self._validate_column_name(DatabaseColumn.AXIS_Y), "axis_1"),
            (self._validate_column_name(DatabaseColumn.AXIS_X), "axis_2"),
            (self._validate_column_name(DatabaseColumn.AXIS_Z), "axis_3"),
        ]

        for new_name, old_name in column_renames:
            if new_name in existing_columns and old_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} RENAME COLUMN {new_name} TO {old_name}")
                    logger.info("Renamed column %s back to %s in %s", new_name, old_name, table_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to rename column %s to %s: %s", new_name, old_name, e)


class Migration004AddMissingAxisColumns(Migration):
    """Add missing axis columns (axis_x, axis_z, vector_magnitude) to raw_activity_data."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=4, description="Add missing axis columns to raw_activity_data")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add missing axis columns."""
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

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
                    logger.info("Added column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.warning("Failed to add column %s: %s", validated_column, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove axis columns (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 4 not fully supported - columns will remain")


class Migration005AddDiaryNapColumns(Migration):
    """Add nap_onset_time_2, nap_offset_time_2, nap_onset_time_3, nap_offset_time_3."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=5, description="Add additional nap time columns to diary_data")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add nap time columns."""
        table_name = self._validate_table_name(DatabaseTable.DIARY_DATA)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            (DatabaseColumn.NAP_ONSET_TIME_2, "TEXT"),
            (DatabaseColumn.NAP_OFFSET_TIME_2, "TEXT"),
            (DatabaseColumn.NAP_ONSET_TIME_3, "TEXT"),
            (DatabaseColumn.NAP_OFFSET_TIME_3, "TEXT"),
        ]

        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info("Added column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.warning("Failed to add column %s: %s", validated_column, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove nap time columns (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 5 not fully supported - columns will remain")


class Migration006AddDiaryNonwearColumns(Migration):
    """Add nonwear_reason_2/3, nonwear_start_time_2/3, nonwear_end_time_2/3."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=6, description="Add additional nonwear columns to diary_data")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add nonwear columns."""
        table_name = self._validate_table_name(DatabaseTable.DIARY_DATA)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            (DatabaseColumn.NONWEAR_REASON_2, "TEXT"),
            (DatabaseColumn.NONWEAR_START_TIME_2, "TEXT"),
            (DatabaseColumn.NONWEAR_END_TIME_2, "TEXT"),
            (DatabaseColumn.NONWEAR_REASON_3, "TEXT"),
            (DatabaseColumn.NONWEAR_START_TIME_3, "TEXT"),
            (DatabaseColumn.NONWEAR_END_TIME_3, "TEXT"),
        ]

        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info("Added column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.warning("Failed to add column %s: %s", validated_column, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove nonwear columns (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 6 not fully supported - columns will remain")


class Migration007AddAutoCalculatedFlags(Migration):
    """Add auto-calculated flags for diary data columns."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=7, description="Add auto-calculated flags to diary_data")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add auto-calculated flag columns."""
        table_name = self._validate_table_name(DatabaseTable.DIARY_DATA)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            (DatabaseColumn.BEDTIME_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.WAKE_TIME_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.SLEEP_ONSET_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.SLEEP_OFFSET_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
            (DatabaseColumn.IN_BED_TIME_AUTO_CALCULATED, "INTEGER DEFAULT 0"),
        ]

        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info("Added column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.warning("Failed to add column %s: %s", validated_column, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove auto-calculated flag columns (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 7 not fully supported - columns will remain")


class Migration008AddDailySleepMarkersColumn(Migration):
    """Add daily_sleep_markers JSON column to sleep_metrics table."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=8, description="Add daily_sleep_markers JSON column to sleep_metrics")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add daily_sleep_markers column."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        column_name = self._validate_column_name(DatabaseColumn.DAILY_SLEEP_MARKERS)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT")
            logger.info("Added column %s to %s", column_name, table_name)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove daily_sleep_markers column (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 8 not fully supported - column will remain")


class Migration009AddSleepAlgorithmColumns(Migration):
    """Add generic sleep algorithm columns (name, onset, offset) to sleep_metrics."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=9, description="Add generic sleep algorithm columns to sleep_metrics")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add sleep algorithm columns."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            (DatabaseColumn.SLEEP_ALGORITHM_NAME, "TEXT DEFAULT 'sadeh_1994'"),
            (DatabaseColumn.SLEEP_ALGORITHM_ONSET, "INTEGER"),
            (DatabaseColumn.SLEEP_ALGORITHM_OFFSET, "INTEGER"),
        ]

        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info("Added column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.warning("Failed to add column %s: %s", validated_column, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove sleep algorithm columns (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 9 not fully supported - columns will remain")


class Migration010AddOverlappingNonwearColumns(Migration):
    """Add overlapping_nonwear_minutes_algorithm and overlapping_nonwear_minutes_sensor."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=10, description="Add overlapping nonwear minutes columns to sleep_metrics")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Add overlapping nonwear columns."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        # Get existing columns
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            (DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_ALGORITHM, "INTEGER"),
            (DatabaseColumn.OVERLAPPING_NONWEAR_MINUTES_SENSOR, "INTEGER"),
        ]

        for column_name, column_type in new_columns:
            validated_column = self._validate_column_name(column_name)
            if validated_column not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {validated_column} {column_type}")
                    logger.info("Added column %s to %s", validated_column, table_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logger.warning("Failed to add column %s: %s", validated_column, e)

    def down(self, conn: sqlite3.Connection) -> None:
        """Remove overlapping nonwear columns (not fully supported in SQLite)."""
        logger.warning("Rollback of migration 10 not fully supported - columns will remain")


class Migration011MigrateSadehToGeneric(Migration):
    """Migrate existing sadeh_onset/sadeh_offset to generic algorithm columns."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=11, description="Migrate Sadeh columns to generic algorithm columns")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Migrate Sadeh data to generic columns."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        sleep_algo_name_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_NAME)
        sleep_algo_onset_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_ONSET)
        sleep_algo_offset_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_OFFSET)
        sadeh_onset_col = self._validate_column_name(DatabaseColumn.SADEH_ONSET)
        sadeh_offset_col = self._validate_column_name(DatabaseColumn.SADEH_OFFSET)

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

        logger.info("Migrated Sadeh values to generic algorithm columns")

    def down(self, conn: sqlite3.Connection) -> None:
        """Reverse migration - copy back to Sadeh columns."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)

        sleep_algo_onset_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_ONSET)
        sleep_algo_offset_col = self._validate_column_name(DatabaseColumn.SLEEP_ALGORITHM_OFFSET)
        sadeh_onset_col = self._validate_column_name(DatabaseColumn.SADEH_ONSET)
        sadeh_offset_col = self._validate_column_name(DatabaseColumn.SADEH_OFFSET)

        # Copy back where algorithm was Sadeh
        conn.execute(f"""
            UPDATE {table_name}
            SET {sadeh_onset_col} = {sleep_algo_onset_col}
            WHERE {sadeh_onset_col} IS NULL
        """)

        conn.execute(f"""
            UPDATE {table_name}
            SET {sadeh_offset_col} = {sleep_algo_offset_col}
            WHERE {sadeh_offset_col} IS NULL
        """)


class Migration012MigrateLegacyAlgorithmType(Migration):
    """Migrate legacy algorithm_type values to new algorithm IDs."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=12, description="Migrate legacy algorithm_type values to new IDs")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Migrate legacy algorithm type values."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        algorithm_type_col = self._validate_column_name(DatabaseColumn.ALGORITHM_TYPE)

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

        logger.info("Migrated legacy algorithm_type values")

    def down(self, conn: sqlite3.Connection) -> None:
        """Reverse migration - restore legacy values."""
        table_name = self._validate_table_name(DatabaseTable.SLEEP_METRICS)
        algorithm_type_col = self._validate_column_name(DatabaseColumn.ALGORITHM_TYPE)

        # Reverse the mappings
        reverse_migrations = [
            ("'sadeh_1994_actilife'", "'Sadeh'"),
            ("'cole_kripke_1992_actilife'", "'Cole-Kripke'"),
            ("'manual'", "'Manual'"),
            ("'choi'", "'Choi'"),
        ]

        for new_value, old_value in reverse_migrations:
            conn.execute(f"""
                UPDATE {table_name}
                SET {algorithm_type_col} = {old_value}
                WHERE {algorithm_type_col} = {new_value}
            """)


class Migration013FixDiaryNapOccurred(Migration):
    """Fix data integrity: Update nap_occurred based on presence of nap times."""

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        super().__init__(version=13, description="Fix nap_occurred data integrity in diary_data")
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name

    def up(self, conn: sqlite3.Connection) -> None:
        """Fix nap_occurred flags."""
        table_name = self._validate_table_name(DatabaseTable.DIARY_DATA)

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

        logger.info("Fixed %d nap_occurred values", cursor.rowcount)

    def down(self, conn: sqlite3.Connection) -> None:
        """Cannot meaningfully reverse this data integrity fix."""
        logger.warning("Rollback of migration 13 (data fix) is not supported")


def get_all_migrations(
    validate_table_name: Callable[[str], str],
    validate_column_name: Callable[[str], str],
) -> list[Migration]:
    """
    Get all registered migrations in order.

    Args:
        validate_table_name: Callback to validate table names
        validate_column_name: Callback to validate column names

    Returns:
        List of all migrations

    """
    return [
        Migration001InitialSchema(validate_table_name, validate_column_name),
        Migration002AddPeriodMetricsJson(validate_table_name, validate_column_name),
        Migration003RenameAxisColumns(validate_table_name, validate_column_name),
        Migration004AddMissingAxisColumns(validate_table_name, validate_column_name),
        Migration005AddDiaryNapColumns(validate_table_name, validate_column_name),
        Migration006AddDiaryNonwearColumns(validate_table_name, validate_column_name),
        Migration007AddAutoCalculatedFlags(validate_table_name, validate_column_name),
        Migration008AddDailySleepMarkersColumn(validate_table_name, validate_column_name),
        Migration009AddSleepAlgorithmColumns(validate_table_name, validate_column_name),
        Migration010AddOverlappingNonwearColumns(validate_table_name, validate_column_name),
        Migration011MigrateSadehToGeneric(validate_table_name, validate_column_name),
        Migration012MigrateLegacyAlgorithmType(validate_table_name, validate_column_name),
        Migration013FixDiaryNapOccurred(validate_table_name, validate_column_name),
    ]
