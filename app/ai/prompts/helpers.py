"""
Shared Prompt Helpers - Sprint 4.4.0 (GAP #2, #3)

Reusable functions for prompt construction to ensure consistency
across execution, scene, and other specialized prompts.

This module prevents duplication and drift between prompts that handle
the same conversation context elements.

Functions:
- inject_generated_content_context(): Adds generated content to prompts (GAP #2)
- inject_last_event_context(): Adds last event to prompts (GAP #4)
- inject_last_doc_context(): Adds last doc to prompts (GAP #5)
- format_conversation_history(): Standardizes conversation history formatting (GAP #3)
"""

from typing import Dict, Optional


def inject_generated_content_context(
    base_section: str,
    conversation_context: Dict,
    format_style: str = "execution"
) -> str:
    """
    Add generated content context to a prompt section consistently.

    Sprint 4.4.0 - GAP #2: Shared function to prevent drift between
    execution_prompts.py and scene_prompts.py generated_content handling.

    Args:
        base_section: The existing conversation/context section
        conversation_context: Dict with potential "generated_content" key
        format_style: "execution" or "scene" - adjusts formatting for each use case

    Returns:
        Updated section with generated content injected (or original if no content)

    Example:
        >>> context = {"generated_content": {"type": "plan", "title": "South Beach", "content": "..."}}
        >>> section = inject_generated_content_context("", context, "scene")
        >>> "RECENTLY GENERATED CONTENT" in section
        True
    """
    if not conversation_context.get("generated_content"):
        return base_section

    gc = conversation_context["generated_content"]

    if format_style == "scene":
        # Scene prompts need the full content for display in components
        content = gc.get('content', '')
        # Escape quotes and limit length to prevent JSON errors
        sanitized_content = content.replace('"', '\\"').replace('\n', '\\n')
        # Truncate if too long (max 2000 chars to prevent token overflow)
        if len(sanitized_content) > 2000:
            sanitized_content = sanitized_content[:2000] + "... [truncated]"

        return f"""{base_section}
*** RECENTLY GENERATED CONTENT (display this!) ***
  Type: {gc.get('type', 'unknown')}
  Title: {gc.get('title', 'Untitled')}
  Content:
{sanitized_content}

IMPORTANT: Use a text_block component to display this generated content! Include the content in the 'props.content' and 'data.content' fields.

"""

    elif format_style == "execution":
        # Execution prompts need awareness but not full content (for actions)
        content_preview = gc.get('content', '')[:200]  # Short preview
        if len(gc.get('content', '')) > 200:
            content_preview += "..."

        return f"""{base_section}
*** RECENTLY GENERATED CONTENT (CRITICAL) ***
You recently generated this {gc.get('type', 'content').upper()} for the user:
  Type: {gc.get('type', 'unknown')}
  Title: {gc.get('title', 'Untitled')}
  Preview: {content_preview}

IMPORTANT - Display Intent Recognition:
When user says "show it", "display it", "muéstralo", "present it":
→ They want to DISPLAY this generated content on screen
→ Use action_name: "show_content" or similar display action
→ Reference the content above (title: "{gc.get('title', 'Untitled')}")
→ Do NOT search for documents - this is generated content in memory

This content was generated {_format_time_ago(gc.get('timestamp'))} and is still in working memory.

"""

    else:
        # Default fallback
        return f"""{base_section}
*** RECENTLY GENERATED CONTENT ***
Type: {gc.get('type', 'unknown')}
Title: {gc.get('title', 'Untitled')}

IMPORTANT: When user references "it", "that", or "the {gc.get('type', 'content')}", they mean THIS generated content.

"""


def _format_time_ago(timestamp) -> str:
    """Format timestamp as 'X minutes ago' for human readability."""
    if not timestamp:
        return "recently"

    from datetime import datetime, timezone
    elapsed = (datetime.now(timezone.utc) - timestamp).total_seconds()
    minutes_ago = int(elapsed / 60)

    if minutes_ago == 0:
        return "just now"
    elif minutes_ago == 1:
        return "1 minute ago"
    elif minutes_ago < 60:
        return f"{minutes_ago} minutes ago"
    else:
        hours = minutes_ago // 60
        return f"{hours} hour(s) ago"


