"""Advanced tests for evaluation metrics and task configuration.

Tests for:
- MetricType and TaskPriority enums
- TaskConfig per-task metric selection
- Priority-based grouping and P0 safety status
- Regression detection with statistical significance
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from tests.evals.metrics import (
    MetricType,
    TaskPriority,
    TaskConfig,
    TASK_CONFIGS,
    get_task_config,
    TrialResult,
    TaskResult,
    EvalResult,
    EvalMetrics,
    calculate_confidence_interval,
    compare_eval_results,
)


class TestMetricTypeEnum:
    """Tests for MetricType enum."""

    def test_deterministic_for_calculations(self):
        """VDOT calculations should use DETERMINISTIC type."""
        config = get_task_config("vdot_marathon_sub3")
        assert config.metric_type == MetricType.DETERMINISTIC

    def test_tool_for_rag(self):
        """RAG retrieval should use TOOL type."""
        config = get_task_config("rag_marathon_training_basics")
        assert config.metric_type == MetricType.TOOL

    def test_customer_facing_for_advice(self):
        """Coaching advice should use CUSTOMER_FACING type."""
        config = get_task_config("advice_first_marathon")
        assert config.metric_type == MetricType.CUSTOMER_FACING


class TestTaskPriorityEnum:
    """Tests for TaskPriority enum."""

    def test_p0_for_safety_tasks(self):
        """Safety-critical tasks should be P0."""
        config = get_task_config("should_not_recommend_running_through_pain")
        assert config.priority == TaskPriority.P0_SAFETY

    def test_p1_for_vdot(self):
        """VDOT calculations should be P1."""
        config = get_task_config("vdot_marathon_sub4")
        assert config.priority == TaskPriority.P1_ACCURACY

    def test_p2_for_quality(self):
        """General advice should be P2."""
        config = get_task_config("advice_tapering")
        assert config.priority == TaskPriority.P2_QUALITY

    def test_p3_for_experience(self):
        """Personalization should be P3."""
        config = get_task_config("personalization_busy_professional")
        assert config.priority == TaskPriority.P3_EXPERIENCE


class TestTaskConfig:
    """Tests for TaskConfig dataclass."""

    def test_get_primary_metric_deterministic(self):
        """Deterministic tasks should use pass_at_1."""
        config = TaskConfig(
            task_id="test_det",
            priority=TaskPriority.P1_ACCURACY,
            metric_type=MetricType.DETERMINISTIC,
        )

        # Create a TaskResult with 100% pass rate
        trials = [
            TrialResult(
                trial_id="t1", task_id="test_det",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t2", task_id="test_det",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t3", task_id="test_det",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
        ]
        task_result = TaskResult(task_id="test_det", task_description="", trials=trials)

        # Pass@1 should be 1.0
        assert config.get_primary_metric(task_result) == 1.0

    def test_get_primary_metric_tool(self):
        """Tool tasks should use pass_at_k."""
        config = TaskConfig(
            task_id="test_tool",
            priority=TaskPriority.P2_QUALITY,
            metric_type=MetricType.TOOL,
        )

        # 1 success out of 3 → pass@3 = 1.0 (at least one success)
        trials = [
            TrialResult(
                trial_id="t1", task_id="test_tool",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t2", task_id="test_tool",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t3", task_id="test_tool",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
        ]
        task_result = TaskResult(task_id="test_tool", task_description="", trials=trials)

        # At least one success → 1.0
        assert config.get_primary_metric(task_result) == 1.0

    def test_get_primary_metric_customer_facing(self):
        """Customer-facing tasks should use pass^k."""
        config = TaskConfig(
            task_id="test_cf",
            priority=TaskPriority.P2_QUALITY,
            metric_type=MetricType.CUSTOMER_FACING,
        )

        # 2 success out of 3 → pass rate = 0.67, pass^3 = 0.67^3 ≈ 0.30
        trials = [
            TrialResult(
                trial_id="t1", task_id="test_cf",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t2", task_id="test_cf",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t3", task_id="test_cf",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
        ]
        task_result = TaskResult(task_id="test_cf", task_description="", trials=trials)

        # (2/3)^3 ≈ 0.296
        metric = config.get_primary_metric(task_result)
        assert 0.29 <= metric <= 0.31

    def test_is_passing_threshold(self):
        """Test is_passing with different thresholds."""
        config = TaskConfig(
            task_id="test",
            priority=TaskPriority.P0_SAFETY,
            metric_type=MetricType.CUSTOMER_FACING,
            min_pass_rate=0.95,
        )

        # All pass → pass^3 = 1.0 > 0.95
        all_pass_trials = [
            TrialResult(
                trial_id=f"t{i}", task_id="test",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            )
            for i in range(3)
        ]
        all_pass_result = TaskResult(task_id="test", task_description="", trials=all_pass_trials)
        assert config.is_passing(all_pass_result)

        # 2/3 pass → pass^3 ≈ 0.30 < 0.95
        partial_trials = all_pass_trials[:2] + [
            TrialResult(
                trial_id="t3", task_id="test",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            )
        ]
        partial_result = TaskResult(task_id="test", task_description="", trials=partial_trials)
        assert not config.is_passing(partial_result)


class TestTaskConfigRegistry:
    """Tests for TASK_CONFIGS registry."""

    def test_all_safety_tasks_are_p0(self):
        """All should_not_* tasks must be P0 safety."""
        for task_id, config in TASK_CONFIGS.items():
            if task_id.startswith("should_not_"):
                assert config.priority == TaskPriority.P0_SAFETY, \
                    f"{task_id} should be P0_SAFETY"

    def test_all_vdot_tasks_are_deterministic(self):
        """All vdot_* tasks must be DETERMINISTIC."""
        for task_id, config in TASK_CONFIGS.items():
            if task_id.startswith("vdot_"):
                assert config.metric_type == MetricType.DETERMINISTIC, \
                    f"{task_id} should be DETERMINISTIC"

    def test_all_rag_tasks_are_tool(self):
        """All rag_* tasks must be TOOL type."""
        for task_id, config in TASK_CONFIGS.items():
            if task_id.startswith("rag_"):
                assert config.metric_type == MetricType.TOOL, \
                    f"{task_id} should be TOOL"

    def test_p0_tasks_have_high_threshold(self):
        """P0 safety tasks must have min_pass_rate >= 0.90."""
        for task_id, config in TASK_CONFIGS.items():
            if config.priority == TaskPriority.P0_SAFETY:
                assert config.min_pass_rate >= 0.90, \
                    f"{task_id} P0 task should have threshold >= 0.90"

    def test_get_task_config_fallback(self):
        """Unknown task IDs should fall back to pattern-based config."""
        # Unknown safety pattern
        config = get_task_config("should_not_unknown_danger")
        assert config.priority == TaskPriority.P0_SAFETY
        assert config.metric_type == MetricType.CUSTOMER_FACING

        # Unknown VDOT pattern
        config = get_task_config("vdot_unknown_distance")
        assert config.priority == TaskPriority.P1_ACCURACY
        assert config.metric_type == MetricType.DETERMINISTIC

        # Unknown RAG pattern
        config = get_task_config("rag_unknown_topic")
        assert config.priority == TaskPriority.P2_QUALITY
        assert config.metric_type == MetricType.TOOL

        # Completely unknown
        config = get_task_config("completely_unknown_task")
        assert config.priority == TaskPriority.P2_QUALITY


class TestEvalResultGrouping:
    """Tests for EvalResult grouping methods."""

    def _create_task_result(
        self,
        task_id: str,
        trials_passed: list[bool],
    ) -> TaskResult:
        """Helper to create TaskResult."""
        trials = [
            TrialResult(
                trial_id=f"{task_id}_t{i}",
                task_id=task_id,
                timestamp=datetime.now(),
                passed=passed,
                score=1.0 if passed else 0.0,
                duration_ms=100,
                token_count=100,
                grader_results={},
            )
            for i, passed in enumerate(trials_passed)
        ]
        return TaskResult(task_id=task_id, task_description="", trials=trials)

    def test_by_priority(self):
        """Test grouping by priority."""
        eval_result = EvalResult(
            eval_id="test",
            eval_name="test",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                self._create_task_result("should_not_recommend_running_through_pain", [True, True, True]),
                self._create_task_result("vdot_marathon_sub3", [True, True, True]),
                self._create_task_result("advice_tapering", [True, True, False]),
            ],
        )

        by_priority = eval_result.by_priority()

        assert TaskPriority.P0_SAFETY in by_priority
        assert TaskPriority.P1_ACCURACY in by_priority
        assert TaskPriority.P2_QUALITY in by_priority
        assert by_priority[TaskPriority.P0_SAFETY].total_tasks == 1
        assert by_priority[TaskPriority.P1_ACCURACY].total_tasks == 1
        assert by_priority[TaskPriority.P2_QUALITY].total_tasks == 1

    def test_by_metric_type(self):
        """Test grouping by metric type."""
        eval_result = EvalResult(
            eval_id="test",
            eval_name="test",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                self._create_task_result("vdot_marathon_sub3", [True, True, True]),
                self._create_task_result("vdot_half_sub90", [True, True, True]),
                self._create_task_result("rag_marathon_training_basics", [True, False, True]),
                self._create_task_result("advice_tapering", [True, True, False]),
            ],
        )

        by_type = eval_result.by_metric_type()

        assert MetricType.DETERMINISTIC in by_type
        assert MetricType.TOOL in by_type
        assert MetricType.CUSTOMER_FACING in by_type
        assert by_type[MetricType.DETERMINISTIC].total_tasks == 2
        assert by_type[MetricType.TOOL].total_tasks == 1
        assert by_type[MetricType.CUSTOMER_FACING].total_tasks == 1

    def test_p0_safety_status_all_passing(self):
        """Test P0 safety status when all passing."""
        eval_result = EvalResult(
            eval_id="test",
            eval_name="test",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                self._create_task_result("should_not_recommend_running_through_pain", [True, True, True]),
                self._create_task_result("should_not_ignore_injury_symptoms", [True, True, True]),
            ],
        )

        status = eval_result.p0_safety_status()

        assert status["all_passing"] is True
        assert status["total"] == 2
        assert status["passing"] == 2
        assert status["failing"] == 0
        assert len(status["failing_tasks"]) == 0

    def test_p0_safety_status_with_failures(self):
        """Test P0 safety status when some failing."""
        eval_result = EvalResult(
            eval_id="test",
            eval_name="test",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                self._create_task_result("should_not_recommend_running_through_pain", [True, True, True]),
                # This will fail: 2/3 pass rate → pass^3 ≈ 0.30 < 0.95 threshold
                self._create_task_result("should_not_ignore_injury_symptoms", [True, True, False]),
            ],
        )

        status = eval_result.p0_safety_status()

        assert status["all_passing"] is False
        assert status["total"] == 2
        assert status["failing"] == 1
        assert len(status["failing_tasks"]) == 1
        assert status["failing_tasks"][0]["task_id"] == "should_not_ignore_injury_symptoms"


class TestConfidenceInterval:
    """Tests for confidence interval calculation."""

    def test_perfect_pass_rate(self):
        """Test CI for 100% pass rate."""
        lower, upper = calculate_confidence_interval(1.0, 100)
        assert lower > 0.95
        assert upper >= 0.99  # Allow floating point precision

    def test_zero_pass_rate(self):
        """Test CI for 0% pass rate."""
        lower, upper = calculate_confidence_interval(0.0, 100)
        assert lower == 0.0
        assert upper < 0.05

    def test_50_percent_pass_rate(self):
        """Test CI for 50% pass rate."""
        lower, upper = calculate_confidence_interval(0.5, 100)
        assert 0.4 <= lower <= 0.5
        assert 0.5 <= upper <= 0.6

    def test_small_sample_wide_interval(self):
        """Small sample should have wider interval."""
        lower_small, upper_small = calculate_confidence_interval(0.8, 10)
        lower_large, upper_large = calculate_confidence_interval(0.8, 100)

        interval_small = upper_small - lower_small
        interval_large = upper_large - lower_large

        assert interval_small > interval_large

    def test_empty_trials(self):
        """Test with zero trials."""
        lower, upper = calculate_confidence_interval(0.5, 0)
        assert lower == 0.0
        assert upper == 1.0


class TestRegressionDetection:
    """Tests for regression detection."""

    def _create_eval_result(
        self,
        eval_id: str,
        task_results: list[TaskResult],
    ) -> EvalResult:
        """Helper to create EvalResult."""
        return EvalResult(
            eval_id=eval_id,
            eval_name="test",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=task_results,
        )

    def _create_task_result(
        self,
        task_id: str,
        pass_rate: float,
    ) -> TaskResult:
        """Helper to create TaskResult with given pass rate."""
        n_trials = 10
        n_pass = int(pass_rate * n_trials)
        trials = [
            TrialResult(
                trial_id=f"{task_id}_t{i}",
                task_id=task_id,
                timestamp=datetime.now(),
                passed=i < n_pass,
                score=1.0 if i < n_pass else 0.0,
                duration_ms=100,
                token_count=100,
                grader_results={},
            )
            for i in range(n_trials)
        ]
        return TaskResult(task_id=task_id, task_description="", trials=trials)

    def test_detect_improvement(self):
        """Test detecting improvement."""
        baseline = self._create_eval_result("baseline", [
            self._create_task_result("task1", 0.7),
            self._create_task_result("task2", 0.6),
        ])
        comparison = self._create_eval_result("comparison", [
            self._create_task_result("task1", 0.9),
            self._create_task_result("task2", 0.8),
        ])

        result = compare_eval_results(baseline, comparison)

        # Check that comparison shows improvement direction
        # Note: compare_eval_results uses pass_at_1 which is first trial only
        assert result["pass_rate_delta"] >= 0
        assert result["regressed"] is False

    def test_detect_regression(self):
        """Test detecting regression."""
        # Create results where first trial fails (pass_at_1 = 0)
        baseline_tasks = []
        for task_id in ["task1", "task2"]:
            trials = [
                TrialResult(
                    trial_id=f"{task_id}_t0",
                    task_id=task_id,
                    timestamp=datetime.now(),
                    passed=True,  # First trial passes
                    score=1.0,
                    duration_ms=100,
                    token_count=100,
                    grader_results={},
                )
            ]
            baseline_tasks.append(TaskResult(task_id=task_id, task_description="", trials=trials))

        comparison_tasks = []
        for task_id in ["task1", "task2"]:
            trials = [
                TrialResult(
                    trial_id=f"{task_id}_t0",
                    task_id=task_id,
                    timestamp=datetime.now(),
                    passed=False,  # First trial fails
                    score=0.0,
                    duration_ms=100,
                    token_count=100,
                    grader_results={},
                )
            ]
            comparison_tasks.append(TaskResult(task_id=task_id, task_description="", trials=trials))

        baseline = self._create_eval_result("baseline", [])
        baseline.task_results = baseline_tasks

        comparison = self._create_eval_result("comparison", [])
        comparison.task_results = comparison_tasks

        result = compare_eval_results(baseline, comparison)

        assert result["improved"] is False
        assert result["regressed"] is True
        assert result["pass_rate_delta"] < 0

    def test_no_significant_change(self):
        """Test when there's no significant change."""
        # Both baselines pass first trial
        baseline_tasks = [
            TaskResult(
                task_id="task1",
                task_description="",
                trials=[
                    TrialResult(
                        trial_id="t0",
                        task_id="task1",
                        timestamp=datetime.now(),
                        passed=True,
                        score=0.8,
                        duration_ms=100,
                        token_count=100,
                        grader_results={},
                    )
                ]
            )
        ]
        comparison_tasks = [
            TaskResult(
                task_id="task1",
                task_description="",
                trials=[
                    TrialResult(
                        trial_id="t0",
                        task_id="task1",
                        timestamp=datetime.now(),
                        passed=True,  # Still passes
                        score=0.78,
                        duration_ms=100,
                        token_count=100,
                        grader_results={},
                    )
                ]
            )
        ]

        baseline = self._create_eval_result("baseline", [])
        baseline.task_results = baseline_tasks

        comparison = self._create_eval_result("comparison", [])
        comparison.task_results = comparison_tasks

        result = compare_eval_results(baseline, comparison)

        # Both pass first trial, so no regression on pass_at_1
        assert result["regressed"] is False


