"""
Unit tests for ErrorPrioritizer.

Tests error prioritization by severity.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.validators.error_prioritizer import ErrorPrioritizer
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def prioritizer():
    """ErrorPrioritizer instance."""
    return ErrorPrioritizer()


@pytest.fixture
def sample_errors():
    """Sample errors of various types."""
    return [
        ClassifiedError(
            error_type=ErrorType.FEEDBACK_MISSING,
            selector="#btn1",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=0.9,
        ),
        ClassifiedError(
            error_type=ErrorType.POINTER_BLOCKED,
            selector="#btn2",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=1.0,
        ),
        ClassifiedError(
            error_type=ErrorType.INVISIBLE_DISPLAY,
            selector="#btn3",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=0.95,
        ),
        ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector="#btn4",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=0.85,
        ),
        ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector="#btn5",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=0.9,
        ),
    ]


# ============================================================================
# PRIORITY ORDER TESTS
# ============================================================================


class TestPriorityOrder:
    """Tests for error priority ordering."""

    def test_prioritize_returns_sorted(self, prioritizer, sample_errors):
        """Prioritize should return errors sorted by priority."""
        result = prioritizer.prioritize(sample_errors)

        # First should be POINTER_BLOCKED (priority 1)
        assert result[0].error_type == ErrorType.POINTER_BLOCKED

        # Second should be ZINDEX_CONFLICT (priority 2)
        assert result[1].error_type == ErrorType.ZINDEX_CONFLICT

        # Third should be INVISIBLE_DISPLAY (priority 3)
        assert result[2].error_type == ErrorType.INVISIBLE_DISPLAY

    def test_prioritize_critical_first(self, prioritizer, sample_errors):
        """Critical errors should come first."""
        result = prioritizer.prioritize(sample_errors)

        critical_types = {ErrorType.POINTER_BLOCKED, ErrorType.ZINDEX_CONFLICT}
        critical_indices = [
            i for i, e in enumerate(result) if e.error_type in critical_types
        ]

        # Critical errors should be at beginning
        assert critical_indices == [0, 1]

    def test_prioritize_feedback_last(self, prioritizer, sample_errors):
        """Feedback errors should come last."""
        result = prioritizer.prioritize(sample_errors)

        # FEEDBACK_MISSING should be last
        assert result[-1].error_type == ErrorType.FEEDBACK_MISSING

    def test_empty_list(self, prioritizer):
        """Should handle empty list."""
        result = prioritizer.prioritize([])
        assert result == []


class TestPriorityValue:
    """Tests for get_priority method."""

    def test_get_priority_pointer_blocked(self, prioritizer):
        """POINTER_BLOCKED should have priority 1."""
        error = ClassifiedError(
            error_type=ErrorType.POINTER_BLOCKED,
            selector="#btn",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        assert prioritizer.get_priority(error) == 1

    def test_get_priority_unknown(self, prioritizer):
        """UNKNOWN should have priority 99."""
        error = ClassifiedError(
            error_type=ErrorType.UNKNOWN,
            selector="#btn",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        assert prioritizer.get_priority(error) == 99


# ============================================================================
# GROUPING TESTS
# ============================================================================


class TestGroupByPriority:
    """Tests for group_by_priority method."""

    def test_group_critical(self, prioritizer, sample_errors):
        """Should group critical errors correctly."""
        groups = prioritizer.group_by_priority(sample_errors)

        assert len(groups["critical"]) == 2
        critical_types = {e.error_type for e in groups["critical"]}
        assert ErrorType.POINTER_BLOCKED in critical_types
        assert ErrorType.ZINDEX_CONFLICT in critical_types

    def test_group_visibility(self, prioritizer, sample_errors):
        """Should group visibility errors correctly."""
        groups = prioritizer.group_by_priority(sample_errors)

        assert len(groups["visibility"]) == 1
        assert groups["visibility"][0].error_type == ErrorType.INVISIBLE_DISPLAY

    def test_group_transform(self, prioritizer, sample_errors):
        """Should group transform errors correctly."""
        groups = prioritizer.group_by_priority(sample_errors)

        assert len(groups["transform"]) == 1
        assert groups["transform"][0].error_type == ErrorType.TRANSFORM_3D_HIDDEN

    def test_group_feedback(self, prioritizer, sample_errors):
        """Should group feedback errors correctly."""
        groups = prioritizer.group_by_priority(sample_errors)

        assert len(groups["feedback"]) == 1
        assert groups["feedback"][0].error_type == ErrorType.FEEDBACK_MISSING

    def test_empty_groups(self, prioritizer):
        """Should return empty groups for no errors."""
        groups = prioritizer.group_by_priority([])

        for group in groups.values():
            assert len(group) == 0


# ============================================================================
# FILTERING TESTS
# ============================================================================


class TestFiltering:
    """Tests for filtering methods."""

    def test_filter_by_confidence(self, prioritizer, sample_errors):
        """Should filter errors by confidence."""
        result = prioritizer.filter_by_confidence(sample_errors, min_confidence=0.9)

        # Should include errors with confidence >= 0.9
        assert len(result) == 4
        for error in result:
            assert error.confidence >= 0.9

    def test_filter_excludes_low_confidence(self, prioritizer, sample_errors):
        """Should exclude low confidence errors."""
        result = prioritizer.filter_by_confidence(sample_errors, min_confidence=0.95)

        # Only errors with confidence >= 0.95
        assert len(result) == 2
        for error in result:
            assert error.confidence >= 0.95

    def test_get_critical_errors(self, prioritizer, sample_errors):
        """Should return only critical errors."""
        result = prioritizer.get_critical_errors(sample_errors)

        assert len(result) == 2
        for error in result:
            assert error.error_type in {
                ErrorType.POINTER_BLOCKED,
                ErrorType.ZINDEX_CONFLICT,
            }

    def test_has_blocking_errors_true(self, prioritizer, sample_errors):
        """Should detect blocking errors."""
        assert prioritizer.has_blocking_errors(sample_errors) is True

    def test_has_blocking_errors_false(self, prioritizer):
        """Should return False when no blocking errors."""
        errors = [
            ClassifiedError(
                error_type=ErrorType.FEEDBACK_MISSING,
                selector="#btn",
                element_tag="button",
                tailwind_info=TailwindInfo(),
            )
        ]
        assert prioritizer.has_blocking_errors(errors) is False
