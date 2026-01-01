"""
Calendar Search Prompts - LLM prompts for semantic calendar event matching.

Sprint 3.9: Smart Calendar Search

These prompts enable semantic matching of user queries to calendar events,
handling:
- Typos: "birday" -> "birthday"
- Translations: "birthday" <-> "cumpleaños" <-> "anniversaire"
- Synonyms: "bday", "appt", "mtg"
- Fuzzy matching: partial matches, abbreviations

The LLM acts as an intelligent filter, understanding user intent
even when the exact words don't match.
"""

# ---------------------------------------------------------------------------
# SEMANTIC CALENDAR MATCHER PROMPT
# ---------------------------------------------------------------------------

CALENDAR_SEMANTIC_MATCHER_PROMPT = """You are a calendar event matcher for a smart home assistant.

Your task: Match a user's search query to calendar events, handling typos, translations, and synonyms.

USER QUERY: "{query}"

CALENDAR EVENTS:
{events_list}

MATCHING RULES:

1. TYPO TOLERANCE:
   Recognize and correct common typos. You know what words look like when misspelled.
   Example: "birday" → "birthday", "meting" → "meeting"

2. CROSS-LANGUAGE MATCHING (English ↔ Spanish ↔ French ↔ German ↔ Portuguese):
   Match semantically across languages. You understand that words like birthday/cumpleaños/anniversaire
   are translations of the same concept. Apply this knowledge to all common calendar terms.

3. SYNONYM HANDLING:
   Recognize common abbreviations and informal terms: bday, appt, mtg, doc, xmas, b-day, dr, apt.
   Match them to their full forms in any language.

4. PARTIAL MATCHING:
   Match partial words to full event titles. "mom" matches "Cumpleaños mamá", "team" matches "Team meeting".

5. CONTEXT AWARENESS:
   Understand possessives like "my birthday" and context words like "work" → work-related events.

RESPONSE FORMAT:
Return ONLY valid JSON with this structure:

{{
  "matched_events": [
    {{
      "event_title": "exact title from the event list",
      "event_date": "the event's date",
      "match_reason": "brief explanation why this matches",
      "confidence": 0.95
    }}
  ],
  "no_match_found": false,
  "corrected_query": "what the user probably meant"
}}

CONFIDENCE LEVELS:
- 0.95-1.00: Exact or near-exact match
- 0.85-0.94: Translation match (birthday = cumpleaños)
- 0.75-0.84: Synonym match (bday = birthday)
- 0.65-0.74: Typo correction match (birday = birthday)
- 0.50-0.64: Partial/fuzzy match (mom matches "mamá's birthday")
- Below 0.50: Don't include - too uncertain

EXAMPLES (showing JSON format and key cases):

Query: "birday"
Events: ["Cumpleaños de Victor - Dec 15", "Team Meeting - Dec 12"]
Response: {{
  "matched_events": [
    {{"event_title": "Cumpleaños de Victor", "event_date": "Dec 15", "match_reason": "typo + translation", "confidence": 0.88}}
  ],
  "no_match_found": false,
  "corrected_query": "birthday"
}}

Query: "doctor"
Events: ["Cumpleaños mamá - Dec 15", "Team Meeting - Dec 12"]
Response: {{
  "matched_events": [],
  "no_match_found": true,
  "corrected_query": "doctor"
}}

CRITICAL RULES:
- Return EXACT event titles from the provided list
- Only include events with confidence >= 0.50
- Set no_match_found: true if matched_events is empty
- Always provide corrected_query (what the user meant)
- Don't match unrelated events just to have results
- Be conservative - it's better to miss a weak match than include a wrong one

Now analyze the user query and match to the provided events."""


# ---------------------------------------------------------------------------
# FORMAT HELPERS
# ---------------------------------------------------------------------------

def format_events_for_prompt(events: list) -> str:
    """
    Format calendar events as a numbered list for the LLM prompt.
    
    Args:
        events: List of CalendarEvent objects
        
    Returns:
        Formatted string with event titles and dates
    """
    if not events:
        return "(No events found)"
    
    lines = []
    for i, event in enumerate(events, 1):
        title = event.get_display_title() if hasattr(event, 'get_display_title') else str(event.get('summary', 'Untitled'))
        date_str = event.get_time_display() if hasattr(event, 'get_time_display') else str(event.get('start', ''))
        lines.append(f"{i}. {title} - {date_str}")
    
    return "\n".join(lines)


def build_matcher_prompt(query: str, events: list) -> str:
    """
    Build the complete semantic matcher prompt.
    
    Args:
        query: User's search query
        events: List of CalendarEvent objects
        
    Returns:
        Formatted prompt string
    """
    events_list = format_events_for_prompt(events)
    return CALENDAR_SEMANTIC_MATCHER_PROMPT.format(
        query=query,
        events_list=events_list,
    )
