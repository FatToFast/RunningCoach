"""Activity endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.activity import Activity, ActivityMetric, ActivitySample
from app.models.garmin import GarminRawFile
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class ActivitySummary(BaseModel):
    """Activity summary for list view."""

    id: int
    garmin_id: int
    activity_type: str
    name: str | None
    start_time: datetime
    duration_seconds: int | None
    distance_meters: float | None
    avg_hr: int | None
    avg_pace_seconds: int | None
    calories: int | None

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    """Paginated activity list."""

    items: list[ActivitySummary]
    total: int
    page: int
    per_page: int


class ActivityMetricResponse(BaseModel):
    """Activity derived metrics."""

    trimp: float | None
    tss: float | None
    training_effect: float | None
    vo2max_est: float | None
    efficiency_factor: float | None

    class Config:
        from_attributes = True


class ActivityDetailResponse(BaseModel):
    """Full activity detail."""

    id: int
    garmin_id: int
    activity_type: str
    name: str | None
    start_time: datetime
    duration_seconds: int | None
    distance_meters: float | None
    calories: int | None
    avg_hr: int | None
    max_hr: int | None
    avg_pace_seconds: int | None
    elevation_gain: float | None
    elevation_loss: float | None
    avg_cadence: int | None
    metrics: ActivityMetricResponse | None
    has_fit_file: bool
    has_samples: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SampleResponse(BaseModel):
    """Activity sample data point."""

    timestamp: datetime
    hr: int | None
    pace_seconds: int | None
    cadence: int | None
    power: int | None
    latitude: float | None
    longitude: float | None
    altitude: float | None

    class Config:
        from_attributes = True


class SamplesListResponse(BaseModel):
    """List of activity samples."""

    activity_id: int
    samples: list[SampleResponse]
    total: int
    is_downsampled: bool = False
    original_count: int | None = None


# -------------------------------------------------------------------------
# List and Detail Endpoints
# -------------------------------------------------------------------------


@router.get("", response_model=ActivityListResponse)
async def list_activities(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    activity_type: str | None = Query(None, description="Filter by activity type"),
    start_date: datetime | None = Query(None, description="Filter start date (from)"),
    end_date: datetime | None = Query(None, description="Filter end date (to)"),
    sort_by: str = Query("start_time", regex="^(start_time|distance|duration)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
) -> ActivityListResponse:
    """List activities with filtering and pagination.

    FR-011: 활동 목록 - 페이지네이션, 필터, 정렬

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        activity_type: Filter by type.
        start_date: Filter from date.
        end_date: Filter to date.
        sort_by: Sort field.
        sort_order: Sort order.

    Returns:
        Paginated activity list.
    """
    # Base query
    query = select(Activity).where(Activity.user_id == current_user.id)

    # Apply filters
    if activity_type:
        query = query.where(Activity.activity_type == activity_type)
    if start_date:
        query = query.where(Activity.start_time >= start_date)
    if end_date:
        query = query.where(Activity.start_time <= end_date)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = {
        "start_time": Activity.start_time,
        "distance": Activity.distance_meters,
        "duration": Activity.duration_seconds,
    }[sort_by]

    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    activities = result.scalars().all()

    return ActivityListResponse(
        items=[ActivitySummary.model_validate(a) for a in activities],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{activity_id}", response_model=ActivityDetailResponse)
async def get_activity(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ActivityDetailResponse:
    """Get activity detail.

    FR-012: 활동 상세

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Activity detail.
    """
    result = await db.execute(
        select(Activity)
        .where(
            Activity.id == activity_id,
            Activity.user_id == current_user.id,
        )
        .options(selectinload(Activity.metrics))
    )
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Check for FIT file
    fit_result = await db.execute(
        select(GarminRawFile).where(GarminRawFile.activity_id == activity_id)
    )
    has_fit = fit_result.scalar_one_or_none() is not None

    # Check for samples
    sample_result = await db.execute(
        select(func.count(ActivitySample.id)).where(
            ActivitySample.activity_id == activity_id
        )
    )
    sample_count = sample_result.scalar() or 0

    return ActivityDetailResponse(
        id=activity.id,
        garmin_id=activity.garmin_id,
        activity_type=activity.activity_type,
        name=activity.name,
        start_time=activity.start_time,
        duration_seconds=activity.duration_seconds,
        distance_meters=activity.distance_meters,
        calories=activity.calories,
        avg_hr=activity.avg_hr,
        max_hr=activity.max_hr,
        avg_pace_seconds=activity.avg_pace_seconds,
        elevation_gain=activity.elevation_gain,
        elevation_loss=activity.elevation_loss,
        avg_cadence=activity.avg_cadence,
        metrics=ActivityMetricResponse.model_validate(activity.metrics)
        if activity.metrics
        else None,
        has_fit_file=has_fit,
        has_samples=sample_count > 0,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# -------------------------------------------------------------------------
# Samples Endpoint
# -------------------------------------------------------------------------


@router.get("/{activity_id}/samples", response_model=SamplesListResponse)
async def get_activity_samples(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    downsample: int | None = Query(
        None,
        ge=50,
        le=2000,
        description="Target number of samples. If total > this, downsample evenly.",
    ),
    fields: str | None = Query(
        None,
        description="Comma-separated fields to include (hr,pace,cadence,power,gps,altitude). Default: all.",
    ),
) -> SamplesListResponse:
    """Get activity time-series samples with optional downsampling.

    차트 성능 최적화를 위한 다운샘플링 지원:
    - downsample=200: 총 샘플 수가 200개를 초과하면 균등하게 200개로 축소
    - fields=hr,pace: HR과 페이스 데이터만 반환 (GPS 제외로 응답 크기 감소)

    Examples:
        GET /activities/123/samples → 전체 샘플 (최대 1000개)
        GET /activities/123/samples?downsample=200 → 200개로 다운샘플링
        GET /activities/123/samples?fields=hr,pace → HR/페이스만
        GET /activities/123/samples?downsample=300&fields=hr,gps → 300개, HR+GPS만

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.
        limit: Max samples to return (before downsampling).
        offset: Offset for pagination.
        downsample: Target sample count for downsampling.
        fields: Comma-separated field filter.

    Returns:
        Activity samples (optionally downsampled).
    """
    # Verify ownership
    activity_result = await db.execute(
        select(Activity).where(
            Activity.id == activity_id,
            Activity.user_id == current_user.id,
        )
    )
    if not activity_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Count total
    count_result = await db.execute(
        select(func.count(ActivitySample.id)).where(
            ActivitySample.activity_id == activity_id
        )
    )
    total = count_result.scalar() or 0

    # Determine if downsampling is needed
    is_downsampled = False
    original_count = None

    if downsample and total > downsample:
        # Calculate step for even sampling
        step = total // downsample
        is_downsampled = True
        original_count = total

        # Use ROW_NUMBER for even distribution (PostgreSQL)
        # For SQLite compatibility, we'll use a simpler approach
        result = await db.execute(
            select(ActivitySample)
            .where(ActivitySample.activity_id == activity_id)
            .order_by(ActivitySample.timestamp.asc())
        )
        all_samples = result.scalars().all()

        # Evenly pick samples
        samples = [all_samples[i] for i in range(0, len(all_samples), step)][:downsample]
    else:
        # Regular pagination
        result = await db.execute(
            select(ActivitySample)
            .where(ActivitySample.activity_id == activity_id)
            .order_by(ActivitySample.timestamp.asc())
            .offset(offset)
            .limit(limit)
        )
        samples = result.scalars().all()

    # Parse field filter
    include_fields = None
    if fields:
        include_fields = set(f.strip().lower() for f in fields.split(","))

    # Build response with optional field filtering
    sample_responses = []
    for s in samples:
        sample_data = SampleResponse(
            timestamp=s.timestamp,
            hr=s.hr if not include_fields or "hr" in include_fields else None,
            pace_seconds=s.pace_seconds if not include_fields or "pace" in include_fields else None,
            cadence=s.cadence if not include_fields or "cadence" in include_fields else None,
            power=s.power if not include_fields or "power" in include_fields else None,
            latitude=s.latitude if not include_fields or "gps" in include_fields else None,
            longitude=s.longitude if not include_fields or "gps" in include_fields else None,
            altitude=s.altitude if not include_fields or "altitude" in include_fields else None,
        )
        sample_responses.append(sample_data)

    return SamplesListResponse(
        activity_id=activity_id,
        samples=sample_responses,
        total=len(sample_responses),
        is_downsampled=is_downsampled,
        original_count=original_count,
    )


# -------------------------------------------------------------------------
# FIT File Download
# -------------------------------------------------------------------------


@router.get("/{activity_id}/fit")
async def download_fit_file(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download original FIT file for activity.

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        FIT file download.
    """
    # Verify ownership
    activity_result = await db.execute(
        select(Activity).where(
            Activity.id == activity_id,
            Activity.user_id == current_user.id,
        )
    )
    activity = activity_result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Get FIT file
    fit_result = await db.execute(
        select(GarminRawFile).where(GarminRawFile.activity_id == activity_id)
    )
    fit_file = fit_result.scalar_one_or_none()

    if not fit_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIT file not found for this activity",
        )

    return FileResponse(
        path=fit_file.file_path,
        filename=f"activity_{activity.garmin_id}.fit",
        media_type="application/octet-stream",
    )


# -------------------------------------------------------------------------
# Activity Types
# -------------------------------------------------------------------------


@router.get("/types/list")
async def list_activity_types(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """List all activity types for the user.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        List of activity types.
    """
    result = await db.execute(
        select(Activity.activity_type)
        .where(Activity.user_id == current_user.id)
        .distinct()
    )
    return [row[0] for row in result.all()]
