"""
Event Mapper - Map and analyze event handlers in HTML.

This module extracts and analyzes inline event handlers from HTML elements,
providing information about what JavaScript functions are called.

Usage:
    from app.ai.scene.custom_layout.html_fixer.analyzers import (
        EventMapper,
        DOMParser
    )

    parser = DOMParser(html_string)
    mapper = EventMapper()
    events = mapper.map_events(parser)
    for event in events:
        print(f"{event.event_type}: {event.handler}")
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Set

from bs4 import Tag

from .dom_parser import DOMParser


@dataclass
class EventInfo:
    """
    Information about an event handler on an element.

    Captures both the event type and the handler code.
    """

    element: Tag
    """The element with the event handler."""

    event_type: str
    """Type of event (onclick, onsubmit, etc.)."""

    handler: str
    """The handler code/function call."""

    is_inline: bool
    """True if this is an inline HTML attribute handler."""

    function_name: Optional[str]
    """Extracted function name (if detectable)."""

    selector: str
    """CSS selector for the element."""

    def __repr__(self) -> str:
        """String representation."""
        fn = self.function_name or "anonymous"
        return f"EventInfo({self.event_type}={fn})"


class EventMapper:
    """
    Maps event handlers from HTML elements.

    Extracts inline event handlers and analyzes the
    JavaScript code to identify function calls.
    """

    # All event attributes to scan for
    EVENT_ATTRIBUTES: Set[str] = {
        # Mouse events
        "onclick",
        "ondblclick",
        "onmousedown",
        "onmouseup",
        "onmouseover",
        "onmouseout",
        "onmouseenter",
        "onmouseleave",
        "onmousemove",
        "oncontextmenu",
        # Touch events
        "ontouchstart",
        "ontouchend",
        "ontouchmove",
        "ontouchcancel",
        # Keyboard events
        "onkeydown",
        "onkeyup",
        "onkeypress",
        # Focus events
        "onfocus",
        "onblur",
        "onfocusin",
        "onfocusout",
        # Form events
        "onsubmit",
        "onreset",
        "onchange",
        "oninput",
        "oninvalid",
        "onselect",
        # Drag events
        "ondrag",
        "ondragstart",
        "ondragend",
        "ondragover",
        "ondragenter",
        "ondragleave",
        "ondrop",
        # Clipboard events
        "oncopy",
        "oncut",
        "onpaste",
        # Media events
        "onplay",
        "onpause",
        "onended",
        # Other
        "onload",
        "onerror",
        "onscroll",
        "onresize",
        "onwheel",
    }

    # Pattern to extract function name from handler code
    FUNCTION_PATTERN = re.compile(r"^\s*(\w+)\s*\(")

    # Pattern to extract function with event.stopPropagation
    STOP_PROPAGATION_PATTERN = re.compile(r"event\.stopPropagation\(\)")

    # =========================================================================
    # MAIN MAPPING
    # =========================================================================

    def map_events(self, parser: DOMParser) -> List[EventInfo]:
        """
        Map all event handlers in the document.

        Args:
            parser: DOMParser instance with loaded HTML

        Returns:
            List of EventInfo objects for all handlers found
        """
        results = []

        for element in parser.get_all_elements():
            element_events = self.get_element_events(element, parser)
            results.extend(element_events)

        return results

    def get_element_events(
        self, element: Tag, parser: Optional[DOMParser] = None
    ) -> List[EventInfo]:
        """
        Get all event handlers for a specific element.

        Args:
            element: BeautifulSoup Tag
            parser: Optional DOMParser for selector generation

        Returns:
            List of EventInfo objects for this element
        """
        events = []

        for attr in self.EVENT_ATTRIBUTES:
            handler = element.get(attr)
            if handler:
                # Generate selector
                if parser:
                    selector = parser.generate_selector(element)
                else:
                    selector = element.name

                events.append(
                    EventInfo(
                        element=element,
                        event_type=attr,
                        handler=handler,
                        is_inline=True,
                        function_name=self._extract_function_name(handler),
                        selector=selector,
                    )
                )

        return events

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def has_click_handler(self, element: Tag) -> bool:
        """
        Check if element has a click-related handler.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element has onclick or similar
        """
        click_events = {
            "onclick",
            "onmousedown",
            "onmouseup",
            "ontouchstart",
            "ontouchend",
        }

        for attr in click_events:
            if element.get(attr):
                return True

        return False

    def has_submit_handler(self, element: Tag) -> bool:
        """
        Check if element has a submit handler.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element has onsubmit
        """
        return element.get("onsubmit") is not None

    def has_change_handler(self, element: Tag) -> bool:
        """
        Check if element has change/input handlers.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element has onchange or oninput
        """
        return (
            element.get("onchange") is not None or
            element.get("oninput") is not None
        )

    def stops_propagation(self, element: Tag) -> bool:
        """
        Check if any handler stops event propagation.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if event.stopPropagation() is called
        """
        for attr in self.EVENT_ATTRIBUTES:
            handler = element.get(attr)
            if handler and self.STOP_PROPAGATION_PATTERN.search(handler):
                return True

        return False

    def get_handler_function(self, element: Tag, event_type: str) -> Optional[str]:
        """
        Get the function name for a specific event type.

        Args:
            element: BeautifulSoup Tag
            event_type: Event attribute name (e.g., "onclick")

        Returns:
            Function name or None
        """
        handler = element.get(event_type)
        if handler:
            return self._extract_function_name(handler)
        return None

    # =========================================================================
    # FILTERING
    # =========================================================================

    def filter_by_event_type(
        self, events: List[EventInfo], event_type: str
    ) -> List[EventInfo]:
        """
        Filter events by event type.

        Args:
            events: List of EventInfo objects
            event_type: Event type to filter by (e.g., "onclick")

        Returns:
            Filtered list of events
        """
        return [e for e in events if e.event_type == event_type]

    def filter_by_function(
        self, events: List[EventInfo], function_name: str
    ) -> List[EventInfo]:
        """
        Filter events by function name.

        Args:
            events: List of EventInfo objects
            function_name: Function name to filter by

        Returns:
            Filtered list of events
        """
        return [e for e in events if e.function_name == function_name]

    def get_unique_functions(self, events: List[EventInfo]) -> Set[str]:
        """
        Get unique function names from events.

        Args:
            events: List of EventInfo objects

        Returns:
            Set of unique function names
        """
        return {e.function_name for e in events if e.function_name}

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def find_elements_calling(
        self, parser: DOMParser, function_name: str
    ) -> List[Tag]:
        """
        Find all elements that call a specific function.

        Args:
            parser: DOMParser instance
            function_name: Function name to search for

        Returns:
            List of elements calling the function
        """
        results = []
        events = self.map_events(parser)

        for event in events:
            if event.function_name == function_name:
                results.append(event.element)

        return results

    def count_handlers_by_type(self, events: List[EventInfo]) -> dict:
        """
        Count events by event type.

        Args:
            events: List of EventInfo objects

        Returns:
            Dict mapping event type to count
        """
        counts = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _extract_function_name(self, handler: str) -> Optional[str]:
        """
        Extract function name from handler code.

        Handles patterns like:
        - "myFunction()"
        - "myFunction(this, 'arg')"
        - "event.stopPropagation(); myFunction()"

        Args:
            handler: Handler code string

        Returns:
            Function name or None
        """
        # Try to find function call pattern
        match = self.FUNCTION_PATTERN.search(handler)
        if match:
            fn_name = match.group(1)
            # Skip common non-function patterns
            if fn_name not in ("event", "this", "return", "if", "else"):
                return fn_name

        # Handle event.stopPropagation(); followed by function
        if ";" in handler:
            parts = handler.split(";")
            for part in parts:
                match = self.FUNCTION_PATTERN.search(part.strip())
                if match:
                    fn_name = match.group(1)
                    if fn_name not in ("event", "this", "return", "if", "else"):
                        return fn_name

        return None

    def __repr__(self) -> str:
        """String representation."""
        return "EventMapper()"
