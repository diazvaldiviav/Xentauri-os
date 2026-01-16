"""
TailwindPatchValidator - Validates Tailwind CSS patches before application.

Sprint 6: Ensures LLM-generated Tailwind patches are safe and valid.
"""

import logging
import re
from typing import List

from bs4 import BeautifulSoup

from ....contracts.patches import TailwindPatch

logger = logging.getLogger(__name__)


class TailwindPatchValidator:
    """
    Validates Tailwind CSS patches before application.

    Checks that:
    - Selectors exist in the HTML
    - Classes are valid Tailwind classes
    - Patches don't break functionality
    """

    # Valid Tailwind class patterns
    VALID_PATTERNS = [
        # State variants
        r"^(hover|active|focus|disabled|group-hover|focus-within|focus-visible):[a-z]+-[a-z0-9-]+$",
        r"^(hover|active|focus|disabled):[a-z]+-\[[^\]]+\]$",  # Arbitrary values with variants

        # Standard utility classes
        r"^[a-z]+-[0-9]+$",                    # z-50, p-4, m-2
        r"^[a-z]+-[a-z]+$",                    # text-white, bg-red
        r"^[a-z]+-[a-z]+-[0-9]+$",             # bg-blue-500, text-gray-700
        r"^-?[a-z]+-[0-9.]+$",                 # -translate-y-1, scale-95

        # Transitions and animations
        r"^transition(-[a-z]+)?$",              # transition, transition-all
        r"^duration-[0-9]+$",                   # duration-150
        r"^ease-(in|out|in-out|linear)$",       # ease-in-out
        r"^delay-[0-9]+$",                      # delay-150

        # Transform classes
        r"^scale-[0-9]+$",                      # scale-95
        r"^-?translate-[xy]-[0-9.]+$",          # translate-y-1
        r"^rotate-[0-9]+$",                     # rotate-45
        r"^skew-[xy]-[0-9]+$",                  # skew-x-12

        # Arbitrary values
        r"^\[[a-z-]+:[^\]]+\]$",                # [color:#fff], [transform:scale(1.1)]

        # Shadow classes
        r"^shadow(-[a-z]+)?$",                  # shadow, shadow-lg
        r"^shadow-[a-z]+-[0-9]+(/[0-9]+)?$",    # shadow-blue-500/50

        # Ring classes (focus rings)
        r"^ring(-[0-9]+)?$",                    # ring, ring-2
        r"^ring-[a-z]+-[0-9]+$",                # ring-blue-500
        r"^ring-offset-[0-9]+$",                # ring-offset-2

        # Outline classes
        r"^outline(-[a-z]+)?$",                 # outline-none

        # Opacity and brightness
        r"^opacity-[0-9]+$",                    # opacity-50
        r"^brightness-[0-9]+$",                 # brightness-75

        # Cursor
        r"^cursor-[a-z]+$",                     # cursor-pointer

        # Pointer events
        r"^pointer-events-(none|auto)$",        # pointer-events-auto
    ]

    # Classes that should never be added to interactive elements
    FORBIDDEN_INTERACTIVE_CLASSES = [
        "hidden",
        "invisible",
        "opacity-0",
        "pointer-events-none",
        "sr-only",
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: If True, reject unknown classes. If False, warn only.
        """
        self.strict_mode = strict_mode
        self._compiled_patterns = [re.compile(p) for p in self.VALID_PATTERNS]

    def validate(self, patch: TailwindPatch, html: str) -> bool:
        """
        Validate a Tailwind patch.

        Args:
            patch: The patch to validate
            html: Original HTML content

        Returns:
            True if patch is valid, False otherwise
        """
        # Check selector exists
        if not self._selector_exists(patch.selector, html):
            logger.warning(f"Selector not found in HTML: {patch.selector}")
            return False

        # Check all added classes are valid
        for cls in patch.add_classes:
            if not self._is_valid_class(cls):
                if self.strict_mode:
                    logger.warning(f"Invalid Tailwind class: {cls}")
                    return False
                else:
                    logger.info(f"Unknown Tailwind class (allowing): {cls}")

        # Check for forbidden classes on interactive elements
        if self._is_interactive_selector(patch.selector, html):
            for forbidden in self.FORBIDDEN_INTERACTIVE_CLASSES:
                if forbidden in patch.add_classes:
                    logger.warning(
                        f"Cannot add '{forbidden}' to interactive element {patch.selector}"
                    )
                    return False

        return True

    def validate_batch(
        self,
        patches: List[TailwindPatch],
        html: str
    ) -> List[TailwindPatch]:
        """
        Validate multiple patches and return only valid ones.

        Args:
            patches: List of patches to validate
            html: Original HTML content

        Returns:
            List of valid patches
        """
        valid = []
        for patch in patches:
            if self.validate(patch, html):
                valid.append(patch)
            else:
                logger.info(f"Rejected invalid patch: {patch.describe()}")
        return valid

    def _selector_exists(self, selector: str, html: str) -> bool:
        """Check if selector matches any element in HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            return len(soup.select(selector)) > 0
        except Exception as e:
            logger.warning(f"Error checking selector '{selector}': {e}")
            return False

    def _is_valid_class(self, cls: str) -> bool:
        """Check if class matches valid Tailwind patterns."""
        # Allow any class with state variant prefix
        if ":" in cls:
            # Extract the base class after the variant
            parts = cls.split(":")
            if len(parts) == 2:
                variant, base = parts
                if variant in ["hover", "active", "focus", "disabled", "group-hover",
                               "focus-within", "focus-visible"]:
                    # Check if base class is valid
                    return self._is_valid_class(base)

        # Check against patterns
        for pattern in self._compiled_patterns:
            if pattern.match(cls):
                return True

        # Allow arbitrary values
        if cls.startswith("[") and cls.endswith("]"):
            return True

        return False

    def _is_interactive_selector(self, selector: str, html: str) -> bool:
        """Check if selector targets an interactive element."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(selector)

            if not elements:
                return False

            element = elements[0]
            tag = element.name.lower()

            # Interactive by tag
            if tag in ["button", "a", "input", "select", "textarea"]:
                return True

            # Interactive by attribute
            if element.get("onclick") or element.get("role") == "button":
                return True

            return False

        except Exception:
            return False
