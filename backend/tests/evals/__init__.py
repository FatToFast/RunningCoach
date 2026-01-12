"""AI Evaluation System for RunningCoach.

This package implements a comprehensive evaluation framework for the AI coach,
based on Anthropic's "Demystifying Evals for AI Agents" methodology.

Key Components:
- tasks/: Task definitions with input/success criteria
- graders/: Code-based, LLM-based, and rubric graders
- datasets/: Test datasets including real failures and edge cases
- transcripts/: Execution logs for debugging and analysis

Evaluation Types:
- VDOT calculation accuracy (P0)
- Training plan safety validation (P0)
- RAG retrieval quality (P1)
- Coaching quality rubric (P2)
"""

from tests.evals.metrics import EvalMetrics, EvalResult
from tests.evals.runner import EvalRunner

__all__ = ["EvalMetrics", "EvalResult", "EvalRunner"]
