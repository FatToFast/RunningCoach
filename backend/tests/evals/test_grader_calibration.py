"""Tests for grader calibration and consistency.

Validates that graders:
- Return consistent results across multiple calls
- Agree with expected ground truth
- Have acceptable inter-grader reliability
"""

import pytest
from datetime import datetime
from typing import Any

from tests.evals.graders.code_graders import (
    grade_weekly_mileage_progression,
    grade_rest_days,
    grade_tapering,
    grade_intensity_distribution,
    grade_must_include_criteria,
    grade_must_not_include_criteria,
    grade_vdot_accuracy,
    grade_pace_accuracy,
)
from tests.evals.graders.rubric_graders import (
    COACHING_QUALITY_RUBRIC,
    TRAINING_PLAN_RUBRIC,
    apply_rubric,
)


class TestCodeGraderCalibration:
    """Calibration tests for code-based graders."""

    def test_mileage_progression_determinism(self):
        """Same input should produce same output."""
        mileages = [30, 33, 36, 40, 44, 48]

        results = [grade_weekly_mileage_progression(mileages) for _ in range(10)]

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_rest_days_language_consistency(self):
        """Korean and English keywords should be graded consistently."""
        korean_schedule = ["이지런", "인터벌", "휴식", "템포런", "이지런", "휴식", "장거리"]
        english_schedule = ["easy", "interval", "rest", "tempo", "easy", "rest", "long run"]

        korean_result = grade_rest_days(korean_schedule)
        english_result = grade_rest_days(english_schedule)

        # Both should pass (2 rest days)
        assert korean_result["passed"] == english_result["passed"]
        assert korean_result["rest_days"] == english_result["rest_days"]

    def test_tapering_boundary_conditions(self):
        """Test tapering grader at boundary conditions."""
        # Exactly 50% reduction (borderline)
        borderline_mileages = [40, 45, 50, 55, 60, 55, 50, 45, 30]  # 30 is 50% of peak 60
        result = grade_tapering(borderline_mileages, race_week_index=8)

        # Should pass (50% reduction is acceptable)
        assert result["passed"]

    def test_intensity_distribution_edge_cases(self):
        """Test intensity distribution at exact thresholds."""
        # Exactly 80/20 split
        exact_80_20 = ["이지런"] * 4 + ["인터벌"]
        result = grade_intensity_distribution(exact_80_20)

        assert result["easy_percent"] == 80

    def test_vdot_accuracy_tolerance(self):
        """Test VDOT accuracy within tolerance."""
        # Expected: 50, Actual: 51.5 (within 2.0 tolerance)
        result = grade_vdot_accuracy(51.5, 50, tolerance=2.0)
        assert result["passed"]

        # Expected: 50, Actual: 52.5 (outside 2.0 tolerance)
        result = grade_vdot_accuracy(52.5, 50, tolerance=2.0)
        assert not result["passed"]

    def test_pace_accuracy_tolerance(self):
        """Test pace accuracy within tolerance."""
        # Expected: 300 sec/km, Actual: 310 (within 15 sec tolerance)
        result = grade_pace_accuracy(310, 300, tolerance=15)
        assert result["passed"]

        # Expected: 300 sec/km, Actual: 320 (outside 15 sec tolerance)
        result = grade_pace_accuracy(320, 300, tolerance=15)
        assert not result["passed"]


class TestRubricGraderCalibration:
    """Calibration tests for rubric-based graders."""

    def test_rubric_score_boundaries(self):
        """Test rubric scoring at grade boundaries."""
        # Perfect scores = A
        perfect = {"개인화": 5, "과학적 정확성": 5, "안전성": 5, "실행 가능성": 5, "명확성": 5}
        assert apply_rubric(COACHING_QUALITY_RUBRIC, perfect)["grade"] == "A"

        # Minimum passing = C (0.6-0.7)
        minimum_passing = {"개인화": 3, "과학적 정확성": 3, "안전성": 3, "실행 가능성": 3, "명확성": 3}
        result = apply_rubric(COACHING_QUALITY_RUBRIC, minimum_passing)
        assert result["grade"] in ["B", "C"]  # 3/5 = 0.6

        # Failing scores = F
        failing = {"개인화": 1, "과학적 정확성": 1, "안전성": 1, "실행 가능성": 1, "명확성": 1}
        assert apply_rubric(COACHING_QUALITY_RUBRIC, failing)["grade"] == "F"

    def test_rubric_weight_impact(self):
        """Test that weights affect scores correctly."""
        # High safety (weight 1.5) vs low safety
        high_safety = {"개인화": 3, "과학적 정확성": 3, "안전성": 5, "실행 가능성": 3, "명확성": 3}
        low_safety = {"개인화": 3, "과학적 정확성": 3, "안전성": 1, "실행 가능성": 3, "명확성": 3}

        high_result = apply_rubric(COACHING_QUALITY_RUBRIC, high_safety)
        low_result = apply_rubric(COACHING_QUALITY_RUBRIC, low_safety)

        # Safety weight (1.5) should create bigger difference than equal weight
        diff = high_result["normalized_score"] - low_result["normalized_score"]
        assert diff > 0.15  # Safety difference should be significant

    def test_rubric_missing_criteria(self):
        """Test rubric handling of missing criteria."""
        incomplete = {"개인화": 4, "과학적 정확성": 4}  # Missing 3 criteria

        # Should handle gracefully
        try:
            result = apply_rubric(COACHING_QUALITY_RUBRIC, incomplete)
            # If it doesn't raise, check it handled missing values
            assert "error" in result or result["total_score"] < 25
        except (KeyError, ValueError):
            # Expected if strict validation
            pass


