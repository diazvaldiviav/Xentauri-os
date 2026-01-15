"""
Unit tests for EventMapper.

Tests event handler extraction and analysis.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.analyzers.event_mapper import EventMapper


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mapper():
    """EventMapper instance."""
    return EventMapper()


@pytest.fixture
def onclick_html():
    """HTML with onclick handlers."""
    return """
    <body>
        <button id="btn1" onclick="handleClick()">Click</button>
        <button id="btn2" onclick="submitForm(this, 'arg')">Submit</button>
        <div id="div1" onclick="doSomething()">Clickable div</div>
        <span id="plain">No handler</span>
    </body>
    """


@pytest.fixture
def multiple_events_html():
    """HTML with multiple event types."""
    return """
    <body>
        <button id="multi"
                onclick="handleClick()"
                onmousedown="handleMouseDown()"
                onfocus="handleFocus()">
            Multiple events
        </button>
        <input id="input1" oninput="handleInput()" onchange="handleChange()" />
        <form id="form1" onsubmit="handleSubmit(event)">
            <button type="submit">Submit</button>
        </form>
    </body>
    """


@pytest.fixture
def stop_propagation_html():
    """HTML with event.stopPropagation()."""
    return """
    <body>
        <div id="parent" onclick="handleParent()">
            <button id="child" onclick="event.stopPropagation(); handleChild()">
                Child
            </button>
        </div>
        <button id="normal" onclick="handleNormal()">Normal</button>
    </body>
    """


@pytest.fixture
def parser(onclick_html):
    """Parser with onclick HTML."""
    return DOMParser(onclick_html)


# ============================================================================
# BASIC MAPPING TESTS
# ============================================================================


class TestBasicMapping:
    """Tests for basic event mapping."""

    def test_map_onclick_events(self, mapper, parser):
        """Should map onclick events."""
        events = mapper.map_events(parser)
        onclick_events = [e for e in events if e.event_type == "onclick"]

        assert len(onclick_events) == 3  # btn1, btn2, div1

    def test_event_info_structure(self, mapper, parser):
        """Should populate EventInfo correctly."""
        events = mapper.map_events(parser)
        btn1_event = next((e for e in events if e.selector == "#btn1"), None)

        assert btn1_event is not None
        assert btn1_event.event_type == "onclick"
        assert btn1_event.handler == "handleClick()"
        assert btn1_event.is_inline is True
        assert btn1_event.function_name == "handleClick"

    def test_extract_function_with_args(self, mapper, parser):
        """Should extract function name with arguments."""
        events = mapper.map_events(parser)
        btn2_event = next((e for e in events if e.selector == "#btn2"), None)

        assert btn2_event is not None
        assert btn2_event.function_name == "submitForm"

    def test_get_element_events(self, mapper, parser):
        """Should get events for specific element."""
        btn = parser.get_element_by_id("btn1")
        events = mapper.get_element_events(btn, parser)

        assert len(events) == 1
        assert events[0].event_type == "onclick"


# ============================================================================
# MULTIPLE EVENT TESTS
# ============================================================================


class TestMultipleEvents:
    """Tests for elements with multiple events."""

    def test_map_multiple_events_on_element(self, mapper, multiple_events_html):
        """Should map multiple events on same element."""
        parser = DOMParser(multiple_events_html)
        events = mapper.map_events(parser)

        multi_events = [e for e in events if e.selector == "#multi"]
        event_types = {e.event_type for e in multi_events}

        assert "onclick" in event_types
        assert "onmousedown" in event_types
        assert "onfocus" in event_types

    def test_map_input_events(self, mapper, multiple_events_html):
        """Should map input and change events."""
        parser = DOMParser(multiple_events_html)
        events = mapper.map_events(parser)

        input_events = [e for e in events if e.selector == "#input1"]
        event_types = {e.event_type for e in input_events}

        assert "oninput" in event_types
        assert "onchange" in event_types

    def test_map_form_submit(self, mapper, multiple_events_html):
        """Should map form submit event."""
        parser = DOMParser(multiple_events_html)
        events = mapper.map_events(parser)

        form_events = [e for e in events if e.selector == "#form1"]
        assert len(form_events) == 1
        assert form_events[0].event_type == "onsubmit"


# ============================================================================
# CONVENIENCE METHOD TESTS
# ============================================================================


class TestConvenienceMethods:
    """Tests for convenience methods."""

    def test_has_click_handler(self, mapper, parser):
        """Should detect click handler."""
        btn = parser.get_element_by_id("btn1")
        assert mapper.has_click_handler(btn) is True

        plain = parser.get_element_by_id("plain")
        assert mapper.has_click_handler(plain) is False

    def test_has_submit_handler(self, mapper, multiple_events_html):
        """Should detect submit handler."""
        parser = DOMParser(multiple_events_html)
        form = parser.get_element_by_id("form1")
        assert mapper.has_submit_handler(form) is True

        btn = parser.get_element_by_id("multi")
        assert mapper.has_submit_handler(btn) is False

    def test_has_change_handler(self, mapper, multiple_events_html):
        """Should detect change/input handlers."""
        parser = DOMParser(multiple_events_html)
        inp = parser.get_element_by_id("input1")
        assert mapper.has_change_handler(inp) is True

    def test_get_handler_function(self, mapper, parser):
        """Should get function name for event type."""
        btn = parser.get_element_by_id("btn1")
        fn = mapper.get_handler_function(btn, "onclick")
        assert fn == "handleClick"

        fn_nonexist = mapper.get_handler_function(btn, "onsubmit")
        assert fn_nonexist is None


# ============================================================================
# STOP PROPAGATION TESTS
# ============================================================================


class TestStopPropagation:
    """Tests for stopPropagation detection."""

    def test_detect_stop_propagation(self, mapper, stop_propagation_html):
        """Should detect event.stopPropagation()."""
        parser = DOMParser(stop_propagation_html)
        child = parser.get_element_by_id("child")
        assert mapper.stops_propagation(child) is True

    def test_no_stop_propagation(self, mapper, stop_propagation_html):
        """Should not detect stopPropagation when not present."""
        parser = DOMParser(stop_propagation_html)
        normal = parser.get_element_by_id("normal")
        assert mapper.stops_propagation(normal) is False

    def test_extract_function_after_stop_propagation(self, mapper, stop_propagation_html):
        """Should extract function name after stopPropagation."""
        parser = DOMParser(stop_propagation_html)
        events = mapper.map_events(parser)
        child_event = next((e for e in events if e.selector == "#child"), None)

        assert child_event is not None
        assert child_event.function_name == "handleChild"


# ============================================================================
# FILTERING TESTS
# ============================================================================


class TestFiltering:
    """Tests for event filtering."""

    def test_filter_by_event_type(self, mapper, multiple_events_html):
        """Should filter events by type."""
        parser = DOMParser(multiple_events_html)
        all_events = mapper.map_events(parser)
        click_events = mapper.filter_by_event_type(all_events, "onclick")

        assert len(click_events) > 0
        assert all(e.event_type == "onclick" for e in click_events)

    def test_filter_by_function(self, mapper, multiple_events_html):
        """Should filter events by function name."""
        parser = DOMParser(multiple_events_html)
        all_events = mapper.map_events(parser)
        click_events = mapper.filter_by_function(all_events, "handleClick")

        assert len(click_events) == 1
        assert click_events[0].function_name == "handleClick"

    def test_get_unique_functions(self, mapper, multiple_events_html):
        """Should get unique function names."""
        parser = DOMParser(multiple_events_html)
        all_events = mapper.map_events(parser)
        functions = mapper.get_unique_functions(all_events)

        assert "handleClick" in functions
        assert "handleInput" in functions


# ============================================================================
# ANALYSIS TESTS
# ============================================================================


class TestAnalysis:
    """Tests for event analysis."""

    def test_find_elements_calling(self, mapper, onclick_html):
        """Should find elements calling a function."""
        parser = DOMParser(onclick_html)
        elements = mapper.find_elements_calling(parser, "handleClick")

        assert len(elements) == 1
        assert elements[0]["id"] == "btn1"

    def test_count_handlers_by_type(self, mapper, multiple_events_html):
        """Should count handlers by type."""
        parser = DOMParser(multiple_events_html)
        all_events = mapper.map_events(parser)
        counts = mapper.count_handlers_by_type(all_events)

        assert "onclick" in counts
        assert counts["onclick"] >= 1
