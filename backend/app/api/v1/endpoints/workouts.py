"""Workout and Schedule endpoints."""

from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.workout import Workout, WorkoutSchedule

router = APIRouter()


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class WorkoutStepCreate(BaseModel):
    """Workout step for creation."""

    type: str  # warmup, main, cooldown, rest, recovery
    duration_minutes: int | None = None
    distance_km: float | None = None
    target_pace: str | None = None
    target_hr_zone: int | None = None
    description: str | None = None


class WorkoutCreate(BaseModel):
    """Request to create a workout."""

    name: str
    workout_type: str  # easy, long, tempo, interval, hills, fartlek
    structure: list[WorkoutStepCreate] | None = None
    target: dict[str, Any] | None = None
    notes: str | None = None


class WorkoutUpdate(BaseModel):
    """Request to update a workout."""

    name: str | None = None
    workout_type: str | None = None
    structure: list[WorkoutStepCreate] | None = None
    target: dict[str, Any] | None = None
    notes: str | None = None


class WorkoutResponse(BaseModel):
    """Workout response."""

    id: int
    name: str
    workout_type: str
    structure: dict[str, Any] | None
    target: dict[str, Any] | None
    garmin_workout_id: int | None
    plan_week_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkoutListResponse(BaseModel):
    """Paginated workout list."""

    items: list[WorkoutResponse]
    total: int


class ScheduleCreate(BaseModel):
    """Request to schedule a workout."""

    workout_id: int
    scheduled_date: date


class ScheduleResponse(BaseModel):
    """Workout schedule response."""

    id: int
    workout_id: int
    scheduled_date: date
    status: str
    garmin_schedule_id: int | None
    workout: WorkoutResponse | None = None

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    """Scheduled workouts list."""

    items: list[ScheduleResponse]
    total: int


# -------------------------------------------------------------------------
# Workout CRUD
# -------------------------------------------------------------------------


