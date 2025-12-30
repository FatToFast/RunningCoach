"""Fix users table columns to match model.

Revision ID: 005_fix_users_columns
Revises: 004_fix_tables
Create Date: 2024-12-30

Changes:
- Rename 'name' to 'display_name' in users table
- Add 'last_login_at' column to users table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_fix_users_columns"
down_revision: Union[str, None] = "004_fix_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename name -> display_name
    op.alter_column(
        "users",
        "name",
        new_column_name="display_name",
    )

    # Add last_login_at column
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Remove last_login_at column
    op.drop_column("users", "last_login_at")

    # Rename display_name -> name
    op.alter_column(
        "users",
        "display_name",
        new_column_name="name",
    )
