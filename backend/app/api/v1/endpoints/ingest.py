"""Data ingestion endpoints.

Paths:
  POST /api/v1/ingest/run    - 수동 동기화 실행
  GET  /api/v1/ingest/status - 동기화 상태 조회
  GET  /api/v1/ingest/history - 동기화 이력 (v1.0)
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.garmin import GarminSession, GarminSyncState
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class IngestRunRequest(BaseModel):
    """Request to run ingestion."""

    endpoints: list[str] | None = None  # None = all endpoints
    full_backfill: bool = False


class IngestRunResponse(BaseModel):
    """Ingestion run response."""

    started: bool
    message: str
    endpoints: list[str]


class SyncStateResponse(BaseModel):
    """Single endpoint sync state."""

    endpoint: str
    last_sync_at: datetime | None
    last_success_at: datetime | None
    cursor: str | None


class IngestStatusResponse(BaseModel):
    """Overall ingestion status."""

    connected: bool
    running: bool
    sync_states: list[SyncStateResponse]


class SyncHistoryItem(BaseModel):
    """Sync history item."""

    endpoint: str
    sync_at: datetime
    success: bool
    records_synced: int | None
    error_message: str | None


class SyncHistoryResponse(BaseModel):
    """Sync history response."""

    items: list[SyncHistoryItem]
    total: int


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.post("/run", response_model=IngestRunResponse)
async def run_ingest(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    request: IngestRunRequest | None = None,
) -> IngestRunResponse:
    """Trigger manual data ingestion.

    FR-002: 활동 데이터 수집 - 수동 동기화 트리거

    Args:
        current_user: Authenticated user.
        db: Database session.
        request: Optional endpoints to sync.

    Returns:
        Ingestion job status.
    """
    # Check Garmin connection
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    # Default endpoints
    all_endpoints = ["activities", "sleep", "heart_rate", "body_composition"]
    endpoints = request.endpoints if request and request.endpoints else all_endpoints

    # Validate endpoints
    invalid = set(endpoints) - set(all_endpoints)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid endpoints: {invalid}",
        )

    # TODO: Queue Celery task for background sync
    # task = sync_garmin_data.delay(
    #     user_id=current_user.id,
    #     endpoints=endpoints,
    #     full_backfill=request.full_backfill if request else False,
    # )

    return IngestRunResponse(
        started=True,
        message="Ingestion job queued",
        endpoints=endpoints,
    )


@router.get("/status", response_model=IngestStatusResponse)
async def get_ingest_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> IngestStatusResponse:
    """Get ingestion status for all endpoints.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Sync states for all endpoints.
    """
    # Check connection
    session_result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    # Get sync states
    result = await db.execute(
        select(GarminSyncState).where(GarminSyncState.user_id == current_user.id)
    )
    states = result.scalars().all()

    return IngestStatusResponse(
        connected=session is not None,
        running=False,  # TODO: Check actual job status via Celery
        sync_states=[
            SyncStateResponse(
                endpoint=s.endpoint,
                last_sync_at=s.last_sync_at,
                last_success_at=s.last_success_at,
                cursor=s.cursor,
            )
            for s in states
        ],
    )


@router.get("/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    endpoint: str | None = Query(None, description="Filter by endpoint"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> SyncHistoryResponse:
    """Get sync history (v1.0).

    Args:
        current_user: Authenticated user.
        db: Database session.
        endpoint: Filter by endpoint.
        page: Page number.
        per_page: Items per page.

    Returns:
        Sync history.
    """
    # TODO: Implement sync history tracking table
    # For now, return empty list
    return SyncHistoryResponse(
        items=[],
        total=0,
    )