@router.get("", response_model=WorkoutListResponse)
async def list_workouts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    workout_type: str | None = None,
) -> WorkoutListResponse:
    """List workouts.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        workout_type: Filter by type.

    Returns:
        Paginated workout list.
    """
    query = select(Workout).where(Workout.user_id == current_user.id)

    if workout_type:
        query = query.where(Workout.workout_type == workout_type)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(Workout.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    workouts = result.scalars().all()

    return WorkoutListResponse(
        items=[WorkoutResponse.model_validate(w) for w in workouts],
        total=total,
    )


@router.post("", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
async def create_workout(
    request: WorkoutCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> WorkoutResponse:
    """Create a new workout.

    FR-021: 워크아웃 생성

    Args:
        request: Workout data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created workout.
    """
    workout = Workout(
        user_id=current_user.id,
        name=request.name,
        workout_type=request.workout_type,
        structure=[s.model_dump() for s in request.structure] if request.structure else None,
        target=request.target,
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    return WorkoutResponse.model_validate(workout)


@router.get("/{workout_id}", response_model=WorkoutResponse)
async def get_workout(
    workout_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> WorkoutResponse:
    """Get workout detail.

    Args:
        workout_id: Workout ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Workout detail.
    """
    result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == current_user.id,
        )
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    return WorkoutResponse.model_validate(workout)


@router.patch("/{workout_id}", response_model=WorkoutResponse)
async def update_workout(
    workout_id: int,
    request: WorkoutUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> WorkoutResponse:
    """Update a workout.

    Args:
        workout_id: Workout ID.
        request: Update data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated workout.
    """
    result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == current_user.id,
        )
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    if request.name is not None:
        workout.name = request.name
    if request.workout_type is not None:
        workout.workout_type = request.workout_type
    if request.structure is not None:
        workout.structure = [s.model_dump() for s in request.structure]
    if request.target is not None:
        workout.target = request.target

    workout.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workout)

    return WorkoutResponse.model_validate(workout)


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout(
    workout_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workout.

    Args:
        workout_id: Workout ID.
        current_user: Authenticated user.
        db: Database session.
    """
    result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == current_user.id,
        )
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    await db.delete(workout)
    await db.commit()


# -------------------------------------------------------------------------
# Garmin Push
# -------------------------------------------------------------------------


class GarminPushResponse(BaseModel):
    """Garmin push response."""

    success: bool
    garmin_workout_id: int | None
    message: str


@router.post("/{workout_id}/push", response_model=GarminPushResponse)
async def push_to_garmin(
    workout_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GarminPushResponse:
    """Push workout to Garmin Connect.

    FR-022: Garmin 워크아웃 전송

    Args:
        workout_id: Workout ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Push result.
    """
    result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == current_user.id,
        )
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    # TODO: Implement Garmin workout push via adapter
    # garmin_id = await garmin_adapter.create_workout(workout)
    # workout.garmin_workout_id = garmin_id
    # await db.commit()

    return GarminPushResponse(
        success=False,
        garmin_workout_id=None,
        message="Garmin push not yet implemented",
    )


# -------------------------------------------------------------------------
# Scheduling
# -------------------------------------------------------------------------


@router.get("/schedules/list", response_model=ScheduleListResponse)
async def list_schedules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    start_date: date | None = None,
    end_date: date | None = None,
    status_filter: str | None = None,
) -> ScheduleListResponse:
    """List scheduled workouts.

    Args:
        current_user: Authenticated user.
        db: Database session.
        start_date: Filter from date.
        end_date: Filter to date.
        status_filter: Filter by status.

    Returns:
        Scheduled workouts.
    """
    query = (
        select(WorkoutSchedule)
        .join(Workout)
        .where(Workout.user_id == current_user.id)
        .options(selectinload(WorkoutSchedule.workout))
    )

    if start_date:
        query = query.where(WorkoutSchedule.scheduled_date >= start_date)
    if end_date:
        query = query.where(WorkoutSchedule.scheduled_date <= end_date)
    if status_filter:
        query = query.where(WorkoutSchedule.status == status_filter)

    query = query.order_by(WorkoutSchedule.scheduled_date.asc())

    result = await db.execute(query)
    schedules = result.scalars().all()

    return ScheduleListResponse(
        items=[
            ScheduleResponse(
                id=s.id,
                workout_id=s.workout_id,
                scheduled_date=s.scheduled_date,
                status=s.status,
                garmin_schedule_id=s.garmin_schedule_id,
                workout=WorkoutResponse.model_validate(s.workout) if s.workout else None,
            )
            for s in schedules
        ],
        total=len(schedules),
    )


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def schedule_workout(
    request: ScheduleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Schedule a workout on a date.

    FR-023: 워크아웃 스케줄링

    Args:
        request: Schedule data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created schedule.
    """
    # Verify workout ownership
    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == request.workout_id,
            Workout.user_id == current_user.id,
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found",
        )

    schedule = WorkoutSchedule(
        workout_id=request.workout_id,
        scheduled_date=request.scheduled_date,
        status="scheduled",
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        workout_id=schedule.workout_id,
        scheduled_date=schedule.scheduled_date,
        status=schedule.status,
        garmin_schedule_id=schedule.garmin_schedule_id,
    )


@router.patch("/schedules/{schedule_id}/status")
async def update_schedule_status(
    schedule_id: int,
    new_status: str = Query(..., regex="^(scheduled|completed|skipped|cancelled)$"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Update schedule status.

    Args:
        schedule_id: Schedule ID.
        new_status: New status.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated schedule.
    """
    result = await db.execute(
        select(WorkoutSchedule)
        .join(Workout)
        .where(
            WorkoutSchedule.id == schedule_id,
            Workout.user_id == current_user.id,
        )
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    schedule.status = new_status
    schedule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        workout_id=schedule.workout_id,
        scheduled_date=schedule.scheduled_date,
        status=schedule.status,
        garmin_schedule_id=schedule.garmin_schedule_id,
    )


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a schedule.

    Args:
        schedule_id: Schedule ID.
        current_user: Authenticated user.
        db: Database session.
    """
    result = await db.execute(
        select(WorkoutSchedule)
        .join(Workout)
        .where(
            WorkoutSchedule.id == schedule_id,
            Workout.user_id == current_user.id,
        )
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    await db.delete(schedule)
    await db.commit()
