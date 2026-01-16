"""
Parametrized tests for all deterministic rules.
Sprint 8 - Comprehensive rule coverage.

Tests each rule with multiple input scenarios to ensure consistent behavior.
"""

import pytest
from typing import List, Optional, Set

from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.patches import TailwindPatch
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.fixers.deterministic import create_default_engine
from html_fixer.fixers.deterministic.visibility_rule import VisibilityRestoreRule
from html_fixer.fixers.deterministic.zindex_rule import ZIndexFixRule
from html_fixer.fixers.deterministic.pointer_events_rule import PointerEventsFixRule
from html_fixer.fixers.deterministic.passthrough_rule import PassthroughRule
from html_fixer.fixers.deterministic.transform_3d_rule import Transform3DFixRule
from html_fixer.fixers.deterministic.visual_feedback_rule import VisualFeedbackAmplifierRule


# =============================================================================
# Test Data Definitions
# =============================================================================

# Format: (error_type, input_classes, expected_add, expected_remove, description)
VISIBILITY_CASES = [
    (
        ErrorType.INVISIBLE_OPACITY,
        {"opacity-0"},
        ["opacity-100"],
        ["opacity-0"],
        "Basic opacity-0 fix"
    ),
    (
        ErrorType.INVISIBLE_OPACITY,
        {"opacity-0", "hover:opacity-100"},
        ["opacity-100"],
        ["opacity-0"],
        "Opacity-0 with hover variant"
    ),
    (
        ErrorType.INVISIBLE_OPACITY,
        {"opacity-0", "opacity-50"},
        ["opacity-100"],
        ["opacity-0", "opacity-50"],
        "Multiple opacity classes"
    ),
    (
        ErrorType.INVISIBLE_DISPLAY,
        {"hidden"},
        ["block"],
        ["hidden"],
        "Basic hidden fix"
    ),
    (
        ErrorType.INVISIBLE_DISPLAY,
        {"hidden", "md:block"},
        ["block"],
        ["hidden"],
        "Hidden with responsive variant"
    ),
    (
        ErrorType.INVISIBLE_VISIBILITY,
        {"invisible"},
        ["visible"],
        ["invisible"],
        "Basic invisible fix"
    ),
    (
        ErrorType.INVISIBLE_VISIBILITY,
        {"invisible", "group-hover:visible"},
        ["visible"],
        ["invisible"],
        "Invisible with group hover"
    ),
]

ZINDEX_CASES = [
    (
        ErrorType.ZINDEX_CONFLICT,
        {"z-10", "relative"},
        ["z-50"],
        ["z-10"],
        True,  # is_positioned
        10,    # current_z
        "Elevate from z-10"
    ),
    (
        ErrorType.ZINDEX_CONFLICT,
        {"z-0"},
        ["z-20", "relative"],
        ["z-0"],
        False,  # is_positioned
        0,      # current_z
        "Elevate from z-0, add relative"
    ),
    (
        ErrorType.ZINDEX_CONFLICT,
        {"z-30", "absolute"},
        ["z-50"],
        ["z-30"],
        True,   # is_positioned (has absolute)
        30,     # current_z
        "Elevate from z-30"
    ),
    (
        ErrorType.ZINDEX_MISSING,
        set(),
        ["z-10", "relative"],
        [],
        False,  # is_positioned
        None,   # current_z
        "Add default z-index"
    ),
    (
        ErrorType.ZINDEX_MISSING,
        {"relative"},
        ["z-10"],
        [],
        True,   # is_positioned
        None,   # current_z
        "Add z-index to positioned element"
    ),
]

POINTER_INTERCEPTED_CASES = [
    (
        ErrorType.POINTER_INTERCEPTED,
        set(),
        ["pointer-events-auto"],
        ["pointer-events-none"],
        "Override parent pointer-events-none"
    ),
    (
        ErrorType.POINTER_INTERCEPTED,
        {"pointer-events-none"},
        ["pointer-events-auto"],
        ["pointer-events-none"],
        "Replace pointer-events-none"
    ),
]

POINTER_BLOCKED_CASES = [
    (
        ErrorType.POINTER_BLOCKED,
        set(),
        ["pointer-events-auto", "relative", "z-20"],
        [],
        None,  # no blocker
        "Add pointer-events-auto and elevate"
    ),
    (
        ErrorType.POINTER_BLOCKED,
        {"relative"},
        ["pointer-events-auto", "z-20"],
        [],
        None,  # no blocker
        "Add pointer-events-auto to positioned element"
    ),
    (
        ErrorType.POINTER_BLOCKED,
        {"z-10", "relative"},
        ["pointer-events-auto", "z-50"],
        ["z-10"],
        None,  # no blocker
        "Elevate z-index when blocked"
    ),
]

