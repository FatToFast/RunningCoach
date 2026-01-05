"""AI conversation and import models.

Schema matches migration 001_initial_schema.py:
- ai_conversations: context_type, context_data (not language, model)
- ai_messages: token_count (not tokens)
- ai_imports: import_type, raw_content, parsed_data, status, error_message, result_plan_id
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.user import User


class AIConversation(BaseModel):
    """AI conversation session for training plan generation.

    DB Schema (001_initial_schema.py):
    - id, user_id, title, context_type, context_data, created_at, updated_at
    """

    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # context_type: e.g., "plan_generation", "analysis", "chat"
    context_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # context_data: flexible JSON for conversation context (goals, preferences, etc.)
    context_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

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
    """Individual message in an AI conversation.

    DB Schema (001_initial_schema.py):
    - id, conversation_id, role, content, token_count, created_at
    """

    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20))  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # DB column is 'token_count', not 'tokens'
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    conversation: Mapped["AIConversation"] = relationship(
        "AIConversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<AIMessage(id={self.id}, role={self.role})>"


class AIImport(BaseModel):
    """Manual plan import from external sources (e.g., ChatGPT).

    DB Schema (001_initial_schema.py):
    - id, user_id, source, import_type, raw_content, parsed_data,
      status, error_message, result_plan_id, created_at, processed_at
    """

    __tablename__ = "ai_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    source: Mapped[str] = mapped_column(String(50), nullable=False)
    import_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "plan", "workout", etc.
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)  # Original input (JSON string)
    parsed_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # Validated payload

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )  # pending, success, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Link to created plan
    result_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="ai_imports")
    result_plan: Mapped[Optional["Plan"]] = relationship(
        "Plan",
        foreign_keys=[result_plan_id],
    )

    def __repr__(self) -> str:
        return f"<AIImport(id={self.id}, user_id={self.user_id}, status={self.status})>"
