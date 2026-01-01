"""Add sensor info fields to activity

Revision ID: 1bf7bd02ff0f
Revises: a45283fea8d2
Create Date: 2024-12-31 23:59:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bf7bd02ff0f'
down_revision: Union[str, None] = '012_fix_garmin_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sensor info columns to activities table
    op.add_column('activities', sa.Column('has_stryd', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('activities', sa.Column('has_external_hr', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('activities', 'has_external_hr')
    op.drop_column('activities', 'has_stryd')
