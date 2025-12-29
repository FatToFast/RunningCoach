"""Analytics endpoints for period comparison and personal records.

Paths:
  GET /api/v1/analytics/compare - 기간 비교 분석
  GET /api/v1/analytics/personal-records - 개인 최고 기록 (PR)
"""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.activity import Activity, ActivityMetric
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class PeriodStats(BaseModel):
    """Statistics for a single period."""

    period_start: date
    period_end: date
    total_distance_km: float
    total_duration_hours: float
    total_activities: int
    avg_pace_per_km: str
    avg_hr: int | None
    total_elevation_m: float | None
    total_calories: int | None
    total_trimp: float | None
    total_tss: float | None


class PeriodChange(BaseModel):
    """Change metrics between two periods."""

    distance_change_pct: float | None
    duration_change_pct: float | None
    activities_change: int
    pace_change_seconds: float | None  # Negative = faster (improvement)
    elevation_change_pct: float | None


class CompareResponse(BaseModel):
    """Period comparison response."""

    current_period: PeriodStats
    previous_period: PeriodStats
    change: PeriodChange
    improvement_summary: str  # 자연어 요약


class PersonalRecord(BaseModel):
    """Single personal record entry."""

    category: str  # "5K", "10K", "half_marathon", "marathon", "longest_run", etc.
    value: float  # 시간(초) 또는 거리(m)
    unit: str  # "seconds", "meters", "min/km"
    activity_id: int
    activity_name: str | None
    achieved_date: date
    previous_best: float | None  # 이전 최고 기록
    improvement_pct: float | None  # 개선율


class PersonalRecordsResponse(BaseModel):
    """Personal records response."""

    distance_records: list[PersonalRecord]  # 거리별 최고 기록 (5K, 10K, etc.)
    pace_records: list[PersonalRecord]  # 페이스 기록
    endurance_records: list[PersonalRecord]  # 최장 거리, 최장 시간
    recent_prs: list[PersonalRecord]  # 최근 달성한 PR


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------


