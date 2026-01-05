"""add strava upload jobs table

Revision ID: 014_add_strava_upload_jobs
Revises: 08eb26d42ac1
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '014_add_strava_upload_jobs'
down_revision: Union[str, None] = '013_add_stryd_metrics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'strava_upload_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('strava_upload_id', sa.BigInteger(), nullable=True),
        sa.Column('strava_activity_id', sa.BigInteger(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Unique constraint on activity_id to prevent duplicate jobs
    op.create_index(
        'ix_strava_upload_jobs_activity_id',
        'strava_upload_jobs',
        ['activity_id'],
        unique=True,
    )

    # Index for querying pending jobs
    op.create_index(
        'ix_strava_upload_jobs_status_next_retry',
        'strava_upload_jobs',
        ['status', 'next_retry_at'],
        unique=False,
    )

    # Index for user status queries
    op.create_index(
        'ix_strava_upload_jobs_user_status',
        'strava_upload_jobs',
        ['user_id', 'status'],
        unique=False,
    )

    # Index for user_id
    op.create_index(
        'ix_strava_upload_jobs_user_id',
        'strava_upload_jobs',
        ['user_id'],
        unique=False,
    )

    # Index for status alone
    op.create_index(
        'ix_strava_upload_jobs_status',
        'strava_upload_jobs',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_strava_upload_jobs_status', table_name='strava_upload_jobs')
    op.drop_index('ix_strava_upload_jobs_user_id', table_name='strava_upload_jobs')
    op.drop_index('ix_strava_upload_jobs_user_status', table_name='strava_upload_jobs')
    op.drop_index('ix_strava_upload_jobs_status_next_retry', table_name='strava_upload_jobs')
    op.drop_index('ix_strava_upload_jobs_activity_id', table_name='strava_upload_jobs')
    op.drop_table('strava_upload_jobs')
