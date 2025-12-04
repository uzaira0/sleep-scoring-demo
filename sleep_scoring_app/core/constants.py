#!/usr/bin/env python3
"""
Constants for Sleep Scoring Application
Centralized definitions for all string enums, numeric constants, and configuration values.
"""

from enum import StrEnum

# ============================================================================
# CORE APPLICATION CONSTANTS
# ============================================================================


class FeatureFlags:
    """Feature flags for enabling/disabling functionality."""

    ENABLE_AUTOSAVE = False  # Set to False to disable autosave functionality


class AlgorithmType(StrEnum):
    """
    Sleep scoring algorithm identifiers.

    These values match the algorithm IDs registered in AlgorithmFactory.
    Use these for storing/retrieving algorithm type in database and exports.

    For creating algorithm instances, use AlgorithmFactory.create(algorithm_id).
    """

    # Sleep scoring algorithms (registered in AlgorithmFactory)
    SADEH_1994_ORIGINAL = "sadeh_1994_original"
    SADEH_1994_ACTILIFE = "sadeh_1994_actilife"
    COLE_KRIPKE_1992 = "cole_kripke_1992"

    # Special values for UI/workflow states
    MANUAL = "manual"  # Manual scoring without algorithm
    CHOI = "choi"  # Nonwear detection (not sleep scoring)

    # Legacy values - kept for database migration compatibility
    # These should be migrated to specific algorithm IDs
    _LEGACY_SADEH = "Sadeh"  # Migrate to SADEH_1994_ACTILIFE
    _LEGACY_COMBINED = "Manual + Algorithm"  # Migrate to SADEH_1994_ACTILIFE
    _LEGACY_MANUAL_SADEH = "Manual + Sadeh"  # Migrate to SADEH_1994_ACTILIFE

    @classmethod
    def get_default(cls) -> "AlgorithmType":
        """Get the default algorithm type."""
        return cls.SADEH_1994_ACTILIFE

    @classmethod
    def migrate_legacy_value(cls, value: str) -> "AlgorithmType":
        """
        Migrate legacy algorithm type values to current values.

        Args:
            value: Legacy or current algorithm type string

        Returns:
            Current AlgorithmType value

        """
        # Map legacy values to current values
        legacy_mapping = {
            "Sadeh": cls.SADEH_1994_ACTILIFE,
            "Manual + Algorithm": cls.SADEH_1994_ACTILIFE,
            "Manual + Sadeh": cls.SADEH_1994_ACTILIFE,
            "Cole-Kripke": cls.COLE_KRIPKE_1992,
            "Manual": cls.MANUAL,
            "Choi": cls.CHOI,
            "Automatic": cls.SADEH_1994_ACTILIFE,
        }

        # Check if it's a legacy value
        if value in legacy_mapping:
            return legacy_mapping[value]

        # Check if it's already a valid current value
        try:
            return cls(value)
        except ValueError:
            # Unknown value, default to SADEH_1994_ACTILIFE
            return cls.SADEH_1994_ACTILIFE


class AlgorithmResult(StrEnum):
    """Algorithm result values."""

    SLEEP = "S"
    WAKE = "W"
    WEARING = "On"
    NOT_WEARING = "Off"


class NonwearDataSource(StrEnum):
    """Nonwear data source types."""

    CHOI_ALGORITHM = "Choi Algorithm"  # Choi nonwear detection from accelerometer
    NONWEAR_SENSOR = "Nonwear Sensor"  # External nonwear sensor data
    NWT_SENSOR = "NWT Sensor"  # Alternative name for nonwear time sensor
    MANUAL_NWT = "Manual NWT"  # Manually marked non-wear time


class SadehDataSource(StrEnum):
    """Sadeh data source types."""

    CALCULATED = "calculated"
    ACTILIFE = "actilife"


class MarkerType(StrEnum):
    """Sleep marker type classifications."""

    MAIN_SLEEP = "MAIN_SLEEP"
    NAP = "NAP"
    NWT = "nwt"


class SleepStatusValue(StrEnum):
    """Sleep status indicator values."""

    NO_SLEEP = "NO_SLEEP"


# ============================================================================
# ALGORITHM PARAMETERS
# ============================================================================


class AlgorithmParams:
    """Algorithm parameter constants."""

    # Choi algorithm
    CHOI_MIN_PERIOD_LENGTH = 90
    CHOI_SPIKE_TOLERANCE = 2
    CHOI_SMALL_WINDOW_LENGTH = 30

    # Sadeh algorithm
    SADEH_LOW_ACTIVITY_THRESHOLD = 30
    SADEH_NATS_MIN = 50
    SADEH_NATS_MAX = 100
    SADEH_ACTIVITY_CAP = 300  # Epoch counts over 300 are reduced to 300
    SADEH_COEFFICIENT_A = 7.601  # Intercept
    SADEH_COEFFICIENT_B = 0.065  # AVG coefficient
    SADEH_COEFFICIENT_C = 1.08  # NATS coefficient
    SADEH_COEFFICIENT_D = 0.056  # SD coefficient
    SADEH_COEFFICIENT_E = 0.703  # LG coefficient
    SADEH_THRESHOLD = -4  # If result > -4, epoch is asleep

    # Sleep rules
    SLEEP_ONSET_CONSECUTIVE_MINUTES = 3
    SLEEP_OFFSET_CONSECUTIVE_MINUTES = 5
    SLEEP_RULE_EXTENSION_MINUTES = 5


class MarkerLimits:
    """
    Marker validation limits.

    Note: MAX_SLEEP_PERIODS_PER_DAY is the default value.
    Actual runtime value is configurable via AppConfig.max_sleep_periods.
    """

    MAX_SLEEP_PERIODS_PER_DAY = 4  # 1 main sleep + up to 3 naps (default)


