"""Garmin-related models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, deferred

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.activity import Activity


class GarminSession(BaseModel):
    """Garmin session tokens for API authentication.

    Uses garminconnect library's session_data format which includes
    OAuth tokens and session cookies. The session_data is stored as JSONB.
    """

    __tablename__ = "garmin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )

    # garminconnect session_data (includes OAuth tokens, cookies, etc.)
    # This is the complete session state from garminconnect library
    session_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Legacy OAuth fields (deprecated, will be removed in v2.0)
    oauth1_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    oauth2_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="garmin_session")

    @property
    def is_valid(self) -> bool:
        """Check if session appears valid (has session_data)."""
        return self.session_data is not None and bool(self.session_data)

    def __repr__(self) -> str:
        return f"<GarminSession(user_id={self.user_id})>"


class GarminSyncState(BaseModel):
    """Sync state per endpoint for incremental sync."""

    __tablename__ = "garmin_sync_states"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uq_garmin_sync_state_user_endpoint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    endpoint: Mapped[str] = mapped_column(String(100), index=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,  # Index for ORDER BY queries
    )
    cursor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="garmin_sync_states")

    def __repr__(self) -> str:
        return f"<GarminSyncState(user_id={self.user_id}, endpoint={self.endpoint})>"


class GarminRawEvent(BaseModel):
    """Raw JSON data fetched from Garmin API."""

    __tablename__ = "garmin_raw_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    endpoint: Mapped[str] = mapped_column(String(100), index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<GarminRawEvent(id={self.id}, endpoint={self.endpoint})>"


class GarminRawFile(BaseModel):
    """FIT file metadata for activities."""

    __tablename__ = "garmin_raw_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"),
        index=True,
    )

    file_type: Mapped[str] = mapped_column(String(20), default="fit")
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # None when file deleted after parse
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Database storage columns
    file_content: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True, deferred=True,
        comment="Compressed FIT file content (gzip)"
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Original file size in bytes"
    )
    compression_type: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, default="gzip",
        comment="Compression type: gzip, zstd, or none"
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
    )

    # Relationship
    activity: Mapped["Activity"] = relationship("Activity", back_populates="raw_file")

    def __repr__(self) -> str:
        return f"<GarminRawFile(activity_id={self.activity_id}, type={self.file_type})>"
