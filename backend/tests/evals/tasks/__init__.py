"""Task definitions for AI evaluation.

Tasks are the fundamental unit of evaluation - each task has:
- A unique ID
- Input context (user profile, goal, constraints)
- Success criteria (must include, must not include, ranges)
"""

from tests.evals.tasks.training_plan_tasks import TRAINING_PLAN_TASKS
from tests.evals.tasks.coaching_advice_tasks import COACHING_ADVICE_TASKS
from tests.evals.tasks.vdot_tasks import VDOT_TASKS

__all__ = ["TRAINING_PLAN_TASKS", "COACHING_ADVICE_TASKS", "VDOT_TASKS"]
