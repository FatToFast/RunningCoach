"""Workout and schedule models."""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.user import User
    from app.models.plan import PlanWeek


class WorkoutScheduleStatus(str, Enum):
    """Workout schedule status enum."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class Workout(BaseModel):
    """Workout template that can be pushed to Garmin."""

    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    plan_week_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("plan_weeks.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200))
    workout_type: Mapped[str] = mapped_column(String(50), index=True)

    # Workout structure (list of steps: warmup, main, cooldown)
    structure: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)

    # Target metrics (pace zones, HR zones, etc.)
    target: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Notes/description
    notes: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    # Garmin sync status
    garmin_workout_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workouts")
    plan_week: Mapped[Optional["PlanWeek"]] = relationship(
        "PlanWeek",
        back_populates="workouts",
    )
    schedules: Mapped[list["WorkoutSchedule"]] = relationship(
        "WorkoutSchedule",
        back_populates="workout",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workout(id={self.id}, name={self.name}, type={self.workout_type})>"


class WorkoutSchedule(BaseModel):
    """Scheduled workout on a specific date."""

    __tablename__ = "workout_schedules"
    __table_args__ = (
        # Prevent duplicate scheduling: same workout on same date
        UniqueConstraint(
            "workout_id", "scheduled_date",
            name="uq_workout_schedule_workout_date",
        ),
        Index("ix_workout_schedules_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"),
        index=True,
    )

    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=WorkoutScheduleStatus.SCHEDULED.value,
        # index defined in __table_args__ as ix_workout_schedules_status
    )

    # Garmin sync status
    garmin_schedule_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Link to completed activity (set when status becomes COMPLETED)
    completed_activity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    workout: Mapped["Workout"] = relationship("Workout", back_populates="schedules")
    completed_activity: Mapped[Optional["Activity"]] = relationship(
        "Activity",
        foreign_keys=[completed_activity_id],
    )

    def __repr__(self) -> str:
        return f"<WorkoutSchedule(workout_id={self.workout_id}, date={self.scheduled_date})>"
