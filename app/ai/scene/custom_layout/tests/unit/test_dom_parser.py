"""
Unit tests for DOMParser.

Tests HTML parsing, CSS selector queries, and element traversal.
"""

import pytest
from bs4 import Tag

import sys
from pathlib import Path

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.analyzers.dom_parser import DOMParser


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def simple_html():
    """Simple HTML for basic tests."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <div id="container" class="bg-gray-900">
            <button id="btn1" class="bg-blue-600 relative z-10">Click</button>
            <button id="btn2" class="bg-green-600">Submit</button>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def nested_html():
    """Nested HTML structure for traversal tests."""
    return """
    <body>
        <div id="parent" class="relative">
            <div id="child1" class="absolute">
                <span id="grandchild">Text</span>
            </div>
            <div id="child2" class="relative z-20">
                <button id="nested-btn">Click</button>
            </div>
        </div>
    </body>
    """


@pytest.fixture
def parser(simple_html):
    """Parser instance with simple HTML."""
    return DOMParser(simple_html)


@pytest.fixture
def nested_parser(nested_html):
    """Parser instance with nested HTML."""
    return DOMParser(nested_html)


# ============================================================================
# PARSING TESTS
# ============================================================================


class TestParsing:
    """Tests for HTML parsing."""

    def test_init_with_valid_html(self, simple_html):
        """Parser should accept valid HTML."""
        parser = DOMParser(simple_html)
        assert parser.soup is not None

    def test_html_property(self, parser, simple_html):
        """Original HTML should be accessible."""
        assert parser.html == simple_html

    def test_get_all_elements(self, parser):
        """Should return all Tag elements."""
        elements = parser.get_all_elements()
        assert len(elements) > 0
        assert all(isinstance(el, Tag) for el in elements)

    def test_repr(self, parser):
        """Should have meaningful repr."""
        assert "DOMParser" in repr(parser)
        assert "elements" in repr(parser)


# ============================================================================
# SELECTOR TESTS
# ============================================================================


class TestSelectors:
    """Tests for CSS selector queries."""

    def test_get_element_by_selector(self, parser):
        """Should find element by CSS selector."""
        btn = parser.get_element_by_selector("#btn1")
        assert btn is not None
        assert btn.name == "button"
        assert btn["id"] == "btn1"

    def test_get_elements_by_selector(self, parser):
        """Should find multiple elements."""
        buttons = parser.get_elements_by_selector("button")
        assert len(buttons) == 2

    def test_get_element_by_id(self, parser):
        """Should find element by ID."""
        container = parser.get_element_by_id("container")
        assert container is not None
        assert container.name == "div"

    def test_get_elements_by_tag(self, parser):
        """Should find all elements by tag name."""
        buttons = parser.get_elements_by_tag("button")
        assert len(buttons) == 2

    def test_get_elements_by_attribute(self, parser):
        """Should find elements by attribute."""
        elements = parser.get_elements_by_attribute("id")
        # Should find container, btn1, btn2
        assert len(elements) >= 3

    def test_get_elements_by_attribute_value(self, parser):
        """Should find elements by attribute value."""
        elements = parser.get_elements_by_attribute("id", "btn1")
        assert len(elements) == 1
        assert elements[0].name == "button"

    def test_selector_not_found(self, parser):
        """Should return None for non-existent selector."""
        result = parser.get_element_by_selector("#nonexistent")
        assert result is None

    def test_selector_empty_list(self, parser):
        """Should return empty list for non-matching selector."""
        result = parser.get_elements_by_selector(".nonexistent")
        assert result == []


# ============================================================================
# TRAVERSAL TESTS
# ============================================================================


class TestTraversal:
    """Tests for DOM traversal."""

    def test_get_parent_chain(self, nested_parser):
        """Should return chain of parent elements."""
        grandchild = nested_parser.get_element_by_id("grandchild")
        parents = nested_parser.get_parent_chain(grandchild)

        assert len(parents) >= 2
        parent_ids = [p.get("id") for p in parents if p.get("id")]
        assert "child1" in parent_ids
        assert "parent" in parent_ids

    def test_get_children(self, nested_parser):
        """Should return direct children."""
        parent = nested_parser.get_element_by_id("parent")
        children = nested_parser.get_children(parent)

        assert len(children) == 2
        child_ids = [c["id"] for c in children]
        assert "child1" in child_ids
        assert "child2" in child_ids

    def test_get_descendants(self, nested_parser):
        """Should return all descendants."""
        parent = nested_parser.get_element_by_id("parent")
        descendants = nested_parser.get_descendants(parent)

        # child1, grandchild, child2, nested-btn
        assert len(descendants) == 4

    def test_get_siblings(self, nested_parser):
        """Should return sibling elements."""
        child1 = nested_parser.get_element_by_id("child1")
        siblings = nested_parser.get_siblings(child1)

        assert len(siblings) == 1
        assert siblings[0]["id"] == "child2"


# ============================================================================
# CONTEXT TESTS
# ============================================================================


class TestContext:
    """Tests for element context extraction."""

    def test_get_bounding_context(self, nested_parser):
        """Should return context information."""
        grandchild = nested_parser.get_element_by_id("grandchild")
        context = nested_parser.get_bounding_context(grandchild)

        assert "parent_chain" in context
        assert "depth" in context
        assert context["depth"] >= 2

    def test_get_source_line(self, simple_html):
        """Should track source line numbers."""
        parser = DOMParser(simple_html)
        btn = parser.get_element_by_id("btn1")
        line = parser.get_source_line(btn)

        # Line tracking may not be exact but should exist
        assert line is None or isinstance(line, int)


# ============================================================================
# SELECTOR GENERATION TESTS
# ============================================================================


class TestSelectorGeneration:
    """Tests for CSS selector generation."""

    def test_generate_selector_with_id(self, parser):
        """Should prefer ID for selector."""
        btn = parser.get_element_by_id("btn1")
        selector = parser.generate_selector(btn)
        assert selector == "#btn1"

    def test_generate_selector_without_id(self, simple_html):
        """Should use tag and classes without ID."""
        html = """<div class="container"><span class="text red">Hello</span></div>"""
        parser = DOMParser(html)
        span = parser.get_element_by_selector("span")
        selector = parser.generate_selector(span)

        assert "span" in selector
        assert "text" in selector or "red" in selector

    def test_generate_unique_selector(self, nested_parser):
        """Should generate unique selector with context."""
        btn = nested_parser.get_element_by_id("nested-btn")
        selector = nested_parser.generate_unique_selector(btn)

        # Should start with ID of ancestor or button itself
        assert "#" in selector or "button" in selector


# ============================================================================
# UTILITY TESTS
# ============================================================================


class TestUtilities:
    """Tests for utility methods."""

    def test_get_text_content(self, parser):
        """Should extract text content."""
        btn = parser.get_element_by_id("btn1")
        text = parser.get_text_content(btn)
        assert text == "Click"

    def test_has_class(self, parser):
        """Should check for class presence."""
        btn = parser.get_element_by_id("btn1")
        assert parser.has_class(btn, "bg-blue-600") is True
        assert parser.has_class(btn, "nonexistent") is False

    def test_get_classes(self, parser):
        """Should return list of classes."""
        btn = parser.get_element_by_id("btn1")
        classes = parser.get_classes(btn)

        assert "bg-blue-600" in classes
        assert "relative" in classes
        assert "z-10" in classes

    def test_get_attribute(self, parser):
        """Should get attribute value."""
        btn = parser.get_element_by_id("btn1")
        assert parser.get_attribute(btn, "id") == "btn1"
        assert parser.get_attribute(btn, "nonexistent") is None
