#!/usr/bin/env python3
"""Re-parse FIT files and store laps for existing activities.

Run from backend directory:
    python scripts/reparse_fit_laps.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from app.adapters.garmin_adapter import GarminConnectAdapter
from app.core.database import async_session_maker
from app.models.activity import Activity, ActivityLap

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def reparse_fit_laps():
    """Re-parse all FIT files and store laps."""
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
        total_laps = 0

        for activity in activities:
            try:
                # Check if laps already exist
                lap_check = await session.execute(
                    select(ActivityLap).where(ActivityLap.activity_id == activity.id).limit(1)
                )
                if lap_check.scalar_one_or_none():
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

                # Store laps
                fit_laps = parsed_data.get("laps", [])
                laps_to_add = []

                for idx, lap_data in enumerate(fit_laps, start=1):
                    # Parse start_time
                    start_time_raw = lap_data.get("start_time") or lap_data.get("timestamp")
                    start_time = None
                    if start_time_raw:
                        if isinstance(start_time_raw, str):
                            start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
                        else:
                            start_time = start_time_raw

                    # Calculate pace from distance and time
                    # 중요: total_timer_time = 순수 러닝 시간 (일시정지 제외)
                    #       total_elapsed_time = 전체 경과 시간 (일시정지 포함)
                    # 페이스 계산에는 timer_time을 사용해야 정확함
                    distance = lap_data.get("total_distance")
                    timer_time = lap_data.get("total_timer_time")  # 순수 러닝 시간
                    elapsed_time = lap_data.get("total_elapsed_time")  # 전체 경과 시간

                    # 페이스 계산에는 timer_time 사용
                    duration_for_pace = timer_time or elapsed_time
                    avg_pace_seconds = None
                    if distance and duration_for_pace and distance > 0:
                        # pace = seconds per km
                        avg_pace_seconds = int((duration_for_pace / distance) * 1000)

                    lap = ActivityLap(
                        activity_id=activity.id,
                        lap_number=idx,
                        start_time=start_time,
                        duration_seconds=timer_time or elapsed_time,  # 표시용도 timer_time 사용
                        distance_meters=distance,
                        avg_hr=lap_data.get("avg_heart_rate"),
                        max_hr=lap_data.get("max_heart_rate"),
                        avg_cadence=lap_data.get("avg_running_cadence") or lap_data.get("avg_cadence"),
                        max_cadence=lap_data.get("max_running_cadence") or lap_data.get("max_cadence"),
                        avg_pace_seconds=avg_pace_seconds,
                        total_ascent_meters=lap_data.get("total_ascent"),
                        total_descent_meters=lap_data.get("total_descent"),
                        calories=lap_data.get("total_calories"),
                    )
                    laps_to_add.append(lap)

                if laps_to_add:
                    session.add_all(laps_to_add)
                    await session.commit()
                    logger.info(f"Activity {activity.id}: Stored {len(laps_to_add)} laps")
                    processed += 1
                    total_laps += len(laps_to_add)
                else:
                    logger.warning(f"Activity {activity.id}: No laps to store")
                    skipped += 1

            except Exception as e:
                logger.error(f"Error processing activity {activity.id}: {e}")
                errors += 1
                await session.rollback()

        logger.info(f"Done! Processed: {processed}, Skipped: {skipped}, Errors: {errors}")
        logger.info(f"Total laps stored: {total_laps}")


if __name__ == "__main__":
    asyncio.run(reparse_fit_laps())
