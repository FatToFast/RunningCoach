"""Code-based graders for deterministic evaluation.

These graders provide fast, objective, and reproducible scoring
for aspects that can be verified programmatically.
"""

import re
from typing import Any


def grade_vdot_accuracy(
    calculated_vdot: float,
    expected_vdot: float,
    tolerance: float = 2.0,
) -> dict[str, Any]:
    """Grade VDOT calculation accuracy.

    Args:
        calculated_vdot: VDOT value from the system
        expected_vdot: Expected VDOT from reference tables
        tolerance: Acceptable deviation

    Returns:
        Grading result with score and details
    """
    difference = abs(calculated_vdot - expected_vdot)
    passed = difference <= tolerance

    if difference == 0:
        score = 1.0
    elif passed:
        score = 1.0 - (difference / tolerance) * 0.5
    else:
        score = max(0, 0.5 - (difference - tolerance) / tolerance * 0.5)

    return {
        "passed": passed,
        "score": round(score, 3),
        "calculated": calculated_vdot,
        "expected": expected_vdot,
        "difference": round(difference, 2),
        "tolerance": tolerance,
        "message": f"VDOT {calculated_vdot:.1f} vs expected {expected_vdot:.1f} (diff: {difference:.1f})",
    }


def grade_pace_accuracy(
    calculated_pace: int,
    expected_pace: int,
    tolerance: int = 15,
) -> dict[str, Any]:
    """Grade training pace accuracy.

    Args:
        calculated_pace: Pace in seconds per km
        expected_pace: Expected pace from reference
        tolerance: Acceptable deviation in seconds

    Returns:
        Grading result with score and details
    """
    difference = abs(calculated_pace - expected_pace)
    passed = difference <= tolerance

    if difference == 0:
        score = 1.0
    elif passed:
        score = 1.0 - (difference / tolerance) * 0.3
    else:
        score = max(0, 0.7 - (difference - tolerance) / tolerance * 0.4)

    return {
        "passed": passed,
        "score": round(score, 3),
        "calculated": calculated_pace,
        "expected": expected_pace,
        "difference": difference,
        "tolerance": tolerance,
        "message": f"Pace {calculated_pace}s vs expected {expected_pace}s (diff: {difference}s)",
    }


def grade_weekly_mileage_progression(
    weekly_mileages: list[float],
    max_increase_percent: float = 10.0,
) -> dict[str, Any]:
    """Grade whether weekly mileage progression follows the 10% rule.

    Args:
        weekly_mileages: List of weekly distances in km
        max_increase_percent: Maximum allowed weekly increase

    Returns:
        Grading result with score and details
    """
    if len(weekly_mileages) < 2:
        return {
            "passed": True,
            "score": 1.0,
            "message": "Insufficient data for progression check",
            "violations": [],
        }

    violations = []
    total_weeks = len(weekly_mileages) - 1

    for i in range(1, len(weekly_mileages)):
        prev = weekly_mileages[i - 1]
        curr = weekly_mileages[i]

        if prev > 0:
            increase_percent = (curr - prev) / prev * 100
            if increase_percent > max_increase_percent:
                violations.append({
                    "week": i + 1,
                    "previous_km": round(prev, 1),
                    "current_km": round(curr, 1),
                    "increase_percent": round(increase_percent, 1),
                })

    passed = len(violations) == 0
    violation_rate = len(violations) / total_weeks if total_weeks > 0 else 0
    score = max(0, 1.0 - violation_rate * 1.5)

    return {
        "passed": passed,
        "score": round(score, 3),
        "violations": violations,
        "total_weeks": total_weeks,
        "max_increase_percent": max_increase_percent,
        "message": f"{len(violations)} violations in {total_weeks} weeks",
    }


def grade_rest_days(
    weekly_schedule: list[str],
    min_rest_days: int = 1,
    max_rest_days: int = 3,
) -> dict[str, Any]:
    """Grade whether rest days are appropriately scheduled.

    Args:
        weekly_schedule: List of workout types for each day
        min_rest_days: Minimum required rest days
        max_rest_days: Maximum reasonable rest days

    Returns:
        Grading result with score and details
    """
    rest_indicators = ["rest", "휴식", "off", "recovery", "회복"]
    rest_days = sum(
        1 for day in weekly_schedule
        if any(r in day.lower() for r in rest_indicators)
    )

    if rest_days < min_rest_days:
        passed = False
        score = rest_days / min_rest_days * 0.5
        message = f"Insufficient rest: {rest_days} days (min: {min_rest_days})"
    elif rest_days > max_rest_days:
        passed = True
        score = 0.8
        message = f"Many rest days: {rest_days} days (may be too conservative)"
    else:
        passed = True
        score = 1.0
        message = f"Appropriate rest: {rest_days} days"

    return {
        "passed": passed,
        "score": round(score, 3),
        "rest_days": rest_days,
        "min_required": min_rest_days,
        "max_recommended": max_rest_days,
        "message": message,
    }


