"""Tests for Strava integration endpoints."""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.activity import Activity
from app.models.strava import StravaActivityMap, StravaSession, StravaSyncState
from app.models.user import User


class TestStravaOAuthCSRF:
    """Tests for OAuth CSRF protection."""

    async def test_connect_generates_state_token(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test that /connect generates a state token in the auth_url."""
        with patch("app.api.v1.endpoints.strava.settings") as mock_settings:
            mock_settings.strava_client_id = "test_client_id"
            mock_settings.strava_redirect_uri = "https://example.com/callback"

            response = await auth_client.get("/api/v1/strava/connect")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state=" in data["auth_url"]

    async def test_callback_invalid_state_returns_400(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that callback with invalid state returns 400."""
        response = await auth_client.post(
            "/api/v1/strava/callback",
            json={
                "code": "test_code",
                "state": "invalid_state_token",
            },
        )

        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    async def test_callback_missing_state_returns_400(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that callback without state returns 400."""
        response = await auth_client.post(
            "/api/v1/strava/callback",
            json={
                "code": "test_code",
                "state": None,
            },
        )

        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    async def test_callback_expired_state_returns_400(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that callback with expired state returns 400."""
        from app.api.v1.endpoints.strava import _oauth_states

        # Create an expired state
        expired_state = "expired_test_state"
        _oauth_states[expired_state] = (test_user.id, time.time() - 100)  # Expired 100s ago

        response = await auth_client.post(
            "/api/v1/strava/callback",
            json={
                "code": "test_code",
                "state": expired_state,
            },
        )

        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    async def test_callback_wrong_user_state_returns_400(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that callback with state for different user returns 400."""
        from app.api.v1.endpoints.strava import _oauth_states

        # Create a state for a different user
        wrong_user_state = "wrong_user_state"
        _oauth_states[wrong_user_state] = (test_user.id + 999, time.time() + 600)

        response = await auth_client.post(
            "/api/v1/strava/callback",
            json={
                "code": "test_code",
                "state": wrong_user_state,
            },
        )

        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    async def test_callback_valid_state_proceeds(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that callback with valid state proceeds to token exchange."""
        from app.api.v1.endpoints.strava import _oauth_states

        # Create a valid state
        valid_state = "valid_test_state"
        _oauth_states[valid_state] = (test_user.id, time.time() + 600)

        with patch("app.api.v1.endpoints.strava.settings") as mock_settings:
            mock_settings.strava_client_id = "test_client_id"
            mock_settings.strava_client_secret = "test_secret"

            # Mock httpx to return an error (we're testing state validation, not the full flow)
            with patch("httpx.AsyncClient") as mock_httpx:
                mock_response = MagicMock()
                mock_response.status_code = 400
                mock_response.raise_for_status.side_effect = Exception("Token exchange failed")

                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_httpx.return_value = mock_client

                response = await auth_client.post(
                    "/api/v1/strava/callback",
                    json={
                        "code": "test_code",
                        "state": valid_state,
                    },
                )

        # The request should have passed state validation and reached token exchange
        # (which fails with mock, returning 400 from the exchange, not from state validation)
        assert response.status_code == 400
        assert "OAuth exchange failed" in response.json()["detail"]

    async def test_state_is_single_use(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test that OAuth state can only be used once."""
        from app.api.v1.endpoints.strava import _oauth_states

        # Create a valid state
        single_use_state = "single_use_state"
        _oauth_states[single_use_state] = (test_user.id, time.time() + 600)

        # First attempt (will fail at token exchange but state is consumed)
        with patch("app.api.v1.endpoints.strava.settings") as mock_settings:
            mock_settings.strava_client_id = "test_client_id"
            mock_settings.strava_client_secret = "test_secret"

            with patch("httpx.AsyncClient") as mock_httpx:
                mock_response = MagicMock()
                mock_response.raise_for_status.side_effect = Exception("Token exchange failed")
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_httpx.return_value = mock_client

                await auth_client.post(
                    "/api/v1/strava/callback",
                    json={"code": "test_code", "state": single_use_state},
                )

        # Second attempt with same state should fail validation
        response = await auth_client.post(
            "/api/v1/strava/callback",
            json={
                "code": "test_code",
                "state": single_use_state,
            },
        )

        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]


class TestStravaStatus:
    """Tests for Strava connection status."""

    async def test_status_not_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test status when not connected."""
        response = await auth_client.get("/api/v1/strava/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    async def test_status_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test status when connected."""
        session = StravaSession(
            user_id=test_user.id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.now(timezone.utc),
        )
        db_session.add(session)
        await db_session.commit()

        response = await auth_client.get("/api/v1/strava/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True

    async def test_disconnect(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test disconnecting Strava account."""
        session = StravaSession(
            user_id=test_user.id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.now(timezone.utc),
        )
        db_session.add(session)
        await db_session.commit()

        response = await auth_client.delete("/api/v1/strava/disconnect")
        assert response.status_code == 204

        # Verify disconnected
        status_response = await auth_client.get("/api/v1/strava/status")
        assert status_response.json()["connected"] is False


class TestStravaSync:
    """Tests for Strava sync endpoints."""

    async def test_sync_run_not_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test running sync when not connected."""
        response = await auth_client.post("/api/v1/strava/sync/run")

        assert response.status_code == 400
        assert "not connected" in response.json()["detail"]

    async def test_sync_run_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test running sync when connected."""
        session = StravaSession(
            user_id=test_user.id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.now(timezone.utc),
        )
        db_session.add(session)
        await db_session.commit()

        response = await auth_client.post("/api/v1/strava/sync/run")

        assert response.status_code == 200
        data = response.json()
        assert data["started"] is True
        assert "pending_count" in data

    async def test_sync_status_counts_pending(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test sync status correctly counts pending uploads."""
        response = await auth_client.get("/api/v1/strava/sync/status")

        assert response.status_code == 200
        data = response.json()
        # All sample_activities should be pending (not uploaded)
        assert data["pending_uploads"] == len(sample_activities)
        assert data["completed_uploads"] == 0


class TestStravaActivitiesList:
    """Tests for activity upload status list."""

    async def test_list_activities_pagination(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test activity list pagination."""
        response = await auth_client.get(
            "/api/v1/strava/activities?page=1&per_page=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["per_page"] == 2

    async def test_list_activities_filter_pending(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test filtering activities by pending status."""
        # Mark one activity as uploaded
        activity_map = StravaActivityMap(
            activity_id=sample_activities[0].id,
            strava_activity_id=123456789,
            uploaded_at=datetime.now(timezone.utc),
        )
        db_session.add(activity_map)
        await db_session.commit()

        response = await auth_client.get("/api/v1/strava/activities?status_filter=pending")

        assert response.status_code == 200
        data = response.json()
        # 5 total - 1 uploaded = 4 pending
        assert data["total"] == 4
        for item in data["items"]:
            assert item["status"] == "pending"

    async def test_list_activities_filter_uploaded(
        self,
        auth_client: AsyncClient,
        test_user: User,
        sample_activities: list[Activity],
        db_session,
    ):
        """Test filtering activities by uploaded status."""
        # Mark two activities as uploaded
        for activity in sample_activities[:2]:
            activity_map = StravaActivityMap(
                activity_id=activity.id,
                strava_activity_id=100000 + activity.id,
                uploaded_at=datetime.now(timezone.utc),
            )
            db_session.add(activity_map)
        await db_session.commit()

        response = await auth_client.get("/api/v1/strava/activities?status_filter=uploaded")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "uploaded"

    async def test_list_activities_invalid_status_filter(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test filtering with invalid status returns 422."""
        response = await auth_client.get("/api/v1/strava/activities?status_filter=invalid")

        assert response.status_code == 422


class TestStravaAuthentication:
    """Tests for authentication requirements."""

    async def test_unauthenticated_connect(self, client: AsyncClient):
        """Test connect without authentication returns 401."""
        response = await client.get("/api/v1/strava/connect")
        assert response.status_code == 401

    async def test_unauthenticated_status(self, client: AsyncClient):
        """Test status without authentication returns 401."""
        response = await client.get("/api/v1/strava/status")
        assert response.status_code == 401
