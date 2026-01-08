"""Gear (shoes/equipment) endpoints."""

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.activity import Activity
from app.models.gear import ActivityGear, Gear, GearStatus, GearType
from app.models.user import User

router = APIRouter()
settings = get_settings()

# -------------------------------------------------------------------------
# Configuration Constants
# -------------------------------------------------------------------------

# Percentage threshold for "near retirement" warning
RETIREMENT_WARNING_THRESHOLD = 80  # 80%

# Valid enum values for validation
VALID_GEAR_TYPES = {e.value for e in GearType}
VALID_GEAR_STATUSES = {e.value for e in GearStatus}


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class GearSummaryResponse(BaseModel):
    """Gear summary for list view."""

    id: int
    name: str
    brand: str | None
    gear_type: str
    status: str
    total_distance_meters: float
    max_distance_meters: float | None
    activity_count: int
    usage_percentage: float | None

    class Config:
        from_attributes = True


class GearListResponse(BaseModel):
    """Gear list response."""

    items: list[GearSummaryResponse]
    total: int


class GearDetailResponse(BaseModel):
    """Full gear detail."""

    id: int
    garmin_uuid: str | None
    name: str
    brand: str | None
    model: str | None
    gear_type: str
    status: str
    purchase_date: date | None
    retired_date: date | None
    initial_distance_meters: float
    total_distance_meters: float
    max_distance_meters: float | None
    activity_count: int
    usage_percentage: float | None
    notes: str | None
    image_url: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GearStatsResponse(BaseModel):
    """Gear statistics."""

    total_gears: int
    active_gears: int
    retired_gears: int
    gears_near_retirement: list[GearSummaryResponse]


class GearCreateRequest(BaseModel):
    """Request to create gear."""

    name: str = Field(..., min_length=1, max_length=100)
    brand: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    gear_type: str = Field(default=GearType.RUNNING_SHOES.value)
    purchase_date: date | None = None
    initial_distance_meters: float = Field(default=0.0, ge=0)
    max_distance_meters: float | None = Field(default=None, ge=0)  # Uses settings.gear_default_max_distance_meters if None
    notes: str | None = None

    @field_validator("gear_type")
    @classmethod
    def validate_gear_type(cls, v: str) -> str:
        if v not in VALID_GEAR_TYPES:
            raise ValueError(f"Invalid gear_type. Must be one of: {', '.join(VALID_GEAR_TYPES)}")
        return v


class GearUpdateRequest(BaseModel):
    """Request to update gear."""

    name: str | None = Field(None, min_length=1, max_length=100)
    brand: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    gear_type: str | None = None
    status: str | None = None
    purchase_date: date | None = None
    initial_distance_meters: float | None = Field(None, ge=0)
    max_distance_meters: float | None = Field(None, ge=0)
    notes: str | None = None

    @field_validator("gear_type")
    @classmethod
    def validate_gear_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_GEAR_TYPES:
            raise ValueError(f"Invalid gear_type. Must be one of: {', '.join(VALID_GEAR_TYPES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_GEAR_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(VALID_GEAR_STATUSES)}")
        return v


class ActivityGearResponse(BaseModel):
    """Activity gear link."""

    gear_id: int
    gear_name: str
    gear_type: str


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------


async def get_gear_stats_batch(
    gear_ids: list[int], db: AsyncSession
) -> dict[int, tuple[float, int]]:
    """Get activity distance and count for multiple gears in a single query.

    Args:
        gear_ids: List of gear IDs to fetch stats for.
        db: Database session.

    Returns:
        Dict mapping gear_id -> (activity_distance, activity_count)
    """
    if not gear_ids:
        return {}

    # Single query to get both sum and count per gear
    result = await db.execute(
        select(
            ActivityGear.gear_id,
            func.coalesce(func.sum(Activity.distance_meters), 0).label("total_distance"),
            func.count(ActivityGear.id).label("activity_count"),
        )
        .join(Activity, ActivityGear.activity_id == Activity.id)
        .where(ActivityGear.gear_id.in_(gear_ids))
        .group_by(ActivityGear.gear_id)
    )

    stats: dict[int, tuple[float, int]] = {gid: (0.0, 0) for gid in gear_ids}
    for row in result.all():
        stats[row.gear_id] = (float(row.total_distance), row.activity_count)

    return stats


def build_gear_summary(
    gear: Gear, activity_distance: float, activity_count: int
) -> GearSummaryResponse:
    """Build gear summary from pre-fetched stats."""
    total_distance = gear.initial_distance_meters + activity_distance
    usage_pct = None
    if gear.max_distance_meters and gear.max_distance_meters > 0:
        usage_pct = round((total_distance / gear.max_distance_meters) * 100, 1)

    # Use Garmin activity count if it's larger than local activity links
    garmin_count = gear.garmin_activity_count or 0
    final_activity_count = max(activity_count, garmin_count)

    return GearSummaryResponse(
        id=gear.id,
        name=gear.name,
        brand=gear.brand,
        gear_type=gear.gear_type,
        status=gear.status,
        total_distance_meters=total_distance,
        max_distance_meters=gear.max_distance_meters,
        activity_count=final_activity_count,
        usage_percentage=usage_pct,
    )


