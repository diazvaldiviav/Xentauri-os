"""
Orchestrator Contracts - Data structures for orchestration pipeline.

Sprint 7: Defines FixPhase, HistoryEntry, OrchestratorMetrics, and OrchestratorResult.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class FixPhase(Enum):
    """
    Phases in the fix pipeline.

    Represents the different stages an HTML document goes through
    during the repair process.
    """

    INITIAL = "initial"
    """Starting state with original HTML."""

    CLASSIFY = "classify"
    """Error classification completed."""

    DETERMINISTIC = "deterministic"
    """Deterministic fixes applied via RuleEngine."""

    VALIDATE_DETERMINISTIC = "validate_deterministic"
    """Validation after deterministic fixes."""

    LLM_FIX = "llm_fix"
    """LLM-based fixes applied."""

    VALIDATE_LLM = "validate_llm"
    """Validation after LLM fixes."""

    COMPLETE = "complete"
    """Pipeline completed."""


@dataclass
class HistoryEntry:
    """
    Single entry in the fix history.

    Represents a snapshot of the HTML at a specific point
    in the repair process, along with its validation score
    and metadata.
    """

    html: str
    """HTML content at this point."""

    phase: FixPhase
    """Phase that produced this version."""

    score: Optional[float] = None
    """Validation score (0.0-1.0), None if not validated."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When this entry was created."""

    patches_applied: List[Any] = field(default_factory=list)
    """Patches applied to reach this state."""

    errors_before: int = 0
    """Number of errors before this phase."""

    errors_after: Optional[int] = None
    """Number of errors after this phase (None if not re-classified)."""

    validation_passed: Optional[bool] = None
    """Whether validation passed at this point."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata (e.g., attempt number for LLM retries)."""

    def describe(self) -> str:
        """Generate human-readable description."""
        if self.score is not None:
            status = f"score={self.score:.2%}"
        else:
            status = "unvalidated"

        errors = self.errors_after if self.errors_after is not None else "?"
        return f"[{self.phase.value}] {status}, errors={errors}"


@dataclass
class OrchestratorMetrics:
    """
    Metrics from an orchestration run.

    Tracks timing, LLM usage, and fix statistics for
    monitoring and optimization.
    """

    # Timing
    total_duration_ms: float = 0.0
    """Total time for the entire pipeline."""

    classification_time_ms: float = 0.0
    """Time spent classifying errors."""

    deterministic_time_ms: float = 0.0
    """Time spent on deterministic fixes."""

    llm_time_ms: float = 0.0
    """Time spent on LLM fixes."""

    validation_time_ms: float = 0.0
    """Time spent on validation (cumulative)."""

    # LLM usage
    llm_calls_made: int = 0
    """Number of LLM API calls."""

    llm_tokens_used: int = 0
    """Total tokens consumed by LLM calls."""

    # Fix statistics
    patches_applied: int = 0
    """Total patches applied (deterministic + LLM)."""

    rollbacks_performed: int = 0
    """Number of rollbacks due to score degradation."""

    # Error tracking
    errors_initial: int = 0
    """Errors found in initial classification."""

    errors_final: int = 0
    """Errors remaining after all fixes."""

    def describe(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Duration: {self.total_duration_ms:.0f}ms",
            f"  - Classification: {self.classification_time_ms:.0f}ms",
            f"  - Deterministic: {self.deterministic_time_ms:.0f}ms",
            f"  - LLM: {self.llm_time_ms:.0f}ms",
            f"  - Validation: {self.validation_time_ms:.0f}ms",
            f"Patches: {self.patches_applied}",
            f"Errors: {self.errors_initial} -> {self.errors_final}",
        ]

        if self.llm_calls_made > 0:
            lines.append(f"LLM: {self.llm_calls_made} calls, {self.llm_tokens_used} tokens")

        if self.rollbacks_performed > 0:
            lines.append(f"Rollbacks: {self.rollbacks_performed}")

        return "\n".join(lines)


@dataclass
class OrchestratorResult:
    """
    Result of the orchestration pipeline.

    Contains the best fixed HTML found, along with comprehensive
    metrics and history for debugging and analysis.
    """

    success: bool
    """True if fixes improved the HTML."""

    original_html: str
    """HTML before any fixes."""

    fixed_html: str
    """Best HTML found (may be original if no improvement)."""

    final_score: float
    """Validation score of fixed HTML (0.0-1.0)."""

    phases_completed: List[FixPhase] = field(default_factory=list)
    """Phases that completed successfully."""

    errors_fixed: int = 0
    """Number of errors addressed."""

    errors_remaining: int = 0
    """Number of errors still present."""

    validation_passed: bool = False
    """Whether final validation passed (score >= 0.9)."""

    metrics: OrchestratorMetrics = field(default_factory=OrchestratorMetrics)
    """Performance and usage metrics."""

    error_message: Optional[str] = None
    """Error message if orchestration failed."""

    history: List[HistoryEntry] = field(default_factory=list)
    """Full history of fix attempts."""

    def describe(self) -> str:
        """Generate human-readable summary."""
        if self.success:
            status = "SUCCESS"
        elif self.final_score > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"

        lines = [
            f"OrchestratorResult: {status}",
            f"  Score: {self.final_score:.1%}",
            f"  Phases: {' -> '.join(p.value for p in self.phases_completed)}",
            f"  Errors: {self.metrics.errors_initial} -> {self.errors_remaining}",
            f"  Patches: {self.metrics.patches_applied}",
            f"  Duration: {self.metrics.total_duration_ms:.0f}ms",
        ]

        if self.metrics.llm_calls_made > 0:
            lines.append(
                f"  LLM calls: {self.metrics.llm_calls_made} "
                f"({self.metrics.llm_tokens_used} tokens)"
            )

        if self.error_message:
            lines.append(f"  Error: {self.error_message}")

        return "\n".join(lines)

    @property
    def improved(self) -> bool:
        """Check if HTML was improved from original."""
        return self.fixed_html != self.original_html and self.final_score > 0

    @property
    def fix_rate(self) -> float:
        """Calculate percentage of errors fixed."""
        total = self.errors_fixed + self.errors_remaining
        if total == 0:
            return 1.0
        return self.errors_fixed / total
