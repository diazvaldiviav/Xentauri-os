"""
JSPromptBuilder - Builds prompts for JavaScript error fixes.

Sprint 6: Specialized prompt builder for JS_* errors.
Generates prompts that instruct the LLM to fix JavaScript code issues.
"""

import json
import logging
import re
from typing import List, Union

from bs4 import BeautifulSoup

from ....contracts.errors import ErrorType
from ....contracts.validation import ClassifiedError
from ....contracts.patches import TailwindPatch
from .base import PromptBuilder, FixContext
from ..contracts.js_patch import JSPatch, JSPatchType

logger = logging.getLogger(__name__)


JS_SYSTEM_PROMPT = """You are a JavaScript specialist. Your task is to fix JavaScript errors in HTML documents.

CONTEXT:
- The HTML contains inline JavaScript in <script> tags
- Event handlers are defined as onclick="functionName()" attributes
- You must fix the JavaScript code to make interactivity work

OUTPUT FORMAT:
Return a JSON array of patches. Each patch specifies a JavaScript fix:
[
  {
    "type": "add_function",
    "function_name": "handleClick",
    "function_code": "function handleClick() {\\n  console.log('clicked');\\n}",
    "reason": "Function was called in onclick but not defined"
  }
]

PATCH TYPES:

1. add_function - Add a new function definition
   Required fields: function_name, function_code
   Example:
   {
     "type": "add_function",
     "function_name": "handleSelection",
     "function_code": "function handleSelection(option) {\\n  const result = document.getElementById('result');\\n  if (result) result.textContent = 'Selected: ' + option;\\n}",
     "reason": "Function called from onclick but not defined"
   }

2. fix_dom_reference - Fix incorrect DOM element reference
   Required fields: old_reference, new_reference
   Example:
   {
     "type": "fix_dom_reference",
     "old_reference": "result",
     "new_reference": "output",
     "reason": "Element with id 'result' doesn't exist, but 'output' does"
   }

3. fix_syntax - Fix syntax error at specific location
   Required fields: script_index (0-based), line_start, line_end, replacement_code
   Example:
   {
     "type": "fix_syntax",
     "script_index": 0,
     "line_start": 5,
     "line_end": 5,
     "replacement_code": "const x = 10;",
     "reason": "Missing semicolon"
   }

4. add_variable - Add missing variable declaration
   Required fields: function_code (the variable declaration)
   Example:
   {
     "type": "add_variable",
     "function_code": "let counter = 0;",
     "reason": "Variable 'counter' used but not declared"
   }

5. modify_handler - Change onclick attribute value
   Required fields: selector, old_handler, new_handler
   Example:
   {
     "type": "modify_handler",
     "selector": "button.submit-btn",
     "old_handler": "submit()",
     "new_handler": "handleSubmit(event)",
     "reason": "Function name was incorrect"
   }

RULES:
1. Generate minimal, focused fixes - don't rewrite entire functions unnecessarily
2. Preserve existing functionality when possible
3. Use modern JavaScript (const/let instead of var)
4. Add null checks for DOM operations (e.g., if (element) element.textContent = ...)
5. Ensure functions are defined before they're called
6. Keep generated code simple and readable
7. Use descriptive function and variable names"""