def _calculate_pace(duration_seconds: int | None, distance_meters: float | None) -> str:
    """Calculate pace string from duration and distance."""
    if not duration_seconds or not distance_meters or distance_meters == 0:
        return "N/A"

    pace_seconds_per_km = (duration_seconds / distance_meters) * 1000
    minutes = int(pace_seconds_per_km // 60)
    seconds = int(pace_seconds_per_km % 60)
    return f"{minutes}:{seconds:02d}/km"


def _calculate_pace_seconds(duration_seconds: int | None, distance_meters: float | None) -> float | None:
    """Calculate pace in seconds per km."""
    if not duration_seconds or not distance_meters or distance_meters == 0:
        return None
    return (duration_seconds / distance_meters) * 1000


def _calculate_change_pct(current: float | None, previous: float | None) -> float | None:
    """Calculate percentage change between two values."""
    if current is None or previous is None or previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


async def _get_period_stats(
    db: AsyncSession,
    user_id: int,
    start_dt: datetime,
    end_dt: datetime,
    start_date: date,
    end_date: date,
) -> PeriodStats:
    """Get aggregated stats for a period."""
    # Activity stats
    result = await db.execute(
        select(
            func.count(Activity.id).label("count"),
            func.sum(Activity.distance_meters).label("distance"),
            func.sum(Activity.duration_seconds).label("duration"),
            func.avg(Activity.avg_hr).label("avg_hr"),
            func.sum(Activity.elevation_gain).label("elevation"),
            func.sum(Activity.calories).label("calories"),
        ).where(
            Activity.user_id == user_id,
            Activity.start_time >= start_dt,
            Activity.start_time <= end_dt,
        )
    )
    stats = result.one()

    # TRIMP/TSS
    trimp_result = await db.execute(
        select(func.sum(ActivityMetric.trimp), func.sum(ActivityMetric.tss))
        .join(Activity)
        .where(
            Activity.user_id == user_id,
            Activity.start_time >= start_dt,
            Activity.start_time <= end_dt,
        )
    )
    trimp_tss = trimp_result.one()

    return PeriodStats(
        period_start=start_date,
        period_end=end_date,
        total_distance_km=round((stats.distance or 0) / 1000, 2),
        total_duration_hours=round((stats.duration or 0) / 3600, 2),
        total_activities=stats.count or 0,
        avg_pace_per_km=_calculate_pace(stats.duration, stats.distance),
        avg_hr=int(stats.avg_hr) if stats.avg_hr else None,
        total_elevation_m=round(stats.elevation, 1) if stats.elevation else None,
        total_calories=int(stats.calories) if stats.calories else None,
        total_trimp=round(trimp_tss[0], 1) if trimp_tss[0] else None,
        total_tss=round(trimp_tss[1], 1) if trimp_tss[1] else None,
    )


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/compare", response_model=CompareResponse)
async def compare_periods(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    period: str = Query("week", regex="^(week|month)$", description="Period type"),
    current_end: date | None = Query(None, description="End date for current period (defaults to today)"),
) -> CompareResponse:
    """Compare current period with previous period.

    기간 비교 분석: 현재 주/월과 이전 주/월 비교

    Examples:
        GET /analytics/compare → 현재 주 vs 지난 주
        GET /analytics/compare?period=month → 현재 월 vs 지난 월
        GET /analytics/compare?current_end=2024-12-15 → 해당 주 vs 이전 주

    Args:
        current_user: Authenticated user.
        db: Database session.
        period: Period type - "week" or "month".
        current_end: End date for current period.

    Returns:
        Comparison data between two consecutive periods.
    """
    today = current_end or datetime.now(timezone.utc).date()

    if period == "month":
        days = 30
    else:
        days = 7

    # Current period
    current_end_date = today
    current_start_date = today - timedelta(days=days - 1)

    # Previous period
    previous_end_date = current_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=days - 1)

    # Convert to datetime
    current_start_dt = datetime.combine(current_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    current_end_dt = datetime.combine(current_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    previous_start_dt = datetime.combine(previous_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    previous_end_dt = datetime.combine(previous_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Get stats for both periods
    current_stats = await _get_period_stats(
        db, current_user.id, current_start_dt, current_end_dt, current_start_date, current_end_date
    )
    previous_stats = await _get_period_stats(
        db, current_user.id, previous_start_dt, previous_end_dt, previous_start_date, previous_end_date
    )

    # Calculate changes
    current_pace = _calculate_pace_seconds(
        int(current_stats.total_duration_hours * 3600),
        current_stats.total_distance_km * 1000,
    )
    previous_pace = _calculate_pace_seconds(
        int(previous_stats.total_duration_hours * 3600),
        previous_stats.total_distance_km * 1000,
    )

    pace_change = None
    if current_pace and previous_pace:
        pace_change = round(current_pace - previous_pace, 1)

    change = PeriodChange(
        distance_change_pct=_calculate_change_pct(
            current_stats.total_distance_km, previous_stats.total_distance_km
        ),
        duration_change_pct=_calculate_change_pct(
            current_stats.total_duration_hours, previous_stats.total_duration_hours
        ),
        activities_change=current_stats.total_activities - previous_stats.total_activities,
        pace_change_seconds=pace_change,
        elevation_change_pct=_calculate_change_pct(
            current_stats.total_elevation_m, previous_stats.total_elevation_m
        ),
    )

    # Generate improvement summary
    improvements = []
    if change.distance_change_pct and change.distance_change_pct > 0:
        improvements.append(f"거리 {change.distance_change_pct}% 증가")
    elif change.distance_change_pct and change.distance_change_pct < 0:
        improvements.append(f"거리 {abs(change.distance_change_pct)}% 감소")

    if pace_change and pace_change < 0:
        improvements.append(f"페이스 {abs(pace_change):.0f}초/km 향상")
    elif pace_change and pace_change > 0:
        improvements.append(f"페이스 {pace_change:.0f}초/km 느려짐")

    if change.activities_change > 0:
        improvements.append(f"활동 {change.activities_change}회 증가")
    elif change.activities_change < 0:
        improvements.append(f"활동 {abs(change.activities_change)}회 감소")

    summary = ", ".join(improvements) if improvements else "변화 없음"

    return CompareResponse(
        current_period=current_stats,
        previous_period=previous_stats,
        change=change,
        improvement_summary=summary,
    )


@router.get("/personal-records", response_model=PersonalRecordsResponse)
async def get_personal_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    activity_type: str = Query("running", description="Activity type filter"),
) -> PersonalRecordsResponse:
    """Get personal records (PRs) for the user.

    개인 최고 기록 조회

    Categories:
        - Distance PRs: 5K, 10K, Half Marathon, Marathon 최고 기록
        - Pace PRs: 각 거리별 최고 페이스
        - Endurance PRs: 최장 거리, 최장 시간

    Args:
        current_user: Authenticated user.
        db: Database session.
        activity_type: Filter by activity type.

    Returns:
        Personal records across various categories.
    """
    # Define distance categories (in meters)
    distance_categories = [
        ("5K", 5000, 5500),  # 5K with 10% tolerance
        ("10K", 10000, 11000),
        ("Half Marathon", 21097, 22000),
        ("Marathon", 42195, 43000),
    ]

    distance_records: list[PersonalRecord] = []
    pace_records: list[PersonalRecord] = []

    for category_name, min_dist, max_dist in distance_categories:
        # Find best time for this distance
        result = await db.execute(
            select(Activity)
            .where(
                Activity.user_id == current_user.id,
                Activity.activity_type == activity_type,
                Activity.distance_meters >= min_dist,
                Activity.distance_meters <= max_dist,
                Activity.duration_seconds.isnot(None),
            )
            .order_by(Activity.duration_seconds.asc())
            .limit(1)
        )
        best_activity = result.scalar_one_or_none()

        if best_activity:
            # Calculate pace
            pace_seconds = _calculate_pace_seconds(
                best_activity.duration_seconds, best_activity.distance_meters
            )

            distance_records.append(
                PersonalRecord(
                    category=category_name,
                    value=best_activity.duration_seconds,
                    unit="seconds",
                    activity_id=best_activity.id,
                    activity_name=best_activity.name,
                    achieved_date=best_activity.start_time.date(),
                    previous_best=None,
                    improvement_pct=None,
                )
            )

            if pace_seconds:
                pace_records.append(
                    PersonalRecord(
                        category=f"{category_name} Pace",
                        value=pace_seconds,
                        unit="sec/km",
                        activity_id=best_activity.id,
                        activity_name=best_activity.name,
                        achieved_date=best_activity.start_time.date(),
                        previous_best=None,
                        improvement_pct=None,
                    )
                )

    # Endurance records: Longest distance
    longest_result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == current_user.id,
            Activity.activity_type == activity_type,
            Activity.distance_meters.isnot(None),
        )
        .order_by(Activity.distance_meters.desc())
        .limit(1)
    )
    longest_activity = longest_result.scalar_one_or_none()

    endurance_records: list[PersonalRecord] = []
    if longest_activity and longest_activity.distance_meters:
        endurance_records.append(
            PersonalRecord(
                category="Longest Run",
                value=longest_activity.distance_meters,
                unit="meters",
                activity_id=longest_activity.id,
                activity_name=longest_activity.name,
                achieved_date=longest_activity.start_time.date(),
                previous_best=None,
                improvement_pct=None,
            )
        )

    # Endurance records: Longest duration
    duration_result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == current_user.id,
            Activity.activity_type == activity_type,
            Activity.duration_seconds.isnot(None),
        )
        .order_by(Activity.duration_seconds.desc())
        .limit(1)
    )
    duration_activity = duration_result.scalar_one_or_none()

    if duration_activity and duration_activity.duration_seconds:
        endurance_records.append(
            PersonalRecord(
                category="Longest Duration",
                value=duration_activity.duration_seconds,
                unit="seconds",
                activity_id=duration_activity.id,
                activity_name=duration_activity.name,
                achieved_date=duration_activity.start_time.date(),
                previous_best=None,
                improvement_pct=None,
            )
        )

    # Recent PRs (activities in last 30 days that set new records)
    # This is a simplified version - a full implementation would compare
    # each activity against all previous activities
    recent_prs: list[PersonalRecord] = []

    return PersonalRecordsResponse(
        distance_records=distance_records,
        pace_records=pace_records,
        endurance_records=endurance_records,
        recent_prs=recent_prs,
    )
