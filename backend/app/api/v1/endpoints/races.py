"""Race API endpoints for managing race events."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.race import Race
from app.models.user import User
from app.models.garmin import GarminSession
from app.adapters.garmin_adapter import GarminConnectAdapter

router = APIRouter()


# Pydantic schemas
class RaceCreate(BaseModel):
    """Schema for creating a race."""

    name: str = Field(..., min_length=1, max_length=200)
    race_date: date
    distance_km: Optional[float] = None
    distance_label: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=200)
    goal_time_seconds: Optional[int] = None
    goal_description: Optional[str] = None
    is_primary: bool = False


class RaceUpdate(BaseModel):
    """Schema for updating a race."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    race_date: Optional[date] = None
    distance_km: Optional[float] = None
    distance_label: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=200)
    goal_time_seconds: Optional[int] = None
    goal_description: Optional[str] = None
    is_primary: Optional[bool] = None
    is_completed: Optional[bool] = None
    result_time_seconds: Optional[int] = None
    result_notes: Optional[str] = None


class RaceResponse(BaseModel):
    """Schema for race response."""

    id: int
    name: str
    race_date: date
    distance_km: Optional[float]
    distance_label: Optional[str]
    location: Optional[str]
    goal_time_seconds: Optional[int]
    goal_description: Optional[str]
    is_primary: bool
    is_completed: bool
    result_time_seconds: Optional[int]
    result_notes: Optional[str]
    days_until: int  # D-day countdown

    class Config:
        from_attributes = True


class RacesListResponse(BaseModel):
    """Schema for races list response."""

    races: list[RaceResponse]
    primary_race: Optional[RaceResponse]


class GarminRacePrediction(BaseModel):
    """Schema for Garmin race prediction."""

    distance: str  # "5K", "10K", "Half Marathon", "Marathon"
    distance_km: float
    predicted_time_seconds: int
    predicted_time_formatted: str  # "HH:MM:SS"
    pace_per_km: str  # "MM:SS"


class GarminRacePredictionsResponse(BaseModel):
    """Schema for Garmin race predictions response."""

    predictions: list[GarminRacePrediction]
    vo2_max: Optional[float]
    last_updated: Optional[str]


def calculate_days_until(race_date: date) -> int:
    """Calculate days until race."""
    today = date.today()
    delta = race_date - today
    return delta.days


def race_to_response(race: Race) -> RaceResponse:
    """Convert Race model to response schema."""
    return RaceResponse(
        id=race.id,
        name=race.name,
        race_date=race.race_date,
        distance_km=race.distance_km,
        distance_label=race.distance_label,
        location=race.location,
        goal_time_seconds=race.goal_time_seconds,
        goal_description=race.goal_description,
        is_primary=race.is_primary,
        is_completed=race.is_completed,
        result_time_seconds=race.result_time_seconds,
        result_notes=race.result_notes,
        days_until=calculate_days_until(race.race_date),
    )


