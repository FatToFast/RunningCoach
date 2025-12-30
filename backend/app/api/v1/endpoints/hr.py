"""Heart rate data endpoints.

Paths:
  GET /api/v1/hr         - 일별 심박수 기록 목록
  GET /api/v1/hr/summary - 심박수 요약 통계
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.health import HRRecord
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class HeartRateRecord(BaseModel):
    """Daily heart rate record."""

    id: int
    date: date
    resting_hr: int | None
    avg_hr: int | None
    max_hr: int | None


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
    avg_max_hr: float | None
    record_count: int


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
    """Get daily heart rate records with pagination.

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
    query = select(HRRecord).where(HRRecord.user_id == current_user.id)

    if start_date:
        query = query.where(HRRecord.date >= start_date)
    if end_date:
        query = query.where(HRRecord.date <= end_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(HRRecord.date.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    records = result.scalars().all()

    items = [
        HeartRateRecord(
            id=r.id,
            date=r.date,
            resting_hr=r.resting_hr,
            avg_hr=r.avg_hr,
            max_hr=r.max_hr,
        )
        for r in records
    ]

    return HeartRateListResponse(
        items=items,
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
        func.avg(HRRecord.resting_hr).label("avg_resting"),
        func.min(HRRecord.resting_hr).label("min_resting"),
        func.max(HRRecord.resting_hr).label("max_resting"),
        func.avg(HRRecord.max_hr).label("avg_max"),
        func.count(HRRecord.id).label("count"),
    ).where(HRRecord.user_id == current_user.id)

    if start_date:
        query = query.where(HRRecord.date >= start_date)
    if end_date:
        query = query.where(HRRecord.date <= end_date)

    result = await db.execute(query)
    row = result.one()

    return HeartRateSummary(
        avg_resting_hr=round(row.avg_resting, 1) if row.avg_resting else None,
        min_resting_hr=row.min_resting,
        max_resting_hr=row.max_resting,
        avg_max_hr=round(row.avg_max, 1) if row.avg_max else None,
        record_count=row.count or 0,
    )
