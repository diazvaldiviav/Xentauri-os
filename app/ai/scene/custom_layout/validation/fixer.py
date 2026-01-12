"""
Direct Fixer - Phase 7: Send full context to Sonnet for repair.

Sprint 6: Visual-based validation system.
Sprint 7: Vision-enhanced repair with screenshots + extended thinking.

Key difference from old system:
- NO Gemini diagnosis step
- Send ALL phase failures directly to Sonnet
- Full context = better repairs
- Sprint 7: Screenshot analysis for invisible element detection
"""

import logging
import re
from typing import Optional, List

from .contracts import SandboxResult

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.fixer")


# ---------------------------------------------------------------------------
# REPAIR PROMPTS
# ---------------------------------------------------------------------------

REPAIR_SYSTEM_PROMPT = """You are an HTML repair specialist for interactive web layouts.

## VALIDATION SYSTEM

The system uses SCREENSHOT COMPARISON to detect visual changes after clicks.
An element is considered "responsive" if clicking it produces visible change.
The system uses MULTI-SCALE comparison: tight (20px), normal (100px), and full-page.

## FAILURE TYPES

1. **under_threshold** - Button WORKS but visual feedback is TOO SUBTLE
   - The onclick handler fires correctly
   - But the CSS change is too subtle to detect
   - FIX: Make the visual change DRAMATIC (see REQUIRED FIXES below)

2. **no_change** - Button produces ZERO visual change
   - Handler is broken or not connected
   - FIX: Check onclick, ensure it modifies visible CSS

3. **error** - JavaScript error occurred
   - FIX: Fix the error shown in the message

## 🚫 ABSOLUTE PROHIBITIONS

**Your repair will be REJECTED if you:**

1. **REMOVE or HIDE interactive elements** (buttons, inputs, clickable items)
2. **ADD display:none, visibility:hidden, or opacity:0** to hide elements
3. **DELETE containers** that hold interactive content

The validation system counts interactive elements. If original has 2 buttons, repaired MUST have 2+ buttons.

**YOUR JOB IS TO FIX BROKEN CODE, NOT TO REMOVE OR HIDE IT.**

## 🚫 PROHIBITED FIXES (THESE WILL FAIL VALIDATION)

These WILL NOT pass validation - the validator compares SCREENSHOTS:
- var(--anything) - CSS variables may not exist in the HTML
- filter: brightness() / filter: opacity() - too subtle for screenshot detection
- border-only without background change - covers too few pixels
- opacity changes (0.8 → 1.0) - almost invisible difference
- outline: 1-2px - too thin
- box-shadow-only without background - not enough pixel change
- text-decoration: underline - minimal pixel change
- color change only (text color without background)

⚠️ CRITICAL: Use CONCRETE colors (#ffffff, rgba(0,255,0,0.3)) - NEVER use var()

## ✅ REQUIRED FIXES (THESE WILL PASS)

The validator compares SCREENSHOTS before/after click. Background change is MANDATORY.

```css
/* MANDATORY: Always include background change */
[data-X="value"].selected { 
  background: #ffffff !important;  /* or rgba(0,255,0,0.3) */
  color: #000000 !important; 
}

/* GOOD: Background + border */
[data-X="value"].selected { 
  background: rgba(0, 255, 0, 0.3) !important; 
  border: 4px solid #00ff00 !important; 
}

/* GOOD: Background + transform */
[data-X="value"].selected { 
  background: rgba(255,255,255,0.2) !important;
  transform: scale(1.05); 
}

/* GOOD: Background + glow */
[data-X="value"].selected { 
  background: rgba(0, 255, 0, 0.2) !important;
  box-shadow: 0 0 20px 8px #00ff00 !important; 
}
```

⚠️ ABSOLUTE REQUIREMENTS:
1. background-color change is MANDATORY (not optional)
2. Use CONCRETE colors: #ffffff, #00ff00, rgba(0,255,0,0.3)
3. NEVER use var(--anything) - it may not exist
4. Border/shadow/transform are ADDITIONS, not replacements for background

## OUTPUT

Return ONLY the fixed HTML from <!DOCTYPE html> to </html>.
No markdown, no explanations, no code blocks."""


# ---------------------------------------------------------------------------
# SPRINT 7: VISION-ENHANCED REPAIR PROMPTS
# ---------------------------------------------------------------------------

