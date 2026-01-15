"""
Tailwind Analyzer - Extract and analyze Tailwind CSS classes from HTML elements.

This module analyzes HTML elements to extract Tailwind class information
and detect missing recommended classes for different element types.

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import TailwindAnalyzer

    analyzer = TailwindAnalyzer()
    info = analyzer.analyze_element(button_element)
    print(f"z-index: {info.z_index}")
    print(f"missing: {info.missing_recommended}")
"""

import re
from typing import Set, Optional, List

from bs4 import Tag

from ..contracts.validation import TailwindInfo
from ..tailwind_rules import TailwindFixes


class TailwindAnalyzer:
    """
    Analyzes Tailwind CSS classes on HTML elements.

    Extracts:
    - z-index values
    - Positioning classes
    - Pointer-events classes
    - Transform/3D classes
    - Missing recommended classes
    """

    # Pattern to extract z-index from Tailwind classes
    Z_INDEX_PATTERN = re.compile(r"^z-(\d+|auto|\[\d+\])$")

    # Classes that interactive elements should have
    INTERACTIVE_RECOMMENDED = {"relative", "z-10"}

    # Classes that overlays should have (to not block clicks)
    OVERLAY_RECOMMENDED = {"pointer-events-none"}

    # Classes that modal content should have
    MODAL_CONTENT_RECOMMENDED = {"relative", "z-50"}

    # =========================================================================
    # MAIN ANALYSIS
    # =========================================================================

    def analyze_element(self, element: Tag) -> TailwindInfo:
        """
        Analyze an element and extract Tailwind class information.

        Args:
            element: BeautifulSoup Tag to analyze

        Returns:
            TailwindInfo with all extracted information
        """
        classes = self._get_classes(element)

        # Extract z-index
        z_index = self._extract_z_index(classes)

        # Build TailwindInfo
        info = TailwindInfo(
            all_classes=classes,
            z_index=z_index,
            has_pointer_none="pointer-events-none" in classes,
            has_pointer_auto="pointer-events-auto" in classes,
            has_relative="relative" in classes,
            has_absolute="absolute" in classes,
            has_fixed="fixed" in classes,
            has_transform=self._has_transform(classes),
            has_preserve_3d="[transform-style:preserve-3d]" in classes,
            has_backface_hidden="[backface-visibility:hidden]" in classes,
            missing_recommended=[],
        )

        # Detect missing classes based on element type
        info.missing_recommended = self._detect_missing_classes(element, info)

        return info

    def analyze_elements(self, elements: List[Tag]) -> List[TailwindInfo]:
        """
        Analyze multiple elements.

        Args:
            elements: List of BeautifulSoup Tags

        Returns:
            List of TailwindInfo for each element
        """
        return [self.analyze_element(el) for el in elements]

    # =========================================================================
    # Z-INDEX EXTRACTION
    # =========================================================================

    def _extract_z_index(self, classes: Set[str]) -> Optional[int]:
        """
        Extract z-index value from Tailwind classes.

        Handles:
        - Standard: z-10, z-20, z-50
        - Arbitrary: z-[100], z-[9999]
        - Special: z-auto (returns None)

        Args:
            classes: Set of class names

        Returns:
            Integer z-index value or None
        """
        for cls in classes:
            match = self.Z_INDEX_PATTERN.match(cls)
            if match:
                value = match.group(1)

                if value == "auto":
                    return None

                # Handle arbitrary values like z-[100]
                if value.startswith("[") and value.endswith("]"):
                    try:
                        return int(value[1:-1])
                    except ValueError:
                        return None

                # Handle standard values like z-50
                try:
                    return int(value)
                except ValueError:
                    return None

        return None

    def get_zindex_class(self, element: Tag) -> Optional[str]:
        """
        Get the z-index class from an element.

        Args:
            element: BeautifulSoup Tag

        Returns:
            The z-index class (e.g., "z-50") or None
        """
        classes = self._get_classes(element)
        for cls in classes:
            if self.Z_INDEX_PATTERN.match(cls):
                return cls
        return None

    # =========================================================================
    # ELEMENT TYPE DETECTION
    # =========================================================================

    def is_interactive(self, element: Tag) -> bool:
        """
        Determine if an element is interactive.

        Interactive elements include:
        - Buttons, links, inputs, selects, textareas
        - Elements with onclick/onmousedown handlers
        - Elements with role="button" etc.
        - Elements with cursor-pointer class

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element should receive clicks
        """
        tag = element.name.lower()

        # Interactive by tag
        if tag in ("button", "a", "input", "select", "textarea"):
            return True

        # Interactive by event handler
        interactive_attrs = {"onclick", "onmousedown", "onmouseup", "ontouchstart"}
        if any(element.get(attr) for attr in interactive_attrs):
            return True

        # Interactive by role
        role = element.get("role", "").lower()
        if role in ("button", "link", "checkbox", "radio", "tab", "menuitem"):
            return True

        # Interactive by cursor class
        classes = self._get_classes(element)
        if "cursor-pointer" in classes:
            return True

        return False

    def is_overlay(self, element: Tag, info: Optional[TailwindInfo] = None) -> bool:
        """
        Determine if an element is a decorative overlay.

        Overlays are typically:
        - Absolute or fixed positioned
        - Have inset-0 (covering parent/viewport)
        - Often have gradient or background classes

        Args:
            element: BeautifulSoup Tag
            info: Pre-computed TailwindInfo (optional)

        Returns:
            True if element appears to be an overlay
        """
        if info is None:
            info = self.analyze_element(element)

        classes = info.all_classes

        # Must be positioned
        if not (info.has_absolute or info.has_fixed):
            return False

        # Must cover area (inset-0 or top-0 left-0 right-0 bottom-0)
        has_inset = "inset-0" in classes
        has_manual_inset = all(
            cls in classes for cls in ["top-0", "left-0", "right-0", "bottom-0"]
        )

        if not (has_inset or has_manual_inset):
            return False

        return True

    def is_modal_backdrop(self, element: Tag) -> bool:
        """
        Determine if an element is a modal backdrop.

        Modal backdrops typically:
        - Cover the viewport (fixed inset-0)
        - Have semi-transparent background (bg-black/50, etc.)
        - Have high z-index

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element appears to be a modal backdrop
        """
        classes = self._get_classes(element)

        # Must be fixed and cover viewport
        if "fixed" not in classes:
            return False

        if "inset-0" not in classes:
            return False

        # Usually has dark background
        has_bg = any(cls.startswith("bg-") for cls in classes)

        return has_bg

    def is_modal_content(self, element: Tag) -> bool:
        """
        Determine if an element is modal content (not backdrop).

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element appears to be modal content
        """
        classes = self._get_classes(element)

        # Usually has relative positioning
        if "relative" not in classes:
            return False

        # Usually has background and rounded corners
        has_bg = any(cls.startswith("bg-") for cls in classes)
        has_rounded = any(cls.startswith("rounded") for cls in classes)

        return has_bg and has_rounded

    # =========================================================================
    # MISSING CLASS DETECTION
    # =========================================================================

    def _detect_missing_classes(
        self, element: Tag, info: TailwindInfo
    ) -> List[str]:
        """
        Detect recommended classes that are missing.

        Args:
            element: BeautifulSoup Tag
            info: TailwindInfo for the element

        Returns:
            List of missing recommended classes
        """
        missing = []

        # Interactive elements should have relative + z-index
        if self.is_interactive(element):
            for cls in self.INTERACTIVE_RECOMMENDED:
                if cls not in info.all_classes:
                    # Check if any z-index is present (z-10 is just default)
                    if cls == "z-10" and info.z_index is not None:
                        continue
                    missing.append(cls)

        # Decorative overlays should have pointer-events-none
        if self.is_overlay(element, info):
            # Only if not a modal backdrop (which SHOULD block)
            if not self.is_modal_backdrop(element):
                for cls in self.OVERLAY_RECOMMENDED:
                    if cls not in info.all_classes:
                        missing.append(cls)

        # Modal content should have high z-index
        if self.is_modal_content(element):
            if info.z_index is None or info.z_index < 50:
                if "z-50" not in info.all_classes:
                    missing.append("z-50")

        return missing

    def get_recommended_classes(self, element: Tag) -> List[str]:
        """
        Get all recommended classes for an element.

        Args:
            element: BeautifulSoup Tag

        Returns:
            List of recommended classes (regardless of current state)
        """
        recommendations = []

        if self.is_interactive(element):
            recommendations.extend(self.INTERACTIVE_RECOMMENDED)

        if self.is_overlay(element):
            if not self.is_modal_backdrop(element):
                recommendations.extend(self.OVERLAY_RECOMMENDED)

        if self.is_modal_content(element):
            recommendations.extend(self.MODAL_CONTENT_RECOMMENDED)

        return list(set(recommendations))

    # =========================================================================
    # TRANSFORM DETECTION
    # =========================================================================

    def _has_transform(self, classes: Set[str]) -> bool:
        """
        Check if element has any transform-related classes.

        Args:
            classes: Set of class names

        Returns:
            True if any transform class is present
        """
        transform_patterns = [
            "transform",
            "rotate-",
            "scale-",
            "translate-",
            "skew-",
            "-rotate-",
            "-translate-",
        ]

        for cls in classes:
            for pattern in transform_patterns:
                if pattern in cls:
                    return True

        return False

    def has_3d_transform_issue(self, element: Tag) -> bool:
        """
        Check if element might have 3D transform visibility issues.

        Issues occur when:
        - Element has 3D transforms (rotateX/Y)
        - Parent lacks preserve-3d
        - Element lacks proper backface-visibility

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if potential 3D issue detected
        """
        classes = self._get_classes(element)

        # Check for 3D rotation classes
        has_3d_rotation = any(
            "rotate" in cls and ("x" in cls.lower() or "y" in cls.lower())
            for cls in classes
        )

        if not has_3d_rotation:
            return False

        # Check parent for preserve-3d
        parent = element.parent
        if parent and isinstance(parent, Tag):
            parent_classes = self._get_classes(parent)
            if "[transform-style:preserve-3d]" not in parent_classes:
                return True

        return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _get_classes(self, element: Tag) -> Set[str]:
        """
        Get all classes from an element as a set.

        Args:
            element: BeautifulSoup Tag

        Returns:
            Set of class names
        """
        classes = element.get("class", [])
        if isinstance(classes, list):
            return set(classes)
        elif isinstance(classes, str):
            return set(classes.split())
        return set()

    def compare_zindex(
        self, element1: Tag, element2: Tag
    ) -> int:
        """
        Compare z-index of two elements.

        Args:
            element1: First element
            element2: Second element

        Returns:
            -1 if element1 < element2
             0 if equal
             1 if element1 > element2
        """
        z1 = self._extract_z_index(self._get_classes(element1))
        z2 = self._extract_z_index(self._get_classes(element2))

        # None is treated as 0
        z1 = z1 or 0
        z2 = z2 or 0

        if z1 < z2:
            return -1
        elif z1 > z2:
            return 1
        return 0

    def __repr__(self) -> str:
        """String representation."""
        return "TailwindAnalyzer()"
