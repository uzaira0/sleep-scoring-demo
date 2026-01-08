"""
File upload and management API endpoints.

Provides endpoints for uploading, listing, and managing activity data files.
Uses FastAPI BackgroundTasks for non-blocking file processing.

Note: We intentionally avoid `from __future__ import annotations` here
because FastAPI's dependency injection needs actual types, not string
annotations. Using Annotated types requires runtime resolution.
"""

import asyncio
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from sqlalchemy import func, select

from sleep_scoring_web.api.deps import CurrentUser, DbSession
from sleep_scoring_web.config import settings
from sleep_scoring_web.db.models import File as FileModel
from sleep_scoring_web.db.models import RawActivityData
from sleep_scoring_web.db.session import async_session_maker
from sleep_scoring_web.schemas import FileInfo, FileListResponse, FileStatus, FileUploadResponse
from sleep_scoring_web.services.loaders.csv_loader import CSVLoaderService

router = APIRouter()


# =============================================================================
# Scan Status Tracking (in-memory, per-process)
# =============================================================================


@dataclass
class ScanStatus:
    """Track background scan progress."""

    is_running: bool = False
    total_files: int = 0
    processed: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    current_file: str = ""
    imported_files: list[str] = field(default_factory=list)
    error: str | None = None


# Global scan status (simple in-memory tracking)
_scan_status = ScanStatus()


