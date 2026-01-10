"""
Direct Fixer - Phase 7: Send full context to Codex-Max for repair.

Sprint 6: Visual-based validation system.

Key difference from old system:
- NO Gemini diagnosis step
- Send ALL phase failures directly to Codex-Max
- Full context = better repairs
"""

import logging
import re
from typing import Optional

from .contracts import SandboxResult

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.fixer")


# ---------------------------------------------------------------------------
# REPAIR PROMPTS
# ---------------------------------------------------------------------------

REPAIR_SYSTEM_PROMPT = """You are an HTML repair specialist for interactive web layouts.

Your task is to fix HTML that failed visual validation. The validation system uses
actual screenshot comparison to detect changes - not just DOM class changes.

CRITICAL REQUIREMENTS:
1. Clicks MUST produce VISIBLE changes (background color, opacity, transform, etc.)
2. All interactive elements MUST respond to user input
3. CSS transitions/animations MUST actually execute (not just add classes)
4. No JavaScript errors allowed
5. All content MUST be visible on 1920x1080 dark theme display

COMMON ISSUES TO FIX:
- CSS transitions defined but never triggered
- Classes added but no corresponding CSS rules
- Hidden elements that never become visible
- Event handlers that don't update visual state
- Z-index issues hiding interactive elements

OUTPUT:
Return ONLY the fixed HTML from <!DOCTYPE html> to </html>.
Do NOT include markdown code blocks or explanations."""


def build_repair_prompt(
    html: str,
    sandbox_result: SandboxResult,
    user_request: str,
) -> str:
    """
    Build repair prompt with full phase-by-phase context.

    Args:
        html: The HTML that failed validation
        sandbox_result: Full validation result with phase details
        user_request: Original user request

    Returns:
        Prompt string for Codex-Max
    """
    # Truncate HTML if too long (keep beginning and end)
    max_html_len = 12000
    if len(html) > max_html_len:
        half = max_html_len // 2
        html = html[:half] + "\n\n<!-- ... TRUNCATED ... -->\n\n" + html[-half:]

    return f"""Fix this HTML that failed visual validation.

## VALIDATION FAILURES

{sandbox_result.to_repair_context()}

## ORIGINAL USER REQUEST

"{user_request[:500]}"

## HTML TO FIX

```html
{html}
```

## REPAIR REQUIREMENTS

1. Fix ALL issues identified in the phase failures above
2. Ensure clicks produce VISIBLE changes (not just DOM class changes)
3. All interactive elements must respond to user input
4. Keep the visual design intact (dark theme, 1920x1080)
5. No JavaScript errors

## OUTPUT

Return ONLY the corrected HTML from <!DOCTYPE html> to </html>.
"""


# ---------------------------------------------------------------------------
# DIRECT FIXER
# ---------------------------------------------------------------------------

class DirectFixer:
    """
    Phase 7: Send full phase report to Codex-Max for repair.

    Skips Gemini diagnosis - goes directly to repair with full context.
    This is more effective because:
    - Codex-Max sees ALL failures, not just a summary
    - No information loss from diagnosis step
    - More consistent repairs
    """

    async def repair(
        self,
        html: str,
        sandbox_result: SandboxResult,
        user_request: str,
        max_tokens: int = 16384,
    ) -> Optional[str]:
        """
        Send all phase failures directly to Codex-Max for repair.

        Args:
            html: HTML that failed validation
            sandbox_result: Full validation result
            user_request: Original user request
            max_tokens: Max tokens for response

        Returns:
            Repaired HTML or None if repair failed
        """
        if sandbox_result.valid:
            # No repair needed
            return html

        logger.info(
            f"Starting direct repair - "
            f"failures: {sandbox_result.failure_summary}"
        )

        try:
            from app.ai.providers.openai_provider import openai_provider

            # Build prompt with full context
            prompt = build_repair_prompt(html, sandbox_result, user_request)

            # Call Codex-Max directly (no Gemini diagnosis)
            response = await openai_provider.generate(
                prompt=prompt,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                temperature=0.2,  # Low temperature for consistent repairs
                max_tokens=max_tokens,
            )

            if not response.success:
                logger.warning(f"Codex-Max repair failed: {response.error}")
                return None

            # Clean and extract HTML
            repaired_html = self._clean_html_response(response.content)

            if repaired_html:
                logger.info(
                    f"Repair completed - "
                    f"original: {len(html)} chars, "
                    f"repaired: {len(repaired_html)} chars"
                )
                return repaired_html
            else:
                logger.warning("Failed to extract valid HTML from repair response")
                return None

        except Exception as e:
            logger.error(f"Direct repair error: {e}", exc_info=True)
            return None

    async def repair_with_reasoning(
        self,
        html: str,
        sandbox_result: SandboxResult,
        user_request: str,
        effort: str = "high",
        max_tokens: int = 16384,
    ) -> Optional[str]:
        """
        Repair using Codex-Max with extended reasoning.

        More expensive but better for complex CSS/JS issues.

        Args:
            html: HTML that failed validation
            sandbox_result: Full validation result
            user_request: Original user request
            effort: Reasoning effort level ("low", "medium", "high")
            max_tokens: Max tokens for response

        Returns:
            Repaired HTML or None if repair failed
        """
        if sandbox_result.valid:
            return html

        logger.info(
            f"Starting reasoning repair (effort={effort}) - "
            f"failures: {sandbox_result.failure_summary}"
        )

        try:
            from app.ai.providers.openai_provider import openai_provider

            prompt = build_repair_prompt(html, sandbox_result, user_request)

            response = await openai_provider.generate_with_reasoning(
                prompt=prompt,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                effort=effort,
                max_tokens=max_tokens,
            )

            if not response.success:
                logger.warning(f"Codex-Max reasoning repair failed: {response.error}")
                return None

            repaired_html = self._clean_html_response(response.content)

            if repaired_html:
                logger.info(
                    f"Reasoning repair completed - "
                    f"original: {len(html)} chars, "
                    f"repaired: {len(repaired_html)} chars"
                )
                return repaired_html
            else:
                logger.warning("Failed to extract valid HTML from reasoning repair")
                return None

        except Exception as e:
            logger.error(f"Reasoning repair error: {e}", exc_info=True)
            return None

    def _clean_html_response(self, content: str) -> Optional[str]:
        """
        Clean and extract HTML from LLM response.

        Handles:
        - Markdown code blocks
        - Leading/trailing whitespace
        - Incomplete HTML
        """
        if not content:
            return None

        text = content.strip()

        # Remove markdown code blocks
        if text.startswith("```html"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Must start with DOCTYPE or <html>
        if not text.lower().startswith("<!doctype") and not text.lower().startswith("<html"):
            # Try to find DOCTYPE in response
            doctype_match = re.search(r'<!DOCTYPE\s+html[^>]*>', text, re.IGNORECASE)
            if doctype_match:
                text = text[doctype_match.start():]
            else:
                # Try to find <html> tag
                html_match = re.search(r'<html[^>]*>', text, re.IGNORECASE)
                if html_match:
                    text = "<!DOCTYPE html>\n" + text[html_match.start():]
                else:
                    return None

        # Must end with </html>
        if not text.lower().rstrip().endswith("</html>"):
            # Try to find </html> tag
            end_match = re.search(r'</html\s*>', text, re.IGNORECASE)
            if end_match:
                text = text[:end_match.end()]
            else:
                # Append closing tag
                text = text + "\n</html>"

        # Basic validation: must have <head> and <body>
        if "<head" not in text.lower() or "<body" not in text.lower():
            return None

        return text


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

direct_fixer = DirectFixer()
