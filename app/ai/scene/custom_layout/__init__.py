"""
Custom Layout Module - Tailwind-based HTML Fixer.

This module provides tools for validating and repairing HTML layouts
using Tailwind CSS class modifications.

Sprint 0: Foundation (contracts, fixtures, tailwind rules)
Sprint 1: Analyzers (DOM parser, Tailwind analyzer, error detection)

Usage:
======
    from app.ai.scene.custom_layout.html_fixer import TailwindFixes
    from app.ai.scene.custom_layout.html_fixer.analyzers import (
        DOMParser,
        TailwindAnalyzer,
        InteractiveDetector,
    )

    # Parse HTML
    parser = DOMParser(html_string)

    # Find interactive elements
    detector = InteractiveDetector()
    interactive = detector.find_interactive_elements(parser)

    # Analyze each element
    analyzer = TailwindAnalyzer()
    for item in interactive:
        info = analyzer.analyze_element(item.element)
        print(f"{item.selector}: z={info.z_index}, missing={info.missing_recommended}")
"""

from app.ai.scene.custom_layout.html_fixer import (
    TailwindFixes,
    ErrorType,
    TailwindPatch,
)

__all__ = [
    "TailwindFixes",
    "ErrorType",
    "TailwindPatch",
]
