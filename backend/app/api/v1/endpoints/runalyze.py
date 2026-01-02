"""Runalyze integration endpoints.

Runalyze API provides health metrics data:
- HRV (Heart Rate Variability) - RMSSD measurements
- Sleep data (duration, REM, deep sleep, quality)

API Reference: https://runalyze.com/help/article/personal-api
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
import httpx

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.models.user import User
from app.observability import get_metrics_backend


def _parse_datetime(value: str) -> datetime:
    """Parse datetime string with various ISO formats.

    Handles:
    - Standard ISO format: 2024-12-31T10:00:00
    - With Z suffix: 2024-12-31T10:00:00Z
    - With timezone offset: 2024-12-31T10:00:00+00:00
    - With microseconds: 2024-12-31T10:00:00.123456Z

    Args:
        value: Datetime string in ISO format.

    Returns:
        Parsed datetime object (always timezone-aware, defaults to UTC).

    Raises:
        ValueError: If format is not recognized.
    """
    # Handle Z suffix (common in APIs)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    # Try standard fromisoformat
    dt = datetime.fromisoformat(value)

    # Ensure timezone-aware (assume UTC if naive)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class RunalyzeStatusResponse(BaseModel):
    """Runalyze connection status."""

    connected: bool
    message: str


class HRVDataPoint(BaseModel):
    """HRV measurement data point."""

    id: int
    date_time: datetime
    hrv: float
    rmssd: float
    metric: str
    measurement_type: str


class HRVResponse(BaseModel):
    """HRV data response."""

    data: list[HRVDataPoint]
    count: int


class SleepDataPoint(BaseModel):
    """Sleep measurement data point."""

    id: int
    date_time: datetime
    duration: int  # minutes
    rem_duration: int | None = None
    light_sleep_duration: int | None = None
    deep_sleep_duration: int | None = None
    awake_duration: int | None = None
    quality: int | None = None  # 1-10
    source: str | None = None


class SleepResponse(BaseModel):
    """Sleep data response."""

    data: list[SleepDataPoint]
    count: int


class RunalyzeSummary(BaseModel):
    """Summary of Runalyze data."""

    latest_hrv: float | None = None
    latest_hrv_date: datetime | None = None
    avg_hrv_7d: float | None = None
    latest_sleep_quality: int | None = None
    latest_sleep_duration: int | None = None
    latest_sleep_date: datetime | None = None
    avg_sleep_quality_7d: float | None = None
    # Error tracking for partial data scenarios
    hrv_error: str | None = None
    sleep_error: str | None = None


class RunalyzeCalculations(BaseModel):
    """Training calculations from Runalyze (Runalyze-style metrics)."""

    effective_vo2max: float | None = None
    marathon_shape: float | None = None  # percentage (0-100)
    atl: float | None = None  # Acute Training Load (Fatigue) %
    ctl: float | None = None  # Chronic Training Load (Fitness) %
    tsb: float | None = None  # Training Stress Balance
    workload_ratio: float | None = None  # A:C ratio
    rest_days: float | None = None
    monotony: float | None = None  # percentage
    training_strain: float | None = None


class RunalyzeTrainingPaces(BaseModel):
    """Daniels-based training paces from Runalyze."""

    vdot: float
    easy_min: int  # seconds per km
    easy_max: int
    marathon_min: int
    marathon_max: int
    threshold_min: int
    threshold_max: int
    interval_min: int
    interval_max: int
    repetition_min: int
    repetition_max: int


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------


class RunalyzeNotConfiguredError(Exception):
    """Raised when Runalyze API token is not configured."""

    pass


async def _get_runalyze_client() -> httpx.AsyncClient:
    """Create configured Runalyze API client.

    Raises:
        RunalyzeNotConfiguredError: If API token is not configured.
    """
    if not settings.runalyze_api_token:
        raise RunalyzeNotConfiguredError("Runalyze API token not configured")

    # Ensure base_url doesn't have trailing slash (httpx handles path joining)
    base_url = settings.runalyze_api_base_url.rstrip("/")

    return httpx.AsyncClient(
        base_url=base_url,
        headers={"token": settings.runalyze_api_token},
        timeout=30.0,
    )


async def _runalyze_get(client: httpx.AsyncClient, path: str) -> httpx.Response:
    """Make GET request to Runalyze API.

    IMPORTANT: path must NOT start with '/' - httpx base_url path joining
    treats leading '/' as absolute path, overwriting base_url's path component.
    e.g., base_url="https://runalyze.com/api/v1" + path="/ping"
          → https://runalyze.com/ping (WRONG)
    Use path="ping" instead → https://runalyze.com/api/v1/ping (CORRECT)
    """
    metrics = get_metrics_backend()
    start_time = time.perf_counter()
    status_code = 500
    try:
        response = await client.get(path)
        status_code = response.status_code
        response.raise_for_status()
        return response
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.observe_external_api("runalyze", path, status_code, duration_ms)
        logger.info(
            "Runalyze API %s status=%s duration_ms=%.2f",
            path,
            status_code,
            duration_ms,
        )


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/status", response_model=RunalyzeStatusResponse)
async def get_runalyze_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> RunalyzeStatusResponse:
    """Check Runalyze API connection status.

    Args:
        current_user: Authenticated user.

    Returns:
        Connection status.
    """
    if not settings.runalyze_api_token:
        return RunalyzeStatusResponse(
            connected=False,
            message="Runalyze API token not configured",
        )

    try:
        async with await _get_runalyze_client() as client:
            response = await _runalyze_get(client, "ping")
            data = response.json()

            # Accept various "pong" response formats:
            # - ["pong"] (array)
            # - "pong" (string)
            # - {"status": "pong"} or {"message": "pong"} (object)
            is_pong = False
            if isinstance(data, list) and "pong" in data:
                is_pong = True
            elif isinstance(data, str) and data.lower() == "pong":
                is_pong = True
            elif isinstance(data, dict):
                if data.get("status") == "pong" or data.get("message") == "pong":
                    is_pong = True

            if is_pong:
                return RunalyzeStatusResponse(
                    connected=True,
                    message="Connected to Runalyze API",
                )
            else:
                logger.warning("Runalyze ping returned unexpected response: %s", data)
                return RunalyzeStatusResponse(
                    connected=False,
                    message=f"Unexpected ping response: {type(data).__name__}",
                )

    except RunalyzeNotConfiguredError:
        return RunalyzeStatusResponse(
            connected=False,
            message="Runalyze API token not configured",
        )
    except Exception as e:
        logger.exception("Runalyze connection check failed")
        return RunalyzeStatusResponse(
            connected=False,
            message="Connection failed. Please check your API token.",
        )


@router.get("/hrv", response_model=HRVResponse)
async def get_hrv_data(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(30, ge=1, le=365, description="Number of records to return"),
) -> HRVResponse:
    """Get HRV (Heart Rate Variability) data from Runalyze.

    HRV is measured as RMSSD (Root Mean Square of Successive Differences)
    and is typically recorded during sleep.

    Args:
        current_user: Authenticated user.
        limit: Maximum number of records.

    Returns:
        HRV measurements.
    """
    try:
        async with await _get_runalyze_client() as client:
            response = await _runalyze_get(client, "metrics/hrv")
            raw_data = response.json()

            # Parse and sort by date descending
            data_points = []
            skipped_count = 0
            for item in raw_data:
                try:
                    data_points.append(HRVDataPoint(
                        id=item["id"],
                        date_time=_parse_datetime(item["date_time"]),
                        hrv=item["hrv"],
                        rmssd=item.get("rmssd", item["hrv"]),
                        metric=item.get("metric", "rmssd"),
                        measurement_type=item.get("measurement_type", "unknown"),
                    ))
                except (KeyError, ValueError) as e:
                    skipped_count += 1
                    logger.debug("Skipped HRV item id=%s: %s", item.get("id"), e)
                    continue

            if skipped_count > 0:
                logger.warning("Skipped %d HRV items due to parsing errors", skipped_count)

            # Sort by date descending and limit
            data_points.sort(key=lambda x: x.date_time, reverse=True)
            data_points = data_points[:limit]

            return HRVResponse(
                data=data_points,
                count=len(data_points),
            )

    except RunalyzeNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Runalyze API token not configured",
        )
    except httpx.HTTPStatusError as e:
        logger.exception("Runalyze API error fetching HRV data")
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Runalyze API error. Please try again later.",
        )
    except Exception as e:
        logger.exception("Failed to fetch HRV data from Runalyze")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch HRV data. Please try again later.",
        )


@router.get("/sleep", response_model=SleepResponse)
async def get_sleep_data(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(30, ge=1, le=365, description="Number of records to return"),
) -> SleepResponse:
    """Get sleep data from Runalyze.

    Includes total duration, REM/light/deep sleep phases, and quality score.

    Args:
        current_user: Authenticated user.
        limit: Maximum number of records.

    Returns:
        Sleep measurements.
    """
    try:
        async with await _get_runalyze_client() as client:
            response = await _runalyze_get(client, "metrics/sleep")
            raw_data = response.json()

            # Parse and sort by date descending
            data_points = []
            skipped_count = 0
            for item in raw_data:
                try:
                    data_points.append(SleepDataPoint(
                        id=item["id"],
                        date_time=_parse_datetime(item["date_time"]),
                        duration=item["duration"],
                        rem_duration=item.get("rem_duration"),
                        light_sleep_duration=item.get("light_sleep_duration"),
                        deep_sleep_duration=item.get("deep_sleep_duration"),
                        awake_duration=item.get("awake_duration"),
                        quality=item.get("quality"),
                        source=item.get("source"),
                    ))
                except (KeyError, ValueError) as e:
                    skipped_count += 1
                    logger.debug("Skipped sleep item id=%s: %s", item.get("id"), e)
                    continue

            if skipped_count > 0:
                logger.warning("Skipped %d sleep items due to parsing errors", skipped_count)

            # Sort by date descending and limit
            data_points.sort(key=lambda x: x.date_time, reverse=True)
            data_points = data_points[:limit]

            return SleepResponse(
                data=data_points,
                count=len(data_points),
            )

    except RunalyzeNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Runalyze API token not configured",
        )
    except httpx.HTTPStatusError as e:
        logger.exception("Runalyze API error fetching sleep data")
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Runalyze API error. Please try again later.",
        )
    except Exception as e:
        logger.exception("Failed to fetch sleep data from Runalyze")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch sleep data. Please try again later.",
        )


@router.get("/summary", response_model=RunalyzeSummary)
async def get_runalyze_summary(
    current_user: Annotated[User, Depends(get_current_user)],
) -> RunalyzeSummary:
    """Get a summary of recent Runalyze health metrics.

    Includes latest HRV, sleep quality, and 7-day averages.

    Args:
        current_user: Authenticated user.

    Returns:
        Health metrics summary.
    """
    summary = RunalyzeSummary()

    try:
        async with await _get_runalyze_client() as client:
            # Fetch HRV data
            try:
                hrv_response = await _runalyze_get(client, "metrics/hrv")
                if hrv_response.status_code == 200:
                    hrv_data = hrv_response.json()
                    if hrv_data:
                        # Sort by date
                        hrv_sorted = sorted(
                            hrv_data,
                            key=lambda x: x.get("date_time", ""),
                            reverse=True,
                        )

                        if hrv_sorted:
                            summary.latest_hrv = hrv_sorted[0].get("hrv")
                            try:
                                summary.latest_hrv_date = _parse_datetime(
                                    hrv_sorted[0]["date_time"]
                                )
                            except (KeyError, ValueError):
                                pass

                            # 7-day average (based on actual dates, not record count)
                            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
                            recent_hrv = []
                            for h in hrv_sorted:
                                try:
                                    dt = _parse_datetime(h["date_time"])
                                    if dt >= seven_days_ago and h.get("hrv"):
                                        recent_hrv.append(h["hrv"])
                                except (KeyError, ValueError):
                                    continue
                            if recent_hrv:
                                summary.avg_hrv_7d = round(sum(recent_hrv) / len(recent_hrv), 1)
                else:
                    summary.hrv_error = f"API returned status {hrv_response.status_code}"
            except httpx.HTTPStatusError as e:
                summary.hrv_error = f"HTTP error: {e.response.status_code}"
                logger.warning("Runalyze HRV API error in summary: %s", e)
            except Exception as e:
                summary.hrv_error = "Failed to fetch HRV data"
                logger.warning("Failed to fetch HRV data for summary: %s", e)

            # Fetch sleep data
            try:
                sleep_response = await _runalyze_get(client, "metrics/sleep")
                if sleep_response.status_code == 200:
                    sleep_data = sleep_response.json()
                    if sleep_data:
                        # Sort by date
                        sleep_sorted = sorted(
                            sleep_data,
                            key=lambda x: x.get("date_time", ""),
                            reverse=True,
                        )

                        if sleep_sorted:
                            summary.latest_sleep_quality = sleep_sorted[0].get("quality")
                            summary.latest_sleep_duration = sleep_sorted[0].get("duration")
                            try:
                                summary.latest_sleep_date = _parse_datetime(
                                    sleep_sorted[0]["date_time"]
                                )
                            except (KeyError, ValueError):
                                pass

                            # 7-day average quality (based on actual dates)
                            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
                            recent_quality = []
                            for s in sleep_sorted:
                                try:
                                    dt = _parse_datetime(s["date_time"])
                                    if dt >= seven_days_ago and s.get("quality") is not None:
                                        recent_quality.append(s["quality"])
                                except (KeyError, ValueError):
                                    continue
                            if recent_quality:
                                summary.avg_sleep_quality_7d = round(
                                    sum(recent_quality) / len(recent_quality), 1
                                )
                else:
                    summary.sleep_error = f"API returned status {sleep_response.status_code}"
            except httpx.HTTPStatusError as e:
                summary.sleep_error = f"HTTP error: {e.response.status_code}"
                logger.warning("Runalyze sleep API error in summary: %s", e)
            except Exception as e:
                summary.sleep_error = "Failed to fetch sleep data"
                logger.warning("Failed to fetch sleep data for summary: %s", e)

    except RunalyzeNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Runalyze API token not configured",
        )
    except httpx.HTTPStatusError as e:
        # Connection-level error - set both
        error_msg = f"HTTP error: {e.response.status_code}"
        summary.hrv_error = error_msg
        summary.sleep_error = error_msg
        logger.warning("Runalyze API connection error: %s", e)
    except Exception as e:
        # Connection-level error - set both
        error_msg = "Failed to connect to Runalyze"
        summary.hrv_error = error_msg
        summary.sleep_error = error_msg
        logger.warning("Failed to connect to Runalyze for summary: %s", e)

    return summary


@router.get("/calculations", response_model=RunalyzeCalculations)
async def get_runalyze_calculations(
    current_user: Annotated[User, Depends(get_current_user)],
) -> RunalyzeCalculations:
    """Get training calculations from Runalyze.

    Includes VO2max, marathon shape, ATL/CTL/TSB, workload ratio,
    rest days, monotony, and training strain.

    Args:
        current_user: Authenticated user.

    Returns:
        Training calculations.
    """
    calculations = RunalyzeCalculations()

    try:
        async with await _get_runalyze_client() as client:
            # Try /metrics/calculations endpoint
            try:
                response = await _runalyze_get(client, "metrics/calculations")
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        calculations.effective_vo2max = data.get("effective_vo2max") or data.get("vo2max")
                        calculations.marathon_shape = data.get("marathon_shape")
                        calculations.atl = data.get("atl") or data.get("fatigue")
                        calculations.ctl = data.get("ctl") or data.get("fitness")
                        calculations.tsb = data.get("tsb") or data.get("stress_balance")
                        calculations.workload_ratio = data.get("workload_ratio") or data.get("ac_ratio")
                        calculations.rest_days = data.get("rest_days")
                        calculations.monotony = data.get("monotony")
                        calculations.training_strain = data.get("training_strain")
            except Exception as e:
                logger.warning("Failed to fetch calculations from Runalyze: %s", e)

            # Fallback: try individual endpoints if /metrics/calculations fails
            if calculations.effective_vo2max is None:
                try:
                    vo2max_response = await _runalyze_get(client, "metrics/vo2max")
                    if vo2max_response.status_code == 200:
                        vo2max_data = vo2max_response.json()
                        if vo2max_data and isinstance(vo2max_data, list) and len(vo2max_data) > 0:
                            # Get latest VO2max
                            sorted_data = sorted(
                                vo2max_data,
                                key=lambda x: x.get("date_time", ""),
                                reverse=True,
                            )
                            calculations.effective_vo2max = sorted_data[0].get("value") or sorted_data[0].get("vo2max")
                except Exception as e:
                    logger.debug("Failed to fetch VO2max from Runalyze: %s", e)

            # Try fitness endpoint for ATL/CTL/TSB
            if calculations.ctl is None:
                try:
                    fitness_response = await _runalyze_get(client, "metrics/fitness")
                    if fitness_response.status_code == 200:
                        fitness_data = fitness_response.json()
                        if fitness_data:
                            if isinstance(fitness_data, list) and len(fitness_data) > 0:
                                # Get latest fitness data
                                sorted_data = sorted(
                                    fitness_data,
                                    key=lambda x: x.get("date", x.get("date_time", "")),
                                    reverse=True,
                                )
                                latest = sorted_data[0]
                                calculations.ctl = latest.get("ctl") or latest.get("fitness")
                                calculations.atl = latest.get("atl") or latest.get("fatigue")
                                calculations.tsb = latest.get("tsb") or latest.get("form")
                            elif isinstance(fitness_data, dict):
                                calculations.ctl = fitness_data.get("ctl") or fitness_data.get("fitness")
                                calculations.atl = fitness_data.get("atl") or fitness_data.get("fatigue")
                                calculations.tsb = fitness_data.get("tsb") or fitness_data.get("form")
                except Exception as e:
                    logger.debug("Failed to fetch fitness data from Runalyze: %s", e)

    except RunalyzeNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Runalyze API token not configured",
        )
    except Exception as e:
        # Log and return empty calculations on error
        logger.warning("Failed to connect to Runalyze for calculations: %s", e)

    return calculations


@router.get("/training-paces", response_model=RunalyzeTrainingPaces | None)
async def get_runalyze_training_paces(
    current_user: Annotated[User, Depends(get_current_user)],
) -> RunalyzeTrainingPaces | None:
    """Get Daniels-based training paces from Runalyze.

    Returns pace zones for Easy, Marathon, Threshold, Interval, and Repetition.

    Args:
        current_user: Authenticated user.

    Returns:
        Training paces or None if not available.
    """
    try:
        async with await _get_runalyze_client() as client:
            # Try /metrics/paces or /training/paces endpoint
            for endpoint in ["metrics/paces", "training/paces", "paces"]:
                try:
                    response = await _runalyze_get(client, endpoint)
                    if response.status_code == 200:
                        data = response.json()
                        if data:
                            # Handle both direct object and array response
                            paces_data = data[0] if isinstance(data, list) and len(data) > 0 else data

                            # VDOT is required
                            vdot = paces_data.get("vdot")
                            if vdot is None:
                                continue

                            # Parse pace values (might be in different formats)
                            def parse_pace(value) -> int | None:
                                """Parse pace value to seconds per km."""
                                if value is None:
                                    return None
                                if isinstance(value, (int, float)):
                                    return int(value)
                                if isinstance(value, str):
                                    # Parse "5:30" format to seconds
                                    try:
                                        parts = value.split(":")
                                        if len(parts) == 2:
                                            return int(parts[0]) * 60 + int(parts[1])
                                        return int(value)
                                    except ValueError:
                                        return None
                                return None

                            # Get parsed values (no fallback to hardcoded values)
                            easy_min = parse_pace(paces_data.get("easy_min"))
                            easy_max = parse_pace(paces_data.get("easy_max"))
                            marathon_min = parse_pace(paces_data.get("marathon_min"))
                            marathon_max = parse_pace(paces_data.get("marathon_max"))
                            threshold_min = parse_pace(paces_data.get("threshold_min"))
                            threshold_max = parse_pace(paces_data.get("threshold_max"))
                            interval_min = parse_pace(paces_data.get("interval_min"))
                            interval_max = parse_pace(paces_data.get("interval_max"))
                            repetition_min = parse_pace(paces_data.get("repetition_min"))
                            repetition_max = parse_pace(paces_data.get("repetition_max"))

                            # Check if we have essential pace data (at least easy paces)
                            if easy_min is None or easy_max is None:
                                logger.warning(
                                    "Runalyze returned incomplete pace data for VDOT %.1f",
                                    vdot,
                                )
                                continue

                            return RunalyzeTrainingPaces(
                                vdot=float(vdot),
                                easy_min=easy_min,
                                easy_max=easy_max,
                                marathon_min=marathon_min or easy_min,  # Fallback to easy if missing
                                marathon_max=marathon_max or easy_max,
                                threshold_min=threshold_min or marathon_min or easy_min,
                                threshold_max=threshold_max or marathon_max or easy_max,
                                interval_min=interval_min or threshold_min or easy_min,
                                interval_max=interval_max or threshold_max or easy_max,
                                repetition_min=repetition_min or interval_min or easy_min,
                                repetition_max=repetition_max or interval_max or easy_max,
                            )
                except Exception as e:
                    logger.debug("Failed to fetch paces from %s: %s", endpoint, e)
                    continue

    except RunalyzeNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Runalyze API token not configured",
        )
    except Exception as e:
        logger.warning("Failed to connect to Runalyze for training paces: %s", e)

    return None
