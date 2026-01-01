#!/usr/bin/env python3
"""Re-parse FIT files and store samples for existing activities.

Run from backend directory:
    python scripts/reparse_fit_files.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.garmin_adapter import GarminConnectAdapter
from app.core.database import async_session_maker
from app.models.activity import Activity, ActivitySample, ActivityLap

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def reparse_fit_files():
    """Re-parse all FIT files and store samples."""
    adapter = GarminConnectAdapter()

    async with async_session_maker() as session:
        # Get all activities with FIT files
        result = await session.execute(
            select(Activity).where(Activity.has_fit_file == True)
        )
        activities = result.scalars().all()

        logger.info(f"Found {len(activities)} activities with FIT files")

        processed = 0
        skipped = 0
        errors = 0

        for activity in activities:
            try:
                # Check if samples already exist
                sample_check = await session.execute(
                    select(ActivitySample).where(ActivitySample.activity_id == activity.id).limit(1)
                )
                if sample_check.scalar_one_or_none():
                    skipped += 1
                    continue

                # Read and parse FIT file
                fit_path = Path(activity.fit_file_path)
                if not fit_path.is_absolute():
                    fit_path = Path(__file__).parent.parent / fit_path

                if not fit_path.exists():
                    logger.warning(f"FIT file not found: {fit_path}")
                    errors += 1
                    continue

                with open(fit_path, "rb") as f:
                    fit_data = f.read()

                parsed_data = adapter.parse_fit_file(fit_data)

                # Store samples
                records = parsed_data.get("records", [])
                samples_to_add = []

                for record in records:
                    timestamp_raw = record.get("timestamp")
                    if not timestamp_raw:
                        continue

                    # Convert string timestamp to datetime if needed
                    if isinstance(timestamp_raw, str):
                        timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
                    else:
                        timestamp = timestamp_raw

                    # Convert semicircles to degrees if needed
                    latitude = record.get("position_lat")
                    longitude = record.get("position_long")
                    if latitude is not None and abs(latitude) > 180:
                        latitude = latitude * (180 / 2**31)
                    if longitude is not None and abs(longitude) > 180:
                        longitude = longitude * (180 / 2**31)

                    sample = ActivitySample(
                        activity_id=activity.id,
                        timestamp=timestamp,
                        hr=record.get("heart_rate"),
                        heart_rate=record.get("heart_rate"),
                        cadence=record.get("cadence"),
                        speed=record.get("enhanced_speed"),
                        latitude=latitude,
                        longitude=longitude,
                        altitude=record.get("enhanced_altitude"),
                        power=record.get("power"),
                        distance_meters=record.get("distance"),
                        ground_contact_time=record.get("stance_time"),
                        vertical_oscillation=record.get("vertical_oscillation"),
                        stride_length=record.get("step_length"),
                    )
                    samples_to_add.append(sample)

                if samples_to_add:
                    session.add_all(samples_to_add)
                    await session.commit()
                    logger.info(f"Activity {activity.id}: Stored {len(samples_to_add)} samples")
                    processed += 1
                else:
                    logger.warning(f"Activity {activity.id}: No samples to store")
                    skipped += 1

            except Exception as e:
                logger.error(f"Error processing activity {activity.id}: {e}")
                errors += 1
                await session.rollback()

        logger.info(f"Done! Processed: {processed}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(reparse_fit_files())