def inject_last_event_context(
    base_section: str,
    conversation_context: Dict,
    format_style: str = "execution"
) -> str:
    """
    Add last event context to a prompt section consistently.

    Sprint 4.4.0 - GAP #4: Ensures all prompts handle last_event the same way.

    Args:
        base_section: The existing conversation/context section
        conversation_context: Dict with potential "last_event" key
        format_style: "execution" or "scene" - adjusts formatting

    Returns:
        Updated section with last event injected (or original if no event)
    """
    if not conversation_context.get("last_event"):
        return base_section

    event = conversation_context["last_event"]

    if format_style == "scene":
        # Scene prompts need component-ready format
        section = f"""{base_section}
*** RECENTLY CREATED/REFERENCED EVENT (CRITICAL) ***
  Title: {event.get('title', 'Unknown')}
"""
        if event.get('id'):
            section += f"  Event ID: {event['id']}\n"
        if event.get('date'):
            section += f"  Date: {event['date']}\n"

        section += "\n⚠️ IMPORTANT: When user refers to 'mi plan', 'my plan', 'my meeting', 'ese evento', etc.,\n"
        section += "they are referring to THIS event. Use the event_id above in meeting_detail component props:\n"
        section += f'{{"type": "meeting_detail", "props": {{"event_id": "{event.get("id", "")}"}}}}\n'
        section += "OR use meeting_search with the exact event title:\n"
        section += f'{{"type": "meeting_detail", "props": {{"meeting_search": "{event.get("title", "")}"}}}}\n\n'

        return section

    elif format_style == "execution":
        # Execution prompts need action-ready format
        section = f"""{base_section}
*** RECENTLY CREATED/REFERENCED EVENT (CRITICAL) ***
  Title: {event.get('title', 'Unknown')}
"""
        if event.get('id'):
            section += f"  Event ID: {event['id']}\n"
        if event.get('date'):
            section += f"  Date: {event['date']}\n"

        section += "\n⚠️ IMPORTANT: When user says 'my plan', 'my meeting', 'that event', 'ese evento':\n"
        section += "→ They are referring to THIS event above\n"
        section += f"→ Use event_id: {event.get('id', 'N/A')} for actions\n"
        section += "→ DO NOT ask 'which event?' - use this one!\n\n"

        return section

    return base_section


def inject_last_doc_context(
    base_section: str,
    conversation_context: Dict,
    format_style: str = "execution"
) -> str:
    """
    Add last document context to a prompt section consistently.

    Sprint 4.4.0 - GAP #5: Ensures all prompts handle last_doc the same way.

    Args:
        base_section: The existing conversation/context section
        conversation_context: Dict with potential "last_doc" key
        format_style: "execution" or "scene" - adjusts formatting

    Returns:
        Updated section with last doc injected (or original if no doc)
    """
    if not conversation_context.get("last_doc"):
        return base_section

    doc = conversation_context["last_doc"]

    if format_style == "scene":
        # Scene prompts need component-ready format
        section = f"""{base_section}
*** RECENTLY REFERENCED DOCUMENT (CRITICAL) ***
  Title: {doc.get('title', 'Unknown')}
"""
        if doc.get('id'):
            section += f"  Doc ID: {doc['id']}\n"
        if doc.get('url'):
            section += f"  URL: {doc['url']}\n"

        section += "\n⚠️ IMPORTANT: When user refers to 'that document', 'the doc', 'this document', 'ese documento':\n"
        section += "they are referring to THIS document. Use the doc_id above in component props:\n"
        if doc.get('id'):
            section += f'{{"type": "doc_summary", "props": {{"doc_id": "{doc.get("id", "")}"}}}}\n'
        if doc.get('url'):
            section += f'OR use doc_url: {{"props": {{"doc_url": "{doc.get("url", "")}"}}}}\n'
        section += "\nDO NOT ask 'which document?' - use the doc_id/url above!\n"
        section += "DO NOT use meeting_search if user is asking about THIS specific document.\n\n"

        return section

    elif format_style == "execution":
        # Execution prompts need action-ready format
        section = f"""{base_section}
*** RECENTLY REFERENCED DOCUMENT (CRITICAL) ***
  Title: {doc.get('title', 'Unknown')}
"""
        if doc.get('id'):
            section += f"  Doc ID: {doc['id']}\n"
        if doc.get('url'):
            section += f"  URL: {doc['url']}\n"

        section += "\n⚠️ IMPORTANT: When user says 'that document', 'the doc', 'ese documento':\n"
        section += "→ They are referring to THIS document above\n"
        if doc.get('id'):
            section += f"→ Use doc_id: {doc['id']} for actions\n"
        if doc.get('url'):
            section += f"→ Use doc_url: {doc['url']} for actions\n"
        section += "→ DO NOT ask 'which document?' - use this one!\n\n"

        return section

    return base_section