class TimeConstants:
    """Time-related constants."""

    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    MINUTES_PER_HOUR = 60
    HOURS_PER_DAY = 24
    FIVE_MINUTES = 5
    TEN_MINUTES = 10
    FIFTEEN_MINUTES = 15
    THIRTY_MINUTES = 30
    SADEH_NIGHT_START_HOUR = 22
    SADEH_NIGHT_END_HOUR = 7


class TimeFormat(StrEnum):
    """Time format strings."""

    HOUR_MINUTE = "%H:%M"
    DATE_ONLY = "%Y-%m-%d"
    ISO_DATETIME = "%Y-%m-%dT%H:%M:%S"
    PLACEHOLDER = "HH:MM"
    EMPTY_TIME = "--:--"
    EMPTY_VALUE = "--"


# ============================================================================
# DATABASE SCHEMA
# ============================================================================


class DatabaseTable(StrEnum):
    """Database table names."""

    SLEEP_METRICS = "sleep_metrics"
    AUTOSAVE_METRICS = "autosave_metrics"
    RAW_ACTIVITY_DATA = "raw_activity_data"
    FILE_REGISTRY = "file_registry"
    NONWEAR_SENSOR_PERIODS = "nonwear_sensor_periods"
    CHOI_ALGORITHM_PERIODS = "choi_algorithm_periods"
    DIARY_DATA = "diary_data"
    DIARY_FILE_REGISTRY = "diary_file_registry"
    DIARY_RAW_DATA = "diary_raw_data"
    DIARY_NAP_PERIODS = "diary_nap_periods"
    DIARY_NONWEAR_PERIODS = "diary_nonwear_periods"
    SLEEP_MARKERS_EXTENDED = "sleep_markers_extended"
    MANUAL_NWT_MARKERS = "manual_nwt_markers"


class DatabaseColumn(StrEnum):
    """Database column names."""

    # Primary keys and identifiers
    ID = "id"
    FILENAME = "filename"
    PARTICIPANT_KEY = "participant_key"  # Composite key: participant_id_group_timepoint
    PARTICIPANT_ID = "participant_id"
    PARTICIPANT_GROUP = "participant_group"
    PARTICIPANT_TIMEPOINT = "participant_timepoint"
    ANALYSIS_DATE = "analysis_date"

    # Timestamp data
    ONSET_TIMESTAMP = "onset_timestamp"
    OFFSET_TIMESTAMP = "offset_timestamp"
    ONSET_TIME = "onset_time"
    OFFSET_TIME = "offset_time"

    # Sleep metrics
    TOTAL_SLEEP_TIME = "total_sleep_time"
    SLEEP_EFFICIENCY = "sleep_efficiency"
    WASO = "waso"
    AWAKENINGS = "awakenings"
    TOTAL_MINUTES_IN_BED = "total_minutes_in_bed"
    AVERAGE_AWAKENING_LENGTH = "average_awakening_length"
    ALGORITHM_TYPE = "algorithm_type"

    # Algorithm-specific values (LEGACY - kept for backward compatibility)
    SADEH_ONSET = "sadeh_onset"
    SADEH_OFFSET = "sadeh_offset"
    CHOI_ONSET = "choi_onset"
    CHOI_OFFSET = "choi_offset"
    TOTAL_CHOI_COUNTS = "total_choi_counts"

    # Generic sleep algorithm columns (NEW - use for all algorithms)
    SLEEP_ALGORITHM_NAME = "sleep_algorithm_name"  # e.g., "sadeh_1994", "cole_kripke_1992"
    SLEEP_ALGORITHM_ONSET = "sleep_algorithm_onset"  # Algorithm value at onset marker
    SLEEP_ALGORITHM_OFFSET = "sleep_algorithm_offset"  # Algorithm value at offset marker

    # Onset/offset rule identifier (NEW - for DI pattern)
    ONSET_OFFSET_RULE = "onset_offset_rule"  # e.g., "consecutive_3_5", "tudor_locke_2014"

    # NWT sensor data columns
    NWT_ONSET = "nwt_onset"
    NWT_OFFSET = "nwt_offset"
    TOTAL_NWT_COUNTS = "total_nwt_counts"

    # Activity metrics
    TOTAL_ACTIVITY = "total_activity"
    MOVEMENT_INDEX = "movement_index"
    FRAGMENTATION_INDEX = "fragmentation_index"
    SLEEP_FRAGMENTATION_INDEX = "sleep_fragmentation_index"

    # Metadata and timestamps
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    METADATA = "metadata"
    SLEEP_DATA = "sleep_data"
    DAILY_SLEEP_MARKERS = "daily_sleep_markers"

    # Raw activity data columns
    FILE_HASH = "file_hash"
    TIMESTAMP = "timestamp"
    AXIS_Y = "axis_y"  # ActiGraph Axis1 = Y-axis (vertical)
    AXIS_X = "axis_x"  # ActiGraph Axis2 = X-axis (lateral)
    AXIS_Z = "axis_z"  # ActiGraph Axis3 = Z-axis (forward)
    VECTOR_MAGNITUDE = "vector_magnitude"
    STEPS = "steps"
    LUX = "lux"
    IMPORT_DATE = "import_date"

    # File registry columns
    ORIGINAL_PATH = "original_path"
    FILE_SIZE = "file_size"
    DATE_RANGE_START = "date_range_start"
    DATE_RANGE_END = "date_range_end"
    TOTAL_RECORDS = "total_records"
    LAST_MODIFIED = "last_modified"
    STATUS = "status"

    # Nonwear sensor and Choi algorithm period columns
    START_TIME = "start_time"
    END_TIME = "end_time"
    DURATION_MINUTES = "duration_minutes"
    START_INDEX = "start_index"
    END_INDEX = "end_index"
    PERIOD_TYPE = "period_type"

    # Extended sleep marker columns
    MARKER_INDEX = "marker_index"
    MARKER_TYPE = "marker_type"
    IS_MAIN_SLEEP = "is_main_sleep"
    CREATED_BY = "created_by"

    # Diary-specific columns
    DIARY_DATE = "diary_date"
    BEDTIME = "bedtime"
    WAKE_TIME = "wake_time"
    SLEEP_QUALITY = "sleep_quality"
    SLEEP_ONSET_TIME = "sleep_onset_time"
    SLEEP_OFFSET_TIME = "sleep_offset_time"
    IN_BED_TIME = "in_bed_time"
    NAP_OCCURRED = "nap_occurred"
    NAP_ONSET_TIME = "nap_onset_time"
    NAP_OFFSET_TIME = "nap_offset_time"
    # Additional nap columns for second and third naps
    NAP_ONSET_TIME_2 = "nap_onset_time_2"
    NAP_OFFSET_TIME_2 = "nap_offset_time_2"
    NAP_ONSET_TIME_3 = "nap_onset_time_3"
    NAP_OFFSET_TIME_3 = "nap_offset_time_3"
    NONWEAR_OCCURRED = "nonwear_occurred"
    NONWEAR_REASON = "nonwear_reason"
    NONWEAR_START_TIME = "nonwear_start_time"
    NONWEAR_END_TIME = "nonwear_end_time"
    # Additional nonwear columns for multiple periods
    NONWEAR_REASON_2 = "nonwear_reason_2"
    NONWEAR_START_TIME_2 = "nonwear_start_time_2"
    NONWEAR_END_TIME_2 = "nonwear_end_time_2"
    NONWEAR_REASON_3 = "nonwear_reason_3"
    NONWEAR_START_TIME_3 = "nonwear_start_time_3"
    NONWEAR_END_TIME_3 = "nonwear_end_time_3"
    DIARY_NOTES = "diary_notes"
    NIGHT_NUMBER = "night_number"
    ORIGINAL_COLUMN_MAPPING = "original_column_mapping"

    # Auto-calculated column flags
    BEDTIME_AUTO_CALCULATED = "bedtime_auto_calculated"
    WAKE_TIME_AUTO_CALCULATED = "wake_time_auto_calculated"
    SLEEP_ONSET_AUTO_CALCULATED = "sleep_onset_auto_calculated"
    SLEEP_OFFSET_AUTO_CALCULATED = "sleep_offset_auto_calculated"
    IN_BED_TIME_AUTO_CALCULATED = "in_bed_time_auto_calculated"

    # Nap period table columns
    NAP_INDEX = "nap_index"
    NAP_START_TIME = "nap_start_time"
    NAP_END_TIME = "nap_end_time"
    NAP_DURATION_MINUTES = "nap_duration_minutes"
    NAP_QUALITY = "nap_quality"
    NAP_NOTES = "nap_notes"

    # Nonwear period table columns
    NONWEAR_INDEX = "nonwear_index"
    NONWEAR_DURATION_MINUTES = "nonwear_duration_minutes"
    NONWEAR_NOTES = "nonwear_notes"


