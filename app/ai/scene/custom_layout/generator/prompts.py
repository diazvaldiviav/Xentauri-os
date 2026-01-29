"""
Prompts for HTML Generation.

System prompts and user prompt templates for Gemini 3 Pro with thinking.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Load the generation rules from markdown file
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_GENERATION_RULES_PATH = _PROMPTS_DIR / "generation_prompt.md"


def _load_generation_rules() -> str:
    """Load generation rules from markdown file."""
    try:
        return _GENERATION_RULES_PATH.read_text()
    except FileNotFoundError:
        return ""


GENERATION_RULES = _load_generation_rules()


SYSTEM_PROMPT = f"""You are an expert HTML/Tailwind CSS developer creating interactive layouts for a 1920x1080 touchscreen TV display.

## Your Task
Generate a complete, self-contained HTML document based on the user's request. The HTML must:
1. Be fully functional with all interactivity working
2. Use Tailwind CSS (via CDN) for all styling
3. Include all necessary JavaScript inline
4. Follow the mandatory rules below to pass validation

## Target Environment
- Display: 1920x1080 touchscreen TV
- Theme: Dark mode (bg-gray-900, text-white)
- Framework: Tailwind CSS v3 (CDN included)
- No external dependencies (everything inline)

{GENERATION_RULES}

## Output Format
Respond with ONLY the HTML document. No explanations, no markdown code blocks.
Start with <!DOCTYPE html> and end with </html>.
"""


def build_user_prompt(
    user_request: str,
    info_type: str = "custom",
    title: str | None = None,
    data: dict | None = None,
    additional_context: str | None = None,
) -> str:
    """
    Build the user prompt for HTML generation.

    Args:
        user_request: Original user request
        info_type: Type of content (trivia, dashboard, game, etc.)
        title: Optional title for the content
        data: Optional data to include in the layout
        additional_context: Any additional context (may include conversation context)

    Returns:
        Formatted user prompt string
    """
    lines = [f"Create an interactive HTML layout for: {user_request}"]

    # Extract and format conversation context if present
    conversation_section = _extract_conversation_context(additional_context)
    if conversation_section:
        lines.append(conversation_section)

    lines.append(f"\nContent type: {info_type}")

    if title:
        lines.append(f"Title: {title}")

    if data:
        lines.append(f"\nData to display:\n```json\n{_format_data(data)}\n```")

    # Add remaining context (layout hints, etc.) excluding conversation
    remaining_context = _get_remaining_context(additional_context)
    if remaining_context:
        lines.append(f"\nAdditional context: {remaining_context}")

    lines.append("\nRemember:")
    lines.append("- All buttons must have `relative z-10` and visible `active:*` feedback")
    lines.append("- All overlays must have `pointer-events-none` or explicit z-index")
    lines.append("- All modals must be dismissable")
    lines.append("- Use `transition-all duration-150` for smooth interactions")
    lines.append("- Add data-* attributes for validator identification")

    return "\n".join(lines)


def _format_data(data: dict) -> str:
    """Format data dict as pretty JSON string."""
    import json
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _parse_context_string(additional_context: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse the additional_context string into a dict.

    The context is passed as JSON from the pipeline (json.dumps with default=str).
    Falls back to ast.literal_eval for legacy str(dict) format.
    """
    if not additional_context:
        return None

    # Try JSON first (primary format after fix)
    try:
        import json
        parsed = json.loads(additional_context)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: ast.literal_eval for legacy str(dict) format
    try:
        parsed = ast.literal_eval(additional_context)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass

    return None


