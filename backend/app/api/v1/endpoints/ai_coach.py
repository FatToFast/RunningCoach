"""AI coach context endpoints."""

from __future__ import annotations

import statistics
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import Activity, ActivityMetric, ActivitySample
from app.models.race import Race
from app.models.user import User
from app.services.ai_snapshot import ensure_ai_training_snapshot, get_multi_period_snapshots

router = APIRouter()
settings = get_settings()


class CoachRaceSummary(BaseModel):
    """Primary or upcoming race summary for AI context."""

    id: int
    name: str
    race_date: date
    days_until: int
    distance_km: float | None
    distance_label: str | None
    location: str | None
    goal_time_seconds: int | None
    goal_description: str | None
    is_primary: bool


class CoachActivitySummary(BaseModel):
    """FIT-derived activity summary for AI context."""

    activity_id: int
    activity_type: str
    name: str | None
    start_time: str
    distance_km: float | None
    duration_min: float | None
    avg_pace_seconds: int | None
    avg_hr: int | None
    max_hr: int | None
    avg_cadence: int | None
    training_effect: float | None
    trimp: float | None
    tss: float | None
    efficiency_factor: float | None
    sample_count: int
    pace_std_seconds: float | None
    hr_std: float | None
    cadence_std: float | None


class CoachContextResponse(BaseModel):
    """AI coach context response with multi-period snapshots."""

    snapshot: dict[str, Any]  # Legacy: 12-week snapshot for backward compatibility
    snapshots: dict[str, dict[str, Any]] | None = None  # New: 6-week, 12-week, all-time snapshots
    primary_race: CoachRaceSummary | None
    activity: CoachActivitySummary | None


def _safe_pstdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return round(float(statistics.pstdev(values)), 2)


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.fmean(values)), 2)


async def _get_primary_race_summary(db: AsyncSession, user_id: int) -> CoachRaceSummary | None:
    today = date.today()

    primary_result = await db.execute(
        select(Race)
        .where(Race.user_id == user_id, Race.is_primary)
        .order_by(Race.race_date.asc())
        .limit(1)
    )
    race = primary_result.scalar_one_or_none()

    if not race or race.race_date < today:
        upcoming_result = await db.execute(
            select(Race)
            .where(Race.user_id == user_id, Race.race_date >= today)
            .order_by(Race.race_date.asc())
            .limit(1)
        )
        race = upcoming_result.scalar_one_or_none()

    if not race:
        return None

    return CoachRaceSummary(
        id=race.id,
        name=race.name,
        race_date=race.race_date,
        days_until=(race.race_date - today).days,
        distance_km=race.distance_km,
        distance_label=race.distance_label,
        location=race.location,
        goal_time_seconds=race.goal_time_seconds,
        goal_description=race.goal_description,
        is_primary=race.is_primary,
    )


async def _get_activity_summary(
    db: AsyncSession,
    user_id: int,
    activity_id: int | None,
) -> CoachActivitySummary | None:
    query = (
        select(Activity)
        .where(Activity.user_id == user_id)
        .options(selectinload(Activity.metrics))
    )

    if activity_id:
        query = query.where(Activity.id == activity_id)
    else:
        query = query.where(Activity.has_fit_file.is_(True)).order_by(Activity.start_time.desc())

    result = await db.execute(query.limit(1))
    activity = result.scalar_one_or_none()

    if not activity and not activity_id:
        fallback_result = await db.execute(
            select(Activity)
            .where(Activity.user_id == user_id)
            .order_by(Activity.start_time.desc())
            .limit(1)
            .options(selectinload(Activity.metrics))
        )
        activity = fallback_result.scalar_one_or_none()

    if not activity:
        return None

    samples_result = await db.execute(
        select(
            ActivitySample.heart_rate,
            ActivitySample.hr,
            ActivitySample.pace_seconds,
            ActivitySample.cadence,
        )
        .where(ActivitySample.activity_id == activity.id)
        .limit(settings.ai_sample_limit)
    )
    rows = samples_result.all()

    pace_values = [row.pace_seconds for row in rows if row.pace_seconds]
    hr_values = [
        (row.heart_rate or row.hr)
        for row in rows
        if (row.heart_rate or row.hr)
    ]
    cadence_values = [row.cadence for row in rows if row.cadence]

    metrics: ActivityMetric | None = activity.metrics
    training_effect = None
    if metrics and metrics.training_effect is not None:
        training_effect = metrics.training_effect
    elif activity.training_effect_aerobic:
        training_effect = activity.training_effect_aerobic
        if activity.training_effect_anaerobic:
            training_effect = (training_effect + activity.training_effect_anaerobic) / 2

    avg_pace_seconds = activity.avg_pace_seconds
    if not avg_pace_seconds and activity.distance_meters and activity.duration_seconds:
        avg_pace_seconds = int((activity.duration_seconds / activity.distance_meters) * 1000)

    return CoachActivitySummary(
        activity_id=activity.id,
        activity_type=activity.activity_type,
        name=activity.name,
        start_time=activity.start_time.isoformat(),
        distance_km=round((activity.distance_meters or 0) / 1000, 2) if activity.distance_meters else None,
        duration_min=round((activity.duration_seconds or 0) / 60, 1) if activity.duration_seconds else None,
        avg_pace_seconds=avg_pace_seconds,
        avg_hr=activity.avg_hr,
        max_hr=activity.max_hr,
        avg_cadence=activity.avg_cadence,
        training_effect=training_effect,
        trimp=metrics.trimp if metrics else None,
        tss=metrics.tss if metrics else None,
        efficiency_factor=metrics.efficiency_factor if metrics else None,
        sample_count=len(rows),
        pace_std_seconds=_safe_pstdev([float(v) for v in pace_values]),
        hr_std=_safe_pstdev([float(v) for v in hr_values]),
        cadence_std=_safe_pstdev([float(v) for v in cadence_values]),
    )


@router.get("/coach/context", response_model=CoachContextResponse)
async def get_ai_coach_context(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    activity_id: int | None = Query(None, description="Activity ID for FIT analysis"),
    multi_period: bool = Query(True, description="Include 6-week, 12-week, all-time snapshots"),
) -> CoachContextResponse:
    """Return AI coach context with multi-period snapshots.

    Args:
        current_user: Authenticated user.
        db: Database session.
        activity_id: Optional activity ID for FIT analysis.
        multi_period: If True, include snapshots for 6 weeks, 12 weeks, and all-time.

    Returns:
        Coach context with snapshots, race info, and activity summary.
    """
    # Generate multi-period snapshots (6 weeks, 12 weeks, all-time)
    if multi_period:
        snapshots = await get_multi_period_snapshots(db, current_user)
        legacy_snapshot = snapshots["recent_12_weeks"]  # Backward compatibility
    else:
        snapshot = await ensure_ai_training_snapshot(db, current_user)
        snapshots = None
        legacy_snapshot = snapshot.payload

    race_summary = await _get_primary_race_summary(db, current_user.id)
    activity_summary = await _get_activity_summary(db, current_user.id, activity_id)

    return CoachContextResponse(
        snapshot=legacy_snapshot,
        snapshots=snapshots,
        primary_race=race_summary,
        activity=activity_summary,
    )
