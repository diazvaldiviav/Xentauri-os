"""
HistoryManager - Manages fix history for rollback support.

Sprint 7: Tracks all intermediate HTML versions with scores
to enable rollback to any previous state.
"""

import logging
from typing import List, Optional

from .contracts import FixPhase, HistoryEntry


logger = logging.getLogger(__name__)


class HistoryManager:
    """
    Manages fix history for rollback support.

    Tracks all intermediate HTML versions with scores
    to enable rollback to any previous state.

    Usage:
        history = HistoryManager()
        history.push(html, FixPhase.INITIAL)
        history.push(fixed_html, FixPhase.DETERMINISTIC)
        history.update_score(0.85)

        best = history.get_best()
        previous = history.rollback(steps=1)
    """

    def __init__(self, max_entries: int = 20):
        """
        Initialize the history manager.

        Args:
            max_entries: Maximum entries to keep (oldest removed when exceeded)
        """
        self._history: List[HistoryEntry] = []
        self._max_entries = max_entries

    def push(
        self,
        html: str,
        phase: FixPhase,
        score: Optional[float] = None,
        patches_applied: Optional[List] = None,
        errors_count: int = 0,
        **metadata
    ) -> HistoryEntry:
        """
        Add entry to history.

        Args:
            html: HTML content at this point
            phase: Phase that produced this version
            score: Validation score (optional)
            patches_applied: List of patches applied
            errors_count: Number of errors at this point
            **metadata: Additional metadata

        Returns:
            The created HistoryEntry
        """
        entry = HistoryEntry(
            html=html,
            phase=phase,
            score=score,
            patches_applied=patches_applied or [],
            errors_after=errors_count,
            metadata=metadata,
        )

        self._history.append(entry)

        # Trim if exceeds max
        while len(self._history) > self._max_entries:
            self._history.pop(0)
            logger.debug(f"History trimmed, now {len(self._history)} entries")

        logger.debug(f"History pushed: {entry.describe()}")
        return entry

    def update_score(
        self,
        score: float,
        validation_passed: bool = False
    ) -> None:
        """
        Update score of the most recent entry.

        Args:
            score: Validation score (0.0-1.0)
            validation_passed: Whether validation passed
        """
        if not self._history:
            logger.warning("Cannot update score: history is empty")
            return

        self._history[-1].score = score
        self._history[-1].validation_passed = validation_passed
        logger.debug(f"Score updated: {score:.2%}, passed={validation_passed}")

    def get_best(self) -> Optional[HistoryEntry]:
        """
        Get entry with highest score.

        Returns:
            HistoryEntry with best score, or None if history is empty
        """
        if not self._history:
            return None

        # Filter to scored entries
        scored = [h for h in self._history if h.score is not None]

        if not scored:
            # Return original if nothing scored
            return self._history[0] if self._history else None

        return max(scored, key=lambda h: h.score)

    def get_by_phase(self, phase: FixPhase) -> Optional[HistoryEntry]:
        """
        Get most recent entry for a specific phase.

        Args:
            phase: The phase to find

        Returns:
            Most recent entry for that phase, or None
        """
        for entry in reversed(self._history):
            if entry.phase == phase:
                return entry
        return None

    def rollback(self, steps: int = 1) -> Optional[HistoryEntry]:
        """
        Get entry N steps back from current.

        Args:
            steps: Number of steps to go back

        Returns:
            HistoryEntry at that position, or None if out of range
        """
        if not self._history:
            return None

        index = len(self._history) - 1 - steps

        if index < 0:
            logger.warning(f"Cannot rollback {steps} steps, only {len(self._history)} entries")
            return self._history[0] if self._history else None

        return self._history[index]

    def rollback_to_phase(self, phase: FixPhase) -> Optional[HistoryEntry]:
        """
        Rollback to the most recent entry of a specific phase.

        Args:
            phase: The phase to rollback to

        Returns:
            Entry for that phase, or None if not found
        """
        entry = self.get_by_phase(phase)

        if entry:
            logger.info(f"Rolling back to phase: {phase.value}")

        return entry

    def get_score_delta(
        self,
        from_phase: FixPhase,
        to_phase: FixPhase
    ) -> Optional[float]:
        """
        Calculate score improvement between two phases.

        Args:
            from_phase: Starting phase
            to_phase: Ending phase

        Returns:
            Score difference (positive = improvement), or None if not available
        """
        from_entry = self.get_by_phase(from_phase)
        to_entry = self.get_by_phase(to_phase)

        if not from_entry or not to_entry:
            return None

        if from_entry.score is None or to_entry.score is None:
            return None

        return to_entry.score - from_entry.score

    def get_all(self) -> List[HistoryEntry]:
        """
        Get full history.

        Returns:
            List of all history entries (copy)
        """
        return self._history.copy()

    @property
    def latest(self) -> Optional[HistoryEntry]:
        """Get most recent entry."""
        return self._history[-1] if self._history else None

    @property
    def original(self) -> Optional[HistoryEntry]:
        """Get original HTML entry (first in history)."""
        return self._history[0] if self._history else None

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
        logger.debug("History cleared")

    def describe(self) -> str:
        """Generate human-readable summary of history."""
        if not self._history:
            return "History: empty"

        lines = [f"History ({len(self._history)} entries):"]
        for i, entry in enumerate(self._history):
            lines.append(f"  {i + 1}. {entry.describe()}")

        return "\n".join(lines)

    def __len__(self) -> int:
        """Get number of entries in history."""
        return len(self._history)

    def __repr__(self) -> str:
        return f"HistoryManager({len(self._history)} entries)"
