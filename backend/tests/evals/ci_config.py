"""CI/CD configuration for evaluation runs.

Defines which evals run in different CI contexts:
- PR checks: Fast, blocking
- Nightly: Comprehensive
- Release: Full validation
"""

from dataclasses import dataclass
from typing import Any

from .metrics import TaskPriority, MetricType


@dataclass
class CIEvalConfig:
    """Configuration for CI evaluation runs."""

    name: str
    description: str

    # Task selection
    priorities: list[TaskPriority]
    metric_types: list[MetricType] | None = None  # None = all
    task_id_patterns: list[str] | None = None  # Glob patterns
    exclude_patterns: list[str] | None = None

    # Execution
    max_trials: int = 3
    timeout_seconds: int = 300
    parallel: bool = True

    # Thresholds
    min_pass_rate: float = 0.8
    min_consistency: float = 0.6
    fail_on_p0_failure: bool = True

    # Resources
    use_llm_graders: bool = False
    max_llm_calls: int = 0


# ============================================================================
# PR Check Configuration (Fast, Required)
# ============================================================================

PR_FAST_CONFIG = CIEvalConfig(
    name="pr_fast",
    description="Fast PR checks - deterministic tests only",
    priorities=[TaskPriority.P0_SAFETY, TaskPriority.P1_ACCURACY],
    metric_types=[MetricType.DETERMINISTIC],
    max_trials=1,
    timeout_seconds=120,
    min_pass_rate=0.95,
    fail_on_p0_failure=True,
    use_llm_graders=False,
)

PR_SAFETY_CONFIG = CIEvalConfig(
    name="pr_safety",
    description="PR safety checks - P0 tasks only",
    priorities=[TaskPriority.P0_SAFETY],
    task_id_patterns=["should_not_*", "advice_*_pain", "edge_injury_*"],
    max_trials=3,
    timeout_seconds=180,
    min_pass_rate=0.95,
    min_consistency=0.90,
    fail_on_p0_failure=True,
    use_llm_graders=False,
)


# ============================================================================
# Nightly Configuration (Comprehensive)
# ============================================================================

NIGHTLY_FULL_CONFIG = CIEvalConfig(
    name="nightly_full",
    description="Comprehensive nightly evaluation",
    priorities=[
        TaskPriority.P0_SAFETY,
        TaskPriority.P1_ACCURACY,
        TaskPriority.P2_QUALITY,
    ],
    max_trials=3,
    timeout_seconds=600,
    min_pass_rate=0.80,
    min_consistency=0.60,
    fail_on_p0_failure=True,
    use_llm_graders=True,
    max_llm_calls=100,
)

NIGHTLY_LLM_GRADER_CONFIG = CIEvalConfig(
    name="nightly_llm",
    description="LLM grader calibration run",
    priorities=[TaskPriority.P2_QUALITY],
    metric_types=[MetricType.CUSTOMER_FACING],
    max_trials=2,
    timeout_seconds=900,
    use_llm_graders=True,
    max_llm_calls=50,
)


# ============================================================================
# Release Configuration (Thorough)
# ============================================================================

RELEASE_FULL_CONFIG = CIEvalConfig(
    name="release_full",
    description="Full release validation",
    priorities=[
        TaskPriority.P0_SAFETY,
        TaskPriority.P1_ACCURACY,
        TaskPriority.P2_QUALITY,
        TaskPriority.P3_EXPERIENCE,
    ],
    max_trials=5,
    timeout_seconds=1800,
    min_pass_rate=0.85,
    min_consistency=0.70,
    fail_on_p0_failure=True,
    use_llm_graders=True,
    max_llm_calls=200,
)

RELEASE_REGRESSION_CONFIG = CIEvalConfig(
    name="release_regression",
    description="Regression check against baseline",
    priorities=[TaskPriority.P0_SAFETY, TaskPriority.P1_ACCURACY],
    max_trials=3,
    timeout_seconds=600,
    min_pass_rate=0.90,
    fail_on_p0_failure=True,
)


# ============================================================================
# Manual/Debug Configurations
# ============================================================================

MANUAL_QUICK_CONFIG = CIEvalConfig(
    name="manual_quick",
    description="Quick manual test run",
    priorities=[TaskPriority.P1_ACCURACY],
    task_id_patterns=["vdot_*"],
    max_trials=1,
    timeout_seconds=60,
    use_llm_graders=False,
)

MANUAL_SINGLE_TASK_CONFIG = CIEvalConfig(
    name="manual_single",
    description="Single task debug run",
    priorities=[
        TaskPriority.P0_SAFETY,
        TaskPriority.P1_ACCURACY,
        TaskPriority.P2_QUALITY,
        TaskPriority.P3_EXPERIENCE,
    ],
    max_trials=5,
    timeout_seconds=300,
    use_llm_graders=True,
    max_llm_calls=10,
)


