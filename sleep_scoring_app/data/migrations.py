#!/usr/bin/env python3
"""
Database Migration System for Sleep Scoring Application.

Provides versioned schema migrations with up/down capability and audit trail.
Replaces scattered _migrate_* and _add_column_if_not_exists calls with
a structured migration system.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration(ABC):
    """Base class for database migrations."""

    version: int
    description: str

    @abstractmethod
    def up(self, conn: sqlite3.Connection) -> None:
        """Apply migration (forward)."""
        ...

    @abstractmethod
    def down(self, conn: sqlite3.Connection) -> None:
        """Revert migration (backward)."""
        ...


class MigrationManager:
    """
    Manages database schema migrations with version tracking.

    Provides:
    - Automatic migration to latest version on database open
    - Version tracking via schema_version table
    - Audit trail of applied migrations
    - Reversible migrations (up/down)
    - Safe migration execution with transaction rollback
    """

    def __init__(
        self,
        validate_table_name: Callable[[str], str],
        validate_column_name: Callable[[str], str],
    ) -> None:
        """
        Initialize migration manager with validation callbacks.

        Args:
            validate_table_name: Callback to validate table names
            validate_column_name: Callback to validate column names

        """
        self._validate_table_name = validate_table_name
        self._validate_column_name = validate_column_name
        self._migrations: list[Migration] = []
        self._register_migrations()

    def _register_migrations(self) -> None:
        """Register all migrations in version order."""
        # Import migrations here to avoid circular imports
        from sleep_scoring_app.data.migrations_registry import get_all_migrations

        self._migrations = sorted(get_all_migrations(self._validate_table_name, self._validate_column_name), key=lambda m: m.version)

    def _ensure_schema_version_table(self, conn: sqlite3.Connection) -> None:
        """Create schema_version table if it doesn't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                execution_time_ms INTEGER,
                success INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Create index for quick version lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_schema_version_applied
            ON schema_version(applied_at)
        """)

    def get_current_version(self, conn: sqlite3.Connection) -> int:
        """
        Get current database schema version.

        Args:
            conn: SQLite connection

        Returns:
            Current schema version (0 if no migrations applied)

        """
        self._ensure_schema_version_table(conn)

        cursor = conn.execute("""
            SELECT MAX(version)
            FROM schema_version
            WHERE success = 1
        """)
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0

    def get_latest_version(self) -> int:
        """Get the latest available migration version."""
        return max((m.version for m in self._migrations), default=0)

    def get_pending_migrations(self, conn: sqlite3.Connection) -> list[Migration]:
        """
        Get list of pending migrations.

        Args:
            conn: SQLite connection

        Returns:
            List of migrations that haven't been applied yet

        """
        current = self.get_current_version(conn)
        return [m for m in self._migrations if m.version > current]

    def migrate_to_latest(self, conn: sqlite3.Connection) -> None:
        """
        Migrate database to latest schema version.

        Args:
            conn: SQLite connection

        Raises:
            sqlite3.Error: If migration fails

        """
        current = self.get_current_version(conn)
        latest = self.get_latest_version()

        if current == latest:
            logger.info("Database schema is up to date (version %d)", current)
            return

        logger.info("Migrating database from version %d to %d", current, latest)

        for migration in self.get_pending_migrations(conn):
            self.run_migration(conn, migration)

        logger.info("Database migration complete. Current version: %d", self.get_current_version(conn))

    def run_migration(self, conn: sqlite3.Connection, migration: Migration) -> None:
        """
        Run a single migration with transaction safety.

        Args:
            conn: SQLite connection
            migration: Migration to run

        Raises:
            sqlite3.Error: If migration fails

        """
        start_time = datetime.now()
        logger.info("Applying migration %d: %s", migration.version, migration.description)

        try:
            # Execute migration
            migration.up(conn)

            # Record success
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            conn.execute(
                """
                INSERT INTO schema_version (version, description, applied_at, execution_time_ms, success)
                VALUES (?, ?, ?, ?, 1)
                """,
                (migration.version, migration.description, datetime.now().isoformat(), execution_time_ms),
            )

            conn.commit()
            logger.info("Migration %d completed in %d ms", migration.version, execution_time_ms)

        except Exception as e:
            # Record failure
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            conn.execute(
                """
                INSERT INTO schema_version (version, description, applied_at, execution_time_ms, success)
                VALUES (?, ?, ?, ?, 0)
                """,
                (migration.version, f"FAILED: {migration.description}", datetime.now().isoformat(), execution_time_ms),
            )
            conn.commit()

            logger.exception("Migration %d failed: %s", migration.version, e)
            raise

    def rollback_migration(self, conn: sqlite3.Connection, migration: Migration) -> None:
        """
        Rollback a single migration.

        Args:
            conn: SQLite connection
            migration: Migration to rollback

        Raises:
            sqlite3.Error: If rollback fails

        """
        start_time = datetime.now()
        logger.info("Rolling back migration %d: %s", migration.version, migration.description)

        try:
            # Execute rollback
            migration.down(conn)

            # Remove from schema_version
            conn.execute(
                """
                DELETE FROM schema_version
                WHERE version = ?
                """,
                (migration.version,),
            )

            conn.commit()
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.info("Migration %d rolled back in %d ms", migration.version, execution_time_ms)

        except Exception as e:
            logger.exception("Rollback of migration %d failed: %s", migration.version, e)
            raise

    def migrate_to_version(self, conn: sqlite3.Connection, target_version: int) -> None:
        """
        Migrate database to specific version (forward or backward).

        Args:
            conn: SQLite connection
            target_version: Target schema version

        Raises:
            ValueError: If target version is invalid
            sqlite3.Error: If migration fails

        """
        current = self.get_current_version(conn)

        if target_version == current:
            logger.info("Database is already at version %d", current)
            return

        if target_version > current:
            # Forward migration
            migrations_to_apply = [m for m in self._migrations if current < m.version <= target_version]
            for migration in migrations_to_apply:
                self.run_migration(conn, migration)
        else:
            # Backward migration (rollback)
            migrations_to_rollback = [m for m in reversed(self._migrations) if target_version < m.version <= current]
            for migration in migrations_to_rollback:
                self.rollback_migration(conn, migration)

    def get_migration_history(self, conn: sqlite3.Connection) -> list[dict[str, any]]:
        """
        Get migration history with execution details.

        Args:
            conn: SQLite connection

        Returns:
            List of migration history records

        """
        self._ensure_schema_version_table(conn)

        cursor = conn.execute("""
            SELECT version, description, applied_at, execution_time_ms, success
            FROM schema_version
            ORDER BY version DESC
        """)

        return [
            {
                "version": row[0],
                "description": row[1],
                "applied_at": row[2],
                "execution_time_ms": row[3],
                "success": bool(row[4]),
            }
            for row in cursor.fetchall()
        ]

    def check_database_status(self, conn: sqlite3.Connection) -> dict[str, any]:
        """
        Get comprehensive database migration status.

        Args:
            conn: SQLite connection

        Returns:
            Dictionary with migration status information

        """
        current_version = self.get_current_version(conn)
        latest_version = self.get_latest_version()
        pending = self.get_pending_migrations(conn)

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "is_up_to_date": current_version == latest_version,
            "pending_migrations": [{"version": m.version, "description": m.description} for m in pending],
            "migration_history": self.get_migration_history(conn),
        }
