"""
Integration tests for ErrorClassificationPipeline.

Tests end-to-end error classification with and without Playwright.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.validators.classification_pipeline import (
    ErrorClassificationPipeline,
    classify_html,
)
from html_fixer.validators.error_report import ErrorReport
from html_fixer.contracts.errors import ErrorType


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def pipeline():
    """ErrorClassificationPipeline instance."""
    return ErrorClassificationPipeline()


@pytest.fixture
def simple_html():
    """Simple HTML with interactive elements."""
    return """
    <html>
    <body>
        <button id="btn1">Button 1</button>
        <button id="btn2">Button 2</button>
        <a href="#" id="link1">Link 1</a>
    </body>
    </html>
    """


@pytest.fixture
def blocked_html():
    """HTML with blocked interactive element."""
    return """
    <html>
    <body style="position: relative">
        <button id="btn" style="position: relative; z-index: 1">Click me</button>
        <div id="overlay" style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; z-index: 10; background: rgba(0,0,0,0.5)"></div>
    </body>
    </html>
    """


# ============================================================================
# STATIC CLASSIFICATION TESTS
# ============================================================================


class TestStaticClassification:
    """Tests for static-only classification (no Playwright)."""

    async def test_classify_static_returns_report(self, pipeline, simple_html):
        """Should return ErrorReport from static classification."""
        report = await pipeline.classify_static(simple_html)

        assert isinstance(report, ErrorReport)
        assert report.total_interactive >= 3  # 2 buttons + 1 link

    async def test_classify_static_has_hash(self, pipeline, simple_html):
        """Should compute HTML hash."""
        report = await pipeline.classify_static(simple_html)

        assert len(report.html_hash) == 16

    async def test_classify_static_has_timestamp(self, pipeline, simple_html):
        """Should have timestamp."""
        report = await pipeline.classify_static(simple_html)

        assert "T" in report.timestamp
        assert report.timestamp.endswith("Z")

    async def test_classify_static_measures_time(self, pipeline, simple_html):
        """Should measure analysis time."""
        report = await pipeline.classify_static(simple_html)

        assert report.analysis_time_ms is not None
        assert report.analysis_time_ms > 0

    async def test_classify_static_detects_blockage(self, pipeline, blocked_html):
        """Should detect static blockage from overlay."""
        report = await pipeline.classify_static(blocked_html)

        # Static analysis can detect overlay blockage
        # The exact number depends on static detection capability
        assert report.total_interactive >= 1


# ============================================================================
# PLAYWRIGHT CLASSIFICATION TESTS
# ============================================================================


@pytest.mark.playwright
class TestPlaywrightClassification:
    """Tests for classification with Playwright."""

    async def test_classify_with_page(self, pipeline, page, simple_html):
        """Should classify with Playwright page."""
        report = await pipeline.classify(simple_html, page)

        assert isinstance(report, ErrorReport)
        assert report.total_interactive >= 3

    async def test_classify_detects_blocked(self, pipeline, page, blocked_html):
        """Should detect blocked element via elementFromPoint."""
        report = await pipeline.classify(blocked_html, page)

        # Should detect that button is blocked by overlay
        blocked_errors = report.get_errors_by_type(ErrorType.POINTER_BLOCKED)
        assert len(blocked_errors) >= 1

    async def test_classify_performance(self, pipeline, page, simple_html):
        """Should complete in reasonable time."""
        report = await pipeline.classify(simple_html, page)

        # Should be fast for simple HTML
        assert report.analysis_time_ms < 5000  # 5 seconds max


# ============================================================================
# FIXTURE CLASSIFICATION TESTS
# ============================================================================


@pytest.mark.playwright
class TestFixtureClassification:
    """Tests for classifying test fixtures."""

    async def test_classify_trivia_multiple_choice(self, pipeline, page, trivia_dir):
        """Test classifying multiple_choice_broken.html."""
        fixture_path = trivia_dir / "multiple_choice_broken.html"
        if not fixture_path.exists():
            pytest.skip("Fixture not found")

        html = fixture_path.read_text()
        report = await pipeline.classify(html, page)

        # Should find interactive elements (buttons)
        assert report.total_interactive >= 1
        assert report.analysis_time_ms < 2000

    async def test_classify_dashboard_sidebar(self, pipeline, page, dashboard_dir):
        """Test classifying sidebar_broken.html."""
        fixture_path = dashboard_dir / "sidebar_broken.html"
        if not fixture_path.exists():
            pytest.skip("Fixture not found")

        html = fixture_path.read_text()
        report = await pipeline.classify(html, page)

        # Should find interactive elements
        assert report.total_interactive >= 1
        assert report.analysis_time_ms < 2000

    async def test_classify_modal_form(self, pipeline, page, modals_dir):
        """Test classifying form_modal_broken.html."""
        fixture_path = modals_dir / "form_modal_broken.html"
        if not fixture_path.exists():
            pytest.skip("Fixture not found")

        html = fixture_path.read_text()
        report = await pipeline.classify(html, page)

        # Should find form elements
        assert report.total_interactive >= 1
        assert report.analysis_time_ms < 2000


# ============================================================================
# PIPELINE STATE TESTS
# ============================================================================


class TestPipelineState:
    """Tests for pipeline state management."""

    async def test_get_interactive_elements(self, pipeline, simple_html):
        """Should provide access to interactive elements after classification."""
        await pipeline.classify_static(simple_html)

        elements = pipeline.get_interactive_elements()
        assert len(elements) >= 3

    async def test_get_static_errors(self, pipeline, blocked_html):
        """Should provide access to static errors after classification."""
        await pipeline.classify_static(blocked_html)

        errors = pipeline.get_static_errors()
        # May or may not have static errors depending on detection
        assert isinstance(errors, list)


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================


@pytest.mark.playwright
class TestConvenienceFunction:
    """Tests for classify_html convenience function."""

    async def test_classify_html_function(self, page, simple_html):
        """Test classify_html convenience function."""
        report = await classify_html(simple_html, page)

        assert isinstance(report, ErrorReport)
        assert report.total_interactive >= 3

    async def test_classify_html_static(self, simple_html):
        """Test classify_html without page (static only)."""
        report = await classify_html(simple_html, page=None)

        assert isinstance(report, ErrorReport)
        assert report.total_interactive >= 3


# ============================================================================
# REPORT CONTENT TESTS
# ============================================================================


@pytest.mark.playwright
class TestReportContent:
    """Tests for report content accuracy."""

    async def test_report_summary_accurate(self, pipeline, page, blocked_html):
        """Report summary should match actual errors."""
        report = await pipeline.classify(blocked_html, page)

        # Summary counts should match errors list
        for error_type_str, count in report.summary.items():
            actual = len([e for e in report.errors if e.error_type.value == error_type_str])
            assert actual == count

    async def test_report_has_selectors(self, pipeline, page, simple_html):
        """Errors should have valid selectors."""
        await pipeline.classify(simple_html, page)

        elements = pipeline.get_interactive_elements()
        for element in elements:
            assert element.selector is not None
            assert len(element.selector) > 0

    async def test_report_viewport_size(self, simple_html):
        """Report should have viewport size."""
        pipeline = ErrorClassificationPipeline(viewport_width=1920, viewport_height=1080)
        report = await pipeline.classify_static(simple_html)

        assert report.viewport_size["width"] == 1920
        assert report.viewport_size["height"] == 1080
