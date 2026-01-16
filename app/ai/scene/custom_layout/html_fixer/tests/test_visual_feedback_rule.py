"""
Tests for VisualFeedbackAmplifierRule (Sprint 4).

Tests the new feedback amplification rule that:
- Handles FEEDBACK_TOO_SUBTLE errors
- Adds comprehensive visual feedback classes
- Avoids duplicate classes
"""

import pytest
from html_fixer.fixers.deterministic import VisualFeedbackAmplifierRule
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.tailwind_rules import TailwindFixes


class TestVisualFeedbackAmplifierRule:
    """Tests for VisualFeedbackAmplifierRule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = VisualFeedbackAmplifierRule()

    def test_handles_feedback_too_subtle(self):
        """Test that rule handles FEEDBACK_TOO_SUBTLE."""
        assert ErrorType.FEEDBACK_TOO_SUBTLE in self.rule.handles
        assert len(self.rule.handles) == 1

    def test_priority_is_50(self):
        """Test that priority is 50 (after critical fixes)."""
        assert self.rule.priority == 50

    def test_can_fix_feedback_errors(self):
        """Test can_fix returns True for handled errors."""
        error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
            selector=".option-btn",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        assert self.rule.can_fix(error) is True

    def test_cannot_fix_other_errors(self):
        """Test can_fix returns False for unhandled errors."""
        error = ClassifiedError(
            error_type=ErrorType.INVISIBLE_OPACITY,
            selector=".button",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        assert self.rule.can_fix(error) is False

    def test_generate_fix_adds_feedback_classes(self):
        """Test fix adds all feedback classes."""
        error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
            selector=".option-btn",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        patch = self.rule.generate_fix(error)

        assert patch.selector == ".option-btn"
        assert TailwindFixes.FEEDBACK_SCALE in patch.add_classes  # active:scale-95
        assert TailwindFixes.FEEDBACK_BRIGHTNESS in patch.add_classes  # active:brightness-75
        assert "focus:ring-4" in patch.add_classes
        assert "focus:ring-blue-500" in patch.add_classes
        assert TailwindFixes.TRANSITION_ALL in patch.add_classes  # transition-all
        assert TailwindFixes.DURATION_150 in patch.add_classes  # duration-150

    def test_generate_fix_has_reason(self):
        """Test fix includes descriptive reason."""
        error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
            selector=".btn",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        patch = self.rule.generate_fix(error)

        assert patch.reason is not None
        assert "feedback" in patch.reason.lower()

    def test_avoids_duplicate_classes(self):
        """Test fix doesn't add classes that already exist."""
        error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
            selector=".btn",
            element_tag="button",
            tailwind_info=TailwindInfo(
                all_classes={
                    "active:scale-95",  # Already has this
                    "transition-all",   # Already has this
                }
            ),
        )
        patch = self.rule.generate_fix(error)

        # Should not add duplicate classes
        assert patch.add_classes.count("active:scale-95") <= 1
        assert patch.add_classes.count("transition-all") <= 1

        # Check that duplicates were filtered out
        for cls in patch.add_classes:
            assert cls not in error.tailwind_info.all_classes

    def test_no_remove_classes(self):
        """Test fix doesn't remove any classes."""
        error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
            selector=".btn",
            element_tag="button",
            tailwind_info=TailwindInfo(
                all_classes={"bg-blue-500", "text-white", "p-4"}
            ),
        )
        patch = self.rule.generate_fix(error)

        assert patch.remove_classes == []


class TestVisualFeedbackRuleIntegration:
    """Integration tests for VisualFeedbackAmplifierRule with RuleEngine."""

    def test_registered_in_default_engine(self):
        """Test rule is registered in default engine."""
        from html_fixer.fixers.deterministic import create_default_engine

        engine = create_default_engine()
        rule_names = [r.name for r in engine.rules]

        assert "VisualFeedbackAmplifierRule" in rule_names

    def test_rule_priority_order(self):
        """Test rules are in correct priority order."""
        from html_fixer.fixers.deterministic import create_default_engine

        engine = create_default_engine()

        # Find rule positions
        positions = {r.name: i for i, r in enumerate(engine.rules)}

        # VisualFeedbackAmplifierRule should be last (priority 50)
        feedback_pos = positions.get("VisualFeedbackAmplifierRule")
        transform_pos = positions.get("Transform3DFixRule")

        assert feedback_pos is not None
        assert transform_pos is not None
        assert feedback_pos > transform_pos  # Feedback runs after transform