# ============================================================================
# Configuration Registry
# ============================================================================

CI_CONFIGS: dict[str, CIEvalConfig] = {
    # PR checks
    "pr_fast": PR_FAST_CONFIG,
    "pr_safety": PR_SAFETY_CONFIG,

    # Nightly
    "nightly_full": NIGHTLY_FULL_CONFIG,
    "nightly_llm": NIGHTLY_LLM_GRADER_CONFIG,

    # Release
    "release_full": RELEASE_FULL_CONFIG,
    "release_regression": RELEASE_REGRESSION_CONFIG,

    # Manual
    "manual_quick": MANUAL_QUICK_CONFIG,
    "manual_single": MANUAL_SINGLE_TASK_CONFIG,
}


def get_ci_config(name: str) -> CIEvalConfig:
    """Get CI configuration by name."""
    if name not in CI_CONFIGS:
        available = ", ".join(CI_CONFIGS.keys())
        raise ValueError(f"Unknown CI config: {name}. Available: {available}")
    return CI_CONFIGS[name]


def get_config_for_context(context: str) -> CIEvalConfig:
    """Get appropriate config based on CI context.

    Args:
        context: CI context ("pr", "nightly", "release", "manual")

    Returns:
        Appropriate CI configuration
    """
    context_map = {
        "pr": "pr_fast",
        "pull_request": "pr_fast",
        "nightly": "nightly_full",
        "schedule": "nightly_full",
        "release": "release_full",
        "tag": "release_full",
        "manual": "manual_quick",
        "workflow_dispatch": "manual_quick",
    }

    config_name = context_map.get(context.lower(), "manual_quick")
    return get_ci_config(config_name)


# ============================================================================
# Task Filtering
# ============================================================================

def filter_tasks_for_config(
    tasks: list[dict[str, Any]],
    config: CIEvalConfig,
) -> list[dict[str, Any]]:
    """Filter tasks based on CI configuration.

    Args:
        tasks: List of task definitions
        config: CI configuration

    Returns:
        Filtered tasks matching configuration
    """
    from fnmatch import fnmatch
    from .metrics import get_task_config

    filtered = []

    for task in tasks:
        task_id = task.get("task_id", "")
        task_config = get_task_config(task_id)

        # Check priority
        if task_config.priority not in config.priorities:
            continue

        # Check metric type
        if config.metric_types and task_config.metric_type not in config.metric_types:
            continue

        # Check include patterns
        if config.task_id_patterns:
            if not any(fnmatch(task_id, p) for p in config.task_id_patterns):
                continue

        # Check exclude patterns
        if config.exclude_patterns:
            if any(fnmatch(task_id, p) for p in config.exclude_patterns):
                continue

        filtered.append(task)

    return filtered


# ============================================================================
# Result Validation
# ============================================================================

def validate_eval_result(
    result: "EvalResult",  # noqa: F821
    config: CIEvalConfig,
) -> dict[str, Any]:
    """Validate evaluation result against CI thresholds.

    Args:
        result: Evaluation result
        config: CI configuration

    Returns:
        Validation result with pass/fail and details
    """
    from .metrics import EvalMetrics

    metrics = EvalMetrics.from_task_results(result.task_results)
    p0_status = result.p0_safety_status()

    issues = []

    # Check P0 safety
    if config.fail_on_p0_failure and not p0_status["all_passing"]:
        issues.append({
            "type": "p0_failure",
            "message": f"P0 safety tasks failing: {p0_status['failing_tasks']}",
            "severity": "critical",
        })

    # Check pass rate
    if metrics.pass_at_1 < config.min_pass_rate:
        issues.append({
            "type": "pass_rate",
            "message": f"Pass rate {metrics.pass_at_1:.1%} below threshold {config.min_pass_rate:.1%}",
            "severity": "error",
        })

    # Check consistency
    if metrics.pass_pow_3 < config.min_consistency:
        issues.append({
            "type": "consistency",
            "message": f"Consistency {metrics.pass_pow_3:.1%} below threshold {config.min_consistency:.1%}",
            "severity": "warning",
        })

    passed = len([i for i in issues if i["severity"] in ["critical", "error"]]) == 0

    return {
        "passed": passed,
        "config": config.name,
        "metrics": metrics.summary(),
        "p0_status": p0_status,
        "issues": issues,
        "recommendation": (
            "Ready for merge" if passed else
            "Fix critical issues before merge"
        ),
    }