def _extract_conversation_context(additional_context: Optional[str]) -> Optional[str]:
    """
    Extract and format conversation context for the prompt.

    This is critical for topic understanding - the HTML generator needs to know
    what the user was discussing to create relevant content.

    Returns:
        Formatted conversation section or None
    """
    ctx = _parse_context_string(additional_context)
    if not ctx or "conversation" not in ctx:
        return None

    conv = ctx["conversation"]
    if not isinstance(conv, dict):
        return None

    lines = ["\n## CONVERSATION CONTEXT (Critical for understanding the topic)"]
    lines.append("The user has been discussing the following topic. Your HTML MUST be relevant to this conversation:")

    # Format conversation history
    history = conv.get("history", [])
    if history:
        lines.append("\n### Recent conversation:")
        # Take last 5 turns max
        for turn in history[-5:]:
            user_msg = turn.get("user", "")
            if user_msg:
                # Truncate long messages
                user_msg = user_msg[:300] + "..." if len(user_msg) > 300 else user_msg
                lines.append(f"User: {user_msg}")

            assistant_msg = turn.get("assistant", "")
            if assistant_msg:
                # Truncate long messages
                assistant_msg = assistant_msg[:400] + "..." if len(assistant_msg) > 400 else assistant_msg
                lines.append(f"Assistant: {assistant_msg}")

    # Include last response always (not just when no history) - critical for topic continuity
    last_response = conv.get("last_response", "")
    if last_response:
        lines.append(f"\n### Last assistant response:")
        last_response = last_response[:500] + "..." if len(last_response) > 500 else last_response
        lines.append(last_response)

    # Include generated content with actual content (not just title/type)
    generated_content = conv.get("generated_content", {})
    if generated_content:
        content_type = generated_content.get("content_type", "") or generated_content.get("type", "")
        content_title = generated_content.get("title", "")
        content_body = generated_content.get("content", "")
        if content_type or content_title or content_body:
            lines.append(f"\n### Previously generated content:")
            if content_title:
                lines.append(f"Title: {content_title}")
            if content_type:
                lines.append(f"Type: {content_type}")
            if content_body:
                content_body = content_body[:800] + "..." if len(content_body) > 800 else content_body
                lines.append(f"Content: {content_body}")

    # Include content memory items for richer context
    content_memory = conv.get("content_memory", [])
    if content_memory:
        lines.append(f"\n### Recent content memory ({len(content_memory)} items):")
        for item in content_memory[-3:]:  # Last 3 items
            item_title = item.get("title", "untitled")
            item_type = item.get("type", "unknown")
            item_content = item.get("content", "")
            lines.append(f"- [{item_type}] {item_title}")
            if item_content:
                item_content = item_content[:300] + "..." if len(item_content) > 300 else item_content
                lines.append(f"  {item_content}")

    # Only return if we have meaningful content
    if len(lines) > 2:  # More than just the header
        lines.append("\n⚠️ IMPORTANT: Your HTML layout MUST be about the topic from the conversation above, NOT a generic/random topic.")
        return "\n".join(lines)

    return None


def _get_remaining_context(additional_context: Optional[str]) -> Optional[str]:
    """
    Get remaining context (layout hints, etc.) excluding conversation.
    """
    ctx = _parse_context_string(additional_context)
    if not ctx:
        # Return original if we couldn't parse it
        return additional_context

    # Remove conversation key and return remaining
    remaining = {k: v for k, v in ctx.items() if k != "conversation"}
    if remaining:
        # Return just the layout hints or other relevant info
        if "layout_hints" in remaining:
            return f"Layout hints: {remaining['layout_hints']}"
        return str(remaining)

    return None


# Content-type specific prompts
CONTENT_TYPE_HINTS = {
    "trivia": """
For trivia content:
- Display 4 answer options as clickable buttons
- Show a question counter (e.g., "Question 1/10")
- Include a score display
- Add visual feedback for correct/incorrect answers
- Optionally include a timer
""",
    "dashboard": """
For dashboard content:
- Use a grid layout for metrics
- Include interactive filters if applicable
- Add hover states for data cards
- Consider using charts or progress bars
""",
    "game": """
For game content:
- Include a start button
- Show score and lives
- Add a restart/play again button
- Include clear win/lose states
""",
    "calendar": """
For calendar content:
- Display events in a clear timeline
- Include navigation (prev/next day/week)
- Show event details on click
- Use color coding for event types
""",
    "weather": """
For weather content:
- Show current conditions prominently
- Include forecast for coming days
- Use appropriate weather icons
- Add location display
""",
    "list": """
For list content:
- Allow item selection
- Include add/remove functionality
- Show item count
- Support filtering or sorting if needed
""",
}


def get_content_type_hint(info_type: str) -> str:
    """Get content-type specific generation hints."""
    return CONTENT_TYPE_HINTS.get(info_type, "")
