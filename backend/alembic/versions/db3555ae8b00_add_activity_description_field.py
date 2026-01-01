"""add_activity_description_field

Revision ID: db3555ae8b00
Revises: 1bf7bd02ff0f
Create Date: 2026-01-01 00:31:29.455977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db3555ae8b00'
down_revision: Union[str, None] = '1bf7bd02ff0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add description column for storing Garmin activity notes/memos
    op.add_column('activities', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'description')
