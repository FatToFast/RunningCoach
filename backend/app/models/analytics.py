"""Analytics summary models."""

from datetime import date
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AnalyticsSummary(BaseModel):
    """Weekly/Monthly analytics summary.

    Stores pre-computed aggregates for dashboard performance optimization.
    period_type: 'week' or 'month'
    """

    __tablename__ = "analytics_summaries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "period_type", "period_start",
            name="uq_analytics_user_period",
        ),
        Index("ix_analytics_summaries_period", "period_type", "period_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Period identification
    period_type: Mapped[str] = mapped_column(String(20), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date)

    # Aggregated metrics
    total_activities: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, server_default="0"
    )
    total_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_pace_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Derived metrics
    total_trimp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_tss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Flexible JSON for additional metrics (elevation, cadence, etc.)
    summary_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="analytics_summaries")

    def __repr__(self) -> str:
        return f"<AnalyticsSummary(user_id={self.user_id}, {self.period_type}={self.period_start})>"