def get_upload_path() -> Path:
    """Get upload directory path, creating if needed."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_data_path() -> Path:
    """Get data directory path."""
    return Path(settings.data_dir)


async def bulk_insert_activity_data(
    db,
    file_id: int,
    activity_df,
) -> int:
    """
    Bulk insert activity data using PostgreSQL COPY for maximum performance.

    For PostgreSQL: Uses COPY protocol via asyncpg (fastest possible)
    For SQLite: Falls back to executemany with raw connection

    Returns the number of rows inserted.
    """
    import io

    if len(activity_df) == 0:
        return 0

    # Prepare DataFrame with required columns
    activity_df = activity_df.reset_index(drop=True)
    activity_df["file_id"] = file_id
    activity_df["epoch_index"] = range(len(activity_df))

    # Ensure columns exist
    for col in ["axis_x", "axis_y", "axis_z", "vector_magnitude"]:
        if col not in activity_df.columns:
            activity_df[col] = None

    # Select and order columns for COPY
    columns = ["file_id", "timestamp", "epoch_index", "axis_x", "axis_y", "axis_z", "vector_magnitude"]
    export_df = activity_df[columns].copy()

    # Convert to appropriate types
    for col in ["axis_x", "axis_y", "axis_z", "vector_magnitude"]:
        export_df[col] = export_df[col].apply(lambda x: int(x) if x is not None and not (isinstance(x, float) and x != x) else None)

    # Get raw connection to use COPY
    raw_conn = await db.connection()
    driver_conn = await raw_conn.get_raw_connection()

    if hasattr(driver_conn, "copy_records_to_table"):
        # PostgreSQL with asyncpg - use COPY protocol (FASTEST)
        records = [
            (row.file_id, row.timestamp, row.epoch_index, row.axis_x, row.axis_y, row.axis_z, row.vector_magnitude)
            for row in export_df.itertuples(index=False)
        ]
        await driver_conn.copy_records_to_table(
            "raw_activity_data",
            records=records,
            columns=columns,
        )
    else:
        # SQLite or other - use executemany (still fast)
        from sqlalchemy import text

        insert_sql = text("""
            INSERT INTO raw_activity_data (file_id, timestamp, epoch_index, axis_x, axis_y, axis_z, vector_magnitude)
            VALUES (:file_id, :timestamp, :epoch_index, :axis_x, :axis_y, :axis_z, :vector_magnitude)
        """)
        records = export_df.to_dict("records")

        # Convert pandas Timestamps to Python datetime for SQLite compatibility
        # Must be done after to_dict() since DataFrame reverts to Timestamp
        for record in records:
            ts = record["timestamp"]
            if hasattr(ts, "to_pydatetime"):
                record["timestamp"] = ts.to_pydatetime()

        await db.execute(insert_sql, records)

    return len(activity_df)


async def import_file_from_disk_async(
    file_path: Path,
    db,
    user_id: int,
) -> FileUploadResponse | None:
    """Import a single file from disk into the database (async version)."""
    filename = file_path.name

    # Check if file already exists
    result = await db.execute(select(FileModel).where(FileModel.filename == filename))
    existing_file = result.scalar_one_or_none()
    if existing_file:
        return None  # Skip already imported files

    # Create file record
    file_record = FileModel(
        filename=filename,
        original_path=str(file_path.absolute()),
        file_type="csv" if filename.lower().endswith(".csv") else "xlsx",
        status=FileStatus.PROCESSING,
        uploaded_by_id=user_id,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    # Process file and load activity data
    try:
        loader = CSVLoaderService(skip_rows=settings.default_skip_rows)
        result = loader.load_file(file_path)

        activity_df = result["activity_data"]
        metadata = result["metadata"]

        # Update file record with metadata
        file_record.row_count = len(activity_df)
        file_record.start_time = metadata.get("start_time")
        file_record.end_time = metadata.get("end_time")
        file_record.metadata_json = {
            k: str(v) if isinstance(v, datetime) else v
            for k, v in metadata.items()
            if k not in ("start_time", "end_time")
        }
        file_record.status = FileStatus.READY

        # Bulk insert activity data (FAST)
        await bulk_insert_activity_data(db, file_record.id, activity_df)
        await db.commit()

        return FileUploadResponse(
            file_id=file_record.id,
            filename=filename,
            status=FileStatus.READY,
            row_count=file_record.row_count,
            message=f"Imported from disk: {file_path}",
        )

    except Exception as e:
        # Mark file as failed
        file_record.status = FileStatus.FAILED
        await db.commit()
        print(f"Failed to import {filename}: {e}")
        return None


async def _async_scan_files(user_id: int, csv_files: list[Path]) -> None:
    """
    Async file scan implementation.

    This is the actual async work that imports files into the database.
    """
    global _scan_status

    async with async_session_maker() as db:
        for file_path in csv_files:
            _scan_status.current_file = file_path.name
            try:
                result = await import_file_from_disk_async(file_path, db, user_id)
                if result is None:
                    # Check if skipped or failed
                    existing = await db.execute(
                        select(FileModel).where(FileModel.filename == file_path.name)
                    )
                    if existing.scalar_one_or_none():
                        _scan_status.skipped += 1
                    else:
                        _scan_status.failed += 1
                else:
                    _scan_status.imported += 1
                    _scan_status.imported_files.append(result.filename)
            except Exception as e:
                _scan_status.failed += 1
                print(f"Background scan error for {file_path.name}: {e}")

            _scan_status.processed += 1

    _scan_status.is_running = False
    _scan_status.current_file = ""


def _run_background_scan(user_id: int, csv_files: list[Path]) -> None:
    """
    Run file scan in background thread.

    Uses anyio.from_thread.run to properly execute async code from
    the thread pool where BackgroundTasks runs sync functions.
    """
    import anyio.from_thread

    try:
        anyio.from_thread.run(_async_scan_files, user_id, csv_files)
    except Exception as e:
        global _scan_status
        _scan_status.is_running = False
        _scan_status.error = str(e)
        print(f"Background scan failed: {e}")


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="CSV file to upload")],
    db: DbSession,
    current_user: CurrentUser,
) -> FileUploadResponse:
    """
    Upload a CSV file for processing.

    The file will be parsed, validated, and stored in the database.
    Activity data will be extracted and made available for analysis.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Validate file extension
    filename = file.filename
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported",
        )

    # Check if file already exists
    result = await db.execute(select(FileModel).where(FileModel.filename == filename))
    existing_file = result.scalar_one_or_none()
    if existing_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{filename}' already exists",
        )

    # Save file to upload directory
    upload_path = get_upload_path() / filename
    try:
        with upload_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}",
        ) from e
    finally:
        await file.close()

    # Create file record
    file_record = FileModel(
        filename=filename,
        original_path=str(upload_path),
        file_type="csv" if filename.lower().endswith(".csv") else "xlsx",
        status=FileStatus.PROCESSING,
        uploaded_by_id=current_user.id,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    # Process file and load activity data
    try:
        loader = CSVLoaderService(skip_rows=settings.default_skip_rows)
        result = loader.load_file(upload_path)

        activity_df = result["activity_data"]
        metadata = result["metadata"]

        # Update file record with metadata
        file_record.row_count = len(activity_df)
        file_record.start_time = metadata.get("start_time")
        file_record.end_time = metadata.get("end_time")
        file_record.metadata_json = {
            k: str(v) if isinstance(v, datetime) else v
            for k, v in metadata.items()
            if k not in ("start_time", "end_time")
        }
        file_record.status = FileStatus.READY

        # Bulk insert using COPY (PostgreSQL) or executemany (SQLite)
        await bulk_insert_activity_data(db, file_record.id, activity_df)
        await db.commit()

        return FileUploadResponse(
            file_id=file_record.id,
            filename=filename,
            status=FileStatus.READY,
            row_count=file_record.row_count,
            message="File uploaded and processed successfully",
        )

    except Exception as e:
        # Mark file as failed
        file_record.status = FileStatus.FAILED
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process file: {e}",
        ) from e


