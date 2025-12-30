"""Garmin data synchronization service.

This module provides a clean, well-structured synchronization pipeline
for fetching and storing Garmin data.
"""

import logging
import time
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Any, Optional

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
from app.adapters.garmin_adapter import GarminConnectAdapter
from app.observability import get_metrics_backend

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
        "activities",
        "sleep",
        "heart_rate",
        # "body_composition",  # Not available in current garminconnect library
    ]

    def __init__(
        self,
        session: AsyncSession,
        adapter: GarminConnectAdapter,
        user: User,
        fit_storage_path: str = "./data/fit_files",
    ):
        self.session = session
        self.adapter = adapter
        self.user = user
        self.fit_storage_path = Path(fit_storage_path)
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
            endpoint: The endpoint to sync (activities, sleep, heart_rate, body_composition)
            start_date: Start date for sync
            end_date: End date for sync
            full_backfill: If True, ignore last sync state

        Returns:
            SyncResult with operation details
        """
        result = SyncResult(endpoint)

        # Determine date range
        if not full_backfill:
            sync_state = await self._get_sync_state(endpoint)
            if sync_state and sync_state.last_success_at and not start_date:
                start_date = sync_state.last_success_at.date() - timedelta(days=1)

        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        logger.info(f"Syncing {endpoint} for user {self.user.id}: {start_date} to {end_date}")

        start_time = time.perf_counter()
        try:
            # Dispatch to appropriate sync method
            if endpoint == "activities":
                await self._sync_activities(result, start_date, end_date)
            elif endpoint == "sleep":
                await self._sync_sleep(result, start_date, end_date)
            elif endpoint == "heart_rate":
                await self._sync_heart_rate(result, start_date, end_date)
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

        await self.session.commit()

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
        activity.calories = data.get("calories") or activity.calories
        activity.vo2max = data.get("vO2MaxValue") or activity.vo2max

    async def _download_fit_file(self, activity: Activity, garmin_id: int) -> None:
        """Download and store FIT file for an activity."""
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

            logger.info(f"Downloaded FIT file for activity {garmin_id}")

        except Exception as e:
            logger.warning(f"Failed to download FIT file for activity {garmin_id}: {e}")

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
                    await self._store_sleep(sleep_data, current_date)
                    result.items_created += 1
            except Exception as e:
                logger.warning(f"Failed to fetch sleep for {current_date}: {e}")

            current_date += timedelta(days=1)

        await self.session.commit()

    async def _store_sleep(self, data: dict[str, Any], sleep_date: date) -> None:
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
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sleep_user_date",
            set_={
                "duration_seconds": stmt.excluded.duration_seconds,
                "score": stmt.excluded.score,
                "stages": stmt.excluded.stages,
                "updated_at": datetime.now(timezone.utc),
            },
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
                    await self._store_heart_rate(hr_data, current_date)
                    result.items_created += 1
            except Exception as e:
                logger.warning(f"Failed to fetch heart rate for {current_date}: {e}")

            current_date += timedelta(days=1)

        await self.session.commit()

    async def _store_heart_rate(self, data: dict[str, Any], hr_date: date) -> None:
        """Store heart rate record."""
        hr_record = HRRecord(
            user_id=self.user.id,
            start_time=datetime.combine(hr_date, datetime.min.time()),
            end_time=datetime.combine(hr_date, datetime.max.time()),
            avg_hr=data.get("restingHeartRate"),
            max_hr=data.get("maxHeartRate"),
            resting_hr=data.get("restingHeartRate"),
            samples=data.get("heartRateValues"),
        )
        self.session.add(hr_record)

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
    ) -> GarminRawEvent:
        """Store raw API response."""
        raw_event = GarminRawEvent(
            user_id=self.user.id,
            endpoint=endpoint,
            fetched_at=datetime.now(timezone.utc),
            payload=payload if isinstance(payload, dict) else {"data": payload},
        )
        self.session.add(raw_event)
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
    fit_storage_path: str = "./data/fit_files",
) -> Optional[GarminSyncService]:
    """Factory function to create a sync service for a user.

    Args:
        session: Database session
        user: User to sync for
        fit_storage_path: Path to store FIT files

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
