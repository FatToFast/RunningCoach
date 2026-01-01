#!/usr/bin/env python3
"""Reparse FIT files to extract and update power/dynamics data.

This script reads existing FIT files and updates activities with:
- avg_power, max_power, normalized_power
- avg_ground_contact_time, avg_vertical_oscillation, avg_stride_length
- training_effect_aerobic, training_effect_anaerobic

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/reparse_fit_power.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.activity import Activity
from app.models.garmin import GarminRawFile


def parse_fit_session(fit_path: str) -> dict | None:
    """Parse FIT file and extract session data with power/dynamics."""
    try:
        from fitparse import FitFile

        with open(fit_path, 'rb') as f:
            fit_data = f.read()

        # Handle ZIP files
        if fit_data[:2] == b'PK':
            import zipfile
            import io
            with zipfile.ZipFile(io.BytesIO(fit_data)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith('.fit'):
                        fit_data = zf.read(name)
                        break

        fit_file = FitFile(fit_data)
        session_data = {}

        for record in fit_file.get_messages():
            if record.name == "session":
                for field in record.fields:
                    session_data[field.name] = field.value
                break

        return session_data
    except Exception as e:
        print(f"  Error parsing {fit_path}: {e}")
        return None


async def update_activity_power_data():
    """Update activities with power and dynamics data from FIT files."""
    async with async_session_maker() as session:
        # Get activities that might need updating
        result = await session.execute(
            select(Activity, GarminRawFile)
            .join(GarminRawFile, GarminRawFile.activity_id == Activity.id)
            .where(GarminRawFile.file_path.isnot(None))
            .order_by(Activity.start_time.desc())
        )
        rows = result.all()

        print(f"Found {len(rows)} activities with FIT files")

        updated_count = 0
        power_count = 0
        dynamics_count = 0

        for activity, raw_file in rows:
            if not raw_file.file_path or not os.path.exists(raw_file.file_path):
                continue

            session_data = parse_fit_session(raw_file.file_path)
            if not session_data:
                continue

            updated = False

            # Power data
            if session_data.get("avg_power") and not activity.avg_power:
                activity.avg_power = int(session_data["avg_power"])
                updated = True
                power_count += 1
                print(f"  {activity.name}: avg_power = {activity.avg_power}W")

            if session_data.get("max_power") and not activity.max_power:
                activity.max_power = int(session_data["max_power"])
                updated = True

            if session_data.get("normalized_power") and not activity.normalized_power:
                activity.normalized_power = int(session_data["normalized_power"])
                updated = True

            # Training metrics
            if session_data.get("training_stress_score") and not activity.training_stress_score:
                activity.training_stress_score = float(session_data["training_stress_score"])
                updated = True

            if session_data.get("intensity_factor") and not activity.intensity_factor:
                activity.intensity_factor = float(session_data["intensity_factor"])
                updated = True

            # Running dynamics
            if session_data.get("avg_ground_contact_time") and not activity.avg_ground_contact_time:
                activity.avg_ground_contact_time = int(session_data["avg_ground_contact_time"])
                updated = True
                dynamics_count += 1
            elif session_data.get("avg_stance_time") and not activity.avg_ground_contact_time:
                activity.avg_ground_contact_time = int(session_data["avg_stance_time"])
                updated = True
                dynamics_count += 1

            if session_data.get("avg_vertical_oscillation") and not activity.avg_vertical_oscillation:
                activity.avg_vertical_oscillation = float(session_data["avg_vertical_oscillation"])
                updated = True

            if session_data.get("avg_step_length") and not activity.avg_stride_length:
                activity.avg_stride_length = float(session_data["avg_step_length"]) / 1000  # mm to m
                updated = True

            # Training Effect
            if session_data.get("total_training_effect") and not activity.training_effect_aerobic:
                activity.training_effect_aerobic = float(session_data["total_training_effect"])
                updated = True

            if session_data.get("total_anaerobic_training_effect") and not activity.training_effect_anaerobic:
                activity.training_effect_anaerobic = float(session_data["total_anaerobic_training_effect"])
                updated = True

            if updated:
                updated_count += 1

        await session.commit()
        print(f"\nUpdated {updated_count} activities")
        print(f"  - Power data: {power_count}")
        print(f"  - Dynamics data: {dynamics_count}")


if __name__ == "__main__":
    asyncio.run(update_activity_power_data())
