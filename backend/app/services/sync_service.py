"""Garmin data synchronization service.

This module provides a clean, well-structured synchronization pipeline
for fetching and storing Garmin data.
"""

import logging
import math
import time
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Any, Optional, Callable

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models import (
    User,
    GarminSession,
    GarminSyncState,
    GarminRawEvent,
    GarminRawFile,
    Activity,
    Sleep,
    HRRecord,
    BodyComposition,
)
from app.models.activity import ActivitySample, ActivityLap, ActivityMetric
from app.models.gear import Gear, ActivityGear, GearType, GearStatus
from app.adapters.garmin_adapter import GarminConnectAdapter
from app.core.config import get_settings
from app.observability import get_metrics_backend

settings = get_settings()

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.success = False
        self.items_fetched = 0
        self.items_created = 0
        self.items_updated = 0
        self.error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "success": self.success,
            "items_fetched": self.items_fetched,
            "items_created": self.items_created,
            "items_updated": self.items_updated,
            "error": self.error,
        }


class GarminSyncService:
    """Service for synchronizing Garmin data."""

    ENDPOINTS = [
        "gear",  # Sync gear first, before activities for activity-gear linking
        "activities",
        "sleep",
        "heart_rate",
        "body_battery",
        "stress",
        "hrv",
        "respiration",
        "spo2",
        "training_status",
        "max_metrics",
        "stats",
        "race_predictions",
        "personal_records",
        "goals",
        # "body_composition",  # Not available in current garminconnect library
    ]

    def __init__(
        self,
        session: AsyncSession,
        adapter: GarminConnectAdapter,
        user: User,
        fit_storage_path: Optional[str] = None,
    ):
        self.session = session
        self.adapter = adapter
        self.user = user
        # Use settings.fit_storage_path if not explicitly provided
        self.fit_storage_path = Path(fit_storage_path or settings.fit_storage_path)
        self.fit_storage_path.mkdir(parents=True, exist_ok=True)
        self.metrics = get_metrics_backend()

    async def sync_user_profile(self) -> bool:
        """Sync user profile data including max HR settings from Garmin.

        Returns:
            True if max HR was updated, False otherwise.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            profile_data = await loop.run_in_executor(
                None,
                self.adapter.get_user_profile,
            )

            if profile_data:
                await self._store_raw_event("user_profile", profile_data, flush=False)

            # Garmin user summary에서 maxHr 추출
            max_hr = profile_data.get("userDailySummary", {}).get("maxHeartRate")
            if not max_hr:
                max_hr = profile_data.get("maxHeartRate")

            if max_hr and max_hr != self.user.max_hr:
                self.user.max_hr = max_hr
                await self.session.commit()
                logger.info(f"Updated max HR for user {self.user.id}: {max_hr}")
                return True

        except Exception as e:
            logger.warning(f"Failed to sync user profile: {e}")

        return False

    async def sync_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        full_backfill: bool = False,
    ) -> dict[str, SyncResult]:
        """Sync all endpoints.

        Args:
            start_date: Start date for sync (default: last sync or 30 days ago)
            end_date: End date for sync (default: today)
            full_backfill: If True, ignore last sync state and fetch all data

        Returns:
            Dictionary of endpoint -> SyncResult
        """
        results = {}

        # 먼저 사용자 프로필 동기화 (max HR 등)
        await self.sync_user_profile()

        for endpoint in self.ENDPOINTS:
            try:
                result = await self.sync_endpoint(
                    endpoint,
                    start_date=start_date,
                    end_date=end_date,
                    full_backfill=full_backfill,
                )
                results[endpoint] = result
            except Exception as e:
                logger.exception(f"Error syncing {endpoint}")
                result = SyncResult(endpoint)
                result.error = str(e)
                results[endpoint] = result

        return results

    async def sync_endpoint(
        self,
        endpoint: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        full_backfill: bool = False,
    ) -> SyncResult:
        """Sync a single endpoint.

        Args:
            endpoint: The endpoint to sync (activities, sleep, heart_rate, body_battery, stress,
                hrv, respiration, spo2, training_status, max_metrics, stats, race_predictions,
                personal_records, goals, body_composition)
            start_date: Start date for sync
            end_date: End date for sync
            full_backfill: If True, ignore last sync state

        Returns:
            SyncResult with operation details
        """
        result = SyncResult(endpoint)

        # Determine date range based on settings
        # garmin_safety_window_days: overlap period for incremental sync (default: 3)
        # garmin_backfill_days: initial backfill period (0 = full history, default: 0)
        safety_window = settings.garmin_safety_window_days
        backfill_days = settings.garmin_backfill_days

        if not full_backfill:
            sync_state = await self._get_sync_state(endpoint)
            if sync_state and sync_state.last_success_at and not start_date:
                # Use safety window from settings for incremental sync
                start_date = sync_state.last_success_at.date() - timedelta(days=safety_window)

        if not start_date:
            # Use backfill_days from settings (0 means as far back as possible)
            if backfill_days > 0:
                start_date = date.today() - timedelta(days=backfill_days)
            else:
                # Full history: go back 10 years (practical limit)
                start_date = date.today() - timedelta(days=365 * 10)
        if not end_date:
            end_date = date.today()

        logger.info(f"Syncing {endpoint} for user {self.user.id}: {start_date} to {end_date}")

        start_time = time.perf_counter()
        try:
            # Dispatch to appropriate sync method
            if endpoint == "gear":
                await self._sync_gear(result)
            elif endpoint == "activities":
                await self._sync_activities(result, start_date, end_date)
            elif endpoint == "sleep":
                await self._sync_sleep(result, start_date, end_date)
            elif endpoint == "heart_rate":
                await self._sync_heart_rate(result, start_date, end_date)
            elif endpoint == "body_battery":
                await self._sync_body_battery(result, start_date, end_date)
            elif endpoint == "stress":
                await self._sync_stress(result, start_date, end_date)
            elif endpoint == "hrv":
                await self._sync_hrv(result, start_date, end_date)
            elif endpoint == "respiration":
                await self._sync_respiration(result, start_date, end_date)
            elif endpoint == "spo2":
                await self._sync_spo2(result, start_date, end_date)
            elif endpoint == "training_status":
                await self._sync_training_status(result, start_date, end_date)
            elif endpoint == "max_metrics":
                await self._sync_max_metrics(result, start_date, end_date)
            elif endpoint == "stats":
                await self._sync_stats(result, start_date, end_date)
            elif endpoint == "race_predictions":
                await self._sync_race_predictions(result, start_date, end_date)
            elif endpoint == "personal_records":
                await self._sync_personal_records(result)
            elif endpoint == "goals":
                await self._sync_goals(result)
            elif endpoint == "body_composition":
                await self._sync_body_composition(result, start_date, end_date)
            else:
                raise ValueError(f"Unknown endpoint: {endpoint}")

            # Update sync state
            await self._update_sync_state(endpoint, success=True)
            result.success = True

        except Exception as e:
            logger.exception(f"Error syncing {endpoint}")
            result.error = str(e)
            await self._update_sync_state(endpoint, success=False)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self.metrics.observe_sync_job(
            endpoint,
            result.success,
            duration_ms,
            items_fetched=result.items_fetched,
            items_created=result.items_created,
            items_updated=result.items_updated,
        )
        logger.info(
            "Sync finished for user %s endpoint %s success=%s fetched=%s created=%s updated=%s duration_ms=%.2f",
            self.user.id,
            endpoint,
            result.success,
            result.items_fetched,
            result.items_created,
            result.items_updated,
            duration_ms,
        )
        return result

    async def _sync_activities(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        """Sync activities from Garmin."""
        import asyncio
        loop = asyncio.get_event_loop()

        # Run synchronous adapter method in thread pool
        activities_data = await loop.run_in_executor(
            None,
            lambda: self.adapter.get_activities(start_date, end_date),
        )

        if not activities_data:
            return

        result.items_fetched = len(activities_data)

        # Store raw event
        raw_event = await self._store_raw_event("activities", activities_data)

        for act_data in activities_data:
            garmin_id = act_data.get("activityId")
            if not garmin_id:
                continue

            try:
                details = await loop.run_in_executor(
                    None,
                    lambda act_id=garmin_id: self.adapter.get_activity_details(act_id),
                )
                if details:
                    await self._store_raw_event("activity_details", details, flush=False)
            except Exception as e:
                logger.warning(f"Failed to fetch activity details for {garmin_id}: {e}")

            # Check if activity exists
            existing = await self.session.execute(
                select(Activity).where(
                    and_(
                        Activity.user_id == self.user.id,
                        Activity.garmin_id == garmin_id,
                    )
                )
            )
            activity = existing.scalar_one_or_none()

            if activity:
                # Update existing
                await self._update_activity(activity, act_data)
                result.items_updated += 1
            else:
                # Create new
                activity = await self._create_activity(act_data, raw_event_id=raw_event.id)
                result.items_created += 1

            # Download FIT file if not already downloaded
            if not activity.has_fit_file:
                await self._download_fit_file(activity, garmin_id)

            # Link activity to gear (shoes, etc.)
            await self._link_activity_gear(activity, garmin_id)

        await self.session.commit()

    async def _sync_daily_raw(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
        endpoint: str,
        fetcher: Callable[[date], Any],
    ) -> None:
        """Sync daily Garmin endpoints with optimized batch processing.

        Performance optimizations:
        1. Process dates in reverse order (most recent first)
        2. Early termination: stop after N consecutive empty responses
        3. Batch commits for better DB performance

        For full backfill scenarios (e.g., 10 years = 3650 days),
        this approach stops early when historical data runs out.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        # Process dates in reverse order (most recent first)
        total_days = (end_date - start_date).days + 1
        dates_to_sync = [end_date - timedelta(days=i) for i in range(total_days)]

        # Early termination settings
        max_consecutive_empty = settings.garmin_max_consecutive_empty  # default: 30
        consecutive_empty = 0
        batch_size = 50  # Commit every 50 records

        items_in_batch = 0

        for current_date in dates_to_sync:
            try:
                data = await loop.run_in_executor(
                    None,
                    lambda d=current_date: fetcher(d),
                )
                if data:
                    result.items_fetched += 1
                    await self._store_raw_event(endpoint, data, flush=False)
                    result.items_created += 1
                    consecutive_empty = 0  # Reset on success
                    items_in_batch += 1

                    # Batch commit
                    if items_in_batch >= batch_size:
                        await self.session.commit()
                        items_in_batch = 0
                else:
                    consecutive_empty += 1

            except Exception as e:
                logger.warning(f"Failed to fetch {endpoint} for {current_date}: {e}")
                consecutive_empty += 1

            # Early termination: stop if too many consecutive empty days
            if consecutive_empty >= max_consecutive_empty:
                logger.info(
                    f"Early termination for {endpoint}: {consecutive_empty} consecutive "
                    f"empty responses at {current_date}. Likely reached data boundary."
                )
                break

        await self.session.commit()

    async def _sync_single_raw(
        self,
        result: SyncResult,
        endpoint: str,
        fetcher: Callable[[], Any],
    ) -> None:
        """Sync single-call Garmin endpoints and store raw data only."""
        import asyncio

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            fetcher,
        )
        if not data:
            return

        if isinstance(data, list):
            result.items_fetched = len(data)
        else:
            result.items_fetched = 1

        await self._store_raw_event(endpoint, data, flush=False)
        result.items_created = 1
        await self.session.commit()

    async def _sync_body_battery(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "body_battery",
            self.adapter.get_body_battery,
        )

    async def _sync_stress(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "stress",
            self.adapter.get_stress_data,
        )

    async def _sync_hrv(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "hrv",
            self.adapter.get_hrv_data,
        )

    async def _sync_respiration(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "respiration",
            self.adapter.get_respiration_data,
        )

    async def _sync_spo2(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "spo2",
            self.adapter.get_spo2_data,
        )

    async def _sync_training_status(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "training_status",
            self.adapter.get_training_status,
        )

    async def _sync_max_metrics(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "max_metrics",
            self.adapter.get_max_metrics,
        )

    async def _sync_stats(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_daily_raw(
            result,
            start_date,
            end_date,
            "stats",
            self.adapter.get_stats,
        )

    async def _sync_race_predictions(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        await self._sync_single_raw(
            result,
            "race_predictions",
            lambda: self.adapter.get_race_predictions(start_date, end_date),
        )

    async def _sync_personal_records(
        self,
        result: SyncResult,
    ) -> None:
        await self._sync_single_raw(
            result,
            "personal_records",
            self.adapter.get_personal_records,
        )

    async def _sync_goals(
        self,
        result: SyncResult,
    ) -> None:
        await self._sync_single_raw(
            result,
            "goals",
            self.adapter.get_goals,
        )

    async def _create_activity(
        self,
        data: dict[str, Any],
        raw_event_id: Optional[int] = None,
    ) -> Activity:
        """Create a new activity from Garmin data."""
        # Parse start time
        start_time_str = data.get("startTimeLocal") or data.get("startTimeGMT")
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")) if start_time_str else datetime.now(timezone.utc)

        # Calculate pace if speed is available
        avg_pace_seconds = None
        best_pace_seconds = None
        avg_speed = data.get("averageSpeed")
        max_speed = data.get("maxSpeed")
        if avg_speed and avg_speed > 0:
            avg_pace_seconds = int(1000 / avg_speed)  # seconds per km
        if max_speed and max_speed > 0:
            best_pace_seconds = int(1000 / max_speed)

        activity = Activity(
            user_id=self.user.id,
            garmin_id=data.get("activityId"),
            raw_event_id=raw_event_id,
            activity_type=data.get("activityType", {}).get("typeKey", "running"),
            name=data.get("activityName"),
            description=data.get("description"),  # User notes/memo from Garmin
            start_time=start_time,
            duration_seconds=int(data.get("duration", 0)),
            elapsed_seconds=int(data.get("elapsedDuration", 0)) if data.get("elapsedDuration") else None,
            distance_meters=data.get("distance"),
            calories=data.get("calories"),
            avg_hr=data.get("averageHR"),
            max_hr=data.get("maxHR"),
            avg_pace_seconds=avg_pace_seconds,
            best_pace_seconds=best_pace_seconds,
            elevation_gain=data.get("elevationGain"),
            elevation_loss=data.get("elevationLoss"),
            avg_cadence=int(data.get("averageRunningCadenceInStepsPerMinute", 0)) if data.get("averageRunningCadenceInStepsPerMinute") else None,
            max_cadence=int(data.get("maxRunningCadenceInStepsPerMinute", 0)) if data.get("maxRunningCadenceInStepsPerMinute") else None,
            training_effect_aerobic=data.get("aerobicTrainingEffect"),
            training_effect_anaerobic=data.get("anaerobicTrainingEffect"),
            vo2max=data.get("vO2MaxValue"),
        )

        self.session.add(activity)
        await self.session.flush()

        return activity

    async def _update_activity(self, activity: Activity, data: dict[str, Any]) -> None:
        """Update an existing activity with new data."""
        # Update fields that may have changed
        activity.name = data.get("activityName") or activity.name
        activity.description = data.get("description") or activity.description
        activity.calories = data.get("calories") or activity.calories
        activity.vo2max = data.get("vO2MaxValue") or activity.vo2max

    async def _download_fit_file(self, activity: Activity, garmin_id: int) -> None:
        """Download, parse, and store FIT file for an activity."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()

            # Create user directory
            user_dir = self.fit_storage_path / str(self.user.id)
            user_dir.mkdir(exist_ok=True)

            # Run synchronous download in thread pool
            # download_fit_file returns (bytes, file_path, file_hash)
            fit_data, file_path, file_hash = await loop.run_in_executor(
                None,
                lambda: self.adapter.download_fit_file(garmin_id, str(user_dir)),
            )

            if not fit_data:
                return

            # Update activity
            activity.fit_file_path = file_path
            activity.fit_file_hash = file_hash
            activity.has_fit_file = True

            # Create raw file record
            raw_file = GarminRawFile(
                user_id=self.user.id,
                activity_id=activity.id,
                file_type="fit",
                file_path=file_path,
                file_hash=file_hash,
            )
            self.session.add(raw_file)

            # Parse FIT file and store samples/laps
            try:
                parsed_data = await loop.run_in_executor(
                    None,
                    lambda: self.adapter.parse_fit_file(fit_data),
                )
                await self._store_fit_data(activity, parsed_data)
            except Exception as parse_error:
                logger.warning(f"Failed to parse FIT file for activity {garmin_id}: {parse_error}")

            logger.info(f"Downloaded and parsed FIT file for activity {garmin_id}")

        except Exception as e:
            logger.warning(f"Failed to download FIT file for activity {garmin_id}: {e}")

    async def _store_fit_data(self, activity: Activity, parsed_data: dict[str, Any]) -> None:
        """Store parsed FIT data as samples and laps.

        Args:
            activity: Activity to attach data to.
            parsed_data: Parsed FIT data from adapter.parse_fit_file()
        """
        # Store records as ActivitySample
        records = parsed_data.get("records", [])
        if records:
            samples_to_add = []
            for record in records:
                timestamp = record.get("timestamp")
                if not timestamp:
                    continue

                # Parse timestamp if it's a string
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

                # Calculate pace from speed (m/s -> seconds per km)
                pace_seconds = None
                speed = record.get("enhanced_speed") or record.get("speed")
                if speed and speed > 0:
                    pace_seconds = int(1000 / speed)

                # Convert semicircle coordinates to degrees if needed
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
                    pace_seconds=pace_seconds,
                    speed=speed,
                    cadence=record.get("cadence"),
                    power=record.get("power"),
                    latitude=latitude,
                    longitude=longitude,
                    altitude=record.get("enhanced_altitude") or record.get("altitude"),
                    distance_meters=record.get("distance"),
                    ground_contact_time=record.get("ground_contact_time") or record.get("stance_time"),
                    vertical_oscillation=record.get("vertical_oscillation"),
                    stride_length=record.get("step_length"),
                )
                samples_to_add.append(sample)

            if samples_to_add:
                self.session.add_all(samples_to_add)
                logger.info(f"Stored {len(samples_to_add)} samples for activity {activity.id}")

        # Store laps as ActivityLap
        laps = parsed_data.get("laps", [])
        if laps:
            laps_to_add = []
            for i, lap in enumerate(laps, 1):
                start_time = lap.get("start_time") or lap.get("timestamp")
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

                # Calculate pace from speed
                avg_pace_seconds = None
                avg_speed = lap.get("enhanced_avg_speed") or lap.get("avg_speed")
                if avg_speed and avg_speed > 0:
                    avg_pace_seconds = int(1000 / avg_speed)

                lap_record = ActivityLap(
                    activity_id=activity.id,
                    lap_number=i,
                    start_time=start_time,
                    duration_seconds=lap.get("total_timer_time") or lap.get("total_elapsed_time"),
                    distance_meters=lap.get("total_distance"),
                    avg_hr=lap.get("avg_heart_rate"),
                    max_hr=lap.get("max_heart_rate"),
                    avg_cadence=lap.get("avg_cadence"),
                    max_cadence=lap.get("max_cadence"),
                    avg_pace_seconds=avg_pace_seconds,
                    total_ascent_meters=lap.get("total_ascent"),
                    total_descent_meters=lap.get("total_descent"),
                    calories=lap.get("total_calories"),
                )
                laps_to_add.append(lap_record)

            if laps_to_add:
                self.session.add_all(laps_to_add)
                logger.info(f"Stored {len(laps_to_add)} laps for activity {activity.id}")

        # Update activity with session-level data from FIT
        session_data = parsed_data.get("session", {})
        if session_data:
            # Training metrics
            if session_data.get("training_stress_score"):
                activity.training_stress_score = session_data["training_stress_score"]
            if session_data.get("intensity_factor"):
                activity.intensity_factor = session_data["intensity_factor"]

            # Running dynamics
            if session_data.get("avg_ground_contact_time"):
                activity.avg_ground_contact_time = int(session_data["avg_ground_contact_time"])
            if session_data.get("avg_vertical_oscillation"):
                activity.avg_vertical_oscillation = session_data["avg_vertical_oscillation"]
            if session_data.get("avg_step_length"):
                activity.avg_stride_length = session_data["avg_step_length"]

            # Power
            if session_data.get("normalized_power"):
                activity.normalized_power = int(session_data["normalized_power"])
            if session_data.get("avg_power"):
                activity.avg_power = int(session_data["avg_power"])
            if session_data.get("max_power"):
                activity.max_power = int(session_data["max_power"])

        # Update sensor detection flags from FIT device_info
        sensors = parsed_data.get("sensors", {})
        if sensors.get("has_stryd"):
            activity.has_stryd = True
            logger.info(f"Stryd detected for activity {activity.id}")

            # Calculate Stryd metrics from records (session data often missing for Stryd)
            power_values = [r["power"] for r in records if r.get("power")]
            form_powers = [r["form_power"] for r in records if r.get("form_power")]
            lss_values = [r["leg_spring_stiffness"] for r in records if r.get("leg_spring_stiffness")]

            # Power (main running power from Stryd)
            if power_values and not activity.avg_power:
                activity.avg_power = int(sum(power_values) / len(power_values))
                activity.max_power = max(power_values)
                logger.info(f"Stryd Power: avg={activity.avg_power}W, max={activity.max_power}W")

            # Form Power (Stryd-specific)
            if form_powers:
                activity.avg_form_power = int(sum(form_powers) / len(form_powers))
                logger.info(f"Avg Form Power: {activity.avg_form_power}W")

            # Leg Spring Stiffness
            if lss_values:
                activity.avg_leg_spring_stiffness = round(sum(lss_values) / len(lss_values), 2)
                logger.info(f"Avg LSS: {activity.avg_leg_spring_stiffness} kN/m")

        if sensors.get("has_external_hr"):
            activity.has_external_hr = True
            logger.info(f"External HR monitor detected for activity {activity.id}")

        # Calculate and store derived metrics (TRIMP, EF, etc.)
        await self._calculate_and_store_metrics(activity, records)

    async def _calculate_and_store_metrics(
        self,
        activity: Activity,
        records: list[dict[str, Any]],
    ) -> None:
        """Calculate TRIMP, Efficiency Factor, and other derived metrics.

        TRIMP (Training Impulse) = duration (min) * HR ratio * 0.64 * e^(1.92 * HR ratio)
        where HR ratio = (avgHR - restHR) / (maxHR - restHR)

        Efficiency Factor = normalized speed / avg HR

        Args:
            activity: Activity to calculate metrics for.
            records: Parsed FIT records with HR data.
        """
        try:
            # Get user's max HR (from profile or estimate)
            max_hr = self.user.max_hr or 220 - (self.user.age or 30)
            rest_hr = self.user.resting_hr or 60  # Default resting HR

            # Calculate TRIMP using HR data from records
            trimp = None
            if records and activity.duration_seconds:
                hr_values = [
                    r.get("heart_rate")
                    for r in records
                    if r.get("heart_rate") and r["heart_rate"] > 0
                ]
                if hr_values:
                    avg_hr = sum(hr_values) / len(hr_values)
                    hr_reserve = max_hr - rest_hr
                    if hr_reserve > 0:
                        hr_ratio = (avg_hr - rest_hr) / hr_reserve
                        hr_ratio = max(0, min(1, hr_ratio))  # Clamp 0-1
                        duration_min = activity.duration_seconds / 60
                        # Banister's TRIMP formula (gender factor 1.92 for male, 1.67 for female)
                        gender_factor = 1.92  # Default to male
                        trimp = duration_min * hr_ratio * 0.64 * math.exp(gender_factor * hr_ratio)
                        trimp = round(trimp, 1)

            # Calculate Efficiency Factor (EF)
            # EF = Normalized Pace / Avg HR (or Normalized Power / Avg HR for cycling)
            efficiency_factor = None
            if activity.avg_hr and activity.avg_hr > 0:
                if activity.normalized_power:
                    # Power-based EF
                    efficiency_factor = round(activity.normalized_power / activity.avg_hr, 3)
                elif activity.distance_meters and activity.duration_seconds:
                    # Speed-based EF (m/min / bpm)
                    speed_m_min = (activity.distance_meters / activity.duration_seconds) * 60
                    efficiency_factor = round(speed_m_min / activity.avg_hr, 3)

            # Get TSS from activity (already calculated from FIT)
            tss = activity.training_stress_score

            # Get training effect (average of aerobic and anaerobic)
            training_effect = None
            if activity.training_effect_aerobic:
                training_effect = activity.training_effect_aerobic
                if activity.training_effect_anaerobic:
                    training_effect = (training_effect + activity.training_effect_anaerobic) / 2

            # Upsert ActivityMetric
            stmt = insert(ActivityMetric).values(
                activity_id=activity.id,
                trimp=trimp,
                tss=tss,
                training_effect=training_effect,
                vo2max_est=activity.vo2max,
                efficiency_factor=efficiency_factor,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["activity_id"],
                set_={
                    "trimp": stmt.excluded.trimp,
                    "tss": stmt.excluded.tss,
                    "training_effect": stmt.excluded.training_effect,
                    "vo2max_est": stmt.excluded.vo2max_est,
                    "efficiency_factor": stmt.excluded.efficiency_factor,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            await self.session.execute(stmt)
            logger.info(
                f"Stored metrics for activity {activity.id}: "
                f"TRIMP={trimp}, TSS={tss}, EF={efficiency_factor}"
            )

        except Exception as e:
            logger.warning(f"Failed to calculate metrics for activity {activity.id}: {e}")

    async def _sync_sleep(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        """Sync sleep data from Garmin."""
        import asyncio

        loop = asyncio.get_event_loop()
        current_date = start_date

        while current_date <= end_date:
            try:
                # Run synchronous adapter method in thread pool
                sleep_data = await loop.run_in_executor(
                    None,
                    lambda d=current_date: self.adapter.get_sleep_data(d),
                )
                if sleep_data:
                    result.items_fetched += 1
                    raw_event = await self._store_raw_event("sleep", sleep_data)
                    await self._store_sleep(
                        sleep_data,
                        current_date,
                        raw_event_id=raw_event.id,
                    )
                    result.items_created += 1
            except Exception as e:
                logger.warning(f"Failed to fetch sleep for {current_date}: {e}")

            current_date += timedelta(days=1)

        await self.session.commit()

    async def _store_sleep(
        self,
        data: dict[str, Any],
        sleep_date: date,
        raw_event_id: Optional[int] = None,
    ) -> None:
        """Store or update sleep record."""
        # Use upsert pattern
        stmt = insert(Sleep).values(
            user_id=self.user.id,
            date=sleep_date,
            duration_seconds=data.get("sleepTimeSeconds"),
            score=data.get("overallSleepScore"),
            stages={
                "deep": data.get("deepSleepSeconds"),
                "light": data.get("lightSleepSeconds"),
                "rem": data.get("remSleepSeconds"),
                "awake": data.get("awakeSleepSeconds"),
            },
            raw_event_id=raw_event_id,
        )
        update_values = {
            "duration_seconds": stmt.excluded.duration_seconds,
            "score": stmt.excluded.score,
            "stages": stmt.excluded.stages,
            "updated_at": datetime.now(timezone.utc),
        }
        if raw_event_id is not None:
            update_values["raw_event_id"] = stmt.excluded.raw_event_id
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sleep_user_date",
            set_=update_values,
        )
        await self.session.execute(stmt)

    async def _sync_heart_rate(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        """Sync heart rate data from Garmin."""
        import asyncio

        loop = asyncio.get_event_loop()
        current_date = start_date

        while current_date <= end_date:
            try:
                # Run synchronous adapter method in thread pool
                hr_data = await loop.run_in_executor(
                    None,
                    lambda d=current_date: self.adapter.get_heart_rate(d),
                )
                if hr_data:
                    result.items_fetched += 1
                    raw_event = await self._store_raw_event("heart_rate", hr_data)
                    await self._store_heart_rate(
                        hr_data,
                        current_date,
                        raw_event_id=raw_event.id,
                    )
                    result.items_created += 1
            except Exception as e:
                logger.warning(f"Failed to fetch heart rate for {current_date}: {e}")

            current_date += timedelta(days=1)

        await self.session.commit()

    async def _store_heart_rate(
        self,
        data: dict[str, Any],
        hr_date: date,
        raw_event_id: Optional[int] = None,
    ) -> None:
        """Store or update heart rate record using upsert."""
        stmt = insert(HRRecord).values(
            user_id=self.user.id,
            date=hr_date,
            start_time=datetime.combine(hr_date, datetime.min.time()),
            end_time=datetime.combine(hr_date, datetime.max.time()),
            avg_hr=data.get("restingHeartRate"),
            max_hr=data.get("maxHeartRate"),
            resting_hr=data.get("restingHeartRate"),
            samples=data.get("heartRateValues"),
            raw_event_id=raw_event_id,
        )
        update_values = {
            "avg_hr": stmt.excluded.avg_hr,
            "max_hr": stmt.excluded.max_hr,
            "resting_hr": stmt.excluded.resting_hr,
            "samples": stmt.excluded.samples,
            "updated_at": datetime.now(timezone.utc),
        }
        if raw_event_id is not None:
            update_values["raw_event_id"] = stmt.excluded.raw_event_id
        stmt = stmt.on_conflict_do_update(
            constraint="uq_hr_record_user_date",
            set_=update_values,
        )
        await self.session.execute(stmt)

    async def _sync_body_composition(
        self,
        result: SyncResult,
        start_date: date,
        end_date: date,
    ) -> None:
        """Sync body composition data from Garmin.

        Note: Currently disabled as garminconnect library doesn't provide
        a direct get_body_composition method. May be available via get_weigh_ins
        in future versions.
        """
        logger.info("Body composition sync not available in current adapter")
        result.success = True

    async def _store_body_composition(self, data: dict[str, Any]) -> None:
        """Store or update body composition record."""
        date_str = data.get("calendarDate") or data.get("measurementDate")
        if not date_str:
            return

        record_date = date.fromisoformat(date_str)

        # Convert weight from grams to kg if needed
        weight = data.get("weight")
        if weight and weight > 500:  # Likely in grams
            weight = weight / 1000

        stmt = insert(BodyComposition).values(
            user_id=self.user.id,
            date=record_date,
            weight_kg=weight,
            body_fat_pct=data.get("bodyFatPercentage"),
            muscle_mass_kg=data.get("muscleMass"),
            bmi=data.get("bmi"),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_body_composition_user_date",
            set_={
                "weight_kg": stmt.excluded.weight_kg,
                "body_fat_pct": stmt.excluded.body_fat_pct,
                "muscle_mass_kg": stmt.excluded.muscle_mass_kg,
                "bmi": stmt.excluded.bmi,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await self.session.execute(stmt)

    async def _store_raw_event(
        self,
        endpoint: str,
        payload: Any,
        flush: bool = True,
    ) -> GarminRawEvent:
        """Store raw API response."""
        raw_event = GarminRawEvent(
            user_id=self.user.id,
            endpoint=endpoint,
            fetched_at=datetime.now(timezone.utc),
            payload=payload if isinstance(payload, dict) else {"data": payload},
        )
        self.session.add(raw_event)
        if flush:
            await self.session.flush()
        return raw_event

    async def _get_sync_state(self, endpoint: str) -> Optional[GarminSyncState]:
        """Get sync state for an endpoint."""
        result = await self.session.execute(
            select(GarminSyncState).where(
                and_(
                    GarminSyncState.user_id == self.user.id,
                    GarminSyncState.endpoint == endpoint,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _sync_gear(self, result: SyncResult) -> None:
        """Sync gear (shoes, bikes, etc.) from Garmin.

        Fetches user's gear list and creates/updates local Gear records.
        Gear sync is performed before activities to enable activity-gear linking.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        try:
            # Get user profile to get userProfileNumber for gear API
            profile_data = await loop.run_in_executor(
                None,
                self.adapter.get_user_profile,
            )
            # The profile 'id' field is the userProfileNumber needed for gear API
            user_profile_number = str(
                profile_data.get("id")
                or profile_data.get("displayName")
                or profile_data.get("userName")
            )
            if not user_profile_number or user_profile_number == "None":
                logger.warning(f"No user profile number found for gear sync. Keys: {list(profile_data.keys())}")
                return

            logger.info(f"Using profile number {user_profile_number} for gear sync")

            # Fetch gear list from Garmin
            gear_list = await loop.run_in_executor(
                None,
                lambda: self.adapter.get_gear(user_profile_number),
            )

            if not gear_list:
                logger.info(f"No gear found for user {self.user.id}")
                return

            result.items_fetched = len(gear_list)

            # Store raw event
            await self._store_raw_event("gear", gear_list, flush=False)

            for gear_data in gear_list:
                garmin_uuid = gear_data.get("uuid") or gear_data.get("gearUUID")
                if not garmin_uuid:
                    continue

                # Get gear stats for distance (stored in initial_distance_meters)
                gear_stats = await loop.run_in_executor(
                    None,
                    lambda uuid=garmin_uuid: self.adapter.get_gear_stats(uuid),
                )
                # Garmin's totalDistance is the cumulative distance tracked by Garmin
                garmin_distance = gear_stats.get("totalDistance", 0) or 0  # in meters
                # Try different key names for activity count
                garmin_activity_count = (
                    gear_stats.get("totalActivities")
                    or gear_stats.get("activityCount")
                    or gear_stats.get("activities")
                    or 0
                )

                # Check if gear exists
                existing = await self.session.execute(
                    select(Gear).where(Gear.garmin_uuid == garmin_uuid)
                )
                gear = existing.scalar_one_or_none()

                # Map Garmin gear type to our GearType
                garmin_type = gear_data.get("gearTypeName", "").lower()
                if "shoe" in garmin_type or "running" in garmin_type:
                    gear_type = GearType.RUNNING_SHOES.value
                elif "bike" in garmin_type or "cycling" in garmin_type:
                    gear_type = GearType.BIKE.value
                else:
                    gear_type = GearType.OTHER.value

                # Determine status from gearStatusName field
                garmin_status = gear_data.get("gearStatusName", "").lower()
                status = GearStatus.ACTIVE.value
                if garmin_status == "retired" or gear_data.get("retired"):
                    status = GearStatus.RETIRED.value

                if gear:
                    # Update existing gear
                    gear.name = gear_data.get("displayName") or gear_data.get("customMakeModel") or gear.name
                    gear.brand = gear_data.get("gearMakeName") if gear_data.get("gearMakeName") != "Other" else gear.brand
                    gear.gear_type = gear_type
                    gear.status = status
                    # Store Garmin's tracked distance as initial_distance_meters
                    # This will be added to local activity distances in the API
                    gear.initial_distance_meters = garmin_distance
                    gear.garmin_activity_count = garmin_activity_count
                    if gear_data.get("maximumMeters"):
                        gear.max_distance_meters = gear_data.get("maximumMeters")
                    result.items_updated += 1
                    logger.debug(f"Updated gear: {gear.name} ({garmin_uuid}) - {garmin_distance/1000:.1f}km, {garmin_activity_count} activities")
                else:
                    # Create new gear
                    gear = Gear(
                        user_id=self.user.id,
                        garmin_uuid=garmin_uuid,
                        name=gear_data.get("displayName") or gear_data.get("customMakeModel") or "Unknown Gear",
                        brand=gear_data.get("gearMakeName") if gear_data.get("gearMakeName") != "Other" else None,
                        gear_type=gear_type,
                        status=status,
                        initial_distance_meters=garmin_distance,  # Garmin's tracked distance
                        garmin_activity_count=garmin_activity_count,  # Garmin's activity count
                        max_distance_meters=gear_data.get("maximumMeters") or 800000.0,  # 800km default for shoes
                    )
                    self.session.add(gear)
                    result.items_created += 1
                    logger.info(f"Created gear: {gear.name} ({garmin_uuid}) - {garmin_distance/1000:.1f}km from Garmin")

            await self.session.commit()
            logger.info(f"Gear sync complete: {result.items_created} created, {result.items_updated} updated")

        except Exception as e:
            logger.warning(f"Failed to sync gear: {e}")
            raise

    async def _link_activity_gear(self, activity: Activity, garmin_activity_id: int) -> None:
        """Link activity to gear used during the activity.

        Fetches gear associated with a Garmin activity and creates ActivityGear links.

        Args:
            activity: The activity to link gear to.
            garmin_activity_id: Garmin's activity ID for gear lookup.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        try:
            # Fetch gear for this activity from Garmin
            activity_gear_list = await loop.run_in_executor(
                None,
                lambda: self.adapter.get_activity_gear(garmin_activity_id),
            )

            if not activity_gear_list:
                return

            for gear_data in activity_gear_list:
                garmin_uuid = gear_data.get("uuid") or gear_data.get("gearUUID")
                if not garmin_uuid:
                    continue

                # Find matching local gear
                gear_result = await self.session.execute(
                    select(Gear).where(
                        and_(
                            Gear.user_id == self.user.id,
                            Gear.garmin_uuid == garmin_uuid,
                        )
                    )
                )
                gear = gear_result.scalar_one_or_none()

                if not gear:
                    logger.debug(f"Gear {garmin_uuid} not found locally, skipping link")
                    continue

                # Check if link already exists
                existing_link = await self.session.execute(
                    select(ActivityGear).where(
                        and_(
                            ActivityGear.activity_id == activity.id,
                            ActivityGear.gear_id == gear.id,
                        )
                    )
                )
                if existing_link.scalar_one_or_none():
                    continue

                # Create link
                link = ActivityGear(
                    activity_id=activity.id,
                    gear_id=gear.id,
                )
                self.session.add(link)
                logger.debug(f"Linked activity {activity.id} to gear {gear.name}")

        except Exception as e:
            logger.warning(f"Failed to link activity {activity.id} to gear: {e}")

    async def _update_sync_state(self, endpoint: str, success: bool) -> None:
        """Update sync state for an endpoint."""
        now = datetime.now(timezone.utc)

        stmt = insert(GarminSyncState).values(
            user_id=self.user.id,
            endpoint=endpoint,
            last_sync_at=now,
            last_success_at=now if success else None,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_garmin_sync_state_user_endpoint",
            set_={
                "last_sync_at": now,
                "last_success_at": now if success else GarminSyncState.last_success_at,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)


async def create_sync_service(
    session: AsyncSession,
    user: User,
    fit_storage_path: Optional[str] = None,
) -> Optional[GarminSyncService]:
    """Factory function to create a sync service for a user.

    Args:
        session: Database session
        user: User to sync for
        fit_storage_path: Path to store FIT files (uses settings.fit_storage_path if None)

    Returns:
        GarminSyncService if user has valid Garmin session, None otherwise
    """
    # Get user's Garmin session
    result = await session.execute(
        select(GarminSession).where(GarminSession.user_id == user.id)
    )
    garmin_session = result.scalar_one_or_none()

    if not garmin_session or not garmin_session.is_valid:
        return None

    # Create adapter with session data
    adapter = GarminConnectAdapter()
    adapter.restore_session(garmin_session.session_data)

    return GarminSyncService(
        session=session,
        adapter=adapter,
        user=user,
        fit_storage_path=fit_storage_path,
    )
