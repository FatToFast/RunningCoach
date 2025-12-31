"""Add raw_event_id to activities table and updated_at to activity_metrics.

Revision ID: 011_activity_raw_event
Revises: 7fccb0ac2198
Create Date: 2024-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "011_activity_raw_event"
down_revision: Union[str, None] = "7fccb0ac2198"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("raw_event_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_activities_raw_event",
        "activities",
        "garmin_raw_events",
        ["raw_event_id"],
        ["id"],
        ondelete="SET NULL"
    )

    # Add updated_at to activity_metrics
    op.add_column(
        "activity_metrics",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("activity_metrics", "updated_at")
    op.drop_constraint("fk_activities_raw_event", "activities", type_="foreignkey")
    op.drop_column("activities", "raw_event_id")