@router.get("", response_model=RacesListResponse)
async def get_races(
    include_completed: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all races for the current user."""
    query = select(Race).where(Race.user_id == current_user.id)

    if not include_completed:
        query = query.where(Race.is_completed == False)

    query = query.order_by(Race.race_date)
    result = await db.execute(query)
    races = result.scalars().all()

    race_responses = [race_to_response(race) for race in races]

    # Find primary race
    primary_race = next((r for r in race_responses if r.is_primary), None)

    # If no primary race, use the nearest upcoming race
    if not primary_race:
        upcoming = [r for r in race_responses if r.days_until >= 0]
        if upcoming:
            primary_race = min(upcoming, key=lambda r: r.days_until)

    return RacesListResponse(races=race_responses, primary_race=primary_race)


@router.get("/upcoming", response_model=Optional[RaceResponse])
async def get_upcoming_race(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the primary or nearest upcoming race for D-day display."""
    today = date.today()

    # First try to get primary race
    query = select(Race).where(
        and_(
            Race.user_id == current_user.id,
            Race.is_primary == True,
            Race.is_completed == False,
            Race.race_date >= today,
        )
    )
    result = await db.execute(query)
    race = result.scalar_one_or_none()

    if race:
        return race_to_response(race)

    # If no primary, get the nearest upcoming race
    query = (
        select(Race)
        .where(
            and_(
                Race.user_id == current_user.id,
                Race.is_completed == False,
                Race.race_date >= today,
            )
        )
        .order_by(Race.race_date)
        .limit(1)
    )
    result = await db.execute(query)
    race = result.scalar_one_or_none()

    if race:
        return race_to_response(race)

    return None


@router.get("/garmin/predictions", response_model=GarminRacePredictionsResponse)
async def get_garmin_race_predictions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get race predictions from Garmin based on VO2Max.

    Returns predicted race times for 5K, 10K, Half Marathon, and Marathon.
    """
    # Get Garmin session for user
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    garmin_session = result.scalar_one_or_none()

    if not garmin_session or not garmin_session.session_data:
        raise HTTPException(
            status_code=400,
            detail="Garmin account not connected. Please connect your Garmin account first.",
        )

    try:
        adapter = GarminConnectAdapter()
        adapter.restore_session(garmin_session.session_data)

        predictions_data = adapter.get_race_predictions()

        # Distance mapping
        distance_map = {
            "5K": 5.0,
            "10K": 10.0,
            "Half Marathon": 21.0975,
            "Marathon": 42.195,
        }

        predictions = []
        vo2_max = None
        last_updated = None

        if predictions_data:
            # Extract VO2Max if available
            vo2_max = predictions_data.get("vo2Max")
            last_updated = predictions_data.get("calendarDate")

            # Parse race predictions
            race_times = predictions_data.get("raceTimes", {})

            for distance_name, distance_km in distance_map.items():
                # Garmin API uses different keys for each distance
                key_map = {
                    "5K": "time5K",
                    "10K": "time10K",
                    "Half Marathon": "timeHalfMarathon",
                    "Marathon": "timeMarathon",
                }

                time_seconds = race_times.get(key_map.get(distance_name, ""))

                if time_seconds:
                    # Format time as HH:MM:SS
                    hours = int(time_seconds // 3600)
                    minutes = int((time_seconds % 3600) // 60)
                    seconds = int(time_seconds % 60)

                    if hours > 0:
                        time_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        time_formatted = f"{minutes}:{seconds:02d}"

                    # Calculate pace per km
                    pace_seconds = time_seconds / distance_km
                    pace_min = int(pace_seconds // 60)
                    pace_sec = int(pace_seconds % 60)
                    pace_per_km = f"{pace_min}:{pace_sec:02d}"

                    predictions.append(
                        GarminRacePrediction(
                            distance=distance_name,
                            distance_km=distance_km,
                            predicted_time_seconds=int(time_seconds),
                            predicted_time_formatted=time_formatted,
                            pace_per_km=pace_per_km,
                        )
                    )

        return GarminRacePredictionsResponse(
            predictions=predictions,
            vo2_max=vo2_max,
            last_updated=last_updated,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Garmin race predictions: {str(e)}",
        )


@router.post("/garmin/import", response_model=RaceResponse, status_code=status.HTTP_201_CREATED)
async def import_race_from_garmin(
    distance: str,  # "5K", "10K", "Half Marathon", "Marathon"
    race_date: date,
    name: str,
    location: Optional[str] = None,
    is_primary: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a race with Garmin's predicted goal time.

    Creates a new race entry using Garmin's race prediction as the goal time.
    """
    # Get Garmin session for user
    result = await db.execute(
        select(GarminSession).where(GarminSession.user_id == current_user.id)
    )
    garmin_session = result.scalar_one_or_none()

    if not garmin_session or not garmin_session.session_data:
        raise HTTPException(
            status_code=400,
            detail="Garmin account not connected. Please connect your Garmin account first.",
        )

    # Distance mapping
    distance_map = {
        "5K": (5.0, "5K"),
        "10K": (10.0, "10K"),
        "Half Marathon": (21.0975, "하프마라톤"),
        "Marathon": (42.195, "풀마라톤"),
    }

    if distance not in distance_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid distance. Must be one of: {', '.join(distance_map.keys())}",
        )

    distance_km, distance_label = distance_map[distance]

    try:
        adapter = GarminConnectAdapter()
        adapter.restore_session(garmin_session.session_data)

        predictions_data = adapter.get_race_predictions()
        goal_time_seconds = None

        if predictions_data:
            race_times = predictions_data.get("raceTimes", {})
            key_map = {
                "5K": "time5K",
                "10K": "time10K",
                "Half Marathon": "timeHalfMarathon",
                "Marathon": "timeMarathon",
            }
            goal_time_seconds = race_times.get(key_map.get(distance))
            if goal_time_seconds:
                goal_time_seconds = int(goal_time_seconds)

    except Exception:
        # If Garmin fetch fails, continue without goal time
        goal_time_seconds = None

    # If setting as primary, unset other primary races
    if is_primary:
        existing_primary = await db.execute(
            select(Race).where(
                and_(Race.user_id == current_user.id, Race.is_primary == True)
            )
        )
        for existing in existing_primary.scalars():
            existing.is_primary = False

    race = Race(
        user_id=current_user.id,
        name=name,
        race_date=race_date,
        distance_km=distance_km,
        distance_label=distance_label,
        location=location,
        goal_time_seconds=goal_time_seconds,
        goal_description="Garmin VO2Max 기반 예측 기록" if goal_time_seconds else None,
        is_primary=is_primary,
    )

    db.add(race)
    await db.commit()
    await db.refresh(race)

    return race_to_response(race)