# ============================================================================
# DATA IMPORT AND EXPORT
# ============================================================================


class ImportStatus(StrEnum):
    """File import status values."""

    PENDING = "pending"
    IMPORTING = "importing"
    IMPORTED = "imported"
    PROCESSED = "processed"
    ERROR = "error"
    UPDATED = "updated"


class DiaryFileType(StrEnum):
    """Diary file type constants."""

    CSV = "csv"
    EXCEL = "excel"
    XLSX = "xlsx"
    XLS = "xls"


class ExportColumn(StrEnum):
    """Export CSV column names."""

    FULL_PARTICIPANT_ID = "Full Participant ID"
    NUMERICAL_PARTICIPANT_ID = "Numerical Participant ID"
    PARTICIPANT_GROUP = "Participant Group"
    PARTICIPANT_TIMEPOINT = "Participant Timepoint"
    SLEEP_ALGORITHM = "Sleep Algorithm"
    SLEEP_DATE = "Sleep Date"
    ONSET_DATE = "Onset Date"
    ONSET_TIME = "Onset Time"
    OFFSET_DATE = "Offset Date"
    OFFSET_TIME = "Offset Time"
    TOTAL_COUNTS = "Total Counts"
    EFFICIENCY = "Efficiency"
    TOTAL_MINUTES_IN_BED = "Total Minutes in Bed"
    TOTAL_SLEEP_TIME = "Total Sleep Time (TST)"
    WASO = "Wake After Sleep Onset (WASO)"
    NUMBER_OF_AWAKENINGS = "Number of Awakenings"
    AVERAGE_AWAKENING_LENGTH = "Average Awakening Length"
    MOVEMENT_INDEX = "Movement Index"
    FRAGMENTATION_INDEX = "Fragmentation Index"
    SLEEP_FRAGMENTATION_INDEX = "Sleep Fragmentation Index"
    # Algorithm results (LEGACY - kept for Sadeh-specific exports)
    SADEH_ONSET = "Sleep Algorithm Value at Onset"
    SADEH_OFFSET = "Sleep Algorithm Value at Offset"
    SADEH_DATA_SOURCE = "Sadeh_Data_Source"
    ACTILIFE_VS_CALCULATED_AGREEMENT = "ActiLife_vs_Calculated_Agreement_Percent"
    ACTILIFE_VS_CALCULATED_DISAGREEMENTS = "ActiLife_vs_Calculated_Disagreements"
    CHOI_ONSET = "Nonwear Algorithm Value at Onset"
    CHOI_OFFSET = "Nonwear Algorithm Value at Offset"
    TOTAL_CHOI_COUNTS = "Total Nonwear Algorithm Counts"

    # Generic algorithm results (NEW - use for all algorithms)
    SLEEP_ALGORITHM_NAME = "Sleep Scoring Algorithm"
    SLEEP_ALGORITHM_ONSET = "Sleep Algorithm Value at Onset"
    SLEEP_ALGORITHM_OFFSET = "Sleep Algorithm Value at Offset"

    # Onset/offset rule (NEW - for DI pattern)
    ONSET_OFFSET_RULE = "Onset/Offset Rule"

    # NWT sensor data columns
    NWT_ONSET = "NWT Sensor Value at Sleep Onset"
    NWT_OFFSET = "NWT Sensor Value at Sleep Offset"
    TOTAL_NWT_COUNTS = "Total NWT Sensor Counts over the Sleep Period"

    SAVED_AT = "Saved At"

    # Multiple sleep period columns
    MARKER_TYPE = "Marker Type"
    MARKER_INDEX = "Marker Index"

    # Diary nap columns
    NAP_OCCURRED = "Nap Occurred"
    NAP_ONSET_TIME = "Nap Onset Time"
    NAP_OFFSET_TIME = "Nap Offset Time"
    NAP_ONSET_TIME_2 = "Nap 2 Onset Time"
    NAP_OFFSET_TIME_2 = "Nap 2 Offset Time"
    NAP_ONSET_TIME_3 = "Nap 3 Onset Time"
    NAP_OFFSET_TIME_3 = "Nap 3 Offset Time"

    # Diary nonwear time columns
    NONWEAR_OCCURRED = "Nonwear Occurred"
    NONWEAR_REASON = "Nonwear Reason"
    NONWEAR_START_TIME = "Nonwear Start Time"
    NONWEAR_END_TIME = "Nonwear End Time"
    NONWEAR_REASON_2 = "Nonwear 2 Reason"
    NONWEAR_START_TIME_2 = "Nonwear 2 Start Time"
    NONWEAR_END_TIME_2 = "Nonwear 2 End Time"
    NONWEAR_REASON_3 = "Nonwear 3 Reason"
    NONWEAR_START_TIME_3 = "Nonwear 3 Start Time"
    NONWEAR_END_TIME_3 = "Nonwear 3 End Time"


