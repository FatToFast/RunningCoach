"""Race API endpoints for managing race events."""

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.race import Race
from app.models.user import User
from app.models.garmin import GarminSession
from app.adapters.garmin_adapter import GarminConnectAdapter, GarminAuthError, GarminAPIError

logger = logging.getLogger(__name__)

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
    # Fields for creating completed races (e.g., from personal records)
    is_completed: bool = False
    result_time_seconds: Optional[int] = None
    result_notes: Optional[str] = None


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


class GarminEventResponse(BaseModel):
    """Schema for Garmin event response."""

    event_date: str
    event_type: str
    name: str
    location: Optional[str] = None
    distance_km: Optional[float] = None
    distance_label: Optional[str] = None
    notes: Optional[str] = None
    raw_data: dict  # Original event data from Garmin


class GarminEventsResponse(BaseModel):
    """Schema for Garmin events list response."""

    events: list[GarminEventResponse]
    total: int


@router.get("/garmin/events/debug")
async def get_garmin_events_debug(
    target_date: date = Query(..., description="Date to check"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint to see raw Garmin event data structure.
    
    Returns raw response from Garmin API for a specific date.
    """
    # Get Garmin session
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

        # Get events for single date
        loop = asyncio.get_event_loop()
        raw_data = await loop.run_in_executor(
            None,
            lambda: adapter.get_all_day_events(target_date),
        )

        return {
            "date": target_date.isoformat(),
            "raw_response": raw_data,
            "type": type(raw_data).__name__,
            "is_dict": isinstance(raw_data, dict),
            "is_list": isinstance(raw_data, list),
            "keys": list(raw_data.keys()) if isinstance(raw_data, dict) else None,
            "length": len(raw_data) if isinstance(raw_data, (dict, list)) else None,
        }

    except Exception as e:
        logger.exception("Failed to get debug events")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch debug events: {str(e)}",
        ) from e


@router.get("/garmin/events", response_model=GarminEventsResponse)
async def get_garmin_events(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get events from Garmin Connect Event Dashboard.

    Fetches all-day events from Garmin Connect for the specified date range.
    Events may include races, workouts, and other scheduled activities.
    
    If the date range exceeds 90 days, it will be automatically split into
    multiple 90-day chunks and all events will be merged.

    Args:
        start_date: Start date for event search.
        end_date: End date for event search.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of Garmin events that may include race information.
    """
    # If range exceeds 90 days, split into multiple requests
    total_days = (end_date - start_date).days
    if total_days <= 90:
        # Single request
        date_ranges = [(start_date, end_date)]
    else:
        # Split into 90-day chunks
        date_ranges = []
        current = start_date
        from datetime import timedelta
        while current <= end_date:
            chunk_end = min(current + timedelta(days=89), end_date)  # 90-day chunks
            date_ranges.append((current, chunk_end))
            current = chunk_end + timedelta(days=1)

    # Get Garmin session
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

        # Get events for all date ranges and merge them
        loop = asyncio.get_event_loop()
        all_raw_events = []
        
        for range_start, range_end in date_ranges:
            logger.info(f"Fetching Garmin events for range {range_start} to {range_end}")
            chunk_events = await loop.run_in_executor(
                None,
                lambda s=range_start, e=range_end: adapter.get_events_in_range(s, e),
            )
            all_raw_events.extend(chunk_events)
            logger.info(f"Retrieved {len(chunk_events)} events from range {range_start} to {range_end}")

        # Remove duplicates based on event_date + name (or other unique identifier)
        seen_events = set()
        unique_events = []
        for event in all_raw_events:
            if not isinstance(event, dict):
                continue
            # Create a unique key for deduplication
            event_date = event.get("event_date") or event.get("date") or "unknown"
            event_name = event.get("eventName") or event.get("name") or event.get("title") or "unknown"
            event_key = f"{event_date}|{event_name}"
            if event_key not in seen_events:
                seen_events.add(event_key)
                unique_events.append(event)
        
        raw_events = unique_events
        logger.info(f"Retrieved total {len(raw_events)} unique events from Garmin for range {start_date} to {end_date} (from {len(date_ranges)} chunks)")
        
        # Log details about what was retrieved
        if raw_events:
            dates_with_events = set()
            event_names = []
            for event in raw_events[:20]:  # First 20 events
                if isinstance(event, dict):
                    event_date = event.get("event_date") or event.get("date") or "unknown"
                    event_name = event.get("eventName") or event.get("name") or event.get("title") or "Unknown"
                    dates_with_events.add(event_date)
                    event_names.append(f"{event_name} ({event_date})")
            logger.info(f"Events found on {len(dates_with_events)} different dates")
            logger.info(f"Sample event names: {', '.join(event_names[:10])}")
        else:
            logger.warning(f"No events returned for range {start_date} to {end_date}")
        
        if raw_events:
            # Log sample event structure
            sample_event = raw_events[0]
            logger.info(f"Sample event structure: {list(sample_event.keys()) if isinstance(sample_event, dict) else type(sample_event)}")
            logger.info(f"Sample event data: {sample_event}")
        else:
            logger.warning(f"No events found in range {start_date} to {end_date}. This might indicate:")
            logger.warning("1. No events registered in Garmin Connect for this date range")
            logger.warning("2. API response structure is different than expected")
            logger.warning("3. Events are stored in a different key than we're checking")

        # Parse events and extract race-like information
        parsed_events: list[GarminEventResponse] = []
        for event in raw_events:
            try:
                if not isinstance(event, dict):
                    continue
                
                # Log raw event for debugging
                logger.debug(f"Parsing event: {list(event.keys())}")
                
                # Extract event information (structure may vary)
                # Try multiple possible field names
                event_date = (
                    event.get("event_date") or
                    event.get("date") or
                    event.get("calendarDate") or
                    event.get("eventDate") or
                    start_date.isoformat()
                )
                
                event_type = (
                    event.get("eventTypeName") or
                    event.get("event_type") or
                    event.get("type") or
                    event.get("eventTypeKey") or
                    "unknown"
                )
                
                name = (
                    event.get("eventName") or
                    event.get("name") or
                    event.get("title") or
                    event.get("eventTypeDesc") or
                    "Unknown Event"
                )
                
                location = (
                    event.get("locationName") or
                    event.get("location") or
                    event.get("eventLocation") or
                    None
                )
                
                # Try to extract distance information
                distance_km = (
                    event.get("distance") or
                    event.get("distanceKm") or
                    event.get("distance_km") or
                    None
                )
                if distance_km and isinstance(distance_km, str):
                    try:
                        distance_km = float(distance_km)
                    except (ValueError, TypeError):
                        distance_km = None
                
                distance_label = (
                    event.get("distanceLabel") or
                    event.get("distance_label") or
                    event.get("eventTypeDesc") or
                    None
                )
                
                # Parse distance from name or label if not explicitly set
                if distance_km is None:
                    name_lower = (name or "").lower()
                    label_lower = (distance_label or "").lower()
                    combined = f"{name_lower} {label_lower}"
                    
                    if "5k" in combined or "5k" in combined:
                        distance_km = 5.0
                        if not distance_label:
                            distance_label = "5K"
                    elif "10k" in combined or "10k" in combined:
                        distance_km = 10.0
                        if not distance_label:
                            distance_label = "10K"
                    elif "half" in combined or "하프" in combined:
                        distance_km = 21.0975
                        if not distance_label:
                            distance_label = "Half Marathon"
                    elif "marathon" in combined or "마라톤" in combined or "풀" in combined or "full" in combined:
                        distance_km = 42.195
                        if not distance_label:
                            distance_label = "Marathon"

                notes = (
                    event.get("notes") or
                    event.get("description") or
                    event.get("eventDescription") or
                    None
                )

                parsed_events.append(
                    GarminEventResponse(
                        event_date=event_date,
                        event_type=event_type,
                        name=name,
                        location=location,
                        distance_km=distance_km,
                        distance_label=distance_label,
                        notes=notes,
                        raw_data=event,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse event: {event}, error: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue

        return GarminEventsResponse(events=parsed_events, total=len(parsed_events))

    except GarminAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Garmin authentication failed: {str(e)}",
        ) from e
    except GarminAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch Garmin events: {str(e)}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error fetching Garmin events")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Garmin events: {str(e)}",
        ) from e


class ImportGarminEventsRequest(BaseModel):
    """Schema for importing selected Garmin events."""

    start_date: date
    end_date: date
    selected_event_dates: Optional[list[str]] = None  # List of event dates to import
    selected_event_names: Optional[list[str]] = None  # List of event names to import
    filter_races_only: bool = False  # Ignored if selected_event_dates is provided


@router.post("/garmin/events/import", response_model=list[RaceResponse], status_code=status.HTTP_201_CREATED)
async def import_garmin_events_as_races(
    request: ImportGarminEventsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import selected Garmin events as races.

    Fetches events from Garmin Connect Event Dashboard and creates Race entries
    for selected events. If selected_event_dates/names are provided, only those
    events will be imported. Otherwise, filters by race_keywords if filter_races_only=True.

    Args:
        request: Import request with date range and optional selection criteria.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of created races.
    """
    # Get Garmin events
    events_response = await get_garmin_events(request.start_date, request.end_date, db, current_user)
    
    created_races: list[RaceResponse] = []
    
    # Filter events based on selection
    events_to_import = []
    
    if request.selected_event_dates and request.selected_event_names:
        # User selected specific events - match by date and name
        selected_set = set(zip(request.selected_event_dates, request.selected_event_names))
        for event in events_response.events:
            if (event.event_date, event.name) in selected_set:
                events_to_import.append(event)
    elif request.filter_races_only:
        # Filter events that look like races
        race_keywords = ["marathon", "마라톤", "race", "race", "5k", "10k", "half", "하프", "풀", "풀마라톤"]
        for event in events_response.events:
            name_lower = event.name.lower()
            event_type_lower = event.event_type.lower()
            is_likely_race = (
                event.distance_km is not None
                or any(keyword in name_lower or keyword in event_type_lower for keyword in race_keywords)
            )
            if is_likely_race:
                events_to_import.append(event)
    else:
        # Import all events (not recommended but allowed)
        events_to_import = events_response.events
    
    for event in events_to_import:
        # Check if race already exists (by date and distance/name)
        event_date = date.fromisoformat(event.event_date)
        existing_query = select(Race).where(
            and_(
                Race.user_id == current_user.id,
                Race.race_date == event_date,
            )
        )
        if event.distance_km:
            existing_query = existing_query.where(Race.distance_km == event.distance_km)
        else:
            existing_query = existing_query.where(
                (Race.name.ilike(f"%{event.name}%")) | (Race.name == event.name)
            )
        
        existing_result = await db.execute(existing_query)
        existing_race = existing_result.scalar_one_or_none()
        
        if existing_race:
            logger.info(f"Race already exists for {event.name} on {event.event_date}")
            created_races.append(race_to_response(existing_race))
            continue
        
        # Create new race
        race = Race(
            user_id=current_user.id,
            name=event.name,
            race_date=event_date,
            distance_km=event.distance_km,
            distance_label=event.distance_label,
            location=event.location,
            goal_description=event.notes,
            is_primary=False,
            is_completed=event_date < date.today(),
        )
        
        db.add(race)
        await db.flush()
        await db.refresh(race)
        created_races.append(race_to_response(race))
    
    await db.commit()
    
    return created_races


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
