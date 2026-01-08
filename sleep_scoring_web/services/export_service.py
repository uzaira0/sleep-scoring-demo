"""
Export service for sleep scoring data.

Generates CSV exports with selectable columns from markers and metrics data.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sleep_scoring_web.db.models import File, Marker, SleepMetric

logger = logging.getLogger(__name__)


# =============================================================================
# Column Registry - Single Source of Truth for Export Columns
# =============================================================================


@dataclass(frozen=True)
class ColumnDefinition:
    """Definition of an export column."""

    name: str
    category: str
    description: str
    data_type: str = "string"
    is_default: bool = True


# Define all available export columns
EXPORT_COLUMNS: list[ColumnDefinition] = [
    # File Info
    ColumnDefinition("Filename", "File Info", "Source data filename"),
    ColumnDefinition("File ID", "File Info", "Database file ID", "number"),
    ColumnDefinition("Participant ID", "File Info", "Extracted participant ID"),
    # Period Info
    ColumnDefinition("Analysis Date", "Period Info", "Date being analyzed"),
    ColumnDefinition("Period Index", "Period Info", "Sleep period number (1=first)", "number"),
    ColumnDefinition("Marker Type", "Period Info", "MAIN_SLEEP or NAP"),
    # Time Markers
    ColumnDefinition("Onset Time", "Time Markers", "Sleep onset time (HH:MM)"),
    ColumnDefinition("Offset Time", "Time Markers", "Sleep offset time (HH:MM)"),
    ColumnDefinition("Onset Datetime", "Time Markers", "Full onset datetime", "datetime"),
    ColumnDefinition("Offset Datetime", "Time Markers", "Full offset datetime", "datetime"),
    # Duration Metrics
    ColumnDefinition("Time in Bed (min)", "Duration Metrics", "Total time from onset to offset", "number"),
    ColumnDefinition("Total Sleep Time (min)", "Duration Metrics", "TST - minutes scored as sleep", "number"),
    ColumnDefinition("WASO (min)", "Duration Metrics", "Wake After Sleep Onset minutes", "number"),
    ColumnDefinition("Sleep Onset Latency (min)", "Duration Metrics", "Time to fall asleep", "number"),
    # Awakening Metrics
    ColumnDefinition("Number of Awakenings", "Awakening Metrics", "Count of wake periods", "number"),
    ColumnDefinition("Avg Awakening Length (min)", "Awakening Metrics", "Mean awakening duration", "number"),
    # Quality Indices
    ColumnDefinition("Sleep Efficiency (%)", "Quality Indices", "TST / Time in Bed * 100", "number"),
    ColumnDefinition("Movement Index", "Quality Indices", "Movement indicator", "number"),
    ColumnDefinition("Fragmentation Index", "Quality Indices", "Sleep fragmentation", "number"),
    ColumnDefinition("Sleep Fragmentation Index", "Quality Indices", "Combined fragmentation", "number"),
    # Activity Metrics
    ColumnDefinition("Total Activity Counts", "Activity Metrics", "Sum of activity counts", "number"),
    ColumnDefinition("Non-zero Epochs", "Activity Metrics", "Count of epochs with movement", "number"),
    # Algorithm Info
    ColumnDefinition("Algorithm", "Algorithm Info", "Sleep scoring algorithm used"),
    ColumnDefinition("Verification Status", "Algorithm Info", "Draft, verified, etc."),
]

# Group columns by category
COLUMN_CATEGORIES: dict[str, list[str]] = {}
for col in EXPORT_COLUMNS:
    if col.category not in COLUMN_CATEGORIES:
        COLUMN_CATEGORIES[col.category] = []
    COLUMN_CATEGORIES[col.category].append(col.name)

# Default columns (subset for quick export)
DEFAULT_COLUMNS = [col.name for col in EXPORT_COLUMNS if col.is_default]


# =============================================================================
# Export Result
# =============================================================================


@dataclass
class ExportResult:
    """Result of an export operation."""

    success: bool
    csv_content: str = ""
    filename: str = ""
    row_count: int = 0
    file_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Export Service
# =============================================================================


class ExportService:
    """Service for generating CSV exports from sleep scoring data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def get_available_columns() -> list[ColumnDefinition]:
        """Get list of all available export columns."""
        return EXPORT_COLUMNS

    @staticmethod
    def get_column_categories() -> dict[str, list[str]]:
        """Get columns grouped by category."""
        return COLUMN_CATEGORIES

    @staticmethod
    def get_default_columns() -> list[str]:
        """Get list of default column names."""
        return DEFAULT_COLUMNS

    async def export_csv(
        self,
        file_ids: list[int],
        date_range: tuple[date, date] | None = None,
        columns: list[str] | None = None,
        include_header: bool = True,
        include_metadata: bool = False,
    ) -> ExportResult:
        """
        Generate CSV export for specified files.

        Args:
            file_ids: List of file IDs to export
            date_range: Optional (start_date, end_date) filter
            columns: Column names to include (None = all default columns)
            include_header: Whether to include CSV header row
            include_metadata: Whether to include metadata comments at top

        Returns:
            ExportResult with CSV content and statistics
        """
        result = ExportResult(success=False)

        if not file_ids:
            result.errors.append("No files specified for export")
            return result

        # Determine columns to export
        export_columns = columns if columns else DEFAULT_COLUMNS

        # Validate columns
        valid_column_names = {col.name for col in EXPORT_COLUMNS}
        invalid_columns = [c for c in export_columns if c not in valid_column_names]
        if invalid_columns:
            result.warnings.append(f"Skipping invalid columns: {', '.join(invalid_columns)}")
            export_columns = [c for c in export_columns if c in valid_column_names]

        if not export_columns:
            result.errors.append("No valid columns selected for export")
            return result

        try:
            # Fetch data from database
            rows = await self._fetch_export_data(file_ids, date_range)

            if not rows:
                result.warnings.append("No data found for selected files and date range")
                result.success = True
                result.csv_content = ""
                return result

            # Generate CSV
            csv_content = self._generate_csv(rows, export_columns, include_header, include_metadata)

            result.success = True
            result.csv_content = csv_content
            result.row_count = len(rows)
            result.file_count = len(set(row.get("File ID") for row in rows))
            result.filename = f"sleep_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            logger.info(
                "Export completed: %d rows from %d files",
                result.row_count,
                result.file_count,
            )
            return result

        except Exception as e:
            logger.exception("Export failed: %s", e)
            result.errors.append(f"Export failed: {str(e)}")
            return result

    async def _fetch_export_data(
        self,
        file_ids: list[int],
        date_range: tuple[date, date] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch and join data from markers and metrics tables."""
        rows: list[dict[str, Any]] = []

        # Get files info
        files_result = await self.db.execute(
            select(File).where(File.id.in_(file_ids))
        )
        files = {f.id: f for f in files_result.scalars().all()}

        # Build marker query
        marker_query = select(Marker).where(
            and_(
                Marker.file_id.in_(file_ids),
                Marker.marker_category == "sleep",
                Marker.end_timestamp.isnot(None),  # Only complete markers
            )
        )

        if date_range:
            start_date, end_date = date_range
            marker_query = marker_query.where(
                and_(
                    Marker.analysis_date >= start_date,
                    Marker.analysis_date <= end_date,
                )
            )

        marker_query = marker_query.order_by(
            Marker.file_id, Marker.analysis_date, Marker.period_index
        )

        markers_result = await self.db.execute(marker_query)
        markers = markers_result.scalars().all()

        for marker in markers:
            file = files.get(marker.file_id)
            if not file:
                continue

            # Get metrics for this marker
            metrics = await self._get_metrics_for_marker(marker)

            # Convert timestamps to datetime
            onset_dt = datetime.fromtimestamp(marker.start_timestamp) if marker.start_timestamp else None
            offset_dt = datetime.fromtimestamp(marker.end_timestamp) if marker.end_timestamp else None

            row = {
                # File Info
                "Filename": file.filename,
                "File ID": file.id,
                "Participant ID": file.participant_id or "",
                # Period Info
                "Analysis Date": str(marker.analysis_date) if marker.analysis_date else "",
                "Period Index": marker.period_index,
                "Marker Type": marker.marker_type,
                # Time Markers
                "Onset Time": onset_dt.strftime("%H:%M") if onset_dt else "",
                "Offset Time": offset_dt.strftime("%H:%M") if offset_dt else "",
                "Onset Datetime": onset_dt.strftime("%Y-%m-%d %H:%M:%S") if onset_dt else "",
                "Offset Datetime": offset_dt.strftime("%Y-%m-%d %H:%M:%S") if offset_dt else "",
            }

            # Add metrics if available
            if metrics:
                row.update({
                    "Time in Bed (min)": self._format_number(metrics.time_in_bed_minutes),
                    "Total Sleep Time (min)": self._format_number(metrics.total_sleep_time_minutes),
                    "WASO (min)": self._format_number(metrics.waso_minutes),
                    "Sleep Onset Latency (min)": self._format_number(metrics.sleep_onset_latency_minutes),
                    "Number of Awakenings": metrics.number_of_awakenings,
                    "Avg Awakening Length (min)": self._format_number(metrics.average_awakening_length_minutes),
                    "Sleep Efficiency (%)": self._format_number(metrics.sleep_efficiency),
                    "Movement Index": self._format_number(metrics.movement_index),
                    "Fragmentation Index": self._format_number(metrics.fragmentation_index),
                    "Sleep Fragmentation Index": self._format_number(metrics.sleep_fragmentation_index),
                    "Total Activity Counts": metrics.total_activity,
                    "Non-zero Epochs": metrics.nonzero_epochs,
                    "Algorithm": metrics.algorithm_type or "",
                    "Verification Status": metrics.verification_status or "draft",
                })
            else:
                # Fill with empty values
                row.update({
                    "Time in Bed (min)": "",
                    "Total Sleep Time (min)": "",
                    "WASO (min)": "",
                    "Sleep Onset Latency (min)": "",
                    "Number of Awakenings": "",
                    "Avg Awakening Length (min)": "",
                    "Sleep Efficiency (%)": "",
                    "Movement Index": "",
                    "Fragmentation Index": "",
                    "Sleep Fragmentation Index": "",
                    "Total Activity Counts": "",
                    "Non-zero Epochs": "",
                    "Algorithm": "",
                    "Verification Status": "draft",
                })

            rows.append(row)

        return rows

    async def _get_metrics_for_marker(self, marker: Marker) -> SleepMetric | None:
        """Get metrics for a specific marker."""
        result = await self.db.execute(
            select(SleepMetric).where(
                and_(
                    SleepMetric.file_id == marker.file_id,
                    SleepMetric.analysis_date == marker.analysis_date,
                    SleepMetric.period_index == marker.period_index,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _format_number(value: float | int | None, precision: int = 2) -> str:
        """Format number for CSV output."""
        if value is None:
            return ""
        if isinstance(value, int):
            return str(value)
        return f"{value:.{precision}f}"

    def _generate_csv(
        self,
        rows: list[dict[str, Any]],
        columns: list[str],
        include_header: bool = True,
        include_metadata: bool = False,
    ) -> str:
        """Generate CSV string from rows."""
        output = io.StringIO()

        # Add metadata comments if requested
        if include_metadata:
            output.write("#\n")
            output.write("# Sleep Scoring Export\n")
            output.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            output.write(f"# Total Rows: {len(rows)}\n")
            output.write(f"# Files: {len(set(r.get('File ID') for r in rows))}\n")
            output.write("#\n")

        writer = csv.DictWriter(
            output,
            fieldnames=columns,
            extrasaction="ignore",
        )

        if include_header:
            writer.writeheader()

        for row in rows:
            # Sanitize values to prevent CSV injection
            sanitized_row = {k: self._sanitize_csv_value(v) for k, v in row.items()}
            writer.writerow(sanitized_row)

        return output.getvalue()

    @staticmethod
    def _sanitize_csv_value(value: Any) -> Any:
        """Sanitize value to prevent CSV formula injection."""
        if not isinstance(value, str):
            return value
        if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + value
        return value
