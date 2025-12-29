"""Dashboard endpoints."""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.activity import Activity, ActivityMetric
from app.models.analytics import AnalyticsSummary
from app.models.health import FitnessMetricDaily, Sleep
from app.models.user import User
from app.models.workout import WorkoutSchedule

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class WeeklySummary(BaseModel):
    """Weekly summary stats."""

    total_distance_km: float
    total_duration_hours: float
    total_activities: int
    avg_pace_per_km: str
    avg_hr: int | None
    total_elevation_m: float | None
    total_calories: int | None


class RecentActivity(BaseModel):
    """Recent activity summary."""

    id: int
    name: str | None
    activity_type: str
    start_time: datetime
    distance_km: float | None
    duration_minutes: int | None
    avg_hr: int | None


class HealthStatus(BaseModel):
    """Current health status."""

    latest_sleep_score: int | None
    latest_sleep_hours: float | None
    resting_hr: int | None
    body_battery: int | None
    vo2max: float | None


class FitnessStatus(BaseModel):
    """Current fitness metrics."""

    ctl: float | None  # Chronic Training Load
    atl: float | None  # Acute Training Load
    tsb: float | None  # Training Stress Balance
    weekly_trimp: float | None
    weekly_tss: float | None


class UpcomingWorkout(BaseModel):
    """Upcoming scheduled workout."""

    id: int
    workout_name: str
    workout_type: str
    scheduled_date: date


class DashboardSummaryResponse(BaseModel):
    """Main dashboard summary."""

    period_type: str  # "week" or "month"
    period_start: date
    period_end: date
    summary: WeeklySummary  # Renamed from weekly_summary for flexibility
    recent_activities: list[RecentActivity]
    health_status: HealthStatus
    fitness_status: FitnessStatus
    upcoming_workouts: list[UpcomingWorkout]


class TrendPoint(BaseModel):
    """Single trend data point."""

    date: date
    value: float


class TrendsResponse(BaseModel):
    """Trend data for charts."""

    weekly_distance: list[TrendPoint]
    weekly_duration: list[TrendPoint]
    avg_pace: list[TrendPoint]
    resting_hr: list[TrendPoint]
    ctl_atl: list[dict]  # [{"date": ..., "ctl": ..., "atl": ..., "tsb": ...}]


class CalendarDay(BaseModel):
    """Calendar day with activities and workouts."""

    date: date
    activities: list[RecentActivity]
    scheduled_workouts: list[UpcomingWorkout]


class CalendarResponse(BaseModel):
    """Calendar view data."""

    days: list[CalendarDay]
    start_date: date
    end_date: date


