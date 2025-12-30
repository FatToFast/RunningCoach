"""Add gear and activity_gear tables.

Revision ID: 002_add_gear
Revises: 001_initial
Create Date: 2024-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_gear"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Gears (shoes, equipment tracking)
    # -------------------------------------------------------------------------
    op.create_table(
        "gears",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("garmin_uuid", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("gear_type", sa.String(length=50), nullable=False, server_default="running_shoes"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("retired_date", sa.Date(), nullable=True),
        sa.Column("initial_distance_meters", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_distance_meters", sa.Float(), nullable=True, server_default="800000"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gears_user_id", "gears", ["user_id"])
    op.create_index("ix_gears_garmin_uuid", "gears", ["garmin_uuid"], unique=True)
    op.create_index("ix_gears_status", "gears", ["status"])
    op.create_index("ix_gears_gear_type", "gears", ["gear_type"])

    # -------------------------------------------------------------------------
    # Activity-Gear Links (many-to-many)
    # -------------------------------------------------------------------------
    op.create_table(
        "activity_gears",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gear_id"], ["gears.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "gear_id", name="uq_activity_gear"),
    )
    op.create_index("ix_activity_gears_activity_id", "activity_gears", ["activity_id"])
    op.create_index("ix_activity_gears_gear_id", "activity_gears", ["gear_id"])


def downgrade() -> None:
    op.drop_table("activity_gears")
    op.drop_table("gears")
