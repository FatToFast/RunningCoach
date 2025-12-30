"""Add session_data column to garmin_sessions.

Revision ID: 003_add_garmin_session_data
Revises: 002_add_gear
Create Date: 2024-12-30

This migration adds a JSONB column for storing garminconnect library's
session_data format, which includes OAuth tokens and session cookies.

The legacy oauth1_token, oauth2_token, and expires_at columns are preserved
for backward compatibility but will be deprecated in v2.0.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "003_add_garmin_session_data"
down_revision = "002_add_gear"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add session_data column to garmin_sessions."""
    op.add_column(
        "garmin_sessions",
        sa.Column("session_data", JSONB, nullable=True),
    )


def downgrade() -> None:
    """Remove session_data column from garmin_sessions."""
    op.drop_column("garmin_sessions", "session_data")
