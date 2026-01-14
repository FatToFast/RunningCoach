"""Strava integration endpoints."""

import asyncio
import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.session import get_redis
from app.models.activity import Activity
from app.models.strava import StravaActivityMap, StravaSession, StravaSyncState
from app.models.user import User
from app.observability import get_metrics_backend

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# OAuth state token TTL (10 minutes)
OAUTH_STATE_TTL = 600

# In-memory fallback for OAuth state when Redis is unavailable
# Format: {state_token: (user_id, expires_at_timestamp)}
_in_memory_oauth_states: dict[str, tuple[int, float]] = {}


def _get_cipher() -> Optional[Fernet]:
    """Get Fernet cipher for token encryption/decryption.

    Returns:
        Fernet cipher if encryption key is configured, None otherwise.
    """
    if not settings.strava_encryption_key:
        logger.warning("STRAVA_ENCRYPTION_KEY not configured - tokens will be stored in plaintext")
        return None

    try:
        return Fernet(settings.strava_encryption_key.encode())
    except Exception as e:
        logger.error(f"Failed to initialize Strava encryption cipher: {e}")
        return None


def _encrypt_token(token: str) -> str:
    """Encrypt a Strava token.

    Args:
        token: The plaintext token.

    Returns:
        Encrypted token (or plaintext if encryption not configured).
    """
    cipher = _get_cipher()
    if not cipher:
        return token

    try:
        return cipher.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt Strava token: {e}")
        return token


def _decrypt_token(encrypted_token: str) -> str:
    """Decrypt a Strava token.

    Args:
        encrypted_token: The encrypted token.

    Returns:
        Decrypted token (or encrypted value if decryption fails/not configured).
    """
    cipher = _get_cipher()
    if not cipher:
        return encrypted_token

    try:
        return cipher.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt Strava token: {e}")
        return encrypted_token


async def _generate_oauth_state(user_id: int) -> str:
    """Generate a secure OAuth state token for CSRF protection.

    Stores the state in Redis for multi-worker support.
    Falls back to in-memory storage if Redis is unavailable.

    Args:
        user_id: The user ID to associate with this state.

    Returns:
        A cryptographically secure state token.
    """
    redis_client = await get_redis()
    state_token = secrets.token_urlsafe(32)

    if redis_client is None:
        # Fallback: use in-memory storage (single instance only)
        logger.warning("Redis unavailable - using in-memory OAuth state storage")
        _in_memory_oauth_states[state_token] = (user_id, time.time() + OAUTH_STATE_TTL)
        return state_token

    # Store state in Redis with TTL
    await redis_client.setex(
        f"oauth:strava:state:{state_token}",
        OAUTH_STATE_TTL,
        str(user_id),
    )

    return state_token


async def _ensure_token_valid(session: StravaSession, db: AsyncSession) -> None:
    """Ensure Strava token is valid, refresh if needed.

    Refreshes token if it expires within the buffer time (default: 5 minutes).

    Args:
        session: StravaSession to check and refresh.
        db: Database session for persisting refreshed tokens.

    Raises:
        HTTPException: If token refresh fails.
    """
    if not session.expires_at:
        # No expiry info - assume valid
        return

    # Calculate refresh threshold (expiry - buffer)
    buffer = timedelta(seconds=settings.strava_token_refresh_buffer_seconds)
    refresh_threshold = session.expires_at - buffer
    now = datetime.now(timezone.utc)

    # Refresh if within buffer window or already expired
    if now >= refresh_threshold:
        logger.info(f"Refreshing Strava token for user {session.user_id} (expires at {session.expires_at})")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.strava_oauth_base_url}/token",
                    data={
                        "client_id": settings.strava_client_id,
                        "client_secret": settings.strava_client_secret,
                        "refresh_token": _decrypt_token(session.refresh_token),
                        "grant_type": "refresh_token",
                    },
                )
                response.raise_for_status()
                tokens = response.json()

            # Update session with encrypted tokens
            session.access_token = _encrypt_token(tokens["access_token"])
            session.refresh_token = _encrypt_token(tokens["refresh_token"])
            session.expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
            await db.flush()

            logger.info(f"Strava token refreshed successfully for user {session.user_id}, new expiry: {session.expires_at}")

        except Exception as e:
            logger.exception(f"Failed to refresh Strava token for user {session.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Strava token expired and refresh failed. Please reconnect.",
            )


