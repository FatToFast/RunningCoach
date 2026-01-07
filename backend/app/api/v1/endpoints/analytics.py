"""Analytics endpoints for period comparison, personal records, and VDOT calculation.

Paths:
  GET /api/v1/analytics/compare - 기간 비교 분석
  GET /api/v1/analytics/personal-records - 개인 최고 기록 (PR)
  GET /api/v1/analytics/vdot - VDOT 계산 및 훈련 페이스
"""

import calendar
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
# Constants
# -------------------------------------------------------------------------

# Distance categories for PR calculation (min_meters, max_meters)
# Tolerance: ±5% to allow for GPS variance (both under and over)
# GPS can read short (signal loss) or long (zigzag path)
DISTANCE_CATEGORIES = [
    ("5K", 4750, 5250),           # 5000m ± 5%
    ("10K", 9500, 10500),         # 10000m ± 5%
    ("Half Marathon", 20042, 22152),  # 21097m ± 5%
    ("Marathon", 40085, 44305),   # 42195m ± 5%
]


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


class PeriodStatsWithRaw(BaseModel):
    """Period stats with raw values for internal calculations."""

    stats: PeriodStats
    raw_distance_meters: float
    raw_duration_seconds: int


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
    value: float  # 시간(초) 또는 거리(m) 또는 페이스(sec/km)
    unit: str  # "seconds", "meters", "sec/km"
    activity_id: int
    activity_name: str | None
    achieved_date: date
    previous_best: float | None  # 이전 최고 기록
    improvement_pct: float | None  # 개선율 (음수 = 개선)


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
) -> PeriodStatsWithRaw:
    """Get aggregated stats for a period.

    Returns PeriodStatsWithRaw which includes raw values for accurate pace calculation.
    """
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

    raw_distance = stats.distance or 0
    raw_duration = stats.duration or 0

    period_stats = PeriodStats(
        period_start=start_date,
        period_end=end_date,
        total_distance_km=round(raw_distance / 1000, 2),
        total_duration_hours=round(raw_duration / 3600, 2),
        total_activities=stats.count or 0,
        avg_pace_per_km=_calculate_pace(raw_duration, raw_distance),
        avg_hr=int(stats.avg_hr) if stats.avg_hr else None,
        total_elevation_m=round(stats.elevation, 1) if stats.elevation else None,
        total_calories=int(stats.calories) if stats.calories else None,
        total_trimp=round(trimp_tss[0], 1) if trimp_tss[0] else None,
        total_tss=round(trimp_tss[1], 1) if trimp_tss[1] else None,
    )

    return PeriodStatsWithRaw(
        stats=period_stats,
        raw_distance_meters=raw_distance,
        raw_duration_seconds=raw_duration,
    )


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/compare", response_model=CompareResponse)
async def compare_periods(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    period: str = Query("week", pattern="^(week|month)$", description="Period type"),
    current_end: date | None = Query(None, description="Reference date to determine the period (defaults to today). The period containing this date will be compared with its previous period."),
) -> CompareResponse:
    """Compare current period with previous period.

    기간 비교 분석: 현재 주/월과 이전 주/월 비교

    - week: 월요일~일요일 기준 (ISO week)
    - month: 달력 기준 월 (1일~말일)

    Examples:
        GET /analytics/compare → 현재 주 vs 지난 주
        GET /analytics/compare?period=month → 현재 월 vs 지난 월
        GET /analytics/compare?current_end=2024-12-15 → 해당 주 vs 이전 주

    Args:
        current_user: Authenticated user.
        db: Database session.
        period: Period type - "week" (Mon-Sun) or "month" (calendar month).
        current_end: End date for current period.

    Returns:
        Comparison data between two consecutive periods.
    """
    today = current_end or datetime.now(timezone.utc).date()

    if period == "month":
        # Calendar month: 1st to last day of month
        current_end_date = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        current_start_date = date(today.year, today.month, 1)

        # Previous month
        if today.month == 1:
            prev_year, prev_month = today.year - 1, 12
        else:
            prev_year, prev_month = today.year, today.month - 1
        previous_start_date = date(prev_year, prev_month, 1)
        previous_end_date = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])
    else:
        # ISO week: Monday to Sunday
        # Find Monday of current week
        days_since_monday = today.weekday()
        current_start_date = today - timedelta(days=days_since_monday)
        current_end_date = current_start_date + timedelta(days=6)

        # Previous week
        previous_start_date = current_start_date - timedelta(days=7)
        previous_end_date = previous_start_date + timedelta(days=6)

    # Convert to datetime
    current_start_dt = datetime.combine(current_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    current_end_dt = datetime.combine(current_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    previous_start_dt = datetime.combine(previous_start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    previous_end_dt = datetime.combine(previous_end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Get stats for both periods (returns PeriodStatsWithRaw)
    current_data = await _get_period_stats(
        db, current_user.id, current_start_dt, current_end_dt, current_start_date, current_end_date
    )
    previous_data = await _get_period_stats(
        db, current_user.id, previous_start_dt, previous_end_dt, previous_start_date, previous_end_date
    )

    # Calculate pace change using raw values for accuracy
    current_pace = _calculate_pace_seconds(
        current_data.raw_duration_seconds,
        current_data.raw_distance_meters,
    )
    previous_pace = _calculate_pace_seconds(
        previous_data.raw_duration_seconds,
        previous_data.raw_distance_meters,
    )

    pace_change = None
    if current_pace and previous_pace:
        pace_change = round(current_pace - previous_pace, 1)

    change = PeriodChange(
        distance_change_pct=_calculate_change_pct(
            current_data.stats.total_distance_km, previous_data.stats.total_distance_km
        ),
        duration_change_pct=_calculate_change_pct(
            current_data.stats.total_duration_hours, previous_data.stats.total_duration_hours
        ),
        activities_change=current_data.stats.total_activities - previous_data.stats.total_activities,
        pace_change_seconds=pace_change,
        elevation_change_pct=_calculate_change_pct(
            current_data.stats.total_elevation_m, previous_data.stats.total_elevation_m
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
        current_period=current_data.stats,
        previous_period=previous_data.stats,
        change=change,
        improvement_summary=summary,
    )


async def _find_previous_best(
    db: AsyncSession,
    user_id: int,
    activity_type: str,
    current_activity_id: int,
    current_activity_date: datetime,
    category: str,
    min_dist: int | None = None,
    max_dist: int | None = None,
    order_by_field: str = "duration",  # "duration", "pace", "distance"
) -> tuple[float | None, float | None]:
    """Find previous best record before the current PR activity.

    Returns:
        (previous_best_value, improvement_pct) or (None, None) if no previous record.
    """
    base_filter = [
        Activity.user_id == user_id,
        Activity.activity_type == activity_type,
        Activity.id != current_activity_id,
        Activity.start_time < current_activity_date,
    ]

    if min_dist is not None and max_dist is not None:
        base_filter.extend([
            Activity.distance_meters >= min_dist,
            Activity.distance_meters <= max_dist,
        ])

    if order_by_field == "duration":
        base_filter.append(Activity.duration_seconds.isnot(None))
        query = select(Activity).where(*base_filter).order_by(Activity.duration_seconds.asc()).limit(1)
    elif order_by_field == "distance":
        base_filter.append(Activity.distance_meters.isnot(None))
        query = select(Activity).where(*base_filter).order_by(Activity.distance_meters.desc()).limit(1)
    else:  # pace - need to calculate
        base_filter.extend([
            Activity.duration_seconds.isnot(None),
            Activity.distance_meters.isnot(None),
            Activity.distance_meters > 0,
        ])
        # For pace, we order by duration/distance (lower is better)
        query = (
            select(Activity)
            .where(*base_filter)
            .order_by((Activity.duration_seconds / Activity.distance_meters).asc())
            .limit(1)
        )

    result = await db.execute(query)
    prev_activity = result.scalar_one_or_none()

    if not prev_activity:
        return None, None

    if order_by_field == "duration":
        prev_value = prev_activity.duration_seconds
    elif order_by_field == "distance":
        prev_value = prev_activity.distance_meters
    else:  # pace
        prev_value = _calculate_pace_seconds(
            prev_activity.duration_seconds, prev_activity.distance_meters
        )

    return prev_value, None  # improvement_pct calculated by caller


@router.get("/personal-records", response_model=PersonalRecordsResponse)
async def get_personal_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    activity_type: str = Query("running", description="Activity type filter"),
) -> PersonalRecordsResponse:
    """Get personal records (PRs) for the user.

    개인 최고 기록 조회

    Categories:
        - Distance PRs: 5K, 10K, Half Marathon, Marathon 최고 기록 (시간 기준)
        - Pace PRs: 각 거리별 최고 페이스 (sec/km 기준, 낮을수록 좋음)
        - Endurance PRs: 최장 거리, 최장 시간

    Args:
        current_user: Authenticated user.
        db: Database session.
        activity_type: Filter by activity type.

    Returns:
        Personal records across various categories.
    """
    distance_records: list[PersonalRecord] = []
    pace_records: list[PersonalRecord] = []
    recent_prs: list[PersonalRecord] = []
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    for category_name, min_dist, max_dist in DISTANCE_CATEGORIES:
        # Find best time for this distance (fastest completion)
        time_result = await db.execute(
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
        best_time_activity = time_result.scalar_one_or_none()

        if best_time_activity:
            # Find previous best time
            prev_time, _ = await _find_previous_best(
                db, current_user.id, activity_type,
                best_time_activity.id, best_time_activity.start_time,
                category_name, min_dist, max_dist, "duration"
            )
            improvement_pct = None
            if prev_time and prev_time > 0:
                # For time, lower is better, so improvement is negative
                improvement_pct = round(
                    ((best_time_activity.duration_seconds - prev_time) / prev_time) * 100, 1
                )

            distance_record = PersonalRecord(
                category=category_name,
                value=best_time_activity.duration_seconds,
                unit="seconds",
                activity_id=best_time_activity.id,
                activity_name=best_time_activity.name,
                achieved_date=best_time_activity.start_time.date(),
                previous_best=prev_time,
                improvement_pct=improvement_pct,
            )
            distance_records.append(distance_record)

            # Check if this is a recent PR (within 30 days)
            # Include both: first-ever PR (no previous) and improvements over previous
            if best_time_activity.start_time >= thirty_days_ago:
                recent_prs.append(distance_record)

        # Find best pace for this distance (lowest sec/km)
        # Use a subquery approach: order by duration/distance ratio
        pace_result = await db.execute(
            select(Activity)
            .where(
                Activity.user_id == current_user.id,
                Activity.activity_type == activity_type,
                Activity.distance_meters >= min_dist,
                Activity.distance_meters <= max_dist,
                Activity.duration_seconds.isnot(None),
                Activity.distance_meters.isnot(None),
                Activity.distance_meters > 0,
            )
            .order_by((Activity.duration_seconds / Activity.distance_meters).asc())
            .limit(1)
        )
        best_pace_activity = pace_result.scalar_one_or_none()

        if best_pace_activity:
            current_pace = _calculate_pace_seconds(
                best_pace_activity.duration_seconds, best_pace_activity.distance_meters
            )

            if current_pace:
                # Find previous best pace
                prev_pace, _ = await _find_previous_best(
                    db, current_user.id, activity_type,
                    best_pace_activity.id, best_pace_activity.start_time,
                    f"{category_name} Pace", min_dist, max_dist, "pace"
                )
                improvement_pct = None
                if prev_pace and prev_pace > 0:
                    # For pace, lower is better, so improvement is negative
                    improvement_pct = round(((current_pace - prev_pace) / prev_pace) * 100, 1)

                pace_record = PersonalRecord(
                    category=f"{category_name} Pace",
                    value=round(current_pace, 1),
                    unit="sec/km",
                    activity_id=best_pace_activity.id,
                    activity_name=best_pace_activity.name,
                    achieved_date=best_pace_activity.start_time.date(),
                    previous_best=round(prev_pace, 1) if prev_pace else None,
                    improvement_pct=improvement_pct,
                )
                pace_records.append(pace_record)

                # Check if this is a recent PR
                if best_pace_activity.start_time >= thirty_days_ago and prev_pace is not None:
                    recent_prs.append(pace_record)

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
        prev_distance, _ = await _find_previous_best(
            db, current_user.id, activity_type,
            longest_activity.id, longest_activity.start_time,
            "Longest Run", order_by_field="distance"
        )
        improvement_pct = None
        if prev_distance and prev_distance > 0:
            # For distance, higher is better, so improvement is positive
            improvement_pct = round(
                ((longest_activity.distance_meters - prev_distance) / prev_distance) * 100, 1
            )

        longest_record = PersonalRecord(
            category="Longest Run",
            value=longest_activity.distance_meters,
            unit="meters",
            activity_id=longest_activity.id,
            activity_name=longest_activity.name,
            achieved_date=longest_activity.start_time.date(),
            previous_best=prev_distance,
            improvement_pct=improvement_pct,
        )
        endurance_records.append(longest_record)

        if longest_activity.start_time >= thirty_days_ago and prev_distance is not None:
            recent_prs.append(longest_record)

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
        # For longest duration, find the previous longest (highest value before current record)
        prev_result = await db.execute(
            select(Activity)
            .where(
                Activity.user_id == current_user.id,
                Activity.activity_type == activity_type,
                Activity.id != duration_activity.id,
                Activity.start_time < duration_activity.start_time,
                Activity.duration_seconds.isnot(None),
            )
            .order_by(Activity.duration_seconds.desc())
            .limit(1)
        )
        prev_activity = prev_result.scalar_one_or_none()
        prev_duration = prev_activity.duration_seconds if prev_activity else None

        improvement_pct = None
        if prev_duration and prev_duration > 0:
            improvement_pct = round(
                ((duration_activity.duration_seconds - prev_duration) / prev_duration) * 100, 1
            )

        duration_record = PersonalRecord(
            category="Longest Duration",
            value=duration_activity.duration_seconds,
            unit="seconds",
            activity_id=duration_activity.id,
            activity_name=duration_activity.name,
            achieved_date=duration_activity.start_time.date(),
            previous_best=prev_duration,
            improvement_pct=improvement_pct,
        )
        endurance_records.append(duration_record)

        if duration_activity.start_time >= thirty_days_ago and prev_duration is not None:
            recent_prs.append(duration_record)

    return PersonalRecordsResponse(
        distance_records=distance_records,
        pace_records=pace_records,
        endurance_records=endurance_records,
        recent_prs=recent_prs,
    )


# -------------------------------------------------------------------------
# VDOT Calculation
# -------------------------------------------------------------------------


class VDOTRequest(BaseModel):
    """Request for VDOT calculation."""

    distance_meters: float
    time_seconds: float


class TrainingPaceResponse(BaseModel):
    """Training pace for a specific type."""

    sec_per_km: int
    pace: str  # "M:SS" format


class TrainingPaceRangeResponse(BaseModel):
    """Training pace range (for Easy pace)."""

    min_sec_per_km: int
    max_sec_per_km: int
    min_pace: str
    max_pace: str


class TrainingPacesResponse(BaseModel):
    """All training paces."""

    easy: TrainingPaceRangeResponse
    marathon: TrainingPaceResponse
    threshold: TrainingPaceResponse
    interval: TrainingPaceResponse
    repetition: TrainingPaceResponse


class RaceEquivalentResponse(BaseModel):
    """Race time equivalent for a distance."""

    distance_name: str
    distance_km: float
    time_seconds: int
    time_formatted: str


class VDOTResponse(BaseModel):
    """VDOT calculation response."""

    vdot: float
    training_paces: TrainingPacesResponse
    race_equivalents: list[RaceEquivalentResponse]


@router.get("/vdot", response_model=VDOTResponse)
async def calculate_vdot_from_race(
    current_user: Annotated[User, Depends(get_current_user)],
    distance_meters: float = Query(..., gt=0, description="Race distance in meters"),
    time_seconds: float = Query(..., gt=0, description="Race time in seconds"),
) -> VDOTResponse:
    """Calculate VDOT and training paces from a race result.

    VDOT은 Jack Daniels 박사의 러닝 공식에 기반한 체력 지표입니다.
    레이스 기록을 입력하면 VDOT과 각 훈련 유형별 적정 페이스를 계산합니다.

    Training Pace Types:
        - Easy: 편안한 조깅 (VO2max 59-74%)
        - Marathon: 마라톤 레이스 페이스 (VO2max 75-84%)
        - Threshold: 젖산역치 훈련 (VO2max 83-88%)
        - Interval: VO2max 훈련 (VO2max 97-100%)
        - Repetition: 스피드 훈련 (1500m 레이스 페이스)

    Examples:
        GET /analytics/vdot?distance_meters=5000&time_seconds=1200  # 5K 20분
        GET /analytics/vdot?distance_meters=10000&time_seconds=2700  # 10K 45분
        GET /analytics/vdot?distance_meters=42195&time_seconds=12600  # 마라톤 3:30

    Args:
        current_user: Authenticated user.
        distance_meters: Race distance in meters.
        time_seconds: Race time in seconds.

    Returns:
        VDOT value, training paces, and race equivalents.
    """
    from app.services.vdot import get_vdot_result

    result = get_vdot_result(distance_meters, time_seconds)
    result_dict = result.to_dict()

    # Convert to response model format
    paces = result_dict["training_paces"]

    return VDOTResponse(
        vdot=result_dict["vdot"],
        training_paces=TrainingPacesResponse(
            easy=TrainingPaceRangeResponse(**paces["easy"]),
            marathon=TrainingPaceResponse(**paces["marathon"]),
            threshold=TrainingPaceResponse(**paces["threshold"]),
            interval=TrainingPaceResponse(**paces["interval"]),
            repetition=TrainingPaceResponse(**paces["repetition"]),
        ),
        race_equivalents=[
            RaceEquivalentResponse(**eq) for eq in result_dict["race_equivalents"]
        ],
    )