async def get_gear_summary(gear: Gear, db: AsyncSession) -> GearSummaryResponse:
    """Build gear summary with calculated fields (single gear)."""
    stats = await get_gear_stats_batch([gear.id], db)
    activity_distance, activity_count = stats.get(gear.id, (0.0, 0))
    return build_gear_summary(gear, activity_distance, activity_count)


async def get_gear_detail(gear: Gear, db: AsyncSession) -> GearDetailResponse:
    """Build gear detail with calculated fields."""
    stats = await get_gear_stats_batch([gear.id], db)
    activity_distance, activity_count = stats.get(gear.id, (0.0, 0))

    total_distance = gear.initial_distance_meters + activity_distance
    usage_pct = None
    if gear.max_distance_meters and gear.max_distance_meters > 0:
        usage_pct = round((total_distance / gear.max_distance_meters) * 100, 1)

    # Use Garmin activity count if it's larger than local activity links
    garmin_count = gear.garmin_activity_count or 0
    final_activity_count = max(activity_count, garmin_count)

    return GearDetailResponse(
        id=gear.id,
        garmin_uuid=gear.garmin_uuid,
        name=gear.name,
        brand=gear.brand,
        model=gear.model,
        gear_type=gear.gear_type,
        status=gear.status,
        purchase_date=gear.purchase_date,
        retired_date=gear.retired_date,
        initial_distance_meters=gear.initial_distance_meters,
        total_distance_meters=total_distance,
        max_distance_meters=gear.max_distance_meters,
        activity_count=final_activity_count,
        usage_percentage=usage_pct,
        notes=gear.notes,
        image_url=gear.image_url,
        created_at=gear.created_at,
        updated_at=gear.updated_at,
    )


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("", response_model=GearListResponse)
async def list_gear(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: active, retired, all"),
    gear_type: str | None = Query(None, description="Filter by gear type"),
) -> GearListResponse:
    """List all gear for the current user.

    Args:
        current_user: Authenticated user.
        db: Database session.
        status_filter: Optional status filter.
        gear_type: Optional gear type filter.

    Returns:
        List of gear.
    """
    query = select(Gear).where(Gear.user_id == current_user.id)

    if status_filter and status_filter != "all":
        query = query.where(Gear.status == status_filter)

    if gear_type:
        query = query.where(Gear.gear_type == gear_type)

    query = query.order_by(Gear.status.asc(), Gear.name.asc())

    result = await db.execute(query)
    gears = result.scalars().all()

    # Batch fetch stats for all gears in a single query (fixes N+1)
    gear_ids = [g.id for g in gears]
    stats = await get_gear_stats_batch(gear_ids, db)

    items = []
    for gear in gears:
        activity_distance, activity_count = stats.get(gear.id, (0.0, 0))
        summary = build_gear_summary(gear, activity_distance, activity_count)
        items.append(summary)

    return GearListResponse(items=items, total=len(items))


@router.get("/stats", response_model=GearStatsResponse)
async def get_gear_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GearStatsResponse:
    """Get gear statistics for dashboard.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Gear statistics.
    """
    # Get all gears
    result = await db.execute(
        select(Gear).where(Gear.user_id == current_user.id)
    )
    gears = result.scalars().all()

    total = len(gears)
    active_gears = [g for g in gears if g.status == GearStatus.ACTIVE.value]
    retired = sum(1 for g in gears if g.status == GearStatus.RETIRED.value)

    # Batch fetch stats for all active gears (fixes N+1)
    active_gear_ids = [g.id for g in active_gears]
    stats = await get_gear_stats_batch(active_gear_ids, db)

    # Find gears near retirement (>= RETIREMENT_WARNING_THRESHOLD% usage)
    near_retirement = []
    for gear in active_gears:
        activity_distance, activity_count = stats.get(gear.id, (0.0, 0))
        summary = build_gear_summary(gear, activity_distance, activity_count)
        if summary.usage_percentage and summary.usage_percentage >= RETIREMENT_WARNING_THRESHOLD:
            near_retirement.append(summary)

    # Sort by usage percentage descending
    near_retirement.sort(key=lambda x: x.usage_percentage or 0, reverse=True)

    return GearStatsResponse(
        total_gears=total,
        active_gears=len(active_gears),
        retired_gears=retired,
        gears_near_retirement=near_retirement,
    )


