"""
Constants for Sleep Scoring Application.

This package provides centralized definitions for all string enums,
numeric constants, and configuration values used throughout the application.

The constants are organized into domain-specific modules:
- algorithms: Algorithm-related constants (sleep scoring, nonwear detection)
- database: Database schema constants (tables, columns)
- io: Import/export and file system constants
- ui: User interface constants (styling, messages, configuration)

All constants are re-exported from this __init__.py for backward compatibility.
You can import directly from the submodules for more specific imports:

    # Full backward-compatible import
    from sleep_scoring_app.core.constants import AlgorithmType, DatabaseColumn

    # Domain-specific import
    from sleep_scoring_app.core.constants.algorithms import AlgorithmType
    from sleep_scoring_app.core.constants.database import DatabaseColumn
"""

# Algorithm constants
from .algorithms import (
    AlgorithmParams,
    AlgorithmResult,
    AlgorithmType,
    MarkerCategory,
    MarkerEndpoint,
    MarkerLimits,
    MarkerType,
    NonwearAlgorithm,
    NonwearDataSource,
    SadehDataSource,
    SelectionState,
    SleepStatusValue,
    StudyDataParadigm,
)

# Database constants
from .database import (
    DatabaseColumn,
    DatabaseTable,
)

# I/O constants
from .io import (
    ActivityColumn,
    ActivityDataPreference,
    DataSourceType,
    DefaultColumn,
    DeleteStatus,
    DevicePreset,
    DiaryFileType,
    DirectoryName,
    ExportColumn,
    FileExtension,
    FileName,
    ImportStatus,
    ParticipantGroup,
    ParticipantTimepoint,
    RegexPattern,
    get_backup_filename,
    sanitize_filename_component,
)

# UI constants
from .ui import (
    AlgorithmHelpText,
    AlgorithmTooltip,
    AppArgument,
    ButtonStyle,
    ButtonText,
    ConfigDefaults,
    ConfigKey,
    ConfirmationMessage,
    DebugMessage,
    ErrorMessage,
    FeatureFlags,
    FileDialogText,
    GroupBoxTitle,
    InfoMessage,
    LabelStyle,
    LabelText,
    MarkerLabel,
    MemoryConstants,
    MenuText,
    MessageType,
    ParadigmInfoText,
    ParadigmLabel,
    ParadigmStyle,
    ParadigmTooltip,
    ParadigmWarning,
    PeriodKey,
    PlotConstants,
    PyQtGraphConfig,
    SettingsSection,
    StatusMessage,
    SuccessMessage,
    TableColumn,
    TableDimensions,
    TabName,
    TimeConstants,
    TimeFormat,
    TooltipText,
    UIColors,
    ViewHours,
    ViewMode,
    WindowTitle,
)

__all__ = [
    "ActivityColumn",
    "ActivityDataPreference",
    "AlgorithmHelpText",
    "AlgorithmParams",
    "AlgorithmResult",
    "AlgorithmTooltip",
    # Algorithm constants
    "AlgorithmType",
    "AppArgument",
    "ButtonStyle",
    "ButtonText",
    "ConfigDefaults",
    "ConfigKey",
    "ConfirmationMessage",
    "DataSourceType",
    "DatabaseColumn",
    # Database constants
    "DatabaseTable",
    "DebugMessage",
    "DefaultColumn",
    "DeleteStatus",
    "DevicePreset",
    "DiaryFileType",
    "DirectoryName",
    "ErrorMessage",
    "ExportColumn",
    # UI constants
    "FeatureFlags",
    "FileDialogText",
    "FileExtension",
    "FileName",
    "GroupBoxTitle",
    # I/O constants
    "ImportStatus",
    "InfoMessage",
    "LabelStyle",
    "LabelText",
    "MarkerCategory",
    "MarkerEndpoint",
    "MarkerLabel",
    "MarkerLimits",
    "MarkerType",
    "MemoryConstants",
    "MenuText",
    "MessageType",
    "NonwearAlgorithm",
    "NonwearDataSource",
    "ParadigmInfoText",
    "ParadigmLabel",
    "ParadigmStyle",
    "ParadigmTooltip",
    "ParadigmWarning",
    "ParticipantGroup",
    "ParticipantTimepoint",
    "PeriodKey",
    "PlotConstants",
    "PyQtGraphConfig",
    "RegexPattern",
    "SadehDataSource",
    "SelectionState",
    "SettingsSection",
    "SleepStatusValue",
    "StatusMessage",
    "StudyDataParadigm",
    "SuccessMessage",
    "TabName",
    "TableColumn",
    "TableDimensions",
    "TimeConstants",
    "TimeFormat",
    "TooltipText",
    "UIColors",
    "ViewHours",
    "ViewMode",
    "WindowTitle",
    "get_backup_filename",
    "sanitize_filename_component",
]
