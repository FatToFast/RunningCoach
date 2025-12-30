"""Tests for dashboard endpoints."""

from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.activity import Activity, ActivityMetric
from app.models.analytics import AnalyticsSummary
from app.models.health import FitnessMetricDaily, HealthMetric, HRRecord, Sleep
from app.models.user import User
from app.models.workout import Workout, WorkoutSchedule


class TestDashboardSummary:
    """Tests for dashboard summary endpoint."""

    async def test_get_summary_unauthenticated(self, client: AsyncClient):
        """Test getting summary without authentication."""
        response = await client.get("/api/v1/dashboard/summary")
        assert response.status_code == 401

    async def test_get_summary_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting summary with no data."""
        response = await auth_client.get("/api/v1/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["period_type"] == "week"
        assert data["summary"]["total_activities"] == 0
        assert data["summary"]["total_distance_km"] == 0.0
        assert data["recent_activities"] == []

    async def test_get_summary_with_activities(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
    ):
        """Test getting summary with activities."""
        # sample_activities uses current date, so no target_date needed
        response = await auth_client.get("/api/v1/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_activities"] > 0
        assert data["summary"]["total_distance_km"] > 0

    async def test_get_summary_with_health_data(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_health_data: dict,
    ):
        """Test getting summary with health data."""
        # sample_health_data uses current date, so no target_date needed
        response = await auth_client.get("/api/v1/dashboard/summary")

        assert response.status_code == 200
        data = response.json()

        health = data["health_status"]
        assert health["latest_sleep_score"] == 85
        assert health["resting_hr"] == 52
        assert health["body_battery"] == 78
        assert health["vo2max"] == 52.4

        fitness = data["fitness_status"]
        assert fitness["ctl"] == 58.2
        assert fitness["atl"] == 72.5
        assert fitness["tsb"] == -14.3

    async def test_get_summary_month_period(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting summary for month period."""
        response = await auth_client.get("/api/v1/dashboard/summary?period=month")

        assert response.status_code == 200
        data = response.json()
        assert data["period_type"] == "month"

        # Check period dates are valid
        period_start = date.fromisoformat(data["period_start"])
        period_end = date.fromisoformat(data["period_end"])
        assert period_start.day == 1  # Month starts on day 1
        assert period_start <= period_end

    async def test_get_summary_with_target_date(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting summary for specific target date."""
        target_date = "2024-12-15"
        response = await auth_client.get(
            f"/api/v1/dashboard/summary?target_date={target_date}"
        )

        assert response.status_code == 200
        data = response.json()

        # Period should contain the target date
        period_start = date.fromisoformat(data["period_start"])
        period_end = date.fromisoformat(data["period_end"])
        target = date.fromisoformat(target_date)
        assert period_start <= target <= period_end

    async def test_get_summary_invalid_period(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting summary with invalid period parameter."""
        response = await auth_client.get("/api/v1/dashboard/summary?period=invalid")

        assert response.status_code == 422  # Validation error


class TestDashboardTrends:
    """Tests for dashboard trends endpoint."""

    async def test_get_trends_unauthenticated(self, client: AsyncClient):
        """Test getting trends without authentication."""
        response = await client.get("/api/v1/dashboard/trends")
        assert response.status_code == 401

    async def test_get_trends_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting trends with no data."""
        response = await auth_client.get("/api/v1/dashboard/trends")

        assert response.status_code == 200
        data = response.json()
        assert data["weekly_distance"] == []
        assert data["weekly_duration"] == []
        assert data["ctl_atl"] == []

    async def test_get_trends_with_analytics(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test getting trends with analytics data."""
        # Create analytics summaries using current date
        today = date.today()
        for i in range(4):
            summary = AnalyticsSummary(
                user_id=test_user.id,
                period_type="week",
                period_start=today - timedelta(weeks=i),  # Past 4 weeks
                total_distance_meters=10000 + i * 1000,
                total_duration_seconds=3600 + i * 300,
                total_activities=3 + i,
                avg_pace_seconds=360 - i * 5,
            )
            db_session.add(summary)
        await db_session.commit()

        response = await auth_client.get("/api/v1/dashboard/trends")

        assert response.status_code == 200
        data = response.json()
        assert len(data["weekly_distance"]) > 0
        assert len(data["weekly_duration"]) > 0

    async def test_get_trends_with_fitness_metrics(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_health_data: dict,
    ):
        """Test getting trends with fitness metrics."""
        response = await auth_client.get("/api/v1/dashboard/trends")

        assert response.status_code == 200
        data = response.json()
        assert len(data["ctl_atl"]) > 0

        # Check CTL/ATL/TSB structure
        metric = data["ctl_atl"][0]
        assert "date" in metric
        assert "ctl" in metric
        assert "atl" in metric
        assert "tsb" in metric

    async def test_get_trends_custom_weeks(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting trends with custom weeks parameter."""
        response = await auth_client.get("/api/v1/dashboard/trends?weeks=8")

        assert response.status_code == 200

    async def test_get_trends_weeks_validation(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test weeks parameter validation."""
        # Too few weeks
        response = await auth_client.get("/api/v1/dashboard/trends?weeks=2")
        assert response.status_code == 422

        # Too many weeks
        response = await auth_client.get("/api/v1/dashboard/trends?weeks=100")
        assert response.status_code == 422

    async def test_get_trends_resting_hr(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_health_data: dict,
    ):
        """Test getting resting HR trend data."""
        response = await auth_client.get("/api/v1/dashboard/trends")

        assert response.status_code == 200
        data = response.json()
        assert len(data["resting_hr"]) > 0


class TestDashboardCalendar:
    """Tests for dashboard calendar endpoint."""

    async def test_get_calendar_unauthenticated(self, client: AsyncClient):
        """Test getting calendar without authentication."""
        response = await client.get(
            "/api/v1/dashboard/calendar",
            params={"start_date": "2024-12-01", "end_date": "2024-12-31"},
        )
        assert response.status_code == 401

    async def test_get_calendar_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting calendar with no data."""
        response = await auth_client.get(
            "/api/v1/dashboard/calendar",
            params={"start_date": "2024-12-01", "end_date": "2024-12-07"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["days"]) == 7  # 7 days in range
        assert data["start_date"] == "2024-12-01"
        assert data["end_date"] == "2024-12-07"

        # All days should be empty
        for day in data["days"]:
            assert day["activities"] == []
            assert day["scheduled_workouts"] == []

    async def test_get_calendar_with_activities(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
    ):
        """Test getting calendar with activities."""
        # sample_activities use current date, so query around today
        today = date.today()
        start_date = (today - timedelta(days=7)).isoformat()
        end_date = today.isoformat()

        response = await auth_client.get(
            "/api/v1/dashboard/calendar",
            params={"start_date": start_date, "end_date": end_date},
        )

        assert response.status_code == 200
        data = response.json()

        # Check that activities are present
        has_activities = any(len(day["activities"]) > 0 for day in data["days"])
        assert has_activities

    async def test_get_calendar_activity_schema(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
    ):
        """Test that calendar activities use correct RecentActivity schema."""
        today = date.today()
        start_date = (today - timedelta(days=7)).isoformat()
        end_date = today.isoformat()

        response = await auth_client.get(
            "/api/v1/dashboard/calendar",
            params={"start_date": start_date, "end_date": end_date},
        )

        assert response.status_code == 200
        data = response.json()

        # Find a day with activities
        activities_day = next(
            (day for day in data["days"] if len(day["activities"]) > 0),
            None,
        )
        assert activities_day is not None, "No activities found in calendar"

        activity = activities_day["activities"][0]

        # Verify RecentActivity schema fields (not deprecated duration_minutes/avg_hr)
        assert "id" in activity
        assert "name" in activity
        assert "activity_type" in activity
        assert "start_time" in activity
        assert "distance_km" in activity
        assert "duration_seconds" in activity  # Not duration_minutes
        assert "avg_pace_seconds" in activity
        assert "avg_hr_percent" in activity  # Not avg_hr (raw value)
        assert "elevation_gain" in activity
        assert "calories" in activity

        # Verify deprecated fields are NOT present
        assert "duration_minutes" not in activity
        assert "avg_hr" not in activity

    async def test_get_calendar_with_scheduled_workouts(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test getting calendar with scheduled workouts."""
        # Create a workout
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy_run",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        # Create a schedule
        schedule = WorkoutSchedule(
            workout_id=workout.id,
            scheduled_date=date(2024, 12, 30),
            status="scheduled",
        )
        db_session.add(schedule)
        await db_session.commit()

        response = await auth_client.get(
            "/api/v1/dashboard/calendar",
            params={"start_date": "2024-12-29", "end_date": "2024-12-31"},
        )

        assert response.status_code == 200
        data = response.json()

        # Check that scheduled workouts are present
        has_workouts = any(len(day["scheduled_workouts"]) > 0 for day in data["days"])
        assert has_workouts

    async def test_get_calendar_missing_dates(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting calendar with missing date parameters."""
        # Missing end_date
        response = await auth_client.get(
            "/api/v1/dashboard/calendar",
            params={"start_date": "2024-12-01"},
        )
        assert response.status_code == 422

        # Missing start_date
        response = await auth_client.get(
            "/api/v1/dashboard/calendar",
            params={"end_date": "2024-12-31"},
        )
        assert response.status_code == 422


class TestPaceCalculation:
    """Tests for pace calculation helper."""

    def test_calculate_pace_valid(self):
        """Test pace calculation with valid input."""
        from app.api.v1.endpoints.dashboard import _calculate_pace

        # 1 hour for 10km = 6:00/km
        pace = _calculate_pace(3600, 10000)
        assert pace == "6:00/km"

        # 30 minutes for 5km = 6:00/km
        pace = _calculate_pace(1800, 5000)
        assert pace == "6:00/km"

        # 45 minutes for 10km = 4:30/km
        pace = _calculate_pace(2700, 10000)
        assert pace == "4:30/km"

    def test_calculate_pace_no_duration(self):
        """Test pace calculation with no duration."""
        from app.api.v1.endpoints.dashboard import _calculate_pace

        pace = _calculate_pace(None, 10000)
        assert pace == "N/A"

        pace = _calculate_pace(0, 10000)
        assert pace == "N/A"

    def test_calculate_pace_no_distance(self):
        """Test pace calculation with no distance."""
        from app.api.v1.endpoints.dashboard import _calculate_pace

        pace = _calculate_pace(3600, None)
        assert pace == "N/A"

        pace = _calculate_pace(3600, 0)
        assert pace == "N/A"
