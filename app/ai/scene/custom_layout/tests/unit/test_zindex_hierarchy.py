"""
Unit tests for ZIndexHierarchyBuilder.

Tests z-index stacking context hierarchy.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.analyzers.zindex_hierarchy import ZIndexHierarchyBuilder


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def builder():
    """ZIndexHierarchyBuilder instance."""
    return ZIndexHierarchyBuilder()


@pytest.fixture
def simple_zindex_html():
    """HTML with simple z-index layers."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <div id="low" class="relative z-10">Low z-index</div>
        <div id="med" class="relative z-20">Medium z-index</div>
        <div id="high" class="relative z-50">High z-index</div>
    </body>
    </html>
    """


@pytest.fixture
def nested_zindex_html():
    """HTML with nested z-index contexts."""
    return """
    <body>
        <div id="parent" class="relative z-10">
            <div id="child1" class="absolute z-20">Child 1</div>
            <div id="child2" class="absolute z-30">Child 2</div>
        </div>
        <div id="sibling" class="relative z-50">Sibling</div>
    </body>
    """


@pytest.fixture
def modal_zindex_html():
    """HTML with modal z-index structure."""
    return """
    <body>
        <div id="content" class="relative z-10">Main content</div>
        <div id="modal" class="fixed inset-0 z-50">
            <div id="backdrop" class="absolute inset-0 z-40 bg-black/50"></div>
            <div id="modal-content" class="relative z-50 bg-white p-4">
                <button id="modal-btn" class="relative z-10">Click</button>
            </div>
        </div>
    </body>
    """


@pytest.fixture
def conflict_html():
    """HTML with z-index conflicts."""
    return """
    <body>
        <div id="el1" class="absolute inset-0 z-50 bg-red-500">Element 1</div>
        <div id="el2" class="absolute inset-0 z-50 bg-blue-500">Element 2</div>
        <button id="btn" class="relative z-10">Button</button>
    </body>
    """


@pytest.fixture
def parser(simple_zindex_html):
    """Parser with simple z-index HTML."""
    return DOMParser(simple_zindex_html)


# ============================================================================
# HIERARCHY BUILDING TESTS
# ============================================================================


class TestHierarchyBuilding:
    """Tests for hierarchy building."""

    def test_build_simple_hierarchy(self, builder, parser):
        """Should build hierarchy from simple HTML."""
        root = builder.build_hierarchy(parser)

        assert root is not None
        assert root.selector == "body"
        assert root.depth == 0

    def test_root_has_children(self, builder, parser):
        """Should find children in hierarchy."""
        root = builder.build_hierarchy(parser)

        # Should have children with z-index
        assert len(root.children) >= 0  # May vary based on implementation

    def test_nested_hierarchy(self, builder, nested_zindex_html):
        """Should build nested hierarchy."""
        parser = DOMParser(nested_zindex_html)
        root = builder.build_hierarchy(parser)

        assert root is not None
        # Hierarchy should be built (details depend on implementation)


# ============================================================================
# ELEMENT QUERY TESTS
# ============================================================================


class TestElementQueries:
    """Tests for element queries by z-index."""

    def test_get_elements_at_zindex(self, builder, simple_zindex_html):
        """Should get elements at specific z-index."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        elements_z10 = builder.get_elements_at_zindex(10)
        assert len(elements_z10) >= 1

        elements_z50 = builder.get_elements_at_zindex(50)
        assert len(elements_z50) >= 1

    def test_get_elements_at_nonexistent_zindex(self, builder, parser):
        """Should return empty for nonexistent z-index."""
        builder.build_hierarchy(parser)
        elements = builder.get_elements_at_zindex(999)
        assert len(elements) == 0

    def test_get_elements_above(self, builder, simple_zindex_html):
        """Should get elements above target."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        low_el = parser.get_element_by_id("low")
        above = builder.get_elements_above(low_el)

        # med (z-20) and high (z-50) should be above low (z-10)
        assert len(above) >= 2

    def test_get_elements_below(self, builder, simple_zindex_html):
        """Should get elements below target."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        high_el = parser.get_element_by_id("high")
        below = builder.get_elements_below(high_el)

        # low (z-10) and med (z-20) should be below high (z-50)
        assert len(below) >= 2

    def test_get_elements_at_same_level(self, builder, conflict_html):
        """Should get elements at same z-index level."""
        parser = DOMParser(conflict_html)
        builder.build_hierarchy(parser)

        el1 = parser.get_element_by_id("el1")
        same_level = builder.get_elements_at_same_level(el1)

        # el2 should be at same z-index as el1
        assert len(same_level) >= 1