class ActivityColumn(StrEnum):
    """Activity data column search keywords."""

    VECTOR = "vector"
    MAGNITUDE = "magnitude"
    VM = "vm"
    VECTORMAGNITUDE = "vectormagnitude"
    ACTIVITY = "activity"
    COUNT = "count"
    # Axis detection patterns (lowercase for matching)
    AXIS_Y = "axis_y"  # ActiGraph Axis1 = Y-axis (vertical)
    AXIS_X = "axis_x"  # ActiGraph Axis2 = X-axis (lateral)
    AXIS_Z = "axis_z"  # ActiGraph Axis3 = Z-axis (forward)
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"


class ActivityDataPreference(StrEnum):
    """Activity data column preferences for algorithms and plotting."""

    AXIS_Y = "axis_y"  # Vertical axis (ActiGraph Axis1)
    AXIS_X = "axis_x"  # Lateral axis (ActiGraph Axis2)
    AXIS_Z = "axis_z"  # Forward axis (ActiGraph Axis3)
    VECTOR_MAGNITUDE = "vector_magnitude"


class ConfigDefaults:
    """Configuration default values."""

    MAX_RECENT_FILES = 10
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    EPOCH_LENGTH = 60
    SKIP_ROWS = 10
    # Activity column preferences - Y-axis (vertical) is default for Sadeh algorithm
    DEFAULT_ACTIVITY_COLUMN = ActivityDataPreference.AXIS_Y
    DEFAULT_CHOI_ACTIVITY_COLUMN = ActivityDataPreference.VECTOR_MAGNITUDE
    DEFAULT_PLOT_ACTIVITY_COLUMN = ActivityDataPreference.AXIS_Y
    # View mode preferences
    DEFAULT_VIEW_MODE = "48h"  # Changed from 24h to 48h as requested
    # UI element visibility
    SEPARATOR_VISIBLE_DEFAULT = True


class DefaultColumn(StrEnum):
    """Default CSV column names for ActiGraph format."""

    DATE = "DATE"
    TIME = "TIME"
    ACTIVITY = "ACTIVITY"
    VECTOR_MAGNITUDE = "Vector Magnitude"
    AXIS_Y = "Axis1"  # ActiGraph CSV header name for Y-axis (vertical)


# ============================================================================
# PARTICIPANT DATA
# ============================================================================


class ParticipantGroup(StrEnum):
    """Compatibility enum for participant groups used in tests and exports."""

    GROUP_1 = "G1"
    ISSUE = "ISSUE"


class ParticipantTimepoint(StrEnum):
    """Compatibility enum for participant timepoints used in tests and exports."""

    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class RegexPattern(StrEnum):
    """Regular expression patterns."""

    PARTICIPANT_GROUP = r"g(\d+)"
    FILENAME_PATTERN = r"^(\d+)\s+([A-Z0-9]+)\s+\((\d{4}-\d{2}-\d{2})\)60sec$"
    PARTICIPANT_ID = r".*(\d+).*"


# ============================================================================
# FILE SYSTEM
# ============================================================================


class FileExtension(StrEnum):
    """Supported file extensions."""

    CSV = ".csv"
    JSON = ".json"
    DB = ".db"
    LOG = ".log"


class DirectoryName(StrEnum):
    """Directory names used by the application."""

    BACKUPS = "backups"
    DATA = "data"
    RESULTS = "results"
    AUTOSAVES = "autosaves"
    CONFIG = ".sleep-scoring-demo"
    SLEEP_DATA_EXPORTS = "sleep_data_exports"


class FileName(StrEnum):
    """File names used by the application."""

    SLEEP_SCORING_DB = "sleep_scoring.db"
    CONFIG_JSON = "config.json"


# ============================================================================
# MEMORY MANAGEMENT
# ============================================================================


class MemoryConstants:
    """Memory management constants."""

    # BoundedCache limits
    CACHE_MAX_SIZE = 500
    CACHE_MAX_MEMORY_MB = 500

    # Memory monitoring thresholds
    MEMORY_WARNING_THRESHOLD_MB = 1000
    MEMORY_CRITICAL_THRESHOLD_MB = 2000

    # Cache cleanup
    DEFAULT_MAX_AGE_HOURS = 24
    MEMORY_UTILIZATION_THRESHOLD = 0.7


