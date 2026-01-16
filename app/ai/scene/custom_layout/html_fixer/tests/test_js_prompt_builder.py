"""
Tests for JSPromptBuilder (Sprint 6).

Tests the prompt generation and response parsing for JavaScript fixes.
"""

import json
import pytest
from html_fixer.fixers.llm.prompt_builders import JSPromptBuilder, FixContext
from html_fixer.fixers.llm.contracts import JSPatch, JSPatchType
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError


class TestJSPromptBuilder:
    """Tests for JSPromptBuilder."""

    def _make_js_error(
        self,
        error_type: ErrorType = ErrorType.JS_MISSING_FUNCTION,
        selector: str = "button",
        tag: str = "button",
    ) -> ClassifiedError:
        """Helper to create test JS error."""
        return ClassifiedError(
            error_type=error_type,
            selector=selector,
            element_tag=tag,
            tailwind_info=None,
            confidence=1.0,
        )

    def test_domain_is_js(self):
        """Test domain property."""
        builder = JSPromptBuilder()
        assert builder.domain == "js"

    def test_handles_js_errors(self):
        """Test handles_error_types includes JS errors."""
        builder = JSPromptBuilder()
        assert ErrorType.JS_SYNTAX_ERROR in builder.handles_error_types
        assert ErrorType.JS_MISSING_FUNCTION in builder.handles_error_types
        assert ErrorType.JS_MISSING_DOM_ELEMENT in builder.handles_error_types
        assert ErrorType.JS_UNDEFINED_VARIABLE in builder.handles_error_types

    def test_does_not_handle_feedback_errors(self):
        """Test handles_error_types excludes feedback errors."""
        builder = JSPromptBuilder()
        assert ErrorType.FEEDBACK_MISSING not in builder.handles_error_types
        assert ErrorType.FEEDBACK_TOO_SUBTLE not in builder.handles_error_types

    def test_system_prompt_exists(self):
        """Test system prompt is defined."""
        builder = JSPromptBuilder()
        assert builder.system_prompt
        assert "JavaScript" in builder.system_prompt
        assert "add_function" in builder.system_prompt.lower()

    def test_builds_prompt_for_missing_function(self):
        """Test prompt generation for JS_MISSING_FUNCTION error."""
        builder = JSPromptBuilder()
        html = '''
        <button onclick="handleClick()">Click me</button>
        <script>
        // No handleClick function defined
        </script>
        '''

        error = self._make_js_error(ErrorType.JS_MISSING_FUNCTION)

        context = FixContext(
            html=html,
            errors=[error],
            called_functions={"handleClick"},
            defined_functions=set(),
        )
        prompt = builder.build(context)

        assert prompt
        assert "handleClick" in prompt
        assert "JS_MISSING_FUNCTION" in prompt

    def test_builds_prompt_for_syntax_error(self):
        """Test prompt generation for JS_SYNTAX_ERROR."""
        builder = JSPromptBuilder()
        html = '''
        <script>
        function test() {
            const x = 10
            console.log(x
        }
        </script>
        '''

        error = self._make_js_error(ErrorType.JS_SYNTAX_ERROR, "script", "script")

        context = FixContext(html=html, errors=[error])
        prompt = builder.build(context)

        assert prompt
        assert "JS_SYNTAX_ERROR" in prompt

    def test_builds_empty_for_non_js_errors(self):
        """Test that non-JS errors produce no prompt."""
        builder = JSPromptBuilder()
        html = '<button class="btn">Click</button>'

        error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_MISSING,
            selector=".btn",
            element_tag="button",
            tailwind_info=None,
            confidence=1.0,
        )

        context = FixContext(html=html, errors=[error])
        prompt = builder.build(context)

        assert prompt == ""

    def test_parses_add_function_patch(self):
        """Test parsing ADD_FUNCTION patch from response."""
        builder = JSPromptBuilder()

        response = json.dumps([
            {
                "type": "add_function",
                "function_name": "handleClick",
                "function_code": "function handleClick() {\n  console.log('clicked');\n}",
                "reason": "Function was called but not defined"
            }
        ])

        context = FixContext(html="<button>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert isinstance(patches[0], JSPatch)
        assert patches[0].patch_type == JSPatchType.ADD_FUNCTION
        assert patches[0].function_name == "handleClick"
        assert "function handleClick" in patches[0].function_code

    def test_parses_fix_dom_reference_patch(self):
        """Test parsing FIX_DOM_REFERENCE patch."""
        builder = JSPromptBuilder()

        response = json.dumps([
            {
                "type": "fix_dom_reference",
                "old_reference": "result",
                "new_reference": "output",
                "reason": "Element 'result' doesn't exist"
            }
        ])

        context = FixContext(html="<div id='output'></div>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert patches[0].patch_type == JSPatchType.FIX_DOM_REFERENCE
        assert patches[0].old_reference == "result"
        assert patches[0].new_reference == "output"

    def test_parses_fix_syntax_patch(self):
        """Test parsing FIX_SYNTAX patch."""
        builder = JSPromptBuilder()

        response = json.dumps([
            {
                "type": "fix_syntax",
                "script_index": 0,
                "line_start": 5,
                "line_end": 5,
                "replacement_code": "const x = 10;",
                "reason": "Missing semicolon"
            }
        ])

        context = FixContext(html="<script></script>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert patches[0].patch_type == JSPatchType.FIX_SYNTAX
        assert patches[0].script_index == 0
        assert patches[0].line_start == 5

    def test_parses_modify_handler_patch(self):
        """Test parsing MODIFY_HANDLER patch."""
        builder = JSPromptBuilder()

        response = json.dumps([
            {
                "type": "modify_handler",
                "selector": "button.submit",
                "old_handler": "submit()",
                "new_handler": "handleSubmit(event)",
                "reason": "Function name was incorrect"
            }
        ])

        context = FixContext(html="<button class='submit'>Go</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert patches[0].patch_type == JSPatchType.MODIFY_HANDLER
        assert patches[0].selector == "button.submit"
        assert patches[0].new_handler == "handleSubmit(event)"

    def test_parses_multiple_patches(self):
        """Test parsing response with multiple patches."""
        builder = JSPromptBuilder()

        response = json.dumps([
            {"type": "add_function", "function_name": "fn1", "function_code": "function fn1() {}"},
            {"type": "add_function", "function_name": "fn2", "function_code": "function fn2() {}"},
        ])

        context = FixContext(html="<div></div>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 2

    def test_extracts_json_from_markdown(self):
        """Test extraction of JSON from markdown code blocks."""
        builder = JSPromptBuilder()

        response = '''Here's the JavaScript fix:

```json
[
  {
    "type": "add_function",
    "function_name": "handleClick",
    "function_code": "function handleClick() {}"
  }
]
```

This adds the missing function.'''

        context = FixContext(html="<button>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert len(patches) == 1
        assert patches[0].function_name == "handleClick"

    def test_handles_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        builder = JSPromptBuilder()

        response = "This is not valid JSON"

        context = FixContext(html="<button>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert patches == []

    def test_handles_unknown_patch_type(self):
        """Test handling of unknown patch type."""
        builder = JSPromptBuilder()

        response = json.dumps([
            {"type": "unknown_type", "data": "something"}
        ])

        context = FixContext(html="<button>Test</button>", errors=[])
        patches = builder.parse_response(response, context)

        assert patches == []

    def test_context_missing_functions(self):
        """Test that missing functions appear in prompt."""
        builder = JSPromptBuilder()
        html = '<button onclick="handleClick()">Click</button>'

        error = self._make_js_error(ErrorType.JS_MISSING_FUNCTION)

        context = FixContext(
            html=html,
            errors=[error],
            defined_functions={"existingFunction"},
            called_functions={"handleClick", "existingFunction"},
        )

        prompt = builder.build(context)

        assert "handleClick" in prompt
        assert "MISSING FUNCTIONS" in prompt

    def test_extracts_scripts(self):
        """Test script extraction from HTML."""
        builder = JSPromptBuilder()
        html = '''
        <script>function test1() {}</script>
        <script src="external.js"></script>
        <script>function test2() {}</script>
        '''

        scripts = builder._extract_scripts(html)

        assert len(scripts) == 3
        assert scripts[0]["is_external"] is False
        assert "test1" in scripts[0]["content"]
        assert scripts[1]["is_external"] is True
        assert scripts[1]["src"] == "external.js"

    def test_extracts_handlers(self):
        """Test handler extraction from HTML."""
        builder = JSPromptBuilder()
        html = '''
        <button onclick="handleClick()">Click</button>
        <input onchange="handleChange(this.value)">
        <form onsubmit="handleSubmit(event)"></form>
        '''

        handlers = builder._extract_handlers(html)

        assert len(handlers) == 3
        assert any(h["event"] == "onclick" for h in handlers)
        assert any(h["event"] == "onchange" for h in handlers)
        assert any(h["event"] == "onsubmit" for h in handlers)

    def test_can_handle_filters_correctly(self):
        """Test can_handle method."""
        builder = JSPromptBuilder()

        js_error = self._make_js_error(ErrorType.JS_MISSING_FUNCTION)
        feedback_error = ClassifiedError(
            error_type=ErrorType.FEEDBACK_MISSING,
            selector=".btn",
            element_tag="button",
            tailwind_info=None,
            confidence=1.0,
        )

        assert builder.can_handle(js_error) is True
        assert builder.can_handle(feedback_error) is False
