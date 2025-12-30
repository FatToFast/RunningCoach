"""Add max_hr column to users table.

Revision ID: 008_add_user_max_hr
Revises: 007_extend_activity_models
Create Date: 2024-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008_add_user_max_hr"
down_revision: Union[str, None] = "007_extend_activity_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add max_hr column to users table (Garmin 연동 최대 심박수)
    op.add_column("users", sa.Column("max_hr", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "max_hr")
