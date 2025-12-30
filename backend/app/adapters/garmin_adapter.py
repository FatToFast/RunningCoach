"""Garmin Connect API adapter using garminconnect library.

This adapter wraps all Garmin API calls, making it easy to swap
implementations if the library changes or breaks. Includes FIT file
download and parsing capabilities for Runalyze+ level data extraction.
"""

import hashlib
import logging
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from garminconnect import Garmin, GarminConnectAuthenticationError

from app.core.config import get_settings
from app.observability import get_metrics_backend

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
        self._metrics = get_metrics_backend()

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
        start_time = time.perf_counter()
        status_code = 500
        try:
            self._client = Garmin(email, password)
            self._client.login()
            logger.info("Successfully logged in to Garmin Connect")
            status_code = 200
            return True
        except GarminConnectAuthenticationError as e:
            status_code = 401
            logger.error(f"Garmin authentication failed: {e}")
            raise GarminAuthError(f"Authentication failed: {e}") from e
        except Exception as e:
            status_code = 500
            logger.error(f"Unexpected error during Garmin login: {e}")
            raise GarminAdapterError(f"Login error: {e}") from e
        finally:
            self._observe_api_call("login", status_code, start_time)

    def login_with_session(self, session_data: dict[str, Any] | str) -> bool:
        """Login using stored session data.

        Args:
            session_data: Previously saved session data.
                - If dict (from JSONB): expects {"garth_session": "base64_string"}
                - If str: expects base64 encoded garth session string

        Returns:
            True if login successful.

        Raises:
            GarminAuthError: If session is invalid.
        """
        start_time = time.perf_counter()
        status_code = 500
        try:
            self._client = Garmin()
            # garminconnect 0.2.x uses garth library
            # Extract base64 string from dict wrapper if needed
            if isinstance(session_data, dict):
                session_str = session_data.get("garth_session", "")
            else:
                session_str = session_data
            self._client.garth.loads(session_str)
            logger.info("Successfully logged in with session data")
            status_code = 200
            return True
        except Exception as e:
            status_code = 401
            logger.error(f"Session login failed: {e}")
            raise GarminAuthError(f"Session invalid: {e}") from e
        finally:
            self._observe_api_call("login_with_session", status_code, start_time)

    def restore_session(self, session_data: dict[str, Any] | str) -> bool:
        """Restore session from stored data (alias for login_with_session).

        Args:
            session_data: Previously saved session data (dict or string).

        Returns:
            True if restore successful.
        """
        return self.login_with_session(session_data)

    def validate_session(self, session_data: dict[str, Any] | str) -> bool:
        """Validate if stored session data is still usable.

        This attempts to restore the session and make a lightweight API call
        to verify the session is not expired.

        Args:
            session_data: Previously saved session data (dict or string).

        Returns:
            True if session is valid and working.
        """
        try:
            self.restore_session(session_data)
            # Make a lightweight API call to verify session
            # get_user_summary is a simple endpoint that requires auth
            self._client.get_user_summary(date.today().isoformat())
            return True
        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            return False

    def get_session_data(self) -> Optional[dict[str, Any]]:
        """Get current session data for persistence.

        Returns:
            Session data as dict (for JSONB storage) or None if not authenticated.
            Format: {"garth_session": "base64_encoded_string"}
        """
        if self._client is None:
            return None
        # garminconnect 0.2.x uses garth library
        # dumps() returns base64 encoded string, wrap in dict for JSONB
        garth_str = self._client.garth.dumps()
        return {"garth_session": garth_str} if garth_str else None

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
        start_time = time.perf_counter()
        status_code = 500
        try:
            activities = self._client.get_activities_by_date(
                start_date.isoformat(),
                end_date.isoformat(),
                activity_type,
            )
            status_code = 200
            return activities or []
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get activities: {e}")
            raise GarminAPIError(f"Failed to get activities: {e}") from e
        finally:
            self._observe_api_call("get_activities_by_date", status_code, start_time)

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
        start_time = time.perf_counter()
        status_code = 500
        try:
            status_code = 200
            return self._client.get_activity_details(activity_id)
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get activity details: {e}")
            raise GarminAPIError(f"Failed to get activity {activity_id}: {e}") from e
        finally:
            self._observe_api_call("get_activity_details", status_code, start_time)

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
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_sleep_data(target_date.isoformat()) or {}
            status_code = 200
            return data
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get sleep data: {e}")
            raise GarminAPIError(f"Failed to get sleep data: {e}") from e
        finally:
            self._observe_api_call("get_sleep_data", status_code, start_time)

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
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_heart_rates(target_date.isoformat()) or {}
            status_code = 200
            return data
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get heart rate data: {e}")
            raise GarminAPIError(f"Failed to get HR data: {e}") from e
        finally:
            self._observe_api_call("get_heart_rates", status_code, start_time)

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
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_stats(target_date.isoformat()) or {}
            status_code = 200
            return data
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get stats: {e}")
            raise GarminAPIError(f"Failed to get stats: {e}") from e
        finally:
            self._observe_api_call("get_stats", status_code, start_time)

    def get_user_profile(self) -> dict[str, Any]:
        """Get user profile including max HR settings.

        Returns:
            User profile data dict with maxHr if available.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            # garminconnect의 get_user_summary() 메서드 사용
            data = self._client.get_user_summary(date.today().isoformat()) or {}
            status_code = 200
            return data
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get user profile: {e}")
            raise GarminAPIError(f"Failed to get user profile: {e}") from e
        finally:
            self._observe_api_call("get_user_profile", status_code, start_time)

    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated.

        Raises:
            GarminAuthError: If not authenticated.
        """
        if self._client is None:
            raise GarminAuthError("Not authenticated. Call login() first.")

    def _observe_api_call(self, operation: str, status_code: int, start_time: float) -> None:
        duration_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.observe_external_api(
            "garmin",
            operation,
            status_code,
            duration_ms,
        )
        if settings.debug:
            logger.info(
                "Garmin API %s status=%s duration_ms=%.2f",
                operation,
                status_code,
                duration_ms,
            )

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
        start_time = time.perf_counter()
        status_code = 500

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
            status_code = 200
            self._metrics.observe_fit_download(len(fit_data), True)
            return fit_data, file_path, file_hash

        except GarminAPIError:
            status_code = 500
            self._metrics.observe_fit_download(0, False)
            raise
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to download FIT file for activity {activity_id}: {e}")
            self._metrics.observe_fit_download(0, False)
            raise GarminAPIError(f"FIT download failed: {e}") from e
        finally:
            self._observe_api_call("download_fit_file", status_code, start_time)

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

    # -------------------------------------------------------------------------
    # Race-related Endpoints
    # -------------------------------------------------------------------------

    def get_race_predictions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        prediction_type: str = "daily",
    ) -> dict[str, Any]:
        """Get race predictions based on VO2Max.

        Returns predicted race times for 5K, 10K, Half Marathon, and Marathon.

        Args:
            start_date: Start date for predictions (optional).
            end_date: End date for predictions (optional).
            prediction_type: 'daily' or 'monthly'.

        Returns:
            Race predictions data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            # Garmin API requires either all parameters or none
            if start_date and end_date:
                data = self._client.get_race_predictions(
                    startdate=start_date.isoformat(),
                    enddate=end_date.isoformat(),
                    _type=prediction_type,
                )
            else:
                # Call without date parameters
                data = self._client.get_race_predictions()
            status_code = 200
            return data or {}
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get race predictions: {e}")
            raise GarminAPIError(f"Failed to get race predictions: {e}") from e
        finally:
            self._observe_api_call("get_race_predictions", status_code, start_time)

    def get_personal_records(self) -> list[dict[str, Any]]:
        """Get personal records from Garmin.

        Returns:
            List of personal records.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_personal_record()
            status_code = 200
            return data or []
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get personal records: {e}")
            raise GarminAPIError(f"Failed to get personal records: {e}") from e
        finally:
            self._observe_api_call("get_personal_records", status_code, start_time)

    def get_goals(self) -> list[dict[str, Any]]:
        """Get user goals from Garmin.

        Returns:
            List of goals.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_goals("all")
            status_code = 200
            return data or []
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get goals: {e}")
            raise GarminAPIError(f"Failed to get goals: {e}") from e
        finally:
            self._observe_api_call("get_goals", status_code, start_time)


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