# ============================================================================
# CONFIGURATION
# ============================================================================


class ConfigKey(StrEnum):
    """Configuration file keys."""

    DATA_FOLDER = "data_folder"
    EPOCH_LENGTH = "epoch_length"
    ACTIVITY_EPOCH_DATA_SKIP_ROWS = "activity_epoch_data_skip_rows"
    DATE_COLUMN = "date_column"
    TIME_COLUMN = "time_column"
    ACTIVITY_COLUMN = "activity_column"
    WINDOW_WIDTH = "window_width"
    WINDOW_HEIGHT = "window_height"
    RECENT_FILES = "recent_files"


# ============================================================================
# USER INTERFACE
# ============================================================================


class ViewMode(StrEnum):
    """Plot view modes."""

    HOURS_24 = "24h"
    HOURS_48 = "48h"


class ViewHours:
    """View mode hour constants."""

    HOURS_24 = 24
    HOURS_48 = 48


class MessageType(StrEnum):
    """Message dialog types."""

    INFORMATION = "Information"
    WARNING = "Warning"
    ERROR = "Error"
    QUESTION = "Question"


# --- Window and Dialog Text ---


class WindowTitle(StrEnum):
    """Window and dialog titles."""

    MAIN_WINDOW = "Sleep Research Analysis Tool - Activity Data Visualization"
    EXPORT_DIALOG = "Export Sleep Scoring Data"
    FOLDER_LOADED = "Folder Loaded"
    NO_FILES_FOUND = "No Files Found"
    NO_FOLDER_SELECTED = "No Folder Selected"
    NO_MARKERS = "No Markers"
    NO_FILE_SELECTED = "No File Selected"
    MARKERS_SAVED = "Markers Saved"
    EXPORT_READY = "Export Ready"
    EXPORT_ERROR = "Export Error"
    NO_DATA = "No Data"
    CLEAR_ALL_MARKERS = "Clear All Markers"
    MARK_NO_SLEEP = "Mark No Sleep"
    SELECT_STUDY_DAYS_FILE = "Select Study Days File"
    SELECT_NWT_DATA_FOLDER = "Select NWT Data Folder"
    SELECT_FOLDER = "Select Folder"
    SELECT_CSV_FILE = "Select CSV File"
    SELECT_DIARY_FOLDER = "Select Diary Data Folder"
    SELECT_DIARY_FILES = "Select Diary Files"


class ButtonText(StrEnum):
    """Button text constants."""

    SAVE_MARKERS = "Save Markers"
    MARKERS_SAVED = "Markers Saved ✓"
    NO_SLEEP_MARKED = "No Sleep Marked ✓"
    LOAD_DATA_FOLDER = "Load Data Folder"
    ANALYZE_COLUMNS = "Analyze Columns"
    EXPORT = "Export"
    CANCEL = "Cancel"
    BROWSE = "Browse..."
    CLEAR_MARKERS = "Clear Markers"
    CLEAR_ACTIVITY_DATA = "Clear Activity Data"
    CLEAR_STUDY_DAYS = "Clear Study Days"
    CLEAR_NWT_DATA = "Clear NWT Data"
    CLEAR_ACTILIFE_DATA = "Clear ActiLife Data"
    CLEAR_DIARY_DATA = "Clear Diary Data"
    MARK_NO_SLEEP = "Mark No Sleep"
    START_IMPORT = "Start Import"
    IMPORT_DIARIES = "Import Diaries"
    MAP_COLUMNS = "Map Columns"
    MAPPING_IN_PROGRESS = "Mapping..."
    MAPPING_COMPLETE = "Mapping Complete ✓"


class TabName(StrEnum):
    """Tab names."""

    DATA_SETTINGS = "Data Settings"
    ANALYSIS = "Analysis"
    EXPORT_TAB = "Export"
    IMPORT_TAB = "Import"


class LabelText(StrEnum):
    """Label text constants."""

    DATA_FOLDER = "Data Folder:"
    EPOCH_LENGTH = "Epoch Length (seconds):"
    SKIP_ROWS = "Skip Rows:"
    DATE_COLUMN = "Date Column:"
    TIME_COLUMN = "Time Column:"
    ACTIVITY_COLUMN = "Activity Column:"


class MenuText(StrEnum):
    """Menu item text."""

    FILE_MENU = "File"
    CHANGE_DATA_FOLDER = "Change Data Folder..."
    EXIT = "Exit"


class GroupBoxTitle(StrEnum):
    """Group box titles."""

    ACTIVITY_DATA = "Activity Data"
    NONWEAR_SENSOR_DATA = "Nonwear Time (NWT) Sensor Data"
    ACTILIFE_NONWEAR_DATA = "ActiLife Nonwear Export Data"
    CHOI_ALGORITHM_DATA = "Choi Algorithm Results"
    DIARY_DATA = "Diary Data"


# --- Status and Messages ---


class StatusMessage(StrEnum):
    """Status bar messages."""

    NO_MARKERS = "Sleep Period Markers: No markers placed. Click on the activity plot to mark sleep start and end times."
    USAGE_INSTRUCTIONS = "Usage: Click to place sleep markers • Mouse wheel to zoom • Drag to pan horizontally"
    SLEEP_START_ONLY = "Sleep Start Time: {} | Click on the plot again to set the sleep end time"
    SLEEP_PERIOD_DEFINED = "Sleep Period Defined: {} to {} | Total Duration: {:.1f} hours | Use Q/E (left) A/D (right) to adjust"


