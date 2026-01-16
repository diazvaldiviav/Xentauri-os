"""
PromptBuilder Base - Abstract base class for specialized prompt builders.

Sprint 6: Defines the interface for Tailwind and JS prompt builders.
Each builder handles specific error types and generates focused prompts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

from ....contracts.errors import ErrorType
from ....contracts.validation import ClassifiedError
from ....contracts.patches import TailwindPatch
from ..contracts.js_patch import JSPatch


@dataclass
class FixContext:
    """
    Context passed to prompt builders.

    Contains all information needed to generate repair prompts,
    including the HTML, errors, and analysis results.
    """

    html: str
    """The HTML content to fix."""

    errors: List[ClassifiedError]
    """Classified errors to address."""

    # Optional screenshot context for visual understanding
    before_screenshot: Optional[bytes] = None
    """Screenshot before interaction (if available)."""

    after_screenshot: Optional[bytes] = None
    """Screenshot after interaction (if available)."""

    # Extracted JavaScript analysis
    defined_functions: Set[str] = field(default_factory=set)
    """Functions defined in the HTML."""

    called_functions: Set[str] = field(default_factory=set)
    """Functions called in event handlers."""

    dom_ids: Set[str] = field(default_factory=set)
    """DOM element IDs present in the HTML."""

    # Previous fix attempts (for retry logic)
    previous_patches: List[Union[TailwindPatch, JSPatch]] = field(default_factory=list)
    """Patches from previous attempts that didn't work."""

    attempt_number: int = 1
    """Current attempt number (1-based)."""

    def get_missing_functions(self) -> Set[str]:
        """Get functions that are called but not defined."""
        return self.called_functions - self.defined_functions

    def has_screenshots(self) -> bool:
        """Check if screenshots are available."""
        return self.before_screenshot is not None and self.after_screenshot is not None


class PromptBuilder(ABC):
    """
    Abstract base class for specialized prompt builders.

    Each implementation handles a specific domain (Tailwind CSS or JavaScript)
    and generates prompts optimized for that domain.
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """
        Domain this builder handles.

        Returns:
            'tailwind' or 'js'
        """
        pass

    @property
    @abstractmethod
    def handles_error_types(self) -> List[ErrorType]:
        """
        Error types this builder can create prompts for.

        Returns:
            List of ErrorType values this builder handles
        """
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        System prompt for LLM.

        Returns:
            System prompt string with instructions for the LLM
        """
        pass

    @abstractmethod
    def build(self, context: FixContext) -> str:
        """
        Build user prompt for LLM API call.

        Args:
            context: FixContext with HTML, errors, and analysis

        Returns:
            User prompt string to send to LLM
        """
        pass

    @abstractmethod
    def parse_response(
        self,
        response: str,
        context: FixContext
    ) -> List[Union[TailwindPatch, JSPatch]]:
        """
        Parse LLM response into patches.

        Args:
            response: Raw LLM response text
            context: Original context for validation

        Returns:
            List of patches (TailwindPatch or JSPatch)
        """
        pass

    def can_handle(self, error: ClassifiedError) -> bool:
        """
        Check if this builder can handle a specific error.

        Args:
            error: The error to check

        Returns:
            True if this builder handles this error type
        """
        return error.error_type in self.handles_error_types

    def filter_errors(self, errors: List[ClassifiedError]) -> List[ClassifiedError]:
        """
        Filter errors to only those this builder handles.

        Args:
            errors: List of all errors

        Returns:
            Filtered list of errors this builder can handle
        """
        return [e for e in errors if self.can_handle(e)]

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.

        Args:
            response: Raw LLM response

        Returns:
            Cleaned JSON string
        """
        import re

        content = response.strip()

        # Try to extract JSON from markdown code blocks (handles text before/after)
        json_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)```"
        matches = re.findall(json_block_pattern, content)
        if matches:
            # Return the first JSON block found
            return matches[0].strip()

        # If no code block, check if it starts/ends with code block markers
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        return content.strip()
