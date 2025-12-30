"""Calendar note model for personal memos on calendar dates."""

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class CalendarNote(BaseModel):
    """User's personal note for a specific date (injury, event, memo)."""

    __tablename__ = "calendar_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_calendar_note_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, index=True)

    # Note type: memo, injury, event, rest, etc.
    note_type: Mapped[str] = mapped_column(
        String(20),
        default="memo",
        nullable=False,
    )

    # Note content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional: emoji or icon for visual indicator
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="calendar_notes")

    def __repr__(self) -> str:
        return f"<CalendarNote(user_id={self.user_id}, date={self.date}, type={self.note_type})>"