class InfoMessage(StrEnum):
    """Information messages."""

    NO_FOLDER_SELECTED = "No folder selected"
    NO_FILE_SELECTED = "Select CSV file..."
    NO_CSV_FILES_FOUND = "No CSV files found"
    SELECT_FOLDER_FIRST = "Please select a data folder first."
    NO_MARKERS_TO_SAVE = "No sleep markers to save. Please place markers first."
    NO_MARKERS_FOUND = "No sleep markers or metrics found in the database."
    IMPORTED_RAW_DATA_PRESERVED = "Imported raw data will be preserved."
    NO_DIRECTORY_SELECTED = "No directory selected"
    NO_FILE_SELECTED_DEFAULT = "No file selected"
    READY_TO_IMPORT = "Ready to import"
    NOT_IMPLEMENTED = "Not implemented"


class ConfirmationMessage(StrEnum):
    """Confirmation dialog messages."""

    CLEAR_ALL_MARKERS = "Are you sure you want to clear all sleep markers and metrics from the database?"
    MARK_NO_SLEEP_CONFIRM = "Mark {} as having no sleep period?\n\nThis will PERMANENTLY DELETE all existing markers for this date and save a record indicating no sleep occurred."
    ACTION_CANNOT_BE_UNDONE = "This action cannot be undone."


class SuccessMessage(StrEnum):
    """Success messages."""

    MARKERS_SAVED_TO_DATABASE = "Sleep markers saved to database successfully!"
    NO_SLEEP_MARKED_SUCCESS = "Date {} marked as having no sleep period.\n\nThis record has been saved to the database."
    IMPORT_COMPLETED = "Import completed successfully!"
    EXPORT_COMPLETED = "Export completed successfully!"


class ErrorMessage(StrEnum):
    """Error messages."""

    FAILED_TO_DELETE_MARKERS = "Failed to delete existing markers: {}"
    FAILED_TO_SAVE_MARKERS = "Error saving markers: {}"
    NO_DATA_AVAILABLE = "No data available for export."
    EXPORT_FAILED = "Export failed: {}"
    IMPORT_FAILED = "Import failed: {}"


class TooltipText(StrEnum):
    """Tooltip messages."""

    ONSET_TIME_INPUT = "Sleep onset time (HH:MM format) - Auto-updates on Enter"
    OFFSET_TIME_INPUT = "Sleep offset time (HH:MM format) - Auto-updates on Enter"
    SAVE_MARKERS = "Save current markers permanently"
    CLEAR_MARKERS = "Clear all sleep markers"
    MARK_NO_SLEEP = "Mark this date as having no sleep period"
    EXPORT_BUTTON = "Export sleep markers and metrics to CSV"
    TIME_COLUMN = "Time in HH:MM format"
    ACTIVITY_COLUMN = "Raw activity counts"
    VM_COLUMN = "Vector Magnitude activity counts"
    SADEH_COLUMN = "Sadeh Algorithm: S=Sleep, W=Wake"
    CHOI_COLUMN = "Choi Algorithm: On=Wearing, Off=Not wearing"
    NWT_SENSOR_COLUMN = "NWT Sensor: Off=Not wearing"
    ACTIVITY_SOURCE_DROPDOWN = "Select which activity data column to display and use for Choi algorithm analysis.\nNote: Sadeh algorithm always uses Axis 1 regardless of this setting."


class FileDialogText(StrEnum):
    """File dialog text."""

    SELECT_DATA_FOLDER = "Select folder containing CSV data files"
    EMPTY_PATH = ""


# --- Styling ---


class UIColors(StrEnum):
    """UI color constants."""

    # Plot styling
    AXIS_PEN = "#333333"
    AXIS_TEXT = "#444444"
    ACTIVITY_DATA = "#2E86AB"
    SLEEP_START = "green"
    SLEEP_END = "red"
    SLEEP_ONSET_MARKER = "#0066CC"
    SLEEP_OFFSET_MARKER = "#CC0000"
    BACKGROUND_WHITE = "w"
    FOREGROUND_BLACK = "k"

    # Extended marker colors (colorblind-friendly blue/orange scheme)
    SELECTED_MARKER_ONSET = "#0080FF"  # Bright blue for main sleep onset
    SELECTED_MARKER_OFFSET = "#FF8000"  # Bright orange for main sleep offset
    UNSELECTED_MARKER_ONSET = "#004080"  # Darker blue for nap onset
    UNSELECTED_MARKER_OFFSET = "#CC4000"  # Darker orange for nap offset
    INCOMPLETE_MARKER = "#808080"  # Gray for incomplete markers
    HOVERED_MARKER = "#606060"  # Gray for selected/hovered markers
    NWT_MARKER_FILL = "#FFE4B5"  # Light beige fill
    NWT_MARKER_BORDER = "#D2691E"  # Chocolate border

    # Nonwear visualization colors (colorblind-friendly scheme)
    NONWEAR_SENSOR_BRUSH = "255,215,0,60"  # Gold with transparency for NWT sensor
    NONWEAR_SENSOR_BORDER = "218,165,32,120"  # Darker gold border
    CHOI_ALGORITHM_BRUSH = "147,112,219,60"  # Medium purple with transparency for Choi
    CHOI_ALGORITHM_BORDER = "138,43,226,120"  # Blue violet border for Choi
    NONWEAR_OVERLAP_BRUSH = "65,105,225,60"  # Royal blue with transparency for overlap
    NONWEAR_OVERLAP_BORDER = "0,0,255,120"  # Pure blue border for overlap

    # Date status colors
    DATE_WITH_MARKERS = "#27ae60"  # Green for dates with markers
    DATE_NO_SLEEP = "#e74c3c"  # Red for no sleep dates
    DATE_PARTIAL_COMPLETION = "#ff8c00"  # Orange for partial completion

    # Focus and interaction colors
    FOCUS_BORDER = "#0080FF"  # Blue focus border
    FOCUS_BACKGROUND = "#f0f8ff"  # Light blue focus background

    # Diary selection colors
    DIARY_SELECTION_DARKER = "#1a5490"  # Darker blue for diary selection highlighting

    # Button colors - Primary (blue)
    BUTTON_PRIMARY = "#4a90e2"
    BUTTON_PRIMARY_HOVER = "#357abd"
    BUTTON_PRIMARY_PRESSED = "#2868a8"
    BUTTON_PRIMARY_ALT = "#3498db"
    BUTTON_PRIMARY_ALT_HOVER = "#2980b9"

    # Button colors - Success (green)
    BUTTON_SUCCESS = "#28a745"
    BUTTON_SUCCESS_HOVER = "#229954"
    BUTTON_SUCCESS_ALT = "#2ecc71"
    BUTTON_SUCCESS_ALT_HOVER = "#27ae60"

    # Button colors - Danger (red)
    BUTTON_DANGER = "#dc3545"
    BUTTON_DANGER_HOVER = "#c0392b"
    BUTTON_DANGER_ALT = "#e74c3c"
    BUTTON_DANGER_ALT_HOVER = "#ec7063"

    # Button colors - Warning (orange)
    BUTTON_WARNING = "#ffc107"
    BUTTON_WARNING_HOVER = "#e0a800"

    # Panel/Background colors
    PANEL_BACKGROUND = "#f0f0f0"
    PANEL_BACKGROUND_LIGHT = "#f8f8f8"
    PANEL_BACKGROUND_SUCCESS = "#f0fff0"
    PANEL_BACKGROUND_ERROR = "#fff0f0"
    PANEL_BORDER = "#ced4da"
    PANEL_BORDER_LIGHT = "#ddd"

    # Text colors
    TEXT_PRIMARY = "#333333"
    TEXT_SECONDARY = "#666666"
    TEXT_MUTED = "#999999"

    # Status colors
    STATUS_ERROR = "#e74c3c"
    STATUS_SUCCESS = "#27ae60"
    STATUS_WARNING = "#f39c12"
    STATUS_INFO = "#3498db"

    # Table colors
    TABLE_ONSET_BACKGROUND = "#87CEEB"
    TABLE_OFFSET_BACKGROUND = "#FFDAB9"
    TABLE_HEADER_BACKGROUND = "#e0e0e0"
    TABLE_ROW_ALT = "#f5f5f5"


