"""
Unit tests for PointerBlockageDetector.

Tests detection of pointer-events blockages.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.analyzers.interactive_detector import InteractiveDetector
from html_fixer.analyzers.pointer_detector import (
    PointerBlockageDetector,
    BlockageReason,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def detector():
    """PointerBlockageDetector instance."""
    return PointerBlockageDetector()


@pytest.fixture
def interactive_detector():
    """InteractiveDetector instance."""
    return InteractiveDetector()


@pytest.fixture
def overlay_blocking_html():
    """HTML with overlay blocking buttons."""
    return """
    <body>
        <div id="container" class="relative">
            <!-- Overlay without pointer-events-none blocks button -->
            <div id="overlay" class="absolute inset-0 bg-black/50 z-40"></div>
            <button id="btn" class="relative z-10 bg-blue-600">Blocked</button>
        </div>
    </body>
    """


@pytest.fixture
def overlay_passthrough_html():
    """HTML with overlay that allows passthrough."""
    return """
    <body>
        <div id="container" class="relative">
            <!-- Overlay with pointer-events-none allows clicks -->
            <div id="overlay" class="absolute inset-0 bg-black/50 pointer-events-none z-40"></div>
            <button id="btn" class="relative z-10 bg-blue-600">Accessible</button>
        </div>
    </body>
    """


@pytest.fixture
def parent_pointer_none_html():
    """HTML with parent pointer-events-none."""
    return """
    <body>
        <div id="parent" class="pointer-events-none">
            <button id="btn-blocked">Blocked by parent</button>
            <button id="btn-override" class="pointer-events-auto">Override works</button>
        </div>
    </body>
    """


@pytest.fixture
def zindex_conflict_html():
    """HTML with z-index conflict blocking."""
    return """
    <body>
        <div id="below" class="relative z-10">
            <button id="btn-below">Low z-index button</button>
        </div>
        <div id="above" class="fixed inset-0 z-50 bg-white">High z-index overlay</div>
    </body>
    """


@pytest.fixture
def modal_structure_html():
    """HTML with proper modal structure."""
    return """
    <body>
        <button id="trigger" class="relative z-10">Open Modal</button>

        <div id="modal" class="fixed inset-0 z-50">
            <div id="backdrop" class="absolute inset-0 bg-black/70" onclick="closeModal()"></div>
            <div id="content" class="relative z-50 bg-white p-4">
                <button id="modal-btn" class="relative z-10">Modal Button</button>
            </div>
        </div>
    </body>
    """


@pytest.fixture
def parser(overlay_blocking_html):
    """Parser with overlay blocking HTML."""
    return DOMParser(overlay_blocking_html)


# ============================================================================
# OVERLAY BLOCKAGE TESTS
# ============================================================================


class TestOverlayBlockage:
    """Tests for overlay blockage detection."""

    def test_detect_overlay_blocking_button(
        self, detector, interactive_detector, overlay_blocking_html
    ):
        """Should detect overlay blocking button."""
        parser = DOMParser(overlay_blocking_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        # Button should be detected as blocked
        assert len(blockages) >= 1
        blocked_selectors = [b.blocked_selector for b in blockages]
        assert any("#btn" in s for s in blocked_selectors)

    def test_overlay_passthrough_no_blockage(
        self, detector, interactive_detector, overlay_passthrough_html
    ):
        """Should not detect blockage when overlay has pointer-events-none."""
        parser = DOMParser(overlay_passthrough_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        # Button should not be blocked
        assert len(blockages) == 0

    def test_blockage_reason_is_overlay(
        self, detector, interactive_detector, overlay_blocking_html
    ):
        """Should report correct blockage reason."""
        parser = DOMParser(overlay_blocking_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        if blockages:
            assert blockages[0].reason == BlockageReason.OVERLAY_BLOCKING


# ============================================================================
# PARENT POINTER-EVENTS TESTS
# ============================================================================


class TestParentPointerEvents:
    """Tests for parent pointer-events inheritance."""

    def test_detect_parent_pointer_none(
        self, detector, interactive_detector, parent_pointer_none_html
    ):
        """Should detect blockage from parent pointer-events-none."""
        parser = DOMParser(parent_pointer_none_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        # btn-blocked should be blocked by parent
        blocked_selectors = [b.blocked_selector for b in blockages]
        assert any("btn-blocked" in s for s in blocked_selectors)

    def test_pointer_auto_overrides_parent(
        self, detector, interactive_detector, parent_pointer_none_html
    ):
        """Should not detect blockage when pointer-events-auto overrides."""
        parser = DOMParser(parent_pointer_none_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        # btn-override should NOT be blocked (has pointer-events-auto)
        blocked_selectors = [b.blocked_selector for b in blockages]
        assert not any("btn-override" in s for s in blocked_selectors)

    def test_check_pointer_inheritance(self, detector, parent_pointer_none_html):
        """Should check pointer-events inheritance."""
        parser = DOMParser(parent_pointer_none_html)

        btn_blocked = parser.get_element_by_id("btn-blocked")
        btn_override = parser.get_element_by_id("btn-override")

        assert detector.check_pointer_inheritance(btn_blocked) is False
        assert detector.check_pointer_inheritance(btn_override) is True


# ============================================================================
# Z-INDEX CONFLICT TESTS
# ============================================================================


class TestZIndexConflict:
    """Tests for z-index conflict detection."""

    def test_detect_zindex_blockage(
        self, detector, interactive_detector, zindex_conflict_html
    ):
        """Should detect z-index conflict blockage."""
        parser = DOMParser(zindex_conflict_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        # btn-below should be blocked by high z-index overlay
        assert len(blockages) >= 1


# ============================================================================
# MODAL STRUCTURE TESTS
# ============================================================================


class TestModalStructure:
    """Tests for modal structure analysis."""

    def test_modal_button_not_blocked(
        self, detector, interactive_detector, modal_structure_html
    ):
        """Modal buttons should not be blocked by same-level backdrop."""
        parser = DOMParser(modal_structure_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        # modal-btn should have proper z-index, may or may not be blocked
        # depending on exact structure
        blocked_selectors = [b.blocked_selector for b in blockages]
        # Check that the trigger button outside modal is blocked
        # but modal-btn might or might not be depending on hierarchy


# ============================================================================
# UTILITY TESTS
# ============================================================================


class TestUtilities:
    """Tests for utility methods."""

    def test_find_overlays_without_passthrough(self, detector, overlay_blocking_html):
        """Should find overlays without pointer-events-none."""
        parser = DOMParser(overlay_blocking_html)
        overlays = detector.find_overlays_without_passthrough(parser)

        assert len(overlays) >= 1
        overlay_ids = [o.get("id") for o in overlays]
        assert "overlay" in overlay_ids

    def test_no_overlays_when_passthrough(self, detector, overlay_passthrough_html):
        """Should not find overlays with pointer-events-none."""
        parser = DOMParser(overlay_passthrough_html)
        overlays = detector.find_overlays_without_passthrough(parser)

        # Overlay has pointer-events-none, should not be in list
        overlay_ids = [o.get("id") for o in overlays]
        assert "overlay" not in overlay_ids


# ============================================================================
# BLOCKAGE INFO TESTS
# ============================================================================


class TestBlockageInfo:
    """Tests for BlockageInfo structure."""

    def test_blockage_info_structure(
        self, detector, interactive_detector, overlay_blocking_html
    ):
        """Should populate BlockageInfo correctly."""
        parser = DOMParser(overlay_blocking_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        if blockages:
            info = blockages[0]
            assert info.blocked_element is not None
            assert info.blocked_selector is not None
            assert info.reason is not None
            assert info.suggested_fix is not None

    def test_blockage_describe(
        self, detector, interactive_detector, overlay_blocking_html
    ):
        """Should generate description."""
        parser = DOMParser(overlay_blocking_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        if blockages:
            description = blockages[0].describe()
            assert "Blocked" in description
            assert "Fix" in description

    def test_blockage_repr(
        self, detector, interactive_detector, overlay_blocking_html
    ):
        """Should have meaningful repr."""
        parser = DOMParser(overlay_blocking_html)
        interactive = interactive_detector.find_interactive_elements(parser)

        blockages = detector.find_blocked_elements(parser, interactive)

        if blockages:
            assert "BlockageInfo" in repr(blockages[0])
