"""
Data management module for sleep scoring application
Handles file operations, data loading, and participant information extraction.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sleep_scoring_app.core.constants import ActivityDataPreference, AlgorithmType
from sleep_scoring_app.core.dataclasses import DailySleepMarkers, ParticipantInfo, SleepMetrics, SleepPeriod
from sleep_scoring_app.core.exceptions import (
    DatabaseError,
    DataLoadingError,
    ErrorCodes,
    ValidationError,
)
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.database import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class DataManager:
    """Handles all data loading and management operations."""

    def __init__(self, database_manager: DatabaseManager | None = None) -> None:
        self.current_data = None
        self.current_date_col = None
        self.current_time_col = None
        self.timestamps_combined = None
        self.current_activity_col = None
        self.data_folder = Path.cwd()  # Default to current directory
        self.db_manager = database_manager or DatabaseManager()
        self.use_database = True  # Flag to enable database-first approach

        # Activity column preferences - will be set by service using this manager
        self.preferred_activity_column: ActivityDataPreference = ActivityDataPreference.AXIS_Y
        self.choi_activity_column: ActivityDataPreference = ActivityDataPreference.AXIS_Y

    def set_activity_column_preferences(
        self, preferred_activity_column: ActivityDataPreference, choi_activity_column: ActivityDataPreference
    ) -> None:
        """Set activity column preferences for data loading and algorithms."""
        self.preferred_activity_column = preferred_activity_column
        self.choi_activity_column = choi_activity_column
        logger.debug("Activity column preferences set: preferred=%s, choi=%s", preferred_activity_column, choi_activity_column)

    def set_data_folder(self, folder_path) -> None:
        """Set the folder to search for data files with validation."""
        try:
            # Validate the folder path
            self.data_folder = InputValidator.validate_directory_path(folder_path, must_exist=True, create_if_missing=False)
            logger.debug("Data folder set to: %s", self.data_folder)
        except ValidationError as e:
            msg = f"Invalid data folder: {e}"
            raise DataLoadingError(msg, ErrorCodes.INVALID_INPUT) from e

    def find_data_files(self) -> list[dict[str, Any]]:
        """Find available data files - prioritize database imports, fallback to CSV files."""
        data_files = []

        # First, try to get imported files from database
        if self.use_database:
            try:
                imported_files = self.db_manager.get_available_files()
                logger.info("Database returned %s files", len(imported_files))
                for file_info in imported_files:
                    data_files.append(
                        {
                            "path": None,  # Database-sourced, no path needed
                            "filename": file_info["filename"],
                            "display_name": f"{file_info['filename']} (imported)",
                            "source": "database",
                            "participant_id": file_info["participant_id"],
                            "participant_group": file_info["participant_group"],
                            "total_records": file_info["total_records"],
                            "import_date": file_info["import_date"],
                        },
                    )
                logger.debug("Found %s imported files in database", len(imported_files))
            except (DatabaseError, ValidationError) as e:
                logger.warning("Failed to load database files: %s", e)

        # Only look for CSV files if we're NOT in database mode
        # In database mode, we only want to show imported files
        if not self.use_database:
            try:
                for csv_file in self.data_folder.rglob("*.csv"):
                    try:
                        # Check if this file is already imported
                        filename = csv_file.name
                        already_imported = any(f["filename"] == filename for f in data_files if f.get("source") == "database")

                        display_suffix = " (not imported)" if already_imported else " (CSV)"

                        data_files.append(
                            {
                                "path": csv_file,
                                "filename": filename,
                                "display_name": f"{filename}{display_suffix}",
                                "source": "csv",
                                "already_imported": already_imported,
                            },
                        )
                    except (OSError, ValueError, PermissionError) as e:
                        logger.debug("Error processing file %s: %s", csv_file, e)
                        continue
            except (OSError, PermissionError) as e:
                logger.warning("Failed to scan CSV files: %s", e)

        # Sort by filename, prioritizing database files
        data_files.sort(key=lambda x: (x.get("source") != "database", x["filename"]))
        logger.debug("Found %s total data files", len(data_files))
        return data_files

    def load_selected_file(self, file_info, skip_rows=10) -> list[date]:
        """Load file and extract available dates - handles both database and CSV sources."""
        if not file_info:
            return []

        # Handle file_info being a path (backward compatibility) or dict (new format)
        if isinstance(file_info, str | Path):
            # Legacy CSV path format
            return self._load_csv_file_legacy(file_info, skip_rows)

        # New format with source information
        if file_info.get("source") == "database":
            return self._load_database_file(file_info["filename"])
        return self._load_csv_file_legacy(file_info.get("path"), skip_rows)

    def _load_database_file(self, filename: str) -> list[date]:
        """Load file dates from database."""
        try:
            dates = self.db_manager.get_file_date_ranges(filename)
            logger.debug("Loaded %s dates from database for %s", len(dates), filename)

            # If no dates found in database, provide fallback
            if not dates:
                logger.warning("No activity data found in database for %s, using fallback", filename)
                default_date = datetime.now().date()
                return [default_date]

            return dates
        except Exception:
            logger.exception("Failed to load dates from database for %s", filename)
            # Provide fallback instead of empty list
            default_date = datetime.now().date()
            return [default_date]

    def _load_csv_file_legacy(self, file_path, skip_rows=10):
        """Legacy CSV file loading method."""
        if not file_path:
            return []

        try:
            # Validate inputs
            validated_path = InputValidator.validate_file_path(file_path, must_exist=True, allowed_extensions={".csv"})
            skip_rows = InputValidator.validate_integer(skip_rows, min_val=0, max_val=1000, name="skip_rows")

            logger.debug("Loading file: %s", validated_path)
            logger.debug("Skipping %s rows", skip_rows)

            # Read CSV file, skipping specified number of rows
            df = pd.read_csv(validated_path, skiprows=skip_rows)

            # Validate loaded data
            if df.empty:
                msg = "CSV file is empty"
                raise DataLoadingError(msg, ErrorCodes.INVALID_INPUT)

            if len(df) > 1000000:  # Limit to prevent memory issues
                msg = f"CSV file too large: {len(df)} rows. Maximum allowed: 1,000,000"
                raise DataLoadingError(
                    msg,
                    ErrorCodes.MEMORY_LIMIT_EXCEEDED,
                )

            logger.debug("CSV columns: %s", list(df.columns))
            logger.debug("CSV shape: %s", df.shape)

            # Find separate DATE and TIME columns and combine them
            date_col = None
            time_col = None

            # Look for DATE column (handle whitespace)
            for col in df.columns:
                col_lower = col.strip().lower()
                if col_lower == "date":
                    date_col = col
                    logger.debug("✓ Found date column: '%s'", col)
                    break

            # Look for TIME column (handle whitespace)
            for col in df.columns:
                col_lower = col.strip().lower()
                if col_lower == " time":
                    time_col = col
                    logger.debug("✓ Found time column: '%s'", col)
                    break

            if date_col is None or time_col is None:
                logger.debug("❌ Could not find both DATE and TIME columns. Available columns: %s", list(df.columns))
                logger.debug("Found DATE column: %s", date_col)
                logger.debug("Found TIME column: %s", time_col)
                # Try fallback to single datetime column
                datetime_col = None
                for col in df.columns:
                    col_lower = col.lower()
                    if any(keyword in col_lower for keyword in ["datetime", "timestamp"]):
                        datetime_col = col
                        logger.debug("⚠ Using single datetime column as fallback: %s", datetime_col)
                        break

                if datetime_col is None:
                    datetime_col = df.columns[0]
                    logger.debug("⚠ Using first column as last resort: %s", datetime_col)

                # Parse single datetime column with robust error handling
                try:
                    timestamps = pd.to_datetime(df[datetime_col], infer_datetime_format=True)
                except (ValueError, TypeError, pd.errors.ParserError) as e:
                    logger.debug("Standard datetime parsing failed for column %s: %s", datetime_col, e)
                    # Fall back to automatic detection with errors='coerce'
                    timestamps = pd.to_datetime(df[datetime_col], errors="coerce")
                    if timestamps.isna().any():
                        logger.warning("Some timestamps in column %s could not be parsed", datetime_col)
                        # Drop rows with invalid timestamps
                        valid_mask = ~timestamps.isna()
                        timestamps = timestamps[valid_mask]
                        df = df[valid_mask]
                        logger.warning("Dropped %s rows with invalid timestamps", (~valid_mask).sum())
            else:
                # Combine DATE and TIME columns
                logger.debug("✓ Combining DATE column '%s' and TIME column '%s'", date_col, time_col)
                logger.debug("Sample date values: %s", df[date_col].head().tolist())
                logger.debug("Sample time values: %s", df[time_col].head().tolist())

                # Combine date and time columns
                datetime_strings = df[date_col].astype(str) + " " + df[time_col].astype(str)

                # Try different date formats that are common in ActiGraph data
                try:
                    # First try with infer_datetime_format=True
                    timestamps = pd.to_datetime(datetime_strings)
                except (ValueError, TypeError, pd.errors.ParserError) as e1:
                    logger.debug("Standard datetime parsing failed: %s", e1)
                    # Fall back to automatic detection with errors='coerce'
                    timestamps = pd.to_datetime(datetime_strings, errors="coerce")
                    if timestamps.isna().any():
                        logger.warning("Some timestamps could not be parsed and were set to NaT")
                        # Drop rows with invalid timestamps
                        valid_mask = ~timestamps.isna()
                        timestamps = timestamps[valid_mask]
                        df = df[valid_mask]
                        logger.warning("Dropped %s rows with invalid timestamps", (~valid_mask).sum())
                logger.debug("✓ Successfully combined date and time columns")
                logger.debug("Sample combined datetime: %s", timestamps.head().tolist())

            # Store the full dataset
            self.current_data = df
            self.current_date_col = date_col
            self.current_time_col = time_col
            self.timestamps_combined = timestamps  # Store the combined timestamps

            # Find vector magnitude column specifically
            activity_col = None

            # First priority: look for vector magnitude columns
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ["vector", "magnitude", "vm", "vectormagnitude"]):
                    activity_col = col
                    logger.debug("✓ Found vector magnitude column: %s", col)
                    break

            # Second priority: other activity-related columns (generic patterns only)
            if activity_col is None:
                for col in df.columns:
                    col_lower = col.lower()
                    if any(keyword in col_lower for keyword in ["activity", "count"]):
                        activity_col = col
                        logger.debug("⚠ Using activity column (no vector magnitude found): %s", col)
                        break

            # Fallback: last numeric column
            if activity_col is None:
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                activity_col = numeric_cols[-1] if len(numeric_cols) > 0 else df.columns[-1]
                logger.debug("⚠ Using fallback numeric column: %s", activity_col)

            self.current_activity_col = activity_col
            logger.debug("Final activity column selection: %s", activity_col)

            # Extract unique dates
            dates = [ts.date() for ts in timestamps]
            unique_dates = sorted(set(dates))

            # Convert back to datetime objects (at noon for consistency)
            datetime_dates = [datetime.combine(date, datetime.min.time().replace(hour=12)) for date in unique_dates]

            logger.debug("Found %s unique dates in file: %s to %s", len(datetime_dates), unique_dates[0], unique_dates[-1])
            return datetime_dates

        except pd.errors.EmptyDataError as e:
            msg = "CSV file is empty or corrupted"
            raise DataLoadingError(msg, ErrorCodes.FILE_CORRUPTED) from e
        except pd.errors.ParserError as e:
            msg = f"CSV parsing error: {e}"
            raise DataLoadingError(msg, ErrorCodes.INVALID_FORMAT) from e
        except FileNotFoundError as e:
            msg = f"File not found: {file_path}"
            raise DataLoadingError(msg, ErrorCodes.FILE_NOT_FOUND) from e
        except PermissionError as e:
            msg = f"Permission denied: {file_path}"
            raise DataLoadingError(msg, ErrorCodes.FILE_PERMISSION_DENIED) from e
        except Exception as e:
            logger.warning("Error loading file %s: %s", file_path, e)
            msg = f"Failed to load file: {e}"
            raise DataLoadingError(msg, ErrorCodes.INVALID_INPUT) from e

    def load_real_data(
        self, target_date, hours, filename: str | None = None, activity_column: ActivityDataPreference | None = None
    ) -> tuple[list[datetime], list[float]]:
        """Load real activity data with configurable activity column - prioritize database, fallback to CSV or mock data."""
        # Use preferred activity column if not specified
        if activity_column is None:
            activity_column = self.preferred_activity_column

        # Try database first if filename is provided
        if filename and self.use_database:
            try:
                return self._load_database_activity_data(filename, target_date, hours, activity_column)
            except (DatabaseError, ValidationError, KeyError) as e:
                logger.warning("Failed to load from database, falling back to CSV: %s", e)

        # Fallback to CSV data if available
        if self.current_data is not None:
            return self._load_csv_activity_data(target_date, hours, activity_column)

        # Final fallback to mock data
        logger.debug("No data source available, falling back to mock data")
        return None, None  # Return None instead of fake data

    def _load_database_activity_data(
        self, filename: str, target_date: datetime, hours: int, activity_column: ActivityDataPreference = ActivityDataPreference.AXIS_Y
    ) -> tuple[list[datetime], list[float]]:
        """Load activity data from database with configurable activity column."""
        try:
            # Convert date to datetime if needed
            if isinstance(target_date, date) and not isinstance(target_date, datetime):
                # Convert date to datetime at midnight
                target_datetime = datetime.combine(target_date, datetime.min.time())
            else:
                target_datetime = target_date

            # Calculate time range
            if hours == 24:
                # 24h: noon to noon (12:00 PM current day to 12:00 PM next day)
                start_time = target_datetime.replace(hour=12, minute=0, second=0, microsecond=0)
                end_time = start_time + timedelta(hours=24)
            else:
                # 48h: midnight to midnight + 48h
                start_time = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = start_time + timedelta(hours=48)

            # Load from database with specified activity column
            timestamps, activities = self.db_manager.load_raw_activity_data(filename, start_time, end_time, activity_column=activity_column)

            if not timestamps:
                logger.warning("No data found in database for %s in time range %s to %s", filename, start_time, end_time)
                return None, None  # Return None instead of fake data

            logger.debug("Loaded %s data points from database for %s using %s column", len(timestamps), filename, activity_column)
            logger.debug("Activity data range: %.1f to %.1f", min(activities), max(activities))

            return timestamps, activities

        except Exception:
            logger.exception("Failed to load database activity data")
            raise

    def _load_csv_activity_data(
        self, target_date: datetime, hours: int, activity_column: ActivityDataPreference | None = None
    ) -> tuple[list[datetime], list[float]]:
        """Load activity data from current CSV file with configurable activity column."""
        try:
            df = self.current_data

            # Use specified activity column or fall back to detected column
            activity_col = None
            if activity_column:
                # First try exact match
                if activity_column in df.columns:
                    activity_col = activity_column
                # If exact match fails and requested vector_magnitude, try variations
                elif activity_column.lower() == ActivityDataPreference.VECTOR_MAGNITUDE:
                    for col in df.columns:
                        col_lower = col.lower()
                        if any(keyword in col_lower for keyword in ["vector", "magnitude", "vm", "vectormagnitude"]):
                            activity_col = col
                            logger.debug("Found vector magnitude column variation: %s (requested %s)", col, activity_column)
                            break

            # Fall back to detected column if no match found
            if activity_col is None:
                activity_col = self.current_activity_col
                if activity_column:
                    logger.warning(
                        "COLUMN MATCH FAILED: Requested column '%s' not found. Available columns: %s. Using detected column: %s",
                        activity_column,
                        list(df.columns),
                        activity_col,
                    )

            # Use the pre-combined timestamps
            timestamps = self.timestamps_combined
            timestamps_list = [ts.to_pydatetime() for ts in timestamps]

            # Get activity values - using configured activity column for general processing
            activity_data = df[activity_col].fillna(0).astype(float).tolist()

            # Filter to requested time range
            # Convert date to datetime if needed
            if isinstance(target_date, date) and not isinstance(target_date, datetime):
                target_datetime = datetime.combine(target_date, datetime.min.time())
            else:
                target_datetime = target_date

            if hours == 24:
                # 24h: noon to noon (12:00 PM current day to 12:00 PM next day)
                start_time = target_datetime.replace(hour=12, minute=0, second=0)
                end_time = start_time + timedelta(hours=24)
            else:
                # 48h: midnight to midnight + 48h
                start_time = target_datetime.replace(hour=0, minute=0, second=0)
                end_time = start_time + timedelta(hours=48)

            # Filter data to time range
            filtered_timestamps = []
            filtered_activity = []

            for i, ts in enumerate(timestamps_list):
                if start_time <= ts <= end_time and i < len(activity_data):
                    filtered_timestamps.append(ts)
                    filtered_activity.append(max(0, activity_data[i]))  # Ensure non-negative

            if len(filtered_timestamps) == 0:
                logger.debug("No data found in time range %s to %s", start_time, end_time)
                return None, None  # Return None instead of fake data

            logger.debug("Loaded %s data points from %s to %s", len(filtered_timestamps), filtered_timestamps[0], filtered_timestamps[-1])
            logger.debug("Activity data range: %.1f to %.1f", min(filtered_activity), max(filtered_activity))
            logger.debug("Sample activity values: %s", filtered_activity[:5] if len(filtered_activity) >= 5 else filtered_activity)
            return filtered_timestamps, filtered_activity

        except (ValueError, KeyError, IndexError, pd.errors.ParserError) as e:
            logger.warning("Error loading data: %s", e)
            return None, None  # Return None instead of fake data

    # REMOVED: generate_mock_data() method - fake data functionality completely eliminated

    def filter_to_24h_view(self, timestamps_48h, activity_data_48h, target_date) -> tuple[list[datetime], list[float]]:
        """Filter 48h dataset to 24h noon-to-noon view."""
        # Convert date to datetime if needed
        if isinstance(target_date, date) and not isinstance(target_date, datetime):
            target_datetime = datetime.combine(target_date, datetime.min.time())
        else:
            target_datetime = target_date

        # 24h: noon to noon (12:00 PM current day to 12:00 PM next day)
        start_time = target_datetime.replace(hour=12, minute=0, second=0)
        end_time = start_time + timedelta(hours=24)

        filtered_timestamps = []
        filtered_activity = []

        for i, ts in enumerate(timestamps_48h):
            if start_time <= ts <= end_time and i < len(activity_data_48h):
                filtered_timestamps.append(ts)
                filtered_activity.append(activity_data_48h[i])

        return filtered_timestamps, filtered_activity

    def load_activity_data_only(
        self, filename: str, target_date: datetime, activity_column: ActivityDataPreference, hours: int = 24
    ) -> tuple[list[datetime], list[float]] | None:
        """
        Load only activity data for the specified column without triggering full reload cycle.

        This method is optimized for seamless data swapping and returns None on failure
        instead of falling back to mock data.

        Args:
            filename: Name of the file to load from
            target_date: Target date for data loading
            activity_column: Specific activity column to load (e.g., 'axis_y', 'vector_magnitude')
            hours: Number of hours to load (24 or 48)

        Returns:
            Tuple of (timestamps, activity_data) if successful, None if failed

        """
        date_str = target_date.date() if hasattr(target_date, "date") else target_date
        logger.info("TARGETED LOAD: Loading %s column from %s for %s (%sh)", activity_column, filename, date_str, hours)

        try:
            # Try database first
            if self.use_database:
                try:
                    return self._load_database_activity_data(filename, target_date, hours, activity_column)
                except (DatabaseError, ValidationError, KeyError) as e:
                    logger.warning("TARGETED LOAD: Database load failed for %s: %s", activity_column, e)

            # Try CSV fallback if current data is available
            if self.current_data is not None:
                try:
                    return self._load_csv_activity_data(target_date, hours, activity_column)
                except Exception as e:
                    logger.warning("TARGETED LOAD: CSV load failed for %s: %s", activity_column, e)

            # Return None instead of mock data for targeted loading
            logger.warning("TARGETED LOAD: No data source available for %s column", activity_column)
            return None

        except Exception as e:
            logger.exception("TARGETED LOAD: Unexpected error loading %s: %s", activity_column, e)
            return None

    def load_axis_y_data_for_sadeh(self, filename: str, target_date: datetime, hours: int = 48) -> tuple[list[datetime], list[float]] | None:
        """
        Unified method to load axis_y (vertical) data specifically for Sadeh algorithm.
        This is the SINGLE SOURCE OF TRUTH for axis_y loading.

        IMPORTANT: Always loads with consistent time bounds:
        - 48hr: midnight to midnight+48h (ensures full data coverage)
        - 24hr: noon to noon+24h (standard sleep period)

        Args:
            filename: Name of file to load from
            target_date: Target date for data loading
            hours: Number of hours to load (24 or 48, default 48)

        Returns:
            Tuple of (timestamps, axis_y_data) if successful, ([], []) if failed

        """
        # Check if target_date is already a date object or datetime
        if hasattr(target_date, "date"):
            # It's a datetime object
            date_str = target_date.date()
        else:
            # It's already a date object
            date_str = target_date

        logger.debug("AXIS_Y UNIFIED LOAD: Loading axis_y data for Sadeh from %s on %s (%sh)", filename, date_str, hours)

        # CRITICAL: Use consistent time bounds to prevent alignment issues
        # Convert date to datetime if needed
        if isinstance(target_date, date) and not isinstance(target_date, datetime):
            target_datetime = datetime.combine(target_date, datetime.min.time())
        else:
            target_datetime = target_date

        if hours == 48:
            # 48hr ALWAYS uses midnight to midnight+48 for consistency
            start_time = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=48)
        else:
            # 24hr uses noon to noon
            start_time = target_datetime.replace(hour=12, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=24)

        # Always load axis_y data specifically
        try:
            # Try database first
            if self.use_database:
                try:
                    timestamps, activities = self.db_manager.load_raw_activity_data(
                        filename, start_time, end_time, activity_column=ActivityDataPreference.AXIS_Y
                    )
                    if timestamps:
                        logger.debug("AXIS_Y UNIFIED: Loaded %d points from database", len(timestamps))
                        return timestamps, activities
                except Exception:
                    pass

            # Try CSV fallback
            if self.current_data is not None:
                try:
                    timestamps, activities = self._load_csv_activity_data(target_date, hours, ActivityDataPreference.AXIS_Y)
                    if timestamps:
                        logger.debug("AXIS_Y UNIFIED: Loaded %d points from CSV", len(timestamps))
                        return timestamps, activities
                except Exception as e:
                    logger.warning("AXIS_Y UNIFIED: CSV load failed: %s", e)

            return [], []

        except Exception:
            return [], []

    def extract_enhanced_participant_info(self, file_path=None) -> dict[str, str]:
        """Extract comprehensive participant information using centralized extractor."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        info = extract_participant_info(file_path)

        return {
            "full_participant_id": info.full_id,
            "numerical_participant_id": info.numerical_id,
            "participant_group": info.group,
            "participant_timepoint": info.timepoint,
            "date": info.date or "Unknown",
        }

    def extract_group_from_path(self, file_path) -> str | None:
        """Extract group information from file path using centralized extractor."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        if not file_path:
            return None
        info = extract_participant_info(file_path)
        return info.group if info.group != "G1" else None

    def calculate_sleep_metrics(
        self,
        sleep_markers,
        sadeh_results,
        choi_results,
        activity_data,
        x_data,
        file_path=None,
        nwt_sensor_results=None,
    ) -> dict[str, Any] | None:
        """Calculate comprehensive sleep metrics from markers and algorithm results."""
        try:
            # Get participant info
            participant_info = self.extract_enhanced_participant_info(file_path)

            # Validate sleep markers
            if not sleep_markers or len(sleep_markers) != 2:
                return None

            sorted_markers = sorted(sleep_markers)
            onset_timestamp = sorted_markers[0]
            offset_timestamp = sorted_markers[1]

            # Convert to datetime objects
            onset_dt = datetime.fromtimestamp(onset_timestamp)
            offset_dt = datetime.fromtimestamp(offset_timestamp)

            # Find indices for onset and offset
            onset_idx = self._find_closest_data_index(x_data, onset_timestamp)
            offset_idx = self._find_closest_data_index(x_data, offset_timestamp)

            # Algorithm values at markers
            sadeh_onset = sadeh_results[onset_idx] if onset_idx is not None and onset_idx < len(sadeh_results) else 0
            sadeh_offset = sadeh_results[offset_idx] if offset_idx is not None and offset_idx < len(sadeh_results) else 0
            choi_onset = choi_results[onset_idx] if onset_idx is not None and onset_idx < len(choi_results) else 0
            choi_offset = choi_results[offset_idx] if offset_idx is not None and offset_idx < len(choi_results) else 0
            nwt_sensor_onset = (
                nwt_sensor_results[onset_idx] if nwt_sensor_results and onset_idx is not None and onset_idx < len(nwt_sensor_results) else 0
            )
            nwt_sensor_offset = (
                nwt_sensor_results[offset_idx] if nwt_sensor_results and offset_idx is not None and offset_idx < len(nwt_sensor_results) else 0
            )

            # Initialize all variables
            total_activity = 0
            movement_events = 0

            # Calculate sleep period metrics from Sadeh results
            if onset_idx is not None and offset_idx is not None and sadeh_results:
                sleep_minutes = 0
                awakenings = 0
                awakening_lengths = []
                current_awakening_length = 0

                # Find first and last actual sleep epochs for WASO calculation (ActiLife-compatible)
                first_sleep_idx = None
                last_sleep_idx = None
                for i in range(onset_idx, min(offset_idx, len(sadeh_results))):
                    if sadeh_results[i] == 1:
                        if first_sleep_idx is None:
                            first_sleep_idx = i
                        last_sleep_idx = i

                for i in range(onset_idx, min(offset_idx, len(sadeh_results))):
                    if i < len(activity_data):
                        activity = activity_data[i]
                        total_activity += activity

                        if activity > 0:
                            movement_events += 1

                    if sadeh_results[i] == 1:  # Sleep
                        sleep_minutes += 1
                        if current_awakening_length > 0:
                            awakening_lengths.append(current_awakening_length)
                            current_awakening_length = 0
                    # Only count awakenings AFTER first sleep epoch (ActiLife-compatible)
                    elif first_sleep_idx is not None and i > first_sleep_idx and i <= last_sleep_idx:
                        current_awakening_length += 1
                        if current_awakening_length == 1:  # Start of new awakening
                            awakenings += 1

                # Handle case where sleep period ends during an awakening
                if current_awakening_length > 0 and last_sleep_idx is not None:
                    awakening_lengths.append(current_awakening_length)

                # Calculate TIB from epoch count (exclusive range)
                total_minutes_in_bed = offset_idx - onset_idx

                # Calculate derived metrics

                if first_sleep_idx is not None and last_sleep_idx is not None:
                    total_sleep_time = sum(1 for i in range(first_sleep_idx, last_sleep_idx + 1) if sadeh_results[i] == 1)
                else:
                    total_sleep_time = 0

                # WASO: Wake time between first and last sleep epochs (ActiLife-compatible)
                # This excludes sleep latency and terminal wake
                if first_sleep_idx is not None and last_sleep_idx is not None:
                    sleep_period_length = last_sleep_idx - first_sleep_idx + 1
                    waso = sleep_period_length - sleep_minutes
                else:
                    waso = total_minutes_in_bed - total_sleep_time

                efficiency = (total_sleep_time / total_minutes_in_bed * 100) if total_minutes_in_bed > 0 else 0
                avg_awakening_length = sum(awakening_lengths) / len(awakening_lengths) if awakening_lengths else 0
                movement_index = movement_events / total_minutes_in_bed if total_minutes_in_bed > 0 else 0
                fragmentation_index = (awakenings / total_sleep_time * 100) if total_sleep_time > 0 else 0
                sleep_fragmentation_index = ((waso + movement_events) / total_minutes_in_bed * 100) if total_minutes_in_bed > 0 else 0

                # Count Choi algorithm results over sleep period
                total_choi_counts = sum(choi_results[onset_idx : offset_idx + 1]) if onset_idx is not None and offset_idx is not None else 0

                # Count NWT sensor results over sleep period
                total_nwt_sensor_counts = (
                    sum(nwt_sensor_results[onset_idx : offset_idx + 1])
                    if nwt_sensor_results and onset_idx is not None and offset_idx is not None
                    else 0
                )
            else:
                # No algorithm data available - use None for all calculated metrics
                # Still calculate TIB from timestamps as fallback when no epoch data
                total_minutes_in_bed = (offset_timestamp - onset_timestamp) / 60
                total_sleep_time = None
                waso = None
                efficiency = None
                awakenings = None
                avg_awakening_length = None
                movement_index = None
                fragmentation_index = None
                sleep_fragmentation_index = None
                total_choi_counts = None
                total_nwt_sensor_counts = None

            return {
                "Full Participant ID": participant_info["full_participant_id"],
                "Numerical Participant ID": participant_info["numerical_participant_id"],
                "Participant Group": participant_info["participant_group"],
                "Participant Timepoint": participant_info["participant_timepoint"],
                "Sleep Algorithm": AlgorithmType.SADEH_1994_ACTILIFE.value,
                "Onset Date": onset_dt.strftime("%Y-%m-%d"),
                "Onset Time": onset_dt.strftime("%H:%M"),
                "Offset Date": offset_dt.strftime("%Y-%m-%d"),
                "Offset Time": offset_dt.strftime("%H:%M"),
                "Total Counts": int(total_activity) if total_activity is not None else None,
                "Efficiency": round(efficiency, 2) if efficiency is not None else None,
                "Total Minutes in Bed": round(total_minutes_in_bed, 1),
                "Total Sleep Time (TST)": round(total_sleep_time, 1) if total_sleep_time is not None else None,
                "Wake After Sleep Onset (WASO)": round(waso, 1) if waso is not None else None,
                "Number of Awakenings": int(awakenings) if awakenings is not None else None,
                "Average Awakening Length": round(avg_awakening_length, 1) if avg_awakening_length is not None else None,
                "Movement Index": round(movement_index, 3) if movement_index is not None else None,
                "Fragmentation Index": round(fragmentation_index, 2) if fragmentation_index is not None else None,
                "Sleep Fragmentation Index": round(sleep_fragmentation_index, 2) if sleep_fragmentation_index is not None else None,
                "Sadeh Algorithm Value at Sleep Onset": sadeh_onset if onset_idx is not None and onset_idx < len(sadeh_results) else None,
                "Sadeh Algorithm Value at Sleep Offset": sadeh_offset if offset_idx is not None and offset_idx < len(sadeh_results) else None,
                "Choi Algorithm Value at Sleep Onset": choi_onset if onset_idx is not None and onset_idx < len(choi_results) else None,
                "Choi Algorithm Value at Sleep Offset": choi_offset if offset_idx is not None and offset_idx < len(choi_results) else None,
                "Total Choi Algorithm Counts over the Sleep Period": int(total_choi_counts) if total_choi_counts is not None else None,
                # NWT sensor data calculation (similar to Choi algorithm)
                "NWT Sensor Value at Sleep Onset": nwt_sensor_onset
                if nwt_sensor_results and onset_idx is not None and onset_idx < len(nwt_sensor_results)
                else None,
                "NWT Sensor Value at Sleep Offset": nwt_sensor_offset
                if nwt_sensor_results and offset_idx is not None and offset_idx < len(nwt_sensor_results)
                else None,
                "Total NWT Sensor Counts over the Sleep Period": int(total_nwt_sensor_counts) if total_nwt_sensor_counts is not None else None,
            }

        except (ValueError, TypeError, KeyError, IndexError):
            logger.exception("Error calculating sleep metrics")
            return None

    def _find_closest_data_index(self, x_data, timestamp):
        """Find the index of the closest data point to the given timestamp."""
        if x_data is None or len(x_data) == 0:
            return None

        min_diff = float("inf")
        closest_idx = None

        for i, data_timestamp in enumerate(x_data):
            diff = abs(data_timestamp - timestamp)
            if diff < min_diff:
                min_diff = diff
                closest_idx = i

        return closest_idx

    def _dict_to_sleep_metrics(self, metrics_dict: dict, file_path: str | None = None) -> SleepMetrics:
        """Convert dictionary metrics to SleepMetrics object."""
        # Extract participant info from the dictionary
        numerical_id = metrics_dict.get("Numerical Participant ID", "Unknown")
        timepoint = metrics_dict.get("Participant Timepoint", "BO")
        group = metrics_dict.get("Participant Group", "G1")

        # Reconstruct full_id from all three components (numerical_id, timepoint, group)
        if numerical_id != "Unknown":
            full_id = f"{numerical_id} {timepoint} {group}"
        else:
            full_id = metrics_dict.get("Full Participant ID", "Unknown BO G1")  # Fallback to stored value

        participant = ParticipantInfo(
            numerical_id=numerical_id,
            full_id=full_id,
            group=group,
            timepoint=timepoint,
            date=metrics_dict.get("Onset Date", ""),
        )

        # Create daily sleep markers from onset/offset data
        daily_markers = DailySleepMarkers()

        # Get timestamps from dictionary - they may be stored differently
        onset_time_str = metrics_dict.get("Onset Time", "")
        offset_time_str = metrics_dict.get("Offset Time", "")
        onset_date_str = metrics_dict.get("Onset Date", "")
        offset_date_str = metrics_dict.get("Offset Date", "")

        # Try to construct timestamps from date/time if available
        onset_timestamp = None
        offset_timestamp = None

        if onset_date_str and onset_time_str:
            try:
                onset_dt = datetime.strptime(f"{onset_date_str} {onset_time_str}", "%Y-%m-%d %H:%M")
                onset_timestamp = onset_dt.timestamp()
            except ValueError:
                onset_timestamp = None

        if offset_date_str and offset_time_str:
            try:
                offset_dt = datetime.strptime(f"{offset_date_str} {offset_time_str}", "%Y-%m-%d %H:%M")
                offset_timestamp = offset_dt.timestamp()
            except ValueError:
                offset_timestamp = None

        # Create sleep period if both timestamps are available
        if onset_timestamp is not None and offset_timestamp is not None:
            sleep_period = SleepPeriod(
                onset_timestamp=onset_timestamp,
                offset_timestamp=offset_timestamp,
            )
            # Set as period_1 for backward compatibility
            daily_markers.period_1 = sleep_period

        # Calculate total minutes in bed if not present
        total_minutes_in_bed = metrics_dict.get("Total Minutes in Bed")
        if total_minutes_in_bed is None and onset_timestamp is not None and offset_timestamp is not None:
            total_minutes_in_bed = (offset_timestamp - onset_timestamp) / 60

        # Create SleepMetrics object
        return SleepMetrics(
            participant=participant,
            filename=Path(file_path).name if file_path else metrics_dict.get("filename", ""),
            analysis_date=onset_date_str,
            algorithm_type=AlgorithmType.migrate_legacy_value(metrics_dict.get("Sleep Algorithm", AlgorithmType.SADEH_1994_ACTILIFE.value)),
            daily_sleep_markers=daily_markers,
            onset_time=onset_time_str,
            offset_time=offset_time_str,
            total_sleep_time=metrics_dict.get("Total Sleep Time (TST)"),
            sleep_efficiency=metrics_dict.get("Efficiency"),
            total_minutes_in_bed=total_minutes_in_bed,
            waso=metrics_dict.get("Wake After Sleep Onset (WASO)"),
            awakenings=metrics_dict.get("Number of Awakenings"),
            average_awakening_length=metrics_dict.get("Average Awakening Length"),
            total_activity=metrics_dict.get("Total Counts"),
            movement_index=metrics_dict.get("Movement Index"),
            fragmentation_index=metrics_dict.get("Fragmentation Index"),
            sleep_fragmentation_index=metrics_dict.get("Sleep Fragmentation Index"),
            sadeh_onset=metrics_dict.get("Sadeh Algorithm Value at Sleep Onset"),
            sadeh_offset=metrics_dict.get("Sadeh Algorithm Value at Sleep Offset"),
            choi_onset=metrics_dict.get("Choi Algorithm Value at Sleep Onset"),
            choi_offset=metrics_dict.get("Choi Algorithm Value at Sleep Offset"),
            total_choi_counts=metrics_dict.get("Total Choi Algorithm Counts over the Sleep Period"),
            nwt_onset=metrics_dict.get("NWT Sensor Value at Sleep Onset"),
            nwt_offset=metrics_dict.get("NWT Sensor Value at Sleep Offset"),
            total_nwt_counts=metrics_dict.get("Total NWT Sensor Counts over the Sleep Period"),
            updated_at=datetime.now().isoformat(),
        )

    def calculate_sleep_metrics_object(
        self,
        sleep_markers,
        sadeh_results,
        choi_results,
        axis_y_data,
        x_data,
        file_path=None,
        nwt_sensor_results=None,
    ) -> SleepMetrics | None:
        """Calculate sleep metrics and return as SleepMetrics object."""
        metrics_dict = self.calculate_sleep_metrics(
            sleep_markers,
            sadeh_results,
            choi_results,
            axis_y_data,
            x_data,
            file_path,
            nwt_sensor_results,
        )
        if metrics_dict is None:
            return None

        # Convert dictionary to SleepMetrics object
        sleep_metrics = self._dict_to_sleep_metrics(metrics_dict, file_path)

        # If we have raw sleep_markers data, override the markers with the actual timestamps
        if sleep_markers and len(sleep_markers) >= 2:
            daily_markers = DailySleepMarkers()
            sleep_period = SleepPeriod(
                onset_timestamp=float(sleep_markers[0]),
                offset_timestamp=float(sleep_markers[1]),
            )
            # Set as period_1 for backward compatibility
            daily_markers.period_1 = sleep_period
            sleep_metrics.daily_sleep_markers = daily_markers

        return sleep_metrics

    def set_current_file_info(self, file_info: dict[str, Any]) -> None:
        """Set current file information for processing."""
        self.current_file_info = file_info
        logger.info("Set current file: %s", file_info.get("filename", "Unknown"))

    def get_database_statistics(self) -> dict[str, Any]:
        """Get database import statistics."""
        if self.use_database:
            return self.db_manager.get_import_statistics()
        return {
            "total_files": 0,
            "imported_files": 0,
            "total_activity_records": 0,
        }

    def is_file_imported(self, filename: str) -> bool:
        """Check if a file has been imported into the database."""
        if not self.use_database:
            return False

        try:
            files = self.db_manager.get_available_files()
            return any(f["filename"] == filename for f in files)
        except (DatabaseError, ValidationError) as e:
            logger.warning("Failed to check import status for %s: %s", filename, e)
            return False

    def get_participant_info_from_database(self, filename: str) -> dict[str, Any] | None:
        """Get participant info from database for imported file."""
        if not self.use_database:
            return None

        try:
            files = self.db_manager.get_available_files()
            for file_info in files:
                if file_info["filename"] == filename:
                    return {
                        "numerical_participant_id": file_info["participant_id"],
                        "participant_group": file_info["participant_group"],
                        "participant_timepoint": file_info["participant_timepoint"],
                        "full_participant_id": f"{file_info['participant_id']} {file_info['participant_timepoint']}",
                    }
            return None
        except (DatabaseError, ValidationError, KeyError) as e:
            logger.warning("Failed to get participant info for %s: %s", filename, e)
            return None

    def toggle_database_mode(self, use_database: bool) -> None:
        """Toggle between database and CSV mode."""
        self.use_database = use_database
        logger.info("Database mode %s", "enabled" if use_database else "disabled")

    def clear_current_data(self) -> None:
        """Clear current loaded data."""
        self.current_data = None
        self.current_date_col = None
        self.current_time_col = None
        self.timestamps_combined = None
        self.current_activity_col = None
        self.current_file_info = None
        logger.debug("Cleared current data")

    def calculate_sleep_metrics_for_period(
        self,
        sleep_period,
        sadeh_results,
        choi_results,
        axis_y_data,
        x_data,
        file_path=None,
        nwt_sensor_results=None,
    ) -> dict[str, Any] | None:
        """Calculate sleep metrics for a specific sleep period."""
        if not sleep_period or not sleep_period.is_complete:
            return None

        # Convert SleepPeriod to legacy format for existing logic
        sleep_markers = [sleep_period.onset_timestamp, sleep_period.offset_timestamp]

        # Use existing calculation logic
        metrics = self.calculate_sleep_metrics(sleep_markers, sadeh_results, choi_results, axis_y_data, x_data, file_path, nwt_sensor_results)

        if metrics:
            # Add period-specific metadata
            metrics["marker_type"] = sleep_period.marker_type.value if sleep_period.marker_type else None
            metrics["marker_index"] = sleep_period.marker_index
            metrics["period_duration_hours"] = sleep_period.duration_hours

        return metrics

    def calculate_sleep_metrics_for_all_periods(
        self,
        daily_sleep_markers,
        sadeh_results,
        choi_results,
        axis_y_data,
        x_data,
        file_path=None,
        nwt_sensor_results=None,
    ) -> list[dict[str, Any]]:
        """Calculate sleep metrics for all complete sleep periods."""
        all_metrics = []

        for period in daily_sleep_markers.get_complete_periods():
            period_metrics = self.calculate_sleep_metrics_for_period(
                period, sadeh_results, choi_results, axis_y_data, x_data, file_path, nwt_sensor_results
            )
            if period_metrics:
                all_metrics.append(period_metrics)

        return all_metrics