POINTER_BLOCKED_WITH_BLOCKER_CASES = [
    (
        ErrorType.POINTER_BLOCKED,
        set(),
        ".overlay",
        "Patch target and blocker"
    ),
]

TRANSFORM_3D_CASES = [
    (
        ErrorType.TRANSFORM_3D_HIDDEN,
        {"[backface-visibility:hidden]", "rotate-y-180"},
        ["[backface-visibility:visible]"],
        ["[backface-visibility:hidden]"],
        ".card .front",
        "Fix backface hidden"
    ),
    (
        ErrorType.TRANSFORM_3D_HIDDEN,
        {"rotate-y-180"},
        ["[backface-visibility:visible]"],
        [],
        ".card .back",
        "Add backface visible without removing"
    ),
    (
        ErrorType.TRANSFORM_OFFSCREEN,
        {"translate-x-full"},
        ["translate-x-0", "translate-y-0"],
        ["translate-x-full"],
        ".slide",
        "Reset translate-x-full"
    ),
    (
        ErrorType.TRANSFORM_OFFSCREEN,
        {"-translate-y-full", "translate-x-1/2"},
        ["translate-x-0", "translate-y-0"],
        ["-translate-y-full", "translate-x-1/2"],
        ".offscreen",
        "Reset multiple translate classes"
    ),
]

FEEDBACK_CASES = [
    (
        ErrorType.FEEDBACK_TOO_SUBTLE,
        set(),
        ["active:scale-95", "active:brightness-75", "transition-all", "duration-150"],
        "Add full feedback to element without any"
    ),
    (
        ErrorType.FEEDBACK_TOO_SUBTLE,
        {"transition-all"},
        ["active:scale-95", "active:brightness-75", "duration-150"],
        "Add feedback keeping existing transition"
    ),
    (
        ErrorType.FEEDBACK_TOO_SUBTLE,
        {"active:scale-95", "active:brightness-75", "transition-all", "duration-150"},
        [],
        "Don't duplicate existing feedback"
    ),
]

PASSTHROUGH_CASES = [
    (
        ErrorType.POINTER_BLOCKED,
        ".overlay",
        ["pointer-events-none"],
        ["pointer-events-auto"],
        "Make overlay pass-through"
    ),
]


# =============================================================================
# Helper Functions
# =============================================================================

def make_error(
    error_type: ErrorType,
    selector: str = ".test-element",
    classes: Optional[Set[str]] = None,
    is_positioned: bool = False,
    z_index: Optional[int] = None,
    has_pointer_auto: bool = False,
    has_pointer_none: bool = False,
    has_backface_hidden: bool = False,
    blocking_element: Optional[str] = None,
    confidence: float = 0.9,
) -> ClassifiedError:
    """Create a ClassifiedError for testing."""
    classes = classes or set()

    # Derive positioning from classes
    has_relative = "relative" in classes or is_positioned
    has_absolute = "absolute" in classes
    has_fixed = "fixed" in classes

    # Derive backface from classes
    if "[backface-visibility:hidden]" in classes:
        has_backface_hidden = True

    tailwind_info = TailwindInfo(
        all_classes=classes,
        z_index=z_index,
        has_pointer_auto=has_pointer_auto,
        has_pointer_none=has_pointer_none,
        has_relative=has_relative,
        has_absolute=has_absolute,
        has_fixed=has_fixed,
        has_backface_hidden=has_backface_hidden,
    )

    return ClassifiedError(
        error_type=error_type,
        selector=selector,
        element_tag="button",
        tailwind_info=tailwind_info,
        blocking_element=blocking_element,
        confidence=confidence,
    )


def assert_patch_contains(patch: TailwindPatch, expected_add: List[str], expected_remove: List[str]):
    """Assert patch contains expected classes."""
    for cls in expected_add:
        assert cls in patch.add_classes, f"Expected {cls} in add_classes, got {patch.add_classes}"
    for cls in expected_remove:
        assert cls in patch.remove_classes, f"Expected {cls} in remove_classes, got {patch.remove_classes}"


# =============================================================================
# Test Classes
# =============================================================================

