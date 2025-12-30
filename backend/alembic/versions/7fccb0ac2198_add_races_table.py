"""Add races table

Revision ID: 7fccb0ac2198
Revises: 092d615b9f22
Create Date: 2025-12-31 01:40:30.303195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7fccb0ac2198'
down_revision: Union[str, None] = '092d615b9f22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create races table only
    op.create_table('races',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('race_date', sa.Date(), nullable=False),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('distance_label', sa.String(length=50), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('goal_time_seconds', sa.Integer(), nullable=True),
        sa.Column('goal_description', sa.Text(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('result_time_seconds', sa.Integer(), nullable=True),
        sa.Column('result_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_races_race_date'), 'races', ['race_date'], unique=False)
    op.create_index(op.f('ix_races_user_id'), 'races', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_races_user_id'), table_name='races')
    op.drop_index(op.f('ix_races_race_date'), table_name='races')
    op.drop_table('races')
