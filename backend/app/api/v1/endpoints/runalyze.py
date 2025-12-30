"""Runalyze integration endpoints.

Runalyze API provides health metrics data:
- HRV (Heart Rate Variability) - RMSSD measurements
- Sleep data (duration, REM, deep sleep, quality)

API Reference: https://runalyze.com/help/article/personal-api
"""

import logging
import time
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
import httpx

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import get_settings
from app.models.user import User
from app.observability import get_metrics_backend

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


async def _get_runalyze_client() -> httpx.AsyncClient:
    """Create configured Runalyze API client."""
    if not settings.runalyze_api_token:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Runalyze API token not configured",
        )

    return httpx.AsyncClient(
        base_url=settings.runalyze_api_base_url,
        headers={"token": settings.runalyze_api_token},
        timeout=30.0,
    )


async def _runalyze_get(client: httpx.AsyncClient, path: str) -> httpx.Response:
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
            response = await _runalyze_get(client, "/ping")
            data = response.json()

            if data == ["pong"]:
                return RunalyzeStatusResponse(
                    connected=True,
                    message="Connected to Runalyze API",
                )
            else:
                return RunalyzeStatusResponse(
                    connected=False,
                    message="Unexpected ping response",
                )

    except Exception as e:
        return RunalyzeStatusResponse(
            connected=False,
            message=f"Connection failed: {str(e)}",
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
            response = await _runalyze_get(client, "/metrics/hrv")
            raw_data = response.json()

            # Parse and sort by date descending
            data_points = []
            for item in raw_data:
                try:
                    data_points.append(HRVDataPoint(
                        id=item["id"],
                        date_time=datetime.fromisoformat(item["date_time"]),
                        hrv=item["hrv"],
                        rmssd=item.get("rmssd", item["hrv"]),
                        metric=item.get("metric", "rmssd"),
                        measurement_type=item.get("measurement_type", "unknown"),
                    ))
                except (KeyError, ValueError):
                    continue

            # Sort by date descending and limit
            data_points.sort(key=lambda x: x.date_time, reverse=True)
            data_points = data_points[:limit]

            return HRVResponse(
                data=data_points,
                count=len(data_points),
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Runalyze API error: {e.response.text}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch HRV data: {str(e)}",
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
            response = await _runalyze_get(client, "/metrics/sleep")
            raw_data = response.json()

            # Parse and sort by date descending
            data_points = []
            for item in raw_data:
                try:
                    data_points.append(SleepDataPoint(
                        id=item["id"],
                        date_time=datetime.fromisoformat(item["date_time"]),
                        duration=item["duration"],
                        rem_duration=item.get("rem_duration"),
                        light_sleep_duration=item.get("light_sleep_duration"),
                        deep_sleep_duration=item.get("deep_sleep_duration"),
                        awake_duration=item.get("awake_duration"),
                        quality=item.get("quality"),
                        source=item.get("source"),
                    ))
                except (KeyError, ValueError):
                    continue

            # Sort by date descending and limit
            data_points.sort(key=lambda x: x.date_time, reverse=True)
            data_points = data_points[:limit]

            return SleepResponse(
                data=data_points,
                count=len(data_points),
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Runalyze API error: {e.response.text}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch sleep data: {str(e)}",
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
                hrv_response = await _runalyze_get(client, "/metrics/hrv")
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
                                summary.latest_hrv_date = datetime.fromisoformat(
                                    hrv_sorted[0]["date_time"]
                                )
                            except (KeyError, ValueError):
                                pass

                            # 7-day average
                            recent_hrv = [h.get("hrv") for h in hrv_sorted[:7] if h.get("hrv")]
                            if recent_hrv:
                                summary.avg_hrv_7d = round(sum(recent_hrv) / len(recent_hrv), 1)
            except Exception:
                pass

            # Fetch sleep data
            try:
                sleep_response = await _runalyze_get(client, "/metrics/sleep")
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
                                summary.latest_sleep_date = datetime.fromisoformat(
                                    sleep_sorted[0]["date_time"]
                                )
                            except (KeyError, ValueError):
                                pass

                            # 7-day average quality
                            recent_quality = [
                                s.get("quality")
                                for s in sleep_sorted[:7]
                                if s.get("quality") is not None
                            ]
                            if recent_quality:
                                summary.avg_sleep_quality_7d = round(
                                    sum(recent_quality) / len(recent_quality), 1
                                )
            except Exception:
                pass

    except Exception:
        # Return empty summary on error
        pass

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
                response = await _runalyze_get(client, "/metrics/calculations")
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
            except Exception:
                pass

            # Fallback: try individual endpoints if /metrics/calculations fails
            if calculations.effective_vo2max is None:
                try:
                    vo2max_response = await _runalyze_get(client, "/metrics/vo2max")
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
                except Exception:
                    pass

            # Try fitness endpoint for ATL/CTL/TSB
            if calculations.ctl is None:
                try:
                    fitness_response = await _runalyze_get(client, "/metrics/fitness")
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
                except Exception:
                    pass

    except Exception:
        # Return empty calculations on error
        pass

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
            for endpoint in ["/metrics/paces", "/training/paces", "/paces"]:
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

                            return RunalyzeTrainingPaces(
                                vdot=float(vdot),
                                easy_min=parse_pace(paces_data.get("easy_min")) or 343,
                                easy_max=parse_pace(paces_data.get("easy_max")) or 430,
                                marathon_min=parse_pace(paces_data.get("marathon_min")) or 302,
                                marathon_max=parse_pace(paces_data.get("marathon_max")) or 338,
                                threshold_min=parse_pace(paces_data.get("threshold_min")) or 276,
                                threshold_max=parse_pace(paces_data.get("threshold_max")) or 288,
                                interval_min=parse_pace(paces_data.get("interval_min")) or 254,
                                interval_max=parse_pace(paces_data.get("interval_max")) or 267,
                                repetition_min=parse_pace(paces_data.get("repetition_min")) or 231,
                                repetition_max=parse_pace(paces_data.get("repetition_max")) or 242,
                            )
                except Exception:
                    continue

    except Exception:
        pass

    return None