@router.post("/sync/garmin")
async def sync_gear_from_garmin(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sync gear from Garmin Connect.

    Fetches the user's gear list from Garmin and creates/updates local records.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Sync summary with counts.
    """
    from app.services.sync_service import create_sync_service

    sync_service = await create_sync_service(db, current_user)
    if not sync_service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin session not found or expired. Please reconnect to Garmin.",
        )

    from app.services.sync_service import SyncResult

    result = SyncResult("gear")
    await sync_service._sync_gear(result)

    return {
        "synced": result.items_created,
        "updated": result.items_updated,
        "message": f"Synced {result.items_created} new gear, updated {result.items_updated}",
    }


@router.get("/{gear_id}", response_model=GearDetailResponse)
async def get_gear(
    gear_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GearDetailResponse:
    """Get gear details.

    Args:
        gear_id: Gear ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Gear details.
    """
    result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    gear = result.scalar_one_or_none()

    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    return await get_gear_detail(gear, db)


@router.post("", response_model=GearDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_gear(
    data: GearCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GearDetailResponse:
    """Create new gear.

    Args:
        data: Gear creation data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created gear.
    """
    gear = Gear(
        user_id=current_user.id,
        name=data.name,
        brand=data.brand,
        model=data.model,
        gear_type=data.gear_type,
        purchase_date=data.purchase_date,
        initial_distance_meters=data.initial_distance_meters,
        max_distance_meters=data.max_distance_meters if data.max_distance_meters is not None else settings.gear_default_max_distance_meters,
        notes=data.notes,
    )

    db.add(gear)
    await db.commit()
    await db.refresh(gear)

    return await get_gear_detail(gear, db)


@router.patch("/{gear_id}", response_model=GearDetailResponse)
async def update_gear(
    gear_id: int,
    data: GearUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GearDetailResponse:
    """Update gear.

    Args:
        gear_id: Gear ID.
        data: Update data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated gear.
    """
    result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    gear = result.scalar_one_or_none()

    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)

    # Handle status changes with retired_date synchronization
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == GearStatus.RETIRED.value and gear.status != GearStatus.RETIRED.value:
            # Transitioning to retired: set retired_date if not already set
            if gear.retired_date is None:
                gear.retired_date = date.today()
        elif new_status == GearStatus.ACTIVE.value and gear.status == GearStatus.RETIRED.value:
            # Reactivating from retired: clear retired_date
            gear.retired_date = None

    for field, value in update_data.items():
        setattr(gear, field, value)

    await db.commit()
    await db.refresh(gear)

    return await get_gear_detail(gear, db)


@router.post("/{gear_id}/retire", response_model=GearDetailResponse)
async def retire_gear(
    gear_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> GearDetailResponse:
    """Retire gear (mark as no longer in use).

    Args:
        gear_id: Gear ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated gear.
    """
    result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    gear = result.scalar_one_or_none()

    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    gear.status = GearStatus.RETIRED.value
    gear.retired_date = date.today()

    await db.commit()
    await db.refresh(gear)

    return await get_gear_detail(gear, db)


@router.delete("/{gear_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gear(
    gear_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete gear.

    Args:
        gear_id: Gear ID.
        current_user: Authenticated user.
        db: Database session.
    """
    result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    gear = result.scalar_one_or_none()

    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    await db.delete(gear)
    await db.commit()


# -------------------------------------------------------------------------
# Activity-Gear Linking
# -------------------------------------------------------------------------


@router.post("/{gear_id}/activities/{activity_id}", status_code=status.HTTP_201_CREATED)
async def link_gear_to_activity(
    gear_id: int,
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Link gear to an activity.

    Args:
        gear_id: Gear ID.
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Success message.
    """
    # Verify gear ownership
    gear_result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    gear = gear_result.scalar_one_or_none()
    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    # Verify activity ownership
    activity_result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = activity_result.scalar_one_or_none()
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Check if link already exists
    existing = await db.execute(
        select(ActivityGear).where(
            ActivityGear.gear_id == gear_id,
            ActivityGear.activity_id == activity_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Gear already linked to this activity",
        )

    link = ActivityGear(activity_id=activity_id, gear_id=gear_id)
    db.add(link)
    await db.commit()

    return {"message": "Gear linked to activity"}


@router.delete("/{gear_id}/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_gear_from_activity(
    gear_id: int,
    activity_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unlink gear from an activity.

    Args:
        gear_id: Gear ID.
        activity_id: Activity ID.
        current_user: Authenticated user.
        db: Database session.
    """
    # Verify gear ownership
    gear_result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    if not gear_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    # Find and delete link
    link_result = await db.execute(
        select(ActivityGear).where(
            ActivityGear.gear_id == gear_id,
            ActivityGear.activity_id == activity_id,
        )
    )
    link = link_result.scalar_one_or_none()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    await db.delete(link)
    await db.commit()


@router.get("/{gear_id}/activities", response_model=list[int])
async def get_gear_activities(
    gear_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> list[int]:
    """Get activity IDs linked to gear, ordered by activity start time (newest first).

    Args:
        gear_id: Gear ID.
        current_user: Authenticated user.
        db: Database session.
        limit: Max results (default: 50, max: 100).
        offset: Number of results to skip for pagination.

    Returns:
        List of activity IDs.
    """
    # Verify gear ownership
    gear_result = await db.execute(
        select(Gear).where(Gear.id == gear_id, Gear.user_id == current_user.id)
    )
    if not gear_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    # Join with Activity to enable sorting by start_time
    result = await db.execute(
        select(ActivityGear.activity_id)
        .join(Activity, ActivityGear.activity_id == Activity.id)
        .where(ActivityGear.gear_id == gear_id)
        .order_by(Activity.start_time.desc())
        .offset(offset)
        .limit(limit)
    )
    return [row[0] for row in result.all()]
