"""
LLM Fixer Contracts - Data structures for LLM-generated patches.

Sprint 6: Contracts for JavaScript patches and fix results.
"""

from .js_patch import JSPatch, JSPatchType, JSPatchSet

__all__ = [
    "JSPatch",
    "JSPatchType",
    "JSPatchSet",
]
