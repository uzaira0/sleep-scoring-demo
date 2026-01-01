#!/usr/bin/env python3
"""
Command-line interface for database migration management.

Provides commands to check migration status, run migrations, and rollback if needed.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

from sleep_scoring_app.data.migrations import MigrationManager
from sleep_scoring_app.utils.resource_resolver import get_database_path

logger = logging.getLogger(__name__)


def validate_table_name(table_name: str) -> str:
    """Simple validation for table names (used by migration manager)."""
    return table_name


def validate_column_name(column_name: str) -> str:
    """Simple validation for column names (used by migration manager)."""
    return column_name


def get_migration_manager() -> MigrationManager:
    """Create and return a migration manager instance."""
    return MigrationManager(validate_table_name, validate_column_name)


def cmd_status(db_path: Path | None = None) -> None:
    """
    Show current database migration status.

    Args:
        db_path: Optional path to database file

    """
    if db_path is None:
        db_path = get_database_path()

    with sqlite3.connect(db_path) as conn:
        manager = get_migration_manager()
        status = manager.check_database_status(conn)

        if status["pending_migrations"]:
            for _migration in status["pending_migrations"]:
                pass
        else:
            pass

        if status["migration_history"]:
            for record in status["migration_history"][:10]:
                _success = "OK" if record["success"] else "FAILED"
                _exec_ms = record["execution_time_ms"]
        else:
            pass


def cmd_migrate(db_path: Path | None = None, target_version: int | None = None) -> None:
    """
    Run database migrations.

    Args:
        db_path: Optional path to database file
        target_version: Optional target version (default: latest)

    """
    if db_path is None:
        db_path = get_database_path()

    with sqlite3.connect(db_path) as conn:
        manager = get_migration_manager()

        current = manager.get_current_version(conn)
        latest = manager.get_latest_version()

        if target_version is None:
            target_version = latest

        if current == target_version:
            return

        if target_version > current:
            manager.migrate_to_version(conn, target_version)
        else:
            # Rollback
            response = input("Are you sure you want to rollback? (yes/no): ")
            if response.lower() != "yes":
                return

            manager.migrate_to_version(conn, target_version)


def cmd_history(db_path: Path | None = None, output_format: str = "table") -> None:
    """
    Show migration history.

    Args:
        db_path: Optional path to database file
        output_format: Output format ('table' or 'json')

    """
    if db_path is None:
        db_path = get_database_path()

    with sqlite3.connect(db_path) as conn:
        manager = get_migration_manager()
        history = manager.get_migration_history(conn)

        if output_format == "json":
            pass
        else:
            for record in history:
                _status = "SUCCESS" if record["success"] else "FAILED"
                _applied_at = record["applied_at"] or ""
                _exec_ms = record["execution_time_ms"] if record["execution_time_ms"] is not None else ""


def main() -> None:
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Database migration management tool")
    parser.add_argument("--db", type=Path, help="Path to database file (default: app database)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status command
    subparsers.add_parser("status", help="Show current migration status")

    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Run migrations")
    migrate_parser.add_argument("--to", type=int, help="Target version (default: latest)")

    # History command
    history_parser = subparsers.add_parser("history", help="Show migration history")
    history_parser.add_argument("--output-format", choices=["table", "json"], default="table", help="Output format")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "status":
            cmd_status(args.db)
        elif args.command == "migrate":
            cmd_migrate(args.db, args.to)
        elif args.command == "history":
            cmd_history(args.db, args.output_format)
    except Exception as e:
        logger.error("Command failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
