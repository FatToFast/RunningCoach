"""Training Plan endpoints."""

import asyncio
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.adapters.garmin_adapter import GarminAuthError, GarminConnectAdapter, GarminAPIError
from app.core.database import get_db
from app.models.garmin import GarminSession
from app.models.plan import Plan, PlanWeek
from app.models.user import User
from app.models.workout import Workout

router = APIRouter()


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class PlanCreate(BaseModel):
    """Request to create a plan."""

    goal_type: str  # marathon, half, 10k, 5k, fitness
    goal_date: date | None = None
    goal_time: str | None = None
    start_date: date
    end_date: date
    description: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "PlanCreate":
        """Validate date constraints."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        if self.goal_date is not None:
            if self.goal_date < self.start_date:
                raise ValueError("goal_date must be >= start_date")
            if self.goal_date > self.end_date:
                raise ValueError("goal_date must be <= end_date")
        return self


class PlanUpdate(BaseModel):
    """Request to update a plan.

    Note: status cannot be changed directly via update.
    Use dedicated endpoints: /approve, /activate, /complete, /archive
    """

    goal_type: str | None = None
    goal_date: date | None = None
    goal_time: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    # status removed - use dedicated state transition endpoints


class WorkoutSummary(BaseModel):
    """Workout summary for plan view."""

    id: int
    name: str
    workout_type: str

    class Config:
        from_attributes = True


class PlanWeekResponse(BaseModel):
    """Plan week response."""

    id: int
    week_index: int
    focus: str | None
    notes: str | None
    target_distance_km: float | None
    target_duration_minutes: int | None
    workouts: list[WorkoutSummary]

    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    """Plan response."""

    id: int
    goal_type: str
    goal_date: date | None
    goal_time: str | None
    start_date: date
    end_date: date
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanDetailResponse(BaseModel):
    """Plan with weeks."""

    id: int
    goal_type: str
    goal_date: date | None
    goal_time: str | None
    start_date: date
    end_date: date
    status: str
    description: str | None
    weeks: list[PlanWeekResponse]
    created_at: datetime
    updated_at: datetime


class PlanListResponse(BaseModel):
    """Paginated plan list."""

    items: list[PlanResponse]
    total: int


# -------------------------------------------------------------------------
# Plan CRUD
# -------------------------------------------------------------------------


@router.get("", response_model=PlanListResponse)
async def list_plans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = None,
    goal_type: str | None = None,
) -> PlanListResponse:
    """List training plans.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        status_filter: Filter by status.
        goal_type: Filter by goal type.

    Returns:
        Paginated plan list.
    """
    query = select(Plan).where(Plan.user_id == current_user.id)

    if status_filter:
        query = query.where(Plan.status == status_filter)
    if goal_type:
        query = query.where(Plan.goal_type == goal_type)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(Plan.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    plans = result.scalars().all()

    return PlanListResponse(
        items=[PlanResponse.model_validate(p) for p in plans],
        total=total,
    )


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    request: PlanCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Create a new training plan.

    Args:
        request: Plan data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created plan.
    """
    plan = Plan(
        user_id=current_user.id,
        goal_type=request.goal_type,
        goal_date=request.goal_date,
        goal_time=request.goal_time,
        start_date=request.start_date,
        end_date=request.end_date,
        description=request.description,
        status="draft",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    plan_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanDetailResponse:
    """Get plan with all weeks.

    Args:
        plan_id: Plan ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Plan detail with weeks.
    """
    result = await db.execute(
        select(Plan)
        .where(
            Plan.id == plan_id,
            Plan.user_id == current_user.id,
        )
        .options(
            selectinload(Plan.weeks).selectinload(PlanWeek.workouts)
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    return PlanDetailResponse(
        id=plan.id,
        goal_type=plan.goal_type,
        goal_date=plan.goal_date,
        goal_time=plan.goal_time,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        description=plan.description,
        weeks=[
            PlanWeekResponse(
                id=w.id,
                week_index=w.week_index,
                focus=w.focus,
                notes=w.notes,
                target_distance_km=w.target_distance_km,
                target_duration_minutes=w.target_duration_minutes,
                workouts=[WorkoutSummary.model_validate(wo) for wo in w.workouts],
            )
            for w in plan.weeks
        ],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int,
    request: PlanUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Update a plan.

    Args:
        plan_id: Plan ID.
        request: Update data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated plan.
    """
    result = await db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    if request.goal_type is not None:
        plan.goal_type = request.goal_type
    if request.goal_date is not None:
        plan.goal_date = request.goal_date
    if request.goal_time is not None:
        plan.goal_time = request.goal_time
    if request.start_date is not None:
        plan.start_date = request.start_date
    if request.end_date is not None:
        plan.end_date = request.end_date
    if request.description is not None:
        plan.description = request.description
    # status is not updatable directly - use /approve, /activate, /complete endpoints

    plan.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a plan.

    Args:
        plan_id: Plan ID.
        current_user: Authenticated user.
        db: Database session.
    """
    result = await db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    await db.delete(plan)
    await db.commit()


# -------------------------------------------------------------------------
# Plan Approval Flow
# -------------------------------------------------------------------------


@router.post("/{plan_id}/approve", response_model=PlanResponse)
async def approve_plan(
    plan_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Approve a plan for execution.

    FR-032: 계획 승인 플로우

    Args:
        plan_id: Plan ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Approved plan.
    """
    result = await db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.user_id == current_user.id,
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    if plan.status not in ("draft", "approved"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve plan with status '{plan.status}'",
        )

    plan.status = "approved"
    plan.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.post("/{plan_id}/activate", response_model=PlanResponse)
async def activate_plan(
    plan_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Activate a plan and push to Garmin.

    Args:
        plan_id: Plan ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Activated plan.
    """
    result = await db.execute(
        select(Plan)
        .where(
            Plan.id == plan_id,
            Plan.user_id == current_user.id,
        )
        .options(selectinload(Plan.weeks).selectinload(PlanWeek.workouts))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    if plan.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be approved before activation",
        )

    session_result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    if not session or not session.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    adapter = GarminConnectAdapter()
    try:
        adapter.restore_session(session.session_data)
    except GarminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Garmin session expired. Please reconnect via /auth/garmin/connect",
        ) from exc

    loop = asyncio.get_event_loop()
    failed: list[dict[str, Any]] = []

    for week in plan.weeks:
        for workout in week.workouts:
            if workout.garmin_workout_id:
                continue
            if workout.workout_type == "rest" or not workout.structure:
                continue
            try:
                garmin_id = await loop.run_in_executor(
                    None,
                    lambda w=workout: adapter.upload_running_workout_template(w),
                )
                workout.garmin_workout_id = garmin_id
                workout.updated_at = datetime.now(timezone.utc)
                await db.commit()
            except GarminAPIError as exc:
                failed.append(
                    {
                        "workout_id": workout.id,
                        "error": str(exc),
                    }
                )

    if failed:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Failed to upload some workouts to Garmin",
                "failed_workouts": failed,
            },
        )

    plan.status = "active"
    plan.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


# -------------------------------------------------------------------------
# Week Management
# -------------------------------------------------------------------------


class WeekCreate(BaseModel):
    """Request to create a plan week."""

    week_index: int
    focus: str | None = None
    notes: str | None = None
    target_distance_km: float | None = None
    target_duration_minutes: int | None = None


@router.post("/{plan_id}/weeks", response_model=PlanWeekResponse, status_code=status.HTTP_201_CREATED)
async def add_week(
    plan_id: int,
    request: WeekCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> PlanWeekResponse:
    """Add a week to a plan.

    Args:
        plan_id: Plan ID.
        request: Week data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created week.

    Raises:
        404: Plan not found.
        400: Plan is active (cannot modify), week_index duplicate,
             or week_index out of plan range.
    """
    # Verify plan ownership and load existing weeks
    result = await db.execute(
        select(Plan)
        .where(
            Plan.id == plan_id,
            Plan.user_id == current_user.id,
        )
        .options(selectinload(Plan.weeks))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Cannot modify active plans
    if plan.status == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add weeks to an active plan",
        )

    # Calculate max allowed week_index based on plan duration
    plan_duration_days = (plan.end_date - plan.start_date).days + 1
    max_week_index = (plan_duration_days + 6) // 7  # Round up to include partial weeks

    # Validate week_index range
    if request.week_index < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="week_index must be >= 1",
        )
    if request.week_index > max_week_index:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"week_index {request.week_index} exceeds plan duration "
                   f"(max {max_week_index} weeks for {plan_duration_days} days)",
        )

    # Check for duplicate week_index
    existing_indices = {w.week_index for w in plan.weeks}
    if request.week_index in existing_indices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"week_index {request.week_index} already exists in this plan",
        )

    week = PlanWeek(
        plan_id=plan_id,
        week_index=request.week_index,
        focus=request.focus,
        notes=request.notes,
        target_distance_km=request.target_distance_km,
        target_duration_minutes=request.target_duration_minutes,
    )
    db.add(week)
    await db.commit()
    await db.refresh(week)

    return PlanWeekResponse(
        id=week.id,
        week_index=week.week_index,
        focus=week.focus,
        notes=week.notes,
        target_distance_km=week.target_distance_km,
        target_duration_minutes=week.target_duration_minutes,
        workouts=[],
    )
