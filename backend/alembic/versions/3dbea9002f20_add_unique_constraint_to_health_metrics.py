"""Add unique constraint to health_metrics

Revision ID: 3dbea9002f20
Revises: 014_add_strava_upload_jobs
Create Date: 2026-01-05 23:13:50.989287

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3dbea9002f20'
down_revision: Union[str, None] = '014_add_strava_upload_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to health_metrics for upsert operations
    op.create_unique_constraint(
        'uq_health_metric_user_type_time',
        'health_metrics',
        ['user_id', 'metric_type', 'metric_time']
    )


def downgrade() -> None:
    op.drop_constraint('uq_health_metric_user_type_time', 'health_metrics', type_='unique')
