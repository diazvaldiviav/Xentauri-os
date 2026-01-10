"""
HTML Repair Prompts - Prompts for diagnosing and repairing invalid HTML.

Sprint 5.2: When GPT-5.2 generates invalid HTML, these prompts enable:
1. Gemini to diagnose what's wrong (fast, cheap)
2. GPT-5.2 to repair based on the diagnosis

Architecture:
=============
- Diagnosis: Short, focused prompt for Gemini (minimal tokens)
- Repair: Detailed prompt for GPT-5.2 with context and requirements
"""


# ---------------------------------------------------------------------------
# DIAGNOSIS PROMPT (For Gemini - fast, cheap)
# ---------------------------------------------------------------------------

def build_html_diagnosis_prompt(html: str, validation_error: str) -> str:
    """
    Build prompt for Gemini to diagnose HTML issues.
    
    Args:
        html: The invalid HTML string
        validation_error: The validation error message
        
    Returns:
        Prompt for Gemini diagnosis
    """
    # Truncate HTML to avoid token limits while keeping relevant parts
    html_preview = html
    if len(html) > 1500:
        # Show beginning and end where issues typically occur
        html_preview = html[:800] + "\n\n... [truncated] ...\n\n" + html[-500:]
    
    return f"""Analyze this HTML and identify what's wrong in 1-2 sentences.

VALIDATION ERROR:
{validation_error}

HTML:
```html
{html_preview}
```

Common issues to check:
- Missing closing tags (</html>, </body>, </div>)
- Truncated/incomplete HTML
- Missing DOCTYPE or <html> tag
- Malformed tag structure

Your diagnosis (1-2 sentences):"""


# ---------------------------------------------------------------------------
# REPAIR PROMPT (For GPT-5.2)
# ---------------------------------------------------------------------------

def build_html_repair_prompt(html: str, diagnosis: str, original_request: str) -> str:
    """
    Build prompt for GPT-5.2 to repair HTML based on diagnosis.
    
    Args:
        html: The original invalid HTML
        diagnosis: Gemini's diagnosis of the issue
        original_request: What the user originally asked for
        
    Returns:
        Prompt for GPT-5.2 repair
    """
    # Truncate original request if too long
    request_preview = original_request
    if len(original_request) > 300:
        request_preview = original_request[:300] + "..."
    
    return f"""You previously generated HTML that has a structural issue. Please fix it.

## DIAGNOSIS
{diagnosis}

## ORIGINAL USER REQUEST
"{request_preview}"

## INVALID HTML
```html
{html}
```

## REPAIR INSTRUCTIONS
1. Fix the specific issue identified in the diagnosis
2. Ensure the HTML is complete and well-formed
3. Keep ALL the original content and styling
4. Requirements:
   - Standalone HTML (inline CSS, no external dependencies)
   - Target: 1920x1080 TV screen
   - Dark theme with good readability
   - Must start with <!DOCTYPE html>
   - Must end with </html>

## OUTPUT
Return ONLY the corrected HTML, starting with <!DOCTYPE html> and ending with </html>.
No explanations, no markdown code blocks - just the raw HTML."""


# ---------------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------------

def get_diagnosis_system_prompt() -> str:
    """System prompt for Gemini HTML diagnosis."""
    return """You are an HTML validator expert. Analyze HTML and identify structural issues.
Be concise - respond in 1-2 sentences describing exactly what's wrong.
Focus on: missing tags, truncation, broken structure, malformed elements."""


def get_repair_system_prompt() -> str:
    """System prompt for GPT-5.2 HTML repair."""
    return """You are an HTML repair specialist for TV display layouts.
Fix HTML structural issues while preserving all content and styling.
Output ONLY the corrected HTML, starting with <!DOCTYPE html> and ending with </html>.
No explanations or markdown - just raw, valid HTML."""


# ---------------------------------------------------------------------------
# CSS INTERACTIVITY DEBUG PROMPTS (Sprint 5.2.2)
# ---------------------------------------------------------------------------

def build_css_debug_diagnosis_prompt(html: str, expected_interactions: str = None) -> str:
    """
    Build prompt for Gemini to diagnose CSS interactivity issues.

    Focus: FUNCTIONAL errors only, not best practices.

    Args:
        html: The HTML to analyze
        expected_interactions: Optional description of what interactions should work

    Returns:
        Prompt for Gemini diagnosis
    """
    # Truncate HTML but keep CSS and interactive elements
    html_preview = html
    if len(html) > 3000:
        html_preview = html[:1500] + "\n\n... [truncated] ...\n\n" + html[-1000:]

    # Build expected behavior section if provided
    expected_section = ""
    if expected_interactions:
        expected_section = f"""
## EXPECTED BEHAVIOR
The developer intended these interactions:
{expected_interactions}

Verify the DOM structure supports these behaviors.
"""

    return f"""Analyze this HTML for CSS INTERACTIVITY BUGS.

```html
{html_preview}
```
{expected_section}
## RULES TO CHECK

1. **Sibling selectors (`~`, `+`) require same-parent elements.** If CSS uses `:checked ~ X` or `:checked + X`, the input and target X MUST share the same parent node.

2. **Checkbox/radio hack requires:** input with `id`, label with matching `for`, and correct DOM structure per rule 1.

3. **<details> requires <summary>** as first child.

4. **:target links** must point to existing element IDs.

5. **Hidden elements** (display:none, opacity:0) must have a CSS rule that reveals them.

## RESPONSE
- "NO ISSUES" if interactivity works
- Or 1-2 sentences describing functional bugs only"""


