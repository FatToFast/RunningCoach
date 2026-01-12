"""Transcript logging for evaluation debugging and analysis.

Captures complete execution traces for debugging failed evaluations
and analyzing AI coach behavior.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvalTranscript:
    """Complete transcript of an evaluation trial.

    Captures all inputs, outputs, and intermediate steps for debugging.
    """

    # Identification
    trial_id: str
    task_id: str
    timestamp: datetime

    # Input
    task_input: dict[str, Any]

    # Execution
    execution_result: dict[str, Any]

    # RAG context (if applicable)
    rag_queries: list[str] = field(default_factory=list)
    rag_results: list[dict[str, Any]] = field(default_factory=list)

    # LLM calls (if applicable)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)

    # Grading
    grader_results: dict[str, Any] = field(default_factory=dict)
    final_score: float = 0.0
    passed: bool = False

    # Metadata
    duration_ms: int = 0
    token_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalTranscript":
        """Create from dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def add_rag_query(self, query: str, results: list[dict]) -> None:
        """Record a RAG query and its results."""
        self.rag_queries.append(query)
        self.rag_results.append({
            "query": query,
            "results": results,
            "result_count": len(results),
        })

    def add_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
    ) -> None:
        """Record an LLM API call."""
        self.llm_calls.append({
            "model": model,
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
            "response_preview": response[:500] + "..." if len(response) > 500 else response,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
        })
        self.token_count += tokens_in + tokens_out

    def summary(self) -> dict[str, Any]:
        """Generate brief summary for logging."""
        return {
            "trial_id": self.trial_id,
            "task_id": self.task_id,
            "passed": self.passed,
            "score": round(self.final_score, 3),
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "rag_queries": len(self.rag_queries),
            "llm_calls": len(self.llm_calls),
            "error": self.error,
        }


class TranscriptLogger:
    """Logger for saving and managing evaluation transcripts."""

    def __init__(self, base_dir: Path):
        """Initialize transcript logger.

        Args:
            base_dir: Base directory for storing transcripts
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def log(self, transcript: EvalTranscript) -> Path:
        """Save transcript to file.

        Args:
            transcript: Transcript to save

        Returns:
            Path to saved transcript file
        """
        # Create directory structure: base_dir/task_id/
        task_dir = self.base_dir / transcript.task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # Save transcript
        file_path = task_dir / f"{transcript.trial_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(transcript.to_json())

        logger.debug(f"Saved transcript to {file_path}")
        return file_path

    def load(self, task_id: str, trial_id: str) -> EvalTranscript | None:
        """Load transcript from file.

        Args:
            task_id: Task identifier
            trial_id: Trial identifier

        Returns:
            Loaded transcript or None if not found
        """
        file_path = self.base_dir / task_id / f"{trial_id}.json"

        if not file_path.exists():
            return None

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        return EvalTranscript.from_dict(data)

    def load_all_for_task(self, task_id: str) -> list[EvalTranscript]:
        """Load all transcripts for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of transcripts
        """
        task_dir = self.base_dir / task_id

        if not task_dir.exists():
            return []

        transcripts = []
        for file_path in task_dir.glob("*.json"):
            if file_path.name == "result.json":
                continue  # Skip result summary files
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                transcripts.append(EvalTranscript.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to load transcript {file_path}: {e}")

        return sorted(transcripts, key=lambda t: t.timestamp)

    def get_failed_transcripts(self, eval_id: str | None = None) -> list[EvalTranscript]:
        """Get all failed trial transcripts.

        Args:
            eval_id: Optional eval ID to filter by

        Returns:
            List of failed transcripts
        """
        failed = []

        search_dir = self.base_dir / eval_id if eval_id else self.base_dir

        for file_path in search_dir.rglob("*.json"):
            if file_path.name == "result.json":
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                if not data.get("passed", True):
                    failed.append(EvalTranscript.from_dict(data))
            except Exception:
                pass

        return failed

    def analyze_failures(self, transcripts: list[EvalTranscript]) -> dict[str, Any]:
        """Analyze patterns in failed transcripts.

        Args:
            transcripts: List of failed transcripts

        Returns:
            Analysis results
        """
        if not transcripts:
            return {"total_failures": 0}

        # Group by task
        by_task: dict[str, list[EvalTranscript]] = {}
        for t in transcripts:
            if t.task_id not in by_task:
                by_task[t.task_id] = []
            by_task[t.task_id].append(t)

        # Analyze error patterns
        error_patterns: dict[str, int] = {}
        for t in transcripts:
            if t.error:
                error_type = t.error.split(":")[0]
                error_patterns[error_type] = error_patterns.get(error_type, 0) + 1

        # Analyze grader failures
        grader_failures: dict[str, int] = {}
        for t in transcripts:
            for grader_name, result in t.grader_results.items():
                if isinstance(result, dict) and not result.get("passed", True):
                    grader_failures[grader_name] = grader_failures.get(grader_name, 0) + 1

        return {
            "total_failures": len(transcripts),
            "unique_tasks_failed": len(by_task),
            "tasks_by_failure_count": {
                task_id: len(trials) for task_id, trials in sorted(
                    by_task.items(), key=lambda x: -len(x[1])
                )
            },
            "error_patterns": error_patterns,
            "grader_failures": grader_failures,
            "avg_score": sum(t.final_score for t in transcripts) / len(transcripts),
            "avg_duration_ms": sum(t.duration_ms for t in transcripts) / len(transcripts),
        }

    def cleanup_old_transcripts(self, days_to_keep: int = 30) -> int:
        """Remove transcripts older than specified days.

        Args:
            days_to_keep: Number of days to keep transcripts

        Returns:
            Number of files removed
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_to_keep)
        removed_count = 0

        for file_path in self.base_dir.rglob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                timestamp = data.get("timestamp")
                if timestamp:
                    file_time = datetime.fromisoformat(timestamp)
                    if file_time < cutoff:
                        file_path.unlink()
                        removed_count += 1
            except Exception:
                pass

        logger.info(f"Removed {removed_count} old transcript files")
        return removed_count


def create_transcript_from_coach_interaction(
    task_id: str,
    user_message: str,
    user_context: dict[str, Any],
    ai_response: str,
    rag_context: list[dict] | None = None,
    llm_metadata: dict | None = None,
) -> EvalTranscript:
    """Create transcript from AI coach interaction.

    Helper function to create transcripts from real coach interactions.

    Args:
        task_id: Task/conversation identifier
        user_message: User's message
        user_context: User context (profile, fitness data, etc.)
        ai_response: AI coach response
        rag_context: RAG retrieval results
        llm_metadata: LLM call metadata

    Returns:
        EvalTranscript ready for logging
    """
    import uuid

    transcript = EvalTranscript(
        trial_id=f"{task_id}_{uuid.uuid4().hex[:8]}",
        task_id=task_id,
        timestamp=datetime.now(),
        task_input={
            "user_message": user_message,
            "user_context": user_context,
        },
        execution_result={
            "response": ai_response,
        },
    )

    if rag_context:
        transcript.add_rag_query(
            query=user_message,
            results=rag_context,
        )

    if llm_metadata:
        transcript.add_llm_call(
            model=llm_metadata.get("model", "unknown"),
            prompt=llm_metadata.get("prompt", ""),
            response=ai_response,
            tokens_in=llm_metadata.get("tokens_in", 0),
            tokens_out=llm_metadata.get("tokens_out", 0),
            latency_ms=llm_metadata.get("latency_ms", 0),
        )

    return transcript
