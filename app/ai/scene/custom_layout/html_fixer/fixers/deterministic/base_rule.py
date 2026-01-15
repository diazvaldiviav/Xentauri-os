"""
FixRule - Abstract base class for deterministic fix rules.

Each rule handles specific ErrorType(s) and generates TailwindPatch(es)
to fix those errors.

Usage:
    class MyFixRule(FixRule):
        @property
        def handles(self) -> List[ErrorType]:
            return [ErrorType.SOME_ERROR]

        @property
        def priority(self) -> int:
            return 10

        def can_fix(self, error: ClassifiedError) -> bool:
            return error.error_type in self.handles

        def generate_fix(self, error: ClassifiedError) -> TailwindPatch:
            return TailwindPatch(...)
"""

from abc import ABC, abstractmethod
from typing import List, Union

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError


class FixRule(ABC):
    """
    Abstract base class for deterministic fix rules.

    Subclasses must implement:
    - handles: List of ErrorType this rule can fix
    - priority: Execution order (lower = earlier)
    - can_fix(): Whether rule can fix a specific error
    - generate_fix(): Generate patch(es) for an error

    Priority Ranges:
    - 0-10: Visibility fixes (critical)
    - 11-20: Z-index fixes
    - 21-30: Pointer event fixes
    - 31-40: Transform fixes
    - 41-50: Visual feedback fixes
    """

    @property
    @abstractmethod
    def handles(self) -> List[ErrorType]:
        """
        Error types this rule handles.

        Returns:
            List of ErrorType enum values
        """
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Execution priority. Lower values run first.

        Returns:
            Integer priority value
        """
        pass

    @property
    def name(self) -> str:
        """
        Rule name for logging and debugging.

        Returns:
            Class name by default
        """
        return self.__class__.__name__

    @abstractmethod
    def can_fix(self, error: ClassifiedError) -> bool:
        """
        Determine if this rule can fix the given error.

        Args:
            error: Classified error to evaluate

        Returns:
            True if rule can generate a fix for this error
        """
        pass

    @abstractmethod
    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        """
        Generate Tailwind patch(es) to fix the error.

        Args:
            error: Classified error to fix

        Returns:
            Single TailwindPatch or list of patches

        Raises:
            ValueError: If rule cannot fix this error type
        """
        pass

    def __repr__(self) -> str:
        """String representation."""
        types = [e.value for e in self.handles]
        return f"{self.name}(handles={types}, priority={self.priority})"

    def __eq__(self, other: object) -> bool:
        """Equality check based on class type."""
        if not isinstance(other, FixRule):
            return False
        return self.__class__ == other.__class__

    def __hash__(self) -> int:
        """Hash based on class name."""
        return hash(self.__class__.__name__)
