"""
DecisionEngine - Decides when to use rules vs LLM.

Sprint 7: Logic for deciding when to use deterministic rules,
when to use LLM, when to stop fixing, and when to rollback.
"""

import logging
from typing import List, Tuple

from ..contracts.validation import ClassifiedError


logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Decides when to use deterministic rules vs LLM.

    Also determines when to stop fixing and when to rollback.

    Usage:
        engine = DecisionEngine()

        # Partition errors
        det_errors, llm_errors = engine.partition_errors(errors)

        # Check if LLM should be used
        if engine.should_use_llm(errors):
            # Use LLM fixer
            pass

        # Check if we should continue fixing
        if engine.should_continue_fixing(score, prev_score, errors, attempt):
            # Continue to next attempt
            pass
    """

    def __init__(
        self,
        llm_confidence_threshold: float = 0.7,
        min_improvement_threshold: float = 0.05,
        max_llm_attempts: int = 1,  # Single attempt, user feedback loop handles iterations
        rollback_threshold: float = 0.1,
    ):
        """
        Initialize the decision engine.

        Args:
            llm_confidence_threshold: Min confidence for LLM errors to be included
            min_improvement_threshold: Min score improvement to continue
            max_llm_attempts: Maximum LLM retry attempts
            rollback_threshold: Score degradation threshold for rollback
        """
        self._llm_threshold = llm_confidence_threshold
        self._improvement_threshold = min_improvement_threshold
        self._max_llm_attempts = max_llm_attempts
        self._rollback_threshold = rollback_threshold

    def should_use_llm(
        self,
        errors: List[ClassifiedError],
        previous_attempts: int = 0,
    ) -> bool:
        """
        Decide if LLM should be used for these errors.

        Returns True if:
        - Any error requires LLM (error_type.requires_llm)
        - Previous attempts haven't exhausted retries

        Args:
            errors: List of classified errors
            previous_attempts: Number of previous LLM attempts

        Returns:
            True if LLM should be used
        """
        if previous_attempts >= self._max_llm_attempts:
            logger.debug(f"Max LLM attempts ({self._max_llm_attempts}) reached")
            return False

        # Check if any error requires LLM
        llm_required = any(e.error_type.requires_llm for e in errors)

        if llm_required:
            logger.debug("LLM required for error(s)")

        return llm_required

    def should_continue_fixing(
        self,
        current_score: float,
        previous_score: float,
        remaining_errors: int,
        attempts: int,
    ) -> bool:
        """
        Decide if fixing should continue.

        Returns False if:
        - Score is 1.0 (perfect)
        - No remaining errors
        - Score stopped improving (below threshold)
        - Max attempts reached

        Args:
            current_score: Current validation score
            previous_score: Previous best score
            remaining_errors: Number of errors still present
            attempts: Current attempt number (1-based)

        Returns:
            True if fixing should continue
        """
        # Perfect score - stop
        if current_score >= 1.0:
            logger.debug("Perfect score achieved, stopping")
            return False

        # No remaining errors - stop
        if remaining_errors == 0:
            logger.debug("No remaining errors, stopping")
            return False

        # Max attempts - stop
        if attempts >= self._max_llm_attempts:
            logger.debug(f"Max attempts ({self._max_llm_attempts}) reached")
            return False

        # Check improvement
        improvement = current_score - previous_score

        if improvement < self._improvement_threshold and current_score < 1.0:
            # Not improving enough
            logger.debug(
                f"Insufficient improvement ({improvement:.2%} < {self._improvement_threshold:.2%})"
            )
            return False

        return True

    def should_rollback(
        self,
        current_score: float,
        previous_score: float,
    ) -> bool:
        """
        Decide if we should rollback to previous version.

        Returns True if current score is significantly worse.

        Args:
            current_score: Score after current fix attempt
            previous_score: Score before current fix attempt

        Returns:
            True if rollback is recommended
        """
        degradation = previous_score - current_score

        if degradation > self._rollback_threshold:
            logger.info(
                f"Score degraded by {degradation:.2%}, recommending rollback"
            )
            return True

        return False

    def select_errors_for_llm(
        self,
        errors: List[ClassifiedError],
        max_errors: int = 5,
    ) -> List[ClassifiedError]:
        """
        Select subset of errors for LLM fixing.

        Prioritizes high-confidence errors that require LLM.

        Args:
            errors: All errors to consider
            max_errors: Maximum errors to return

        Returns:
            Filtered and prioritized list of errors
        """
        # Filter to LLM-requiring errors
        llm_errors = [e for e in errors if e.error_type.requires_llm]

        if not llm_errors:
            return []

        # Filter by confidence threshold
        confident_errors = [
            e for e in llm_errors
            if e.confidence >= self._llm_threshold
        ]

        # If none meet threshold, use all LLM errors
        if not confident_errors:
            confident_errors = llm_errors

        # Sort by confidence (highest first)
        sorted_errors = sorted(
            confident_errors,
            key=lambda e: e.confidence,
            reverse=True
        )

        # Limit to max_errors
        selected = sorted_errors[:max_errors]

        logger.debug(f"Selected {len(selected)}/{len(errors)} errors for LLM")
        return selected

    def partition_errors(
        self,
        errors: List[ClassifiedError],
    ) -> Tuple[List[ClassifiedError], List[ClassifiedError]]:
        """
        Partition errors into deterministic and LLM groups.

        Args:
            errors: All classified errors

        Returns:
            Tuple of (deterministic_errors, llm_errors)
        """
        deterministic = []
        llm = []

        for error in errors:
            if error.error_type.requires_llm:
                llm.append(error)
            else:
                deterministic.append(error)

        logger.debug(
            f"Partitioned errors: {len(deterministic)} deterministic, {len(llm)} LLM"
        )

        return deterministic, llm

    @property
    def max_llm_attempts(self) -> int:
        """Get maximum LLM attempts."""
        return self._max_llm_attempts

    def __repr__(self) -> str:
        return (
            f"DecisionEngine("
            f"llm_threshold={self._llm_threshold}, "
            f"improvement_threshold={self._improvement_threshold}, "
            f"max_llm_attempts={self._max_llm_attempts})"
        )
