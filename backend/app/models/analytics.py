"""Analytics summary models."""

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AnalyticsSummary(BaseModel):
    """Weekly/Monthly analytics summary."""

    __tablename__ = "analytics_summaries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "period_type", "period_start",
            name="uq_analytics_summaries_user_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Period type: 'week' or 'month'
    period_type: Mapped[str] = mapped_column(String(10), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)

    # Aggregated metrics
    total_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_activities: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    elevation_gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Derived metrics
    total_trimp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_tss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="analytics_summaries")

    def __repr__(self) -> str:
        return f"<AnalyticsSummary(user_id={self.user_id}, {self.period_type}={self.period_start})>"
