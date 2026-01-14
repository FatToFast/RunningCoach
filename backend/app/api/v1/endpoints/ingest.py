"""Data ingestion endpoints.

Paths:
  POST /api/v1/ingest/run    - 수동 동기화 실행
  GET  /api/v1/ingest/status - 동기화 상태 조회
  GET  /api/v1/ingest/history - 동기화 이력
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db, async_session_maker
from app.core.session import acquire_lock, release_lock, check_lock, extend_lock
from app.models.garmin import GarminSession, GarminSyncState, GarminRawEvent
from app.models.user import User
from app.services.ai_snapshot import ensure_ai_training_snapshot
from app.services.sync_service import GarminSyncService, create_sync_service
from app.adapters.garmin_adapter import GarminConnectAdapter, GarminAuthError

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# In-memory sync status (per user)
# Format: {user_id: {"error": str|None, "started_at": datetime|None}}
_sync_status: dict[int, dict[str, Any]] = {}

# Default endpoints for quick sync (activities only for faster sync)
DEFAULT_SYNC_ENDPOINTS = ["activities"]


def _sync_lock_name(user_id: int) -> str:
    """Get lock name for user sync."""
    return f"sync:user:{user_id}"


async def validate_garmin_session(
    db: AsyncSession,
    user_id: int,
    validate_with_api: bool = True,
) -> GarminSession:
    """Validate Garmin session exists and is working.

    Args:
        db: Database session.
        user_id: User ID to check.
        validate_with_api: If True, make API call to verify session is not expired.

    Returns:
        Valid GarminSession.

    Raises:
        HTTPException: If session is missing or expired.
    """
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()

    if not session or not session.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    if validate_with_api:
        # Validate session is actually working (not just existing)
        adapter = GarminConnectAdapter()
        try:
            loop = asyncio.get_event_loop()
            is_valid = await loop.run_in_executor(
                None,
                lambda: adapter.validate_session(session.session_data),
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Garmin session expired. Please reconnect via /auth/garmin/connect",
                )
        except GarminAuthError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Garmin session expired. Please reconnect via /auth/garmin/connect",
            )

    return session


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class IngestRunRequest(BaseModel):
    """Request to run ingestion."""

    endpoints: list[str] | None = None  # None = all endpoints
    full_backfill: bool = False
    start_date: date | None = None
    end_date: date | None = None


class SyncResultItem(BaseModel):
    """Result of syncing a single endpoint."""

    endpoint: str
    success: bool
    items_fetched: int
    items_created: int
    items_updated: int
    error: str | None


class IngestRunResponse(BaseModel):
    """Ingestion run response."""

    started: bool
    message: str
    endpoints: list[str]
    # Note: sync_id was removed as it was not persisted or queryable.
    # Use /ingest/status to check if sync is running.


class SyncStateResponse(BaseModel):
    """Single endpoint sync state."""

    endpoint: str
    last_sync_at: datetime | None
    last_success_at: datetime | None
    cursor: str | None


class SyncProgress(BaseModel):
    """Sync progress information."""

    current_endpoint: str  # 현재 동기화 중인 엔드포인트
    current_index: int  # 현재 엔드포인트 인덱스 (0-based)
    total_endpoints: int  # 총 엔드포인트 수
    items_synced: int  # 현재 엔드포인트에서 동기화된 항목 수


class IngestStatusResponse(BaseModel):
    """Overall ingestion status."""

    connected: bool
    running: bool
    sync_states: list[SyncStateResponse]
    last_error: str | None = None
    last_sync_started_at: datetime | None = None
    progress: SyncProgress | None = None  # 동기화 진행률


class SyncHistoryItem(BaseModel):
    """Sync history item."""

    id: int
    endpoint: str
    fetched_at: datetime
    record_count: int


class SyncHistoryResponse(BaseModel):
    """Sync history response."""

    items: list[SyncHistoryItem]
    total: int


# -------------------------------------------------------------------------
# Background Task
# -------------------------------------------------------------------------


async def run_sync_background(
    user_id: int,
    endpoints: list[str],
    lock_owner: str,
    full_backfill: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """Run sync in background.

    This function runs in a separate task and performs the actual sync.
    Uses Redis distributed lock for multi-worker safety with periodic extension
    to support long-running syncs (1000+ activities).

    Args:
        user_id: User ID to sync.
        endpoints: List of endpoints to sync.
        lock_owner: Lock owner token (for releasing lock).
        full_backfill: If True, sync all historical data.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
    """
    lock_name = _sync_lock_name(user_id)

    # Initialize sync status with progress tracking
    _sync_status[user_id] = {
        "error": None,
        "started_at": datetime.now(timezone.utc),
        "progress": {
            "current_endpoint": endpoints[0] if endpoints else "",
            "current_index": 0,
            "total_endpoints": len(endpoints),
            "items_synced": 0,
        },
    }

    # Background task to periodically extend lock during long syncs
    async def extend_lock_periodically():
        """Extend lock every N minutes to prevent expiration during long syncs."""
        try:
            while True:
                await asyncio.sleep(settings.sync_lock_extension_interval)
                success = await extend_lock(
                    lock_name,
                    lock_owner,
                    ttl_seconds=settings.sync_lock_ttl_seconds,
                )
                if success:
                    logger.debug(f"Extended sync lock for user {user_id}")
                else:
                    logger.warning(f"Failed to extend sync lock for user {user_id}")
        except asyncio.CancelledError:
            # Normal cancellation when sync completes
            pass

    # Start lock extension task
    extension_task = asyncio.create_task(extend_lock_periodically())

    try:
        async with async_session_maker() as session:
            # Get user
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User {user_id} not found")
                _sync_status[user_id]["error"] = "User not found"
                return

            # Create sync service
            sync_service = await create_sync_service(session, user)
            if not sync_service:
                logger.error(f"Could not create sync service for user {user_id}")
                _sync_status[user_id]["error"] = "Garmin 연결이 필요합니다"
                return

            # Sync user profile once per run (max HR, raw snapshot)
            await sync_service.sync_user_profile()

            # Run sync for each endpoint
            errors = []
            for idx, endpoint in enumerate(endpoints):
                # Update progress before starting each endpoint
                _sync_status[user_id]["progress"] = {
                    "current_endpoint": endpoint,
                    "current_index": idx,
                    "total_endpoints": len(endpoints),
                    "items_synced": 0,
                }

                try:
                    result = await sync_service.sync_endpoint(
                        endpoint,
                        start_date=start_date,
                        end_date=end_date,
                        full_backfill=full_backfill,
                    )

                    # Update items_synced after completion
                    _sync_status[user_id]["progress"]["items_synced"] = (
                        result.items_created + result.items_updated
                    )

                    logger.info(
                        f"Sync {endpoint} for user {user_id}: "
                        f"fetched={result.items_fetched}, "
                        f"created={result.items_created}, "
                        f"updated={result.items_updated}"
                    )
                except Exception as e:
                    logger.exception(f"Error syncing {endpoint} for user {user_id}")
                    errors.append(f"{endpoint}: {str(e)[:50]}")

            # Store error summary if any failures
            if errors:
                _sync_status[user_id]["error"] = "; ".join(errors[:3])  # Max 3 errors

            try:
                await ensure_ai_training_snapshot(session, user)
            except Exception as e:
                logger.warning(
                    "Failed to refresh AI snapshot for user %s: %s",
                    user_id,
                    e,
                )

    except Exception as e:
        logger.exception(f"Background sync error for user {user_id}")
        _sync_status[user_id]["error"] = str(e)[:100]
    finally:
        # Cancel lock extension task
        extension_task.cancel()
        try:
            await extension_task
        except asyncio.CancelledError:
            pass

        # Always release the lock when done
        await release_lock(lock_name, lock_owner)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.post("/run", response_model=IngestRunResponse)
async def run_ingest(
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    request: IngestRunRequest | None = None,
) -> IngestRunResponse:
    """Trigger manual data ingestion.

    FR-002: 활동 데이터 수집 - 수동 동기화 트리거

    This endpoint starts a background sync job. Use /status to check progress.

    Args:
        current_user: Authenticated user.
        background_tasks: FastAPI background tasks.
        db: Database session.
        request: Optional sync parameters.

    Returns:
        Ingestion job status.
    """
    # Try to acquire distributed lock
    lock_name = _sync_lock_name(current_user.id)
    lock_owner = await acquire_lock(lock_name, ttl_seconds=settings.sync_lock_ttl_seconds)

    if not lock_owner:
        return IngestRunResponse(
            started=False,
            message="Sync already in progress",
            endpoints=[],
        )

    try:
        # Validate Garmin session (with API call to verify not expired)
        await validate_garmin_session(db, current_user.id, validate_with_api=True)

        # Determine endpoints to sync
        # - None or not provided: sync all endpoints (default)
        # - Empty list []: explicitly means "do nothing" - return early
        # - List with items: sync only those endpoints
        all_endpoints = GarminSyncService.ENDPOINTS

        if request and request.endpoints is not None:
            if len(request.endpoints) == 0:
                # Explicit empty list means no sync requested
                await release_lock(lock_name, lock_owner)
                return IngestRunResponse(
                    started=False,
                    message="No endpoints specified for sync",
                    endpoints=[],
                )
            endpoints = request.endpoints
        else:
            # Default: sync only activities for faster sync
            # Use full_backfill=True or explicit endpoints list for full sync
            endpoints = DEFAULT_SYNC_ENDPOINTS

        # Validate endpoints
        invalid = set(endpoints) - set(all_endpoints)
        if invalid:
            await release_lock(lock_name, lock_owner)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid endpoints: {invalid}. Valid: {all_endpoints}",
            )

        # Validate date range
        if request and request.start_date and request.end_date:
            if request.start_date > request.end_date:
                await release_lock(lock_name, lock_owner)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date must be before or equal to end_date",
                )

        # Start background sync (lock will be released by background task)
        background_tasks.add_task(
            run_sync_background,
            user_id=current_user.id,
            endpoints=endpoints,
            lock_owner=lock_owner,
            full_backfill=request.full_backfill if request else False,
            start_date=request.start_date if request else None,
            end_date=request.end_date if request else None,
        )

        return IngestRunResponse(
            started=True,
            message="Sync started in background. Use /ingest/status to monitor progress.",
            endpoints=endpoints,
        )

    except Exception:
        # Release lock on any error before background task starts
        await release_lock(lock_name, lock_owner)
        raise


@router.post("/run/sync", response_model=list[SyncResultItem])
async def run_ingest_sync(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    request: IngestRunRequest | None = None,
) -> list[SyncResultItem]:
    """Run data ingestion synchronously (blocking).

    Use this for testing or when you need immediate results.
    For production use /run which runs in background.

    Args:
        current_user: Authenticated user.
        db: Database session.
        request: Optional sync parameters.

    Returns:
        List of sync results for each endpoint.

    Raises:
        HTTPException 409: If sync is already running for this user.
    """
    # Try to acquire distributed lock
    lock_name = _sync_lock_name(current_user.id)
    lock_owner = await acquire_lock(lock_name, ttl_seconds=settings.sync_lock_ttl_seconds)

    if not lock_owner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sync already in progress. Use /ingest/status to check progress.",
        )

    try:
        # Validate Garmin session (with API call to verify not expired)
        await validate_garmin_session(db, current_user.id, validate_with_api=True)

        # Create sync service
        sync_service = await create_sync_service(db, current_user)
        if not sync_service:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not initialize sync service",
            )

        # Sync user profile once per run (max HR, raw snapshot)
        await sync_service.sync_user_profile()

        # Determine endpoints to sync (same logic as /run)
        all_endpoints = GarminSyncService.ENDPOINTS

        if request and request.endpoints is not None:
            if len(request.endpoints) == 0:
                # Explicit empty list means no sync requested
                return []
            endpoints = request.endpoints
        else:
            endpoints = all_endpoints

        # Validate endpoints
        invalid = set(endpoints) - set(all_endpoints)
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid endpoints: {invalid}",
            )

        # Run sync
        results = []
        for endpoint in endpoints:
            sync_result = await sync_service.sync_endpoint(
                endpoint,
                start_date=request.start_date if request else None,
                end_date=request.end_date if request else None,
                full_backfill=request.full_backfill if request else False,
            )
            results.append(
                SyncResultItem(
                    endpoint=sync_result.endpoint,
                    success=sync_result.success,
                    items_fetched=sync_result.items_fetched,
                    items_created=sync_result.items_created,
                    items_updated=sync_result.items_updated,
                    error=sync_result.error,
                )
            )

        try:
            await ensure_ai_training_snapshot(db, current_user)
        except Exception as e:
            logger.warning(
                "Failed to refresh AI snapshot for user %s: %s",
                current_user.id,
                e,
            )

        return results

    finally:
        # Release lock when sync completes
        await release_lock(lock_name, lock_owner)


@router.get("/status", response_model=IngestStatusResponse)
async def get_ingest_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> IngestStatusResponse:
    """Get ingestion status for all endpoints.

    This is a lightweight status check that does NOT validate with Garmin API.
    Use /auth/garmin/status for accurate connection validation.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Sync states for all endpoints.
    """
    # Check if Garmin session exists (no API validation - fast check)
    session_result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()
    is_connected = session is not None and session.is_valid

    # Get sync states
    result = await db.execute(
        select(GarminSyncState).where(GarminSyncState.user_id == current_user.id)
    )
    states = result.scalars().all()

    # Check if running (via distributed lock)
    lock_name = _sync_lock_name(current_user.id)
    is_running = await check_lock(lock_name)

    # Get last error and started_at from in-memory status
    user_status = _sync_status.get(current_user.id, {})
    last_sync_started_at = user_status.get("started_at")

    # Detect and handle stale locks
    # If lock exists but sync started too long ago (or no record of start), it's stale
    if is_running:
        is_stale = False
        if last_sync_started_at:
            elapsed = (datetime.now(timezone.utc) - last_sync_started_at).total_seconds()
            if elapsed > settings.sync_stale_threshold_seconds:
                is_stale = True
                logger.warning(
                    f"Stale sync lock detected for user {current_user.id} "
                    f"(started {elapsed:.0f}s ago, threshold={settings.sync_stale_threshold_seconds}s). "
                    f"Lock will expire soon."
                )
        else:
            # No start time recorded - likely from previous deployment/crash
            # Treat as stale since we can't track it
            is_stale = True
            logger.warning(
                f"Orphaned sync lock detected for user {current_user.id} "
                f"(no start time recorded). Lock will expire soon."
            )

        if is_stale:
            # Mark as not running for UI - the lock TTL will handle cleanup
            is_running = False
            # Set error message
            if current_user.id not in _sync_status:
                _sync_status[current_user.id] = {}
            _sync_status[current_user.id]["error"] = "동기화 시간 초과 - 다시 시도해주세요"

    # Only show error after sync completes
    last_error = user_status.get("error") if not is_running else None

    # Get progress if running
    progress = None
    if is_running:
        progress_data = user_status.get("progress")
        if progress_data:
            progress = SyncProgress(
                current_endpoint=progress_data.get("current_endpoint", ""),
                current_index=progress_data.get("current_index", 0),
                total_endpoints=progress_data.get("total_endpoints", 0),
                items_synced=progress_data.get("items_synced", 0),
            )

    return IngestStatusResponse(
        connected=is_connected,
        running=is_running,
        sync_states=[
            SyncStateResponse(
                endpoint=s.endpoint,
                last_sync_at=s.last_sync_at,
                last_success_at=s.last_success_at,
                cursor=s.cursor,
            )
            for s in states
        ],
        last_error=last_error,
        last_sync_started_at=last_sync_started_at,
        progress=progress,
    )


@router.get("/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    endpoint: str | None = Query(None, description="Filter by endpoint"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> SyncHistoryResponse:
    """Get sync history from raw events.

    Args:
        current_user: Authenticated user.
        db: Database session.
        endpoint: Filter by endpoint.
        page: Page number.
        per_page: Items per page.

    Returns:
        Sync history based on raw events.
    """
    # Build base filter
    base_filter = GarminRawEvent.user_id == current_user.id
    if endpoint:
        base_filter = base_filter & (GarminRawEvent.endpoint == endpoint)

    # Get total count using COUNT(*) for O(1) instead of O(n)
    count_query = select(func.count()).select_from(GarminRawEvent).where(base_filter)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Build query for paginated results
    query = select(GarminRawEvent).where(base_filter)

    # Get paginated results
    query = query.order_by(desc(GarminRawEvent.fetched_at))
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    events = result.scalars().all()

    return SyncHistoryResponse(
        items=[
            SyncHistoryItem(
                id=e.id,
                endpoint=e.endpoint,
                fetched_at=e.fetched_at,
                record_count=len(e.payload.get("data", [])) if isinstance(e.payload, dict) and "data" in e.payload else (len(e.payload) if isinstance(e.payload, list) else 1),
            )
            for e in events
        ],
        total=total,
    )
