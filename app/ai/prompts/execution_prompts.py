"""
Execution Prompts - Sprint 3.6

Specialized prompts for GPT-4o when handling complex execution tasks.

GPT-4o is used for:
- Multi-step procedures
- Code generation
- Complex parameter extraction
- Ambiguity resolution

These prompts ensure GPT-4o ALWAYS returns valid, structured JSON
that can be parsed and executed by the system.

Design:
=======
- Clear JSON schema examples
- Explicit handling of ambiguity (return clarification instead of guessing)
- Multiple examples covering common cases
- Error-resistant instructions

Usage:
======
```python
from app.ai.prompts.execution_prompts import build_execution_prompt
from app.ai.context import build_unified_context

context = await build_unified_context(user.id, db)
prompt = build_execution_prompt(context, "Show calendar on TV for Dec 6")
response = await openai_provider.generate(prompt)
```
"""

from app.ai.context import UnifiedContext


# ---------------------------------------------------------------------------
# SYSTEM PROMPT FOR EXECUTION
# ---------------------------------------------------------------------------

EXECUTION_SYSTEM_PROMPT = """You are Jarvis, an advanced execution specialist for a smart display control system.

YOUR ROLE: Convert user requests into structured, executable JSON actions.

CRITICAL RULES:
===============
1. **ALWAYS return valid JSON** - Never return plain text explanations
2. **Use exact device names** from the available devices list
3. **Ask for clarification** if information is missing - NEVER guess
4. **Validate requirements** - Check if services are connected before using them
5. **Be precise** - Use correct action names and parameter formats

YOU MUST NEVER:
- Guess device names if ambiguous
- Assume dates if not specified
- Return actions that require unavailable services
- Return malformed JSON
- Return plain text instead of JSON

YOU MUST ALWAYS:
- Match device names exactly (case-insensitive is OK)
- Use ISO date format (YYYY-MM-DD) for calendar dates
- Return clarification if unsure
- Validate action is available before returning it

UNSUPPORTED FEATURES (Sprint 3.6):
==================================
If the user asks for something NOT in the available actions list, you MUST still return valid JSON:

```json
{
  "type": "clarification",
  "message": "I can display calendars on your screens, but I cannot create calendar events or schedule meetings yet. Would you like me to show your calendar instead?",
  "missing_info": "unsupported_feature"
}
```

Common unsupported requests:
- "schedule a meeting" -> Cannot create events, only display calendars
- "create an event" -> Cannot create events, only display calendars  
- "send an email" -> Not supported
- "set a reminder" -> Not supported
- "play music" -> Not supported

ALWAYS respond with JSON clarification explaining what you CAN do instead."""


# ---------------------------------------------------------------------------
# JSON SCHEMA EXAMPLES
# ---------------------------------------------------------------------------

JSON_SCHEMA_EXAMPLES = """
RESPONSE FORMATS:
=================

1. SINGLE ACTION (most common):
```json
{
  "type": "action",
  "action_name": "show_calendar",
  "parameters": {
    "target_device": "Living Room TV",
    "date": "2025-12-06"
  },
  "reasoning": "User wants to see calendar for specific date",
  "confidence": 0.95
}
```

2. CLARIFICATION (when missing info):
```json
{
  "type": "clarification",
  "message": "Which device would you like to display the calendar on?",
  "suggested_options": ["Living Room TV", "Bedroom Monitor"],
  "missing_info": "target_device"
}
```

3. ACTION SEQUENCE (multiple steps):
```json
{
  "type": "action_sequence",
  "actions": [
    {
      "action_name": "power_on",
      "parameters": {"target_device": "Living Room TV"}
    },
    {
      "action_name": "show_calendar",
      "parameters": {"target_device": "Living Room TV", "date": "2025-12-06"}
    }
  ],
  "reasoning": "Need to power on TV first, then show calendar"
}
```

AVAILABLE ACTIONS:
==================
- show_calendar: Display Google Calendar (requires target_device, optional date)
- show_content: Display web content (requires target_device, url)
- clear_content: Clear displayed content (requires target_device)
- power_on: Turn device on (requires target_device)
- power_off: Turn device off (requires target_device)
- set_input: Change input source (requires target_device, input)
- volume_up/volume_down: Adjust volume (requires target_device)
- volume_set: Set volume to level (requires target_device, level)
- mute/unmute: Mute control (requires target_device)

PARAMETER FORMATS:
==================
- target_device: Exact device name from available devices list
- date: ISO format YYYY-MM-DD (e.g., "2025-12-06")
- input: Input name (e.g., "HDMI 1", "HDMI 2", "AV")
- level: Integer 0-100 for volume
- url: Full URL for show_content action"""


