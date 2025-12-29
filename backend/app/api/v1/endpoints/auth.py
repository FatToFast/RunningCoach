"""Authentication endpoints.

Includes local auth, Garmin connection, and Strava OAuth.
Paths:
  /api/v1/auth/login, /logout, /me
  /api/v1/auth/garmin/connect, /refresh, /disconnect, /status
  /api/v1/auth/strava/connect, /callback, /refresh, /status
"""

from datetime import datetime, timezone as tz
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.garmin_adapter import GarminAdapter
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import verify_password
from app.core.session import create_session, delete_session, get_session
from app.models.garmin import GarminSession, GarminSyncState
from app.models.strava import StravaSession, StravaSyncState
from app.models.user import User

settings = get_settings()
router = APIRouter()

SESSION_COOKIE_NAME = "session_id"


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


class StravaConnectResponse(BaseModel):
    """Response for Strava OAuth initiation."""

    auth_url: str
    message: str


class StravaCallbackRequest(BaseModel):
    """OAuth callback data."""

    code: str
    state: str | None = None


class StravaStatusResponse(BaseModel):
    """Response for Strava connection status."""

    connected: bool
    expires_at: datetime | None = None
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

    user_id = session_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

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

    if not user or not verify_password(request.password, user.password_hash):
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

    FR-001: Garmin 계정 연결 - 2FA 지원, 세션 만료 시 자동 갱신
    """
    try:
        adapter = GarminAdapter()
        tokens = await adapter.login(request.email, request.password)

        result = await db.execute(
            select(GarminSession).where(GarminSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()

        now = datetime.now(tz.utc)

        if session:
            session.oauth1_token = tokens.get("oauth1_token")
            session.oauth2_token = tokens.get("oauth2_token")
            session.expires_at = tokens.get("expires_at")
            session.last_login = now
        else:
            session = GarminSession(
                user_id=current_user.id,
                oauth1_token=tokens.get("oauth1_token"),
                oauth2_token=tokens.get("oauth2_token"),
                expires_at=tokens.get("expires_at"),
                last_login=now,
            )
            db.add(session)

        await db.commit()

        return GarminConnectResponse(
            connected=True,
            message="Garmin account connected successfully",
            last_login=now,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Garmin authentication failed: {str(e)}",
        )


@router.post("/garmin/refresh")
async def refresh_garmin_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Refresh Garmin session tokens."""
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    try:
        adapter = GarminAdapter()
        new_tokens = await adapter.refresh_session(session.oauth2_token)

        session.oauth2_token = new_tokens.get("oauth2_token")
        session.expires_at = new_tokens.get("expires_at")
        session.last_login = datetime.now(tz.utc)

        await db.commit()

        return {"success": True, "message": "Session refreshed successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Session refresh failed: {str(e)}",
        )


@router.delete("/garmin/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_garmin(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect Garmin account."""
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if session:
        await db.delete(session)
        await db.commit()


@router.get("/garmin/status", response_model=GarminStatusResponse)
async def get_garmin_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GarminStatusResponse:
    """Get current Garmin connection status."""
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        return GarminStatusResponse(connected=False)

    session_valid = False
    if session.expires_at:
        session_valid = session.expires_at > datetime.now(tz.utc)

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


# -------------------------------------------------------------------------
# Strava Endpoints (/auth/strava/*)
# -------------------------------------------------------------------------


@router.post("/strava/connect", response_model=StravaConnectResponse)
async def connect_strava(
    current_user: Annotated[User, Depends(get_current_user)],
) -> StravaConnectResponse:
    """Initiate Strava OAuth connection."""
    client_id = settings.strava_client_id
    redirect_uri = settings.strava_redirect_uri

    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Strava OAuth not configured",
        )

    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=activity:write,activity:read_all"
        f"&state={current_user.id}"
    )

    return StravaConnectResponse(
        auth_url=auth_url,
        message="Redirect user to auth_url to authorize Strava access",
    )


@router.post("/strava/callback")
async def strava_callback(
    request: StravaCallbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Handle Strava OAuth callback."""
    import httpx

    client_id = settings.strava_client_id
    client_secret = settings.strava_client_secret

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Strava OAuth not configured",
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": request.code,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            tokens = response.json()

        result = await db.execute(
            select(StravaSession).where(StravaSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()

        expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=tz.utc)

        if session:
            session.access_token = tokens["access_token"]
            session.refresh_token = tokens["refresh_token"]
            session.expires_at = expires_at
        else:
            session = StravaSession(
                user_id=current_user.id,
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                expires_at=expires_at,
            )
            db.add(session)

        await db.commit()

        return {"success": True, "message": "Strava account connected successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth exchange failed: {str(e)}",
        )


@router.post("/strava/refresh")
async def refresh_strava_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Refresh Strava session tokens."""
    import httpx

    result = await db.execute(
        select(StravaSession).where(StravaSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session or not session.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strava account not connected",
        )

    client_id = settings.strava_client_id
    client_secret = settings.strava_client_secret

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": session.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            tokens = response.json()

        session.access_token = tokens["access_token"]
        session.refresh_token = tokens["refresh_token"]
        session.expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=tz.utc)

        await db.commit()

        return {"success": True, "message": "Strava session refreshed successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
        )


@router.get("/strava/status", response_model=StravaStatusResponse)
async def get_strava_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StravaStatusResponse:
    """Get current Strava connection status."""
    session_result = await db.execute(
        select(StravaSession).where(StravaSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        return StravaStatusResponse(connected=False)

    sync_result = await db.execute(
        select(StravaSyncState).where(StravaSyncState.user_id == current_user.id)
    )
    sync_state = sync_result.scalar_one_or_none()

    return StravaStatusResponse(
        connected=session.access_token is not None,
        expires_at=session.expires_at,
        last_sync=sync_state.last_success_at if sync_state else None,
    )
