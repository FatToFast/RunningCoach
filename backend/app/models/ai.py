"""AI conversation and import models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AIConversation(BaseModel):
    """AI conversation session for training plan generation."""

    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="ko")
    model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="ai_conversations")
    messages: Mapped[list["AIMessage"]] = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<AIConversation(id={self.id}, user_id={self.user_id})>"


class AIMessage(BaseModel):
    """Individual message in an AI conversation."""

    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20))  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    conversation: Mapped["AIConversation"] = relationship(
        "AIConversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<AIMessage(id={self.id}, role={self.role})>"


class AIImport(BaseModel):
    """Manual plan import from external sources (e.g., ChatGPT).

    Stores imported plan JSON and tracks import history.
    """

    __tablename__ = "ai_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    source: Mapped[str] = mapped_column(String(50), default="manual")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="ai_imports")

    def __repr__(self) -> str:
        return f"<AIImport(id={self.id}, user_id={self.user_id}, source={self.source})>"
