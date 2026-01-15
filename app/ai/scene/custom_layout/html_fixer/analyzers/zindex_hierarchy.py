"""
Z-Index Hierarchy Builder - Analyze stacking context hierarchy.

This module builds a tree representation of the z-index stacking contexts
in an HTML document, enabling detection of z-index conflicts.

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import (
        ZIndexHierarchyBuilder,
        DOMParser
    )

    parser = DOMParser(html_string)
    builder = ZIndexHierarchyBuilder()
    hierarchy = builder.build_hierarchy(parser)
    conflicts = builder.find_conflicts()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from bs4 import Tag

from .dom_parser import DOMParser
from .tailwind_analyzer import TailwindAnalyzer


@dataclass
class StackingContext:
    """
    Represents a CSS stacking context.

    A stacking context is created by elements with:
    - position: relative/absolute/fixed AND z-index != auto
    - opacity < 1
    - transform, filter, etc.

    In Tailwind, this typically means:
    - Elements with both position class AND z-* class
    """

    element: Tag
    """The element creating this stacking context."""

    selector: str
    """CSS selector for the element."""

    z_index: Optional[int]
    """The z-index value (None if auto/not set)."""

    depth: int
    """Depth in the stacking context tree (root = 0)."""

    children: List["StackingContext"] = field(default_factory=list)
    """Child stacking contexts."""

    parent: Optional["StackingContext"] = None
    """Parent stacking context (None for root)."""

    def __repr__(self) -> str:
        """String representation."""
        z = self.z_index if self.z_index is not None else "auto"
        return f"StackingContext({self.selector}, z={z}, depth={self.depth})"

    @property
    def effective_z_index(self) -> int:
        """Get effective z-index (0 if not set)."""
        return self.z_index if self.z_index is not None else 0


class ZIndexHierarchyBuilder:
    """
    Builds and analyzes z-index stacking context hierarchies.

    Provides methods to:
    - Build the stacking context tree
    - Find elements at specific z-index levels
    - Detect z-index conflicts between elements
    """

    def __init__(self):
        """Initialize the builder."""
        self._analyzer = TailwindAnalyzer()
        self._parser: Optional[DOMParser] = None
        self._root: Optional[StackingContext] = None
        self._element_map: Dict[Tag, StackingContext] = {}
        self._zindex_groups: Dict[int, List[StackingContext]] = {}

    @property
    def root(self) -> Optional[StackingContext]:
        """Get the root stacking context."""
        return self._root

    # =========================================================================
    # HIERARCHY BUILDING
    # =========================================================================

    def build_hierarchy(self, parser: DOMParser) -> StackingContext:
        """
        Build the stacking context hierarchy from HTML.

        Args:
            parser: DOMParser instance with loaded HTML

        Returns:
            Root StackingContext (represents the document)
        """
        self._parser = parser
        self._element_map = {}
        self._zindex_groups = {}

        # Create root context (document body)
        body = parser.get_element_by_selector("body")
        if not body:
            # Create virtual root if no body
            body = parser.soup

        self._root = StackingContext(
            element=body,
            selector="body",
            z_index=0,
            depth=0,
        )
        self._element_map[body] = self._root
        self._add_to_zindex_group(self._root)

        # Build tree recursively
        self._build_subtree(parser.get_all_elements(), self._root)

        return self._root

    def _build_subtree(
        self,
        elements: List[Tag],
        parent_context: StackingContext
    ) -> None:
        """
        Recursively build stacking context subtree.

        Args:
            elements: All elements in document
            parent_context: Parent stacking context
        """
        for element in elements:
            # Skip already processed
            if element in self._element_map:
                continue

            # Check if element creates a stacking context
            if self._creates_stacking_context(element):
                info = self._analyzer.analyze_element(element)

                context = StackingContext(
                    element=element,
                    selector=self._parser.generate_selector(element),
                    z_index=info.z_index,
                    depth=parent_context.depth + 1,
                    parent=parent_context,
                )

                # Find correct parent context
                actual_parent = self._find_parent_context(element)
                if actual_parent:
                    context.parent = actual_parent
                    context.depth = actual_parent.depth + 1
                    actual_parent.children.append(context)
                else:
                    parent_context.children.append(context)

                self._element_map[element] = context
                self._add_to_zindex_group(context)

    def _creates_stacking_context(self, element: Tag) -> bool:
        """
        Check if element creates a new stacking context.

        In CSS, stacking contexts are created by:
        - position (relative/absolute/fixed/sticky) + z-index != auto
        - opacity < 1
        - transform, filter, perspective
        - will-change

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element creates stacking context
        """
        info = self._analyzer.analyze_element(element)

        # Position + z-index
        if info.is_positioned and info.z_index is not None:
            return True

        # Check for opacity (Tailwind opacity-* classes)
        classes = info.all_classes
        for cls in classes:
            if cls.startswith("opacity-"):
                # opacity-100 doesn't create context, others do
                if cls != "opacity-100":
                    return True

        # Check for transform
        if info.has_transform:
            return True

        return False

    def _find_parent_context(self, element: Tag) -> Optional[StackingContext]:
        """
        Find the nearest ancestor that is a stacking context.

        Args:
            element: BeautifulSoup Tag

        Returns:
            Parent StackingContext or None
        """
        parent = element.parent
        while parent:
            if parent in self._element_map:
                return self._element_map[parent]
            parent = parent.parent
        return None

    def _add_to_zindex_group(self, context: StackingContext) -> None:
        """
        Add context to z-index grouping.

        Args:
            context: StackingContext to add
        """
        z = context.effective_z_index
        if z not in self._zindex_groups:
            self._zindex_groups[z] = []
        self._zindex_groups[z].append(context)

    # =========================================================================
    # ELEMENT QUERIES
    # =========================================================================

    def get_elements_at_zindex(self, z: int) -> List[Tag]:
        """
        Get all elements at a specific z-index level.

        Args:
            z: Z-index value to query

        Returns:
            List of elements at that z-index
        """
        if z not in self._zindex_groups:
            return []
        return [ctx.element for ctx in self._zindex_groups[z]]

    def get_elements_above(self, element: Tag) -> List[Tag]:
        """
        Get elements with higher z-index than target.

        Args:
            element: Target element

        Returns:
            List of elements above this one
        """
        if element not in self._element_map:
            return []

        target_z = self._element_map[element].effective_z_index
        results = []

        for z, contexts in self._zindex_groups.items():
            if z > target_z:
                results.extend(ctx.element for ctx in contexts)

        return results

    def get_elements_below(self, element: Tag) -> List[Tag]:
        """
        Get elements with lower z-index than target.

        Args:
            element: Target element

        Returns:
            List of elements below this one
        """
        if element not in self._element_map:
            return []

        target_z = self._element_map[element].effective_z_index
        results = []

        for z, contexts in self._zindex_groups.items():
            if z < target_z:
                results.extend(ctx.element for ctx in contexts)

        return results

    def get_elements_at_same_level(self, element: Tag) -> List[Tag]:
        """
        Get elements with same z-index as target.

        Args:
            element: Target element

        Returns:
            List of elements at same z-index (excluding target)
        """
        if element not in self._element_map:
            return []

        target_z = self._element_map[element].effective_z_index

        if target_z not in self._zindex_groups:
            return []

        return [
            ctx.element for ctx in self._zindex_groups[target_z]
            if ctx.element != element
        ]

    def get_zindex_for_element(self, element: Tag) -> Optional[int]:
        """
        Get z-index for a specific element.

        Args:
            element: Target element

        Returns:
            Z-index value or None
        """
        if element in self._element_map:
            return self._element_map[element].z_index
        return None

    # =========================================================================
    # CONFLICT DETECTION
    # =========================================================================

    def find_conflicts(self) -> List[Tuple[Tag, Tag]]:
        """
        Find elements that may have z-index conflicts.

        Conflicts occur when:
        - Two elements at same z-index overlap visually
        - An overlay doesn't have pointer-events-none
        - Interactive elements are below overlays

        Returns:
            List of (element1, element2) tuples representing conflicts
        """
        conflicts = []

        # Check each z-index group for conflicts
        for z, contexts in self._zindex_groups.items():
            if len(contexts) > 1:
                # Multiple elements at same z-index
                for i, ctx1 in enumerate(contexts):
                    for ctx2 in contexts[i + 1:]:
                        if self._may_overlap(ctx1.element, ctx2.element):
                            conflicts.append((ctx1.element, ctx2.element))

        return conflicts

    def find_interactive_below_overlay(
        self, interactive_elements: List[Tag]
    ) -> List[Tuple[Tag, Tag]]:
        """
        Find interactive elements that are below overlays.

        Args:
            interactive_elements: List of interactive elements

        Returns:
            List of (interactive, overlay) tuples
        """
        conflicts = []

        for element in interactive_elements:
            above = self.get_elements_above(element)
            for other in above:
                if self._is_potential_overlay(other):
                    conflicts.append((element, other))

        return conflicts

    def _may_overlap(self, el1: Tag, el2: Tag) -> bool:
        """
        Check if two elements may overlap visually.

        This is a heuristic based on Tailwind classes since
        we don't have actual computed positions.

        Args:
            el1: First element
            el2: Second element

        Returns:
            True if elements might overlap
        """
        info1 = self._analyzer.analyze_element(el1)
        info2 = self._analyzer.analyze_element(el2)

        # Fixed/absolute positioned elements likely overlap
        if info1.has_fixed and info2.has_fixed:
            return True
        if info1.has_absolute and info2.has_absolute:
            return True

        # Check for inset-0 (full coverage)
        classes1 = info1.all_classes
        classes2 = info2.all_classes

        if "inset-0" in classes1 or "inset-0" in classes2:
            return True

        return False

    def _is_potential_overlay(self, element: Tag) -> bool:
        """
        Check if element is a potential overlay.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element looks like an overlay
        """
        info = self._analyzer.analyze_element(element)

        # Must be positioned
        if not (info.has_absolute or info.has_fixed):
            return False

        # Must cover area
        classes = info.all_classes
        if "inset-0" in classes:
            return True

        return False

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def get_sorted_zindexes(self) -> List[int]:
        """
        Get all z-index values in sorted order.

        Returns:
            Sorted list of z-index values
        """
        return sorted(self._zindex_groups.keys())

    def get_max_zindex(self) -> int:
        """
        Get the maximum z-index in the document.

        Returns:
            Maximum z-index value or 0
        """
        if not self._zindex_groups:
            return 0
        return max(self._zindex_groups.keys())

    def get_min_zindex(self) -> int:
        """
        Get the minimum z-index in the document.

        Returns:
            Minimum z-index value or 0
        """
        if not self._zindex_groups:
            return 0
        return min(self._zindex_groups.keys())

    def describe_hierarchy(self) -> str:
        """
        Generate a text description of the hierarchy.

        Returns:
            Multi-line string describing the hierarchy
        """
        if not self._root:
            return "No hierarchy built"

        lines = ["Z-Index Hierarchy:"]
        self._describe_context(self._root, lines, "")
        return "\n".join(lines)

    def _describe_context(
        self,
        context: StackingContext,
        lines: List[str],
        indent: str
    ) -> None:
        """
        Recursively describe a stacking context.

        Args:
            context: Context to describe
            lines: List to append lines to
            indent: Current indentation
        """
        z = context.z_index if context.z_index is not None else "auto"
        lines.append(f"{indent}{context.selector} (z={z})")

        for child in sorted(context.children, key=lambda c: c.effective_z_index):
            self._describe_context(child, lines, indent + "  ")

    def __repr__(self) -> str:
        """String representation."""
        if self._root:
            count = len(self._element_map)
            return f"ZIndexHierarchyBuilder({count} contexts)"
        return "ZIndexHierarchyBuilder(not built)"
