"""
CSV data loader service.

Ported from desktop app's io/sources/csv_loader.py for web use.
Loads activity data from CSV and Excel files with automatic column detection.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ColumnMapping:
    """CSV column mapping configuration."""

    date_column: str | None = None
    time_column: str | None = None
    datetime_column: str | None = None
    activity_column: str | None = None
    axis_x_column: str | None = None
    axis_z_column: str | None = None
    vector_magnitude_column: str | None = None


class CSVLoaderService:
    """
    CSV/XLSX data source loader.

    Loads activity data from CSV and Excel files with automatic column detection
    and format validation.
    """

    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".csv", ".xlsx", ".xls"})

    def __init__(self, skip_rows: int = 10) -> None:
        """
        Initialize CSV loader.

        Args:
            skip_rows: Number of header rows to skip (default 10 for ActiGraph)
        """
        self.skip_rows = skip_rows
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit

    def load_file(
        self,
        file_path: str | Path,
        skip_rows: int | None = None,
        custom_columns: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Load activity data from CSV/XLSX file.

        Args:
            file_path: Path to the data file
            skip_rows: Number of header rows to skip
            custom_columns: Optional custom column mapping

        Returns:
            Dictionary containing:
                - activity_data: pd.DataFrame with standardized columns
                - metadata: dict with file metadata
                - column_mapping: ColumnMapping object

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file format is invalid
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {suffix}")

        skip_rows = skip_rows if skip_rows is not None else self.skip_rows

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            msg = f"File too large: {file_size / 1024 / 1024:.1f}MB > {self.max_file_size / 1024 / 1024:.1f}MB"
            raise ValueError(msg)

        # Load CSV/Excel file
        try:
            if suffix == ".csv":
                df = pd.read_csv(file_path, skiprows=skip_rows, skipinitialspace=True)
            else:
                df = pd.read_excel(file_path, skiprows=skip_rows)
        except pd.errors.EmptyDataError as e:
            raise ValueError(f"Empty data file: {file_path}") from e
        except pd.errors.ParserError as e:
            raise ValueError(f"Failed to parse file: {file_path}") from e

        if df.empty:
            raise ValueError(f"No data in file: {file_path}")

        # Strip whitespace from column names
        df.columns = df.columns.str.strip()

        # Detect or use custom column mapping
        if custom_columns:
            column_mapping = self._create_custom_mapping(df, custom_columns)
        else:
            column_mapping = self.detect_columns(df)

        # Validate column mapping
        is_valid, errors = self._validate_column_mapping(column_mapping)
        if not is_valid:
            raise ValueError(f"Invalid column mapping: {', '.join(errors)}")

        # Standardize columns
        standardized_df = self._standardize_columns(df, column_mapping)

        # Validate standardized data
        is_valid, errors = self.validate_data(standardized_df)
        if not is_valid:
            raise ValueError(f"Data validation failed: {', '.join(errors)}")

        # Extract metadata
        metadata = self.get_file_metadata(file_path)

        # Infer sample rate from timestamps
        sample_rate = None
        if len(standardized_df) >= 2:
            time_diff = (
                standardized_df["timestamp"].iloc[1] - standardized_df["timestamp"].iloc[0]
            ).total_seconds()
            if time_diff > 0:
                sample_rate = 1.0 / time_diff

        metadata.update({
            "loader": "csv",
            "total_epochs": len(standardized_df),
            "start_time": standardized_df["timestamp"].iloc[0],
            "end_time": standardized_df["timestamp"].iloc[-1],
            "sample_rate": sample_rate,
        })

        return {
            "activity_data": standardized_df,
            "metadata": metadata,
            "column_mapping": column_mapping,
        }

    def detect_columns(self, df: pd.DataFrame) -> ColumnMapping:
        """Detect and map column names automatically."""
        columns = list(df.columns)
        mapping = ColumnMapping()

        # Detect combined datetime column first
        for col in columns:
            col_lower = col.lower().strip()
            if col_lower in ("datetime", "timestamp"):
                mapping.datetime_column = col
                break

        # If no combined datetime, look for separate date/time columns
        if mapping.datetime_column is None:
            for col in columns:
                col_lower = col.lower().strip()
                if "date" in col_lower and mapping.date_column is None:
                    mapping.date_column = col
                if "time" in col_lower and mapping.time_column is None:
                    mapping.time_column = col

        # Find Y-axis (activity) column first - this is the primary activity measure for Sadeh
        for col in columns:
            col_lower = col.lower().strip()
            if col_lower in ("axis_y", "axis1", "y", "axis 1", "y-axis"):
                mapping.activity_column = col
                break

        # Detect other axis columns
        for col in columns:
            col_lower = col.lower().strip()
            if col_lower in ("axis_x", "axis2", "x", "axis 2"):
                mapping.axis_x_column = col
            if col_lower in ("axis_z", "axis3", "z", "axis 3"):
                mapping.axis_z_column = col

        # Find vector magnitude column (separate from activity column)
        for col in columns:
            col_lower = col.lower().strip()
            if any(kw in col_lower for kw in ["vector", "magnitude", "vm"]):
                mapping.vector_magnitude_column = col
                # If no Y-axis found, use vector magnitude as fallback activity
                if mapping.activity_column is None:
                    mapping.activity_column = col
                break

        return mapping

    def _create_custom_mapping(self, df: pd.DataFrame, custom_columns: dict[str, str]) -> ColumnMapping:
        """Create column mapping from custom specification."""
        columns = list(df.columns)
        mapping = ColumnMapping()

        if custom_columns.get("datetime_combined"):
            date_col = custom_columns.get("date")
            if date_col and date_col in columns:
                mapping.datetime_column = date_col
        else:
            date_col = custom_columns.get("date")
            time_col = custom_columns.get("time")
            if date_col and date_col in columns:
                mapping.date_column = date_col
            if time_col and time_col in columns:
                mapping.time_column = time_col

        activity_col = custom_columns.get("activity")
        if activity_col and activity_col in columns:
            mapping.activity_column = activity_col

        axis_y = custom_columns.get("axis_y")
        if axis_y and axis_y in columns and not mapping.activity_column:
            mapping.activity_column = axis_y

        axis_x = custom_columns.get("axis_x")
        if axis_x and axis_x in columns:
            mapping.axis_x_column = axis_x

        axis_z = custom_columns.get("axis_z")
        if axis_z and axis_z in columns:
            mapping.axis_z_column = axis_z

        vm = custom_columns.get("vector_magnitude")
        if vm and vm in columns:
            mapping.vector_magnitude_column = vm

        return mapping

    def _validate_column_mapping(self, mapping: ColumnMapping) -> tuple[bool, list[str]]:
        """Validate that required columns are present."""
        errors = []

        if not mapping.datetime_column and not mapping.date_column:
            errors.append("Missing timestamp column")

        if not mapping.activity_column:
            errors.append("Missing activity column")

        return len(errors) == 0, errors

    def _standardize_columns(self, df: pd.DataFrame, mapping: ColumnMapping) -> pd.DataFrame:
        """Standardize column names to database schema."""
        result = pd.DataFrame()

        # Process timestamp
        if mapping.datetime_column:
            result["timestamp"] = pd.to_datetime(df[mapping.datetime_column])
        elif mapping.date_column:
            if mapping.time_column:
                datetime_str = df[mapping.date_column].astype(str) + " " + df[mapping.time_column].astype(str)
            else:
                datetime_str = df[mapping.date_column].astype(str)
            result["timestamp"] = pd.to_datetime(datetime_str)

        # Map activity column to axis_y
        if mapping.activity_column:
            result["axis_y"] = df[mapping.activity_column].fillna(0).astype(float)

        # Map additional axis columns
        if mapping.axis_x_column:
            result["axis_x"] = df[mapping.axis_x_column].fillna(0).astype(float)

        if mapping.axis_z_column:
            result["axis_z"] = df[mapping.axis_z_column].fillna(0).astype(float)

        # Handle vector magnitude
        if mapping.vector_magnitude_column:
            result["vector_magnitude"] = df[mapping.vector_magnitude_column].fillna(0).astype(float)
        elif "axis_x" in result and "axis_y" in result and "axis_z" in result:
            result["vector_magnitude"] = result.apply(
                lambda row: math.sqrt(row["axis_x"] ** 2 + row["axis_y"] ** 2 + row["axis_z"] ** 2),
                axis=1,
            )

        return result

    def validate_data(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Validate data structure and content."""
        errors = []

        if "timestamp" not in df.columns:
            errors.append("Missing timestamp column")

        if "axis_y" not in df.columns:
            errors.append("Missing axis_y column")

        if len(df) == 0:
            errors.append("DataFrame is empty")

        return len(errors) == 0, errors

    def get_file_metadata(self, file_path: str | Path) -> dict[str, Any]:
        """Extract file metadata."""
        file_path = Path(file_path)
        return {
            "file_size": file_path.stat().st_size,
            "device_type": "actigraph",
            "epoch_length_seconds": 60,
        }
