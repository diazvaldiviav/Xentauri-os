"""
TailwindPromptBuilder - Builds prompts for Tailwind CSS visual feedback fixes.

Sprint 6: Specialized prompt builder for FEEDBACK_MISSING and FEEDBACK_TOO_SUBTLE errors.
Generates prompts that instruct the LLM to add appropriate hover/active/focus states.
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
from ..contracts.js_patch import JSPatch

logger = logging.getLogger(__name__)


TAILWIND_SYSTEM_PROMPT = """You are a Tailwind CSS specialist. Your task is to fix visual feedback issues in interactive HTML elements.

CONTEXT:
- The HTML uses Tailwind CSS for styling
- Interactive elements are missing or have insufficient visual feedback when clicked/hovered
- You must ONLY suggest Tailwind class additions/removals
- Do NOT suggest JavaScript changes or raw CSS

OUTPUT FORMAT:
Return a JSON array of patches. Each patch specifies classes to add/remove:
[
  {
    "selector": "CSS selector for element (e.g., '.btn-primary', '#submit-btn', 'button.option')",
    "add": ["hover:bg-blue-600", "active:scale-95", "transition-all", "duration-150"],
    "remove": [],
    "reason": "Add hover color change and click scale feedback with smooth transition"
  }
]

VALID TAILWIND FEEDBACK CLASSES:

Hover states (visual change on mouse over):
- hover:bg-{color}-{shade} (e.g., hover:bg-blue-600, hover:bg-gray-700)
- hover:text-{color}-{shade}
- hover:scale-105, hover:scale-110
- hover:shadow-lg, hover:shadow-xl
- hover:brightness-110, hover:brightness-90
- hover:-translate-y-1

Active states (visual change on click/press):
- active:scale-95, active:scale-90
- active:bg-{color}-{shade} (usually darker than hover)
- active:brightness-75, active:brightness-90
- active:translate-y-0.5

Focus states (for accessibility):
- focus:ring-2, focus:ring-4
- focus:ring-{color}-{shade}
- focus:outline-none
- focus:border-{color}-{shade}

Transitions (for smooth animations):
- transition-all
- transition-colors
- transition-transform
- transition-shadow
- duration-150, duration-200, duration-300
- ease-in-out

RULES:
1. Always include a transition class for smooth feedback (transition-all duration-150)
2. For buttons: add both hover AND active states
3. Use color shades that contrast with the element's base color
4. Prefer subtle feedback (scale-95) over dramatic (scale-75)
5. Include focus states for keyboard accessibility
6. Do NOT remove existing functional classes
7. Do NOT add layout-changing classes (margins, padding, width, height)"""


class TailwindPromptBuilder(PromptBuilder):
    """
    Builds prompts for Tailwind CSS visual feedback fixes.

    Handles FEEDBACK_MISSING and FEEDBACK_TOO_SUBTLE errors by generating
    prompts that instruct the LLM to add hover, active, and focus states.
    """

    SYSTEM_PROMPT = TAILWIND_SYSTEM_PROMPT

    @property
    def domain(self) -> str:
        return "tailwind"

    @property
    def handles_error_types(self) -> List[ErrorType]:
        return [ErrorType.FEEDBACK_MISSING, ErrorType.FEEDBACK_TOO_SUBTLE]

    @property
    def system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def build(self, context: FixContext) -> str:
        """
        Build user prompt for Tailwind feedback fixes.

        Args:
            context: FixContext with HTML and errors

        Returns:
            User prompt string
        """
        # Filter to only Tailwind-relevant errors
        relevant_errors = self.filter_errors(context.errors)

        if not relevant_errors:
            return ""

        # Build error descriptions with HTML context
        error_sections = []
        for i, error in enumerate(relevant_errors, 1):
            element_html = self._extract_element_context(context.html, error.selector)
            current_classes = self._get_element_classes(context.html, error.selector)

            error_sections.append(f"""
### Error {i}: {error.error_type.value.upper()}
- Selector: `{error.selector}`
- Element tag: `{error.element_tag}`
- Current classes: `{current_classes}`

HTML excerpt:
```html
{element_html}
```""")

        # Build the user prompt
        prompt = f"""Fix visual feedback for these interactive elements that don't respond visually to clicks:

{chr(10).join(error_sections)}

Generate Tailwind class patches to add hover, active, and focus states.
Ensure smooth transitions are included.
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
        Parse LLM JSON response into TailwindPatch objects.

        Args:
            response: Raw LLM response
            context: Original context

        Returns:
            List of TailwindPatch objects
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
                    patch = TailwindPatch(
                        selector=data.get("selector", ""),
                        add_classes=data.get("add", []),
                        remove_classes=data.get("remove", []),
                        reason=data.get("reason"),
                    )
                    # Basic validation
                    if patch.selector and (patch.add_classes or patch.remove_classes):
                        patches.append(patch)
                    else:
                        logger.warning(f"Invalid patch data: {data}")
                except Exception as e:
                    logger.warning(f"Failed to parse patch: {data}, error: {e}")

            return patches

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            return []

    def _extract_element_context(self, html: str, selector: str) -> str:
        """
        Extract HTML context for a specific element.

        Args:
            html: Full HTML content
            selector: CSS selector

        Returns:
            HTML string of the element and surrounding context
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(selector)

            if not elements:
                return f"<!-- Element not found: {selector} -->"

            element = elements[0]

            # Get the element's outer HTML
            return str(element)

        except Exception as e:
            logger.warning(f"Failed to extract element context: {e}")
            return f"<!-- Error extracting element: {selector} -->"

    def _get_element_classes(self, html: str, selector: str) -> str:
        """
        Get current classes on an element.

        Args:
            html: Full HTML content
            selector: CSS selector

        Returns:
            Space-separated class string
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(selector)

            if not elements:
                return "(element not found)"

            element = elements[0]
            classes = element.get("class", [])

            if isinstance(classes, list):
                return " ".join(classes)
            return str(classes)

        except Exception:
            return "(error reading classes)"
