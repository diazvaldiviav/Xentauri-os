"""
JavaScript Runtime Validator - Browser-based JS validation using Playwright.

Extends static validation with runtime checks:
1. Validates JavaScript syntax in browser context
2. Captures console.error messages
3. Verifies functions exist at runtime (global scope)
4. Tests event handler execution

Usage:
    from playwright.async_api import async_playwright
    from app.ai.scene.custom_layout.html_fixer.validators import JSRuntimeValidator

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        validator = JSRuntimeValidator()
        result = await validator.validate(html, page)

        for error in result.syntax_errors:
            print(f"Syntax error: {error.message}")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set

from .js_evaluators import JSEvaluators
from .js_validator import JSValidator, JSValidationResult


@dataclass
class RuntimeError:
    """A JavaScript runtime error."""

    error_type: str
    """Type of error: 'syntax', 'reference', 'console', 'uncaught'."""

    message: str
    """Error message."""

    line_number: Optional[int] = None
    """Line number if available."""

    column_number: Optional[int] = None
    """Column number if available."""

    source: Optional[str] = None
    """Source location or script identifier."""

    error_name: Optional[str] = None
    """JavaScript error name (SyntaxError, ReferenceError, etc.)."""


@dataclass
class JSRuntimeResult:
    """Combined static and runtime validation result."""

    static_result: JSValidationResult
    """Result from static validation."""

    syntax_errors: List[RuntimeError] = field(default_factory=list)
    """JavaScript syntax errors found."""

    console_errors: List[RuntimeError] = field(default_factory=list)
    """Errors captured from console.error."""

    undefined_functions: List[str] = field(default_factory=list)
    """Functions that don't exist at runtime."""

    handler_errors: List[Dict[str, Any]] = field(default_factory=list)
    """Errors from testing event handlers."""

    has_errors: bool = False
    """True if any errors were found."""

    @property
    def all_missing_functions(self) -> Set[str]:
        """Get all missing functions (static + runtime)."""
        return set(self.static_result.missing_functions) | set(
            self.undefined_functions
        )

    @property
    def total_errors(self) -> int:
        """Get total number of errors."""
        return (
            len(self.syntax_errors)
            + len(self.console_errors)
            + len(self.all_missing_functions)
            + len(self.static_result.missing_dom_elements)
            + len(self.handler_errors)
        )


