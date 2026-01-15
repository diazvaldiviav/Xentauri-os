"""
Interactive Detector - Find interactive elements in HTML.

This module identifies elements that should respond to user interactions
(clicks, focus, hover) based on tag type, attributes, and ARIA roles.

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import (
        InteractiveDetector,
        DOMParser
    )

    parser = DOMParser(html_string)
    detector = InteractiveDetector()
    elements = detector.find_interactive_elements(parser)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set

from bs4 import Tag

from .dom_parser import DOMParser


class InteractionType(Enum):
    """Types of user interactions."""

    CLICK = "click"
    """Click/tap interaction (buttons, links)."""

    INPUT = "input"
    """Text input interaction (input, textarea)."""

    SELECT = "select"
    """Selection interaction (select, checkbox, radio)."""

    FOCUS = "focus"
    """Focus-only interaction (tabindex elements)."""

    UNKNOWN = "unknown"
    """Unknown interaction type."""


@dataclass
class InteractiveElement:
    """
    Information about an interactive element.

    Bundles the element with metadata about how it should
    respond to user interaction.
    """

    element: Tag
    """The BeautifulSoup Tag."""

    interaction_type: InteractionType
    """Type of expected interaction."""

    selector: str
    """CSS selector for the element."""

    has_handler: bool
    """Whether element has inline event handlers."""

    is_form_element: bool
    """Whether element is a form control."""

    is_link: bool
    """Whether element is a link."""

    is_disabled: bool
    """Whether element is disabled."""


class InteractiveDetector:
    """
    Detects interactive elements in HTML documents.

    Identifies elements that should respond to user actions
    based on multiple criteria.
    """

    # Tags that are inherently interactive
    INTERACTIVE_TAGS: Set[str] = {
        "button",
        "a",
        "input",
        "select",
        "textarea",
        "details",
        "summary",
    }

    # Attributes that indicate interactivity
    INTERACTIVE_ATTRS: Set[str] = {
        "onclick",
        "onmousedown",
        "onmouseup",
        "ontouchstart",
        "ontouchend",
        "onkeydown",
        "onkeypress",
        "onfocus",
        "onblur",
    }

    # ARIA roles that indicate interactivity
    INTERACTIVE_ROLES: Set[str] = {
        "button",
        "link",
        "checkbox",
        "radio",
        "tab",
        "menuitem",
        "menuitemcheckbox",
        "menuitemradio",
        "option",
        "switch",
        "slider",
        "spinbutton",
        "textbox",
        "combobox",
        "listbox",
        "searchbox",
        "gridcell",
        "treeitem",
    }

    # Form input types
    FORM_INPUT_TYPES: Set[str] = {
        "text",
        "password",
        "email",
        "number",
        "tel",
        "url",
        "search",
        "date",
        "datetime-local",
        "time",
        "month",
        "week",
        "color",
        "file",
        "range",
    }

    # Click input types
    CLICK_INPUT_TYPES: Set[str] = {
        "button",
        "submit",
        "reset",
        "checkbox",
        "radio",
    }

    # =========================================================================
    # MAIN DETECTION
    # =========================================================================

    def find_interactive_elements(
        self, parser: DOMParser
    ) -> List[InteractiveElement]:
        """
        Find all interactive elements in the document.

        Args:
            parser: DOMParser instance with loaded HTML

        Returns:
            List of InteractiveElement objects
        """
        results = []

        for element in parser.get_all_elements():
            if self.is_interactive(element):
                info = InteractiveElement(
                    element=element,
                    interaction_type=self.get_interaction_type(element),
                    selector=parser.generate_selector(element),
                    has_handler=self._has_event_handler(element),
                    is_form_element=self._is_form_element(element),
                    is_link=self._is_link(element),
                    is_disabled=self._is_disabled(element),
                )
                results.append(info)

        return results

    def find_clickable_elements(
        self, parser: DOMParser
    ) -> List[InteractiveElement]:
        """
        Find elements that respond to click/tap.

        Filters out input/focus-only elements.

        Args:
            parser: DOMParser instance

        Returns:
            List of clickable InteractiveElement objects
        """
        all_interactive = self.find_interactive_elements(parser)
        return [
            el for el in all_interactive
            if el.interaction_type in (InteractionType.CLICK, InteractionType.SELECT)
        ]

    def find_form_elements(
        self, parser: DOMParser
    ) -> List[InteractiveElement]:
        """
        Find form input elements.

        Args:
            parser: DOMParser instance

        Returns:
            List of form InteractiveElement objects
        """
        all_interactive = self.find_interactive_elements(parser)
        return [el for el in all_interactive if el.is_form_element]

    # =========================================================================
    # ELEMENT CHECKS
    # =========================================================================

    def is_interactive(self, element: Tag) -> bool:
        """
        Determine if an element is interactive.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element should respond to user interaction
        """
        # Skip disabled elements
        if self._is_disabled(element):
            return False

        tag = element.name.lower()

        # Check tag name
        if tag in self.INTERACTIVE_TAGS:
            # Links need href to be interactive
            if tag == "a" and not element.get("href"):
                return self._has_event_handler(element)
            return True

        # Check event handlers
        if self._has_event_handler(element):
            return True

        # Check ARIA role
        role = element.get("role", "").lower()
        if role in self.INTERACTIVE_ROLES:
            return True

        # Check tabindex (positive tabindex means focusable)
        tabindex = element.get("tabindex")
        if tabindex is not None:
            try:
                if int(tabindex) >= 0:
                    return True
            except ValueError:
                pass

        # Check cursor-pointer class (Tailwind convention)
        classes = element.get("class", [])
        if "cursor-pointer" in classes:
            return True

        # Check contenteditable
        if element.get("contenteditable") == "true":
            return True

        return False

    def get_interaction_type(self, element: Tag) -> InteractionType:
        """
        Determine the type of interaction for an element.

        Args:
            element: BeautifulSoup Tag

        Returns:
            InteractionType enum value
        """
        tag = element.name.lower()

        # Input elements have various types
        if tag == "input":
            input_type = element.get("type", "text").lower()

            if input_type in self.CLICK_INPUT_TYPES:
                return InteractionType.SELECT if input_type in (
                    "checkbox", "radio"
                ) else InteractionType.CLICK

            if input_type in self.FORM_INPUT_TYPES:
                return InteractionType.INPUT

        # Text input elements
        if tag == "textarea":
            return InteractionType.INPUT

        # Selection elements
        if tag == "select":
            return InteractionType.SELECT

        # Clickable elements
        if tag in ("button", "a", "summary"):
            return InteractionType.CLICK

        # Check role for clues
        role = element.get("role", "").lower()
        if role in ("textbox", "searchbox", "combobox"):
            return InteractionType.INPUT
        if role in ("checkbox", "radio", "option", "switch"):
            return InteractionType.SELECT
        if role in ("button", "link", "tab", "menuitem"):
            return InteractionType.CLICK

        # Default to click for elements with handlers
        if self._has_event_handler(element):
            return InteractionType.CLICK

        # Tabindex-only elements
        tabindex = element.get("tabindex")
        if tabindex is not None:
            return InteractionType.FOCUS

        return InteractionType.UNKNOWN

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _has_event_handler(self, element: Tag) -> bool:
        """
        Check if element has inline event handlers.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if any event handler attribute is present
        """
        for attr in self.INTERACTIVE_ATTRS:
            if element.get(attr):
                return True
        return False

    def _is_form_element(self, element: Tag) -> bool:
        """
        Check if element is a form control.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element is a form input
        """
        tag = element.name.lower()

        if tag in ("input", "select", "textarea"):
            return True

        role = element.get("role", "").lower()
        if role in ("textbox", "searchbox", "combobox", "checkbox", "radio", "slider"):
            return True

        return False

    def _is_link(self, element: Tag) -> bool:
        """
        Check if element is a link.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element is a link
        """
        if element.name.lower() == "a":
            return True

        role = element.get("role", "").lower()
        return role == "link"

    def _is_disabled(self, element: Tag) -> bool:
        """
        Check if element is disabled.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element is disabled
        """
        # HTML disabled attribute
        if element.get("disabled") is not None:
            return True

        # ARIA disabled
        if element.get("aria-disabled") == "true":
            return True

        # Check for disabled class (common pattern)
        classes = element.get("class", [])
        if "disabled" in classes or "opacity-50" in classes:
            # opacity-50 often indicates disabled state with cursor-not-allowed
            if "cursor-not-allowed" in classes:
                return True

        return False

    def get_elements_by_type(
        self,
        parser: DOMParser,
        interaction_type: InteractionType
    ) -> List[InteractiveElement]:
        """
        Get interactive elements filtered by interaction type.

        Args:
            parser: DOMParser instance
            interaction_type: Type of interaction to filter by

        Returns:
            List of matching InteractiveElement objects
        """
        all_elements = self.find_interactive_elements(parser)
        return [el for el in all_elements if el.interaction_type == interaction_type]

    def __repr__(self) -> str:
        """String representation."""
        return "InteractiveDetector()"
