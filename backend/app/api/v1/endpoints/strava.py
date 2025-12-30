"""Strava integration endpoints."""

import logging
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import Activity
from app.models.strava import StravaActivityMap, StravaSession, StravaSyncState
from app.models.user import User
from app.observability import get_metrics_backend

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class StravaConnectResponse(BaseModel):
    """Strava OAuth initiation response."""

    auth_url: str
    message: str


class StravaStatusResponse(BaseModel):
    """Strava connection status."""

    connected: bool
    expires_at: datetime | None = None
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None


class StravaCallbackRequest(BaseModel):
    """OAuth callback data."""

    code: str
    state: str | None = None


class StravaCallbackResponse(BaseModel):
    """OAuth callback result."""

    success: bool
    message: str


class SyncRunResponse(BaseModel):
    """Sync run response."""

    started: bool
    message: str
    pending_count: int


class SyncStatusResponse(BaseModel):
    """Sync status response."""

    last_sync_at: datetime | None
    last_success_at: datetime | None
    pending_uploads: int
    completed_uploads: int


class UploadStatusResponse(BaseModel):
    """Activity upload status."""

    activity_id: int
    garmin_id: int
    strava_activity_id: int | None
    uploaded_at: datetime | None
    status: str  # pending, uploaded, failed


# -------------------------------------------------------------------------
# OAuth Endpoints
# -------------------------------------------------------------------------


@router.get("/connect", response_model=StravaConnectResponse)
async def initiate_strava_connect(
    current_user: Annotated[User, Depends(get_current_user)],
) -> StravaConnectResponse:
    """Initiate Strava OAuth flow.

    Args:
        current_user: Authenticated user.

    Returns:
        OAuth authorization URL.
    """
    # Build OAuth URL
    # Note: In production, use a proper OAuth library
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


