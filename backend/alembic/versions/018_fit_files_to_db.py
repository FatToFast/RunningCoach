"""Store FIT files in database

Revision ID: 018_fit_files_to_db
Revises: 017
Create Date: 2026-01-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA

# revision identifiers
revision = "018_fit_files_to_db"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add columns for storing FIT file content in database."""

    # Add file content columns to garmin_raw_files
    op.add_column("garmin_raw_files",
        sa.Column("file_content", BYTEA, nullable=True,
                  comment="Compressed FIT file content (gzip)"))
    op.add_column("garmin_raw_files",
        sa.Column("file_size", sa.Integer, nullable=True,
                  comment="Original file size in bytes"))
    op.add_column("garmin_raw_files",
        sa.Column("compression_type", sa.String(10), nullable=True, default="gzip",
                  comment="Compression type: gzip, zstd, or none"))

    # Add index for querying files with content
    op.create_index(
        "ix_garmin_raw_files_has_content",
        "garmin_raw_files",
        ["user_id"],
        postgresql_where="file_content IS NOT NULL"
    )

    # Optional: Add similar columns to activities table for quick access
    op.add_column("activities",
        sa.Column("fit_file_content", BYTEA, nullable=True,
                  comment="Compressed FIT file content (cached copy)"))
    op.add_column("activities",
        sa.Column("fit_file_size", sa.Integer, nullable=True,
                  comment="Original FIT file size in bytes"))


def downgrade() -> None:
    """Remove database storage columns."""

    op.drop_index("ix_garmin_raw_files_has_content", "garmin_raw_files")

    op.drop_column("garmin_raw_files", "file_content")
    op.drop_column("garmin_raw_files", "file_size")
    op.drop_column("garmin_raw_files", "compression_type")

    op.drop_column("activities", "fit_file_content")
    op.drop_column("activities", "fit_file_size")