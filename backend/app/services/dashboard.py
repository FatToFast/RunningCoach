"""Dashboard data service.

Provides aggregated data for dashboard, trends, and analytics views.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, and_, desc
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.health import SleepRecord, HeartRateRecord
from app.models.analytics import WeeklyStats, FitnessMetrics

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

    def get_summary(
        self,
        period: str = "week",
        target_date: Optional[date] = None,
    ) -> dict:
        """Get dashboard summary.

        Args:
            period: 'week' or 'month'.
            target_date: Reference date (defaults to today).

        Returns:
            Dashboard summary dict.
        """
        target_date = target_date or date.today()

        if period == "week":
            # ISO week: Monday to Sunday
            start = target_date - timedelta(days=target_date.weekday())
            end = start + timedelta(days=6)
        else:  # month
            start = target_date.replace(day=1)
            next_month = start.replace(day=28) + timedelta(days=4)
            end = next_month - timedelta(days=next_month.day)

        # Get activities in period
        activities = self._get_activities_in_range(start, end)

        # Calculate summary stats
        summary = self._calculate_summary_stats(activities)

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

    def get_trends(self, weeks: int = 12) -> dict:
        """Get trend data for charts.

        Args:
            weeks: Number of weeks to include.

        Returns:
            Trend data dict.
        """
        end_date = date.today()
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
            start_date, end_date, HeartRateRecord, "resting_hr"
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
            target_date: Reference date.

        Returns:
            Comparison dict.
        """
        target_date = target_date or date.today()

        if period == "week":
            current_start = target_date - timedelta(days=target_date.weekday())
            current_end = current_start + timedelta(days=6)
            previous_start = current_start - timedelta(weeks=1)
            previous_end = current_end - timedelta(weeks=1)
        else:
            current_start = target_date.replace(day=1)
            next_month = current_start.replace(day=28) + timedelta(days=4)
            current_end = next_month - timedelta(days=next_month.day)
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
        total_elevation = sum(a.total_ascent_meters or 0 for a in activities)
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
            select(SleepRecord)
            .where(
                SleepRecord.user_id == self.user_id,
                SleepRecord.calendar_date <= target_date,
            )
            .order_by(SleepRecord.calendar_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Get most recent HR
        hr = self.db.execute(
            select(HeartRateRecord)
            .where(
                HeartRateRecord.user_id == self.user_id,
                HeartRateRecord.calendar_date <= target_date,
            )
            .order_by(HeartRateRecord.calendar_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        return {
            "latest_sleep_score": sleep.sleep_score if sleep else None,
            "latest_sleep_hours": round(sleep.total_sleep_seconds / 3600, 1) if sleep and sleep.total_sleep_seconds else None,
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
        """Get fitness metrics (CTL/ATL/TSB)."""
        metrics = self.db.execute(
            select(FitnessMetrics)
            .where(
                FitnessMetrics.user_id == self.user_id,
                FitnessMetrics.date <= target_date,
            )
            .order_by(FitnessMetrics.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if metrics:
            return {
                "ctl": round(metrics.ctl, 1),
                "atl": round(metrics.atl, 1),
                "tsb": round(metrics.tsb, 1),
                "weekly_trimp": metrics.weekly_trimp,
                "weekly_tss": metrics.weekly_tss,
            }

        # Calculate from recent activities if no stored metrics
        return self._calculate_fitness_metrics(target_date)

    def _calculate_fitness_metrics(self, target_date: date) -> dict:
        """Calculate fitness metrics from activities."""
        # Simple TRIMP calculation
        activities_42d = self._get_activities_in_range(
            target_date - timedelta(days=42),
            target_date,
        )

        # Weekly load
        activities_7d = [
            a for a in activities_42d
            if a.start_time and a.start_time.date() > target_date - timedelta(days=7)
        ]

        weekly_trimp = sum(self._calculate_trimp(a) for a in activities_7d)

        # CTL (42-day exponential moving average)
        daily_loads = {}
        for a in activities_42d:
            if a.start_time:
                d = a.start_time.date()
                daily_loads[d] = daily_loads.get(d, 0) + self._calculate_trimp(a)

        ctl = self._calculate_ema(daily_loads, target_date, 42)
        atl = self._calculate_ema(daily_loads, target_date, 7)
        tsb = ctl - atl

        return {
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
            "weekly_trimp": round(weekly_trimp),
            "weekly_tss": None,
        }

    def _calculate_trimp(self, activity: Activity) -> float:
        """Calculate TRIMP for an activity."""
        if not activity.duration_seconds or not activity.avg_hr:
            return 0

        # Simplified TRIMP calculation
        # TRIMP = duration (min) * avg_hr_reserve_ratio * weighting
        duration_min = activity.duration_seconds / 60

        # Assume max HR = 220 - age (use 185 as default if unknown)
        max_hr = 185
        rest_hr = 50  # Assume resting HR

        hr_reserve = (activity.avg_hr - rest_hr) / (max_hr - rest_hr)
        hr_reserve = max(0, min(1, hr_reserve))  # Clamp to 0-1

        # Gender-neutral weighting
        weighting = 0.64 * (hr_reserve ** 1.92)

        return duration_min * hr_reserve * weighting

    def _calculate_ema(
        self,
        daily_loads: dict[date, float],
        target_date: date,
        days: int,
    ) -> float:
        """Calculate exponential moving average."""
        alpha = 2 / (days + 1)
        ema = 0.0

        for i in range(days):
            d = target_date - timedelta(days=i)
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
        # Sample weekly instead of daily for trends
        query = (
            select(model)
            .where(
                model.user_id == self.user_id,
                model.calendar_date >= start_date,
                model.calendar_date <= end_date,
            )
            .order_by(model.calendar_date)
        )

        records = self.db.execute(query).scalars().all()

        # Group by week
        weeks = {}
        for r in records:
            week_start = r.calendar_date - timedelta(days=r.calendar_date.weekday())
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
        """Get CTL/ATL/TSB trend."""
        # Sample weekly
        result = []
        current = start_date - timedelta(days=start_date.weekday())  # Start from Monday

        while current <= end_date:
            metrics = self._calculate_fitness_metrics(current)
            result.append({
                "date": current.isoformat(),
                "ctl": metrics["ctl"],
                "atl": metrics["atl"],
                "tsb": metrics["tsb"],
            })
            current += timedelta(weeks=1)

        return result

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


def get_dashboard_service(db: Session, user_id: int) -> DashboardService:
    """Factory function to create dashboard service."""
    return DashboardService(db, user_id)
