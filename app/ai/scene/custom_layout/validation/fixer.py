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

## VALIDATION SYSTEM

The system uses SCREENSHOT COMPARISON to detect visual changes after clicks.
An element is considered "responsive" if clicking it produces visible change.

## FAILURE TYPES

1. **under_threshold** - Button WORKS but visual feedback is TOO SUBTLE
   - The onclick handler fires correctly
   - But the CSS change is too subtle to detect
   - FIX: Make the visual change more obvious (see SAFE FIXES below)

2. **no_change** - Button produces ZERO visual change
   - Handler is broken or not connected
   - FIX: Check onclick, ensure it modifies visible CSS

3. **error** - JavaScript error occurred
   - FIX: Fix the error shown in the message

## ⚠️ CRITICAL RULES - VIOLATION BREAKS THE LAYOUT

1. **NEVER modify CSS that affects multiple elements**
   - NO: Changing `.option { }` when multiple elements share this class
   - NO: Changing parent container styles
   - YES: Use ultra-specific selectors like `[data-option="A"]` or `#unique-id`

2. **NEVER add overlays, panels, or elements that cover other buttons**
   - NO: `::after` overlays covering 20%+ of screen
   - NO: Modal/popup overlays
   - YES: Changes ONLY to the clicked element itself

3. **PROTECTED ELEMENTS MUST NOT BE TOUCHED**
   - Elements marked ✅ WORKING are PROTECTED
   - Any modification to protected elements = FAILURE
   - Copy their PATTERN to fix broken elements

## SAFE FIXES FOR under_threshold

Apply these ONLY to the specific broken element:

```css
/* Option 1: High-contrast background */
[data-option="X"].selected { background: #ffffff !important; }

/* Option 2: Visible border */
[data-option="X"].selected { border: 3px solid #00ff00 !important; }

/* Option 3: Transform (scale up) */
[data-option="X"].selected { transform: scale(1.1); }

/* Option 4: Box shadow glow */
[data-option="X"].selected { box-shadow: 0 0 15px #00ff00; }
```

## OUTPUT

