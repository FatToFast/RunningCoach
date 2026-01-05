"""Workout and Schedule endpoints."""

import asyncio
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.adapters.garmin_adapter import GarminAuthError, GarminConnectAdapter, GarminAPIError
from app.core.database import get_db
from app.models.garmin import GarminSession
from app.models.user import User
from app.models.workout import Workout, WorkoutSchedule, WorkoutScheduleStatus

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
    structure: list[dict[str, Any]] | None  # List of workout steps
    target: dict[str, Any] | None
    notes: str | None
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
    completed_activity_id: int | None = None
    workout: WorkoutResponse | None = None

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    """Paginated scheduled workouts list."""

    items: list[ScheduleResponse]
    total: int
    page: int = 1
    per_page: int = 20


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
        notes=request.notes,
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
    if request.notes is not None:
        workout.notes = request.notes

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

    if workout.garmin_workout_id:
        return GarminPushResponse(
            success=True,
            garmin_workout_id=workout.garmin_workout_id,
            message="Workout already pushed to Garmin",
        )

    if not workout.structure:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workout structure is missing",
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

    try:
        loop = asyncio.get_event_loop()
        garmin_id = await loop.run_in_executor(
            None,
            lambda w=workout: adapter.upload_running_workout_template(w),
        )
    except GarminAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload workout to Garmin: {exc}",
        ) from exc

    workout.garmin_workout_id = garmin_id
    workout.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workout)

    return GarminPushResponse(
        success=True,
        garmin_workout_id=garmin_id,
        message="Workout uploaded to Garmin",
    )


# -------------------------------------------------------------------------
# Scheduling
# -------------------------------------------------------------------------


@router.get("/schedules/list", response_model=ScheduleListResponse)
async def list_schedules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    status_filter: WorkoutScheduleStatus | None = None,
) -> ScheduleListResponse:
    """List scheduled workouts with pagination.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number.
        per_page: Items per page.
        start_date: Filter from date.
        end_date: Filter to date.
        status_filter: Filter by status.

    Returns:
        Paginated scheduled workouts.
    """
    base_query = (
        select(WorkoutSchedule)
        .join(Workout)
        .where(Workout.user_id == current_user.id)
    )

    if start_date:
        base_query = base_query.where(WorkoutSchedule.scheduled_date >= start_date)
    if end_date:
        base_query = base_query.where(WorkoutSchedule.scheduled_date <= end_date)
    if status_filter:
        base_query = base_query.where(WorkoutSchedule.status == status_filter.value)

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate with stable ordering (tie-breaker: id for consistent pagination)
    offset = (page - 1) * per_page
    query = (
        base_query
        .options(selectinload(WorkoutSchedule.workout))
        .order_by(WorkoutSchedule.scheduled_date.asc(), WorkoutSchedule.id.asc())
        .offset(offset)
        .limit(per_page)
    )

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
                completed_activity_id=s.completed_activity_id,
                workout=WorkoutResponse.model_validate(s.workout) if s.workout else None,
            )
            for s in schedules
        ],
        total=total,
        page=page,
        per_page=per_page,
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

    # DB unique constraint (workout_id, scheduled_date) prevents duplicates
    # IntegrityError will be raised if duplicate exists
    schedule = WorkoutSchedule(
        workout_id=request.workout_id,
        scheduled_date=request.scheduled_date,
        status=WorkoutScheduleStatus.SCHEDULED.value,
    )
    db.add(schedule)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workout already scheduled for {request.scheduled_date}",
        )

    await db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        workout_id=schedule.workout_id,
        scheduled_date=schedule.scheduled_date,
        status=schedule.status,
        garmin_schedule_id=schedule.garmin_schedule_id,
        completed_activity_id=schedule.completed_activity_id,
    )


class ScheduleStatusUpdate(BaseModel):
    """Request to update schedule status."""

    status: WorkoutScheduleStatus
    completed_activity_id: int | None = None  # Required when status=COMPLETED


