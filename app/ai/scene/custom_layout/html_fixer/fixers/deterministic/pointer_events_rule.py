"""
PointerEventsFixRule - Fix pointer event blockages.

This rule handles elements that can't receive clicks due to
pointer-events CSS property issues.

Handles:
- POINTER_BLOCKED: Element blocked by overlay
- POINTER_INTERCEPTED: Clicks captured by ancestor with pointer-events-none
"""

from typing import List, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class PointerEventsFixRule(FixRule):
    """
    Fix pointer event related errors.

    Strategy:
    For POINTER_BLOCKED:
      - Add pointer-events-auto to target element
      - Add relative positioning and z-index elevation
      - If blocker is known, add pointer-events-none to it

    For POINTER_INTERCEPTED (parent has pointer-events-none):
      - Add pointer-events-auto to target to override inheritance
    """

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.POINTER_BLOCKED, ErrorType.POINTER_INTERCEPTED]

    @property
    def priority(self) -> int:
        return 25  # After z-index fixes

    def can_fix(self, error: ClassifiedError) -> bool:
        """Can fix pointer event issues."""
        return error.error_type in self.handles

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate pointer event fix patches.

        May generate patches for both target and blocking element.
        """
        patches: List[TailwindPatch] = []
        info = error.tailwind_info

        if error.error_type == ErrorType.POINTER_INTERCEPTED:
            # Parent has pointer-events-none, child needs override
            patches.append(TailwindPatch(
                selector=error.selector,
                add_classes=[TailwindFixes.POINTER_AUTO],
                remove_classes=[TailwindFixes.POINTER_NONE],
                reason="Override parent pointer-events-none",
            ))

        elif error.error_type == ErrorType.POINTER_BLOCKED:
            # Element is blocked by another element
            target_add: List[str] = []
            target_remove: List[str] = []

            # Ensure interactive element can receive clicks
            if not info.has_pointer_auto:
                target_add.append(TailwindFixes.POINTER_AUTO)

            # Add positioning if needed
            if not info.is_positioned:
                target_add.append(TailwindFixes.POSITION_RELATIVE)

            # Elevate z-index
            new_z = TailwindFixes.get_zindex_fix(info.z_index)
            target_add.append(new_z)

            # Remove old z-index if different
            old_z = info.get_zindex_class()
            if old_z and old_z != new_z:
                target_remove.append(old_z)

            # Patch for target element
            if target_add:
                patches.append(TailwindPatch(
                    selector=error.selector,
                    add_classes=target_add,
                    remove_classes=target_remove,
                    reason="Enable pointer events and elevate",
                ))

            # If we know the blocking element, make it pass-through
            if error.blocking_element:
                patches.append(TailwindPatch(
                    selector=error.blocking_element,
                    add_classes=[TailwindFixes.POINTER_NONE],
                    remove_classes=[TailwindFixes.POINTER_AUTO],
                    reason="Make blocker pass-through",
                ))

        return patches if len(patches) > 1 else patches[0]
