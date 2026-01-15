"""
Unit tests for TailwindAnalyzer.

Tests Tailwind class extraction and analysis.
"""

import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.analyzers.tailwind_analyzer import TailwindAnalyzer


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def analyzer():
    """TailwindAnalyzer instance."""
    return TailwindAnalyzer()


@pytest.fixture
def button_html():
    """Button element HTML."""
    return """
    <button id="btn" class="relative z-10 bg-blue-600 hover:bg-blue-500
                            active:scale-95 transition-all">
        Click me
    </button>
    """


@pytest.fixture
def overlay_html():
    """Overlay element HTML."""
    return """
    <div class="absolute inset-0 bg-black/50 z-40 pointer-events-none"></div>
    """


@pytest.fixture
def modal_html():
    """Modal structure HTML."""
    return """
    <div class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/70"></div>
        <div class="relative z-50 bg-gray-800 rounded-xl p-6">Content</div>
    </div>
    """


def parse_element(html):
    """Helper to parse single element from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.find()


# ============================================================================
# Z-INDEX EXTRACTION TESTS
# ============================================================================


class TestZIndexExtraction:
    """Tests for z-index extraction."""

    def test_extract_standard_zindex(self, analyzer):
        """Should extract standard z-index values."""
        element = parse_element('<div class="z-10">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.z_index == 10

    def test_extract_high_zindex(self, analyzer):
        """Should extract high z-index values."""
        element = parse_element('<div class="z-50">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.z_index == 50

    def test_extract_arbitrary_zindex(self, analyzer):
        """Should extract arbitrary z-index values."""
        element = parse_element('<div class="z-[100]">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.z_index == 100

    def test_extract_large_arbitrary_zindex(self, analyzer):
        """Should extract large arbitrary z-index values."""
        element = parse_element('<div class="z-[9999]">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.z_index == 9999

    def test_no_zindex(self, analyzer):
        """Should return None when no z-index class."""
        element = parse_element('<div class="relative">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.z_index is None

    def test_zindex_auto(self, analyzer):
        """Should handle z-auto class."""
        element = parse_element('<div class="z-auto">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.z_index is None

    def test_get_zindex_class(self, analyzer):
        """Should return the z-index class itself."""
        element = parse_element('<div class="relative z-50">Test</div>')
        zclass = analyzer.get_zindex_class(element)
        assert zclass == "z-50"


# ============================================================================
# POINTER EVENTS TESTS
# ============================================================================


class TestPointerEvents:
    """Tests for pointer-events detection."""

    def test_detect_pointer_none(self, analyzer):
        """Should detect pointer-events-none class."""
        element = parse_element('<div class="pointer-events-none">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_pointer_none is True
        assert info.has_pointer_auto is False

    def test_detect_pointer_auto(self, analyzer):
        """Should detect pointer-events-auto class."""
        element = parse_element('<div class="pointer-events-auto">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_pointer_auto is True
        assert info.has_pointer_none is False

    def test_no_pointer_events(self, analyzer):
        """Should handle no pointer-events classes."""
        element = parse_element('<div class="relative">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_pointer_none is False
        assert info.has_pointer_auto is False


# ============================================================================
# POSITIONING TESTS
# ============================================================================


class TestPositioning:
    """Tests for position class detection."""

    def test_detect_relative(self, analyzer):
        """Should detect relative positioning."""
        element = parse_element('<div class="relative">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_relative is True
        assert info.is_positioned is True

    def test_detect_absolute(self, analyzer):
        """Should detect absolute positioning."""
        element = parse_element('<div class="absolute">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_absolute is True
        assert info.is_positioned is True

    def test_detect_fixed(self, analyzer):
        """Should detect fixed positioning."""
        element = parse_element('<div class="fixed">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_fixed is True
        assert info.is_positioned is True

    def test_no_positioning(self, analyzer):
        """Should handle no positioning classes."""
        element = parse_element('<div class="flex">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.is_positioned is False


# ============================================================================
# TRANSFORM TESTS
# ============================================================================


class TestTransforms:
    """Tests for transform class detection."""

    def test_detect_transform(self, analyzer):
        """Should detect transform class."""
        element = parse_element('<div class="transform rotate-45">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_transform is True

    def test_detect_rotate(self, analyzer):
        """Should detect rotate class as transform."""
        element = parse_element('<div class="rotate-180">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_transform is True

    def test_detect_scale(self, analyzer):
        """Should detect scale class as transform."""
        element = parse_element('<div class="scale-95">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_transform is True

    def test_detect_preserve_3d(self, analyzer):
        """Should detect preserve-3d class."""
        element = parse_element('<div class="[transform-style:preserve-3d]">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_preserve_3d is True

    def test_detect_backface_hidden(self, analyzer):
        """Should detect backface-hidden class."""
        element = parse_element('<div class="[backface-visibility:hidden]">Test</div>')
        info = analyzer.analyze_element(element)
        assert info.has_backface_hidden is True


# ============================================================================
# ELEMENT TYPE DETECTION TESTS
# ============================================================================


class TestElementTypeDetection:
    """Tests for element type detection."""

    def test_is_interactive_button(self, analyzer):
        """Should identify buttons as interactive."""
        element = parse_element('<button>Click</button>')
        assert analyzer.is_interactive(element) is True

    def test_is_interactive_link(self, analyzer):
        """Should identify links with href as interactive."""
        element = parse_element('<a href="/page">Link</a>')
        assert analyzer.is_interactive(element) is True

    def test_is_interactive_onclick(self, analyzer):
        """Should identify onclick elements as interactive."""
        element = parse_element('<div onclick="doSomething()">Click</div>')
        assert analyzer.is_interactive(element) is True

    def test_is_interactive_cursor_pointer(self, analyzer):
        """Should identify cursor-pointer elements as interactive."""
        element = parse_element('<div class="cursor-pointer">Click</div>')
        assert analyzer.is_interactive(element) is True

    def test_not_interactive_div(self, analyzer):
        """Should not identify plain divs as interactive."""
        element = parse_element('<div class="flex">Content</div>')
        assert analyzer.is_interactive(element) is False

    def test_is_overlay_absolute_inset(self, analyzer):
        """Should identify absolute inset-0 as overlay."""
        element = parse_element('<div class="absolute inset-0">Overlay</div>')
        assert analyzer.is_overlay(element) is True

    def test_is_overlay_fixed_inset(self, analyzer):
        """Should identify fixed inset-0 as overlay."""
        element = parse_element('<div class="fixed inset-0">Overlay</div>')
        assert analyzer.is_overlay(element) is True

    def test_not_overlay_without_positioning(self, analyzer):
        """Should not identify non-positioned as overlay."""
        element = parse_element('<div class="inset-0">Content</div>')
        assert analyzer.is_overlay(element) is False


# ============================================================================
# MISSING CLASSES DETECTION TESTS
# ============================================================================


class TestMissingClassesDetection:
    """Tests for missing class recommendations."""

    def test_missing_classes_interactive(self, analyzer):
        """Should detect missing classes for interactive elements."""
        element = parse_element('<button class="bg-blue-600">Click</button>')
        info = analyzer.analyze_element(element)

        # Button should recommend relative and z-10
        assert "relative" in info.missing_recommended

    def test_no_missing_classes_when_present(self, analyzer):
        """Should not report missing classes when present."""
        element = parse_element(
            '<button class="relative z-10 bg-blue-600">Click</button>'
        )
        info = analyzer.analyze_element(element)

        assert "relative" not in info.missing_recommended
        assert "z-10" not in info.missing_recommended

    def test_missing_pointer_events_on_overlay(self, analyzer):
        """Should detect missing pointer-events-none on overlay."""
        # Overlay without pointer-events-none
        element = parse_element('<div class="absolute inset-0 bg-black/50">Overlay</div>')
        info = analyzer.analyze_element(element)

        assert "pointer-events-none" in info.missing_recommended


# ============================================================================
# COMPARISON TESTS
# ============================================================================


class TestComparison:
    """Tests for element comparison methods."""

    def test_compare_zindex_higher(self, analyzer):
        """Should compare z-index values correctly."""
        el1 = parse_element('<div class="z-50">Higher</div>')
        el2 = parse_element('<div class="z-10">Lower</div>')

        result = analyzer.compare_zindex(el1, el2)
        assert result == 1  # el1 > el2

    def test_compare_zindex_lower(self, analyzer):
        """Should compare z-index values correctly."""
        el1 = parse_element('<div class="z-10">Lower</div>')
        el2 = parse_element('<div class="z-50">Higher</div>')

        result = analyzer.compare_zindex(el1, el2)
        assert result == -1  # el1 < el2

    def test_compare_zindex_equal(self, analyzer):
        """Should compare z-index values correctly."""
        el1 = parse_element('<div class="z-20">Same</div>')
        el2 = parse_element('<div class="z-20">Same</div>')

        result = analyzer.compare_zindex(el1, el2)
        assert result == 0  # el1 == el2
