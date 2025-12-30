"""Tests for Gear API endpoints."""

from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.activity import Activity
from app.models.gear import ActivityGear, Gear, GearStatus, GearType
from app.models.user import User


class TestGearValidation:
    """Tests for gear field validation."""

    async def test_create_gear_invalid_gear_type(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test creating gear with invalid gear_type returns 422."""
        response = await auth_client.post(
            "/api/v1/gear",
            json={
                "name": "Test Shoes",
                "gear_type": "invalid_type",
            },
        )

        assert response.status_code == 422
        assert "gear_type" in response.text.lower()

    async def test_create_gear_valid_gear_types(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test creating gear with valid gear_type succeeds."""
        for gear_type in [GearType.RUNNING_SHOES.value, GearType.BIKE.value, GearType.OTHER.value]:
            response = await auth_client.post(
                "/api/v1/gear",
                json={
                    "name": f"Test {gear_type}",
                    "gear_type": gear_type,
                },
            )
            assert response.status_code == 201, f"Failed for gear_type: {gear_type}"

    async def test_update_gear_invalid_status(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test updating gear with invalid status returns 422."""
        # Create gear first
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            gear_type=GearType.RUNNING_SHOES.value,
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        response = await auth_client.patch(
            f"/api/v1/gear/{gear.id}",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 422
        assert "status" in response.text.lower()

    async def test_update_gear_valid_statuses(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test updating gear with valid status succeeds."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            gear_type=GearType.RUNNING_SHOES.value,
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        for status_val in [GearStatus.ACTIVE.value, GearStatus.RETIRED.value]:
            response = await auth_client.patch(
                f"/api/v1/gear/{gear.id}",
                json={"status": status_val},
            )
            assert response.status_code == 200, f"Failed for status: {status_val}"


class TestRetiredDateSync:
    """Tests for retired_date synchronization with status changes."""

    async def test_status_retired_sets_retired_date(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that changing status to retired sets retired_date automatically."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            gear_type=GearType.RUNNING_SHOES.value,
            status=GearStatus.ACTIVE.value,
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        assert gear.retired_date is None

        response = await auth_client.patch(
            f"/api/v1/gear/{gear.id}",
            json={"status": GearStatus.RETIRED.value},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == GearStatus.RETIRED.value
        assert data["retired_date"] == date.today().isoformat()

    async def test_status_active_clears_retired_date(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that changing status to active clears retired_date."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            gear_type=GearType.RUNNING_SHOES.value,
            status=GearStatus.RETIRED.value,
            retired_date=date.today() - timedelta(days=30),
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        response = await auth_client.patch(
            f"/api/v1/gear/{gear.id}",
            json={"status": GearStatus.ACTIVE.value},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == GearStatus.ACTIVE.value
        assert data["retired_date"] is None

    async def test_retire_endpoint_sets_retired_date(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that POST /retire endpoint sets retired_date."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            gear_type=GearType.RUNNING_SHOES.value,
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        response = await auth_client.post(f"/api/v1/gear/{gear.id}/retire")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == GearStatus.RETIRED.value
        assert data["retired_date"] == date.today().isoformat()


class TestDefaultMaxDistance:
    """Tests for default max_distance_meters."""

    async def test_create_gear_without_max_distance_uses_default(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test that creating gear without max_distance_meters uses default (800km)."""
        response = await auth_client.post(
            "/api/v1/gear",
            json={"name": "Test Shoes"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["max_distance_meters"] == 800_000  # 800km default

    async def test_create_gear_with_max_distance_uses_provided(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test that creating gear with max_distance_meters uses provided value."""
        response = await auth_client.post(
            "/api/v1/gear",
            json={
                "name": "Test Shoes",
                "max_distance_meters": 600_000,  # 600km
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["max_distance_meters"] == 600_000


class TestGearCRUD:
    """Tests for basic CRUD operations."""

    async def test_list_gear_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test listing gear when none exists."""
        response = await auth_client.get("/api/v1/gear")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_gear_with_items(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test listing gear with items."""
        for i in range(3):
            gear = Gear(
                user_id=test_user.id,
                name=f"Shoes {i}",
                gear_type=GearType.RUNNING_SHOES.value,
            )
            db_session.add(gear)
        await db_session.commit()

        response = await auth_client.get("/api/v1/gear")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    async def test_list_gear_filter_by_status(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test listing gear filtered by status."""
        active_gear = Gear(
            user_id=test_user.id,
            name="Active Shoes",
            status=GearStatus.ACTIVE.value,
        )
        retired_gear = Gear(
            user_id=test_user.id,
            name="Retired Shoes",
            status=GearStatus.RETIRED.value,
        )
        db_session.add(active_gear)
        db_session.add(retired_gear)
        await db_session.commit()

        # Filter active
        response = await auth_client.get("/api/v1/gear?status=active")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Active Shoes"

        # Filter retired
        response = await auth_client.get("/api/v1/gear?status=retired")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Retired Shoes"

    async def test_get_gear_not_found(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting non-existent gear returns 404."""
        response = await auth_client.get("/api/v1/gear/99999")

        assert response.status_code == 404

    async def test_delete_gear(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test deleting gear."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)
        gear_id = gear.id

        response = await auth_client.delete(f"/api/v1/gear/{gear_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = await auth_client.get(f"/api/v1/gear/{gear_id}")
        assert get_response.status_code == 404


class TestGearStats:
    """Tests for gear statistics endpoint."""

    async def test_get_stats_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting stats with no gear."""
        response = await auth_client.get("/api/v1/gear/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_gears"] == 0
        assert data["active_gears"] == 0
        assert data["retired_gears"] == 0
        assert data["gears_near_retirement"] == []

    async def test_get_stats_counts_active_retired(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test stats correctly counts active and retired gear."""
        for i in range(3):
            db_session.add(Gear(
                user_id=test_user.id,
                name=f"Active {i}",
                status=GearStatus.ACTIVE.value,
            ))
        for i in range(2):
            db_session.add(Gear(
                user_id=test_user.id,
                name=f"Retired {i}",
                status=GearStatus.RETIRED.value,
            ))
        await db_session.commit()

        response = await auth_client.get("/api/v1/gear/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_gears"] == 5
        assert data["active_gears"] == 3
        assert data["retired_gears"] == 2

    async def test_get_stats_near_retirement(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test stats identifies gear near retirement (>= 80% usage)."""
        # Gear at 85% usage: 680km / 800km
        near_retirement = Gear(
            user_id=test_user.id,
            name="Near Retirement",
            status=GearStatus.ACTIVE.value,
            initial_distance_meters=680_000,
            max_distance_meters=800_000,
        )
        # Gear at 50% usage: 400km / 800km
        healthy = Gear(
            user_id=test_user.id,
            name="Healthy Shoes",
            status=GearStatus.ACTIVE.value,
            initial_distance_meters=400_000,
            max_distance_meters=800_000,
        )
        db_session.add(near_retirement)
        db_session.add(healthy)
        await db_session.commit()

        response = await auth_client.get("/api/v1/gear/stats")

        assert response.status_code == 200
        data = response.json()
        assert len(data["gears_near_retirement"]) == 1
        assert data["gears_near_retirement"][0]["name"] == "Near Retirement"


class TestActivityGearLinking:
    """Tests for activity-gear linking."""

    async def test_link_gear_to_activity(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test linking gear to an activity."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        activity_id = sample_activities[0].id

        response = await auth_client.post(
            f"/api/v1/gear/{gear.id}/activities/{activity_id}"
        )

        assert response.status_code == 201
        assert response.json()["message"] == "Gear linked to activity"

    async def test_link_gear_duplicate_returns_409(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test linking same gear to same activity twice returns 409."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        activity_id = sample_activities[0].id

        # First link
        response1 = await auth_client.post(
            f"/api/v1/gear/{gear.id}/activities/{activity_id}"
        )
        assert response1.status_code == 201

        # Duplicate link
        response2 = await auth_client.post(
            f"/api/v1/gear/{gear.id}/activities/{activity_id}"
        )
        assert response2.status_code == 409

    async def test_unlink_gear_from_activity(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test unlinking gear from an activity."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        activity_id = sample_activities[0].id

        # Link first
        await auth_client.post(f"/api/v1/gear/{gear.id}/activities/{activity_id}")

        # Unlink
        response = await auth_client.delete(
            f"/api/v1/gear/{gear.id}/activities/{activity_id}"
        )
        assert response.status_code == 204

    async def test_get_gear_activities_pagination(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test getting activities linked to gear with pagination."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        # Link multiple activities
        for activity in sample_activities[:3]:
            link = ActivityGear(gear_id=gear.id, activity_id=activity.id)
            db_session.add(link)
        await db_session.commit()

        # Test with limit
        response = await auth_client.get(
            f"/api/v1/gear/{gear.id}/activities?limit=2"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Test with offset
        response = await auth_client.get(
            f"/api/v1/gear/{gear.id}/activities?limit=2&offset=2"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Only 1 remaining


class TestGearUsageCalculation:
    """Tests for gear usage percentage calculation."""

    async def test_usage_percentage_with_activities(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test usage percentage includes activity distances."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            initial_distance_meters=100_000,  # 100km initial
            max_distance_meters=800_000,  # 800km max
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        # Create activity with 100km
        activity = Activity(
            user_id=test_user.id,
            garmin_id=999999,
            activity_type="running",
            name="Long Run",
            start_time=datetime.now(timezone.utc),
            distance_meters=100_000,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        # Link gear to activity
        link = ActivityGear(gear_id=gear.id, activity_id=activity.id)
        db_session.add(link)
        await db_session.commit()

        response = await auth_client.get(f"/api/v1/gear/{gear.id}")

        assert response.status_code == 200
        data = response.json()
        # 100km initial + 100km activity = 200km total
        assert data["total_distance_meters"] == 200_000
        # 200km / 800km = 25%
        assert data["usage_percentage"] == 25.0

    async def test_usage_percentage_null_when_no_max(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test usage percentage is null when max_distance is not set."""
        gear = Gear(
            user_id=test_user.id,
            name="Test Shoes",
            initial_distance_meters=100_000,
            max_distance_meters=None,
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        response = await auth_client.get(f"/api/v1/gear/{gear.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["usage_percentage"] is None


class TestGearAuthentication:
    """Tests for authentication requirements."""

    async def test_unauthenticated_list_gear(self, client: AsyncClient):
        """Test listing gear without authentication returns 401."""
        response = await client.get("/api/v1/gear")
        assert response.status_code == 401

    async def test_unauthenticated_create_gear(self, client: AsyncClient):
        """Test creating gear without authentication returns 401."""
        response = await client.post(
            "/api/v1/gear",
            json={"name": "Test Shoes"},
        )
        assert response.status_code == 401


class TestActivityGearEndpoint:
    """Tests for GET /activities/{id}/gear endpoint."""

    async def test_get_activity_gear_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
    ):
        """Test getting gear for an activity with no linked gear."""
        activity_id = sample_activities[0].id
        response = await auth_client.get(f"/api/v1/activities/{activity_id}/gear")

        assert response.status_code == 200
        data = response.json()
        assert data["activity_id"] == activity_id
        assert data["gears"] == []
        assert data["total"] == 0

    async def test_get_activity_gear_with_links(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test getting gear linked to an activity."""
        activity = sample_activities[0]

        # Create gear
        gear = Gear(
            user_id=test_user.id,
            name="Test Running Shoes",
            brand="Nike",
            gear_type="running_shoes",
        )
        db_session.add(gear)
        await db_session.commit()
        await db_session.refresh(gear)

        # Link gear to activity
        link = ActivityGear(gear_id=gear.id, activity_id=activity.id)
        db_session.add(link)
        await db_session.commit()

        response = await auth_client.get(f"/api/v1/activities/{activity.id}/gear")

        assert response.status_code == 200
        data = response.json()
        assert data["activity_id"] == activity.id
        assert len(data["gears"]) == 1
        assert data["gears"][0]["name"] == "Test Running Shoes"
        assert data["gears"][0]["brand"] == "Nike"
        assert data["total"] == 1

    async def test_get_activity_gear_not_found(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test getting gear for non-existent activity returns 404."""
        response = await auth_client.get("/api/v1/activities/99999/gear")

        assert response.status_code == 404
