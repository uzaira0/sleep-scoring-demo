#!/usr/bin/env python3
"""
Type Definitions for Sleep Scoring Application
Defines all dataclasses and type structures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.constants import (
    ActivityDataPreference,
    AlgorithmResult,
    AlgorithmType,
    ConfigKey,
    DatabaseColumn,
    DefaultColumn,
    DeleteStatus,
    ExportColumn,
    MarkerLimits,
    MarkerType,
    NonwearDataSource,
    ParticipantGroup,
    ParticipantTimepoint,
    SadehDataSource,
    StudyDataParadigm,
)
from sleep_scoring_app.utils.column_registry import column_registry

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

# Module-level cached database manager for NWT calculations
# Avoids creating thousands of DatabaseManager instances during export
_cached_db_manager = None

# ============================================================================
# DATACLASS DEFINITIONS
# ============================================================================


@dataclass
class ParticipantInfo:
    """Participant information extracted from filename."""

    numerical_id: str = "Unknown"
    full_id: str = "Unknown T1 G1"
    group: ParticipantGroup = ParticipantGroup.GROUP_1
    timepoint: ParticipantTimepoint = ParticipantTimepoint.T1
    date: str = ""
    # Raw extracted strings (before enum conversion) for display purposes
    group_str: str = "G1"
    timepoint_str: str = "T1"

    @property
    def participant_key(self) -> str:
        """Generate composite PARTICIPANT_KEY from id, group, and timepoint."""
        return f"{self.numerical_id}_{self.group}_{self.timepoint}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParticipantInfo:
        """Create from dictionary data."""
        return cls(
            numerical_id=data.get("numerical_participant_id", "Unknown"),
            full_id=data.get("full_participant_id", "Unknown T1 G1"),
            group=ParticipantGroup(data.get("participant_group", ParticipantGroup.GROUP_1)),
            timepoint=ParticipantTimepoint(data.get("participant_timepoint", ParticipantTimepoint.T1)),
            date=data.get("date", ""),
        )

    @classmethod
    def from_participant_key(cls, participant_key: str) -> ParticipantInfo:
        """Create from composite PARTICIPANT_KEY string."""
        parts = participant_key.split("_")
        if len(parts) != 3:
            msg = f"Invalid participant key format: {participant_key}"
            raise ValueError(msg)

        return cls(
            numerical_id=parts[0],
            group=ParticipantGroup(parts[1]),
            timepoint=ParticipantTimepoint(parts[2]),
        )


@dataclass
class ColumnMapping:
    """CSV column mapping configuration."""

    # Date/time columns
    date_column: str | None = None
    time_column: str | None = None
    datetime_column: str | None = None

    # Activity columns
    activity_column: str | None = None
    axis_x_column: str | None = None
    axis_z_column: str | None = None
    vector_magnitude_column: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for config storage."""
        result = {}
        if self.date_column:
            result[ConfigKey.DATE_COLUMN] = self.date_column
        if self.time_column:
            result[ConfigKey.TIME_COLUMN] = self.time_column
        if self.datetime_column:
            result["datetime_column"] = self.datetime_column
        if self.activity_column:
            result[ConfigKey.ACTIVITY_COLUMN] = self.activity_column
        if self.axis_x_column:
            result["axis_x_column"] = self.axis_x_column
        if self.axis_z_column:
            result["axis_z_column"] = self.axis_z_column
        if self.vector_magnitude_column:
            result["vector_magnitude_column"] = self.vector_magnitude_column
        return result


@dataclass
class FileInfo:
    """Information about a data file."""

    path: Path
    filename: str
    display_name: str

    @classmethod
    def from_path(cls, file_path: Path, base_path: Path) -> FileInfo:
        """Create FileInfo from path."""
        try:
            display_name = str(file_path.relative_to(base_path)) if file_path.parent != base_path else file_path.name
        except ValueError:
            display_name = file_path.name

        return cls(path=file_path, filename=file_path.name, display_name=display_name)


@dataclass(frozen=True)
class ImportedFileInfo:
    """Information about an imported file in the database."""

    filename: str
    participant_id: str
    date_range_start: str
    date_range_end: str
    record_count: int
    import_date: str
    has_metrics: bool


@dataclass(frozen=True)
class DeleteResult:
    """Result of a single file deletion operation."""

    status: DeleteStatus
    filename: str
    records_deleted: int = 0
    metrics_deleted: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class BatchDeleteResult:
    """Result of a batch file deletion operation."""

    total_requested: int
    successful: int
    failed: int
    results: list[DeleteResult]


@dataclass
class SleepPeriod:
    """Individual sleep period with extended marker support."""

    onset_timestamp: float | None = None
    offset_timestamp: float | None = None
    marker_index: int = 1
    marker_type: MarkerType = MarkerType.MAIN_SLEEP

    @property
    def is_complete(self) -> bool:
        """Check if both markers are set."""
        return self.onset_timestamp is not None and self.offset_timestamp is not None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate duration in seconds."""
        if self.is_complete:
            return self.offset_timestamp - self.onset_timestamp
        return None

    @property
    def duration_minutes(self) -> float | None:
        """Calculate duration in minutes."""
        if self.duration_seconds is not None:
            return self.duration_seconds / 60
        return None

    @property
    def duration_hours(self) -> float | None:
        """Calculate duration in hours."""
        if self.duration_seconds is not None:
            return self.duration_seconds / 3600
        return None

    def to_list(self) -> list[float]:
        """Convert to list format for compatibility."""
        if self.is_complete:
            return [self.onset_timestamp, self.offset_timestamp]
        return []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "onset_timestamp": self.onset_timestamp,
            "offset_timestamp": self.offset_timestamp,
            "marker_index": self.marker_index,
            "marker_type": self.marker_type.value if self.marker_type else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SleepPeriod:
        """Create from dictionary data."""
        from sleep_scoring_app.core.constants import MarkerType

        return cls(
            onset_timestamp=data.get("onset_timestamp"),
            offset_timestamp=data.get("offset_timestamp"),
            marker_index=data.get("marker_index", 1),
            marker_type=MarkerType(data["marker_type"]) if data.get("marker_type") else MarkerType.MAIN_SLEEP,
        )


@dataclass
class NonwearPeriod:
    """
    Represents a single nonwear or wear period.

    Used by both the Choi algorithm output and nonwear sensor data processing.
    """

    start_time: datetime
    end_time: datetime
    participant_id: str
    source: NonwearDataSource
    duration_minutes: int | None = None
    start_index: int | None = None
    end_index: int | None = None

    def __post_init__(self) -> None:
        """Ensure timestamps are datetime objects for consistent comparisons."""
        self.start_time = self._parse_datetime(self.start_time)
        self.end_time = self._parse_datetime(self.end_time)

    @staticmethod
    def _parse_datetime(timestamp: str | datetime) -> datetime:
        """Parse timestamp to datetime object."""
        if isinstance(timestamp, datetime):
            return timestamp
        return datetime.fromisoformat(str(timestamp))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            DatabaseColumn.START_TIME: self.start_time.isoformat() if isinstance(self.start_time, datetime) else str(self.start_time),
            DatabaseColumn.END_TIME: self.end_time.isoformat() if isinstance(self.end_time, datetime) else str(self.end_time),
            DatabaseColumn.PARTICIPANT_ID: self.participant_id,
            DatabaseColumn.PERIOD_TYPE: self.source,
            DatabaseColumn.DURATION_MINUTES: self.duration_minutes,
            DatabaseColumn.START_INDEX: self.start_index,
            DatabaseColumn.END_INDEX: self.end_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NonwearPeriod:
        """Create from dictionary data."""
        return cls(
            start_time=data.get(DatabaseColumn.START_TIME) or data.get("start_time"),
            end_time=data.get(DatabaseColumn.END_TIME) or data.get("end_time"),
            participant_id=data.get(DatabaseColumn.PARTICIPANT_ID) or data.get("participant_id", ""),
            source=NonwearDataSource(data.get(DatabaseColumn.PERIOD_TYPE) or data.get("source", NonwearDataSource.MANUAL_NWT)),
            duration_minutes=data.get(DatabaseColumn.DURATION_MINUTES) or data.get("duration_minutes"),
            start_index=data.get(DatabaseColumn.START_INDEX) or data.get("start_index"),
            end_index=data.get(DatabaseColumn.END_INDEX) or data.get("end_index"),
        )


@dataclass
class DailySleepMarkers:
    """Daily sleep markers with automatic main sleep/nap classification."""

    period_1: SleepPeriod | None = None
    period_2: SleepPeriod | None = None
    period_3: SleepPeriod | None = None
    period_4: SleepPeriod | None = None

    def get_all_periods(self) -> list[SleepPeriod]:
        """Get all non-None sleep periods."""
        return [p for p in [self.period_1, self.period_2, self.period_3, self.period_4] if p is not None]

    def get_complete_periods(self) -> list[SleepPeriod]:
        """Get all complete sleep periods."""
        return [p for p in self.get_all_periods() if p.is_complete]

    def get_main_sleep(self) -> SleepPeriod | None:
        """Get the longest sleep period (main sleep)."""
        complete_periods = self.get_complete_periods()
        if not complete_periods:
            return None
        return max(complete_periods, key=lambda p: p.duration_seconds or 0)

    def get_naps(self) -> list[SleepPeriod]:
        """Get all non-main sleep periods (naps)."""
        main_sleep = self.get_main_sleep()
        if main_sleep is None:
            return []
        return [p for p in self.get_complete_periods() if p is not main_sleep]

    def update_classifications(self) -> None:
        """Update marker type classifications based on duration."""
        main_sleep = self.get_main_sleep()
        for period in self.get_complete_periods():
            period.marker_type = MarkerType.MAIN_SLEEP if period is main_sleep else MarkerType.NAP

    def check_duration_tie(self) -> bool:
        """Check if there are periods with identical durations."""
        complete_periods = self.get_complete_periods()
        if len(complete_periods) < 2:
            return False
        durations = [p.duration_seconds for p in complete_periods]
        return len(durations) != len(set(durations))

    def count_periods(self) -> int:
        """Count number of defined periods."""
        return len(self.get_all_periods())

    def has_space_for_new_period(self) -> bool:
        """Check if we can add another period."""
        return self.count_periods() < MarkerLimits.MAX_SLEEP_PERIODS_PER_DAY

    def get_period_by_slot(self, slot: int) -> SleepPeriod | None:
        """Get period by slot number (1, 2, 3, or 4)."""
        if slot == 1:
            return self.period_1
        if slot == 2:
            return self.period_2
        if slot == 3:
            return self.period_3
        if slot == 4:
            return self.period_4
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "period_1": self.period_1.to_dict() if self.period_1 else None,
            "period_2": self.period_2.to_dict() if self.period_2 else None,
            "period_3": self.period_3.to_dict() if self.period_3 else None,
            "period_4": self.period_4.to_dict() if self.period_4 else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailySleepMarkers:
        """Create from dictionary data."""
        return cls(
            period_1=SleepPeriod.from_dict(data["period_1"]) if data.get("period_1") else None,
            period_2=SleepPeriod.from_dict(data["period_2"]) if data.get("period_2") else None,
            period_3=SleepPeriod.from_dict(data["period_3"]) if data.get("period_3") else None,
            period_4=SleepPeriod.from_dict(data["period_4"]) if data.get("period_4") else None,
        )


@dataclass
class ManualNonwearPeriod:
    """
    Individual manual nonwear period with timestamps.

    Similar to SleepPeriod but for user-placed nonwear markers.
    Uses dashed lines to distinguish from algorithmic nonwear.
    """

    start_timestamp: float | None = None
    end_timestamp: float | None = None
    marker_index: int = 1

    @property
    def is_complete(self) -> bool:
        """Check if both markers are set."""
        return self.start_timestamp is not None and self.end_timestamp is not None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate duration in seconds."""
        if self.is_complete:
            return self.end_timestamp - self.start_timestamp
        return None

    @property
    def duration_minutes(self) -> float | None:
        """Calculate duration in minutes."""
        if self.duration_seconds is not None:
            return self.duration_seconds / 60
        return None

    def to_list(self) -> list[float]:
        """Convert to list format for compatibility."""
        if self.is_complete:
            return [self.start_timestamp, self.end_timestamp]
        return []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "marker_index": self.marker_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManualNonwearPeriod:
        """Create from dictionary data."""
        return cls(
            start_timestamp=data.get("start_timestamp"),
            end_timestamp=data.get("end_timestamp"),
            marker_index=data.get("marker_index", 1),
        )


