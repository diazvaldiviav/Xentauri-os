"""
Base Prompt Templates - Sprint 3.6

Shared prompt templates used across all AI providers (Gemini, GPT, Claude).

This ensures consistent context is provided to all models about:
- User information
- Available devices and capabilities
- Connected services (Google Calendar, etc.)
- Available actions

Design Principles:
==================
1. **DRY**: Single source of truth for base context
2. **Role-specific**: Base prompt can be extended for Router/Executor/Reasoner
3. **Consistent**: All models see the same context format
4. **Concise**: Only include what models need to know

Usage:
======
```python
from app.ai.prompts.base_prompt import build_router_prompt
from app.ai.context import build_unified_context

context = await build_unified_context(user.id, db)
prompt = build_router_prompt(context, "Show calendar on TV")
response = await gemini_provider.generate(prompt)
```
"""

from typing import Optional
from app.ai.context import UnifiedContext


# ---------------------------------------------------------------------------
# BASE SYSTEM PROMPT TEMPLATE
# ---------------------------------------------------------------------------

def build_base_system_prompt(context: UnifiedContext) -> str:
    """
    Build the base system prompt with full context.
    
    This is the foundation that all role-specific prompts build upon.
    It gives the AI model complete awareness of:
    - Who the user is
    - What devices they have
    - What services are connected
    - What actions are possible
    
    Args:
        context: UnifiedContext with all user/device/service info
        
    Returns:
        Base system prompt string
    """
    # Format device list
    device_list = []
    for device in context.devices:
        status = "🟢 ONLINE" if device.is_online else "🔴 OFFLINE"
        device_list.append(
            f"  • {device.device_name} ({status}) - Type: {device.device_type or 'display'}"
        )
    
    devices_section = "\n".join(device_list) if device_list else "  (No devices configured)"
    
    # Format connected services
    services = []
    if context.has_google_calendar:
        services.append("✓ Google Calendar (can display calendar on screens)")
    if context.has_google_drive:
        services.append("✓ Google Drive")
    
    services_section = "\n".join(f"  {s}" for s in services) if services else "  (No external services connected)"
    
    # Format available actions
    actions_section = ", ".join(context.available_actions)
    
    # Build the prompt
    return f"""You are Jarvis, an intelligent assistant for controlling display devices (TVs, monitors, screens).

CRITICAL LANGUAGE RULE:
=======================
ALWAYS respond in the SAME LANGUAGE the user is speaking.
- Spanish input → Spanish output
- English input → English output
- French input → French output

CURRENT USER:
  Name: {context.user_name}
  Email: {context.user_email}

AVAILABLE DEVICES ({context.device_count} total, {len(context.online_devices)} online):
{devices_section}

CONNECTED SERVICES:
{services_section}

AVAILABLE ACTIONS:
  {actions_section}

CAPABILITIES SUMMARY:
  {context.capabilities_summary}

IMPORTANT GUIDELINES:
1. ALWAYS respond in the user's language
2. You can only control devices that are ONLINE (🟢)
3. For calendar display, you MUST have Google Calendar connected
4. Always specify which device to target
5. Be helpful and concise in your responses
6. If the user asks for something you can't do, explain why clearly"""


# ---------------------------------------------------------------------------
# ROUTER PROMPT (Gemini Flash)
# ---------------------------------------------------------------------------

def build_router_prompt(context: UnifiedContext, user_input: str) -> str:
    """
    Build prompt for the AI Router (Gemini Flash).
    
    The router analyzes requests and decides routing:
    - SIMPLE → Handle directly with intent parsing
    - COMPLEX_EXECUTION → Route to GPT-4o
    - COMPLEX_REASONING → Route to Claude
    
    Args:
        context: UnifiedContext
        user_input: The user's natural language request
        
    Returns:
        Complete prompt for the router
    """
    base = build_base_system_prompt(context)
    
    return f"""{base}

YOUR ROLE: Request Analyzer & Router

Your job is to analyze the user's request and decide how to handle it.

ROUTING RULES:
1. **SIMPLE** - Handle directly:
   - Device commands: "Turn on TV", "Switch to HDMI 2"
   - Status queries: "Is the TV on?"
   - List devices: "What devices do I have?"
   - Greetings, thanks, simple questions

2. **COMPLEX_EXECUTION** - Route to GPT-4o:
   - Code generation: "Write a script to..."
   - API integration: "Search for..."
   - Multi-step procedures: "Calculate and then..."

3. **COMPLEX_REASONING** - Route to Claude:
   - Strategic planning: "Plan a movie night setup"
   - Analysis: "Why might my TV keep disconnecting?"
   - Recommendations: "What's the best way to organize my devices?"

Analyze this request and decide routing:

USER REQUEST: "{user_input}"

Return your analysis as JSON:
{{
  "complexity": "simple|complex_execution|complex_reasoning",
  "reasoning": "Why you chose this routing",
  "confidence": 0.0-1.0,
  "is_device_command": true/false,
  "target_device": "device name if applicable"
}}"""


# ---------------------------------------------------------------------------
# EXECUTOR PROMPT (GPT-4o)
# ---------------------------------------------------------------------------

