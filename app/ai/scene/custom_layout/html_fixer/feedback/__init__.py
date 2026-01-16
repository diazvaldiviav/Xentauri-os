"""
Human Feedback module for layout validation.

This module provides tools for preparing HTML for human validation,
collecting user feedback on interactive elements, and applying fixes
based on combined sandbox and user feedback.
"""

from .element_mapper import ElementMapper, ElementInfo, PreparedHTML
from .annotation_injector import AnnotationInjector
from .feedback_merger import FeedbackMerger

__all__ = [
    "ElementMapper",
    "ElementInfo",
    "PreparedHTML",
    "AnnotationInjector",
    "FeedbackMerger",
]
