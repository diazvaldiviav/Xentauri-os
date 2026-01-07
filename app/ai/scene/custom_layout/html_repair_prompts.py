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
