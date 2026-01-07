"""VDOT calculation service based on Jack Daniels' Running Formula.

This module provides functions to calculate VDOT from race results
and derive training paces for different workout types.
"""

import math
from dataclasses import dataclass
from typing import Literal


TrainingPaceType = Literal["easy", "marathon", "threshold", "interval", "repetition"]


@dataclass
class TrainingPaces:
    """Training paces derived from VDOT.

    All paces are in seconds per kilometer.
    """

    easy_min: int  # Easy pace range (slow end)
    easy_max: int  # Easy pace range (fast end)
    marathon: int
    threshold: int
    interval: int
    repetition: int

    def to_dict(self) -> dict:
        """Convert to dictionary with formatted pace strings."""
        return {
            "easy": {
                "min_sec_per_km": self.easy_min,
                "max_sec_per_km": self.easy_max,
                "min_pace": _format_pace(self.easy_min),
                "max_pace": _format_pace(self.easy_max),
            },
            "marathon": {
                "sec_per_km": self.marathon,
                "pace": _format_pace(self.marathon),
            },
            "threshold": {
                "sec_per_km": self.threshold,
                "pace": _format_pace(self.threshold),
            },
            "interval": {
                "sec_per_km": self.interval,
                "pace": _format_pace(self.interval),
            },
            "repetition": {
                "sec_per_km": self.repetition,
                "pace": _format_pace(self.repetition),
            },
        }


@dataclass
class RaceEquivalent:
    """Equivalent race times for a given VDOT."""

    distance_name: str
    distance_km: float
    time_seconds: int

    def to_dict(self) -> dict:
        """Convert to dictionary with formatted time."""
        return {
            "distance_name": self.distance_name,
            "distance_km": self.distance_km,
            "time_seconds": self.time_seconds,
            "time_formatted": _format_time(self.time_seconds),
        }


@dataclass
class VDOTResult:
    """Complete VDOT calculation result."""

    vdot: float
    training_paces: TrainingPaces
    race_equivalents: list[RaceEquivalent]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "vdot": round(self.vdot, 1),
            "training_paces": self.training_paces.to_dict(),
            "race_equivalents": [r.to_dict() for r in self.race_equivalents],
        }


# Standard race distances in meters
RACE_DISTANCES = {
    "5K": 5000,
    "10K": 10000,
    "Half Marathon": 21097.5,
    "Marathon": 42195,
}


def calculate_vdot(distance_meters: float, time_seconds: float) -> float:
    """Calculate VDOT from a race result.

    Based on Jack Daniels' formulas from "Daniels' Running Formula".

    Args:
        distance_meters: Race distance in meters.
        time_seconds: Race time in seconds.

    Returns:
        VDOT value (typically between 30-85 for most runners).
    """
    time_minutes = time_seconds / 60.0
    velocity = distance_meters / time_minutes  # meters per minute

    # Calculate VO2 (oxygen cost of running at this velocity)
    vo2 = -4.60 + 0.182258 * velocity + 0.000104 * (velocity**2)

    # Calculate %VO2max (fraction of VO2max used for this duration)
    pct_vo2max = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * time_minutes)
        + 0.2989558 * math.exp(-0.1932605 * time_minutes)
    )

    # VDOT = VO2 / %VO2max
    vdot = vo2 / pct_vo2max

    return vdot


def calculate_race_time(vdot: float, distance_meters: float) -> float:
    """Calculate expected race time for a given VDOT and distance.

    Uses iterative approach to solve for time.

    Args:
        vdot: VDOT value.
        distance_meters: Target distance in meters.

    Returns:
        Expected time in seconds.
    """
    # Initial guess based on rough approximation
    velocity_guess = vdot * 0.8  # rough m/min estimate
    time_guess = distance_meters / velocity_guess * 60  # seconds

    # Newton-Raphson iteration to find time
    for _ in range(50):  # Max iterations
        time_minutes = time_guess / 60.0
        velocity = distance_meters / time_minutes

        # Calculate what VDOT this time would give
        vo2 = -4.60 + 0.182258 * velocity + 0.000104 * (velocity**2)
        pct_vo2max = (
            0.8
            + 0.1894393 * math.exp(-0.012778 * time_minutes)
            + 0.2989558 * math.exp(-0.1932605 * time_minutes)
        )
        calculated_vdot = vo2 / pct_vo2max

        # Adjust time based on difference
        if abs(calculated_vdot - vdot) < 0.01:
            break

        # If calculated VDOT is higher than target, we're running too fast (time too short)
        ratio = vdot / calculated_vdot
        time_guess = time_guess / ratio

    return time_guess


