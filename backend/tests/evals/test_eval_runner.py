"""Tests for evaluation runner and metrics."""

import pytest
from datetime import datetime

from tests.evals.metrics import (
    EvalMetrics,
    EvalResult,
    TaskResult,
    TrialResult,
    calculate_confidence_interval,
    compare_eval_results,
)
from tests.evals.runner import EvalRunner, MockExecutor


class TestEvalMetrics:
    """Tests for evaluation metrics calculations."""

    @pytest.fixture
    def sample_trials(self):
        """Create sample trial results."""
        return [
            TrialResult(
                trial_id="task1_trial_1",
                task_id="task1",
                timestamp=datetime.now(),
                passed=True,
                score=0.9,
                duration_ms=100,
                token_count=200,
                grader_results={},
            ),
            TrialResult(
                trial_id="task1_trial_2",
                task_id="task1",
                timestamp=datetime.now(),
                passed=True,
                score=0.85,
                duration_ms=120,
                token_count=220,
                grader_results={},
            ),
            TrialResult(
                trial_id="task1_trial_3",
                task_id="task1",
                timestamp=datetime.now(),
                passed=False,
                score=0.6,
                duration_ms=150,
                token_count=250,
                grader_results={},
            ),
        ]

    def test_pass_at_1(self, sample_trials):
        """Test pass@1 calculation."""
        task_result = TaskResult(
            task_id="task1",
            task_description="Test task",
            trials=sample_trials,
        )

        # First trial passed
        assert task_result.pass_at_1() == 1.0

    def test_pass_at_k(self, sample_trials):
        """Test pass@k calculation."""
        task_result = TaskResult(
            task_id="task1",
            task_description="Test task",
            trials=sample_trials,
        )

        # At least one success in 3 trials
        assert task_result.pass_at_k(3) == 1.0

    def test_pass_pow_k(self, sample_trials):
        """Test pass^k calculation."""
        task_result = TaskResult(
            task_id="task1",
            task_description="Test task",
            trials=sample_trials,
        )

        # Success rate is 2/3 ≈ 0.67
        # pass^3 = 0.67^3 ≈ 0.30
        pass_pow_3 = task_result.pass_pow_k(3)
        assert 0.25 < pass_pow_3 < 0.35

    def test_avg_score(self, sample_trials):
        """Test average score calculation."""
        task_result = TaskResult(
            task_id="task1",
            task_description="Test task",
            trials=sample_trials,
        )

        # (0.9 + 0.85 + 0.6) / 3 = 0.783
        assert 0.78 < task_result.avg_score() < 0.79

    def test_all_passed_pass_pow_k(self):
        """Test pass^k when all trials pass."""
        trials = [
            TrialResult(
                trial_id=f"task_trial_{i}",
                task_id="task",
                timestamp=datetime.now(),
                passed=True,
                score=0.95,
                duration_ms=100,
                token_count=200,
                grader_results={},
            )
            for i in range(3)
        ]

        task_result = TaskResult(
            task_id="task",
            task_description="All pass",
            trials=trials,
        )

        # 100% success rate => 1.0^3 = 1.0
        assert task_result.pass_pow_k(3) == 1.0

    def test_all_failed_pass_pow_k(self):
        """Test pass^k when all trials fail."""
        trials = [
            TrialResult(
                trial_id=f"task_trial_{i}",
                task_id="task",
                timestamp=datetime.now(),
                passed=False,
                score=0.3,
                duration_ms=100,
                token_count=200,
                grader_results={},
            )
            for i in range(3)
        ]

        task_result = TaskResult(
            task_id="task",
            task_description="All fail",
            trials=trials,
        )

        # 0% success rate => 0.0^3 = 0.0
        assert task_result.pass_pow_k(3) == 0.0


class TestEvalResult:
    """Tests for complete eval result aggregation."""

    @pytest.fixture
    def sample_eval_result(self):
        """Create sample evaluation result."""
        task_results = []

        for task_num in range(3):
            trials = [
                TrialResult(
                    trial_id=f"task{task_num}_trial_{i}",
                    task_id=f"marathon_task_{task_num}",
                    timestamp=datetime.now(),
                    passed=(i < 2),  # 2 pass, 1 fail
                    score=0.8 if i < 2 else 0.4,
                    duration_ms=100 + i * 10,
                    token_count=200,
                    grader_results={},
                )
                for i in range(3)
            ]

            task_results.append(
                TaskResult(
                    task_id=f"marathon_task_{task_num}",
                    task_description=f"Task {task_num}",
                    trials=trials,
                )
            )

        return EvalResult(
            eval_id="test_eval_001",
            eval_name="test_eval",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=task_results,
        )

    def test_overall_pass_rate(self, sample_eval_result):
        """Test overall pass rate calculation."""
        # Each task has pass@1 = 1.0 (first trial passes)
        assert sample_eval_result.overall_pass_rate() == 1.0

    def test_overall_avg_score(self, sample_eval_result):
        """Test overall average score."""
        # Each task: (0.8 + 0.8 + 0.4) / 3 ≈ 0.67
        avg = sample_eval_result.overall_avg_score()
        assert 0.65 < avg < 0.70

    def test_by_category(self, sample_eval_result):
        """Test grouping by category."""
        by_cat = sample_eval_result.by_category()

        # All tasks have "marathon" prefix
        assert "marathon" in by_cat

    def test_summary(self, sample_eval_result):
        """Test summary generation."""
        summary = sample_eval_result.summary()

        assert "eval_id" in summary
        assert "total_tasks" in summary
        assert "overall_pass_rate" in summary
        assert "pass_at_3" in summary
        assert "pass_pow_3" in summary


