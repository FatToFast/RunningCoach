"""Gear (shoes/equipment) models."""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.activity import Activity


class GearType(str, Enum):
    """Type of gear."""

    RUNNING_SHOES = "running_shoes"
    CYCLING_SHOES = "cycling_shoes"
    BIKE = "bike"
    OTHER = "other"


class GearStatus(str, Enum):
    """Status of gear."""

    ACTIVE = "active"
    RETIRED = "retired"


class Gear(BaseModel):
    """Gear (shoes, bikes, etc.) for tracking usage and mileage."""

    __tablename__ = "gears"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Garmin sync
    garmin_uuid: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gear_type: Mapped[str] = mapped_column(
        String(50),
        default=GearType.RUNNING_SHOES.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=GearStatus.ACTIVE.value,
        index=True,
    )

    # Dates
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retired_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Distance tracking
    initial_distance_meters: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    max_distance_meters: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Recommended max distance before retirement (default 800km for shoes)",
    )

    # Notes and image
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="gears")
    activity_links: Mapped[list["ActivityGear"]] = relationship(
        "ActivityGear",
        back_populates="gear",
        cascade="all, delete-orphan",
    )

    @property
    def total_distance_meters(self) -> float:
        """Calculate total distance including initial and activity distances."""
        activity_distance = sum(
            link.activity.distance_meters or 0
            for link in self.activity_links
            if link.activity.distance_meters
        )
        return self.initial_distance_meters + activity_distance

    @property
    def activity_count(self) -> int:
        """Count of activities using this gear."""
        return len(self.activity_links)

    @property
    def usage_percentage(self) -> Optional[float]:
        """Percentage of recommended max distance used."""
        if self.max_distance_meters is None or self.max_distance_meters == 0:
            return None
        return round((self.total_distance_meters / self.max_distance_meters) * 100, 1)

    def __repr__(self) -> str:
        return f"<Gear(id={self.id}, name={self.name}, type={self.gear_type})>"


class ActivityGear(BaseModel):
    """Association table linking activities to gear."""

    __tablename__ = "activity_gears"
    __table_args__ = (
        UniqueConstraint("activity_id", "gear_id", name="uq_activity_gear"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        index=True,
    )
    gear_id: Mapped[int] = mapped_column(
        ForeignKey("gears.id", ondelete="CASCADE"),
        index=True,
    )

    # Relationships
    activity: Mapped["Activity"] = relationship("Activity", back_populates="gear_links")
    gear: Mapped["Gear"] = relationship("Gear", back_populates="activity_links")

    def __repr__(self) -> str:
        return f"<ActivityGear(activity_id={self.activity_id}, gear_id={self.gear_id})>"