def get_training_paces(vdot: float) -> TrainingPaces:
    """Calculate training paces for a given VDOT.

    Based on Jack Daniels' training intensity zones.

    Args:
        vdot: VDOT value.

    Returns:
        TrainingPaces with paces in seconds per kilometer.
    """
    # Training intensities as fractions of VDOT
    # These are approximations based on Daniels' tables

    # Easy: 59-74% of VO2max
    easy_slow_vdot = vdot * 0.65
    easy_fast_vdot = vdot * 0.78

    # Marathon: ~79% of VO2max
    marathon_vdot = vdot * 0.84

    # Threshold: ~88% of VO2max
    threshold_vdot = vdot * 0.92

    # Interval: ~98% of VO2max
    interval_vdot = vdot * 0.98

    # Repetition: ~105% effort (using 1500m race pace approximation)
    rep_vdot = vdot * 1.02

    return TrainingPaces(
        easy_min=_vdot_to_pace(easy_slow_vdot),
        easy_max=_vdot_to_pace(easy_fast_vdot),
        marathon=_vdot_to_pace(marathon_vdot),
        threshold=_vdot_to_pace(threshold_vdot),
        interval=_vdot_to_pace(interval_vdot),
        repetition=_vdot_to_pace(rep_vdot),
    )


def get_race_equivalents(vdot: float) -> list[RaceEquivalent]:
    """Calculate equivalent race times for standard distances.

    Args:
        vdot: VDOT value.

    Returns:
        List of RaceEquivalent for standard distances.
    """
    equivalents = []
    for name, distance in RACE_DISTANCES.items():
        time_seconds = calculate_race_time(vdot, distance)
        equivalents.append(
            RaceEquivalent(
                distance_name=name,
                distance_km=distance / 1000,
                time_seconds=int(time_seconds),
            )
        )
    return equivalents


def get_vdot_result(distance_meters: float, time_seconds: float) -> VDOTResult:
    """Get complete VDOT analysis from a race result.

    Args:
        distance_meters: Race distance in meters.
        time_seconds: Race time in seconds.

    Returns:
        Complete VDOTResult with VDOT, training paces, and race equivalents.
    """
    vdot = calculate_vdot(distance_meters, time_seconds)
    paces = get_training_paces(vdot)
    equivalents = get_race_equivalents(vdot)

    return VDOTResult(
        vdot=vdot,
        training_paces=paces,
        race_equivalents=equivalents,
    )


def _vdot_to_pace(vdot: float) -> int:
    """Convert VDOT-like value to pace in seconds per km.

    Uses inverse of the VDOT formula to find velocity.
    """
    # For a sustained effort, approximate velocity from VDOT
    # VO2 ≈ VDOT * 0.9 (assuming ~90% VO2max utilization)
    vo2 = vdot * 0.9

    # Solve quadratic: VO2 = -4.60 + 0.182258 * v + 0.000104 * v^2
    # 0.000104 * v^2 + 0.182258 * v + (-4.60 - VO2) = 0
    a = 0.000104
    b = 0.182258
    c = -4.60 - vo2

    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        return 600  # fallback: 10:00/km

    velocity = (-b + math.sqrt(discriminant)) / (2 * a)  # m/min

    # Convert to seconds per km
    if velocity <= 0:
        return 600  # fallback

    pace_sec_per_km = 1000 / velocity * 60
    return int(pace_sec_per_km)


def _format_pace(seconds_per_km: int) -> str:
    """Format pace as M:SS string."""
    minutes = seconds_per_km // 60
    seconds = seconds_per_km % 60
    return f"{minutes}:{seconds:02d}"


def _format_time(total_seconds: int) -> str:
    """Format time as H:MM:SS or M:SS string."""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# Convenience functions for common distances
def vdot_from_5k(time_seconds: float) -> VDOTResult:
    """Calculate VDOT from 5K time."""
    return get_vdot_result(5000, time_seconds)


def vdot_from_10k(time_seconds: float) -> VDOTResult:
    """Calculate VDOT from 10K time."""
    return get_vdot_result(10000, time_seconds)


def vdot_from_half_marathon(time_seconds: float) -> VDOTResult:
    """Calculate VDOT from half marathon time."""
    return get_vdot_result(21097.5, time_seconds)


def vdot_from_marathon(time_seconds: float) -> VDOTResult:
    """Calculate VDOT from marathon time."""
    return get_vdot_result(42195, time_seconds)
