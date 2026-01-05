"""Add user profile fields for training calculations

Revision ID: ce46550fb697
Revises: 3dbea9002f20
Create Date: 2026-01-05 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ce46550fb697'
down_revision: Union[str, None] = '3dbea9002f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user profile fields for more accurate training calculations
    op.add_column('users', sa.Column('birth_year', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('gender', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('threshold_pace', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'threshold_pace')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'birth_year')
