"""add_index_garmin_sync_state_last_success_at

Revision ID: 80813f01fdae
Revises: 011_activity_raw_event
Create Date: 2025-12-31 17:14:07.170656

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '80813f01fdae'
down_revision: Union[str, None] = '011_activity_raw_event'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index for ORDER BY queries on last_success_at
    op.create_index(
        'ix_garmin_sync_states_last_success_at',
        'garmin_sync_states',
        ['last_success_at'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_garmin_sync_states_last_success_at', table_name='garmin_sync_states')
