"""Garmin data synchronization service.

Handles syncing activities, health data from Garmin Connect to local database.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.garmin_adapter import (
    GarminConnectAdapter,
    GarminAdapterError,
    get_garmin_adapter,
)
from app.models.activity import Activity, ActivityLap, ActivitySample
from app.models.health import SleepRecord, HeartRateRecord
from app.models.user import User
from app.models.garmin import GarminCredential

logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Error during sync operation."""
    pass


class GarminSyncService:
    """Service for syncing Garmin data to local database."""

    def __init__(self, db: Session, user_id: int):
        """Initialize sync service.

        Args:
            db: Database session.
            user_id: User ID to sync data for.
        """
        self.db = db
        self.user_id = user_id
        self._adapter: Optional[GarminConnectAdapter] = None

    def _get_adapter(self) -> GarminConnectAdapter:
        """Get authenticated Garmin adapter.

        Returns:
            Authenticated GarminConnectAdapter.

        Raises:
            SyncError: If authentication fails.
        """
        if self._adapter and self._adapter.is_authenticated:
            return self._adapter

        # Get stored credentials
        cred = self.db.execute(
            select(GarminCredential).where(
                GarminCredential.user_id == self.user_id,
                GarminCredential.is_active == True,
            )
        ).scalar_one_or_none()

        if not cred:
            raise SyncError("No Garmin credentials found. Please connect your account.")

        adapter = get_garmin_adapter()

        # Try session-based login first
        if cred.session_data:
            try:
                adapter.login_with_session(cred.session_data)
                self._adapter = adapter
                return adapter
            except Exception:
                logger.warning("Session expired, re-authenticating...")

        # Fall back to email/password
        if cred.email and cred.encrypted_password:
            try:
                # TODO: Decrypt password properly
                adapter.login(cred.email, cred.encrypted_password)

                # Save new session data
                cred.session_data = adapter.get_session_data()
                self.db.commit()

                self._adapter = adapter
                return adapter
            except Exception as e:
                raise SyncError(f"Authentication failed: {e}")

        raise SyncError("No valid credentials available")

    def sync_activities(
        self,
        start_date: date,
        end_date: Optional[date] = None,
        force: bool = False,
    ) -> dict:
        """Sync activities from Garmin.

        Args:
            start_date: Start of date range.
            end_date: End of date range (defaults to today).
            force: Re-sync even if already exists.

        Returns:
            Sync result dict with counts.
        """
        end_date = end_date or date.today()
        adapter = self._get_adapter()

        result = {
            "synced": 0,
            "skipped": 0,
            "errors": 0,
            "activities": [],
        }

        try:
            activities = adapter.get_activities(start_date, end_date)
            logger.info(f"Found {len(activities)} activities from Garmin")

            for activity_data in activities:
                try:
                    garmin_id = activity_data.get("activityId")

                    # Check if already exists
                    existing = self.db.execute(
                        select(Activity).where(
                            Activity.user_id == self.user_id,
                            Activity.garmin_activity_id == garmin_id,
                        )
                    ).scalar_one_or_none()

                    if existing and not force:
                        result["skipped"] += 1
                        continue

                    # Create or update activity
                    activity = self._process_activity(activity_data, existing)
                    result["synced"] += 1
                    result["activities"].append(activity.id)

                except Exception as e:
                    logger.error(f"Error processing activity {activity_data.get('activityId')}: {e}")
                    result["errors"] += 1

            self.db.commit()

        except GarminAdapterError as e:
            raise SyncError(f"Garmin API error: {e}")

        return result

    def _process_activity(
        self,
        data: dict,
        existing: Optional[Activity] = None,
    ) -> Activity:
        """Process and save a single activity.

        Args:
            data: Activity data from Garmin.
            existing: Existing activity to update, or None to create.

        Returns:
            Saved Activity model.
        """
        garmin_id = data.get("activityId")

        # Map Garmin data to our model
        activity_data = {
            "user_id": self.user_id,
            "garmin_activity_id": garmin_id,
            "name": data.get("activityName", "Untitled"),
            "activity_type": self._map_activity_type(data.get("activityType", {}).get("typeKey")),
            "start_time": self._parse_timestamp(data.get("startTimeLocal")),
            "start_time_utc": self._parse_timestamp(data.get("startTimeGMT")),
            "duration_seconds": data.get("duration"),
            "elapsed_seconds": data.get("elapsedDuration"),
            "distance_meters": data.get("distance"),
            "avg_hr": data.get("averageHR"),
            "max_hr": data.get("maxHR"),
            "avg_cadence": data.get("averageRunningCadenceInStepsPerMinute"),
            "max_cadence": data.get("maxRunningCadenceInStepsPerMinute"),
            "avg_pace_seconds": self._calculate_pace(data.get("distance"), data.get("duration")),
            "best_pace_seconds": self._calculate_pace(data.get("distance"), data.get("duration")),  # TODO: get from laps
            "total_ascent_meters": data.get("elevationGain"),
            "total_descent_meters": data.get("elevationLoss"),
            "calories": data.get("calories"),
            "avg_power": data.get("avgPower"),
            "max_power": data.get("maxPower"),
            "normalized_power": data.get("normPower"),
            "training_effect_aerobic": data.get("aerobicTrainingEffect"),
            "training_effect_anaerobic": data.get("anaerobicTrainingEffect"),
            "vo2max": data.get("vO2MaxValue"),
        }

        if existing:
            for key, value in activity_data.items():
                if value is not None:
                    setattr(existing, key, value)
            activity = existing
        else:
            activity = Activity(**activity_data)
            self.db.add(activity)

        self.db.flush()
        return activity

    def sync_activity_details(self, activity_id: int) -> Activity:
        """Sync detailed data for a specific activity.

        Downloads FIT file and extracts laps, samples.

        Args:
            activity_id: Local activity ID.

        Returns:
            Updated Activity model.
        """
        activity = self.db.get(Activity, activity_id)
        if not activity or activity.user_id != self.user_id:
            raise SyncError(f"Activity {activity_id} not found")

        adapter = self._get_adapter()

        try:
            # Download and parse FIT file
            parsed_data, file_path, file_hash = adapter.download_and_parse_fit(
                activity.garmin_activity_id
            )

            # Update activity with FIT data
            activity.fit_file_path = file_path
            activity.fit_file_hash = file_hash

            session = parsed_data.get("session", {})
            if session:
                activity.training_stress_score = session.get("training_stress_score")
                activity.intensity_factor = session.get("intensity_factor")
                activity.avg_ground_contact_time = session.get("avg_ground_contact_time")
                activity.avg_vertical_oscillation = session.get("avg_vertical_oscillation")
                activity.avg_stride_length = session.get("avg_step_length")

            # Process laps
            self._process_laps(activity, parsed_data.get("laps", []))

            # Process samples (time series)
            self._process_samples(activity, parsed_data.get("records", []))

            activity.has_fit_file = True
            self.db.commit()

            return activity

        except GarminAdapterError as e:
            raise SyncError(f"Failed to sync activity details: {e}")

    def _process_laps(self, activity: Activity, laps_data: list) -> None:
        """Process and save lap data.

        Args:
            activity: Parent activity.
            laps_data: List of lap data dicts.
        """
        # Remove existing laps
        self.db.execute(
            ActivityLap.__table__.delete().where(
                ActivityLap.activity_id == activity.id
            )
        )

        for idx, lap_data in enumerate(laps_data):
            lap = ActivityLap(
                activity_id=activity.id,
                lap_number=idx + 1,
                start_time=self._parse_timestamp(lap_data.get("start_time")),
                duration_seconds=lap_data.get("total_timer_time"),
                distance_meters=lap_data.get("total_distance"),
                avg_hr=lap_data.get("avg_heart_rate"),
                max_hr=lap_data.get("max_heart_rate"),
                avg_cadence=lap_data.get("avg_cadence"),
                max_cadence=lap_data.get("max_cadence"),
                avg_pace_seconds=self._calculate_pace(
                    lap_data.get("total_distance"),
                    lap_data.get("total_timer_time"),
                ),
                total_ascent_meters=lap_data.get("total_ascent"),
                total_descent_meters=lap_data.get("total_descent"),
                calories=lap_data.get("total_calories"),
            )
            self.db.add(lap)

    def _process_samples(self, activity: Activity, records_data: list) -> None:
        """Process and save sample data (time series).

        Args:
            activity: Parent activity.
            records_data: List of record data dicts.
        """
        # Remove existing samples
        self.db.execute(
            ActivitySample.__table__.delete().where(
                ActivitySample.activity_id == activity.id
            )
        )

        # Downsample if too many records (keep every Nth record)
        max_samples = 5000
        step = max(1, len(records_data) // max_samples)

        for idx, record in enumerate(records_data[::step]):
            sample = ActivitySample(
                activity_id=activity.id,
                timestamp=self._parse_timestamp(record.get("timestamp")),
                elapsed_seconds=idx * step,  # Approximate
                heart_rate=record.get("heart_rate"),
                cadence=record.get("cadence"),
                speed=record.get("enhanced_speed") or record.get("speed"),
                altitude=record.get("enhanced_altitude") or record.get("altitude"),
                latitude=self._convert_semicircles(record.get("position_lat")),
                longitude=self._convert_semicircles(record.get("position_long")),
                distance_meters=record.get("distance"),
                power=record.get("power"),
                ground_contact_time=record.get("ground_contact_time"),
                vertical_oscillation=record.get("vertical_oscillation"),
                stride_length=record.get("step_length"),
            )
            self.db.add(sample)

    def sync_sleep(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> dict:
        """Sync sleep data from Garmin.

        Args:
            start_date: Start of date range.
            end_date: End of date range (defaults to today).

        Returns:
            Sync result dict.
        """
        end_date = end_date or date.today()
        adapter = self._get_adapter()

        result = {"synced": 0, "skipped": 0, "errors": 0}
        current = start_date

        while current <= end_date:
            try:
                sleep_data = adapter.get_sleep_data(current)

                if not sleep_data:
                    result["skipped"] += 1
                    current += timedelta(days=1)
                    continue

                # Check existing
                existing = self.db.execute(
                    select(SleepRecord).where(
                        SleepRecord.user_id == self.user_id,
                        SleepRecord.calendar_date == current,
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update
                    self._update_sleep_record(existing, sleep_data)
                else:
                    # Create
                    record = self._create_sleep_record(current, sleep_data)
                    self.db.add(record)

                result["synced"] += 1

            except Exception as e:
                logger.error(f"Error syncing sleep for {current}: {e}")
                result["errors"] += 1

            current += timedelta(days=1)

        self.db.commit()
        return result

    def _create_sleep_record(self, calendar_date: date, data: dict) -> SleepRecord:
        """Create sleep record from Garmin data."""
        daily = data.get("dailySleepDTO", {})

        return SleepRecord(
            user_id=self.user_id,
            calendar_date=calendar_date,
            sleep_start=self._parse_timestamp(daily.get("sleepStartTimestampGMT")),
            sleep_end=self._parse_timestamp(daily.get("sleepEndTimestampGMT")),
            total_sleep_seconds=daily.get("sleepTimeSeconds"),
            deep_sleep_seconds=daily.get("deepSleepSeconds"),
            light_sleep_seconds=daily.get("lightSleepSeconds"),
            rem_sleep_seconds=daily.get("remSleepSeconds"),
            awake_seconds=daily.get("awakeSleepSeconds"),
            sleep_score=daily.get("sleepScores", {}).get("overallScore"),
            avg_spo2=daily.get("averageSpO2Value"),
            avg_respiration=daily.get("averageRespirationValue"),
            hrv_status=daily.get("hrvStatus"),
        )

    def _update_sleep_record(self, record: SleepRecord, data: dict) -> None:
        """Update existing sleep record."""
        daily = data.get("dailySleepDTO", {})

        record.sleep_start = self._parse_timestamp(daily.get("sleepStartTimestampGMT"))
        record.sleep_end = self._parse_timestamp(daily.get("sleepEndTimestampGMT"))
        record.total_sleep_seconds = daily.get("sleepTimeSeconds")
        record.deep_sleep_seconds = daily.get("deepSleepSeconds")
        record.light_sleep_seconds = daily.get("lightSleepSeconds")
        record.rem_sleep_seconds = daily.get("remSleepSeconds")
        record.awake_seconds = daily.get("awakeSleepSeconds")
        record.sleep_score = daily.get("sleepScores", {}).get("overallScore")

    def sync_heart_rate(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> dict:
        """Sync heart rate data from Garmin.

        Args:
            start_date: Start of date range.
            end_date: End of date range (defaults to today).

        Returns:
            Sync result dict.
        """
        end_date = end_date or date.today()
        adapter = self._get_adapter()

        result = {"synced": 0, "skipped": 0, "errors": 0}
        current = start_date

        while current <= end_date:
            try:
                hr_data = adapter.get_heart_rate(current)

                if not hr_data:
                    result["skipped"] += 1
                    current += timedelta(days=1)
                    continue

                # Check existing
                existing = self.db.execute(
                    select(HeartRateRecord).where(
                        HeartRateRecord.user_id == self.user_id,
                        HeartRateRecord.calendar_date == current,
                    )
                ).scalar_one_or_none()

                if existing:
                    self._update_hr_record(existing, hr_data)
                else:
                    record = self._create_hr_record(current, hr_data)
                    self.db.add(record)

                result["synced"] += 1

            except Exception as e:
                logger.error(f"Error syncing HR for {current}: {e}")
                result["errors"] += 1

            current += timedelta(days=1)

        self.db.commit()
        return result

    def _create_hr_record(self, calendar_date: date, data: dict) -> HeartRateRecord:
        """Create heart rate record from Garmin data."""
        return HeartRateRecord(
            user_id=self.user_id,
            calendar_date=calendar_date,
            resting_hr=data.get("restingHeartRate"),
            min_hr=data.get("minHeartRate"),
            max_hr=data.get("maxHeartRate"),
            avg_hr=None,  # Calculate from time series if needed
        )

    def _update_hr_record(self, record: HeartRateRecord, data: dict) -> None:
        """Update existing HR record."""
        record.resting_hr = data.get("restingHeartRate")
        record.min_hr = data.get("minHeartRate")
        record.max_hr = data.get("maxHeartRate")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _map_activity_type(self, garmin_type: Optional[str]) -> str:
        """Map Garmin activity type to our type."""
        mapping = {
            "running": "running",
            "trail_running": "trail_running",
            "treadmill_running": "treadmill",
            "track_running": "track",
            "cycling": "cycling",
            "indoor_cycling": "indoor_cycling",
            "walking": "walking",
            "hiking": "hiking",
            "swimming": "swimming",
            "open_water_swimming": "open_water",
            "strength_training": "strength",
        }
        return mapping.get(garmin_type, garmin_type or "other")

    def _parse_timestamp(self, value) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            # Unix timestamp in milliseconds
            return datetime.fromtimestamp(value / 1000)
        if isinstance(value, str):
            # ISO format
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    def _calculate_pace(
        self,
        distance_meters: Optional[float],
        duration_seconds: Optional[float],
    ) -> Optional[float]:
        """Calculate pace in seconds per kilometer."""
        if not distance_meters or not duration_seconds or distance_meters == 0:
            return None
        return (duration_seconds / distance_meters) * 1000

    def _convert_semicircles(self, semicircles: Optional[int]) -> Optional[float]:
        """Convert Garmin semicircles to decimal degrees."""
        if semicircles is None:
            return None
        return semicircles * (180 / 2**31)


def get_sync_service(db: Session, user_id: int) -> GarminSyncService:
    """Factory function to create sync service."""
    return GarminSyncService(db, user_id)
