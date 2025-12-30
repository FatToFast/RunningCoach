"""Extend Activity and ActivitySample models with new fields.

Revision ID: 007_extend_activity_models
Revises: 006_add_activity_laps
Create Date: 2024-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007_extend_activity_models"
down_revision: Union[str, None] = "006_add_activity_laps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Activities table - Add new columns
    # -------------------------------------------------------------------------

    # Time fields
    op.add_column("activities", sa.Column("start_time_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("activities", sa.Column("elapsed_seconds", sa.Integer(), nullable=True))

    # Pace
    op.add_column("activities", sa.Column("best_pace_seconds", sa.Integer(), nullable=True))

    # Cadence
    op.add_column("activities", sa.Column("max_cadence", sa.Integer(), nullable=True))

    # Power metrics
    op.add_column("activities", sa.Column("avg_power", sa.Integer(), nullable=True))
    op.add_column("activities", sa.Column("max_power", sa.Integer(), nullable=True))
    op.add_column("activities", sa.Column("normalized_power", sa.Integer(), nullable=True))

    # Training Effect
    op.add_column("activities", sa.Column("training_effect_aerobic", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("training_effect_anaerobic", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("vo2max", sa.Float(), nullable=True))

    # Training metrics (from FIT file)
    op.add_column("activities", sa.Column("training_stress_score", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("intensity_factor", sa.Float(), nullable=True))

    # Running dynamics
    op.add_column("activities", sa.Column("avg_ground_contact_time", sa.Integer(), nullable=True))
    op.add_column("activities", sa.Column("avg_vertical_oscillation", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("avg_stride_length", sa.Float(), nullable=True))

    # FIT file info
    op.add_column("activities", sa.Column("fit_file_path", sa.Text(), nullable=True))
    op.add_column("activities", sa.Column("fit_file_hash", sa.String(64), nullable=True))
    op.add_column("activities", sa.Column("has_fit_file", sa.Boolean(), server_default="false", nullable=False))

    # -------------------------------------------------------------------------
    # Activity Samples table - Add new columns
    # -------------------------------------------------------------------------

    op.add_column("activity_samples", sa.Column("elapsed_seconds", sa.Integer(), nullable=True))
    op.add_column("activity_samples", sa.Column("heart_rate", sa.Integer(), nullable=True))
    op.add_column("activity_samples", sa.Column("speed", sa.Float(), nullable=True))
    op.add_column("activity_samples", sa.Column("distance_meters", sa.Float(), nullable=True))
    op.add_column("activity_samples", sa.Column("ground_contact_time", sa.Integer(), nullable=True))
    op.add_column("activity_samples", sa.Column("vertical_oscillation", sa.Float(), nullable=True))
    op.add_column("activity_samples", sa.Column("stride_length", sa.Float(), nullable=True))


def downgrade() -> None:
    # Activity Samples - Drop columns
    op.drop_column("activity_samples", "stride_length")
    op.drop_column("activity_samples", "vertical_oscillation")
    op.drop_column("activity_samples", "ground_contact_time")
    op.drop_column("activity_samples", "distance_meters")
    op.drop_column("activity_samples", "speed")
    op.drop_column("activity_samples", "heart_rate")
    op.drop_column("activity_samples", "elapsed_seconds")

    # Activities - Drop columns
    op.drop_column("activities", "has_fit_file")
    op.drop_column("activities", "fit_file_hash")
    op.drop_column("activities", "fit_file_path")
    op.drop_column("activities", "avg_stride_length")
    op.drop_column("activities", "avg_vertical_oscillation")
    op.drop_column("activities", "avg_ground_contact_time")
    op.drop_column("activities", "intensity_factor")
    op.drop_column("activities", "training_stress_score")
    op.drop_column("activities", "vo2max")
    op.drop_column("activities", "training_effect_anaerobic")
    op.drop_column("activities", "training_effect_aerobic")
    op.drop_column("activities", "normalized_power")
    op.drop_column("activities", "max_power")
    op.drop_column("activities", "avg_power")
    op.drop_column("activities", "max_cadence")
    op.drop_column("activities", "best_pace_seconds")
    op.drop_column("activities", "elapsed_seconds")
    op.drop_column("activities", "start_time_utc")
