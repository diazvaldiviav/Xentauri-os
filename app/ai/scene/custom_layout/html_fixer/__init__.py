"""
HTML Fixer - Tailwind-based HTML repair system.

Sprint 0: Foundation module for the chirurgical HTML fixer.
"""

from .tailwind_rules import TailwindFixes
from .contracts import (
    ErrorType,
    TailwindPatch,
)

__all__ = [
    "TailwindFixes",
    "ErrorType",
    "TailwindPatch",
]
