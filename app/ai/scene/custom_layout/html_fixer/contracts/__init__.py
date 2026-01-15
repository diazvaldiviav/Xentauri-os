"""
Contracts - Data structures for the HTML Fixer.

Provides:
- ErrorType: Classification of HTML/CSS errors
- TailwindPatch: Patch format for Tailwind class modifications
- ValidationResult: Result of HTML validation
"""

from .errors import ErrorType
from .patches import TailwindPatch
from .validation import (
    TailwindInfo,
    ClassifiedError,
    FixResult,
)

__all__ = [
    "ErrorType",
    "TailwindPatch",
    "TailwindInfo",
    "ClassifiedError",
    "FixResult",
]
