"""Dashboard data service.

Provides aggregated data for dashboard, trends, and analytics views.
"""

import logging
import math
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, and_, desc
from sqlalchemy.orm import Session

from zoneinfo import ZoneInfo

from app.models.activity import Activity
from app.models.analytics import AnalyticsSummary
from app.models.health import Sleep, HRRecord, FitnessMetricDaily
from app.models.user import User

logger = logging.getLogger(__name__)


class DashboardService:
    """Service for dashboard data aggregation."""

    def __init__(self, db: Session, user_id: int):
        """Initialize dashboard service.

        Args:
            db: Database session.
            user_id: User ID.
        """
        self.db = db
        self.user_id = user_id
        self._user: Optional[User] = None

    @property
    def user(self) -> User:
        """Get user with HR settings."""
        if self._user is None:
            self._user = self.db.execute(
                select(User).where(User.id == self.user_id)
            ).scalar_one()
        return self._user

    @property
    def user_tz(self) -> ZoneInfo:
        """Get user's timezone (default: Asia/Seoul)."""
        return ZoneInfo(self.user.timezone or "Asia/Seoul")

    @property
    def max_hr(self) -> int:
        """Get user's max HR (default: 185 if not set)."""
        return self.user.max_hr or 185

    @property
    def resting_hr(self) -> int:
        """Get user's resting HR (default: 50 if not set)."""
        return self.user.resting_hr or 50

    @property
    def gender_factor(self) -> float:
        """Get gender-specific TRIMP weighting factor.

        Banister's formula uses different exponents:
        - Male: 1.92
        - Female: 1.67
        """
        return 1.67 if self.user.gender == "female" else 1.92

    def get_summary(
        self,
        period: str = "week",
        target_date: Optional[date] = None,
    ) -> dict:
        """Get dashboard summary.

        Args:
            period: 'week' or 'month'.
            target_date: Reference date (defaults to today in user's timezone).

        Returns:
            Dashboard summary dict.
        """
        # Use user's timezone for determining "today"
        if target_date is None:
            now_local = datetime.now(self.user_tz)
            target_date = now_local.date()

        # Calculate period boundaries in user's timezone
        start, end = self._get_period_boundaries(period, target_date)

        # Get activities in period
        activities = self._get_activities_in_range(start, end)

        # Calculate summary stats
        summary = self._calculate_summary_stats(activities)

        # Save to analytics_summaries for caching (only for completed periods)
        if end < date.today():
            self._save_analytics_summary(period, start, end, activities, summary)

        # Get recent activities (last 5)
        recent = self._get_recent_activities(limit=5)

        # Get health status
        health_status = self._get_health_status(target_date)

        # Get fitness status (CTL/ATL/TSB)
        fitness_status = self._get_fitness_status(target_date)

        # Get upcoming workouts
        upcoming = self._get_upcoming_workouts(target_date, limit=3)

        return {
            "period_type": period,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "summary": summary,
            "recent_activities": recent,
            "health_status": health_status,
            "fitness_status": fitness_status,
            "upcoming_workouts": upcoming,
        }

    def _get_period_boundaries(
        self,
        period: str,
        target_date: date,
    ) -> tuple[date, date]:
        """Calculate period start/end dates using user's timezone.

        Args:
            period: 'week' or 'month'.
            target_date: Reference date (in user's timezone).

        Returns:
            Tuple of (start_date, end_date).
        """
        if period == "week":
            # ISO week: Monday to Sunday
            start = target_date - timedelta(days=target_date.weekday())
            end = start + timedelta(days=6)
        else:  # month
            start = target_date.replace(day=1)
            next_month = start.replace(day=28) + timedelta(days=4)
            end = next_month - timedelta(days=next_month.day)

        return start, end

    def _save_analytics_summary(
        self,
        period_type: str,
        start: date,
        end: date,
        activities: list[Activity],
        summary: dict,
    ) -> Optional[AnalyticsSummary]:
        """Save or update analytics summary for a period.

        Args:
            period_type: 'week' or 'month'.
            start: Period start date.
            end: Period end date.
            activities: Activities in the period.
            summary: Pre-calculated summary stats.

        Returns:
            The created/updated AnalyticsSummary record.
        """
        # Calculate TRIMP for the period
        total_trimp = sum(self._calculate_trimp(a) for a in activities)

        # Build summary_data for extra metrics
        summary_data = {
            "elevation_gain": summary.get("total_elevation_m", 0),
            "avg_pace_per_km": summary.get("avg_pace_per_km"),
        }

        # Check for existing record
        existing = self.db.execute(
            select(AnalyticsSummary).where(
                AnalyticsSummary.user_id == self.user_id,
                AnalyticsSummary.period_type == period_type,
                AnalyticsSummary.period_start == start,
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing record
            existing.period_end = end
            existing.total_activities = summary.get("total_activities", 0)
            existing.total_distance_meters = (
                summary.get("total_distance_km", 0) * 1000
            )
            existing.total_duration_seconds = int(
                summary.get("total_duration_hours", 0) * 3600
            )
            existing.total_calories = summary.get("total_calories", 0)
            existing.avg_pace_seconds = self._parse_pace_to_seconds(
                summary.get("avg_pace_per_km")
            )
            existing.avg_hr = summary.get("avg_hr")
            existing.total_trimp = round(total_trimp, 1)
            existing.summary_data = summary_data
            self.db.flush()
            logger.debug(
                f"Updated AnalyticsSummary for user {self.user_id} "
                f"{period_type} {start}"
            )
            return existing
        else:
            # Create new record
            record = AnalyticsSummary(
                user_id=self.user_id,
                period_type=period_type,
                period_start=start,
                period_end=end,
                total_activities=summary.get("total_activities", 0),
                total_distance_meters=(
                    summary.get("total_distance_km", 0) * 1000
                ),
                total_duration_seconds=int(
                    summary.get("total_duration_hours", 0) * 3600
                ),
                total_calories=summary.get("total_calories", 0),
                avg_pace_seconds=self._parse_pace_to_seconds(
                    summary.get("avg_pace_per_km")
                ),
                avg_hr=summary.get("avg_hr"),
                total_trimp=round(total_trimp, 1),
                summary_data=summary_data,
            )
            self.db.add(record)
            self.db.flush()
            logger.debug(
                f"Created AnalyticsSummary for user {self.user_id} "
                f"{period_type} {start}"
            )
            return record

    def _parse_pace_to_seconds(self, pace_str: Optional[str]) -> Optional[int]:
        """Parse pace string (e.g., '5:30/km') to total seconds.

        Args:
            pace_str: Pace string in format 'M:SS/km'.

        Returns:
            Total seconds, or None if invalid.
        """
        if not pace_str:
            return None
        try:
            # Remove '/km' suffix and split
            pace_clean = pace_str.replace("/km", "")
            parts = pace_clean.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            pass
        return None

    def get_trends(self, weeks: int = 12) -> dict:
        """Get trend data for charts.

        Args:
            weeks: Number of weeks to include.

        Returns:
            Trend data dict.
        """
        # Use user's timezone for determining "today"
        now_local = datetime.now(self.user_tz)
        end_date = now_local.date()
        start_date = end_date - timedelta(weeks=weeks)

        # Weekly distance
        weekly_distance = self._get_weekly_metric(
            start_date, end_date, "distance_meters"
        )

        # Weekly duration
        weekly_duration = self._get_weekly_metric(
            start_date, end_date, "duration_seconds"
        )

        # Average pace (per week)
        avg_pace = self._get_weekly_avg_pace(start_date, end_date)

        # Resting heart rate
        resting_hr = self._get_daily_metric(
            start_date, end_date, HRRecord, "resting_hr"
        )

        # CTL/ATL/TSB over time
        ctl_atl = self._get_fitness_trend(start_date, end_date)

        return {
            "weekly_distance": weekly_distance,
            "weekly_duration": weekly_duration,
            "avg_pace": avg_pace,
            "resting_hr": resting_hr,
            "ctl_atl": ctl_atl,
        }

    def compare_periods(
        self,
        period: str = "week",
        target_date: Optional[date] = None,
    ) -> dict:
        """Compare current period to previous period.

        Args:
            period: 'week' or 'month'.
            target_date: Reference date (defaults to today in user's timezone).

        Returns:
            Comparison dict.
        """
        # Use user's timezone for determining "today"
        if target_date is None:
            now_local = datetime.now(self.user_tz)
            target_date = now_local.date()

        # Calculate period boundaries using shared method
        current_start, current_end = self._get_period_boundaries(period, target_date)

        if period == "week":
            previous_start = current_start - timedelta(weeks=1)
            previous_end = current_end - timedelta(weeks=1)
        else:
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end.replace(day=1)

        current_activities = self._get_activities_in_range(current_start, current_end)
        previous_activities = self._get_activities_in_range(previous_start, previous_end)

        current_stats = self._calculate_period_stats(current_activities, current_start, current_end)
        previous_stats = self._calculate_period_stats(previous_activities, previous_start, previous_end)

        # Calculate changes
        change = self._calculate_change(current_stats, previous_stats)

        # Generate summary
        summary = self._generate_improvement_summary(change)

        return {
            "current_period": current_stats,
            "previous_period": previous_stats,
            "change": change,
            "improvement_summary": summary,
        }

    def get_personal_records(self, activity_type: str = "running") -> dict:
        """Get personal records.

        Args:
            activity_type: Filter by activity type.

        Returns:
            Personal records dict.
        """
        # Distance records (5K, 10K, Half, Full)
        distance_records = self._get_distance_records(activity_type)

        # Pace records
        pace_records = self._get_pace_records(activity_type)

        # Endurance records
        endurance_records = self._get_endurance_records(activity_type)

        # Recent PRs
        recent_prs = self._get_recent_prs(activity_type, limit=5)

        return {
            "distance_records": distance_records,
            "pace_records": pace_records,
            "endurance_records": endurance_records,
            "recent_prs": recent_prs,
        }

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _get_activities_in_range(
        self,
        start_date: date,
        end_date: date,
        activity_type: Optional[str] = None,
    ) -> list[Activity]:
        """Get activities within date range."""
        query = select(Activity).where(
            Activity.user_id == self.user_id,
            func.date(Activity.start_time) >= start_date,
            func.date(Activity.start_time) <= end_date,
        )

        if activity_type:
            query = query.where(Activity.activity_type == activity_type)

        query = query.order_by(Activity.start_time.desc())

        return list(self.db.execute(query).scalars().all())

    def _get_recent_activities(self, limit: int = 5) -> list[dict]:
        """Get most recent activities."""
        query = (
            select(Activity)
            .where(Activity.user_id == self.user_id)
            .order_by(Activity.start_time.desc())
            .limit(limit)
        )

        activities = self.db.execute(query).scalars().all()

        return [
            {
                "id": a.id,
                "name": a.name,
                "activity_type": a.activity_type,
                "start_time": a.start_time.isoformat() if a.start_time else None,
                "distance_km": round(a.distance_meters / 1000, 2) if a.distance_meters else None,
                "duration_minutes": round(a.duration_seconds / 60) if a.duration_seconds else None,
                "avg_hr": a.avg_hr,
            }
            for a in activities
        ]

    def _calculate_summary_stats(self, activities: list[Activity]) -> dict:
        """Calculate summary statistics for activities."""
        if not activities:
            return {
                "total_distance_km": 0,
                "total_duration_hours": 0,
                "total_activities": 0,
                "avg_pace_per_km": None,
                "avg_hr": None,
                "total_elevation_m": 0,
                "total_calories": 0,
            }

        total_distance = sum(a.distance_meters or 0 for a in activities)
        total_duration = sum(a.duration_seconds or 0 for a in activities)
        total_elevation = sum(a.elevation_gain or 0 for a in activities)
        total_calories = sum(a.calories or 0 for a in activities)

        # Average pace
        if total_distance > 0:
            avg_pace_seconds = (total_duration / total_distance) * 1000
            pace_min = int(avg_pace_seconds // 60)
            pace_sec = int(avg_pace_seconds % 60)
            avg_pace = f"{pace_min}:{pace_sec:02d}/km"
        else:
            avg_pace = None

        # Average HR (weighted by duration)
        hr_weighted = sum(
            (a.avg_hr or 0) * (a.duration_seconds or 0)
            for a in activities
            if a.avg_hr
        )
        hr_duration = sum(
            a.duration_seconds or 0
            for a in activities
            if a.avg_hr
        )
        avg_hr = round(hr_weighted / hr_duration) if hr_duration > 0 else None

        return {
            "total_distance_km": round(total_distance / 1000, 1),
            "total_duration_hours": round(total_duration / 3600, 1),
            "total_activities": len(activities),
            "avg_pace_per_km": avg_pace,
            "avg_hr": avg_hr,
            "total_elevation_m": round(total_elevation),
            "total_calories": round(total_calories),
        }

    def _get_health_status(self, target_date: date) -> dict:
        """Get latest health metrics."""
        # Get most recent sleep
        sleep = self.db.execute(
            select(Sleep)
            .where(
                Sleep.user_id == self.user_id,
                Sleep.date <= target_date,
            )
            .order_by(Sleep.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Get most recent HR
        hr = self.db.execute(
            select(HRRecord)
            .where(
                HRRecord.user_id == self.user_id,
            )
            .order_by(HRRecord.start_time.desc())
            .limit(1)
        ).scalar_one_or_none()

        return {
            "latest_sleep_score": sleep.score if sleep else None,
            "latest_sleep_hours": round(sleep.duration_seconds / 3600, 1) if sleep and sleep.duration_seconds else None,
            "resting_hr": hr.resting_hr if hr else None,
            "body_battery": None,  # TODO: Add body battery tracking
            "vo2max": self._get_latest_vo2max(),
        }

    def _get_latest_vo2max(self) -> Optional[float]:
        """Get latest VO2max from activities."""
        activity = self.db.execute(
            select(Activity)
            .where(
                Activity.user_id == self.user_id,
                Activity.vo2max.isnot(None),
            )
            .order_by(Activity.start_time.desc())
            .limit(1)
        ).scalar_one_or_none()

        return activity.vo2max if activity else None

    def _get_fitness_status(self, target_date: date) -> dict:
        """Get fitness metrics (CTL/ATL/TSB).

        Always calculate in real-time using user's current HR settings
        for accurate Runalyze-compatible results.
        """
        # Always calculate from activities for accurate, real-time results
        return self._calculate_fitness_metrics(target_date)

    def _calculate_fitness_metrics(self, target_date: date) -> dict:
        """Calculate fitness metrics from activities (Runalyze method).

        Uses all historical activities to properly converge the EMA.
        CTL uses 42-day time constant, ATL uses 7-day time constant.

        Returns both absolute values and percentages (relative to all-time max),
        which matches how Runalyze displays these metrics.
        """
        # Get ALL activities (no lookback limit for proper EMA convergence)
        # Query from the earliest possible date
        earliest_possible = date(2020, 1, 1)  # Reasonable floor
        activities = self._get_activities_in_range(earliest_possible, target_date)

        # Build daily load dictionary
        daily_loads: dict[date, float] = {}
        for a in activities:
            if a.start_time:
                d = a.start_time.date()
                daily_loads[d] = daily_loads.get(d, 0) + self._calculate_trimp(a)

        if not daily_loads:
            return {
                "ctl": 0.0,
                "atl": 0.0,
                "tsb": 0.0,
                "ctl_percent": 0.0,
                "atl_percent": 0.0,
                "weekly_trimp": 0,
                "weekly_tss": None,
                "marathon_shape": None,
            }

        # Weekly TRIMP
        week_start = target_date - timedelta(days=6)
        weekly_trimp = sum(
            load for d, load in daily_loads.items()
            if d >= week_start
        )

        # Calculate CTL/ATL for target_date and find all-time max
        ctl, atl, max_ctl, max_atl = self._calculate_ctl_atl_with_max(
            daily_loads, target_date
        )
        tsb = ctl - atl

        # Calculate percentages (Runalyze-style display)
        ctl_percent = (ctl / max_ctl * 100) if max_ctl > 0 else 0.0
        atl_percent = (atl / max_atl * 100) if max_atl > 0 else 0.0

        # Calculate ACWR (Acute:Chronic Workload Ratio)
        # ACWR = ATL / CTL
        # Ideal range: 0.8 - 1.3 (injury risk increases outside this range)
        workload_ratio = (atl / ctl) if ctl > 0 else None

        # Calculate Marathon Shape (Runalyze-style)
        marathon_shape = self._calculate_marathon_shape(activities, target_date)

        return {
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
            "ctl_percent": round(ctl_percent, 1),
            "atl_percent": round(atl_percent, 1),
            "max_ctl": round(max_ctl, 1),
            "max_atl": round(max_atl, 1),
            "weekly_trimp": round(weekly_trimp),
            "weekly_tss": None,
            "workload_ratio": round(workload_ratio, 2) if workload_ratio is not None else None,
            "marathon_shape": marathon_shape,
        }

    def _calculate_ctl_atl_with_max(
        self,
        daily_loads: dict[date, float],
        target_date: date,
    ) -> tuple[float, float, float, float]:
        """Calculate CTL/ATL for target_date and find all-time max values.

        Args:
            daily_loads: Dictionary of date -> TRIMP load
            target_date: The date to calculate metrics for

        Returns:
            Tuple of (ctl, atl, max_ctl, max_atl)
        """
        earliest = min(daily_loads.keys())

        decay_42 = 1 - math.exp(-1 / 42)
        decay_7 = 1 - math.exp(-1 / 7)

        ctl = 0.0
        atl = 0.0
        max_ctl = 0.0
        max_atl = 0.0

        current = earliest
        while current <= target_date:
            load = daily_loads.get(current, 0)
            ctl = ctl + decay_42 * (load - ctl)
            atl = atl + decay_7 * (load - atl)

            # Track all-time maximums
            if ctl > max_ctl:
                max_ctl = ctl
            if atl > max_atl:
                max_atl = atl

            current += timedelta(days=1)

        return ctl, atl, max_ctl, max_atl

    def _calculate_marathon_shape(
        self,
        activities: list[Activity],
        target_date: date,
    ) -> Optional[float]:
        """Calculate Marathon Shape (Runalyze-style).

        Marathon Shape adjusts marathon prognoses for endurance readiness.
        Based on Runalyze's algorithm:
        - Weekly mileage achievement (2/3 weight) - 182 days period
        - Long run achievement (1/3 weight) - 70 days period with time-decay + distance² weighting

        Target values are based on VO2max-predicted marathon time.

        Returns:
            Marathon Shape as percentage (0-100+), or None if insufficient data.
        """
        import math

        # Get latest VO2max from activities
        vo2max = None
        for a in sorted(activities, key=lambda x: x.start_time or datetime.min, reverse=True):
            if a.vo2max:
                vo2max = a.vo2max
                break

        if not vo2max:
            vo2max = 50.0  # Default VO2max

        # Calculate target marathon time from VO2max
        predicted_marathon_minutes = self._estimate_marathon_time_from_vo2max(vo2max)

        # Target weekly distance based on marathon goal
        target_weekly_km = self._get_target_weekly_km(predicted_marathon_minutes)

        # Target long run: based on marathon time (Runalyze uses ~39% of weekly for sub-3:30)
        target_long_run_km = self._get_target_long_run_km(predicted_marathon_minutes)

        # === Weekly Mileage Calculation (182 days) ===
        weekly_period_start = target_date - timedelta(days=182)

        # Filter running activities for weekly calculation
        running_activities_weekly = [
            a for a in activities
            if a.start_time
            and a.start_time.date() >= weekly_period_start
            and a.start_time.date() <= target_date
            and a.activity_type in ("running", "trail_running", "treadmill_running", "track_running")
        ]

        if not running_activities_weekly:
            return None

        # Build weekly data
        weekly_distances: dict[int, float] = {}

        for a in running_activities_weekly:
            if not a.start_time or not a.distance_meters:
                continue

            week_key = a.start_time.isocalendar()[1] + a.start_time.isocalendar()[0] * 100
            distance_km = a.distance_meters / 1000.0
            weekly_distances[week_key] = weekly_distances.get(week_key, 0) + distance_km

        if not weekly_distances:
            return None

        avg_weekly_km = sum(weekly_distances.values()) / len(weekly_distances)

        # === Long Run Calculation (70 days with time-decay + distance² weighting) ===
        long_run_period_start = target_date - timedelta(days=70)

        running_activities_longrun = [
            a for a in activities
            if a.start_time
            and a.start_time.date() >= long_run_period_start
            and a.start_time.date() <= target_date
            and a.activity_type in ("running", "trail_running", "treadmill_running", "track_running")
            and a.distance_meters and a.distance_meters >= 15000  # Only runs >= 15km count as long runs
        ]

        # Calculate weighted long run score using Runalyze-style formula
        # weight = distance² × time_decay (recent runs count more)
        weighted_sum = 0.0
        weight_sum = 0.0

        for a in running_activities_longrun:
            if not a.start_time or not a.distance_meters:
                continue

            distance_km = a.distance_meters / 1000.0
            days_ago = (target_date - a.start_time.date()).days

            # Time decay: exponential decay over 70 days (half-life ~35 days)
            time_decay = math.exp(-days_ago / 35.0)

            # Distance² weighting: 30km counts much more than 20km
            distance_weight = distance_km ** 2

            # Combined weight
            weight = distance_weight * time_decay

            weighted_sum += distance_km * weight
            weight_sum += weight

        # Effective long run distance (weighted average)
        if weight_sum > 0:
            effective_long_run_km = weighted_sum / weight_sum
        else:
            # Fallback: use max long run from last 70 days
            max_long_run = 0.0
            for a in running_activities_longrun:
                if a.distance_meters:
                    max_long_run = max(max_long_run, a.distance_meters / 1000.0)
            effective_long_run_km = max_long_run

        # Calculate achievements (capped at 150%)
        weekly_achievement = min(150.0, (avg_weekly_km / target_weekly_km) * 100) if target_weekly_km > 0 else 0
        long_run_achievement = min(150.0, (effective_long_run_km / target_long_run_km) * 100) if target_long_run_km > 0 else 0

        # Marathon Shape = (Weekly * 2/3) + (Long Run * 1/3)
        marathon_shape = (weekly_achievement * 2 / 3) + (long_run_achievement * 1 / 3)

        return round(marathon_shape, 1)

    def _get_target_long_run_km(self, marathon_minutes: float) -> float:
        """Get target long run distance based on marathon goal time.

        Based on Runalyze's targets:
        - Sub 3:00 marathon: ~32km long run
        - 3:00-3:30: ~29km
        - 3:30-4:00: ~26km
        - 4:00-4:30: ~23km
        - 4:30+: ~20km
        """
        if marathon_minutes <= 180:
            return 32.0
        elif marathon_minutes <= 210:
            return 29.0
        elif marathon_minutes <= 240:
            return 26.0
        elif marathon_minutes <= 270:
            return 23.0
        else:
            return 20.0

    def _estimate_marathon_time_from_vo2max(self, vo2max: float) -> float:
        """Estimate marathon time (minutes) from VO2max.

        Uses Runalyze-style formula for consistency:
        - VO2max 44.70 → Marathon 3:29:24 (209 min)
        - VO2max 52 → Marathon ~3:00 (180 min)

        Linear interpolation: time = 470 - 5.85 * VO2max
        (Derived from Runalyze data points)
        """
        if vo2max <= 0:
            return 300.0

        # Runalyze-aligned formula
        # VO2max 44.70 → 209 min (3:29)
        # VO2max 52 → 166 min (2:46) but this seems too fast
        # More conservative: VO2max 50 → 200 min, VO2max 45 → 230 min
        # time = 430 - 4.6 * VO2max
        predicted_time = 430.0 - (vo2max * 4.6)
        return max(120.0, min(360.0, predicted_time))

    def _get_target_weekly_km(self, marathon_minutes: float) -> float:
        """Get target weekly training volume based on marathon goal.

        Based on Runalyze's targets:
        - Sub 3:00 (< 180 min): 110+ km/week
        - 3:00-3:30 (180-210 min): 80-90 km/week
        - 3:30-4:00 (210-240 min): 70-75 km/week
        - 4:00-4:30 (240-270 min): 55-65 km/week
        - 4:30+ (> 270 min): 45-55 km/week
        """
        if marathon_minutes <= 180:
            return 110.0
        elif marathon_minutes <= 195:
            return 90.0
        elif marathon_minutes <= 210:
            return 80.0  # Runalyze: 3:29 → 75km
        elif marathon_minutes <= 225:
            return 75.0
        elif marathon_minutes <= 240:
            return 70.0
        elif marathon_minutes <= 255:
            return 60.0
        elif marathon_minutes <= 270:
            return 55.0
        else:
            return 45.0

    def calculate_training_paces(self, vo2max: Optional[float] = None) -> Optional[dict]:
        """Calculate Daniels' Running Formula training paces.

        Priority:
        1. VDOT calculated from best segment times in last 6 weeks
        2. VO2max from activities as fallback

        Args:
            vo2max: VO2max value override. If None, calculates VDOT from segments.

        Returns:
            Dict with VDOT and pace ranges, or None if no data available.
        """
        # Try to calculate VDOT from recent best segment times
        vdot = self._calculate_vdot_from_segments()

        # Fallback to VO2max if no segment data
        if vdot is None:
            if vo2max is None:
                result = self.db.execute(
                    select(Activity.vo2max)
                    .where(
                        Activity.user_id == self.user_id,
                        Activity.vo2max.isnot(None),
                    )
                    .order_by(Activity.start_time.desc())
                    .limit(1)
                )
                vo2max = result.scalar_one_or_none()

            if vo2max and vo2max > 0:
                vdot = vo2max

        if not vdot or vdot <= 0:
            return None

        # Calculate paces using Daniels' VDOT tables approximation
        # Returns pace in seconds per km (int) to match TrainingPaces schema
        #
        # Based on Jack Daniels' Running Formula VDOT pace tables:
        # Reference values for VDOT 52 from fellrnr.com:
        # - Easy (E): 4:47 - 5:23/km (287-323 sec)
        # - Marathon (M): 4:22/km (262 sec)
        # - Threshold (T): 4:07/km (247 sec)
        # - Interval (I): 3:47/km (227 sec, from 1000m pace)
        # - Repetition (R): 3:30/km (210 sec, from 200m pace)

        # Easy pace: conversational, recovery runs
        # VDOT 52 reference: 4:47 - 5:23/km
        easy_pace = self._daniels_pace_from_vdot(vdot, intensity=0.72)
        easy_min = int(round(easy_pace * 1.12))  # Slower end ~5:23/km
        easy_max = int(round(easy_pace * 0.98))  # Faster end ~4:47/km

        # Marathon pace: race pace for marathon
        # VDOT 52 reference: 4:22/km
        marathon_pace = self._daniels_pace_from_vdot(vdot, intensity=0.82)
        marathon_min = int(round(marathon_pace * 1.01))
        marathon_max = int(round(marathon_pace * 0.99))

        # Threshold (Tempo) pace: lactate threshold
        # VDOT 52 reference: 4:07/km
        threshold_pace = self._daniels_pace_from_vdot(vdot, intensity=0.88)
        threshold_min = int(round(threshold_pace * 1.01))
        threshold_max = int(round(threshold_pace * 0.99))

        # Interval pace: VO2max development (3-5 min intervals)
        # VDOT 52 reference: 3:47/km
        interval_pace = self._daniels_pace_from_vdot(vdot, intensity=0.97)
        interval_min = int(round(interval_pace * 1.01))
        interval_max = int(round(interval_pace * 0.99))

        # Repetition pace: speed work (200-400m repeats)
        # VDOT 52 reference: 3:30/km
        rep_pace = self._daniels_pace_from_vdot(vdot, intensity=1.05)
        rep_min = int(round(rep_pace * 1.01))
        rep_max = int(round(rep_pace * 0.99))

        return {
            "vdot": round(vdot, 1),
            "easy_min": easy_min,
            "easy_max": easy_max,
            "marathon_min": marathon_min,
            "marathon_max": marathon_max,
            "threshold_min": threshold_min,
            "threshold_max": threshold_max,
            "interval_min": interval_min,
            "interval_max": interval_max,
            "repetition_min": rep_min,
            "repetition_max": rep_max,
        }

    def _daniels_pace_from_vdot(self, vdot: float, intensity: float) -> float:
        """Calculate pace (seconds per km) from VDOT and intensity.

        Uses Daniels' formula approximation:
        velocity (m/min) ≈ 29.54 + 5.000663 × VO2 - 0.007546 × VO2²

        For different intensities, we scale the VO2 used.

        Args:
            vdot: VDOT value (≈VO2max)
            intensity: Fraction of VO2max (0.65 for easy, 0.98 for interval, etc.)

        Returns:
            Pace in seconds per kilometer.
        """
        # Effective VO2 at this intensity
        effective_vo2 = vdot * intensity

        # Daniels' velocity formula (m/min)
        # This is derived from the relationship between VO2 and running velocity
        velocity_m_per_min = 29.54 + 5.000663 * effective_vo2 - 0.007546 * (effective_vo2 ** 2)

        # Ensure positive velocity
        if velocity_m_per_min <= 0:
            velocity_m_per_min = 100  # Fallback to ~10 min/km

        # Convert to seconds per km
        pace_sec_per_km = (1000 / velocity_m_per_min) * 60

        return pace_sec_per_km

    def _format_pace(self, seconds_per_km: float) -> str:
        """Format pace as 'M:SS/km' string.

        Args:
            seconds_per_km: Pace in seconds per kilometer.

        Returns:
            Formatted pace string (e.g., '5:30/km').
        """
        total_seconds = int(round(seconds_per_km))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}/km"

    def _calculate_vdot_from_segments(self) -> Optional[float]:
        """Calculate VDOT from best segment times in last 6 weeks.

        Uses Daniels-Gilbert formula to convert race/segment times to VDOT.
        Looks at laps that are close to standard distances (400m, 1km, 5km, etc.)
        and finds the best performances.

        Returns:
            VDOT value or None if insufficient data.
        """
        from app.models.activity import ActivityLap

        # Look back 6 weeks
        six_weeks_ago = datetime.now(ZoneInfo("UTC")) - timedelta(weeks=6)

        # Get all laps from running activities in last 6 weeks
        result = self.db.execute(
            select(ActivityLap)
            .join(Activity)
            .where(
                Activity.user_id == self.user_id,
                Activity.start_time >= six_weeks_ago,
                Activity.activity_type.in_(["running", "track_running", "treadmill_running"]),
                ActivityLap.distance_meters.isnot(None),
                ActivityLap.duration_seconds.isnot(None),
                ActivityLap.distance_meters > 200,  # Minimum 200m
            )
        )
        laps = result.scalars().all()

        if not laps:
            return None

        # Standard distances to look for (in meters)
        # Each tuple: (distance, tolerance_meters, min_time_seconds)
        target_distances = [
            (400, 50, 60),      # 400m ± 50m, min 1 min
            (800, 100, 120),    # 800m ± 100m, min 2 min
            (1000, 100, 150),   # 1km ± 100m, min 2:30
            (1609, 150, 240),   # Mile ± 150m, min 4 min
            (3000, 200, 480),   # 3km ± 200m, min 8 min
            (5000, 300, 900),   # 5km ± 300m, min 15 min
            (10000, 500, 1800), # 10km ± 500m, min 30 min
        ]

        # Find best performances for each distance
        best_vdots = []

        for target_dist, tolerance, min_time in target_distances:
            best_time = None
            best_distance = None

            for lap in laps:
                if lap.distance_meters is None or lap.duration_seconds is None:
                    continue

                # Check if lap is within tolerance of target distance
                if abs(lap.distance_meters - target_dist) <= tolerance:
                    # Check minimum time (to filter out erroneous data)
                    if lap.duration_seconds >= min_time:
                        # Normalize time to exact target distance
                        normalized_time = (lap.duration_seconds / lap.distance_meters) * target_dist

                        if best_time is None or normalized_time < best_time:
                            best_time = normalized_time
                            best_distance = target_dist

            if best_time and best_distance:
                # Calculate VDOT from this performance
                vdot = self._vdot_from_time(best_distance, best_time)
                if vdot and 30 <= vdot <= 85:  # Reasonable VDOT range
                    best_vdots.append(vdot)
                    logger.debug(f"VDOT from {best_distance}m in {best_time:.0f}s: {vdot:.1f}")

        if not best_vdots:
            return None

        # Return the highest VDOT (best performance)
        max_vdot = max(best_vdots)
        logger.info(f"Best VDOT from segments: {max_vdot:.1f} (from {len(best_vdots)} distances)")
        return max_vdot

    def _vdot_from_time(self, distance_meters: float, time_seconds: float) -> Optional[float]:
        """Calculate VDOT from race/segment time using Daniels-Gilbert formula.

        Formula:
        VDOT = O2cost / %VO2max

        Where:
        - O2cost = -4.6 + 0.182258 × V + 0.000104 × V²
        - %VO2max = 0.8 + 0.1894393 × e^(-0.012778×t) + 0.2989558 × e^(-0.1932605×t)
        - V = velocity in meters per minute
        - t = time in minutes

        Args:
            distance_meters: Distance in meters
            time_seconds: Time in seconds

        Returns:
            VDOT value or None if invalid input
        """
        if distance_meters <= 0 or time_seconds <= 0:
            return None

        # Convert to meters per minute and minutes
        time_minutes = time_seconds / 60
        velocity = distance_meters / time_minutes  # m/min

        # Oxygen cost (VO2 at this velocity)
        o2_cost = -4.6 + 0.182258 * velocity + 0.000104 * (velocity ** 2)

        # Percent of VO2max sustainable for this duration
        # Uses exponential decay model
        pct_max = (
            0.8
            + 0.1894393 * math.exp(-0.012778 * time_minutes)
            + 0.2989558 * math.exp(-0.1932605 * time_minutes)
        )

        if pct_max <= 0:
            return None

        # VDOT = O2cost / %VO2max
        vdot = o2_cost / pct_max

        return round(vdot, 1)

    def _calculate_full_ema(
        self,
        daily_loads: dict[date, float],
        target_date: date,
        time_constant: int,
    ) -> float:
        """Calculate EMA iteratively from the earliest data point.

        This matches Runalyze's calculation method where EMA builds up
        over time from the first activity.

        Args:
            daily_loads: Dictionary of date -> TRIMP load
            target_date: The date to calculate EMA for
            time_constant: 42 for CTL, 7 for ATL

        Returns:
            The EMA value for target_date
        """
        if not daily_loads:
            return 0.0

        # Find the earliest date with data
        earliest_date = min(daily_loads.keys())

        # Decay factor (lambda = 1 - e^(-1/τ))
        # This is the standard EMA decay formula used by Runalyze
        decay = 1 - math.exp(-1 / time_constant)

        ema = 0.0
        current_date = earliest_date

        while current_date <= target_date:
            load = daily_loads.get(current_date, 0)
            ema = ema + decay * (load - ema)
            current_date += timedelta(days=1)

        return ema

    def _calculate_trimp(self, activity: Activity) -> float:
        """Calculate TRIMP for an activity using Banister's method.

        TRIMP = duration (min) * HRreserve * 0.64 * e^(gender_factor * HRr)

        Uses user's actual max_hr, resting_hr, and gender for accurate calculation.
        This matches sync_service.py and Runalyze's TRIMP calculation method.
        """
        if not activity.duration_seconds or not activity.avg_hr:
            return 0

        duration_min = activity.duration_seconds / 60

        # Use user's actual HR values
        max_hr = self.max_hr
        rest_hr = self.resting_hr

        # Heart rate reserve ratio
        hr_reserve = (activity.avg_hr - rest_hr) / (max_hr - rest_hr)
        hr_reserve = max(0, min(1, hr_reserve))  # Clamp to 0-1

        # Banister's exponential weighting with gender-specific factor
        # Male: 0.64 * e^(1.92 * HRr), Female: 0.64 * e^(1.67 * HRr)
        # Uses user's gender setting (defaults to male if not set)
        weighting = 0.64 * math.exp(self.gender_factor * hr_reserve)

        return duration_min * hr_reserve * weighting

    def _calculate_ema(
        self,
        daily_loads: dict[date, float],
        target_date: date,
        days: int,
    ) -> float:
        """Calculate exponential moving average (Runalyze method).

        EMA is calculated from oldest to newest date, which is the
        mathematically correct way to compute a running EMA.

        Formula: EMA_today = α * load_today + (1 - α) * EMA_yesterday
        where α = 2 / (days + 1)

        For CTL: days = 42 (chronic training load)
        For ATL: days = 7 (acute training load)
        """
        alpha = 2 / (days + 1)
        ema = 0.0

        # Calculate from oldest to newest (correct order)
        start_date = target_date - timedelta(days=days - 1)
        for i in range(days):
            d = start_date + timedelta(days=i)
            load = daily_loads.get(d, 0)
            ema = alpha * load + (1 - alpha) * ema

        return ema

    def _get_upcoming_workouts(self, target_date: date, limit: int = 3) -> list[dict]:
        """Get upcoming scheduled workouts."""
        # TODO: Implement when workout scheduling is added
        return []

    def _get_weekly_metric(
        self,
        start_date: date,
        end_date: date,
        metric: str,
    ) -> list[dict]:
        """Get weekly aggregated metric."""
        # Get all activities in range
        activities = self._get_activities_in_range(start_date, end_date)

        # Group by week
        weeks = {}
        for a in activities:
            if a.start_time:
                # Get Monday of the week
                week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
                if week_start not in weeks:
                    weeks[week_start] = 0

                value = getattr(a, metric, 0) or 0
                if metric == "distance_meters":
                    value = value / 1000  # Convert to km
                elif metric == "duration_seconds":
                    value = value / 3600  # Convert to hours
                weeks[week_start] += value

        # Sort and format
        result = []
        for week_start in sorted(weeks.keys()):
            result.append({
                "date": week_start.isoformat(),
                "value": round(weeks[week_start], 1),
            })

        return result

    def _get_weekly_avg_pace(self, start_date: date, end_date: date) -> list[dict]:
        """Get weekly average pace."""
        activities = self._get_activities_in_range(start_date, end_date, "running")

        weeks = {}
        for a in activities:
            if a.start_time and a.distance_meters and a.duration_seconds:
                week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
                if week_start not in weeks:
                    weeks[week_start] = {"distance": 0, "duration": 0}

                weeks[week_start]["distance"] += a.distance_meters
                weeks[week_start]["duration"] += a.duration_seconds

        result = []
        for week_start in sorted(weeks.keys()):
            data = weeks[week_start]
            if data["distance"] > 0:
                pace_sec_per_km = (data["duration"] / data["distance"]) * 1000
                result.append({
                    "date": week_start.isoformat(),
                    "value": round(pace_sec_per_km),  # seconds per km
                })

        return result

    def _get_daily_metric(
        self,
        start_date: date,
        end_date: date,
        model,
        field: str,
    ) -> list[dict]:
        """Get daily metric from health records."""
        # For HRRecord, use start_time instead of calendar_date
        if model == HRRecord:
            query = (
                select(model)
                .where(
                    model.user_id == self.user_id,
                    func.date(model.start_time) >= start_date,
                    func.date(model.start_time) <= end_date,
                )
                .order_by(model.start_time)
            )
            records = self.db.execute(query).scalars().all()

            # Group by week
            weeks = {}
            for r in records:
                record_date = r.start_time.date() if r.start_time else None
                if record_date:
                    week_start = record_date - timedelta(days=record_date.weekday())
                    value = getattr(r, field, None)
                    if value is not None:
                        if week_start not in weeks:
                            weeks[week_start] = []
                        weeks[week_start].append(value)
        else:
            # For other models with date field
            query = (
                select(model)
                .where(
                    model.user_id == self.user_id,
                    model.date >= start_date,
                    model.date <= end_date,
                )
                .order_by(model.date)
            )
            records = self.db.execute(query).scalars().all()

            # Group by week
            weeks = {}
            for r in records:
                week_start = r.date - timedelta(days=r.date.weekday())
                value = getattr(r, field, None)
                if value is not None:
                    if week_start not in weeks:
                        weeks[week_start] = []
                    weeks[week_start].append(value)

        # Average per week
        result = []
        for week_start in sorted(weeks.keys()):
            values = weeks[week_start]
            avg = sum(values) / len(values) if values else None
            if avg is not None:
                result.append({
                    "date": week_start.isoformat(),
                    "value": round(avg),
                })

        return result

    def _get_fitness_trend(self, start_date: date, end_date: date) -> list[dict]:
        """Get CTL/ATL/TSB trend.

        Optimized: Query FitnessMetricDaily first, then batch-calculate
        missing dates in a single pass instead of repeated full calculations.
        """
        # Try to get data from FitnessMetricDaily first (much faster)
        stored_metrics = self.db.execute(
            select(FitnessMetricDaily)
            .where(
                FitnessMetricDaily.user_id == self.user_id,
                FitnessMetricDaily.date >= start_date,
                FitnessMetricDaily.date <= end_date,
            )
            .order_by(FitnessMetricDaily.date)
        ).scalars().all()

        # Build lookup dict for stored data
        stored_by_date: dict[date, FitnessMetricDaily] = {
            m.date: m for m in stored_metrics
        }

        # Collect all sample dates (weekly Mondays)
        sample_dates: list[date] = []
        current = start_date - timedelta(days=start_date.weekday())
        while current <= end_date:
            sample_dates.append(current)
            current += timedelta(weeks=1)

        # Find dates that need calculation
        missing_dates = [d for d in sample_dates if d not in stored_by_date]

        # If there are missing dates, calculate all in one pass
        calculated: dict[date, dict] = {}
        if missing_dates:
            calculated = self._batch_calculate_fitness_metrics(
                missing_dates, end_date
            )

        # Build result
        result = []
        for sample_date in sample_dates:
            if sample_date in stored_by_date:
                m = stored_by_date[sample_date]
                result.append({
                    "date": sample_date.isoformat(),
                    "ctl": m.ctl,
                    "atl": m.atl,
                    "tsb": m.tsb,
                })
            elif sample_date in calculated:
                m = calculated[sample_date]
                result.append({
                    "date": sample_date.isoformat(),
                    "ctl": m["ctl"],
                    "atl": m["atl"],
                    "tsb": m["tsb"],
                })

        return result

    def _batch_calculate_fitness_metrics(
        self,
        sample_dates: list[date],
        max_date: date,
    ) -> dict[date, dict]:
        """Calculate fitness metrics for multiple dates in a single pass.

        Performance optimization: Instead of recalculating full history for
        each date (O(dates × history)), calculate once through history and
        sample at required dates (O(history)).

        Args:
            sample_dates: List of dates to sample CTL/ATL/TSB.
            max_date: Maximum date to calculate to.

        Returns:
            Dictionary mapping date -> {ctl, atl, tsb}.
        """
        if not sample_dates:
            return {}

        # Get all activities up to max_date
        earliest_possible = date(2020, 1, 1)
        activities = self._get_activities_in_range(earliest_possible, max_date)

        # Build daily load dictionary
        daily_loads: dict[date, float] = {}
        for a in activities:
            if a.start_time:
                d = a.start_time.date()
                daily_loads[d] = daily_loads.get(d, 0) + self._calculate_trimp(a)

        if not daily_loads:
            # No activities - return zeros for all sample dates
            return {d: {"ctl": 0.0, "atl": 0.0, "tsb": 0.0} for d in sample_dates}

        # Sort sample dates and find the range to calculate
        sample_set = set(sample_dates)
        earliest_load = min(daily_loads.keys())
        latest_sample = max(sample_dates)

        # Calculate EMA through entire history, sampling at required dates
        decay_42 = 1 - math.exp(-1 / 42)
        decay_7 = 1 - math.exp(-1 / 7)

        ctl = 0.0
        atl = 0.0
        results: dict[date, dict] = {}

        current = earliest_load
        while current <= latest_sample:
            load = daily_loads.get(current, 0)
            ctl = ctl + decay_42 * (load - ctl)
            atl = atl + decay_7 * (load - atl)

            # Sample if this is a requested date
            if current in sample_set:
                results[current] = {
                    "ctl": round(ctl, 1),
                    "atl": round(atl, 1),
                    "tsb": round(ctl - atl, 1),
                }

            current += timedelta(days=1)

        # Handle sample dates before earliest activity (return zeros)
        for d in sample_dates:
            if d not in results:
                results[d] = {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

        return results

    def _calculate_period_stats(
        self,
        activities: list[Activity],
        start_date: date,
        end_date: date,
    ) -> dict:
        """Calculate stats for a period."""
        summary = self._calculate_summary_stats(activities)

        # Add TRIMP/TSS
        total_trimp = sum(self._calculate_trimp(a) for a in activities)

        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_distance_km": summary["total_distance_km"],
            "total_duration_hours": summary["total_duration_hours"],
            "total_activities": summary["total_activities"],
            "avg_pace_per_km": summary["avg_pace_per_km"],
            "avg_hr": summary["avg_hr"],
            "total_elevation_m": summary["total_elevation_m"],
            "total_calories": summary["total_calories"],
            "total_trimp": round(total_trimp),
            "total_tss": None,
        }

    def _calculate_change(self, current: dict, previous: dict) -> dict:
        """Calculate percentage changes between periods."""
        def pct_change(curr, prev):
            if prev and prev != 0:
                return round(((curr - prev) / prev) * 100, 1)
            return None

        return {
            "distance_change_pct": pct_change(
                current["total_distance_km"],
                previous["total_distance_km"],
            ),
            "duration_change_pct": pct_change(
                current["total_duration_hours"],
                previous["total_duration_hours"],
            ),
            "activities_change": current["total_activities"] - previous["total_activities"],
            "pace_change_seconds": None,  # TODO: Calculate pace change
            "elevation_change_pct": pct_change(
                current["total_elevation_m"],
                previous["total_elevation_m"],
            ),
        }

    def _generate_improvement_summary(self, change: dict) -> str:
        """Generate human-readable improvement summary."""
        parts = []

        if change["distance_change_pct"]:
            direction = "증가" if change["distance_change_pct"] > 0 else "감소"
            parts.append(f"거리 {abs(change['distance_change_pct'])}% {direction}")

        if change["pace_change_seconds"]:
            direction = "향상" if change["pace_change_seconds"] < 0 else "저하"
            parts.append(f"페이스 {abs(change['pace_change_seconds'])}초/km {direction}")

        if change["activities_change"]:
            direction = "증가" if change["activities_change"] > 0 else "감소"
            parts.append(f"활동 {abs(change['activities_change'])}회 {direction}")

        return ", ".join(parts) if parts else "변화 없음"

    def _get_distance_records(self, activity_type: str) -> list[dict]:
        """Get best times for standard distances."""
        # TODO: Implement distance record tracking
        return []

    def _get_pace_records(self, activity_type: str) -> list[dict]:
        """Get best pace records."""
        # TODO: Implement pace record tracking
        return []

    def _get_endurance_records(self, activity_type: str) -> list[dict]:
        """Get endurance records (longest run, etc)."""
        # Longest run
        longest = self.db.execute(
            select(Activity)
            .where(
                Activity.user_id == self.user_id,
                Activity.activity_type == activity_type,
                Activity.distance_meters.isnot(None),
            )
            .order_by(Activity.distance_meters.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Longest duration
        longest_duration = self.db.execute(
            select(Activity)
            .where(
                Activity.user_id == self.user_id,
                Activity.activity_type == activity_type,
                Activity.duration_seconds.isnot(None),
            )
            .order_by(Activity.duration_seconds.desc())
            .limit(1)
        ).scalar_one_or_none()

        records = []

        if longest and longest.distance_meters:
            records.append({
                "category": "Longest Run",
                "value": round(longest.distance_meters),
                "unit": "meters",
                "activity_id": longest.id,
                "activity_name": longest.name,
                "achieved_date": longest.start_time.date().isoformat() if longest.start_time else None,
            })

        if longest_duration and longest_duration.duration_seconds:
            records.append({
                "category": "Longest Duration",
                "value": round(longest_duration.duration_seconds),
                "unit": "seconds",
                "activity_id": longest_duration.id,
                "activity_name": longest_duration.name,
                "achieved_date": longest_duration.start_time.date().isoformat() if longest_duration.start_time else None,
            })

        return records

    def _get_recent_prs(self, activity_type: str, limit: int = 5) -> list[dict]:
        """Get recently achieved PRs."""
        # TODO: Implement PR tracking with history
        return []

    def save_fitness_metrics_for_date(self, target_date: date) -> Optional[FitnessMetricDaily]:
        """Calculate and save fitness metrics for a specific date.

        Args:
            target_date: The date to calculate and save metrics for.

        Returns:
            The created/updated FitnessMetricDaily record, or None if no data.
        """
        # Calculate metrics
        metrics = self._calculate_fitness_metrics(target_date)

        if metrics["ctl"] == 0 and metrics["atl"] == 0:
            # No activities, don't save empty record
            return None

        # Check for existing record
        existing = self.db.execute(
            select(FitnessMetricDaily).where(
                FitnessMetricDaily.user_id == self.user_id,
                FitnessMetricDaily.date == target_date,
            )
        ).scalar_one_or_none()

        if existing:
            existing.ctl = metrics["ctl"]
            existing.atl = metrics["atl"]
            existing.tsb = metrics["tsb"]
            self.db.flush()
            logger.debug(f"Updated FitnessMetricDaily for user {self.user_id} date {target_date}")
            return existing
        else:
            record = FitnessMetricDaily(
                user_id=self.user_id,
                date=target_date,
                ctl=metrics["ctl"],
                atl=metrics["atl"],
                tsb=metrics["tsb"],
            )
            self.db.add(record)
            self.db.flush()
            logger.debug(f"Created FitnessMetricDaily for user {self.user_id} date {target_date}")
            return record

    def backfill_fitness_metrics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Backfill fitness metrics for a date range.

        Args:
            start_date: Start date (default: earliest activity date)
            end_date: End date (default: today)

        Returns:
            Number of records created/updated.
        """
        # Get date range from activities if not specified
        if not start_date:
            earliest = self.db.execute(
                select(func.min(func.date(Activity.start_time))).where(
                    Activity.user_id == self.user_id
                )
            ).scalar()
            start_date = earliest or date.today()

        if not end_date:
            end_date = date.today()

        logger.info(
            f"Backfilling fitness metrics for user {self.user_id}: {start_date} to {end_date}"
        )

        count = 0
        current = start_date
        while current <= end_date:
            if self.save_fitness_metrics_for_date(current):
                count += 1
            current += timedelta(days=1)

        self.db.commit()
        logger.info(f"Backfilled {count} fitness metric records for user {self.user_id}")
        return count

    def update_today_fitness_metrics(self) -> Optional[FitnessMetricDaily]:
        """Update fitness metrics for today.

        Convenience method for sync operations.

        Returns:
            The updated FitnessMetricDaily record.
        """
        record = self.save_fitness_metrics_for_date(date.today())
        self.db.commit()
        return record


def get_dashboard_service(db: Session, user_id: int) -> DashboardService:
    """Factory function to create dashboard service."""
    return DashboardService(db, user_id)