def grade_tapering(
    weekly_mileages: list[float],
    race_week_index: int,
    expected_taper_reduction: float = 0.4,
) -> dict[str, Any]:
    """Grade whether tapering is properly implemented before race.

    Args:
        weekly_mileages: List of weekly distances
        race_week_index: Index of race week (0-based)
        expected_taper_reduction: Expected reduction (0.4 = 40% of peak)

    Returns:
        Grading result with score and details
    """
    if race_week_index < 2 or race_week_index >= len(weekly_mileages):
        return {
            "passed": False,
            "score": 0.0,
            "message": "Invalid race week index",
        }

    # Find peak week (excluding last 2 weeks)
    peak_mileage = max(weekly_mileages[:race_week_index - 1])
    race_week_mileage = weekly_mileages[race_week_index]

    expected_race_week = peak_mileage * expected_taper_reduction
    actual_reduction = race_week_mileage / peak_mileage if peak_mileage > 0 else 1.0

    # Score based on how close to expected taper
    if actual_reduction <= expected_taper_reduction + 0.1:
        passed = True
        score = 1.0 - abs(actual_reduction - expected_taper_reduction) * 2
    else:
        passed = False
        score = max(0, 0.5 - (actual_reduction - expected_taper_reduction - 0.1))

    return {
        "passed": passed,
        "score": round(max(0, score), 3),
        "peak_mileage": round(peak_mileage, 1),
        "race_week_mileage": round(race_week_mileage, 1),
        "actual_reduction": round(actual_reduction, 2),
        "expected_reduction": expected_taper_reduction,
        "message": f"Race week is {actual_reduction:.0%} of peak (expected: ~{expected_taper_reduction:.0%})",
    }


def grade_long_run_placement(
    weekly_schedule: list[dict],
    long_run_day_index: int | None = None,
) -> dict[str, Any]:
    """Grade whether long runs are placed appropriately (not after hard workouts).

    Args:
        weekly_schedule: List of daily workouts with type and intensity
        long_run_day_index: Expected long run day (None for auto-detect)

    Returns:
        Grading result with score and details
    """
    hard_indicators = ["interval", "tempo", "threshold", "인터벌", "템포", "역치"]
    long_indicators = ["long", "장거리", "롱런"]

    long_run_indices = []
    hard_workout_indices = []

    for i, day in enumerate(weekly_schedule):
        workout_type = day.get("type", "").lower()
        if any(l in workout_type for l in long_indicators):
            long_run_indices.append(i)
        if any(h in workout_type for h in hard_indicators):
            hard_workout_indices.append(i)

    # Check if long run follows hard workout
    violations = []
    for long_idx in long_run_indices:
        prev_idx = (long_idx - 1) % 7
        if prev_idx in hard_workout_indices:
            violations.append({
                "long_run_day": long_idx,
                "hard_workout_day": prev_idx,
                "message": "Long run follows hard workout",
            })

    passed = len(violations) == 0
    score = 1.0 - len(violations) * 0.3

    return {
        "passed": passed,
        "score": round(max(0, score), 3),
        "violations": violations,
        "long_run_days": long_run_indices,
        "hard_workout_days": hard_workout_indices,
        "message": f"Long run placement: {len(violations)} violations",
    }


def grade_intensity_distribution(
    workout_intensities: list[str],
    easy_percent_min: float = 70.0,
    hard_percent_max: float = 20.0,
) -> dict[str, Any]:
    """Grade whether intensity distribution follows 80/20 rule.

    Args:
        workout_intensities: List of intensity levels (easy, moderate, hard)
        easy_percent_min: Minimum percentage of easy workouts
        hard_percent_max: Maximum percentage of hard workouts

    Returns:
        Grading result with score and details
    """
    if not workout_intensities:
        return {
            "passed": False,
            "score": 0.0,
            "message": "No workout data",
        }

    easy_keywords = ["easy", "recovery", "이지", "회복", "휴식"]
    hard_keywords = ["interval", "tempo", "threshold", "hard", "인터벌", "템포", "역치", "강도"]

    easy_count = sum(
        1 for w in workout_intensities
        if any(k in w.lower() for k in easy_keywords)
    )
    hard_count = sum(
        1 for w in workout_intensities
        if any(k in w.lower() for k in hard_keywords)
    )
    total = len(workout_intensities)

    easy_percent = (easy_count / total) * 100 if total > 0 else 0
    hard_percent = (hard_count / total) * 100 if total > 0 else 0

    violations = []
    if easy_percent < easy_percent_min:
        violations.append(f"Easy workouts too low: {easy_percent:.0f}% (min: {easy_percent_min}%)")
    if hard_percent > hard_percent_max:
        violations.append(f"Hard workouts too high: {hard_percent:.0f}% (max: {hard_percent_max}%)")

    passed = len(violations) == 0
    score = 1.0
    if easy_percent < easy_percent_min:
        score -= (easy_percent_min - easy_percent) / 100
    if hard_percent > hard_percent_max:
        score -= (hard_percent - hard_percent_max) / 100

    return {
        "passed": passed,
        "score": round(max(0, score), 3),
        "easy_percent": round(easy_percent, 1),
        "hard_percent": round(hard_percent, 1),
        "easy_count": easy_count,
        "hard_count": hard_count,
        "total_workouts": total,
        "violations": violations,
        "message": f"Distribution: {easy_percent:.0f}% easy, {hard_percent:.0f}% hard",
    }


