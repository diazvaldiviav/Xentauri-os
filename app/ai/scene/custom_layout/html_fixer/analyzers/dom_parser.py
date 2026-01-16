"""
DOM Parser - HTML parsing and element selection using BeautifulSoup.

This module provides the foundation for all HTML analysis in the fixer pipeline.
It wraps BeautifulSoup with convenient methods for CSS selector queries and
source line tracking.

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import DOMParser

    parser = DOMParser(html_string)
    buttons = parser.get_elements_by_selector("button")
    for btn in buttons:
        line = parser.get_source_line(btn)
        print(f"Button at line {line}")
"""

import re
from typing import Dict, List, Optional, Any

from bs4 import BeautifulSoup, Tag, NavigableString

from ..core.selector import SelectorService


class DOMParser:
    """
    HTML parser using BeautifulSoup for DOM analysis.

    Provides methods for:
    - CSS selector queries
    - Element traversal
    - Source line number extraction
    - Parent chain analysis
    """

    def __init__(self, html: str):
        """
        Initialize parser with HTML content.

        Args:
            html: Raw HTML string to parse
        """
        self._html = html
        self._soup = BeautifulSoup(html, "html.parser")
        self._line_map = self._build_line_map()

    @property
    def soup(self) -> BeautifulSoup:
        """Access the underlying BeautifulSoup object."""
        return self._soup

    @property
    def html(self) -> str:
        """Access the original HTML string."""
        return self._html

    # =========================================================================
    # ELEMENT SELECTION
    # =========================================================================

    def get_all_elements(self) -> List[Tag]:
        """
        Get all Tag elements in the document.

        Returns:
            List of all Tag elements (excludes NavigableString, etc.)
        """
        return [el for el in self._soup.descendants if isinstance(el, Tag)]

    def get_element_by_selector(self, selector: str) -> Optional[Tag]:
        """
        Get first element matching CSS selector.

        Args:
            selector: CSS selector string (e.g., "button.primary", "#modal")

        Returns:
            First matching Tag or None
        """
        return self._soup.select_one(selector)

    def get_elements_by_selector(self, selector: str) -> List[Tag]:
        """
        Get all elements matching CSS selector.

        Args:
            selector: CSS selector string

        Returns:
            List of matching Tags (may be empty)
        """
        return self._soup.select(selector)

    def get_element_by_id(self, element_id: str) -> Optional[Tag]:
        """
        Get element by ID attribute.

        Args:
            element_id: ID value (without #)

        Returns:
            Matching Tag or None
        """
        return self._soup.find(id=element_id)

    def get_elements_by_tag(self, tag_name: str) -> List[Tag]:
        """
        Get all elements with specific tag name.

        Args:
            tag_name: HTML tag name (e.g., "button", "div")

        Returns:
            List of matching Tags
        """
        return self._soup.find_all(tag_name)

    def get_elements_by_attribute(
        self, attr: str, value: Optional[str] = None
    ) -> List[Tag]:
        """
        Get elements by attribute presence or value.

        Args:
            attr: Attribute name (e.g., "onclick", "data-option")
            value: Optional attribute value to match

        Returns:
            List of elements with the attribute
        """
        if value is not None:
            return self._soup.find_all(attrs={attr: value})
        else:
            return self._soup.find_all(attrs={attr: True})

    # =========================================================================
    # ELEMENT TRAVERSAL
    # =========================================================================

    def get_parent_chain(self, element: Tag) -> List[Tag]:
        """
        Get all ancestors of an element (excluding document root).

        Args:
            element: Starting element

        Returns:
            List of parent Tags from immediate parent to body/html
        """
        parents = []
        current = element.parent
        while current and isinstance(current, Tag):
            parents.append(current)
            current = current.parent
        return parents

    def get_children(self, element: Tag) -> List[Tag]:
        """
        Get direct children of an element.

        Args:
            element: Parent element

        Returns:
            List of direct child Tags
        """
        return [child for child in element.children if isinstance(child, Tag)]

    def get_descendants(self, element: Tag) -> List[Tag]:
        """
        Get all descendants of an element.

        Args:
            element: Root element

        Returns:
            List of all descendant Tags
        """
        return [desc for desc in element.descendants if isinstance(desc, Tag)]

    def get_siblings(self, element: Tag) -> List[Tag]:
        """
        Get all siblings of an element.

        Args:
            element: Target element

        Returns:
            List of sibling Tags (excludes the element itself)
        """
        if not element.parent:
            return []
        return [
            sib for sib in element.parent.children
            if isinstance(sib, Tag) and sib != element
        ]

    # =========================================================================
    # CONTEXT AND METADATA
    # =========================================================================

    def get_bounding_context(self, element: Tag) -> Dict[str, Any]:
        """
        Get context information about an element's position in the DOM.

        Args:
            element: Target element

        Returns:
            Dict with parent_chain, depth, sibling_index, etc.
        """
        parent_chain = self.get_parent_chain(element)
        siblings = self.get_siblings(element)

        # Find sibling index
        sibling_index = 0
        if element.parent:
            for i, child in enumerate(element.parent.children):
                if isinstance(child, Tag):
                    if child == element:
                        sibling_index = i
                        break

        return {
            "parent_chain": [p.name for p in parent_chain],
            "depth": len(parent_chain),
            "sibling_count": len(siblings),
            "sibling_index": sibling_index,
            "has_children": len(self.get_children(element)) > 0,
            "is_body_child": len(parent_chain) == 1 and parent_chain[0].name == "body",
        }

    def get_source_line(self, element: Tag) -> Optional[int]:
        """
        Get the source line number of an element.

        Note: This is an approximation based on string position.

        Args:
            element: Target element

        Returns:
            Line number (1-indexed) or None if not found
        """
        if element.sourceline is not None:
            return element.sourceline

        # Fallback: try to find in line map
        element_str = str(element)[:50]  # First 50 chars
        return self._line_map.get(element_str)

    # =========================================================================
    # SELECTOR GENERATION
    # =========================================================================

    def generate_selector(self, element: Tag) -> str:
        """
        Generate a CSS selector for an element using SelectorService.

        Priority:
        1. ID if present
        2. data-* attribute if present
        3. Tag + escaped classes + nth-child

        Args:
            element: Target element

        Returns:
            Valid CSS selector string with properly escaped Tailwind classes
        """
        element_id = element.get("id")
        classes = element.get("class", [])

        # Extract data-* attributes
        data_attrs = {
            k: v for k, v in element.attrs.items()
            if k.startswith("data-")
        }

        # Calculate nth-child if needed for uniqueness
        nth_child = None
        if not element_id and not data_attrs and element.parent:
            same_tag_siblings = [
                sib for sib in element.parent.children
                if isinstance(sib, Tag) and sib.name == element.name
            ]
            if len(same_tag_siblings) > 1:
                nth_child = same_tag_siblings.index(element) + 1

        return SelectorService.build_selector(
            tag=element.name,
            element_id=element_id,
            classes=classes,
            nth_child=nth_child,
            data_attrs=data_attrs if data_attrs else None,
            escape_classes=True,
        )

    def generate_unique_selector(self, element: Tag) -> str:
        """
        Generate a unique CSS selector using parent context.

        Uses SelectorService for proper escaping of Tailwind variant classes.

        Args:
            element: Target element

        Returns:
            Unique CSS selector string with escaped classes
        """
        # If ID exists, it should be unique
        if element.get("id"):
            return f"#{element['id']}"

        # Build path from nearest identifiable ancestor
        parts = []
        current = element

        while current and isinstance(current, Tag):
            if current.name in ("html", "body"):
                break

            if current.get("id"):
                parts.append(f"#{current['id']}")
                break

            # Use SelectorService to escape classes properly
            classes = current.get("class", [])
            selector = SelectorService.build_selector(
                tag=current.name,
                classes=classes,
                max_classes=2,
                escape_classes=True,
            )

            parts.append(selector)
            current = current.parent

        parts.reverse()
        return " > ".join(parts) if parts else element.name

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_text_content(self, element: Tag) -> str:
        """
        Get text content of an element (stripped).

        Args:
            element: Target element

        Returns:
            Text content with whitespace normalized
        """
        return element.get_text(strip=True)

    def has_class(self, element: Tag, class_name: str) -> bool:
        """
        Check if element has a specific class.

        Args:
            element: Target element
            class_name: Class to check for

        Returns:
            True if class is present
        """
        classes = element.get("class", [])
        return class_name in classes

    def get_classes(self, element: Tag) -> List[str]:
        """
        Get all classes of an element.

        Args:
            element: Target element

        Returns:
            List of class names
        """
        classes = element.get("class", [])
        return list(classes) if isinstance(classes, list) else []

    def get_attribute(self, element: Tag, attr: str) -> Optional[str]:
        """
        Get attribute value from element.

        Args:
            element: Target element
            attr: Attribute name

        Returns:
            Attribute value or None
        """
        value = element.get(attr)
        if isinstance(value, list):
            return " ".join(value)
        return value

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _build_line_map(self) -> Dict[str, int]:
        """
        Build a mapping of element snippets to line numbers.

        This is a fallback for when sourceline is not available.
        """
        line_map = {}
        lines = self._html.split("\n")

        for i, line in enumerate(lines, 1):
            # Find element openings in this line
            tag_matches = re.findall(r"<(\w+)[^>]*>", line)
            for match in tag_matches:
                # Store first 50 chars as key
                start = line.find(f"<{match}")
                if start >= 0:
                    snippet = line[start:start + 50]
                    line_map[snippet] = i

        return line_map

    def __repr__(self) -> str:
        """String representation."""
        element_count = len(self.get_all_elements())
        return f"DOMParser({element_count} elements)"
