"""
Tests for Sandbox visual validation (Sprint 4).

Tests the basic sandbox functionality:
- Contracts (dataclasses)
- Sandbox initialization
- Error extraction
- Screenshot comparison
"""

import pytest
from html_fixer.sandbox import (
    Sandbox,
    ElementInfo,
    ElementResult,
    ElementStatus,
    ValidationResult,
)


class TestElementStatus:
    """Tests for ElementStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        assert ElementStatus.RESPONSIVE
        assert ElementStatus.NO_VISUAL_CHANGE
        assert ElementStatus.INTERCEPTED
        assert ElementStatus.TIMEOUT
        assert ElementStatus.ERROR
        assert ElementStatus.NOT_TESTED


class TestElementInfo:
    """Tests for ElementInfo dataclass."""

    def test_create_element_info(self):
        """Test creating ElementInfo."""
        info = ElementInfo(
            selector=".btn",
            tag="button",
            bounding_box={"x": 100, "y": 200, "width": 80, "height": 40},
            has_handler=True,
            inner_text="Click me",
        )

        assert info.selector == ".btn"
        assert info.tag == "button"
        assert info.bounding_box["width"] == 80
        assert info.has_handler is True
        assert info.inner_text == "Click me"

    def test_repr(self):
        """Test string representation."""
        info = ElementInfo(
            selector="#submit",
            tag="button",
            inner_text="Submit form",
        )
        repr_str = repr(info)
        assert "#submit" in repr_str
        assert "button" in repr_str


class TestElementResult:
    """Tests for ElementResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = ElementResult(
            selector=".btn",
            status=ElementStatus.RESPONSIVE,
            diff_ratio=0.15,
        )

        assert result.is_success is True
        assert result.is_blocked is False
        assert result.has_feedback is True

    def test_create_blocked_result(self):
        """Test creating a blocked result."""
        result = ElementResult(
            selector=".btn",
            status=ElementStatus.INTERCEPTED,
            blocking_element=".overlay",
            error="Element intercepted",
        )

        assert result.is_success is False
        assert result.is_blocked is True
        assert result.blocking_element == ".overlay"

    def test_has_feedback_threshold(self):
        """Test feedback detection threshold."""
        no_feedback = ElementResult(
            selector=".btn",
            status=ElementStatus.RESPONSIVE,
            diff_ratio=0.01,  # Below 0.02 threshold
        )
        has_feedback = ElementResult(
            selector=".btn",
            status=ElementStatus.RESPONSIVE,
            diff_ratio=0.03,  # Above 0.02 threshold
        )

        assert no_feedback.has_feedback is False
        assert has_feedback.has_feedback is True


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_empty_result(self):
        """Test empty validation result."""
        result = ValidationResult()

        assert result.total_elements == 0
        assert result.responsive_elements == 0
        assert result.blocked_elements == 0
        assert result.success_rate == 1.0
        assert result.passed is True

    def test_result_with_elements(self):
        """Test result with element results."""
        result = ValidationResult(
            element_results=[
                ElementResult(".btn1", ElementStatus.RESPONSIVE),
                ElementResult(".btn2", ElementStatus.RESPONSIVE),
                ElementResult(".btn3", ElementStatus.INTERCEPTED, blocking_element=".overlay"),
            ]
        )

        assert result.total_elements == 3
        assert result.responsive_elements == 2
        assert result.blocked_elements == 1
        assert result.success_rate == pytest.approx(2/3)
        assert result.passed is False  # Has blocked elements

    def test_result_with_js_errors(self):
        """Test result with JavaScript errors."""
        result = ValidationResult(
            element_results=[
                ElementResult(".btn", ElementStatus.RESPONSIVE),
            ],
            js_errors=["TypeError: Cannot read property 'x' of undefined"],
        )

        assert result.has_js_errors is True
        assert result.passed is False  # Has JS errors

    def test_get_blocked(self):
        """Test getting blocked elements."""
        result = ValidationResult(
            element_results=[
                ElementResult(".btn1", ElementStatus.RESPONSIVE),
                ElementResult(".btn2", ElementStatus.INTERCEPTED, blocking_element=".overlay"),
                ElementResult(".btn3", ElementStatus.INTERCEPTED, blocking_element=".modal"),
            ]
        )

        blocked = result.get_blocked()
        assert len(blocked) == 2
        assert all(r.is_blocked for r in blocked)

    def test_describe(self):
        """Test human-readable description."""
        result = ValidationResult(
            element_results=[
                ElementResult(".btn", ElementStatus.RESPONSIVE),
            ],
            validation_time_ms=150.5,
        )

        desc = result.describe()
        assert "1/1 responsive" in desc
        assert "150ms" in desc