# -------------------------------------------------------------------------
# Dashboard Endpoints
# -------------------------------------------------------------------------


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    target_date: date | None = Query(None, description="Target date for summary (defaults to today)"),
    period: str = Query("week", regex="^(week|month)$", description="Period type: week or month"),
) -> DashboardSummaryResponse:
    """Get main dashboard summary for a specific date range.

    FR-010: 메인 대시보드

    Query Parameters:
        target_date: 조회 기준 날짜 (기본값: 오늘)
        period: 기간 유형 - "week" (7일) 또는 "month" (30일)

    Examples:
        GET /dashboard/summary → 현재 주간 요약
        GET /dashboard/summary?target_date=2024-12-01 → 2024-12-01 포함 주간
        GET /dashboard/summary?period=month → 현재 월간 요약
        GET /dashboard/summary?target_date=2024-11-15&period=month → 해당 월간 요약

    Args:
        current_user: Authenticated user.
        db: Database session.
        target_date: Target date for the period (defaults to today).
        period: Period type - "week" or "month".

    Returns:
        Dashboard summary data for the specified period.
    """
    now = datetime.now(timezone.utc)
    today = target_date or now.date()

    # Calculate period boundaries
    if period == "month":
        # Month: 30 days ending on target_date
        period_end = today
        period_start = today - timedelta(days=29)
    else:
        # Week: 7 days ending on target_date (default)
        period_end = today
        period_start = today - timedelta(days=6)

    # Convert to datetime for queries
    period_start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    period_end_dt = datetime.combine(period_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Period summary (활동 통계)
    summary_result = await db.execute(
        select(
            func.count(Activity.id).label("count"),
            func.sum(Activity.distance_meters).label("distance"),
            func.sum(Activity.duration_seconds).label("duration"),
            func.avg(Activity.avg_hr).label("avg_hr"),
            func.sum(Activity.elevation_gain).label("elevation"),
            func.sum(Activity.calories).label("calories"),
        ).where(
            Activity.user_id == current_user.id,
            Activity.start_time >= period_start_dt,
            Activity.start_time <= period_end_dt,
        )
    )
    stats = summary_result.one()

    period_summary = WeeklySummary(
        total_distance_km=round((stats.distance or 0) / 1000, 2),
        total_duration_hours=round((stats.duration or 0) / 3600, 2),
        total_activities=stats.count or 0,
        avg_pace_per_km=_calculate_pace(stats.duration, stats.distance),
        avg_hr=int(stats.avg_hr) if stats.avg_hr else None,
        total_elevation_m=round(stats.elevation, 1) if stats.elevation else None,
        total_calories=int(stats.calories) if stats.calories else None,
    )

    # Recent activities
    recent_result = await db.execute(
        select(Activity)
        .where(Activity.user_id == current_user.id)
        .order_by(Activity.start_time.desc())
        .limit(5)
    )
    recent_activities = [
        RecentActivity(
            id=a.id,
            name=a.name,
            activity_type=a.activity_type,
            start_time=a.start_time,
            distance_km=round(a.distance_meters / 1000, 2) if a.distance_meters else None,
            duration_minutes=int(a.duration_seconds / 60) if a.duration_seconds else None,
            avg_hr=a.avg_hr,
        )
        for a in recent_result.scalars().all()
    ]

    # Health status
    sleep_result = await db.execute(
        select(Sleep)
        .where(Sleep.user_id == current_user.id)
        .order_by(Sleep.date.desc())
        .limit(1)
    )
    latest_sleep = sleep_result.scalar_one_or_none()

    health_status = HealthStatus(
        latest_sleep_score=latest_sleep.score if latest_sleep else None,
        latest_sleep_hours=round(latest_sleep.duration_seconds / 3600, 1) if latest_sleep and latest_sleep.duration_seconds else None,
        resting_hr=None,
        body_battery=None,
        vo2max=None,
    )

    # Fitness status
    fitness_result = await db.execute(
        select(FitnessMetricDaily)
        .where(FitnessMetricDaily.user_id == current_user.id)
        .order_by(FitnessMetricDaily.date.desc())
        .limit(1)
    )
    latest_fitness = fitness_result.scalar_one_or_none()

    # Period TRIMP/TSS (기간 내 훈련 부하)
    trimp_result = await db.execute(
        select(func.sum(ActivityMetric.trimp), func.sum(ActivityMetric.tss))
        .join(Activity)
        .where(
            Activity.user_id == current_user.id,
            Activity.start_time >= period_start_dt,
            Activity.start_time <= period_end_dt,
        )
    )
    trimp_tss = trimp_result.one()

    fitness_status = FitnessStatus(
        ctl=latest_fitness.ctl if latest_fitness else None,
        atl=latest_fitness.atl if latest_fitness else None,
        tsb=latest_fitness.tsb if latest_fitness else None,
        weekly_trimp=round(trimp_tss[0], 1) if trimp_tss[0] else None,
        weekly_tss=round(trimp_tss[1], 1) if trimp_tss[1] else None,
    )

    # Upcoming workouts (기준일 이후 예정된 운동)
    from app.models.workout import Workout

    upcoming_result = await db.execute(
        select(WorkoutSchedule, Workout)
        .join(Workout)
        .where(
            Workout.user_id == current_user.id,
            WorkoutSchedule.scheduled_date >= period_end,
            WorkoutSchedule.status == "scheduled",
        )
        .order_by(WorkoutSchedule.scheduled_date.asc())
        .limit(5)
    )
    upcoming_workouts = [
        UpcomingWorkout(
            id=schedule.id,
            workout_name=workout.name,
            workout_type=workout.workout_type,
            scheduled_date=schedule.scheduled_date,
        )
        for schedule, workout in upcoming_result.all()
    ]

    return DashboardSummaryResponse(
        period_type=period,
        period_start=period_start,
        period_end=period_end,
        summary=period_summary,
        recent_activities=recent_activities,
        health_status=health_status,
        fitness_status=fitness_status,
        upcoming_workouts=upcoming_workouts,
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    weeks: int = Query(12, ge=4, le=52),
) -> TrendsResponse:
    """Get trend data for charts.

    FR-013: 트렌드 분석

    Args:
        current_user: Authenticated user.
        db: Database session.
        weeks: Number of weeks to include.

    Returns:
        Trend data.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(weeks=weeks)

    # Get weekly analytics summaries
    result = await db.execute(
        select(AnalyticsSummary)
        .where(
            AnalyticsSummary.user_id == current_user.id,
            AnalyticsSummary.period_type == "week",
            AnalyticsSummary.period_start >= start_date,
        )
        .order_by(AnalyticsSummary.period_start.asc())
    )
    summaries = result.scalars().all()

    weekly_distance = [
        TrendPoint(
            date=s.period_start,
            value=round((s.total_distance_meters or 0) / 1000, 2),
        )
        for s in summaries
    ]

    weekly_duration = [
        TrendPoint(
            date=s.period_start,
            value=round((s.total_duration_seconds or 0) / 3600, 2),
        )
        for s in summaries
    ]

    avg_pace = [
        TrendPoint(
            date=s.period_start,
            value=s.avg_pace_seconds or 0,
        )
        for s in summaries
        if s.avg_pace_seconds
    ]

    # Get fitness metrics for CTL/ATL/TSB
    fitness_result = await db.execute(
        select(FitnessMetricDaily)
        .where(
            FitnessMetricDaily.user_id == current_user.id,
            FitnessMetricDaily.date >= start_date,
        )
        .order_by(FitnessMetricDaily.date.asc())
    )
    fitness_metrics = fitness_result.scalars().all()

    ctl_atl = [
        {
            "date": f.date.isoformat(),
            "ctl": f.ctl,
            "atl": f.atl,
            "tsb": f.tsb,
        }
        for f in fitness_metrics
    ]

    return TrendsResponse(
        weekly_distance=weekly_distance,
        weekly_duration=weekly_duration,
        avg_pace=avg_pace,
        resting_hr=[],
        ctl_atl=ctl_atl,
    )


@router.get("/calendar", response_model=CalendarResponse)
async def get_calendar(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    start_date: date = Query(...),
    end_date: date = Query(...),
) -> CalendarResponse:
    """Get calendar view with activities and scheduled workouts.

    Args:
        current_user: Authenticated user.
        db: Database session.
        start_date: Calendar start date.
        end_date: Calendar end date.

    Returns:
        Calendar data.
    """
    from app.models.workout import Workout

    # Get activities in range
    activities_result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == current_user.id,
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time <= datetime.combine(end_date, datetime.max.time()),
        )
        .order_by(Activity.start_time.asc())
    )
    activities = activities_result.scalars().all()

    # Get scheduled workouts in range
    schedules_result = await db.execute(
        select(WorkoutSchedule, Workout)
        .join(Workout)
        .where(
            Workout.user_id == current_user.id,
            WorkoutSchedule.scheduled_date >= start_date,
            WorkoutSchedule.scheduled_date <= end_date,
        )
        .order_by(WorkoutSchedule.scheduled_date.asc())
    )
    schedules = schedules_result.all()

    # Build calendar days
    days = []
    current = start_date
    while current <= end_date:
        day_activities = [
            RecentActivity(
                id=a.id,
                name=a.name,
                activity_type=a.activity_type,
                start_time=a.start_time,
                distance_km=round(a.distance_meters / 1000, 2) if a.distance_meters else None,
                duration_minutes=int(a.duration_seconds / 60) if a.duration_seconds else None,
                avg_hr=a.avg_hr,
            )
            for a in activities
            if a.start_time.date() == current
        ]

        day_workouts = [
            UpcomingWorkout(
                id=schedule.id,
                workout_name=workout.name,
                workout_type=workout.workout_type,
                scheduled_date=schedule.scheduled_date,
            )
            for schedule, workout in schedules
            if schedule.scheduled_date == current
        ]

        days.append(
            CalendarDay(
                date=current,
                activities=day_activities,
                scheduled_workouts=day_workouts,
            )
        )
        current += timedelta(days=1)

    return CalendarResponse(
        days=days,
        start_date=start_date,
        end_date=end_date,
    )


def _calculate_pace(duration_seconds: int | None, distance_meters: float | None) -> str:
    """Calculate pace string from duration and distance."""
    if not duration_seconds or not distance_meters or distance_meters == 0:
        return "N/A"

    pace_seconds_per_km = (duration_seconds / distance_meters) * 1000
    minutes = int(pace_seconds_per_km // 60)
    seconds = int(pace_seconds_per_km % 60)
    return f"{minutes}:{seconds:02d}/km"