class TestConfidenceInterval:
    """Tests for confidence interval calculation."""

    def test_high_pass_rate(self):
        """Test CI for high pass rate."""
        lower, upper = calculate_confidence_interval(0.9, 100)

        assert lower > 0.8
        assert upper < 1.0
        assert lower < 0.9 < upper

    def test_low_pass_rate(self):
        """Test CI for low pass rate."""
        lower, upper = calculate_confidence_interval(0.2, 100)

        assert lower > 0.0
        assert upper < 0.4
        assert lower < 0.2 < upper

    def test_few_samples(self):
        """Test CI with few samples (wider interval)."""
        lower_few, upper_few = calculate_confidence_interval(0.5, 10)
        lower_many, upper_many = calculate_confidence_interval(0.5, 1000)

        # Fewer samples = wider interval
        assert (upper_few - lower_few) > (upper_many - lower_many)


class TestCompareEvalResults:
    """Tests for comparing eval results."""

    def test_improved_result(self):
        """Test detecting improvement."""
        baseline = EvalResult(
            eval_id="baseline",
            eval_name="baseline",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                TaskResult(
                    task_id="task1",
                    task_description="Task",
                    trials=[
                        TrialResult(
                            trial_id="t1",
                            task_id="task1",
                            timestamp=datetime.now(),
                            passed=True,
                            score=0.7,
                            duration_ms=100,
                            token_count=200,
                            grader_results={},
                        )
                    ],
                )
            ],
        )

        comparison = EvalResult(
            eval_id="comparison",
            eval_name="comparison",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            config={},
            task_results=[
                TaskResult(
                    task_id="task1",
                    task_description="Task",
                    trials=[
                        TrialResult(
                            trial_id="t1",
                            task_id="task1",
                            timestamp=datetime.now(),
                            passed=True,
                            score=0.9,  # Improved
                            duration_ms=100,
                            token_count=200,
                            grader_results={},
                        )
                    ],
                )
            ],
        )

        result = compare_eval_results(baseline, comparison)

        assert result["improved"]
        assert result["score_delta"] > 0


class TestMockExecutor:
    """Tests for mock executor."""

    @pytest.mark.asyncio
    async def test_mock_executor_success_rate(self):
        """Test mock executor respects success rate."""
        executor = MockExecutor(success_rate=1.0)  # Always succeed

        results = []
        for i in range(10):
            result = await executor({"task_id": f"task_{i}"})
            results.append(result["success"])

        assert all(results)

    @pytest.mark.asyncio
    async def test_mock_executor_failure_rate(self):
        """Test mock executor can fail."""
        executor = MockExecutor(success_rate=0.0)  # Always fail

        results = []
        for i in range(10):
            result = await executor({"task_id": f"task_{i}"})
            results.append(result["success"])

        assert not any(results)


class TestEvalRunner:
    """Tests for evaluation runner."""

    @pytest.mark.asyncio
    async def test_runner_basic(self):
        """Test basic runner functionality."""
        runner = EvalRunner(
            eval_name="test_runner",
            config={
                "trials_per_task": 2,
                "save_transcripts": False,
            },
        )

        tasks = [
            {"task_id": "test_task_1", "description": "Test 1"},
            {"task_id": "test_task_2", "description": "Test 2"},
        ]

        executor = MockExecutor(success_rate=0.8)

        def simple_grader(task, result):
            return {
                "passed": result.get("success", False),
                "score": 0.8 if result.get("success") else 0.2,
            }

        result = await runner.run_eval(
            tasks=tasks,
            executor=executor,
            graders=[simple_grader],
        )

        assert result.eval_name == "test_runner"
        assert len(result.task_results) == 2
        assert all(len(tr.trials) == 2 for tr in result.task_results)

    @pytest.mark.asyncio
    async def test_runner_timeout(self):
        """Test runner handles timeouts."""
        import asyncio

        runner = EvalRunner(
            eval_name="timeout_test",
            config={
                "trials_per_task": 1,
                "timeout_seconds": 0.1,
                "save_transcripts": False,
            },
        )

        async def slow_executor(task):
            await asyncio.sleep(1)  # Longer than timeout
            return {"response": "done"}

        tasks = [{"task_id": "slow_task"}]

        result = await runner.run_eval(
            tasks=tasks,
            executor=slow_executor,
            graders=[],
        )

        # Should have error due to timeout
        assert result.task_results[0].trials[0].error is not None
        assert "timeout" in result.task_results[0].trials[0].error.lower()
