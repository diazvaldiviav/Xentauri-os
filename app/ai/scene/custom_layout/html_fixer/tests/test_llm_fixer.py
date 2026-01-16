"""
Tests for LLMFixer (Sprint 6).

Integration tests with mock LLM provider.
"""

import json
import pytest
from dataclasses import dataclass
from typing import Optional

from html_fixer.fixers.llm import LLMFixer, LLMFixResult
from html_fixer.fixers.llm.contracts import JSPatch, JSPatchType
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.contracts.patches import TailwindPatch


# Mock classes for testing
@dataclass
class MockTokenUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 50

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens


@dataclass
class MockAIResponse:
    content: str
    success: bool = True
    error: Optional[str] = None
    usage: MockTokenUsage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = MockTokenUsage()


class MockGeminiProvider:
    """Mock GeminiProvider for testing."""

    def __init__(self, responses=None):
        """
        Args:
            responses: List of response strings to return in order.
                      If None, returns empty JSON array.
        """
        self.responses = responses or ['[]']
        self.call_count = 0
        self.calls = []

    async def generate(self, **kwargs):
        """Mock generate method."""
        self.calls.append(kwargs)

        response_content = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1

        return MockAIResponse(content=response_content)


class TestLLMFixer:
    """Tests for LLMFixer."""

    def _make_feedback_error(
        self,
        selector: str = ".btn",
    ) -> ClassifiedError:
        """Helper to create feedback error."""
        return ClassifiedError(
            error_type=ErrorType.FEEDBACK_MISSING,
            selector=selector,
            element_tag="button",
            tailwind_info=TailwindInfo(
                all_classes={"bg-blue-500"},
                z_index=None,
                has_pointer_none=False,
                has_pointer_auto=False,
                has_relative=False,
                has_absolute=False,
                has_fixed=False,
                has_transform=False,
                missing_recommended=[],
            ),
            confidence=1.0,
        )

    def _make_js_error(
        self,
        error_type: ErrorType = ErrorType.JS_MISSING_FUNCTION,
        selector: str = "button",
    ) -> ClassifiedError:
        """Helper to create JS error."""
        return ClassifiedError(
            error_type=error_type,
            selector=selector,
            element_tag="button",
            tailwind_info=None,
            confidence=1.0,
        )

    @pytest.mark.asyncio
    async def test_fix_with_no_errors(self):
        """Test fix with no errors returns success."""
        provider = MockGeminiProvider()
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn">Click</button>'
        result = await fixer.fix([], html)

        assert result.success is True
        assert result.fixed_html == html
        assert result.llm_calls_made == 0

    @pytest.mark.asyncio
    async def test_fix_with_non_llm_errors(self):
        """Test that non-LLM errors are skipped."""
        provider = MockGeminiProvider()
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn">Click</button>'

        # ZINDEX_CONFLICT doesn't require LLM
        error = ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector=".btn",
            element_tag="button",
            tailwind_info=None,
            confidence=1.0,
        )

        result = await fixer.fix([error], html)

        assert result.success is True
        assert result.llm_calls_made == 0  # No LLM calls for non-LLM errors

    @pytest.mark.asyncio
    async def test_fixes_feedback_missing(self):
        """Test fixing FEEDBACK_MISSING error."""
        # Mock response with Tailwind patches
        mock_response = json.dumps([
            {
                "selector": ".btn",
                "add": ["hover:bg-blue-600", "active:scale-95", "transition-all"],
                "remove": [],
                "reason": "Add hover and click feedback"
            }
        ])

        provider = MockGeminiProvider(responses=[mock_response])
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn bg-blue-500">Click</button>'
        error = self._make_feedback_error(".btn")

        result = await fixer.fix([error], html)

        assert result.success is True
        assert len(result.tailwind_patches) == 1
        assert "hover:bg-blue-600" in result.tailwind_patches[0].add_classes
        assert "hover:bg-blue-600" in result.fixed_html

    @pytest.mark.asyncio
    async def test_fixes_missing_function(self):
        """Test fixing JS_MISSING_FUNCTION error."""
        mock_response = json.dumps([
            {
                "type": "add_function",
                "function_name": "handleClick",
                "function_code": "function handleClick() { console.log('clicked'); }",
                "reason": "Function was called but not defined"
            }
        ])

        provider = MockGeminiProvider(responses=[mock_response])
        fixer = LLMFixer(provider=provider)

        html = '<button onclick="handleClick()">Click</button>'
        error = self._make_js_error(ErrorType.JS_MISSING_FUNCTION)

        result = await fixer.fix([error], html)

        assert result.success is True
        assert len(result.js_patches) == 1
        assert result.js_patches[0].function_name == "handleClick"
        assert "function handleClick" in result.fixed_html

    @pytest.mark.asyncio
    async def test_combined_tailwind_and_js_errors(self):
        """Test fixing both Tailwind and JS errors in one call."""
        tailwind_response = json.dumps([
            {"selector": ".btn", "add": ["hover:bg-blue-600"], "remove": []}
        ])
        js_response = json.dumps([
            {
                "type": "add_function",
                "function_name": "handleClick",
                "function_code": "function handleClick() {}"
            }
        ])

        provider = MockGeminiProvider(responses=[tailwind_response, js_response])
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn" onclick="handleClick()">Click</button>'
        errors = [
            self._make_feedback_error(".btn"),
            self._make_js_error(ErrorType.JS_MISSING_FUNCTION),
        ]

        result = await fixer.fix(errors, html)

        assert result.success is True
        assert len(result.tailwind_patches) == 1
        assert len(result.js_patches) == 1
        assert provider.call_count == 2  # One call per domain

    @pytest.mark.asyncio
    async def test_handles_empty_llm_response(self):
        """Test handling of empty LLM response."""
        provider = MockGeminiProvider(responses=['[]'])
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn">Click</button>'
        error = self._make_feedback_error()

        result = await fixer.fix([error], html)

        assert result.success is False  # No patches applied
        assert len(result.tailwind_patches) == 0

    @pytest.mark.asyncio
    async def test_handles_invalid_llm_response(self):
        """Test handling of invalid JSON from LLM."""
        provider = MockGeminiProvider(responses=['not valid json'])
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn">Click</button>'
        error = self._make_feedback_error()

        result = await fixer.fix([error], html)

        assert result.success is False
        assert len(result.tailwind_patches) == 0

    @pytest.mark.asyncio
    async def test_validates_patches(self):
        """Test that invalid patches are rejected."""
        # Patch with non-existent selector
        mock_response = json.dumps([
            {"selector": ".nonexistent", "add": ["hover:bg-blue-600"], "remove": []}
        ])

        provider = MockGeminiProvider(responses=[mock_response])
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn">Click</button>'
        error = self._make_feedback_error(".btn")

        result = await fixer.fix([error], html)

        assert result.success is False  # Invalid patch rejected
        assert len(result.tailwind_patches) == 0

    @pytest.mark.asyncio
    async def test_result_description(self):
        """Test LLMFixResult.describe() method."""
        result = LLMFixResult(
            success=True,
            original_html="<div></div>",
            fixed_html="<div class='test'></div>",
            tailwind_patches=[TailwindPatch(".div", ["test"], [])],
            js_patches=[],
            llm_calls_made=1,
            duration_ms=500.0,
        )

        desc = result.describe()

        assert "SUCCESS" in desc
        assert "Tailwind patches: 1" in desc
        assert "JS patches: 0" in desc
        assert "LLM calls: 1" in desc

    @pytest.mark.asyncio
    async def test_extracts_defined_functions(self):
        """Test extraction of defined functions from HTML."""
        fixer = LLMFixer(provider=MockGeminiProvider())

        html = '''
        <script>
        function myFunction() {}
        const arrowFunc = () => {};
        let funcExpr = function() {};
        </script>
        '''

        functions = fixer._extract_defined_functions(html)

        assert "myFunction" in functions
        assert "arrowFunc" in functions
        assert "funcExpr" in functions

    @pytest.mark.asyncio
    async def test_extracts_called_functions(self):
        """Test extraction of called functions from handlers."""
        fixer = LLMFixer(provider=MockGeminiProvider())

        html = '''
        <button onclick="handleClick()">Click</button>
        <input onchange="handleChange(this.value)">
        '''

        functions = fixer._extract_called_functions(html)

        assert "handleClick" in functions
        assert "handleChange" in functions

    @pytest.mark.asyncio
    async def test_extracts_dom_ids(self):
        """Test extraction of DOM IDs from HTML."""
        fixer = LLMFixer(provider=MockGeminiProvider())

        html = '''
        <div id="container">
            <span id="output">Result</span>
            <input id="input-field">
        </div>
        '''

        ids = fixer._extract_dom_ids(html)

        assert "container" in ids
        assert "output" in ids
        assert "input-field" in ids

    @pytest.mark.asyncio
    async def test_no_provider_returns_error(self):
        """Test that disabled provider returns error result."""
        # Use a mock that simulates no provider available
        class NoProvider:
            """Mock that simulates unavailable provider."""
            pass

        # Create fixer and explicitly set _provider to None after init
        fixer = LLMFixer(provider=MockGeminiProvider())
        fixer._provider = None  # Force no provider

        html = '<button class="btn">Click</button>'
        error = self._make_feedback_error()

        result = await fixer.fix([error], html)

        assert result.success is False
        assert result.error_message is not None
        assert "provider" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_tracks_token_usage(self):
        """Test that token usage is tracked."""
        # Return valid patches so retries aren't needed
        mock_response = json.dumps([
            {"selector": ".btn", "add": ["hover:bg-blue-600"], "remove": []}
        ])
        provider = MockGeminiProvider(responses=[mock_response])
        fixer = LLMFixer(provider=provider, max_retries=1)

        html = '<button class="btn">Click</button>'
        error = self._make_feedback_error()

        result = await fixer.fix([error], html)

        assert result.tokens_used > 0
        assert result.llm_calls_made == 1

    @pytest.mark.asyncio
    async def test_tracks_duration(self):
        """Test that duration is tracked."""
        provider = MockGeminiProvider(responses=['[]'])
        fixer = LLMFixer(provider=provider)

        html = '<button class="btn">Click</button>'
        error = self._make_feedback_error()

        result = await fixer.fix([error], html)

        assert result.duration_ms > 0