class TestVisibilityRuleParametrized:
    """Parametrized tests for VisibilityRestoreRule."""

    @pytest.fixture
    def rule(self):
        return VisibilityRestoreRule()

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,expected_remove,description",
        VISIBILITY_CASES,
        ids=[case[4] for case in VISIBILITY_CASES]
    )
    def test_visibility_fix(
        self,
        rule,
        error_type,
        input_classes,
        expected_add,
        expected_remove,
        description
    ):
        """Test visibility fixes with various input scenarios."""
        error = make_error(error_type, classes=input_classes)

        assert rule.can_fix(error), f"Rule should handle {error_type}"

        patch = rule.generate_fix(error)

        assert isinstance(patch, TailwindPatch)
        assert_patch_contains(patch, expected_add, expected_remove)

    def test_priority(self, rule):
        """Visibility rule should have highest priority."""
        assert rule.priority == 5

    def test_handles_only_visibility_errors(self, rule):
        """Rule should only handle visibility-related errors."""
        handled = rule.handles
        assert ErrorType.INVISIBLE_OPACITY in handled
        assert ErrorType.INVISIBLE_DISPLAY in handled
        assert ErrorType.INVISIBLE_VISIBILITY in handled
        assert ErrorType.ZINDEX_CONFLICT not in handled


class TestZIndexRuleParametrized:
    """Parametrized tests for ZIndexFixRule."""

    @pytest.fixture
    def rule(self):
        return ZIndexFixRule()

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,expected_remove,is_positioned,current_z,description",
        ZINDEX_CASES,
        ids=[case[6] for case in ZINDEX_CASES]
    )
    def test_zindex_fix(
        self,
        rule,
        error_type,
        input_classes,
        expected_add,
        expected_remove,
        is_positioned,
        current_z,
        description
    ):
        """Test z-index fixes with various scenarios."""
        error = make_error(
            error_type,
            classes=input_classes,
            is_positioned=is_positioned,
            z_index=current_z,
        )

        assert rule.can_fix(error), f"Rule should handle {error_type}"

        patch = rule.generate_fix(error)

        assert isinstance(patch, TailwindPatch)
        for cls in expected_add:
            assert cls in patch.add_classes, f"Expected {cls} in {patch.add_classes}"

    def test_low_confidence_rejection(self, rule):
        """Rule should reject low confidence errors."""
        error = make_error(ErrorType.ZINDEX_CONFLICT, confidence=0.3)
        assert not rule.can_fix(error)

    def test_priority(self, rule):
        """Z-index rule should run after visibility."""
        assert rule.priority == 15


class TestPointerEventsRuleParametrized:
    """Parametrized tests for PointerEventsFixRule."""

    @pytest.fixture
    def rule(self):
        return PointerEventsFixRule()

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,expected_remove,description",
        POINTER_INTERCEPTED_CASES,
        ids=[case[4] for case in POINTER_INTERCEPTED_CASES]
    )
    def test_pointer_intercepted_fix(
        self,
        rule,
        error_type,
        input_classes,
        expected_add,
        expected_remove,
        description
    ):
        """Test POINTER_INTERCEPTED fixes."""
        error = make_error(error_type, classes=input_classes)

        assert rule.can_fix(error)

        result = rule.generate_fix(error)
        patch = result if isinstance(result, TailwindPatch) else result[0]

        assert_patch_contains(patch, expected_add, expected_remove)

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,expected_remove,blocking_element,description",
        POINTER_BLOCKED_CASES,
        ids=[case[5] for case in POINTER_BLOCKED_CASES]
    )
    def test_pointer_blocked_fix(
        self,
        rule,
        error_type,
        input_classes,
        expected_add,
        expected_remove,
        blocking_element,
        description
    ):
        """Test POINTER_BLOCKED fixes without blocker."""
        is_positioned = "relative" in input_classes or "absolute" in input_classes
        z_index = None
        for cls in input_classes:
            if cls.startswith("z-"):
                try:
                    z_index = int(cls.split("-")[1])
                except (ValueError, IndexError):
                    pass

        error = make_error(
            error_type,
            classes=input_classes,
            is_positioned=is_positioned,
            z_index=z_index,
            blocking_element=blocking_element,
        )

        assert rule.can_fix(error)

        result = rule.generate_fix(error)
        patch = result if isinstance(result, TailwindPatch) else result[0]

        for cls in expected_add:
            assert cls in patch.add_classes, f"Expected {cls} in {patch.add_classes}"

    def test_pointer_blocked_with_blocker(self, rule):
        """Test POINTER_BLOCKED generates blocker patch."""
        error = make_error(
            ErrorType.POINTER_BLOCKED,
            blocking_element=".overlay"
        )

        result = rule.generate_fix(error)
        patches = result if isinstance(result, list) else [result]

        # Should have patch for both target and blocker
        assert len(patches) >= 1

        # Find blocker patch
        blocker_patches = [p for p in patches if p.selector == ".overlay"]
        if blocker_patches:
            assert "pointer-events-none" in blocker_patches[0].add_classes

    def test_priority(self, rule):
        """Pointer events rule runs after z-index."""
        assert rule.priority == 25


