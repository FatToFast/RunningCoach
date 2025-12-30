"""Sleep data endpoints.

Paths:
  GET /api/v1/sleep        - 수면 기록 목록
  GET /api/v1/sleep/{date} - 특정 날짜 수면 (v1.0)
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.health import Sleep
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class SleepRecord(BaseModel):
    """Sleep record."""

    id: int
    date: date
    duration_seconds: int | None
    score: int | None
    deep_seconds: int | None
    light_seconds: int | None
    rem_seconds: int | None
    awake_seconds: int | None


class SleepListResponse(BaseModel):
    """Paginated sleep list."""

    items: list[SleepRecord]
    total: int
    page: int
    per_page: int


class SleepDetailResponse(BaseModel):
    """Detailed sleep record."""

    id: int
    date: date
    duration_seconds: int | None
    score: int | None
    deep_seconds: int | None
    light_seconds: int | None
    rem_seconds: int | None
    awake_seconds: int | None
    deep_pct: float | None
    light_pct: float | None
    rem_pct: float | None
    awake_pct: float | None
    created_at: datetime


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("", response_model=SleepListResponse)
async def list_sleep_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: date | None = Query(None, description="Filter from date"),
    end_date: date | None = Query(None, description="Filter to date"),
) -> SleepListResponse:
    """Get sleep records with pagination.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        start_date: Filter start date.
        end_date: Filter end date.

    Returns:
        Paginated sleep records.
    """
    query = select(Sleep).where(Sleep.user_id == current_user.id)

    if start_date:
        query = query.where(Sleep.date >= start_date)
    if end_date:
        query = query.where(Sleep.date <= end_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(Sleep.date.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    records = result.scalars().all()

    # Convert Sleep models to SleepRecord, extracting stages from JSON
    items = []
    for r in records:
        stages = r.stages or {}
        items.append(
            SleepRecord(
                id=r.id,
                date=r.date,
                duration_seconds=r.duration_seconds,
                score=r.score,
                deep_seconds=stages.get("deep"),
                light_seconds=stages.get("light"),
                rem_seconds=stages.get("rem"),
                awake_seconds=stages.get("awake"),
            )
        )

    return SleepListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{sleep_date}", response_model=SleepDetailResponse)
async def get_sleep_by_date(
    sleep_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SleepDetailResponse:
    """Get sleep record for specific date (v1.0).

    Args:
        sleep_date: Date to query.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Sleep record for the date.
    """
    result = await db.execute(
        select(Sleep).where(
            Sleep.user_id == current_user.id,
            Sleep.date == sleep_date,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sleep record found for {sleep_date}",
        )

    # Extract sleep stages from JSON
    stages = record.stages or {}
    deep_seconds = stages.get("deep")
    light_seconds = stages.get("light")
    rem_seconds = stages.get("rem")
    awake_seconds = stages.get("awake")

    # Calculate percentages
    total = record.duration_seconds or 0
    deep_pct = (deep_seconds / total * 100) if total and deep_seconds else None
    light_pct = (light_seconds / total * 100) if total and light_seconds else None
    rem_pct = (rem_seconds / total * 100) if total and rem_seconds else None
    awake_pct = (awake_seconds / total * 100) if total and awake_seconds else None

    return SleepDetailResponse(
        id=record.id,
        date=record.date,
        duration_seconds=record.duration_seconds,
        score=record.score,
        deep_seconds=deep_seconds,
        light_seconds=light_seconds,
        rem_seconds=rem_seconds,
        awake_seconds=awake_seconds,
        deep_pct=round(deep_pct, 1) if deep_pct else None,
        light_pct=round(light_pct, 1) if light_pct else None,
        rem_pct=round(rem_pct, 1) if rem_pct else None,
        awake_pct=round(awake_pct, 1) if awake_pct else None,
        created_at=record.created_at,
    )