class JSRuntimeValidator:
    """
    JavaScript runtime validator using Playwright.

    Combines static analysis with browser-based runtime validation
    for comprehensive error detection.
    """

    def __init__(self):
        """Initialize the runtime validator."""
        self._static_validator = JSValidator()

    async def validate(self, html: str, page) -> JSRuntimeResult:
        """
        Validate JavaScript in HTML using browser.

        Args:
            html: HTML string containing JavaScript
            page: Playwright Page instance

        Returns:
            JSRuntimeResult with all errors found
        """
        from ..analyzers.dom_parser import DOMParser

        # First do static analysis
        parser = DOMParser(html)
        static_result = self._static_validator.validate(parser)

        # Initialize result
        result = JSRuntimeResult(static_result=static_result)

        # Load HTML into page
        try:
            await page.set_content(html, wait_until="networkidle", timeout=10000)
        except Exception as e:
            result.syntax_errors.append(
                RuntimeError(
                    error_type="load_error",
                    message=f"Failed to load HTML: {str(e)}",
                    source="page.set_content",
                )
            )
            result.has_errors = True
            return result

        # Setup error capture
        await page.evaluate(JSEvaluators.CAPTURE_JS_ERRORS)

        # Validate syntax of each inline script
        syntax_errors = await self._validate_syntax(page, static_result)
        result.syntax_errors = syntax_errors

        # Check if called functions exist at runtime
        undefined_functions = await self._check_functions_exist(
            page, static_result.called_functions
        )
        result.undefined_functions = undefined_functions

        # Get any captured errors
        captured = await page.evaluate(JSEvaluators.GET_CAPTURED_ERRORS)
        for err in captured:
            result.console_errors.append(
                RuntimeError(
                    error_type=err.get("type", "console"),
                    message=err.get("message", "Unknown error"),
                    line_number=err.get("lineno"),
                    column_number=err.get("colno"),
                    source=err.get("filename"),
                )
            )

        # Test event handlers if there are any
        handler_errors = await self._test_handlers(page, parser)
        result.handler_errors = handler_errors

        # Set overall error flag
        result.has_errors = (
            len(syntax_errors) > 0
            or len(undefined_functions) > 0
            or len(result.console_errors) > 0
            or len(handler_errors) > 0
            or static_result.has_errors
        )

        return result

    async def _validate_syntax(
        self, page, static_result: JSValidationResult
    ) -> List[RuntimeError]:
        """Validate syntax of all inline scripts."""
        errors = []

        for script in static_result.scripts:
            if script.is_external or not script.content.strip():
                continue

            try:
                result = await page.evaluate(
                    JSEvaluators.VALIDATE_JS_SYNTAX, script.content
                )

                if not result.get("valid", True):
                    errors.append(
                        RuntimeError(
                            error_type="syntax",
                            message=result.get("error", "Syntax error"),
                            line_number=result.get("line"),
                            column_number=result.get("column"),
                            source=f"script at line {script.line_number}",
                            error_name=result.get("name", "SyntaxError"),
                        )
                    )
            except Exception as e:
                errors.append(
                    RuntimeError(
                        error_type="validation_error",
                        message=str(e),
                        source=f"script at line {script.line_number}",
                    )
                )

        return errors

    async def _check_functions_exist(
        self, page, called_functions: Set[str]
    ) -> List[str]:
        """Check which called functions don't exist at runtime."""
        if not called_functions:
            return []

        undefined = []

        try:
            # Batch check all functions
            results = await page.evaluate(
                JSEvaluators.CHECK_FUNCTIONS_BATCH, list(called_functions)
            )

            for fn_name, info in results.items():
                if not info.get("exists", False):
                    undefined.append(fn_name)

        except Exception:
            # Fallback: check one by one
            for fn_name in called_functions:
                try:
                    result = await page.evaluate(
                        JSEvaluators.CHECK_FUNCTION_EXISTS, fn_name
                    )
                    if not result.get("exists", False):
                        undefined.append(fn_name)
                except Exception:
                    undefined.append(fn_name)

        return undefined

    async def _test_handlers(
        self, page, parser
    ) -> List[Dict[str, Any]]:
        """Test event handlers for execution errors."""
        from ..analyzers.event_mapper import EventMapper

        errors = []
        event_mapper = EventMapper()
        events = event_mapper.map_events(parser)

        # Only test click handlers (most common)
        click_events = [e for e in events if e.event_type == "onclick"]

        # Limit to first 10 to avoid timeout
        for event in click_events[:10]:
            try:
                result = await page.evaluate(
                    JSEvaluators.TEST_HANDLER_EXECUTION,
                    [event.selector, "click"],
                )

                if not result.get("success", True):
                    reason = result.get("reason", "unknown")
                    if reason == "execution_error":
                        errors.append(
                            {
                                "selector": event.selector,
                                "event_type": "click",
                                "error": result.get("error"),
                                "error_type": result.get("errorType"),
                                "handler": event.handler,
                            }
                        )
            except Exception as e:
                errors.append(
                    {
                        "selector": event.selector,
                        "event_type": "click",
                        "error": str(e),
                        "error_type": "playwright_error",
                        "handler": event.handler,
                    }
                )

        return errors

    async def validate_static_only(self, html: str) -> JSValidationResult:
        """
        Validate using only static analysis (no browser).

        Args:
            html: HTML string

        Returns:
            JSValidationResult from static validation
        """
        from ..analyzers.dom_parser import DOMParser

        parser = DOMParser(html)
        return self._static_validator.validate(parser)

    def __repr__(self) -> str:
        """String representation."""
        return "JSRuntimeValidator()"