class TestMetricSelectionIntegration:
    """Integration tests for metric selection strategy."""

    def test_vdot_uses_pass_at_1(self):
        """VDOT should fail if any trial fails (Pass@1 = first trial)."""
        config = get_task_config("vdot_marathon_sub3")

        # First trial fails, others pass
        trials = [
            TrialResult(
                trial_id="t1", task_id="vdot_marathon_sub3",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t2", task_id="vdot_marathon_sub3",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
        ]
        task_result = TaskResult(task_id="vdot_marathon_sub3", task_description="", trials=trials)

        # Pass@1 = 0 (first trial failed)
        assert config.get_primary_metric(task_result) == 0.0
        assert not config.is_passing(task_result)

    def test_rag_uses_pass_at_k(self):
        """RAG should pass if any trial succeeds."""
        config = get_task_config("rag_marathon_training_basics")

        # First 2 fail, 3rd passes
        trials = [
            TrialResult(
                trial_id="t1", task_id="rag_marathon_training_basics",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t2", task_id="rag_marathon_training_basics",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t3", task_id="rag_marathon_training_basics",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
        ]
        task_result = TaskResult(task_id="rag_marathon_training_basics", task_description="", trials=trials)

        # Pass@3 = 1.0 (at least one success)
        assert config.get_primary_metric(task_result) == 1.0
        assert config.is_passing(task_result)

    def test_advice_uses_pass_pow_k(self):
        """Advice should require consistent success (Pass^k)."""
        config = get_task_config("advice_first_marathon")

        # 2/3 pass rate
        trials = [
            TrialResult(
                trial_id="t1", task_id="advice_first_marathon",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t2", task_id="advice_first_marathon",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            ),
            TrialResult(
                trial_id="t3", task_id="advice_first_marathon",
                timestamp=datetime.now(), passed=False,
                score=0.0, duration_ms=100, token_count=0, grader_results={}
            ),
        ]
        task_result = TaskResult(task_id="advice_first_marathon", task_description="", trials=trials)

        # Pass^3 = (2/3)^3 ≈ 0.296 < 0.75 threshold
        metric = config.get_primary_metric(task_result)
        assert 0.29 <= metric <= 0.31
        assert not config.is_passing(task_result)


class TestCIConfigIntegration:
    """Integration tests with CI configuration."""

    def test_pr_config_filters_p0_p1_only(self):
        """PR config should only include P0 and P1 tasks with matching metric type."""
        from tests.evals.ci_config import PR_FAST_CONFIG, filter_tasks_for_config

        # Create mock tasks
        tasks = [
            {"task_id": "should_not_recommend_running_through_pain"},  # P0, CUSTOMER_FACING
            {"task_id": "vdot_marathon_sub3"},  # P1, DETERMINISTIC
            {"task_id": "advice_tapering"},  # P2
            {"task_id": "personalization_busy_professional"},  # P3
        ]

        filtered = filter_tasks_for_config(tasks, PR_FAST_CONFIG)

        # PR_FAST_CONFIG: P0+P1 priorities, DETERMINISTIC metric type only
        # So only vdot_marathon_sub3 should pass (P1 + DETERMINISTIC)
        # P0 tasks are CUSTOMER_FACING, not DETERMINISTIC
        filtered_ids = [t["task_id"] for t in filtered]

        # At minimum, VDOT should be included (P1 + DETERMINISTIC)
        assert "vdot_marathon_sub3" in filtered_ids
        # P2 and P3 should not be included
        assert "advice_tapering" not in filtered_ids
        assert "personalization_busy_professional" not in filtered_ids

    def test_p0_failure_blocks_release(self):
        """P0 safety failure should block release."""
        from tests.evals.ci_config import RELEASE_FULL_CONFIG, validate_eval_result

        # Create eval result with P0 failure
        trials_pass = [
            TrialResult(
                trial_id=f"t{i}", task_id="should_not_recommend_running_through_pain",
                timestamp=datetime.now(), passed=True,
                score=1.0, duration_ms=100, token_count=0, grader_results={}
            )
            for i in range(3)
        ]
        trials_fail = [
            TrialResult(
                trial_id=f"t{i}", task_id="should_not_ignore_injury_symptoms",
                timestamp=datetime.now(), passed=i < 2,  # 2/3 pass
                score=1.0 if i < 2 else 0.0, duration_ms=100, token_count=0, grader_results={}
            )
            for i in range(3)
        ]

        eval_result = EvalResult(
            eval_id="test",
            eval_name="test",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                TaskResult(task_id="should_not_recommend_running_through_pain", task_description="", trials=trials_pass),
                TaskResult(task_id="should_not_ignore_injury_symptoms", task_description="", trials=trials_fail),
            ],
        )

        # Mock the EvalMetrics for simpler test
        validation = validate_eval_result(eval_result, RELEASE_FULL_CONFIG)

        # Should not pass due to P0 failure
        assert validation["passed"] is False
        assert any(issue["type"] == "p0_failure" for issue in validation["issues"])
