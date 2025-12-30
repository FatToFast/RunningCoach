"""Add strength training tables.

Revision ID: 010_strength
Revises: 009_activity_pr_idx
Create Date: 2024-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "010_strength"
down_revision: Union[str, None] = "009_add_activity_pr_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Strength Sessions (main table)
    # -------------------------------------------------------------------------
    op.create_table(
        "strength_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(length=50), nullable=False),  # 상체/하체/코어/전신
        sa.Column("session_purpose", sa.String(length=50), nullable=True),  # 근력/유연성/밸런스/부상예방
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),  # 1-5
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strength_sessions_user_id", "strength_sessions", ["user_id"])
    op.create_index("ix_strength_sessions_session_date", "strength_sessions", ["session_date"])
    op.create_index("ix_strength_sessions_session_type", "strength_sessions", ["session_type"])
    op.create_index("ix_strength_sessions_user_date", "strength_sessions", ["user_id", "session_date"])

    # -------------------------------------------------------------------------
    # Strength Exercises (individual exercises within a session)
    # -------------------------------------------------------------------------
    op.create_table(
        "strength_exercises",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("exercise_name", sa.String(length=100), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sets", JSONB(), nullable=False, server_default="[]"),  # [{weight_kg, reps, rest_seconds}, ...]
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["strength_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strength_exercises_session_id", "strength_exercises", ["session_id"])


def downgrade() -> None:
    op.drop_table("strength_exercises")
    op.drop_table("strength_sessions")
