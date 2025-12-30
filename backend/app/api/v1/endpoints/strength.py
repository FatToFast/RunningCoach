"""Strength training endpoints."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.strength import StrengthExercise, StrengthSession
from app.models.user import User

router = APIRouter()

# -------------------------------------------------------------------------
# Constants - Session Types and Purposes
# -------------------------------------------------------------------------

SESSION_TYPES = [
    {"value": "upper", "label": "상체", "label_en": "Upper Body"},
    {"value": "lower", "label": "하체", "label_en": "Lower Body"},
    {"value": "core", "label": "코어", "label_en": "Core"},
    {"value": "full_body", "label": "전신", "label_en": "Full Body"},
]

SESSION_PURPOSES = [
    {"value": "strength", "label": "근력", "label_en": "Strength"},
    {"value": "flexibility", "label": "유연성", "label_en": "Flexibility"},
    {"value": "balance", "label": "밸런스", "label_en": "Balance"},
    {"value": "injury_prevention", "label": "부상예방", "label_en": "Injury Prevention"},
]

# -------------------------------------------------------------------------
# Preset Exercises (useful for runners)
# -------------------------------------------------------------------------

PRESET_EXERCISES = [
    # Lower body - most important for runners
    {"name": "스쿼트", "name_en": "Squat", "category": "lower"},
    {"name": "런지", "name_en": "Lunge", "category": "lower"},
    {"name": "데드리프트", "name_en": "Deadlift", "category": "lower"},
    {"name": "카프레이즈", "name_en": "Calf Raise", "category": "lower"},
    {"name": "레그프레스", "name_en": "Leg Press", "category": "lower"},
    {"name": "힙브릿지", "name_en": "Hip Bridge", "category": "lower"},
    {"name": "레그컬", "name_en": "Leg Curl", "category": "lower"},
    {"name": "레그익스텐션", "name_en": "Leg Extension", "category": "lower"},
    {"name": "싱글레그 스쿼트", "name_en": "Single Leg Squat", "category": "lower"},
    {"name": "스텝업", "name_en": "Step Up", "category": "lower"},
    # Core - essential for running form
    {"name": "플랭크", "name_en": "Plank", "category": "core"},
    {"name": "러시안 트위스트", "name_en": "Russian Twist", "category": "core"},
    {"name": "버드독", "name_en": "Bird Dog", "category": "core"},
    {"name": "데드버그", "name_en": "Dead Bug", "category": "core"},
    {"name": "사이드플랭크", "name_en": "Side Plank", "category": "core"},
    {"name": "크런치", "name_en": "Crunch", "category": "core"},
    {"name": "레그레이즈", "name_en": "Leg Raise", "category": "core"},
    {"name": "마운틴클라이머", "name_en": "Mountain Climber", "category": "core"},
    # Upper body
    {"name": "푸시업", "name_en": "Push-up", "category": "upper"},
    {"name": "풀업", "name_en": "Pull-up", "category": "upper"},
    {"name": "덤벨 로우", "name_en": "Dumbbell Row", "category": "upper"},
    {"name": "숄더프레스", "name_en": "Shoulder Press", "category": "upper"},
    {"name": "암컬", "name_en": "Arm Curl", "category": "upper"},
    {"name": "트라이셉 익스텐션", "name_en": "Tricep Extension", "category": "upper"},
    {"name": "랫풀다운", "name_en": "Lat Pulldown", "category": "upper"},
    # Full body / functional
    {"name": "버피", "name_en": "Burpee", "category": "full_body"},
    {"name": "박스점프", "name_en": "Box Jump", "category": "full_body"},
    {"name": "케틀벨 스윙", "name_en": "Kettlebell Swing", "category": "full_body"},
    {"name": "클린", "name_en": "Clean", "category": "full_body"},
    {"name": "스내치", "name_en": "Snatch", "category": "full_body"},
]


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class ExerciseSetSchema(BaseModel):
    """Individual set within an exercise."""

    weight_kg: float | None = Field(None, ge=0, description="Weight in kg (None for bodyweight)")
    reps: int = Field(..., ge=1, description="Number of repetitions")
    rest_seconds: int | None = Field(None, ge=0, description="Rest time after this set in seconds")


class ExerciseCreateSchema(BaseModel):
    """Schema for creating an exercise."""

    exercise_name: str = Field(..., min_length=1, max_length=100)
    is_custom: bool = False
    sets: list[ExerciseSetSchema] = Field(default_factory=list)
    notes: str | None = None


class ExerciseUpdateSchema(BaseModel):
    """Schema for updating an exercise."""

    exercise_name: str | None = Field(None, min_length=1, max_length=100)
    sets: list[ExerciseSetSchema] | None = None
    notes: str | None = None


class ExerciseResponse(BaseModel):
    """Exercise response."""

    id: int
    exercise_name: str
    is_custom: bool
    order: int
    sets: list[ExerciseSetSchema]
    notes: str | None

    class Config:
        from_attributes = True


class StrengthSessionCreateRequest(BaseModel):
    """Request to create a strength session."""

    session_date: date
    session_type: str = Field(..., description="상체/하체/코어/전신")
    session_purpose: str | None = Field(None, description="근력/유연성/밸런스/부상예방")
    duration_minutes: int | None = Field(None, ge=0)
    notes: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    exercises: list[ExerciseCreateSchema] = Field(default_factory=list)


class StrengthSessionUpdateRequest(BaseModel):
    """Request to update a strength session."""

    session_date: date | None = None
    session_type: str | None = None
    session_purpose: str | None = None
    duration_minutes: int | None = Field(None, ge=0)
    notes: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    exercises: list[ExerciseCreateSchema] | None = None  # Replace all exercises if provided


class StrengthSessionResponse(BaseModel):
    """Strength session response."""

    id: int
    session_date: date
    session_type: str
    session_purpose: str | None
    duration_minutes: int | None
    notes: str | None
    rating: int | None
    exercises: list[ExerciseResponse]
    total_sets: int
    total_exercises: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrengthSessionSummary(BaseModel):
    """Strength session summary for list view."""

    id: int
    session_date: date
    session_type: str
    session_purpose: str | None
    duration_minutes: int | None
    rating: int | None
    exercise_count: int
    total_sets: int

    class Config:
        from_attributes = True


class StrengthSessionListResponse(BaseModel):
    """Strength session list response."""

    items: list[StrengthSessionSummary]
    total: int


class SessionTypesResponse(BaseModel):
    """Session types and purposes."""

    types: list[dict]
    purposes: list[dict]


class ExercisePresetsResponse(BaseModel):
    """Preset exercises list."""

    exercises: list[dict]


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------


def build_session_response(session: StrengthSession) -> StrengthSessionResponse:
    """Build session response with calculated fields."""
    exercises = [
        ExerciseResponse(
            id=ex.id,
            exercise_name=ex.exercise_name,
            is_custom=ex.is_custom,
            order=ex.order,
            sets=[ExerciseSetSchema(**s) for s in (ex.sets or [])],
            notes=ex.notes,
        )
        for ex in session.exercises
    ]

    total_sets = sum(len(ex.sets) for ex in exercises)

    return StrengthSessionResponse(
        id=session.id,
        session_date=session.session_date,
        session_type=session.session_type,
        session_purpose=session.session_purpose,
        duration_minutes=session.duration_minutes,
        notes=session.notes,
        rating=session.rating,
        exercises=exercises,
        total_sets=total_sets,
        total_exercises=len(exercises),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def build_session_summary(session: StrengthSession) -> StrengthSessionSummary:
    """Build session summary for list view."""
    exercise_count = len(session.exercises)
    total_sets = sum(len(ex.sets or []) for ex in session.exercises)

    return StrengthSessionSummary(
        id=session.id,
        session_date=session.session_date,
        session_type=session.session_type,
        session_purpose=session.session_purpose,
        duration_minutes=session.duration_minutes,
        rating=session.rating,
        exercise_count=exercise_count,
        total_sets=total_sets,
    )


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/types", response_model=SessionTypesResponse)
async def get_session_types() -> SessionTypesResponse:
    """Get available session types and purposes.

    Returns:
        Session types and purposes.
    """
    return SessionTypesResponse(types=SESSION_TYPES, purposes=SESSION_PURPOSES)


@router.get("/exercises/presets", response_model=ExercisePresetsResponse)
async def get_exercise_presets(
    category: str | None = Query(None, description="Filter by category: upper, lower, core, full_body"),
) -> ExercisePresetsResponse:
    """Get preset exercise list for runners.

    Args:
        category: Optional category filter.

    Returns:
        List of preset exercises.
    """
    exercises = PRESET_EXERCISES
    if category:
        exercises = [e for e in exercises if e["category"] == category]
    return ExercisePresetsResponse(exercises=exercises)


@router.get("", response_model=StrengthSessionListResponse)
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(None, description="Filter from date (inclusive)"),
    end_date: date | None = Query(None, description="Filter to date (inclusive)"),
    session_type: str | None = Query(None, description="Filter by session type"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Skip results"),
) -> StrengthSessionListResponse:
    """List strength sessions for the current user.

    Args:
        current_user: Authenticated user.
        db: Database session.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        session_type: Optional session type filter.
        limit: Max results.
        offset: Skip results.

    Returns:
        List of strength sessions.
    """
    query = (
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.user_id == current_user.id)
    )

    if start_date:
        query = query.where(StrengthSession.session_date >= start_date)
    if end_date:
        query = query.where(StrengthSession.session_date <= end_date)
    if session_type:
        query = query.where(StrengthSession.session_type == session_type)

    # Count total
    count_query = select(func.count()).select_from(
        query.with_only_columns(StrengthSession.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(StrengthSession.session_date.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    sessions = result.scalars().all()

    items = [build_session_summary(s) for s in sessions]

    return StrengthSessionListResponse(items=items, total=total)


@router.get("/calendar/{year}/{month}", response_model=list[StrengthSessionSummary])
async def get_calendar_sessions(
    year: int,
    month: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[StrengthSessionSummary]:
    """Get strength sessions for calendar view (specific month).

    Args:
        year: Year.
        month: Month (1-12).
        current_user: Authenticated user.
        db: Database session.

    Returns:
        List of sessions for the month.
    """
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(
            StrengthSession.user_id == current_user.id,
            StrengthSession.session_date >= start_date,
            StrengthSession.session_date <= end_date,
        )
        .order_by(StrengthSession.session_date.asc())
    )
    sessions = result.scalars().all()

    return [build_session_summary(s) for s in sessions]


@router.get("/{strength_session_id}", response_model=StrengthSessionResponse)
async def get_session(
    strength_session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StrengthSessionResponse:
    """Get strength session details.

    Args:
        strength_session_id: Strength session ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Session details with exercises.
    """
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == strength_session_id, StrengthSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return build_session_response(session)


@router.post("", response_model=StrengthSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: StrengthSessionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StrengthSessionResponse:
    """Create a new strength session.

    Args:
        data: Session data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created session.
    """
    session = StrengthSession(
        user_id=current_user.id,
        session_date=data.session_date,
        session_type=data.session_type,
        session_purpose=data.session_purpose,
        duration_minutes=data.duration_minutes,
        notes=data.notes,
        rating=data.rating,
    )
    db.add(session)
    await db.flush()  # Get session ID

    # Create exercises
    for i, ex_data in enumerate(data.exercises):
        exercise = StrengthExercise(
            session_id=session.id,
            exercise_name=ex_data.exercise_name,
            is_custom=ex_data.is_custom,
            order=i,
            sets=[s.model_dump() for s in ex_data.sets],
            notes=ex_data.notes,
        )
        db.add(exercise)

    await db.commit()

    # Reload with exercises
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == session.id)
    )
    session = result.scalar_one()

    return build_session_response(session)


@router.patch("/{strength_session_id}", response_model=StrengthSessionResponse)
async def update_session(
    strength_session_id: int,
    data: StrengthSessionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> StrengthSessionResponse:
    """Update a strength session.

    Args:
        session_id: Session ID.
        data: Update data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated session.
    """
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == strength_session_id, StrengthSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Update basic fields
    update_data = data.model_dump(exclude_unset=True, exclude={"exercises"})
    for field, value in update_data.items():
        setattr(session, field, value)

    # Replace exercises if provided
    if data.exercises is not None:
        # Delete existing exercises
        for ex in session.exercises:
            await db.delete(ex)

        # Create new exercises
        for i, ex_data in enumerate(data.exercises):
            exercise = StrengthExercise(
                session_id=session.id,
                exercise_name=ex_data.exercise_name,
                is_custom=ex_data.is_custom,
                order=i,
                sets=[s.model_dump() for s in ex_data.sets],
                notes=ex_data.notes,
            )
            db.add(exercise)

    await db.commit()

    # Reload with exercises
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == session.id)
    )
    session = result.scalar_one()

    return build_session_response(session)


@router.delete("/{strength_session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    strength_session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a strength session.

    Args:
        session_id: Session ID.
        current_user: Authenticated user.
        db: Database session.
    """
    result = await db.execute(
        select(StrengthSession).where(
            StrengthSession.id == strength_session_id, StrengthSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await db.delete(session)
    await db.commit()


# -------------------------------------------------------------------------
# Exercise-level endpoints (for adding/removing individual exercises)
# -------------------------------------------------------------------------


@router.post("/{strength_session_id}/exercises", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
async def add_exercise(
    strength_session_id: int,
    data: ExerciseCreateSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ExerciseResponse:
    """Add an exercise to a session.

    Args:
        session_id: Session ID.
        data: Exercise data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created exercise.
    """
    # Verify session ownership
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == strength_session_id, StrengthSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get next order
    max_order = max((ex.order for ex in session.exercises), default=-1)

    exercise = StrengthExercise(
        session_id=session.id,
        exercise_name=data.exercise_name,
        is_custom=data.is_custom,
        order=max_order + 1,
        sets=[s.model_dump() for s in data.sets],
        notes=data.notes,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)

    return ExerciseResponse(
        id=exercise.id,
        exercise_name=exercise.exercise_name,
        is_custom=exercise.is_custom,
        order=exercise.order,
        sets=[ExerciseSetSchema(**s) for s in (exercise.sets or [])],
        notes=exercise.notes,
    )


@router.delete("/{strength_session_id}/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_exercise(
    strength_session_id: int,
    exercise_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an exercise from a session.

    Args:
        session_id: Session ID.
        exercise_id: Exercise ID.
        current_user: Authenticated user.
        db: Database session.
    """
    # Verify session ownership
    session_result = await db.execute(
        select(StrengthSession).where(
            StrengthSession.id == strength_session_id, StrengthSession.user_id == current_user.id
        )
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Find and delete exercise
    result = await db.execute(
        select(StrengthExercise).where(
            StrengthExercise.id == exercise_id, StrengthExercise.session_id == strength_session_id
        )
    )
    exercise = result.scalar_one_or_none()

    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    await db.delete(exercise)
    await db.commit()


