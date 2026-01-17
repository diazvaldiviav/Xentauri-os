"""
LLMFixer - Orchestrates LLM-based HTML repairs.

Sprint 6: Main orchestrator that coordinates prompt builders, LLM calls,
validation, and patch application for both Tailwind and JavaScript fixes.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, TYPE_CHECKING

from app.core.config import settings

from bs4 import BeautifulSoup

from ...contracts.errors import ErrorType
from ...contracts.validation import ClassifiedError
from ...contracts.patches import TailwindPatch, PatchSet
from ...contracts.feedback import MergedError
from ...fixers.tailwind_injector import TailwindInjector
from ...prompts.fixer_prompt_v2 import FeedbackAwareLLMPrompt

from .contracts.js_patch import JSPatch
from .prompt_builders.base import FixContext
from .prompt_builders.tailwind_prompt_builder import TailwindPromptBuilder
from .prompt_builders.js_prompt_builder import JSPromptBuilder
from .validators.patch_validator import PatchValidator
from .js_patch_applier import JSPatchApplier

if TYPE_CHECKING:
    from app.ai.providers.gemini import GeminiProvider

logger = logging.getLogger("jarvis.ai.html_fixer.llm_fixer")


@dataclass
class LLMFixResult:
    """Result of LLM-based fixing."""

    success: bool
    """True if any patches were applied."""

    original_html: str
    """Original HTML before fixes."""

    fixed_html: Optional[str] = None
    """Fixed HTML after patches applied."""

    tailwind_patches: List[TailwindPatch] = field(default_factory=list)
    """Tailwind patches that were applied."""

    js_patches: List[JSPatch] = field(default_factory=list)
    """JavaScript patches that were applied."""

    errors_addressed: List[ClassifiedError] = field(default_factory=list)
    """Errors that were attempted to fix."""

    errors_remaining: List[ClassifiedError] = field(default_factory=list)
    """Errors that couldn't be fixed."""

    llm_calls_made: int = 0
    """Number of LLM API calls made."""

    tokens_used: int = 0
    """Total tokens used in LLM calls."""

    duration_ms: float = 0.0
    """Total time taken in milliseconds."""

    error_message: Optional[str] = None
    """Error message if fix failed."""

    def describe(self) -> str:
        """Generate human-readable description."""
        lines = [
            f"LLMFixResult: {'SUCCESS' if self.success else 'FAILED'}",
            f"  Tailwind patches: {len(self.tailwind_patches)}",
            f"  JS patches: {len(self.js_patches)}",
            f"  LLM calls: {self.llm_calls_made}",
            f"  Duration: {self.duration_ms:.0f}ms",
        ]

        if self.error_message:
            lines.append(f"  Error: {self.error_message}")

        return "\n".join(lines)


