"""
VisualFeedbackAmplifierRule - Amplify subtle visual feedback.

Sprint 4: New rule to enhance visual feedback on interactive elements.

This rule handles elements where the visual feedback on interaction
(click, focus, hover) is too subtle to be noticed.

Handles:
- FEEDBACK_TOO_SUBTLE: Existing feedback is too weak
"""

from typing import List, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError
from ...tailwind_rules import TailwindFixes

from .base_rule import FixRule


class VisualFeedbackAmplifierRule(FixRule):
    """
    Amplify visual feedback on interactive elements.

    When an element has feedback that's too subtle to notice,
    this rule adds strong visual cues:
    - Scale animation on active state
    - Brightness change on active state
    - Focus ring for accessibility
    - Smooth transitions for all changes

    Priority 50 means this runs after critical fixes (visibility,
    z-index, pointer-events, transforms) are applied.
    """

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.FEEDBACK_TOO_SUBTLE]

    @property
    def priority(self) -> int:
        return 50  # Run after critical visibility/interaction fixes

    def can_fix(self, error: ClassifiedError) -> bool:
        """Can fix feedback issues."""
        return error.error_type in self.handles

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate visual feedback amplification patch.

        Adds a comprehensive set of feedback classes:
        - active:scale-95 - slight shrink on click
        - active:brightness-75 - darken on click
        - focus:ring-4 focus:ring-blue-500 - visible focus state
        - transition-all duration-150 - smooth animations
        """
        add_classes = [
            TailwindFixes.FEEDBACK_SCALE,      # active:scale-95
            TailwindFixes.FEEDBACK_BRIGHTNESS,  # active:brightness-75
            "focus:ring-4",
            "focus:ring-blue-500",
            TailwindFixes.TRANSITION_ALL,       # transition-all
            TailwindFixes.DURATION_150,         # duration-150
        ]

        # Check for existing feedback classes to avoid duplication
        existing = error.tailwind_info.all_classes
        add_classes = [cls for cls in add_classes if cls not in existing]

        return TailwindPatch(
            selector=error.selector,
            add_classes=add_classes,
            reason="Amplify visual feedback",
        )
