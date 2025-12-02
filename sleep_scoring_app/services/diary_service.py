#!/usr/bin/env python3
"""
Unified Diary Service for Sleep Scoring Application
Consolidates functionality from diary_service.py and diary_service_sync.py.
Provides both Qt-based async operations and synchronous data access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from sleep_scoring_app.core.constants import (
    DatabaseColumn,
    DatabaseTable,
)
from sleep_scoring_app.core.dataclasses import (
    DiaryColumnMapping,
    DiaryEntry,
    DiaryFileInfo,
    DiaryImportResult,
    ParticipantInfo,
)
from sleep_scoring_app.core.exceptions import (
    DatabaseError,
    ErrorCodes,
    SleepScoringImportError,
    ValidationError,
)
from sleep_scoring_app.core.validation import InputValidator

if TYPE_CHECKING:
    from collections.abc import Callable

    from sleep_scoring_app.data.database import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class DiaryImportProgress:
    """Progress tracking for diary import operations."""

    def __init__(self, total_files: int = 0, total_sheets: int = 0) -> None:
        self.total_files = total_files
        self.total_sheets = total_sheets
        self.processed_files = 0
        self.processed_sheets = 0
        self.current_file = ""
        self.current_sheet = ""
        self.current_operation = ""
        self.entries_imported = 0

    @property
    def file_progress_percent(self) -> float:
        """Calculate file progress percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    @property
    def sheet_progress_percent(self) -> float:
        """Calculate sheet progress percentage."""
        if self.total_sheets == 0:
            return 0.0
        return (self.processed_sheets / self.total_sheets) * 100

    def get_status_text(self) -> str:
        """Get current status as readable text."""
        if self.current_operation == "loading":
            return f"Loading {self.current_file} - {self.current_sheet}"
        if self.current_operation == "importing":
            return f"Importing {self.current_file} - {self.current_sheet}"
        if self.current_operation == "processing":
            return f"Processing {self.current_file}"
        return f"Processing file {self.processed_files + 1} of {self.total_files}"


