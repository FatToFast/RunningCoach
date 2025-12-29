"""Activity models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.garmin import GarminRawFile


class Activity(BaseModel):
    """Running/workout activity from Garmin."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    garmin_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    # Basic info
    activity_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Duration and distance
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Heart rate
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pace (seconds per km)
    avg_pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Elevation
    elevation_gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elevation_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Cadence
    avg_cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Reference to raw data
    raw_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("garmin_raw_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="activities")
    samples: Mapped[list["ActivitySample"]] = relationship(
        "ActivitySample",
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    raw_file: Mapped[Optional["GarminRawFile"]] = relationship(
        "GarminRawFile",
        back_populates="activity",
        uselist=False,
    )
    metrics: Mapped[Optional["ActivityMetric"]] = relationship(
        "ActivityMetric",
        back_populates="activity",
        uselist=False,
    )
    strava_map: Mapped[Optional["StravaActivityMap"]] = relationship(
        "StravaActivityMap",
        back_populates="activity",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Activity(id={self.id}, type={self.activity_type}, date={self.start_time})>"


class ActivitySample(BaseModel):
    """Time-series sample data for an activity (from FIT parsing)."""

    __tablename__ = "activity_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        index=True,
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Metrics
    hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # GPS
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    activity: Mapped["Activity"] = relationship("Activity", back_populates="samples")

    def __repr__(self) -> str:
        return f"<ActivitySample(activity_id={self.activity_id}, ts={self.timestamp})>"


class ActivityMetric(BaseModel):
    """Derived metrics for an activity (TRIMP, TSS, etc.)."""

    __tablename__ = "activity_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    trimp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    training_effect: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vo2max_est: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    efficiency_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    activity: Mapped["Activity"] = relationship("Activity", back_populates="metrics")

    def __repr__(self) -> str:
        return f"<ActivityMetric(activity_id={self.activity_id})>"


# Forward reference for Strava mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.strava import StravaActivityMap
