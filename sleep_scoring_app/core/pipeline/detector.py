"""
Data source type detection for pipeline routing.

This module automatically detects whether a file contains:
- Raw high-frequency tri-axial accelerometer data
- Pre-aggregated 60-second epoch count data

Detection is based on file format and column structure.

Example Usage:
    >>> from sleep_scoring_app.core.pipeline import DataSourceDetector
    >>>
    >>> detector = DataSourceDetector()
    >>>
    >>> # Detect from file path
    >>> source_type = detector.detect_from_file("data.gt3x")
    >>> print(source_type)  # DataSourceType.GT3X_RAW
    >>>
    >>> # Detect from loaded DataFrame
    >>> import pandas as pd
    >>> df = pd.read_csv("data.csv")
    >>> source_type = detector.detect_from_dataframe(df)

References:
    - CLAUDE.md: Protocol-first design
    - types.py: DataSourceType enum

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    import pandas as pd

from .exceptions import DataDetectionError
from .types import DataSourceType

logger = logging.getLogger(__name__)


class DataSourceDetector:
    """
    Detector for identifying data source types.

    This class implements automatic detection logic to distinguish between
    raw accelerometer data and pre-epoched count data.

    Detection Rules:
        1. GT3X files -> Always GT3X_RAW (binary format contains raw data)
        2. CSV with AXIS_X, AXIS_Y, AXIS_Z -> CSV_RAW (raw tri-axial data)
        3. CSV with Axis1/Activity + ~60s intervals -> CSV_EPOCH (epoch counts)

    Example:
        >>> detector = DataSourceDetector()
        >>> source_type = detector.detect_from_file("data.gt3x")
        >>> if source_type.is_raw():
        ...     print("Raw data detected")

    """

    # Column patterns for detection
    RAW_CSV_COLUMNS: ClassVar[set[str]] = {"AXIS_X", "AXIS_Y", "AXIS_Z"}
    EPOCH_CSV_COLUMNS: ClassVar[set[str]] = {"Axis1"}  # Can also be "Activity"
    TIMESTAMP_COLUMNS: ClassVar[set[str]] = {
        "timestamp",
        "datetime",
        "Timestamp",
        "Date Time",
    }

    # Threshold for epoch detection (seconds)
    # If median interval is ~60s (+/-10s tolerance), consider it epoch data
    EPOCH_INTERVAL_MIN = 50
    EPOCH_INTERVAL_MAX = 70

    def detect_from_file(self, file_path: str | Path) -> DataSourceType:
        """
        Detect data source type from file path.

        This method uses file extension and (for CSV) column inspection
        to determine the data source type.

        Args:
            file_path: Path to data file

        Returns:
            DataSourceType enum value

        Raises:
            DataDetectionError: If data type cannot be determined
            FileNotFoundError: If file does not exist

        Example:
            >>> detector = DataSourceDetector()
            >>> source_type = detector.detect_from_file("raw_data.gt3x")
            >>> print(source_type)  # DataSourceType.GT3X_RAW

        """
        file_path = Path(file_path)

        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        # Check file extension
        extension = file_path.suffix.lower()

        # GT3X files are always raw data
        if extension == ".gt3x":
            logger.debug(f"Detected GT3X file: {file_path.name}")
            return DataSourceType.GT3X_RAW

        # CSV files require content inspection
        if extension == ".csv":
            return self._detect_csv_type(file_path)

        # Unknown file type
        raise DataDetectionError(
            file_path=str(file_path),
            reason=f"Unsupported file extension: {extension}. Supported: .gt3x, .csv",
        )

    def detect_from_dataframe(self, df: pd.DataFrame) -> DataSourceType:
        """
        Detect data source type from loaded DataFrame.

        This method inspects column names and data intervals to determine
        whether the DataFrame contains raw or epoch data.

        Args:
            df: DataFrame to inspect

        Returns:
            DataSourceType enum value

        Raises:
            DataDetectionError: If data type cannot be determined

        Example:
            >>> import pandas as pd
            >>> df = pd.read_csv("data.csv")
            >>> detector = DataSourceDetector()
            >>> source_type = detector.detect_from_dataframe(df)

        """
        if df is None or len(df) == 0:
            raise DataDetectionError(
                file_path="<dataframe>",
                reason="DataFrame is None or empty",
            )

        # Get column names (case-insensitive check)
        columns = set(df.columns)
        columns_lower = {col.lower() for col in columns}

        # Check for raw tri-axial data columns
        if self._has_raw_columns(columns):
            logger.debug("Detected raw tri-axial data (AXIS_X, AXIS_Y, AXIS_Z columns)")
            return DataSourceType.CSV_RAW

        # Check for epoch count column
        if self._has_epoch_columns(columns):
            # Verify interval is ~60 seconds
            if self._has_epoch_intervals(df):
                logger.debug("Detected epoch count data (Axis1 column with 60s intervals)")
                return DataSourceType.CSV_EPOCH
            # Has Axis1 but not 60s intervals - might be raw counts
            logger.warning("Found Axis1 column but intervals are not ~60s. This may be raw epoch data at different resolution.")
            return DataSourceType.CSV_EPOCH  # Still treat as epoch data

        # Cannot determine type
        available_columns = ", ".join(sorted(columns)[:10])
        raise DataDetectionError(
            file_path="<dataframe>",
            reason=(
                f"Cannot determine data type from columns. "
                f"Expected either (AXIS_X, AXIS_Y, AXIS_Z) for raw data "
                f"or (Axis1/Activity) for epoch data. "
                f"Found columns: {available_columns}"
            ),
        )

    def _detect_csv_type(self, file_path: Path) -> DataSourceType:
        """
        Detect CSV data type by loading and inspecting columns.

        Args:
            file_path: Path to CSV file

        Returns:
            DataSourceType enum value

        Raises:
            DataDetectionError: If CSV type cannot be determined

        """
        try:
            import pandas as pd

            # Read first few rows to inspect columns
            df_sample = pd.read_csv(file_path, nrows=100)

            return self.detect_from_dataframe(df_sample)

        except Exception as e:
            raise DataDetectionError(
                file_path=str(file_path),
                reason=f"Failed to read CSV file: {e}",
            ) from e

    def _has_raw_columns(self, columns: set[str]) -> bool:
        """
        Check if DataFrame has raw tri-axial data columns.

        Args:
            columns: Set of column names

        Returns:
            True if AXIS_X, AXIS_Y, AXIS_Z columns are present

        """
        return self.RAW_CSV_COLUMNS.issubset(columns)

    def _has_epoch_columns(self, columns: set[str]) -> bool:
        """
        Check if DataFrame has epoch count column.

        Args:
            columns: Set of column names

        Returns:
            True if Axis1 or Activity column is present

        """
        columns_lower = {col.lower() for col in columns}
        return any(epoch_col.lower() in columns_lower for epoch_col in ["Axis1", "Activity", "axis1", "activity"])

    def _has_epoch_intervals(self, df: pd.DataFrame) -> bool:
        """
        Check if DataFrame has ~60 second intervals between timestamps.

        Args:
            df: DataFrame to inspect

        Returns:
            True if median interval is approximately 60 seconds

        """
        # Find timestamp column
        timestamp_col = self._find_timestamp_column(df)

        if timestamp_col is None:
            logger.warning("No timestamp column found, cannot verify epoch intervals")
            return True  # Assume epoch data if no timestamp column

        try:
            import pandas as pd

            # Convert to datetime
            timestamps = pd.to_datetime(df[timestamp_col])

            # Calculate intervals
            intervals = timestamps.diff().dt.total_seconds()

            # Get median interval (ignore first NaN)
            median_interval = intervals.median()

            logger.debug(f"Median timestamp interval: {median_interval}s")

            # Check if ~60 seconds (+/-10s tolerance)
            return self.EPOCH_INTERVAL_MIN <= median_interval <= self.EPOCH_INTERVAL_MAX

        except Exception as e:
            logger.warning(f"Failed to check timestamp intervals: {e}")
            return True  # Assume epoch data if interval check fails

    def _find_timestamp_column(self, df: pd.DataFrame) -> str | None:
        """
        Find timestamp/datetime column in DataFrame.

        Args:
            df: DataFrame to inspect

        Returns:
            Column name if found, None otherwise

        """
        # Check for common timestamp column names
        for col in df.columns:
            if col in self.TIMESTAMP_COLUMNS:
                return col

            # Case-insensitive check
            if col.lower() in {tc.lower() for tc in self.TIMESTAMP_COLUMNS}:
                return col

        return None
