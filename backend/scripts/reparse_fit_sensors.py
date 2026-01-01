#!/usr/bin/env python3
"""Reparse FIT files to extract sensor information.

This script reads existing FIT files and updates activities with:
- has_stryd: True if Stryd footpod was used
- has_external_hr: True if external HR monitor was used (device_type=120)

Device type reference:
- 0: Main watch
- 3: GPS
- 4: Remote
- 8: Activity tracker
- 10: Barometer
- 12: Software (app)
- 120: Heart rate monitor (ANT+/Bluetooth chest strap)

Manufacturer 'stryd' indicates Stryd footpod usage.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/reparse_fit_sensors.py
"""

import asyncio
import io
import os
import sys
import zipfile
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.activity import Activity
from app.models.garmin import GarminRawFile


def parse_fit_sensors(fit_path: str) -> dict:
    """Parse FIT file and extract sensor/device information."""
    try:
        from fitparse import FitFile

        with open(fit_path, 'rb') as f:
            fit_data = f.read()

        # Handle ZIP files
        if fit_data[:2] == b'PK':
            with zipfile.ZipFile(io.BytesIO(fit_data)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith('.fit'):
                        fit_data = zf.read(name)
                        break

        fit_file = FitFile(fit_data)

        has_stryd = False
        has_external_hr = False

        for record in fit_file.get_messages('device_info'):
            device_data = {}
            for field in record.fields:
                device_data[field.name] = field.value

            manufacturer = device_data.get('manufacturer')
            device_type = device_data.get('device_type')
            antplus_device_type = device_data.get('antplus_device_type')

            # Stryd detection - manufacturer is 'stryd'
            if manufacturer == 'stryd':
                has_stryd = True

            # External HR monitor detection
            # - device_type 120 is HR monitor
            # - antplus_device_type 'heart_rate' indicates ANT+ HR strap
            if device_type == 120 or antplus_device_type == 'heart_rate':
                has_external_hr = True

        return {
            'has_stryd': has_stryd,
            'has_external_hr': has_external_hr,
        }
    except Exception as e:
        print(f"  Error parsing {fit_path}: {e}")
        return {}


async def update_activity_sensors():
    """Update activities with sensor data from FIT files."""
    async with async_session_maker() as session:
        # Get activities with FIT files
        result = await session.execute(
            select(Activity, GarminRawFile)
            .join(GarminRawFile, GarminRawFile.activity_id == Activity.id)
            .where(GarminRawFile.file_path.isnot(None))
            .order_by(Activity.start_time.desc())
        )
        rows = result.all()

        print(f"Found {len(rows)} activities with FIT files")

        updated_count = 0
        stryd_count = 0
        hr_count = 0

        for activity, raw_file in rows:
            if not raw_file.file_path or not os.path.exists(raw_file.file_path):
                continue

            sensor_data = parse_fit_sensors(raw_file.file_path)
            if not sensor_data:
                continue

            updated = False

            if sensor_data.get('has_stryd') and not activity.has_stryd:
                activity.has_stryd = True
                updated = True
                stryd_count += 1
                print(f"  {activity.name}: Stryd detected")

            if sensor_data.get('has_external_hr') and not activity.has_external_hr:
                activity.has_external_hr = True
                updated = True
                hr_count += 1
                print(f"  {activity.name}: External HR detected")

            if updated:
                updated_count += 1

        await session.commit()
        print(f"\nUpdated {updated_count} activities")
        print(f"  - Stryd: {stryd_count}")
        print(f"  - External HR: {hr_count}")


if __name__ == "__main__":
    asyncio.run(update_activity_sensors())