@router.patch("/schedules/{schedule_id}/status")
async def update_schedule_status(
    schedule_id: int,
    request: ScheduleStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Update schedule status.

    Args:
        schedule_id: Schedule ID.
        request: Status update data.
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

    schedule.status = request.status.value
    if request.completed_activity_id is not None:
        schedule.completed_activity_id = request.completed_activity_id
    schedule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(schedule)

    return ScheduleResponse(
        id=schedule.id,
        workout_id=schedule.workout_id,
        scheduled_date=schedule.scheduled_date,
        status=schedule.status,
        garmin_schedule_id=schedule.garmin_schedule_id,
        completed_activity_id=schedule.completed_activity_id,
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


# -------------------------------------------------------------------------
# Garmin Workout Import
# -------------------------------------------------------------------------


class GarminWorkoutPreview(BaseModel):
    """Preview of a Garmin workout for import."""

    garmin_workout_id: int
    name: str
    workout_type: str
    description: str | None
    estimated_duration_seconds: int | None
    step_count: int
    already_imported: bool


class GarminWorkoutsListResponse(BaseModel):
    """List of Garmin workouts available for import."""

    items: list[GarminWorkoutPreview]
    total: int


class GarminWorkoutImportRequest(BaseModel):
    """Request to import Garmin workouts."""

    garmin_workout_ids: list[int]


class GarminWorkoutImportResponse(BaseModel):
    """Response from Garmin workout import."""

    imported: int
    skipped: int
    errors: list[str]


def _map_garmin_workout_type(garmin_type: str | None) -> str:
    """Map Garmin workout type to our workout types."""
    if not garmin_type:
        return "easy"
    garmin_type = garmin_type.lower()
    mapping = {
        "interval": "interval",
        "tempo": "tempo",
        "long_run": "long",
        "recovery": "recovery",
        "easy": "easy",
        "fartlek": "fartlek",
        "hill": "hills",
        "hills": "hills",
    }
    return mapping.get(garmin_type, "easy")


def _parse_pace_from_speed(speed_mps: float | None) -> str | None:
    """Convert speed (m/s) to pace (min:sec/km)."""
    if not speed_mps or speed_mps <= 0:
        return None
    # speed in m/s -> pace in sec/km
    pace_seconds_per_km = 1000 / speed_mps
    minutes = int(pace_seconds_per_km // 60)
    seconds = int(pace_seconds_per_km % 60)
    return f"{minutes}:{seconds:02d}"


def _parse_single_step(step: dict) -> dict | None:
    """Parse a single Garmin workout step into our format.

    Args:
        step: Garmin step data.

    Returns:
        Parsed step dict or None if invalid.
    """
    step_type_data = step.get("stepType", {})
    step_type_key = step_type_data.get("stepTypeKey", "interval")

    # Map Garmin step types to our types
    type_mapping = {
        "warmup": "warmup",
        "cooldown": "cooldown",
        "interval": "main",
        "recovery": "recovery",
        "rest": "rest",
    }
    mapped_type = type_mapping.get(step_type_key, "main")

    # Parse end condition (duration or distance)
    end_condition = step.get("endCondition", {})
    end_condition_key = end_condition.get("conditionTypeKey", "")
    end_value = step.get("endConditionValue", 0)

    parsed_step = {
        "type": mapped_type,
        "duration_minutes": None,
        "distance_km": None,
        "target_pace": None,
        "target_hr_zone": None,
        "description": step.get("description"),
    }

    # Parse duration or distance
    if end_condition_key == "distance":
        # Value is in meters
        parsed_step["distance_km"] = round(end_value / 1000, 2) if end_value else None
    elif end_condition_key == "time":
        # Value is in seconds
        parsed_step["duration_minutes"] = round(end_value / 60, 1) if end_value else None

    # Parse target (pace, HR zone, speed)
    target_type = step.get("targetType", {})
    target_type_key = target_type.get("workoutTargetTypeKey", "")
    target_value = step.get("targetValue", {}) if isinstance(step.get("targetValue"), dict) else {}

    # Target value can also be in targetValueOne/targetValueTwo for ranges
    target_value_one = step.get("targetValueOne")
    target_value_two = step.get("targetValueTwo")

    if target_type_key == "pace.zone":
        # Pace zone - use low/high values (in m/s)
        low_speed = target_value.get("lowInMetersPerSecond") or target_value_one
        high_speed = target_value.get("highInMetersPerSecond") or target_value_two
        if low_speed and high_speed:
            # Use average pace
            avg_speed = (low_speed + high_speed) / 2
            parsed_step["target_pace"] = _parse_pace_from_speed(avg_speed)
        elif low_speed:
            parsed_step["target_pace"] = _parse_pace_from_speed(low_speed)
    elif target_type_key == "speed.zone":
        # Speed zone - similar to pace
        low_speed = target_value.get("lowInMetersPerSecond") or target_value_one
        high_speed = target_value.get("highInMetersPerSecond") or target_value_two
        if low_speed and high_speed:
            avg_speed = (low_speed + high_speed) / 2
            parsed_step["target_pace"] = _parse_pace_from_speed(avg_speed)
        elif high_speed:
            parsed_step["target_pace"] = _parse_pace_from_speed(high_speed)
    elif target_type_key == "heart.rate.zone":
        # HR zone - extract zone number
        zone_number = target_value.get("zoneNumber")
        if zone_number:
            parsed_step["target_hr_zone"] = zone_number
        elif target_value_one:
            # Sometimes it's just a number indicating zone
            parsed_step["target_hr_zone"] = int(target_value_one) if target_value_one <= 5 else None

    return parsed_step


def _parse_garmin_workout_steps(workout_data: dict) -> list[dict]:
    """Parse Garmin workout steps into our format.

    Handles nested RepeatGroupDTO structures for interval workouts.
    """
    steps = []
    segments = workout_data.get("workoutSegments", [])

    for segment in segments:
        workout_steps = segment.get("workoutSteps", [])
        for step in workout_steps:
            step_type = step.get("type", "")

            # Handle repeat groups (intervals)
            if step_type == "RepeatGroupDTO":
                repeat_count = step.get("numberOfIterations", 1)
                nested_steps = step.get("workoutSteps", [])

                # Add a marker for repeat group start
                steps.append({
                    "type": "main",
                    "duration_minutes": None,
                    "distance_km": None,
                    "target_pace": None,
                    "target_hr_zone": None,
                    "description": f"🔄 {repeat_count}회 반복",
                    "is_repeat_marker": True,
                    "repeat_count": repeat_count,
                })

                # Parse nested steps within the repeat group
                for nested_step in nested_steps:
                    parsed = _parse_single_step(nested_step)
                    if parsed:
                        # Add repeat context to description if needed
                        if parsed["description"]:
                            parsed["description"] = f"[x{repeat_count}] {parsed['description']}"
                        steps.append(parsed)
            else:
                # Regular step (warmup, cooldown, etc.)
                parsed = _parse_single_step(step)
                if parsed:
                    steps.append(parsed)

    return steps


@router.get("/garmin/list", response_model=GarminWorkoutsListResponse)
async def list_garmin_workouts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
) -> GarminWorkoutsListResponse:
    """List workouts from Garmin Connect available for import.

    Args:
        current_user: Authenticated user.
        db: Database session.
        limit: Max workouts to fetch.

    Returns:
        List of Garmin workouts.
    """
    # Get Garmin session
    session_result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    if not session or not session.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    # Get already imported Garmin workout IDs
    imported_result = await db.execute(
        select(Workout.garmin_workout_id).where(
            Workout.user_id == current_user.id,
            Workout.garmin_workout_id.isnot(None),
        )
    )
    imported_ids = {row[0] for row in imported_result.all()}

    adapter = GarminConnectAdapter()
    try:
        adapter.restore_session(session.session_data)
    except GarminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Garmin session expired. Please reconnect.",
        ) from exc

    try:
        loop = asyncio.get_event_loop()
        garmin_workouts = await loop.run_in_executor(
            None,
            lambda: adapter.get_workouts(limit),
        )
    except GarminAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Garmin workouts: {exc}",
        ) from exc

    items = []
    for gw in garmin_workouts:
        garmin_id = gw.get("workoutId")
        if not garmin_id:
            continue

        # Count steps
        step_count = 0
        for segment in gw.get("workoutSegments", []):
            step_count += len(segment.get("workoutSteps", []))

        items.append(
            GarminWorkoutPreview(
                garmin_workout_id=garmin_id,
                name=gw.get("workoutName", "Untitled"),
                workout_type=_map_garmin_workout_type(gw.get("subTypeKey")),
                description=gw.get("description"),
                estimated_duration_seconds=gw.get("estimatedDurationInSecs"),
                step_count=step_count,
                already_imported=garmin_id in imported_ids,
            )
        )

    return GarminWorkoutsListResponse(items=items, total=len(items))


