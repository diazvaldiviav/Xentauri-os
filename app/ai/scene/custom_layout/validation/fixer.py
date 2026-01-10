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

The validation system uses SCREENSHOT COMPARISON to detect visual changes.
It requires at least 2% of viewport pixels (41,000 pixels on 1920x1080) to change.

FAILURE TYPES YOU WILL SEE:

1. **under_threshold** - Button WORKS but visual feedback is TOO SUBTLE
   - The handler fires, but the color change is too small
   - DO NOT add new handlers or rewrite JavaScript
   - DO: Add overlays, expand affected area, use ::after pseudo-elements
   - Example fix: Add a full-screen flash overlay on click

2. **no_change** - Button produces ZERO visual change
   - Handler is broken or not connected
   - DO: Check onclick, add missing handlers, fix CSS selectors

3. **error** - JavaScript error occurred
   - Fix the error shown in the message

FOR under_threshold FAILURES (most common):
- A 100x40 button = 4000 pixels = 0.2% of viewport (NOT ENOUGH)
- You need to affect a LARGER AREA when clicked
- Best fix: Add ::after overlay that covers 20%+ of screen
- Alternative: Change entire panel background, not just button

CRITICAL: Read the "interpretation" field - it tells you exactly what to do.

OUTPUT:
Return ONLY the fixed HTML from <!DOCTYPE html> to </html>.
No markdown, no explanations."""


def build_repair_prompt(
    html: str,
    sandbox_result: SandboxResult,
    user_request: str,
) -> str:
    """
    Build repair prompt with full phase-by-phase context.

    CRITICAL: Includes pixel_diff_ratio and failure classification so
    Sonnet knows the REAL problem (under_threshold vs no_change).
    """
    # Truncate HTML if too long (keep beginning and end)
    max_html_len = 12000
    if len(html) > max_html_len:
        half = max_html_len // 2
        html = html[:half] + "\n\n<!-- ... TRUNCATED ... -->\n\n" + html[-half:]

    # Build rich context for each interaction result
    interaction_details = []
    under_threshold_count = 0
    no_change_count = 0

    for ir in sandbox_result.interaction_results:
        ctx = ir.get_repair_context(threshold=0.02)

        if ctx["failure_type"] == "under_threshold":
            under_threshold_count += 1
            interaction_details.append(
                f"  ⚠️ {ctx['selector']}\n"
                f"     Type: {ctx['failure_type']}\n"
                f"     Change: {ctx['pixel_diff_pct']} (need {ctx['threshold']})\n"
                f"     Action: {ctx['interpretation']}"
            )
        elif ctx["failure_type"] == "no_change":
            no_change_count += 1
            interaction_details.append(
                f"  ❌ {ctx['selector']}\n"
                f"     Type: {ctx['failure_type']}\n"
                f"     Action: {ctx['interpretation']}"
            )
        elif ctx["failure_type"] == "error":
            interaction_details.append(
                f"  💥 {ctx['selector']}\n"
                f"     Type: error\n"
                f"     Action: {ctx['interpretation']}"
            )
        # Skip "passed" elements

    interaction_section = "\n\n".join(interaction_details) if interaction_details else "  (none)"

    # Build summary based on failure types
    if under_threshold_count > 0 and no_change_count == 0:
        summary = f"""DIAGNOSIS: All {under_threshold_count} failing elements are "under_threshold".
This means the buttons WORK but produce INSUFFICIENT visual change.
DO NOT rewrite handlers. AMPLIFY the visual feedback instead."""
    elif no_change_count > 0 and under_threshold_count == 0:
        summary = f"""DIAGNOSIS: All {no_change_count} failing elements produce NO visual change.
The handlers are likely broken or not connected.
Check onclick handlers, CSS selectors, and event binding."""
    else:
        summary = f"""DIAGNOSIS: Mixed failures.
- {under_threshold_count} elements need visual amplification (under_threshold)
- {no_change_count} elements have broken handlers (no_change)
Fix each according to its failure type."""

    return f"""Fix this HTML that failed visual validation.

## DIAGNOSIS

{summary}

## ELEMENTS TO FIX

{interaction_section}

## ORIGINAL REQUEST

"{user_request[:300]}"

## HTML TO FIX

```html
{html}
```

## REPAIR INSTRUCTIONS

1. Read each element's "failure_type" and "Action" carefully
2. For "under_threshold": Add large visual effects (overlays, panel changes)
3. For "no_change": Fix or add event handlers
4. Keep the visual design intact (dark theme, 1920x1080)

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