@dataclass
class DailyNonwearMarkers:
    """
    Daily manual nonwear markers container with 10 period slots.

    Follows the same fixed-slot pattern as DailySleepMarkers for consistency.
    Supports up to 10 user-placed nonwear periods per sleep_date.
    """

    period_1: ManualNonwearPeriod | None = None
    period_2: ManualNonwearPeriod | None = None
    period_3: ManualNonwearPeriod | None = None
    period_4: ManualNonwearPeriod | None = None
    period_5: ManualNonwearPeriod | None = None
    period_6: ManualNonwearPeriod | None = None
    period_7: ManualNonwearPeriod | None = None
    period_8: ManualNonwearPeriod | None = None
    period_9: ManualNonwearPeriod | None = None
    period_10: ManualNonwearPeriod | None = None

    def get_all_periods(self) -> list[ManualNonwearPeriod]:
        """Get all non-None nonwear periods."""
        periods = [
            self.period_1,
            self.period_2,
            self.period_3,
            self.period_4,
            self.period_5,
            self.period_6,
            self.period_7,
            self.period_8,
            self.period_9,
            self.period_10,
        ]
        return [p for p in periods if p is not None]

    def get_complete_periods(self) -> list[ManualNonwearPeriod]:
        """Get all complete nonwear periods (both start and end set)."""
        return [p for p in self.get_all_periods() if p.is_complete]

    def count_periods(self) -> int:
        """Count number of defined periods."""
        return len(self.get_all_periods())

    def has_space_for_new_period(self) -> bool:
        """Check if we can add another period."""
        return self.count_periods() < MarkerLimits.MAX_NONWEAR_PERIODS_PER_DAY

    def get_next_available_slot(self) -> int | None:
        """Get the next available slot number (1-10), or None if full."""
        for i in range(1, 11):
            if self.get_period_by_slot(i) is None:
                return i
        return None

    def get_period_by_slot(self, slot: int) -> ManualNonwearPeriod | None:
        """Get period by slot number (1-10)."""
        slot_map = {
            1: self.period_1,
            2: self.period_2,
            3: self.period_3,
            4: self.period_4,
            5: self.period_5,
            6: self.period_6,
            7: self.period_7,
            8: self.period_8,
            9: self.period_9,
            10: self.period_10,
        }
        return slot_map.get(slot)

    def set_period_by_slot(self, slot: int, period: ManualNonwearPeriod | None) -> None:
        """Set period by slot number (1-10)."""
        if slot == 1:
            self.period_1 = period
        elif slot == 2:
            self.period_2 = period
        elif slot == 3:
            self.period_3 = period
        elif slot == 4:
            self.period_4 = period
        elif slot == 5:
            self.period_5 = period
        elif slot == 6:
            self.period_6 = period
        elif slot == 7:
            self.period_7 = period
        elif slot == 8:
            self.period_8 = period
        elif slot == 9:
            self.period_9 = period
        elif slot == 10:
            self.period_10 = period

    def remove_period_by_slot(self, slot: int) -> None:
        """Remove a period by slot number."""
        self.set_period_by_slot(slot, None)

    def check_overlap(self, new_start: float, new_end: float, exclude_slot: int | None = None) -> bool:
        """
        Check if a new period would overlap with existing periods.

        Args:
            new_start: Start timestamp of new period
            new_end: End timestamp of new period
            exclude_slot: Slot to exclude from check (for editing existing period)

        Returns:
            True if overlap detected, False otherwise

        """
        for i in range(1, 11):
            if exclude_slot is not None and i == exclude_slot:
                continue
            period = self.get_period_by_slot(i)
            if period and period.is_complete:
                # Check for overlap: not (new_end <= existing_start or new_start >= existing_end)
                if not (new_end <= period.start_timestamp or new_start >= period.end_timestamp):
                    return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "period_1": self.period_1.to_dict() if self.period_1 else None,
            "period_2": self.period_2.to_dict() if self.period_2 else None,
            "period_3": self.period_3.to_dict() if self.period_3 else None,
            "period_4": self.period_4.to_dict() if self.period_4 else None,
            "period_5": self.period_5.to_dict() if self.period_5 else None,
            "period_6": self.period_6.to_dict() if self.period_6 else None,
            "period_7": self.period_7.to_dict() if self.period_7 else None,
            "period_8": self.period_8.to_dict() if self.period_8 else None,
            "period_9": self.period_9.to_dict() if self.period_9 else None,
            "period_10": self.period_10.to_dict() if self.period_10 else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyNonwearMarkers:
        """Create from dictionary data."""
        return cls(
            period_1=ManualNonwearPeriod.from_dict(data["period_1"]) if data.get("period_1") else None,
            period_2=ManualNonwearPeriod.from_dict(data["period_2"]) if data.get("period_2") else None,
            period_3=ManualNonwearPeriod.from_dict(data["period_3"]) if data.get("period_3") else None,
            period_4=ManualNonwearPeriod.from_dict(data["period_4"]) if data.get("period_4") else None,
            period_5=ManualNonwearPeriod.from_dict(data["period_5"]) if data.get("period_5") else None,
            period_6=ManualNonwearPeriod.from_dict(data["period_6"]) if data.get("period_6") else None,
            period_7=ManualNonwearPeriod.from_dict(data["period_7"]) if data.get("period_7") else None,
            period_8=ManualNonwearPeriod.from_dict(data["period_8"]) if data.get("period_8") else None,
            period_9=ManualNonwearPeriod.from_dict(data["period_9"]) if data.get("period_9") else None,
            period_10=ManualNonwearPeriod.from_dict(data["period_10"]) if data.get("period_10") else None,
        )