@router.post("/garmin/import", response_model=GarminWorkoutImportResponse)
async def import_garmin_workouts(
    request: GarminWorkoutImportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GarminWorkoutImportResponse:
    """Import selected workouts from Garmin Connect.

    Args:
        request: List of Garmin workout IDs to import.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Import result summary.
    """
    # Get Garmin session
    session_result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()

    if not session or not session.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin account not connected",
        )

    # Get already imported Garmin workout IDs
    imported_result = await db.execute(
        select(Workout.garmin_workout_id).where(
            Workout.user_id == current_user.id,
            Workout.garmin_workout_id.isnot(None),
        )
    )
    imported_ids = {row[0] for row in imported_result.all()}

    adapter = GarminConnectAdapter()
    try:
        adapter.restore_session(session.session_data)
    except GarminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Garmin session expired. Please reconnect.",
        ) from exc

    imported = 0
    skipped = 0
    errors = []

    for garmin_id in request.garmin_workout_ids:
        # Skip already imported
        if garmin_id in imported_ids:
            skipped += 1
            continue

        try:
            loop = asyncio.get_event_loop()
            garmin_workout = await loop.run_in_executor(
                None,
                lambda gid=garmin_id: adapter.get_workout_by_id(gid),
            )

            if not garmin_workout:
                errors.append(f"Workout {garmin_id} not found")
                continue

            # Parse workout structure
            structure = _parse_garmin_workout_steps(garmin_workout)

            # Create local workout
            workout = Workout(
                user_id=current_user.id,
                name=garmin_workout.get("workoutName", "Imported Workout"),
                workout_type=_map_garmin_workout_type(garmin_workout.get("subTypeKey")),
                structure=structure if structure else None,
                notes=garmin_workout.get("description"),
                garmin_workout_id=garmin_id,
            )
            db.add(workout)
            imported += 1
            imported_ids.add(garmin_id)  # Track to avoid duplicates in same batch

        except GarminAPIError as exc:
            errors.append(f"Failed to import {garmin_id}: {exc}")
        except Exception as exc:
            errors.append(f"Error importing {garmin_id}: {exc}")

    await db.commit()

    return GarminWorkoutImportResponse(
        imported=imported,
        skipped=skipped,
        errors=errors,
    )


@router.get("/garmin/raw/{workout_id}")
async def get_garmin_workout_raw(
    workout_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get raw Garmin workout data for debugging.

    Args:
        workout_id: Garmin workout ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Raw Garmin workout data.
    """
    # Get Garmin session
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
            detail="Garmin session expired. Please reconnect.",
        ) from exc

    try:
        loop = asyncio.get_event_loop()
        garmin_workout = await loop.run_in_executor(
            None,
            lambda: adapter.get_workout_by_id(workout_id),
        )
        return garmin_workout
    except GarminAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Garmin workout: {exc}",
        ) from exc
