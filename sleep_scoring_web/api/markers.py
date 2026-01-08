"""
Marker API endpoints for sleep and nonwear marker management.

Provides CRUD operations for markers with optimistic update support.

Note: We intentionally avoid `from __future__ import annotations` here
because FastAPI's dependency injection needs actual types, not string
annotations. Using Annotated types requires runtime resolution.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from sleep_scoring_web.api.deps import CurrentUser, DbSession
from sleep_scoring_web.db.models import File as FileModel
from sleep_scoring_web.db.models import Marker, RawActivityData, SleepMetric, UserAnnotation
from sleep_scoring_web.schemas import ManualNonwearPeriod, MarkerResponse, MarkerUpdateRequest, SleepMetrics, SleepPeriod
from sleep_scoring_web.schemas.enums import AlgorithmType, MarkerCategory, MarkerLimits, MarkerType, VerificationStatus

router = APIRouter()


def naive_to_unix(dt: datetime) -> float:
    """Convert naive datetime to Unix timestamp without timezone interpretation."""
    return float(calendar.timegm(dt.timetuple()))


# =============================================================================
# Request/Response Models
# =============================================================================


class OnsetOffsetDataPoint(BaseModel):
    """Single data point for onset/offset tables."""

    timestamp: float
    datetime_str: str
    axis_y: int
    vector_magnitude: int
    algorithm_result: int | None = None  # 0=wake, 1=sleep
    choi_result: int | None = None  # 0=wear, 1=nonwear
    is_nonwear: bool = False  # Manual nonwear marker overlap


class OnsetOffsetTableResponse(BaseModel):
    """Response with data points around a marker for tables."""

    onset_data: list[OnsetOffsetDataPoint] = Field(default_factory=list)
    offset_data: list[OnsetOffsetDataPoint] = Field(default_factory=list)
    period_index: int


class MarkersWithMetricsResponse(BaseModel):
    """Response with markers and their calculated metrics."""

    sleep_markers: list[SleepPeriod] = Field(default_factory=list)
    nonwear_markers: list[ManualNonwearPeriod] = Field(default_factory=list)
    metrics: list[SleepMetrics] = Field(default_factory=list)
    algorithm_results: list[int] | None = None
    verification_status: VerificationStatus = VerificationStatus.DRAFT
    last_modified_at: datetime | None = None
    is_dirty: bool = False  # For optimistic update tracking


class SaveStatusResponse(BaseModel):
    """Response after saving markers."""

    success: bool
    saved_at: datetime
    sleep_marker_count: int
    nonwear_marker_count: int
    message: str = "Markers saved successfully"


# =============================================================================
# Marker CRUD Endpoints
# =============================================================================


@router.get("/{file_id}/{analysis_date}", response_model=MarkersWithMetricsResponse)
async def get_markers(
    file_id: int,
    analysis_date: date,
    db: DbSession,
    current_user: CurrentUser,
    include_algorithm: Annotated[bool, Query(description="Include Sadeh algorithm results")] = True,
) -> MarkersWithMetricsResponse:
    """
    Get all markers for a specific file and date.

    Returns sleep markers, nonwear markers, and calculated metrics.
    Optionally includes algorithm results for overlay display.
    """
    # Verify file exists
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = file_result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Get markers from database
    markers_result = await db.execute(
        select(Marker).where(
            and_(
                Marker.file_id == file_id,
                Marker.analysis_date == analysis_date,
            )
        )
    )
    markers = markers_result.scalars().all()

    # Separate sleep and nonwear markers
    sleep_markers: list[SleepPeriod] = []
    nonwear_markers: list[ManualNonwearPeriod] = []

    for marker in markers:
        if marker.marker_category == MarkerCategory.SLEEP:
            sleep_markers.append(
                SleepPeriod(
                    onset_timestamp=marker.start_timestamp,
                    offset_timestamp=marker.end_timestamp,
                    marker_index=marker.period_index,
                    marker_type=MarkerType(marker.marker_type) if marker.marker_type else MarkerType.MAIN_SLEEP,
                )
            )
        elif marker.marker_category == MarkerCategory.NONWEAR:
            nonwear_markers.append(
                ManualNonwearPeriod(
                    start_timestamp=marker.start_timestamp,
                    end_timestamp=marker.end_timestamp,
                    marker_index=marker.period_index,
                )
            )

    # Get metrics for each sleep period
    metrics_result = await db.execute(
        select(SleepMetric).where(
            and_(
                SleepMetric.file_id == file_id,
                SleepMetric.analysis_date == analysis_date,
            )
        )
    )
    db_metrics = metrics_result.scalars().all()

    metrics: list[SleepMetrics] = []
    for m in db_metrics:
        metrics.append(
            SleepMetrics(
                # Period boundaries
                in_bed_time=m.in_bed_time,
                out_bed_time=m.out_bed_time,
                sleep_onset=m.sleep_onset,
                sleep_offset=m.sleep_offset,
                # Duration metrics
                time_in_bed_minutes=m.time_in_bed_minutes,
                total_sleep_time_minutes=m.total_sleep_time_minutes,
                sleep_onset_latency_minutes=m.sleep_onset_latency_minutes,
                waso_minutes=m.waso_minutes,
                # Awakening metrics
                number_of_awakenings=m.number_of_awakenings,
                average_awakening_length_minutes=m.average_awakening_length_minutes,
                # Quality indices
                sleep_efficiency=m.sleep_efficiency,
                movement_index=m.movement_index,
                fragmentation_index=m.fragmentation_index,
                sleep_fragmentation_index=m.sleep_fragmentation_index,
                # Activity metrics
                total_activity=m.total_activity,
                nonzero_epochs=m.nonzero_epochs,
            )
        )

    # Get algorithm results if requested
    algorithm_results: list[int] | None = None
    if include_algorithm and sleep_markers:
        # Get activity data for the date and run Sadeh
        start_time = datetime.combine(analysis_date, datetime.min.time()) + timedelta(hours=12)
        end_time = start_time + timedelta(hours=24)

        activity_result = await db.execute(
            select(RawActivityData)
            .where(
                and_(
                    RawActivityData.file_id == file_id,
                    RawActivityData.timestamp >= start_time,
                    RawActivityData.timestamp < end_time,
                )
            )
            .order_by(RawActivityData.timestamp)
        )
        activity_rows = activity_result.scalars().all()

        if activity_rows:
            from sleep_scoring_web.services.algorithms.sadeh import SadehAlgorithm

            axis_y_data = [row.axis_y or 0 for row in activity_rows]
            algorithm = SadehAlgorithm()
            algorithm_results = algorithm.score(axis_y_data)

    # Get last modified time
    last_modified = None
    if markers:
        last_modified = max(m.updated_at for m in markers)

    return MarkersWithMetricsResponse(
        sleep_markers=sleep_markers,
        nonwear_markers=nonwear_markers,
        metrics=metrics,
        algorithm_results=algorithm_results,
        verification_status=VerificationStatus.DRAFT,
        last_modified_at=last_modified,
        is_dirty=False,
    )


@router.put("/{file_id}/{analysis_date}", response_model=SaveStatusResponse)
async def save_markers(
    file_id: int,
    analysis_date: date,
    request: MarkerUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> SaveStatusResponse:
    """
    Save markers for a specific file and date.

    Replaces all existing markers for this file/date with the new ones.
    Triggers background calculation of sleep metrics.
    """
    # Verify file exists
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = file_result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Delete existing markers for this file/date
    await db.execute(
        delete(Marker).where(
            and_(
                Marker.file_id == file_id,
                Marker.analysis_date == analysis_date,
            )
        )
    )

    # Insert new sleep markers
    sleep_count = 0
    if request.sleep_markers:
        for i, marker in enumerate(request.sleep_markers):
            if marker.onset_timestamp is not None:
                db_marker = Marker(
                    file_id=file_id,
                    analysis_date=analysis_date,
                    marker_category=MarkerCategory.SLEEP,
                    marker_type=marker.marker_type.value if marker.marker_type else MarkerType.MAIN_SLEEP.value,
                    start_timestamp=marker.onset_timestamp,
                    end_timestamp=marker.offset_timestamp,
                    period_index=marker.marker_index or (i + 1),
                    created_by_id=current_user.id,
                )
                db.add(db_marker)
                sleep_count += 1

    # Insert new nonwear markers
    nonwear_count = 0
    if request.nonwear_markers:
        for i, marker in enumerate(request.nonwear_markers):
            if marker.start_timestamp is not None:
                db_marker = Marker(
                    file_id=file_id,
                    analysis_date=analysis_date,
                    marker_category=MarkerCategory.NONWEAR,
                    marker_type="manual",
                    start_timestamp=marker.start_timestamp,
                    end_timestamp=marker.end_timestamp,
                    period_index=marker.marker_index or (i + 1),
                    created_by_id=current_user.id,
                )
                db.add(db_marker)
                nonwear_count += 1

    await db.commit()

    # Also update user annotation (for consensus tracking)
    background_tasks.add_task(
        _update_user_annotation,
        file_id=file_id,
        analysis_date=analysis_date,
        user_id=current_user.id,
        sleep_markers=request.sleep_markers,
        nonwear_markers=request.nonwear_markers,
        algorithm_used=request.algorithm_used,
        notes=request.notes,
    )

    # Calculate and store metrics in background
    if request.sleep_markers:
        background_tasks.add_task(
            _calculate_and_store_metrics,
            file_id=file_id,
            analysis_date=analysis_date,
            sleep_markers=request.sleep_markers,
            user_id=current_user.id,
        )

    return SaveStatusResponse(
        success=True,
        saved_at=datetime.now(),
        sleep_marker_count=sleep_count,
        nonwear_marker_count=nonwear_count,
    )


@router.delete("/{file_id}/{analysis_date}/{period_index}")
async def delete_marker(
    file_id: int,
    analysis_date: date,
    period_index: int,
    db: DbSession,
    current_user: CurrentUser,
    marker_category: Annotated[MarkerCategory, Query()] = MarkerCategory.SLEEP,
) -> dict[str, Any]:
    """Delete a specific marker period."""
    result = await db.execute(
        delete(Marker).where(
            and_(
                Marker.file_id == file_id,
                Marker.analysis_date == analysis_date,
                Marker.period_index == period_index,
                Marker.marker_category == marker_category,
            )
        )
    )
    await db.commit()

    if result.rowcount == 0:  # type: ignore[union-attr]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marker not found")

    return {"deleted": True, "period_index": period_index}


# =============================================================================
# Data Tables Endpoint (for onset/offset panels)
# =============================================================================


@router.get("/{file_id}/{analysis_date}/table/{period_index}", response_model=OnsetOffsetTableResponse)
async def get_onset_offset_data(
    file_id: int,
    analysis_date: date,
    period_index: int,
    db: DbSession,
    current_user: CurrentUser,
    window_minutes: Annotated[int, Query(ge=5, le=120)] = 100,
) -> OnsetOffsetTableResponse:
    """
    Get activity data around a marker for onset/offset tables.

    Returns data points within window_minutes of the onset and offset timestamps.
    """
    # Get the marker
    marker_result = await db.execute(
        select(Marker).where(
            and_(
                Marker.file_id == file_id,
                Marker.analysis_date == analysis_date,
                Marker.period_index == period_index,
                Marker.marker_category == MarkerCategory.SLEEP,
            )
        )
    )
    marker = marker_result.scalar_one_or_none()

    if not marker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marker not found")

    if marker.start_timestamp is None or marker.end_timestamp is None:
        return OnsetOffsetTableResponse(onset_data=[], offset_data=[], period_index=period_index)

    # Get data around onset
    onset_dt = datetime.fromtimestamp(marker.start_timestamp)
    onset_start = onset_dt - timedelta(minutes=window_minutes)
    onset_end = onset_dt + timedelta(minutes=window_minutes)

    onset_result = await db.execute(
        select(RawActivityData)
        .where(
            and_(
                RawActivityData.file_id == file_id,
                RawActivityData.timestamp >= onset_start,
                RawActivityData.timestamp <= onset_end,
            )
        )
        .order_by(RawActivityData.timestamp)
    )
    onset_rows = onset_result.scalars().all()

    # Get data around offset
    offset_dt = datetime.fromtimestamp(marker.end_timestamp)
    offset_start = offset_dt - timedelta(minutes=window_minutes)
    offset_end = offset_dt + timedelta(minutes=window_minutes)

    offset_result = await db.execute(
        select(RawActivityData)
        .where(
            and_(
                RawActivityData.file_id == file_id,
                RawActivityData.timestamp >= offset_start,
                RawActivityData.timestamp <= offset_end,
            )
        )
        .order_by(RawActivityData.timestamp)
    )
    offset_rows = offset_result.scalars().all()

    # Get nonwear markers to check overlap
    nonwear_result = await db.execute(
        select(Marker).where(
            and_(
                Marker.file_id == file_id,
                Marker.analysis_date == analysis_date,
                Marker.marker_category == MarkerCategory.NONWEAR,
            )
        )
    )
    nonwear_markers = nonwear_result.scalars().all()

    def is_in_nonwear(ts: float) -> bool:
        """Check if timestamp falls within any nonwear marker."""
        for nw in nonwear_markers:
            if nw.start_timestamp and nw.end_timestamp:
                if nw.start_timestamp <= ts <= nw.end_timestamp:
                    return True
        return False

    # Run algorithms on the data ranges
    from sleep_scoring_web.services.algorithms.choi import ChoiNonwearAlgorithm
    from sleep_scoring_web.services.algorithms.sadeh import SadehAlgorithm

    def compute_algorithm_results(rows: list[RawActivityData]) -> tuple[list[int], list[int]]:
        """Compute Sadeh and Choi results for a set of rows."""
        if not rows:
            return [], []

        axis_y_data = [row.axis_y or 0 for row in rows]

        # Sadeh algorithm
        sadeh = SadehAlgorithm()
        sleep_results = sadeh.score(axis_y_data)

        # Choi nonwear detection
        choi = ChoiNonwearAlgorithm()
        choi_results = choi.detect(axis_y_data)

        return sleep_results, choi_results

    onset_sleep, onset_choi = compute_algorithm_results(onset_rows)
    offset_sleep, offset_choi = compute_algorithm_results(offset_rows)

    # Convert to response format with all columns
    onset_data = [
        OnsetOffsetDataPoint(
            timestamp=naive_to_unix(row.timestamp),
            datetime_str=row.timestamp.strftime("%H:%M:%S"),
            axis_y=row.axis_y or 0,
            vector_magnitude=row.vector_magnitude or 0,
            algorithm_result=onset_sleep[i] if i < len(onset_sleep) else None,
            choi_result=onset_choi[i] if i < len(onset_choi) else None,
            is_nonwear=is_in_nonwear(naive_to_unix(row.timestamp)),
        )
        for i, row in enumerate(onset_rows)
    ]

    offset_data = [
        OnsetOffsetDataPoint(
            timestamp=naive_to_unix(row.timestamp),
            datetime_str=row.timestamp.strftime("%H:%M:%S"),
            axis_y=row.axis_y or 0,
            vector_magnitude=row.vector_magnitude or 0,
            algorithm_result=offset_sleep[i] if i < len(offset_sleep) else None,
            choi_result=offset_choi[i] if i < len(offset_choi) else None,
            is_nonwear=is_in_nonwear(naive_to_unix(row.timestamp)),
        )
        for i, row in enumerate(offset_rows)
    ]

    return OnsetOffsetTableResponse(
        onset_data=onset_data,
        offset_data=offset_data,
        period_index=period_index,
    )


class FullTableDataPoint(BaseModel):
    """Single data point for full 48h table."""

    timestamp: float
    datetime_str: str
    axis_y: int
    vector_magnitude: int
    algorithm_result: int | None = None
    choi_result: int | None = None
    is_nonwear: bool = False


class FullTableResponse(BaseModel):
    """Response with full 48h of data for popout table."""

    data: list[FullTableDataPoint] = Field(default_factory=list)
    total_rows: int = 0
    start_time: str | None = None
    end_time: str | None = None


@router.get("/{file_id}/{analysis_date}/table-full", response_model=FullTableResponse)
async def get_full_table_data(
    file_id: int,
    analysis_date: date,
    db: DbSession,
    current_user: CurrentUser,
) -> FullTableResponse:
    """
    Get full 48h of activity data for popout table display.

    Returns all epochs from noon of analysis_date to noon of next day.
    Includes algorithm results and nonwear detection.
    """
    # Verify file exists
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = file_result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Get 24h of data (noon to noon)
    start_time = datetime.combine(analysis_date, datetime.min.time()) + timedelta(hours=12)
    end_time = start_time + timedelta(hours=24)

    activity_result = await db.execute(
        select(RawActivityData)
        .where(
            and_(
                RawActivityData.file_id == file_id,
                RawActivityData.timestamp >= start_time,
                RawActivityData.timestamp < end_time,
            )
        )
        .order_by(RawActivityData.timestamp)
    )
    rows = activity_result.scalars().all()

    if not rows:
        return FullTableResponse(data=[], total_rows=0)

    # Get nonwear markers
    nonwear_result = await db.execute(
        select(Marker).where(
            and_(
                Marker.file_id == file_id,
                Marker.analysis_date == analysis_date,
                Marker.marker_category == MarkerCategory.NONWEAR,
            )
        )
    )
    nonwear_markers = nonwear_result.scalars().all()

    def is_in_nonwear(ts: float) -> bool:
        """Check if timestamp falls within any nonwear marker."""
        for nw in nonwear_markers:
            if nw.start_timestamp and nw.end_timestamp:
                if nw.start_timestamp <= ts <= nw.end_timestamp:
                    return True
        return False

    # Run algorithms on full data
    from sleep_scoring_web.services.algorithms.choi import ChoiNonwearAlgorithm
    from sleep_scoring_web.services.algorithms.sadeh import SadehAlgorithm

    axis_y_data = [row.axis_y or 0 for row in rows]

    sadeh = SadehAlgorithm()
    sleep_results = sadeh.score(axis_y_data)

    choi = ChoiNonwearAlgorithm()
    choi_results = choi.detect(axis_y_data)

    # Convert to response format
    data = [
        FullTableDataPoint(
            timestamp=naive_to_unix(row.timestamp),
            datetime_str=row.timestamp.strftime("%H:%M:%S"),
            axis_y=row.axis_y or 0,
            vector_magnitude=row.vector_magnitude or 0,
            algorithm_result=sleep_results[i] if i < len(sleep_results) else None,
            choi_result=choi_results[i] if i < len(choi_results) else None,
            is_nonwear=is_in_nonwear(naive_to_unix(row.timestamp)),
        )
        for i, row in enumerate(rows)
    ]

    return FullTableResponse(
        data=data,
        total_rows=len(data),
        start_time=rows[0].timestamp.strftime("%Y-%m-%d %H:%M:%S") if rows else None,
        end_time=rows[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S") if rows else None,
    )


# =============================================================================
# Background Tasks
# =============================================================================


async def _update_user_annotation(
    file_id: int,
    analysis_date: date,
    user_id: int,
    sleep_markers: list[SleepPeriod] | None,
    nonwear_markers: list[ManualNonwearPeriod] | None,
    algorithm_used: AlgorithmType | None,
    notes: str | None,
) -> None:
    """Update or create user annotation for consensus tracking."""
    from sleep_scoring_web.db.session import async_session_maker

    async with async_session_maker() as db:
        # Convert markers to dicts
        sleep_json = [m.model_dump() for m in sleep_markers] if sleep_markers else None
        nonwear_json = [m.model_dump() for m in nonwear_markers] if nonwear_markers else None

        # Upsert annotation
        existing = await db.execute(
            select(UserAnnotation).where(
                and_(
                    UserAnnotation.file_id == file_id,
                    UserAnnotation.analysis_date == analysis_date,
                    UserAnnotation.user_id == user_id,
                )
            )
        )
        annotation = existing.scalar_one_or_none()

        if annotation:
            annotation.sleep_markers_json = sleep_json
            annotation.nonwear_markers_json = nonwear_json
            annotation.algorithm_used = algorithm_used.value if algorithm_used else None
            annotation.notes = notes
            annotation.status = "submitted"
        else:
            annotation = UserAnnotation(
                file_id=file_id,
                analysis_date=analysis_date,
                user_id=user_id,
                sleep_markers_json=sleep_json,
                nonwear_markers_json=nonwear_json,
                algorithm_used=algorithm_used.value if algorithm_used else None,
                notes=notes,
                status="submitted",
            )
            db.add(annotation)

        await db.commit()


async def _calculate_and_store_metrics(
    file_id: int,
    analysis_date: date,
    sleep_markers: list[SleepPeriod],
    user_id: int,
) -> None:
    """
    Calculate and store Tudor-Locke sleep metrics for each complete period.

    Uses the TudorLockeSleepMetricsCalculator to compute comprehensive metrics.
    """
    import logging

    from sleep_scoring_web.db.session import async_session_maker
    from sleep_scoring_web.services.metrics import TudorLockeSleepMetricsCalculator

    logger = logging.getLogger(__name__)

    async with async_session_maker() as db:
        # Get activity data for the date
        start_time = datetime.combine(analysis_date, datetime.min.time()) + timedelta(hours=12)
        end_time = start_time + timedelta(hours=24)

        activity_result = await db.execute(
            select(RawActivityData)
            .where(
                and_(
                    RawActivityData.file_id == file_id,
                    RawActivityData.timestamp >= start_time,
                    RawActivityData.timestamp < end_time,
                )
            )
            .order_by(RawActivityData.timestamp)
        )
        activity_rows = activity_result.scalars().all()

        if not activity_rows:
            logger.warning("No activity data found for file %d on %s", file_id, analysis_date)
            return

        # Run Sadeh algorithm to get sleep scores
        from sleep_scoring_web.services.algorithms.sadeh import SadehAlgorithm

        axis_y_data = [row.axis_y or 0 for row in activity_rows]
        timestamps_float = [naive_to_unix(row.timestamp) for row in activity_rows]
        timestamps_dt = [row.timestamp for row in activity_rows]
        algorithm = SadehAlgorithm()
        sleep_scores = algorithm.score(axis_y_data)

        # Delete existing metrics for this file/date
        await db.execute(
            delete(SleepMetric).where(
                and_(
                    SleepMetric.file_id == file_id,
                    SleepMetric.analysis_date == analysis_date,
                )
            )
        )

        # Initialize metrics calculator
        calculator = TudorLockeSleepMetricsCalculator()

        # Calculate metrics for each complete period
        for marker in sleep_markers:
            if not marker.is_complete or marker.onset_timestamp is None or marker.offset_timestamp is None:
                continue

            # Find indices for this period
            onset_idx = None
            offset_idx = None
            for i, ts in enumerate(timestamps_float):
                if onset_idx is None and ts >= marker.onset_timestamp:
                    onset_idx = i
                if ts >= marker.offset_timestamp:
                    offset_idx = i
                    break

            if onset_idx is None or offset_idx is None:
                logger.warning(
                    "Could not find indices for marker period %d (onset=%s, offset=%s)",
                    marker.marker_index,
                    marker.onset_timestamp,
                    marker.offset_timestamp,
                )
                continue

            try:
                # Calculate comprehensive metrics using Tudor-Locke calculator
                metrics = calculator.calculate_metrics(
                    sleep_scores=sleep_scores,
                    activity_counts=[float(x) for x in axis_y_data],
                    onset_idx=onset_idx,
                    offset_idx=offset_idx,
                    timestamps=timestamps_dt,
                )

                sleep_metric = SleepMetric(
                    file_id=file_id,
                    analysis_date=analysis_date,
                    period_index=marker.marker_index,
                    # Period boundaries
                    onset_timestamp=marker.onset_timestamp,
                    offset_timestamp=marker.offset_timestamp,
                    in_bed_time=metrics["in_bed_time"],
                    out_bed_time=metrics["out_bed_time"],
                    sleep_onset=metrics["sleep_onset"],
                    sleep_offset=metrics["sleep_offset"],
                    # Duration metrics
                    time_in_bed_minutes=metrics["time_in_bed_minutes"],
                    total_sleep_time_minutes=metrics["total_sleep_time_minutes"],
                    sleep_onset_latency_minutes=metrics["sleep_onset_latency_minutes"],
                    waso_minutes=metrics["waso_minutes"],
                    # Awakening metrics
                    number_of_awakenings=metrics["number_of_awakenings"],
                    average_awakening_length_minutes=metrics["average_awakening_length_minutes"],
                    # Quality indices
                    sleep_efficiency=metrics["sleep_efficiency"],
                    movement_index=metrics["movement_index"],
                    fragmentation_index=metrics["fragmentation_index"],
                    sleep_fragmentation_index=metrics["sleep_fragmentation_index"],
                    # Activity metrics
                    total_activity=metrics["total_activity"],
                    nonzero_epochs=metrics["nonzero_epochs"],
                    # Algorithm info
                    algorithm_type=AlgorithmType.SADEH_1994_ACTILIFE.value,
                    scored_by_user_id=user_id,
                    verification_status=VerificationStatus.DRAFT.value,
                )
                db.add(sleep_metric)
            except ValueError as e:
                logger.exception("Failed to calculate metrics for period %d: %s", marker.marker_index, e)
                continue

        await db.commit()
