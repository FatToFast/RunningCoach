"""Authentication endpoints.

Includes local auth and Garmin connection.
Paths:
  /api/v1/auth/login, /logout, /me
  /api/v1/auth/garmin/connect, /refresh, /disconnect, /status

Note: Strava OAuth is handled by /api/v1/strava/* endpoints.
"""

import logging
from datetime import datetime, timezone as tz
from typing import Annotated, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.garmin_adapter import (
    GarminAdapterError,
    GarminAuthError,
    GarminConnectAdapter,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import verify_password_async
from app.core.session import create_session, delete_session, get_session, refresh_session
from app.models.garmin import GarminSession, GarminSyncState
from app.models.user import User

settings = get_settings()
router = APIRouter()

# Use configured session cookie name
SESSION_COOKIE_NAME = settings.session_cookie_name


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Request body for local login."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Response for successful login."""

    success: bool
    message: str
    user: dict[str, Any]


class UserResponse(BaseModel):
    """Current user response."""

    id: int
    email: str
    display_name: str | None
    timezone: str
    last_login_at: str | None


class GarminConnectRequest(BaseModel):
    """Request body for Garmin connection."""

    email: str
    password: str


class GarminConnectResponse(BaseModel):
    """Response for Garmin connection."""

    connected: bool
    message: str
    last_login: datetime | None = None


class GarminStatusResponse(BaseModel):
    """Response for Garmin connection status."""

    connected: bool
    session_valid: bool = False
    last_login: datetime | None = None
    last_sync: datetime | None = None


# -------------------------------------------------------------------------
# Dependencies
# -------------------------------------------------------------------------


async def get_current_user(
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from session.

    Args:
        session_id: Session ID from cookie.
        db: Database session.

    Returns:
        Current user.

    Raises:
        HTTPException: If not authenticated.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session_data = await get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    # Validate session data before refreshing TTL
    user_id = session_data.get("user_id")
    if not user_id:
        # Invalid session data - delete it and reject
        await delete_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        # User no longer exists - delete session and reject
        await delete_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Sliding expiry: refresh TTL only after full validation
    await refresh_session(session_id)

    return user


# -------------------------------------------------------------------------
# Local Auth Endpoints
# -------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Login with local account.

    Args:
        request: Login credentials.
        response: FastAPI response object for setting cookies.
        db: Database session.

    Returns:
        Login success response.

    Raises:
        HTTPException: If credentials are invalid.
    """
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not await verify_password_async(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user.last_login_at = datetime.now(tz.utc)
    await db.commit()

    session_id = await create_session(
        user_id=user.id,
        user_data={
            "email": user.email,
            "display_name": user.display_name,
        },
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_seconds,
    )

    return LoginResponse(
        success=True,
        message="Login successful",
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "timezone": user.timezone,
        },
    )


@router.post("/logout")
async def logout(
    response: Response,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, str]:
    """Logout and invalidate session."""
    if session_id:
        await delete_session(session_id)

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Get current authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        timezone=current_user.timezone,
        last_login_at=current_user.last_login_at.isoformat() if current_user.last_login_at else None,
    )


# -------------------------------------------------------------------------
# Garmin Endpoints (/auth/garmin/*)
# -------------------------------------------------------------------------


@router.post("/garmin/connect", response_model=GarminConnectResponse)
async def connect_garmin(
    request: GarminConnectRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GarminConnectResponse:
    """Connect Garmin account with email/password.

    FR-001: Garmin 계정 연결

    Note: garminconnect library uses synchronous login. For production,
    consider running in a thread pool to avoid blocking the event loop.

    TODO: 2FA support requires additional endpoint for challenge/response flow.
    """
    import asyncio

    try:
        adapter = GarminConnectAdapter()

        # Run synchronous login in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            adapter.login,
            request.email,
            request.password,
        )

        # Get session data from adapter
        garmin_session_data = adapter.get_session_data()

        result = await db.execute(
            select(GarminSession).where(GarminSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()

        now = datetime.now(tz.utc)

        if session:
            session.session_data = garmin_session_data
            session.last_login = now
        else:
            session = GarminSession(
                user_id=current_user.id,
                session_data=garmin_session_data,
                last_login=now,
            )
            db.add(session)

        await db.commit()

        return GarminConnectResponse(
            connected=True,
            message="Garmin account connected successfully",
            last_login=now,
        )

    except GarminAuthError as e:
        logger.warning(f"Garmin authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Garmin authentication failed. Please check your credentials.",
        )
    except GarminAdapterError as e:
        logger.error(f"Garmin API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Garmin API is currently unavailable. Please try again later.",
        )
    except Exception as e:
        logger.exception("Unexpected error during Garmin connect")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )


@router.post("/garmin/refresh")
async def refresh_garmin_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Validate and refresh Garmin session.

    Note: garminconnect library does not support explicit token refresh.
    This endpoint validates the stored session by attempting to use it.
    If the session is invalid, the user must re-connect via /garmin/connect.

    Returns:
        Success if session is valid, error if session needs re-authentication.
    """
    import asyncio

    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    if not session.session_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid session data. Please reconnect your Garmin account.",
        )

    try:
        adapter = GarminConnectAdapter()

        # Attempt to login with stored session data
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            adapter.login_with_session,
            session.session_data,
        )

        # If successful, update session data (may have refreshed internally)
        new_session_data = adapter.get_session_data()
        session.session_data = new_session_data
        session.last_login = datetime.now(tz.utc)

        await db.commit()

        return {"success": True, "message": "Session validated successfully"}

    except GarminAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please reconnect your Garmin account.",
        )
    except Exception as e:
        logger.exception("Unexpected error during Garmin session refresh")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session validation failed. Please try again.",
        )


