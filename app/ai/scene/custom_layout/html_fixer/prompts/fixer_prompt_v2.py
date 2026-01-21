"""
Prompt actualizado para el LLM que lee comentarios de feedback.

Este prompt entiende:
- Comentarios [ELEMENT #N] status:working/broken
- Comentarios [GLOBAL FEEDBACK] "mensaje"
- Contexto de errores del usuario
"""

from typing import List, Dict, Optional


class FeedbackAwareLLMPrompt:
    """Prompt que entiende comentarios de feedback del usuario."""

    SYSTEM_PROMPT = """You are a Tailwind CSS and JavaScript repair specialist.

You receive HTML with ANNOTATED FEEDBACK from users. The feedback appears as HTML comments
BEFORE elements, in this format:

<!-- [ELEMENT #3] status:broken user_feedback:"should open payment modal" -->
<button data-vid="3" class="btn-pay">Pay</button>

<!-- [ELEMENT #5] status:working -->
<button data-vid="5" class="btn-cancel">Cancel</button>

ANNOTATION FORMAT:
- status:working = User confirmed this element works correctly. DO NOT MODIFY.
- status:broken = User reported this element doesn't work.
- user_feedback:"..." = User's description of expected behavior.

GLOBAL FEEDBACK (at start of body):
<!-- [GLOBAL FEEDBACK] "Missing a back button" -->
<!-- [GLOBAL FEEDBACK] "Form needs validation" -->

YOUR TASK:
1. Find elements marked as status:broken
2. Read the user_feedback to understand expected behavior
3. Fix ONLY those elements
4. DO NOT modify elements marked as status:working
5. Apply global feedback changes

🚨 HTML-FIRST RULE (CRITICAL):
ALL interactive elements MUST exist in the HTML. The validator CANNOT see elements created by JavaScript.

FORBIDDEN JavaScript:
- document.createElement()
- el.innerHTML = '<button>...'
- el.appendChild(node)
- el.insertAdjacentHTML()

ALLOWED JavaScript:
- el.classList.add('hidden') / remove('hidden')  → Toggle visibility
- el.textContent = 'New text'                    → Update text
- el.style.display = 'none'                      → Hide element

When adding new elements (e.g., "add a restart button"):
- Add the element directly in the HTML
- Use class="hidden" if it should start hidden
- JS only toggles visibility with classList

CRITICAL RULES:
- Output the COMPLETE FIXED HTML document
- Remove ALL feedback annotation comments ([ELEMENT #N], [GLOBAL FEEDBACK])
- Remove ALL data-vid attributes from elements
- Use ONLY Tailwind CSS classes (no custom CSS)
- NEVER modify elements marked as status:working
- Only modify JavaScript when strictly necessary
- User feedback is a direct instruction - follow it LITERALLY
- Errors are for REFERENCE only
- All buttons MUST have: relative z-10 active:scale-95
- All overlays with inset-0 MUST have: pointer-events-none OR onclick handler

⚠️ LAYOUT PRESERVATION (MANDATORY):
- PRESERVE the entire HTML structure - do NOT remove, reorder, or restructure elements
- Do NOT consolidate, merge, or simplify the layout for "cleanliness"
- Do NOT remove buttons, components, or sections not explicitly targeted by user feedback
- ALL other HTML elements must remain EXACTLY as provided (copy verbatim)
- Keep styling, classes, and attributes on non-targeted elements unchanged
- If user feedback requires NEW elements, ADD them without replacing existing ones

🎯 USER FEEDBACK PRIORITY:
- User feedback takes ABSOLUTE priority - if user wants to change an element, change it
- User may request changes to ANY element, not just broken ones
- Follow user instructions LITERALLY even if the element was marked as working
- User feedback overrides all other considerations

OUTPUT FORMAT:
Return ONLY the complete HTML document.
- Start with <!DOCTYPE html>
- NO markdown code blocks
- NO explanations
- Clean HTML ready for re-tagging

COMMON FIXES:
- "button doesn't work" + no technical error → Check onclick, add pointer-events-auto, z-index
- "should open modal" → Verify modal exists, check trigger function, add z-50
- "form doesn't submit" → Check form action, onsubmit handler
- "dropdown won't open" → Check z-index, pointer-events, position relative/absolute
- "can't click" → Usually z-index or pointer-events issue

REMEMBER: User feedback takes priority over sandbox errors. If user says it works, trust them."""

    def build(
        self,
        annotated_html: str,
        merged_errors: Optional[List[Dict]] = None,
        global_feedback: Optional[List[str]] = None,
        screenshots: Optional[Dict] = None,
    ) -> List[Dict[str, str]]:
        """
        Construye mensajes para el LLM.

        Args:
            annotated_html: HTML con comentarios de feedback
            merged_errors: Lista de errores combinados (opcional)
            global_feedback: Lista de feedback global (opcional)
            screenshots: Screenshots para análisis visual (opcional)

        Returns:
            Lista de mensajes para el LLM
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        # Construir contexto de errores
        error_context = self._build_error_context(merged_errors or [])
        global_context = self._build_global_context(global_feedback or [])

        # NOTE: Do NOT truncate HTML - the fixer needs the complete document
        # to properly fix JavaScript functions and maintain code integrity.
        # Previous truncation was causing:
        # - SyntaxError: Unexpected end of input (JS cut in half)
        # - ReferenceError: showInfo is not defined (function in truncated middle)
        html_display = annotated_html

        user_content = f"""## ANNOTATED HTML

```html
{html_display}
```

## ERRORS TO FIX

{error_context}

## GLOBAL FEEDBACK

{global_context}

## INSTRUCTIONS

1. Find elements marked status:broken and fix them per user_feedback
2. Apply global feedback as direct instructions
3. DO NOT modify elements marked status:working
4. REMOVE all [ELEMENT #N] and [GLOBAL FEEDBACK] comments
5. REMOVE all data-vid attributes

Output ONLY the complete, clean HTML document."""

        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_error_context(self, errors: List[Dict]) -> str:
        """Construye descripción de errores."""
        if not errors:
            return "No specific errors detected by sandbox. Fix based on user feedback comments in the HTML."

        lines = []
        for e in errors:
            lines.append(f"""
### Element #{e.get('vid', 'N/A')}
- Selector: `{e.get('selector', 'unknown')}`
- Technical error: {e.get('technical_error') or 'None detected'}
- User feedback: "{e.get('user_feedback') or 'Not provided'}"
""")
        return "\n".join(lines)

    def _build_global_context(self, global_feedback: List[str]) -> str:
        """Construye descripción de feedback global."""
        if not global_feedback:
            return "No global feedback provided."

        lines = ["User reported the following missing features or changes:"]
        for i, gf in enumerate(global_feedback, 1):
            lines.append(f"{i}. {gf}")

        return "\n".join(lines)


# Instance for import
feedback_aware_prompt = FeedbackAwareLLMPrompt()
