"""Activity endpoints."""

import math
import os
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import Activity, ActivityMetric, ActivitySample, ActivityLap
from app.models.garmin import GarminRawFile
from app.models.gear import ActivityGear, Gear
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
    """Activity derived metrics - includes both stored metrics and computed values."""

    # From ActivityMetric table
    trimp: float | None = None
    tss: float | None = None
    training_effect: float | None = None
    vo2max_est: float | None = None
    efficiency_factor: float | None = None

    # From Activity table (FIT session data)
    avg_power: int | None = None
    max_power: int | None = None
    normalized_power: int | None = None
    intensity_factor: float | None = None

    # Running dynamics from FIT
    ground_time: int | None = None  # GCT in ms
    vertical_oscillation: float | None = None  # in cm
    stride_length: float | None = None  # in m
    # Note: leg_spring_stiffness and form_power are planned but not yet populated.
    # They require either Stryd pod (form_power) or calculation from GCT/mass (LSS).
    # Keeping in schema for forward compatibility. Always null until implemented.
    leg_spring_stiffness: float | None = None  # in kN/m (requires body weight + GCT)
    form_power: int | None = None  # from Stryd pod (not Garmin)

    # Calculated metrics
    power_to_hr: float | None = None  # Pa:Hr ratio (W/bpm)
    running_effectiveness: float | None = None  # m/kJ

    class Config:
        from_attributes = True


class SensorInfo(BaseModel):
    """Sensor information for an activity."""

    has_power_meter: bool = False
    power_meter_name: str | None = None
    has_hr_monitor: bool = False
    hr_monitor_name: str | None = None
    has_footpod: bool = False
    footpod_name: str | None = None