class ButtonStyle(StrEnum):
    """Button CSS styles."""

    # Common focus style for all interactive elements
    FOCUS_STYLE = "QPushButton:focus { border: 2px solid #0080FF; background-color: #f0f8ff; }"

    SAVE_MARKERS = """
        QPushButton {
            font-weight: bold;
            background-color: #0066CC;
            color: white;
        }
        QPushButton:focus {
            border: 2px solid #0080FF;
        }
    """
    SAVE_MARKERS_SAVED = """
        QPushButton {
            font-weight: bold;
            background-color: #004080;
            color: white;
        }
        QPushButton:focus {
            border: 2px solid #0080FF;
        }
    """
    MARK_NO_SLEEP = """
        QPushButton {
            font-weight: bold;
            background-color: #FF8000;
            color: white;
        }
        QPushButton:focus {
            border: 2px solid #0080FF;
        }
    """
    NO_SLEEP_MARKED = """
        QPushButton {
            font-weight: bold;
            background-color: #CC4000;
            color: white;
        }
        QPushButton:focus {
            border: 2px solid #0080FF;
        }
    """
    NAVIGATION = "font-size: 16px; padding: 8px 16px;"
    BOLD_PADDED = "font-weight: bold; padding: 5px 10px;"
    EXPORT = "font-weight: bold; padding: 10px;"
    CLEAR_MARKERS_RED = """
        QPushButton {
            font-weight: bold;
            padding: 5px 10px;
            background-color: #dc3545;
            color: white;
            border: 1px solid #bd2130;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #c82333;
        }
        QPushButton:pressed {
            background-color: #bd2130;
        }
    """


class LabelStyle(StrEnum):
    """Label CSS styles."""

    FOLDER_INFO = "color: #666; margin-left: 10px;"
    DATE_LABEL = "font-weight: bold; font-size: 20px; min-width: 200px; margin: 0 20px;"


# --- Table and Plot Configuration ---


class TableColumn(StrEnum):
    """Table column identifiers."""

    TIME = "Time"
    ACTIVITY = "Activity"
    VM = "VM"  # Vector Magnitude
    SADEH = "Sadeh"
    CHOI = "Choi"
    NWT_SENSOR = "NWT Sensor"
    IS_MARKER = "is_marker"
    START_TIME = "start_time"
    END_TIME = "end_time"
    DURATION_MINUTES = "duration_minutes"
    TIMESTAMP = "timestamp"
    SLEEP_WAKE_SCORE = "sleep_wake_score"
    AXIS_Y = "Axis Y"  # Display name for Y-axis (vertical)


class TableDimensions:
    """Table layout dimensions."""

    ROW_HEIGHT = 20
    ROW_COUNT = 21
    ELEMENTS_AROUND_MARKER = 10

    # Fixed table widths for side tables
    TABLE_MIN_WIDTH = 1
    TABLE_MAX_WIDTH = 250
    TABLE_MARGINS = 5
    TABLE_SPACING = 3
    TABLE_HEADER_HEIGHT = 22
    TABLE_FONT_SIZE = 9

    # Marker table colors (matching the actual markers)
    ONSET_MARKER_BACKGROUND = "#87CEEB"  # Light blue (135, 206, 235) - Sky blue
    ONSET_MARKER_FOREGROUND = "#000000"  # Black text for readability
    OFFSET_MARKER_BACKGROUND = "#FFDAB9"  # Light orange/peach (255, 218, 185)
    OFFSET_MARKER_FOREGROUND = "#000000"  # Black text for readability


class PlotConstants:
    """Plot widget constants."""

    TICK_MAJOR = 3600  # 1 hour
    TICK_MINOR = 900  # 15 minutes
    MARKER_ADJUSTMENT_SECONDS = 60
    MINUTE_SNAP_SECONDS = 60


