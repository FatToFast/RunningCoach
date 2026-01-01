"""Fix Garmin table schema drift between models and migrations.

Revision ID: 012_fix_garmin_schema
Revises: 011_activity_raw_event
Create Date: 2024-12-31

Fixes:
1. garmin_raw_events: event_type/event_date/raw_data → endpoint/fetched_at/payload
2. garmin_raw_files: Add user_id, file_hash, fetched_at; change file_size semantics
3. garmin_sync_states: Rename constraint to match model
4. activities.garmin_id: Change from global unique to (user_id, garmin_id) composite unique
5. Add composite index for ingest history queries

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "012_fix_garmin_schema"
down_revision: Union[str, None] = "011_activity_raw_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Fix garmin_raw_events schema
    # Model expects: endpoint, fetched_at, payload
    # Migration 004 created: event_type, event_date, raw_data
    # -------------------------------------------------------------------------

    # Rename columns to match model
    op.alter_column("garmin_raw_events", "event_type", new_column_name="endpoint")
    op.alter_column("garmin_raw_events", "raw_data", new_column_name="payload")

    # Change event_date (Date) to fetched_at (DateTime with timezone)
    # First add new column, copy data, drop old column
    op.add_column(
        "garmin_raw_events",
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Copy data: convert Date to DateTime at midnight
    op.execute(
        "UPDATE garmin_raw_events SET fetched_at = event_date::timestamp AT TIME ZONE 'UTC'"
    )

    # Make fetched_at not null and drop old column
    op.alter_column("garmin_raw_events", "fetched_at", nullable=False)
    op.drop_column("garmin_raw_events", "event_date")

    # Update indexes (drop old, create new)
    op.drop_index("ix_garmin_raw_events_event_type", table_name="garmin_raw_events")
    op.drop_index("ix_garmin_raw_events_event_date", table_name="garmin_raw_events")
    op.create_index("ix_garmin_raw_events_endpoint", "garmin_raw_events", ["endpoint"])
    op.create_index("ix_garmin_raw_events_fetched_at", "garmin_raw_events", ["fetched_at"])

    # Add updated_at column (from BaseModel)
    op.add_column(
        "garmin_raw_events",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )

    # Make payload not null (model expects non-null)
    op.alter_column("garmin_raw_events", "payload", nullable=False)

    # Expand endpoint column to 100 chars (model uses String(100))
    op.alter_column(
        "garmin_raw_events",
        "endpoint",
        type_=sa.String(100),
        existing_type=sa.String(50),
    )

    # -------------------------------------------------------------------------
    # 2. Fix garmin_raw_files schema
    # Model expects: user_id, activity_id, file_type, file_path, file_hash, fetched_at
    # Migration 001 created: activity_id, file_path, file_type, file_size (no user_id, file_hash, fetched_at)
    # -------------------------------------------------------------------------

    # Add user_id column
    op.add_column(
        "garmin_raw_files",
        sa.Column("user_id", sa.Integer(), nullable=True)
    )

    # Populate user_id from activities table
    op.execute("""
        UPDATE garmin_raw_files grf
        SET user_id = a.user_id
        FROM activities a
        WHERE grf.activity_id = a.id
    """)

    # Make user_id not null and add FK
    op.alter_column("garmin_raw_files", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_garmin_raw_files_user",
        "garmin_raw_files",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_index("ix_garmin_raw_files_user_id", "garmin_raw_files", ["user_id"])

    # Add file_hash column
    op.add_column(
        "garmin_raw_files",
        sa.Column("file_hash", sa.String(64), nullable=True)
    )

    # Add fetched_at column (rename created_at or add new)
    # Model uses fetched_at with server_default, let's use that
    op.add_column(
        "garmin_raw_files",
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )

    # Copy existing created_at to fetched_at for existing records
    op.execute("UPDATE garmin_raw_files SET fetched_at = created_at")

    # Add updated_at column (from BaseModel)
    op.add_column(
        "garmin_raw_files",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )

    # Drop file_size column (not in model)
    op.drop_column("garmin_raw_files", "file_size")

    # Change file_path from String(500) to Text (model uses Text)
    op.alter_column(
        "garmin_raw_files",
        "file_path",
        type_=sa.Text(),
        existing_type=sa.String(500),
    )

    # -------------------------------------------------------------------------
    # 3. Fix garmin_sync_states constraint name
    # Model: uq_garmin_sync_state_user_endpoint
    # Migration 001: uq_garmin_sync_user_endpoint
    # -------------------------------------------------------------------------

    op.drop_constraint("uq_garmin_sync_user_endpoint", "garmin_sync_states", type_="unique")
    op.create_unique_constraint(
        "uq_garmin_sync_state_user_endpoint",
        "garmin_sync_states",
        ["user_id", "endpoint"]
    )

    # Expand endpoint column to 100 chars (model uses String(100), migration used 50)
    op.alter_column(
        "garmin_sync_states",
        "endpoint",
        type_=sa.String(100),
        existing_type=sa.String(50),
    )

    # Change cursor from String(255) to Text (model uses Text)
    op.alter_column(
        "garmin_sync_states",
        "cursor",
        type_=sa.Text(),
        existing_type=sa.String(255),
    )

    # Add index on last_success_at (model has index=True)
    op.create_index(
        "ix_garmin_sync_states_last_success_at",
        "garmin_sync_states",
        ["last_success_at"]
    )

    # -------------------------------------------------------------------------
    # 4. Fix activities.garmin_id unique constraint
    # Current: global unique (garmin_id alone)
    # Should be: composite unique (user_id, garmin_id)
    # Garmin activity IDs are unique per user, not globally
    # -------------------------------------------------------------------------

    op.drop_index("ix_activities_garmin_id", table_name="activities")
    op.create_index("ix_activities_garmin_id", "activities", ["garmin_id"])  # Non-unique
    op.create_unique_constraint(
        "uq_activities_user_garmin_id",
        "activities",
        ["user_id", "garmin_id"]
    )

    # -------------------------------------------------------------------------
    # 5. Add composite index for ingest history queries
    # /ingest/history filters by user_id + endpoint + fetched_at
    # -------------------------------------------------------------------------

    op.create_index(
        "ix_garmin_raw_events_user_endpoint_fetched",
        "garmin_raw_events",
        ["user_id", "endpoint", "fetched_at"]
    )


def downgrade() -> None:
    # 5. Drop composite index
    op.drop_index("ix_garmin_raw_events_user_endpoint_fetched", table_name="garmin_raw_events")

    # 4. Revert activities.garmin_id constraint
    op.drop_constraint("uq_activities_user_garmin_id", "activities", type_="unique")
    op.drop_index("ix_activities_garmin_id", table_name="activities")
    op.create_index("ix_activities_garmin_id", "activities", ["garmin_id"], unique=True)

    # 3. Revert garmin_sync_states changes
    op.drop_index("ix_garmin_sync_states_last_success_at", table_name="garmin_sync_states")
    op.alter_column(
        "garmin_sync_states",
        "cursor",
        type_=sa.String(255),
        existing_type=sa.Text(),
    )
    op.alter_column(
        "garmin_sync_states",
        "endpoint",
        type_=sa.String(50),
        existing_type=sa.String(100),
    )
    op.drop_constraint("uq_garmin_sync_state_user_endpoint", "garmin_sync_states", type_="unique")
    op.create_unique_constraint(
        "uq_garmin_sync_user_endpoint",
        "garmin_sync_states",
        ["user_id", "endpoint"]
    )

    # 2. Revert garmin_raw_files changes
    op.alter_column(
        "garmin_raw_files",
        "file_path",
        type_=sa.String(500),
        existing_type=sa.Text(),
    )
    op.add_column(
        "garmin_raw_files",
        sa.Column("file_size", sa.Integer(), nullable=True)
    )
    op.drop_column("garmin_raw_files", "updated_at")
    op.drop_column("garmin_raw_files", "fetched_at")
    op.drop_column("garmin_raw_files", "file_hash")
    op.drop_index("ix_garmin_raw_files_user_id", table_name="garmin_raw_files")
    op.drop_constraint("fk_garmin_raw_files_user", "garmin_raw_files", type_="foreignkey")
    op.drop_column("garmin_raw_files", "user_id")

    # 1. Revert garmin_raw_events changes
    op.alter_column(
        "garmin_raw_events",
        "endpoint",
        type_=sa.String(50),
        existing_type=sa.String(100),
    )
    op.alter_column("garmin_raw_events", "payload", nullable=True)
    op.drop_column("garmin_raw_events", "updated_at")

    # Recreate event_date from fetched_at
    op.add_column(
        "garmin_raw_events",
        sa.Column("event_date", sa.Date(), nullable=True)
    )
    op.execute("UPDATE garmin_raw_events SET event_date = fetched_at::date")
    op.alter_column("garmin_raw_events", "event_date", nullable=False)
    op.drop_column("garmin_raw_events", "fetched_at")

    # Rename columns back
    op.alter_column("garmin_raw_events", "payload", new_column_name="raw_data")
    op.alter_column("garmin_raw_events", "endpoint", new_column_name="event_type")

    # Recreate old indexes
    op.drop_index("ix_garmin_raw_events_fetched_at", table_name="garmin_raw_events")
    op.drop_index("ix_garmin_raw_events_endpoint", table_name="garmin_raw_events")
    op.create_index("ix_garmin_raw_events_event_date", "garmin_raw_events", ["event_date"])
    op.create_index("ix_garmin_raw_events_event_type", "garmin_raw_events", ["event_type"])