Return ONLY the fixed HTML from <!DOCTYPE html> to </html>.
No markdown, no explanations, no code blocks."""


def _format_element_context(elem: dict, pixels: dict = None, strategy: str = None) -> str:
    """
    Sprint 6.2: Format semantic element context for the fixer.

    This gives the fixer critical information about WHAT the element is,
    WHAT it should do, and EXACTLY how to fix it with concrete numbers.

    "El fixer necesita números concretos, no solo porcentajes."
    """
    if not elem:
        return ""

    lines = []

    # Element identity with size
    tag = elem.get("tag", "unknown")
    input_type = elem.get("input_type", "unknown")
    text = elem.get("text_content")
    area_pct = elem.get("area_pct", "?")
    area_pixels = elem.get("area_pixels", 0)

    lines.append(f"     Element: <{tag}> (type: {input_type}), size: {area_pixels:,}px ({area_pct} viewport)")

    if text:
        lines.append(f"     Text: \"{text}\"")

    # Key attributes that hint at behavior
    attrs = elem.get("key_attributes", {})
    if attrs:
        attr_parts = []
        for k, v in attrs.items():
            if v == "present":
                attr_parts.append(f"{k}=✓")
            else:
                attr_parts.append(f"{k}=\"{v}\"")
        if attr_parts:
            lines.append(f"     Attrs: {', '.join(attr_parts)}")

    # Sprint 6.2: Add concrete pixel counts
    if pixels:
        changed = pixels.get("changed", 0)
        needed = pixels.get("needed", 0)
        gap = pixels.get("gap", 0)
        if gap > 0:
            lines.append(f"     Pixels: changed {changed:,}, need {needed:,}, gap {gap:,}")

    # Sprint 6.2: Add concrete repair strategy
    if strategy:
        lines.append(f"     STRATEGY: {strategy}")

    return "\n".join(lines)


def build_repair_prompt(
    html: str,
    sandbox_result: SandboxResult,
    user_request: str,
) -> str:
    """
    Build repair prompt with full phase-by-phase context.

    Sprint 6.2 CRITICAL FIX: Now includes BOTH working AND broken elements.
    "Un Fixer que no sabe qué funciona no es un reparador: es un destructor elegante."

    The fixer MUST know:
    - Which elements work (DO NOT MODIFY)
    - Which elements are broken (FIX THESE)
    """
    # Truncate HTML if too long (keep beginning and end)
    max_html_len = 12000
    if len(html) > max_html_len:
        half = max_html_len // 2
        html = html[:half] + "\n\n<!-- ... TRUNCATED ... -->\n\n" + html[-half:]

    # Build rich context for BOTH working and broken elements
    working_elements = []
    broken_elements = []
    under_threshold_count = 0
    no_change_count = 0

    for ir in sandbox_result.interaction_results:
        ctx = ir.get_repair_context(threshold=0.02)

        if ctx["failure_type"] == "passed":
            # Sprint 6.2: Include working elements with FULL semantic context
            # "El fixer debe saber QUÉ funciona para replicar el patrón en lo roto"
            elem = ctx.get("element", {})
            pixels = ctx.get("pixels", {})
            elem_desc = _format_element_context(elem, pixels)
            working_elements.append(
                f"  ✅ {ctx['selector']}\n"
                f"     Status: WORKING (visual change: {ctx['pixel_diff_pct']}, {pixels.get('changed', 0):,} pixels)\n"
                f"     ⛔ DO NOT MODIFY - This element meets requirements\n"
                f"{elem_desc}"
            )
        elif ctx["failure_type"] == "under_threshold":
            under_threshold_count += 1
            # Sprint 6.2: Include semantic context with CONCRETE pixel counts and strategy
            elem = ctx.get("element", {})
            pixels = ctx.get("pixels", {})
            strategy = ctx.get("strategy")
            elem_desc = _format_element_context(elem, pixels, strategy)
            broken_elements.append(
                f"  ⚠️ {ctx['selector']}\n"
                f"     Type: {ctx['failure_type']}\n"
                f"     Change: {ctx['pixel_diff_pct']} (need {ctx['threshold']})\n"
                f"     Problem: {ctx['interpretation']}\n"
                f"{elem_desc}"
            )
        elif ctx["failure_type"] == "no_change":
            no_change_count += 1
            # Sprint 6.2: Include semantic context with strategy
            elem = ctx.get("element", {})
            pixels = ctx.get("pixels", {})
            strategy = ctx.get("strategy")
            elem_desc = _format_element_context(elem, pixels, strategy)
            broken_elements.append(
                f"  ❌ {ctx['selector']}\n"
                f"     Type: {ctx['failure_type']}\n"
                f"     Problem: {ctx['interpretation']}\n"
                f"{elem_desc}"
            )
        elif ctx["failure_type"] == "error":
            elem = ctx.get("element", {})
            strategy = ctx.get("strategy")
            elem_desc = _format_element_context(elem, None, strategy)
            broken_elements.append(
                f"  💥 {ctx['selector']}\n"
                f"     Type: error\n"
                f"     Problem: {ctx['interpretation']}\n"
                f"{elem_desc}"
            )

    working_section = "\n\n".join(working_elements) if working_elements else "  (none detected)"
    broken_section = "\n\n".join(broken_elements) if broken_elements else "  (none)"

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

    # Sprint 6.2: Add protection warning if there are working elements
    protection_warning = ""
    if working_elements:
        protection_warning = f"""
## ⛔ PROTECTED ELEMENTS - DO NOT MODIFY

The following {len(working_elements)} element(s) ALREADY WORK correctly.
You MUST NOT change their CSS, JavaScript handlers, or HTML structure.
Any modification to these elements will BREAK the layout.

{working_section}

---
"""

    # Sprint 6.2: Get navigation exclusion info from Phase 5
    navigation_note = ""
    phase5 = next((p for p in sandbox_result.phases if p.phase == 5), None)
    if phase5:
        nav_excluded = phase5.details.get("navigation_excluded", 0)
        if nav_excluded > 0:
            navigation_note = f"""
## 🔗 NAVIGATION ELEMENTS (excluded from testing)

{nav_excluded} navigation link(s) were detected but excluded from validation.
Navigation elements (links with href) are designed to navigate, not produce local visual feedback.
Do NOT try to add visual effects to navigation links.

