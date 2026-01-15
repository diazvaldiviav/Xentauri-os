"""
Unit tests for PlaywrightDiagnostic.

Tests browser-based element diagnosis.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.validators.playwright_diagnostic import (
    PlaywrightDiagnostic,
    ElementDiagnosis,
    BoundingRect,
    VisibilityInfo,
    diagnose_element,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def diagnostic():
    """PlaywrightDiagnostic instance."""
    return PlaywrightDiagnostic()


# ============================================================================
# BOUNDING RECT TESTS
# ============================================================================


class TestBoundingRect:
    """Tests for BoundingRect dataclass."""

    def test_center_x(self):
        """Should calculate center X correctly."""
        rect = BoundingRect(x=100, y=50, width=200, height=100)
        assert rect.center_x == 200  # 100 + 200/2

    def test_center_y(self):
        """Should calculate center Y correctly."""
        rect = BoundingRect(x=100, y=50, width=200, height=100)
        assert rect.center_y == 100  # 50 + 100/2

    def test_is_visible_size_true(self):
        """Should return True for visible dimensions."""
        rect = BoundingRect(x=0, y=0, width=100, height=50)
        assert rect.is_visible_size is True

    def test_is_visible_size_false_zero_width(self):
        """Should return False for zero width."""
        rect = BoundingRect(x=0, y=0, width=0, height=50)
        assert rect.is_visible_size is False

    def test_is_in_viewport_true(self):
        """Should return True when in viewport."""
        rect = BoundingRect(x=100, y=100, width=100, height=50)
        assert rect.is_in_viewport(1920, 1080) is True

    def test_is_in_viewport_false_offscreen(self):
        """Should return False when off screen."""
        rect = BoundingRect(x=2000, y=100, width=100, height=50)
        assert rect.is_in_viewport(1920, 1080) is False

    def test_to_dict(self):
        """Should convert to dictionary."""
        rect = BoundingRect(x=10, y=20, width=30, height=40)
        d = rect.to_dict()
        assert d == {"x": 10, "y": 20, "width": 30, "height": 40}


# ============================================================================
# VISIBILITY INFO TESTS
# ============================================================================


class TestVisibilityInfo:
    """Tests for VisibilityInfo dataclass."""

    def test_is_visible_true(self):
        """Should return True for visible element."""
        info = VisibilityInfo(
            display="block",
            visibility="visible",
            opacity=1.0,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.is_visible is True

    def test_is_visible_false_display_none(self):
        """Should return False for display:none."""
        info = VisibilityInfo(
            display="none",
            visibility="visible",
            opacity=1.0,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.is_visible is False

    def test_is_visible_false_visibility_hidden(self):
        """Should return False for visibility:hidden."""
        info = VisibilityInfo(
            display="block",
            visibility="hidden",
            opacity=1.0,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.is_visible is False

    def test_is_visible_false_zero_opacity(self):
        """Should return False for zero opacity."""
        info = VisibilityInfo(
            display="block",
            visibility="visible",
            opacity=0.0,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.is_visible is False

    def test_visibility_issue_display_none(self):
        """Should detect display:none issue."""
        from html_fixer.contracts.errors import ErrorType

        info = VisibilityInfo(
            display="none",
            visibility="visible",
            opacity=1.0,
            width=0,
            height=0,
            in_viewport=False,
        )
        assert info.visibility_issue == ErrorType.INVISIBLE_DISPLAY

    def test_visibility_issue_visibility_hidden(self):
        """Should detect visibility:hidden issue."""
        from html_fixer.contracts.errors import ErrorType

        info = VisibilityInfo(
            display="block",
            visibility="hidden",
            opacity=1.0,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.visibility_issue == ErrorType.INVISIBLE_VISIBILITY

    def test_visibility_issue_low_opacity(self):
        """Should detect low opacity issue."""
        from html_fixer.contracts.errors import ErrorType

        info = VisibilityInfo(
            display="block",
            visibility="visible",
            opacity=0.05,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.visibility_issue == ErrorType.INVISIBLE_OPACITY

    def test_visibility_issue_none(self):
        """Should return None when no issue."""
        info = VisibilityInfo(
            display="block",
            visibility="visible",
            opacity=1.0,
            width=100,
            height=50,
            in_viewport=True,
        )
        assert info.visibility_issue is None


# ============================================================================
# ELEMENT DIAGNOSIS TESTS
# ============================================================================


class TestElementDiagnosis:
    """Tests for ElementDiagnosis dataclass."""

    def test_is_clickable_not_found(self):
        """Should return False when not found."""
        diagnosis = ElementDiagnosis(
            found=False,
            selector="#btn",
            visibility=None,
            interceptor=None,
            stacking=None,
            pointer_events=None,
            rect=None,
        )
        assert diagnosis.is_clickable is False

    def test_is_clickable_visible(self):
        """Should return True for visible element."""
        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn",
            visibility=VisibilityInfo(
                display="block",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=50,
                in_viewport=True,
            ),
            interceptor=None,
            stacking=None,
            pointer_events=None,
            rect=BoundingRect(x=100, y=100, width=100, height=50),
        )
        assert diagnosis.is_clickable is True

    def test_is_clickable_with_interceptor(self):
        """Should return False with blocking interceptor."""
        from html_fixer.validators.playwright_diagnostic import InterceptorInfo

        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn",
            visibility=VisibilityInfo(
                display="block",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=50,
                in_viewport=True,
            ),
            interceptor=InterceptorInfo(
                selector="#overlay",
                tag_name="div",
                classes=["overlay"],
                is_overlay=True,
                has_pointer_events_none=False,
                z_index=50,
            ),
            stacking=None,
            pointer_events=None,
            rect=BoundingRect(x=100, y=100, width=100, height=50),
        )
        assert diagnosis.is_clickable is False

    def test_to_dict(self):
        """Should serialize to dictionary."""
        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn",
            visibility=VisibilityInfo(
                display="block",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=50,
                in_viewport=True,
            ),
            interceptor=None,
            stacking=None,
            pointer_events=None,
            rect=BoundingRect(x=100, y=100, width=100, height=50),
        )

        d = diagnosis.to_dict()
        assert d["found"] is True
        assert d["selector"] == "#btn"
        assert d["is_clickable"] is True


# ============================================================================
# PLAYWRIGHT DIAGNOSTIC TESTS (Require Playwright)
# ============================================================================


@pytest.mark.playwright
class TestPlaywrightDiagnostic:
    """Tests that require Playwright browser."""

    async def test_diagnose_visible_element(self, page_with_html, diagnostic):
        """Test diagnosis of visible element."""
        html = """
        <html><body>
            <button id="btn" class="relative z-10">Click me</button>
        </body></html>
        """
        page = await page_with_html(html)

        diagnosis = await diagnostic.diagnose_element(page, "#btn")

        assert diagnosis.found is True
        assert diagnosis.visibility is not None
        assert diagnosis.visibility.display != "none"

    async def test_diagnose_element_not_found(self, page_with_html, diagnostic):
        """Test diagnosis when element doesn't exist."""
        html = "<html><body><div>Empty</div></body></html>"
        page = await page_with_html(html)

        diagnosis = await diagnostic.diagnose_element(page, "#nonexistent")

        assert diagnosis.found is False
        assert diagnosis.is_clickable is False

    async def test_diagnose_hidden_element(self, page_with_html, diagnostic):
        """Test diagnosis of display:none element."""
        html = """
        <html><body>
            <button id="hidden" style="display:none">Hidden</button>
        </body></html>
        """
        page = await page_with_html(html)

        diagnosis = await diagnostic.diagnose_element(page, "#hidden")

        assert diagnosis.found is True
        assert diagnosis.visibility.display == "none"
        assert diagnosis.visibility.is_visible is False

    async def test_diagnose_blocked_element(self, page_with_html, diagnostic):
        """Test diagnosis of element blocked by overlay."""
        html = """
        <html><body style="position:relative">
            <button id="btn" style="position:relative;z-index:1">Click me</button>
            <div id="overlay" style="position:absolute;top:0;left:0;right:0;bottom:0;z-index:10;background:rgba(0,0,0,0.5)"></div>
        </body></html>
        """
        page = await page_with_html(html)

        diagnosis = await diagnostic.diagnose_element(page, "#btn")

        assert diagnosis.found is True
        assert diagnosis.interceptor is not None
        assert diagnosis.is_clickable is False

    async def test_convenience_function(self, page_with_html):
        """Test diagnose_element convenience function."""
        html = """
        <html><body>
            <button id="btn">Click me</button>
        </body></html>
        """
        page = await page_with_html(html)

        diagnosis = await diagnose_element(page, "#btn")

        assert diagnosis.found is True


# ============================================================================
# INTERCEPTOR DETECTION TESTS
# ============================================================================


@pytest.mark.playwright
class TestInterceptorDetection:
    """Tests for interceptor detection."""

    async def test_find_interceptor_at_point(self, page_with_html, diagnostic):
        """Test finding element at point."""
        html = """
        <html><body style="margin:0">
            <div id="box" style="position:absolute;top:50px;left:50px;width:100px;height:100px;background:red"></div>
        </body></html>
        """
        page = await page_with_html(html)

        interceptor = await diagnostic.find_interceptor_at_point(page, 100, 100)

        assert interceptor is not None
        assert interceptor.selector == "#box"

    async def test_find_interceptor_at_empty_point(self, page_with_html, diagnostic):
        """Test finding element at empty point returns body or html."""
        html = """
        <html><body style="margin:0;width:100%;height:100%">
        </body></html>
        """
        page = await page_with_html(html)

        interceptor = await diagnostic.find_interceptor_at_point(page, 100, 100)

        # Should find body or html element
        assert interceptor is not None
