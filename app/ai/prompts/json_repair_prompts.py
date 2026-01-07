"""
JSON Repair Prompts - Prompt templates for diagnosing and repairing malformed JSON.

Sprint 5.3: These prompts enable intelligent JSON repair when LLMs return
malformed JSON (unescaped quotes, trailing commas, etc.).

Architecture:
=============
1. DIAGNOSE_JSON_PROMPT - Used by Gemini (fast, cheap) to identify the issue
2. REPAIR_JSON_PROMPT - Used by the original provider to fix its own output

Design Philosophy:
==================
- Diagnosis is fast and cheap (Gemini Flash)
- Repair is done by the original model (knows its output style)
- Prompts are minimal to reduce latency
"""


# ---------------------------------------------------------------------------
# DIAGNOSIS PROMPT (For Gemini - fast, cheap)
# ---------------------------------------------------------------------------

DIAGNOSE_JSON_PROMPT = """You are a JSON syntax expert. Analyze this malformed JSON and identify the error in 1-2 sentences.

MALFORMED JSON:
```
{json_content}
```

PARSER ERROR:
{error_message}

Respond with ONLY a brief diagnosis (1-2 sentences) explaining what's wrong. Do NOT provide the fixed JSON.

Examples of good diagnoses:
- "Missing closing brace at end of object."
- "Unescaped double quote in string value at position 45."
- "Trailing comma after last array element."
- "Invalid escape sequence '\\x' in string."

Your diagnosis:"""


# ---------------------------------------------------------------------------
# REPAIR PROMPT (For original provider to fix its own output)
# ---------------------------------------------------------------------------

REPAIR_JSON_PROMPT = """You previously generated JSON that had a syntax error. Please fix it.

ORIGINAL (MALFORMED) JSON:
```
{json_content}
```

DIAGNOSIS OF ERROR:
{diagnosis}

ORIGINAL REQUEST CONTEXT:
{original_context}

Instructions:
1. Fix ONLY the syntax error identified in the diagnosis
2. Preserve ALL original content and structure
3. Return ONLY the corrected JSON - no explanation, no markdown code blocks
4. Ensure proper escaping of special characters
5. Validate all brackets, braces, and commas

Corrected JSON:"""


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def build_diagnosis_prompt(json_content: str, error_message: str) -> str:
    """
    Build the diagnosis prompt for Gemini.
    
    Args:
        json_content: The malformed JSON string
        error_message: The JSONDecodeError message
        
    Returns:
        Complete prompt for diagnosis
    """
    # Truncate very long JSON to avoid token limits
    truncated_json = json_content
    if len(json_content) > 2000:
        truncated_json = json_content[:1000] + "\n... [truncated] ...\n" + json_content[-500:]
    
    return DIAGNOSE_JSON_PROMPT.format(
        json_content=truncated_json,
        error_message=error_message,
    )


def build_repair_prompt(
    json_content: str,
    diagnosis: str,
    original_prompt: str,
    original_system_prompt: str = None,
) -> str:
    """
    Build the repair prompt for the original provider.
    
    Args:
        json_content: The malformed JSON string
        diagnosis: The diagnosis from Gemini
        original_prompt: The original user prompt that generated this JSON
        original_system_prompt: The original system prompt (optional)
        
    Returns:
        Complete prompt for repair
    """
    # Build context from original request
    context_parts = []
    if original_system_prompt:
        # Truncate system prompt to save tokens
        sys_truncated = original_system_prompt[:300] + "..." if len(original_system_prompt) > 300 else original_system_prompt
        context_parts.append(f"System: {sys_truncated}")
    if original_prompt:
        # Truncate user prompt to save tokens
        user_truncated = original_prompt[:300] + "..." if len(original_prompt) > 300 else original_prompt
        context_parts.append(f"User: {user_truncated}")
    
    original_context = "\n".join(context_parts) if context_parts else "(Context not available)"
    
    return REPAIR_JSON_PROMPT.format(
        json_content=json_content,
        diagnosis=diagnosis,
        original_context=original_context,
    )
