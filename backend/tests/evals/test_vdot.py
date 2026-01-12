"""VDOT calculation accuracy tests.

These tests verify the VDOT calculation service against
Jack Daniels' published tables and formulas.
"""

import pytest

from app.services.vdot import (
    calculate_vdot,
    get_training_paces,
    get_race_equivalents,
    vdot_from_5k,
    vdot_from_10k,
    vdot_from_half_marathon,
    vdot_from_marathon,
)
from tests.evals.graders.code_graders import grade_vdot_accuracy, grade_pace_accuracy


class TestVDOTCalculation:
    """Tests for VDOT calculation accuracy."""

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "time_5k_str,expected_vdot",
        [
            ("14:30", 70.0),  # Elite
            ("18:00", 55.0),  # Advanced
            ("20:00", 50.0),  # Good
            ("22:00", 44.0),  # Intermediate
            ("25:00", 40.0),  # Recreational
            ("28:00", 35.0),  # Beginner
            ("30:00", 33.0),  # Novice
        ],
    )
    def test_vdot_from_5k(self, time_5k_str: str, expected_vdot: float):
        """Test VDOT calculation from 5K times."""
        parts = time_5k_str.split(":")
        time_seconds = int(parts[0]) * 60 + int(parts[1])

        result = vdot_from_5k(time_seconds)
        grade = grade_vdot_accuracy(result.vdot, expected_vdot, tolerance=2.0)

        assert grade["passed"], f"VDOT {result.vdot:.1f} not within tolerance of {expected_vdot}"

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "time_10k_str,expected_vdot",
        [
            ("30:00", 70.0),  # Elite
            ("38:00", 58.0),  # Advanced
            ("45:00", 49.0),  # Good
            ("50:00", 44.0),  # Intermediate
            ("55:00", 40.0),  # Recreational
            ("60:00", 37.0),  # Beginner
        ],
    )
    def test_vdot_from_10k(self, time_10k_str: str, expected_vdot: float):
        """Test VDOT calculation from 10K times."""
        parts = time_10k_str.split(":")
        time_seconds = int(parts[0]) * 60 + int(parts[1])

        result = vdot_from_10k(time_seconds)
        grade = grade_vdot_accuracy(result.vdot, expected_vdot, tolerance=2.0)

        assert grade["passed"], f"VDOT {result.vdot:.1f} not within tolerance of {expected_vdot}"

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "time_half_str,expected_vdot",
        [
            ("1:10:00", 65.0),  # Elite
            ("1:25:00", 56.0),  # Advanced
            ("1:40:00", 48.0),  # Good
            ("1:50:00", 44.0),  # Intermediate
            ("2:00:00", 40.0),  # Recreational
            ("2:15:00", 36.0),  # Beginner
        ],
    )
    def test_vdot_from_half_marathon(self, time_half_str: str, expected_vdot: float):
        """Test VDOT calculation from half marathon times."""
        parts = time_half_str.split(":")
        time_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        result = vdot_from_half_marathon(time_seconds)
        grade = grade_vdot_accuracy(result.vdot, expected_vdot, tolerance=2.0)

        assert grade["passed"], f"VDOT {result.vdot:.1f} not within tolerance of {expected_vdot}"

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "time_marathon_str,expected_vdot",
        [
            ("2:30:00", 60.0),  # Elite
            ("2:55:00", 54.0),  # Advanced
            ("3:15:00", 48.0),  # Good
            ("3:30:00", 45.0),  # Intermediate
            ("4:00:00", 39.0),  # Recreational
            ("4:30:00", 35.0),  # Beginner
        ],
    )
    def test_vdot_from_marathon(self, time_marathon_str: str, expected_vdot: float):
        """Test VDOT calculation from marathon times."""
        parts = time_marathon_str.split(":")
        time_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        result = vdot_from_marathon(time_seconds)
        grade = grade_vdot_accuracy(result.vdot, expected_vdot, tolerance=2.0)

        assert grade["passed"], f"VDOT {result.vdot:.1f} not within tolerance of {expected_vdot}"


class TestTrainingPaces:
    """Tests for training pace calculations."""

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "vdot,expected_easy_min,expected_easy_max",
        [
            (50, 330, 380),  # 5:30-6:20
            (45, 370, 430),  # 6:10-7:10
            (40, 420, 490),  # 7:00-8:10
            (55, 300, 350),  # 5:00-5:50
            (60, 270, 320),  # 4:30-5:20
        ],
    )
    def test_easy_pace_range(
        self, vdot: float, expected_easy_min: int, expected_easy_max: int
    ):
        """Test easy pace range calculation."""
        paces = get_training_paces(vdot)

        # Easy min should be in expected range (slower end)
        min_grade = grade_pace_accuracy(paces.easy_min, expected_easy_min, tolerance=20)
        max_grade = grade_pace_accuracy(paces.easy_max, expected_easy_max, tolerance=20)

        assert min_grade["passed"], f"Easy min {paces.easy_min}s not in range"
        assert max_grade["passed"], f"Easy max {paces.easy_max}s not in range"

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "vdot,expected_marathon_pace",
        [
            (50, 300),  # 5:00/km
            (45, 330),  # 5:30/km
            (40, 370),  # 6:10/km
            (55, 270),  # 4:30/km
        ],
    )
    def test_marathon_pace(self, vdot: float, expected_marathon_pace: int):
        """Test marathon pace calculation."""
        paces = get_training_paces(vdot)
        grade = grade_pace_accuracy(paces.marathon, expected_marathon_pace, tolerance=15)

        assert grade["passed"], f"Marathon pace {paces.marathon}s not accurate"

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "vdot,expected_threshold_pace",
        [
            (50, 276),  # 4:36/km
            (45, 306),  # 5:06/km
            (40, 342),  # 5:42/km
            (55, 252),  # 4:12/km
        ],
    )
    def test_threshold_pace(self, vdot: float, expected_threshold_pace: int):
        """Test threshold pace calculation."""
        paces = get_training_paces(vdot)
        grade = grade_pace_accuracy(paces.threshold, expected_threshold_pace, tolerance=15)

        assert grade["passed"], f"Threshold pace {paces.threshold}s not accurate"

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "vdot,expected_interval_pace",
        [
            (50, 258),  # 4:18/km
            (45, 282),  # 4:42/km
            (40, 318),  # 5:18/km
            (55, 234),  # 3:54/km
        ],
    )
    def test_interval_pace(self, vdot: float, expected_interval_pace: int):
        """Test interval pace calculation."""
        paces = get_training_paces(vdot)
        grade = grade_pace_accuracy(paces.interval, expected_interval_pace, tolerance=15)

        assert grade["passed"], f"Interval pace {paces.interval}s not accurate"


