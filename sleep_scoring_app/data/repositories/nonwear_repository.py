"""Repository for nonwear database operations."""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.dataclasses import DailyNonwearMarkers, ManualNonwearPeriod
from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class NonwearRepository(BaseRepository):
    """Repository for nonwear operations (sensor, algorithm, manual)."""

    def save_manual_nonwear_markers(
        self,
        filename: str,
        participant_id: str,
        sleep_date: str,
        daily_nonwear_markers: DailyNonwearMarkers,
    ) -> bool:
        """Save manual nonwear markers to database."""
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(participant_id, min_length=1, name="participant_id")
        InputValidator.validate_string(sleep_date, min_length=1, name="sleep_date")

        table_name = self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.SLEEP_DATE)} = ?
                """,
                    (filename, sleep_date),
                )

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

        except sqlite3.Error as e:
            logger.exception(
                "Database error saving manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Failed to save manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_INSERT_FAILED,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error saving manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Unexpected error saving manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_INSERT_FAILED,
            ) from e

    def load_manual_nonwear_markers(
        self,
        filename: str,
        sleep_date: str,
    ) -> DailyNonwearMarkers:
        """Load manual nonwear markers from database."""
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

        except sqlite3.Error as e:
            logger.exception(
                "Database error loading manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Failed to load manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error loading manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Unexpected error loading manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def delete_manual_nonwear_markers(
        self,
        filename: str,
        sleep_date: str,
    ) -> bool:
        """Delete all manual nonwear markers for a specific file and date."""
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

        except sqlite3.Error as e:
            logger.exception(
                "Database error deleting manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Failed to delete manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_DELETE_FAILED,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error deleting manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Unexpected error deleting manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_DELETE_FAILED,
            ) from e

    def has_manual_nonwear_markers(
        self,
        filename: str,
        sleep_date: str,
    ) -> bool:
        """Check if there are any manual nonwear markers for a specific file and date."""
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

        except sqlite3.Error as e:
            logger.exception(
                "Database error checking manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Failed to check manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error checking manual nonwear markers for %s on %s",
                filename,
                sleep_date,
            )
            msg = f"Unexpected error checking manual nonwear markers for {filename} on {sleep_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def clear_nwt_data(self) -> int:
        """
        Clear all NWT sensor data from database.

        Returns:
            Total number of rows deleted across all NWT tables.

        """
        tables_to_clear = [
            DatabaseTable.NONWEAR_SENSOR_PERIODS,
            DatabaseTable.CHOI_ALGORITHM_PERIODS,
            DatabaseTable.MANUAL_NWT_MARKERS,
        ]

        total_deleted = 0

        try:
            with self._get_connection() as conn:
                for table in tables_to_clear:
                    table_name = self._validate_table_name(table)
                    cursor = conn.execute(f"DELETE FROM {table_name}")
                    total_deleted += cursor.rowcount

                conn.commit()
                logger.info("Cleared %s NWT data records from all nonwear tables", total_deleted)
                return total_deleted

        except sqlite3.Error as e:
            logger.exception("Database error clearing NWT data")
            msg = f"Failed to clear NWT data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_DELETE_FAILED) from e
