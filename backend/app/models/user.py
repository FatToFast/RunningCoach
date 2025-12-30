"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.garmin import GarminSession, GarminSyncState
    from app.models.activity import Activity
    from app.models.health import Sleep, HRRecord, HealthMetric, FitnessMetricDaily, HeartRateZone, BodyComposition
    from app.models.workout import Workout
    from app.models.plan import Plan
    from app.models.analytics import AnalyticsSummary
    from app.models.ai import AIConversation, AIImport
    from app.models.strava import StravaSession, StravaSyncState
    from app.models.gear import Gear
    from app.models.strength import StrengthSession


class User(BaseModel):
    """User model representing a RunningCoach user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Seoul")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Garmin 연동 최대 심박수 (Garmin Connect에서 설정된 값)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    garmin_session: Mapped[Optional["GarminSession"]] = relationship(
        "GarminSession",
        back_populates="user",
        uselist=False,
    )
    garmin_sync_states: Mapped[list["GarminSyncState"]] = relationship(
        "GarminSyncState",
        back_populates="user",
    )
    activities: Mapped[list["Activity"]] = relationship(
        "Activity",
        back_populates="user",
    )
    sleep_records: Mapped[list["Sleep"]] = relationship(
        "Sleep",
        back_populates="user",
    )
    hr_records: Mapped[list["HRRecord"]] = relationship(
        "HRRecord",
        back_populates="user",
    )
    health_metrics: Mapped[list["HealthMetric"]] = relationship(
        "HealthMetric",
        back_populates="user",
    )
    fitness_metrics_daily: Mapped[list["FitnessMetricDaily"]] = relationship(
        "FitnessMetricDaily",
        back_populates="user",
    )
    heart_rate_zones: Mapped[list["HeartRateZone"]] = relationship(
        "HeartRateZone",
        back_populates="user",
    )
    body_compositions: Mapped[list["BodyComposition"]] = relationship(
        "BodyComposition",
        back_populates="user",
    )
    workouts: Mapped[list["Workout"]] = relationship(
        "Workout",
        back_populates="user",
    )
    plans: Mapped[list["Plan"]] = relationship(
        "Plan",
        back_populates="user",
    )
    analytics_summaries: Mapped[list["AnalyticsSummary"]] = relationship(
        "AnalyticsSummary",
        back_populates="user",
    )
    ai_conversations: Mapped[list["AIConversation"]] = relationship(
        "AIConversation",
        back_populates="user",
    )
    ai_imports: Mapped[list["AIImport"]] = relationship(
        "AIImport",
        back_populates="user",
    )
    strava_session: Mapped[Optional["StravaSession"]] = relationship(
        "StravaSession",
        back_populates="user",
        uselist=False,
    )
    strava_sync_state: Mapped[Optional["StravaSyncState"]] = relationship(
        "StravaSyncState",
        back_populates="user",
        uselist=False,
    )
    gears: Mapped[list["Gear"]] = relationship(
        "Gear",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    strength_sessions: Mapped[list["StrengthSession"]] = relationship(
        "StrengthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