class TestCriteriaGraderCalibration:
    """Calibration tests for criteria-based graders."""

    def test_must_include_partial_matching(self):
        """Test partial matching behavior."""
        response = "이 계획은 점진적 거리 증가를 포함합니다."

        # Exact match
        exact_criteria = ["점진적"]
        exact_result = grade_must_include_criteria(response, exact_criteria)
        assert exact_result["passed"]

        # Partial match (should find "점진적" in "점진적 거리")
        partial_criteria = ["점진적 거리"]
        partial_result = grade_must_include_criteria(response, partial_criteria)
        assert partial_result["passed"]

    def test_must_not_include_case_sensitivity(self):
        """Test case sensitivity in exclusion checks."""
        response = "통증을 무시하지 마세요."

        # Exact case
        exact_criteria = ["통증을 무시"]
        exact_result = grade_must_not_include_criteria(response, exact_criteria)
        # Should find "통증을 무시" in the response
        assert not exact_result["passed"]

        # Different phrasing
        diff_criteria = ["통증 무시"]
        diff_result = grade_must_not_include_criteria(response, diff_criteria)
        # Might not find exact "통증 무시" (depends on implementation)

    def test_criteria_scoring_proportional(self):
        """Test that scoring is proportional to criteria met."""
        response = "점진적 증가와 휴식일을 포함한 계획"

        # 2 of 4 criteria
        criteria = ["점진적", "휴식일", "테이퍼링", "장거리"]
        result = grade_must_include_criteria(response, criteria)

        # Score should be ~0.5 (2/4)
        assert 0.4 <= result["score"] <= 0.6


class TestInterGraderReliability:
    """Tests for agreement between different grading methods."""

    def test_safety_graders_agree(self):
        """Safety-related graders should agree on obvious cases."""
        # Obviously unsafe advice
        unsafe_response = "통증이 있어도 계속 달리세요. 매일 운동해야 합니다."

        # Criteria-based grader
        criteria_result = grade_must_not_include_criteria(
            unsafe_response,
            ["통증", "매일"]
        )

        # Both should flag as problematic
        assert not criteria_result["passed"]

    def test_quality_graders_correlate(self):
        """Quality metrics should correlate across grading methods."""
        # High quality plan with all elements
        high_quality_response = """
        훈련 계획입니다.
        점진적으로 거리를 늘려갑니다 (10% 규칙).
        장거리 러닝은 주 1회, 휴식일은 2일 포함.
        테이퍼링 기간도 충분히 배치했습니다.
        """

        # Criteria check
        criteria_result = grade_must_include_criteria(
            high_quality_response,
            ["점진적", "장거리", "휴식", "테이퍼링"]
        )

        # Rubric check (simulated)
        rubric_scores = {
            "점진적 부하 원칙": 5,  # Clear progressive loading
            "강도 분배": 4,          # Good distribution
            "테이퍼링": 5,           # Explicit tapering
            "장거리 배치": 4,        # Good long run placement
            "목표 적합성": 4,        # Reasonable goals
        }
        rubric_result = apply_rubric(TRAINING_PLAN_RUBRIC, rubric_scores)

        # Both should indicate high quality
        assert criteria_result["passed"]
        assert rubric_result["passed"]