def build_executor_prompt(
    context: UnifiedContext,
    task_description: str,
    include_action_schema: bool = True,
) -> str:
    """
    Build prompt for the Executor (GPT-4o).
    
    The executor handles complex execution tasks and returns structured
    JSON actions that can be executed by the system.
    
    Args:
        context: UnifiedContext
        task_description: What the user wants to do
        include_action_schema: Whether to include JSON schema (for structured responses)
        
    Returns:
        Complete prompt for GPT-4o
    """
    base = build_base_system_prompt(context)
    
    schema_section = ""
    if include_action_schema:
        schema_section = """

RESPONSE FORMAT:
You MUST respond with valid JSON in one of these formats:

1. **Action Response** (when you can execute something):
{
  "type": "action",
  "action_name": "show_calendar|show_content|power_on|power_off|set_input|etc.",
  "parameters": {
    "target_device": "device name",
    "date": "YYYY-MM-DD (for calendar)",
    "input": "HDMI 1 (for set_input)",
    "level": 50 (for volume_set)
  }
}

2. **Clarification Response** (when you need more info):
{
  "type": "clarification",
  "message": "What you need to ask the user",
  "suggested_options": ["option 1", "option 2"] // optional
}

3. **Multiple Actions** (for sequences):
{
  "type": "action_sequence",
  "actions": [
    {"action_name": "...", "parameters": {...}},
    {"action_name": "...", "parameters": {...}}
  ]
}

CRITICAL RULES:
- ALWAYS return valid JSON
- Use exact device names from the device list above
- For calendar actions, ONLY use if Google Calendar is connected
- If missing required info (device, date), return clarification
- Match action names to the available actions list above"""
    
    return f"""{base}

YOUR ROLE: Execution Specialist

You handle complex tasks that require:
- Step-by-step execution
- Code generation
- Tool usage
- Structured planning

USER TASK: "{task_description}"
{schema_section}

Analyze the task and return the appropriate JSON response."""


# ---------------------------------------------------------------------------
# REASONER PROMPT (Claude)
# ---------------------------------------------------------------------------

def build_reasoner_prompt(
    context: UnifiedContext,
    question: str,
) -> str:
    """
    Build prompt for the Reasoner (Claude).
    
    The reasoner handles complex reasoning tasks that require:
    - Deep analysis
    - Strategic planning
    - Recommendations
    
    Args:
        context: UnifiedContext
        question: The user's question or problem
        
    Returns:
        Complete prompt for Claude
    """
    base = build_base_system_prompt(context)
    
    return f"""{base}

YOUR ROLE: Strategic Advisor & Analyst

You handle complex reasoning tasks that require:
- Deep analysis and understanding
- Strategic planning and recommendations
- Explaining complex concepts
- Problem diagnosis

USER QUESTION: "{question}"

Provide a thoughtful, well-reasoned response. Consider:
1. The user's current setup (devices, services)
2. Best practices and common patterns
3. Potential issues and solutions
4. Clear explanations and recommendations

Be thorough but concise. Focus on actionable insights."""


# ---------------------------------------------------------------------------
# INTENT PARSING PROMPT (Gemini Flash)
# ---------------------------------------------------------------------------

def build_intent_prompt(
    context: UnifiedContext,
    user_input: str,
) -> str:
    """
    Build prompt for intent parsing.
    
    This is used by the IntentParser to extract structured intents
    from natural language.
    
    Args:
        context: UnifiedContext
        user_input: The user's request
        
    Returns:
        Prompt for intent extraction
    """
    base = build_base_system_prompt(context)
    
    # Format device names for fuzzy matching
    device_names = [d.device_name for d in context.devices]
    device_names_str = ", ".join(device_names) if device_names else "(none)"
    
    return f"""{base}

YOUR ROLE: Intent Extractor

Extract the user's intent from their natural language request.

USER REQUEST: "{user_input}"

Available device names: {device_names_str}

Return JSON in this format:
{{
  "intent_type": "device_command|device_query|system_query|conversation",
  "confidence": 0.0-1.0,
  "reasoning": "Why you classified it this way",
  
  // For device_command:
  "device_name": "exact or fuzzy match from available devices",
  "action": "power_on|power_off|set_input|show_calendar|etc.",
  "parameters": {{"input": "HDMI 1", "date": "2025-12-06"}},
  
  // For device_query:
  "device_name": "device name",
  "action": "status|capabilities|is_online",
  
  // For system_query:
  "action": "list_devices|help",
  
  // For conversation:
  "action": "greeting|thanks|question"
}}

Match device names flexibly (e.g., "TV" could match "Living Room TV").
Use exact action names from the available actions list."""


# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def format_context_for_logging(context: UnifiedContext) -> str:
    """
    Format context for logging/debugging.
    
    Returns a concise summary suitable for logs.
    """
    return (
        f"User: {context.user_name} | "
        f"Devices: {context.device_count} ({len(context.online_devices)} online) | "
        f"Calendar: {'✓' if context.has_google_calendar else '✗'} | "
        f"Actions: {len(context.available_actions)}"
    )


def get_context_hash(context: UnifiedContext) -> str:
    """
    Generate a hash of the context for caching.
    
    This can be used to determine if context has changed
    and prompts need to be rebuilt.
    """
    import hashlib
    import json
    
    # Create a stable representation
    context_data = {
        "user_id": str(context.user_id),
        "device_count": context.device_count,
        "online_count": len(context.online_devices),
        "has_calendar": context.has_google_calendar,
        "actions": sorted(context.available_actions),
    }
    
    # Hash it
    context_str = json.dumps(context_data, sort_keys=True)
    return hashlib.md5(context_str.encode()).hexdigest()
