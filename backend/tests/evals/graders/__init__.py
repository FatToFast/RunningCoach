"""Graders for AI evaluation.

Three types of graders:
1. Code-based: Fast, deterministic, objective (exact matching, regex, ranges)
2. LLM-based: Flexible, captures nuance (rubric scoring, natural language)
3. Human-based: Gold standard quality (expert review, calibration)
"""

from tests.evals.graders.code_graders import (
    grade_weekly_mileage_progression,
    grade_rest_days,
    grade_tapering,
    grade_long_run_placement,
    grade_intensity_distribution,
    grade_vdot_accuracy,
)
from tests.evals.graders.llm_graders import (
    grade_coaching_quality,
    grade_personalization,
    grade_safety_awareness,
)
from tests.evals.graders.rubric_graders import (
    COACHING_QUALITY_RUBRIC,
    TRAINING_PLAN_RUBRIC,
    apply_rubric,
)

__all__ = [
    "grade_weekly_mileage_progression",
    "grade_rest_days",
    "grade_tapering",
    "grade_long_run_placement",
    "grade_intensity_distribution",
    "grade_vdot_accuracy",
    "grade_coaching_quality",
    "grade_personalization",
    "grade_safety_awareness",
    "COACHING_QUALITY_RUBRIC",
    "TRAINING_PLAN_RUBRIC",
    "apply_rubric",
]
