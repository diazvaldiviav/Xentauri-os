"""
BestResultTracker - Tracks the best HTML result found.

Sprint 7: Ensures we always return the best version found,
even if later fix attempts fail or degrade quality.
"""

import logging

from .contracts import FixPhase


logger = logging.getLogger(__name__)


class BestResultTracker:
    """
    Tracks the best HTML result found during fixing.

    Compares by validation score and ensures we always
    return the best version, even if later attempts fail.

    Usage:
        tracker = BestResultTracker(original_html)

        # After each fix attempt
        if tracker.update(html, score, phase, errors_remaining):
            print("New best found!")

        # Get best result
        best = tracker.best_html
        score = tracker.best_score
    """

    def __init__(self, original_html: str):
        """
        Initialize the tracker.

        Args:
            original_html: The original HTML before any fixes
        """
        self._original = original_html
        self._best_html = original_html
        self._best_score = 0.0
        self._best_phase = FixPhase.INITIAL
        self._best_errors = 0
        self._updates = 0

    def update(
        self,
        html: str,
        score: float,
        phase: FixPhase,
        errors_remaining: int = 0,
    ) -> bool:
        """
        Update best result if this is better.

        Args:
            html: HTML content to consider
            score: Validation score (0.0-1.0)
            phase: Phase that produced this result
            errors_remaining: Number of errors still present

        Returns:
            True if this became the new best
        """
        self._updates += 1

        if score > self._best_score:
            logger.info(
                f"New best result: {self._best_score:.2%} -> {score:.2%} "
                f"(phase: {phase.value})"
            )

            self._best_html = html
            self._best_score = score
            self._best_phase = phase
            self._best_errors = errors_remaining
            return True

        logger.debug(
            f"Result not better: {score:.2%} <= {self._best_score:.2%}"
        )
        return False

    @property
    def best_html(self) -> str:
        """Get best HTML found."""
        return self._best_html

    @property
    def best_score(self) -> float:
        """Get best score achieved."""
        return self._best_score

    @property
    def best_phase(self) -> FixPhase:
        """Get phase that produced best result."""
        return self._best_phase

    @property
    def best_errors(self) -> int:
        """Get errors remaining in best result."""
        return self._best_errors

    @property
    def improved(self) -> bool:
        """Check if any improvement was made over original."""
        return self._best_html != self._original and self._best_score > 0

    @property
    def original(self) -> str:
        """Get original HTML."""
        return self._original

    @property
    def updates_count(self) -> int:
        """Get number of update calls made."""
        return self._updates

    def describe(self) -> str:
        """Generate human-readable summary."""
        status = "IMPROVED" if self.improved else "UNCHANGED"
        return (
            f"BestResultTracker: {status}\n"
            f"  Score: {self._best_score:.1%}\n"
            f"  Phase: {self._best_phase.value}\n"
            f"  Errors: {self._best_errors}\n"
            f"  Updates: {self._updates}"
        )

    def __repr__(self) -> str:
        return (
            f"BestResultTracker("
            f"score={self._best_score:.2%}, "
            f"phase={self._best_phase.value})"
        )
