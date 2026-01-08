"""
Export API endpoints.

Provides endpoints for generating CSV exports of sleep scoring data.
"""

from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from sleep_scoring_web.api.deps import CurrentUser, DbSession
from sleep_scoring_web.schemas import (
    ExportColumnCategory,
    ExportColumnInfo,
    ExportColumnsResponse,
    ExportRequest,
    ExportResponse,
)
from sleep_scoring_web.services.export_service import (
    COLUMN_CATEGORIES,
    EXPORT_COLUMNS,
    ExportService,
)

router = APIRouter()


@router.get("/columns", response_model=ExportColumnsResponse)
async def get_export_columns(
    current_user: CurrentUser,
) -> ExportColumnsResponse:
    """
    Get list of available export columns.

    Returns all available columns with their metadata, grouped by category.
    """
    columns = [
        ExportColumnInfo(
            name=col.name,
            category=col.category,
            description=col.description,
            data_type=col.data_type,
            is_default=col.is_default,
        )
        for col in EXPORT_COLUMNS
    ]

    categories = [
        ExportColumnCategory(name=name, columns=cols)
        for name, cols in COLUMN_CATEGORIES.items()
    ]

    return ExportColumnsResponse(columns=columns, categories=categories)


@router.post("/csv", response_model=ExportResponse)
async def generate_csv_export(
    request: ExportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ExportResponse:
    """
    Generate CSV export for specified files.

    Returns metadata about the export. Use /csv/download to get the actual file.
    """
    service = ExportService(db)

    result = await service.export_csv(
        file_ids=request.file_ids,
        date_range=request.date_range,
        columns=request.columns,
        include_header=request.include_header,
        include_metadata=request.include_metadata,
    )

    return ExportResponse(
        success=result.success,
        filename=result.filename,
        row_count=result.row_count,
        file_count=result.file_count,
        message=f"Exported {result.row_count} rows from {result.file_count} files" if result.success else "Export failed",
        warnings=result.warnings + result.errors,
    )


@router.post("/csv/download")
async def download_csv_export(
    request: ExportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """
    Generate and download CSV export.

    Returns the CSV file directly as a download.
    """
    service = ExportService(db)

    result = await service.export_csv(
        file_ids=request.file_ids,
        date_range=request.date_range,
        columns=request.columns,
        include_header=request.include_header,
        include_metadata=request.include_metadata,
    )

    if not result.success:
        # Return error as CSV comment
        error_content = f"# Export Error\n# {'; '.join(result.errors)}\n"
        return StreamingResponse(
            iter([error_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="export_error.csv"',
            },
        )

    return StreamingResponse(
        iter([result.csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
        },
    )


@router.get("/csv/quick")
async def quick_export(
    file_ids: str = Query(description="Comma-separated file IDs"),
    db: DbSession = None,
    current_user: CurrentUser = None,
    start_date: date | None = Query(default=None, description="Start date filter"),
    end_date: date | None = Query(default=None, description="End date filter"),
) -> StreamingResponse:
    """
    Quick export endpoint for simple GET requests.

    Uses default columns and returns CSV directly.
    """
    # Parse file IDs
    try:
        ids = [int(x.strip()) for x in file_ids.split(",") if x.strip()]
    except ValueError:
        error_content = "# Error: Invalid file IDs format\n"
        return StreamingResponse(
            iter([error_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="export_error.csv"',
            },
        )

    if not ids:
        error_content = "# Error: No file IDs provided\n"
        return StreamingResponse(
            iter([error_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="export_error.csv"',
            },
        )

    service = ExportService(db)

    date_range = (start_date, end_date) if start_date and end_date else None

    result = await service.export_csv(
        file_ids=ids,
        date_range=date_range,
        columns=None,  # Use default columns
        include_header=True,
        include_metadata=True,
    )

    if not result.success:
        error_content = f"# Export Error\n# {'; '.join(result.errors)}\n"
        return StreamingResponse(
            iter([error_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="export_error.csv"',
            },
        )

    return StreamingResponse(
        iter([result.csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
        },
    )