def build_css_debug_repair_prompt(html: str, diagnosis: str) -> str:
    """
    Build prompt for Codex-Max to fix CSS interactivity bugs.

    Args:
        html: The HTML with bugs
        diagnosis: Gemini's diagnosis of functional issues

    Returns:
        Prompt for Codex-Max repair
    """
    return f"""Fix the CSS interactivity bugs in this HTML.

## DIAGNOSIS
{diagnosis}

## HTML TO FIX
```html
{html}
```

## FIX RULES

1. **Sibling selector fix:** Move inputs to be direct siblings of target elements. Hide moved inputs with CSS.

2. **Preserve everything else:** Keep all visual design, content, animations, colors unchanged.

3. **Minimal changes:** Fix ONLY what's broken, don't refactor working code.

## OUTPUT
Return ONLY the fixed HTML from <!DOCTYPE html> to </html>. No explanations."""


def get_css_debug_diagnosis_system_prompt() -> str:
    """System prompt for Gemini CSS interactivity diagnosis."""
    return """You are a CSS interactivity debugger. Find FUNCTIONAL bugs only.
Focus on: checkbox hacks, radio hacks, details/summary, :target navigation, :checked selectors.
Respond "NO ISSUES" if everything works, or describe bugs in 1-2 sentences.
Do NOT suggest improvements or best practices - only report broken functionality."""


def get_css_debug_repair_system_prompt() -> str:
    """System prompt for Codex-Max CSS interactivity repair."""
    return """You are a CSS interactivity repair specialist.
Fix ONLY the functional bugs identified. Do not change visual design or refactor code.
Output ONLY corrected HTML from <!DOCTYPE html> to </html>.
No explanations or markdown."""


# ---------------------------------------------------------------------------
# VALIDATION REPAIR PROMPTS (Sprint 5.2.3)
# ---------------------------------------------------------------------------

def build_validation_diagnosis_prompt(
    html: str,
    validation_errors: list,
    behavior_report_str: str = None,
) -> str:
    """
    Build prompt for Gemini to diagnose validation errors.

    Args:
        html: The HTML that failed validation
        validation_errors: List of validation error messages
        behavior_report_str: Optional behavior report from testing

    Returns:
        Prompt for Gemini diagnosis
    """
    # Truncate HTML to avoid token limits
    html_preview = html
    if len(html) > 2000:
        html_preview = html[:1000] + "\n\n... [truncated] ...\n\n" + html[-800:]

    errors_str = "\n".join(f"- {err}" for err in validation_errors) if validation_errors else "No specific errors"

    behavior_section = ""
    if behavior_report_str:
        behavior_section = f"""

BEHAVIOR TEST RESULTS:
{behavior_report_str}
"""

    return f"""Analyze this HTML and identify why validation failed in 2-3 sentences.

VALIDATION ERRORS:
{errors_str}
{behavior_section}
HTML:
```html
{html_preview}
```

Common issues to check:
- Interactive elements that don't produce visible changes when clicked
- Missing or broken CSS transitions/animations
- Elements hidden by CSS that never become visible
- JavaScript errors preventing interactivity
- Z-index issues hiding clickable elements

Your diagnosis (2-3 sentences describing the root cause):"""


def build_validation_repair_prompt(
    html: str,
    diagnosis: str,
    validation_errors: list,
    user_request: str,
) -> str:
    """
    Build prompt for Codex-Max to repair validation failures.

    Args:
        html: The HTML that failed validation
        diagnosis: Gemini's diagnosis of the issues
        validation_errors: List of validation error messages
        user_request: Original user request

    Returns:
        Prompt for Codex-Max repair
    """
    # Truncate if needed
    request_preview = user_request[:400] if len(user_request) > 400 else user_request

    errors_str = "\n".join(f"- {err}" for err in validation_errors) if validation_errors else "No specific errors"

    return f"""Fix this HTML that failed visual validation.

## DIAGNOSIS
{diagnosis}

## VALIDATION ERRORS
{errors_str}

## ORIGINAL USER REQUEST
"{request_preview}"

## HTML TO FIX
```html
{html}
```

## CRITICAL REQUIREMENTS
1. All interactive elements MUST produce VISIBLE changes when clicked
2. CSS transitions and animations MUST actually execute (not just add classes)
3. Clicks should change: background color, opacity, transform, border, or other visible properties
4. Keep dark theme optimized for 1920x1080 TV display
5. Must start with <!DOCTYPE html> and end with </html>

## COMMON FIXES NEEDED
- Add actual CSS rules for state changes (e.g., .selected {{ background: #4CAF50; }})
- Ensure transitions have visible duration and effect
- Fix z-index so clickable elements are accessible
- Add visual feedback for hover/active/selected states

## OUTPUT
Return ONLY the corrected HTML, starting with <!DOCTYPE html> and ending with </html>.
No explanations, no markdown code blocks - just the raw HTML."""


def get_validation_diagnosis_system_prompt() -> str:
    """System prompt for Gemini validation diagnosis."""
    return """You are an HTML validation expert specializing in interactive layouts.
Analyze HTML that failed visual validation and identify the root cause.
Focus on: missing visual feedback, broken interactivity, CSS issues, hidden elements.
Be concise - respond in 2-3 sentences describing exactly what's wrong."""


def get_validation_repair_system_prompt() -> str:
    """System prompt for Codex-Max validation repair."""
    return """You are an HTML repair specialist for interactive TV display layouts.

Your task is to fix HTML that failed visual validation. The validation system uses
actual screenshot comparison to detect changes - clicking elements MUST produce
visible pixel differences.

CRITICAL: Every interactive element must produce a VISIBLE change when clicked:
- Background color changes
- Opacity changes
- Transform effects (scale, rotate)
- Border changes
- Element appearance/disappearance

Output ONLY the corrected HTML from <!DOCTYPE html> to </html>.
No explanations or markdown - just raw, valid HTML."""
