"""add ai training snapshots

Revision ID: 08eb26d42ac1
Revises: c1f82ac4f045
Create Date: 2026-01-02 13:37:35.810247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '08eb26d42ac1'
down_revision: Union[str, None] = 'c1f82ac4f045'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_training_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('window_start', sa.Date(), nullable=False),
        sa.Column('window_end', sa.Date(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column(
            'generated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('source_last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id',
            'window_start',
            'window_end',
            'schema_version',
            name='uq_ai_training_snapshot_user_window_version',
        ),
    )
    op.create_index(
        op.f('ix_ai_training_snapshots_generated_at'),
        'ai_training_snapshots',
        ['generated_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_ai_training_snapshots_user_id'),
        'ai_training_snapshots',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_ai_training_snapshots_window_end'),
        'ai_training_snapshots',
        ['window_end'],
        unique=False,
    )
    op.create_index(
        op.f('ix_ai_training_snapshots_window_start'),
        'ai_training_snapshots',
        ['window_start'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_training_snapshots_window_start'), table_name='ai_training_snapshots')
    op.drop_index(op.f('ix_ai_training_snapshots_window_end'), table_name='ai_training_snapshots')
    op.drop_index(op.f('ix_ai_training_snapshots_user_id'), table_name='ai_training_snapshots')
    op.drop_index(op.f('ix_ai_training_snapshots_generated_at'), table_name='ai_training_snapshots')
    op.drop_table('ai_training_snapshots')