class JSPromptBuilder(PromptBuilder):
    """
    Builds prompts for JavaScript error fixes.

    Handles JS_SYNTAX_ERROR, JS_MISSING_FUNCTION, JS_MISSING_DOM_ELEMENT,
    and JS_UNDEFINED_VARIABLE errors.
    """

    SYSTEM_PROMPT = JS_SYSTEM_PROMPT

    @property
    def domain(self) -> str:
        return "js"

    @property
    def handles_error_types(self) -> List[ErrorType]:
        return [
            ErrorType.JS_SYNTAX_ERROR,
            ErrorType.JS_MISSING_FUNCTION,
            ErrorType.JS_MISSING_DOM_ELEMENT,
            ErrorType.JS_UNDEFINED_VARIABLE,
        ]

    @property
    def system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build(self, context: FixContext) -> str:
        """
        Build user prompt for JavaScript error fixes.

        Args:
            context: FixContext with HTML and errors

        Returns:
            User prompt string
        """
        # Filter to only JS-relevant errors
        relevant_errors = self.filter_errors(context.errors)

        if not relevant_errors:
            return ""

        # Extract script content
        scripts = self._extract_scripts(context.html)

        # Extract event handlers
        handlers = self._extract_handlers(context.html)

        # Build error descriptions
        error_sections = []
        for i, error in enumerate(relevant_errors, 1):
            error_sections.append(f"""
### Error {i}: {error.error_type.value.upper()}
- Selector: `{error.selector}`
- Element: `{error.element_tag}`
- Line: {error.line_number if error.line_number else 'N/A'}""")

        # Build the user prompt
        prompt = f"""Fix JavaScript errors in this HTML:

## SCRIPT CONTENT
{self._format_scripts(scripts)}

## EVENT HANDLERS FOUND
{self._format_handlers(handlers)}

## EXISTING DOM ELEMENT IDs
{', '.join(sorted(context.dom_ids)) if context.dom_ids else 'None found'}

## DEFINED FUNCTIONS
{', '.join(sorted(context.defined_functions)) if context.defined_functions else 'None found'}

## CALLED FUNCTIONS (from handlers)
{', '.join(sorted(context.called_functions)) if context.called_functions else 'None found'}

## MISSING FUNCTIONS
{', '.join(sorted(context.get_missing_functions())) if context.get_missing_functions() else 'None'}

## ERRORS TO FIX
{chr(10).join(error_sections)}

Generate JSON patches to fix these JavaScript errors.
Output ONLY the JSON array of patches."""

        # Add retry context if this is a retry attempt
        if context.attempt_number > 1 and context.previous_patches:
            prompt += f"""

NOTE: This is attempt #{context.attempt_number}. Previous patches did not fully resolve the issues.
Previous attempted patches:
{json.dumps([p.to_dict() if hasattr(p, 'to_dict') else str(p) for p in context.previous_patches], indent=2)}

Please provide different or more comprehensive patches."""

        return prompt

    def parse_response(
        self,
        response: str,
        context: FixContext
    ) -> List[Union[TailwindPatch, JSPatch]]:
        """
        Parse LLM JSON response into JSPatch objects.

        Args:
            response: Raw LLM response
            context: Original context

        Returns:
            List of JSPatch objects
        """
        try:
            # Extract JSON from response
            json_str = self._extract_json_from_response(response)
            patches_data = json.loads(json_str)

            if not isinstance(patches_data, list):
                logger.warning("LLM response is not a list, wrapping in list")
                patches_data = [patches_data]

            patches = []
            for data in patches_data:
                try:
                    patch = self._parse_single_patch(data)
                    if patch:
                        patches.append(patch)
                except Exception as e:
                    logger.warning(f"Failed to parse JS patch: {data}, error: {e}")

            return patches

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            return []

    def _parse_single_patch(self, data: dict) -> JSPatch:
        """
        Parse a single patch from LLM response.

        Args:
            data: Dictionary with patch data

        Returns:
            JSPatch object or None if invalid
        """
        patch_type_str = data.get("type", "")

        try:
            patch_type = JSPatchType(patch_type_str)
        except ValueError:
            logger.warning(f"Unknown patch type: {patch_type_str}")
            return None

        return JSPatch(
            patch_type=patch_type,
            function_name=data.get("function_name"),
            function_code=data.get("function_code"),
            old_reference=data.get("old_reference"),
            new_reference=data.get("new_reference"),
            selector=data.get("selector"),
            old_handler=data.get("old_handler"),
            new_handler=data.get("new_handler"),
            script_index=data.get("script_index"),
            line_start=data.get("line_start"),
            line_end=data.get("line_end"),
            replacement_code=data.get("replacement_code"),
            reason=data.get("reason"),
            confidence=data.get("confidence", 1.0),
        )

    def _extract_scripts(self, html: str) -> List[dict]:
        """
        Extract all script content from HTML.

        Args:
            html: HTML content

        Returns:
            List of dicts with script info
        """
        scripts = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            for i, script in enumerate(soup.find_all("script")):
                src = script.get("src")
                content = script.string or ""

                scripts.append({
                    "index": i,
                    "is_external": bool(src),
                    "src": src,
                    "content": content.strip() if content else "",
                })

        except Exception as e:
            logger.warning(f"Failed to extract scripts: {e}")

        return scripts

    def _extract_handlers(self, html: str) -> List[dict]:
        """
        Extract event handlers from HTML elements.

        Args:
            html: HTML content

        Returns:
            List of dicts with handler info
        """
        handlers = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Find elements with onclick, onchange, etc.
            for attr in ["onclick", "onchange", "onsubmit", "onmouseover", "onkeydown"]:
                for element in soup.find_all(attrs={attr: True}):
                    handler_code = element.get(attr, "")

                    # Generate selector
                    selector = self._generate_selector(element)

                    handlers.append({
                        "selector": selector,
                        "event": attr,
                        "handler": handler_code,
                        "tag": element.name,
                    })

        except Exception as e:
            logger.warning(f"Failed to extract handlers: {e}")

        return handlers

    def _generate_selector(self, element) -> str:
        """
        Generate a CSS selector for an element.

        Args:
            element: BeautifulSoup element

        Returns:
            CSS selector string
        """
        if element.get("id"):
            return f"#{element.get('id')}"

        classes = element.get("class", [])
        if classes:
            if isinstance(classes, list):
                return f"{element.name}.{'.'.join(classes)}"
            return f"{element.name}.{classes}"

        return element.name

    def _format_scripts(self, scripts: List[dict]) -> str:
        """Format scripts for prompt."""
        if not scripts:
            return "No <script> tags found."

        parts = []
        for script in scripts:
            if script["is_external"]:
                parts.append(f"Script {script['index']}: External ({script['src']})")
            elif script["content"]:
                parts.append(f"Script {script['index']}:\n```javascript\n{script['content']}\n```")
            else:
                parts.append(f"Script {script['index']}: Empty")

        return "\n\n".join(parts)

    def _format_handlers(self, handlers: List[dict]) -> str:
        """Format handlers for prompt."""
        if not handlers:
            return "No event handlers found."

        parts = []
        for h in handlers:
            parts.append(f"- {h['selector']} {h['event']}=\"{h['handler']}\"")

        return "\n".join(parts)