@dataclass
class SleepMetrics:
    """Comprehensive sleep scoring metrics."""

    # Participant information
    participant: ParticipantInfo = field(default_factory=ParticipantInfo)

    # File and analysis information
    filename: str = ""
    analysis_date: str = ""
    algorithm_type: AlgorithmType = AlgorithmType.SADEH_1994_ACTILIFE

    # Daily sleep markers (up to 4 periods with main/nap classification)
    daily_sleep_markers: DailySleepMarkers = field(default_factory=DailySleepMarkers)

    # Sleep timing
    onset_time: str = ""
    offset_time: str = ""

    # Sleep metrics
    total_sleep_time: float | None = None
    sleep_efficiency: float | None = None
    total_minutes_in_bed: float | None = None
    waso: float | None = None
    awakenings: int | None = None
    average_awakening_length: float | None = None

    # Activity metrics
    total_activity: int | None = None
    movement_index: float | None = None
    fragmentation_index: float | None = None
    sleep_fragmentation_index: float | None = None

    # Sleep algorithm identifier (for DI pattern)
    sleep_algorithm_name: str = "sadeh_1994_actilife"  # Default to Sadeh ActiLife version

    # Onset/offset rule identifier (for DI pattern)
    onset_offset_rule: str = "consecutive_3_5"  # Default to Consecutive 3/5 for backward compatibility

    # Algorithm-specific values (legacy columns - kept for backward compatibility)
    sadeh_onset: int | None = None
    sadeh_offset: int | None = None

    # Generic algorithm values (NEW - preferred for new code)
    sleep_algorithm_onset: int | None = None
    sleep_algorithm_offset: int | None = None

    # Overlapping nonwear minutes during sleep period
    # These are the sum of 0/1 values per minute epoch = total nonwear minutes
    overlapping_nonwear_minutes_algorithm: int | None = None
    overlapping_nonwear_minutes_sensor: int | None = None

    # Registry-based dynamic fields
    _dynamic_fields: dict[str, Any] = field(default_factory=dict, init=False)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def get_main_sleep_period(self) -> SleepPeriod | None:
        """Get the main sleep period (longest duration)."""
        return self.daily_sleep_markers.get_main_sleep()

    def get_nap_periods(self) -> list[SleepPeriod]:
        """Get all nap periods."""
        return self.daily_sleep_markers.get_naps()

    def has_multiple_sleep_periods(self) -> bool:
        """Check if there are multiple sleep periods defined."""
        return self.daily_sleep_markers.count_periods() > 1

    def update_time_strings(self) -> None:
        """Update onset_time and offset_time strings from main sleep period."""
        main_sleep = self.get_main_sleep_period()
        if main_sleep and main_sleep.is_complete:
            from datetime import datetime

            self.onset_time = datetime.fromtimestamp(main_sleep.onset_timestamp).strftime("%H:%M")
            self.offset_time = datetime.fromtimestamp(main_sleep.offset_timestamp).strftime("%H:%M")
        else:
            self.onset_time = ""
            self.offset_time = ""

    def to_export_dict_list(self) -> list[dict[str, Any]]:
        """Convert to list of export dictionaries - one per sleep period."""
        complete_periods = self.daily_sleep_markers.get_complete_periods()

        # Check if this is a NO_SLEEP case
        is_no_sleep = self.onset_time == "NO_SLEEP" and self.offset_time == "NO_SLEEP"

        if not complete_periods:
            if is_no_sleep:
                # NO_SLEEP case - return single row with NO_SLEEP marker type
                return [self._create_no_sleep_export_row()]
            # No complete periods and not NO_SLEEP - return single row with empty markers for compatibility
            return [self._create_export_row(None)]

        # Return one row per complete sleep period
        export_rows = []
        for period in complete_periods:
            export_rows.append(self._create_export_row(period))

        return export_rows

    def to_export_dict(self) -> dict[str, Any]:
        """Legacy method - exports main sleep period only for backward compatibility."""
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        return self._create_export_row(main_sleep)

    def _create_export_row(self, sleep_period: SleepPeriod | None) -> dict[str, Any]:
        """Create a single export row for a specific sleep period."""
        # Reconstruct full_id with correct format: ID + Timepoint + Group (use _str fields for extracted values)
        correct_full_id = f"{self.participant.numerical_id} {self.participant.timepoint_str} {self.participant.group_str}"

        # Base export data
        export_data = {
            ExportColumn.FULL_PARTICIPANT_ID: correct_full_id,
            ExportColumn.NUMERICAL_PARTICIPANT_ID: self.participant.numerical_id,
            ExportColumn.PARTICIPANT_GROUP: self.participant.group_str,
            ExportColumn.PARTICIPANT_TIMEPOINT: self.participant.timepoint_str,
            ExportColumn.SLEEP_ALGORITHM: self.algorithm_type,
            ExportColumn.SLEEP_DATE: self.analysis_date,  # The date/night being analyzed (from UI dropdown)
            ExportColumn.SAVED_AT: self.updated_at,
            "filename": self.filename,  # Keep for compatibility
        }

        # Add sleep period specific data
        if sleep_period and sleep_period.is_complete:
            onset_datetime = datetime.fromtimestamp(sleep_period.onset_timestamp)
            offset_datetime = datetime.fromtimestamp(sleep_period.offset_timestamp)
            export_data.update(
                {
                    ExportColumn.ONSET_DATE: onset_datetime.strftime("%Y-%m-%d"),
                    ExportColumn.ONSET_TIME: onset_datetime.strftime("%H:%M"),
                    ExportColumn.OFFSET_DATE: offset_datetime.strftime("%Y-%m-%d"),
                    ExportColumn.OFFSET_TIME: offset_datetime.strftime("%H:%M"),
                    ExportColumn.MARKER_TYPE: sleep_period.marker_type.value if sleep_period.marker_type else None,
                    ExportColumn.MARKER_INDEX: sleep_period.marker_index,
                }
            )
        else:
            # Empty period data for incomplete/missing periods
            export_data.update(
                {
                    ExportColumn.ONSET_DATE: "",
                    ExportColumn.ONSET_TIME: "",
                    ExportColumn.OFFSET_DATE: "",
                    ExportColumn.OFFSET_TIME: "",
                    ExportColumn.MARKER_TYPE: None,
                    ExportColumn.MARKER_INDEX: None,
                }
            )

        # Add data from column registry with period-specific calculations
        for column in column_registry.get_exportable():
            if column.export_column and column.export_column not in export_data:
                value = self._get_period_specific_field_value(column.name, sleep_period)
                # Include all columns, even with None values, for consistent CSV structure
                export_data[column.export_column] = value

        # Add dynamic fields
        for field_name, value in self._dynamic_fields.items():
            column = column_registry.get(field_name)
            if column and column.export_column and column.is_exportable:
                export_data[column.export_column] = value

        # Add ActiLife Sadeh data source information
        self._add_actilife_data_source_info(export_data)

        # Convert algorithm values to human-readable format
        self._convert_algorithm_values_for_export(export_data)

        return export_data

    def _create_no_sleep_export_row(self) -> dict[str, Any]:
        """Create export row for NO_SLEEP case."""
        # Reconstruct full_id with correct format: ID + Timepoint + Group (use _str fields for extracted values)
        correct_full_id = f"{self.participant.numerical_id} {self.participant.timepoint_str} {self.participant.group_str}"

        # Base export data
        export_data = {
            ExportColumn.FULL_PARTICIPANT_ID: correct_full_id,
            ExportColumn.NUMERICAL_PARTICIPANT_ID: self.participant.numerical_id,
            ExportColumn.PARTICIPANT_GROUP: self.participant.group_str,
            ExportColumn.PARTICIPANT_TIMEPOINT: self.participant.timepoint_str,
            ExportColumn.SLEEP_ALGORITHM: self.algorithm_type,
            ExportColumn.SLEEP_DATE: self.analysis_date,  # The date/night being analyzed (from UI dropdown)
            ExportColumn.SAVED_AT: self.updated_at,
            "filename": self.filename,  # Keep for compatibility
        }

        # Add NO_SLEEP specific data - use analysis date for both onset and offset
        if self.analysis_date:
            export_data.update(
                {
                    ExportColumn.ONSET_DATE: self.analysis_date,
                    ExportColumn.ONSET_TIME: "NO_SLEEP",
                    ExportColumn.OFFSET_DATE: self.analysis_date,
                    ExportColumn.OFFSET_TIME: "NO_SLEEP",
                    ExportColumn.MARKER_TYPE: "NO_SLEEP",
                    ExportColumn.MARKER_INDEX: 0,  # 0 for NO_SLEEP
                }
            )
        else:
            # Fallback to empty values if no analysis date
            export_data.update(
                {
                    ExportColumn.ONSET_DATE: "",
                    ExportColumn.ONSET_TIME: "NO_SLEEP",
                    ExportColumn.OFFSET_DATE: "",
                    ExportColumn.OFFSET_TIME: "NO_SLEEP",
                    ExportColumn.MARKER_TYPE: "NO_SLEEP",
                    ExportColumn.MARKER_INDEX: 0,
                }
            )

        # Add data from column registry - for NO_SLEEP, most metrics should be None
        for column in column_registry.get_exportable():
            if column.export_column and column.export_column not in export_data:
                # For NO_SLEEP, return None for most metrics except basic info
                export_data[column.export_column] = None

        # Add dynamic fields
        for field_name, value in self._dynamic_fields.items():
            column = column_registry.get(field_name)
            if column and column.export_column and column.is_exportable:
                export_data[column.export_column] = value

        # Convert algorithm values to human-readable format
        self._convert_algorithm_values_for_export(export_data)

        return export_data

    def _add_actilife_data_source_info(self, export_data: dict[str, Any]) -> None:
        """Add ActiLife Sadeh data source information to export data."""
        try:
            # Import here to avoid circular imports
            from sleep_scoring_app.services.unified_data_service import UnifiedDataService

            # Get or create unified data service
            unified_service = UnifiedDataService.get_instance()
            if unified_service is None:
                logger.warning("UnifiedDataService not available for ActiLife data source info")
                return

            # Get participant ID from filename
            participant_id = self.filename

            # Determine data source
            data_source = unified_service.get_sadeh_data_source(participant_id)
            export_data[ExportColumn.SADEH_DATA_SOURCE] = data_source.value

            # Get validation info if both sources are available
            config_manager = unified_service.config_manager
            if (
                config_manager
                and config_manager.config.actilife_validate_against_calculated
                and unified_service.has_actilife_sadeh_data(participant_id)
            ):
                validation_result = unified_service.validate_actilife_against_calculated(participant_id)
                if validation_result.get("status") == "success":
                    export_data[ExportColumn.ACTILIFE_VS_CALCULATED_AGREEMENT] = validation_result.get("agreement_percentage", None)
                    export_data[ExportColumn.ACTILIFE_VS_CALCULATED_DISAGREEMENTS] = validation_result.get("disagreements", None)
                else:
                    export_data[ExportColumn.ACTILIFE_VS_CALCULATED_AGREEMENT] = None
                    export_data[ExportColumn.ACTILIFE_VS_CALCULATED_DISAGREEMENTS] = None
            else:
                # No validation data available
                export_data[ExportColumn.ACTILIFE_VS_CALCULATED_AGREEMENT] = None
                export_data[ExportColumn.ACTILIFE_VS_CALCULATED_DISAGREEMENTS] = None

        except Exception as e:
            logger.warning("Error adding ActiLife data source info: %s", e)
            # Set default values on error
            export_data[ExportColumn.SADEH_DATA_SOURCE] = SadehDataSource.CALCULATED.value
            export_data[ExportColumn.ACTILIFE_VS_CALCULATED_AGREEMENT] = None
            export_data[ExportColumn.ACTILIFE_VS_CALCULATED_DISAGREEMENTS] = None

    def _convert_algorithm_values_for_export(self, export_data: dict[str, Any]) -> None:
        """Convert algorithm integer values to human-readable strings for export."""
        # Convert Sadeh algorithm values (0/1 to W/S)
        if ExportColumn.SADEH_ONSET in export_data:
            value = export_data[ExportColumn.SADEH_ONSET]
            if value == 0:
                export_data[ExportColumn.SADEH_ONSET] = AlgorithmResult.WAKE
            elif value == 1:
                export_data[ExportColumn.SADEH_ONSET] = AlgorithmResult.SLEEP

        if ExportColumn.SADEH_OFFSET in export_data:
            value = export_data[ExportColumn.SADEH_OFFSET]
            if value == 0:
                export_data[ExportColumn.SADEH_OFFSET] = AlgorithmResult.WAKE
            elif value == 1:
                export_data[ExportColumn.SADEH_OFFSET] = AlgorithmResult.SLEEP

        # Overlapping nonwear minutes are already integers representing minutes
        # No conversion needed - they are displayed as-is

    def to_database_dict(self) -> dict[str, Any]:
        """Convert to database storage format using column registry."""
        # Start with core database data
        db_data = {
            DatabaseColumn.FILENAME: self.filename,
            DatabaseColumn.PARTICIPANT_KEY: self.participant.participant_key,  # Add composite key
            DatabaseColumn.PARTICIPANT_ID: self.participant.numerical_id,
            DatabaseColumn.PARTICIPANT_GROUP: self.participant.group_str,
            DatabaseColumn.PARTICIPANT_TIMEPOINT: self.participant.timepoint_str,
            DatabaseColumn.ANALYSIS_DATE: self.analysis_date,
            DatabaseColumn.UPDATED_AT: self.updated_at,
        }

        # Add data from column registry
        for column in column_registry.get_all():
            if column.database_column and column.database_column not in db_data:
                value = self._get_field_value(column.name)
                # Include all columns for complete database records
                db_data[column.database_column] = value

        # Add dynamic fields
        for field_name, value in self._dynamic_fields.items():
            column = column_registry.get(field_name)
            if column and column.database_column:
                db_data[column.database_column] = value

        return db_data

    def to_dict(self) -> dict[str, Any]:
        """Convert to comprehensive dictionary format."""
        # Get all dataclass fields
        result = {}

        # Add core fields
        result.update(
            {
                "filename": self.filename,
                "analysis_date": self.analysis_date,
                "algorithm_type": self.algorithm_type,
                "onset_time": self.onset_time,
                "offset_time": self.offset_time,
                "total_sleep_time": self.total_sleep_time,
                "sleep_efficiency": self.sleep_efficiency,
                "total_minutes_in_bed": self.total_minutes_in_bed,
                "waso": self.waso,
                "awakenings": self.awakenings,
                "average_awakening_length": self.average_awakening_length,
                "total_activity": self.total_activity,
                "movement_index": self.movement_index,
                "fragmentation_index": self.fragmentation_index,
                "sleep_fragmentation_index": self.sleep_fragmentation_index,
                "sadeh_onset": self.sadeh_onset,
                "sadeh_offset": self.sadeh_offset,
                "overlapping_nonwear_minutes_algorithm": self.overlapping_nonwear_minutes_algorithm,
                "overlapping_nonwear_minutes_sensor": self.overlapping_nonwear_minutes_sensor,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
        )

        # Add participant info
        result.update(
            {
                "participant_numerical_id": self.participant.numerical_id,
                "participant_full_id": self.participant.full_id,
                "participant_group": self.participant.group_str,
                "participant_timepoint": self.participant.timepoint_str,
            },
        )

        # Add marker info (main sleep period for legacy compatibility)
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        result.update(
            {
                "onset_timestamp": main_sleep.onset_timestamp if main_sleep else None,
                "offset_timestamp": main_sleep.offset_timestamp if main_sleep else None,
            },
        )

        # Add full daily_sleep_markers structure for nap support
        result["daily_sleep_markers"] = self.daily_sleep_markers.to_dict()

        # Extract individual nap fields for database storage
        naps = self.daily_sleep_markers.get_naps()
        # Sort naps by onset time to ensure consistent ordering
        naps_sorted = sorted(naps, key=lambda p: p.onset_timestamp if p.onset_timestamp else float("inf"))

        # Add up to 3 naps as individual fields
        for i, nap in enumerate(naps_sorted[:3], start=1):
            if nap.is_complete and nap.onset_timestamp and nap.offset_timestamp:
                from datetime import datetime

                onset_time = datetime.fromtimestamp(nap.onset_timestamp).strftime("%H:%M")
                offset_time = datetime.fromtimestamp(nap.offset_timestamp).strftime("%H:%M")

                if i == 1:
                    result["nap_onset_time"] = onset_time
                    result["nap_offset_time"] = offset_time
                elif i == 2:
                    result["nap_onset_time_2"] = onset_time
                    result["nap_offset_time_2"] = offset_time
                elif i == 3:
                    result["nap_onset_time_3"] = onset_time
                    result["nap_offset_time_3"] = offset_time

        # Add dynamic fields
        result.update(self._dynamic_fields)

        return result

    def _get_field_value(self, field_name: str) -> Any:
        """Get value of a field by name, including dynamic fields."""
        # Check dynamic fields first
        if field_name in self._dynamic_fields:
            return self._dynamic_fields[field_name]

        # Check standard fields with various name mappings
        field_mappings = {
            "total_sleep_time": self.total_sleep_time,
            "sleep_efficiency": self.sleep_efficiency,
            "total_minutes_in_bed": self.total_minutes_in_bed,
            "waso": self.waso,
            "awakenings": self.awakenings,
            "average_awakening_length": self.average_awakening_length,
            "total_activity": self.total_activity,
            "movement_index": self.movement_index,
            "fragmentation_index": self.fragmentation_index,
            "sleep_fragmentation_index": self.sleep_fragmentation_index,
            # Sleep algorithm identifier (DI pattern)
            "sleep_algorithm_name": self.sleep_algorithm_name,
            # Onset/offset rule identifier (DI pattern)
            "onset_offset_rule": self.onset_offset_rule,
            # Legacy algorithm columns
            "sadeh_onset": self.sadeh_onset,
            "sadeh_offset": self.sadeh_offset,
            # Generic algorithm columns (maps to same values as sadeh for now)
            "sleep_algorithm_onset": self.sleep_algorithm_onset if self.sleep_algorithm_onset is not None else self.sadeh_onset,
            "sleep_algorithm_offset": self.sleep_algorithm_offset if self.sleep_algorithm_offset is not None else self.sadeh_offset,
            # Overlapping nonwear minutes during sleep period
            "overlapping_nonwear_minutes_algorithm": self.overlapping_nonwear_minutes_algorithm,
            "overlapping_nonwear_minutes_sensor": self.overlapping_nonwear_minutes_sensor,
            "onset_timestamp": self.daily_sleep_markers.get_main_sleep().onset_timestamp if self.daily_sleep_markers.get_main_sleep() else None,
            "offset_timestamp": self.daily_sleep_markers.get_main_sleep().offset_timestamp if self.daily_sleep_markers.get_main_sleep() else None,
            "onset_time": self.onset_time,
            "offset_time": self.offset_time,
            "algorithm_type": self.algorithm_type,
            "saved_date": self.updated_at,
            "participant_id": self.participant.numerical_id,
            "full_participant_id": self.participant.full_id,
            "participant_group": self.participant.group_str,
            "participant_timepoint": self.participant.timepoint_str,
            # Nap-related fields from diary data (stored in dynamic fields)
            "nap_occurred": self._dynamic_fields.get("nap_occurred"),
            "nap_onset_time": self._dynamic_fields.get("nap_onset_time"),
            "nap_offset_time": self._dynamic_fields.get("nap_offset_time"),
            "nap_onset_time_2": self._dynamic_fields.get("nap_onset_time_2"),
            "nap_offset_time_2": self._dynamic_fields.get("nap_offset_time_2"),
        }

        return field_mappings.get(field_name)

    def _get_period_specific_field_value(self, field_name: str, sleep_period: SleepPeriod | None) -> Any:
        """Get value of a field by name for a specific sleep period."""
        # Check dynamic fields first
        if field_name in self._dynamic_fields:
            return self._dynamic_fields[field_name]

        # For incomplete/missing periods, return None for metrics
        if sleep_period is None or not sleep_period.is_complete:
            period_specific_metrics = {
                "total_sleep_time",
                "sleep_efficiency",
                "total_minutes_in_bed",
                "waso",
                "awakenings",
                "average_awakening_length",
                "total_activity",
                "movement_index",
                "fragmentation_index",
                "sleep_fragmentation_index",
                "sadeh_onset",
                "sadeh_offset",
                "overlapping_nonwear_minutes_algorithm",
                "overlapping_nonwear_minutes_sensor",
            }
            if field_name in period_specific_metrics:
                return None

        # Get period-specific calculated metrics
        # First check if we have stored calculated metrics for this specific period
        period_metrics = self._get_stored_period_metrics(sleep_period)

        # If no stored metrics, use actual calculation or fallback logic
        main_sleep = self.daily_sleep_markers.get_main_sleep()
        is_main_sleep = sleep_period == main_sleep

        # Check standard fields with period-specific logic
        field_mappings = {
            "total_sleep_time": period_metrics.get("total_sleep_time") if period_metrics else (self.total_sleep_time if is_main_sleep else None),
            "sleep_efficiency": period_metrics.get("sleep_efficiency") if period_metrics else (self.sleep_efficiency if is_main_sleep else None),
            "total_minutes_in_bed": period_metrics.get("total_minutes_in_bed")
            if period_metrics
            else (self.total_minutes_in_bed if is_main_sleep else None),
            "waso": period_metrics.get("waso") if period_metrics else (self.waso if is_main_sleep else None),
            "awakenings": period_metrics.get("awakenings") if period_metrics else (self.awakenings if is_main_sleep else None),
            "average_awakening_length": period_metrics.get("average_awakening_length")
            if period_metrics
            else (self.average_awakening_length if is_main_sleep else None),
            "total_activity": period_metrics.get("total_activity") if period_metrics else (self.total_activity if is_main_sleep else None),
            "movement_index": period_metrics.get("movement_index") if period_metrics else (self.movement_index if is_main_sleep else None),
            "fragmentation_index": period_metrics.get("fragmentation_index")
            if period_metrics
            else (self.fragmentation_index if is_main_sleep else None),
            "sleep_fragmentation_index": period_metrics.get("sleep_fragmentation_index")
            if period_metrics
            else (self.sleep_fragmentation_index if is_main_sleep else None),
            # Sleep algorithm identifier (DI pattern) - same for all periods
            "sleep_algorithm_name": self.sleep_algorithm_name,
            # Onset/offset rule identifier (DI pattern) - same for all periods
            "onset_offset_rule": self.onset_offset_rule,
            # Legacy algorithm columns
            "sadeh_onset": period_metrics.get("sadeh_onset") if period_metrics else (self.sadeh_onset if is_main_sleep else None),
            "sadeh_offset": period_metrics.get("sadeh_offset") if period_metrics else (self.sadeh_offset if is_main_sleep else None),
            # Generic algorithm columns
            "sleep_algorithm_onset": period_metrics.get("sleep_algorithm_onset")
            if period_metrics
            else (self.sleep_algorithm_onset if self.sleep_algorithm_onset is not None else (self.sadeh_onset if is_main_sleep else None)),
            "sleep_algorithm_offset": period_metrics.get("sleep_algorithm_offset")
            if period_metrics
            else (self.sleep_algorithm_offset if self.sleep_algorithm_offset is not None else (self.sadeh_offset if is_main_sleep else None)),
            # Overlapping nonwear minutes during sleep period
            "overlapping_nonwear_minutes_algorithm": period_metrics.get("overlapping_nonwear_minutes_algorithm")
            if period_metrics
            else (self.overlapping_nonwear_minutes_algorithm if is_main_sleep else None),
            "overlapping_nonwear_minutes_sensor": self._calculate_nwt_overlapping_minutes(sleep_period)
            if sleep_period and sleep_period.is_complete
            else None,
            # Period-specific timestamps
            "onset_timestamp": sleep_period.onset_timestamp if sleep_period and sleep_period.is_complete else None,
            "offset_timestamp": sleep_period.offset_timestamp if sleep_period and sleep_period.is_complete else None,
            "onset_time": datetime.fromtimestamp(sleep_period.onset_timestamp).strftime("%H:%M") if sleep_period and sleep_period.is_complete else "",
            "offset_time": datetime.fromtimestamp(sleep_period.offset_timestamp).strftime("%H:%M")
            if sleep_period and sleep_period.is_complete
            else "",
            # Non-period-specific fields (same for all periods)
            "algorithm_type": self.algorithm_type,
            "saved_date": self.updated_at,
            "participant_id": self.participant.numerical_id,
            "full_participant_id": self.participant.full_id,
            "participant_group": self.participant.group_str,
            "participant_timepoint": self.participant.timepoint_str,
            # Nap-related fields from diary data (stored in dynamic fields) - same for all periods
            "nap_occurred": self._dynamic_fields.get("nap_occurred"),
            "nap_onset_time": self._dynamic_fields.get("nap_onset_time"),
            "nap_offset_time": self._dynamic_fields.get("nap_offset_time"),
            "nap_onset_time_2": self._dynamic_fields.get("nap_onset_time_2"),
            "nap_offset_time_2": self._dynamic_fields.get("nap_offset_time_2"),
        }

        return field_mappings.get(field_name)

    def _get_stored_period_metrics(self, sleep_period: SleepPeriod | None) -> dict[str, Any]:
        """Get stored calculated metrics for a specific sleep period."""
        if not sleep_period or not sleep_period.is_complete:
            return {}

        # Check if we have per-period metrics stored in dynamic fields
        period_key = f"period_{sleep_period.marker_index}_metrics"
        stored_metrics = self._dynamic_fields.get(period_key, {})

        # If no stored metrics, fall back to main sleep metrics for main sleep period only
        if not stored_metrics and sleep_period == self.daily_sleep_markers.get_main_sleep():
            return {
                "total_sleep_time": self.total_sleep_time,
                "sleep_efficiency": self.sleep_efficiency,
                "total_minutes_in_bed": self.total_minutes_in_bed,
                "waso": self.waso,
                "awakenings": self.awakenings,
                "average_awakening_length": self.average_awakening_length,
                "total_activity": self.total_activity,
                "movement_index": self.movement_index,
                "fragmentation_index": self.fragmentation_index,
                "sleep_fragmentation_index": self.sleep_fragmentation_index,
                "sadeh_onset": self.sadeh_onset,
                "sadeh_offset": self.sadeh_offset,
                "overlapping_nonwear_minutes_algorithm": self.overlapping_nonwear_minutes_algorithm,
                "overlapping_nonwear_minutes_sensor": self.overlapping_nonwear_minutes_sensor,
            }

        return stored_metrics

    def store_period_metrics(self, sleep_period: SleepPeriod, metrics: dict[str, Any]) -> None:
        """Store calculated metrics for a specific sleep period."""
        if not sleep_period or not sleep_period.is_complete:
            return

        period_key = f"period_{sleep_period.marker_index}_metrics"
        self._dynamic_fields[period_key] = metrics

    def _calculate_nwt_overlapping_minutes(self, sleep_period: SleepPeriod) -> int | None:
        """
        Calculate total overlapping nonwear minutes from NWT sensor data.

        Returns the total minutes of NWT sensor-detected nonwear that overlap
        with the sleep period.
        """
        if not sleep_period or not sleep_period.is_complete:
            return None

        try:
            from datetime import datetime

            from sleep_scoring_app.data.database import DatabaseManager
            from sleep_scoring_app.services.nonwear_service import NonwearDataService, NonwearDataSource

            # Use cached database manager to avoid creating thousands of instances during export
            global _cached_db_manager
            if _cached_db_manager is None:
                _cached_db_manager = DatabaseManager()

            nonwear_service = NonwearDataService(_cached_db_manager)

            # Convert timestamps to datetime objects
            sleep_start = datetime.fromtimestamp(sleep_period.onset_timestamp)
            sleep_end = datetime.fromtimestamp(sleep_period.offset_timestamp)

            # Query NWT sensor periods for this file and time range
            nwt_periods = nonwear_service.get_nonwear_periods_for_file(
                filename=self.filename, source=NonwearDataSource.NONWEAR_SENSOR, start_time=sleep_start, end_time=sleep_end
            )

            # Calculate total overlapping minutes
            total_overlapping_minutes = 0
            for period in nwt_periods:
                # Handle both datetime objects and string timestamps
                period_start = period.start_time if isinstance(period.start_time, datetime) else datetime.fromisoformat(period.start_time)
                period_end = period.end_time if isinstance(period.end_time, datetime) else datetime.fromisoformat(period.end_time)

                # Calculate the overlap between sleep period and nonwear period
                overlap_start = max(sleep_start, period_start)
                overlap_end = min(sleep_end, period_end)

                if overlap_start < overlap_end:
                    # There is an overlap - calculate minutes
                    overlap_seconds = (overlap_end - overlap_start).total_seconds()
                    total_overlapping_minutes += int(overlap_seconds / 60)

            return total_overlapping_minutes

        except Exception as e:
            logger.warning("Error calculating NWT overlapping minutes: %s", e)
            return None

    def set_dynamic_field(self, field_name: str, value: Any) -> None:
        """Set a dynamic field value."""
        self._dynamic_fields[field_name] = value

    def get_dynamic_field(self, field_name: str, default: Any = None) -> Any:
        """Get a dynamic field value."""
        return self._dynamic_fields.get(field_name, default)


@dataclass
class AppConfig:
    """Application configuration settings with hardcoded defaults."""

    # Directory settings (configurable via QSettings)
    data_folder: str = ""
    export_directory: str = ""
    import_activity_directory: str = ""
    import_nonwear_directory: str = ""
    diary_import_directory: str = ""
    actilife_import_directory: str = ""

    # Hardcoded data settings (no longer configurable)
    data_directory: str = ""  # Directory path for ActiLife import browsing
    epoch_length: int = 60
    skip_rows: int = 10
    use_database: bool = True  # Prefer imported database files over CSV files

    # Hardcoded column mappings
    column_mapping: ColumnMapping = field(default_factory=ColumnMapping)
    preferred_activity_column: ActivityDataPreference = ActivityDataPreference.AXIS_Y
    choi_activity_column: ActivityDataPreference = ActivityDataPreference.AXIS_Y

    # Hardcoded window settings
    window_width: int = 1200
    window_height: int = 800

    # Recently used files (stored in QSettings)
    recent_files: list[str] = field(default_factory=list)

    # Hardcoded export settings
    export_columns: list[str] = field(default_factory=list)
    export_grouping: int = 0  # 0=all, 1=participant, 2=group, 3=timepoint
    include_headers: bool = True
    include_metadata: bool = True
    include_config_in_metadata: bool = True  # Include config settings in CSV metadata header
    export_config_sidecar: bool = True  # Export config as separate .config.csv file
    export_nonwear_separate: bool = True  # Export nonwear markers to separate file

    # Hardcoded import settings
    nwt_data_folder: str = ""  # NWT sensor data folder
    import_skip_rows: int = 10
    import_force_reimport: bool = False

    # Hardcoded study days settings
    study_days_use_database: bool = True
    study_days_file: str = ""  # Direct load file path
    study_days_import_file: str = ""  # Import to database file path

    # Hardcoded diary settings
    diary_use_database: bool = True
    diary_skip_rows: int = 1  # Diaries typically have fewer header rows

    # Hardcoded ActiLife Sadeh settings
    use_actilife_sadeh: bool = False  # Enable ActiLife Sadeh data usage
    actilife_skip_rows: int = 3  # Header rows to skip in ActiLife CSV files
    actilife_prefer_over_calculated: bool = True  # Prefer ActiLife over calculated when available
    actilife_validate_against_calculated: bool = False  # Validate ActiLife against calculated

    # Hardcoded study settings - defaults match DEMO data patterns
    study_default_group: str = "G1"
    study_default_timepoint: str = "T1"
    study_valid_groups: list[str] = field(default_factory=lambda: ["G1", "DEMO"])
    study_valid_timepoints: list[str] = field(default_factory=lambda: ["T1", "T2", "T3"])
    study_unknown_value: str = "Unknown"
    study_group_pattern: str = r"(G1|DEMO)"
    study_timepoint_pattern: str = r"(T[123])"
    study_participant_id_patterns: list[str] = field(default_factory=lambda: [r"(DEMO-\d{3})"])

    # Device/Format Configuration
    device_preset: str = "actigraph"
    custom_date_column: str = ""
    custom_time_column: str = ""
    custom_activity_column: str = ""  # Primary activity column (for display/general use)
    datetime_combined: bool = False

    # Custom axis column mappings (for Generic CSV)
    # User specifies which CSV column maps to each axis
    custom_axis_y_column: str = ""  # Y-axis (vertical) - Required for Sadeh algorithm
    custom_axis_x_column: str = ""  # X-axis (lateral)
    custom_axis_z_column: str = ""  # Z-axis (forward)
    custom_vector_magnitude_column: str = ""  # Recommended for Choi algorithm

    # Algorithm Configuration
    night_start_hour: int = 22
    night_end_hour: int = 7
    max_sleep_periods: int = 4  # 1 main sleep + up to 3 naps (hardcoded, not configurable)
    choi_axis: str = ActivityDataPreference.VECTOR_MAGNITUDE

    # Data Paradigm Selection (controls file types and available algorithms)
    data_paradigm: str = StudyDataParadigm.EPOCH_BASED  # StudyDataParadigm enum value

    # Sleep Scoring Algorithm Selection (DI pattern)
    sleep_algorithm_id: str = "sadeh_1994_actilife"  # Algorithm identifier for factory

    # Onset/Offset Rule Selection (DI pattern)
    onset_offset_rule_id: str = "consecutive_3_5"  # Rule identifier for factory

    # Raw Data Pipeline (gt3x) - for future use
    data_source_type: str = "csv"  # "csv" or "gt3x"
    gt3x_folder: str = ""

    # Data Source Configuration (DI pattern)
    data_source_type_id: str = "csv"  # Factory identifier for data source loader
    csv_skip_rows: int = 10  # CSV-specific: rows to skip
    gt3x_epoch_length: int = 60  # GT3X-specific: epoch length in seconds
    gt3x_return_raw: bool = False  # GT3X-specific: return raw acceleration data

    # Nonwear Detection Algorithm Selection (DI pattern)
    nonwear_algorithm_id: str = "choi_2011"  # Algorithm identifier for factory

    # Automatic Processing
    auto_place_diary_markers: bool = True
    auto_place_apply_rules_until_convergence: bool = True
    auto_detect_nonwear_overlap: bool = True
    auto_scroll_to_unmarked: bool = True
    auto_advance_after_save: bool = False
    auto_populate_nap_markers: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage (only directory paths)."""
        return {
            ConfigKey.DATA_FOLDER: self.data_folder,
            "export_directory": self.export_directory,
            "import_activity_directory": self.import_activity_directory,
            "import_nonwear_directory": self.import_nonwear_directory,
            "diary_import_directory": self.diary_import_directory,
            "actilife_import_directory": self.actilife_import_directory,
        }

    def to_full_dict(self, include_paths: bool = False) -> dict[str, Any]:
        """
        Convert to comprehensive dictionary for config export/sharing.

        This focuses on RESEARCH-RELEVANT settings that affect reproducibility:
        - Study identification patterns (how participants are identified)
        - Algorithm parameters (how sleep is scored)
        - Data processing settings (how data is interpreted)

        UI preferences (colors, window size) are NOT included as they don't
        affect research outcomes.

        Args:
            include_paths: If True, include directory paths (may contain sensitive info).
                          If False, exclude paths for safe sharing.

        Returns:
            Complete configuration dictionary suitable for export.

        """
        # Import app version from package
        from sleep_scoring_app import __version__ as app_version

        # Config schema version - increment when config structure changes
        # This is separate from app version to track config compatibility
        CONFIG_SCHEMA_VERSION = "1.0.0"

        config_dict = {
            # Version info for compatibility checking
            "config_schema_version": CONFIG_SCHEMA_VERSION,  # Schema version for config structure
            "app_version": app_version,  # App version that created this config
            "app_name": "SleepScoringApp",
            # ============================================================
            # STUDY IDENTIFICATION SETTINGS (Critical for reproducibility)
            # ============================================================
            "study": {
                # Regex patterns for extracting info from filenames
                "participant_id_patterns": self.study_participant_id_patterns,
                "timepoint_pattern": self.study_timepoint_pattern,
                "group_pattern": self.study_group_pattern,
                # Valid values for categorical fields
                "valid_groups": self.study_valid_groups,
                "valid_timepoints": self.study_valid_timepoints,
                # Default values when extraction fails
                "default_group": self.study_default_group,
                "default_timepoint": self.study_default_timepoint,
                "unknown_value": self.study_unknown_value,
            },
            # ============================================================
            # ALGORITHM SETTINGS (Critical for reproducibility)
            # ============================================================
            "algorithm": {
                # Sleep scoring algorithm selection (DI pattern)
                "sleep_algorithm_id": self.sleep_algorithm_id,  # e.g., "sadeh_1994_actilife", "sadeh_1994_original", "cole_kripke_1992"
                # Onset/offset rule selection (DI pattern)
                "onset_offset_rule_id": self.onset_offset_rule_id,  # e.g., "consecutive_3_5", "tudor_locke_2014"
                # Night definition for sleep period detection
                "night_start_hour": self.night_start_hour,
                "night_end_hour": self.night_end_hour,
                # Nonwear detection algorithm (DI pattern)
                "choi_axis": self.choi_axis,  # Which axis to use for nonwear detection
                "nonwear_algorithm_id": self.nonwear_algorithm_id,
            },
            # ============================================================
            # DATA PROCESSING SETTINGS (Important for data interpretation)
            # ============================================================
            "data_processing": {
                "epoch_length": self.epoch_length,
                "skip_rows": self.skip_rows,  # Header rows in CSV files
                "preferred_activity_column": self.preferred_activity_column,
                "device_preset": self.device_preset,
            },
        }

        # Optionally include paths (for full backup, not for sharing)
        if include_paths:
            config_dict["paths"] = {
                "data_folder": self.data_folder,
                "export_directory": self.export_directory,
                "import_activity_directory": self.import_activity_directory,
                "import_nonwear_directory": self.import_nonwear_directory,
                "diary_import_directory": self.diary_import_directory,
                "actilife_import_directory": self.actilife_import_directory,
            }

        return config_dict

    def to_flat_dict(self) -> dict[str, Any]:
        """
        Convert to flat key-value dictionary for CSV sidecar export.

        Returns:
            Flat dictionary with dot-notation keys for CSV export.

        """
        full_dict = self.to_full_dict(include_paths=False)
        flat = {}

        def flatten(obj: dict | list | Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{prefix}.{key}" if prefix else key
                    flatten(value, new_key)
            elif isinstance(obj, list):
                flat[prefix] = "|".join(str(v) for v in obj) if obj else ""
            else:
                flat[prefix] = str(obj) if obj is not None else ""

        flatten(full_dict)
        return flat

    @classmethod
    def from_full_dict(cls, data: dict[str, Any]) -> AppConfig:
        """
        Create AppConfig from a full config dictionary (for import).

        Loads RESEARCH-RELEVANT settings only:
        - Study identification patterns (participant ID, group, timepoint extraction)
        - Algorithm parameters (Sadeh variant, night hours, Choi settings)
        - Data processing settings (epoch length, skip rows)

        Args:
            data: Configuration dictionary from to_full_dict() or loaded from file.

        Returns:
            New AppConfig instance with loaded settings.

        """
        config = cls.create_default()

        # Study identification settings (Critical for reproducibility)
        if "study" in data:
            st = data["study"]
            config.study_participant_id_patterns = st.get("participant_id_patterns", config.study_participant_id_patterns)
            config.study_timepoint_pattern = st.get("timepoint_pattern", config.study_timepoint_pattern)
            config.study_group_pattern = st.get("group_pattern", config.study_group_pattern)
            config.study_valid_groups = st.get("valid_groups", config.study_valid_groups)
            config.study_valid_timepoints = st.get("valid_timepoints", config.study_valid_timepoints)
            config.study_default_group = st.get("default_group", config.study_default_group)
            config.study_default_timepoint = st.get("default_timepoint", config.study_default_timepoint)
            config.study_unknown_value = st.get("unknown_value", config.study_unknown_value)

        # Algorithm settings (Critical for reproducibility)
        if "algorithm" in data:
            alg = data["algorithm"]
            config.sleep_algorithm_id = alg.get("sleep_algorithm_id", config.sleep_algorithm_id)
            config.onset_offset_rule_id = alg.get("onset_offset_rule_id", config.onset_offset_rule_id)
            config.night_start_hour = alg.get("night_start_hour", config.night_start_hour)
            config.night_end_hour = alg.get("night_end_hour", config.night_end_hour)
            config.choi_axis = alg.get("choi_axis", config.choi_axis)
            config.nonwear_algorithm_id = alg.get("nonwear_algorithm_id", config.nonwear_algorithm_id)

        # Data processing settings
        if "data_processing" in data:
            d = data["data_processing"]
            config.epoch_length = d.get("epoch_length", config.epoch_length)
            config.skip_rows = d.get("skip_rows", config.skip_rows)
            config.preferred_activity_column = d.get("preferred_activity_column", config.preferred_activity_column)
            config.device_preset = d.get("device_preset", config.device_preset)

        # Paths (only if provided - typically not shared between researchers)
        if "paths" in data:
            paths = data["paths"]
            config.data_folder = paths.get("data_folder", config.data_folder)
            config.export_directory = paths.get("export_directory", config.export_directory)
            config.import_activity_directory = paths.get("import_activity_directory", config.import_activity_directory)
            config.import_nonwear_directory = paths.get("import_nonwear_directory", config.import_nonwear_directory)
            config.diary_import_directory = paths.get("diary_import_directory", config.diary_import_directory)
            config.actilife_import_directory = paths.get("actilife_import_directory", config.actilife_import_directory)

        return config

    @classmethod
    def from_dict(cls, data: dict[str, Any], validate_complete: bool = True) -> AppConfig:
        """Create from dictionary data (loads only directory paths, uses hardcoded defaults for everything else)."""
        # Create instance with hardcoded defaults, only override directory paths
        return cls(
            data_folder=data.get(ConfigKey.DATA_FOLDER, ""),
            export_directory=data.get("export_directory", ""),
            import_activity_directory=data.get("import_activity_directory", ""),
            import_nonwear_directory=data.get("import_nonwear_directory", ""),
            diary_import_directory=data.get("diary_import_directory", ""),
            actilife_import_directory=data.get("actilife_import_directory", ""),
            # All other values use hardcoded defaults defined in the dataclass
        )

    @classmethod
    def create_default(cls) -> AppConfig:
        """Create default configuration with all hardcoded values."""
        return cls()


@dataclass
class ColumnAnalysis:
    """Results of column analysis across CSV files."""

    files: dict[str, list[str]] = field(default_factory=dict)
    common_columns: list[str] = field(default_factory=list)
    all_columns: list[str] = field(default_factory=list)
    column_compatibility: bool = True
    file_count: int = 0


# ============================================================================
# DIARY-SPECIFIC DATACLASSES
# ============================================================================


@dataclass
class DiaryColumnMapping:
    """Diary column mapping result."""

    participant_id_column_name: str | None = None
    sleep_onset_time_column_name: str | None = None
    sleep_offset_time_column_name: str | None = None
    napped_column_name: str | None = None
    nap_onset_time_column_name: str | None = None
    nap_offset_time_column_name: str | None = None
    nonwear_occurred_column_name: str | None = None
    nonwear_reason_column_names: str | None = None
    nonwear_start_time_column_names: str | None = None
    nonwear_end_time_column_names: str | None = None
    in_bed_time_column_name: str | None = None
    out_of_bed_time_column_name: str | None = None
    date_of_last_night_column_name: str | None = None
    sleep_onset_date_column_name: str | None = None
    sleep_offset_date_column_name: str | None = None
    todays_date_column_name: str | None = None
    nap_onset_date_column_name: str | None = None
    nap_offset_date_column_name: str | None = None
    nap_onset_time_column_names: str | None = None  # For multiple nap columns
    nap_offset_time_column_names: str | None = None  # For multiple nap columns
    diary_completed_for_current_day_column_name: str | None = None
    activity_columns: str | None = None
    expected_diary_entry_date_column_name: str | None = None
    diary_submission_date_column_name: str | None = None
    participant_timepoint_column_name: str | None = None
    participant_group_column_name: str | None = None
    auto_calculated_columns: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiaryColumnMapping:
        """Create from dictionary data."""
        auto_calc = data.get("auto_calculated_columns", {})

        return cls(
            participant_id_column_name=data.get("participant_id_column_name"),
            sleep_onset_time_column_name=data.get("sleep_onset_time_column_name"),
            sleep_offset_time_column_name=data.get("sleep_offset_time_column_name"),
            napped_column_name=data.get("napped_column_name"),
            nap_onset_time_column_name=data.get("nap_onset_time_column_name"),
            nap_offset_time_column_name=data.get("nap_offset_time_column_name"),
            nonwear_occurred_column_name=data.get("nonwear_occurred_column_name"),
            nonwear_reason_column_names=data.get("nonwear_reason_column_names"),
            nonwear_start_time_column_names=data.get("nonwear_start_time_column_names"),
            nonwear_end_time_column_names=data.get("nonwear_end_time_column_names"),
            in_bed_time_column_name=data.get("in_bed_time_column_name"),
            out_of_bed_time_column_name=data.get("out_of_bed_time_column_name"),
            date_of_last_night_column_name=data.get("date_of_last_night_column_name"),
            sleep_onset_date_column_name=data.get("sleep_onset_date_column_name"),
            sleep_offset_date_column_name=data.get("sleep_offset_date_column_name"),
            todays_date_column_name=data.get("todays_date_column_name"),
            nap_onset_date_column_name=data.get("nap_onset_date_column_name"),
            nap_offset_date_column_name=data.get("nap_offset_date_column_name"),
            nap_onset_time_column_names=data.get("nap_onset_time_column_names"),
            nap_offset_time_column_names=data.get("nap_offset_time_column_names"),
            diary_completed_for_current_day_column_name=data.get("diary_completed_for_current_day_column_name"),
            activity_columns=data.get("activity_columns"),
            expected_diary_entry_date_column_name=data.get("expected_diary_entry_date_column_name"),
            diary_submission_date_column_name=data.get("diary_submission_date_column_name"),
            participant_timepoint_column_name=data.get("participant_timepoint_column_name"),
            participant_group_column_name=data.get("participant_group_column_name"),
            auto_calculated_columns=auto_calc,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "participant_id_column_name": self.participant_id_column_name,
            "sleep_onset_time_column_name": self.sleep_onset_time_column_name,
            "sleep_offset_time_column_name": self.sleep_offset_time_column_name,
            "napped_column_name": self.napped_column_name,
            "nap_onset_time_column_name": self.nap_onset_time_column_name,
            "nap_offset_time_column_name": self.nap_offset_time_column_name,
            "nonwear_occurred_column_name": self.nonwear_occurred_column_name,
            "nonwear_reason_column_names": self.nonwear_reason_column_names,
            "nonwear_start_time_column_names": self.nonwear_start_time_column_names,
            "nonwear_end_time_column_names": self.nonwear_end_time_column_names,
            "in_bed_time_column_name": self.in_bed_time_column_name,
            "out_of_bed_time_column_name": self.out_of_bed_time_column_name,
            "date_of_last_night_column_name": self.date_of_last_night_column_name,
            "sleep_onset_date_column_name": self.sleep_onset_date_column_name,
            "sleep_offset_date_column_name": self.sleep_offset_date_column_name,
            "todays_date_column_name": self.todays_date_column_name,
            "nap_onset_date_column_name": self.nap_onset_date_column_name,
            "nap_offset_date_column_name": self.nap_offset_date_column_name,
            "nap_onset_time_column_names": self.nap_onset_time_column_names,
            "nap_offset_time_column_names": self.nap_offset_time_column_names,
            "diary_completed_for_current_day_column_name": self.diary_completed_for_current_day_column_name,
            "activity_columns": self.activity_columns,
            "expected_diary_entry_date_column_name": self.expected_diary_entry_date_column_name,
            "diary_submission_date_column_name": self.diary_submission_date_column_name,
            "participant_timepoint_column_name": self.participant_timepoint_column_name,
            "participant_group_column_name": self.participant_group_column_name,
            "auto_calculated_columns": self.auto_calculated_columns,
        }


@dataclass
class DiaryFileInfo:
    """Information about a diary file to be processed."""

    file_path: Path
    file_type: str  # csv, xlsx, xls
    sheet_names: list[str] = field(default_factory=list)
    participant_info: ParticipantInfo | None = None
    column_mapping: DiaryColumnMapping | None = None
    import_status: str = "pending"
    error_message: str = ""
    total_records: int = 0

    @classmethod
    def from_path(cls, file_path: Path) -> DiaryFileInfo:
        """Create from file path."""
        file_extension = file_path.suffix.lower()

        if file_extension == ".csv":
            file_type = "csv"
            sheet_names = []
        elif file_extension in [".xlsx", ".xls"]:
            file_type = "excel"
            # Sheet names will be populated during processing
            sheet_names = []
        else:
            msg = f"Unsupported file format: {file_extension}"
            raise ValueError(msg)

        return cls(
            file_path=file_path,
            file_type=file_type,
            sheet_names=sheet_names,
        )


@dataclass
class DiaryEntry:
    """Single diary entry record."""

    participant_id: str
    diary_date: str
    filename: str
    # Core sleep timing
    bedtime: str | None = None
    wake_time: str | None = None
    sleep_onset_time: str | None = None
    sleep_offset_time: str | None = None
    in_bed_time: str | None = None

    # Sleep quality and metrics
    sleep_quality: int | None = None

    # Nap information
    nap_occurred: int | None = None  # Number of naps (0-3)
    nap_onset_time: str | None = None
    nap_offset_time: str | None = None
    # Second nap
    nap_onset_time_2: str | None = None
    nap_offset_time_2: str | None = None
    # Third nap
    nap_onset_time_3: str | None = None
    nap_offset_time_3: str | None = None

    # Nonwear information
    nonwear_occurred: bool | None = None
    nonwear_reason: str | None = None
    nonwear_start_time: str | None = None
    nonwear_end_time: str | None = None
    # Additional nonwear periods
    nonwear_reason_2: str | None = None
    nonwear_start_time_2: str | None = None
    nonwear_end_time_2: str | None = None
    nonwear_reason_3: str | None = None
    nonwear_start_time_3: str | None = None
    nonwear_end_time_3: str | None = None

    # Additional metadata
    diary_notes: str | None = None
    night_number: int | None = None

    # Import metadata
    import_date: str = field(default_factory=lambda: datetime.now().isoformat())
    original_column_mapping: str | None = None  # JSON string of original mapping

    @property
    def participant_key(self) -> str:
        """Generate composite PARTICIPANT_KEY from participant_id."""
        from sleep_scoring_app.utils.participant_extractor import extract_participant_info

        info = extract_participant_info(self.participant_id)
        return info.participant_key

    def to_database_dict(self) -> dict[str, Any]:
        """Convert to database storage format (only columns that exist in diary_data table)."""
        return {
            DatabaseColumn.PARTICIPANT_KEY: self.participant_key,  # Add composite key
            DatabaseColumn.PARTICIPANT_ID: self.participant_id,
            DatabaseColumn.DIARY_DATE: self.diary_date,
            DatabaseColumn.FILENAME: self.filename,
            DatabaseColumn.BEDTIME: self.bedtime,
            DatabaseColumn.WAKE_TIME: self.wake_time,
            DatabaseColumn.SLEEP_ONSET_TIME: self.sleep_onset_time,
            DatabaseColumn.SLEEP_OFFSET_TIME: self.sleep_offset_time,
            DatabaseColumn.IN_BED_TIME: self.in_bed_time,
            DatabaseColumn.SLEEP_QUALITY: self.sleep_quality,
            DatabaseColumn.NAP_OCCURRED: self.nap_occurred,
            DatabaseColumn.NAP_ONSET_TIME: self.nap_onset_time,
            DatabaseColumn.NAP_OFFSET_TIME: self.nap_offset_time,
            DatabaseColumn.NAP_ONSET_TIME_2: self.nap_onset_time_2,
            DatabaseColumn.NAP_OFFSET_TIME_2: self.nap_offset_time_2,
            DatabaseColumn.NAP_ONSET_TIME_3: self.nap_onset_time_3,
            DatabaseColumn.NAP_OFFSET_TIME_3: self.nap_offset_time_3,
            DatabaseColumn.NONWEAR_OCCURRED: self.nonwear_occurred,
            DatabaseColumn.NONWEAR_REASON: self.nonwear_reason,
            DatabaseColumn.NONWEAR_START_TIME: self.nonwear_start_time,
            DatabaseColumn.NONWEAR_END_TIME: self.nonwear_end_time,
            DatabaseColumn.NONWEAR_REASON_2: self.nonwear_reason_2,
            DatabaseColumn.NONWEAR_START_TIME_2: self.nonwear_start_time_2,
            DatabaseColumn.NONWEAR_END_TIME_2: self.nonwear_end_time_2,
            DatabaseColumn.NONWEAR_REASON_3: self.nonwear_reason_3,
            DatabaseColumn.NONWEAR_START_TIME_3: self.nonwear_start_time_3,
            DatabaseColumn.NONWEAR_END_TIME_3: self.nonwear_end_time_3,
            DatabaseColumn.DIARY_NOTES: self.diary_notes,
            DatabaseColumn.NIGHT_NUMBER: self.night_number,
            # NOTE: import_date and original_column_mapping belong in other tables:
            # - import_date goes to diary_file_registry
            # - original_column_mapping goes to diary_raw_data
            # The diary_data table uses created_at/updated_at instead
        }

    @classmethod
    def from_database_dict(cls, data: dict[str, Any]) -> DiaryEntry:
        """Create from database data."""
        return cls(
            participant_id=data[DatabaseColumn.PARTICIPANT_ID],
            diary_date=data[DatabaseColumn.DIARY_DATE],
            filename=data[DatabaseColumn.FILENAME],
            bedtime=data.get(DatabaseColumn.BEDTIME),
            wake_time=data.get(DatabaseColumn.WAKE_TIME),
            sleep_onset_time=data.get(DatabaseColumn.SLEEP_ONSET_TIME),
            sleep_offset_time=data.get(DatabaseColumn.SLEEP_OFFSET_TIME),
            in_bed_time=data.get(DatabaseColumn.IN_BED_TIME),
            sleep_quality=data.get(DatabaseColumn.SLEEP_QUALITY),
            nap_occurred=data.get(DatabaseColumn.NAP_OCCURRED),
            nap_onset_time=data.get(DatabaseColumn.NAP_ONSET_TIME),
            nap_offset_time=data.get(DatabaseColumn.NAP_OFFSET_TIME),
            nap_onset_time_2=data.get(DatabaseColumn.NAP_ONSET_TIME_2),
            nap_offset_time_2=data.get(DatabaseColumn.NAP_OFFSET_TIME_2),
            nap_onset_time_3=data.get(DatabaseColumn.NAP_ONSET_TIME_3),
            nap_offset_time_3=data.get(DatabaseColumn.NAP_OFFSET_TIME_3),
            nonwear_occurred=data.get(DatabaseColumn.NONWEAR_OCCURRED),
            nonwear_reason=data.get(DatabaseColumn.NONWEAR_REASON),
            nonwear_start_time=data.get(DatabaseColumn.NONWEAR_START_TIME),
            nonwear_end_time=data.get(DatabaseColumn.NONWEAR_END_TIME),
            nonwear_reason_2=data.get(DatabaseColumn.NONWEAR_REASON_2),
            nonwear_start_time_2=data.get(DatabaseColumn.NONWEAR_START_TIME_2),
            nonwear_end_time_2=data.get(DatabaseColumn.NONWEAR_END_TIME_2),
            nonwear_reason_3=data.get(DatabaseColumn.NONWEAR_REASON_3),
            nonwear_start_time_3=data.get(DatabaseColumn.NONWEAR_START_TIME_3),
            nonwear_end_time_3=data.get(DatabaseColumn.NONWEAR_END_TIME_3),
            diary_notes=data.get(DatabaseColumn.DIARY_NOTES),
            night_number=data.get(DatabaseColumn.NIGHT_NUMBER),
            import_date=data.get(DatabaseColumn.IMPORT_DATE, datetime.now().isoformat()),
            original_column_mapping=data.get(DatabaseColumn.ORIGINAL_COLUMN_MAPPING),
        )


@dataclass
class ActiLifeSadehConfig:
    """ActiLife Sadeh configuration settings."""

    enabled: bool = False
    skip_rows: int = 3
    prefer_over_calculated: bool = True
    validate_against_calculated: bool = False


@dataclass
class DiaryImportResult:
    """Result of diary import operation."""

    total_files_processed: int = 0
    total_entries_imported: int = 0
    successful_files: list[str] = field(default_factory=list)
    failed_files: list[tuple[str, str]] = field(default_factory=list)  # (filename, error)
    mapping_results: dict[str, DiaryColumnMapping] = field(default_factory=dict)
    participants_found: set[str] = field(default_factory=set)
    import_duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_files_processed == 0:
            return 0.0
        return (len(self.successful_files) / self.total_files_processed) * 100


# ============================================================================
# DATA SOURCE CONFIGURATION (DI PATTERN)
# ============================================================================


@dataclass(frozen=True)
class DataSourceConfig:
    """
    Data source configuration for dependency injection.

    Immutable configuration for data source loaders.
    Used to specify which data source to use and how to configure it.

    Attributes:
        source_type: Data source type identifier (e.g., "csv", "gt3x")
        file_path: Path to the data file
        skip_rows: Number of header rows to skip (CSV-specific)
        encoding: File encoding (CSV-specific)
        custom_columns: Custom column mappings (optional)

    """

    source_type: str = "csv"  # DataSourceType enum value
    file_path: str = ""
    skip_rows: int = 10
    encoding: str = "utf-8"
    custom_columns: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "source_type": self.source_type,
            "file_path": self.file_path,
            "skip_rows": self.skip_rows,
            "encoding": self.encoding,
            "custom_columns": self.custom_columns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataSourceConfig:
        """Create from dictionary data."""
        return cls(
            source_type=data.get("source_type", "csv"),
            file_path=data.get("file_path", ""),
            skip_rows=data.get("skip_rows", 10),
            encoding=data.get("encoding", "utf-8"),
            custom_columns=data.get("custom_columns", {}),
        )


@dataclass(frozen=True)
class LoadedDataResult:
    """
    Result of data loading operation.

    Immutable container for loaded activity data and metadata.
    Returned by DataSourceLoader.load_file() implementations.

    Attributes:
        activity_data: DataFrame with datetime and activity columns
        metadata: File and device metadata
        column_mapping: Mapping of standard names to actual column names
        source_type: Data source type identifier
        file_path: Original file path

    """

    activity_data: pd.DataFrame
    metadata: dict[str, Any]
    column_mapping: dict[str, str]
    source_type: str
    file_path: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding DataFrame)."""
        return {
            "metadata": self.metadata,
            "column_mapping": self.column_mapping,
            "source_type": self.source_type,
            "file_path": self.file_path,
            "record_count": len(self.activity_data),
        }

    @property
    def has_data(self) -> bool:
        """Check if activity data is present and non-empty."""
        return self.activity_data is not None and not self.activity_data.empty

    @property
    def record_count(self) -> int:
        """Get number of records in activity data."""
        return len(self.activity_data) if self.has_data else 0
