"""Race model for tracking race events and goals."""

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Race(BaseModel):
    """Race model representing a race event."""

    __tablename__ = "races"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Race details
    name: Mapped[str] = mapped_column(String(200))
    race_date: Mapped[date] = mapped_column(Date, index=True)
    distance_km: Mapped[Optional[float]] = mapped_column(nullable=True)
    distance_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "풀마라톤", "하프", "10K"
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Goals
    goal_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    goal_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)  # Primary target race for D-day display
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Results (filled after race)
    result_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="races")

    def __repr__(self) -> str:
        return f"<Race(id={self.id}, name={self.name}, date={self.race_date})>"