async def _validate_oauth_state(state: str | None, user_id: int) -> bool:
    """Validate OAuth state token for CSRF protection.

    Checks Redis for the state token (multi-worker safe).
    Falls back to in-memory storage if Redis is unavailable.

    Args:
        state: The state token from the callback.
        user_id: The authenticated user's ID.

    Returns:
        True if the state is valid for this user, False otherwise.
    """
    if not state:
        return False

    redis_client = await get_redis()

    # Fallback to in-memory storage if Redis unavailable
    if redis_client is None:
        stored = _in_memory_oauth_states.pop(state, None)
        if stored is None:
            return False
        stored_user_id, expires_at = stored
        if time.time() > expires_at:
            return False
        return stored_user_id == user_id

    key = f"oauth:strava:state:{state}"

    # Get stored user_id from Redis
    stored_user_id_str = await redis_client.get(key)

    if not stored_user_id_str:
        return False

    # Check user ID matches
    try:
        stored_user_id = int(stored_user_id_str)
    except ValueError:
        await redis_client.delete(key)
        return False

    if stored_user_id != user_id:
        return False

    # Remove used state (one-time use)
    await redis_client.delete(key)
    return True


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
    queued_count: int


class SyncStatusResponse(BaseModel):
    """Sync status response."""

    last_sync_at: datetime | None
    last_success_at: datetime | None
    pending_uploads: int
    completed_uploads: int
    queued_jobs: int
    uploading_jobs: int
    failed_jobs: int


class UploadStatusResponse(BaseModel):
    """Activity upload status."""

    activity_id: int
    garmin_id: int
    strava_activity_id: int | None
    uploaded_at: datetime | None
    status: str  # pending, uploaded, failed


