"""Dashboard endpoints."""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.core.config import get_settings
from app.models.activity import Activity, ActivityMetric
from app.models.analytics import AnalyticsSummary
from app.models.health import FitnessMetricDaily, HealthMetric, HRRecord, Sleep
from app.models.user import User
from app.models.workout import WorkoutSchedule
import httpx

router = APIRouter()
settings = get_settings()


# -------------------------------------------------------------------------
# Runalyze Integration Helper
# -------------------------------------------------------------------------


async def _fetch_runalyze_data() -> tuple[dict | None, dict | None]:
    """Fetch calculations and training paces from Runalyze API.

    Returns:
        Tuple of (calculations_dict, training_paces_dict) or (None, None) on error.
    """
    if not settings.runalyze_api_token:
        return None, None

    calculations = None
    training_paces = None

    try:
        async with httpx.AsyncClient(
            base_url=settings.runalyze_api_base_url,
            headers={"token": settings.runalyze_api_token},
            timeout=10.0,
        ) as client:
            # Fetch calculations
            try:
                calc_response = await client.get("/metrics/calculations")
                if calc_response.status_code == 200:
                    calculations = calc_response.json()
            except Exception:
                pass

            # Fallback: try fitness endpoint for ATL/CTL/TSB
            if not calculations:
                try:
                    fitness_response = await client.get("/metrics/fitness")
                    if fitness_response.status_code == 200:
                        fitness_data = fitness_response.json()
                        if fitness_data:
                            if isinstance(fitness_data, list) and len(fitness_data) > 0:
                                latest = sorted(
                                    fitness_data,
                                    key=lambda x: x.get("date", x.get("date_time", "")),
                                    reverse=True,
                                )[0]
                                calculations = {
                                    "ctl": latest.get("ctl") or latest.get("fitness"),
                                    "atl": latest.get("atl") or latest.get("fatigue"),
                                    "tsb": latest.get("tsb") or latest.get("form"),
                                }
                            elif isinstance(fitness_data, dict):
                                calculations = {
                                    "ctl": fitness_data.get("ctl") or fitness_data.get("fitness"),
                                    "atl": fitness_data.get("atl") or fitness_data.get("fatigue"),
                                    "tsb": fitness_data.get("tsb") or fitness_data.get("form"),
                                }
                except Exception:
                    pass

            # Fetch training paces
            for endpoint in ["/metrics/paces", "/training/paces", "/paces"]:
                try:
                    paces_response = await client.get(endpoint)
                    if paces_response.status_code == 200:
                        paces_data = paces_response.json()
                        if paces_data:
                            training_paces = paces_data[0] if isinstance(paces_data, list) else paces_data
                            if training_paces.get("vdot"):
                                break
                            training_paces = None
                except Exception:
                    continue

    except Exception:
        pass

    return calculations, training_paces


def _parse_pace(value) -> int | None:
    """Parse pace value to seconds per km."""
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


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class WeeklySummary(BaseModel):
    """Weekly summary stats."""

    total_distance_km: float
    total_duration_hours: float
    total_activities: int
    avg_pace_per_km: str
    avg_pace_seconds: int | None  # 페이스를 초 단위로 (formatPace용)
    avg_hr: int | None
    total_elevation_m: float | None
    total_calories: int | None


class RecentActivity(BaseModel):
    """Recent activity summary (Runalyze-style)."""

    id: int
    name: str | None
    activity_type: str
    start_time: datetime
    distance_km: float | None
    duration_seconds: int | None  # Duration in seconds (for hh:mm:ss format)
    avg_pace_seconds: int | None  # 페이스 (초/km)
    avg_hr_percent: int | None  # 최대심박 대비 % (Runalyze: 72%)
    elevation_gain: float | None  # 고도 상승 (m)
    calories: int | None  # 에너지 (kcal)
    trimp: float | None  # TRIMP
    vo2max_est: float | None  # 활동별 VO2max 추정치
    avg_cadence: int | None  # 케이던스 (spm)
    avg_ground_time: int | None  # 지면 접촉 시간 (ms)
    avg_vertical_oscillation: float | None  # 수직 진동 (cm)


class HealthStatus(BaseModel):
    """Current health status."""

    latest_sleep_score: int | None
    latest_sleep_hours: float | None
    resting_hr: int | None
    body_battery: int | None
    vo2max: float | None


class FitnessStatus(BaseModel):
    """Current fitness metrics (including Runalyze-style extended metrics)."""

    ctl: float | None  # Chronic Training Load (Fitness)
    atl: float | None  # Acute Training Load (Fatigue)
    tsb: float | None  # Training Stress Balance
    weekly_trimp: float | None
    weekly_tss: float | None
    # Extended Runalyze-style metrics
    effective_vo2max: float | None = None
    marathon_shape: float | None = None  # percentage
    workload_ratio: float | None = None  # A:C ratio
    rest_days: float | None = None
    monotony: float | None = None  # percentage
    training_strain: float | None = None


