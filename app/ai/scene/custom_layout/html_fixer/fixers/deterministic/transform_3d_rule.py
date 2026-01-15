"""
Transform3DFixRule - Fix 3D transform visibility issues.

This rule handles elements that are hidden or moved offscreen
due to CSS transforms.

Handles:
- TRANSFORM_3D_HIDDEN: Element hidden due to backface-visibility
- TRANSFORM_OFFSCREEN: Element transformed outside viewport
"""

from typing import List, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class Transform3DFixRule(FixRule):
    """
    Fix 3D transform related visibility issues.

    Strategy:
    For TRANSFORM_3D_HIDDEN:
      - Add [backface-visibility:visible]
      - Add [transform-style:preserve-3d] if using 3D transforms
      - Add [perspective:1000px] for proper 3D rendering

    For TRANSFORM_OFFSCREEN:
      - Reset translate values to bring element back into view
    """

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.TRANSFORM_3D_HIDDEN, ErrorType.TRANSFORM_OFFSCREEN]

    @property
    def priority(self) -> int:
        return 35  # After pointer/z-index fixes

    def can_fix(self, error: ClassifiedError) -> bool:
        """Can fix transform issues."""
        return error.error_type in self.handles

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate transform fix patches.
        """
        info = error.tailwind_info

        if error.error_type == ErrorType.TRANSFORM_3D_HIDDEN:
            return self._fix_backface_hidden(error, info)
        elif error.error_type == ErrorType.TRANSFORM_OFFSCREEN:
            return self._fix_offscreen(error, info)
        else:
            raise ValueError(f"Cannot fix {error.error_type}")

    def _fix_backface_hidden(
        self, error: ClassifiedError, info
    ) -> TailwindPatch:
        """
        Fix backface-visibility issue.

        When an element is rotated 180 degrees and has backface-visibility:hidden,
        it becomes invisible. We fix this by making the backface visible.
        """
        add_classes = [TailwindFixes.BACKFACE_VISIBLE]
        remove_classes = []

        if info.has_backface_hidden:
            remove_classes.append(TailwindFixes.BACKFACE_HIDDEN)

        # Add preserve-3d and perspective if using 3D transforms
        if info.has_transform and not info.has_preserve_3d:
            add_classes.append(TailwindFixes.PRESERVE_3D)
            add_classes.append(TailwindFixes.PERSPECTIVE)

        return TailwindPatch(
            selector=error.selector,
            add_classes=add_classes,
            remove_classes=remove_classes,
            reason="Fix 3D transform visibility",
        )

    def _fix_offscreen(
        self, error: ClassifiedError, info
    ) -> TailwindPatch:
        """
        Fix element transformed offscreen.

        Reset translate values to bring element back into the viewport.
        """
        add_classes = ["translate-x-0", "translate-y-0"]
        remove_classes = []

        # Remove any existing translate classes that push offscreen
        for cls in info.all_classes:
            if self._is_translate_class(cls) and cls not in add_classes:
                remove_classes.append(cls)

        return TailwindPatch(
            selector=error.selector,
            add_classes=add_classes,
            remove_classes=remove_classes,
            reason="Reset transform to visible area",
        )

    def _is_translate_class(self, cls: str) -> bool:
        """Check if class is a translate transform."""
        return (
            cls.startswith("translate-") or
            cls.startswith("-translate-") or
            cls.startswith("translate-x-") or
            cls.startswith("translate-y-") or
            cls.startswith("-translate-x-") or
            cls.startswith("-translate-y-")
        )
