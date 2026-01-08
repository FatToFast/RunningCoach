"""Garmin Connect API adapter using garminconnect library.

This adapter wraps all Garmin API calls, making it easy to swap
implementations if the library changes or breaks. Includes FIT file
download and parsing capabilities for Runalyze+ level data extraction.
"""

import hashlib
import io
import logging
import os
import time
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from garminconnect import Garmin, GarminConnectAuthenticationError

from app.core.config import get_settings
from app.observability import get_metrics_backend

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_ESTIMATED_PACE_SECONDS = 360  # 6:00/km fallback for distance-only steps


def _parse_single_pace(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    if ":" in value:
        parts = value.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) * 60 + int(parts[1])
    if value.isdigit():
        return int(value)
    return None


def _parse_pace_seconds(pace: str | None) -> int | None:
    if not pace:
        return None
    cleaned = pace.strip().lower()
    cleaned = cleaned.replace("/km", "").replace("km", "")
    for sep in ("~", "–", "—"):
        cleaned = cleaned.replace(sep, "-")
    if "-" in cleaned:
        parts = [p.strip() for p in cleaned.split("-") if p.strip()]
        values = [_parse_single_pace(p) for p in parts]
        values = [v for v in values if v is not None]
        if values:
            return int(sum(values) / len(values))
        return None
    return _parse_single_pace(cleaned)


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

    async def upload_running_workout_template(self, workout: Any) -> int:
        """Upload a running workout template."""
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
            # Use get_full_name() which doesn't require external API calls
            # and validates that the garth session has valid tokens
            display_name = self._client.get_full_name()
            if display_name:
                logger.debug(f"Session valid for user: {display_name}")
                return True
            # Fallback: check if garth session has valid oauth tokens
            if hasattr(self._client, 'garth') and self._client.garth.oauth1_token:
                return True
            return False
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
            # Use garminconnect's built-in get_user_profile method
            data = self._client.get_user_profile() or {}
            status_code = 200
            return data
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get user profile: {e}")
            raise GarminAPIError(f"Failed to get user profile: {e}") from e
        finally:
            self._observe_api_call("get_user_profile", status_code, start_time)

    def get_gear(self, user_profile_number: str) -> list[dict[str, Any]]:
        """Get all gear (shoes, bikes, etc.) for user.

        Args:
            user_profile_number: User's Garmin profile number.

        Returns:
            List of gear items.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_gear(user_profile_number)
            status_code = 200
            # API returns dict with gear list
            if isinstance(data, dict):
                return data.get("gearDTOList", []) or data.get("gear", []) or []
            return data if isinstance(data, list) else []
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get gear: {e}")
            raise GarminAPIError(f"Failed to get gear: {e}") from e
        finally:
            self._observe_api_call("get_gear", status_code, start_time)

    def get_gear_stats(self, gear_uuid: str) -> dict[str, Any]:
        """Get statistics for a specific gear item.

        Args:
            gear_uuid: UUID of the gear item.

        Returns:
            Gear statistics including total distance, activity count, etc.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_gear_stats(gear_uuid)
            status_code = 200
            return data if isinstance(data, dict) else {}
        except Exception as e:
            status_code = 500
            logger.warning(f"Failed to get gear stats for {gear_uuid}: {e}")
            return {}  # Return empty dict on error to allow sync to continue
        finally:
            self._observe_api_call("get_gear_stats", status_code, start_time)

    def get_activity_gear(self, activity_id: int) -> list[dict[str, Any]]:
        """Get gear associated with a specific activity.

        Args:
            activity_id: Garmin activity ID.

        Returns:
            List of gear items used in activity.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_activity_gear(activity_id)
            status_code = 200
            # API returns list of gear or dict with list
            if isinstance(data, dict):
                return data.get("gearDTOList", []) or data.get("gear", []) or []
            return data if isinstance(data, list) else []
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get activity gear: {e}")
            raise GarminAPIError(f"Failed to get activity gear: {e}") from e
        finally:
            self._observe_api_call("get_activity_gear", status_code, start_time)

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
            # Download FIT file bytes (may be ZIP-compressed)
            raw_data = self._client.download_activity(
                activity_id,
                dl_fmt=self._client.ActivityDownloadFormat.ORIGINAL,
            )

            if not raw_data:
                raise GarminAPIError(f"No FIT data returned for activity {activity_id}")

            # Extract FIT from ZIP if needed (Garmin returns ZIP archives)
            fit_data = self._extract_fit_from_zip(raw_data)

            # Calculate hash for deduplication
            file_hash = hashlib.sha256(fit_data).hexdigest()

            # Determine save path
            storage_dir = save_dir or settings.fit_storage_path
            Path(storage_dir).mkdir(parents=True, exist_ok=True)

            file_name = f"{activity_id}.fit"
            file_path = os.path.join(storage_dir, file_name)

            # Save extracted FIT file (not ZIP)
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

    def _extract_fit_from_zip(self, data: bytes) -> bytes:
        """Extract FIT file from ZIP archive if needed.

        Garmin API returns FIT files wrapped in ZIP archives.
        This method extracts the actual FIT data.

        Args:
            data: Raw bytes that may be ZIP or FIT format.

        Returns:
            Extracted FIT file bytes.

        Raises:
            GarminAPIError: If extraction fails.
        """
        # Check if data is a ZIP file (starts with PK magic bytes)
        if data[:2] == b"PK":
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    # Find .fit file in archive
                    fit_files = [f for f in zf.namelist() if f.lower().endswith(".fit")]
                    if not fit_files:
                        raise GarminAPIError("No .fit file found in ZIP archive")

                    # Extract the first .fit file
                    fit_filename = fit_files[0]
                    logger.debug(f"Extracting {fit_filename} from ZIP archive")
                    return zf.read(fit_filename)
            except zipfile.BadZipFile as e:
                raise GarminAPIError(f"Invalid ZIP archive: {e}") from e
        else:
            # Already raw FIT data
            return data

    def parse_fit_file(self, fit_data: bytes) -> dict[str, Any]:
        """Parse FIT file and extract detailed data.

        Extracts Runalyze+ level data including:
        - Records (time series): HR, pace, cadence, altitude, power, etc.
        - Laps: splits, HR zones, pace per lap
        - Session: summary statistics
        - Device info

        Args:
            fit_data: Raw FIT file bytes (may be ZIP-compressed).

        Returns:
            Parsed data dict with records, laps, session, and device info.

        Raises:
            GarminAPIError: If parsing fails.
        """
        try:
            from fitparse import FitFile

            # Extract FIT data from ZIP if needed
            actual_fit_data = self._extract_fit_from_zip(fit_data)

            fit_file = FitFile(actual_fit_data)
            result: dict[str, Any] = {
                "records": [],
                "laps": [],
                "session": {},
                "device_info": [],  # List of all device_info records
                "events": [],
                "hrv": [],
                "sensors": {  # Detected sensors
                    "has_stryd": False,
                    "has_external_hr": False,
                },
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
                    result["device_info"].append(record_data)
                    # Detect sensors from device_info
                    manufacturer = record_data.get("manufacturer")
                    device_type = record_data.get("device_type")
                    # Stryd detection
                    if manufacturer == "stryd":
                        result["sensors"]["has_stryd"] = True
                    # External HR monitor detection (device_type 120 = ANT+ HR)
                    if device_type == 120:
                        result["sensors"]["has_external_hr"] = True
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
        result = {k: data.get(k) for k in fields if data.get(k) is not None}

        # Handle Stryd-specific fields (different casing)
        # Stryd uses "Power" instead of "power"
        if result.get("power") is None and data.get("Power") is not None:
            result["power"] = data.get("Power")
        if data.get("Form Power") is not None:
            result["form_power"] = data.get("Form Power")
        if data.get("Leg Spring Stiffness") is not None:
            result["leg_spring_stiffness"] = data.get("Leg Spring Stiffness")
        if data.get("Air Power") is not None:
            result["air_power"] = data.get("Air Power")

        return result

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
    # Workout Upload
    # -------------------------------------------------------------------------

    def upload_running_workout_template(self, workout: Any) -> int:
        """Upload a running workout template to Garmin Connect.

        Args:
            workout: Workout model with structure steps.

        Returns:
            Garmin workout ID.

        Raises:
            GarminAPIError: If upload fails or workout is invalid.
        """
        self._ensure_authenticated()

        if not workout or not getattr(workout, "structure", None):
            raise GarminAPIError("Workout structure is required for Garmin upload")

        try:
            from garminconnect.workout import (
                ConditionType,
                ExecutableStep,
                RunningWorkout,
                StepType,
                TargetType,
                WorkoutSegment,
            )
        except ImportError as exc:
            raise GarminAPIError(
                "garminconnect workout models unavailable (pydantic missing?)"
            ) from exc

        step_type_map = {
            "warmup": (StepType.WARMUP, "warmup", 1),
            "cooldown": (StepType.COOLDOWN, "cooldown", 2),
            "main": (StepType.INTERVAL, "interval", 3),
            "interval": (StepType.INTERVAL, "interval", 3),
            "recovery": (StepType.RECOVERY, "recovery", 4),
            "rest": (StepType.REST, "rest", 5),
        }

        fallback_pace = DEFAULT_ESTIMATED_PACE_SECONDS
        steps = []
        total_duration = 0.0

        for index, step in enumerate(workout.structure, start=1):
            step_type_key = (step.get("type") or "main").lower()
            step_type = step_type_map.get(step_type_key, step_type_map["main"])

            duration_minutes = step.get("duration_minutes")
            distance_km = step.get("distance_km")
            target_pace = _parse_pace_seconds(step.get("target_pace"))

            if target_pace:
                fallback_pace = target_pace

            if distance_km:
                end_condition = {
                    "conditionTypeId": ConditionType.DISTANCE,
                    "conditionTypeKey": "distance",
                    "displayOrder": 1,
                    "displayable": True,
                }
                end_value = float(distance_km) * 1000
                duration_seconds = float(distance_km) * float(fallback_pace)
            else:
                end_condition = {
                    "conditionTypeId": ConditionType.TIME,
                    "conditionTypeKey": "time",
                    "displayOrder": 2,
                    "displayable": True,
                }
                duration_seconds = float(duration_minutes or 0) * 60
                if duration_seconds <= 0:
                    duration_seconds = 300.0
                end_value = duration_seconds

            total_duration += duration_seconds

            steps.append(
                ExecutableStep(
                    stepOrder=index,
                    stepType={
                        "stepTypeId": step_type[0],
                        "stepTypeKey": step_type[1],
                        "displayOrder": step_type[2],
                    },
                    endCondition=end_condition,
                    endConditionValue=end_value,
                    targetType={
                        "workoutTargetTypeId": TargetType.NO_TARGET,
                        "workoutTargetTypeKey": "no.target",
                        "displayOrder": 1,
                    },
                )
            )

        if total_duration <= 0:
            total_duration = float(len(steps) * 300)

        running_workout = RunningWorkout(
            workoutName=workout.name,
            estimatedDurationInSecs=int(total_duration),
            workoutSegments=[
                WorkoutSegment(
                    segmentOrder=1,
                    sportType={
                        "sportTypeId": 1,
                        "sportTypeKey": "running",
                        "displayOrder": 1,
                    },
                    workoutSteps=steps,
                )
            ],
        )

        response = self._client.upload_running_workout(running_workout)
        workout_id = None
        for key in ("workoutId", "workout_id", "id"):
            if isinstance(response, dict) and response.get(key):
                workout_id = response.get(key)
                break

        if not workout_id:
            raise GarminAPIError(f"Garmin workout upload failed: {response}")

        return int(workout_id)

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
    # Workout Import
    # -------------------------------------------------------------------------

    def get_workouts(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get workouts from Garmin Connect.

        Args:
            limit: Maximum number of workouts to fetch.

        Returns:
            List of workout dicts.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_workouts(0, limit)
            status_code = 200
            return data or []
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get workouts: {e}")
            raise GarminAPIError(f"Failed to get workouts: {e}") from e
        finally:
            self._observe_api_call("get_workouts", status_code, start_time)

    def get_workout_by_id(self, workout_id: int) -> dict[str, Any]:
        """Get a specific workout from Garmin Connect.

        Args:
            workout_id: Garmin workout ID.

        Returns:
            Workout data dict.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            data = self._client.get_workout_by_id(workout_id)
            status_code = 200
            return data or {}
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get workout {workout_id}: {e}")
            raise GarminAPIError(f"Failed to get workout: {e}") from e
        finally:
            self._observe_api_call("get_workout_by_id", status_code, start_time)

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

    def get_all_day_events(self, target_date: date) -> dict[str, Any]:
        """Get all-day events from Garmin Connect for a specific date.

        This includes autodetected activities and scheduled events.

        Args:
            target_date: Date to get events for.

        Returns:
            Dictionary with event data.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        try:
            date_str = target_date.isoformat()  # YYYY-MM-DD format
            data = self._client.get_all_day_events(date_str)
            status_code = 200
            
            # Log raw response for debugging - use INFO level so we can see it
            if data:
                # Use DEBUG level for data details to avoid logging sensitive information
                logger.debug(f"get_all_day_events for {date_str} returned: type={type(data)}")
                if isinstance(data, dict):
                    logger.debug(f"Dict keys: {list(data.keys())}")
                    logger.debug(f"Dict has {len(data)} keys")
                elif isinstance(data, list):
                    logger.debug(f"List with {len(data)} items")
                    if data and isinstance(data[0], dict):
                        logger.debug(f"First item keys: {list(data[0].keys())}")
                # Summary only at INFO level (no sensitive data)
                logger.info(f"get_all_day_events for {date_str}: fetched {len(data) if isinstance(data, (list, dict)) else 0} items")

            return data or {}
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get all-day events for {target_date}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            raise GarminAPIError(f"Failed to get all-day events: {e}") from e
        finally:
            self._observe_api_call("get_all_day_events", status_code, start_time)

    def get_events_in_range(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Get all-day events from Garmin Connect for a date range.

        Iterates through dates and collects events. Note: This may make
        multiple API calls (one per day).

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            List of event dictionaries with date information.

        Raises:
            GarminAPIError: If API call fails.
        """
        self._ensure_authenticated()
        start_time = time.perf_counter()
        status_code = 500
        events: list[dict[str, Any]] = []
        
        try:
            current_date = start_date
            from datetime import timedelta
            
            while current_date <= end_date:
                try:
                    date_events = self.get_all_day_events(current_date)
                    # Add date info to each event for reference
                    if date_events:
                        # Log structure for debugging
                        logger.info(f"Processing events for {current_date}: type={type(date_events)}")
                        
                        event_list: list[dict[str, Any]] = []
                        
                        # Handle different response structures
                        if isinstance(date_events, dict):
                            # Try multiple possible keys for events
                            for key in ["events", "calendarEvents", "calendar_events", "items", "data", "calendarList"]:
                                if key in date_events:
                                    value = date_events[key]
                                    if isinstance(value, list):
                                        event_list.extend(value)
                                        logger.debug(f"Found {len(value)} events in key '{key}'")
                                        break
                                    elif isinstance(value, dict):
                                        # Nested dict might contain events
                                        for nested_key in ["events", "items"]:
                                            if nested_key in value and isinstance(value[nested_key], list):
                                                event_list.extend(value[nested_key])
                                                logger.debug(f"Found {len(value[nested_key])} events in nested key '{key}.{nested_key}'")
                                                break
                            
                            # If no list found in common keys, check if dict itself is event data
                            if not event_list:
                                # Check if this dict looks like a single event (has common event fields)
                                event_fields = ["eventName", "name", "title", "eventTypeName", "eventTypeId", "eventTypeKey", "eventTypeDesc"]
                                if any(key in date_events for key in event_fields):
                                    event_list = [date_events]
                                    logger.debug(f"Treating dict as single event with keys: {list(date_events.keys())}")
                                else:
                                    # Log all keys to help debug - use INFO so we can see it
                                    logger.info(f"Dict doesn't look like an event. All keys: {list(date_events.keys())}")
                                    # Try to extract any nested structures
                                    for k, v in date_events.items():
                                        if isinstance(v, (list, dict)):
                                            logger.info(f"  Key '{k}': type={type(v)}, length={len(v) if isinstance(v, (list, dict)) else 'N/A'}")
                                            if isinstance(v, list) and v:
                                                logger.info(f"    First item type: {type(v[0])}, keys: {list(v[0].keys()) if isinstance(v[0], dict) else 'N/A'}")
                                            elif isinstance(v, dict):
                                                logger.info(f"    Nested dict keys: {list(v.keys())}")
                                    # As last resort, if we see any list-like structure, try to use it
                                    for k, v in date_events.items():
                                        if isinstance(v, list) and len(v) > 0:
                                            logger.info(f"Found list in key '{k}' with {len(v)} items, trying to use it")
                                            event_list.extend(v)
                                            break
                        elif isinstance(date_events, list):
                            event_list = date_events
                            logger.info(f"Response is directly a list with {len(date_events)} items")
                        
                        # Add date to each event and append to results
                        for event in event_list:
                            if isinstance(event, dict):
                                event["event_date"] = current_date.isoformat()
                                events.append(event)
                                
                                # Log event details for debugging - use INFO so we can see it
                                event_name = event.get("eventName") or event.get("name") or event.get("title") or "Unknown"
                                event_keys = list(event.keys())
                                logger.info(f"Added event: '{event_name}' on {current_date}, keys: {event_keys}")
                            else:
                                logger.warning(f"Skipping non-dict event item: type={type(event)}, value={str(event)[:100]}")
                        
                        if event_list:
                            logger.info(f"Found {len(event_list)} events for {current_date}, total so far: {len(events)}")
                        else:
                            logger.info(f"No events extracted for {current_date} (raw response was not empty but parsing found no events)")
                            
                except Exception as e:
                    logger.warning(f"Failed to get events for {current_date}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    # Continue with next date even if one fails
                
                current_date += timedelta(days=1)
            
            status_code = 200
            return events
        except Exception as e:
            status_code = 500
            logger.error(f"Failed to get events in range {start_date} to {end_date}: {e}")
            raise GarminAPIError(f"Failed to get events in range: {e}") from e
        finally:
            self._observe_api_call("get_events_in_range", status_code, start_time)


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
