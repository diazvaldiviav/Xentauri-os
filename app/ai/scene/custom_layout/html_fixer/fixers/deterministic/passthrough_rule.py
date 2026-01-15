"""
PassthroughRule - Make decorative overlays pass-through.

This rule handles a special case: overlays that are blocking clicks
but shouldn't be (decorative backgrounds, gradients, etc.).

This complements PointerEventsFixRule by focusing specifically on
the blocking element rather than the target.

Handles:
- POINTER_BLOCKED: When the blocker should be made pass-through
"""

from typing import List, Union, Set

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class PassthroughRule(FixRule):
    """
    Make decorative overlays pass-through.

    This rule identifies blocking elements that appear to be decorative
    (backgrounds, gradients, etc.) and makes them pass-through for
    pointer events.

    Strategy:
    - Check if blocking element exists
    - Apply pointer-events-none to the blocking element
    """

    # Indicators that an element is decorative (not interactive)
    DECORATIVE_INDICATORS: Set[str] = {
        "bg-gradient-",
        "from-",
        "to-",
        "via-",
        "bg-black/",
        "bg-white/",
        "backdrop-",
        "inset-0",
    }

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.POINTER_BLOCKED]

    @property
    def priority(self) -> int:
        return 26  # Just after PointerEventsFixRule

    def can_fix(self, error: ClassifiedError) -> bool:
        """
        Can fix if there's a blocking element.
        """
        if error.error_type != ErrorType.POINTER_BLOCKED:
            return False

        # Need to know what's blocking
        if not error.blocking_element:
            return False

        return True

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate passthrough patch for blocking overlay.

        Only generates patch for the blocking element, not the target.
        (Target is handled by PointerEventsFixRule)
        """
        if not error.blocking_element:
            raise ValueError("No blocking element specified")

        return TailwindPatch(
            selector=error.blocking_element,
            add_classes=[TailwindFixes.POINTER_NONE],
            remove_classes=[TailwindFixes.POINTER_AUTO],
            reason="Make overlay pass-through for clicks",
        )

    def _is_likely_decorative(self, classes: Set[str]) -> bool:
        """
        Heuristic to determine if element is decorative.

        Args:
            classes: Set of Tailwind classes

        Returns:
            True if element appears to be decorative
        """
        for cls in classes:
            for indicator in self.DECORATIVE_INDICATORS:
                if indicator in cls:
                    return True
        return False
