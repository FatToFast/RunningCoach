"""Strava integration models."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.activity import Activity


class StravaUploadStatus(str, Enum):
    """Status of a Strava upload job."""

    QUEUED = "queued"
    UPLOADING = "uploading"
    POLLING = "polling"  # Waiting for Strava to process
    UPLOADED = "uploaded"
    FAILED = "failed"


class StravaSession(BaseModel):
    """Strava OAuth session tokens."""

    __tablename__ = "strava_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )

    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="strava_session")

    def __repr__(self) -> str:
        return f"<StravaSession(user_id={self.user_id})>"


class StravaSyncState(BaseModel):
    """Strava sync state."""

    __tablename__ = "strava_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="strava_sync_state")

    def __repr__(self) -> str:
        return f"<StravaSyncState(user_id={self.user_id})>"


class StravaActivityMap(BaseModel):
    """Mapping between Garmin activities and Strava uploads."""

    __tablename__ = "strava_activity_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    strava_activity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
    )

    # Relationship
    activity: Mapped["Activity"] = relationship("Activity", back_populates="strava_map")

    def __repr__(self) -> str:
        return f"<StravaActivityMap(activity_id={self.activity_id}, strava_id={self.strava_activity_id})>"


class StravaUploadJob(BaseModel):
    """Queue for Strava upload jobs.

    This table serves as a persistent queue for Strava uploads, allowing
    for reliable retry handling and status tracking.
    """

    __tablename__ = "strava_upload_jobs"
    __table_args__ = (
        Index("ix_strava_upload_jobs_status_next_retry", "status", "next_retry_at"),
        Index("ix_strava_upload_jobs_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        unique=True,  # Prevent duplicate jobs for same activity
        index=True,
    )

    # Job status
    status: Mapped[str] = mapped_column(
        String(20),
        default=StravaUploadStatus.QUEUED.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Strava upload tracking
    strava_upload_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    strava_activity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    activity: Mapped["Activity"] = relationship("Activity")

    def __repr__(self) -> str:
        return (
            f"<StravaUploadJob(id={self.id}, activity_id={self.activity_id}, "
            f"status={self.status}, attempts={self.attempts})>"
        )
