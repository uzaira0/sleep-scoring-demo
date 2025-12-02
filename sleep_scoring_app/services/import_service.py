#!/usr/bin/env python3
"""
Import Service for Sleep Scoring Application
Handles bulk CSV import functionality with progress tracking and file change detection.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from sleep_scoring_app.core.constants import (
    ActivityColumn,
    ActivityDataPreference,
    DatabaseColumn,
    DatabaseTable,
    ImportStatus,
)
from sleep_scoring_app.core.exceptions import (
    DatabaseError,
    ErrorCodes,
    SleepScoringImportError,
    ValidationError,
)
from sleep_scoring_app.core.validation import InputValidator
from sleep_scoring_app.data.database import DatabaseManager
from sleep_scoring_app.services.nonwear_service import NonwearDataService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from sleep_scoring_app.core.dataclasses import ParticipantInfo

# Configure logging
logger = logging.getLogger(__name__)


class ImportProgress:
    """Progress tracking for import operations."""

    def __init__(self, total_files: int = 0, total_records: int = 0) -> None:
        self.total_files = total_files
        self.processed_files = 0
        self.total_records = total_records
        self.processed_records = 0
        self.current_file = ""
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.skipped_files: list[str] = []
        self.imported_files: list[str] = []
        self.info_messages: list[str] = []

        # Separate tracking for nonwear data
        self.total_nonwear_files = 0
        self.processed_nonwear_files = 0
        self.current_nonwear_file = ""
        self.imported_nonwear_files: list[str] = []

    def add_info(self, message: str) -> None:
        """Add an informational message to the progress."""
        self.info_messages.append(message)

    @property
    def file_progress_percent(self) -> float:
        try:
            if self.total_files == 0:
                return 0.0
            return (self.processed_files / self.total_files) * 100
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return 0.0

    @property
    def record_progress_percent(self) -> float:
        try:
            if self.total_records == 0:
                return 0.0
            return (self.processed_records / self.total_records) * 100
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return 0.0

    @property
    def nonwear_progress_percent(self) -> float:
        try:
            if self.total_nonwear_files == 0:
                return 0.0
            return (self.processed_nonwear_files / self.total_nonwear_files) * 100
        except (TypeError, AttributeError):
            # Handle mock objects during testing
            return 0.0

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        logger.error(error)

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)
        logger.warning(warning)


class ImportService(QObject):
    """Service for importing CSV files into database with progress tracking."""

    # Signals for progress tracking
    progress_updated = pyqtSignal(object)  # ImportProgress object
    nonwear_progress_updated = pyqtSignal(object)  # ImportProgress object (for nonwear progress)
    file_started = pyqtSignal(str)  # filename
    file_completed = pyqtSignal(str, bool)  # filename, success
    import_completed = pyqtSignal(object)  # ImportProgress object

    def __init__(self, database_manager: DatabaseManager | None = None) -> None:
        super().__init__()
        self.db_manager = database_manager or DatabaseManager()
        self.nonwear_service = NonwearDataService(self.db_manager)
        self.batch_size = 1000  # Records per batch for large files
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file for change detection."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            msg = f"Failed to calculate hash for {file_path}: {e}"
            raise SleepScoringImportError(
                msg,
                ErrorCodes.FILE_CORRUPTED,
            ) from e

    def extract_participant_info(self, file_path: Path) -> ParticipantInfo:
        """Extract participant information using centralized extractor - fail fast if configuration incomplete."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        try:
            return extract_participant_info(file_path)
        except Exception as e:
            # Convert extraction errors to import errors for proper error handling
            msg = f"Failed to extract participant information from {file_path.name}: {e}"
            raise SleepScoringImportError(
                msg,
                ErrorCodes.CONFIG_INVALID,
            ) from e

    # Group extraction is now handled by the centralized participant extractor
    # This method has been removed to eliminate fallback patterns

    def check_file_needs_import(self, file_path: Path) -> tuple[bool, str | None]:
        """Check if file needs to be imported based on PARTICIPANT_KEY and hash comparison."""
        try:
            # Extract participant info to get PARTICIPANT_KEY
            participant_info = self.extract_participant_info(file_path)
            participant_key = participant_info.participant_key
            current_hash = self.calculate_file_hash(file_path)

            # Check if file exists in registry using PARTICIPANT_KEY
            with self.db_manager._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT {DatabaseColumn.FILE_HASH}, {DatabaseColumn.STATUS}, {DatabaseColumn.FILENAME}
                    FROM {DatabaseTable.FILE_REGISTRY}
                    WHERE {DatabaseColumn.PARTICIPANT_KEY} = ?
                    """,
                    (participant_key,),
                )
                result = cursor.fetchone()

                if result is None:
                    return True, "New participant data"

                stored_hash, status, existing_filename = result

                # If it's a different file for same participant, check if it's newer
                if existing_filename != file_path.name:
                    logger.info("Found different file for participant %s: %s vs %s", participant_key, existing_filename, file_path.name)
                    return True, "Different file for participant"

                if stored_hash != current_hash:
                    return True, "File changed"
                if status == ImportStatus.ERROR:
                    return True, "Previous import failed"
                return False, "Already imported"

        except (DatabaseError, OSError, ValidationError) as e:
            logger.warning("Error checking import status for %s: %s", file_path, e)
            return True, "Import check failed"

    def import_csv_file(
        self,
        file_path: Path,
        progress: ImportProgress | None = None,
        skip_rows: int = 10,
        force_reimport: bool = False,
        custom_columns: dict[str, str] | None = None,
    ) -> bool:
        """Import a single CSV file into the database."""
        try:
            # Validate file
            validated_path = InputValidator.validate_file_path(file_path, must_exist=True, allowed_extensions={".csv"})

            filename = validated_path.name

            # Check if import is needed
            if not force_reimport:
                needs_import, reason = self.check_file_needs_import(validated_path)
                if not needs_import:
                    if progress:
                        progress.skipped_files.append(f"{filename}: {reason}")
                    logger.info("Skipping %s: %s", filename, reason)
                    return True

            # Check file size
            file_size = validated_path.stat().st_size
            if file_size > self.max_file_size:
                error_msg = f"File {filename} too large: {file_size / 1024 / 1024:.1f}MB > {self.max_file_size / 1024 / 1024:.1f}MB"
                if progress:
                    progress.add_error(error_msg)
                return False

            if progress:
                progress.current_file = filename
                self.file_started.emit(filename)

            # Extract participant info
            participant_info = self.extract_participant_info(validated_path)

            # Calculate file hash
            file_hash = self.calculate_file_hash(validated_path)

            # Load and validate CSV
            df = self._load_and_validate_csv(validated_path, skip_rows)
            if df is None or df.empty:
                error_msg = f"Failed to load CSV data from {filename}"
                if progress:
                    progress.add_error(error_msg)
                return False

            # Find required columns (use custom columns if provided)
            date_col, time_col, activity_col, extra_cols = self._identify_columns(df, custom_columns)
            if not all([date_col, activity_col]):  # time_col can be None if datetime is combined
                error_msg = f"Required columns not found in {filename}"
                logger.error("Column identification failed for %s:", filename)
                logger.error("  Available columns: %s", list(df.columns))
                logger.error("  Found date_col: %s", date_col)
                logger.error("  Found time_col: %s", time_col)
                logger.error("  Found activity_col: %s", activity_col)
                if progress:
                    progress.add_error(error_msg)
                return False

            # Type guard: ensure required columns are not None after validation
            # Note: time_col can be None if datetime is combined in date_col
            assert date_col is not None
            assert activity_col is not None

            # Process timestamps
            timestamps = self._process_timestamps(df, date_col, time_col)
            if timestamps is None:
                error_msg = f"Failed to process timestamps in {filename}"
                if progress:
                    progress.add_error(error_msg)
                return False

            # Import data using transaction
            success = self._import_data_transaction(
                filename,
                participant_info,
                file_hash,
                validated_path,
                df,
                timestamps,
                activity_col,
                extra_cols,
                progress,
            )

            if success:
                if progress:
                    progress.imported_files.append(filename)
                    progress.processed_files += 1
                self.file_completed.emit(filename, True)
                logger.info("Successfully imported %s", filename)
            else:
                self.file_completed.emit(filename, False)

            return success

        except Exception as e:
            error_msg = f"Failed to import {file_path}: {e}"
            if progress:
                progress.add_error(error_msg)
            self.file_completed.emit(str(file_path), False)
            logger.exception(error_msg)
            return False

    def _load_and_validate_csv(self, file_path: Path, skip_rows: int) -> pd.DataFrame | None:
        """Load and validate CSV file."""
        try:
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                logger.error("CSV file too large: %.1f MB > %.1f MB", file_size / 1024 / 1024, self.max_file_size / 1024 / 1024)
                return None

            df = pd.read_csv(file_path, skiprows=skip_rows)

            if df.empty:
                return None

            if len(df) > 100000:
                logger.warning("Large CSV file %s: %s rows", file_path.name, len(df))

            return df

        except pd.errors.EmptyDataError:
            logger.exception("CSV file %s is empty", file_path.name)
            return None
        except pd.errors.ParserError:
            logger.exception("CSV parsing error in %s", file_path.name)
            return None
        except Exception:
            logger.exception("Error loading CSV %s", file_path.name)
            return None

    def _identify_columns(
        self, df: pd.DataFrame, custom_columns: dict[str, str] | None = None
    ) -> tuple[str | None, str | None, str | None, dict[str, str]]:
        """
        Identify required and optional columns in CSV.

        Args:
            df: DataFrame to identify columns in
            custom_columns: Optional dict with keys 'date', 'time', 'activity', 'datetime_combined'
                          If provided and datetime_combined is True, time will be None

        Returns:
            Tuple of (date_col, time_col, activity_col, extra_cols)

        """
        # Note: Do NOT strip columns here - we need to preserve the exact column names
        columns = list(df.columns)

        logger.debug("Available columns (raw): %s", columns)
        logger.debug("Available columns (repr): %s", [repr(col) for col in columns])

        # Use custom columns if provided
        if custom_columns:
            date_col = custom_columns.get("date")
            time_col = custom_columns.get("time")  # Will be None if datetime_combined
            activity_col = custom_columns.get("activity")
            datetime_combined = custom_columns.get("datetime_combined", False)

            # Validate custom columns exist in dataframe
            if date_col and date_col not in columns:
                logger.warning("Custom date column '%s' not found in CSV columns", date_col)
                date_col = None
            if time_col and time_col not in columns:
                logger.warning("Custom time column '%s' not found in CSV columns", time_col)
                time_col = None
            if activity_col and activity_col not in columns:
                logger.warning("Custom activity column '%s' not found in CSV columns", activity_col)
                activity_col = None

            # If datetime is combined, time_col should be None
            if datetime_combined:
                time_col = None

            logger.info("Using custom columns: date=%s, time=%s, activity=%s, combined=%s", date_col, time_col, activity_col, datetime_combined)

            # Use custom axis column mappings if provided, otherwise use standard detection
            extra_cols = {}

            # Get custom axis columns from the custom_columns dict
            # User specifies which CSV column maps to each axis (Y=vertical, X=lateral, Z=forward)
            custom_axis_y = custom_columns.get(ActivityDataPreference.AXIS_Y)
            custom_axis_x = custom_columns.get(ActivityDataPreference.AXIS_X)
            custom_axis_z = custom_columns.get(ActivityDataPreference.AXIS_Z)
            custom_vm = custom_columns.get(ActivityDataPreference.VECTOR_MAGNITUDE)

            # Validate and add custom axis columns
            if custom_axis_y and custom_axis_y in columns:
                extra_cols[DatabaseColumn.AXIS_Y] = custom_axis_y
                logger.info("Using custom Y-Axis (vertical) column: %s", custom_axis_y)
            if custom_axis_x and custom_axis_x in columns:
                extra_cols[DatabaseColumn.AXIS_X] = custom_axis_x
                logger.info("Using custom X-Axis (lateral) column: %s", custom_axis_x)
            if custom_axis_z and custom_axis_z in columns:
                extra_cols[DatabaseColumn.AXIS_Z] = custom_axis_z
                logger.info("Using custom Z-Axis (forward) column: %s", custom_axis_z)
            if custom_vm and custom_vm in columns:
                extra_cols[DatabaseColumn.VECTOR_MAGNITUDE] = custom_vm
                logger.info("Using custom Vector Magnitude column: %s", custom_vm)

            # If no custom axis columns provided, fall back to standard detection
            if not extra_cols:
                extra_cols = self._find_extra_columns(columns)

            return date_col, time_col, activity_col, extra_cols

        # Find DATE column - try multiple variations
        # First check for combined datetime column (exact match)
        date_col = None
        time_col = None
        datetime_combined = False

        for col in columns:
            col_lower = col.lower().strip()
            if col_lower in ("datetime", "timestamp"):
                date_col = col
                datetime_combined = True
                logger.debug("Found combined datetime column: '%s'", col)
                break

        # If no combined datetime, look for separate date column
        if date_col is None:
            date_patterns = ["date", "datum", "day"]
            for col in columns:
                col_lower = col.lower().strip()
                for pattern in date_patterns:
                    if pattern in col_lower:
                        date_col = col
                        logger.debug("Found date column: '%s' (repr: %r, matched pattern: '%s')", col, col, pattern)
                        break
                if date_col:
                    break

        # Find TIME column - only if not using combined datetime
        if not datetime_combined:
            time_patterns = [
                "time",
                "tijd",
                "hour",
            ]  # Removed the space pattern since we check stripped versions
            for col in columns:
                col_lower = col.lower().strip()
                for pattern in time_patterns:
                    if pattern in col_lower:
                        time_col = col
                        logger.debug("Found time column: '%s' (repr: %r, matched pattern: '%s')", col, col, pattern)
                        break
                if time_col:
                    break

        # Find activity column (prioritize vector magnitude)
        activity_col = None
        for col in columns:
            col_lower = col.lower().strip()
            if any(
                keyword in col_lower
                for keyword in [
                    ActivityColumn.VECTOR,
                    ActivityColumn.MAGNITUDE,
                    ActivityColumn.VM,
                    ActivityColumn.VECTORMAGNITUDE,
                ]
            ):
                activity_col = col
                logger.debug("Found activity column: '%s' (repr: %r, vector magnitude)", col, col)
                break

        # Fallback to other activity columns (only generic patterns, not axis-specific)
        if activity_col is None:
            for col in columns:
                col_lower = col.lower().strip()
                if any(
                    keyword in col_lower
                    for keyword in [
                        ActivityColumn.ACTIVITY,
                        ActivityColumn.COUNT,
                    ]
                ):
                    activity_col = col
                    logger.debug("Found activity column: '%s' (repr: %r, fallback)", col, col)
                    break

        # Find extra columns (only vector magnitude - axis columns must be user-specified)
        extra_cols = self._find_extra_columns(columns)

        return date_col, time_col, activity_col, extra_cols

    def _find_extra_columns(self, columns: list[str]) -> dict[str, str]:
        """
        Find axis and vector magnitude columns with common naming patterns.

        Auto-detects columns with standard naming conventions:
        - Y-Axis (vertical): axis_y, axis1, y
        - X-Axis (lateral): axis_x, axis2, x
        - Z-Axis (forward): axis_z, axis3, z
        - Vector Magnitude: vector_magnitude, vm, vector magnitude
        """
        extra_cols = {}
        for col in columns:
            col_lower = col.lower().strip()

            # Auto-detect Y-Axis (vertical) - ActiGraph Axis1
            if DatabaseColumn.AXIS_Y not in extra_cols:
                if col_lower in ("axis_y", "axis1", "y") or col_lower == "axis 1":
                    extra_cols[DatabaseColumn.AXIS_Y] = col

            # Auto-detect X-Axis (lateral) - ActiGraph Axis2
            if DatabaseColumn.AXIS_X not in extra_cols:
                if col_lower in ("axis_x", "axis2", "x") or col_lower == "axis 2":
                    extra_cols[DatabaseColumn.AXIS_X] = col

            # Auto-detect Z-Axis (forward) - ActiGraph Axis3
            if DatabaseColumn.AXIS_Z not in extra_cols:
                if col_lower in ("axis_z", "axis3", "z") or col_lower == "axis 3":
                    extra_cols[DatabaseColumn.AXIS_Z] = col

            # Auto-detect Vector Magnitude
            if DatabaseColumn.VECTOR_MAGNITUDE not in extra_cols:
                if any(keyword in col_lower for keyword in [ActivityColumn.VECTOR, ActivityColumn.MAGNITUDE, "vm", "vectormagnitude"]):
                    extra_cols[DatabaseColumn.VECTOR_MAGNITUDE] = col

        return extra_cols

    def _process_timestamps(self, df: pd.DataFrame, date_col: str, time_col: str | None) -> list[str] | None:
        """
        Process date and time columns into ISO timestamps.

        Args:
            df: DataFrame containing the data
            date_col: Column name for date (or combined datetime if time_col is None)
            time_col: Column name for time, or None if datetime is combined in date_col

        """
        try:
            # Verify date column exists
            if date_col not in df.columns:
                logger.error("Date column '%s' not found in DataFrame. Available columns: %s", date_col, list(df.columns))
                return None

            # Handle combined datetime vs separate date/time columns
            if time_col is None:
                # Combined datetime in single column
                datetime_strings = df[date_col].astype(str)
                logger.debug("Using combined datetime column: %s", date_col)
            else:
                # Separate date and time columns
                if time_col not in df.columns:
                    logger.error("Time column '%s' not found in DataFrame. Available columns: %s", time_col, list(df.columns))
                    return None
                datetime_strings = df[date_col].astype(str) + " " + df[time_col].astype(str)

            # Debug: show sample data
            logger.debug("Sample datetime strings: %s", datetime_strings.head(3).tolist())

            # Try different datetime parsing methods
            try:
                timestamps = pd.to_datetime(datetime_strings)
            except (ValueError, TypeError, pd.errors.ParserError) as parse_error:
                logger.warning("Standard datetime parsing failed: %s", parse_error)
                # Try with different format inference
                try:
                    timestamps = pd.to_datetime(datetime_strings, infer_datetime_format=True)
                except Exception as infer_error:
                    logger.exception("Inferred datetime parsing also failed: %s", infer_error)
                    return None

            # Convert to ISO format strings
            iso_timestamps = [ts.isoformat() for ts in timestamps]

            # Validate intervals (should be roughly 1 minute)
            if len(iso_timestamps) > 1:
                first_interval = timestamps.iloc[1] - timestamps.iloc[0]
                if abs(first_interval.total_seconds() - 60) > 30:  # Allow 30s tolerance
                    logger.warning("Data intervals may not be exactly 1 minute: %s", first_interval)

            logger.debug("Successfully processed %s timestamps", len(iso_timestamps))
            return iso_timestamps

        except Exception:
            logger.exception("Failed to process timestamps")
            return None

    def _import_data_transaction(
        self,
        filename: str,
        participant_info: ParticipantInfo,
        file_hash: str,
        file_path: Path,
        df: pd.DataFrame,
        timestamps: list[str],
        activity_col: str,
        extra_cols: dict[str, str],
        progress: ImportProgress | None,
    ) -> bool:
        """Import data within a database transaction."""
        try:
            with self.db_manager._get_connection() as conn:
                # Begin transaction
                conn.execute("BEGIN TRANSACTION")

                try:
                    # Register file first
                    self._register_file(
                        conn,
                        filename,
                        participant_info,
                        file_hash,
                        file_path,
                        len(df),
                        timestamps[0] if timestamps else None,
                        timestamps[-1] if timestamps else None,
                    )

                    # Delete existing data if reimporting
                    conn.execute(
                        f"DELETE FROM {DatabaseTable.RAW_ACTIVITY_DATA} WHERE {DatabaseColumn.FILENAME} = ?",
                        (filename,),
                    )

                    # Import activity data in batches
                    success = self._import_activity_data_batched(
                        conn,
                        filename,
                        participant_info,  # Pass full participant info for composite key
                        file_hash,
                        df,
                        timestamps,
                        activity_col,
                        extra_cols,
                        progress,
                    )

                    if success:
                        # Update file status
                        conn.execute(
                            f"""
                            UPDATE {DatabaseTable.FILE_REGISTRY}
                            SET {DatabaseColumn.STATUS} = ?, {DatabaseColumn.IMPORT_DATE} = ?
                            WHERE {DatabaseColumn.FILENAME} = ?
                            """,
                            (
                                ImportStatus.IMPORTED,
                                datetime.now().isoformat(),
                                filename,
                            ),
                        )
                        conn.commit()
                        return True
                    conn.rollback()
                    return False

                except Exception:
                    conn.rollback()
                    logger.exception("Transaction failed for %s", filename)
                    return False

        except Exception:
            logger.exception("Database connection failed for %s", filename)
            return False

    def _register_file(
        self,
        conn: Any,
        filename: str,
        participant_info: ParticipantInfo,
        file_hash: str,
        file_path: Path,
        total_records: int,
        date_start: str | None,
        date_end: str | None,
    ) -> None:
        """Register file in file registry."""
        file_stat = file_path.stat()

        conn.execute(
            f"""
            INSERT OR REPLACE INTO {DatabaseTable.FILE_REGISTRY} (
                {DatabaseColumn.FILENAME}, {DatabaseColumn.ORIGINAL_PATH},
                {DatabaseColumn.PARTICIPANT_KEY}, {DatabaseColumn.PARTICIPANT_ID},
                {DatabaseColumn.PARTICIPANT_GROUP}, {DatabaseColumn.PARTICIPANT_TIMEPOINT},
                {DatabaseColumn.FILE_SIZE}, {DatabaseColumn.FILE_HASH},
                {DatabaseColumn.DATE_RANGE_START}, {DatabaseColumn.DATE_RANGE_END},
                {DatabaseColumn.TOTAL_RECORDS}, {DatabaseColumn.LAST_MODIFIED},
                {DatabaseColumn.STATUS}
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                str(file_path),
                participant_info.participant_key,  # Add composite key
                participant_info.numerical_id,
                participant_info.group,
                participant_info.timepoint,
                file_stat.st_size,
                file_hash,
                date_start,
                date_end,
                total_records,
                datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                ImportStatus.IMPORTING,
            ),
        )

    def _import_activity_data_batched(
        self,
        conn: Any,
        filename: str,
        participant_info: ParticipantInfo,
        file_hash: str,
        df: pd.DataFrame,
        timestamps: list[str],
        activity_col: str,
        extra_cols: dict[str, str],
        progress: ImportProgress | None,
    ) -> bool:
        """Import activity data in batches for memory efficiency."""
        try:
            total_rows = len(df)
            batch_count = 0

            # Prepare base data
            activity_data = df[activity_col].fillna(0).astype(float)

            # Process in batches
            for start_idx in range(0, total_rows, self.batch_size):
                end_idx = min(start_idx + self.batch_size, total_rows)
                batch_data = []

                for i in range(start_idx, end_idx):
                    if i >= len(timestamps):
                        break

                    # Get AXIS_Y data (vertical) - use specific column if available, otherwise use activity column
                    if DatabaseColumn.AXIS_Y in extra_cols and extra_cols[DatabaseColumn.AXIS_Y] in df.columns:
                        axis_y_value = df[extra_cols[DatabaseColumn.AXIS_Y]].iloc[i]
                        axis_y_value = float(axis_y_value) if not pd.isna(axis_y_value) else 0.0
                    else:
                        axis_y_value = float(activity_data.iloc[i])

                    # Get AXIS_X (lateral) if available
                    axis_x_value = None
                    if DatabaseColumn.AXIS_X in extra_cols and extra_cols[DatabaseColumn.AXIS_X] in df.columns:
                        value = df[extra_cols[DatabaseColumn.AXIS_X]].iloc[i]
                        axis_x_value = float(value) if not pd.isna(value) else None

                    # Get AXIS_Z (forward) if available
                    axis_z_value = None
                    if DatabaseColumn.AXIS_Z in extra_cols and extra_cols[DatabaseColumn.AXIS_Z] in df.columns:
                        value = df[extra_cols[DatabaseColumn.AXIS_Z]].iloc[i]
                        axis_z_value = float(value) if not pd.isna(value) else None

                    # Get Vector Magnitude if available, or calculate from X, Y, Z
                    vector_magnitude = None
                    if DatabaseColumn.VECTOR_MAGNITUDE in extra_cols and extra_cols[DatabaseColumn.VECTOR_MAGNITUDE] in df.columns:
                        value = df[extra_cols[DatabaseColumn.VECTOR_MAGNITUDE]].iloc[i]
                        vector_magnitude = float(value) if not pd.isna(value) else None
                    elif axis_x_value is not None and axis_y_value is not None and axis_z_value is not None:
                        # Calculate vector magnitude from X, Y, Z: sqrt(x^2 + y^2 + z^2)
                        vector_magnitude = math.sqrt(axis_x_value**2 + axis_y_value**2 + axis_z_value**2)

                    # Base record with PARTICIPANT_KEY and individual components
                    record = [
                        file_hash,
                        filename,
                        participant_info.participant_key,  # Add composite key
                        participant_info.numerical_id,
                        participant_info.group,
                        participant_info.timepoint,
                        timestamps[i],
                        axis_y_value,  # AXIS_Y (vertical - primary for Sadeh algorithm)
                        axis_x_value,  # AXIS_X (lateral)
                        axis_z_value,  # AXIS_Z (forward)
                        vector_magnitude,  # Vector Magnitude
                    ]

                    batch_data.append(tuple(record))

                if batch_data:
                    # Insert batch with PARTICIPANT_KEY and all axis columns
                    conn.executemany(
                        f"""
                        INSERT INTO {DatabaseTable.RAW_ACTIVITY_DATA} (
                            {DatabaseColumn.FILE_HASH}, {DatabaseColumn.FILENAME},
                            {DatabaseColumn.PARTICIPANT_KEY}, {DatabaseColumn.PARTICIPANT_ID},
                            {DatabaseColumn.PARTICIPANT_GROUP}, {DatabaseColumn.PARTICIPANT_TIMEPOINT},
                            {DatabaseColumn.TIMESTAMP}, {DatabaseColumn.AXIS_Y},
                            {DatabaseColumn.AXIS_X}, {DatabaseColumn.AXIS_Z},
                            {DatabaseColumn.VECTOR_MAGNITUDE}
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch_data,
                    )

                    batch_count += 1
                    if progress:
                        progress.processed_records += len(batch_data)
                        self.progress_updated.emit(progress)

            return True

        except Exception:
            logger.exception("Failed to import activity data for %s", filename)
            return False

    def import_directory(
        self,
        directory_path: Path,
        skip_rows: int = 10,
        force_reimport: bool = False,
        progress_callback: Callable[[ImportProgress], None] | None = None,
        include_nonwear: bool = False,
        custom_columns: dict[str, str] | None = None,
    ) -> ImportProgress:
        """Import all CSV files from a directory."""
        try:
            # Validate directory
            validated_dir = InputValidator.validate_directory_path(directory_path, must_exist=True, create_if_missing=False)

            # Find CSV files
            csv_files = list(validated_dir.rglob("*.csv"))
            logger.info("Found %s CSV files in %s", len(csv_files), validated_dir)

            # Estimate total records for progress tracking
            total_records = 0
            valid_files = []

            for csv_file in csv_files:
                try:
                    # Quick row count estimation
                    with open(csv_file) as f:
                        # Skip header rows and count remaining
                        for _ in range(skip_rows):
                            next(f, None)
                        row_count = sum(1 for _ in f)

                    total_records += max(0, row_count)
                    valid_files.append(csv_file)

                except (OSError, PermissionError, ValueError) as e:
                    logger.warning("Skipping %s: %s", csv_file, e)

            # Initialize progress
            progress = ImportProgress(total_files=len(valid_files), total_records=total_records)

            # Import files
            for csv_file in valid_files:
                try:
                    self.import_csv_file(csv_file, progress, skip_rows, force_reimport, custom_columns)

                    if progress_callback:
                        progress_callback(progress)

                except (DatabaseError, OSError, ValidationError, ValueError) as e:
                    progress.add_error(f"Failed to import {csv_file}: {e}")

            # Import nonwear sensor and Choi algorithm data (only if requested)
            if include_nonwear:
                try:
                    self.import_nonwear_data(validated_dir, progress)
                except (DatabaseError, OSError, ValidationError) as e:
                    progress.add_error(f"Failed to import nonwear data: {e}")

            # Complete
            progress.processed_files = len(valid_files)
            self.import_completed.emit(progress)

            logger.info(
                "Import completed: %s files imported, %s skipped, %s errors",
                len(progress.imported_files),
                len(progress.skipped_files),
                len(progress.errors),
            )

            return progress

        except (OSError, DatabaseError, ValidationError) as e:
            error_progress = ImportProgress()
            error_progress.add_error(f"Failed to import directory {directory_path}: {e}")
            return error_progress

    def import_files(
        self,
        file_paths: list[Path],
        skip_rows: int = 10,
        force_reimport: bool = False,
        progress_callback: Callable[[ImportProgress], None] | None = None,
        custom_columns: dict[str, str] | None = None,
    ) -> ImportProgress:
        """Import a list of CSV files directly."""
        try:
            # Validate and filter files
            valid_files = []
            total_records = 0

            for file_path in file_paths:
                try:
                    validated_file = InputValidator.validate_file_path(file_path, must_exist=True)
                    # Quick row count estimation
                    with open(validated_file) as f:
                        for _ in range(skip_rows):
                            next(f, None)
                        row_count = sum(1 for _ in f)

                    total_records += max(0, row_count)
                    valid_files.append(validated_file)

                except (OSError, PermissionError, ValueError, ValidationError) as e:
                    logger.warning("Skipping %s: %s", file_path, e)

            logger.info("Importing %s CSV files (%s total records)", len(valid_files), total_records)

            # Initialize progress
            progress = ImportProgress(total_files=len(valid_files), total_records=total_records)

            # Import files
            for csv_file in valid_files:
                try:
                    self.import_csv_file(csv_file, progress, skip_rows, force_reimport, custom_columns)

                    if progress_callback:
                        progress_callback(progress)

                except (DatabaseError, OSError, ValidationError, ValueError) as e:
                    progress.add_error(f"Failed to import {csv_file}: {e}")

            # Complete
            progress.processed_files = len(valid_files)
            self.import_completed.emit(progress)

            logger.info(
                "Import completed: %s files imported, %s skipped, %s errors",
                len(progress.imported_files),
                len(progress.skipped_files),
                len(progress.errors),
            )

            return progress

        except (OSError, DatabaseError, ValidationError) as e:
            error_progress = ImportProgress()
            error_progress.add_error(f"Failed to import files: {e}")
            return error_progress

    def get_import_summary(self) -> dict[str, Any]:
        """Get summary of imported files."""
        try:
            with self.db_manager._get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_files,
                        SUM({DatabaseColumn.TOTAL_RECORDS}) as total_records,
                        COUNT(CASE WHEN {DatabaseColumn.STATUS} = ? THEN 1 END) as imported_files,
                        COUNT(CASE WHEN {DatabaseColumn.STATUS} = ? THEN 1 END) as error_files
                    FROM {DatabaseTable.FILE_REGISTRY}
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

        except Exception:
            logger.exception("Failed to get import summary")
            return {
                "total_files": 0,
                "total_records": 0,
                "imported_files": 0,
                "error_files": 0,
            }

    def import_nonwear_data(self, data_directory: Path, progress: ImportProgress | None = None) -> None:
        """Import nonwear sensor data (Choi algorithm results are generated on-demand)."""
        try:
            # Import nonwear sensor data only
            nonwear_files = self.nonwear_service.find_nonwear_sensor_files(data_directory)

            # Setup separate nonwear progress tracking
            if progress:
                progress.total_nonwear_files = len(nonwear_files)
                progress.processed_nonwear_files = 0

            for nonwear_file in nonwear_files:
                try:
                    if progress:
                        progress.current_nonwear_file = nonwear_file.name
                        self.nonwear_progress_updated.emit(progress)

                    periods = self.nonwear_service.load_nonwear_sensor_periods(nonwear_file)
                    filename = nonwear_file.name
                    self.nonwear_service.save_nonwear_periods(periods, filename)

                    if progress:
                        progress.imported_nonwear_files.append(nonwear_file.name)
                        progress.processed_nonwear_files += 1
                        progress.add_info(f"Imported {len(periods)} nonwear sensor periods from {nonwear_file.name}")
                        self.nonwear_progress_updated.emit(progress)

                except (OSError, PermissionError, pd.errors.ParserError, ValueError) as e:
                    if progress:
                        progress.processed_nonwear_files += 1
                        progress.add_error(f"Failed to import nonwear sensor file {nonwear_file.name}: {e}")
                        self.nonwear_progress_updated.emit(progress)

            logger.info("Nonwear sensor data import completed: %s sensor files", len(nonwear_files))

        except Exception:
            logger.exception("Failed to import nonwear sensor data")
            raise

    def import_nonwear_files(self, file_paths: list[Path], progress: ImportProgress | None = None) -> None:
        """Import specific nonwear sensor files."""
        try:
            # Setup separate nonwear progress tracking
            if progress:
                progress.total_nonwear_files = len(file_paths)
                progress.processed_nonwear_files = 0

            for nonwear_file in file_paths:
                try:
                    if progress:
                        progress.current_nonwear_file = nonwear_file.name
                        self.nonwear_progress_updated.emit(progress)

                    periods = self.nonwear_service.load_nonwear_sensor_periods(nonwear_file)
                    filename = nonwear_file.name
                    self.nonwear_service.save_nonwear_periods(periods, filename)

                    if progress:
                        progress.imported_nonwear_files.append(nonwear_file.name)
                        progress.processed_nonwear_files += 1
                        progress.add_info(f"Imported {len(periods)} nonwear sensor periods from {nonwear_file.name}")
                        self.nonwear_progress_updated.emit(progress)

                except (OSError, PermissionError, pd.errors.ParserError, ValueError) as e:
                    if progress:
                        progress.processed_nonwear_files += 1
                        progress.add_error(f"Failed to import nonwear sensor file {nonwear_file.name}: {e}")
                        self.nonwear_progress_updated.emit(progress)

            logger.info("Nonwear sensor file import completed: %s files", len(file_paths))

        except Exception:
            logger.exception("Failed to import nonwear sensor files")
            raise
