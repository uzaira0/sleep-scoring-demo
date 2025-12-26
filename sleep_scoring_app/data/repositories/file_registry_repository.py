"""Repository for file registry database operations."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.constants import DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.config import DataConfig
from sleep_scoring_app.data.repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from datetime import date

logger = logging.getLogger(__name__)


class FileRegistryRepository(BaseRepository):
    """Repository for file registry operations."""

    def get_available_files(self) -> list[dict[str, Any]]:
        """Get list of available imported files with metadata."""
        table_name = self._validate_table_name(DatabaseTable.FILE_REGISTRY)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute(f"""
                    SELECT
                        {self._validate_column_name(DatabaseColumn.FILENAME)},
                        {self._validate_column_name(DatabaseColumn.ORIGINAL_PATH)},
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
                            "original_path": row[DatabaseColumn.ORIGINAL_PATH],
                            "participant_id": row[DatabaseColumn.PARTICIPANT_ID],
                            "participant_group": row[DatabaseColumn.PARTICIPANT_GROUP],
                            "participant_timepoint": row[DatabaseColumn.PARTICIPANT_TIMEPOINT],
                            "date_range_start": row[DatabaseColumn.DATE_RANGE_START],
                            "date_range_end": row[DatabaseColumn.DATE_RANGE_END],
                            "total_records": row[DatabaseColumn.TOTAL_RECORDS],
                            "status": row[DatabaseColumn.STATUS],
                            "import_date": row[DatabaseColumn.IMPORT_DATE],
                        },
                    )

                logger.debug("Found %s imported files", len(files))
                return files

        except sqlite3.Error as e:
            logger.exception("Database error getting available files")
            msg = f"Failed to retrieve file list: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting available files")
            msg = f"Unexpected error retrieving file list: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def get_file_date_ranges(self, filename: str) -> list[date]:
        """Get available date ranges for a specific file."""
        InputValidator.validate_string(filename, min_length=1, name="filename")
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
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
                        dates.append(date_obj)
                    except (ValueError, TypeError) as e:
                        logger.warning("Skipping invalid date: %s", e)
                        continue

                logger.debug("Found %s unique dates for %s", len(dates), filename)
                return dates

        except sqlite3.Error as e:
            logger.exception("Database error getting date ranges for %s", filename)
            msg = f"Failed to get date ranges for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting date ranges for %s", filename)
            msg = f"Unexpected error getting date ranges for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def get_all_file_date_ranges(self) -> dict[str, int]:
        """Get date ranges for ALL files in a single query - returns dict of filename -> date count."""
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

        except sqlite3.Error as e:
            logger.exception("Database error getting all file date ranges")
            msg = f"Failed to get all file date ranges: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting all file date ranges")
            msg = f"Unexpected error getting all file date ranges: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def get_all_file_date_ranges_batch(self) -> dict[str, tuple[str, str]]:
        """Get min/max date ranges for ALL files in a single query - returns dict of filename -> (start_date, end_date)."""
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
                    start_date = row[1]
                    end_date = row[2]
                    result[filename] = (start_date, end_date)

                logger.info("Batch loaded date ranges for %s files", len(result))
                return result

        except sqlite3.Error as e:
            logger.exception("Database error getting all file date ranges")
            msg = f"Failed to get file date ranges: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting all file date ranges")
            msg = f"Unexpected error getting file date ranges: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def get_import_statistics(self) -> dict[str, Any]:
        """Get comprehensive import statistics."""
        try:
            with self._get_connection() as conn:
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

                cursor = conn.execute(f"""
                    SELECT
                        COUNT(*) as total_activity_records,
                        COUNT(DISTINCT {self._validate_column_name(DatabaseColumn.FILENAME)}) as files_with_data,
                        MIN({self._validate_column_name(DatabaseColumn.TIMESTAMP)}) as earliest_data,
                        MAX({self._validate_column_name(DatabaseColumn.TIMESTAMP)}) as latest_data
                    FROM {self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)}
                """)

                activity_stats = cursor.fetchone()

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
                }

        except sqlite3.Error as e:
            logger.exception("Database error getting import statistics")
            msg = f"Failed to get import statistics: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting import statistics")
            msg = f"Unexpected error getting import statistics: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def check_file_exists_by_participant_key(self, participant_key: str) -> tuple[bool, str | None, str | None, str | None]:
        """
        Check if a file exists for a given participant key.

        Returns:
            Tuple of (exists, file_hash, status, existing_filename)

        """
        InputValidator.validate_string(participant_key, min_length=1, name="participant_key")
        table_name = self._validate_table_name(DatabaseTable.FILE_REGISTRY)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT {self._validate_column_name(DatabaseColumn.FILE_HASH)},
                           {self._validate_column_name(DatabaseColumn.STATUS)},
                           {self._validate_column_name(DatabaseColumn.FILENAME)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.PARTICIPANT_KEY)} = ?
                    """,
                    (participant_key,),
                )
                result = cursor.fetchone()

                if result is None:
                    return False, None, None, None

                return True, result[0], result[1], result[2]

        except sqlite3.Error as e:
            logger.exception("Database error checking file existence for participant_key %s", participant_key)
            msg = f"Failed to check file existence: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error checking file existence for participant_key %s", participant_key)
            msg = f"Unexpected error checking file existence: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def get_available_dates_for_file(self, filename: str) -> list[str]:
        """
        Get available analysis dates for a specific file from sleep_markers_extended.

        Returns:
            List of date strings (YYYY-MM-DD format) sorted in ascending order

        """
        InputValidator.validate_string(filename, min_length=1, name="filename")
        table_name = self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)}
                    FROM {table_name}
                    WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?
                    ORDER BY {self._validate_column_name(DatabaseColumn.ANALYSIS_DATE)}
                    """,
                    (filename,),
                )

                dates = [row[0] for row in cursor.fetchall()]
                logger.debug("Found %s available dates for %s", len(dates), filename)
                return dates

        except sqlite3.Error as e:
            logger.exception("Database error getting available dates for %s", filename)
            msg = f"Failed to get available dates for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting available dates for %s", filename)
            msg = f"Unexpected error getting available dates for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def get_import_summary(self) -> dict[str, Any]:
        """
        Get summary of imported files for import status display.

        Returns:
            Dictionary with total_files, total_records, imported_files, error_files counts

        """
        from sleep_scoring_app.core.constants import ImportStatus

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_files,
                        SUM({self._validate_column_name(DatabaseColumn.TOTAL_RECORDS)}) as total_records,
                        COUNT(CASE WHEN {self._validate_column_name(DatabaseColumn.STATUS)} = ? THEN 1 END) as imported_files,
                        COUNT(CASE WHEN {self._validate_column_name(DatabaseColumn.STATUS)} = ? THEN 1 END) as error_files
                    FROM {self._validate_table_name(DatabaseTable.FILE_REGISTRY)}
                """,
                    (ImportStatus.IMPORTED, ImportStatus.ERROR),
                )

                result = cursor.fetchone()
                if result:
                    return {
                        "total_files": result[0],
                        "total_records": result[1] or 0,
                        "imported_files": result[2],
                        "error_files": result[3],
                    }
                return {
                    "total_files": 0,
                    "total_records": 0,
                    "imported_files": 0,
                    "error_files": 0,
                }

        except sqlite3.Error as e:
            logger.exception("Database error getting import summary")
            msg = f"Failed to get import summary: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error getting import summary")
            msg = f"Unexpected error getting import summary: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def delete_imported_file(self, filename: str) -> bool:
        """Delete an imported file and all its associated data (cascade delete)."""
        InputValidator.validate_string(filename, min_length=1, name="filename")

        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN TRANSACTION")

                try:
                    deleted_counts: dict[str, int] = {}

                    # Delete from all related tables (cascade delete)
                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.SLEEP_MARKERS_EXTENDED)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["markers_extended"] = cursor.rowcount

                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.SLEEP_METRICS)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["sleep_metrics"] = cursor.rowcount

                    if DataConfig.ENABLE_AUTOSAVE:
                        cursor = conn.execute(
                            f"DELETE FROM {self._validate_table_name(DatabaseTable.AUTOSAVE_METRICS)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                            (filename,),
                        )
                        deleted_counts["autosave_metrics"] = cursor.rowcount

                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.NONWEAR_SENSOR_PERIODS)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["nonwear_periods"] = cursor.rowcount

                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.MANUAL_NWT_MARKERS)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["manual_nwt"] = cursor.rowcount

                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.CHOI_ALGORITHM_PERIODS)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["choi_periods"] = cursor.rowcount

                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["activity_data"] = cursor.rowcount

                    cursor = conn.execute(
                        f"DELETE FROM {self._validate_table_name(DatabaseTable.FILE_REGISTRY)} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                    deleted_counts["file_registry"] = cursor.rowcount

                    conn.commit()

                    non_zero = {k: v for k, v in deleted_counts.items() if v > 0}
                    logger.info(
                        "Cascade deleted %s: %s",
                        filename,
                        ", ".join(f"{v} {k}" for k, v in non_zero.items()) if non_zero else "no records found",
                    )
                    return True

                except sqlite3.Error as e:
                    conn.rollback()
                    logger.exception("Database error during cascade delete for %s", filename)
                    msg = f"Failed to cascade delete {filename}: {e}"
                    raise DatabaseError(
                        msg,
                        ErrorCodes.DB_DELETE_FAILED,
                    ) from e
                except Exception as e:
                    conn.rollback()
                    logger.exception("Unexpected error during cascade delete for %s", filename)
                    msg = f"Unexpected error deleting {filename}: {e}"
                    raise DatabaseError(
                        msg,
                        ErrorCodes.DB_DELETE_FAILED,
                    ) from e

        except DatabaseError:
            raise
        except sqlite3.Error as e:
            logger.exception("Database connection failed when deleting %s", filename)
            msg = f"Connection failed when deleting {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_CONNECTION_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected connection error when deleting %s", filename)
            msg = f"Unexpected connection error deleting {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_CONNECTION_FAILED,
            ) from e