def grade_must_include_criteria(
    response_text: str,
    must_include: list[str],
) -> dict[str, Any]:
    """Grade whether response includes all required elements.

    Args:
        response_text: AI response text
        must_include: List of required keywords/phrases

    Returns:
        Grading result with score and details
    """
    response_lower = response_text.lower()
    found = []
    missing = []

    for item in must_include:
        if item.lower() in response_lower:
            found.append(item)
        else:
            missing.append(item)

    passed = len(missing) == 0
    score = len(found) / len(must_include) if must_include else 1.0

    return {
        "passed": passed,
        "score": round(score, 3),
        "found": found,
        "missing": missing,
        "total_required": len(must_include),
        "message": f"Found {len(found)}/{len(must_include)} required elements",
    }


def grade_must_not_include_criteria(
    response_text: str,
    must_not_include: list[str],
) -> dict[str, Any]:
    """Grade whether response avoids prohibited elements.

    Args:
        response_text: AI response text
        must_not_include: List of prohibited keywords/phrases

    Returns:
        Grading result with score and details
    """
    response_lower = response_text.lower()
    found_prohibited = []

    for item in must_not_include:
        if item.lower() in response_lower:
            found_prohibited.append(item)

    passed = len(found_prohibited) == 0
    score = 1.0 - (len(found_prohibited) / len(must_not_include)) if must_not_include else 1.0

    return {
        "passed": passed,
        "score": round(max(0, score), 3),
        "found_prohibited": found_prohibited,
        "total_prohibited": len(must_not_include),
        "message": f"Found {len(found_prohibited)} prohibited elements",
    }


def grade_weekly_mileage_range(
    actual_mileage: float,
    expected_range: tuple[float, float],
) -> dict[str, Any]:
    """Grade whether weekly mileage falls within expected range.

    Args:
        actual_mileage: Actual weekly mileage in km
        expected_range: (min_km, max_km) expected range

    Returns:
        Grading result with score and details
    """
    min_km, max_km = expected_range

    if min_km <= actual_mileage <= max_km:
        passed = True
        # Score higher for being in the middle of range
        mid = (min_km + max_km) / 2
        range_half = (max_km - min_km) / 2
        distance_from_mid = abs(actual_mileage - mid)
        score = 1.0 - (distance_from_mid / range_half) * 0.2
    else:
        passed = False
        if actual_mileage < min_km:
            score = max(0, 0.5 - (min_km - actual_mileage) / min_km)
        else:
            score = max(0, 0.5 - (actual_mileage - max_km) / max_km)

    return {
        "passed": passed,
        "score": round(score, 3),
        "actual_km": round(actual_mileage, 1),
        "expected_range": expected_range,
        "message": f"Mileage {actual_mileage:.1f}km (expected: {min_km}-{max_km}km)",
    }


def extract_weekly_mileages_from_plan(plan_text: str) -> list[float]:
    """Extract weekly mileages from a training plan text.

    Args:
        plan_text: Training plan text containing weekly distances

    Returns:
        List of weekly mileages in km
    """
    # Pattern: 주간 거리: 45km, 총 거리: 50km, etc.
    patterns = [
        r"주간\s*(?:거리|총)?\s*[:\s]*(\d+(?:\.\d+)?)\s*km",
        r"총\s*거리\s*[:\s]*(\d+(?:\.\d+)?)\s*km",
        r"(\d+(?:\.\d+)?)\s*km\s*/?\s*주",
        r"week(?:ly)?\s*(?:distance|total)?\s*[:\s]*(\d+(?:\.\d+)?)\s*km",
    ]

    mileages = []
    for pattern in patterns:
        matches = re.findall(pattern, plan_text.lower())
        for match in matches:
            try:
                mileages.append(float(match))
            except ValueError:
                pass

    return mileages


def extract_workout_types_from_plan(plan_text: str) -> list[str]:
    """Extract workout types from a training plan text.

    Args:
        plan_text: Training plan text

    Returns:
        List of workout type strings
    """
    # Common workout patterns
    workout_patterns = [
        r"(이지런|easy\s*run|회복\s*러닝|recovery)",
        r"(템포런|tempo\s*run|젖산역치|threshold)",
        r"(인터벌|interval|스피드\s*훈련)",
        r"(장거리|long\s*run|롱런)",
        r"(휴식|rest|off)",
        r"(크로스\s*트레이닝|cross\s*training|xt)",
    ]

    workouts = []
    for pattern in workout_patterns:
        matches = re.findall(pattern, plan_text.lower())
        workouts.extend(matches)

    return workouts