class DiaryService(QObject):
    """Unified service for managing diary data import and retrieval."""

    # Signals for progress tracking (Qt-based functionality)
    progress_updated = pyqtSignal(object)  # DiaryImportProgress
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    import_completed = pyqtSignal(object)  # DiaryImportResult

    def __init__(self, database_manager: DatabaseManager, config_path: Path | None = None) -> None:
        super().__init__()
        self.db_manager = database_manager
        self.validator = InputValidator()
        self._progress = DiaryImportProgress()
        # config_path parameter kept for backward compatibility but no longer used
        self._column_mapping: DiaryColumnMapping | None = None

    def load_column_mapping(self) -> DiaryColumnMapping:
        """
        Load column mapping from embedded configuration.

        Returns:
            DiaryColumnMapping object with column mappings

        """
        try:
            logger.debug("Loading embedded diary mapping configuration")

            # Embedded mapping configuration based on TECH_diary_mapping.json
            config_data = {
                "participant_id_column_name": "participant_id",
                "sleep_onset_time_column_name": "sleep_onset_time",
                "sleep_offset_time_column_name": "sleep_offset_time",
                "in_bed_time_column_name": "in_bed_time",
                "out_of_bed_time_column_name": None,
                "napped_column_name": "napped",
                "nap_onset_time_column_name": "napstart_1_time",  # Use alternative column names for first nap
                "nap_offset_time_column_name": "napend_1_time",  # Use alternative column names for first nap
                "nap_onset_time_column_names": "nap_onset_time_2,nap_onset_time_3,nap_onset_time_4",
                "nap_offset_time_column_names": "nap_offset_time_2,nap_offset_time_3,nap_offset_time_4",
                "nonwear_occurred_column_name": "nonwear_occurred",
                "nonwear_reason_column_names": "nonwear_reason,nonwear_reason_2,nonwear_reason_3,nonwear_reason_4",
                "nonwear_start_time_column_names": "nonwear_start_time,nonwear_start_time_2,nonwear_start_time_3,nonwear_start_time_4",
                "nonwear_end_time_column_names": "nonwear_end_time,nonwear_end_time_2,nonwear_end_time_3,nonwear_end_time_4",
                "diary_completed_for_current_day_column_name": "sleep_diary_day_complete",
                "activity_columns": "activity_other1,activity_other2,activity_other3,activity_other4",
                "expected_diary_entry_date_column_name": None,
                "diary_submission_date_column_name": None,
                "date_of_last_night_column_name": "startdate",
                "sleep_onset_date_column_name": None,
                "sleep_offset_date_column_name": None,
                "todays_date_column_name": None,
                "nap_onset_date_column_name": None,
                "nap_offset_date_column_name": None,
                "participant_timepoint_column_name": None,
                "participant_group_column_name": None,
                "auto_calculated_columns": {
                    "sleep_onset_time_column_name": False,
                    "sleep_offset_time_column_name": False,
                    "in_bed_time_column_name": False,
                    "nap_onset_time_column_name": True,
                    "nap_offset_time_column_name": True,
                    "todays_date_column_name": False,
                    "sleep_onset_date_column_name": False,
                    "sleep_offset_date_column_name": False,
                    "nap_onset_date_column_name": False,
                    "nap_offset_date_column_name": False,
                },
                "alternative_column_names": {
                    "sleep_onset_time": ["sleep_onset_time", "sleep_onset_time_auto", "asleep_time"],
                    "sleep_offset_time": ["sleep_offset_time", "sleep_offset_time_auto", "wake_time"],
                    "in_bed_time": ["bedtime", "in_bed_time_auto", "inbed_time"],
                    "nap_onset_time": ["nap_onset_time_auto", "napstart_1_time"],
                    "nap_offset_time": ["nap_offset_time_auto", "napend_1_time"],
                },
            }

            logger.debug(f"Embedded config data has {len(config_data)} fields")
            logger.debug(f"Config keys: {list(config_data.keys())[:10]}...")  # Show first 10 keys

            mapping = DiaryColumnMapping.from_dict(config_data)
            logger.info("Successfully loaded embedded diary column mapping")
            logger.debug(f"Participant ID column: {mapping.participant_id_column_name}")
            logger.debug(f"Sleep onset column: {mapping.sleep_onset_time_column_name}")
            logger.debug(f"Sleep offset column: {mapping.sleep_offset_time_column_name}")
            return mapping

        except Exception as e:
            msg = f"Failed to load embedded diary mapping configuration: {e}"
            raise ValidationError(
                msg,
                error_code=ErrorCodes.VALIDATION_FAILED,
                context={"error": str(e)},
            ) from e

    # SYNCHRONOUS DATA ACCESS METHODS (from diary_service_sync.py)

    def get_diary_data_for_participant(
        self,
        participant_id: str,
        date_range: tuple[datetime, datetime] | None = None,
    ) -> list[DiaryEntry]:
        """Get diary data for a specific participant using PARTICIPANT_KEY for matching."""
        try:
            # Extract participant info to get composite key
            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            participant_info = extract_participant_info(participant_id)
            participant_key = participant_info.participant_key

            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                # Use PARTICIPANT_KEY for matching across different data sources
                query = f"""
                    SELECT * FROM {DatabaseTable.DIARY_DATA}
                    WHERE {DatabaseColumn.PARTICIPANT_KEY} = ?
                """
                params = [participant_key]

                if date_range:
                    query += f" AND {DatabaseColumn.DIARY_DATE} BETWEEN ? AND ?"
                    params.extend([date_range[0].strftime("%Y-%m-%d"), date_range[1].strftime("%Y-%m-%d")])

                query += f" ORDER BY {DatabaseColumn.DIARY_DATE}"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                if rows:
                    logger.debug(f"Found {len(rows)} diary entries for participant key: '{participant_key}'")
                    all_entries = []
                    for row in rows:
                        row_dict = dict(zip([desc[0] for desc in cursor.description], row, strict=False))
                        all_entries.append(DiaryEntry.from_database_dict(row_dict))
                    return all_entries

                # No need for timepoint variations - PARTICIPANT_KEY handles cross-source matching
                logger.debug(f"No diary entries found for participant key '{participant_key}'")
                return []

        except Exception as e:
            logger.exception(f"Failed to get diary data for participant {participant_id}: {e}")
            return []

    def get_diary_data_for_date(
        self,
        participant_id: str,
        target_date: datetime,
    ) -> DiaryEntry | None:
        """Get diary data for a specific participant and date using PARTICIPANT_KEY."""
        date_str = target_date.strftime("%Y-%m-%d")

        try:
            # Extract participant info to get composite key
            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            participant_info = extract_participant_info(participant_id)
            participant_key = participant_info.participant_key

            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                # Use PARTICIPANT_KEY for matching
                query = f"""
                    SELECT * FROM {DatabaseTable.DIARY_DATA}
                    WHERE {DatabaseColumn.PARTICIPANT_KEY} = ?
                    AND {DatabaseColumn.DIARY_DATE} = ?
                """

                cursor.execute(query, [participant_key, date_str])
                row = cursor.fetchone()

                if row:
                    logger.debug(f"Found diary data for date '{date_str}' with participant key: '{participant_key}'")
                    row_dict = dict(zip([desc[0] for desc in cursor.description], row, strict=False))
                    return DiaryEntry.from_database_dict(row_dict)

                # No need for timepoint variations - PARTICIPANT_KEY handles cross-source matching
                logger.debug(f"No diary data found for participant key '{participant_key}' on date '{date_str}'")
                return None

        except Exception as e:
            logger.exception(f"Failed to get diary data for participant {participant_id} on {date_str}: {e}")
            return None

    def get_available_participants(self) -> list[str]:
        """Get list of participants with diary data."""
        try:
            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                query = f"""
                    SELECT DISTINCT {DatabaseColumn.PARTICIPANT_ID}
                    FROM {DatabaseTable.DIARY_DATA}
                    ORDER BY {DatabaseColumn.PARTICIPANT_ID}
                """

                cursor.execute(query)
                rows = cursor.fetchall()

                return [row[0] for row in rows]

        except Exception as e:
            logger.exception(f"Failed to get available participants: {e}")
            return []

    def get_diary_stats(self) -> dict[str, Any]:
        """Get diary data statistics."""
        try:
            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                # Count total entries
                cursor.execute(f"SELECT COUNT(*) FROM {DatabaseTable.DIARY_DATA}")
                total_entries = cursor.fetchone()[0]

                # Count unique participants
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT {DatabaseColumn.PARTICIPANT_ID})
                    FROM {DatabaseTable.DIARY_DATA}
                """)
                unique_participants = cursor.fetchone()[0]

                # Get date range
                cursor.execute(f"""
                    SELECT MIN({DatabaseColumn.DIARY_DATE}), MAX({DatabaseColumn.DIARY_DATE})
                    FROM {DatabaseTable.DIARY_DATA}
                """)
                date_range = cursor.fetchone()

                return {
                    "total_entries": total_entries,
                    "unique_participants": unique_participants,
                    "date_range_start": date_range[0],
                    "date_range_end": date_range[1],
                }

        except Exception as e:
            logger.exception(f"Failed to get diary stats: {e}")
            return {
                "total_entries": 0,
                "unique_participants": 0,
                "date_range_start": None,
                "date_range_end": None,
            }

    def check_participant_has_diary_data(self, participant_id: str) -> bool:
        """Check if participant has any diary data using PARTICIPANT_KEY."""
        try:
            # Extract participant info to get composite key
            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            participant_info = extract_participant_info(participant_id)
            participant_key = participant_info.participant_key

            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                query = f"""
                    SELECT 1 FROM {DatabaseTable.DIARY_DATA}
                    WHERE {DatabaseColumn.PARTICIPANT_KEY} = ?
                    LIMIT 1
                """

                cursor.execute(query, [participant_key])
                return cursor.fetchone() is not None

        except Exception as e:
            logger.exception(f"Failed to check diary data for participant {participant_id}: {e}")
            return False

    # IMPORT FUNCTIONALITY (from diary_service.py)

    def import_diary_files(
        self,
        file_paths: list[Path],
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> DiaryImportResult:
        """Import multiple diary files using configuration-based column mapping."""
        start_time = time.time()
        result = DiaryImportResult()

        try:
            # Load column mapping configuration
            self._column_mapping = self.load_column_mapping()

            # Validate inputs
            self._validate_import_inputs(file_paths)

            # Prepare file info
            file_infos = []
            total_sheets = 0

            for file_path in file_paths:
                try:
                    file_info = DiaryFileInfo.from_path(file_path)

                    # Get sheet names for Excel files
                    if file_info.file_type == "excel":
                        file_info.sheet_names = self._get_excel_sheet_names(file_path)
                        total_sheets += len(file_info.sheet_names)
                    else:
                        total_sheets += 1

                    file_infos.append(file_info)

                except Exception as e:
                    logger.exception(f"Failed to process file info for {file_path}: {e}")
                    result.failed_files.append((str(file_path), str(e)))

            # Initialize progress tracking
            self._progress = DiaryImportProgress(total_files=len(file_infos), total_sheets=total_sheets)

            # Process each file
            for file_info in file_infos:
                self._progress.current_file = file_info.file_path.name
                self._progress.current_operation = "processing"
                self._emit_progress(progress_callback)

                try:
                    self._process_diary_file(
                        file_info,
                        result,
                        progress_callback,
                    )

                    result.successful_files.append(file_info.file_path.name)

                except Exception as e:
                    logger.exception(f"Failed to process file {file_info.file_path}: {e}")
                    result.failed_files.append((file_info.file_path.name, str(e)))

                finally:
                    self._progress.processed_files += 1
                    self._emit_progress(progress_callback)

            # Finalize results
            result.total_files_processed = len(file_infos)
            result.import_duration_seconds = time.time() - start_time

            logger.info(
                f"Diary import completed: {len(result.successful_files)}/{result.total_files_processed} files successful, "
                f"{result.total_entries_imported} entries imported"
            )

            self.import_completed.emit(result)
            return result

        except Exception as e:
            logger.exception(f"Diary import failed: {e}")
            result.import_duration_seconds = time.time() - start_time
            self.error_occurred.emit(str(e))
            msg = f"Diary import failed: {e}"
            raise SleepScoringImportError(
                msg,
                error_code=ErrorCodes.IMPORT_FAILED,
                context={"file_count": len(file_paths)},
            ) from e

    # HELPER METHODS FOR IMPORTS

    def _process_diary_file(
        self,
        file_info: DiaryFileInfo,
        result: DiaryImportResult,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> None:
        """Process a single diary file."""
        if file_info.file_type == "excel":
            # Process each sheet in Excel file
            for sheet_name in file_info.sheet_names:
                self._progress.current_sheet = sheet_name
                self._process_sheet(
                    file_info,
                    sheet_name,
                    result,
                    progress_callback,
                )
                self._progress.processed_sheets += 1
                self._emit_progress(progress_callback)
        else:
            # Process CSV file
            self._process_sheet(
                file_info,
                None,  # No sheet name for CSV
                result,
                progress_callback,
            )
            self._progress.processed_sheets += 1
            self._emit_progress(progress_callback)

    def _process_sheet(
        self,
        file_info: DiaryFileInfo,
        sheet_name: str | None,
        result: DiaryImportResult,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> None:
        """Process a single sheet/CSV file."""
        try:
            # Load data
            self._progress.current_operation = "loading"
            self._emit_progress(progress_callback)

            data = self._load_sheet_data(file_info.file_path, sheet_name)
            if data.empty:
                logger.warning(f"No data found in {file_info.file_path} sheet {sheet_name}")
                return

            # Store mapping result
            mapping_key = f"{file_info.file_path.name}:{sheet_name}" if sheet_name else file_info.file_path.name
            result.mapping_results[mapping_key] = self._column_mapping

            # Convert data to standard format
            self._progress.current_operation = "importing"
            self._emit_progress(progress_callback)

            diary_entries = self._convert_data_to_entries(
                data,
                self._column_mapping,
                file_info.file_path.name,
                sheet_name,
            )

            # Import to database (pass file info for registration)
            self._import_entries_to_database(diary_entries, file_info.file_path)

            # Update statistics
            result.total_entries_imported += len(diary_entries)
            self._progress.entries_imported += len(diary_entries)

            # Collect participant IDs
            for entry in diary_entries:
                result.participants_found.add(entry.participant_id)

            logger.info(
                f"Successfully imported {len(diary_entries)} diary entries from {file_info.file_path.name}{':' + sheet_name if sheet_name else ''}"
            )

        except Exception as e:
            error_msg = f"Failed to process sheet {sheet_name or 'CSV'}: {e}"
            logger.exception(error_msg)
            sheet_key = f"{file_info.file_path.name}:{sheet_name}" if sheet_name else file_info.file_path.name
            result.failed_files.append((sheet_key, error_msg))

    def _load_sheet_data(self, file_path: Path, sheet_name: str | None) -> pd.DataFrame:
        """Load data from CSV or Excel sheet."""
        file_extension = file_path.suffix.lower()

        try:
            if file_extension == ".csv":
                # Debug: Try different encodings and show what we actually read
                for encoding in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        data = pd.read_csv(file_path, encoding=encoding)
                        logger.debug(f"Successfully read CSV with {encoding} encoding")
                        logger.debug(f"CSV columns: {list(data.columns)}")
                        logger.debug(f"First few participant IDs: {data['participant_id'].head().tolist()}")
                        logger.debug(f"First few sleep onset times: {data['sleep_onset_time'].head().tolist()}")
                        return data
                    except (UnicodeDecodeError, KeyError) as e:
                        logger.debug(f"Failed to read with {encoding}: {e}")
                        continue
                # Fallback to default
                data = pd.read_csv(file_path)
            elif file_extension in [".xlsx", ".xls"]:
                data = pd.read_excel(file_path, sheet_name=sheet_name or 0)
            else:
                msg = f"Unsupported file format: {file_extension}"
                raise ValueError(msg)

            return data

        except Exception as e:
            msg = f"Failed to load data from {file_path}: {e}"
            raise SleepScoringImportError(
                msg,
                error_code=ErrorCodes.FILE_READ_ERROR,
                context={"file_path": str(file_path), "sheet_name": sheet_name},
            ) from e

    def _get_excel_sheet_names(self, file_path: Path) -> list[str]:
        """Get sheet names from Excel file."""
        try:
            excel_file = pd.ExcelFile(file_path)
            return excel_file.sheet_names
        except Exception as e:
            logger.exception(f"Failed to get sheet names from {file_path}: {e}")
            return []

    def _convert_data_to_entries(
        self,
        data: pd.DataFrame,
        column_mapping: DiaryColumnMapping,
        filename: str,
        sheet_name: str | None,
    ) -> list[DiaryEntry]:
        """Convert DataFrame to DiaryEntry objects using column mapping."""
        entries = []

        logger.debug(f"Converting {len(data)} rows from {filename} sheet {sheet_name or 'CSV'}")
        logger.debug(f"Available columns in data: {list(data.columns)}")
        logger.debug(f"Looking for participant ID in column: {column_mapping.participant_id_column_name}")
        logger.debug(f"Looking for date in column: {column_mapping.date_of_last_night_column_name}")
        logger.debug(f"Looking for sleep onset time in column: {column_mapping.sleep_onset_time_column_name}")
        logger.debug(f"Looking for sleep offset time in column: {column_mapping.sleep_offset_time_column_name}")
        logger.debug(f"Looking for in bed time in column: {column_mapping.in_bed_time_column_name}")

        for idx, row in data.iterrows():
            try:
                # Extract participant ID
                participant_id = self._extract_participant_id(row, column_mapping)
                if not participant_id:
                    logger.warning("No participant ID found in row, skipping")
                    continue

                # Extract diary date
                diary_date = self._extract_diary_date(row, column_mapping)
                if not diary_date:
                    logger.warning(f"No diary date found for participant {participant_id}, skipping")
                    continue

                # Extract multiple nonwear fields
                nonwear_start_1, nonwear_start_2, nonwear_start_3 = self._extract_multiple_time_fields(
                    row, column_mapping.nonwear_start_time_column_names
                )
                nonwear_end_1, nonwear_end_2, nonwear_end_3 = self._extract_multiple_time_fields(row, column_mapping.nonwear_end_time_column_names)
                nonwear_reason_raw_1, nonwear_reason_raw_2, nonwear_reason_raw_3 = self._extract_multiple_text_fields(
                    row, column_mapping.nonwear_reason_column_names
                )

                # Convert reason codes to descriptive text
                nonwear_reason_1 = self._convert_nonwear_reason_code(nonwear_reason_raw_1)
                nonwear_reason_2 = self._convert_nonwear_reason_code(nonwear_reason_raw_2)
                nonwear_reason_3 = self._convert_nonwear_reason_code(nonwear_reason_raw_3)

                # Extract nap data - handle various CSV column configurations
                # Some CSVs have nap data in nap_onset_time_2 columns even for the first/only nap

                # First try the configured primary nap columns (napstart_1_time, napend_1_time)
                nap_onset_1 = self._extract_time_field(row, column_mapping.nap_onset_time_column_name)
                nap_offset_1 = self._extract_time_field(row, column_mapping.nap_offset_time_column_name)

                # If no primary nap columns, try alternative column names
                if nap_onset_1 is None:
                    alt_onset_cols = ["nap_onset_time_auto", "nap_onset_time", "napstart_time", "nap_start_time"]
                    for alt_col in alt_onset_cols:
                        if alt_col != column_mapping.nap_onset_time_column_name:
                            nap_onset_1 = self._extract_time_field(row, alt_col)
                            if nap_onset_1:
                                logger.debug(f"Found first nap onset in alternative column: {alt_col}")
                                break

                if nap_offset_1 is None:
                    alt_offset_cols = ["nap_offset_time_auto", "nap_offset_time", "napend_time", "nap_end_time"]
                    for alt_col in alt_offset_cols:
                        if alt_col != column_mapping.nap_offset_time_column_name:
                            nap_offset_1 = self._extract_time_field(row, alt_col)
                            if nap_offset_1:
                                logger.debug(f"Found first nap offset in alternative column: {alt_col}")
                                break

                # Extract additional nap columns (nap 2, 3, etc.)
                nap_onset_2_temp, nap_onset_3_temp, nap_offset_2_temp, nap_offset_3_temp = self._extract_multiple_nap_fields(row, column_mapping)

                # IMPORTANT: If we found no first nap but found data in "nap_2" columns,
                # this is likely the ONLY nap and should go in the first nap slot
                if nap_onset_1 is None and nap_offset_1 is None and nap_onset_2_temp is not None:
                    logger.debug("Found nap data only in nap_2 columns - moving to first nap slot")
                    nap_onset_1 = nap_onset_2_temp
                    nap_offset_1 = nap_offset_2_temp
                    nap_onset_2 = nap_onset_3_temp
                    nap_offset_2 = nap_offset_3_temp
                    nap_onset_3 = None
                    nap_offset_3 = None
                else:
                    # We have first nap data, so keep additional naps in their positions
                    nap_onset_2 = nap_onset_2_temp
                    nap_offset_2 = nap_offset_2_temp
                    nap_onset_3 = nap_onset_3_temp
                    nap_offset_3 = nap_offset_3_temp

                # Create diary entry
                entry = DiaryEntry(
                    participant_id=participant_id,
                    diary_date=diary_date,
                    filename=filename,
                    sleep_onset_time=self._extract_time_field(row, column_mapping.sleep_onset_time_column_name),
                    sleep_offset_time=self._extract_time_field(row, column_mapping.sleep_offset_time_column_name),
                    in_bed_time=self._extract_time_field(row, column_mapping.in_bed_time_column_name),
                    nap_occurred=self._extract_integer_field(row, column_mapping.napped_column_name),
                    nap_onset_time=nap_onset_1,  # Use the extracted first nap onset
                    nap_offset_time=nap_offset_1,  # Use the extracted first nap offset
                    nap_onset_time_2=nap_onset_2,
                    nap_offset_time_2=nap_offset_2,
                    nap_onset_time_3=nap_onset_3,
                    nap_offset_time_3=nap_offset_3,
                    nonwear_occurred=self._extract_boolean_field(row, column_mapping.nonwear_occurred_column_name),
                    nonwear_start_time=nonwear_start_1,
                    nonwear_end_time=nonwear_end_1,
                    nonwear_reason=nonwear_reason_1,
                    nonwear_start_time_2=nonwear_start_2,
                    nonwear_end_time_2=nonwear_end_2,
                    nonwear_reason_2=nonwear_reason_2,
                    nonwear_start_time_3=nonwear_start_3,
                    nonwear_end_time_3=nonwear_end_3,
                    nonwear_reason_3=nonwear_reason_3,
                    original_column_mapping=json.dumps(column_mapping.to_dict()),
                )

                entries.append(entry)

            except Exception as e:
                logger.exception(f"Failed to convert row to diary entry: {e}")
                continue

        return entries

    def _register_diary_file(
        self,
        conn: Any,
        filename: str,
        file_path: Path,
        file_hash: str,
        participant_info: ParticipantInfo | None = None,
    ) -> None:
        """Register diary file in diary file registry before importing entries."""
        try:
            file_stat = file_path.stat()

            # If no participant info provided, try to extract from filename
            if participant_info is None:
                participant_info = self.extract_participant_info_from_filename(filename)

            # Use default values if extraction fails
            if participant_info is None:
                from sleep_scoring_app.core.dataclasses import ParticipantInfo

                participant_info = ParticipantInfo(numerical_id="UNKNOWN")

            conn.execute(
                f"""
                INSERT OR REPLACE INTO {DatabaseTable.DIARY_FILE_REGISTRY} (
                    {DatabaseColumn.FILENAME}, {DatabaseColumn.ORIGINAL_PATH},
                    {DatabaseColumn.PARTICIPANT_ID}, {DatabaseColumn.PARTICIPANT_GROUP},
                    {DatabaseColumn.PARTICIPANT_TIMEPOINT}, {DatabaseColumn.FILE_HASH},
                    {DatabaseColumn.FILE_SIZE}, {DatabaseColumn.LAST_MODIFIED}
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    str(file_path),
                    participant_info.numerical_id,
                    participant_info.group,
                    participant_info.timepoint,
                    file_hash,
                    file_stat.st_size,
                    datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                ),
            )

        except Exception as e:
            logger.exception(f"Failed to register diary file {filename}: {e}")
            raise

    def _import_entries_to_database(self, entries: list[DiaryEntry], file_path: Path | None = None) -> None:
        """Import diary entries to database with proper file registration."""
        if not entries:
            return

        try:
            with self.db_manager._get_connection() as conn:
                cursor = conn.cursor()

                # Group entries by filename to register files first
                files_by_filename = {}
                for entry in entries:
                    if entry.filename not in files_by_filename:
                        files_by_filename[entry.filename] = entry

                # Register each unique file in diary_file_registry first
                for filename in files_by_filename:
                    try:
                        # Use provided file path or try to determine it
                        actual_file_path = file_path if file_path else Path(filename)

                        # Calculate file hash
                        file_hash = "unknown"
                        if actual_file_path.exists():
                            file_hash = self.calculate_file_hash(actual_file_path)

                        # Extract participant info from the entry
                        participant_info = self.extract_participant_info_from_filename(filename)

                        self._register_diary_file(
                            conn,
                            filename,
                            actual_file_path,
                            file_hash,
                            participant_info,
                        )

                    except Exception as reg_error:
                        logger.warning(f"Failed to register file {filename}, will try to continue: {reg_error}")

                # Insert entries
                for entry in entries:
                    entry_dict = entry.to_database_dict()

                    # Prepare column names and values
                    columns = list(entry_dict.keys())
                    placeholders = ", ".join(["?" for _ in columns])
                    values = list(entry_dict.values())

                    # Insert or replace entry
                    query = f"""
                        INSERT OR REPLACE INTO {DatabaseTable.DIARY_DATA}
                        ({", ".join(columns)})
                        VALUES ({placeholders})
                    """

                    cursor.execute(query, values)

                conn.commit()
                logger.info(f"Successfully imported {len(entries)} diary entries to database")

        except Exception as e:
            msg = f"Failed to import diary entries: {e}"
            raise DatabaseError(
                msg,
                error_code=ErrorCodes.DB_QUERY_FAILED,
                context={"entry_count": len(entries)},
            ) from e

    # EXTRACTION HELPER METHODS

    def _extract_participant_id(self, row: pd.Series, column_mapping: DiaryColumnMapping) -> str | None:
        """Extract participant ID from row data."""
        if not column_mapping.participant_id_column_name:
            logger.debug("No participant_id_column_name configured")
            return None

        try:
            value = row.get(column_mapping.participant_id_column_name)
            logger.debug(f"Extracted participant ID value: {value} from column {column_mapping.participant_id_column_name}")
            if pd.isna(value):
                logger.debug("Participant ID value is NaN")
                return None

            # Convert to string and clean
            participant_id = str(value).strip()
            logger.debug(f"Cleaned participant ID: {participant_id}")

            # If already a clean number, return as-is
            if participant_id.isdigit():
                return participant_id

            from sleep_scoring_app.utils.participant_extractor import extract_participant_info

            extracted_info = extract_participant_info(participant_id)
            if extracted_info and extracted_info.numerical_id != "UNKNOWN":
                # Return full_id to preserve timepoint and group information
                return extracted_info.full_id

            return participant_id

        except Exception as e:
            logger.exception(f"Failed to extract participant ID: {e}")
            return None

    def _extract_diary_date(self, row: pd.Series, column_mapping: DiaryColumnMapping) -> str | None:
        """Extract diary date from row data."""
        # Try different date columns in order of preference
        date_columns = []

        # Add date_of_last_night if it exists in the configuration
        if column_mapping.date_of_last_night_column_name:
            date_columns.append(column_mapping.date_of_last_night_column_name)
            logger.debug(f"Looking for date in column: {column_mapping.date_of_last_night_column_name}")

        # Add standard date columns
        date_columns.extend(
            [
                column_mapping.todays_date_column_name,
                column_mapping.sleep_onset_date_column_name,
                column_mapping.sleep_offset_date_column_name,
            ]
        )

        for column_name in date_columns:
            if column_name:
                try:
                    value = row.get(column_name)
                    logger.debug(f"Checking date column '{column_name}': value = {value}")
                    if pd.isna(value):
                        logger.debug(f"Column '{column_name}' value is NaN")
                        continue

                    # Try to parse as date
                    if hasattr(value, "strftime"):
                        date_str = value.strftime("%Y-%m-%d")
                        logger.debug(f"Parsed date from datetime object: {date_str}")
                        return date_str
                    # Try to parse string date
                    parsed_date = pd.to_datetime(str(value))
                    date_str = parsed_date.strftime("%Y-%m-%d")
                    logger.debug(f"Parsed date from string: {date_str}")
                    return date_str

                except Exception as e:
                    logger.debug(f"Failed to parse date from column '{column_name}': {e}")
                    continue

        return None

    def _extract_time_field(self, row: pd.Series, column_name: str | None) -> str | None:
        """Extract time field from row data, properly handling AM/PM format."""
        if not column_name:
            logger.debug("Time field extraction skipped: column_name is None")
            return None

        try:
            # Check if the column exists in the row
            if column_name not in row.index:
                logger.debug(f"Time column '{column_name}' not found in data")
                return None

            value = row.get(column_name)
            if pd.isna(value):
                logger.debug(f"Time column '{column_name}' value is NaN")
                return None

            # Convert to string and clean
            time_str = str(value).strip()
            logger.debug(f"Extracting time from column '{column_name}': raw value = {value}, cleaned = {time_str}")

            # Try to parse as datetime object first
            if hasattr(value, "strftime"):
                return value.strftime("%H:%M")

            # Try to parse using pandas to_datetime which handles AM/PM format
            try:
                parsed_time = pd.to_datetime(time_str, format="%I:%M %p")
                result = parsed_time.strftime("%H:%M")
                logger.debug(f"Successfully parsed AM/PM time '{time_str}' to '{result}'")
                return result
            except (ValueError, TypeError):
                logger.debug(f"Failed to parse '{time_str}' as AM/PM format")

            # Try alternative parsing with pandas (handles various formats automatically)
            try:
                parsed_time = pd.to_datetime(time_str)
                result = parsed_time.strftime("%H:%M")
                logger.debug(f"Successfully parsed time '{time_str}' to '{result}' using auto format")
                return result
            except (ValueError, TypeError):
                logger.debug(f"Failed to auto-parse time '{time_str}'")

            # Fallback to regex for simple HH:MM format (24-hour)
            import re

            time_match = re.search(r"(\d{1,2}):(\d{2})", time_str)
            if time_match:
                result = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                logger.debug(f"Fallback regex parsed '{time_str}' to '{result}' (assuming 24-hour format)")
                return result

            logger.debug(f"Could not parse time '{time_str}', returning as-is")
            return time_str

        except Exception as e:
            logger.debug(f"Exception while parsing time from column '{column_name}': {e}")
            return None

    def _extract_integer_field(self, row: pd.Series, column_name: str | None) -> int | None:
        """Extract integer field from row data."""
        if not column_name:
            return None

        try:
            # Check if the column exists in the row
            if column_name not in row.index:
                logger.debug(f"Integer column '{column_name}' not found in data")
                return None

            value = row.get(column_name)
            if pd.isna(value):
                return None

            # Handle numeric values (float/int)
            if isinstance(value, int | float):
                return int(value)

            # Try to parse string to integer
            str_value = str(value).strip()
            try:
                return int(float(str_value))  # Parse as float first to handle "1.0"
            except ValueError:
                return None

        except Exception:
            return None

    def _extract_boolean_field(self, row: pd.Series, column_name: str | None) -> bool | None:
        """Extract boolean field from row data."""
        if not column_name:
            return None

        try:
            # Check if the column exists in the row
            if column_name not in row.index:
                logger.debug(f"Boolean column '{column_name}' not found in data")
                return None

            value = row.get(column_name)
            if pd.isna(value):
                return None

            if isinstance(value, bool):
                return value

            # Handle numeric values (float/int)
            if isinstance(value, int | float):
                return bool(value)

            # Try to parse string boolean
            str_value = str(value).strip().lower()
            if str_value in ["yes", "y", "true", "1", "1.0", "on"]:
                return True
            if str_value in ["no", "n", "false", "0", "0.0", "off"]:
                return False

            return None

        except Exception:
            return None

    def _extract_multiple_time_fields(self, row: pd.Series, column_names_str: str | None) -> tuple[str | None, str | None, str | None]:
        """
        Extract multiple time fields from comma-separated column names.

        Returns the first 3 values found from the provided column names.
        If a column doesn't exist or has no value, None is returned for that position.
        """
        if not column_names_str:
            return None, None, None

        column_names = [name.strip() for name in column_names_str.split(",")]
        times = []

        for i, column_name in enumerate(column_names):
            if column_name:
                # Check if the column exists before trying to extract
                if column_name in row.index:
                    time_value = self._extract_time_field(row, column_name)
                    times.append(time_value)
                    if time_value:
                        logger.debug(f"Found time value '{time_value}' in column '{column_name}' (position {i + 1})")
                else:
                    logger.debug(f"Column '{column_name}' not found in data (position {i + 1})")
                    times.append(None)
            else:
                times.append(None)

        # Pad with None to ensure we return exactly 3 values
        while len(times) < 3:
            times.append(None)

        return times[0], times[1], times[2]

    def _extract_multiple_text_fields(self, row: pd.Series, column_names_str: str | None) -> tuple[str | None, str | None, str | None]:
        """
        Extract multiple text fields from comma-separated column names.

        Returns the first 3 values found from the provided column names.
        If a column doesn't exist or has no value, None is returned for that position.
        """
        if not column_names_str:
            return None, None, None

        column_names = [name.strip() for name in column_names_str.split(",")]
        texts = []

        for i, column_name in enumerate(column_names):
            if column_name:
                try:
                    # Check if the column exists before trying to extract
                    if column_name in row.index:
                        value = row.get(column_name)
                        if pd.isna(value):
                            texts.append(None)
                        else:
                            text_value = str(value).strip()
                            texts.append(text_value)
                            logger.debug(f"Found text value '{text_value}' in column '{column_name}' (position {i + 1})")
                    else:
                        logger.debug(f"Text column '{column_name}' not found in data (position {i + 1})")
                        texts.append(None)
                except Exception:
                    texts.append(None)
            else:
                texts.append(None)

        # Pad with None to ensure we return exactly 3 values
        while len(texts) < 3:
            texts.append(None)

        return texts[0], texts[1], texts[2]

    def _convert_nonwear_reason_code(self, reason: str | None) -> str | None:
        """
        Convert nonwear reason code to descriptive text.

        Args:
            reason: Numeric reason code (1, 2, 3) or text

        Returns:
            Descriptive text for the reason code

        """
        if reason is None:
            return None

        # Handle if it's already text
        reason_str = str(reason).strip()

        # Convert numeric codes to text
        if reason_str in ["1", "1.0"]:
            return "Bath/Shower"
        if reason_str in ["2", "2.0"]:
            return "Swimming"
        if reason_str in ["3", "3.0"]:
            return "Other"
        # Return as-is if not a recognized code
        return reason_str

    def _extract_multiple_nap_fields(
        self, row: pd.Series, column_mapping: DiaryColumnMapping
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """
        Extract multiple nap fields (onset and offset times for naps 2 and 3).

        This function extracts the SECOND and THIRD naps from columns like
        'nap_onset_time_2', 'nap_onset_time_3', etc.

        Returns:
            Tuple of (nap_onset_time_2, nap_onset_time_3, nap_offset_time_2, nap_offset_time_3)

        """
        # These column names are expected to be for additional naps (nap 2, 3, 4, etc.)
        nap_onset_2 = None
        nap_onset_3 = None
        nap_offset_2 = None
        nap_offset_3 = None

        # Extract nap onset times from the multiple nap columns
        if column_mapping.nap_onset_time_column_names:
            nap_onset_2, nap_onset_3, _ = self._extract_multiple_time_fields(row, column_mapping.nap_onset_time_column_names)
            if nap_onset_2:
                logger.debug(f"Found second nap onset time: {nap_onset_2}")
            if nap_onset_3:
                logger.debug(f"Found third nap onset time: {nap_onset_3}")

        # Extract nap offset times from the multiple nap columns
        if column_mapping.nap_offset_time_column_names:
            nap_offset_2, nap_offset_3, _ = self._extract_multiple_time_fields(row, column_mapping.nap_offset_time_column_names)
            if nap_offset_2:
                logger.debug(f"Found second nap offset time: {nap_offset_2}")
            if nap_offset_3:
                logger.debug(f"Found third nap offset time: {nap_offset_3}")

        # Warn about incomplete nap data
        if (nap_onset_2 and not nap_offset_2) or (nap_offset_2 and not nap_onset_2):
            logger.warning(f"Incomplete second nap data: onset={nap_onset_2}, offset={nap_offset_2}")
        if (nap_onset_3 and not nap_offset_3) or (nap_offset_3 and not nap_onset_3):
            logger.warning(f"Incomplete third nap data: onset={nap_onset_3}, offset={nap_offset_3}")

        return nap_onset_2, nap_onset_3, nap_offset_2, nap_offset_3

    # VALIDATION AND UTILITIES

    def _validate_import_inputs(self, file_paths: list[Path]) -> None:
        """Validate import inputs."""
        if not file_paths:
            msg = "No files provided for import"
            raise ValidationError(
                msg,
                error_code=ErrorCodes.VALIDATION_FAILED,
            )

        # Validate file paths
        for file_path in file_paths:
            if not file_path.exists():
                msg = f"File does not exist: {file_path}"
                raise ValidationError(
                    msg,
                    error_code=ErrorCodes.FILE_NOT_FOUND,
                    context={"file_path": str(file_path)},
                )

            if file_path.suffix.lower() not in [".csv", ".xlsx", ".xls"]:
                msg = f"Unsupported file format: {file_path.suffix}"
                raise ValidationError(
                    msg,
                    error_code=ErrorCodes.UNSUPPORTED_FILE_FORMAT,
                    context={"file_path": str(file_path)},
                )

    def _emit_progress(self, progress_callback: Callable[[str, int, int], None] | None) -> None:
        """Emit progress update."""
        self.progress_updated.emit(self._progress)
        self.status_updated.emit(self._progress.get_status_text())

        if progress_callback:
            progress_callback(self._progress.get_status_text(), self._progress.processed_sheets, self._progress.total_sheets)

    def _generate_timepoint_variations(self, participant_id: str) -> list[str]:
        """Generate timepoint variations for flexible matching."""
        if " " not in participant_id:
            return [participant_id]  # Not a full ID, return as-is

        parts = participant_id.split()
        if len(parts) < 3:
            return [participant_id]  # Not in expected format

        numerical_id = parts[0]
        timepoint = parts[1]
        group = parts[2]

        # Create timepoint variation mappings
        timepoint_variations = {
            # Baseline variations
            "BO": ["BO", "B0", "BL", "Bo", "Bl", "bl", "b0", "bo"],
            "B0": ["B0", "BO", "BL", "b0", "bo", "bl"],
            "BL": ["BL", "BO", "B0", "Bl", "bl", "bo", "b0"],
            "Bo": ["Bo", "BO", "B0", "BL", "bo", "bl", "b0"],
            "Bl": ["Bl", "BL", "BO", "B0", "bl", "bo", "b0"],
            "bo": ["bo", "BO", "B0", "BL", "Bo", "Bl", "bl", "b0"],
            "bl": ["bl", "BL", "BO", "B0", "Bl", "Bo", "bo", "b0"],
            "b0": ["b0", "B0", "BO", "BL", "bo", "bl", "Bo", "Bl"],
            # Phase 1 variations
            "P1": ["P1", "p1"],
            "p1": ["p1", "P1"],
            # Phase 2 variations
            "P2": ["P2", "p2"],
            "p2": ["p2", "P2"],
            # Phase 3 variations
            "P3": ["P3", "p3"],
            "p3": ["p3", "P3"],
        }

        # Get variations for this timepoint
        variations = timepoint_variations.get(timepoint, [timepoint])

        # Generate full participant IDs with each variation
        result = []
        for variation in variations:
            variation_id = f"{numerical_id} {variation} {group}"
            result.append(variation_id)

        logger.debug(f"Generated timepoint variations for '{participant_id}': {result[:5]}{'...' if len(result) > 5 else ''}")
        return result

    # PARTICIPANT EXTRACTION UTILITIES

    def extract_participant_id_from_filename(self, filename: str) -> str | None:
        """Extract full participant identifier from filename using centralized extractor."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        # Use full participant info instead of just numerical ID
        info = extract_participant_info(filename)
        return info.full_id if info.numerical_id != "Unknown" else None

    def extract_participant_info_from_filename(self, filename: str) -> ParticipantInfo | None:
        """Extract full participant info from filename using centralized extractor."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        try:
            # Use centralized extractor which returns ParticipantInfo dataclass
            return extract_participant_info(filename)
        except Exception as e:
            logger.exception(f"Failed to extract participant info from filename {filename}: {e}")
            return None

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file for change detection."""
        try:
            hash_sha256 = hashlib.sha256()
            with file_path.open("rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.exception(f"Failed to calculate hash for {file_path}: {e}")
            # Return a fallback hash based on file size and modification time
            stat = file_path.stat()
            fallback_data = f"{file_path.name}_{stat.st_size}_{stat.st_mtime}".encode()
            return hashlib.sha256(fallback_data).hexdigest()