@router.get("/{race_id}", response_model=RaceResponse)
async def get_race(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific race."""
    query = select(Race).where(
        and_(Race.id == race_id, Race.user_id == current_user.id)
    )
    result = await db.execute(query)
    race = result.scalar_one_or_none()

    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    return race_to_response(race)


@router.post("", response_model=RaceResponse, status_code=status.HTTP_201_CREATED)
async def create_race(
    race_data: RaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new race."""
    # If setting as primary, unset other primary races
    if race_data.is_primary:
        await db.execute(
            select(Race)
            .where(and_(Race.user_id == current_user.id, Race.is_primary == True))
        )
        existing_primary = await db.execute(
            select(Race).where(
                and_(Race.user_id == current_user.id, Race.is_primary == True)
            )
        )
        for existing in existing_primary.scalars():
            existing.is_primary = False

    race = Race(
        user_id=current_user.id,
        name=race_data.name,
        race_date=race_data.race_date,
        distance_km=race_data.distance_km,
        distance_label=race_data.distance_label,
        location=race_data.location,
        goal_time_seconds=race_data.goal_time_seconds,
        goal_description=race_data.goal_description,
        is_primary=race_data.is_primary,
    )

    db.add(race)
    await db.commit()
    await db.refresh(race)

    return race_to_response(race)


@router.patch("/{race_id}", response_model=RaceResponse)
async def update_race(
    race_id: int,
    race_data: RaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a race."""
    query = select(Race).where(
        and_(Race.id == race_id, Race.user_id == current_user.id)
    )
    result = await db.execute(query)
    race = result.scalar_one_or_none()

    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    # If setting as primary, unset other primary races
    if race_data.is_primary:
        existing_primary = await db.execute(
            select(Race).where(
                and_(
                    Race.user_id == current_user.id,
                    Race.is_primary == True,
                    Race.id != race_id,
                )
            )
        )
        for existing in existing_primary.scalars():
            existing.is_primary = False

    # Update fields
    update_data = race_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(race, field, value)

    await db.commit()
    await db.refresh(race)

    return race_to_response(race)


@router.delete("/{race_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_race(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a race."""
    query = select(Race).where(
        and_(Race.id == race_id, Race.user_id == current_user.id)
    )
    result = await db.execute(query)
    race = result.scalar_one_or_none()

    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    await db.delete(race)
    await db.commit()


@router.post("/{race_id}/set-primary", response_model=RaceResponse)
async def set_primary_race(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a race as the primary race for D-day display."""
    # Unset all other primary races
    existing_primary = await db.execute(
        select(Race).where(
            and_(Race.user_id == current_user.id, Race.is_primary == True)
        )
    )
    for existing in existing_primary.scalars():
        existing.is_primary = False

    # Set this race as primary
    query = select(Race).where(
        and_(Race.id == race_id, Race.user_id == current_user.id)
    )
    result = await db.execute(query)
    race = result.scalar_one_or_none()

    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    race.is_primary = True
    await db.commit()
    await db.refresh(race)

    return race_to_response(race)
