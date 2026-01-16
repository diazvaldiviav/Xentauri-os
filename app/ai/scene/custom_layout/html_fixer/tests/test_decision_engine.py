"""
Tests for DecisionEngine (Sprint 7).

Tests the decision logic for deterministic vs LLM fixes.
"""

import pytest
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.orchestrator.decision_engine import DecisionEngine


class TestDecisionEngine:
    """Tests for DecisionEngine."""

    def _make_error(
        self,
        error_type: ErrorType = ErrorType.ZINDEX_CONFLICT,
        confidence: float = 1.0,
    ) -> ClassifiedError:
        """Helper to create a test error."""
        return ClassifiedError(
            error_type=error_type,
            selector=".test",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=confidence,
        )

    def test_should_use_llm_with_llm_errors(self):
        """Test should_use_llm returns True for LLM-requiring errors."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING),  # requires_llm = True
        ]

        assert engine.should_use_llm(errors) is True

    def test_should_use_llm_without_llm_errors(self):
        """Test should_use_llm returns False for deterministic-only errors."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.ZINDEX_CONFLICT),  # requires_llm = False
            self._make_error(ErrorType.POINTER_BLOCKED),  # requires_llm = False
        ]

        assert engine.should_use_llm(errors) is False

    def test_should_use_llm_max_attempts_reached(self):
        """Test should_use_llm returns False after max attempts."""
        engine = DecisionEngine(max_llm_attempts=3)

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING),
        ]

        # Under max attempts
        assert engine.should_use_llm(errors, previous_attempts=2) is True

        # At max attempts
        assert engine.should_use_llm(errors, previous_attempts=3) is False

    def test_should_use_llm_empty_errors(self):
        """Test should_use_llm returns False for empty errors."""
        engine = DecisionEngine()
        assert engine.should_use_llm([]) is False

    def test_should_continue_fixing_perfect_score(self):
        """Test should_continue returns False for perfect score."""
        engine = DecisionEngine()

        assert engine.should_continue_fixing(
            current_score=1.0,
            previous_score=0.8,
            remaining_errors=0,
            attempts=1,
        ) is False

    def test_should_continue_fixing_no_errors(self):
        """Test should_continue returns False when no errors remain."""
        engine = DecisionEngine()

        assert engine.should_continue_fixing(
            current_score=0.9,
            previous_score=0.8,
            remaining_errors=0,
            attempts=1,
        ) is False

    def test_should_continue_fixing_max_attempts(self):
        """Test should_continue returns False at max attempts."""
        engine = DecisionEngine(max_llm_attempts=3)

        assert engine.should_continue_fixing(
            current_score=0.7,
            previous_score=0.5,
            remaining_errors=2,
            attempts=3,
        ) is False

    def test_should_continue_fixing_insufficient_improvement(self):
        """Test should_continue returns False for insufficient improvement."""
        engine = DecisionEngine(min_improvement_threshold=0.1)

        assert engine.should_continue_fixing(
            current_score=0.55,
            previous_score=0.50,  # Only 5% improvement
            remaining_errors=2,
            attempts=1,
        ) is False

    def test_should_continue_fixing_good_improvement(self):
        """Test should_continue returns True for good improvement."""
        engine = DecisionEngine(min_improvement_threshold=0.05)

        assert engine.should_continue_fixing(
            current_score=0.7,
            previous_score=0.5,  # 20% improvement
            remaining_errors=2,
            attempts=1,
        ) is True

    def test_should_rollback_score_degraded(self):
        """Test should_rollback returns True when score degraded significantly."""
        engine = DecisionEngine(rollback_threshold=0.1)

        assert engine.should_rollback(
            current_score=0.5,
            previous_score=0.8,  # 30% degradation
        ) is True

    def test_should_rollback_minor_degradation(self):
        """Test should_rollback returns False for minor degradation."""
        engine = DecisionEngine(rollback_threshold=0.1)

        assert engine.should_rollback(
            current_score=0.75,
            previous_score=0.80,  # Only 5% degradation
        ) is False

    def test_should_rollback_improvement(self):
        """Test should_rollback returns False for improvement."""
        engine = DecisionEngine(rollback_threshold=0.1)

        assert engine.should_rollback(
            current_score=0.9,
            previous_score=0.7,  # Improvement, not degradation
        ) is False

    def test_partition_errors(self):
        """Test partitioning errors into deterministic and LLM groups."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.ZINDEX_CONFLICT),  # deterministic
            self._make_error(ErrorType.FEEDBACK_MISSING),  # LLM
            self._make_error(ErrorType.POINTER_BLOCKED),  # deterministic
            self._make_error(ErrorType.JS_MISSING_FUNCTION),  # LLM
        ]

        det, llm = engine.partition_errors(errors)

        assert len(det) == 2
        assert len(llm) == 2
        assert all(not e.error_type.requires_llm for e in det)
        assert all(e.error_type.requires_llm for e in llm)

    def test_partition_errors_all_deterministic(self):
        """Test partition with only deterministic errors."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.ZINDEX_CONFLICT),
            self._make_error(ErrorType.POINTER_BLOCKED),
        ]

        det, llm = engine.partition_errors(errors)

        assert len(det) == 2
        assert len(llm) == 0

    def test_partition_errors_all_llm(self):
        """Test partition with only LLM errors."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING),
            self._make_error(ErrorType.JS_SYNTAX_ERROR),
        ]

        det, llm = engine.partition_errors(errors)

        assert len(det) == 0
        assert len(llm) == 2

    def test_partition_errors_empty(self):
        """Test partition with empty errors."""
        engine = DecisionEngine()

        det, llm = engine.partition_errors([])

        assert det == []
        assert llm == []

    def test_select_errors_for_llm(self):
        """Test selecting high-confidence LLM errors."""
        engine = DecisionEngine(llm_confidence_threshold=0.7)

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.9),
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.5),  # Below threshold
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.8),
        ]

        selected = engine.select_errors_for_llm(errors)

        assert len(selected) == 2
        # Should be sorted by confidence
        assert selected[0].confidence == 0.9
        assert selected[1].confidence == 0.8

    def test_select_errors_for_llm_max_errors(self):
        """Test selecting respects max_errors limit."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.9),
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.8),
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.7),
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.6),
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.5),
        ]

        selected = engine.select_errors_for_llm(errors, max_errors=3)

        assert len(selected) == 3
        # Top 3 by confidence
        assert selected[0].confidence == 0.9
        assert selected[1].confidence == 0.8
        assert selected[2].confidence == 0.7

    def test_select_errors_for_llm_no_llm_errors(self):
        """Test selecting returns empty for non-LLM errors."""
        engine = DecisionEngine()

        errors = [
            self._make_error(ErrorType.ZINDEX_CONFLICT),
            self._make_error(ErrorType.POINTER_BLOCKED),
        ]

        selected = engine.select_errors_for_llm(errors)

        assert selected == []

    def test_select_errors_for_llm_below_threshold_fallback(self):
        """Test selecting uses all LLM errors if none meet threshold."""
        engine = DecisionEngine(llm_confidence_threshold=0.9)

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.5),
            self._make_error(ErrorType.FEEDBACK_MISSING, confidence=0.6),
        ]

        selected = engine.select_errors_for_llm(errors)

        # Should use all since none meet threshold
        assert len(selected) == 2

    def test_max_llm_attempts_property(self):
        """Test max_llm_attempts property."""
        engine = DecisionEngine(max_llm_attempts=5)
        assert engine.max_llm_attempts == 5

    def test_repr(self):
        """Test string representation."""
        engine = DecisionEngine(
            llm_confidence_threshold=0.8,
            min_improvement_threshold=0.1,
            max_llm_attempts=5
        )

        repr_str = repr(engine)
        assert "llm_threshold=0.8" in repr_str
        assert "improvement_threshold=0.1" in repr_str
        assert "max_llm_attempts=5" in repr_str
