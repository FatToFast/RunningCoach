"""Garmin Connect API adapter using garminconnect library.

This adapter wraps all Garmin API calls, making it easy to swap
implementations if the library changes or breaks. Includes FIT file
download and parsing capabilities for Runalyze+ level data extraction.
"""

import hashlib
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from garminconnect import Garmin, GarminConnectAuthenticationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GarminAdapterError(Exception):
    """Base exception for Garmin adapter errors."""

    pass


class GarminAuthError(GarminAdapterError):
    """Authentication error with Garmin."""

    pass


class GarminAPIError(GarminAdapterError):
    """API error from Garmin."""

    pass


class GarminAdapterProtocol(Protocol):
    """Protocol defining the Garmin adapter interface."""

    async def login(self, email: str, password: str) -> bool:
        """Login to Garmin Connect."""
        ...

    async def get_activities(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get activities within date range."""
        ...

    async def get_activity_details(self, activity_id: int) -> dict[str, Any]:
        """Get detailed activity data."""
        ...

    async def get_sleep_data(self, target_date: date) -> dict[str, Any]:
        """Get sleep data for a specific date."""
        ...

    async def get_heart_rate(self, target_date: date) -> dict[str, Any]:
        """Get heart rate data for a specific date."""
        ...


class GarminConnectAdapter:
    """Adapter for garminconnect library.

    This class wraps the garminconnect library to provide a consistent
    interface and handle common errors.
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        self._client: Optional[Garmin] = None
        self._session_data: Optional[dict[str, Any]] = None

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._client is not None

    def login(self, email: str, password: str) -> bool:
        """Login to Garmin Connect.

        Args:
            email: Garmin account email.
            password: Garmin account password.

        Returns:
            True if login successful.

        Raises:
            GarminAuthError: If authentication fails.
        """
        try:
            self._client = Garmin(email, password)
            self._client.login()
            logger.info("Successfully logged in to Garmin Connect")
            return True
        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin authentication failed: {e}")
            raise GarminAuthError(f"Authentication failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during Garmin login: {e}")
            raise GarminAdapterError(f"Login error: {e}") from e

    def login_with_session(self, session_data: dict[str, Any]) -> bool:
        """Login using stored session data.

        Args:
            session_data: Previously saved session data.

        Returns:
            True if login successful.

        Raises:
            GarminAuthError: If session is invalid.
        """
        try:
            self._client = Garmin()
            self._client.login(session_data)
            self._session_data = session_data
            logger.info("Successfully logged in with session data")
            return True
        except Exception as e:
            logger.error(f"Session login failed: {e}")
            raise GarminAuthError(f"Session invalid: {e}") from e

    def get_session_data(self) -> Optional[dict[str, Any]]:
        """Get current session data for persistence.

        Returns:
            Session data dict or None if not authenticated.
        """
        if self._client is None:
            return None
        return self._client.session_data

    def get_activities(
        self,
        start_date: date,
        end_date: date,
        activity_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get activities within date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            activity_type: Filter by activity type (optional).

        Returns:
            List of activity data dicts.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            activities = self._client.get_activities_by_date(
                start_date.isoformat(),
                end_date.isoformat(),
                activity_type,
            )
            return activities or []
        except Exception as e:
            logger.error(f"Failed to get activities: {e}")
            raise GarminAPIError(f"Failed to get activities: {e}") from e

    def get_activity_details(self, activity_id: int) -> dict[str, Any]:
        """Get detailed activity data.

        Args:
            activity_id: Garmin activity ID.

        Returns:
            Activity details dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_activity_details(activity_id)
        except Exception as e:
            logger.error(f"Failed to get activity details: {e}")
            raise GarminAPIError(f"Failed to get activity {activity_id}: {e}") from e

    def get_sleep_data(self, target_date: date) -> dict[str, Any]:
        """Get sleep data for a specific date.

        Args:
            target_date: Date to get sleep data for.

        Returns:
            Sleep data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_sleep_data(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get sleep data: {e}")
            raise GarminAPIError(f"Failed to get sleep data: {e}") from e

    def get_heart_rate(self, target_date: date) -> dict[str, Any]:
        """Get heart rate data for a specific date.

        Args:
            target_date: Date to get HR data for.

        Returns:
            Heart rate data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_heart_rates(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get heart rate data: {e}")
            raise GarminAPIError(f"Failed to get HR data: {e}") from e

    def get_stats(self, target_date: date) -> dict[str, Any]:
        """Get daily stats summary.

        Args:
            target_date: Date to get stats for.

        Returns:
            Stats data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_stats(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise GarminAPIError(f"Failed to get stats: {e}") from e

    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated.

        Raises:
            GarminAuthError: If not authenticated.
        """
        if self._client is None:
            raise GarminAuthError("Not authenticated. Call login() first.")

    # -------------------------------------------------------------------------
    # FIT File Download & Parsing (Runalyze+ level data extraction)
    # -------------------------------------------------------------------------

    def download_fit_file(
        self,
        activity_id: int,
        save_dir: Optional[str] = None,
    ) -> tuple[bytes, str, str]:
        """Download FIT file for an activity.

        Args:
            activity_id: Garmin activity ID.
            save_dir: Directory to save FIT file. If None, uses settings.fit_storage_path.

        Returns:
            Tuple of (file_bytes, file_path, file_hash).

        Raises:
            GarminAPIError: If download fails.
        """
        self._ensure_authenticated()

        try:
            # Download FIT file bytes
            fit_data = self._client.download_activity(
                activity_id,
                dl_fmt=self._client.ActivityDownloadFormat.ORIGINAL,
            )

            if not fit_data:
                raise GarminAPIError(f"No FIT data returned for activity {activity_id}")

            # Calculate hash for deduplication
            file_hash = hashlib.sha256(fit_data).hexdigest()

            # Determine save path
            storage_dir = save_dir or settings.fit_storage_path
            Path(storage_dir).mkdir(parents=True, exist_ok=True)

            file_name = f"{activity_id}.fit"
            file_path = os.path.join(storage_dir, file_name)

            # Save file
            with open(file_path, "wb") as f:
                f.write(fit_data)

            logger.info(f"Downloaded FIT file for activity {activity_id}: {file_path}")
            return fit_data, file_path, file_hash

        except GarminAPIError:
            raise
        except Exception as e:
            logger.error(f"Failed to download FIT file for activity {activity_id}: {e}")
            raise GarminAPIError(f"FIT download failed: {e}") from e

    def parse_fit_file(self, fit_data: bytes) -> dict[str, Any]:
        """Parse FIT file and extract detailed data.

        Extracts Runalyze+ level data including:
        - Records (time series): HR, pace, cadence, altitude, power, etc.
        - Laps: splits, HR zones, pace per lap
        - Session: summary statistics
        - Device info

        Args:
            fit_data: Raw FIT file bytes.

        Returns:
            Parsed data dict with records, laps, session, and device info.

        Raises:
            GarminAPIError: If parsing fails.
        """
        try:
            from fitparse import FitFile

            fit_file = FitFile(fit_data)
            result: dict[str, Any] = {
                "records": [],
                "laps": [],
                "session": {},
                "device_info": {},
                "events": [],
                "hrv": [],
            }

            for record in fit_file.get_messages():
                record_data = {}
                for field in record.fields:
                    # Convert datetime to ISO string
                    value = field.value
                    if isinstance(value, datetime):
                        value = value.replace(tzinfo=timezone.utc).isoformat()
                    record_data[field.name] = value

                if record.name == "record":
                    # Time series data point
                    result["records"].append(self._extract_record_fields(record_data))
                elif record.name == "lap":
                    result["laps"].append(self._extract_lap_fields(record_data))
                elif record.name == "session":
                    result["session"] = self._extract_session_fields(record_data)
                elif record.name == "device_info":
                    result["device_info"] = record_data
                elif record.name == "event":
                    result["events"].append(record_data)
                elif record.name == "hrv":
                    # HRV data for advanced analysis
                    result["hrv"].append(record_data)

            logger.info(
                f"Parsed FIT file: {len(result['records'])} records, "
                f"{len(result['laps'])} laps"
            )
            return result

        except ImportError:
            logger.error("fitparse library not installed")
            raise GarminAPIError("fitparse library required for FIT parsing")
        except Exception as e:
            logger.error(f"Failed to parse FIT file: {e}")
            raise GarminAPIError(f"FIT parsing failed: {e}") from e

    def _extract_record_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant fields from a FIT record message.

        Args:
            data: Raw record data.

        Returns:
            Filtered record with key metrics.
        """
        fields = [
            "timestamp",
            "heart_rate",
            "cadence",
            "speed",
            "enhanced_speed",
            "altitude",
            "enhanced_altitude",
            "position_lat",
            "position_long",
            "distance",
            "power",
            "vertical_oscillation",
            "stance_time",
            "ground_contact_time",
            "vertical_ratio",
            "step_length",
            "temperature",
        ]
        return {k: data.get(k) for k in fields if data.get(k) is not None}

    def _extract_lap_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant fields from a FIT lap message.

        Args:
            data: Raw lap data.

        Returns:
            Filtered lap data with key metrics.
        """
        fields = [
            "timestamp",
            "start_time",
            "total_elapsed_time",
            "total_timer_time",
            "total_distance",
            "total_calories",
            "avg_heart_rate",
            "max_heart_rate",
            "avg_cadence",
            "max_cadence",
            "avg_speed",
            "enhanced_avg_speed",
            "max_speed",
            "enhanced_max_speed",
            "total_ascent",
            "total_descent",
            "avg_power",
            "max_power",
            "normalized_power",
            "lap_trigger",
            "avg_vertical_oscillation",
            "avg_stance_time",
            "avg_ground_contact_time",
            "avg_vertical_ratio",
            "avg_step_length",
        ]
        return {k: data.get(k) for k in fields if data.get(k) is not None}

    def _extract_session_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant fields from a FIT session message.

        Args:
            data: Raw session data.

        Returns:
            Filtered session summary.
        """
        fields = [
            "timestamp",
            "start_time",
            "sport",
            "sub_sport",
            "total_elapsed_time",
            "total_timer_time",
            "total_distance",
            "total_calories",
            "avg_heart_rate",
            "max_heart_rate",
            "avg_cadence",
            "max_cadence",
            "avg_speed",
            "enhanced_avg_speed",
            "max_speed",
            "enhanced_max_speed",
            "total_ascent",
            "total_descent",
            "avg_power",
            "max_power",
            "normalized_power",
            "training_stress_score",
            "intensity_factor",
            "threshold_power",
            "avg_vertical_oscillation",
            "avg_stance_time",
            "avg_ground_contact_time",
            "avg_vertical_ratio",
            "avg_step_length",
            "total_training_effect",
            "total_anaerobic_training_effect",
        ]
        return {k: data.get(k) for k in fields if data.get(k) is not None}

    def download_and_parse_fit(
        self,
        activity_id: int,
        save_dir: Optional[str] = None,
    ) -> tuple[dict[str, Any], str, str]:
        """Download and parse FIT file in one operation.

        Args:
            activity_id: Garmin activity ID.
            save_dir: Optional directory to save FIT file.

        Returns:
            Tuple of (parsed_data, file_path, file_hash).

        Raises:
            GarminAPIError: If download or parsing fails.
        """
        fit_data, file_path, file_hash = self.download_fit_file(activity_id, save_dir)
        parsed_data = self.parse_fit_file(fit_data)
        return parsed_data, file_path, file_hash

    # -------------------------------------------------------------------------
    # Additional Health/Fitness Data Endpoints
    # -------------------------------------------------------------------------

    def get_body_battery(self, target_date: date) -> dict[str, Any]:
        """Get Body Battery data for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            Body Battery data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_body_battery(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get Body Battery data: {e}")
            raise GarminAPIError(f"Failed to get Body Battery: {e}") from e

    def get_stress_data(self, target_date: date) -> dict[str, Any]:
        """Get stress data for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            Stress data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_stress_data(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get stress data: {e}")
            raise GarminAPIError(f"Failed to get stress data: {e}") from e

    def get_hrv_data(self, target_date: date) -> dict[str, Any]:
        """Get HRV (Heart Rate Variability) data for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            HRV data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_hrv_data(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get HRV data: {e}")
            raise GarminAPIError(f"Failed to get HRV data: {e}") from e

    def get_training_status(self, target_date: date) -> dict[str, Any]:
        """Get training status/load for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            Training status data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_training_status(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get training status: {e}")
            raise GarminAPIError(f"Failed to get training status: {e}") from e

    def get_max_metrics(self, target_date: date) -> dict[str, Any]:
        """Get max metrics (VO2max, etc.) for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            Max metrics data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_max_metrics(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get max metrics: {e}")
            raise GarminAPIError(f"Failed to get max metrics: {e}") from e

    def get_respiration_data(self, target_date: date) -> dict[str, Any]:
        """Get respiration data for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            Respiration data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_respiration_data(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get respiration data: {e}")
            raise GarminAPIError(f"Failed to get respiration data: {e}") from e

    def get_spo2_data(self, target_date: date) -> dict[str, Any]:
        """Get SpO2 (blood oxygen) data for a specific date.

        Args:
            target_date: Date to get data for.

        Returns:
            SpO2 data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        try:
            return self._client.get_spo2_data(target_date.isoformat()) or {}
        except Exception as e:
            logger.error(f"Failed to get SpO2 data: {e}")
            raise GarminAPIError(f"Failed to get SpO2 data: {e}") from e


# Global adapter instance (for simple single-user MVP)
_adapter: Optional[GarminConnectAdapter] = None


def get_garmin_adapter() -> GarminConnectAdapter:
    """Get or create the global Garmin adapter instance.

    Returns:
        GarminConnectAdapter instance.
    """
    global _adapter
    if _adapter is None:
        _adapter = GarminConnectAdapter()
    return _adapter