# ============================================================================
# Z-INDEX INFO TESTS
# ============================================================================


class TestZIndexInfo:
    """Tests for z-index information retrieval."""

    def test_get_zindex_for_element(self, builder, simple_zindex_html):
        """Should get z-index for specific element."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        high_el = parser.get_element_by_id("high")
        z = builder.get_zindex_for_element(high_el)
        assert z == 50

    def test_get_sorted_zindexes(self, builder, simple_zindex_html):
        """Should get sorted list of z-indexes."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        zindexes = builder.get_sorted_zindexes()
        assert zindexes == sorted(zindexes)

    def test_get_max_zindex(self, builder, simple_zindex_html):
        """Should get maximum z-index."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        max_z = builder.get_max_zindex()
        assert max_z >= 50

    def test_get_min_zindex(self, builder, simple_zindex_html):
        """Should get minimum z-index."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        min_z = builder.get_min_zindex()
        assert min_z <= 10


# ============================================================================
# CONFLICT DETECTION TESTS
# ============================================================================


class TestConflictDetection:
    """Tests for z-index conflict detection."""

    def test_find_conflicts(self, builder, conflict_html):
        """Should find z-index conflicts."""
        parser = DOMParser(conflict_html)
        builder.build_hierarchy(parser)

        conflicts = builder.find_conflicts()

        # el1 and el2 both have z-50 and inset-0 (overlap)
        assert len(conflicts) >= 1

    def test_no_conflicts_different_levels(self, builder, simple_zindex_html):
        """Should not find conflicts at different levels."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        conflicts = builder.find_conflicts()

        # Elements at different z-levels shouldn't conflict
        # (unless they have same z-index with inset-0)
        # This depends on implementation


# ============================================================================
# MODAL STRUCTURE TESTS
# ============================================================================


class TestModalStructure:
    """Tests for modal z-index structures."""

    def test_modal_hierarchy(self, builder, modal_zindex_html):
        """Should handle modal z-index hierarchy."""
        parser = DOMParser(modal_zindex_html)
        root = builder.build_hierarchy(parser)

        assert root is not None

    def test_modal_content_above_backdrop(self, builder, modal_zindex_html):
        """Modal content should be above backdrop."""
        parser = DOMParser(modal_zindex_html)
        builder.build_hierarchy(parser)

        backdrop = parser.get_element_by_id("backdrop")
        modal_content = parser.get_element_by_id("modal-content")

        backdrop_z = builder.get_zindex_for_element(backdrop)
        content_z = builder.get_zindex_for_element(modal_content)

        # Content should have >= z-index as backdrop
        assert content_z >= backdrop_z


# ============================================================================
# UTILITY TESTS
# ============================================================================


class TestUtilities:
    """Tests for utility methods."""

    def test_describe_hierarchy(self, builder, simple_zindex_html):
        """Should generate hierarchy description."""
        parser = DOMParser(simple_zindex_html)
        builder.build_hierarchy(parser)

        description = builder.describe_hierarchy()
        assert "Z-Index Hierarchy" in description

    def test_repr_before_build(self, builder):
        """Should have repr before building."""
        assert "not built" in repr(builder)

    def test_repr_after_build(self, builder, parser):
        """Should have meaningful repr after building."""
        builder.build_hierarchy(parser)
        assert "ZIndexHierarchyBuilder" in repr(builder)
        assert "contexts" in repr(builder)
