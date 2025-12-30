"""Tests for ingest endpoints (/api/v1/ingest/*)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.garmin import GarminRawEvent, GarminSession, GarminSyncState


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
async def garmin_session(db_session, test_user):
    """Create a Garmin session for the test user."""
    # Note: is_valid is a property that returns True when session_data exists
    session = GarminSession(
        user_id=test_user.id,
        session_data={"garth_session": "test_base64_session_data"},
    )
    db_session.add(session)
    await db_session.commit()
    return session


@pytest.fixture
async def garmin_sync_state(db_session, test_user):
    """Create sync state for the test user."""
    state = GarminSyncState(
        user_id=test_user.id,
        endpoint="activities",
        last_success_at=datetime.now(timezone.utc),
        cursor=None,
    )
    db_session.add(state)
    await db_session.commit()
    return state


@pytest.fixture
async def garmin_raw_events(db_session, test_user):
    """Create sample raw events for history tests."""
    events = []
    for i in range(5):
        event = GarminRawEvent(
            user_id=test_user.id,
            endpoint="activities",
            fetched_at=datetime.now(timezone.utc),
            payload=[{"activityId": 1000 + i}],
        )
        events.append(event)
        db_session.add(event)
    await db_session.commit()
    return events


@pytest.fixture
def mock_garmin_validate_session():
    """Mock Garmin session validation."""
    with patch("app.api.v1.endpoints.ingest.GarminConnectAdapter") as mock_class:
        mock_adapter = MagicMock()
        mock_adapter.validate_session = MagicMock(return_value=True)
        mock_class.return_value = mock_adapter
        yield mock_adapter


@pytest.fixture
def mock_garmin_validate_session_expired():
    """Mock expired Garmin session."""
    with patch("app.api.v1.endpoints.ingest.GarminConnectAdapter") as mock_class:
        mock_adapter = MagicMock()
        mock_adapter.validate_session = MagicMock(return_value=False)
        mock_class.return_value = mock_adapter
        yield mock_adapter


# -------------------------------------------------------------------------
# Tests: /ingest/status
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_status_no_garmin_session(auth_client: AsyncClient):
    """Test /ingest/status when user has no Garmin session."""
    response = await auth_client.get("/api/v1/ingest/status")
    assert response.status_code == 200

    data = response.json()
    assert data["connected"] is False
    assert data["running"] is False


@pytest.mark.asyncio
async def test_ingest_status_with_garmin_session(
    auth_client: AsyncClient,
    garmin_session,
    garmin_sync_state,
):
    """Test /ingest/status with connected Garmin account."""
    response = await auth_client.get("/api/v1/ingest/status")
    assert response.status_code == 200

    data = response.json()
    assert data["connected"] is True
    assert data["running"] is False
    assert len(data["sync_states"]) > 0


# -------------------------------------------------------------------------
# Tests: /ingest/run
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_run_no_garmin_session(auth_client: AsyncClient):
    """Test /ingest/run fails without Garmin connection."""
    response = await auth_client.post("/api/v1/ingest/run")
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingest_run_expired_session(
    auth_client: AsyncClient,
    garmin_session,
    mock_garmin_validate_session_expired,
):
    """Test /ingest/run fails with expired Garmin session."""
    response = await auth_client.post("/api/v1/ingest/run")
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingest_run_success(
    auth_client: AsyncClient,
    garmin_session,
    mock_garmin_validate_session,
):
    """Test /ingest/run starts background sync successfully."""
    response = await auth_client.post("/api/v1/ingest/run")
    assert response.status_code == 200

    data = response.json()
    assert data["started"] is True
    assert "sync_id" in data
    assert len(data["endpoints"]) > 0


@pytest.mark.asyncio
async def test_ingest_run_with_specific_endpoints(
    auth_client: AsyncClient,
    garmin_session,
    mock_garmin_validate_session,
):
    """Test /ingest/run with specific endpoints."""
    response = await auth_client.post(
        "/api/v1/ingest/run",
        json={"endpoints": ["activities", "sleep"]},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["started"] is True
    assert "activities" in data["endpoints"]
    assert "sleep" in data["endpoints"]
    assert len(data["endpoints"]) == 2


@pytest.mark.asyncio
async def test_ingest_run_invalid_endpoint(
    auth_client: AsyncClient,
    garmin_session,
    mock_garmin_validate_session,
):
    """Test /ingest/run fails with invalid endpoint."""
    response = await auth_client.post(
        "/api/v1/ingest/run",
        json={"endpoints": ["invalid_endpoint"]},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


# -------------------------------------------------------------------------
# Tests: /ingest/run/sync
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_run_sync_no_garmin_session(auth_client: AsyncClient):
    """Test /ingest/run/sync fails without Garmin connection."""
    response = await auth_client.post("/api/v1/ingest/run/sync")
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingest_run_sync_expired_session(
    auth_client: AsyncClient,
    garmin_session,
    mock_garmin_validate_session_expired,
):
    """Test /ingest/run/sync fails with expired Garmin session."""
    response = await auth_client.post("/api/v1/ingest/run/sync")
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


# -------------------------------------------------------------------------
# Tests: /ingest/history
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_history_empty(auth_client: AsyncClient):
    """Test /ingest/history with no events."""
    response = await auth_client.get("/api/v1/ingest/history")
    assert response.status_code == 200

    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_ingest_history_with_events(
    auth_client: AsyncClient,
    garmin_raw_events,
):
    """Test /ingest/history returns events."""
    response = await auth_client.get("/api/v1/ingest/history")
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) == 5
    assert data["total"] == 5

    # Check event structure
    event = data["items"][0]
    assert "id" in event
    assert "endpoint" in event
    assert "fetched_at" in event
    assert "record_count" in event


@pytest.mark.asyncio
async def test_ingest_history_pagination(
    auth_client: AsyncClient,
    garmin_raw_events,
):
    """Test /ingest/history pagination."""
    response = await auth_client.get(
        "/api/v1/ingest/history",
        params={"page": 1, "per_page": 2},
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_ingest_history_filter_by_endpoint(
    auth_client: AsyncClient,
    garmin_raw_events,
):
    """Test /ingest/history filters by endpoint."""
    response = await auth_client.get(
        "/api/v1/ingest/history",
        params={"endpoint": "activities"},
    )
    assert response.status_code == 200

    data = response.json()
    assert all(item["endpoint"] == "activities" for item in data["items"])


# -------------------------------------------------------------------------
# Tests: Session Validation Helper
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_garmin_session_helper_no_session(auth_client: AsyncClient):
    """Test validate_garmin_session helper with no session."""
    # This is implicitly tested through /ingest/run and /ingest/run/sync
    response = await auth_client.post("/api/v1/ingest/run")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_validate_garmin_session_helper_invalid_flag(
    auth_client: AsyncClient,
    db_session,
    test_user,
):
    """Test validate_garmin_session helper with is_valid=False (empty session_data)."""
    # Create invalid session (is_valid is a property that returns False when session_data is empty)
    session = GarminSession(
        user_id=test_user.id,
        session_data=None,  # No session data = is_valid returns False
    )
    db_session.add(session)
    await db_session.commit()

    response = await auth_client.post("/api/v1/ingest/run")
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"].lower()