VISION_REPAIR_SYSTEM_PROMPT = """You are an expert HTML repair specialist with VISUAL ANALYSIS capabilities.

You are receiving:
1. A SCREENSHOT of the rendered HTML page
2. The original user request describing what they wanted
3. A validation report showing what failed
4. The HTML code that needs fixing

## YOUR PRIMARY TASK

LOOK AT THE SCREENSHOT and compare it to what the user requested.
Identify what is VISUALLY WRONG or MISSING and fix it.

## 🚫 ABSOLUTE PROHIBITIONS - VIOLATION = AUTOMATIC REJECTION

**NEVER do any of the following - your repair will be REJECTED:**

1. **NEVER REMOVE interactive elements** (buttons, inputs, clickable items)
2. **NEVER ADD display:none** to any element that wasn't already hidden
3. **NEVER ADD visibility:hidden or opacity:0** to hide elements
4. **NEVER DELETE containers** that hold interactive content
5. **NEVER SIMPLIFY** by removing functionality - FIX the broken parts instead

The validation system will REJECT repairs that reduce the number of interactive elements.
If original HTML has 2 buttons, your repaired HTML MUST have at least 2 buttons.

**YOUR JOB IS TO FIX, NOT TO REMOVE OR HIDE.**

## CRITICAL ANALYSIS STEPS

1. **Visual Coherence Check**
   - Does the screenshot show what the user requested?
   - Example: If user asked for "solar system simulation", do you see the sun AND planets?
   - If elements are MISSING from the visual, they need to be made visible

2. **Invisible Element Detection**
   - Elements may exist in HTML/DOM but be INVISIBLE due to:
     - CSS transforms placing them off-screen (rotateX/Y with perspective)
     - opacity: 0 or visibility: hidden
     - z-index issues (behind other elements)
     - size: 0x0 pixels
     - JavaScript not initializing properly

3. **Interactive Feedback Check**
   - Buttons/interactive elements should have VISIBLE feedback when clicked
   - Background color change is MANDATORY (not just border/shadow)

## COMMON INVISIBLE ELEMENT ISSUES

### 3D Transforms (Most Common!)
```css
/* BROKEN - Planets invisible due to 3D rotation without proper positioning */
.planet {
    transform: rotateY(45deg);  /* Rotates element "into" the screen */
}

/* FIXED - Add transform-style and ensure elements stay in view */
.orbit-container {
    transform-style: preserve-3d;
    perspective: 1000px;
}
.planet {
    transform: translateX(100px);  /* Position along orbit */
    /* Don't use rotateY for positioning! */
}
```

### JavaScript Initialization
```javascript
/* BROKEN - Elements created but not positioned */
planets.forEach(p => container.appendChild(p));

/* FIXED - Ensure elements have visible positions */
planets.forEach((p, i) => {
    p.style.left = `${100 + i * 80}px`;
    p.style.top = '50%';
    container.appendChild(p);
});
```

## OUTPUT FORMAT

Return ONLY the corrected HTML from <!DOCTYPE html> to </html>.
No markdown code blocks, no explanations - just the HTML."""


def build_vision_repair_prompt(
    html: str,
    sandbox_result: SandboxResult,
    user_request: str,
) -> str:
    """
    Sprint 7: Build repair prompt WITH SCREENSHOT for vision-based repair.

    This prompt is designed to work with Claude's vision API.
    The screenshot is passed separately as an image.

    Key differences from text-only repair:
    1. Emphasizes VISUAL coherence check
    2. Asks Claude to compare screenshot vs user request
    3. Focuses on invisible element detection
    """
    # Build phase summary (same as before)
    phase_summary = _build_phase_summary(sandbox_result)

    # Build invisible elements report (Sprint 7)
    invisible_report = _build_invisible_elements_report(sandbox_result)

    # Truncate HTML if needed
    max_html_len = 10000
    if len(html) > max_html_len:
        half = max_html_len // 2
        truncated_html = html[:half] + "\n\n<!-- ... TRUNCATED ... -->\n\n" + html[-half:]
    else:
        truncated_html = html

    return f"""## SCREENSHOT ATTACHED

Look at the screenshot above. This is what the HTML currently renders.

## ORIGINAL USER REQUEST

"{user_request}"

## QUESTION FOR YOU

Does the screenshot show what the user requested?
If NOT, what is MISSING or WRONG?

---

{phase_summary}

---

{invisible_report}

---

## HTML TO FIX

```html
{truncated_html}
```

## REPAIR INSTRUCTIONS

1. **FIRST**: Look at the screenshot and identify what's visually wrong
2. **SECOND**: Check the invisible elements report above
3. **THIRD**: Fix the HTML so that ALL requested elements are VISIBLE

Common fixes needed:
- If elements exist but aren't visible → Fix their CSS positioning/transforms
- If 3D transforms are used → Ensure preserve-3d and proper perspective
- If JavaScript creates elements → Ensure they have visible positions
- If click feedback is too subtle → Add background-color changes

## OUTPUT

Return ONLY the corrected HTML from <!DOCTYPE html> to </html>.
"""