# ============================================================================
# SLEEP MARKERS AND LABELS
# ============================================================================


class MarkerLabel(StrEnum):
    """Sleep marker labels."""

    SLEEP_START = "Sleep Start"
    SLEEP_END = "Sleep End"
    SLEEP_ONSET = "Sleep Onset at {}\n3-minute rule applied"
    SLEEP_OFFSET = "Sleep Offset at {}\n5-minute rule applied"

    # Extended marker labels
    MAIN_SLEEP_START = "Main Sleep Start"
    MAIN_SLEEP_END = "Main Sleep End"
    NAP_START = "Nap Start"
    NAP_END = "Nap End"
    NWT_START = "Non-wear Start"
    NWT_END = "Non-wear End"


class PeriodKey(StrEnum):
    """Sleep period dictionary keys."""

    START_INDEX = "start_index"
    END_INDEX = "end_index"
    DURATION_MINUTES = "duration_minutes"


# ============================================================================
# DEBUGGING AND LOGGING
# ============================================================================


class DebugMessage(StrEnum):
    """Debug/logging messages."""

    AUTO_SAVED_MARKERS = "Auto-saved markers on change for {}"
    LOADED_SAVED_MARKERS = "Loaded saved markers for {} on {} from database"
    LOADED_RECORDS_ON_STARTUP = "Loaded {} saved records on startup from database"
    FOUND_DATA_FOR_FILES = "Found data for {} files: {}"
    USING_VECTOR_MAGNITUDE = "Using vector magnitude for Choi algorithm"
    VECTOR_MAGNITUDE_UNAVAILABLE = "Vector magnitude requested but multi-axis data not available, using single axis"
    DATA_INTERVALS_WARNING = "Data intervals may not be exactly 1 minute - proceeding with algorithm"


# ============================================================================
# EXTERNAL INTEGRATION
# ============================================================================


class AppArgument(StrEnum):
    """Application arguments."""

    PLATFORM = "-platform"
    WINDOWS_DARKMODE = "windows:darkmode=1"
    STYLE_FUSION = "--style=Fusion"


class PyQtGraphConfig(StrEnum):
    """PyQtGraph configuration keys."""

    BACKGROUND = "background"
    FOREGROUND = "foreground"
    ANTIALIAS = "antialias"


class DevicePreset(StrEnum):
    """Device/format preset options."""

    ACTIGRAPH = "actigraph"
    GENEACTIV = "geneactiv"
    AXIVITY = "axivity"
    ACTIWATCH = "actiwatch"
    MOTIONWATCH = "motionwatch"
    GENERIC_CSV = "generic_csv"


class DataSourceType(StrEnum):
    """Data source type options."""

    CSV = "csv"
    GT3X = "gt3x"

    @classmethod
    def get_default(cls) -> "DataSourceType":
        """Get the default data source type."""
        return cls.CSV

    @classmethod
    def migrate_legacy_value(cls, value: str) -> "DataSourceType":
        """
        Migrate legacy data source type values to current values.

        Args:
            value: Legacy or current data source type string

        Returns:
            Current DataSourceType value

        """
        # Map legacy values to current values
        legacy_mapping = {
            "csv_file": cls.CSV,
            "excel": cls.CSV,
            "xlsx": cls.CSV,
            "gt3x_file": cls.GT3X,
            "actigraph": cls.GT3X,
        }

        # Check if it's a legacy value
        if value in legacy_mapping:
            return legacy_mapping[value]

        # Check if it's already a valid current value
        try:
            return cls(value)
        except ValueError:
            # Unknown value, default to CSV
            return cls.CSV


class NonwearAlgorithm(StrEnum):
    """
    Nonwear detection algorithm identifiers.

    These values match the algorithm IDs registered in NonwearAlgorithmFactory.
    Use these for storing/retrieving algorithm type in database and exports.

    For creating algorithm instances, use NonwearAlgorithmFactory.create(algorithm_id).
    """

    # Nonwear detection algorithms (registered in NonwearAlgorithmFactory)
    CHOI_2011 = "choi_2011"
    VAN_HEES_2023 = "van_hees_2023"

    # Future algorithms
    VANHEES_2013 = "vanhees_2013"

    # Legacy values - kept for migration compatibility
    _LEGACY_CHOI = "choi"  # Migrate to CHOI_2011

    @classmethod
    def get_default(cls) -> "NonwearAlgorithm":
        """Get the default nonwear algorithm type."""
        return cls.CHOI_2011

    @classmethod
    def migrate_legacy_value(cls, value: str) -> "NonwearAlgorithm":
        """
        Migrate legacy algorithm type values to current values.

        Args:
            value: Legacy or current algorithm type string

        Returns:
            Current NonwearAlgorithm value

        """
        # Map legacy values to current values
        legacy_mapping = {
            "choi": cls.CHOI_2011,
            "Choi": cls.CHOI_2011,
            "choi_algorithm": cls.CHOI_2011,
            "vanhees_2023": cls.VAN_HEES_2023,
            "van_hees_2023": cls.VAN_HEES_2023,
        }

        # Check if it's a legacy value
        if value in legacy_mapping:
            return legacy_mapping[value]

        # Check if it's already a valid current value
        try:
            return cls(value)
        except ValueError:
            # Unknown value, default to CHOI_2011
            return cls.CHOI_2011


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def sanitize_filename_component(text: str) -> str:
    """Sanitize text for use in filenames."""
    return "".join(c for c in str(text) if c.isalnum() or c in ("-", "_")).strip()


def get_backup_filename(algorithm: AlgorithmType) -> str:
    """Generate backup filename for algorithm."""
    safe_algorithm = sanitize_filename_component(algorithm)
    return f"sleep_scoring_backup_{safe_algorithm}{FileExtension.CSV}"