@router.post("/callback", response_model=StravaCallbackResponse)
async def handle_strava_callback(
    request: StravaCallbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StravaCallbackResponse:
    """Handle Strava OAuth callback.

    Args:
        request: OAuth callback data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Callback result.
    """
    import httpx

    client_id = settings.strava_client_id
    client_secret = settings.strava_client_secret

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Strava OAuth not configured",
        )

    metrics = get_metrics_backend()
    start_time = time.perf_counter()
    status_code = 500
    try:
        # Exchange code for tokens
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
            status_code = response.status_code
            response.raise_for_status()
            tokens = response.json()

        # Save or update session
        result = await db.execute(
            select(StravaSession).where(StravaSession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()

        expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)

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

        return StravaCallbackResponse(
            success=True,
            message="Strava account connected successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth exchange failed: {str(e)}",
        )
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.observe_external_api("strava", "oauth_token", status_code, duration_ms)
        logger.info(
            "Strava API oauth_token status=%s duration_ms=%.2f",
            status_code,
            duration_ms,
        )


@router.get("/status", response_model=StravaStatusResponse)
async def get_strava_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StravaStatusResponse:
    """Get Strava connection status.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Connection status.
    """
    session_result = await db.execute(
        select(StravaSession).where(StravaSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    sync_result = await db.execute(
        select(StravaSyncState).where(StravaSyncState.user_id == current_user.id)
    )
    sync_state = sync_result.scalar_one_or_none()

    return StravaStatusResponse(
        connected=session is not None and session.access_token is not None,
        expires_at=session.expires_at if session else None,
        last_sync_at=sync_state.last_sync_at if sync_state else None,
        last_success_at=sync_state.last_success_at if sync_state else None,
    )


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_strava(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect Strava account.

    Args:
        current_user: Authenticated user.
        db: Database session.
    """
    result = await db.execute(
        select(StravaSession).where(StravaSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if session:
        await db.delete(session)
        await db.commit()


class RefreshResponse(BaseModel):
    """Token refresh response."""

    success: bool
    message: str
    expires_at: datetime | None = None


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_strava_tokens(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """Refresh Strava OAuth tokens.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Refresh result.
    """
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

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Strava OAuth not configured",
        )

    metrics = get_metrics_backend()
    start_time = time.perf_counter()
    status_code = 500
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
            status_code = response.status_code
            response.raise_for_status()
            tokens = response.json()

        session.access_token = tokens["access_token"]
        session.refresh_token = tokens["refresh_token"]
        session.expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)

        await db.commit()

        return RefreshResponse(
            success=True,
            message="Strava tokens refreshed successfully",
            expires_at=session.expires_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
        )
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.observe_external_api("strava", "oauth_refresh", status_code, duration_ms)
        logger.info(
            "Strava API oauth_refresh status=%s duration_ms=%.2f",
            status_code,
            duration_ms,
        )


# -------------------------------------------------------------------------
# Sync Endpoints
# -------------------------------------------------------------------------


@router.post("/sync/run", response_model=SyncRunResponse)
async def run_strava_sync(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    force: bool = Query(False, description="Force re-upload already synced activities"),
) -> SyncRunResponse:
    """Trigger Strava sync for pending activities.

    FR-040: Strava 자동 동기화

    Args:
        current_user: Authenticated user.
        db: Database session.
        force: Force re-upload.

    Returns:
        Sync job status.
    """
    # Check Strava connection
    session_result = await db.execute(
        select(StravaSession).where(StravaSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    if not session or not session.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strava account not connected",
        )

    # Count pending uploads
    if force:
        # All activities
        pending_query = select(Activity).where(Activity.user_id == current_user.id)
    else:
        # Activities not yet uploaded
        pending_query = (
            select(Activity)
            .outerjoin(StravaActivityMap)
            .where(
                Activity.user_id == current_user.id,
                StravaActivityMap.id == None,
            )
        )

    pending_result = await db.execute(pending_query)
    pending_count = len(pending_result.scalars().all())

    # TODO: Queue Celery task for background sync
    # task = sync_to_strava.delay(user_id=current_user.id, force=force)

    return SyncRunResponse(
        started=True,
        message="Strava sync job queued",
        pending_count=pending_count,
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    """Get Strava sync status.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Sync status.
    """
    # Get sync state
    sync_result = await db.execute(
        select(StravaSyncState).where(StravaSyncState.user_id == current_user.id)
    )
    sync_state = sync_result.scalar_one_or_none()

    # Count pending (not uploaded)
    from sqlalchemy import func

    pending_result = await db.execute(
        select(func.count(Activity.id))
        .outerjoin(StravaActivityMap)
        .where(
            Activity.user_id == current_user.id,
            StravaActivityMap.id == None,
        )
    )
    pending_count = pending_result.scalar() or 0

    # Count completed
    completed_result = await db.execute(
        select(func.count(StravaActivityMap.id))
        .join(Activity)
        .where(Activity.user_id == current_user.id)
    )
    completed_count = completed_result.scalar() or 0

    return SyncStatusResponse(
        last_sync_at=sync_state.last_sync_at if sync_state else None,
        last_success_at=sync_state.last_success_at if sync_state else None,
        pending_uploads=pending_count,
        completed_uploads=completed_count,
    )


# -------------------------------------------------------------------------
# Activity Upload Status
# -------------------------------------------------------------------------


@router.get("/activities", response_model=list[UploadStatusResponse])
async def list_activity_uploads(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, regex="^(pending|uploaded|failed)$"),
) -> list[UploadStatusResponse]:
    """List activity upload statuses.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        status_filter: Filter by status.

    Returns:
        Upload statuses.
    """
    # Get activities with optional Strava map
    query = (
        select(Activity, StravaActivityMap)
        .outerjoin(StravaActivityMap)
        .where(Activity.user_id == current_user.id)
        .order_by(Activity.start_time.desc())
    )

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    uploads = []
    for activity, strava_map in rows:
        if strava_map:
            upload_status = "uploaded"
        else:
            upload_status = "pending"

        # Apply filter
        if status_filter and upload_status != status_filter:
            continue

        uploads.append(
            UploadStatusResponse(
                activity_id=activity.id,
                garmin_id=activity.garmin_id,
                strava_activity_id=strava_map.strava_activity_id if strava_map else None,
                uploaded_at=strava_map.uploaded_at if strava_map else None,
                status=upload_status,
            )
        )

    return uploads


@router.post("/activities/{activity_id}/upload", response_model=UploadStatusResponse)
async def upload_single_activity(
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> UploadStatusResponse:
    """Upload a single activity to Strava.

    Args:
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Upload status.
    """
    # Verify ownership
    activity_result = await db.execute(
        select(Activity).where(
            Activity.id == activity_id,
            Activity.user_id == current_user.id,
        )
    )
    activity = activity_result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Check Strava connection
    session_result = await db.execute(
        select(StravaSession).where(StravaSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    if not session or not session.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strava account not connected",
        )

    # Check if already uploaded
    map_result = await db.execute(
        select(StravaActivityMap).where(StravaActivityMap.activity_id == activity_id)
    )
    existing_map = map_result.scalar_one_or_none()

    if existing_map:
        return UploadStatusResponse(
            activity_id=activity.id,
            garmin_id=activity.garmin_id,
            strava_activity_id=existing_map.strava_activity_id,
            uploaded_at=existing_map.uploaded_at,
            status="uploaded",
        )

    # TODO: Implement actual Strava upload
    # strava_id = await strava_client.upload_activity(activity, session.access_token)

    return UploadStatusResponse(
        activity_id=activity.id,
        garmin_id=activity.garmin_id,
        strava_activity_id=None,
        uploaded_at=None,
        status="pending",
    )
