"""Tests for Workouts and Schedule endpoints."""

from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.workout import Workout, WorkoutSchedule


class TestWorkoutCRUD:
    """Tests for workout CRUD operations."""

    async def test_create_workout(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test creating a workout."""
        response = await auth_client.post(
            "/api/v1/workouts",
            json={
                "name": "Morning Run",
                "workout_type": "easy",
                "notes": "Keep it relaxed",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Morning Run"
        assert data["workout_type"] == "easy"
        assert data["notes"] == "Keep it relaxed"

    async def test_create_workout_with_structure(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test creating a workout with structure."""
        structure = [
            {"type": "warmup", "duration_minutes": 10, "description": "Easy jog"},
            {"type": "main", "distance_km": 5.0, "target_pace": "5:00/km"},
            {"type": "cooldown", "duration_minutes": 5},
        ]
        response = await auth_client.post(
            "/api/v1/workouts",
            json={
                "name": "Interval Workout",
                "workout_type": "interval",
                "structure": structure,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["structure"]) == 3
        assert data["structure"][0]["type"] == "warmup"
        assert data["structure"][1]["distance_km"] == 5.0

    async def test_update_workout_notes(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test updating workout notes."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        response = await auth_client.patch(
            f"/api/v1/workouts/{workout.id}",
            json={"notes": "Updated notes"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"

    async def test_list_workouts(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test listing workouts."""
        for i in range(3):
            workout = Workout(
                user_id=test_user.id,
                name=f"Workout {i}",
                workout_type="easy",
            )
            db_session.add(workout)
        await db_session.commit()

        response = await auth_client.get("/api/v1/workouts")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    async def test_list_workouts_filter_by_type(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test listing workouts filtered by type."""
        db_session.add(Workout(user_id=test_user.id, name="Easy Run", workout_type="easy"))
        db_session.add(Workout(user_id=test_user.id, name="Tempo Run", workout_type="tempo"))
        db_session.add(Workout(user_id=test_user.id, name="Long Run", workout_type="long"))
        await db_session.commit()

        response = await auth_client.get("/api/v1/workouts?workout_type=easy")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["workout_type"] == "easy"

    async def test_get_workout_not_found(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting non-existent workout returns 404."""
        response = await auth_client.get("/api/v1/workouts/99999")

        assert response.status_code == 404

    async def test_delete_workout(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test deleting a workout."""
        workout = Workout(
            user_id=test_user.id,
            name="To Delete",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)
        workout_id = workout.id

        response = await auth_client.delete(f"/api/v1/workouts/{workout_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = await auth_client.get(f"/api/v1/workouts/{workout_id}")
        assert get_response.status_code == 404


class TestScheduleDuplicatePrevention:
    """Tests for schedule duplicate prevention."""

    async def test_schedule_workout(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test scheduling a workout."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        schedule_date = (date.today() + timedelta(days=1)).isoformat()
        response = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={
                "workout_id": workout.id,
                "scheduled_date": schedule_date,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["workout_id"] == workout.id
        assert data["status"] == "scheduled"

    async def test_schedule_duplicate_returns_409(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test scheduling same workout on same date returns 409."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        schedule_date = (date.today() + timedelta(days=1)).isoformat()

        # First schedule
        response1 = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={
                "workout_id": workout.id,
                "scheduled_date": schedule_date,
            },
        )
        assert response1.status_code == 201

        # Duplicate schedule
        response2 = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={
                "workout_id": workout.id,
                "scheduled_date": schedule_date,
            },
        )
        assert response2.status_code == 409
        assert "already scheduled" in response2.json()["detail"]

    async def test_schedule_different_dates_allowed(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test scheduling same workout on different dates is allowed."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        # Schedule on first date
        date1 = (date.today() + timedelta(days=1)).isoformat()
        response1 = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={"workout_id": workout.id, "scheduled_date": date1},
        )
        assert response1.status_code == 201

        # Schedule on second date
        date2 = (date.today() + timedelta(days=2)).isoformat()
        response2 = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={"workout_id": workout.id, "scheduled_date": date2},
        )
        assert response2.status_code == 201

    async def test_schedule_cancelled_can_be_rescheduled(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that cancelled schedules don't block new schedules."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        schedule_date = (date.today() + timedelta(days=1)).isoformat()

        # First schedule
        response1 = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={"workout_id": workout.id, "scheduled_date": schedule_date},
        )
        assert response1.status_code == 201
        schedule_id = response1.json()["id"]

        # Cancel it
        await auth_client.patch(
            f"/api/v1/workouts/schedules/{schedule_id}/status?new_status=cancelled"
        )

        # Should be able to schedule again on same date
        response2 = await auth_client.post(
            "/api/v1/workouts/schedules",
            json={"workout_id": workout.id, "scheduled_date": schedule_date},
        )
        assert response2.status_code == 201


class TestScheduleList:
    """Tests for schedule list endpoint."""

    async def test_list_schedules_pagination(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test schedule list pagination."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        # Create 5 schedules
        base_date = date.today()
        for i in range(5):
            schedule = WorkoutSchedule(
                workout_id=workout.id,
                scheduled_date=base_date + timedelta(days=i),
                status="scheduled",
            )
            db_session.add(schedule)
        await db_session.commit()

        response = await auth_client.get(
            "/api/v1/workouts/schedules/list?page=1&per_page=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["per_page"] == 2

    async def test_list_schedules_filter_by_date_range(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test filtering schedules by date range."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        base_date = date.today()
        for i in range(5):
            schedule = WorkoutSchedule(
                workout_id=workout.id,
                scheduled_date=base_date + timedelta(days=i),
                status="scheduled",
            )
            db_session.add(schedule)
        await db_session.commit()

        # Query for dates 1-3 (indices 1, 2, 3 = 3 records)
        start = (base_date + timedelta(days=1)).isoformat()
        end = (base_date + timedelta(days=3)).isoformat()
        response = await auth_client.get(
            f"/api/v1/workouts/schedules/list?start_date={start}&end_date={end}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    async def test_list_schedules_filter_by_status(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test filtering schedules by status."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        base_date = date.today()
        statuses = ["scheduled", "scheduled", "completed", "skipped", "cancelled"]
        for i, status_val in enumerate(statuses):
            schedule = WorkoutSchedule(
                workout_id=workout.id,
                scheduled_date=base_date + timedelta(days=i),
                status=status_val,
            )
            db_session.add(schedule)
        await db_session.commit()

        response = await auth_client.get(
            "/api/v1/workouts/schedules/list?status_filter=scheduled"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Only 2 scheduled


class TestScheduleStatusUpdate:
    """Tests for schedule status updates."""

    async def test_update_schedule_status(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test updating schedule status."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        schedule = WorkoutSchedule(
            workout_id=workout.id,
            scheduled_date=date.today(),
            status="scheduled",
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        response = await auth_client.patch(
            f"/api/v1/workouts/schedules/{schedule.id}/status?new_status=completed"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    async def test_update_schedule_status_invalid(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test updating schedule with invalid status returns 422."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        schedule = WorkoutSchedule(
            workout_id=workout.id,
            scheduled_date=date.today(),
            status="scheduled",
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        response = await auth_client.patch(
            f"/api/v1/workouts/schedules/{schedule.id}/status?new_status=invalid_status"
        )

        assert response.status_code == 422

    async def test_delete_schedule(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test deleting a schedule."""
        workout = Workout(
            user_id=test_user.id,
            name="Test Run",
            workout_type="easy",
        )
        db_session.add(workout)
        await db_session.commit()
        await db_session.refresh(workout)

        schedule = WorkoutSchedule(
            workout_id=workout.id,
            scheduled_date=date.today(),
            status="scheduled",
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)
        schedule_id = schedule.id

        response = await auth_client.delete(f"/api/v1/workouts/schedules/{schedule_id}")
        assert response.status_code == 204


class TestWorkoutAuthentication:
    """Tests for authentication requirements."""

    async def test_unauthenticated_list_workouts(self, client: AsyncClient):
        """Test listing workouts without authentication returns 401."""
        response = await client.get("/api/v1/workouts")
        assert response.status_code == 401

    async def test_unauthenticated_create_workout(self, client: AsyncClient):
        """Test creating workout without authentication returns 401."""
        response = await client.post(
            "/api/v1/workouts",
            json={"name": "Test", "workout_type": "easy"},
        )
        assert response.status_code == 401