def _build_invisible_elements_report(sandbox_result: SandboxResult) -> str:
    """
    Sprint 7: Build report of elements that exist in DOM but are invisible.
    """
    lines = []
    lines.append("## 👻 INVISIBLE ELEMENTS DETECTED\n")

    invisible_count = 0

    for ir in sandbox_result.interaction_results:
        if ir.input.is_invisible():
            invisible_count += 1
            lines.append(f"### Element {invisible_count}: `{ir.input.selector}`")
            lines.append(f"- **Status**: EXISTS in DOM but has NO visible pixels")
            lines.append(f"- **Visibility ratio**: {ir.input.visibility_ratio:.1%}")
            lines.append(f"- **Tag**: {ir.input.tag}")

            # Get classes for diagnosis
            classes = ir.input.key_attributes.get("class", "")
            if classes:
                lines.append(f"- **Classes**: {classes}")

            lines.append("")

    if invisible_count == 0:
        lines.append("No invisible elements detected in Phase 4.\n")
        lines.append("However, elements may still be missing - check the screenshot!\n")
    else:
        lines.append(f"\n⚠️ **{invisible_count} element(s) exist in HTML but are NOT VISIBLE!**")
        lines.append("These need CSS/JS fixes to become visible.\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSS DIAGNOSTIC FUNCTIONS - Sprint 6.5
# ---------------------------------------------------------------------------

def _extract_css_from_html(html: str) -> str:
    """Extract all CSS from <style> tags in HTML."""
    css_blocks = []
    pattern = r'<style[^>]*>(.*?)</style>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    for match in matches:
        css_blocks.append(match)
    return "\n".join(css_blocks)


def _find_css_rules_for_classes(css: str, classes: list) -> list:
    """
    Find CSS rules that match any of the given classes combined with .selected or .active.
    
    Args:
        css: CSS content
        classes: List of class names (e.g., ['celestial-body', 'venus'])
    
    Returns:
        List of dicts with rule info: [{"selector": "...", "properties": "...", "has_background": bool}]
    """
    rules = []
    
    # Pattern to find CSS rules: selector { properties }
    rule_pattern = r'([^{}]+)\{([^{}]+)\}'
    
    for match in re.finditer(rule_pattern, css):
        selector = match.group(1).strip()
        properties = match.group(2).strip()
        
        # Check if this rule involves .selected or .active
        if '.selected' not in selector and '.active' not in selector:
            continue
        
        # Check if this rule involves any of our classes
        for cls in classes:
            if f'.{cls}' in selector:
                has_background = bool(re.search(r'\bbackground(?:-color)?\s*:', properties, re.IGNORECASE))
                rules.append({
                    "selector": selector,
                    "properties": properties,
                    "has_background": has_background,
                    "matched_class": cls,
                })
                break  # Don't add same rule multiple times
    
    return rules


def analyze_css_for_element(html: str, element_classes: list) -> dict:
    """
    Sprint 6.5: Analyze CSS to diagnose why an element's visual feedback fails.
    
    This is the KEY function that bridges pixel-based validation with CSS-based repair.
    
    Args:
        html: Full HTML with embedded CSS
        element_classes: Classes from the failing element (e.g., ['celestial-body', 'venus'])
    
    Returns:
        {
            "rules_found": [{"selector": "...", "properties": "...", "has_background": bool}],
            "has_background": False,  # Any rule has background?
            "diagnosis": "NO tiene background-color",
            "fix_action": "Añadir 'background-color: rgba(0,200,255,0.3);' a .celestial-body.selected",
            "problematic_rule": ".celestial-body.selected { transform: scale(1.5); ... }"
        }
    """
    css = _extract_css_from_html(html)
    rules = _find_css_rules_for_classes(css, element_classes)
    
    result = {
        "rules_found": rules,
        "has_background": False,
        "diagnosis": "",
        "fix_action": "",
        "problematic_rule": "",
    }
    
    if not rules:
        # No .selected/.active rules found for these classes
        result["diagnosis"] = f"No se encontró regla .selected/.active para clases: {', '.join(element_classes)}"
        result["fix_action"] = f"Crear regla CSS: .{element_classes[0]}.selected {{ background-color: rgba(0,200,255,0.3); }}"
        return result
    
    # Check if any rule has background
    rules_with_bg = [r for r in rules if r["has_background"]]
    rules_without_bg = [r for r in rules if not r["has_background"]]
    
    if rules_with_bg:
        result["has_background"] = True
        result["diagnosis"] = "Ya tiene background-color (problema puede ser otro)"
    else:
        result["has_background"] = False
        # Pick the most specific rule to fix
        rule_to_fix = rules_without_bg[0]
        result["diagnosis"] = f"La regla '{rule_to_fix['selector']}' NO tiene background-color"
        result["problematic_rule"] = f"{rule_to_fix['selector']} {{ {rule_to_fix['properties']} }}"
        result["fix_action"] = (
            f"Modificar '{rule_to_fix['selector']}' añadiendo: background-color: rgba(0,200,255,0.3);"
        )
    
    return result


def _build_phase_summary(sandbox_result) -> str:
    """
    Sprint 6.5: Build a progressive summary of all validation phases.
    
    This gives Sonnet the full context of what happened in each phase.
    """
    lines = []
    lines.append("## 📋 VALIDATION REPORT\n")
    
    for phase in sandbox_result.phases:
        emoji = "✅" if phase.passed else "❌"
        phase_num = phase.phase
        phase_name = phase.phase_name.upper()
        
        if phase_num == 1:
            lines.append(f"### Phase 1: Render {emoji}")
            if phase.passed:
                lines.append("HTML renderiza correctamente en viewport 1920x1080\n")
            else:
                lines.append(f"Error: {phase.error}\n")
        
        elif phase_num == 2:
            lines.append(f"### Phase 2: Visual Check {emoji}")
            if phase.passed:
                lines.append("Página tiene contenido visual (no está en blanco)\n")
            else:
                lines.append("Página está en blanco o tiene error visual\n")
        
        elif phase_num == 3:
            lines.append(f"### Phase 3: Scene Graph {emoji}")
            layout_type = phase.details.get("layout_type", "unknown")
            lines.append(f"Layout detectado: {layout_type}\n")
        
        elif phase_num == 4:
            lines.append(f"### Phase 4: Input Detection {emoji}")
            interactive = phase.details.get("interactive_count", 0)
            nav_excluded = phase.details.get("navigation_excluded", 0)
            display_excluded = phase.details.get("display_only", 0)
            lines.append(f"Detectados {interactive} elementos INTERACTIVE_UI")
            if nav_excluded > 0:
                lines.append(f"  - {nav_excluded} elementos NAVIGATION excluidos")
            if display_excluded > 0:
                lines.append(f"  - {display_excluded} elementos DISPLAY_ONLY excluidos")
            lines.append("")
        
        elif phase_num == 5:
            lines.append(f"### Phase 5: Interaction Testing {emoji}")
            tested = phase.details.get("tested", 0)
            responsive = phase.details.get("responsive", 0)
            lines.append(f"Resultado: {responsive}/{tested} elementos responden correctamente")

            # Sprint 7: Show JS errors detected during interaction
            js_errors = phase.details.get("js_errors_during_interaction", [])
            if js_errors:
                lines.append(f"\n⚠️ **{len(js_errors)} ERROR(ES) JAVASCRIPT DETECTADO(S) DURANTE INTERACCIÓN:**")
                for i, err in enumerate(js_errors[:5]):  # Show first 5
                    # Truncate long error messages
                    err_short = err[:200] + "..." if len(err) > 200 else err
                    lines.append(f"  {i+1}. `{err_short}`")
                lines.append("\n**ESTO ES CRÍTICO: Los botones pueden parecer funcionar pero el JavaScript falla.**")
                lines.append("Revisa funciones llamadas después de clicks (setTimeout, event handlers, etc.)")
            lines.append("")
        
        elif phase_num == 6:
            lines.append(f"### Phase 6: Aggregation {emoji}")
            if not phase.passed:
                lines.append(f"FALLO: {sandbox_result.failure_summary}\n")
    
    return "\n".join(lines)


def _build_css_diagnosis(html: str, interaction_results: list, threshold: float = 0.02) -> str:
    """
    Sprint 6.5: Build detailed CSS diagnosis for each failing element.
    
    This is the critical section that tells Sonnet EXACTLY what CSS to fix.
    """
    lines = []
    lines.append("## 🔧 CSS DIAGNOSIS FOR FAILING ELEMENTS\n")
    
    failing_count = 0
    
    for ir in interaction_results:
        ctx = ir.get_repair_context(threshold=threshold)
        
        if ctx["failure_type"] == "passed":
            continue
        
        failing_count += 1
        selector = ctx["selector"]
        elem = ctx.get("element", {})
        
        # Get element classes
        key_attrs = elem.get("key_attributes", {})
        class_attr = key_attrs.get("class", "")
        
        # Also try to extract from selector
        classes = []
        if class_attr:
            classes.extend(class_attr.split())
        
        # Extract classes from selector (e.g., ".celestial-body" -> "celestial-body")
        selector_classes = re.findall(r'\.([a-zA-Z][\w-]*)', selector)
        for cls in selector_classes:
            if cls not in classes and cls not in ('selected', 'active'):
                classes.append(cls)
        
        if not classes:
            classes = ["unknown"]
        
        lines.append(f"### ❌ Input {failing_count}: `{selector}`\n")
        
        # Element info
        tag = elem.get("tag", "div")
        text = elem.get("text_content", "")
        lines.append(f"**Element:** `<{tag}>` with classes: `{', '.join(classes)}`")
        if text:
            lines.append(f"**Text:** \"{text[:50]}\"")
        
        # Failure info
        lines.append(f"**Failure Type:** {ctx['failure_type']}")
        lines.append(f"**Pixel Change:** {ctx['pixel_diff_pct']} (need {ctx['threshold']})")
        
        # CSS Diagnosis
        css_analysis = analyze_css_for_element(html, classes)
        
        lines.append(f"\n**CSS Diagnosis:**")
        lines.append(f"- {css_analysis['diagnosis']}")
        
        if css_analysis["problematic_rule"]:
            lines.append(f"\n**Current CSS Rule:**")
            lines.append(f"```css")
            lines.append(css_analysis["problematic_rule"])
            lines.append(f"```")
        
        lines.append(f"\n**🎯 REQUIRED ACTION:**")
        lines.append(f"{css_analysis['fix_action']}")
        
        if not css_analysis["has_background"]:
            # Show the exact fix needed
            rule_selector = css_analysis["rules_found"][0]["selector"] if css_analysis["rules_found"] else f".{classes[0]}.selected"
            old_props = css_analysis["rules_found"][0]["properties"] if css_analysis["rules_found"] else ""
            
            lines.append(f"\n**✅ CORRECTED CSS:**")
            lines.append(f"```css")
            lines.append(f"{rule_selector} {{")
            lines.append(f"    background-color: rgba(0, 200, 255, 0.3);  /* ADD THIS */")
            if old_props:
                # Show existing properties
                for prop in old_props.split(';'):
                    prop = prop.strip()
                    if prop:
                        lines.append(f"    {prop};")
            lines.append(f"}}")
            lines.append(f"```")
        
        lines.append("")
    
    if failing_count == 0:
        lines.append("No failing elements detected.\n")
    
    return "\n".join(lines)


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
    Sprint 6.5: Build repair prompt with PROGRESSIVE CONTEXT and CSS DIAGNOSIS.
    
    Key improvements over Sprint 6.2:
    1. Phase-by-phase summary showing what passed/failed
    2. CSS diagnosis for each failing element
    3. Exact CSS rules to modify with concrete examples
    
    "Sonnet es suficientemente fuerte para reparar si le damos el diagnóstico exacto."
    """
    # Truncate HTML if too long (keep beginning and end)
    max_html_len = 12000
    if len(html) > max_html_len:
        half = max_html_len // 2
        truncated_html = html[:half] + "\n\n<!-- ... TRUNCATED ... -->\n\n" + html[-half:]
    else:
        truncated_html = html

    # Sprint 6.5: Build progressive phase summary
    phase_summary = _build_phase_summary(sandbox_result)
    
    # Sprint 6.5: Build CSS diagnosis for failing elements
    css_diagnosis = _build_css_diagnosis(html, sandbox_result.interaction_results, threshold=0.02)
    
    # Build protected elements list
    protected_selectors = []
    for ir in sandbox_result.interaction_results:
        if ir.responsive:
            protected_selectors.append(ir.input.selector)
    
    protected_section = ""
    if protected_selectors:
        protected_section = f"""
## ⛔ PROTECTED ELEMENTS - DO NOT MODIFY

These {len(protected_selectors)} element(s) ALREADY WORK correctly:
{chr(10).join(f'  ✅ {sel}' for sel in protected_selectors)}

You MUST NOT change their CSS or JavaScript.

---
"""

    # Sprint 6.4: Get display-only exclusion info from Phase 4
    display_only_note = ""
    phase4 = next((p for p in sandbox_result.phases if p.phase == 4), None)
    if phase4:
        display_only_excluded = phase4.details.get("display_only", 0)
        if display_only_excluded > 0:
            display_only_note = f"""
## 🖥️ DISPLAY-ONLY ELEMENTS (excluded)

{display_only_excluded} display-only element(s) excluded from validation.
Do NOT add click handlers to clocks, weather widgets, calendars, or charts.

---
"""

    return f"""Fix this HTML that failed visual validation.

{phase_summary}

---

{css_diagnosis}

---
{protected_section}{display_only_note}
## ORIGINAL REQUEST

"{user_request[:300]}"

## HTML TO FIX

```html
{truncated_html}
```

## REPAIR INSTRUCTIONS

Based on the CSS DIAGNOSIS above, make these specific changes:

1. **For each failing element**: Find the CSS rule mentioned in the diagnosis
2. **Add background-color**: This is MANDATORY for passing validation
3. **Use concrete colors**: `rgba(0,200,255,0.3)`, `#ffffff`, `#00ff00`
4. **DO NOT use**: `var(--anything)`, `filter:`, `opacity:` alone
5. **DO NOT modify** protected elements (marked with ✅)

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

    async def repair_with_vision(
        self,
        html: str,
        sandbox_result: SandboxResult,
        user_request: str,
        screenshot: bytes,
        max_tokens: int = 16384,
        thinking_budget: int = 10000,
    ) -> Optional[str]:
        """
        Sprint 7: Repair using vision (screenshot analysis) + extended thinking.

        This is the most powerful repair method. It:
        1. Shows Claude the actual rendered screenshot
        2. Uses extended thinking for complex reasoning
        3. Compares what user requested vs what's visible
        4. Identifies invisible elements and fixes them

        Args:
            html: HTML that failed validation
            sandbox_result: Full validation result
            user_request: Original user request
            screenshot: PNG screenshot bytes of the rendered page
            max_tokens: Max tokens for response
            thinking_budget: Extended thinking budget

        Returns:
            Repaired HTML or None if repair failed
        """
        if sandbox_result.valid:
            return html

        logger.info(
            f"Starting vision-enhanced repair - "
            f"failures: {sandbox_result.failure_summary}, "
            f"invisible_count: {sandbox_result.invisible_elements_count}"
        )

        try:
            from app.ai.providers.anthropic_provider import anthropic_provider

            # Build vision repair prompt
            prompt = build_vision_repair_prompt(html, sandbox_result, user_request)

            # Resize screenshot for optimal API performance
            from .visual_analyzer import resize_image_for_api
            optimized_screenshot = resize_image_for_api(screenshot)

            # Call with vision + extended thinking
            response = await anthropic_provider.generate_with_vision(
                prompt=prompt,
                images=[optimized_screenshot],
                system_prompt=VISION_REPAIR_SYSTEM_PROMPT,
                max_tokens=max_tokens,
                use_extended_thinking=True,
                thinking_budget=thinking_budget,
            )

            if not response.success:
                logger.warning(f"Vision repair failed: {response.error}")
                # Fallback to regular repair
                return await self.repair(html, sandbox_result, user_request, max_tokens)

            # Clean and extract HTML
            repaired_html = self._clean_html_response(response.content)

            if repaired_html:
                logger.info(
                    f"Vision repair completed - "
                    f"original: {len(html)} chars, "
                    f"repaired: {len(repaired_html)} chars, "
                    f"latency: {response.latency_ms:.0f}ms"
                )
                return repaired_html
            else:
                logger.warning("Failed to extract valid HTML from vision repair")
                # Fallback to regular repair
                return await self.repair(html, sandbox_result, user_request, max_tokens)

        except Exception as e:
            logger.error(f"Vision repair error: {e}", exc_info=True)
            # Fallback to regular repair
            return await self.repair(html, sandbox_result, user_request, max_tokens)

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