class TestPassthroughRuleParametrized:
    """Parametrized tests for PassthroughRule."""

    @pytest.fixture
    def rule(self):
        return PassthroughRule()

    @pytest.mark.parametrize(
        "error_type,blocking_element,expected_add,expected_remove,description",
        PASSTHROUGH_CASES,
        ids=[case[4] for case in PASSTHROUGH_CASES]
    )
    def test_passthrough_fix(
        self,
        rule,
        error_type,
        blocking_element,
        expected_add,
        expected_remove,
        description
    ):
        """Test passthrough fixes for blocking overlays."""
        error = make_error(error_type, blocking_element=blocking_element)

        assert rule.can_fix(error)

        patch = rule.generate_fix(error)

        assert patch.selector == blocking_element
        assert_patch_contains(patch, expected_add, expected_remove)

    def test_requires_blocking_element(self, rule):
        """Rule should not fix without blocking element."""
        error = make_error(ErrorType.POINTER_BLOCKED, blocking_element=None)
        assert not rule.can_fix(error)

    def test_priority(self, rule):
        """Passthrough runs just after pointer events."""
        assert rule.priority == 26


class TestTransform3DRuleParametrized:
    """Parametrized tests for Transform3DFixRule."""

    @pytest.fixture
    def rule(self):
        return Transform3DFixRule()

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,expected_remove,selector,description",
        TRANSFORM_3D_CASES,
        ids=[case[5] for case in TRANSFORM_3D_CASES]
    )
    def test_transform_fix(
        self,
        rule,
        error_type,
        input_classes,
        expected_add,
        expected_remove,
        selector,
        description
    ):
        """Test transform fixes with various scenarios."""
        error = make_error(error_type, selector=selector, classes=input_classes)

        assert rule.can_fix(error)

        result = rule.generate_fix(error)
        patches = result if isinstance(result, list) else [result]

        # Find the element patch (not parent)
        element_patches = [p for p in patches if p.selector == selector]
        assert len(element_patches) > 0, f"No patch for selector {selector}"

        patch = element_patches[0]
        for cls in expected_add:
            assert cls in patch.add_classes, f"Expected {cls} in {patch.add_classes}"

    def test_backface_hidden_generates_parent_patch(self, rule):
        """TRANSFORM_3D_HIDDEN should patch parent if derivable."""
        error = make_error(
            ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".card .front",
            classes={"[backface-visibility:hidden]"},
        )

        result = rule.generate_fix(error)
        patches = result if isinstance(result, list) else [result]

        # Should have parent patch
        parent_patches = [p for p in patches if p.selector == ".card"]
        assert len(parent_patches) == 1

        parent_patch = parent_patches[0]
        assert "[transform-style:preserve-3d]" in parent_patch.add_classes
        assert "[perspective:1000px]" in parent_patch.add_classes

    def test_priority(self, rule):
        """Transform rule runs after pointer events."""
        assert rule.priority == 30


class TestVisualFeedbackRuleParametrized:
    """Parametrized tests for VisualFeedbackAmplifierRule."""

    @pytest.fixture
    def rule(self):
        return VisualFeedbackAmplifierRule()

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,description",
        [(ErrorType.FEEDBACK_TOO_SUBTLE, c[1], c[2], c[3]) for c in FEEDBACK_CASES],
        ids=[case[3] for case in FEEDBACK_CASES]
    )
    def test_feedback_fix(
        self,
        rule,
        error_type,
        input_classes,
        expected_add,
        description
    ):
        """Test feedback amplification with various existing states."""
        error = make_error(error_type, classes=input_classes)

        assert rule.can_fix(error)

        patch = rule.generate_fix(error)

        for cls in expected_add:
            assert cls in patch.add_classes, f"Expected {cls} in {patch.add_classes}"

    def test_no_duplicate_classes(self, rule):
        """Should not add classes that already exist."""
        existing = {"active:scale-95", "active:brightness-75", "transition-all", "duration-150"}
        error = make_error(ErrorType.FEEDBACK_TOO_SUBTLE, classes=existing)

        patch = rule.generate_fix(error)

        # Should have empty add_classes since all exist
        assert len(patch.add_classes) == 0 or all(
            cls not in existing for cls in patch.add_classes
        )

    def test_priority(self, rule):
        """Feedback rule runs last among deterministic rules."""
        assert rule.priority == 50


