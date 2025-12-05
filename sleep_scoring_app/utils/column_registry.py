#!/usr/bin/env python3
"""
Column Registry System for Sleep Scoring Application
Provides a centralized way to register and manage data columns across the application.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from sleep_scoring_app.core.constants import AlgorithmType, DatabaseColumn, ExportColumn

if TYPE_CHECKING:
    from collections.abc import Callable


class ColumnType(StrEnum):
    """Types of columns that can be registered."""

    METADATA = auto()  # Participant info, dates, etc.
    ALGORITHM = auto()  # Algorithm results
    STATISTIC = auto()  # Calculated statistics
    MARKER = auto()  # Sleep markers
    QUALITY = auto()  # Data quality metrics
    CUSTOM = auto()  # User-defined columns


class DataType(StrEnum):
    """Data types for columns."""

    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    DATETIME = auto()
    BOOLEAN = auto()
    JSON = auto()


@dataclass
class ColumnDefinition:
    """Definition of a data column."""

    # Basic properties
    name: str  # Internal column name
    display_name: str  # User-friendly display name
    column_type: ColumnType  # Category of column
    data_type: DataType  # Data type

    # Storage properties
    database_column: str | None = None  # Database column name
    export_column: str | None = None  # Export CSV column name

    # Behavior properties
    is_required: bool = False  # Required for data integrity
    is_exportable: bool = True  # Show in export dialog and can be toggled
    is_always_exported: bool = False  # Always exported, not toggleable in dialog
    is_autosaved: bool = True  # Include in autosave
    is_user_visible: bool = True  # Show in UI

    # Calculation properties
    calculator: Callable[[dict[str, Any]], Any] | None = None  # Function to calculate value
    dependencies: list[str] = field(default_factory=list)  # Other columns this depends on

    # Validation
    validator: Callable[[Any], bool] | None = None  # Validation function
    default_value: Any = None  # Default if not provided

    # UI properties
    ui_order: int = 1000  # Display order in UI
    ui_group: str = "Other"  # Grouping in UI
    format_string: str | None = None  # Display format (e.g., "{:.2f}" for floats)
    unit: str | None = None  # Unit of measurement
    description: str = ""  # Help text for users


class ColumnRegistry:
    """
    Central registry for all data columns in the application.
    Provides a single source of truth for column definitions.
    """

    def __init__(self) -> None:
        self._columns: dict[str, ColumnDefinition] = {}
        self._groups: dict[str, list[str]] = {}
        self._initialize_core_columns()

    def _initialize_core_columns(self) -> None:
        """Initialize the core columns that come with the application."""
        # Metadata columns
        self.register(
            ColumnDefinition(
                name="participant_id",
                display_name="Participant ID",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.PARTICIPANT_ID,
                export_column=ExportColumn.NUMERICAL_PARTICIPANT_ID,
                is_required=True,
                ui_order=100,
                ui_group="Participant Information",
                description="Numerical participant identifier",
            ),
        )

        self.register(
            ColumnDefinition(
                name="full_participant_id",
                display_name="Full Participant ID",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                export_column=ExportColumn.FULL_PARTICIPANT_ID,
                is_required=True,
                ui_order=101,
                ui_group="Participant Information",
                description="Full participant ID including timepoint",
            ),
        )

        self.register(
            ColumnDefinition(
                name="participant_group",
                display_name="Participant Group",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.PARTICIPANT_GROUP,
                export_column=ExportColumn.PARTICIPANT_GROUP,
                ui_order=103,
                ui_group="Participant Information",
                default_value="G1",
            ),
        )

        self.register(
            ColumnDefinition(
                name="participant_timepoint",
                display_name="Timepoint",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.PARTICIPANT_TIMEPOINT,
                export_column=ExportColumn.PARTICIPANT_TIMEPOINT,
                ui_order=102,
                ui_group="Participant Information",
                default_value="BO",
            ),
        )

        self.register(
            ColumnDefinition(
                name="analysis_date",
                display_name="Sleep Date",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.ANALYSIS_DATE,
                export_column=ExportColumn.SLEEP_DATE,
                is_always_exported=True,
                ui_order=104,
                ui_group="Participant Information",
                description="The date/night being analyzed (from UI dropdown)",
            ),
        )

        # Marker columns - Unix timestamps are internal only, not exported
        self.register(
            ColumnDefinition(
                name="onset_timestamp",
                display_name="Sleep Onset Timestamp",
                column_type=ColumnType.MARKER,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.ONSET_TIMESTAMP,
                export_column=None,
                is_exportable=False,
                is_required=False,
                ui_order=200,
                ui_group="Sleep Markers",
                description="Unix timestamp of sleep onset (internal use only)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="offset_timestamp",
                display_name="Sleep Offset Timestamp",
                column_type=ColumnType.MARKER,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.OFFSET_TIMESTAMP,
                export_column=None,
                is_exportable=False,
                is_required=False,
                ui_order=201,
                ui_group="Sleep Markers",
                description="Unix timestamp of sleep offset (internal use only)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="onset_time",
                display_name="Sleep Onset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.ONSET_TIME,
                export_column=ExportColumn.ONSET_TIME,
                ui_order=202,
                ui_group="Sleep Markers",
                format_string="%H:%M",
            ),
        )

        self.register(
            ColumnDefinition(
                name="offset_time",
                display_name="Sleep Offset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.OFFSET_TIME,
                export_column=ExportColumn.OFFSET_TIME,
                ui_order=203,
                ui_group="Sleep Markers",
                format_string="%H:%M",
            ),
        )

        # Extended marker columns for multiple sleep periods
        self.register(
            ColumnDefinition(
                name="marker_index",
                display_name="Sleep Period Index",
                column_type=ColumnType.MARKER,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.MARKER_INDEX,
                export_column=ExportColumn.MARKER_INDEX,
                is_required=False,
                ui_order=204,
                ui_group="Sleep Markers",
                description="Index of sleep period (1, 2, 3, or 4)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="marker_type",
                display_name="Marker Type",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.MARKER_TYPE,
                is_exportable=True,
                export_column=ExportColumn.MARKER_TYPE,
                ui_order=205,
                ui_group="Sleep Markers",
                description="Type of sleep marker (main_sleep, nap, nwt)",
            ),
        )

        # Onset/offset rule column (NEW - for DI pattern)
        self.register(
            ColumnDefinition(
                name="onset_offset_rule",
                display_name="Onset/Offset Rule",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.ONSET_OFFSET_RULE,
                export_column=ExportColumn.ONSET_OFFSET_RULE,
                is_always_exported=True,
                ui_order=206,
                ui_group="Sleep Markers",
                default_value="consecutive_3_5",
                description="Rule used to detect sleep onset and offset (e.g., Consecutive 3/5 Minutes, Tudor-Locke)",
            ),
        )

        # Statistics columns
        self.register(
            ColumnDefinition(
                name="total_sleep_time",
                display_name="Total Sleep Time (TST)",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.TOTAL_SLEEP_TIME,
                export_column=ExportColumn.TOTAL_SLEEP_TIME,
                ui_order=300,
                ui_group="Sleep Metrics",
                format_string="{:.1f}",
                unit="minutes",
                calculator=None,
                dependencies=[],
            ),
        )

        self.register(
            ColumnDefinition(
                name="sleep_efficiency",
                display_name="Sleep Efficiency",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.SLEEP_EFFICIENCY,
                export_column=ExportColumn.EFFICIENCY,
                ui_order=301,
                ui_group="Sleep Metrics",
                format_string="{:.2f}",
                unit="%",
                calculator=None,
                dependencies=[],
            ),
        )

        self.register(
            ColumnDefinition(
                name="waso",
                display_name="Wake After Sleep Onset (WASO)",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.WASO,
                export_column=ExportColumn.WASO,
                ui_order=302,
                ui_group="Sleep Metrics",
                format_string="{:.1f}",
                unit="minutes",
            ),
        )

        self.register(
            ColumnDefinition(
                name="awakenings",
                display_name="Number of Awakenings",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.AWAKENINGS,
                export_column=ExportColumn.NUMBER_OF_AWAKENINGS,
                ui_order=303,
                ui_group="Sleep Metrics",
            ),
        )

        # Algorithm columns
        self.register(
            ColumnDefinition(
                name="algorithm_type",
                display_name="Algorithm Type",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.ALGORITHM_TYPE,
                export_column=ExportColumn.SLEEP_ALGORITHM,
                ui_order=400,
                ui_group="Algorithm Results",
                default_value=AlgorithmType.SADEH_1994_ACTILIFE,
                description="Type of algorithm used (Manual, Combined, etc.)",
            ),
        )

        # Generic sleep algorithm identifier (NEW - for DI pattern)
        self.register(
            ColumnDefinition(
                name="sleep_algorithm_name",
                display_name="Sleep Algorithm",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.SLEEP_ALGORITHM_NAME,
                export_column=ExportColumn.SLEEP_ALGORITHM_NAME,
                is_always_exported=True,
                ui_order=401,
                ui_group="Algorithm Results",
                default_value="sadeh_1994",
                description="Sleep scoring algorithm identifier (e.g., sadeh_1994_actilife, cole_kripke_1992_actilife)",
            ),
        )

        # Legacy Sadeh columns (kept for backward compatibility)
        self.register(
            ColumnDefinition(
                name="sadeh_onset",
                display_name="Sleep Algorithm Value at Onset",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.SADEH_ONSET,
                export_column=ExportColumn.SADEH_ONSET,
                ui_order=402,
                ui_group="Algorithm Results",
                description="Sleep scoring algorithm value at onset marker (legacy column)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="sadeh_offset",
                display_name="Sleep Algorithm Value at Offset",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.SADEH_OFFSET,
                export_column=ExportColumn.SADEH_OFFSET,
                ui_order=403,
                ui_group="Algorithm Results",
                description="Sleep scoring algorithm value at offset marker (legacy column)",
            ),
        )

        # Generic algorithm result columns (NEW - preferred for new code)
        self.register(
            ColumnDefinition(
                name="sleep_algorithm_onset",
                display_name="Sleep Algorithm Onset Value",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.SLEEP_ALGORITHM_ONSET,
                export_column=ExportColumn.SLEEP_ALGORITHM_ONSET,
                is_exportable=False,  # Hidden - use sadeh_onset for now (same data)
                ui_order=404,
                ui_group="Algorithm Results",
                description="Sleep scoring algorithm value at onset marker (generic column)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="sleep_algorithm_offset",
                display_name="Sleep Algorithm Offset Value",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.SLEEP_ALGORITHM_OFFSET,
                export_column=ExportColumn.SLEEP_ALGORITHM_OFFSET,
                is_exportable=False,  # Hidden - use sadeh_offset for now (same data)
                ui_order=405,
                ui_group="Algorithm Results",
                description="Sleep scoring algorithm value at offset marker (generic column)",
            ),
        )

        # Add saved_date column for export - always exported
        self.register(
            ColumnDefinition(
                name="saved_date",
                display_name="Saved Date",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.UPDATED_AT,
                export_column=ExportColumn.SAVED_AT,
                is_always_exported=True,
                ui_order=105,
                ui_group="Metadata",
                description="Date when record was saved",
            ),
        )

        # Missing sleep metrics columns
        self.register(
            ColumnDefinition(
                name="total_minutes_in_bed",
                display_name="Total Minutes in Bed",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.TOTAL_MINUTES_IN_BED,
                export_column=ExportColumn.TOTAL_MINUTES_IN_BED,
                ui_order=302,
                ui_group="Sleep Metrics",
                format_string="{:.1f}",
                unit="minutes",
            ),
        )

        self.register(
            ColumnDefinition(
                name="average_awakening_length",
                display_name="Average Awakening Length",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.AVERAGE_AWAKENING_LENGTH,
                export_column=ExportColumn.AVERAGE_AWAKENING_LENGTH,
                ui_order=303,
                ui_group="Sleep Metrics",
                format_string="{:.1f}",
                unit="minutes",
            ),
        )

        # Activity metrics columns
        self.register(
            ColumnDefinition(
                name="total_activity",
                display_name="Total Activity Counts",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.TOTAL_ACTIVITY,
                export_column=ExportColumn.TOTAL_COUNTS,
                is_exportable=True,
                ui_order=350,
                ui_group="Activity Metrics",
                format_string="{:.1f}",
            ),
        )

        self.register(
            ColumnDefinition(
                name="movement_index",
                display_name="Movement Index",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.MOVEMENT_INDEX,
                export_column=ExportColumn.MOVEMENT_INDEX,
                is_exportable=True,
                ui_order=351,
                ui_group="Activity Metrics",
                format_string="{:.2f}",
            ),
        )

        self.register(
            ColumnDefinition(
                name="fragmentation_index",
                display_name="Fragmentation Index",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.FRAGMENTATION_INDEX,
                export_column=ExportColumn.FRAGMENTATION_INDEX,
                is_exportable=True,
                ui_order=352,
                ui_group="Activity Metrics",
                format_string="{:.2f}",
            ),
        )

        self.register(
            ColumnDefinition(
                name="sleep_fragmentation_index",
                display_name="Sleep Fragmentation Index",
                column_type=ColumnType.STATISTIC,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.SLEEP_FRAGMENTATION_INDEX,
                export_column=ExportColumn.SLEEP_FRAGMENTATION_INDEX,
                is_exportable=True,
                ui_order=353,
                ui_group="Activity Metrics",
                format_string="{:.2f}",
            ),
        )

        # Choi algorithm columns (nonwear detection)
        self.register(
            ColumnDefinition(
                name="choi_onset",
                display_name="Nonwear Algorithm Value at Onset",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.CHOI_ONSET,
                export_column=ExportColumn.CHOI_ONSET,
                is_exportable=True,
                ui_order=403,
                ui_group="Algorithm Results",
            ),
        )

        self.register(
            ColumnDefinition(
                name="choi_offset",
                display_name="Nonwear Algorithm Value at Offset",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.CHOI_OFFSET,
                export_column=ExportColumn.CHOI_OFFSET,
                is_exportable=True,
                ui_order=404,
                ui_group="Algorithm Results",
            ),
        )

        self.register(
            ColumnDefinition(
                name="total_choi_counts",
                display_name="Total Nonwear Algorithm Counts",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.TOTAL_CHOI_COUNTS,
                export_column=ExportColumn.TOTAL_CHOI_COUNTS,
                is_exportable=True,
                ui_order=405,
                ui_group="Algorithm Results",
            ),
        )

        # NWT sensor data columns
        self.register(
            ColumnDefinition(
                name="nwt_onset",
                display_name="Nonwear Sensor Value at Onset",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.NWT_ONSET,
                export_column=ExportColumn.NWT_ONSET,
                is_exportable=True,
                ui_order=406,
                ui_group="Algorithm Results",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nwt_offset",
                display_name="Nonwear Sensor Value at Offset",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.NWT_OFFSET,
                export_column=ExportColumn.NWT_OFFSET,
                is_exportable=True,
                ui_order=407,
                ui_group="Algorithm Results",
            ),
        )

        self.register(
            ColumnDefinition(
                name="total_nwt_counts",
                display_name="Total Nonwear Sensor Counts",
                column_type=ColumnType.ALGORITHM,
                data_type=DataType.FLOAT,
                database_column=DatabaseColumn.TOTAL_NWT_COUNTS,
                export_column=ExportColumn.TOTAL_NWT_COUNTS,
                is_exportable=True,
                ui_order=408,
                ui_group="Algorithm Results",
            ),
        )

        # Raw activity data columns for import/export
        self.register(
            ColumnDefinition(
                name="import_status",
                display_name="Import Status",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.STATUS,
                is_exportable=False,  # Internal metadata, not for research export
                ui_order=106,
                ui_group="Import Information",
                description="Status of file import",
            ),
        )

        self.register(
            ColumnDefinition(
                name="file_hash",
                display_name="File Hash",
                column_type=ColumnType.METADATA,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.FILE_HASH,
                is_exportable=False,  # Internal metadata, not for research export
                is_user_visible=False,
                ui_order=107,
                ui_group="Import Information",
                description="SHA256 hash for change detection",
            ),
        )

        self.register(
            ColumnDefinition(
                name="total_records",
                display_name="Total Records",
                column_type=ColumnType.QUALITY,
                data_type=DataType.INTEGER,
                database_column=DatabaseColumn.TOTAL_RECORDS,
                is_exportable=False,  # Internal metadata, not for research export
                ui_order=108,
                ui_group="Data Quality",
                description="Total number of activity records",
            ),
        )

        self.register(
            ColumnDefinition(
                name="date_range_start",
                display_name="Data Start Date",
                column_type=ColumnType.METADATA,
                data_type=DataType.DATETIME,
                database_column=DatabaseColumn.DATE_RANGE_START,
                is_exportable=False,  # Internal metadata, not for research export
                ui_order=109,
                ui_group="Data Coverage",
                description="Earliest timestamp in dataset",
            ),
        )

        self.register(
            ColumnDefinition(
                name="date_range_end",
                display_name="Data End Date",
                column_type=ColumnType.METADATA,
                data_type=DataType.DATETIME,
                database_column=DatabaseColumn.DATE_RANGE_END,
                is_exportable=False,  # Internal metadata, not for research export
                ui_order=110,
                ui_group="Data Coverage",
                description="Latest timestamp in dataset",
            ),
        )

        # Diary-specific nap columns
        self.register(
            ColumnDefinition(
                name="nap_occurred",
                display_name="Diary: Nap 1 Occurred",
                column_type=ColumnType.MARKER,
                data_type=DataType.BOOLEAN,
                database_column=DatabaseColumn.NAP_OCCURRED,
                export_column=ExportColumn.NAP_OCCURRED,
                is_exportable=True,
                ui_order=250,
                ui_group="Diary: Nap Information",
                default_value=False,
                description="Whether a nap occurred during this period",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nap_onset_time",
                display_name="Diary: Nap 1 Onset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NAP_ONSET_TIME,
                export_column=ExportColumn.NAP_ONSET_TIME,
                is_exportable=True,
                ui_order=251,
                ui_group="Diary: Nap Information",
                format_string="%H:%M",
                description="Time when nap began",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nap_offset_time",
                display_name="Diary: Nap 1 Offset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NAP_OFFSET_TIME,
                export_column=ExportColumn.NAP_OFFSET_TIME,
                is_exportable=True,
                ui_order=252,
                ui_group="Diary: Nap Information",
                format_string="%H:%M",
                description="Time when nap ended",
            ),
        )

        # Diary-specific nonwear time columns
        self.register(
            ColumnDefinition(
                name="nonwear_occurred",
                display_name="Diary: Nonwear Occurred",
                column_type=ColumnType.MARKER,
                data_type=DataType.BOOLEAN,
                database_column=DatabaseColumn.NONWEAR_OCCURRED,
                export_column=ExportColumn.NONWEAR_OCCURRED,
                is_exportable=True,
                ui_order=260,
                ui_group="Diary: Nonwear Information",
                default_value=False,
                description="Whether device was not worn during this period",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_reason",
                display_name="Diary: Nonwear Reason",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_REASON,
                export_column=ExportColumn.NONWEAR_REASON,
                is_exportable=True,
                ui_order=261,
                ui_group="Diary: Nonwear Information",
                description="Reason for device not being worn",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_start_time",
                display_name="Diary: Nonwear Start Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_START_TIME,
                export_column=ExportColumn.NONWEAR_START_TIME,
                is_exportable=True,
                ui_order=262,
                ui_group="Diary: Nonwear Information",
                format_string="%H:%M",
                description="Time when device was removed",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_end_time",
                display_name="Diary: Nonwear End Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_END_TIME,
                export_column=ExportColumn.NONWEAR_END_TIME,
                is_exportable=True,
                ui_order=263,
                ui_group="Diary: Nonwear Information",
                format_string="%H:%M",
                description="Time when device was put back on",
            ),
        )

        # Second nap columns
        self.register(
            ColumnDefinition(
                name="nap_onset_time_2",
                display_name="Diary: Nap 2 Onset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NAP_ONSET_TIME_2,
                export_column=ExportColumn.NAP_ONSET_TIME_2,
                is_exportable=True,
                ui_order=253,
                ui_group="Diary: Nap Information",
                format_string="%H:%M",
                description="Time when second nap began",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nap_offset_time_2",
                display_name="Diary: Nap 2 Offset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NAP_OFFSET_TIME_2,
                export_column=ExportColumn.NAP_OFFSET_TIME_2,
                is_exportable=True,
                ui_order=254,
                ui_group="Diary: Nap Information",
                format_string="%H:%M",
                description="Time when second nap ended",
            ),
        )

        # Third nap columns
        self.register(
            ColumnDefinition(
                name="nap_onset_time_3",
                display_name="Diary: Nap 3 Onset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NAP_ONSET_TIME_3,
                export_column=ExportColumn.NAP_ONSET_TIME_3,
                is_exportable=True,
                ui_order=255,
                ui_group="Diary: Nap Information",
                format_string="%H:%M",
                description="Time when third nap began",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nap_offset_time_3",
                display_name="Diary: Nap 3 Offset Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NAP_OFFSET_TIME_3,
                export_column=ExportColumn.NAP_OFFSET_TIME_3,
                is_exportable=True,
                ui_order=256,
                ui_group="Diary: Nap Information",
                format_string="%H:%M",
                description="Time when third nap ended",
            ),
        )

        # Additional nonwear period columns
        self.register(
            ColumnDefinition(
                name="nonwear_reason_2",
                display_name="Diary: Nonwear 2 Reason",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_REASON_2,
                export_column=ExportColumn.NONWEAR_REASON_2,
                is_exportable=True,
                ui_order=264,
                ui_group="Diary: Nonwear Information",
                description="Reason for second nonwear period",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_start_time_2",
                display_name="Diary: Nonwear 2 Start Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_START_TIME_2,
                export_column=ExportColumn.NONWEAR_START_TIME_2,
                is_exportable=True,
                ui_order=265,
                ui_group="Diary: Nonwear Information",
                format_string="%H:%M",
                description="Time when device was removed (2nd period)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_end_time_2",
                display_name="Diary: Nonwear 2 End Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_END_TIME_2,
                export_column=ExportColumn.NONWEAR_END_TIME_2,
                is_exportable=True,
                ui_order=266,
                ui_group="Diary: Nonwear Information",
                format_string="%H:%M",
                description="Time when device was put back on (2nd period)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_reason_3",
                display_name="Diary: Nonwear 3 Reason",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_REASON_3,
                export_column=ExportColumn.NONWEAR_REASON_3,
                is_exportable=True,
                ui_order=267,
                ui_group="Diary: Nonwear Information",
                description="Reason for third nonwear period",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_start_time_3",
                display_name="Diary: Nonwear 3 Start Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_START_TIME_3,
                export_column=ExportColumn.NONWEAR_START_TIME_3,
                is_exportable=True,
                ui_order=268,
                ui_group="Diary: Nonwear Information",
                format_string="%H:%M",
                description="Time when device was removed (3rd period)",
            ),
        )

        self.register(
            ColumnDefinition(
                name="nonwear_end_time_3",
                display_name="Diary: Nonwear 3 End Time",
                column_type=ColumnType.MARKER,
                data_type=DataType.STRING,
                database_column=DatabaseColumn.NONWEAR_END_TIME_3,
                export_column=ExportColumn.NONWEAR_END_TIME_3,
                is_exportable=True,
                ui_order=269,
                ui_group="Diary: Nonwear Information",
                format_string="%H:%M",
                description="Time when device was put back on (3rd period)",
            ),
        )

        # Daily sleep markers (complete structure with naps)
        self.register(
            ColumnDefinition(
                name="daily_sleep_markers",
                display_name="Daily Sleep Markers",
                column_type=ColumnType.METADATA,
                data_type=DataType.JSON,
                database_column=DatabaseColumn.DAILY_SLEEP_MARKERS,
                is_exportable=False,  # Internal structure, not for direct export
                ui_order=999,  # Keep at end
                ui_group="Sleep Markers",
                description="Complete daily sleep markers including all periods and naps",
            ),
        )

    def register(self, column: ColumnDefinition) -> None:
        """Register a new column definition."""
        if column.name in self._columns:
            msg = f"Column '{column.name}' is already registered"
            raise ValueError(msg)

        self._columns[column.name] = column

        # Update group tracking
        if column.ui_group not in self._groups:
            self._groups[column.ui_group] = []
        self._groups[column.ui_group].append(column.name)

    def get(self, column_name: str) -> ColumnDefinition | None:
        """Get a column definition by name."""
        return self._columns.get(column_name)

    def get_all(self) -> list[ColumnDefinition]:
        """Get all registered columns."""
        return list(self._columns.values())

    def get_by_group(self, group_name: str) -> list[ColumnDefinition]:
        """Get all columns in a specific UI group."""
        column_names = self._groups.get(group_name, [])
        return [self._columns[name] for name in column_names]

    def get_all_groups(self) -> list[str]:
        """Get all UI group names."""
        return list(self._groups.keys())

    def get_groups_with_exportable_columns(self) -> dict[str, list[str]]:
        """Get groups that contain exportable columns with their export column names."""
        groups = {}
        for group_name in self._groups:
            exportable_columns = []
            for column_name in self._groups[group_name]:
                column = self._columns[column_name]
                if column.is_exportable and column.export_column:
                    exportable_columns.append(column.export_column)
            if exportable_columns:
                groups[group_name] = exportable_columns
        return groups

    def get_exportable(self) -> list[ColumnDefinition]:
        """Get all columns that should be included in exports, sorted by ui_order."""
        exportable_columns = [col for col in self._columns.values() if col.is_exportable]
        return sorted(exportable_columns, key=lambda col: col.ui_order)


# Global registry instance
column_registry = ColumnRegistry()


def register_custom_column(column: ColumnDefinition) -> None:
    """Convenience function to register a custom column."""
    column_registry.register(column)


def get_column_registry() -> ColumnRegistry:
    """Get the global column registry instance."""
    return column_registry
