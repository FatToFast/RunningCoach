"""Add date column and unique constraint to hr_records.

Revision ID: 008_add_hr_record_date_unique
Revises: 007_extend_activity_models
Create Date: 2024-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008_add_hr_record_date_unique"
down_revision: Union[str, None] = "007_extend_activity_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add date column
    op.add_column("hr_records", sa.Column("date", sa.Date(), nullable=True))

    # Create index on date column
    op.create_index("ix_hr_records_date", "hr_records", ["date"])

    # Populate date column from start_time for existing records
    op.execute("""
        UPDATE hr_records
        SET date = DATE(start_time)
        WHERE date IS NULL
    """)

    # Delete duplicate records, keeping only the latest one per user/date
    op.execute("""
        DELETE FROM hr_records
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM hr_records
            GROUP BY user_id, date
        )
    """)

    # Make date column not nullable
    op.alter_column("hr_records", "date", nullable=False)

    # Add unique constraint
    op.create_unique_constraint(
        "uq_hr_record_user_date",
        "hr_records",
        ["user_id", "date"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_hr_record_user_date", "hr_records", type_="unique")
    op.drop_index("ix_hr_records_date", "hr_records")
    op.drop_column("hr_records", "date")