class LLMFixer:
    """
    Orchestrates LLM-based HTML repairs.

    Dispatches errors to appropriate prompt builders, calls LLM,
    parses responses, validates patches, and applies fixes.

    Uses GeminiProvider with Gemini 3 Flash for LLM calls.
    """

    def __init__(
        self,
        provider: "GeminiProvider" = None,
        tailwind_builder: TailwindPromptBuilder = None,
        js_builder: JSPromptBuilder = None,
        validator: PatchValidator = None,
        max_retries: int = 2,
    ):
        """
        Initialize the LLM fixer.

        Args:
            provider: GeminiProvider instance (uses singleton if not provided)
            tailwind_builder: Custom Tailwind prompt builder
            js_builder: Custom JS prompt builder
            validator: Custom patch validator
            max_retries: Maximum retry attempts per domain
        """
        # Use provided provider or import singleton
        if provider is not None:
            self._provider = provider
        else:
            try:
                from app.ai.providers.gemini import gemini_provider
                self._provider = gemini_provider
            except ImportError:
                logger.warning("GeminiProvider not available, LLM calls will fail")
                self._provider = None

        self._tailwind_builder = tailwind_builder or TailwindPromptBuilder()
        self._js_builder = js_builder or JSPromptBuilder()
        self._validator = validator or PatchValidator()
        self._max_retries = max_retries

        # Appliers
        self._tailwind_injector = TailwindInjector()
        self._js_applier = JSPatchApplier()

    async def fix(
        self,
        errors: List[ClassifiedError],
        html: str,
        screenshots: Optional[Dict[str, bytes]] = None,
    ) -> LLMFixResult:
        """
        Fix errors using LLM.

        Args:
            errors: Classified errors to fix
            html: Original HTML content
            screenshots: Optional before/after screenshots for context

        Returns:
            LLMFixResult with patches and fixed HTML
        """
        start_time = time.time()
        result = LLMFixResult(success=False, original_html=html)

        if not self._provider:
            result.error_message = "LLM provider not available"
            result.duration_ms = (time.time() - start_time) * 1000
            return result

        # Filter to only LLM-requiring errors
        llm_errors = [e for e in errors if e.error_type.requires_llm]

        if not llm_errors:
            result.success = True
            result.fixed_html = html
            result.duration_ms = (time.time() - start_time) * 1000
            return result

        result.errors_addressed = llm_errors

        # Build context
        context = self._build_context(html, llm_errors, screenshots)

        # Separate errors by domain
        tailwind_errors = [e for e in llm_errors if e.error_type.is_feedback_related]
        js_errors = [e for e in llm_errors if e.error_type.is_js_related]

        current_html = html
        total_tokens = 0
        total_calls = 0

        # Fix Tailwind/CSS errors first (simpler)
        if tailwind_errors:
            tailwind_context = FixContext(
                html=current_html,
                errors=tailwind_errors,
                before_screenshot=screenshots.get("before") if screenshots else None,
                after_screenshot=screenshots.get("after") if screenshots else None,
                dom_ids=context.dom_ids,
            )

            tailwind_patches, calls, tokens = await self._fix_domain(
                builder=self._tailwind_builder,
                context=tailwind_context,
            )

            total_calls += calls
            total_tokens += tokens

            if tailwind_patches:
                # Apply Tailwind patches
                patch_set = PatchSet(patches=tailwind_patches, source="llm")
                injection_result = self._tailwind_injector.inject(current_html, patch_set)

                if injection_result.success:
                    current_html = injection_result.html
                    result.tailwind_patches.extend(tailwind_patches)
                    logger.info(f"Applied {len(tailwind_patches)} Tailwind patches")

        # Fix JavaScript errors
        if js_errors:
            # Update context with potentially modified HTML
            js_context = FixContext(
                html=current_html,
                errors=js_errors,
                defined_functions=context.defined_functions,
                called_functions=context.called_functions,
                dom_ids=context.dom_ids,
            )

            js_patches, calls, tokens = await self._fix_domain(
                builder=self._js_builder,
                context=js_context,
            )

            total_calls += calls
            total_tokens += tokens

            if js_patches:
                # Apply JS patches
                apply_result = self._js_applier.apply(current_html, js_patches)

                if apply_result.success:
                    current_html = apply_result.html
                    result.js_patches.extend(apply_result.applied)
                    logger.info(f"Applied {len(apply_result.applied)} JS patches")

        # Finalize result
        result.fixed_html = current_html
        result.llm_calls_made = total_calls
        result.tokens_used = total_tokens
        result.success = len(result.tailwind_patches) > 0 or len(result.js_patches) > 0
        result.duration_ms = (time.time() - start_time) * 1000

        logger.info(result.describe())
        return result

    async def _fix_domain(
        self,
        builder,
        context: FixContext,
    ) -> tuple[List[Union[TailwindPatch, JSPatch]], int, int]:
        """
        Fix errors using a specific prompt builder.

        Returns:
            Tuple of (patches, calls_made, tokens_used)
        """
        patches = []
        total_calls = 0
        total_tokens = 0

        for attempt in range(1, self._max_retries + 1):
            context.attempt_number = attempt

            try:
                # Build prompt
                user_prompt = builder.build(context)

                if not user_prompt:
                    logger.debug(f"No prompt generated for {builder.domain}")
                    break

                # Call LLM
                response = await self._call_llm(
                    system_prompt=builder.system_prompt,
                    user_prompt=user_prompt,
                )

                total_calls += 1
                if response.usage:
                    total_tokens += response.usage.total_tokens

                if not response.success:
                    logger.warning(f"LLM call failed: {response.error}")
                    continue

                # Parse response into patches
                parsed_patches = builder.parse_response(response.content, context)

                if not parsed_patches:
                    logger.debug("No patches parsed from LLM response")
                    continue

                # Validate patches
                valid_patches = self._validator.validate_batch(
                    parsed_patches, context.html, builder.domain
                )

                if valid_patches:
                    patches.extend(valid_patches)
                    break  # Success, no need to retry

                # Add failed patches to context for retry
                context.previous_patches.extend(parsed_patches)

            except Exception as e:
                logger.error(f"Error in {builder.domain} fix attempt {attempt}: {e}")
                continue

        return patches, total_calls, total_tokens

    async def _call_llm(self, system_prompt: str, user_prompt: str):
        """
        Make LLM API call using GeminiProvider.

        Args:
            system_prompt: System instructions
            user_prompt: User message with context

        Returns:
            AIResponse from provider
        """
        return await self._provider.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,  # Low temperature for consistent, focused output
            max_tokens=16500,  # Gemini 3 Flash needs more tokens for complex JS fixes
            response_mime_type="application/json",  # Force JSON output
        )

    def _build_context(
        self,
        html: str,
        errors: List[ClassifiedError],
        screenshots: Optional[Dict[str, bytes]],
    ) -> FixContext:
        """
        Build context for prompt builders.

        Extracts JavaScript analysis and DOM info from HTML.
        """
        # Extract defined functions
        defined_functions = self._extract_defined_functions(html)

        # Extract called functions from handlers
        called_functions = self._extract_called_functions(html)

        # Extract DOM IDs
        dom_ids = self._extract_dom_ids(html)

        return FixContext(
            html=html,
            errors=errors,
            before_screenshot=screenshots.get("before") if screenshots else None,
            after_screenshot=screenshots.get("after") if screenshots else None,
            defined_functions=defined_functions,
            called_functions=called_functions,
            dom_ids=dom_ids,
        )

    def _extract_defined_functions(self, html: str) -> set:
        """Extract function names defined in <script> tags."""
        import re

        functions = set()
        soup = BeautifulSoup(html, "html.parser")

        for script in soup.find_all("script"):
            if script.get("src"):
                continue

            content = script.string or ""

            # Pattern for function declarations
            patterns = [
                r"function\s+(\w+)\s*\(",           # function name()
                r"(const|let|var)\s+(\w+)\s*=\s*function",  # const name = function
                r"(const|let|var)\s+(\w+)\s*=\s*\([^)]*\)\s*=>",  # const name = () =>
                r"(const|let|var)\s+(\w+)\s*=\s*async\s*function",  # const name = async function
                r"(const|let|var)\s+(\w+)\s*=\s*async\s*\([^)]*\)\s*=>",  # const name = async () =>
            ]

            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    # Get the function name (last group that's a word)
                    groups = match.groups()
                    for g in reversed(groups):
                        if g and g not in ("const", "let", "var", "async"):
                            functions.add(g)
                            break

        return functions

    def _extract_called_functions(self, html: str) -> set:
        """Extract function names called in event handlers."""
        import re

        functions = set()
        soup = BeautifulSoup(html, "html.parser")

        # Find elements with event handlers
        handler_attrs = ["onclick", "onchange", "onsubmit", "onmouseover", "onkeydown", "onload"]

        for attr in handler_attrs:
            for element in soup.find_all(attrs={attr: True}):
                handler = element.get(attr, "")

                # Extract function calls: name() or name(args)
                for match in re.finditer(r"(\w+)\s*\(", handler):
                    func_name = match.group(1)
                    # Exclude common JS keywords
                    if func_name not in ("if", "for", "while", "return", "function"):
                        functions.add(func_name)

        return functions

    def _extract_dom_ids(self, html: str) -> set:
        """Extract all element IDs from HTML."""
        ids = set()
        soup = BeautifulSoup(html, "html.parser")

        for element in soup.find_all(id=True):
            ids.add(element.get("id"))

        return ids

    # =========================================================================
    # HUMAN FEEDBACK INTEGRATION (Sprint: Human Feedback)
    # =========================================================================

    async def fix_with_feedback(
        self,
        annotated_html: str,
        merged_errors: List[MergedError],
        global_feedback: List[str],
    ) -> LLMFixResult:
        """
        Fix HTML using human feedback annotations.

        This method uses the FeedbackAwareLLMPrompt which understands:
        - [ELEMENT #N] status:working/broken comments
        - [GLOBAL FEEDBACK] comments
        - User feedback messages

        Args:
            annotated_html: HTML with feedback comments injected
            merged_errors: List of MergedError from FeedbackMerger
            global_feedback: List of global feedback strings

        Returns:
            LLMFixResult with fixed HTML
        """
        import json
        import time

        start_time = time.time()
        result = LLMFixResult(success=False, original_html=annotated_html)

        if not self._provider:
            result.error_message = "LLM provider not available"
            result.duration_ms = (time.time() - start_time) * 1000
            return result

        # Convert MergedError to dict format for prompt
        errors_dict = [
            {
                "vid": e.vid,
                "selector": e.element_selector,
                "technical_error": e.technical_error,
                "user_feedback": e.user_feedback,
            }
            for e in merged_errors
        ]

        # Build prompt using FeedbackAwareLLMPrompt
        prompt_builder = FeedbackAwareLLMPrompt()
        messages = prompt_builder.build(
            annotated_html=annotated_html,
            merged_errors=errors_dict,
            global_feedback=global_feedback,
        )

        logger.info(
            f"[FEEDBACK_FIX] Calling LLM with {len(merged_errors)} errors, "
            f"{len(global_feedback)} global feedback items"
        )

        try:
            # Call LLM with Gemini 3 Pro for better instruction following and layout preservation
            response = await self._provider.generate(
                prompt=messages[1]["content"],  # User message
                system_prompt=messages[0]["content"],  # System message
                temperature=0.3,
                max_tokens=16000,
                model_override=settings.GEMINI_PRO_MODEL,  # Use Gemini 3 Pro
            )

            result.llm_calls_made = 1
            if response.usage:
                result.tokens_used = response.usage.total_tokens

            if not response.success:
                result.error_message = f"LLM call failed: {response.error}"
                result.duration_ms = (time.time() - start_time) * 1000
                return result

            # LLM returns complete HTML directly
            fixed_html = self._extract_html_from_response(response.content)

            if not fixed_html:
                result.error_message = "Failed to extract HTML from LLM response"
                result.duration_ms = (time.time() - start_time) * 1000
                return result

            logger.info(f"[FEEDBACK_FIX] LLM returned HTML ({len(fixed_html)} chars)")

            result.fixed_html = fixed_html
            result.success = True
            result.duration_ms = (time.time() - start_time) * 1000

            return result

        except Exception as e:
            logger.error(f"[FEEDBACK_FIX] Error: {e}", exc_info=True)
            result.error_message = str(e)
            result.duration_ms = (time.time() - start_time) * 1000
            return result

    def _extract_html_from_response(self, content: str) -> Optional[str]:
        """Extract HTML from LLM response."""
        import re

        if not content:
            return None

        content_stripped = content.strip()

        # Direct HTML (no wrapper)
        if content_stripped.lower().startswith('<!doctype') or content_stripped.lower().startswith('<html'):
            return content_stripped

        # HTML in markdown code block
        html_match = re.search(r"```(?:html)?\s*(<!DOCTYPE[\s\S]*?</html>)\s*```", content, re.IGNORECASE)
        if html_match:
            return html_match.group(1).strip()

        # Fallback: find HTML anywhere
        html_match = re.search(r"(<!DOCTYPE[\s\S]*?</html>)", content, re.IGNORECASE)
        if html_match:
            return html_match.group(1).strip()

        logger.warning(f"[FEEDBACK_FIX] Could not extract HTML: {content[:200]}...")
        return None
