"""
ZIndexFixRule - Fix z-index conflicts and missing z-index issues.

This rule handles elements that are behind other elements due to
z-index stacking issues.

Handles:
- ZINDEX_CONFLICT: Element behind another due to z-index
- ZINDEX_MISSING: Interactive element lacks z-index positioning
"""

from typing import List, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class ZIndexFixRule(FixRule):
    """
    Fix z-index related errors.

    Strategy:
    1. Add relative positioning if not already positioned
    2. Calculate appropriate z-index based on current context
    3. Remove conflicting z-index classes

    Note: For ZINDEX_CONFLICT, we elevate the element above what's
    blocking it. For ZINDEX_MISSING, we add a baseline z-index.
    """

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.ZINDEX_CONFLICT, ErrorType.ZINDEX_MISSING]

    @property
    def priority(self) -> int:
        return 15  # Run after visibility fixes

    def can_fix(self, error: ClassifiedError) -> bool:
        """Can fix if error is z-index related."""
        if error.error_type not in self.handles:
            return False

        # Don't fix if confidence is too low
        if error.confidence < 0.5:
            return False

        return True

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate z-index fix patches.

        For ZINDEX_CONFLICT: Elevate z-index above blocker
        For ZINDEX_MISSING: Add default z-10 with relative positioning
        """
        info = error.tailwind_info

        # Determine classes to add and remove
        add_classes: List[str] = []
        remove_classes: List[str] = []

        # Add positioning if not present (z-index requires positioned element)
        if not info.is_positioned:
            add_classes.append(TailwindFixes.POSITION_RELATIVE)

        # Determine z-index fix
        if error.error_type == ErrorType.ZINDEX_CONFLICT:
            # Need to go above the blocker
            current_z = info.z_index
            new_z_class = TailwindFixes.get_zindex_fix(current_z)
            add_classes.append(new_z_class)

            # Remove old z-index if present
            old_z_class = info.get_zindex_class()
            if old_z_class and old_z_class != new_z_class:
                remove_classes.append(old_z_class)

        elif error.error_type == ErrorType.ZINDEX_MISSING:
            # Add default z-index for interactive elements
            add_classes.append(TailwindFixes.ZINDEX_LOW)

        return TailwindPatch(
            selector=error.selector,
            add_classes=add_classes,
            remove_classes=remove_classes,
            reason=f"Fix {error.error_type.value}",
        )
