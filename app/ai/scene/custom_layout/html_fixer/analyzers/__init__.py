"""
Analyzers - DOM and Tailwind analysis tools.

This module provides tools for analyzing HTML documents:
- DOMParser: Parse and query HTML structure
- TailwindAnalyzer: Extract Tailwind class information
- InteractiveDetector: Find interactive elements
- EventMapper: Map event handlers
- ZIndexHierarchyBuilder: Build stacking context hierarchy
- PointerBlockageDetector: Detect pointer-events blockages

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import (
        DOMParser,
        TailwindAnalyzer,
        InteractiveDetector,
    )

    html = "<html>...</html>"
    parser = DOMParser(html)
    analyzer = TailwindAnalyzer()
    detector = InteractiveDetector()

    # Find interactive elements
    interactive = detector.find_interactive_elements(parser)

    # Analyze each element
    for item in interactive:
        info = analyzer.analyze_element(item.element)
        print(f"{item.selector}: z={info.z_index}")
"""

from .dom_parser import DOMParser
from .tailwind_analyzer import TailwindAnalyzer
from .interactive_detector import (
    InteractiveDetector,
    InteractiveElement,
    InteractionType,
)
from .event_mapper import (
    EventMapper,
    EventInfo,
)
from .zindex_hierarchy import (
    ZIndexHierarchyBuilder,
    StackingContext,
)
from .pointer_detector import (
    PointerBlockageDetector,
    BlockageInfo,
    BlockageReason,
)

__all__ = [
    # DOM Parser
    "DOMParser",
    # Tailwind Analyzer
    "TailwindAnalyzer",
    # Interactive Detector
    "InteractiveDetector",
    "InteractiveElement",
    "InteractionType",
    # Event Mapper
    "EventMapper",
    "EventInfo",
    # Z-Index Hierarchy
    "ZIndexHierarchyBuilder",
    "StackingContext",
    # Pointer Detector
    "PointerBlockageDetector",
    "BlockageInfo",
    "BlockageReason",
]
