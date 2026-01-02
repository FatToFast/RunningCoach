"""add_stryd_metrics_to_activities

Revision ID: 013_add_stryd_metrics
Revises: 012_add_resting_hr
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '013_add_stryd_metrics'
down_revision: Union[str, None] = '012_add_resting_hr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('avg_form_power', sa.Integer(), nullable=True))
    op.add_column('activities', sa.Column('avg_leg_spring_stiffness', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'avg_leg_spring_stiffness')
    op.drop_column('activities', 'avg_form_power')
