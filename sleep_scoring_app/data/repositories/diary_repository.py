"""Repository for diary data database operations."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DiaryRepository(BaseRepository):
    """Repository for diary data operations."""

    def save_diary_nap_periods(self, filename: str, participant_id: str, diary_date: str, nap_periods: list[dict[str, Any]]) -> bool:
        """Save nap periods for a diary entry."""
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(participant_id, min_length=1, name="participant_id")
        InputValidator.validate_string(diary_date, min_length=1, name="diary_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_NAP_PERIODS)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?
                """,
                    (filename, diary_date),
                )

                for i, nap_period in enumerate(nap_periods, 1):
                    if nap_period.get("start_time") or nap_period.get("end_time"):
                        duration_minutes = None
                        if nap_period.get("start_time") and nap_period.get("end_time"):
                            try:
                                from sleep_scoring_app.utils.calculations import calculate_duration_minutes_from_datetimes

                                start = datetime.strptime(nap_period["start_time"], "%H:%M")
                                end = datetime.strptime(nap_period["end_time"], "%H:%M")
                                duration_minutes = calculate_duration_minutes_from_datetimes(start, end)
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

        except sqlite3.Error as e:
            logger.exception("Database error saving nap periods for %s on %s", filename, diary_date)
            msg = f"Failed to save nap periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_INSERT_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error saving nap periods for %s on %s", filename, diary_date)
            msg = f"Unexpected error saving nap periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_INSERT_FAILED,
            ) from e

    def load_diary_nap_periods(self, filename: str, diary_date: str) -> list[dict[str, Any]]:
        """Load nap periods for a diary entry."""
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

        except sqlite3.Error as e:
            logger.exception("Database error loading nap periods for %s on %s", filename, diary_date)
            msg = f"Failed to load nap periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error loading nap periods for %s on %s", filename, diary_date)
            msg = f"Unexpected error loading nap periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def save_diary_nonwear_periods(self, filename: str, participant_id: str, diary_date: str, nonwear_periods: list[dict[str, Any]]) -> bool:
        """Save nonwear periods for a diary entry."""
        InputValidator.validate_string(filename, min_length=1, name="filename")
        InputValidator.validate_string(participant_id, min_length=1, name="participant_id")
        InputValidator.validate_string(diary_date, min_length=1, name="diary_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_NONWEAR_PERIODS)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    f"""
                    DELETE FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?
                """,
                    (filename, diary_date),
                )

                for i, nonwear_period in enumerate(nonwear_periods, 1):
                    if nonwear_period.get("start_time") or nonwear_period.get("end_time"):
                        duration_minutes = None
                        if nonwear_period.get("start_time") and nonwear_period.get("end_time"):
                            try:
                                from sleep_scoring_app.utils.calculations import calculate_duration_minutes_from_datetimes

                                start = datetime.strptime(nonwear_period["start_time"], "%H:%M")
                                end = datetime.strptime(nonwear_period["end_time"], "%H:%M")
                                duration_minutes = calculate_duration_minutes_from_datetimes(start, end)
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

        except sqlite3.Error as e:
            logger.exception("Database error saving nonwear periods for %s on %s", filename, diary_date)
            msg = f"Failed to save nonwear periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_INSERT_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error saving nonwear periods for %s on %s", filename, diary_date)
            msg = f"Unexpected error saving nonwear periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_INSERT_FAILED,
            ) from e

    def load_diary_nonwear_periods(self, filename: str, diary_date: str) -> list[dict[str, Any]]:
        """Load nonwear periods for a diary entry."""
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

        except sqlite3.Error as e:
            logger.exception("Database error loading nonwear periods for %s on %s", filename, diary_date)
            msg = f"Failed to load nonwear periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error loading nonwear periods for %s on %s", filename, diary_date)
            msg = f"Unexpected error loading nonwear periods for {filename} on {diary_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def clear_diary_data(self) -> int:
        """
        Clear all diary data from database.

        Returns:
            Total number of rows deleted across all diary tables.

        """
        tables_to_clear = [
            DatabaseTable.DIARY_DATA,
            DatabaseTable.DIARY_FILE_REGISTRY,
            DatabaseTable.DIARY_RAW_DATA,
            DatabaseTable.DIARY_NAP_PERIODS,
            DatabaseTable.DIARY_NONWEAR_PERIODS,
        ]

        total_deleted = 0

        try:
            with self._get_connection() as conn:
                for table in tables_to_clear:
                    table_name = self._validate_table_name(table)
                    cursor = conn.execute(f"DELETE FROM {table_name}")
                    total_deleted += cursor.rowcount

                conn.commit()
                logger.info("Cleared %s diary data records from all diary tables", total_deleted)
                return total_deleted

        except sqlite3.Error as e:
            logger.exception("Database error clearing diary data")
            msg = f"Failed to clear diary data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_DELETE_FAILED) from e

    def get_diary_nap_data_for_export(self, participant_key: str, analysis_date: str) -> dict[str, Any] | None:
        """
        Get diary nap data for a participant on a specific date for export.

        Args:
            participant_key: Participant key to match
            analysis_date: Analysis date string in YYYY-MM-DD format

        Returns:
            Dictionary with nap_occurred, nap_onset_time, nap_offset_time, etc., or None if not found

        """
        InputValidator.validate_string(participant_key, min_length=1, name="participant_key")
        InputValidator.validate_string(analysis_date, min_length=1, name="analysis_date")

        table_name = self._validate_table_name(DatabaseTable.DIARY_DATA)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""SELECT {self._validate_column_name(DatabaseColumn.NAP_OCCURRED)},
                              {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME)},
                              {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME)},
                              {self._validate_column_name(DatabaseColumn.NAP_ONSET_TIME_2)},
                              {self._validate_column_name(DatabaseColumn.NAP_OFFSET_TIME_2)}
                         FROM {table_name}
                         WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                           AND {self._validate_column_name(DatabaseColumn.DIARY_DATE)} = ?""",
                    (participant_key, analysis_date),
                )

                row = cursor.fetchone()

                if row:
                    return {
                        "nap_occurred": row[0],
                        "nap_onset_time": row[1],
                        "nap_offset_time": row[2],
                        "nap_onset_time_2": row[3],
                        "nap_offset_time_2": row[4],
                    }
                return None

        except sqlite3.Error as e:
            logger.exception("Database error getting diary nap data for participant_key %s on %s", participant_key, analysis_date)
            msg = f"Failed to get diary nap data for {participant_key} on {analysis_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting diary nap data for participant_key %s on %s", participant_key, analysis_date)
            msg = f"Unexpected error getting diary nap data for {participant_key} on {analysis_date}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
