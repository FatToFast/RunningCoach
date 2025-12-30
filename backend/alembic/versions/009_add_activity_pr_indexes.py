"""Add indexes for PR query optimization.

Revision ID: 009_add_activity_pr_indexes
Revises: 008_add_hr_record_date_unique
Create Date: 2024-12-30

These indexes optimize personal record queries that filter by
user_id, activity_type and sort by distance/duration.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "009_add_activity_pr_indexes"
down_revision: Union[str, None] = "008_add_hr_record_date_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for distance-based PR queries
    # Covers: WHERE user_id=? AND activity_type=? ORDER BY distance_meters
    op.create_index(
        "ix_activities_user_type_distance",
        "activities",
        ["user_id", "activity_type", "distance_meters"],
    )

    # Composite index for duration-based PR queries
    # Covers: WHERE user_id=? AND activity_type=? ORDER BY duration_seconds
    op.create_index(
        "ix_activities_user_type_duration",
        "activities",
        ["user_id", "activity_type", "duration_seconds"],
    )

    # Composite index for date-filtered queries (recent PRs)
    # Covers: WHERE user_id=? AND activity_type=? AND start_time >= ?
    op.create_index(
        "ix_activities_user_type_start_time",
        "activities",
        ["user_id", "activity_type", "start_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_activities_user_type_start_time", "activities")
    op.drop_index("ix_activities_user_type_duration", "activities")
    op.drop_index("ix_activities_user_type_distance", "activities")
