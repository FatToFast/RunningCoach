"""Unified metrics endpoints.

Paths:
  GET /api/v1/metrics         - 가능한 모든 지표 목록
  GET /api/v1/metrics/body    - 체성분 기록 (v1.0)
  GET /api/v1/metrics/fitness - 피트니스 지표 (v1.0)
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.health import BodyComposition, FitnessMetricDaily
from app.models.user import User

router = APIRouter()


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class MetricsSummary(BaseModel):
    """Available metrics summary."""

    has_body_composition: bool
    has_fitness_metrics: bool
    latest_weight_kg: float | None
    latest_body_fat_pct: float | None
    latest_ctl: float | None
    latest_atl: float | None
    latest_tsb: float | None
    latest_vo2max: float | None


class BodyCompositionRecord(BaseModel):
    """Body composition record."""

    id: int
    date: date
    weight_kg: float | None
    body_fat_pct: float | None
    muscle_mass_kg: float | None
    bmi: float | None

    class Config:
        from_attributes = True


class BodyCompositionListResponse(BaseModel):
    """Paginated body composition list."""

    items: list[BodyCompositionRecord]
    total: int
    page: int
    per_page: int


class FitnessMetricRecord(BaseModel):
    """Fitness metric record."""

    id: int
    date: date
    ctl: float | None
    atl: float | None
    tsb: float | None
    weekly_trimp: float | None
    weekly_tss: float | None

    class Config:
        from_attributes = True


class FitnessMetricListResponse(BaseModel):
    """Paginated fitness metrics list."""

    items: list[FitnessMetricRecord]
    total: int
    page: int
    per_page: int


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("", response_model=MetricsSummary)
async def get_metrics_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MetricsSummary:
    """Get available metrics summary.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Metrics availability and latest values.
    """
    # Latest body composition
    body_result = await db.execute(
        select(BodyComposition)
        .where(BodyComposition.user_id == current_user.id)
        .order_by(BodyComposition.date.desc())
        .limit(1)
    )
    latest_body = body_result.scalar_one_or_none()

    # Latest fitness metrics
    fitness_result = await db.execute(
        select(FitnessMetricDaily)
        .where(FitnessMetricDaily.user_id == current_user.id)
        .order_by(FitnessMetricDaily.date.desc())
        .limit(1)
    )
    latest_fitness = fitness_result.scalar_one_or_none()

    # Get user's VO2max
    vo2max = current_user.vo2max if hasattr(current_user, 'vo2max') else None

    return MetricsSummary(
        has_body_composition=latest_body is not None,
        has_fitness_metrics=latest_fitness is not None,
        latest_weight_kg=latest_body.weight_kg if latest_body else None,
        latest_body_fat_pct=latest_body.body_fat_pct if latest_body else None,
        latest_ctl=latest_fitness.ctl if latest_fitness else None,
        latest_atl=latest_fitness.atl if latest_fitness else None,
        latest_tsb=latest_fitness.tsb if latest_fitness else None,
        latest_vo2max=vo2max,
    )


@router.get("/body", response_model=BodyCompositionListResponse)
async def list_body_composition(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: date | None = Query(None, description="Filter from date"),
    end_date: date | None = Query(None, description="Filter to date"),
) -> BodyCompositionListResponse:
    """Get body composition records (v1.0).

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        start_date: Filter start date.
        end_date: Filter end date.

    Returns:
        Paginated body composition records.
    """
    query = select(BodyComposition).where(BodyComposition.user_id == current_user.id)

    if start_date:
        query = query.where(BodyComposition.date >= start_date)
    if end_date:
        query = query.where(BodyComposition.date <= end_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(BodyComposition.date.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    records = result.scalars().all()

    return BodyCompositionListResponse(
        items=[BodyCompositionRecord.model_validate(r) for r in records],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/fitness", response_model=FitnessMetricListResponse)
async def list_fitness_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: date | None = Query(None, description="Filter from date"),
    end_date: date | None = Query(None, description="Filter to date"),
) -> FitnessMetricListResponse:
    """Get fitness metrics records (v1.0).

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        start_date: Filter start date.
        end_date: Filter end date.

    Returns:
        Paginated fitness metric records.
    """
    query = select(FitnessMetricDaily).where(FitnessMetricDaily.user_id == current_user.id)

    if start_date:
        query = query.where(FitnessMetricDaily.date >= start_date)
    if end_date:
        query = query.where(FitnessMetricDaily.date <= end_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(FitnessMetricDaily.date.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    records = result.scalars().all()

    return FitnessMetricListResponse(
        items=[FitnessMetricRecord.model_validate(r) for r in records],
        total=total,
        page=page,
        per_page=per_page,
    )
