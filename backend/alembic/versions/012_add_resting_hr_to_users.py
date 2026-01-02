"""add_resting_hr_to_users

Revision ID: 012_add_resting_hr
Revises: 08eb26d42ac1
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012_add_resting_hr'
down_revision: Union[str, None] = '08eb26d42ac1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('resting_hr', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'resting_hr')
