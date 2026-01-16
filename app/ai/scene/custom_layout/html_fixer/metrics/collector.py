"""
Metrics Collector - Collects metrics from orchestrator runs.

Sprint 8: Provides a simple interface for recording and retrieving
metrics from orchestration runs.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from ..orchestrator.contracts import OrchestratorResult


@dataclass
class RunMetrics:
    """Metrics from a single orchestrator run."""

    timestamp: datetime
    """When this run occurred."""

    fixture_name: str
    """Name of the fixture/file being processed."""

    initial_errors: int
    """Number of errors in initial classification."""

    final_errors: int
    """Number of errors remaining after fixes."""

    fix_rate: float
    """Percentage of errors fixed (0.0-1.0)."""

    deterministic_fixes: int
    """Number of fixes made by deterministic rules."""

    llm_fixes: int
    """Number of fixes requiring LLM."""

    duration_ms: float
    """Total duration of the fix operation."""

    score: float
    """Final validation score (0.0-1.0)."""

    passed: bool
    """Whether validation passed (score >= 0.9)."""

    llm_tokens: int = 0
    """Total LLM tokens used."""

    rollbacks: int = 0
    """Number of rollbacks performed."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RunMetrics":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class MetricsCollector:
    """
    Collects and stores metrics across orchestrator runs.

    Supports both in-memory and persistent storage via JSONL files.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the collector.

        Args:
            storage_path: Optional path to JSONL file for persistence.
                         If None, metrics are only stored in memory.
        """
        self._storage_path = Path(storage_path) if storage_path else None
        self._runs: List[RunMetrics] = []

        # Load existing metrics if storage file exists
        if self._storage_path and self._storage_path.exists():
            self._load_history()

    @property
    def runs(self) -> List[RunMetrics]:
        """Get all recorded run metrics."""
        return self._runs.copy()

    def record(self, result: "OrchestratorResult", fixture_name: str) -> RunMetrics:
        """
        Record metrics from an orchestrator result.

        Args:
            result: The OrchestratorResult from a fix operation.
            fixture_name: Name/identifier for this fixture.

        Returns:
            The recorded RunMetrics instance.
        """
        metrics = result.metrics

        # Calculate deterministic vs LLM fixes
        # Deterministic fixes = total patches - LLM-induced patches
        deterministic_fixes = max(0, metrics.patches_applied - metrics.llm_calls_made)
        llm_fixes = metrics.llm_calls_made

        run_metrics = RunMetrics(
            timestamp=datetime.now(),
            fixture_name=fixture_name,
            initial_errors=metrics.errors_initial,
            final_errors=result.errors_remaining,
            fix_rate=result.fix_rate,
            deterministic_fixes=deterministic_fixes,
            llm_fixes=llm_fixes,
            duration_ms=metrics.total_duration_ms,
            score=result.final_score,
            passed=result.validation_passed,
            llm_tokens=metrics.llm_tokens_used,
            rollbacks=metrics.rollbacks_performed,
        )

        self._runs.append(run_metrics)

        if self._storage_path:
            self._persist(run_metrics)

        return run_metrics

    def record_manual(
        self,
        fixture_name: str,
        initial_errors: int,
        final_errors: int,
        deterministic_fixes: int,
        llm_fixes: int,
        duration_ms: float,
        score: float,
        passed: bool,
        llm_tokens: int = 0,
        rollbacks: int = 0,
    ) -> RunMetrics:
        """
        Manually record metrics (useful for testing).

        Args:
            fixture_name: Name/identifier for this fixture.
            initial_errors: Number of initial errors.
            final_errors: Number of remaining errors.
            deterministic_fixes: Number of deterministic fixes applied.
            llm_fixes: Number of LLM fixes applied.
            duration_ms: Total duration.
            score: Final validation score.
            passed: Whether validation passed.
            llm_tokens: LLM tokens used.
            rollbacks: Number of rollbacks.

        Returns:
            The recorded RunMetrics instance.
        """
        total_fixes = deterministic_fixes + llm_fixes
        fix_rate = (initial_errors - final_errors) / initial_errors if initial_errors > 0 else 1.0

        run_metrics = RunMetrics(
            timestamp=datetime.now(),
            fixture_name=fixture_name,
            initial_errors=initial_errors,
            final_errors=final_errors,
            fix_rate=fix_rate,
            deterministic_fixes=deterministic_fixes,
            llm_fixes=llm_fixes,
            duration_ms=duration_ms,
            score=score,
            passed=passed,
            llm_tokens=llm_tokens,
            rollbacks=rollbacks,
        )

        self._runs.append(run_metrics)

        if self._storage_path:
            self._persist(run_metrics)

        return run_metrics

    def _persist(self, metrics: RunMetrics) -> None:
        """Append metrics to storage file."""
        if not self._storage_path:
            return

        # Ensure parent directory exists
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self._storage_path, "a") as f:
            f.write(json.dumps(metrics.to_dict()) + "\n")

    def _load_history(self) -> None:
        """Load historical metrics from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return

        self._runs = []
        with open(self._storage_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        self._runs.append(RunMetrics.from_dict(data))
                    except (json.JSONDecodeError, KeyError, TypeError):
                        # Skip malformed entries
                        continue

    def clear(self) -> None:
        """Clear all recorded metrics."""
        self._runs = []
        if self._storage_path and self._storage_path.exists():
            self._storage_path.unlink()

    def get_by_fixture(self, fixture_name: str) -> List[RunMetrics]:
        """Get all runs for a specific fixture."""
        return [r for r in self._runs if r.fixture_name == fixture_name]

    def get_recent(self, count: int = 10) -> List[RunMetrics]:
        """Get the most recent runs."""
        return sorted(self._runs, key=lambda r: r.timestamp, reverse=True)[:count]

    def get_failed(self) -> List[RunMetrics]:
        """Get all failed runs."""
        return [r for r in self._runs if not r.passed]
