"""
Tests for database migrations.

Tests migration execution, ordering, and idempotency.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.data.migrations import Migration, MigrationManager
from sleep_scoring_app.data.migrations_registry import (
    Migration001InitialSchema,
    Migration002AddPeriodMetricsJson,
    Migration003RenameAxisColumns,
    Migration004AddMissingAxisColumns,
    Migration005AddDiaryNapColumns,
    Migration006AddDiaryNonwearColumns,
    Migration007AddAutoCalculatedFlags,
    Migration008AddDailySleepMarkersColumn,
    Migration009AddSleepAlgorithmColumns,
    Migration010AddOverlappingNonwearColumns,
    Migration011MigrateSadehToGeneric,
    Migration012MigrateLegacyAlgorithmType,
    Migration013FixDiaryNapOccurred,
    get_all_migrations,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path() -> Path:
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def valid_tables() -> set[str]:
    """Set of valid table names for testing."""
    return {
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


@pytest.fixture
def valid_columns() -> set[str]:
    """Set of valid column names for testing - includes ALL columns from DatabaseColumn."""
    # Return all DatabaseColumn values to avoid validation errors
    return {getattr(DatabaseColumn, attr) for attr in dir(DatabaseColumn) if not attr.startswith("_")}


@pytest.fixture
def validate_table_name(valid_tables: set[str]) -> Callable[[str], str]:
    """Create table name validator."""

    def validator(name: str) -> str:
        if name not in valid_tables:
            raise ValueError(f"Invalid table name: {name}")
        return name

    return validator


@pytest.fixture
def validate_column_name(valid_columns: set[str]) -> Callable[[str], str]:
    """Create column name validator."""

    def validator(name: str) -> str:
        if name not in valid_columns:
            raise ValueError(f"Invalid column name: {name}")
        return name

    return validator


@pytest.fixture
def db_connection(temp_db_path: Path) -> sqlite3.Connection:
    """Create a database connection."""
    conn = sqlite3.connect(temp_db_path)
    yield conn
    conn.close()


# ============================================================================
# Test Migration Base Class
# ============================================================================


class TestMigrationBaseClass:
    """Tests for Migration base class - tested via concrete implementations."""

    def test_migration_has_version(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Migration has version attribute."""
        migration = Migration001InitialSchema(validate_table_name, validate_column_name)
        assert migration.version == 1

    def test_migration_has_description(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Migration has description attribute."""
        migration = Migration001InitialSchema(validate_table_name, validate_column_name)
        assert "Initial" in migration.description

    def test_migration_comparison(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Migrations can be compared by version."""
        m1 = Migration001InitialSchema(validate_table_name, validate_column_name)
        m2 = Migration002AddPeriodMetricsJson(validate_table_name, validate_column_name)

        assert m1.version < m2.version
        assert m2.version > m1.version
        assert m1 != m2


# ============================================================================
# Test Get All Migrations
# ============================================================================


class TestGetAllMigrations:
    """Tests for get_all_migrations function."""

    def test_returns_list_of_migrations(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Returns list of migration instances."""
        migrations = get_all_migrations(validate_table_name, validate_column_name)

        assert isinstance(migrations, list)
        assert len(migrations) > 0
        assert all(isinstance(m, Migration) for m in migrations)

    def test_migrations_are_ordered_by_version(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Migrations are returned in version order."""
        migrations = get_all_migrations(validate_table_name, validate_column_name)

        versions = [m.version for m in migrations]
        assert versions == sorted(versions)
        assert versions == list(range(1, len(migrations) + 1))

    def test_has_expected_number_of_migrations(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Has expected number of migrations (13 as of current)."""
        migrations = get_all_migrations(validate_table_name, validate_column_name)

        assert len(migrations) == 13


# ============================================================================
# Test Individual Migrations
# ============================================================================


class TestMigration001:
    """Tests for initial schema migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration001InitialSchema(validate_table_name, validate_column_name)

        assert migration.version == 1
        assert "Initial" in migration.description

    def test_up_creates_tables(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Up method creates tables."""
        migration = Migration001InitialSchema(validate_table_name, validate_column_name)

        migration.up(db_connection)
        db_connection.commit()

        # Check that at least one table was created
        cursor = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert len(tables) > 0


class TestMigration002:
    """Tests for period_metrics_json column migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration002AddPeriodMetricsJson(validate_table_name, validate_column_name)

        assert migration.version == 2
        assert "period_metrics_json" in migration.description


class TestMigration003:
    """Tests for axis column rename migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration003RenameAxisColumns(validate_table_name, validate_column_name)

        assert migration.version == 3
        assert "axis" in migration.description.lower()


class TestMigration004:
    """Tests for missing axis columns migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration004AddMissingAxisColumns(validate_table_name, validate_column_name)

        assert migration.version == 4


class TestMigration005:
    """Tests for diary nap columns migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration005AddDiaryNapColumns(validate_table_name, validate_column_name)

        assert migration.version == 5
        assert "nap" in migration.description.lower()


class TestMigration006:
    """Tests for diary nonwear columns migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration006AddDiaryNonwearColumns(validate_table_name, validate_column_name)

        assert migration.version == 6
        assert "nonwear" in migration.description.lower()


class TestMigration007:
    """Tests for auto-calculated flags migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration007AddAutoCalculatedFlags(validate_table_name, validate_column_name)

        assert migration.version == 7
        assert "auto" in migration.description.lower()


class TestMigration008:
    """Tests for daily_sleep_markers column migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration008AddDailySleepMarkersColumn(validate_table_name, validate_column_name)

        assert migration.version == 8
        assert "daily_sleep_markers" in migration.description


class TestMigration009:
    """Tests for sleep algorithm columns migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration009AddSleepAlgorithmColumns(validate_table_name, validate_column_name)

        assert migration.version == 9
        assert "algorithm" in migration.description.lower()


class TestMigration010:
    """Tests for overlapping nonwear columns migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration010AddOverlappingNonwearColumns(validate_table_name, validate_column_name)

        assert migration.version == 10
        assert "overlapping" in migration.description.lower()


class TestMigration011:
    """Tests for Sadeh to generic migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration011MigrateSadehToGeneric(validate_table_name, validate_column_name)

        assert migration.version == 11
        assert "Sadeh" in migration.description


class TestMigration012:
    """Tests for legacy algorithm type migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration012MigrateLegacyAlgorithmType(validate_table_name, validate_column_name)

        assert migration.version == 12
        assert "legacy" in migration.description.lower()


class TestMigration013:
    """Tests for nap_occurred fix migration."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates migration instance."""
        migration = Migration013FixDiaryNapOccurred(validate_table_name, validate_column_name)

        assert migration.version == 13
        assert "nap_occurred" in migration.description


# ============================================================================
# Test Migration Idempotency
# ============================================================================


class TestMigrationIdempotency:
    """Tests that migrations can be run multiple times safely."""

    def test_migration002_idempotent(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Migration 2 can be run multiple times."""
        # First run initial schema
        m1 = Migration001InitialSchema(validate_table_name, validate_column_name)
        m1.up(db_connection)
        db_connection.commit()

        # Run migration 2 twice
        m2 = Migration002AddPeriodMetricsJson(validate_table_name, validate_column_name)
        m2.up(db_connection)
        db_connection.commit()

        # Should not raise on second run
        m2.up(db_connection)
        db_connection.commit()


# ============================================================================
# Test Migration Manager
# ============================================================================


class TestMigrationManager:
    """Tests for MigrationManager class."""

    def test_creates_instance(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Creates manager instance."""
        manager = MigrationManager(validate_table_name, validate_column_name)
        assert manager is not None

    def test_get_current_version_empty_db(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Returns 0 for empty database."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        version = manager.get_current_version(db_connection)

        assert version == 0

    def test_get_latest_version(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """Returns latest migration version."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        latest = manager.get_latest_version()

        assert latest == 13  # Current number of migrations

    def test_get_pending_migrations_empty_db(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Returns all migrations as pending for empty db."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        pending = manager.get_pending_migrations(db_connection)

        # All migrations should be pending on empty db
        assert len(pending) == 13

    def test_migrate_to_latest(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Migrates database to latest version."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        manager.migrate_to_latest(db_connection)

        current = manager.get_current_version(db_connection)
        assert current == 13

    def test_get_migration_history(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Returns migration history."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        # Run first migration
        manager.migrate_to_latest(db_connection)

        history = manager.get_migration_history(db_connection)

        assert len(history) == 13
        assert history[0]["version"] == 13  # Most recent first
        assert history[0]["success"] is True

    def test_check_database_status(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Returns comprehensive database status."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        # Before migration
        status = manager.check_database_status(db_connection)

        assert status["current_version"] == 0
        assert status["latest_version"] == 13
        assert status["is_up_to_date"] is False
        assert len(status["pending_migrations"]) == 13

    def test_migrate_to_specific_version(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """Migrates to specific version."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        # Migrate to version 5
        manager.migrate_to_version(db_connection, 5)

        current = manager.get_current_version(db_connection)
        assert current == 5

    def test_no_pending_after_migrate(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
        db_connection: sqlite3.Connection,
    ) -> None:
        """No pending migrations after migrate_to_latest."""
        manager = MigrationManager(validate_table_name, validate_column_name)

        manager.migrate_to_latest(db_connection)
        pending = manager.get_pending_migrations(db_connection)

        assert len(pending) == 0