---
"""

    # Sprint 6.3: Extract PROTECTED selectors for explicit prohibition
    protected_selectors = []
    for ir in sandbox_result.interaction_results:
        if ir.responsive:
            protected_selectors.append(ir.input.selector)
    
    prohibited_css_section = ""
    if protected_selectors:
        prohibited_css_section = f"""
## 🚫 PROHIBITED CSS SELECTORS

These selectors belong to WORKING elements. You MUST NOT write ANY CSS rule
that matches or affects these selectors:

{chr(10).join(f'  - {sel}' for sel in protected_selectors)}

If you write CSS like `.option {{ }}` and it matches a protected selector, you BREAK the layout.
Use ultra-specific selectors like `[data-option="X"]` where X is the broken element's value.

---
"""

    return f"""Fix this HTML that failed visual validation.

## DIAGNOSIS

{summary}
{protection_warning}{navigation_note}{prohibited_css_section}
## ELEMENTS TO FIX (broken)

{broken_section}

## ORIGINAL REQUEST

"{user_request[:300]}"

## HTML TO FIX

```html
{html}
```

## REPAIR INSTRUCTIONS

1. ⛔ FIRST: Check the PROHIBITED CSS SELECTORS list above
2. Read each broken element's "failure_type" and "STRATEGY" carefully
3. For "under_threshold": Add HIGH-CONTRAST visual changes to ONLY that element
   - Use: background:#fff, border:3px solid #0f0, transform:scale(1.1), box-shadow
   - Selector MUST be ultra-specific: [data-option="X"] or #unique-id
4. For "no_change": Fix the onclick handler for ONLY that element
5. NEVER use generic selectors like .option, .btn, div - they affect protected elements
6. Keep the visual design intact (dark theme, 1920x1080)

## OUTPUT

Return ONLY the corrected HTML from <!DOCTYPE html> to </html>.
"""


# ---------------------------------------------------------------------------
# DIRECT FIXER
# ---------------------------------------------------------------------------

class DirectFixer:
    """
    Phase 7: Send full phase report to Sonnet 4.5 for repair.

    Sprint 6.2: Upgraded from Codex-Max to Sonnet 4.5 for better repair quality.
    Sonnet 4.5 has stronger reasoning for CSS/JS fixes with concrete pixel guidance.
    """

    async def repair(
        self,
        html: str,
        sandbox_result: SandboxResult,
        user_request: str,
        max_tokens: int = 16384,
    ) -> Optional[str]:
        """
        Send all phase failures directly to Sonnet 4.5 for repair.

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
            f"Starting Sonnet 4.5 repair - "
            f"failures: {sandbox_result.failure_summary}"
        )

        try:
            from app.ai.providers.anthropic_provider import anthropic_provider

            # Build prompt with full context
            prompt = build_repair_prompt(html, sandbox_result, user_request)

            # Call Sonnet 4.5 directly (upgraded from Codex-Max)
            response = await anthropic_provider.generate(
                prompt=prompt,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                temperature=0.2,  # Low temperature for consistent repairs
                max_tokens=max_tokens,
            )

            if not response.success:
                logger.warning(f"Sonnet 4.5 repair failed: {response.error}")
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
        Repair using Sonnet 4.5 (same as repair(), kept for API compatibility).

        Sprint 6.2: Sonnet 4.5 has strong reasoning built-in, no special mode needed.

        Args:
            html: HTML that failed validation
            sandbox_result: Full validation result
            user_request: Original user request
            effort: Ignored (Sonnet 4.5 has built-in reasoning)
            max_tokens: Max tokens for response

        Returns:
            Repaired HTML or None if repair failed
        """
        if sandbox_result.valid:
            return html

        logger.info(
            f"Starting Sonnet 4.5 reasoning repair - "
            f"failures: {sandbox_result.failure_summary}"
        )

        try:
            from app.ai.providers.anthropic_provider import anthropic_provider

            prompt = build_repair_prompt(html, sandbox_result, user_request)

            # Sonnet 4.5 has strong reasoning built-in
            response = await anthropic_provider.generate(
                prompt=prompt,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                temperature=0.1,  # Even lower for reasoning mode
                max_tokens=max_tokens,
            )

            if not response.success:
                logger.warning(f"Sonnet 4.5 reasoning repair failed: {response.error}")
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
