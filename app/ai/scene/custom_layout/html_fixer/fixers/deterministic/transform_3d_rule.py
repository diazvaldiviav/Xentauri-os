"""
Transform3DFixRule - Fix 3D transform visibility issues.

Sprint 4: Enhanced to support parent container patching.

This rule handles elements that are hidden or moved offscreen
due to CSS transforms.

Handles:
- TRANSFORM_3D_HIDDEN: Element hidden due to backface-visibility
- TRANSFORM_OFFSCREEN: Element transformed outside viewport
"""

from typing import List, Optional, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class Transform3DFixRule(FixRule):
    """
    Fix 3D transform related visibility issues.

    Sprint 4 Strategy:
    For TRANSFORM_3D_HIDDEN:
      - Patch parent with [transform-style:preserve-3d] and [perspective:1000px]
      - Patch element with [backface-visibility:visible]

    For TRANSFORM_OFFSCREEN:
      - Reset translate values to bring element back into view
    """

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.TRANSFORM_3D_HIDDEN, ErrorType.TRANSFORM_OFFSCREEN]

    @property
    def priority(self) -> int:
        return 30  # Sprint 4: Changed from 35 to 30

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

    def _find_transform_container(self, error: ClassifiedError) -> Optional[str]:
        """
        Find the parent container that should receive 3D transform context.

        Returns the parent selector if we can derive it from the element selector,
        None otherwise.

        Examples:
            ".card .front" -> ".card"
            ".container > .item" -> ".container"
            ".single-element" -> None (no parent in selector)
        """
        selector = error.selector.strip()

        # Try to extract parent from descendant combinator
        if " > " in selector:
            # Direct child combinator: ".parent > .child" -> ".parent"
            parts = selector.rsplit(" > ", 1)
            return parts[0].strip() if len(parts) > 1 else None

        if " " in selector:
            # Descendant combinator: ".parent .child" -> ".parent"
            parts = selector.rsplit(" ", 1)
            return parts[0].strip() if len(parts) > 1 else None

        # Single element selector, no parent derivable
        return None

    def _fix_backface_hidden(
        self, error: ClassifiedError, info
    ) -> List[TailwindPatch]:
        """
        Fix backface-visibility issue with parent + element patches.

        Sprint 4: Now returns List[TailwindPatch] to patch both parent and element.

        When an element is rotated 180 degrees and has backface-visibility:hidden,
        it becomes invisible. We fix this by:
        1. Adding preserve-3d and perspective to parent (if derivable)
        2. Making the backface visible on the element
        """
        patches: List[TailwindPatch] = []

        # 1. Parent needs preserve-3d and perspective
        parent_selector = self._find_transform_container(error)
        if parent_selector:
            patches.append(
                TailwindPatch(
                    selector=parent_selector,
                    add_classes=[
                        TailwindFixes.PRESERVE_3D,
                        TailwindFixes.PERSPECTIVE,
                    ],
                    reason="Add 3D transform context to parent",
                )
            )

        # 2. Element needs backface visible
        remove_classes = []
        if info.has_backface_hidden:
            remove_classes.append(TailwindFixes.BACKFACE_HIDDEN)

        patches.append(
            TailwindPatch(
                selector=error.selector,
                add_classes=[TailwindFixes.BACKFACE_VISIBLE],
                remove_classes=remove_classes,
                reason="Fix 3D transform visibility",
            )
        )

        return patches

    def _fix_offscreen(
        self, error: ClassifiedError, info
    ) -> List[TailwindPatch]:
        """
        Fix element transformed offscreen.

        Reset translate values to bring element back into the viewport.
        Returns a list for consistency with _fix_backface_hidden.
        """
        add_classes = ["translate-x-0", "translate-y-0"]
        remove_classes = []

        # Remove any existing translate classes that push offscreen
        for cls in info.all_classes:
            if self._is_translate_class(cls) and cls not in add_classes:
                remove_classes.append(cls)

        return [
            TailwindPatch(
                selector=error.selector,
                add_classes=add_classes,
                remove_classes=remove_classes,
                reason="Reset transform to visible area",
            )
        ]

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
