"""
Unit tests for FixRule base class.

Tests the abstract base class contract and concrete implementations.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.patches import TailwindPatch
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.fixers.deterministic import (
    FixRule,
    VisibilityRestoreRule,
    ZIndexFixRule,
    PointerEventsFixRule,
    PassthroughRule,
    Transform3DFixRule,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def make_error(
    error_type: ErrorType,
    selector: str = "#btn",
    element_tag: str = "button",
    z_index: int = None,
    has_pointer_none: bool = False,
    has_pointer_auto: bool = False,
    has_relative: bool = False,
    blocking_element: str = None,
    requires_llm: bool = False,
    confidence: float = 1.0,
) -> ClassifiedError:
    """Helper to create ClassifiedError for tests."""
    info = TailwindInfo(
        all_classes=set(),
        z_index=z_index,
        has_pointer_none=has_pointer_none,
        has_pointer_auto=has_pointer_auto,
        has_relative=has_relative,
    )
    return ClassifiedError(
        error_type=error_type,
        selector=selector,
        element_tag=element_tag,
        tailwind_info=info,
        blocking_element=blocking_element,
        requires_llm=requires_llm,
        confidence=confidence,
    )


# ============================================================================
# CONCRETE RULES TO TEST
# ============================================================================

ALL_RULES = [
    VisibilityRestoreRule,
    ZIndexFixRule,
    PointerEventsFixRule,
    PassthroughRule,
    Transform3DFixRule,
]


# ============================================================================
# FIXRULE CONTRACT TESTS
# ============================================================================


class TestFixRuleContract:
    """Test that all rules implement the FixRule contract properly."""

    @pytest.mark.parametrize("rule_class", ALL_RULES)
    def test_handles_returns_list_of_error_types(self, rule_class):
        """handles property should return a list of ErrorType."""
        rule = rule_class()
        handles = rule.handles

        assert isinstance(handles, list)
        assert len(handles) > 0
        for error_type in handles:
            assert isinstance(error_type, ErrorType)

    @pytest.mark.parametrize("rule_class", ALL_RULES)
    def test_priority_returns_integer(self, rule_class):
        """priority property should return an integer."""
        rule = rule_class()
        priority = rule.priority

        assert isinstance(priority, int)
        assert priority >= 0

    @pytest.mark.parametrize("rule_class", ALL_RULES)
    def test_name_returns_string(self, rule_class):
        """name property should return the class name."""
        rule = rule_class()
        name = rule.name

        assert isinstance(name, str)
        assert name == rule_class.__name__

    @pytest.mark.parametrize("rule_class", ALL_RULES)
    def test_repr_contains_info(self, rule_class):
        """__repr__ should contain useful information."""
        rule = rule_class()
        repr_str = repr(rule)

        assert rule.name in repr_str
        assert "handles" in repr_str or "priority" in repr_str


# ============================================================================
# RULE PRIORITY TESTS
# ============================================================================


class TestRulePriority:
    """Test that rules have correct priority ordering."""

    def test_visibility_has_lowest_priority(self):
        """Visibility rule should run first (lowest priority number)."""
        visibility = VisibilityRestoreRule()
        zindex = ZIndexFixRule()
        pointer = PointerEventsFixRule()

        assert visibility.priority < zindex.priority
        assert visibility.priority < pointer.priority

    def test_zindex_before_pointer(self):
        """Z-index rule should run before pointer events."""
        zindex = ZIndexFixRule()
        pointer = PointerEventsFixRule()

        assert zindex.priority < pointer.priority

    def test_passthrough_after_pointer(self):
        """Passthrough rule should run just after pointer events."""
        pointer = PointerEventsFixRule()
        passthrough = PassthroughRule()

        assert passthrough.priority > pointer.priority
        assert passthrough.priority - pointer.priority <= 5  # Close together

    def test_transform_runs_last(self):
        """Transform rule should run after pointer fixes."""
        transform = Transform3DFixRule()
        pointer = PointerEventsFixRule()

        assert transform.priority > pointer.priority


# ============================================================================
# RULE EQUALITY TESTS
# ============================================================================


class TestRuleEquality:
    """Test rule equality and hashing."""

    def test_same_class_equals(self):
        """Two instances of same class should be equal."""
        rule1 = ZIndexFixRule()
        rule2 = ZIndexFixRule()

        assert rule1 == rule2

    def test_different_class_not_equals(self):
        """Instances of different classes should not be equal."""
        zindex = ZIndexFixRule()
        visibility = VisibilityRestoreRule()

        assert zindex != visibility

    def test_hashable(self):
        """Rules should be hashable for use in sets/dicts."""
        rules = {ZIndexFixRule(), VisibilityRestoreRule()}

        assert len(rules) == 2

    def test_same_class_same_hash(self):
        """Same class instances should have same hash."""
        rule1 = ZIndexFixRule()
        rule2 = ZIndexFixRule()

        assert hash(rule1) == hash(rule2)


# ============================================================================
# CAN_FIX TESTS
# ============================================================================


class TestCanFix:
    """Test can_fix method for each rule."""

    def test_visibility_can_fix_opacity(self):
        """VisibilityRestoreRule can fix opacity errors."""
        rule = VisibilityRestoreRule()
        error = make_error(ErrorType.INVISIBLE_OPACITY)

        assert rule.can_fix(error) is True

    def test_visibility_cannot_fix_zindex(self):
        """VisibilityRestoreRule cannot fix z-index errors."""
        rule = VisibilityRestoreRule()
        error = make_error(ErrorType.ZINDEX_CONFLICT)

        assert rule.can_fix(error) is False

    def test_zindex_can_fix_conflict(self):
        """ZIndexFixRule can fix z-index conflicts."""
        rule = ZIndexFixRule()
        error = make_error(ErrorType.ZINDEX_CONFLICT)

        assert rule.can_fix(error) is True

    def test_zindex_respects_confidence(self):
        """ZIndexFixRule should not fix low-confidence errors."""
        rule = ZIndexFixRule()
        error = make_error(ErrorType.ZINDEX_CONFLICT, confidence=0.3)

        assert rule.can_fix(error) is False

    def test_pointer_can_fix_blocked(self):
        """PointerEventsFixRule can fix blocked errors."""
        rule = PointerEventsFixRule()
        error = make_error(ErrorType.POINTER_BLOCKED)

        assert rule.can_fix(error) is True

    def test_passthrough_requires_blocking_element(self):
        """PassthroughRule requires blocking_element."""
        rule = PassthroughRule()
        error_without = make_error(ErrorType.POINTER_BLOCKED)
        error_with = make_error(ErrorType.POINTER_BLOCKED, blocking_element="#overlay")

        assert rule.can_fix(error_without) is False
        assert rule.can_fix(error_with) is True

    def test_transform_can_fix_3d_hidden(self):
        """Transform3DFixRule can fix 3D hidden errors."""
        rule = Transform3DFixRule()
        error = make_error(ErrorType.TRANSFORM_3D_HIDDEN)

        assert rule.can_fix(error) is True
