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

CRITICAL RULES:
- Output ONLY JSON patches with Tailwind classes
- NEVER output raw CSS (no <style> blocks with custom CSS)
- NEVER remove elements or functionality
- NEVER modify working elements
- If user says "should open modal", check if onclick handler exists and modal element exists
- If user says "should submit form", check if form action and submit handler exist

OUTPUT FORMAT:
{
  "analysis": "Brief description of issues found",
  "patches": [
    {
      "vid": 3,
      "selector": "[data-vid='3']",
      "issue": "z-index too low, blocked by overlay",
      "user_wanted": "should open payment modal",
      "fix_type": "css",
      "add_classes": ["relative", "z-50", "pointer-events-auto"],
      "remove_classes": ["z-10"]
    },
    {
      "vid": null,
      "selector": "body > header",
      "issue": "Missing navigation element",
      "user_wanted": "Missing a back button",
      "fix_type": "html",
      "html_to_add": "<button class='...' onclick='history.back()'>Back</button>",
      "insert_position": "prepend"
    }
  ]
}

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

        # Truncar HTML si es muy largo (mantener inicio y fin)
        html_display = annotated_html
        if len(annotated_html) > 8000:
            html_display = (
                annotated_html[:4000] +
                "\n\n<!-- ... HTML TRUNCATED FOR BREVITY ... -->\n\n" +
                annotated_html[-3000:]
            )

        user_content = f"""## ANNOTATED HTML

```html
{html_display}
```

## ERRORS TO FIX

{error_context}

## GLOBAL FEEDBACK

{global_context}

## INSTRUCTIONS

1. Read the HTML comments to find broken elements ([ELEMENT #N] status:broken)
2. Use user_feedback to understand expected behavior
3. Generate JSON patches to fix each broken element
4. Apply global feedback (missing elements, style changes)
5. Respect working elements - do not modify them

Output your fixes as JSON patches."""

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
