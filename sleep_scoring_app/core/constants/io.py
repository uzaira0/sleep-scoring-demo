"""
I/O related constants for Sleep Scoring Application.

Contains enums and constants for data import, export, file system operations,
and external integrations.
"""

from enum import StrEnum

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


class DeleteStatus(StrEnum):
    """File deletion status values."""

    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    HAS_METRICS = "has_metrics"


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

    # Overlapping nonwear minutes during sleep period
    OVERLAPPING_NONWEAR_MINUTES_ALGORITHM = "Overlapping Nonwear Minutes (Algorithm)"
    OVERLAPPING_NONWEAR_MINUTES_SENSOR = "Overlapping Nonwear Minutes (Sensor)"

    # Generic algorithm results (NEW - use for all algorithms)
    SLEEP_ALGORITHM_NAME = "Sleep Scoring Algorithm"
    SLEEP_ALGORITHM_ONSET = "Sleep Algorithm Value at Onset"
    SLEEP_ALGORITHM_OFFSET = "Sleep Algorithm Value at Offset"

    # Onset/offset rule (NEW - for DI pattern)
    ONSET_OFFSET_RULE = "Onset/Offset Rule"

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
# EXTERNAL INTEGRATION
# ============================================================================


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


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def sanitize_filename_component(text: str) -> str:
    """Sanitize text for use in filenames."""
    return "".join(c for c in str(text) if c.isalnum() or c in ("-", "_")).strip()


def get_backup_filename(algorithm: str) -> str:
    """Generate backup filename for algorithm."""
    safe_algorithm = sanitize_filename_component(algorithm)
    return f"sleep_scoring_backup_{safe_algorithm}{FileExtension.CSV}"