class TestSandbox:
    """Tests for Sandbox class."""

    def test_initialization_defaults(self):
        """Test sandbox default initialization."""
        sandbox = Sandbox()

        assert sandbox.viewport["width"] == 1920
        assert sandbox.viewport["height"] == 1080
        assert sandbox.timeout_ms == 2000
        assert sandbox.stabilization_ms == 500

    def test_initialization_custom(self):
        """Test sandbox custom initialization."""
        sandbox = Sandbox(
            viewport_width=1280,
            viewport_height=720,
            timeout_ms=5000,
            stabilization_ms=1000,
        )

        assert sandbox.viewport["width"] == 1280
        assert sandbox.viewport["height"] == 720
        assert sandbox.timeout_ms == 5000
        assert sandbox.stabilization_ms == 1000

    def test_compare_screenshots_identical(self):
        """Test screenshot comparison with identical images."""
        sandbox = Sandbox()

        screenshot = b"identical image content here"
        diff = sandbox._compare_screenshots(screenshot, screenshot)

        assert diff == 0.0

    def test_compare_screenshots_different(self):
        """Test screenshot comparison with different images."""
        sandbox = Sandbox()

        before = b"aaaaaaaaaa"
        after = b"aaaaaabbbb"
        diff = sandbox._compare_screenshots(before, after)

        assert diff > 0.0
        assert diff < 1.0

    def test_compare_screenshots_completely_different(self):
        """Test screenshot comparison with completely different images."""
        sandbox = Sandbox()

        before = b"aaaaaaaaaa"
        after = b"bbbbbbbbbb"
        diff = sandbox._compare_screenshots(before, after)

        assert diff == 1.0

    def test_extract_blocker_with_class(self):
        """Test blocker extraction from error with class."""
        sandbox = Sandbox()

        error_msg = "Element <div class='overlay bg-black'> intercepts pointer events"
        blocker = sandbox._extract_blocker(error_msg)

        assert blocker == "div.overlay"

    def test_extract_blocker_with_id(self):
        """Test blocker extraction from error with id."""
        sandbox = Sandbox()

        error_msg = "Element <div id='modal-backdrop'> intercepts pointer events"
        blocker = sandbox._extract_blocker(error_msg)

        assert blocker == "#modal-backdrop"

    def test_extract_blocker_simple_tag(self):
        """Test blocker extraction from error with just tag."""
        sandbox = Sandbox()

        error_msg = "Element <div> intercepts pointer events"
        blocker = sandbox._extract_blocker(error_msg)

        assert blocker == "div"

    def test_extract_blocker_no_match(self):
        """Test blocker extraction with no match."""
        sandbox = Sandbox()

        error_msg = "Some other error message"
        blocker = sandbox._extract_blocker(error_msg)

        assert blocker is None


class TestSandboxIntegration:
    """Integration tests for Sandbox (requires Playwright)."""

    @pytest.mark.asyncio
    async def test_check_playwright_available(self):
        """Test Playwright availability check."""
        sandbox = Sandbox()
        available = await sandbox.check_playwright_available()

        # Just check it returns a boolean
        assert isinstance(available, bool)

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("playwright", reason="Playwright not installed"),
        reason="Playwright not installed"
    )
    async def test_validate_simple_html(self):
        """Test validation of simple HTML with button."""
        sandbox = Sandbox()

        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <button onclick="this.style.background='red'">Click me</button>
        </body>
        </html>
        """

        result = await sandbox.validate(html)

        assert isinstance(result, ValidationResult)
        assert result.validation_time_ms > 0