class TrainingPaces(BaseModel):
    """Daniels-based training paces."""

    vdot: float
    easy_min: int  # seconds per km
    easy_max: int
    marathon_min: int
    marathon_max: int
    threshold_min: int
    threshold_max: int
    interval_min: int
    interval_max: int
    repetition_min: int
    repetition_max: int


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
    training_paces: TrainingPaces | None = None


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
        period: 기간 유형
            - "week": 해당 날짜가 속한 주 (월요일~일요일)
            - "month": 해당 날짜가 속한 월 (1일~말일)

    Examples:
        GET /dashboard/summary → 이번 주(월~일) 요약
        GET /dashboard/summary?target_date=2024-12-01 → 2024-12-01이 속한 주 요약
        GET /dashboard/summary?period=month → 이번 달(1일~말일) 요약
        GET /dashboard/summary?target_date=2024-11-15&period=month → 2024년 11월 요약

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

    # Calculate period boundaries (calendar-based)
    if period == "month":
        # Month: 1st to last day of the month containing target_date
        period_start = today.replace(day=1)
        # Last day of month
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        period_end = next_month - timedelta(days=1)
    else:
        # Week: Monday to Sunday containing target_date
        # weekday(): Monday=0, Sunday=6
        days_since_monday = today.weekday()
        period_start = today - timedelta(days=days_since_monday)
        period_end = period_start + timedelta(days=6)

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

    # Calculate avg pace in seconds per km
    avg_pace_seconds = None
    if stats.duration and stats.distance and stats.distance > 0:
        avg_pace_seconds = int((stats.duration / stats.distance) * 1000)

    period_summary = WeeklySummary(
        total_distance_km=round((stats.distance or 0) / 1000, 2),
        total_duration_hours=round((stats.duration or 0) / 3600, 2),
        total_activities=stats.count or 0,
        avg_pace_per_km=_calculate_pace(stats.duration, stats.distance),
        avg_pace_seconds=avg_pace_seconds,
        avg_hr=int(stats.avg_hr) if stats.avg_hr else None,
        total_elevation_m=round(stats.elevation, 1) if stats.elevation else None,
        total_calories=int(stats.calories) if stats.calories else None,
    )

    # Get user's max HR (priority: User.max_hr from Garmin > observed max_hr)
    user_max_hr = current_user.max_hr
    if not user_max_hr:
        # Fallback: 관측된 최대 심박수 사용
        max_hr_result = await db.execute(
            select(func.max(Activity.max_hr)).where(
                Activity.user_id == current_user.id,
                Activity.max_hr.isnot(None),
            )
        )
        user_max_hr = max_hr_result.scalar_one_or_none()

    # Recent activities (기준일 기준 최근 7일 이내, 최대 5건) - PRD FR-010
    # target_date 기준으로 최근 활동을 조회 (과거 날짜 조회 시에도 일관성 유지)
    recent_cutoff = datetime.combine(
        today - timedelta(days=6), datetime.min.time()
    ).replace(tzinfo=timezone.utc)
    recent_limit = datetime.combine(
        today, datetime.max.time()
    ).replace(tzinfo=timezone.utc)
    recent_result = await db.execute(
        select(Activity, ActivityMetric)
        .outerjoin(ActivityMetric, Activity.id == ActivityMetric.activity_id)
        .where(
            Activity.user_id == current_user.id,
            Activity.start_time >= recent_cutoff,
            Activity.start_time <= recent_limit,  # 기준일까지만 (미래 활동 제외)
        )
        .order_by(Activity.start_time.desc())
        .limit(5)
    )

    recent_activities = []
    for a, m in recent_result.all():
        # Calculate avg pace in seconds per km
        activity_pace = None
        if a.duration_seconds and a.distance_meters and a.distance_meters > 0:
            activity_pace = int((a.duration_seconds / a.distance_meters) * 1000)

        # Calculate avg HR as percentage of max HR (Runalyze style: shows only %)
        avg_hr_percent = None
        if a.avg_hr and user_max_hr:
            avg_hr_percent = int(round((a.avg_hr / user_max_hr) * 100))

        recent_activities.append(
            RecentActivity(
                id=a.id,
                name=a.name,
                activity_type=a.activity_type,
                start_time=a.start_time,
                distance_km=round(a.distance_meters / 1000, 2) if a.distance_meters else None,
                duration_seconds=a.duration_seconds,
                avg_pace_seconds=activity_pace,
                avg_hr_percent=avg_hr_percent,
                elevation_gain=round(a.elevation_gain, 1) if a.elevation_gain else None,
                calories=int(a.calories) if a.calories else None,
                trimp=round(m.trimp, 1) if m and m.trimp else None,
                vo2max_est=round(m.vo2max_est, 1) if m and m.vo2max_est else None,
                avg_cadence=a.avg_cadence,
                avg_ground_time=a.avg_ground_contact_time,  # Activity 모델 필드명
                avg_vertical_oscillation=round(a.avg_vertical_oscillation, 1) if a.avg_vertical_oscillation else None,
            )
        )

    # Health status
    sleep_result = await db.execute(
        select(Sleep)
        .where(Sleep.user_id == current_user.id)
        .order_by(Sleep.date.desc())
        .limit(1)
    )
    latest_sleep = sleep_result.scalar_one_or_none()

    # Resting HR from HRRecord (latest non-null value)
    hr_result = await db.execute(
        select(HRRecord.resting_hr)
        .where(
            HRRecord.user_id == current_user.id,
            HRRecord.resting_hr.isnot(None),
        )
        .order_by(HRRecord.start_time.desc())
        .limit(1)
    )
    latest_resting_hr = hr_result.scalar_one_or_none()

    # Body Battery from HealthMetric (latest value)
    body_battery_result = await db.execute(
        select(HealthMetric.value)
        .where(
            HealthMetric.user_id == current_user.id,
            HealthMetric.metric_type == "body_battery",
        )
        .order_by(HealthMetric.metric_time.desc())
        .limit(1)
    )
    latest_body_battery = body_battery_result.scalar_one_or_none()

    # VO2Max from HealthMetric (latest value)
    vo2max_result = await db.execute(
        select(HealthMetric.value)
        .where(
            HealthMetric.user_id == current_user.id,
            HealthMetric.metric_type == "vo2max",
        )
        .order_by(HealthMetric.metric_time.desc())
        .limit(1)
    )
    latest_vo2max = vo2max_result.scalar_one_or_none()

    health_status = HealthStatus(
        latest_sleep_score=latest_sleep.score if latest_sleep else None,
        latest_sleep_hours=round(latest_sleep.duration_seconds / 3600, 1) if latest_sleep and latest_sleep.duration_seconds else None,
        resting_hr=latest_resting_hr,
        body_battery=int(latest_body_battery) if latest_body_battery else None,
        vo2max=round(float(latest_vo2max), 1) if latest_vo2max else None,
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

    # Fetch Runalyze data (calculations and training paces)
    runalyze_calc, runalyze_paces = await _fetch_runalyze_data()

    # Build fitness status with Runalyze extended metrics
    fitness_status = FitnessStatus(
        # Use Runalyze data if available, otherwise fall back to local DB
        ctl=runalyze_calc.get("ctl") if runalyze_calc else (latest_fitness.ctl if latest_fitness else None),
        atl=runalyze_calc.get("atl") if runalyze_calc else (latest_fitness.atl if latest_fitness else None),
        tsb=runalyze_calc.get("tsb") if runalyze_calc else (latest_fitness.tsb if latest_fitness else None),
        weekly_trimp=round(trimp_tss[0], 1) if trimp_tss[0] else None,
        weekly_tss=round(trimp_tss[1], 1) if trimp_tss[1] else None,
        # Extended Runalyze-style metrics
        effective_vo2max=runalyze_calc.get("effective_vo2max") or runalyze_calc.get("vo2max") if runalyze_calc else None,
        marathon_shape=runalyze_calc.get("marathon_shape") if runalyze_calc else None,
        workload_ratio=runalyze_calc.get("workload_ratio") or runalyze_calc.get("ac_ratio") if runalyze_calc else None,
        rest_days=runalyze_calc.get("rest_days") if runalyze_calc else None,
        monotony=runalyze_calc.get("monotony") if runalyze_calc else None,
        training_strain=runalyze_calc.get("training_strain") if runalyze_calc else None,
    )

    # Build training paces from Runalyze
    training_paces = None
    if runalyze_paces and runalyze_paces.get("vdot"):
        training_paces = TrainingPaces(
            vdot=float(runalyze_paces.get("vdot")),
            easy_min=_parse_pace(runalyze_paces.get("easy_min")) or 343,
            easy_max=_parse_pace(runalyze_paces.get("easy_max")) or 430,
            marathon_min=_parse_pace(runalyze_paces.get("marathon_min")) or 302,
            marathon_max=_parse_pace(runalyze_paces.get("marathon_max")) or 338,
            threshold_min=_parse_pace(runalyze_paces.get("threshold_min")) or 276,
            threshold_max=_parse_pace(runalyze_paces.get("threshold_max")) or 288,
            interval_min=_parse_pace(runalyze_paces.get("interval_min")) or 254,
            interval_max=_parse_pace(runalyze_paces.get("interval_max")) or 267,
            repetition_min=_parse_pace(runalyze_paces.get("repetition_min")) or 231,
            repetition_max=_parse_pace(runalyze_paces.get("repetition_max")) or 242,
        )

    # Upcoming workouts (기준일 이후 예정된 운동 - today 또는 target_date 기준)
    from app.models.workout import Workout

    upcoming_result = await db.execute(
        select(WorkoutSchedule, Workout)
        .join(Workout)
        .where(
            Workout.user_id == current_user.id,
            WorkoutSchedule.scheduled_date >= today,  # 기준일(today) 이후 예정 운동
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
        training_paces=training_paces,
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

    # Get resting HR trend from HRRecord (daily values)
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    hr_trend_result = await db.execute(
        select(HRRecord.start_time, HRRecord.resting_hr)
        .where(
            HRRecord.user_id == current_user.id,
            HRRecord.start_time >= start_datetime,
            HRRecord.resting_hr.isnot(None),
        )
        .order_by(HRRecord.start_time.asc())
    )
    hr_records = hr_trend_result.all()

    resting_hr = [
        TrendPoint(
            date=hr.start_time.date(),
            value=float(hr.resting_hr),
        )
        for hr in hr_records
    ]

    return TrendsResponse(
        weekly_distance=weekly_distance,
        weekly_duration=weekly_duration,
        avg_pace=avg_pace,
        resting_hr=resting_hr,
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
    from collections import defaultdict

    # Convert to timezone-aware datetime for consistent filtering
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Get user's max HR for avg_hr_percent calculation
    user_max_hr = current_user.max_hr
    if not user_max_hr:
        max_hr_result = await db.execute(
            select(func.max(Activity.max_hr)).where(
                Activity.user_id == current_user.id,
                Activity.max_hr.isnot(None),
            )
        )
        user_max_hr = max_hr_result.scalar_one_or_none()

    # Get activities in range with ActivityMetric for extended fields
    activities_result = await db.execute(
        select(Activity, ActivityMetric)
        .outerjoin(ActivityMetric, Activity.id == ActivityMetric.activity_id)
        .where(
            Activity.user_id == current_user.id,
            Activity.start_time >= start_dt,
            Activity.start_time <= end_dt,
        )
        .order_by(Activity.start_time.asc())
    )
    activities_with_metrics = activities_result.all()

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

    # Pre-group activities by date for O(activities + days) instead of O(activities × days)
    activities_by_date: dict[date, list[RecentActivity]] = defaultdict(list)
    for a, m in activities_with_metrics:
        activity_date = a.start_time.date()
        # Calculate avg pace in seconds per km
        activity_pace = None
        if a.duration_seconds and a.distance_meters and a.distance_meters > 0:
            activity_pace = int((a.duration_seconds / a.distance_meters) * 1000)

        # Calculate avg HR as percentage of max HR (Runalyze style)
        avg_hr_percent = None
        if a.avg_hr and user_max_hr:
            avg_hr_percent = int(round((a.avg_hr / user_max_hr) * 100))

        activities_by_date[activity_date].append(
            RecentActivity(
                id=a.id,
                name=a.name,
                activity_type=a.activity_type,
                start_time=a.start_time,
                distance_km=round(a.distance_meters / 1000, 2) if a.distance_meters else None,
                duration_seconds=a.duration_seconds,
                avg_pace_seconds=activity_pace,
                avg_hr_percent=avg_hr_percent,
                elevation_gain=round(a.elevation_gain, 1) if a.elevation_gain else None,
                calories=int(a.calories) if a.calories else None,
                trimp=round(m.trimp, 1) if m and m.trimp else None,
                vo2max_est=round(m.vo2max_est, 1) if m and m.vo2max_est else None,
                avg_cadence=a.avg_cadence,
                avg_ground_time=a.avg_ground_contact_time,
                avg_vertical_oscillation=round(a.avg_vertical_oscillation, 1) if a.avg_vertical_oscillation else None,
            )
        )

    # Pre-group workouts by date
    workouts_by_date: dict[date, list[UpcomingWorkout]] = defaultdict(list)
    for schedule, workout in schedules:
        workouts_by_date[schedule.scheduled_date].append(
            UpcomingWorkout(
                id=schedule.id,
                workout_name=workout.name,
                workout_type=workout.workout_type,
                scheduled_date=schedule.scheduled_date,
            )
        )

    # Build calendar days - now O(days) instead of O(days × items)
    days = []
    current = start_date
    while current <= end_date:
        days.append(
            CalendarDay(
                date=current,
                activities=activities_by_date.get(current, []),
                scheduled_workouts=workouts_by_date.get(current, []),
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
