"""
Diary API endpoints for importing and retrieving sleep diary data.
"""

from datetime import date, datetime
from io import StringIO
from typing import Annotated

import polars as pl
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sleep_scoring_web.api.deps import get_current_user, get_db
from sleep_scoring_web.db.models import DiaryEntry, File as FileModel, User


router = APIRouter(prefix="/diary", tags=["diary"])

# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# =============================================================================
# Pydantic Models
# =============================================================================


class DiaryEntryResponse(BaseModel):
    """Response model for a single diary entry."""

    id: int
    file_id: int
    analysis_date: date
    bed_time: str | None = None
    wake_time: str | None = None
    lights_out: str | None = None
    got_up: str | None = None
    sleep_quality: int | None = None
    time_to_fall_asleep_minutes: int | None = None
    number_of_awakenings: int | None = None
    notes: str | None = None

    class Config:
        from_attributes = True


class DiaryEntryCreate(BaseModel):
    """Request model for creating/updating a diary entry."""

    bed_time: str | None = None
    wake_time: str | None = None
    lights_out: str | None = None
    got_up: str | None = None
    sleep_quality: int | None = None
    time_to_fall_asleep_minutes: int | None = None
    number_of_awakenings: int | None = None
    notes: str | None = None


class DiaryUploadResponse(BaseModel):
    """Response after uploading diary CSV."""

    entries_imported: int
    entries_skipped: int
    errors: list[str]


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/{file_id}/{analysis_date}", response_model=DiaryEntryResponse | None)
async def get_diary_entry(
    file_id: int,
    analysis_date: date,
    db: DbSession,
    current_user: CurrentUser,
) -> DiaryEntryResponse | None:
    """
    Get diary entry for a specific file and date.

    Returns None if no diary entry exists for the given file/date.
    """
    result = await db.execute(
        select(DiaryEntry).where(
            and_(
                DiaryEntry.file_id == file_id,
                DiaryEntry.analysis_date == analysis_date,
            )
        )
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        return None

    return DiaryEntryResponse.model_validate(entry)


@router.put("/{file_id}/{analysis_date}", response_model=DiaryEntryResponse)
async def update_diary_entry(
    file_id: int,
    analysis_date: date,
    entry_data: DiaryEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> DiaryEntryResponse:
    """
    Create or update a diary entry for a specific file and date.
    """
    # Verify file exists
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = file_result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Check for existing entry
    result = await db.execute(
        select(DiaryEntry).where(
            and_(
                DiaryEntry.file_id == file_id,
                DiaryEntry.analysis_date == analysis_date,
            )
        )
    )
    entry = result.scalar_one_or_none()

    if entry:
        # Update existing
        for field, value in entry_data.model_dump(exclude_unset=True).items():
            setattr(entry, field, value)
    else:
        # Create new
        entry = DiaryEntry(
            file_id=file_id,
            analysis_date=analysis_date,
            imported_by_id=current_user.id,
            **entry_data.model_dump(),
        )
        db.add(entry)

    await db.commit()
    await db.refresh(entry)

    return DiaryEntryResponse.model_validate(entry)


@router.delete("/{file_id}/{analysis_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary_entry(
    file_id: int,
    analysis_date: date,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a diary entry."""
    result = await db.execute(
        select(DiaryEntry).where(
            and_(
                DiaryEntry.file_id == file_id,
                DiaryEntry.analysis_date == analysis_date,
            )
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary entry not found")

    await db.delete(entry)
    await db.commit()


@router.post("/{file_id}/upload", response_model=DiaryUploadResponse)
async def upload_diary_csv(
    file_id: int,
    file: UploadFile,
    db: DbSession,
    current_user: CurrentUser,
) -> DiaryUploadResponse:
    """
    Upload a diary CSV file to import entries for a specific activity file.

    Expected CSV columns (case-insensitive):
    - date: Analysis date (YYYY-MM-DD or MM/DD/YYYY)
    - bed_time: Time went to bed (HH:MM)
    - wake_time: Time woke up (HH:MM)
    - lights_out: Time lights were turned off (optional)
    - got_up: Time got out of bed (optional)
    - sleep_quality: Quality rating 1-5 or 1-10 (optional)
    - time_to_fall_asleep: Minutes to fall asleep (optional)
    - awakenings: Number of awakenings (optional)
    - notes: Free text notes (optional)
    """
    # Verify file exists
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    db_file = file_result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Read uploaded CSV
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Parse CSV with polars
    try:
        df = pl.read_csv(StringIO(text))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {e}",
        )

    # Normalize column names to lowercase
    df = df.rename({col: col.lower().strip().replace(" ", "_") for col in df.columns})

    # Check for required date column
    date_col = None
    for col in ["date", "analysis_date", "diary_date"]:
        if col in df.columns:
            date_col = col
            break

    if date_col is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must have a 'date' column",
        )

    entries_imported = 0
    entries_skipped = 0
    errors: list[str] = []

    for row in df.iter_rows(named=True):
        try:
            # Parse date
            date_str = str(row[date_col])
            try:
                analysis_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    analysis_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                except ValueError:
                    errors.append(f"Invalid date format: {date_str}")
                    entries_skipped += 1
                    continue

            # Extract fields
            entry_data = {
                "bed_time": _get_time_field(row, ["bed_time", "bedtime", "time_to_bed"]),
                "wake_time": _get_time_field(row, ["wake_time", "waketime", "time_woke"]),
                "lights_out": _get_time_field(row, ["lights_out", "lightsout"]),
                "got_up": _get_time_field(row, ["got_up", "gotup", "out_of_bed"]),
                "sleep_quality": _get_int_field(row, ["sleep_quality", "quality"]),
                "time_to_fall_asleep_minutes": _get_int_field(row, ["time_to_fall_asleep", "sol", "sleep_latency"]),
                "number_of_awakenings": _get_int_field(row, ["awakenings", "number_of_awakenings", "waso_count"]),
                "notes": _get_str_field(row, ["notes", "comments"]),
            }

            # Check for existing entry
            result = await db.execute(
                select(DiaryEntry).where(
                    and_(
                        DiaryEntry.file_id == file_id,
                        DiaryEntry.analysis_date == analysis_date,
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing entry
                for field, value in entry_data.items():
                    if value is not None:
                        setattr(existing, field, value)
            else:
                # Create new entry
                entry = DiaryEntry(
                    file_id=file_id,
                    analysis_date=analysis_date,
                    imported_by_id=current_user.id,
                    **{k: v for k, v in entry_data.items() if v is not None},
                )
                db.add(entry)

            entries_imported += 1

        except Exception as e:
            errors.append(f"Error processing row: {e}")
            entries_skipped += 1

    await db.commit()

    return DiaryUploadResponse(
        entries_imported=entries_imported,
        entries_skipped=entries_skipped,
        errors=errors[:10],  # Limit errors returned
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _get_time_field(row: dict, field_names: list[str]) -> str | None:
    """Extract a time field from row, trying multiple column names."""
    for name in field_names:
        if name in row and row[name] is not None:
            value = str(row[name]).strip()
            if value and value.lower() not in ("", "nan", "none", "null"):
                # Validate time format (HH:MM or HH:MM:SS)
                try:
                    if ":" in value:
                        parts = value.split(":")
                        if len(parts) >= 2:
                            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                except (ValueError, IndexError):
                    pass
                return value
    return None


def _get_int_field(row: dict, field_names: list[str]) -> int | None:
    """Extract an integer field from row, trying multiple column names."""
    for name in field_names:
        if name in row and row[name] is not None:
            try:
                return int(float(row[name]))
            except (ValueError, TypeError):
                pass
    return None


def _get_str_field(row: dict, field_names: list[str]) -> str | None:
    """Extract a string field from row, trying multiple column names."""
    for name in field_names:
        if name in row and row[name] is not None:
            value = str(row[name]).strip()
            if value and value.lower() not in ("nan", "none", "null"):
                return value
    return None
