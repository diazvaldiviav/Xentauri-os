"""
Error Prioritizer - Sort errors by severity and fixability.

Errors are prioritized so that fixing them in order produces
the best results with minimum conflicts.
"""

from typing import List, Dict

from ..contracts.errors import ErrorType
from ..contracts.validation import ClassifiedError


class ErrorPrioritizer:
    """
    Prioritizes classified errors for fixing.

    Higher priority errors should be fixed first as they often
    cause secondary issues that resolve automatically.
    """

    # Priority order (lower number = higher priority)
    PRIORITY_ORDER: Dict[ErrorType, int] = {
        # Critical blocking issues (fix first)
        ErrorType.POINTER_BLOCKED: 1,
        ErrorType.ZINDEX_CONFLICT: 2,
        # Visibility issues (fix second)
        ErrorType.INVISIBLE_DISPLAY: 3,
        ErrorType.INVISIBLE_VISIBILITY: 4,
        ErrorType.INVISIBLE_OPACITY: 5,
        # Transform issues (fix third)
        ErrorType.TRANSFORM_3D_HIDDEN: 6,
        ErrorType.TRANSFORM_OFFSCREEN: 7,
        # Secondary issues (fix last)
        ErrorType.POINTER_INTERCEPTED: 8,
        ErrorType.ZINDEX_MISSING: 9,
        # Feedback issues (lowest priority)
        ErrorType.FEEDBACK_MISSING: 10,
        ErrorType.FEEDBACK_TOO_SUBTLE: 11,
        # Unknown (last)
        ErrorType.UNKNOWN: 99,
    }

    def prioritize(self, errors: List[ClassifiedError]) -> List[ClassifiedError]:
        """
        Sort errors by priority.

        Args:
            errors: Unsorted list of errors

        Returns:
            Sorted list with highest priority first
        """
        return sorted(
            errors,
            key=lambda e: (
                self.PRIORITY_ORDER.get(e.error_type, 50),
                -e.confidence,  # Higher confidence first within same type
                e.selector,  # Alphabetical for consistency
            ),
        )

    def get_priority(self, error: ClassifiedError) -> int:
        """Get priority value for a single error."""
        return self.PRIORITY_ORDER.get(error.error_type, 50)

    def group_by_priority(
        self, errors: List[ClassifiedError]
    ) -> Dict[str, List[ClassifiedError]]:
        """
        Group errors by priority tier.

        Returns dict with keys: 'critical', 'visibility', 'transform', 'secondary', 'feedback'
        """
        groups: Dict[str, List[ClassifiedError]] = {
            "critical": [],
            "visibility": [],
            "transform": [],
            "secondary": [],
            "feedback": [],
        }

        for error in errors:
            priority = self.PRIORITY_ORDER.get(error.error_type, 50)

            if priority <= 2:
                groups["critical"].append(error)
            elif priority <= 5:
                groups["visibility"].append(error)
            elif priority <= 7:
                groups["transform"].append(error)
            elif priority <= 9:
                groups["secondary"].append(error)
            else:
                groups["feedback"].append(error)

        return groups

    def filter_by_confidence(
        self, errors: List[ClassifiedError], min_confidence: float = 0.8
    ) -> List[ClassifiedError]:
        """
        Filter errors by minimum confidence.

        Args:
            errors: List of errors
            min_confidence: Minimum confidence threshold

        Returns:
            Filtered list
        """
        return [e for e in errors if e.confidence >= min_confidence]

    def get_critical_errors(
        self, errors: List[ClassifiedError]
    ) -> List[ClassifiedError]:
        """Get only critical priority errors (POINTER_BLOCKED, ZINDEX_CONFLICT)."""
        critical_types = {ErrorType.POINTER_BLOCKED, ErrorType.ZINDEX_CONFLICT}
        return [e for e in errors if e.error_type in critical_types]

    def has_blocking_errors(self, errors: List[ClassifiedError]) -> bool:
        """Check if there are any blocking errors that prevent interaction."""
        blocking_types = {
            ErrorType.POINTER_BLOCKED,
            ErrorType.ZINDEX_CONFLICT,
            ErrorType.INVISIBLE_DISPLAY,
            ErrorType.INVISIBLE_VISIBILITY,
        }
        return any(e.error_type in blocking_types for e in errors)
