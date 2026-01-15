"""
Unit tests for concrete fix rules.

Tests each rule's fix generation logic.
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
    VisibilityRestoreRule,
    ZIndexFixRule,
    PointerEventsFixRule,
    PassthroughRule,
    Transform3DFixRule,
)
from html_fixer.tailwind_rules import TailwindFixes


def make_tailwind_info(**kwargs) -> TailwindInfo:
    """Helper to create TailwindInfo with defaults."""
    defaults = {
        "all_classes": set(),
        "z_index": None,
        "has_pointer_none": False,
        "has_pointer_auto": False,
        "has_relative": False,
        "has_absolute": False,
        "has_fixed": False,
        "has_transform": False,
        "has_preserve_3d": False,
        "has_backface_hidden": False,
    }
    defaults.update(kwargs)
    return TailwindInfo(**defaults)


def make_classified_error(
    error_type: ErrorType,
    selector: str = "#btn",
    tailwind_info: TailwindInfo = None,
    **kwargs
) -> ClassifiedError:
    """Helper to create ClassifiedError with defaults."""
    if tailwind_info is None:
        tailwind_info = make_tailwind_info()
    return ClassifiedError(
        error_type=error_type,
        selector=selector,
        element_tag="button",
        tailwind_info=tailwind_info,
        **kwargs
    )


# ============================================================================
# VISIBILITY RESTORE RULE TESTS
# ============================================================================


class TestVisibilityRestoreRule:
    """Tests for VisibilityRestoreRule."""

    @pytest.fixture
    def rule(self):
        return VisibilityRestoreRule()

    def test_fixes_invisible_opacity(self, rule):
        """Should fix opacity: 0 issue."""
        error = make_classified_error(ErrorType.INVISIBLE_OPACITY)

        patch = rule.generate_fix(error)

        assert isinstance(patch, TailwindPatch)
        assert TailwindFixes.OPACITY_100 in patch.add_classes
        assert TailwindFixes.OPACITY_0 in patch.remove_classes

    def test_fixes_invisible_display(self, rule):
        """Should fix display: none issue."""
        error = make_classified_error(ErrorType.INVISIBLE_DISPLAY)

        patch = rule.generate_fix(error)

        assert TailwindFixes.BLOCK in patch.add_classes
        assert TailwindFixes.HIDDEN in patch.remove_classes

    def test_fixes_invisible_visibility(self, rule):
        """Should fix visibility: hidden issue."""
        error = make_classified_error(ErrorType.INVISIBLE_VISIBILITY)

        patch = rule.generate_fix(error)

        assert TailwindFixes.VISIBLE in patch.add_classes
        assert TailwindFixes.INVISIBLE in patch.remove_classes

    def test_removes_other_opacity_classes(self, rule):
        """Should remove other opacity classes when fixing opacity."""
        info = make_tailwind_info(all_classes={"opacity-50", "bg-blue-500"})
        error = make_classified_error(
            ErrorType.INVISIBLE_OPACITY,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert "opacity-50" in patch.remove_classes

    def test_patch_has_reason(self, rule):
        """Patch should have descriptive reason."""
        error = make_classified_error(ErrorType.INVISIBLE_OPACITY)

        patch = rule.generate_fix(error)

        assert patch.reason is not None
        assert "visibility" in patch.reason.lower()


# ============================================================================
# ZINDEX FIX RULE TESTS
# ============================================================================


class TestZIndexFixRule:
    """Tests for ZIndexFixRule."""

    @pytest.fixture
    def rule(self):
        return ZIndexFixRule()

    def test_fixes_zindex_conflict(self, rule):
        """Should elevate z-index for conflict."""
        info = make_tailwind_info(z_index=10, has_relative=True)
        error = make_classified_error(
            ErrorType.ZINDEX_CONFLICT,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        # Should add elevated z-index
        assert any(c.startswith("z-") for c in patch.add_classes)

    def test_fixes_zindex_missing(self, rule):
        """Should add z-index when missing."""
        error = make_classified_error(ErrorType.ZINDEX_MISSING)

        patch = rule.generate_fix(error)

        assert TailwindFixes.ZINDEX_LOW in patch.add_classes

    def test_adds_relative_when_not_positioned(self, rule):
        """Should add relative positioning if not positioned."""
        info = make_tailwind_info(has_relative=False)
        error = make_classified_error(
            ErrorType.ZINDEX_CONFLICT,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert TailwindFixes.POSITION_RELATIVE in patch.add_classes

    def test_does_not_add_relative_when_positioned(self, rule):
        """Should not add relative if already positioned."""
        info = make_tailwind_info(has_absolute=True)
        error = make_classified_error(
            ErrorType.ZINDEX_CONFLICT,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert TailwindFixes.POSITION_RELATIVE not in patch.add_classes

    def test_removes_old_zindex(self, rule):
        """Should remove old z-index class."""
        info = make_tailwind_info(
            z_index=10,
            all_classes={"z-10", "bg-blue-500"},
            has_relative=True
        )
        error = make_classified_error(
            ErrorType.ZINDEX_CONFLICT,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert "z-10" in patch.remove_classes

    def test_respects_low_confidence(self, rule):
        """Should not fix low-confidence errors."""
        error = make_classified_error(
            ErrorType.ZINDEX_CONFLICT,
            confidence=0.3
        )

        assert rule.can_fix(error) is False


# ============================================================================
# POINTER EVENTS FIX RULE TESTS
# ============================================================================


class TestPointerEventsFixRule:
    """Tests for PointerEventsFixRule."""

    @pytest.fixture
    def rule(self):
        return PointerEventsFixRule()

    def test_fixes_pointer_intercepted(self, rule):
        """Should add pointer-events-auto for intercepted."""
        error = make_classified_error(ErrorType.POINTER_INTERCEPTED)

        patch = rule.generate_fix(error)

        assert isinstance(patch, TailwindPatch)
        assert TailwindFixes.POINTER_AUTO in patch.add_classes

    def test_fixes_pointer_blocked(self, rule):
        """Should fix blocked element."""
        info = make_tailwind_info(has_pointer_auto=False, has_relative=False)
        error = make_classified_error(
            ErrorType.POINTER_BLOCKED,
            tailwind_info=info
        )

        patches = rule.generate_fix(error)
        # Could be single patch or list
        if isinstance(patches, list):
            patch = patches[0]
        else:
            patch = patches

        assert TailwindFixes.POINTER_AUTO in patch.add_classes

    def test_patches_blocking_element(self, rule):
        """Should create patch for blocking element."""
        error = make_classified_error(
            ErrorType.POINTER_BLOCKED,
            blocking_element="#overlay"
        )

        result = rule.generate_fix(error)
        patches = result if isinstance(result, list) else [result]

        # Should have patch for blocker
        blocker_patches = [p for p in patches if p.selector == "#overlay"]
        assert len(blocker_patches) == 1
        assert TailwindFixes.POINTER_NONE in blocker_patches[0].add_classes

    def test_elevates_zindex(self, rule):
        """Should elevate z-index when fixing blocked."""
        info = make_tailwind_info(z_index=10, has_relative=True)
        error = make_classified_error(
            ErrorType.POINTER_BLOCKED,
            tailwind_info=info
        )

        result = rule.generate_fix(error)
        patches = result if isinstance(result, list) else [result]

        target_patch = [p for p in patches if p.selector == "#btn"][0]
        # Should have elevated z-index
        assert any(c.startswith("z-") for c in target_patch.add_classes)


# ============================================================================
# PASSTHROUGH RULE TESTS
# ============================================================================


class TestPassthroughRule:
    """Tests for PassthroughRule."""

    @pytest.fixture
    def rule(self):
        return PassthroughRule()

    def test_requires_blocking_element(self, rule):
        """Should require blocking_element."""
        error = make_classified_error(ErrorType.POINTER_BLOCKED)

        assert rule.can_fix(error) is False

    def test_can_fix_with_blocking_element(self, rule):
        """Should be able to fix when blocking element known."""
        error = make_classified_error(
            ErrorType.POINTER_BLOCKED,
            blocking_element="#overlay"
        )

        assert rule.can_fix(error) is True

    def test_patches_blocking_element(self, rule):
        """Should patch the blocking element."""
        error = make_classified_error(
            ErrorType.POINTER_BLOCKED,
            blocking_element="#overlay"
        )

        patch = rule.generate_fix(error)

        assert patch.selector == "#overlay"
        assert TailwindFixes.POINTER_NONE in patch.add_classes

    def test_raises_without_blocking_element(self, rule):
        """Should raise if called without blocking element."""
        error = make_classified_error(ErrorType.POINTER_BLOCKED)

        with pytest.raises(ValueError):
            rule.generate_fix(error)


# ============================================================================
# TRANSFORM 3D FIX RULE TESTS
# ============================================================================


class TestTransform3DFixRule:
    """Tests for Transform3DFixRule."""

    @pytest.fixture
    def rule(self):
        return Transform3DFixRule()

    def test_fixes_backface_hidden(self, rule):
        """Should fix backface-visibility issue."""
        info = make_tailwind_info(has_backface_hidden=True)
        error = make_classified_error(
            ErrorType.TRANSFORM_3D_HIDDEN,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert TailwindFixes.BACKFACE_VISIBLE in patch.add_classes
        assert TailwindFixes.BACKFACE_HIDDEN in patch.remove_classes

    def test_adds_preserve_3d(self, rule):
        """Should add preserve-3d for transform elements."""
        info = make_tailwind_info(has_transform=True, has_preserve_3d=False)
        error = make_classified_error(
            ErrorType.TRANSFORM_3D_HIDDEN,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert TailwindFixes.PRESERVE_3D in patch.add_classes

    def test_fixes_transform_offscreen(self, rule):
        """Should reset offscreen transforms."""
        info = make_tailwind_info(
            all_classes={"-translate-x-full", "bg-blue-500"}
        )
        error = make_classified_error(
            ErrorType.TRANSFORM_OFFSCREEN,
            tailwind_info=info
        )

        patch = rule.generate_fix(error)

        assert "translate-x-0" in patch.add_classes
        assert "translate-y-0" in patch.add_classes
        assert "-translate-x-full" in patch.remove_classes

    def test_handles_both_error_types(self, rule):
        """Should handle both 3D hidden and offscreen."""
        assert ErrorType.TRANSFORM_3D_HIDDEN in rule.handles
        assert ErrorType.TRANSFORM_OFFSCREEN in rule.handles


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestRuleIntegration:
    """Integration tests combining multiple rules."""

    def test_all_rules_generate_valid_patches(self):
        """All rules should generate valid TailwindPatch objects."""
        rules_and_errors = [
            (VisibilityRestoreRule(), ErrorType.INVISIBLE_OPACITY, {}),
            (ZIndexFixRule(), ErrorType.ZINDEX_CONFLICT, {}),
            (PointerEventsFixRule(), ErrorType.POINTER_BLOCKED, {}),
            (PassthroughRule(), ErrorType.POINTER_BLOCKED, {"blocking_element": "#overlay"}),
            (Transform3DFixRule(), ErrorType.TRANSFORM_3D_HIDDEN, {}),
        ]

        for rule, error_type, extra in rules_and_errors:
            error = make_classified_error(error_type, **extra)
            result = rule.generate_fix(error)

            patches = result if isinstance(result, list) else [result]
            for patch in patches:
                assert isinstance(patch, TailwindPatch)
                assert patch.selector is not None
                assert isinstance(patch.add_classes, list)
                assert isinstance(patch.remove_classes, list)
