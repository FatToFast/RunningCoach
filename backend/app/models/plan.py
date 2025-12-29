"""Training plan models."""

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workout import Workout


class Plan(BaseModel):
    """Training plan for a specific goal."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Goal info
    goal_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )  # marathon, half, 10k, 5k, fitness
    goal_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    goal_time: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )  # Target time (e.g., "3:30:00")

    # Plan period
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        index=True,
    )  # draft, approved, active, completed, cancelled

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="plans")
    weeks: Mapped[list["PlanWeek"]] = relationship(
        "PlanWeek",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanWeek.week_index",
    )

    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, goal={self.goal_type}, status={self.status})>"


class PlanWeek(BaseModel):
    """Week within a training plan."""

    __tablename__ = "plan_weeks"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        index=True,
    )

    week_index: Mapped[int] = mapped_column(Integer)  # 1-indexed
    focus: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # build, peak, recovery, taper
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Target metrics for the week
    target_distance_km: Mapped[Optional[float]] = mapped_column(nullable=True)
    target_duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="weeks")
    workouts: Mapped[list["Workout"]] = relationship(
        "Workout",
        back_populates="plan_week",
    )

    def __repr__(self) -> str:
        return f"<PlanWeek(plan_id={self.plan_id}, week={self.week_index})>"
