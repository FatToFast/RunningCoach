"""AI training snapshot endpoints."""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.ai_snapshot import ensure_ai_training_snapshot

router = APIRouter()


class AITrainingSnapshotResponse(BaseModel):
    window_start: date
    window_end: date
    generated_at: datetime
    source_last_sync_at: datetime | None
    schema_version: int
    payload: dict[str, Any]


@router.get("/snapshot", response_model=AITrainingSnapshotResponse)
async def get_ai_training_snapshot(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    refresh: bool = Query(False, description="Force snapshot regeneration"),
) -> AITrainingSnapshotResponse:
    snapshot = await ensure_ai_training_snapshot(db, current_user, force=refresh)
    return AITrainingSnapshotResponse(
        window_start=snapshot.window_start,
        window_end=snapshot.window_end,
        generated_at=snapshot.generated_at,
        source_last_sync_at=snapshot.source_last_sync_at,
        schema_version=snapshot.schema_version,
        payload=snapshot.payload,
    )