def format_conversation_history(
    conversation_history: str,
    format_style: str = "execution",
    include_context_notes: bool = True,
) -> str:
    """
    Format conversation history consistently across all prompts.

    Sprint 4.4.0 - GAP #3: Standardizes conversation history formatting to prevent
    drift between execution_prompts.py, scene_prompts.py, and base_prompt.py.

    Args:
        conversation_history: The conversation history text (pre-formatted)
        format_style: "execution", "reasoner", or "scene"
        include_context_notes: Whether to include guidance about using context

    Returns:
        Formatted history section ready to inject into prompt

    Example:
        >>> history = "User: Hello\\nAssistant: Hi there!"
        >>> formatted = format_conversation_history(history, "execution")
        >>> "PREVIOUS CONVERSATION CONTEXT" in formatted
        True
    """
    if not conversation_history:
        return ""

    if format_style == "scene":
        # Scene prompts may receive history as turns, but this function expects text
        # Scene-specific formatting is handled in scene_prompts.py directly
        return f"""
Recent conversation turns:
{conversation_history}

"""

    elif format_style == "execution":
        # Execution prompts need action context
        base = f"""
PREVIOUS CONVERSATION CONTEXT:
=============================
{conversation_history}
"""
        if include_context_notes:
            base += """
IMPORTANT: The conversation above includes information from web searches,
calendar queries, and previous responses. Use this context to inform your actions.

CRITICAL - RECENT EVENT/DOC REFERENCES (Sprint 4.4.0):
If the conversation mentions a recently created or viewed event/document:
- Look for "last_event" with event_id, title, date
- Look for "last_doc" with doc_id, title, url

When user says "my plan", "my meeting", "that event", "ese evento":
→ Check if last_event exists in conversation above
→ If yes: Use that event_id/title, DO NOT ask "which event?"
→ If no or too old (>5 min): Ask for clarification

When user says "that document", "the doc", "ese documento":
→ Check if last_doc exists in conversation above
→ If yes: Use that doc_id/url, DO NOT ask "which document?"
→ If no or too old (>5 min): Ask for clarification

This prevents asking users to re-specify things they just mentioned!
=============================

"""
        return base

    elif format_style == "reasoner":
        # Reasoner prompts need strategic context
        base = f"""
PREVIOUS CONVERSATION CONTEXT:
=============================
{conversation_history}
"""
        if include_context_notes:
            base += """
IMPORTANT: The conversation above includes information from web searches and
previous queries. Use this context to inform your response.
=============================

"""
        return base

    else:
        # Default fallback
        return f"""
CONVERSATION CONTEXT:
{conversation_history}

"""


# ---------------------------------------------------------------------------
# MULTILINGUAL CONFIRMATION HELPERS (Sprint 5.1.2)
# ---------------------------------------------------------------------------

def detect_user_language(text: str) -> str:
    """
    Detect if the user's text is Spanish or English.

    Uses word boundary matching for accurate detection.
    Returns "es" for Spanish, "en" for English (default).

    Args:
        text: The user's original text

    Returns:
        "es" or "en"
    """
    if not text:
        return "en"

    import re

    # Spanish words/phrases that are unlikely to appear in English
    # Using word boundaries to avoid false positives (e.g. "crea" in "create")
    spanish_patterns = [
        r"\bnecesito\b", r"\bcrear\b", r"\breunión\b", r"\breunion\b",
        r"\bevento\b", r"\bpara el\b", r"\bpara la\b",
        r"\bayuda\b", r"\bquiero\b", r"\bmuestra\b", r"\bcalendario\b",
        r"\bcrea\b", r"\bprograma\b", r"\bmañana\b", r"\bsemana\b",
        r"\bhoy\b", r"\bcancelar\b", r"\bcambiar\b", r"\bhora\b",
        r"\bpor favor\b", r"\bgracias\b", r"\bbuenos\b", r"\bhola\b",
        r"\bque viene\b", r"\bpróxima\b", r"\bproxima\b",
    ]
    text_lower = text.lower()
    spanish_count = sum(1 for pattern in spanish_patterns if re.search(pattern, text_lower))
    return "es" if spanish_count >= 1 else "en"


def get_confirmation_suffix(language: str, include_edit_hint: bool = True) -> str:
    """
    Get the confirmation prompt suffix in the appropriate language.

    DRY helper to avoid hardcoded English strings throughout the codebase.

    Args:
        language: "es" for Spanish, "en" for English
        include_edit_hint: Whether to include "or edit like..." hint

    Returns:
        Localized confirmation suffix string
    """
    if language == "es":
        if include_edit_hint:
            return "Di 'sí' para confirmar, 'no' para cancelar, o edita como 'cambiar hora a 8 pm'"
        return "Di 'sí' para confirmar o 'no' para cancelar."
    else:
        if include_edit_hint:
            return "Say 'yes' to confirm, 'no' to cancel, or edit like 'change time to 8 pm'"
        return "Say 'yes' to confirm or 'no' to cancel."


def get_create_event_prefix(language: str, is_all_day: bool = False) -> str:
    """
    Get the "Create event" prefix in the appropriate language.

    Args:
        language: "es" for Spanish, "en" for English
        is_all_day: Whether this is an all-day event

    Returns:
        Localized prefix like "Create" or "Crear evento de todo el día"
    """
    if language == "es":
        if is_all_day:
            return "Crear evento de todo el día"
        return "Crear"
    else:
        if is_all_day:
            return "Create all-day event"
        return "Create"