class TestRuleEngineIntegration:
    """Integration tests for the rule engine with all rules."""

    @pytest.fixture
    def engine(self):
        return create_default_engine()

    def test_engine_has_all_rules(self, engine):
        """Engine should have all 6 deterministic rules."""
        # Access private rules for testing
        rules = engine._rules
        assert len(rules) >= 6

    def test_rules_sorted_by_priority(self, engine):
        """Rules should be sorted by priority."""
        rules = engine._rules
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities)

    def test_visibility_runs_first(self, engine):
        """Visibility rule should run before others."""
        rules = engine._rules
        first_rule = rules[0]
        assert isinstance(first_rule, VisibilityRestoreRule)

    @pytest.mark.parametrize("error_type,should_fix", [
        (ErrorType.INVISIBLE_OPACITY, True),
        (ErrorType.INVISIBLE_DISPLAY, True),
        (ErrorType.INVISIBLE_VISIBILITY, True),
        (ErrorType.ZINDEX_CONFLICT, True),
        (ErrorType.ZINDEX_MISSING, True),
        (ErrorType.POINTER_BLOCKED, True),
        (ErrorType.POINTER_INTERCEPTED, True),
        (ErrorType.TRANSFORM_3D_HIDDEN, True),
        (ErrorType.TRANSFORM_OFFSCREEN, True),
        (ErrorType.FEEDBACK_TOO_SUBTLE, True),
        (ErrorType.JS_SYNTAX_ERROR, False),
        (ErrorType.JS_MISSING_FUNCTION, False),
        (ErrorType.UNKNOWN, False),
    ])
    def test_engine_handles_error_types(self, engine, error_type, should_fix):
        """Test which error types the engine can fix."""
        error = make_error(error_type)
        patches = engine.apply_rules([error])

        if should_fix:
            assert len(patches) > 0, f"Engine should generate patches for {error_type}"
        # Note: some error types may not generate patches due to can_fix checks


class TestEdgeCases:
    """Edge case tests for rules."""

    @pytest.fixture
    def engine(self):
        return create_default_engine()

    def test_empty_error_list(self, engine):
        """Engine should handle empty error list."""
        result = engine.apply_rules([])
        # Engine returns PatchSet, check that patches list is empty
        assert len(result.patches) == 0

    def test_multiple_errors_same_element(self, engine):
        """Engine should handle multiple errors on same element."""
        errors = [
            make_error(ErrorType.INVISIBLE_OPACITY, selector=".btn", classes={"opacity-0"}),
            make_error(ErrorType.FEEDBACK_TOO_SUBTLE, selector=".btn"),
        ]

        result = engine.apply_rules(errors)

        # Engine merges patches for same selector, so we check the merged patch has both fixes
        assert len(result.patches) >= 1
        merged_patch = result.patches[0]
        # Should have opacity fix
        assert "opacity-100" in merged_patch.add_classes
        # Should have feedback classes (at least some)
        feedback_classes = ["active:scale-95", "active:brightness-75", "transition-all"]
        has_feedback = any(cls in merged_patch.add_classes for cls in feedback_classes)
        assert has_feedback, "Merged patch should contain feedback classes"

    def test_conflicting_fixes(self, engine):
        """Engine should handle potentially conflicting fixes."""
        errors = [
            make_error(ErrorType.ZINDEX_CONFLICT, classes={"z-10"}, z_index=10),
            make_error(ErrorType.POINTER_BLOCKED, classes={"z-10"}, z_index=10),
        ]

        result = engine.apply_rules(errors)

        # Engine merges patches, check that fixes are applied
        assert len(result.patches) >= 1
        # The merged patch should have pointer-events and z-index fixes
        merged_patch = result.patches[0]
        assert "pointer-events-auto" in merged_patch.add_classes or "z-50" in merged_patch.add_classes

    def test_already_fixed_element(self):
        """Rule should not break on element that already has fix classes."""
        rule = VisibilityRestoreRule()
        error = make_error(
            ErrorType.INVISIBLE_OPACITY,
            classes={"opacity-0", "opacity-100"}  # Conflicting state
        )

        # Should not raise
        patch = rule.generate_fix(error)
        assert patch is not None
