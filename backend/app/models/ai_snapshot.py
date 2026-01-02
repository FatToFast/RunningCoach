"""AI training snapshot models."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AITrainingSnapshot(BaseModel):
    """Cached AI-ready training snapshot for a user."""

    __tablename__ = "ai_training_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "window_start",
            "window_end",
            "schema_version",
            name="uq_ai_training_snapshot_user_window_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    window_start: Mapped[date] = mapped_column(Date, index=True)
    window_end: Mapped[date] = mapped_column(Date, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    source_last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="ai_training_snapshots",
    )

    def __repr__(self) -> str:
        return (
            "<AITrainingSnapshot("
            f"user_id={self.user_id}, "
            f"window_start={self.window_start}, "
            f"window_end={self.window_end}, "
            f"schema_version={self.schema_version}"
            ")>"
        )
