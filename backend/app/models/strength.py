"""Strength training models."""

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class StrengthSession(BaseModel):
    """Strength training session."""

    __tablename__ = "strength_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Session info
    session_date: Mapped[date] = mapped_column(Date, index=True)
    session_type: Mapped[str] = mapped_column(String(50), index=True)  # 상체/하체/코어/전신
    session_purpose: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 근력/유연성/밸런스/부상예방
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="strength_sessions")
    exercises: Mapped[list["StrengthExercise"]] = relationship(
        "StrengthExercise",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="StrengthExercise.order",
    )

    def __repr__(self) -> str:
        return f"<StrengthSession(id={self.id}, date={self.session_date}, type={self.session_type})>"


class StrengthExercise(BaseModel):
    """Individual exercise within a strength session."""

    __tablename__ = "strength_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("strength_sessions.id", ondelete="CASCADE"),
        index=True,
    )

    # Exercise info
    exercise_name: Mapped[str] = mapped_column(String(100))
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Sets: JSONB array of {"weight_kg": float, "reps": int, "rest_seconds": int | None}
    sets: Mapped[list] = mapped_column(JSONB, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    session: Mapped["StrengthSession"] = relationship("StrengthSession", back_populates="exercises")

    def __repr__(self) -> str:
        return f"<StrengthExercise(id={self.id}, name={self.exercise_name})>"
