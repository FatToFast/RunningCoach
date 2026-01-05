"""Fix workout_schedules schema drift

Add unique constraint and status index to workout_schedules table.
The completed_activity_id column already exists in initial migration.

Revision ID: 015_fix_workout_schedule_schema
Revises: ce46550fb697
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '015_fix_workout_schedule_schema'
down_revision: Union[str, None] = 'ce46550fb697'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate scheduling (same workout on same date)
    op.create_unique_constraint(
        'uq_workout_schedule_workout_date',
        'workout_schedules',
        ['workout_id', 'scheduled_date']
    )

    # Add index on status column for filtering
    op.create_index(
        'ix_workout_schedules_status',
        'workout_schedules',
        ['status']
    )


def downgrade() -> None:
    op.drop_index('ix_workout_schedules_status', table_name='workout_schedules')
    op.drop_constraint('uq_workout_schedule_workout_date', 'workout_schedules', type_='unique')
