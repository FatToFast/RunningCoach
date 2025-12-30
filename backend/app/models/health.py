"""Health-related models (sleep, heart rate, metrics, etc.)."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Sleep(BaseModel):
    """Sleep record from Garmin."""

    __tablename__ = "sleep"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_sleep_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, index=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Sleep stages as JSON
    stages: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Reference to raw data
    raw_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("garmin_raw_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="sleep_records")

    def __repr__(self) -> str:
        return f"<Sleep(user_id={self.user_id}, date={self.date})>"


class HRRecord(BaseModel):
    """Heart rate record from Garmin (daily summary)."""

    __tablename__ = "hr_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resting_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # HR samples as JSON (time series within the period)
    samples: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Reference to raw data
    raw_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("garmin_raw_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="hr_records")

    def __repr__(self) -> str:
        return f"<HRRecord(user_id={self.user_id}, start={self.start_time})>"


class HealthMetric(BaseModel):
    """Generic health/fitness metrics from Garmin (Body Battery, Stress, HRV, etc.)."""

    __tablename__ = "health_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    metric_type: Mapped[str] = mapped_column(String(50), index=True)
    metric_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Additional payload as JSON
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Reference to raw data
    raw_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("garmin_raw_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="health_metrics")

    def __repr__(self) -> str:
        return f"<HealthMetric(user_id={self.user_id}, type={self.metric_type})>"


class HeartRateZone(BaseModel):
    """Daily heart rate zone time distribution."""

    __tablename__ = "heart_rate_zones"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_heart_rate_zone_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, index=True)
    resting_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Time spent in each zone (seconds)
    zone1_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zone2_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zone3_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zone4_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zone5_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="heart_rate_zones")

    def __repr__(self) -> str:
        return f"<HeartRateZone(user_id={self.user_id}, date={self.date})>"


class BodyComposition(BaseModel):
    """Body composition measurements (weight, body fat, etc.)."""

    __tablename__ = "body_compositions"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_body_composition_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, index=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_fat_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    muscle_mass_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bmi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="body_compositions")

    def __repr__(self) -> str:
        return f"<BodyComposition(user_id={self.user_id}, date={self.date})>"


class FitnessMetricDaily(BaseModel):
    """Daily fitness metrics (CTL, ATL, TSB)."""

    __tablename__ = "fitness_metrics_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_fitness_metrics_daily_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, index=True)

    # Chronic Training Load (fitness)
    ctl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Acute Training Load (fatigue)
    atl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Training Stress Balance (form)
    tsb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="fitness_metrics_daily")

    def __repr__(self) -> str:
        return f"<FitnessMetricDaily(user_id={self.user_id}, date={self.date})>"