class UploadStatusListResponse(BaseModel):
    """Paginated activity upload status list."""

    items: list[UploadStatusResponse]
    total: int
    page: int
    per_page: int


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
    client_id = settings.strava_client_id
    redirect_uri = settings.strava_redirect_uri

    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Strava OAuth not configured",
        )

    # Generate secure state token for CSRF protection
    state_token = await _generate_oauth_state(current_user.id)

    auth_url = (
        f"{settings.strava_oauth_base_url}/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=activity:write,activity:read_all"
        f"&state={state_token}"
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
    # Validate OAuth state for CSRF protection
    if not await _validate_oauth_state(request.state, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Please restart the authorization flow.",
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
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.strava_oauth_base_url}/token",
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
            session.access_token = _encrypt_token(tokens["access_token"])
            session.refresh_token = _encrypt_token(tokens["refresh_token"])
            session.expires_at = expires_at
        else:
            session = StravaSession(
                user_id=current_user.id,
                access_token=_encrypt_token(tokens["access_token"]),
                refresh_token=_encrypt_token(tokens["refresh_token"]),
                expires_at=expires_at,
            )
            db.add(session)

        await db.commit()

        return StravaCallbackResponse(
            success=True,
            message="Strava account connected successfully",
        )

    except Exception as e:
        logger.exception("OAuth exchange failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth exchange failed. Please try again.",
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
                f"{settings.strava_oauth_base_url}/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": _decrypt_token(session.refresh_token),
                    "grant_type": "refresh_token",
                },
            )
            status_code = response.status_code
            response.raise_for_status()
            tokens = response.json()

        session.access_token = _encrypt_token(tokens["access_token"])
        session.refresh_token = _encrypt_token(tokens["refresh_token"])
        session.expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)

        await db.commit()

        return RefreshResponse(
            success=True,
            message="Strava tokens refreshed successfully",
            expires_at=session.expires_at,
        )

    except Exception as e:
        logger.exception("Token refresh failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed. Please reconnect your Strava account.",
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

    Queues all pending activities (with FIT files) for upload to Strava.
    Activities are processed asynchronously by the ARQ worker.

    Args:
        current_user: Authenticated user.
        db: Database session.
        force: Force re-upload (not yet implemented - requires deleting existing maps).

    Returns:
        Sync job status with counts.
    """
    from app.models.strava import StravaUploadJob, StravaUploadStatus
    from app.services.strava_upload import StravaUploadService

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

    # Count pending uploads (activities with FIT files, not uploaded, not queued)
    pending_query = (
        select(func.count(Activity.id))
        .outerjoin(StravaActivityMap)
        .outerjoin(StravaUploadJob)
        .where(
            Activity.user_id == current_user.id,
            Activity.has_fit_file == True,
            StravaActivityMap.id == None,
            StravaUploadJob.id == None,
        )
    )
    pending_result = await db.execute(pending_query)
    pending_count = pending_result.scalar() or 0

    # Queue activities for upload
    upload_service = StravaUploadService(db)
    queued_count = await upload_service.enqueue_pending_activities(
        user_id=current_user.id,
        since=None,  # Queue all pending
    )

    return SyncRunResponse(
        started=True,
        message=f"Queued {queued_count} activities for Strava upload",
        pending_count=pending_count,
        queued_count=queued_count,
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
        Sync status including job queue statistics.
    """
    from app.models.strava import StravaUploadJob, StravaUploadStatus
    from app.services.strava_upload import StravaUploadService

    # Get sync state
    sync_result = await db.execute(
        select(StravaSyncState).where(StravaSyncState.user_id == current_user.id)
    )
    sync_state = sync_result.scalar_one_or_none()

    # Count pending (activities with FIT, not uploaded, not in queue)
    pending_result = await db.execute(
        select(func.count(Activity.id))
        .outerjoin(StravaActivityMap)
        .outerjoin(StravaUploadJob)
        .where(
            Activity.user_id == current_user.id,
            Activity.has_fit_file == True,
            StravaActivityMap.id == None,
            StravaUploadJob.id == None,
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

    # Get job statistics
    upload_service = StravaUploadService(db)
    job_stats = await upload_service.get_job_stats(current_user.id)

    return SyncStatusResponse(
        last_sync_at=sync_state.last_sync_at if sync_state else None,
        last_success_at=sync_state.last_success_at if sync_state else None,
        pending_uploads=pending_count,
        completed_uploads=completed_count,
        queued_jobs=job_stats.get(StravaUploadStatus.QUEUED.value, 0),
        uploading_jobs=job_stats.get(StravaUploadStatus.UPLOADING.value, 0)
        + job_stats.get(StravaUploadStatus.POLLING.value, 0),
        failed_jobs=job_stats.get(StravaUploadStatus.FAILED.value, 0),
    )


# -------------------------------------------------------------------------
# Activity Upload Status
# -------------------------------------------------------------------------


@router.get("/activities", response_model=UploadStatusListResponse)
async def list_activity_uploads(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, pattern="^(pending|uploaded|failed)$"),
) -> UploadStatusListResponse:
    """List activity upload statuses.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        status_filter: Filter by status (pending, uploaded, failed).

    Returns:
        Paginated upload statuses.
    """
    # Build base query with user filter
    base_query = (
        select(Activity, StravaActivityMap)
        .outerjoin(StravaActivityMap)
        .where(Activity.user_id == current_user.id)
    )

    # Apply status filter BEFORE pagination
    if status_filter == "pending":
        # Pending = no StravaActivityMap record
        base_query = base_query.where(StravaActivityMap.id == None)
    elif status_filter == "uploaded":
        # Uploaded = has StravaActivityMap record
        base_query = base_query.where(StravaActivityMap.id != None)
    # Note: "failed" status would need a status column in StravaActivityMap

    # Count total matching records
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * per_page
    query = base_query.order_by(Activity.start_time.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    uploads = []
    for activity, strava_map in rows:
        upload_status = "uploaded" if strava_map else "pending"
        uploads.append(
            UploadStatusResponse(
                activity_id=activity.id,
                garmin_id=activity.garmin_id,
                strava_activity_id=strava_map.strava_activity_id if strava_map else None,
                uploaded_at=strava_map.uploaded_at if strava_map else None,
                status=upload_status,
            )
        )

    return UploadStatusListResponse(
        items=uploads,
        total=total,
        page=page,
        per_page=per_page,
    )


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

    # Check if FIT file exists
    if not activity.has_fit_file or not activity.fit_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity does not have a FIT file for upload",
        )

    # Upload to Strava
    fit_path = Path(activity.fit_file_path)
    if not fit_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FIT file not found on disk",
        )

    # Ensure token is valid (refresh if needed, with 5-min buffer)
    await _ensure_token_valid(session, db)

    metrics = get_metrics_backend()
    start_time = time.perf_counter()
    upload_status_code = 500
    try:
        async with httpx.AsyncClient() as client:
            with fit_path.open("rb") as f:
                files = {"file": (fit_path.name, f, "application/octet-stream")}
                data = {
                    "data_type": "fit",
                    "name": activity.name or f"Run {activity.start_time.strftime('%Y-%m-%d')}",
                    "activity_type": "run",
                }
                response = await client.post(
                    f"{settings.strava_api_base_url}/uploads",
                    headers={"Authorization": f"Bearer {_decrypt_token(session.access_token)}"},
                    files=files,
                    data=data,
                    timeout=60.0,
                )
                upload_status_code = response.status_code
                response.raise_for_status()
                upload_result = response.json()

        # Strava returns upload_id, activity_id comes later
        # We'll store the upload_id temporarily and poll for completion
        upload_id = upload_result.get("id")
        strava_activity_id = upload_result.get("activity_id")

        # If activity_id is not yet available, poll for it with exponential backoff
        if not strava_activity_id and upload_id:
            # Exponential backoff: 2s, 4s, 8s (total ~14s)
            backoff_delays = [2, 4, 8]
            for delay in backoff_delays:
                await asyncio.sleep(delay)
                async with httpx.AsyncClient() as client:
                    check_response = await client.get(
                        f"{settings.strava_api_base_url}/uploads/{upload_id}",
                        headers={"Authorization": f"Bearer {_decrypt_token(session.access_token)}"},
                    )
                    if check_response.status_code == 200:
                        check_result = check_response.json()
                        strava_activity_id = check_result.get("activity_id")
                        if strava_activity_id:
                            logger.debug(f"Strava upload {upload_id} completed after {delay}s delay")
                            break

        # Create mapping record
        strava_map = StravaActivityMap(
            activity_id=activity.id,
            strava_activity_id=strava_activity_id,
        )
        db.add(strava_map)

        # Update sync state
        sync_result = await db.execute(
            select(StravaSyncState).where(StravaSyncState.user_id == current_user.id)
        )
        sync_state = sync_result.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if sync_state:
            sync_state.last_sync_at = now
            sync_state.last_success_at = now
        else:
            sync_state = StravaSyncState(
                user_id=current_user.id,
                last_sync_at=now,
                last_success_at=now,
            )
            db.add(sync_state)

        await db.commit()
        await db.refresh(strava_map)

        return UploadStatusResponse(
            activity_id=activity.id,
            garmin_id=activity.garmin_id,
            strava_activity_id=strava_activity_id,
            uploaded_at=strava_map.uploaded_at,
            status="uploaded",
        )

    except httpx.HTTPStatusError as e:
        logger.exception("Strava upload failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload to Strava. Please try again.",
        )
    except Exception as e:
        logger.exception("Unexpected error during Strava upload")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed. Please try again.",
        )
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.observe_external_api("strava", "upload", upload_status_code, duration_ms)
        logger.info(
            "Strava API upload status=%s duration_ms=%.2f",
            upload_status_code,
            duration_ms,
        )