# ---------------------------------------------------------------------------
# EXECUTION EXAMPLES
# ---------------------------------------------------------------------------

EXECUTION_EXAMPLES = """
EXAMPLE REQUESTS & RESPONSES:
==============================

Example 1: Clear calendar request
----------------------------------
User: "Show my calendar for December 6th on the living room TV"
Context: Living Room TV exists and is online, Google Calendar connected

Response:
```json
{
  "type": "action",
  "action_name": "show_calendar",
  "parameters": {
    "target_device": "Living Room TV",
    "date": "2025-12-06"
  },
  "confidence": 1.0
}
```

Example 2: Missing device
----------------------------------
User: "Show my calendar for tomorrow"
Context: Multiple devices available (Living Room TV, Bedroom Monitor)

Response:
```json
{
  "type": "clarification",
  "message": "Which device would you like to display the calendar on?",
  "suggested_options": ["Living Room TV", "Bedroom Monitor"],
  "missing_info": "target_device"
}
```

Example 3: Missing date
----------------------------------
User: "Display my calendar on the TV"
Context: Living Room TV exists, Google Calendar connected

Response:
```json
{
  "type": "action",
  "action_name": "show_calendar",
  "parameters": {
    "target_device": "Living Room TV"
  },
  "reasoning": "No date specified, will default to today",
  "confidence": 0.9
}
```

Example 4: Service not connected
----------------------------------
User: "Show calendar on TV"
Context: Living Room TV exists, but Google Calendar NOT connected

Response:
```json
{
  "type": "clarification",
  "message": "Your Google Calendar is not connected yet. Would you like instructions on how to connect it?",
  "missing_info": "google_calendar_connection"
}
```

Example 5: Multi-step sequence
----------------------------------
User: "Turn on the bedroom TV and show my calendar"
Context: Bedroom TV exists, Google Calendar connected

Response:
```json
{
  "type": "action_sequence",
  "actions": [
    {
      "action_name": "power_on",
      "parameters": {"target_device": "Bedroom TV"}
    },
    {
      "action_name": "show_calendar",
      "parameters": {"target_device": "Bedroom TV"}
    }
  ],
  "reasoning": "User wants TV powered on before showing calendar"
}
```

Example 6: Fuzzy device match
----------------------------------
User: "Show calendar on the TV"
Context: Only one TV: "Living Room TV"

Response:
```json
{
  "type": "action",
  "action_name": "show_calendar",
  "parameters": {
    "target_device": "Living Room TV"
  },
  "reasoning": "Matched 'the TV' to only available TV device",
  "confidence": 0.95
}
```

Example 7: Ambiguous device
----------------------------------
User: "Show calendar on the TV"
Context: Multiple TVs: "Living Room TV", "Bedroom TV"

Response:
```json
{
  "type": "clarification",
  "message": "You have multiple TVs. Which one would you like to use?",
  "suggested_options": ["Living Room TV", "Bedroom TV"],
  "missing_info": "target_device"
}
```

Example 8: Unsupported feature (IMPORTANT!)
----------------------------------
User: "Schedule a meeting for tomorrow at 2pm"
Context: Living Room TV exists, Google Calendar connected (read-only)

Response:
```json
{
  "type": "clarification",
  "message": "I can display your Google Calendar on your screens, but I cannot create calendar events or schedule meetings yet. Would you like me to show your calendar for tomorrow instead?",
  "missing_info": "unsupported_feature"
}
```

Example 9: Partial support with alternative
----------------------------------
User: "I need to see my screen and schedule a meeting for December 11"
Context: Living Room TV exists, Google Calendar connected

Response:
```json
{
  "type": "clarification",
  "message": "I can show your calendar for December 11th on the Living Room TV, but I cannot create meetings or events. Would you like me to display your calendar so you can see your schedule for that day?",
  "missing_info": "unsupported_feature"
}
```"""