@router.get("", response_model=FileListResponse)
async def list_files(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> FileListResponse:
    """List all uploaded files."""
    # Get total count
    count_result = await db.execute(select(func.count(FileModel.id)))
    total = count_result.scalar() or 0

    # Get files with pagination
    result = await db.execute(
        select(FileModel).order_by(FileModel.uploaded_at.desc()).offset(skip).limit(limit)
    )
    files = result.scalars().all()

    return FileListResponse(
        files=[
            FileInfo(
                id=f.id,
                filename=f.filename,
                original_path=f.original_path,
                file_type=f.file_type,
                status=FileStatus(f.status),
                row_count=f.row_count,
                start_time=f.start_time,
                end_time=f.end_time,
                uploaded_by_id=f.uploaded_by_id,
                uploaded_at=f.uploaded_at,
            )
            for f in files
        ],
        total=total,
    )


@router.get("/{file_id}", response_model=FileInfo)
async def get_file(
    file_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileInfo:
    """Get file metadata by ID."""
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return FileInfo(
        id=file.id,
        filename=file.filename,
        original_path=file.original_path,
        file_type=file.file_type,
        status=FileStatus(file.status),
        row_count=file.row_count,
        start_time=file.start_time,
        end_time=file.end_time,
        uploaded_by_id=file.uploaded_by_id,
        uploaded_at=file.uploaded_at,
    )


@router.get("/{file_id}/dates", response_model=list[str])
async def get_file_dates(
    file_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[str]:
    """Get available dates for a file."""
    # Verify file exists
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Get distinct dates from activity data using labeled column
    date_col = func.date(RawActivityData.timestamp).label("date")
    result = await db.execute(
        select(date_col)
        .where(RawActivityData.file_id == file_id)
        .group_by(date_col)
        .order_by(date_col)
    )
    dates = result.scalars().all()

    return [str(d) for d in dates]


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_file(
    file_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Delete a file and its associated data."""
    # Only admins can delete files
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete files",
        )

    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete the file from disk
    if file.original_path:
        upload_path = Path(file.original_path)
        if upload_path.exists():
            upload_path.unlink()

    # Delete from database (cascade will handle related records)
    await db.delete(file)
    await db.commit()


@router.delete("", status_code=status.HTTP_200_OK, response_model=dict)
async def delete_all_files(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: str | None = None,
) -> dict:
    """
    Delete all files from the database (admin only).

    Optionally filter by status (e.g., 'failed' to delete only failed files).
    """
    # Only admins can delete files
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete files",
        )

    # Build query
    query = select(FileModel)
    if status_filter:
        query = query.where(FileModel.status == status_filter)

    result = await db.execute(query)
    files = result.scalars().all()

    deleted_count = 0
    for file in files:
        # Delete the file from disk if it exists
        if file.original_path:
            upload_path = Path(file.original_path)
            if upload_path.exists():
                upload_path.unlink()

        await db.delete(file)
        deleted_count += 1

    await db.commit()

    return {
        "message": f"Deleted {deleted_count} files",
        "deleted_count": deleted_count,
    }


@router.post("/scan", response_model=dict)
async def scan_data_directory(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
) -> dict:
    """
    Start a background scan of the data directory for CSV files.

    Only admins can trigger a scan. Files already in the database are skipped.
    Returns immediately with scan status - poll GET /scan/status for progress.
    """
    global _scan_status

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can scan for files",
        )

    # Check if scan is already running
    if _scan_status.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already in progress. Check GET /api/v1/files/scan/status",
        )

    data_path = get_data_path()
    if not data_path.exists():
        return {
            "message": f"Data directory '{data_path}' does not exist",
            "started": False,
            "total_files": 0,
        }

    # Find all CSV files
    csv_files = list(data_path.glob("*.csv")) + list(data_path.glob("*.CSV"))

    if not csv_files:
        return {
            "message": "No CSV files found in data directory",
            "started": False,
            "total_files": 0,
        }

    # Reset scan status
    _scan_status.is_running = True
    _scan_status.total_files = len(csv_files)
    _scan_status.processed = 0
    _scan_status.imported = 0
    _scan_status.skipped = 0
    _scan_status.failed = 0
    _scan_status.current_file = ""
    _scan_status.imported_files = []
    _scan_status.error = None

    # Start background task
    background_tasks.add_task(_run_background_scan, current_user.id, csv_files)

    return {
        "message": f"Background scan started for {len(csv_files)} files",
        "started": True,
        "total_files": len(csv_files),
        "status_url": "/api/v1/files/scan/status",
    }


@router.get("/scan/status", response_model=dict)
async def get_scan_status(
    current_user: CurrentUser,
) -> dict:
    """
    Get the current status of the background file scan.

    Poll this endpoint to track import progress.
    """
    global _scan_status

    return {
        "is_running": _scan_status.is_running,
        "total_files": _scan_status.total_files,
        "processed": _scan_status.processed,
        "imported": _scan_status.imported,
        "skipped": _scan_status.skipped,
        "failed": _scan_status.failed,
        "current_file": _scan_status.current_file,
        "progress_percent": (
            round(_scan_status.processed / _scan_status.total_files * 100, 1)
            if _scan_status.total_files > 0
            else 0
        ),
        "imported_files": _scan_status.imported_files[-10:],  # Last 10 imported
        "error": _scan_status.error,
    }


@router.get("/watcher/status", response_model=dict)
async def get_watcher_status(
    current_user: CurrentUser,
) -> dict:
    """
    Get the current status of the automatic file watcher.

    The file watcher monitors the data directory for new CSV files
    and automatically ingests them into the database.
    """
    from sleep_scoring_web.services.file_watcher import get_watcher_status as get_status

    return get_status()
