"""Fix table names and add missing tables.

Revision ID: 004_fix_tables
Revises: 003_add_garmin_session_data
Create Date: 2024-12-30

Changes:
- Rename body_composition to body_compositions (match model)
- Add hr_records table
- Add health_metrics table
- Add garmin_raw_events table (referenced by health models)

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_fix_tables"
down_revision: Union[str, None] = "003_add_garmin_session_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Rename body_composition to body_compositions
    # -------------------------------------------------------------------------
    op.rename_table("body_composition", "body_compositions")

    # Update unique constraint name to match model
    op.drop_constraint("uq_body_comp_user_date", "body_compositions", type_="unique")
    op.create_unique_constraint(
        "uq_body_composition_user_date",
        "body_compositions",
        ["user_id", "date"]
    )

    # -------------------------------------------------------------------------
    # Add garmin_raw_events table (referenced by health models)
    # -------------------------------------------------------------------------
    op.create_table(
        "garmin_raw_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_garmin_raw_events_user_id", "garmin_raw_events", ["user_id"])
    op.create_index("ix_garmin_raw_events_event_type", "garmin_raw_events", ["event_type"])
    op.create_index("ix_garmin_raw_events_event_date", "garmin_raw_events", ["event_date"])

    # -------------------------------------------------------------------------
    # Add hr_records table
    # -------------------------------------------------------------------------
    op.create_table(
        "hr_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_hr", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),
        sa.Column("resting_hr", sa.Integer(), nullable=True),
        sa.Column("samples", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_event_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_event_id"], ["garmin_raw_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_records_user_id", "hr_records", ["user_id"])
    op.create_index("ix_hr_records_start_time", "hr_records", ["start_time"])

    # -------------------------------------------------------------------------
    # Add health_metrics table
    # -------------------------------------------------------------------------
    op.create_table(
        "health_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("metric_type", sa.String(length=50), nullable=False),
        sa.Column("metric_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_event_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_event_id"], ["garmin_raw_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_metrics_user_id", "health_metrics", ["user_id"])
    op.create_index("ix_health_metrics_metric_type", "health_metrics", ["metric_type"])
    op.create_index("ix_health_metrics_metric_time", "health_metrics", ["metric_time"])

    # -------------------------------------------------------------------------
    # Add raw_event_id to sleep table (missing FK)
    # -------------------------------------------------------------------------
    op.add_column(
        "sleep",
        sa.Column("raw_event_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_sleep_raw_event",
        "sleep",
        "garmin_raw_events",
        ["raw_event_id"],
        ["id"],
        ondelete="SET NULL"
    )

    # -------------------------------------------------------------------------
    # Update sleep table: rename raw_data to stages (match model)
    # -------------------------------------------------------------------------
    op.alter_column("sleep", "raw_data", new_column_name="stages")


def downgrade() -> None:
    # Revert sleep table changes
    op.alter_column("sleep", "stages", new_column_name="raw_data")
    op.drop_constraint("fk_sleep_raw_event", "sleep", type_="foreignkey")
    op.drop_column("sleep", "raw_event_id")

    # Drop new tables
    op.drop_table("health_metrics")
    op.drop_table("hr_records")
    op.drop_table("garmin_raw_events")

    # Revert body_compositions rename
    op.drop_constraint("uq_body_composition_user_date", "body_compositions", type_="unique")
    op.create_unique_constraint(
        "uq_body_comp_user_date",
        "body_compositions",
        ["user_id", "date"]
    )
    op.rename_table("body_compositions", "body_composition")
