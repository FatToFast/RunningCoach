"""Add Clerk user ID and R2 storage fields

Revision ID: 019_add_clerk_user_id
Revises: 018_fit_files_to_db
Create Date: 2026-01-13
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "019_add_clerk_user_id"
down_revision = "018_fit_files_to_db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Clerk authentication and R2 storage fields."""

    # Add Clerk user ID to users table
    op.add_column("users",
        sa.Column("clerk_user_id", sa.String(255), nullable=True, unique=True,
                  comment="Clerk authentication user ID"))

    # Create index for Clerk user ID
    op.create_index(
        "ix_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=True
    )

    # Add R2 storage fields to activities table
    op.add_column("activities",
        sa.Column("r2_key", sa.String(500), nullable=True,
                  comment="R2 object storage key"))
    op.add_column("activities",
        sa.Column("storage_provider", sa.String(20), nullable=True,
                  comment="Storage provider: local, r2, s3"))
    op.add_column("activities",
        sa.Column("storage_metadata", sa.JSON, nullable=True,
                  comment="Storage metadata (size, hash, etc)"))

    # Create index for R2 key lookups
    op.create_index(
        "ix_activities_r2_key",
        "activities",
        ["r2_key"],
        postgresql_where="r2_key IS NOT NULL"
    )

    # Add migration status tracking
    op.create_table(
        "migration_status",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("migration_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),  # pending, in_progress, completed, failed
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default="now()")
    )

    # Make password_hash nullable for Clerk migration
    # (Users will authenticate through Clerk, not local passwords)
    op.alter_column("users", "password_hash",
                    existing_type=sa.Text,
                    nullable=True,
                    comment="Legacy password hash - null for Clerk users")


def downgrade() -> None:
    """Remove Clerk and R2 storage fields."""

    # Restore password_hash as required
    op.alter_column("users", "password_hash",
                    existing_type=sa.Text,
                    nullable=False)

    # Drop migration status table
    op.drop_table("migration_status")

    # Remove indexes
    op.drop_index("ix_activities_r2_key", "activities")
    op.drop_index("ix_users_clerk_user_id", "users")

    # Remove columns
    op.drop_column("activities", "storage_metadata")
    op.drop_column("activities", "storage_provider")
    op.drop_column("activities", "r2_key")
    op.drop_column("users", "clerk_user_id")