class ActivityDetailResponse(BaseModel):
    """Full activity detail."""

    id: int
    garmin_id: int
    activity_type: str
    name: str | None
    start_time: datetime
    duration_seconds: int | None
    elapsed_seconds: int | None
    distance_meters: float | None
    calories: int | None

    # Heart rate
    avg_hr: int | None
    max_hr: int | None

    # Pace
    avg_pace_seconds: int | None
    best_pace_seconds: int | None

    # Elevation
    elevation_gain: float | None
    elevation_loss: float | None

    # Cadence
    avg_cadence: int | None
    max_cadence: int | None

    # Training Effect (from Garmin)
    training_effect_aerobic: float | None = None
    training_effect_anaerobic: float | None = None
    vo2max: float | None = None

    # Metrics (combined from Activity and ActivityMetric)
    metrics: ActivityMetricResponse | None

    # Sensor info
    sensors: SensorInfo | None = None

    # File status
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
    sort_by: str = Query("start_time", pattern="^(start_time|distance|duration)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
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

    # Build metrics response with data from both Activity and ActivityMetric
    metrics_response = _build_metrics_response(activity)

    # Build sensor info based on available data
    sensors = _build_sensor_info(activity)

    return ActivityDetailResponse(
        id=activity.id,
        garmin_id=activity.garmin_id,
        activity_type=activity.activity_type,
        name=activity.name,
        start_time=activity.start_time,
        duration_seconds=activity.duration_seconds,
        elapsed_seconds=activity.elapsed_seconds,
        distance_meters=activity.distance_meters,
        calories=activity.calories,
        # Heart rate
        avg_hr=activity.avg_hr,
        max_hr=activity.max_hr,
        # Pace
        avg_pace_seconds=activity.avg_pace_seconds,
        best_pace_seconds=activity.best_pace_seconds,
        # Elevation
        elevation_gain=activity.elevation_gain,
        elevation_loss=activity.elevation_loss,
        # Cadence
        avg_cadence=activity.avg_cadence,
        max_cadence=activity.max_cadence,
        # Training Effect
        training_effect_aerobic=activity.training_effect_aerobic,
        training_effect_anaerobic=activity.training_effect_anaerobic,
        vo2max=activity.vo2max,
        # Metrics
        metrics=metrics_response,
        # Sensors
        sensors=sensors,
        # File status
        has_fit_file=has_fit,
        has_samples=sample_count > 0,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


def _build_metrics_response(activity: Activity) -> ActivityMetricResponse | None:
    """Build metrics response from Activity and ActivityMetric data.

    Combines data from:
    - ActivityMetric table (TRIMP, TSS, etc.)
    - Activity table (power, running dynamics from FIT)
    - Calculated metrics (power-to-HR ratio, etc.)
    """
    # Start with ActivityMetric data if available
    metric_data = {}

    if activity.metrics:
        metric_data = {
            "trimp": activity.metrics.trimp,
            "tss": activity.metrics.tss,
            "training_effect": activity.metrics.training_effect,
            "vo2max_est": activity.metrics.vo2max_est,
            "efficiency_factor": activity.metrics.efficiency_factor,
        }

    # Add power data from Activity (from FIT file)
    metric_data["avg_power"] = activity.avg_power
    metric_data["max_power"] = activity.max_power
    metric_data["normalized_power"] = activity.normalized_power
    metric_data["intensity_factor"] = activity.intensity_factor

    # Add running dynamics from Activity (from FIT file)
    # Note: DB stores values in mm, convert to cm/m for API response
    metric_data["ground_time"] = activity.avg_ground_contact_time  # already in ms
    metric_data["vertical_oscillation"] = (
        round(activity.avg_vertical_oscillation / 10, 1)
        if activity.avg_vertical_oscillation
        else None
    )  # mm -> cm
    metric_data["stride_length"] = (
        round(activity.avg_stride_length / 1000, 2)
        if activity.avg_stride_length
        else None
    )  # mm -> m

    # Stryd metrics (Form Power and Leg Spring Stiffness)
    metric_data["form_power"] = activity.avg_form_power
    metric_data["leg_spring_stiffness"] = activity.avg_leg_spring_stiffness

    # Calculate Power-to-HR ratio if we have both
    if activity.avg_power and activity.avg_hr and activity.avg_hr > 0:
        metric_data["power_to_hr"] = round(activity.avg_power / activity.avg_hr, 2)

    # Calculate Running Effectiveness (m/kJ) if we have power and distance
    if activity.avg_power and activity.distance_meters and activity.duration_seconds:
        # Total energy in kJ = (avg_power * duration) / 1000
        total_energy_kj = (activity.avg_power * activity.duration_seconds) / 1000
        if total_energy_kj > 0:
            # RE = distance in meters / energy in kJ
            metric_data["running_effectiveness"] = round(
                activity.distance_meters / total_energy_kj, 2
            )

    # Use TSS from activity if not in metrics table
    if not metric_data.get("tss") and activity.training_stress_score:
        metric_data["tss"] = activity.training_stress_score

    # Use training effect from activity if not in metrics table
    if not metric_data.get("training_effect") and activity.training_effect_aerobic:
        metric_data["training_effect"] = activity.training_effect_aerobic

    # Check if we have any meaningful data
    has_data = any(v is not None for v in metric_data.values())
    if not has_data:
        return None

    return ActivityMetricResponse(**metric_data)


def _build_sensor_info(activity: Activity) -> SensorInfo:
    """Build sensor info based on FIT file device_info data.

    Sensors are detected from FIT file device_info records:
    - has_stryd: manufacturer == 'stryd'
    - has_external_hr: device_type == 120 (ANT+ HR monitor)
    """
    # Use explicit sensor flags from FIT parsing
    has_stryd = activity.has_stryd
    has_external_hr = activity.has_external_hr

    # Power meter (Stryd)
    power_meter_name = "Stryd" if has_stryd else None

    # HR monitor detection
    has_hr_data = activity.avg_hr is not None and activity.avg_hr > 0
    hr_monitor_name = "HR Monitor" if has_external_hr else None

    # Footpod (Stryd serves as footpod too)
    has_footpod = has_stryd
    footpod_name = "Stryd" if has_stryd else None

    return SensorInfo(
        has_power_meter=has_stryd,
        power_meter_name=power_meter_name,
        has_hr_monitor=has_external_hr,
        hr_monitor_name=hr_monitor_name,
        has_footpod=has_footpod,
        footpod_name=footpod_name,
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

    # Count total samples (always returns full count)
    count_result = await db.execute(
        select(func.count(ActivitySample.id)).where(
            ActivitySample.activity_id == activity_id
        )
    )
    total_count = count_result.scalar() or 0

    # Determine if downsampling is needed
    is_downsampled = False

    if downsample and total_count > downsample:
        # Downsampling mode: evenly sample from full dataset
        # Note: limit/offset are ignored in downsample mode
        is_downsampled = True
        step = total_count // downsample

        # DB-based downsampling using window function (PostgreSQL only)
        # This avoids loading all samples into memory
        from sqlalchemy.sql.expression import func as sql_func

        # Create subquery with row numbers
        row_num = sql_func.row_number().over(
            partition_by=ActivitySample.activity_id,
            order_by=ActivitySample.timestamp.asc()
        ).label("row_num")

        subq = (
            select(ActivitySample, row_num)
            .where(ActivitySample.activity_id == activity_id)
            .subquery()
        )

        # Select every step-th row (row_num % step = 1)
        sample_query = (
            select(subq)
            .where((subq.c.row_num - 1) % step == 0)
            .order_by(subq.c.timestamp.asc())
            .limit(downsample)
        )

        result = await db.execute(sample_query)
        rows = result.all()

        # Convert rows to objects (subquery returns tuples)
        samples = []
        for row in rows:
            sample = ActivitySample(
                id=row.id,
                activity_id=row.activity_id,
                timestamp=row.timestamp,
                elapsed_seconds=row.elapsed_seconds,
                hr=row.hr,
                heart_rate=row.heart_rate,
                pace_seconds=row.pace_seconds,
                speed=row.speed,
                cadence=row.cadence,
                power=row.power,
                latitude=row.latitude,
                longitude=row.longitude,
                altitude=row.altitude,
                distance_meters=row.distance_meters,
                ground_contact_time=row.ground_contact_time,
                vertical_oscillation=row.vertical_oscillation,
                stride_length=row.stride_length,
            )
            samples.append(sample)
    else:
        # Regular pagination mode (downsample not requested or not needed)
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
        total=total_count,  # Always return full count
        is_downsampled=is_downsampled,
        original_count=total_count if is_downsampled else None,
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

    # Validate file path exists before serving
    if not fit_file.file_path or not os.path.isfile(fit_file.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIT file path is invalid or file has been deleted",
        )

    # Path traversal protection: ensure file is within allowed storage directory
    # This prevents serving arbitrary files if DB is compromised
    settings = get_settings()
    allowed_root = os.path.realpath(settings.fit_storage_path)
    file_real_path = os.path.realpath(fit_file.file_path)

    if not file_real_path.startswith(allowed_root + os.sep):
        # Log this as a security warning - possible DB tampering
        import logging
        logging.getLogger(__name__).warning(
            f"Path traversal blocked: {fit_file.file_path} not in {allowed_root}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIT file not found",  # Intentionally vague for security
        )

    return FileResponse(
        path=file_real_path,
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


# -------------------------------------------------------------------------
# HR Zones Endpoint
# -------------------------------------------------------------------------


class HRZoneResponse(BaseModel):
    """HR zone time distribution."""

    zone: int
    name: str
    min_hr: int
    max_hr: int
    time_seconds: int
    percentage: float


class HRZonesResponse(BaseModel):
    """HR zones for an activity."""

    activity_id: int
    max_hr: int
    zones: list[HRZoneResponse]
    total_time_in_zones: int


# Garmin-style HR zone definitions using HRR (Heart Rate Reserve) method
# Zone boundaries are percentages of HRR: resting_hr + (max_hr - resting_hr) * pct
# These percentages match Garmin Connect's default 5-zone calculation
# Derived from user's Garmin settings: max=175, resting=50, HRR=125
# Z1: 88-105 → 30-44%, Z2: 106-122 → 45-58%, Z3: 123-140 → 58-72%, etc.
HR_ZONE_DEFINITIONS = [
    {"zone": 1, "min_pct": 0.304, "max_pct": 0.44},  # Zone 1: ~30-44% HRR
    {"zone": 2, "min_pct": 0.448, "max_pct": 0.576},  # Zone 2: ~45-58% HRR
    {"zone": 3, "min_pct": 0.584, "max_pct": 0.72},  # Zone 3: ~58-72% HRR
    {"zone": 4, "min_pct": 0.728, "max_pct": 0.856},  # Zone 4: ~73-86% HRR
    {"zone": 5, "min_pct": 0.856, "max_pct": 1.00},  # Zone 5: ~86-100% HRR
]


@router.get("/{activity_id}/hr-zones", response_model=HRZonesResponse)
async def get_activity_hr_zones(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    max_hr: int | None = Query(None, ge=100, le=250, description="User's max HR. Default: user.max_hr or 220-age"),
    resting_hr: int | None = Query(None, ge=30, le=100, description="User's resting HR. Default: user.resting_hr or 60"),
) -> HRZonesResponse:
    """Calculate HR zone distribution for an activity.

    FR-013: HR존별 시간 분포

    Uses Garmin-style HRR (Heart Rate Reserve) method:
    Zone HR = resting_hr + (max_hr - resting_hr) * percentage

    Zones are calculated based on percentage of HRR:
    - Zone 1: 50-60% HRR
    - Zone 2: 60-70% HRR
    - Zone 3: 70-80% HRR
    - Zone 4: 80-90% HRR
    - Zone 5: 90-100% HRR

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.
        max_hr: User's max heart rate (optional).
        resting_hr: User's resting heart rate (optional).

    Returns:
        HR zone distribution.
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

    # Get all HR samples with timestamps for accurate time calculation
    # Note: We use timestamp deltas instead of assuming 1 sample = 1 second,
    # as sampling rates can vary (e.g., 1Hz, 5Hz, or irregular intervals)
    result = await db.execute(
        select(ActivitySample.hr, ActivitySample.timestamp)
        .where(
            ActivitySample.activity_id == activity_id,
            ActivitySample.hr.isnot(None),
        )
        .order_by(ActivitySample.timestamp.asc())
    )
    samples = [(row[0], row[1]) for row in result.all() if row[0] and row[1]]

    if not samples:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No HR data available for this activity",
        )

    # Extract HR values for max calculation
    hr_values = [hr for hr, _ in samples]

    # Determine max HR (priority: query param > user.max_hr > max from samples)
    if max_hr is None:
        if current_user.max_hr:
            max_hr = current_user.max_hr
        else:
            # Fallback to max observed HR from this activity
            max_hr = max(hr_values)

    # Determine resting HR (priority: query param > user.resting_hr > default 60)
    if resting_hr is None:
        if current_user.resting_hr:
            resting_hr = current_user.resting_hr
        else:
            # Default resting HR if not set
            resting_hr = 60

    # Calculate HRR (Heart Rate Reserve)
    hrr = max_hr - resting_hr

    # Calculate zone boundaries using HRR method (Karvonen formula)
    # Zone HR = resting_hr + HRR * percentage
    zones = []
    for zone_def in HR_ZONE_DEFINITIONS:
        zone_min = int(resting_hr + hrr * zone_def["min_pct"])
        zone_max = int(resting_hr + hrr * zone_def["max_pct"])
        zones.append({
            "zone": zone_def["zone"],
            "min_hr": zone_min,
            "max_hr": zone_max,
            "count": 0,
        })

    # Calculate time in each zone using timestamp deltas
    # This handles variable sampling rates (1Hz, 5Hz, irregular, etc.)
    for i, (hr, ts) in enumerate(samples):
        # Calculate duration: time until next sample, or 0 for last sample
        if i < len(samples) - 1:
            next_ts = samples[i + 1][1]
            duration_seconds = (next_ts - ts).total_seconds()
            # Cap duration at 60s to handle gaps (e.g., paused activity)
            duration_seconds = min(duration_seconds, 60.0)
        else:
            # Last sample: estimate based on average interval or use 1 second
            if len(samples) > 1:
                total_span = (samples[-1][1] - samples[0][1]).total_seconds()
                avg_interval = total_span / (len(samples) - 1)
                duration_seconds = min(avg_interval, 60.0)
            else:
                duration_seconds = 1.0

        # Assign duration to appropriate zone
        for zone in zones:
            if zone["min_hr"] <= hr < zone["max_hr"]:
                zone["count"] += duration_seconds
                break
        else:
            # Handle values at or above max zone threshold
            if hr >= zones[-1]["max_hr"]:
                zones[-1]["count"] += duration_seconds

    # Calculate percentages and build response
    total_time = sum(z["count"] for z in zones)
    zone_names = ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"]
    zone_responses = []
    for z in zones:
        zone_responses.append(HRZoneResponse(
            zone=z["zone"],
            name=zone_names[z["zone"] - 1],
            min_hr=z["min_hr"],
            max_hr=z["max_hr"],
            time_seconds=int(round(z["count"])),
            percentage=round((z["count"] / total_time * 100) if total_time > 0 else 0, 1),
        ))

    return HRZonesResponse(
        activity_id=activity_id,
        max_hr=max_hr,
        zones=zone_responses,
        total_time_in_zones=int(round(total_time)),
    )


# -------------------------------------------------------------------------
# Laps Endpoint
# -------------------------------------------------------------------------


class LapResponse(BaseModel):
    """Activity lap/segment data."""

    lap_number: int
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    distance_meters: float | None
    avg_hr: int | None
    max_hr: int | None
    avg_pace_seconds: int | None
    elevation_gain: float | None
    avg_cadence: int | None


class LapsResponse(BaseModel):
    """Laps for an activity."""

    activity_id: int
    laps: list[LapResponse]
    total_laps: int


@router.get("/{activity_id}/laps", response_model=LapsResponse)
async def get_activity_laps(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    split_distance: int = Query(1000, ge=100, le=10000, description="Split distance in meters (default: 1km)"),
) -> LapsResponse:
    """Get lap/split data for an activity.

    FR-014: 랩/구간 데이터

    Returns laps from FIT file if available, otherwise calculates splits
    based on distance or time.

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.
        split_distance: Distance per lap in meters for calculated splits (default: 1000m = 1km).

    Returns:
        Lap data for the activity.
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

    # First, try to get laps from FIT file (stored in ActivityLap table)
    fit_laps_result = await db.execute(
        select(ActivityLap)
        .where(ActivityLap.activity_id == activity_id)
        .order_by(ActivityLap.lap_number.asc())
    )
    fit_laps = fit_laps_result.scalars().all()

    if fit_laps:
        # Use FIT laps directly
        laps = []
        for lap in fit_laps:
            # Calculate proper end_time even when start_time is missing
            lap_start = lap.start_time or activity.start_time
            lap_duration = int(lap.duration_seconds or 0)
            lap_end = lap_start + timedelta(seconds=lap_duration) if lap_duration > 0 else lap_start

            # Calculate pace if not stored (e.g., track running without GPS speed)
            avg_pace = lap.avg_pace_seconds
            if avg_pace is None and lap.distance_meters and lap.duration_seconds:
                if lap.distance_meters > 0:
                    avg_pace = int(lap.duration_seconds / (lap.distance_meters / 1000))

            laps.append(LapResponse(
                lap_number=lap.lap_number,
                start_time=lap_start,
                end_time=lap_end,
                duration_seconds=int(lap.duration_seconds or 0),
                distance_meters=lap.distance_meters,
                avg_hr=lap.avg_hr,
                max_hr=lap.max_hr,
                avg_pace_seconds=avg_pace,
                elevation_gain=lap.total_ascent_meters,
                avg_cadence=lap.avg_cadence,
            ))
        return LapsResponse(
            activity_id=activity_id,
            laps=laps,
            total_laps=len(laps),
        )

    # Fallback: Calculate laps from samples
    result = await db.execute(
        select(ActivitySample)
        .where(ActivitySample.activity_id == activity_id)
        .order_by(ActivitySample.timestamp.asc())
    )
    samples = result.scalars().all()

    if not samples:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No lap or sample data available for this activity",
        )

    # Calculate cumulative distance (if GPS data available)
    # Note: Using "is not None" to properly handle 0.0 coordinates (equator/prime meridian)
    has_gps = any(s.latitude is not None and s.longitude is not None for s in samples)

    laps: list[LapResponse] = []

    if has_gps and activity.distance_meters:
        # Distance-based splits
        total_distance = activity.distance_meters
        num_full_laps = int(total_distance // split_distance)

        # Group samples by lap
        current_lap_samples: list = []
        current_distance = 0.0
        lap_number = 1
        prev_sample = None

        for sample in samples:
            # Use "is not None" to handle 0.0 coordinates (equator/prime meridian)
            if (prev_sample and
                sample.latitude is not None and sample.longitude is not None and
                prev_sample.latitude is not None and prev_sample.longitude is not None):
                # Calculate distance between points (simplified haversine)
                lat1, lon1 = math.radians(prev_sample.latitude), math.radians(prev_sample.longitude)
                lat2, lon2 = math.radians(sample.latitude), math.radians(sample.longitude)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                distance = 6371000 * c  # Earth radius in meters
                current_distance += distance

            current_lap_samples.append(sample)
            prev_sample = sample

            # Check if we've completed a lap
            if current_distance >= split_distance and current_lap_samples:
                lap = _calculate_lap_stats(lap_number, current_lap_samples)
                laps.append(lap)
                lap_number += 1
                current_lap_samples = []
                current_distance = current_distance - split_distance

        # Add remaining samples as final lap
        if current_lap_samples:
            lap = _calculate_lap_stats(lap_number, current_lap_samples)
            laps.append(lap)
    else:
        # Time-based splits (every 5 minutes)
        time_split_seconds = 300  # 5 minutes
        current_lap_samples = []
        lap_number = 1
        lap_start_time = samples[0].timestamp

        for sample in samples:
            current_lap_samples.append(sample)
            elapsed = (sample.timestamp - lap_start_time).total_seconds()

            if elapsed >= time_split_seconds:
                lap = _calculate_lap_stats(lap_number, current_lap_samples)
                laps.append(lap)
                lap_number += 1
                current_lap_samples = []
                lap_start_time = sample.timestamp

        # Add remaining samples
        if current_lap_samples:
            lap = _calculate_lap_stats(lap_number, current_lap_samples)
            laps.append(lap)

    return LapsResponse(
        activity_id=activity_id,
        laps=laps,
        total_laps=len(laps),
    )


def _calculate_lap_stats(lap_number: int, samples: list) -> LapResponse:
    """Calculate statistics for a lap from samples.

    Args:
        lap_number: Lap number.
        samples: List of ActivitySample objects.

    Returns:
        LapResponse with calculated stats.
    """
    if not samples:
        raise ValueError("No samples provided for lap calculation")

    start_time = samples[0].timestamp
    end_time = samples[-1].timestamp
    duration = int((end_time - start_time).total_seconds())

    # HR stats
    hr_values = [s.hr for s in samples if s.hr is not None]
    avg_hr = int(sum(hr_values) / len(hr_values)) if hr_values else None
    max_hr = max(hr_values) if hr_values else None

    # Pace stats
    pace_values = [s.pace_seconds for s in samples if s.pace_seconds is not None]
    avg_pace = int(sum(pace_values) / len(pace_values)) if pace_values else None

    # Cadence stats
    cadence_values = [s.cadence for s in samples if s.cadence is not None]
    avg_cadence = int(sum(cadence_values) / len(cadence_values)) if cadence_values else None

    # Elevation (simple difference between first and last with altitude)
    altitude_values = [s.altitude for s in samples if s.altitude is not None]
    elevation_gain = None
    if len(altitude_values) >= 2:
        gain = 0.0
        for i in range(1, len(altitude_values)):
            diff = altitude_values[i] - altitude_values[i-1]
            if diff > 0:
                gain += diff
        elevation_gain = round(gain, 1)

    # Distance (estimate from pace and time if available)
    distance = None
    if avg_pace and duration > 0:
        # pace_seconds is seconds per km
        # distance = duration / (pace_seconds / 1000) = duration * 1000 / pace_seconds
        distance = round(duration * 1000 / avg_pace, 1)

    return LapResponse(
        lap_number=lap_number,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration,
        distance_meters=distance,
        avg_hr=avg_hr,
        max_hr=max_hr,
        avg_pace_seconds=avg_pace,
        elevation_gain=elevation_gain,
        avg_cadence=avg_cadence,
    )


# -------------------------------------------------------------------------
# Activity Gear Endpoint
# -------------------------------------------------------------------------


class ActivityGearResponse(BaseModel):
    """Gear linked to an activity."""

    id: int
    name: str
    brand: str | None
    gear_type: str
    status: str
    total_distance_meters: float | None = None
    max_distance_meters: float | None = None
    usage_percentage: float | None = None

    class Config:
        from_attributes = True


class ActivityGearsResponse(BaseModel):
    """List of gear linked to an activity."""

    activity_id: int
    gears: list[ActivityGearResponse]
    total: int


@router.get("/{activity_id}/gear", response_model=ActivityGearsResponse)
async def get_activity_gear(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ActivityGearsResponse:
    """Get gear linked to an activity.

    This endpoint is used by the frontend to display which gear was used
    for a specific activity.

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        List of gear linked to the activity.
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

    # Get linked gear
    result = await db.execute(
        select(Gear)
        .join(ActivityGear, ActivityGear.gear_id == Gear.id)
        .where(ActivityGear.activity_id == activity_id)
        .order_by(Gear.name.asc())
    )
    gears = result.scalars().all()

    gear_responses = []
    for g in gears:
        # Calculate total distance (Garmin's tracked + local activities if any)
        total_distance = g.initial_distance_meters or 0
        max_distance = g.max_distance_meters or 800000  # Default 800km for shoes

        # Calculate usage percentage
        usage_pct = (total_distance / max_distance * 100) if max_distance > 0 else 0

        gear_responses.append(
            ActivityGearResponse(
                id=g.id,
                name=g.name,
                brand=g.brand,
                gear_type=g.gear_type,
                status=g.status,
                total_distance_meters=total_distance,
                max_distance_meters=max_distance,
                usage_percentage=min(usage_pct, 100),
            )
        )

    return ActivityGearsResponse(
        activity_id=activity_id,
        gears=gear_responses,
        total=len(gears),
    )


# -------------------------------------------------------------------------
# Re-parse FIT File (Development/Testing)
# -------------------------------------------------------------------------


class ReparseResponse(BaseModel):
    """Response for FIT file reparse."""

    activity_id: int
    message: str
    updated_fields: list[str]


@router.post("/{activity_id}/reparse-fit", response_model=ReparseResponse)
async def reparse_fit_file(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ReparseResponse:
    """Re-parse existing FIT file to update activity with new fields.

    This endpoint re-parses the stored FIT file and updates the activity
    with any newly added fields (e.g., Stryd metrics like LSS, Form Power).

    Useful during development when new fields are added to the parser.

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated fields summary.
    """
    import logging
    from pathlib import Path

    from app.adapters.garmin_adapter import GarminConnectAdapter

    logger = logging.getLogger(__name__)

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

    # Get FIT file path
    if not activity.fit_file_path or not os.path.isfile(activity.fit_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIT file not found for this activity",
        )

    # Read and parse FIT file
    try:
        with open(activity.fit_file_path, "rb") as f:
            fit_data = f.read()

        adapter = GarminConnectAdapter()  # Credentials not needed for parsing
        parsed_data = adapter.parse_fit_file(fit_data)

        updated_fields = []

        # Update Stryd metrics
        sensors = parsed_data.get("sensors", {})
        records = parsed_data.get("records", [])

        if sensors.get("has_stryd"):
            activity.has_stryd = True
            updated_fields.append("has_stryd")

            # Calculate Stryd averages from records
            form_powers = [r["form_power"] for r in records if r.get("form_power")]
            lss_values = [r["leg_spring_stiffness"] for r in records if r.get("leg_spring_stiffness")]

            if form_powers:
                activity.avg_form_power = int(sum(form_powers) / len(form_powers))
                updated_fields.append(f"avg_form_power={activity.avg_form_power}")
                logger.info(f"Activity {activity_id}: Avg Form Power = {activity.avg_form_power}W")

            if lss_values:
                activity.avg_leg_spring_stiffness = round(sum(lss_values) / len(lss_values), 2)
                updated_fields.append(f"avg_leg_spring_stiffness={activity.avg_leg_spring_stiffness}")
                logger.info(f"Activity {activity_id}: Avg LSS = {activity.avg_leg_spring_stiffness} kN/m")

        # Update session-level data
        session_data = parsed_data.get("session", {})
        if session_data:
            if session_data.get("avg_ground_contact_time") and not activity.avg_ground_contact_time:
                activity.avg_ground_contact_time = int(session_data["avg_ground_contact_time"])
                updated_fields.append(f"avg_ground_contact_time={activity.avg_ground_contact_time}")

            if session_data.get("avg_vertical_oscillation") and not activity.avg_vertical_oscillation:
                activity.avg_vertical_oscillation = session_data["avg_vertical_oscillation"]
                updated_fields.append(f"avg_vertical_oscillation={activity.avg_vertical_oscillation}")

        await db.commit()

        return ReparseResponse(
            activity_id=activity_id,
            message=f"Successfully re-parsed FIT file. Updated {len(updated_fields)} fields.",
            updated_fields=updated_fields,
        )

    except Exception as e:
        logger.error(f"Failed to reparse FIT file for activity {activity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse FIT file: {str(e)}",
        )
