"""
Pointer Detector - Detect elements blocking pointer events.

This module analyzes HTML to find elements that may be blocking
clicks from reaching interactive elements (overlays, z-index issues, etc.)

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import (
        PointerBlockageDetector,
        DOMParser,
        InteractiveDetector
    )

    parser = DOMParser(html_string)
    detector = InteractiveDetector()
    interactive = detector.find_interactive_elements(parser)

    blocker = PointerBlockageDetector()
    blockages = blocker.find_blocked_elements(parser, interactive)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Tuple

from bs4 import Tag

from .dom_parser import DOMParser
from .tailwind_analyzer import TailwindAnalyzer
from .interactive_detector import InteractiveElement


class BlockageReason(Enum):
    """Reasons why an element might be blocked."""

    OVERLAY_BLOCKING = "overlay_blocking"
    """An overlay without pointer-events-none is covering the element."""

    ZINDEX_CONFLICT = "zindex_conflict"
    """Another element has higher z-index and overlaps."""

    PARENT_POINTER_NONE = "parent_pointer_none"
    """Parent has pointer-events-none without child override."""

    SIBLING_OVERLAP = "sibling_overlap"
    """A sibling element is overlapping."""

    MODAL_BACKDROP = "modal_backdrop"
    """Modal backdrop is blocking without proper z-index."""


@dataclass
class BlockageInfo:
    """
    Information about a blocked element.

    Describes what element is blocked, what is blocking it,
    and why.
    """

    blocked_element: Tag
    """The element that cannot receive clicks."""

    blocking_element: Optional[Tag]
    """The element causing the blockage (may be None for parent issues)."""

    reason: BlockageReason
    """Reason for the blockage."""

    blocked_selector: str
    """CSS selector for blocked element."""

    blocking_selector: Optional[str]
    """CSS selector for blocking element (if applicable)."""

    suggested_fix: str
    """Suggested fix for this blockage."""

    def __repr__(self) -> str:
        """String representation."""
        return f"BlockageInfo({self.blocked_selector} blocked by {self.reason.value})"

    def describe(self) -> str:
        """Generate human-readable description."""
        lines = [f"Blocked: {self.blocked_selector}"]
        if self.blocking_selector:
            lines.append(f"Blocker: {self.blocking_selector}")
        lines.append(f"Reason: {self.reason.value}")
        lines.append(f"Fix: {self.suggested_fix}")
        return "\n".join(lines)


class PointerBlockageDetector:
    """
    Detects elements that block pointer events.

    Analyzes HTML to find:
    - Overlays blocking interactive elements
    - Z-index conflicts
    - Pointer-events inheritance issues
    """

    def __init__(self):
        """Initialize the detector."""
        self._analyzer = TailwindAnalyzer()

    # =========================================================================
    # MAIN DETECTION
    # =========================================================================

    def find_blocked_elements(
        self,
        parser: DOMParser,
        interactive: List[InteractiveElement],
    ) -> List[BlockageInfo]:
        """
        Find all interactive elements that may be blocked.

        Args:
            parser: DOMParser instance
            interactive: List of interactive elements to check

        Returns:
            List of BlockageInfo for blocked elements
        """
        blockages = []

        # Find all potential blockers (overlays, high z-index elements)
        potential_blockers = self._find_potential_blockers(parser)

        for item in interactive:
            # Check overlay blockage
            overlay_blockage = self._check_overlay_blockage(
                item.element, potential_blockers, parser
            )
            if overlay_blockage:
                blockages.append(overlay_blockage)
                continue

            # Check z-index conflicts
            zindex_blockage = self._check_zindex_blockage(
                item.element, potential_blockers, parser
            )
            if zindex_blockage:
                blockages.append(zindex_blockage)
                continue

            # Check parent pointer-events inheritance
            parent_blockage = self._check_parent_pointer_none(item.element, parser)
            if parent_blockage:
                blockages.append(parent_blockage)

        return blockages

    def _find_potential_blockers(self, parser: DOMParser) -> List[Tag]:
        """
        Find elements that could potentially block others.

        Potential blockers:
        - Elements with inset-0 (full coverage overlays)
        - Elements with high z-index
        - Fixed/absolute positioned elements

        Args:
            parser: DOMParser instance

        Returns:
            List of potential blocking elements
        """
        blockers = []

        for element in parser.get_all_elements():
            info = self._analyzer.analyze_element(element)
            classes = info.all_classes

            # Skip if has pointer-events-none (pass-through)
            if info.has_pointer_none:
                continue

            # Check if covering element
            is_covering = "inset-0" in classes

            # Check positioning
            is_positioned = info.has_absolute or info.has_fixed

            if is_covering and is_positioned:
                blockers.append(element)
            elif info.z_index is not None and info.z_index >= 40:
                # High z-index elements
                blockers.append(element)

        return blockers

    # =========================================================================
    # BLOCKAGE CHECKS
    # =========================================================================

    def _check_overlay_blockage(
        self,
        element: Tag,
        potential_blockers: List[Tag],
        parser: DOMParser,
    ) -> Optional[BlockageInfo]:
        """
        Check if element is blocked by an overlay.

        Args:
            element: Element to check
            potential_blockers: List of potential blocking elements
            parser: DOMParser instance

        Returns:
            BlockageInfo if blocked, None otherwise
        """
        element_info = self._analyzer.analyze_element(element)
        element_z = element_info.z_index or 0

        best: Optional[Tuple[Tag, str, int, Optional[int]]] = None
        # Tuple: (blocker_tag, blocker_selector, line_number, blocker_z)

        for blocker in potential_blockers:
            # Skip self
            if blocker == element:
                continue

            blocker_info = self._analyzer.analyze_element(blocker)

            # Check if blocker is an overlay
            if not self._is_blocking_overlay(blocker):
                continue

            # Overlay scope: absolute inset-0 overlays only cover their containing block.
            # Avoid false positives where an overlay in one section "blocks" buttons in another.
            if not blocker_info.has_fixed:
                container = self._find_containing_block(blocker)
                if container is not None and not self._is_descendant_of(element, container):
                    continue

            # Check z-index relationship
            blocker_z = blocker_info.z_index or 0

            # Overlay at same or higher z-index blocks
            if blocker_z >= element_z:
                # Check if they share context (same container)
                if self._share_stacking_context(element, blocker):
                    selector = parser.generate_selector(blocker)
                    line = parser.get_source_line(blocker) or 0
                    if best is None:
                        best = (blocker, selector, line, blocker_z)
                    else:
                        _, _, best_line, best_z = best
                        best_z_val = best_z or 0
                        # Prefer highest z-index; tie-break by later appearance in DOM (line number)
                        if (blocker_z, line) > (best_z_val, best_line):
                            best = (blocker, selector, line, blocker_z)

        if best is None:
            return None

        best_blocker, best_selector, _, _ = best
        blocked_selector = parser.generate_selector(element)

        return BlockageInfo(
            blocked_element=element,
            blocking_element=best_blocker,
            reason=BlockageReason.OVERLAY_BLOCKING,
            blocked_selector=blocked_selector,
            blocking_selector=best_selector,
            suggested_fix=(
                f"Add 'pointer-events-none' to {best_selector} "
                f"or increase z-index on {blocked_selector}"
            ),
        )

    def _check_zindex_blockage(
        self,
        element: Tag,
        potential_blockers: List[Tag],
        parser: DOMParser,
    ) -> Optional[BlockageInfo]:
        """
        Check if element is blocked by z-index conflict.

        Args:
            element: Element to check
            potential_blockers: List of potential blocking elements
            parser: DOMParser instance

        Returns:
            BlockageInfo if blocked, None otherwise
        """
        element_info = self._analyzer.analyze_element(element)
        element_z = element_info.z_index or 0

        for blocker in potential_blockers:
            if blocker == element:
                continue

            blocker_info = self._analyzer.analyze_element(blocker)
            blocker_z = blocker_info.z_index or 0

            # Only check elements with higher z-index
            if blocker_z <= element_z:
                continue

            # Check if they might overlap
            if self._elements_may_overlap(element, blocker):
                return BlockageInfo(
                    blocked_element=element,
                    blocking_element=blocker,
                    reason=BlockageReason.ZINDEX_CONFLICT,
                    blocked_selector=parser.generate_selector(element),
                    blocking_selector=parser.generate_selector(blocker),
                    suggested_fix=(
                        f"Increase z-index on {parser.generate_selector(element)} "
                        f"to z-{blocker_z + 10} or higher"
                    ),
                )

        return None

    def _check_parent_pointer_none(
        self,
        element: Tag,
        parser: DOMParser,
    ) -> Optional[BlockageInfo]:
        """
        Check if element inherits pointer-events-none from parent.

        Args:
            element: Element to check
            parser: DOMParser instance

        Returns:
            BlockageInfo if blocked by parent, None otherwise
        """
        element_info = self._analyzer.analyze_element(element)

        # If element has pointer-events-auto, it overrides parent
        if element_info.has_pointer_auto:
            return None

        # Check parent chain
        parent = element.parent
        while parent and isinstance(parent, Tag):
            parent_info = self._analyzer.analyze_element(parent)

            if parent_info.has_pointer_none:
                return BlockageInfo(
                    blocked_element=element,
                    blocking_element=parent,
                    reason=BlockageReason.PARENT_POINTER_NONE,
                    blocked_selector=parser.generate_selector(element),
                    blocking_selector=parser.generate_selector(parent),
                    suggested_fix=(
                        f"Add 'pointer-events-auto' to {parser.generate_selector(element)}"
                    ),
                )

            parent = parent.parent

        return None

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _is_blocking_overlay(self, element: Tag) -> bool:
        """
        Check if element is an overlay that blocks clicks.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element is a blocking overlay
        """
        info = self._analyzer.analyze_element(element)
        classes = info.all_classes

        # Must be positioned and covering
        if not (info.has_absolute or info.has_fixed):
            return False

        if "inset-0" not in classes:
            return False

        # Must NOT have pointer-events-none
        if info.has_pointer_none:
            return False

        return True

    def _share_stacking_context(self, el1: Tag, el2: Tag) -> bool:
        """
        Check if two elements share a stacking context.

        Elements in same stacking context can potentially overlap.

        Args:
            el1: First element
            el2: Second element

        Returns:
            True if elements might be in same stacking context
        """
        info2 = self._analyzer.analyze_element(el2)
        # Fixed overlays can block across the viewport
        if info2.has_fixed:
            return True

        # Absolute inset-0 overlays only cover their containing block
        container = self._find_containing_block(el2)
        if container is None:
            return True

        return self._is_descendant_of(el1, container)

    def _find_containing_block(self, element: Tag) -> Optional[Tag]:
        """
        Find the nearest positioned ancestor that acts as the containing block.

        For absolute positioned elements, this is the nearest ancestor with
        position != static (relative/absolute/fixed in Tailwind terms).
        Returns None if not found (treat as global scope).
        """
        current = element.parent
        while current and isinstance(current, Tag):
            info = self._analyzer.analyze_element(current)
            if info.is_positioned:
                return current
            current = current.parent
        return None

    def _is_descendant_of(self, element: Tag, ancestor: Tag) -> bool:
        """Return True if `ancestor` is in `element`'s parent chain."""
        current = element
        while current and isinstance(current, Tag):
            if current == ancestor:
                return True
            current = current.parent
        return False

    def _get_parent_chain(self, element: Tag) -> Set[Tag]:
        """
        Get set of all parent elements.

        Args:
            element: Starting element

        Returns:
            Set of parent Tags
        """
        parents = set()
        current = element.parent
        while current and isinstance(current, Tag):
            parents.add(current)
            current = current.parent
        return parents

    def _elements_may_overlap(self, el1: Tag, el2: Tag) -> bool:
        """
        Check if two elements may visually overlap.

        This is a heuristic since we don't have actual positions.

        Args:
            el1: First element
            el2: Second element

        Returns:
            True if elements might overlap
        """
        info1 = self._analyzer.analyze_element(el1)
        info2 = self._analyzer.analyze_element(el2)

        classes1 = info1.all_classes
        classes2 = info2.all_classes

        # Full-coverage elements overlap with everything
        if "inset-0" in classes1 or "inset-0" in classes2:
            return True

        # Both fixed means they share viewport space
        if info1.has_fixed and info2.has_fixed:
            return True

        # Same parent with absolute positioning
        if el1.parent == el2.parent:
            if info1.has_absolute and info2.has_absolute:
                return True

        return False

    def check_pointer_inheritance(self, element: Tag) -> bool:
        """
        Check if element can receive pointer events.

        Traverses parent chain to check for pointer-events-none
        that might block the element.

        Args:
            element: Element to check

        Returns:
            True if element can receive pointer events
        """
        element_info = self._analyzer.analyze_element(element)

        # Explicit pointer-events-auto allows events
        if element_info.has_pointer_auto:
            return True

        # Check for blocking parent
        parent = element.parent
        while parent and isinstance(parent, Tag):
            parent_info = self._analyzer.analyze_element(parent)

            if parent_info.has_pointer_none:
                return False

            parent = parent.parent

        return True

    def find_overlays_without_passthrough(
        self, parser: DOMParser
    ) -> List[Tag]:
        """
        Find overlays that don't have pointer-events-none.

        Args:
            parser: DOMParser instance

        Returns:
            List of blocking overlays
        """
        overlays = []

        for element in parser.get_all_elements():
            if self._is_blocking_overlay(element):
                overlays.append(element)

        return overlays

    def __repr__(self) -> str:
        """String representation."""
        return "PointerBlockageDetector()"
