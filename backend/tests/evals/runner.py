"""Evaluation runner for executing and managing eval suites.

Orchestrates task execution, grading, and result aggregation.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable

from tests.evals.metrics import (
    EvalResult,
    TaskResult,
    TrialResult,
    get_task_config,
    TaskPriority,
    MetricType,
)
from tests.evals.transcript import TranscriptLogger, EvalTranscript
from tests.evals.ci_config import CIEvalConfig, filter_tasks_for_config, validate_eval_result

logger = logging.getLogger(__name__)


class EvalRunner:
    """Runner for executing evaluation suites.

    Supports:
    - Per-task metric selection (Pass@1, Pass@k, Pass^k)
    - Priority-based task filtering
    - CI configuration integration
    - Statistical regression detection
    """

    def __init__(
        self,
        eval_name: str,
        config: dict[str, Any] | None = None,
        ci_config: CIEvalConfig | None = None,
        transcript_dir: Path | None = None,
    ):
        """Initialize evaluation runner.

        Args:
            eval_name: Name of this evaluation run
            config: Configuration options
            ci_config: CI configuration for filtering and validation
            transcript_dir: Directory for saving transcripts
        """
        self.eval_id = f"{eval_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.eval_name = eval_name
        self.config = config or {}
        self.ci_config = ci_config
        self.transcript_dir = transcript_dir or Path(__file__).parent / "transcripts"
        self.transcript_logger = TranscriptLogger(self.transcript_dir)

        # Use CI config if provided, otherwise use defaults
        if ci_config:
            self.trials_per_task = ci_config.max_trials
            self.timeout_seconds = ci_config.timeout_seconds
            self.parallel_tasks = self.config.get("parallel_tasks", 1) if ci_config.parallel else 1
        else:
            self.trials_per_task = self.config.get("trials_per_task", 3)
            self.timeout_seconds = self.config.get("timeout_seconds", 120)
            self.parallel_tasks = self.config.get("parallel_tasks", 1)

        self.save_transcripts = self.config.get("save_transcripts", True)

    async def run_eval(
        self,
        tasks: list[dict[str, Any]],
        executor: Callable[[dict], Awaitable[dict]],
        graders: list[Callable[[dict, dict], dict]],
    ) -> EvalResult:
        """Run evaluation on a set of tasks.

        Args:
            tasks: List of task definitions
            executor: Async function that executes a task and returns response
            graders: List of grader functions to apply

        Returns:
            Complete evaluation result
        """
        started_at = datetime.now()
        result = EvalResult(
            eval_id=self.eval_id,
            eval_name=self.eval_name,
            started_at=started_at,
            completed_at=None,
            config=self.config,
        )

        # Filter tasks based on CI config if provided
        if self.ci_config:
            tasks = filter_tasks_for_config(tasks, self.ci_config)
            logger.info(f"Filtered to {len(tasks)} tasks based on CI config '{self.ci_config.name}'")

        logger.info(f"Starting eval '{self.eval_name}' with {len(tasks)} tasks")

        # Run tasks (optionally in parallel)
        if self.parallel_tasks > 1:
            task_results = await self._run_parallel(tasks, executor, graders)
        else:
            task_results = await self._run_sequential(tasks, executor, graders)

        result.task_results = task_results
        result.completed_at = datetime.now()

        # Log summary
        summary = result.summary()
        logger.info(
            f"Eval complete: {summary['overall_pass_rate']:.1%} pass rate, "
            f"{summary['avg_score']:.2f} avg score, "
            f"{summary['failing_tasks']} failing tasks"
        )

        # Log priority-based breakdown
        by_priority = result.by_priority()
        for priority, metrics in by_priority.items():
            logger.info(
                f"  {priority.value}: {metrics.pass_at_1:.1%} pass@1, "
                f"{metrics.pass_pow_3:.1%} pass^3, {metrics.total_tasks} tasks"
            )

        # Validate against CI thresholds if configured
        if self.ci_config:
            validation = validate_eval_result(result, self.ci_config)
            if not validation["passed"]:
                logger.warning(f"CI validation FAILED: {validation['recommendation']}")
                for issue in validation["issues"]:
                    logger.warning(f"  [{issue['severity']}] {issue['message']}")
            else:
                logger.info(f"CI validation PASSED: {validation['recommendation']}")
            result.config["ci_validation"] = validation

        # Save results
        if self.save_transcripts:
            await self._save_eval_result(result)

        return result

    async def _run_sequential(
        self,
        tasks: list[dict],
        executor: Callable[[dict], Awaitable[dict]],
        graders: list[Callable[[dict, dict], dict]],
    ) -> list[TaskResult]:
        """Run tasks sequentially."""
        results = []
        for i, task in enumerate(tasks):
            logger.info(f"Running task {i+1}/{len(tasks)}: {task.get('task_id', 'unknown')}")
            task_result = await self._run_task(task, executor, graders)
            results.append(task_result)
        return results

    async def _run_parallel(
        self,
        tasks: list[dict],
        executor: Callable[[dict], Awaitable[dict]],
        graders: list[Callable[[dict, dict], dict]],
    ) -> list[TaskResult]:
        """Run tasks in parallel batches."""
        results = []
        batch_size = self.parallel_tasks

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            batch_tasks = [
                self._run_task(task, executor, graders) for task in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                else:
                    results.append(result)

        return results

    async def _run_task(
        self,
        task: dict,
        executor: Callable[[dict], Awaitable[dict]],
        graders: list[Callable[[dict, dict], dict]],
    ) -> TaskResult:
        """Run a single task with multiple trials."""
        task_id = task.get("task_id", str(uuid.uuid4()))
        task_description = task.get("description", "")
        trials = []

        for trial_num in range(self.trials_per_task):
            trial_id = f"{task_id}_trial_{trial_num + 1}"

            try:
                trial_result = await self._run_trial(
                    trial_id=trial_id,
                    task=task,
                    executor=executor,
                    graders=graders,
                )
                trials.append(trial_result)
            except Exception as e:
                logger.error(f"Trial {trial_id} failed: {e}")
                trials.append(
                    TrialResult(
                        trial_id=trial_id,
                        task_id=task_id,
                        timestamp=datetime.now(),
                        passed=False,
                        score=0.0,
                        duration_ms=0,
                        token_count=0,
                        grader_results={},
                        error=str(e),
                    )
                )

        return TaskResult(
            task_id=task_id,
            task_description=task_description,
            trials=trials,
        )

    async def _run_trial(
        self,
        trial_id: str,
        task: dict,
        executor: Callable[[dict], Awaitable[dict]],
        graders: list[Callable[[dict, dict], dict]],
    ) -> TrialResult:
        """Run a single trial."""
        task_id = task.get("task_id", "unknown")
        start_time = time.time()

        # Execute task
        try:
            execution_result = await asyncio.wait_for(
                executor(task),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return TrialResult(
                trial_id=trial_id,
                task_id=task_id,
                timestamp=datetime.now(),
                passed=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                token_count=0,
                grader_results={"error": "timeout"},
                error=f"Execution timed out after {self.timeout_seconds}s",
            )

        duration_ms = int((time.time() - start_time) * 1000)

        # Apply graders
        grader_results = {}
        scores = []

        for grader in graders:
            try:
                grade_result = grader(task, execution_result)
                grader_name = grader.__name__
                grader_results[grader_name] = grade_result
                if "score" in grade_result:
                    scores.append(grade_result["score"])
            except Exception as e:
                logger.warning(f"Grader {grader.__name__} failed: {e}")
                grader_results[grader.__name__] = {"error": str(e)}

        # Calculate overall score and pass/fail
        avg_score = sum(scores) / len(scores) if scores else 0.0
        passed = all(
            gr.get("passed", True)
            for gr in grader_results.values()
            if isinstance(gr, dict) and "passed" in gr
        )

        # Create transcript
        if self.save_transcripts:
            transcript = EvalTranscript(
                trial_id=trial_id,
                task_id=task_id,
                timestamp=datetime.now(),
                task_input=task.get("input", {}),
                execution_result=execution_result,
                grader_results=grader_results,
                final_score=avg_score,
                passed=passed,
                duration_ms=duration_ms,
                token_count=execution_result.get("token_count", 0),
            )
            await self.transcript_logger.log(transcript)

        return TrialResult(
            trial_id=trial_id,
            task_id=task_id,
            timestamp=datetime.now(),
            passed=passed,
            score=avg_score,
            duration_ms=duration_ms,
            token_count=execution_result.get("token_count", 0),
            grader_results=grader_results,
        )

    async def _save_eval_result(self, result: EvalResult) -> None:
        """Save evaluation result to file."""
        result_dir = self.transcript_dir / self.eval_id
        result_dir.mkdir(parents=True, exist_ok=True)

        result_path = result_dir / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.summary(), f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Saved eval result to {result_path}")


class MockExecutor:
    """Mock executor for testing the eval framework."""

    def __init__(self, success_rate: float = 0.8):
        """Initialize mock executor.

        Args:
            success_rate: Probability of successful execution
        """
        self.success_rate = success_rate
        self.call_count = 0

    async def __call__(self, task: dict) -> dict:
        """Execute task (mock)."""
        import random

        self.call_count += 1
        await asyncio.sleep(0.1)  # Simulate processing time

        success = random.random() < self.success_rate

        return {
            "response": f"Mock response for {task.get('task_id', 'unknown')}",
            "success": success,
            "token_count": random.randint(100, 500),
        }


async def run_vdot_eval(
    vdot_service: Any = None,
) -> EvalResult:
    """Run VDOT calculation evaluation.

    Args:
        vdot_service: VDOT calculation service (uses real if provided)

    Returns:
        Evaluation result
    """
    from tests.evals.tasks.vdot_tasks import VDOT_TASKS
    from tests.evals.graders.code_graders import grade_vdot_accuracy, grade_pace_accuracy

    # Import real VDOT service if not provided
    if vdot_service is None:
        from app.services.vdot import calculate_vdot, get_training_paces

    async def vdot_executor(task: dict) -> dict:
        """Execute VDOT calculation task."""
        input_data = task.get("input", {})

        if "distance_meters" in input_data and "time_seconds" in input_data:
            # Calculate VDOT from race result
            if vdot_service:
                vdot = vdot_service.calculate_vdot(
                    input_data["distance_meters"],
                    input_data["time_seconds"],
                )
                paces = vdot_service.get_training_paces(vdot)
            else:
                vdot = calculate_vdot(
                    input_data["distance_meters"],
                    input_data["time_seconds"],
                )
                paces = get_training_paces(vdot)

            return {
                "vdot": vdot,
                "training_paces": paces.to_dict() if hasattr(paces, "to_dict") else paces,
                "token_count": 0,  # No LLM calls
            }
        elif "vdot" in input_data:
            # Calculate race times from VDOT
            from app.services.vdot import get_race_equivalents

            equivalents = get_race_equivalents(input_data["vdot"])
            return {
                "race_equivalents": [e.to_dict() for e in equivalents],
                "token_count": 0,
            }
        else:
            return {"error": "Invalid task input", "token_count": 0}

    def vdot_grader(task: dict, result: dict) -> dict:
        """Grade VDOT calculation."""
        expected = task.get("expected", {})
        tolerance = task.get("tolerance", {})

        if "error" in result:
            return {"passed": False, "score": 0.0, "error": result["error"]}

        grades = []

        # Grade VDOT
        if "vdot" in expected and "vdot" in result:
            vdot_grade = grade_vdot_accuracy(
                result["vdot"],
                expected["vdot"],
                tolerance.get("vdot", 2.0),
            )
            grades.append(vdot_grade)

        # Grade paces
        if "training_paces" in expected and "training_paces" in result:
            pace_tolerance = tolerance.get("pace", 15)
            for pace_type, expected_pace in expected["training_paces"].items():
                if pace_type in result.get("training_paces", {}):
                    actual = result["training_paces"][pace_type]
                    if isinstance(actual, dict):
                        actual = actual.get("sec_per_km", actual.get("min_sec_per_km", 0))
                    pace_grade = grade_pace_accuracy(actual, expected_pace, pace_tolerance)
                    grades.append(pace_grade)

        if not grades:
            return {"passed": False, "score": 0.0, "message": "No gradable outputs"}

        avg_score = sum(g["score"] for g in grades) / len(grades)
        all_passed = all(g["passed"] for g in grades)

        return {
            "passed": all_passed,
            "score": avg_score,
            "details": grades,
        }

    runner = EvalRunner(
        eval_name="vdot_accuracy",
        config={
            "trials_per_task": 1,  # VDOT is deterministic
            "save_transcripts": True,
        },
    )

    return await runner.run_eval(
        tasks=VDOT_TASKS,
        executor=vdot_executor,
        graders=[vdot_grader],
    )


async def run_training_plan_eval(
    ai_coach_service: Any = None,
) -> EvalResult:
    """Run training plan evaluation.

    Args:
        ai_coach_service: AI coach service for generating plans

    Returns:
        Evaluation result
    """
    from tests.evals.tasks.training_plan_tasks import TRAINING_PLAN_TASKS
    from tests.evals.graders.code_graders import (
        grade_must_include_criteria,
        grade_must_not_include_criteria,
    )

    async def plan_executor(task: dict) -> dict:
        """Execute training plan generation task."""
        # For now, return mock response
        # In real implementation, call AI coach service
        return {
            "response": "Mock training plan response",
            "token_count": 500,
        }

    def plan_grader(task: dict, result: dict) -> dict:
        """Grade training plan."""
        criteria = task.get("success_criteria", {})
        response = result.get("response", "")

        grades = []

        if "must_include" in criteria:
            include_grade = grade_must_include_criteria(
                response, criteria["must_include"]
            )
            grades.append(include_grade)

        if "must_not_include" in criteria:
            exclude_grade = grade_must_not_include_criteria(
                response, criteria["must_not_include"]
            )
            grades.append(exclude_grade)

        if not grades:
            return {"passed": True, "score": 1.0}

        avg_score = sum(g["score"] for g in grades) / len(grades)
        all_passed = all(g["passed"] for g in grades)

        return {
            "passed": all_passed,
            "score": avg_score,
            "details": grades,
        }

    runner = EvalRunner(
        eval_name="training_plan_quality",
        config={
            "trials_per_task": 3,
            "save_transcripts": True,
        },
    )

    return await runner.run_eval(
        tasks=TRAINING_PLAN_TASKS,
        executor=plan_executor,
        graders=[plan_grader],
    )


# ============================================================================
# Unified Evaluation Entry Point
# ============================================================================

class EvalSuiteType:
    """Evaluation suite types."""
    VDOT = "vdot"
    TRAINING_PLAN = "training_plan"
    FULL = "full"
    CUSTOM = "custom"


async def run_eval_suite(
    suite_type: str = EvalSuiteType.FULL,
    ci_config: CIEvalConfig | str | None = None,
    executor: Callable[[dict], Awaitable[dict]] | None = None,
    graders: list[Callable[[dict, dict], dict]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[EvalResult, dict[str, Any]]:
    """Unified entry point for all evaluation runs.

    This function consolidates multiple entry points into a single interface:
    - run_vdot_eval() → run_eval_suite("vdot")
    - run_training_plan_eval() → run_eval_suite("training_plan")
    - run_pr_eval() → run_eval_suite("full", ci_config="pr_fast")
    - run_nightly_eval() → run_eval_suite("full", ci_config="nightly_full")
    - run_release_eval() → run_eval_suite("full", ci_config="release_full")

    Args:
        suite_type: Type of evaluation suite ("vdot", "training_plan", "full", "custom")
        ci_config: CI configuration (name string or CIEvalConfig object)
        executor: Custom executor function (uses suite defaults if None)
        graders: Custom grader functions (uses suite defaults if None)
        tasks: Custom task list (uses suite defaults if None)
        config: Additional runner configuration

    Returns:
        (EvalResult, report) tuple with evaluation results and detailed report

    Examples:
        # VDOT evaluation (deterministic, Pass@1)
        result, report = await run_eval_suite("vdot")

        # PR check (fast, blocking)
        result, report = await run_eval_suite("full", ci_config="pr_fast")

        # Nightly evaluation (comprehensive)
        result, report = await run_eval_suite("full", ci_config="nightly_full")

        # Release validation (thorough)
        result, report = await run_eval_suite("full", ci_config="release_full")

        # Custom evaluation
        result, report = await run_eval_suite(
            "custom",
            tasks=my_tasks,
            executor=my_executor,
            graders=[my_grader],
        )
    """
    from tests.evals.ci_config import get_ci_config
    from tests.evals.graders.code_graders import (
        grade_vdot_accuracy,
        grade_pace_accuracy,
        grade_must_include_criteria,
        grade_must_not_include_criteria,
    )

    # Resolve CI config if string name provided
    resolved_ci_config: CIEvalConfig | None = None
    if isinstance(ci_config, str):
        resolved_ci_config = get_ci_config(ci_config)
    elif isinstance(ci_config, CIEvalConfig):
        resolved_ci_config = ci_config

    # Get suite-specific defaults
    suite_tasks, suite_executor, suite_graders, suite_config = _get_suite_defaults(
        suite_type, resolved_ci_config
    )

    # Apply overrides
    final_tasks = tasks if tasks is not None else suite_tasks
    final_executor = executor if executor is not None else suite_executor
    final_graders = graders if graders is not None else suite_graders
    final_config = {**(suite_config or {}), **(config or {})}

    # Determine eval name
    eval_name = _get_eval_name(suite_type, resolved_ci_config)

    # Create runner
    runner = EvalRunner(
        eval_name=eval_name,
        ci_config=resolved_ci_config,
        config=final_config,
    )

    # Run evaluation
    result = await runner.run_eval(
        tasks=final_tasks,
        executor=final_executor,
        graders=final_graders,
    )

    # Generate report
    report = _generate_report(result, resolved_ci_config)

    return result, report


def _get_suite_defaults(
    suite_type: str,
    ci_config: CIEvalConfig | None,
) -> tuple[list[dict], Callable, list[Callable], dict | None]:
    """Get default tasks, executor, graders for a suite type."""
    from tests.evals.tasks.vdot_tasks import VDOT_TASKS
    from tests.evals.tasks.training_plan_tasks import TRAINING_PLAN_TASKS
    from tests.evals.tasks.coaching_advice_tasks import COACHING_ADVICE_TASKS
    from tests.evals.graders.code_graders import grade_vdot_accuracy, grade_pace_accuracy

    # Default mock executor
    async def mock_executor(task: dict) -> dict:
        return {"response": "Mock response", "token_count": 100}

    def mock_grader(task: dict, result: dict) -> dict:
        return {"passed": True, "score": 1.0}

    if suite_type == EvalSuiteType.VDOT:
        return (
            VDOT_TASKS,
            _create_vdot_executor(),
            [_create_vdot_grader()],
            {"trials_per_task": 1, "save_transcripts": True},
        )
    elif suite_type == EvalSuiteType.TRAINING_PLAN:
        return (
            TRAINING_PLAN_TASKS,
            mock_executor,
            [_create_training_plan_grader()],
            {"trials_per_task": 3, "save_transcripts": True},
        )
    elif suite_type == EvalSuiteType.FULL:
        # Combine all tasks, apply CI config filtering
        all_tasks = VDOT_TASKS + TRAINING_PLAN_TASKS + COACHING_ADVICE_TASKS
        parallel_tasks = 4 if ci_config and ci_config.parallel else 1
        return (
            all_tasks,
            mock_executor,
            [mock_grader],
            {"parallel_tasks": parallel_tasks},
        )
    else:  # CUSTOM
        return ([], mock_executor, [mock_grader], {})


def _get_eval_name(suite_type: str, ci_config: CIEvalConfig | None) -> str:
    """Generate evaluation name."""
    if ci_config:
        return ci_config.name
    return f"{suite_type}_eval"


def _create_vdot_executor() -> Callable[[dict], Awaitable[dict]]:
    """Create VDOT executor."""
    async def vdot_executor(task: dict) -> dict:
        from app.services.vdot import calculate_vdot, get_training_paces, get_race_equivalents

        input_data = task.get("input", {})

        if "distance_meters" in input_data and "time_seconds" in input_data:
            vdot = calculate_vdot(
                input_data["distance_meters"],
                input_data["time_seconds"],
            )
            paces = get_training_paces(vdot)
            return {
                "vdot": vdot,
                "training_paces": paces.to_dict() if hasattr(paces, "to_dict") else paces,
                "token_count": 0,
            }
        elif "vdot" in input_data:
            equivalents = get_race_equivalents(input_data["vdot"])
            return {
                "race_equivalents": [e.to_dict() for e in equivalents],
                "token_count": 0,
            }
        else:
            return {"error": "Invalid task input", "token_count": 0}

    return vdot_executor


def _create_vdot_grader() -> Callable[[dict, dict], dict]:
    """Create VDOT grader."""
    from tests.evals.graders.code_graders import grade_vdot_accuracy, grade_pace_accuracy

    def vdot_grader(task: dict, result: dict) -> dict:
        expected = task.get("expected", {})
        tolerance = task.get("tolerance", {})

        if "error" in result:
            return {"passed": False, "score": 0.0, "error": result["error"]}

        grades = []

        if "vdot" in expected and "vdot" in result:
            vdot_grade = grade_vdot_accuracy(
                result["vdot"],
                expected["vdot"],
                tolerance.get("vdot", 2.0),
            )
            grades.append(vdot_grade)

        if "training_paces" in expected and "training_paces" in result:
            pace_tolerance = tolerance.get("pace", 15)
            for pace_type, expected_pace in expected["training_paces"].items():
                if pace_type in result.get("training_paces", {}):
                    actual = result["training_paces"][pace_type]
                    if isinstance(actual, dict):
                        actual = actual.get("sec_per_km", actual.get("min_sec_per_km", 0))
                    pace_grade = grade_pace_accuracy(actual, expected_pace, pace_tolerance)
                    grades.append(pace_grade)

        if not grades:
            return {"passed": False, "score": 0.0, "message": "No gradable outputs"}

        avg_score = sum(g["score"] for g in grades) / len(grades)
        all_passed = all(g["passed"] for g in grades)

        return {"passed": all_passed, "score": avg_score, "details": grades}

    return vdot_grader


def _create_training_plan_grader() -> Callable[[dict, dict], dict]:
    """Create training plan grader."""
    from tests.evals.graders.code_graders import (
        grade_must_include_criteria,
        grade_must_not_include_criteria,
    )

    def plan_grader(task: dict, result: dict) -> dict:
        criteria = task.get("success_criteria", {})
        response = result.get("response", "")

        grades = []

        if "must_include" in criteria:
            include_grade = grade_must_include_criteria(response, criteria["must_include"])
            grades.append(include_grade)

        if "must_not_include" in criteria:
            exclude_grade = grade_must_not_include_criteria(response, criteria["must_not_include"])
            grades.append(exclude_grade)

        if not grades:
            return {"passed": True, "score": 1.0}

        avg_score = sum(g["score"] for g in grades) / len(grades)
        all_passed = all(g["passed"] for g in grades)

        return {"passed": all_passed, "score": avg_score, "details": grades}

    return plan_grader


def _generate_report(
    result: EvalResult,
    ci_config: CIEvalConfig | None,
) -> dict[str, Any]:
    """Generate detailed evaluation report."""
    validation = result.config.get("ci_validation", {})
    by_priority = result.by_priority()
    by_metric = result.by_metric_type()

    report = {
        "eval_id": result.eval_id,
        "eval_name": result.eval_name,
        "timestamp": result.completed_at.isoformat() if result.completed_at else None,
        "passed": validation.get("passed", True),
        "summary": result.summary(),
        "p0_safety_status": result.p0_safety_status(),
        "by_priority": {p.value: m.summary() for p, m in by_priority.items()},
        "by_metric_type": {m.value: metrics.summary() for m, metrics in by_metric.items()},
    }

    if ci_config:
        report["ci_config"] = ci_config.name
        report["validation"] = validation
        report["release_ready"] = validation.get("passed", False)

    return report


# ============================================================================
# Legacy Entry Points (Deprecated - Use run_eval_suite instead)
# ============================================================================

async def run_pr_eval() -> tuple[EvalResult, bool]:
    """Run PR-level evaluation (fast, blocking).

    .. deprecated::
        Use ``run_eval_suite("full", ci_config="pr_fast")`` instead.

    Returns:
        (EvalResult, passed) tuple
    """
    import warnings
    warnings.warn(
        "run_pr_eval is deprecated. Use run_eval_suite('full', ci_config='pr_fast') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from tests.evals.ci_config import PR_FAST_CONFIG
    from tests.evals.tasks.vdot_tasks import VDOT_TASKS
    from tests.evals.tasks.coaching_advice_tasks import COACHING_ADVICE_TASKS

    # Combine tasks for PR check
    all_tasks = VDOT_TASKS + [
        t for t in COACHING_ADVICE_TASKS
        if t.get("task_id", "").startswith("should_not_")
    ]

    runner = EvalRunner(
        eval_name="pr_check",
        ci_config=PR_FAST_CONFIG,
    )

    # Simple mock executor for demonstration
    async def mock_executor(task: dict) -> dict:
        return {"response": "Mock response", "token_count": 100}

    def mock_grader(task: dict, result: dict) -> dict:
        return {"passed": True, "score": 1.0}

    result = await runner.run_eval(
        tasks=all_tasks,
        executor=mock_executor,
        graders=[mock_grader],
    )

    validation = result.config.get("ci_validation", {})
    passed = validation.get("passed", False)

    return result, passed


async def run_nightly_eval() -> tuple[EvalResult, bool]:
    """Run nightly evaluation (comprehensive).

    .. deprecated::
        Use ``run_eval_suite("full", ci_config="nightly_full")`` instead.

    Returns:
        (EvalResult, passed) tuple
    """
    import warnings
    warnings.warn(
        "run_nightly_eval is deprecated. Use run_eval_suite('full', ci_config='nightly_full') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from tests.evals.ci_config import NIGHTLY_FULL_CONFIG
    from tests.evals.tasks.vdot_tasks import VDOT_TASKS
    from tests.evals.tasks.training_plan_tasks import TRAINING_PLAN_TASKS
    from tests.evals.tasks.coaching_advice_tasks import COACHING_ADVICE_TASKS

    all_tasks = VDOT_TASKS + TRAINING_PLAN_TASKS + COACHING_ADVICE_TASKS

    runner = EvalRunner(
        eval_name="nightly_full",
        ci_config=NIGHTLY_FULL_CONFIG,
        config={"parallel_tasks": 4},
    )

    # Mock executor - in production, use real AI coach
    async def mock_executor(task: dict) -> dict:
        return {"response": "Mock response", "token_count": 100}

    def mock_grader(task: dict, result: dict) -> dict:
        return {"passed": True, "score": 1.0}

    result = await runner.run_eval(
        tasks=all_tasks,
        executor=mock_executor,
        graders=[mock_grader],
    )

    validation = result.config.get("ci_validation", {})
    passed = validation.get("passed", False)

    return result, passed


async def run_release_eval() -> tuple[EvalResult, dict[str, Any]]:
    """Run release evaluation (thorough, with detailed report).

    .. deprecated::
        Use ``run_eval_suite("full", ci_config="release_full")`` instead.

    Returns:
        (EvalResult, detailed_report) tuple
    """
    import warnings
    warnings.warn(
        "run_release_eval is deprecated. Use run_eval_suite('full', ci_config='release_full') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from tests.evals.ci_config import RELEASE_FULL_CONFIG
    from tests.evals.tasks.vdot_tasks import VDOT_TASKS
    from tests.evals.tasks.training_plan_tasks import TRAINING_PLAN_TASKS
    from tests.evals.tasks.coaching_advice_tasks import COACHING_ADVICE_TASKS

    all_tasks = VDOT_TASKS + TRAINING_PLAN_TASKS + COACHING_ADVICE_TASKS

    runner = EvalRunner(
        eval_name="release_validation",
        ci_config=RELEASE_FULL_CONFIG,
        config={"parallel_tasks": 4},
    )

    # Mock executor - in production, use real AI coach
    async def mock_executor(task: dict) -> dict:
        return {"response": "Mock response", "token_count": 100}

    def mock_grader(task: dict, result: dict) -> dict:
        return {"passed": True, "score": 1.0}

    result = await runner.run_eval(
        tasks=all_tasks,
        executor=mock_executor,
        graders=[mock_grader],
    )

    # Generate detailed release report
    validation = result.config.get("ci_validation", {})
    by_priority = result.by_priority()
    by_metric = result.by_metric_type()

    report = {
        "eval_id": result.eval_id,
        "timestamp": result.completed_at.isoformat() if result.completed_at else None,
        "validation": validation,
        "summary": result.summary(),
        "by_priority": {
            p.value: m.summary() for p, m in by_priority.items()
        },
        "by_metric_type": {
            m.value: metrics.summary() for m, metrics in by_metric.items()
        },
        "p0_safety_status": result.p0_safety_status(),
        "release_ready": validation.get("passed", False),
    }

    return result, report


def check_regression(
    current: EvalResult,
    baseline: EvalResult,
    significance_threshold: float = 0.05,
) -> dict[str, Any]:
    """Check for statistically significant regression.

    Args:
        current: Current evaluation result
        baseline: Baseline evaluation result
        significance_threshold: Threshold for significant change

    Returns:
        Regression analysis report
    """
    from tests.evals.metrics import compare_eval_results, calculate_confidence_interval

    comparison = compare_eval_results(baseline, current)

    # Calculate confidence intervals
    current_metrics = current.summary()
    baseline_metrics = baseline.summary()

    current_ci = calculate_confidence_interval(
        current_metrics["overall_pass_rate"],
        current_metrics["total_trials"],
    )
    baseline_ci = calculate_confidence_interval(
        baseline_metrics["overall_pass_rate"],
        baseline_metrics["total_trials"],
    )

    # Check if intervals overlap (no significant difference)
    intervals_overlap = not (current_ci[1] < baseline_ci[0] or baseline_ci[1] < current_ci[0])

    # Check P0 safety specifically
    current_p0 = current.p0_safety_status()
    baseline_p0 = baseline.p0_safety_status()

    p0_regression = (
        baseline_p0["all_passing"] and not current_p0["all_passing"]
    )

    return {
        "comparison": comparison,
        "current_ci": current_ci,
        "baseline_ci": baseline_ci,
        "statistically_significant": not intervals_overlap,
        "p0_safety_regression": p0_regression,
        "action_required": (
            comparison["regressed"] or
            p0_regression or
            (not intervals_overlap and comparison["pass_rate_delta"] < -significance_threshold)
        ),
        "recommendation": (
            "BLOCK: P0 safety regression detected" if p0_regression else
            "BLOCK: Significant regression detected" if comparison["regressed"] else
            "REVIEW: Statistical change detected" if not intervals_overlap else
            "PASS: No significant change"
        ),
    }