class DisconnectResponse(BaseModel):
    """Response for disconnect endpoints."""

    message: str


@router.delete("/garmin/disconnect", response_model=DisconnectResponse)
async def disconnect_garmin(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> DisconnectResponse:
    """Disconnect Garmin account."""
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if session:
        await db.delete(session)
        await db.commit()
        return DisconnectResponse(message="Garmin account disconnected")

    return DisconnectResponse(message="No Garmin account was connected")


@router.get("/garmin/status", response_model=GarminStatusResponse)
async def get_garmin_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    validate: bool = Query(
        False,
        description="If True, validates session with Garmin API (slower but accurate)",
    ),
) -> GarminStatusResponse:
    """Get current Garmin connection status.

    Args:
        current_user: Authenticated user.
        db: Database session.
        validate: If True, makes an API call to verify session is actually valid.
                  Default False for fast status check.

    Returns:
        Connection status with session validity.
    """
    import asyncio

    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return GarminStatusResponse(connected=False)

    # Fast check: session_data exists and not empty
    session_valid = session.is_valid

    # Optional deep validation: actually test with Garmin API
    if validate and session_valid:
        try:
            adapter = GarminConnectAdapter()
            loop = asyncio.get_event_loop()
            is_actually_valid = await loop.run_in_executor(
                None,
                lambda: adapter.validate_session(session.session_data),
            )
            session_valid = is_actually_valid
        except GarminAuthError:
            session_valid = False
        except Exception as e:
            logger.warning(f"Garmin session validation error: {e}")
            # On unexpected error, keep the fast-check result
            pass

    sync_result = await db.execute(
        select(GarminSyncState)
        .where(GarminSyncState.user_id == current_user.id)
        .order_by(GarminSyncState.last_success_at.desc())
        .limit(1)
    )
    sync_state = sync_result.scalar_one_or_none()

    return GarminStatusResponse(
        connected=True,
        session_valid=session_valid,
        last_login=session.last_login,
        last_sync=sync_state.last_success_at if sync_state else None,
    )
