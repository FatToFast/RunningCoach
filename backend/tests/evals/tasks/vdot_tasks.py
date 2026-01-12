"""VDOT calculation evaluation tasks.

These tasks verify the accuracy of VDOT calculations against
Jack Daniels' published tables and formulas.
"""

from typing import TypedDict


class VDOTTask(TypedDict):
    """VDOT evaluation task definition."""

    task_id: str
    description: str
    input: dict
    expected: dict
    tolerance: dict


# Reference data from Jack Daniels' Running Formula tables
VDOT_TASKS: list[VDOTTask] = [
    # 5K times
    {
        "task_id": "vdot_5k_elite",
        "description": "Elite 5K runner (sub-15)",
        "input": {
            "distance_meters": 5000,
            "time_seconds": 14 * 60 + 30,  # 14:30
        },
        "expected": {
            "vdot": 70.0,
            "training_paces": {
                "easy_min": 270,  # 4:30/km
                "easy_max": 300,  # 5:00/km
                "marathon": 218,  # 3:38/km
                "threshold": 203,  # 3:23/km
                "interval": 189,  # 3:09/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 10,  # seconds
        },
    },
    {
        "task_id": "vdot_5k_advanced",
        "description": "Advanced 5K runner (~18:00)",
        "input": {
            "distance_meters": 5000,
            "time_seconds": 18 * 60,  # 18:00
        },
        "expected": {
            "vdot": 55.0,
            "training_paces": {
                "easy_min": 330,  # 5:30/km
                "easy_max": 370,  # 6:10/km
                "marathon": 270,  # 4:30/km
                "threshold": 252,  # 4:12/km
                "interval": 234,  # 3:54/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 12,
        },
    },
    {
        "task_id": "vdot_5k_intermediate",
        "description": "Intermediate 5K runner (~22:00)",
        "input": {
            "distance_meters": 5000,
            "time_seconds": 22 * 60,  # 22:00
        },
        "expected": {
            "vdot": 44.0,
            "training_paces": {
                "easy_min": 400,  # 6:40/km
                "easy_max": 450,  # 7:30/km
                "marathon": 330,  # 5:30/km
                "threshold": 306,  # 5:06/km
                "interval": 282,  # 4:42/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 15,
        },
    },
    {
        "task_id": "vdot_5k_beginner",
        "description": "Beginner 5K runner (~28:00)",
        "input": {
            "distance_meters": 5000,
            "time_seconds": 28 * 60,  # 28:00
        },
        "expected": {
            "vdot": 35.0,
            "training_paces": {
                "easy_min": 480,  # 8:00/km
                "easy_max": 540,  # 9:00/km
                "marathon": 400,  # 6:40/km
                "threshold": 372,  # 6:12/km
                "interval": 342,  # 5:42/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 18,
        },
    },
    # 10K times
    {
        "task_id": "vdot_10k_sub40",
        "description": "10K runner sub-40",
        "input": {
            "distance_meters": 10000,
            "time_seconds": 38 * 60,  # 38:00
        },
        "expected": {
            "vdot": 58.0,
            "training_paces": {
                "easy_min": 318,  # 5:18/km
                "easy_max": 354,  # 5:54/km
                "marathon": 258,  # 4:18/km
                "threshold": 240,  # 4:00/km
                "interval": 222,  # 3:42/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 12,
        },
    },
    {
        "task_id": "vdot_10k_45min",
        "description": "10K runner ~45 min",
        "input": {
            "distance_meters": 10000,
            "time_seconds": 45 * 60,  # 45:00
        },
        "expected": {
            "vdot": 49.0,
            "training_paces": {
                "easy_min": 366,  # 6:06/km
                "easy_max": 408,  # 6:48/km
                "marathon": 300,  # 5:00/km
                "threshold": 276,  # 4:36/km
                "interval": 258,  # 4:18/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 15,
        },
    },
    {
        "task_id": "vdot_10k_50min",
        "description": "10K runner ~50 min",
        "input": {
            "distance_meters": 10000,
            "time_seconds": 50 * 60,  # 50:00
        },
        "expected": {
            "vdot": 44.0,
            "training_paces": {
                "easy_min": 400,  # 6:40/km
                "easy_max": 450,  # 7:30/km
                "marathon": 330,  # 5:30/km
                "threshold": 306,  # 5:06/km
                "interval": 282,  # 4:42/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 15,
        },
    },
    {
        "task_id": "vdot_10k_60min",
        "description": "10K runner ~60 min (beginner)",
        "input": {
            "distance_meters": 10000,
            "time_seconds": 60 * 60,  # 60:00
        },
        "expected": {
            "vdot": 37.0,
            "training_paces": {
                "easy_min": 468,  # 7:48/km
                "easy_max": 522,  # 8:42/km
                "marathon": 390,  # 6:30/km
                "threshold": 360,  # 6:00/km
                "interval": 330,  # 5:30/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 18,
        },
    },
    # Half Marathon times
    {
        "task_id": "vdot_half_sub90",
        "description": "Half marathon sub-90",
        "input": {
            "distance_meters": 21097.5,
            "time_seconds": 85 * 60,  # 1:25:00
        },
        "expected": {
            "vdot": 56.0,
            "training_paces": {
                "easy_min": 324,  # 5:24/km
                "easy_max": 360,  # 6:00/km
                "marathon": 264,  # 4:24/km
                "threshold": 246,  # 4:06/km
                "interval": 228,  # 3:48/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 12,
        },
    },
    {
        "task_id": "vdot_half_100min",
        "description": "Half marathon ~1:40",
        "input": {
            "distance_meters": 21097.5,
            "time_seconds": 100 * 60,  # 1:40:00
        },
        "expected": {
            "vdot": 48.0,
            "training_paces": {
                "easy_min": 372,  # 6:12/km
                "easy_max": 414,  # 6:54/km
                "marathon": 306,  # 5:06/km
                "threshold": 282,  # 4:42/km
                "interval": 264,  # 4:24/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 15,
        },
    },
    {
        "task_id": "vdot_half_2hours",
        "description": "Half marathon ~2:00",
        "input": {
            "distance_meters": 21097.5,
            "time_seconds": 120 * 60,  # 2:00:00
        },
        "expected": {
            "vdot": 40.0,
            "training_paces": {
                "easy_min": 432,  # 7:12/km
                "easy_max": 480,  # 8:00/km
                "marathon": 360,  # 6:00/km
                "threshold": 336,  # 5:36/km
                "interval": 306,  # 5:06/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 18,
        },
    },
    # Marathon times
    {
        "task_id": "vdot_marathon_sub3",
        "description": "Marathon sub-3",
        "input": {
            "distance_meters": 42195,
            "time_seconds": 2 * 3600 + 55 * 60,  # 2:55:00
        },
        "expected": {
            "vdot": 54.0,
            "training_paces": {
                "easy_min": 336,  # 5:36/km
                "easy_max": 378,  # 6:18/km
                "marathon": 276,  # 4:36/km
                "threshold": 258,  # 4:18/km
                "interval": 240,  # 4:00/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 15,
        },
    },
    {
        "task_id": "vdot_marathon_330",
        "description": "Marathon 3:30",
        "input": {
            "distance_meters": 42195,
            "time_seconds": 3 * 3600 + 30 * 60,  # 3:30:00
        },
        "expected": {
            "vdot": 45.0,
            "training_paces": {
                "easy_min": 390,  # 6:30/km
                "easy_max": 438,  # 7:18/km
                "marathon": 324,  # 5:24/km
                "threshold": 300,  # 5:00/km
                "interval": 276,  # 4:36/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 15,
        },
    },
    {
        "task_id": "vdot_marathon_4hours",
        "description": "Marathon 4:00",
        "input": {
            "distance_meters": 42195,
            "time_seconds": 4 * 3600,  # 4:00:00
        },
        "expected": {
            "vdot": 39.0,
            "training_paces": {
                "easy_min": 444,  # 7:24/km
                "easy_max": 498,  # 8:18/km
                "marathon": 372,  # 6:12/km
                "threshold": 342,  # 5:42/km
                "interval": 318,  # 5:18/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 18,
        },
    },
    {
        "task_id": "vdot_marathon_430",
        "description": "Marathon 4:30 (beginner)",
        "input": {
            "distance_meters": 42195,
            "time_seconds": 4 * 3600 + 30 * 60,  # 4:30:00
        },
        "expected": {
            "vdot": 35.0,
            "training_paces": {
                "easy_min": 480,  # 8:00/km
                "easy_max": 540,  # 9:00/km
                "marathon": 402,  # 6:42/km
                "threshold": 372,  # 6:12/km
                "interval": 342,  # 5:42/km
            },
        },
        "tolerance": {
            "vdot": 2.0,
            "pace": 20,
        },
    },
    # Edge cases
    {
        "task_id": "vdot_edge_very_fast",
        "description": "World-class 5K (~13:00)",
        "input": {
            "distance_meters": 5000,
            "time_seconds": 13 * 60,  # 13:00
        },
        "expected": {
            "vdot": 78.0,
        },
        "tolerance": {
            "vdot": 3.0,
            "pace": 10,
        },
    },
    {
        "task_id": "vdot_edge_very_slow",
        "description": "Beginning jogger 5K (~35:00)",
        "input": {
            "distance_meters": 5000,
            "time_seconds": 35 * 60,  # 35:00
        },
        "expected": {
            "vdot": 28.0,
        },
        "tolerance": {
            "vdot": 3.0,
            "pace": 25,
        },
    },
    # Race equivalency tests
    {
        "task_id": "vdot_equivalency_50",
        "description": "Race equivalency at VDOT 50",
        "input": {
            "vdot": 50.0,
        },
        "expected": {
            "race_times": {
                "5K": 20 * 60 + 45,  # 20:45
                "10K": 43 * 60 + 6,  # 43:06
                "Half Marathon": 1 * 3600 + 35 * 60,  # 1:35:00
                "Marathon": 3 * 3600 + 20 * 60,  # 3:20:00
            },
        },
        "tolerance": {
            "time": 90,  # seconds
        },
    },
    {
        "task_id": "vdot_equivalency_40",
        "description": "Race equivalency at VDOT 40",
        "input": {
            "vdot": 40.0,
        },
        "expected": {
            "race_times": {
                "5K": 26 * 60 + 27,  # 26:27
                "10K": 55 * 60,  # 55:00
                "Half Marathon": 2 * 3600 + 2 * 60,  # 2:02:00
                "Marathon": 4 * 3600 + 18 * 60,  # 4:18:00
            },
        },
        "tolerance": {
            "time": 120,  # seconds
        },
    },
]
