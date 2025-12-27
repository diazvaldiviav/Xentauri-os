"""
Document Intelligence Prompts - LLM prompts for document analysis.

Sprint 3.9: Google Docs Intelligence

These prompts enable intelligent document analysis including:
- Summarization (short and detailed)
- Key point extraction
- Action item identification
- Content classification

The prompts are optimized for both simple docs (Gemini) and
complex docs (Claude).
"""

# ---------------------------------------------------------------------------
# DOCUMENT SUMMARY PROMPT
# ---------------------------------------------------------------------------

DOC_SUMMARY_PROMPT = """You are a document analysis assistant for a smart home system.

CRITICAL: Respond in the SAME LANGUAGE as the user's request.

Analyze the following document and provide a clear, concise summary.

DOCUMENT TITLE: {title}

DOCUMENT CONTENT:
{content}

TASK: {task}

RESPONSE FORMAT:
Provide a natural, conversational response that directly answers what the user wants.
Be concise but thorough. If the document is short, your summary should be proportionally shorter.

GUIDELINES:
- Focus on the most important information
- Use clear, simple language
- If the document has action items or deadlines, highlight them
- If asked about specific topics, focus on those
- Keep your response under 500 words unless the document is very detailed"""


# ---------------------------------------------------------------------------
# KEY POINTS EXTRACTION PROMPT
# ---------------------------------------------------------------------------

DOC_KEY_POINTS_PROMPT = """You are a document analysis assistant.

CRITICAL: Respond in the SAME LANGUAGE as the user's request.

Extract the key points from the following document.

DOCUMENT TITLE: {title}

DOCUMENT CONTENT:
{content}

RESPONSE FORMAT:
Return a JSON object with this structure:

{{
  "key_points": [
    "First main point or takeaway",
    "Second main point or takeaway",
    "..."
  ],
  "action_items": [
    {{"task": "What needs to be done", "deadline": "If mentioned, else null", "owner": "If mentioned, else null"}}
  ],
  "mentions": [
    "Important names, dates, or references mentioned"
  ],
  "document_type": "meeting_notes|agenda|proposal|report|general"
}}

GUIDELINES:
- Extract 3-7 key points depending on document length
- Only include action items if they're explicitly stated
- Don't invent information not in the document
- Be concise with each point"""


# ---------------------------------------------------------------------------
# MEETING DOCUMENT SUMMARY PROMPT
# ---------------------------------------------------------------------------

DOC_MEETING_SUMMARY_PROMPT = """You are a smart assistant helping a user understand their meeting document.

CRITICAL: Respond in the SAME LANGUAGE as the user's request.

The user has a calendar event and wants to know about the linked document.

MEETING TITLE: {meeting_title}
MEETING TIME: {meeting_time}

LINKED DOCUMENT TITLE: {doc_title}

DOCUMENT CONTENT:
{doc_content}

USER QUESTION: {user_question}

Provide a helpful, conversational response that:
1. Answers their question directly
2. Highlights any action items or deadlines
3. Notes anything they should prepare before the meeting
4. Keeps the response concise but complete

If the document is an agenda, highlight the key topics.
If it's meeting notes, summarize the important decisions and action items.
If it's a proposal or document to review, summarize the key points."""


# ---------------------------------------------------------------------------
# DOCUMENT COMPLEXITY CHECK PROMPT
# ---------------------------------------------------------------------------

DOC_COMPLEXITY_CHECK_PROMPT = """Analyze this document and determine its complexity.

DOCUMENT TITLE: {title}
CHARACTER COUNT: {char_count}
ESTIMATED HEADERS: {header_count}

FIRST 1000 CHARACTERS:
{preview}

Return JSON:
{{
  "is_complex": true|false,
  "reason": "Brief explanation",
  "recommended_model": "gemini|claude",
  "estimated_analysis_time": "fast|medium|slow"
}}

COMPLEXITY CRITERIA:
- Complex = >5000 chars OR >10 headers OR technical/legal content
- Simple = Short, straightforward content"""


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def build_summary_prompt(
    title: str,
    content: str,
    task: str = "Provide a brief summary of this document."
) -> str:
    """
    Build a document summary prompt.
    
    Args:
        title: Document title
        content: Document text content
        task: Specific task or question about the document
    
    Returns:
        Formatted prompt string
    """
    return DOC_SUMMARY_PROMPT.format(
        title=title,
        content=content,
        task=task,
    )


def build_key_points_prompt(title: str, content: str) -> str:
    """
    Build a key points extraction prompt.
    
    Args:
        title: Document title
        content: Document text content
    
    Returns:
        Formatted prompt string
    """
    return DOC_KEY_POINTS_PROMPT.format(
        title=title,
        content=content,
    )


def build_meeting_doc_prompt(
    meeting_title: str,
    meeting_time: str,
    doc_title: str,
    doc_content: str,
    user_question: str = "What's in this document?",
) -> str:
    """
    Build a meeting document summary prompt.
    
    Args:
        meeting_title: Title of the calendar event
        meeting_time: Time of the meeting
        doc_title: Title of the linked document
        doc_content: Document text content
        user_question: The user's specific question
    
    Returns:
        Formatted prompt string
    """
    return DOC_MEETING_SUMMARY_PROMPT.format(
        meeting_title=meeting_title,
        meeting_time=meeting_time,
        doc_title=doc_title,
        doc_content=doc_content,
        user_question=user_question,
    )


def truncate_content(content: str, max_chars: int = 50000) -> str:
    """
    Truncate content to fit within LLM context limits.
    
    Args:
        content: Full document content
        max_chars: Maximum characters to include
    
    Returns:
        Truncated content with note if truncated
    """
    if len(content) <= max_chars:
        return content
    
    truncated = content[:max_chars]
    return f"{truncated}\n\n[... Document truncated. Showing first {max_chars:,} characters of {len(content):,} total ...]"


# ---------------------------------------------------------------------------
# MEETING EXTRACTION PROMPT (Sprint 3.9)
# ---------------------------------------------------------------------------

MEETING_EXTRACTION_PROMPT = """Extract meeting details from this document to create a calendar event.

DOCUMENT TITLE: {title}

DOCUMENT CONTENT:
{content}

TODAY'S DATE: {today}

Extract the following information. If not found, use null.
Return ONLY valid JSON:

{{
  "event_title": "Meeting title (use doc title if not specified)",
  "event_date": "YYYY-MM-DD format",
  "event_time": "HH:MM 24-hour format",
  "duration_minutes": 60,
  "location": "Location or null",
  "attendees": ["email1@example.com"],
  "description": "Brief description from doc content"
}}

IMPORTANT:
- For relative dates like "next Monday", "tomorrow", calculate from today: {today}
- Default duration is 60 minutes if not specified
- Include key agenda items in description (max 200 chars)
- For attendees, only include actual email addresses if present
- If no date/time found, set them to null"""


def build_meeting_extraction_prompt(
    title: str,
    content: str,
    today: str = None,
) -> str:
    """
    Build prompt to extract meeting details from document content.
    
    Args:
        title: Document title
        content: Document text content
        today: Today's date in YYYY-MM-DD format (for relative date parsing)
    
    Returns:
        Formatted prompt string
    """
    from datetime import datetime
    
    if today is None:
        today = datetime.now().strftime('%Y-%m-%d')
    
    return MEETING_EXTRACTION_PROMPT.format(
        title=title,
        content=content,
        today=today,
    )
