"""add_garmin_activity_count_to_gears

Revision ID: c1f82ac4f045
Revises: db3555ae8b00
Create Date: 2026-01-01 01:29:21.778301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f82ac4f045'
down_revision: Union[str, None] = 'db3555ae8b00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gears', sa.Column('garmin_activity_count', sa.Integer(), nullable=True, default=0))


def downgrade() -> None:
    op.drop_column('gears', 'garmin_activity_count')
