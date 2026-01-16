"""
Tests for TailwindPromptBuilder (Sprint 6).

Tests the prompt generation and response parsing for Tailwind CSS fixes.
"""

import json
import pytest
from html_fixer.fixers.llm.prompt_builders import TailwindPromptBuilder, FixContext
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.contracts.patches import TailwindPatch


class TestTailwindPromptBuilder:
    """Tests for TailwindPromptBuilder."""

    def _make_error(
        self,
        error_type: ErrorType = ErrorType.FEEDBACK_MISSING,
        selector: str = ".btn",
        tag: str = "button"
    ) -> ClassifiedError:
        """Helper to create test error."""
        return ClassifiedError(
            error_type=error_type,
            selector=selector,
            element_tag=tag,
            tailwind_info=TailwindInfo(
                all_classes={"bg-blue-500", "text-white"},
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

    def test_domain_is_tailwind(self):
        """Test domain property."""
        builder = TailwindPromptBuilder()
        assert builder.domain == "tailwind"

    def test_handles_feedback_errors(self):
        """Test handles_error_types includes feedback errors."""
        builder = TailwindPromptBuilder()
        assert ErrorType.FEEDBACK_MISSING in builder.handles_error_types
        assert ErrorType.FEEDBACK_TOO_SUBTLE in builder.handles_error_types

    def test_does_not_handle_js_errors(self):
        """Test handles_error_types excludes JS errors."""
        builder = TailwindPromptBuilder()
        assert ErrorType.JS_SYNTAX_ERROR not in builder.handles_error_types
        assert ErrorType.JS_MISSING_FUNCTION not in builder.handles_error_types

    def test_system_prompt_exists(self):
        """Test system prompt is defined."""
        builder = TailwindPromptBuilder()
        assert builder.system_prompt
        assert "Tailwind" in builder.system_prompt
        assert "hover" in builder.system_prompt.lower()

    def test_builds_prompt_for_feedback_missing(self):
        """Test prompt generation for FEEDBACK_MISSING error."""
        builder = TailwindPromptBuilder()
        html = '<button class="btn bg-blue-500">Click me</button>'

        error = self._make_error(ErrorType.FEEDBACK_MISSING, ".btn", "button")

        context = FixContext(html=html, errors=[error])
        prompt = builder.build(context)

        assert prompt
        assert "FEEDBACK_MISSING" in prompt
        assert ".btn" in prompt
        assert "bg-blue-500" in prompt

    def test_builds_empty_for_non_feedback_errors(self):
        """Test that non-feedback errors produce no prompt."""
        builder = TailwindPromptBuilder()
        html = '<button onclick="handleClick()">Click</button>'

        error = ClassifiedError(
            error_type=ErrorType.JS_MISSING_FUNCTION,
            selector="button",
            element_tag="button",
            tailwind_info=None,
            confidence=1.0,
        )

        context = FixContext(html=html, errors=[error])
        prompt = builder.build(context)

        assert prompt == ""

    def test_parses_valid_json_response(self):
        """Test parsing valid LLM response."""
        builder = TailwindPromptBuilder()

        response = json.dumps([
            {
                "selector": ".btn",
                "add": ["hover:bg-blue-600", "active:scale-95", "transition-all"],
                "remove": [],
                "reason": "Add hover and click feedback"
            }
        ])

        context = FixContext(html="<button class='btn'>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert isinstance(patches[0], TailwindPatch)
        assert patches[0].selector == ".btn"
        assert "hover:bg-blue-600" in patches[0].add_classes
        assert "active:scale-95" in patches[0].add_classes

    def test_parses_multiple_patches(self):
        """Test parsing response with multiple patches."""
        builder = TailwindPromptBuilder()

        response = json.dumps([
            {"selector": ".btn-1", "add": ["hover:bg-blue-600"], "remove": []},
            {"selector": ".btn-2", "add": ["hover:bg-red-600"], "remove": []},
        ])

        context = FixContext(html="<div></div>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 2
        assert patches[0].selector == ".btn-1"
        assert patches[1].selector == ".btn-2"

    def test_extracts_json_from_markdown(self):
        """Test extraction of JSON from markdown code blocks."""
        builder = TailwindPromptBuilder()

        response = '''Here's the fix:

```json
[
  {
    "selector": ".btn",
    "add": ["hover:bg-blue-600"],
    "remove": []
  }
]
```

This will add hover feedback.'''

        context = FixContext(html="<button class='btn'>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert patches[0].selector == ".btn"

    def test_handles_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        builder = TailwindPromptBuilder()

        response = "This is not valid JSON at all"

        context = FixContext(html="<button>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert patches == []

    def test_ignores_patches_without_selector(self):
        """Test that patches without selector are ignored."""
        builder = TailwindPromptBuilder()

        response = json.dumps([
            {"add": ["hover:bg-blue-600"], "remove": []},  # Missing selector
        ])

        context = FixContext(html="<button>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert patches == []

    def test_retry_context_included(self):
        """Test that retry attempts include previous patches."""
        builder = TailwindPromptBuilder()
        html = '<button class="btn">Click</button>'

        error = self._make_error()
        previous_patch = TailwindPatch(
            selector=".btn",
            add_classes=["hover:bg-blue-600"],
            remove_classes=[],
        )

        context = FixContext(
            html=html,
            errors=[error],
            attempt_number=2,
            previous_patches=[previous_patch],
        )

        prompt = builder.build(context)

        assert "attempt #2" in prompt.lower()
        assert "previous" in prompt.lower()

    def test_can_handle_filters_correctly(self):
        """Test can_handle method."""
        builder = TailwindPromptBuilder()

        feedback_error = self._make_error(ErrorType.FEEDBACK_MISSING)
        js_error = ClassifiedError(
            error_type=ErrorType.JS_SYNTAX_ERROR,
            selector="script",
            element_tag="script",
            tailwind_info=None,
            confidence=1.0,
        )

        assert builder.can_handle(feedback_error) is True
        assert builder.can_handle(js_error) is False

    def test_filter_errors(self):
        """Test filter_errors method."""
        builder = TailwindPromptBuilder()

        errors = [
            self._make_error(ErrorType.FEEDBACK_MISSING),
            ClassifiedError(
                error_type=ErrorType.JS_MISSING_FUNCTION,
                selector="button",
                element_tag="button",
                tailwind_info=None,
                confidence=1.0,
            ),
            self._make_error(ErrorType.FEEDBACK_TOO_SUBTLE),
        ]

        filtered = builder.filter_errors(errors)

        assert len(filtered) == 2
        assert all(e.error_type.is_feedback_related for e in filtered)
