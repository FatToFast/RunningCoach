"""Activity models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, deferred

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.garmin import GarminRawFile
    from app.models.gear import ActivityGear


class Activity(BaseModel):
    """Running/workout activity from Garmin."""

    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("user_id", "garmin_id", name="uq_activities_user_garmin_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    # garmin_id is unique per user (not globally) - see UniqueConstraint below
    garmin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # Basic info
    activity_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # User notes/memo from Garmin
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    start_time_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Duration and distance
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    elapsed_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Heart rate
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pace (seconds per km)
    avg_pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    best_pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Elevation
    elevation_gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elevation_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Cadence
    avg_cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Power metrics (Stryd, etc.)
    avg_power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    normalized_power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Training Effect
    training_effect_aerobic: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    training_effect_anaerobic: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vo2max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Training metrics (from FIT file)
    training_stress_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intensity_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Running dynamics (from FIT file)
    avg_ground_contact_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_vertical_oscillation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_stride_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Stryd metrics (from FIT file - Stryd power meter)
    avg_form_power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_leg_spring_stiffness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kN/m

    # FIT file info
    # fit_file_path: Path to FIT file on disk. None if file was deleted after parse.
    fit_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # fit_file_hash: SHA-256 hash of FIT file. Preserved even after file deletion for verification.
    fit_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Database storage for FIT file (cached copy)
    fit_file_content: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True, deferred=True,
        comment="Compressed FIT file content (cached copy)"
    )
    fit_file_size: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Original FIT file size in bytes"
    )
    # has_fit_file: True if FIT file was successfully parsed (data is in ActivitySample/Lap/Metric).
    #   Note: This does NOT mean the file exists on disk. Check fit_file_path for file existence.
    #   Semantic: "FIT data was successfully ingested" not "FIT file exists".
    has_fit_file: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sensor info (detected from FIT file device_info)
    has_stryd: Mapped[bool] = mapped_column(Boolean, default=False)
    has_external_hr: Mapped[bool] = mapped_column(Boolean, default=False)

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
    laps: Mapped[list["ActivityLap"]] = relationship(
        "ActivityLap",
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
    gear_links: Mapped[list["ActivityGear"]] = relationship(
        "ActivityGear",
        back_populates="activity",
        cascade="all, delete-orphan",
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
    elapsed_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Heart rate (both naming conventions for compatibility)
    hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # alias for heart_rate
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Speed/Pace
    pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # m/s

    # Cadence
    cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Power
    power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # GPS
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Distance
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Running dynamics
    ground_contact_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vertical_oscillation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stride_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    activity: Mapped["Activity"] = relationship("Activity", back_populates="samples")

    def __repr__(self) -> str:
        return f"<ActivitySample(activity_id={self.activity_id}, ts={self.timestamp})>"


class ActivityLap(BaseModel):
    """Lap data for an activity (from FIT parsing)."""

    __tablename__ = "activity_laps"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        index=True,
    )

    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Duration and distance
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Heart rate
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Cadence
    avg_cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pace (seconds per km)
    avg_pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Elevation
    total_ascent_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_descent_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Calories
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    activity: Mapped["Activity"] = relationship("Activity", back_populates="laps")

    def __repr__(self) -> str:
        return f"<ActivityLap(activity_id={self.activity_id}, lap={self.lap_number})>"


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
