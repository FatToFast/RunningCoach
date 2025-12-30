"""add calendar_notes table

Revision ID: 092d615b9f22
Revises: 010_strength
Create Date: 2025-12-31 00:59:16.557908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '092d615b9f22'
down_revision: Union[str, None] = '010_strength'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create calendar_notes table
    op.create_table('calendar_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('note_type', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('icon', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_calendar_note_user_date')
    )
    op.create_index(op.f('ix_calendar_notes_date'), 'calendar_notes', ['date'], unique=False)
    op.create_index(op.f('ix_calendar_notes_user_id'), 'calendar_notes', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_calendar_notes_user_id'), table_name='calendar_notes')
    op.drop_index(op.f('ix_calendar_notes_date'), table_name='calendar_notes')
    op.drop_table('calendar_notes')
