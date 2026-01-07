"""AI training snapshot generation service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Activity, AITrainingSnapshot, GarminSyncState, HRRecord, Sleep
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

SNAPSHOT_SCHEMA_VERSION = 1
RECENT_ACTIVITY_LIMIT = 10

# Use config values with fallback to sensible defaults
SNAPSHOT_WEEKS = settings.ai_snapshot_weeks
RECOVERY_DAYS = settings.ai_snapshot_recovery_days
DEFAULT_INTERVAL_CUTOFF = settings.ai_default_interval_pace  # 4:30/km default
DEFAULT_TEMPO_CUTOFF = settings.ai_default_tempo_pace  # 5:00/km default

# Earliest possible date for "all-time" queries (GPS running watches became mainstream around 2006)
# This serves as a safe lower bound that captures all realistic user data
ALL_TIME_START_YEAR = 2006


def _parse_pace(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            parts = value.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            return int(value)
        except ValueError:
            return None
    return None


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    index = int(round((len(values) - 1) * percentile))
    return values[index]


async def _fetch_runalyze_training_paces() -> dict[str, Any] | None:
    if not settings.runalyze_api_token:
        return None

    base_url = settings.runalyze_api_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            headers={"token": settings.runalyze_api_token},
            timeout=10.0,
        ) as client:
            for endpoint in ("metrics/paces", "training/paces", "paces"):
                response = await client.get(endpoint)
                if response.status_code != 200:
                    continue
                data = response.json()
                if not data:
                    continue
                paces = data[0] if isinstance(data, list) else data
                if paces.get("vdot"):
                    return paces
    except Exception as exc:
        logger.debug("Runalyze training paces fetch failed: %s", exc)

    return None


async def _resolve_pace_profile(pace_values: list[int]) -> tuple[int, int, str]:
    paces = await _fetch_runalyze_training_paces()
    if paces:
        easy_min = _parse_pace(paces.get("easy_min"))
        marathon_max = _parse_pace(paces.get("marathon_max"))
        threshold_max = _parse_pace(paces.get("threshold_max"))
        interval_max = _parse_pace(paces.get("interval_max"))

        tempo_cutoff = easy_min or marathon_max or threshold_max
        interval_cutoff = interval_max or threshold_max or marathon_max or easy_min

        if tempo_cutoff and interval_cutoff:
            if tempo_cutoff <= interval_cutoff:
                tempo_cutoff = interval_cutoff + 10
            return interval_cutoff, tempo_cutoff, "runalyze"

    if len(pace_values) >= 5:
        interval_cutoff = _percentile(pace_values, 0.2) or DEFAULT_INTERVAL_CUTOFF
        tempo_cutoff = _percentile(pace_values, 0.6) or DEFAULT_TEMPO_CUTOFF
        if tempo_cutoff <= interval_cutoff:
            tempo_cutoff = interval_cutoff + 10
        return interval_cutoff, tempo_cutoff, "activity_percentile"

    return DEFAULT_INTERVAL_CUTOFF, DEFAULT_TEMPO_CUTOFF, "heuristic"


def _calculate_pace_seconds(activity: Activity) -> int | None:
    if activity.avg_pace_seconds and activity.avg_pace_seconds > 0:
        return int(activity.avg_pace_seconds)
    if activity.distance_meters and activity.duration_seconds:
        if activity.distance_meters > 0 and activity.duration_seconds > 0:
            return int((activity.duration_seconds / activity.distance_meters) * 1000)
    return None


async def _get_last_sync_at(db: AsyncSession, user_id: int) -> datetime | None:
    result = await db.execute(
        select(func.max(GarminSyncState.last_success_at)).where(
            GarminSyncState.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def _build_snapshot_payload(
    db: AsyncSession,
    user: User,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    activity_result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == user.id,
            Activity.start_time >= window_start,
            Activity.start_time <= window_end,
        )
        .order_by(Activity.start_time.desc())
    )
    activities = activity_result.scalars().all()

    total_distance_m = sum(a.distance_meters or 0 for a in activities)
    total_duration_s = sum(a.duration_seconds or 0 for a in activities)
    total_activities = len(activities)
    long_run_max_m = max((a.distance_meters or 0 for a in activities), default=0)

    active_dates = {a.start_time.date() for a in activities if a.start_time}
    window_days = (window_end.date() - window_start.date()).days + 1
    coverage_pct = round(len(active_dates) / window_days, 2) if window_days > 0 else 0.0

    pace_values = []
    for activity in activities:
        pace_sec = _calculate_pace_seconds(activity)
        if pace_sec:
            pace_values.append(pace_sec)

    interval_cutoff, tempo_cutoff, pace_source = await _resolve_pace_profile(pace_values)

    easy_m = tempo_m = interval_m = 0.0
    for activity in activities:
        pace_sec = _calculate_pace_seconds(activity)
        distance_m = activity.distance_meters or 0
        if not pace_sec or distance_m <= 0:
            continue
        if pace_sec <= interval_cutoff:
            interval_m += distance_m
        elif pace_sec <= tempo_cutoff:
            tempo_m += distance_m
        else:
            easy_m += distance_m

    total_zone_m = easy_m + tempo_m + interval_m
    if total_zone_m > 0:
        easy_pct = round(easy_m / total_zone_m * 100, 1)
        tempo_pct = round(tempo_m / total_zone_m * 100, 1)
        interval_pct = round(interval_m / total_zone_m * 100, 1)
    else:
        easy_pct = tempo_pct = interval_pct = 0.0

    recent_activities = []
    for activity in activities[:RECENT_ACTIVITY_LIMIT]:
        recent_activities.append(
            {
                "date": activity.start_time.date().isoformat() if activity.start_time else None,
                "type": activity.activity_type,
                "distance_km": round((activity.distance_meters or 0) / 1000, 2),
                "duration_min": round((activity.duration_seconds or 0) / 60, 1),
                "avg_pace_sec": _calculate_pace_seconds(activity),
            }
        )

    recovery_start = window_end.date() - timedelta(days=RECOVERY_DAYS - 1)
    sleep_result = await db.execute(
        select(func.avg(Sleep.duration_seconds), func.avg(Sleep.score))
        .where(
            Sleep.user_id == user.id,
            Sleep.date >= recovery_start,
            Sleep.date <= window_end.date(),
        )
    )
    sleep_avg_seconds, sleep_avg_score = sleep_result.one()

    hr_result = await db.execute(
        select(func.avg(HRRecord.resting_hr))
        .where(
            HRRecord.user_id == user.id,
            HRRecord.date >= recovery_start,
            HRRecord.date <= window_end.date(),
        )
    )
    resting_hr = hr_result.scalar_one_or_none()

    missing_hr_count = sum(1 for a in activities if not (a.avg_hr and a.avg_hr > 0))
    missing_hr_pct = round(missing_hr_count / total_activities * 100, 1) if total_activities else 0.0

    payload = {
        "window": {
            "start": window_start.date().isoformat(),
            "end": window_end.date().isoformat(),
            "coverage_pct": coverage_pct,
        },
        "load": {
            "weekly_km_avg": round(total_distance_m / 1000 / SNAPSHOT_WEEKS, 1) if total_distance_m else 0.0,
            "weekly_hours_avg": round(total_duration_s / 3600 / SNAPSHOT_WEEKS, 1) if total_duration_s else 0.0,
            "sessions_avg": round(total_activities / SNAPSHOT_WEEKS, 1) if total_activities else 0.0,
            "long_run_max_km": round(long_run_max_m / 1000, 1) if long_run_max_m else 0.0,
            "total_distance_km": round(total_distance_m / 1000, 1) if total_distance_m else 0.0,
        },
        "distribution_distance": {
            "easy_km": round(easy_m / 1000, 1),
            "tempo_km": round(tempo_m / 1000, 1),
            "interval_km": round(interval_m / 1000, 1),
            "easy_pct": easy_pct,
            "tempo_pct": tempo_pct,
            "interval_pct": interval_pct,
        },
        "pace_profile": {
            "interval_cutoff": interval_cutoff,
            "tempo_cutoff": tempo_cutoff,
            "source": pace_source,
        },
        "recent_activities": recent_activities,
        "recovery": {
            "sleep_hours_7d": round((sleep_avg_seconds or 0) / 3600, 1) if sleep_avg_seconds else None,
            "sleep_quality_7d": round(float(sleep_avg_score), 1) if sleep_avg_score else None,
            "resting_hr_7d": round(resting_hr) if resting_hr else None,
            "hrv_7d": None,
        },
        "prs": {
            "5k": None,
            "10k": None,
            "hm": None,
            "marathon": None,
        },
        "constraints": {
            "days_available": None,
            "injury": None,
        },
        "data_quality": {
            "missing_hr_pct": missing_hr_pct,
        },
    }

    return payload


async def ensure_ai_training_snapshot(
    db: AsyncSession,
    user: User,
    *,
    force: bool = False,
    weeks: int | None = None,
) -> AITrainingSnapshot:
    """Generate training snapshot for a specific time window.

    Args:
        db: Database session.
        user: User.
        force: Force regeneration even if cached.
        weeks: Number of weeks to include. None = all-time, otherwise specific weeks.

    Returns:
        Generated or cached snapshot.
    """
    now = datetime.now(timezone.utc)
    window_end = now.date()

    if weeks is None:
        # All-time: start from earliest realistic date for running data
        window_start = datetime(ALL_TIME_START_YEAR, 1, 1).date()
    else:
        window_start = window_end - timedelta(days=weeks * 7 - 1)

    window_start_dt = datetime.combine(window_start, datetime.min.time(), tzinfo=timezone.utc)
    window_end_dt = datetime.combine(window_end, datetime.max.time(), tzinfo=timezone.utc)

    last_sync_at = await _get_last_sync_at(db, user.id)

    existing_result = await db.execute(
        select(AITrainingSnapshot)
        .where(
            AITrainingSnapshot.user_id == user.id,
            AITrainingSnapshot.window_start == window_start,
            AITrainingSnapshot.window_end == window_end,
            AITrainingSnapshot.schema_version == SNAPSHOT_SCHEMA_VERSION,
        )
        .order_by(AITrainingSnapshot.generated_at.desc())
        .limit(1)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and not force and existing.source_last_sync_at == last_sync_at:
        return existing

    payload = await _build_snapshot_payload(db, user, window_start_dt, window_end_dt)

    if existing:
        existing.payload = payload
        existing.source_last_sync_at = last_sync_at
        existing.generated_at = now
        await db.commit()
        await db.refresh(existing)
        return existing

    snapshot = AITrainingSnapshot(
        user_id=user.id,
        window_start=window_start,
        window_end=window_end,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        generated_at=now,
        source_last_sync_at=last_sync_at,
        payload=payload,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def get_multi_period_snapshots(
    db: AsyncSession,
    user: User,
    *,
    force: bool = False,
) -> dict[str, dict[str, Any]]:
    """Generate snapshots for multiple time periods (6 weeks, 12 weeks, all-time).

    Returns a dictionary with keys: 'recent_6_weeks', 'recent_12_weeks', 'all_time'.
    Each value is the snapshot payload (dict).

    Args:
        db: Database session.
        user: User.
        force: Force regeneration even if cached.

    Returns:
        Dictionary containing snapshots for different time periods.
    """
    # Generate snapshots for each period
    snapshot_6w = await ensure_ai_training_snapshot(db, user, force=force, weeks=6)
    snapshot_12w = await ensure_ai_training_snapshot(db, user, force=force, weeks=12)
    snapshot_all = await ensure_ai_training_snapshot(db, user, force=force, weeks=None)

    return {
        "recent_6_weeks": snapshot_6w.payload,
        "recent_12_weeks": snapshot_12w.payload,
        "all_time": snapshot_all.payload,
    }
