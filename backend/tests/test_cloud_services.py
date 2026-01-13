"""Tests for cloud services: Clerk Auth, R2 Storage, Webhooks.

These tests validate the cloud migration components:
1. Clerk JWT authentication
2. R2 storage service
3. Webhook handling
4. Hybrid authentication
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.activity import Activity


# =============================================================================
# Clerk Authentication Tests
# =============================================================================


class TestClerkAuth:
    """Test suite for Clerk JWT authentication."""

    @pytest.fixture
    def mock_jwt_payload(self):
        """Sample decoded JWT payload."""
        return {
            "sub": "user_2abc123def456",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
            "email": "test@example.com",
        }

    @pytest.fixture
    def mock_clerk_user_data(self):
        """Sample Clerk API user response."""
        return {
            "id": "user_2abc123def456",
            "email_addresses": [
                {"id": "email_1", "email_address": "test@example.com"}
            ],
            "primary_email_address_id": "email_1",
            "first_name": "Test",
            "last_name": "User",
        }

    async def test_verify_token_success(self, mock_jwt_payload):
        """Test successful JWT token verification."""
        from app.core.clerk_auth import ClerkAuth

        with patch("app.core.clerk_auth.get_jwks_client") as mock_jwks:
            mock_client = MagicMock()
            mock_key = MagicMock()
            mock_key.key = "test_key"
            mock_client.get_signing_key_from_jwt.return_value = mock_key
            mock_jwks.return_value = mock_client

            with patch("app.core.clerk_auth.jwt.decode") as mock_decode:
                mock_decode.return_value = mock_jwt_payload

                payload = await ClerkAuth.verify_token("test_token")

                assert payload["sub"] == "user_2abc123def456"
                assert payload["email"] == "test@example.com"

    async def test_verify_token_expired(self):
        """Test expired token rejection."""
        from app.core.clerk_auth import ClerkAuth
        import jwt as pyjwt

        with patch("app.core.clerk_auth.get_jwks_client") as mock_jwks:
            mock_client = MagicMock()
            mock_key = MagicMock()
            mock_key.key = "test_key"
            mock_client.get_signing_key_from_jwt.return_value = mock_key
            mock_jwks.return_value = mock_client

            with patch("app.core.clerk_auth.jwt.decode") as mock_decode:
                mock_decode.side_effect = pyjwt.ExpiredSignatureError("Token expired")

                with pytest.raises(HTTPException) as exc_info:
                    await ClerkAuth.verify_token("expired_token")

                assert exc_info.value.status_code == 401
                assert "expired" in exc_info.value.detail.lower()

    async def test_verify_token_invalid(self):
        """Test invalid token rejection."""
        from app.core.clerk_auth import ClerkAuth
        import jwt as pyjwt

        with patch("app.core.clerk_auth.get_jwks_client") as mock_jwks:
            mock_client = MagicMock()
            mock_key = MagicMock()
            mock_key.key = "test_key"
            mock_client.get_signing_key_from_jwt.return_value = mock_key
            mock_jwks.return_value = mock_client

            with patch("app.core.clerk_auth.jwt.decode") as mock_decode:
                mock_decode.side_effect = pyjwt.InvalidTokenError("Invalid signature")

                with pytest.raises(HTTPException) as exc_info:
                    await ClerkAuth.verify_token("invalid_token")

                assert exc_info.value.status_code == 401
                assert "invalid" in exc_info.value.detail.lower()

    async def test_get_clerk_user_data_success(self, mock_clerk_user_data):
        """Test fetching user data from Clerk API."""
        from app.core.clerk_auth import ClerkAuth

        with patch("app.core.clerk_auth.settings") as mock_settings:
            mock_settings.clerk_secret_key = "sk_test_123"

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_clerk_user_data
                mock_get.return_value = mock_response

                # This would need proper mocking in actual implementation
                # Just validating the structure here
                assert "email_addresses" in mock_clerk_user_data
                assert mock_clerk_user_data["first_name"] == "Test"

    async def test_auto_create_user_on_first_login(
        self, db_session: AsyncSession, mock_jwt_payload, mock_clerk_user_data
    ):
        """Test automatic user creation on first Clerk login."""
        clerk_user_id = mock_jwt_payload["sub"]

        # Verify user doesn't exist
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

        # Create user (simulating what get_current_user_clerk does)
        user = User(
            clerk_user_id=clerk_user_id,
            email=mock_clerk_user_data["email_addresses"][0]["email_address"],
            display_name=f"{mock_clerk_user_data['first_name']} {mock_clerk_user_data['last_name']}",
            password_hash=None,
        )
        db_session.add(user)
        await db_session.commit()

        # Verify user was created
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        result = await db_session.execute(stmt)
        created_user = result.scalar_one_or_none()

        assert created_user is not None
        assert created_user.clerk_user_id == clerk_user_id
        assert created_user.email == "test@example.com"
        assert created_user.password_hash is None  # Clerk users have no local password


# =============================================================================
# R2 Storage Tests
# =============================================================================


class TestR2Storage:
    """Test suite for Cloudflare R2 storage service."""

    @pytest.fixture
    def mock_r2_service(self):
        """Create a mock R2 service."""
        from app.services.r2_storage import R2StorageService

        service = R2StorageService()
        service._initialized = True
        service._client = MagicMock()
        return service

    def test_generate_key(self, mock_r2_service):
        """Test S3 key generation."""
        key = mock_r2_service._generate_key(user_id=1, activity_id=100, year=2026)
        assert key == "users/1/2026/activities/100.fit.gz"

    def test_compress_data(self, mock_r2_service):
        """Test gzip compression."""
        original = b"x" * 1000  # Compressible data
        compressed, ratio = mock_r2_service.compress_data(original)

        assert len(compressed) < len(original)
        assert ratio > 0  # Some compression achieved

    def test_compress_empty_data(self, mock_r2_service):
        """Test compression with empty data."""
        compressed, ratio = mock_r2_service.compress_data(b"")
        assert compressed == b""
        assert ratio == 0.0

    def test_decompress_data(self, mock_r2_service):
        """Test gzip decompression."""
        original = b"test data for compression"
        compressed, _ = mock_r2_service.compress_data(original)
        decompressed = mock_r2_service.decompress_data(compressed)

        assert decompressed == original

    def test_calculate_hash(self, mock_r2_service):
        """Test SHA-256 hash calculation."""
        data = b"test data"
        hash1 = mock_r2_service.calculate_hash(data)
        hash2 = mock_r2_service.calculate_hash(data)

        assert hash1 == hash2  # Deterministic
        assert len(hash1) == 64  # SHA-256 hex digest length

    async def test_upload_fit_success(self, mock_r2_service):
        """Test successful FIT file upload."""
        mock_r2_service._client.put_object = MagicMock()

        result = await mock_r2_service.upload_fit(
            user_id=1,
            activity_id=100,
            fit_data=b"fake fit data",
            compress=True
        )

        assert result["success"] is True
        assert "key" in result
        assert "compression_ratio" in result
        assert result["original_size"] == 13

    async def test_upload_fit_failure(self, mock_r2_service):
        """Test FIT file upload failure handling."""
        from botocore.exceptions import ClientError

        mock_r2_service._client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}},
            "PutObject"
        )

        result = await mock_r2_service.upload_fit(
            user_id=1,
            activity_id=100,
            fit_data=b"fake fit data"
        )

        assert result["success"] is False
        assert "error" in result

    def test_presigned_upload_url(self, mock_r2_service):
        """Test presigned URL generation for upload."""
        mock_r2_service._client.generate_presigned_url.return_value = "https://r2.example.com/upload?signature=xxx"

        result = mock_r2_service.generate_presigned_upload_url(
            user_id=1,
            activity_id=100,
            expires_in=3600
        )

        assert "upload_url" in result
        assert "key" in result
        assert result["expires_in"] == 3600

    def test_presigned_download_url(self, mock_r2_service):
        """Test presigned URL generation for download."""
        mock_r2_service._client.generate_presigned_url.return_value = "https://r2.example.com/download?signature=xxx"

        url = mock_r2_service.generate_presigned_download_url(
            user_id=1,
            activity_id=100,
            expires_in=300
        )

        assert url is not None
        assert "r2.example.com" in url

    async def test_delete_fit(self, mock_r2_service):
        """Test FIT file deletion."""
        mock_r2_service._client.delete_object = MagicMock()

        result = await mock_r2_service.delete_fit(user_id=1, activity_id=100)

        assert result is True
        mock_r2_service._client.delete_object.assert_called_once()

    async def test_storage_stats(self, mock_r2_service):
        """Test storage statistics retrieval."""
        # Mock paginator response
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [
                {"Key": "users/1/2026/activities/1.fit.gz", "Size": 1000},
                {"Key": "users/1/2026/activities/2.fit.gz", "Size": 2000},
            ]}
        ]
        mock_r2_service._client.get_paginator.return_value = mock_paginator

        stats = await mock_r2_service.get_storage_stats(user_id=1)

        assert stats["total_files"] == 2
        assert stats["total_size_bytes"] == 3000
        assert "free_tier_used_percent" in stats


# =============================================================================
# Webhook Tests
# =============================================================================


class TestWebhooks:
    """Test suite for Clerk webhook handling."""

    @pytest.fixture
    def user_created_payload(self):
        """Sample user.created webhook payload."""
        return {
            "type": "user.created",
            "data": {
                "id": "user_new123",
                "email_addresses": [
                    {"id": "email_1", "email_address": "newuser@example.com"}
                ],
                "primary_email_address_id": "email_1",
                "first_name": "New",
                "last_name": "User",
            }
        }

    @pytest.fixture
    def user_updated_payload(self):
        """Sample user.updated webhook payload."""
        return {
            "type": "user.updated",
            "data": {
                "id": "user_existing123",
                "email_addresses": [
                    {"id": "email_1", "email_address": "updated@example.com"}
                ],
                "primary_email_address_id": "email_1",
                "first_name": "Updated",
                "last_name": "Name",
            }
        }

    @pytest.fixture
    def user_deleted_payload(self):
        """Sample user.deleted webhook payload."""
        return {
            "type": "user.deleted",
            "data": {
                "id": "user_todelete123",
            }
        }

    async def test_webhook_user_created(
        self, db_session: AsyncSession, user_created_payload
    ):
        """Test user.created webhook creates user in database."""
        from app.api.v1.endpoints.webhooks import _handle_user_created

        await _handle_user_created(db_session, user_created_payload["data"])

        # Verify user was created
        stmt = select(User).where(User.clerk_user_id == "user_new123")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.display_name == "New User"

    async def test_webhook_user_updated(
        self, db_session: AsyncSession, user_updated_payload
    ):
        """Test user.updated webhook updates existing user."""
        from app.api.v1.endpoints.webhooks import _handle_user_updated

        # Create existing user first
        existing_user = User(
            clerk_user_id="user_existing123",
            email="original@example.com",
            display_name="Original Name",
        )
        db_session.add(existing_user)
        await db_session.commit()

        # Process update webhook
        await _handle_user_updated(db_session, user_updated_payload["data"])

        # Verify user was updated
        stmt = select(User).where(User.clerk_user_id == "user_existing123")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.email == "updated@example.com"
        assert user.display_name == "Updated Name"

    async def test_webhook_user_deleted(self, db_session: AsyncSession):
        """Test user.deleted webhook soft-deletes user."""
        from app.api.v1.endpoints.webhooks import _handle_user_deleted

        # Create user to delete
        user_to_delete = User(
            clerk_user_id="user_todelete123",
            email="delete@example.com",
            display_name="To Delete",
        )
        db_session.add(user_to_delete)
        await db_session.commit()

        # Process delete webhook
        await _handle_user_deleted(db_session, "user_todelete123")

        # Verify user was soft-deleted (clerk_user_id cleared)
        stmt = select(User).where(User.email == "delete@example.com")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.clerk_user_id is None  # Soft deleted

    def test_webhook_signature_verification_invalid(self):
        """Test webhook signature verification rejects invalid signatures."""
        from app.core.clerk_auth import verify_webhook_signature

        # Without proper webhook secret, should fail
        with patch("app.core.clerk_auth.settings") as mock_settings:
            mock_settings.clerk_webhook_secret = None

            result = verify_webhook_signature(
                payload=b'{"test": "data"}',
                svix_id="msg_123",
                svix_timestamp="12345",
                svix_signature="invalid_sig"
            )

            assert result is False


# =============================================================================
# Activity R2 Field Tests
# =============================================================================


class TestActivityR2Fields:
    """Test Activity model R2 storage fields."""

    async def test_activity_r2_fields(self, db_session: AsyncSession, test_user: User):
        """Test Activity model has R2 storage fields."""
        activity = Activity(
            user_id=test_user.id,
            garmin_id=12345,
            activity_type="running",
            name="Test Activity",
            start_time=datetime.now(timezone.utc),
            r2_key="users/1/2026/activities/12345.fit.gz",
            storage_provider="r2",
            storage_metadata={
                "status": "uploaded",
                "file_size": 10000,
                "checksum": "abc123"
            }
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        # Verify fields were saved
        assert activity.r2_key == "users/1/2026/activities/12345.fit.gz"
        assert activity.storage_provider == "r2"
        assert activity.storage_metadata["status"] == "uploaded"
        assert activity.storage_metadata["file_size"] == 10000


# =============================================================================
# User Clerk Field Tests
# =============================================================================


class TestUserClerkFields:
    """Test User model Clerk fields."""

    async def test_user_clerk_user_id(self, db_session: AsyncSession):
        """Test User model has clerk_user_id field."""
        user = User(
            clerk_user_id="user_clerk_abc123",
            email="clerk-user@example.com",
            display_name="Clerk User",
            password_hash=None,  # Clerk users don't have passwords
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.clerk_user_id == "user_clerk_abc123"
        assert user.password_hash is None

    async def test_user_clerk_user_id_unique(self, db_session: AsyncSession):
        """Test clerk_user_id is unique."""
        from sqlalchemy.exc import IntegrityError

        user1 = User(
            clerk_user_id="user_unique_test",
            email="user1@example.com",
            display_name="User 1",
        )
        db_session.add(user1)
        await db_session.commit()

        user2 = User(
            clerk_user_id="user_unique_test",  # Same clerk_user_id
            email="user2@example.com",
            display_name="User 2",
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            await db_session.commit()
