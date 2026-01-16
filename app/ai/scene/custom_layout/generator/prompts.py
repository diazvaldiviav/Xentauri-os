"""
Prompts for HTML Generation.

System prompts and user prompt templates for Gemini 3 Pro with thinking.
"""

from pathlib import Path

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
        additional_context: Any additional context

    Returns:
        Formatted user prompt string
    """
    lines = [f"Create an interactive HTML layout for: {user_request}"]

    lines.append(f"\nContent type: {info_type}")

    if title:
        lines.append(f"Title: {title}")

    if data:
        lines.append(f"\nData to display:\n```json\n{_format_data(data)}\n```")

    if additional_context:
        lines.append(f"\nAdditional context: {additional_context}")

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
