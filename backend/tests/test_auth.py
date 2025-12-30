"""Tests for authentication endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.garmin import GarminSession
from app.models.user import User


class TestLocalAuth:
    """Tests for local authentication endpoints."""

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login with valid credentials."""
        with patch("app.core.session.create_session") as mock_create:
            mock_create.return_value = "test_session_id"

            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Login successful"
        assert data["user"]["email"] == "test@example.com"

    async def test_login_invalid_email(self, client: AsyncClient, test_user: User):
        """Test login with non-existent email."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "testpassword123"},
        )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    async def test_login_invalid_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    async def test_get_me_authenticated(self, auth_client: AsyncClient, test_user: User):
        """Test getting current user when authenticated."""
        response = await auth_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        """Test getting current user when not authenticated."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    async def test_logout(self, auth_client: AsyncClient):
        """Test logout endpoint."""
        with patch("app.core.session.delete_session") as mock_delete:
            mock_delete.return_value = None

            response = await auth_client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestGarminAuth:
    """Tests for Garmin authentication endpoints."""

    async def test_garmin_connect_success(
        self,
        auth_client: AsyncClient,
        test_user: User,
        mock_garmin_adapter,
        db_session,
    ):
        """Test successful Garmin account connection."""
        response = await auth_client.post(
            "/api/v1/auth/garmin/connect",
            json={"email": "garmin@example.com", "password": "garminpass"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["message"] == "Garmin account connected successfully"
        assert data["last_login"] is not None

    async def test_garmin_connect_auth_failure(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test Garmin connection with invalid credentials."""
        from app.adapters.garmin_adapter import GarminAuthError

        with patch("app.api.v1.endpoints.auth.GarminConnectAdapter") as mock_class:
            mock_adapter = MagicMock()
            mock_adapter.login.side_effect = GarminAuthError("Invalid credentials")
            mock_class.return_value = mock_adapter

            response = await auth_client.post(
                "/api/v1/auth/garmin/connect",
                json={"email": "wrong@example.com", "password": "wrongpass"},
            )

        assert response.status_code == 401
        assert "Garmin authentication failed" in response.json()["detail"]

    async def test_garmin_connect_unauthenticated(self, client: AsyncClient):
        """Test Garmin connection without local authentication."""
        response = await client.post(
            "/api/v1/auth/garmin/connect",
            json={"email": "garmin@example.com", "password": "garminpass"},
        )

        assert response.status_code == 401

    async def test_garmin_status_not_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test Garmin status when not connected."""
        response = await auth_client.get("/api/v1/auth/garmin/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["session_valid"] is False

    async def test_garmin_status_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test Garmin status when connected."""
        # Create Garmin session
        garmin_session = GarminSession(
            user_id=test_user.id,
            session_data={"oauth_token": "test"},
            last_login=datetime.now(timezone.utc),
        )
        db_session.add(garmin_session)
        await db_session.commit()

        response = await auth_client.get("/api/v1/auth/garmin/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["session_valid"] is True

    async def test_garmin_refresh_not_connected(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ):
        """Test Garmin refresh when not connected."""
        response = await auth_client.post("/api/v1/auth/garmin/refresh")

        assert response.status_code == 400
        assert "Garmin account not connected" in response.json()["detail"]

    async def test_garmin_refresh_success(
        self,
        auth_client: AsyncClient,
        test_user: User,
        mock_garmin_adapter,
        db_session,
    ):
        """Test successful Garmin session refresh."""
        # Create Garmin session
        garmin_session = GarminSession(
            user_id=test_user.id,
            session_data={"oauth_token": "old_token"},
            last_login=datetime.now(timezone.utc),
        )
        db_session.add(garmin_session)
        await db_session.commit()

        response = await auth_client.post("/api/v1/auth/garmin/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Session validated successfully"

    async def test_garmin_disconnect(
        self,
        auth_client: AsyncClient,
        test_user: User,
        db_session,
    ):
        """Test Garmin account disconnection."""
        # Create Garmin session
        garmin_session = GarminSession(
            user_id=test_user.id,
            session_data={"oauth_token": "test"},
            last_login=datetime.now(timezone.utc),
        )
        db_session.add(garmin_session)
        await db_session.commit()

        response = await auth_client.delete("/api/v1/auth/garmin/disconnect")

        assert response.status_code == 204

        # Verify session was deleted
        status_response = await auth_client.get("/api/v1/auth/garmin/status")
        assert status_response.json()["connected"] is False