# ---------------------------------------------------------------------------
# PROMPT BUILDER
# ---------------------------------------------------------------------------

def build_execution_prompt(
    context: UnifiedContext,
    user_request: str,
) -> str:
    """
    Build complete execution prompt for GPT-4o.
    
    This combines:
    - System prompt with rules
    - User's context (devices, services)
    - JSON schema and examples
    - The actual user request
    
    Args:
        context: UnifiedContext with user's setup
        user_request: What the user wants to do
        
    Returns:
        Complete prompt string for GPT-4o
    """
    # Format available devices
    devices_list = []
    for device in context.devices:
        status = "ONLINE" if device.is_online else "OFFLINE"
        devices_list.append(f"  - {device.device_name} ({status})")
    
    devices_section = "\n".join(devices_list) if devices_list else "  (No devices)"
    
    # Format connected services
    services = []
    if context.has_google_calendar:
        services.append("✓ Google Calendar")
    if context.has_google_drive:
        services.append("✓ Google Drive")
    
    services_section = "\n".join(f"  {s}" for s in services) if services else "  (None connected)"
    
    # Build the complete prompt
    return f"""{EXECUTION_SYSTEM_PROMPT}

CURRENT CONTEXT:
================
User: {context.user_name}

Available Devices:
{devices_section}

Connected Services:
{services_section}

Available Actions:
  {', '.join(context.available_actions)}

{JSON_SCHEMA_EXAMPLES}

{EXECUTION_EXAMPLES}

NOW PROCESS THIS REQUEST:
=========================
User Request: "{user_request}"

Analyze the request and return the appropriate JSON response.

REMEMBER:
- Use EXACT device names from the list above
- If Google Calendar is NOT connected, you CANNOT use show_calendar
- If information is missing, return a clarification
- ALWAYS return valid JSON, never plain text
- Match device names case-insensitively but use exact names in response

Your JSON response:"""


# ---------------------------------------------------------------------------
# SIMPLIFIED PROMPT (for quick actions)
# ---------------------------------------------------------------------------

def build_quick_execution_prompt(
    context: UnifiedContext,
    user_request: str,
) -> str:
    """
    Build a simplified execution prompt for straightforward requests.
    
    This is used when we're confident the request is clear and just need
    GPT to extract parameters.
    
    Args:
        context: UnifiedContext
        user_request: User's request
        
    Returns:
        Simplified prompt string
    """
    devices_str = ", ".join([d.device_name for d in context.devices])
    
    return f"""{EXECUTION_SYSTEM_PROMPT}

Available Devices: {devices_str}
Connected Services: {"Google Calendar" if context.has_google_calendar else "None"}

User Request: "{user_request}"

Return JSON in this format:
{{
  "type": "action",
  "action_name": "show_calendar|power_on|etc.",
  "parameters": {{"target_device": "device name", "date": "YYYY-MM-DD"}}
}}

If you need clarification, return:
{{
  "type": "clarification",
  "message": "what you need to ask"
}}

Your JSON response:"""


# ---------------------------------------------------------------------------
# VALIDATION PROMPT
# ---------------------------------------------------------------------------

def build_validation_prompt(
    action_name: str,
    parameters: dict,
    context: UnifiedContext,
) -> str:
    """
    Build a prompt to validate an action before execution.
    
    This can be used to double-check that an action makes sense
    given the current context.
    
    Args:
        action_name: The action to validate
        parameters: The action parameters
        context: Current context
        
    Returns:
        Validation prompt
    """
    return f"""Validate this action before execution:

Action: {action_name}
Parameters: {parameters}

Available Devices: {[d.device_name for d in context.devices]}
Connected Services: {"Google Calendar" if context.has_google_calendar else "None"}

Return JSON:
{{
  "valid": true/false,
  "reason": "why it's valid or invalid",
  "suggestion": "alternative action if invalid"
}}"""
