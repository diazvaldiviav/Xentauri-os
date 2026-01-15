"""
VisibilityRestoreRule - Restore hidden/invisible elements.

This rule has the highest priority (5) because visibility issues
prevent all other interactions.

Handles:
- INVISIBLE_OPACITY: opacity: 0 -> opacity-100
- INVISIBLE_DISPLAY: display: none -> block
- INVISIBLE_VISIBILITY: visibility: hidden -> visible
"""

from typing import List, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class VisibilityRestoreRule(FixRule):
    """
    Fix visibility related errors.

    This is typically the first rule to run because if an element
    is invisible, all other fixes are moot.

    Strategy:
    - Map each visibility issue to the appropriate Tailwind class fix
    - Remove the hiding class and add the showing class
    """

    # Mapping of error types to (add_classes, remove_classes)
    FIXES = {
        ErrorType.INVISIBLE_OPACITY: (
            [TailwindFixes.OPACITY_100],
            [TailwindFixes.OPACITY_0],
        ),
        ErrorType.INVISIBLE_DISPLAY: (
            [TailwindFixes.BLOCK],
            [TailwindFixes.HIDDEN],
        ),
        ErrorType.INVISIBLE_VISIBILITY: (
            [TailwindFixes.VISIBLE],
            [TailwindFixes.INVISIBLE],
        ),
    }

    @property
    def handles(self) -> List[ErrorType]:
        return [
            ErrorType.INVISIBLE_OPACITY,
            ErrorType.INVISIBLE_DISPLAY,
            ErrorType.INVISIBLE_VISIBILITY,
        ]

    @property
    def priority(self) -> int:
        return 5  # Run first - visibility is critical

    def can_fix(self, error: ClassifiedError) -> bool:
        """Can fix visibility issues."""
        return error.error_type in self.handles

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate visibility restoration patches.

        For opacity issues, also removes any other opacity-* classes
        that might conflict.
        """
        add_classes, remove_classes = self.FIXES[error.error_type]

        # Copy to avoid modifying class constant
        add_classes = list(add_classes)
        remove_classes = list(remove_classes)

        # For opacity, also remove any other opacity classes
        if error.error_type == ErrorType.INVISIBLE_OPACITY:
            for cls in error.tailwind_info.all_classes:
                if cls.startswith("opacity-") and cls not in add_classes:
                    if cls not in remove_classes:
                        remove_classes.append(cls)

        return TailwindPatch(
            selector=error.selector,
            add_classes=add_classes,
            remove_classes=remove_classes,
            reason=f"Restore visibility ({error.error_type.value})",
        )
