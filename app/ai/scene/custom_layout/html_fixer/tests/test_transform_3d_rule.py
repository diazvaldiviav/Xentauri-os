"""
Tests for Transform3DFixRule (Sprint 4).

Tests the enhanced transform fix rule that:
- Patches parent containers with preserve-3d and perspective
- Patches elements with backface-visibility
- Handles TRANSFORM_OFFSCREEN errors
"""

import pytest
from html_fixer.fixers.deterministic import Transform3DFixRule
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.tailwind_rules import TailwindFixes


class TestTransform3DFixRule:
    """Tests for Transform3DFixRule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = Transform3DFixRule()

    def test_handles_correct_error_types(self):
        """Test that rule handles transform-related errors."""
        assert ErrorType.TRANSFORM_3D_HIDDEN in self.rule.handles
        assert ErrorType.TRANSFORM_OFFSCREEN in self.rule.handles

    def test_priority_is_30(self):
        """Test that priority is 30 (Sprint 4 change from 35)."""
        assert self.rule.priority == 30

    def test_can_fix_transform_errors(self):
        """Test can_fix returns True for handled errors."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".card .front",
            element_tag="div",
            tailwind_info=TailwindInfo(),
        )
        assert self.rule.can_fix(error) is True

    def test_cannot_fix_other_errors(self):
        """Test can_fix returns False for unhandled errors."""
        error = ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector=".button",
            element_tag="button",
            tailwind_info=TailwindInfo(),
        )
        assert self.rule.can_fix(error) is False

    def test_find_transform_container_descendant(self):
        """Test parent extraction from descendant selector."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".card .front",
            element_tag="div",
            tailwind_info=TailwindInfo(),
        )
        parent = self.rule._find_transform_container(error)
        assert parent == ".card"

    def test_find_transform_container_direct_child(self):
        """Test parent extraction from direct child selector."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".flip-container > .flipper",
            element_tag="div",
            tailwind_info=TailwindInfo(),
        )
        parent = self.rule._find_transform_container(error)
        assert parent == ".flip-container"

    def test_find_transform_container_no_parent(self):
        """Test no parent for single element selector."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".single-element",
            element_tag="div",
            tailwind_info=TailwindInfo(),
        )
        parent = self.rule._find_transform_container(error)
        assert parent is None

    def test_fix_backface_hidden_with_parent(self):
        """Test fix generates patches for both parent and element."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".card .front",
            element_tag="div",
            tailwind_info=TailwindInfo(has_backface_hidden=True),
        )
        patches = self.rule.generate_fix(error)

        assert isinstance(patches, list)
        assert len(patches) == 2

        # Parent patch
        parent_patch = patches[0]
        assert parent_patch.selector == ".card"
        assert TailwindFixes.PRESERVE_3D in parent_patch.add_classes
        assert TailwindFixes.PERSPECTIVE in parent_patch.add_classes

        # Element patch
        element_patch = patches[1]
        assert element_patch.selector == ".card .front"
        assert TailwindFixes.BACKFACE_VISIBLE in element_patch.add_classes
        assert TailwindFixes.BACKFACE_HIDDEN in element_patch.remove_classes

    def test_fix_backface_hidden_no_parent(self):
        """Test fix only patches element when no parent derivable."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".flip-card",
            element_tag="div",
            tailwind_info=TailwindInfo(has_backface_hidden=True),
        )
        patches = self.rule.generate_fix(error)

        assert isinstance(patches, list)
        assert len(patches) == 1

        patch = patches[0]
        assert patch.selector == ".flip-card"
        assert TailwindFixes.BACKFACE_VISIBLE in patch.add_classes

    def test_fix_offscreen(self):
        """Test fix for offscreen elements resets translate."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_OFFSCREEN,
            selector=".slide",
            element_tag="div",
            tailwind_info=TailwindInfo(
                all_classes={"translate-x-full", "-translate-y-1/2"}
            ),
        )
        patches = self.rule.generate_fix(error)

        assert isinstance(patches, list)
        assert len(patches) == 1

        patch = patches[0]
        assert "translate-x-0" in patch.add_classes
        assert "translate-y-0" in patch.add_classes
        assert "translate-x-full" in patch.remove_classes
        assert "-translate-y-1/2" in patch.remove_classes

    def test_fix_preserves_non_translate_classes(self):
        """Test fix doesn't remove non-translate classes."""
        error = ClassifiedError(
            error_type=ErrorType.TRANSFORM_OFFSCREEN,
            selector=".slide",
            element_tag="div",
            tailwind_info=TailwindInfo(
                all_classes={"translate-x-full", "rotate-45", "scale-50"}
            ),
        )
        patches = self.rule.generate_fix(error)
        patch = patches[0]

        assert "rotate-45" not in patch.remove_classes
        assert "scale-50" not in patch.remove_classes