class TestRaceEquivalents:
    """Tests for race time predictions."""

    @pytest.mark.vdot
    def test_race_equivalents_consistency(self):
        """Test that race equivalents are internally consistent."""
        # Calculate VDOT from 5K
        result_5k = vdot_from_5k(20 * 60)  # 20:00 5K

        # Get race equivalents
        equivalents = get_race_equivalents(result_5k.vdot)

        # Verify we get all standard distances
        distance_names = [e.distance_name for e in equivalents]
        assert "5K" in distance_names
        assert "10K" in distance_names
        assert "Half Marathon" in distance_names
        assert "Marathon" in distance_names

        # Verify times increase with distance
        times = {e.distance_name: e.time_seconds for e in equivalents}
        assert times["5K"] < times["10K"]
        assert times["10K"] < times["Half Marathon"]
        assert times["Half Marathon"] < times["Marathon"]

    @pytest.mark.vdot
    @pytest.mark.parametrize(
        "vdot,expected_5k,expected_marathon",
        [
            (50, 20 * 60 + 45, 3 * 3600 + 20 * 60),  # ~20:45, ~3:20
            (45, 23 * 60 + 15, 3 * 3600 + 48 * 60),  # ~23:15, ~3:48
            (40, 26 * 60 + 30, 4 * 3600 + 18 * 60),  # ~26:30, ~4:18
        ],
    )
    def test_race_time_predictions(
        self, vdot: float, expected_5k: int, expected_marathon: int
    ):
        """Test race time prediction accuracy."""
        equivalents = get_race_equivalents(vdot)
        times = {e.distance_name: e.time_seconds for e in equivalents}

        # 5K should be within 90 seconds
        assert abs(times["5K"] - expected_5k) < 90, f"5K prediction off by {abs(times['5K'] - expected_5k)}s"

        # Marathon should be within 5 minutes
        assert abs(times["Marathon"] - expected_marathon) < 300, f"Marathon prediction off by {abs(times['Marathon'] - expected_marathon)}s"


class TestVDOTEdgeCases:
    """Tests for edge cases in VDOT calculation."""

    @pytest.mark.vdot
    def test_very_fast_5k(self):
        """Test world-class 5K time (~13:00)."""
        result = vdot_from_5k(13 * 60)
        assert 75 < result.vdot < 85, f"Elite VDOT {result.vdot} out of expected range"

    @pytest.mark.vdot
    def test_very_slow_5k(self):
        """Test beginner jogger 5K (~40:00)."""
        result = vdot_from_5k(40 * 60)
        assert 20 < result.vdot < 30, f"Beginner VDOT {result.vdot} out of expected range"

    @pytest.mark.vdot
    def test_vdot_consistency_across_distances(self):
        """Test that same fitness level gives similar VDOT from different distances."""
        # For a VDOT 50 runner
        vdot_50_5k = 20 * 60 + 45  # ~20:45
        vdot_50_10k = 43 * 60 + 6  # ~43:06
        vdot_50_half = 1 * 3600 + 35 * 60  # ~1:35:00
        vdot_50_full = 3 * 3600 + 20 * 60  # ~3:20:00

        result_5k = vdot_from_5k(vdot_50_5k)
        result_10k = vdot_from_10k(vdot_50_10k)
        result_half = vdot_from_half_marathon(vdot_50_half)
        result_full = vdot_from_marathon(vdot_50_full)

        vdots = [result_5k.vdot, result_10k.vdot, result_half.vdot, result_full.vdot]

        # All should be within 3 of each other
        assert max(vdots) - min(vdots) < 4, f"VDOT inconsistency: {vdots}"

    @pytest.mark.vdot
    def test_training_pace_ordering(self):
        """Test that training paces are in correct order (fast to slow)."""
        paces = get_training_paces(50)

        # Repetition < Interval < Threshold < Marathon < Easy
        assert paces.repetition < paces.interval
        assert paces.interval < paces.threshold
        assert paces.threshold < paces.marathon
        assert paces.marathon < paces.easy_min

    @pytest.mark.vdot
    def test_result_to_dict(self):
        """Test VDOTResult serialization."""
        result = vdot_from_5k(20 * 60)
        data = result.to_dict()

        assert "vdot" in data
        assert "training_paces" in data
        assert "race_equivalents" in data

        # Check training paces structure
        assert "easy" in data["training_paces"]
        assert "marathon" in data["training_paces"]
        assert "threshold" in data["training_paces"]
        assert "interval" in data["training_paces"]
        assert "repetition" in data["training_paces"]

        # Check paces have correct format
        assert "pace" in data["training_paces"]["marathon"]
        assert ":" in data["training_paces"]["marathon"]["pace"]
