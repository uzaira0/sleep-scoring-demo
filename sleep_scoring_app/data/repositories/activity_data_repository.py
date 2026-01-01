"""Repository for raw activity data database operations."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from sleep_scoring_app.core.constants import ActivityDataPreference, DatabaseColumn, DatabaseTable
from sleep_scoring_app.core.exceptions import DatabaseError, ErrorCodes
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ActivityDataRepository(BaseRepository):
    """Repository for raw activity data operations."""

    def load_raw_activity_data(
        self,
        filename: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        activity_column: ActivityDataPreference = ActivityDataPreference.VECTOR_MAGNITUDE,
    ) -> tuple[list[datetime], list[float]]:
        """Load raw activity data from database for visualization."""
        InputValidator.validate_string(filename, min_length=1, name="filename")
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                if activity_column == ActivityDataPreference.VECTOR_MAGNITUDE:
                    activity_col = DatabaseColumn.VECTOR_MAGNITUDE
                elif activity_column == ActivityDataPreference.AXIS_X:
                    activity_col = DatabaseColumn.AXIS_X
                elif activity_column == ActivityDataPreference.AXIS_Z:
                    activity_col = DatabaseColumn.AXIS_Z
                else:  # ActivityDataPreference.AXIS_Y
                    activity_col = DatabaseColumn.AXIS_Y

                # Use COALESCE to replace NULL values with 0.0 - prevents row skipping
                # which caused alignment bugs between different column loads
                activity_col_name = self._validate_column_name(activity_col)
                base_query = f"""
                    SELECT {self._validate_column_name(DatabaseColumn.TIMESTAMP)},
                           COALESCE({activity_col_name}, 0.0) as activity_value
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
                    # Parse timestamp first - if this fails, skip the row entirely
                    try:
                        timestamp_str = row[DatabaseColumn.TIMESTAMP]
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, TypeError) as e:
                        logger.warning("Invalid timestamp in row, skipping: %s", e)
                        continue

                    # Parse activity value - if this fails, use 0.0 to prevent alignment bugs
                    try:
                        # Use aliased column name from COALESCE - guaranteed non-NULL
                        activity = max(0.0, float(row["activity_value"]))
                    except (ValueError, TypeError) as e:
                        logger.warning("Invalid activity value in row, using 0.0: %s", e)
                        activity = 0.0

                    timestamps.append(timestamp)
                    activities.append(activity)

                logger.debug("Loaded %s activity data points for %s", len(timestamps), filename)
                return timestamps, activities

        except sqlite3.Error as e:
            logger.exception("Database error loading raw activity data for %s", filename)
            msg = f"Failed to load activity data for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error loading raw activity data for %s", filename)
            msg = f"Unexpected error loading activity data for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def load_all_activity_columns(
        self,
        filename: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, list]:
        """
        Load ALL activity columns in ONE query with unified timestamps.

        This is the SINGLE SOURCE OF TRUTH for activity data loading.
        All columns share the SAME timestamps, preventing alignment bugs.

        Returns:
            Dictionary with keys: 'timestamps', 'axis_y', 'axis_x', 'axis_z', 'vector_magnitude'
            All lists have the SAME length (guaranteed).
            NULL values are replaced with 0.0 to prevent row skipping.

        """
        InputValidator.validate_string(filename, min_length=1, name="filename")
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                # Load ALL columns in ONE query - no row skipping!
                base_query = f"""
                    SELECT {self._validate_column_name(DatabaseColumn.TIMESTAMP)},
                           COALESCE({self._validate_column_name(DatabaseColumn.AXIS_Y)}, 0.0) as axis_y,
                           COALESCE({self._validate_column_name(DatabaseColumn.AXIS_X)}, 0.0) as axis_x,
                           COALESCE({self._validate_column_name(DatabaseColumn.AXIS_Z)}, 0.0) as axis_z,
                           COALESCE({self._validate_column_name(DatabaseColumn.VECTOR_MAGNITUDE)}, 0.0) as vector_magnitude
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

                result: dict[str, list] = {
                    "timestamps": [],
                    "axis_y": [],
                    "axis_x": [],
                    "axis_z": [],
                    "vector_magnitude": [],
                }

                for row in cursor:
                    try:
                        timestamp_str = row[DatabaseColumn.TIMESTAMP]
                        timestamp = datetime.fromisoformat(timestamp_str)

                        result["timestamps"].append(timestamp)
                        result["axis_y"].append(max(0.0, float(row["axis_y"])))
                        result["axis_x"].append(max(0.0, float(row["axis_x"])))
                        result["axis_z"].append(max(0.0, float(row["axis_z"])))
                        result["vector_magnitude"].append(max(0.0, float(row["vector_magnitude"])))

                    except (ValueError, TypeError) as e:
                        # Log but DON'T skip - use 0.0 for invalid values
                        logger.warning("Invalid data in row, using 0.0: %s", e)
                        if result["timestamps"]:  # Only if we have a valid timestamp
                            result["axis_y"].append(0.0)
                            result["axis_x"].append(0.0)
                            result["axis_z"].append(0.0)
                            result["vector_magnitude"].append(0.0)

                logger.info(
                    "Loaded unified activity data for %s: %d rows (all columns aligned)",
                    filename,
                    len(result["timestamps"]),
                )
                return result

        except sqlite3.Error as e:
            logger.exception("Database error loading unified activity data for %s", filename)
            msg = f"Failed to load unified activity data for {filename}: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_QUERY_FAILED) from e

    def get_available_activity_columns(self, filename: str) -> list[ActivityDataPreference]:
        """Check which activity columns have non-null data for a file."""
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

        except sqlite3.Error as e:
            logger.exception("Database error checking available activity columns for %s", filename)
            msg = f"Failed to check available activity columns for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e
        except Exception as e:
            logger.exception("Unexpected error checking available activity columns for %s", filename)
            msg = f"Unexpected error checking available activity columns for {filename}: {e}"
            raise DatabaseError(
                msg,
                ErrorCodes.DB_QUERY_FAILED,
            ) from e

    def clear_activity_data(self, filename: str | None = None) -> int:
        """
        Clear raw activity data from database.

        Args:
            filename: Optional filename to clear data for. If None, clears all activity data.

        Returns:
            Number of rows deleted.

        """
        table_name = self._validate_table_name(DatabaseTable.RAW_ACTIVITY_DATA)

        try:
            with self._get_connection() as conn:
                if filename:
                    InputValidator.validate_string(filename, min_length=1, name="filename")
                    cursor = conn.execute(
                        f"DELETE FROM {table_name} WHERE {self._validate_column_name(DatabaseColumn.FILENAME)} = ?",
                        (filename,),
                    )
                else:
                    cursor = conn.execute(f"DELETE FROM {table_name}")

                deleted_count = cursor.rowcount
                conn.commit()
                logger.info("Cleared %s activity data records%s", deleted_count, f" for {filename}" if filename else "")
                return deleted_count

        except sqlite3.Error as e:
            logger.exception("Database error clearing activity data")
            msg = f"Failed to clear activity data: {e}"
            raise DatabaseError(msg, ErrorCodes.DB_DELETE_FAILED) from e
