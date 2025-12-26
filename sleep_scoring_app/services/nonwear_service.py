#!/usr/bin/env python3
"""
Nonwear Sensor Data Service for Sleep Scoring Application
Handles loading and processing of nonwear time (NWT) sensor data and Choi algorithm results.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from sleep_scoring_app.core.constants import (
    DatabaseColumn,
    DatabaseTable,
    NonwearDataSource,
)
from sleep_scoring_app.core.dataclasses import NonwearPeriod
from sleep_scoring_app.core.exceptions import (
    DataLoadingError,
    ErrorCodes,
)
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.database import DatabaseManager

if TYPE_CHECKING:
    from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class NonwearDataService:
    """Service for loading and managing nonwear sensor data."""

    def __init__(self, database_manager: DatabaseManager = None) -> None:
        self.db_manager = database_manager or DatabaseManager()
        self.data_base_path = None  # Will be set when data folder is provided

    def find_nonwear_sensor_files(self, data_folder: Path) -> list[Path]:
        """Find all nonwear sensor files in the data folder."""
        try:
            # Look for nonwear files directly in the data folder
            # No hardcoded subdirectory - use the actual data folder provided
            if not data_folder.exists():
                logger.info("Data folder does not exist: %s", data_folder)
                return []

            # Find all nonwear period files in the data folder
            pattern = "*_nonwear_periods.csv"
            nonwear_files = list(data_folder.glob(pattern))

            logger.info("Found %d nonwear sensor files", len(nonwear_files))
            return nonwear_files

        except Exception:
            logger.exception("Error finding nonwear sensor files")
            return []

    def find_choi_algorithm_files(self, data_folder: Path) -> list[Path]:
        """Find all Choi algorithm result files in the data folder."""
        try:
            # Look for Choi result files directly in the data folder
            # No hardcoded subdirectory - use the actual data folder provided
            if not data_folder.exists():
                logger.info("Data folder does not exist: %s", data_folder)
                return []

            # Find all Choi result files in the data folder
            pattern = "*60sec_choi.csv"
            choi_files = list(data_folder.glob(pattern))

            logger.info("Found %d Choi algorithm files", len(choi_files))
            return choi_files

        except Exception:
            logger.exception("Error finding Choi algorithm files")
            return []

    def extract_participant_from_filename(self, file_path: Path) -> str:
        """Extract participant ID from filename using centralized extractor."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        participant_info = extract_participant_info(file_path)
        return participant_info.numerical_id

    def _extract_participant_id_from_filename(self, file_path: Path) -> str:
        """Extract participant ID from filename - must match format used when saving."""
        # Use the same method as extract_participant_from_filename to ensure consistency
        # between saving and querying nonwear periods
        return self.extract_participant_from_filename(file_path)

    def load_nonwear_sensor_periods(self, file_path: Path) -> list[NonwearPeriod]:
        """Load nonwear periods from sensor data file."""
        try:
            # Validate file
            validated_path = InputValidator.validate_file_path(file_path, must_exist=True, allowed_extensions={".csv"})

            # Load CSV - handle small/corrupted files gracefully
            try:
                df = pd.read_csv(validated_path)
            except pd.errors.EmptyDataError:
                logger.info("Nonwear sensor file %s contains no data", file_path.name)
                return []
            except (OSError, PermissionError, pd.errors.ParserError, UnicodeDecodeError) as e:
                logger.warning("Error reading CSV file %s: %s", file_path.name, e)
                return []

            # Check if file is empty (only headers or completely empty)
            if df.empty or len(df) == 0:
                logger.info("Nonwear sensor file %s is empty - no nonwear periods to load", file_path.name)
                return []

            # Validate required columns
            required_columns = ["start", "end", "participant_id"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                msg = f"Missing required columns in {file_path.name}: {missing_columns}"
                raise DataLoadingError(
                    msg,
                    ErrorCodes.INVALID_FORMAT,
                )

            # Extract participant ID from filename if not reliable in data
            filename_participant = self.extract_participant_from_filename(file_path)

            periods = []
            for _, row in df.iterrows():
                try:
                    # Use participant ID from filename as it's more reliable
                    participant_id = filename_participant

                    period = NonwearPeriod(
                        start_time=str(row["start"]),
                        end_time=str(row["end"]),
                        participant_id=participant_id,
                        source=NonwearDataSource.NONWEAR_SENSOR,
                    )
                    periods.append(period)

                except (ValueError, KeyError, TypeError) as e:
                    logger.warning("Error processing row in %s: %s", file_path.name, e)
                    continue

            logger.debug("Loaded %d nonwear sensor periods from %s", len(periods), file_path.name)
            return periods

        except Exception as e:
            logger.exception("Failed to load nonwear sensor periods from %s", file_path)
            msg = f"Failed to load nonwear sensor data: {e}"
            raise DataLoadingError(
                msg,
                ErrorCodes.FILE_OPERATION_FAILED,
            ) from e

    def load_choi_algorithm_periods(self, file_path: Path) -> list[NonwearPeriod]:
        """Load wear periods from Choi algorithm results file."""
        try:
            # Validate file
            validated_path = InputValidator.validate_file_path(file_path, must_exist=True, allowed_extensions={".csv"})

            # Load CSV - handle small/corrupted files gracefully
            try:
                df = pd.read_csv(validated_path)
            except pd.errors.EmptyDataError:
                logger.info("Choi algorithm file %s contains no data", file_path.name)
                return []
            except (OSError, PermissionError, pd.errors.ParserError, UnicodeDecodeError) as e:
                logger.warning("Error reading CSV file %s: %s", file_path.name, e)
                return []

            # Check if file is empty (only headers or completely empty)
            if df.empty or len(df) == 0:
                logger.info("Choi algorithm file %s is empty - no periods to load", file_path.name)
                return []

            # Validate required columns
            required_columns = [
                "start_time",
                "end_time",
                "duration_minutes",
                "start_index",
                "end_index",
            ]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                msg = f"Missing required columns in {file_path.name}: {missing_columns}"
                raise DataLoadingError(
                    msg,
                    ErrorCodes.INVALID_FORMAT,
                )

            # Extract participant ID from filename
            participant_id = self.extract_participant_from_filename(file_path)

            periods = []
            for _, row in df.iterrows():
                try:
                    period = NonwearPeriod(
                        start_time=str(row["start_time"]),
                        end_time=str(row["end_time"]),
                        participant_id=participant_id,
                        source=NonwearDataSource.CHOI_ALGORITHM,
                        duration_minutes=int(row["duration_minutes"]) if pd.notna(row["duration_minutes"]) else None,
                        start_index=int(row["start_index"]) if pd.notna(row["start_index"]) else None,
                        end_index=int(row["end_index"]) if pd.notna(row["end_index"]) else None,
                    )
                    periods.append(period)

                except (ValueError, KeyError, TypeError) as e:
                    logger.warning("Error processing row in %s: %s", file_path.name, e)
                    continue

            logger.debug("Loaded %d Choi algorithm periods from %s", len(periods), file_path.name)
            return periods

        except Exception as e:
            logger.exception("Failed to load Choi algorithm periods from %s", file_path)
            msg = f"Failed to load Choi algorithm data: {e}"
            raise DataLoadingError(
                msg,
                ErrorCodes.FILE_OPERATION_FAILED,
            ) from e

    def get_nonwear_periods_for_file(
        self,
        filename: str,
        source: NonwearDataSource,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[NonwearPeriod]:
        """Get nonwear periods for a specific file from database, optionally filtered by date range."""
        try:
            logger.debug("Getting nonwear periods for file: %s, source: %s", filename, source)

            # Determine table based on source
            table = DatabaseTable.NONWEAR_SENSOR_PERIODS if source == NonwearDataSource.NONWEAR_SENSOR else DatabaseTable.CHOI_ALGORITHM_PERIODS
            logger.debug("Using table: %s", table)

            # Extract participant ID from filename
            participant_id = self._extract_participant_id_from_filename(Path(filename))
            logger.info("Extracted participant ID '%s' from filename '%s'", participant_id, filename)

            from sleep_scoring_app.data.repositories.base_repository import BaseRepository

            temp_repo = BaseRepository(self.db_manager.db_path, self.db_manager._validate_table_name, self.db_manager._validate_column_name)
            with temp_repo._get_connection() as conn:
                # For sensor periods, query by participant_id since that's how the data is stored
                # For Choi periods, query by filename since they're computed per file
                if source == NonwearDataSource.NONWEAR_SENSOR:
                    # Query by participant_id for sensor data
                    query = f"""
                        SELECT * FROM {table}
                        WHERE {DatabaseColumn.PARTICIPANT_ID} = ?
                    """
                    params = [participant_id]
                else:
                    # Query by filename for Choi data
                    query = f"""
                        SELECT * FROM {table}
                        WHERE {DatabaseColumn.FILENAME} = ? AND {DatabaseColumn.PERIOD_TYPE} = ?
                    """
                    params = [filename, source.value]

                # Add date filtering if provided
                if start_time and end_time:
                    query += f"""
                    AND (
                        ({DatabaseColumn.START_TIME} <= ? AND {DatabaseColumn.END_TIME} >= ?) OR
                        ({DatabaseColumn.START_TIME} >= ? AND {DatabaseColumn.START_TIME} <= ?) OR
                        ({DatabaseColumn.END_TIME} >= ? AND {DatabaseColumn.END_TIME} <= ?)
                    )
                    """
                    # Add parameters for overlap detection
                    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    params.extend([end_str, start_str, start_str, end_str, start_str, end_str])

                query += f" ORDER BY {DatabaseColumn.START_TIME}"

                logger.debug("Executing query: %s", query)
                logger.debug("Query params: %s", params)

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                periods = []

                logger.debug("Database query returned %d rows for file %s", len(rows), filename)

                # Debug logging for date filtering
                if start_time and end_time:
                    logger.info("Filtering nonwear periods for %s between %s and %s", filename, start_time, end_time)
                    logger.info("Found %d periods in date range", len(rows))

                for row in rows:
                    # Convert SQLite row to dictionary for easier access
                    # Get column names from the cursor description
                    column_names = [description[0] for description in cursor.description]
                    row_dict = dict(zip(column_names, row, strict=False))

                    # Handle different column structures for different table types
                    period_data = {
                        "start_time": row_dict.get(DatabaseColumn.START_TIME),
                        "end_time": row_dict.get(DatabaseColumn.END_TIME),
                        "participant_id": row_dict.get(DatabaseColumn.PARTICIPANT_ID),
                        "source": NonwearDataSource(row_dict.get(DatabaseColumn.PERIOD_TYPE)),
                        "duration_minutes": row_dict.get(DatabaseColumn.DURATION_MINUTES),
                    }

                    # Only add index columns if they exist (Choi data has them, sensor data doesn't)
                    period_data["start_index"] = row_dict.get(DatabaseColumn.START_INDEX)
                    period_data["end_index"] = row_dict.get(DatabaseColumn.END_INDEX)

                    period = NonwearPeriod(**period_data)
                    periods.append(period)
                    logger.debug("Added period: %s to %s", period.start_time, period.end_time)

                logger.debug("Returning %d nonwear periods for file %s", len(periods), filename)
                return periods

        except Exception:
            logger.exception("Failed to get nonwear periods for %s", filename)
            return []

    def save_nonwear_periods(self, periods: list[NonwearPeriod], filename: str) -> bool:
        """Save nonwear periods to database."""
        from sleep_scoring_app.data.repositories.base_repository import BaseRepository

        temp_repo = BaseRepository(self.db_manager.db_path, self.db_manager._validate_table_name, self.db_manager._validate_column_name)
        try:
            with temp_repo._get_connection() as conn:
                for period in periods:
                    # Determine table based on source
                    table = (
                        DatabaseTable.NONWEAR_SENSOR_PERIODS
                        if period.source == NonwearDataSource.NONWEAR_SENSOR
                        else DatabaseTable.CHOI_ALGORITHM_PERIODS
                    )

                    # Insert or replace period - different columns for different tables
                    if period.source == NonwearDataSource.NONWEAR_SENSOR:
                        # Sensor data: no indices, only timestamps and duration
                        conn.execute(
                            f"""
                            INSERT OR REPLACE INTO {table} (
                                {DatabaseColumn.FILENAME}, {DatabaseColumn.PARTICIPANT_ID},
                                {DatabaseColumn.START_TIME}, {DatabaseColumn.END_TIME},
                                {DatabaseColumn.DURATION_MINUTES}, {DatabaseColumn.PERIOD_TYPE}
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                filename,
                                period.participant_id,
                                period.start_time,
                                period.end_time,
                                period.duration_minutes,
                                period.source,
                            ),
                        )
                    else:
                        # Choi algorithm data: has indices
                        conn.execute(
                            f"""
                            INSERT OR REPLACE INTO {table} (
                                {DatabaseColumn.FILENAME}, {DatabaseColumn.PARTICIPANT_ID},
                                {DatabaseColumn.START_TIME}, {DatabaseColumn.END_TIME},
                                {DatabaseColumn.DURATION_MINUTES}, {DatabaseColumn.START_INDEX},
                                {DatabaseColumn.END_INDEX}, {DatabaseColumn.PERIOD_TYPE}
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                filename,
                                period.participant_id,
                                period.start_time,
                                period.end_time,
                                period.duration_minutes,
                                period.start_index,
                                period.end_index,
                                period.source,
                            ),
                        )

                conn.commit()
                logger.debug("Saved %d nonwear periods for %s", len(periods), filename)
                return True

        except Exception:
            logger.exception("Failed to save nonwear periods for %s", filename)
            return False

    def align_nonwear_with_activity(self, nonwear_periods: list[NonwearPeriod], activity_timestamps: list[datetime]) -> list[bool]:
        """
        Align nonwear periods with activity data timestamps.

        Returns a list of boolean values indicating nonwear status for each timestamp
        """
        try:
            nonwear_status = [False] * len(activity_timestamps)

            for period in nonwear_periods:
                try:
                    # Parse period timestamps
                    start_dt = pd.to_datetime(period.start_time)
                    end_dt = pd.to_datetime(period.end_time)

                    # Find matching activity timestamps
                    for i, activity_dt in enumerate(activity_timestamps):
                        if start_dt <= activity_dt <= end_dt:
                            nonwear_status[i] = True

                except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime) as e:
                    logger.warning("Error processing nonwear period: %s", e)
                    continue

            nonwear_count = sum(nonwear_status)
            logger.debug("Aligned nonwear periods: %d/%d minutes marked as nonwear", nonwear_count, len(activity_timestamps))

            return nonwear_status

        except Exception:
            logger.exception("Failed to align nonwear periods with activity data")
            # Return all wear periods as fallback
            return [False] * len(activity_timestamps)
