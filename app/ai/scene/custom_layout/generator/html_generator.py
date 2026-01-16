"""
HTMLGenerator - Generates HTML using Gemini 3 Pro with thinking.

Uses extended thinking for deeper reasoning about layout structure,
interactivity, and Tailwind CSS patterns.
"""

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from .contracts import HTMLGenerationResult, GenerationContext
from .prompts import SYSTEM_PROMPT, build_user_prompt, get_content_type_hint

if TYPE_CHECKING:
    from app.ai.providers.gemini import GeminiProvider

logger = logging.getLogger("jarvis.ai.html_fixer.generator")


class HTMLGenerator:
    """
    Generates HTML layouts using Gemini 3 Pro with extended thinking.

    Uses SYSTEM_PROMPT with Tailwind CSS rules and best practices
    to generate interactive HTML that passes validation.

    Usage:
        generator = HTMLGenerator()
        result = await generator.generate(
            user_request="Show me trivia about world history",
            info_type="trivia",
        )

        if result.success:
            html = result.html
    """

    # Default model for HTML generation (Gemini 3 Pro)
    DEFAULT_MODEL = "gemini-3-pro-preview"

    def __init__(
        self,
        provider: "GeminiProvider" = None,
        model: str = None,
        use_thinking: bool = True,
        thinking_level: str = "HIGH",
        temperature: float = 0.3,
        max_tokens: int = 16000,
    ):
        """
        Initialize the HTML generator.

        Args:
            provider: GeminiProvider instance (uses singleton if not provided)
            model: Model to use (defaults to gemini-3-pro-preview)
            use_thinking: Enable extended thinking mode
            thinking_level: Thinking depth ("HIGH" or "LOW")
            temperature: Generation temperature (lower = more focused)
            max_tokens: Maximum output tokens
        """
        # Use provided provider or import singleton
        if provider is not None:
            self._provider = provider
        else:
            try:
                from app.ai.providers.gemini import gemini_provider
                self._provider = gemini_provider
            except ImportError:
                logger.warning("GeminiProvider not available")
                self._provider = None

        self._model = model or self.DEFAULT_MODEL
        self._use_thinking = use_thinking
        self._thinking_level = thinking_level
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def generate(
        self,
        user_request: Optional[str] = None,
        info_type: str = "custom",
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[GenerationContext] = None,
    ) -> HTMLGenerationResult:
        """
        Generate HTML from user request.

        Args:
            user_request: Original user request (e.g., "Show me trivia")
            info_type: Type of content (trivia, dashboard, game, etc.)
            title: Optional title for the content
            data: Optional data to include in the layout
            context: Optional full GenerationContext (overrides other params)

        Returns:
            HTMLGenerationResult with generated HTML
        """
        start_time = time.time()

        if not self._provider:
            return HTMLGenerationResult(
                success=False,
                error="LLM provider not available",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Use context if provided, otherwise build from params
        if context is not None:
            user_request = context.user_request
            info_type = context.info_type
            title = context.title
            data = context.data
        elif user_request is None:
            return HTMLGenerationResult(
                success=False,
                error="Either user_request or context must be provided",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Build context if not provided
        if context is None:
            context = GenerationContext(
                user_request=user_request,
                info_type=info_type,
                title=title,
                data=data,
            )

        # Build user prompt
        user_prompt = self._build_prompt(context)

        logger.info(f"Generating HTML for: {user_request[:50]}...")
        logger.info(f"Using model: {self._model}, thinking={self._use_thinking}, level={self._thinking_level}")

        try:
            # Call Gemini 3 Pro with thinking
            response = await self._provider.generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                model_override=self._model,
                use_thinking=self._use_thinking,
                thinking_level=self._thinking_level,
            )

            latency_ms = (time.time() - start_time) * 1000

            if not response.success:
                logger.error(f"Generation failed: {response.error}")
                return HTMLGenerationResult(
                    success=False,
                    error=response.error,
                    latency_ms=latency_ms,
                    model=self._model,
                )

            # Extract and clean HTML
            html = self._extract_html(response.content)

            if not html:
                logger.warning("No valid HTML extracted from response")
                return HTMLGenerationResult(
                    success=False,
                    error="No valid HTML in response",
                    latency_ms=latency_ms,
                    tokens_used=response.usage.total_tokens if response.usage else 0,
                    model=self._model,
                )

            # Validate basic HTML structure
            if not self._is_valid_html(html):
                logger.warning("Generated HTML has invalid structure")
                return HTMLGenerationResult(
                    success=False,
                    html=html,
                    error="Invalid HTML structure",
                    latency_ms=latency_ms,
                    tokens_used=response.usage.total_tokens if response.usage else 0,
                    model=self._model,
                )

            logger.info(f"Generated {len(html)} chars of HTML in {latency_ms:.0f}ms")

            return HTMLGenerationResult(
                success=True,
                html=html,
                latency_ms=latency_ms,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                thinking_used=self._use_thinking,
                model=self._model,
            )

        except Exception as e:
            logger.exception(f"HTML generation failed: {e}")
            return HTMLGenerationResult(
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
                model=self._model,
            )

    def _build_prompt(self, context: GenerationContext) -> str:
        """Build the user prompt from context."""
        # Get base prompt
        prompt = build_user_prompt(
            user_request=context.user_request,
            info_type=context.info_type,
            title=context.title,
            data=context.data,
            additional_context=context.additional_context,
        )

        # Add content-type specific hints
        content_hint = get_content_type_hint(context.info_type)
        if content_hint:
            prompt = f"{content_hint}\n\n{prompt}"

        return prompt

    def _extract_html(self, content: str) -> Optional[str]:
        """
        Extract HTML from LLM response.

        Handles cases where response includes markdown code blocks.
        """
        if not content:
            return None

        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```html"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        # Ensure it starts with DOCTYPE or html
        if not content.startswith("<!DOCTYPE") and not content.startswith("<html"):
            # Try to find DOCTYPE in content
            doctype_pos = content.find("<!DOCTYPE")
            if doctype_pos != -1:
                content = content[doctype_pos:]
            else:
                html_pos = content.find("<html")
                if html_pos != -1:
                    content = content[html_pos:]
                else:
                    return None

        return content

    def _is_valid_html(self, html: str) -> bool:
        """Basic validation of HTML structure."""
        if not html:
            return False

        # Must have basic structure
        has_doctype = "<!DOCTYPE" in html or "<!doctype" in html
        has_html_tag = "<html" in html
        has_body = "<body" in html
        has_closing = "</html>" in html

        return has_doctype and has_html_tag and has_body and has_closing

    def __repr__(self) -> str:
        return (
            f"HTMLGenerator("
            f"model={self._model}, "
            f"thinking={self._use_thinking})"
        )