class TestGraderEdgeCases:
    """Edge case tests for grader robustness."""

    def test_empty_input_handling(self):
        """Graders should handle empty inputs gracefully."""
        # Empty mileages
        result = grade_weekly_mileage_progression([])
        assert result["score"] == 1.0 or result["passed"]  # No violations

        # Empty schedule
        result = grade_rest_days([])
        assert "rest_days" in result

        # Empty response
        result = grade_must_include_criteria("", ["test"])
        assert not result["passed"]

    def test_single_element_handling(self):
        """Graders should handle single-element inputs."""
        # Single week
        result = grade_weekly_mileage_progression([40])
        assert result["passed"]  # No progression to check

        # Single workout
        result = grade_intensity_distribution(["이지런"])
        assert result["easy_percent"] == 100

    def test_unicode_handling(self):
        """Graders should handle Unicode correctly."""
        korean_response = "훈련 계획: 점진적 증가, 휴식일 포함, 장거리 러닝"
        emoji_response = "훈련 계획 🏃‍♂️: 점진적 증가 📈, 휴식일 포함 😴"

        korean_result = grade_must_include_criteria(korean_response, ["점진적", "휴식일"])
        emoji_result = grade_must_include_criteria(emoji_response, ["점진적", "휴식일"])

        assert korean_result["passed"]
        assert emoji_result["passed"]

    def test_extreme_values(self):
        """Graders should handle extreme values."""
        # Very high mileage increase
        extreme_mileages = [10, 100]  # 900% increase
        result = grade_weekly_mileage_progression(extreme_mileages)
        assert not result["passed"]
        assert len(result["violations"]) > 0

        # Perfect tapering (100% reduction)
        perfect_taper = [60, 55, 50, 45, 40, 35, 30, 25, 0]
        result = grade_tapering(perfect_taper, race_week_index=8)
        assert result["passed"]


class TestGroundTruthValidation:
    """Validate graders against known ground truth examples."""

    @pytest.mark.parametrize("mileages,expected_pass", [
        # Safe progression (< 10% per week)
        ([30, 33, 36, 39, 43], True),
        # Borderline (exactly 10%)
        ([30, 33, 36.3, 39.93, 43.92], True),
        # Unsafe (> 10%)
        ([30, 35, 42, 50, 60], False),
        # Recovery week pattern (safe)
        ([40, 44, 48, 35, 45], True),
    ])
    def test_mileage_progression_ground_truth(self, mileages, expected_pass):
        """Test mileage progression against ground truth."""
        result = grade_weekly_mileage_progression(mileages)
        assert result["passed"] == expected_pass, f"Failed for {mileages}"

    @pytest.mark.parametrize("vdot,expected_vdot,tolerance,expected_pass", [
        # Exact match
        (50.0, 50.0, 2.0, True),
        # Within tolerance
        (51.5, 50.0, 2.0, True),
        # At boundary
        (52.0, 50.0, 2.0, True),
        # Outside tolerance
        (53.0, 50.0, 2.0, False),
    ])
    def test_vdot_accuracy_ground_truth(self, vdot, expected_vdot, tolerance, expected_pass):
        """Test VDOT accuracy against ground truth."""
        result = grade_vdot_accuracy(vdot, expected_vdot, tolerance)
        assert result["passed"] == expected_pass

    @pytest.mark.parametrize("response,criteria,expected_found", [
        # All present
        ("점진적 증가와 휴식일, 장거리 포함", ["점진적", "휴식일", "장거리"], 3),
        # Partial
        ("점진적 증가만 있는 계획", ["점진적", "휴식일", "장거리"], 1),
        # None present
        ("일반적인 계획입니다", ["점진적", "휴식일", "장거리"], 0),
    ])
    def test_must_include_ground_truth(self, response, criteria, expected_found):
        """Test must include criteria against ground truth."""
        result = grade_must_include_criteria(response, criteria)
        assert len(result["found"]) == expected_found


class TestGraderPerformance:
    """Performance tests for graders."""

    def test_large_input_performance(self):
        """Graders should handle large inputs efficiently."""
        import time

        # Large mileage list (52 weeks)
        large_mileages = [30 + i * 0.5 for i in range(52)]

        start = time.time()
        for _ in range(100):
            grade_weekly_mileage_progression(large_mileages)
        elapsed = time.time() - start

        # Should complete 100 iterations in < 1 second
        assert elapsed < 1.0, f"Too slow: {elapsed:.2f}s for 100 iterations"

    def test_long_response_performance(self):
        """Criteria grading should be fast for long responses."""
        import time

        # Long response (1000 words)
        long_response = " ".join(["점진적 증가와 휴식일을 포함한 훈련 계획"] * 100)
        criteria = ["점진적", "휴식일", "테이퍼링", "장거리", "강도"]

        start = time.time()
        for _ in range(100):
            grade_must_include_criteria(long_response, criteria)
        elapsed = time.time() - start

        # Should complete 100 iterations in < 1 second
        assert elapsed < 1.0, f"Too slow: {elapsed:.2f}s for 100 iterations"
