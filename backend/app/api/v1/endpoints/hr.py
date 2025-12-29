"""Heart rate data endpoints.

Paths:
  GET /api/v1/hr - 심박수/HRV 기록 목록
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.health import HeartRateZone
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class HeartRateRecord(BaseModel):
    """Heart rate zone record."""

    id: int
    date: date
    resting_hr: int | None
    zone1_seconds: int | None
    zone2_seconds: int | None
    zone3_seconds: int | None
    zone4_seconds: int | None
    zone5_seconds: int | None

    class Config:
        from_attributes = True


class HeartRateListResponse(BaseModel):
    """Paginated heart rate list."""

    items: list[HeartRateRecord]
    total: int
    page: int
    per_page: int


class HeartRateSummary(BaseModel):
    """Heart rate summary statistics."""

    avg_resting_hr: float | None
    min_resting_hr: int | None
    max_resting_hr: int | None
    total_zone1_hours: float | None
    total_zone2_hours: float | None
    total_zone3_hours: float | None
    total_zone4_hours: float | None
    total_zone5_hours: float | None


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("", response_model=HeartRateListResponse)
async def list_heart_rate_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: date | None = Query(None, description="Filter from date"),
    end_date: date | None = Query(None, description="Filter to date"),
) -> HeartRateListResponse:
    """Get heart rate zone records with pagination.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        start_date: Filter start date.
        end_date: Filter end date.

    Returns:
        Paginated heart rate records.
    """
    query = select(HeartRateZone).where(HeartRateZone.user_id == current_user.id)

    if start_date:
        query = query.where(HeartRateZone.date >= start_date)
    if end_date:
        query = query.where(HeartRateZone.date <= end_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(HeartRateZone.date.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    records = result.scalars().all()

    return HeartRateListResponse(
        items=[HeartRateRecord.model_validate(r) for r in records],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/summary", response_model=HeartRateSummary)
async def get_heart_rate_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(None, description="Filter from date"),
    end_date: date | None = Query(None, description="Filter to date"),
) -> HeartRateSummary:
    """Get heart rate summary statistics.

    Args:
        current_user: Authenticated user.
        db: Database session.
        start_date: Filter start date.
        end_date: Filter end date.

    Returns:
        Heart rate summary.
    """
    query = select(
        func.avg(HeartRateZone.resting_hr).label("avg_resting"),
        func.min(HeartRateZone.resting_hr).label("min_resting"),
        func.max(HeartRateZone.resting_hr).label("max_resting"),
        func.sum(HeartRateZone.zone1_seconds).label("z1"),
        func.sum(HeartRateZone.zone2_seconds).label("z2"),
        func.sum(HeartRateZone.zone3_seconds).label("z3"),
        func.sum(HeartRateZone.zone4_seconds).label("z4"),
        func.sum(HeartRateZone.zone5_seconds).label("z5"),
    ).where(HeartRateZone.user_id == current_user.id)

    if start_date:
        query = query.where(HeartRateZone.date >= start_date)
    if end_date:
        query = query.where(HeartRateZone.date <= end_date)

    result = await db.execute(query)
    row = result.one()

    return HeartRateSummary(
        avg_resting_hr=round(row.avg_resting, 1) if row.avg_resting else None,
        min_resting_hr=row.min_resting,
        max_resting_hr=row.max_resting,
        total_zone1_hours=round(row.z1 / 3600, 2) if row.z1 else None,
        total_zone2_hours=round(row.z2 / 3600, 2) if row.z2 else None,
        total_zone3_hours=round(row.z3 / 3600, 2) if row.z3 else None,
        total_zone4_hours=round(row.z4 / 3600, 2) if row.z4 else None,
        total_zone5_hours=round(row.z5 / 3600, 2) if row.z5 else None,
    )
