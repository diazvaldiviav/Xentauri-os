"""
Scene Generation Prompts - Templates for Claude scene generation.

Sprint 4.0: These prompts are used when users request custom layouts
that don't match any default scene template.

Claude receives:
1. System prompt with available components and schema
2. Generation prompt with user request and hints
3. Returns valid Scene Graph JSON

Usage:
======
    from app.ai.prompts.scene_prompts import (
        SCENE_SYSTEM_PROMPT,
        build_scene_generation_prompt,
    )

    response = await anthropic_provider.generate_json(
        prompt=build_scene_generation_prompt(user_request, hints, info_type),
        system_prompt=SCENE_SYSTEM_PROMPT.format(
            components=component_registry.to_prompt_context(),
            schema=SCENE_GRAPH_SCHEMA,
        ),
    )
"""

# Sprint 4.4.0 - GAP #2: Import shared helpers for consistent context injection
from app.ai.prompts.helpers import (
    inject_generated_content_context,
    inject_last_event_context,
    inject_last_doc_context,
)

# ---------------------------------------------------------------------------
# SCENE GRAPH SCHEMA (for Claude reference)
# ---------------------------------------------------------------------------

SCENE_GRAPH_SCHEMA = """
{
    "scene_id": "descriptive-id-001",
    "version": "1.1",
    "target_devices": ["device-uuid-1"],
    "layout": {
        "intent": "fullscreen | two_column | three_column | sidebar | dashboard | overlay | stack",
        "engine": "grid | flex | absolute",
        "columns": 1-12 (for grid),
        "rows": 1-12 (for grid),
        "gap": "16px | 24px"
    },
    "components": [
        {
            "id": "unique_component_id",
            "type": "component_type_from_registry",
            "priority": "primary | secondary | tertiary",
            "position": {
                "grid_column": "1" or "1 / 3" (for grid),
                "grid_row": "1" (for grid)
            },
            "style": {
                "background": "#1a1a2e (REQUIRED - never null)",
                "text_color": "#ffffff (REQUIRED)",
                "border_radius": "12px | 16px (REQUIRED)",
                "padding": "20px | 24px (REQUIRED)"
            },
            "props": {},
            "data": {}
        }
    ],
    "global_style": {
        "background": "#0f0f23 (REQUIRED)",
        "font_family": "Inter (REQUIRED)",
        "text_color": "#ffffff (REQUIRED)",
        "accent_color": "#7b2cbf (REQUIRED)"
    },
    "animation_hints": [
        {
            "target": "element selector or description (e.g., 'planets', 'electrons', 'data-flow')",
            "type": "orbit | rotate | flow | pulse | scale | bounce",
            "duration_range": "fast: 2-5s | medium: 5-15s | slow: 15-60s",
            "description": "What motion represents and why it helps understanding"
        }
    ],
    "scroll_hints": [
        {
            "target": "component id or content area description",
            "type": "vertical | horizontal | snap-carousel | paginated",
            "reason": "Why scrolling is needed (e.g., 'list exceeds viewport', 'multiple sections')"
        }
    ],
    "metadata": {
        "created_at": "ISO datetime",
        "refresh_seconds": 60 | 300,
        "user_request": "original request",
        "generated_by": "claude_sonnet"
    }
}
"""


# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SCENE_SYSTEM_PROMPT = """You are a layout designer for smart TV displays.
Generate Scene Graph JSON that describes visual layouts for Raspberry Pi screens.

CRITICAL RULES:
1. Output ONLY valid JSON - no explanations, no markdown, no code blocks
2. Use only components from the available list below
3. The "primary" component should be the main user focus
4. NEVER return null for style fields - ALWAYS apply styling to every component
5. Leave the "data" field empty for all components - the service will populate it
6. ESCAPE ALL STRING CONTENT PROPERLY - use \\" for quotes inside strings, \\n for newlines
7. NEVER create unterminated strings - always close all quotes properly
8. If content is too long, truncate it cleanly rather than breaking JSON syntax

LAYOUT INTENT SELECTION:
- "fullscreen" → single component, full screen
- "two_column" → equal 50/50 split (2-column grid)
- "three_column" → equal 33/33/33 split (3-column grid)
- "sidebar" → main content 75% + sidebar 25% (4-column grid: 3+1)
- "dashboard" → multi-widget grid (2x2, 3x2, etc.)
- "overlay" → layered components with absolute positioning
- "stack" → vertical stack using flex column

SPATIAL LAYOUT MAPPING:
=======================
Spatial positions = SEPARATE COMPONENTS. Map positions to layouts:
- Two positions (horizontal) → two_column with grid_column="1", "2"
- Two positions (vertical) → stack with flex layout  
- Three positions → three_column with grid_column="1", "2", "3"
- Four+ positions → dashboard grid

NEVER create fullscreen when user specifies MULTIPLE positions!

DESIGN SYSTEM - ALWAYS APPLY THESE DEFAULTS:
When user doesn't specify styling, use these values:

Colors (Dark Theme):
- Scene background: "#0f0f23" (darkest)
- Primary component background: "#1a1a2e"
- Secondary component background: "#16213e"
- Tertiary/accent background: "#0f3460"
- Text color: "#ffffff"
- Accent color: "#7b2cbf" (purple) or "#4361ee" (blue)

Spacing & Sizing:
- Layout gap: "16px" (compact) or "24px" (spacious)
- Component padding: "20px" or "24px"
- Border radius: "12px" (cards) or "16px" (large panels)
- Font family: "Inter" (clean, readable from distance)

Component Styling Rules:
- Primary components: larger padding (24px), prominent background (#1a1a2e)
- Secondary components: standard padding (20px), subtle background (#16213e)
- Timers/Countdowns: use accent color for emphasis
- Meeting details: include subtle border or shadow for separation

POSITIONING GUIDELINES:
- Two-column: grid with columns=2, rows=1, each component in grid_column="1" or "2"
- Sidebar: grid with columns=4, main spans "1 / 4", sidebar is "4"
- Dashboard: grid with columns=2, rows=2, gap="16px"
- Fullscreen: flex engine with flex=1
- Corner overlays: absolute positioning with top/right/bottom/left

ANIMATION HINTS (add ONLY when motion is essential to understand the concept):
=============================================================================
Include "animation_hints" array when the topic involves inherent movement or process flow.
Do NOT add animations for static content (facts, definitions, lists, schedules).

RULES for when to include animation_hints:

1. ORBITAL/CIRCULAR MOTION → type: "orbit"
   - Bodies moving around a center point (planets, moons, electrons, satellites)
   - Include: target elements, relative speeds (inner=faster, outer=slower)
   - Duration: proportional to distance (inner 5-10s, outer 30-60s)

2. ROTATION/SPIN → type: "rotate"
   - Objects spinning on their axis (Earth rotation, wheels, turbines, molecules)
   - Include: rotation direction, speed
   - Duration: 2-10s depending on what's being shown

3. FLOW/SEQUENCE → type: "flow"
   - Movement from point A to B (blood circulation, data pipelines, water cycle, electricity)
   - Include: path description, direction
   - Duration: 3-8s for one complete cycle

4. PULSING/BREATHING → type: "pulse"
   - Rhythmic expansion/contraction (heartbeat, sound waves, emphasis)
   - Include: scale range (e.g., 1.0 to 1.1)
   - Duration: 1-3s

5. GROWTH/SCALING → type: "scale"
   - Size changes over time (population growth, cell division, statistics)
   - Include: start and end scale
   - Duration: 5-15s

6. BOUNCE/OSCILLATION → type: "bounce"
   - Back-and-forth motion (pendulum, springs, vibration)
   - Include: amplitude, axis
   - Duration: 1-4s

ANIMATION HINT EXAMPLE (solar system):
"animation_hints": [
    {"target": "mercury", "type": "orbit", "duration_range": "fast", "description": "Closest planet, fastest orbit ~10s"},
    {"target": "earth", "type": "orbit", "duration_range": "medium", "description": "Reference orbit ~20s"},
    {"target": "jupiter", "type": "orbit", "duration_range": "slow", "description": "Outer planet, slow orbit ~45s"},
    {"target": "saturn-rings", "type": "rotate", "duration_range": "slow", "description": "Ring rotation ~30s"}
]

IMPORTANT: animation_hints is OPTIONAL. Only include when animations add educational value.
Static topics (history facts, vocabulary, math formulas) should have empty array or omit the field.

SCROLL HINTS (add when content may exceed viewport):
====================================================
Include "scroll_hints" array when content is likely too large for 1920x1080 display.
Do NOT add scroll for content that fits comfortably on screen.

RULES for when to include scroll_hints:

1. LONG LISTS → type: "vertical"
   - More than 8-10 items in a list (events, bullet points, steps)
   - Timeline with many entries
   - Tables with many rows

2. WIDE CONTENT → type: "horizontal"
   - Timelines, processes, or sequences that flow left-to-right
   - Comparison tables with many columns
   - Galleries or image rows

3. MULTIPLE SECTIONS/CARDS → type: "snap-carousel"
   - Content naturally divided into discrete "pages" or "cards"
   - Step-by-step tutorials where each step is a screen
   - Slideshows, galleries, or multiple topics to explore

4. VERY LONG TEXT → type: "paginated"
   - Long articles, stories, or detailed explanations
   - Documents that need page-by-page reading
   - Content where user needs to read sequentially

SCROLL HINT EXAMPLES:
- Event list with 15 items: {"target": "events_list", "type": "vertical", "reason": "15 events exceed viewport"}
- Tutorial with 5 steps: {"target": "tutorial_steps", "type": "snap-carousel", "reason": "5 discrete step cards"}
- Wide timeline: {"target": "history_timeline", "type": "horizontal", "reason": "timeline spans 100 years"}

IMPORTANT: scroll_hints is OPTIONAL. Only include when content genuinely needs scrolling.
Short content (3-5 items, single paragraph) should NOT have scroll hints.

DOCUMENT COMPONENT GUIDANCE:
When user asks for a document related to a meeting/event, use these props:
- "meeting_search": Use when document is linked to a calendar event (e.g., "project kickoff meeting")
- "event_id": Use if you know the specific event ID
- "doc_id": Use only if you have the exact Google Doc ID
- "doc_url": Use only if you have the full document URL

The service will search the meeting, find the linked document in the event description, and fetch it.

AI CONTENT GENERATION VS DOCUMENT EXTRACTION (CRITICAL):
=========================================================
RULE: "create/genera/crea" verbs = text_block (YOU generate props.content)
RULE: "extract/show/muestra" from doc = doc_summary (backend fetches, use content_request)
NEVER MIX: doc_summary is for EXISTING docs, text_block is for NEW content you create.

AI DOCUMENT INTELLIGENCE (for doc_summary only):
- "content_request": Natural language describing what to extract (e.g., "Extract key points", "List action items")
- "content_type": Category hint: "impact_phrases", "script", "key_points", "action_items", "summary", "agenda", "custom"

MULTI-COMPONENT RULE: Different positions = different content_request values.
Example: "puntos clave arriba, acciones abajo" → Component 1: content_request="key points", Component 2: content_request="action items"

MEETING + DOCUMENT COMBINATIONS:
When user asks for meeting info AND doc content, use TWO components:
- Meeting info (time/location) → meeting_detail or countdown_timer
- Doc content (agenda/points) → doc_summary with content_request

COMPONENT SELECTION GUIDE:
- "próxima reunión" / "next meeting" → meeting_detail (NOT calendar_week)
- "el día de [X]" / "the [X] day" → meeting_detail with meeting_search="[X]" (user refers to an EVENT, not a calendar view)
- "el evento [X]" / "the [X] event" → meeting_detail with meeting_search="[X]"
- "countdown" / "cuanto falta" → countdown_timer or event_countdown
- "calendario de la semana" / "week calendar" → calendar_week
- "agenda del día" / "today's events" → calendar_agenda (shows ALL events of the day)
- "primer punto" / "first item" / "puntos de la agenda" → doc_summary with content_request

NOTE: calendar_day = view of a DATE with all events. meeting_detail = view of a SPECIFIC event by name/search.

Example for AI-generated content:
{{
    "type": "doc_summary",
    "props": {{
        "meeting_search": "project kickoff meeting",
        "content_request": "Generate 3 powerful opening phrases that capture the meeting's main goals",
        "content_type": "impact_phrases"
    }}
}}

Example for meeting-related document (simple preview):
{{
    "type": "doc_preview",
    "props": {{
        "meeting_search": "project kickoff meeting",
        "show_title": true,
        "max_chars": 800
    }}
}}

COMPLETE EXAMPLE 1: Meeting + First Agenda Item (TWO COMPONENTS, stack):
User request: "próxima reunión con hora y abajo el primer punto de la agenda"
→ This is a MULTI-PART request requiring 2 components in a "stack" layout:

{{
    "layout": {{ "intent": "stack", "engine": "flex", "gap": "16px" }},
    "components": [
        {{
            "id": "meeting_info",
            "type": "meeting_detail",
            "priority": "primary",
            "position": {{ "flex": 2 }},
            "style": {{ "background": "#1a1a2e", "text_color": "#ffffff", "border_radius": "16px", "padding": "24px" }},
            "props": {{ "show_location": true, "show_attendees": false }},
            "data": {{}}
        }},
        {{
            "id": "agenda_first_item",
            "type": "doc_summary",
            "priority": "secondary",
            "position": {{ "flex": 1 }},
            "style": {{ "background": "#16213e", "text_color": "#ffffff", "border_radius": "12px", "padding": "20px" }},
            "props": {{
                "meeting_search": "next meeting",
                "content_request": "Extract ONLY the first agenda item in a single line. Just the first point, nothing more.",
                "content_type": "agenda"
            }},
            "data": {{}}
        }}
    ]
}}

CRITICAL EXAMPLE: Calendar + Generated Plan (Sprint 4.4.0):
User request: "manten el evento a la izquierda y creame un plan a la derecha para hacer en South Beach"

BREAKDOWN:
→ MULTI-PART request with SPATIAL keywords ("izquierda" AND "derecha")
→ Part 1: "manten el evento a la izquierda" = calendar component (shows events)
→ Part 2: "creame un plan a la derecha" = text_block with GENERATED content (NOT doc_summary!)

REQUIRED OUTPUT:
- Layout: "two_column" with columns=2, rows=1, gap="24px"
- Component 1: calendar_week with grid_column="1"
- Component 2: text_block with grid_column="2", props.content=[YOUR GENERATED SOUTH BEACH PLAN]

KEY LESSONS:
- "creame/create" verb = YOU generate the content in props.content (text_block)
- "muestra/show" verb = FETCH existing content (doc_summary/meeting_detail)
- Spatial keywords ("izquierda Y derecha") = two_column layout with 2 components
- NEVER use doc_summary for generated content - that's text_block territory!

EXAMPLE COMPLETE COMPONENT (NEVER return less than this):
{{
    "id": "countdown_main",
    "type": "countdown_timer",
    "priority": "primary",
    "position": {{
        "grid_column": "1",
        "grid_row": "1"
    }},
    "style": {{
        "background": "#1a1a2e",
        "text_color": "#ffffff",
        "border_radius": "16px",
        "padding": "24px"
    }},
    "props": {{
        "show_label": true
    }},
    "data": {{}}
}}

__COMPONENTS__

SCHEMA:
__SCHEMA__
"""


# ---------------------------------------------------------------------------
# GENERATION PROMPT
# ---------------------------------------------------------------------------

SCENE_GENERATION_TEMPLATE = """Generate a Scene Graph for this display request.

User Request: {user_request}
Content Type: {info_type}
Layout Hints: {layout_hints}
Target Devices: {device_count} device(s)
{realtime_data}
{conversation_context}
Requirements:
1. Follow the user's layout instructions exactly
2. Choose appropriate layout intent based on component count and user description
3. ALWAYS include complete "style" object for EVERY component - NEVER null
4. Apply the design system defaults for any styling not specified by user
5. Use the correct component types from the registry
6. Assign priorities: main focus = primary, supporting = secondary
7. Include proper position for each component based on layout engine
8. If REAL-TIME DATA is provided above, include it in the component's "data" field with "is_placeholder": false
9. For components WITHOUT real-time data, leave "data" empty (will be populated by service)
10. Set appropriate refresh_seconds in metadata (60 for countdowns, 300 for static)
11. DETECT MULTI-PART REQUESTS: If user asks for X AND Y, create separate components for each part
    - "reunión + agenda" = meeting_detail + doc_summary with content_request
    - "countdown + summary" = countdown_timer + doc_summary
    - "calendario a la izquierda y plan a la derecha" = calendar_week (grid_column="1") + text_block (grid_column="2")
    - "manten X a la izquierda y crea Y a la derecha" = two_column layout with 2 components

    CRITICAL: When user says "a la izquierda Y a la derecha", that's TWO components, NOT one!
12. CONTENT EXTRACTION (Sprint 4.4.0 - GAP #1): When user says "show X" where X is a specific item, extract search terms:
    - "show my South Beach plan" → meeting_detail with props {{"meeting_search": "South Beach plan"}}
    - "show budget document" → doc_summary with props {{"doc_search": "budget"}}
    - "show my dentist appointment" → meeting_detail with props {{"meeting_search": "dentist"}}
    - DO NOT create empty components - ALWAYS populate search props from the user's request
    - Extract the KEY NOUNS from the request and use them as search terms
    - If user says "my plan" and conversation shows a recent event_id, use that instead

12a. GENERATE vs EXTRACT (Sprint 4.4.0 - Critical Fix):
    WHEN USER SAYS "crea/genera/create/generate" → Use text_block, YOU generate content:
    - "crearas un plan para South Beach" → text_block with props.content = [YOUR GENERATED PLAN]
    - "generate a checklist for the meeting" → text_block with props.content = [YOUR CHECKLIST]
    - "dame ideas para la presentación" → text_block with props.content = [YOUR IDEAS]

    WHEN USER SAYS "muestra/show/extrae/extract" → Use doc_summary/meeting_detail to FETCH:
    - "muestra el plan de South Beach" → meeting_detail with meeting_search="South Beach"
    - "show the budget document" → doc_summary with doc_search="budget"
    - "extract key points from the doc" → doc_summary with content_request="Extract key points"

    CRITICAL: "crear/generar" = text_block (you make it), "mostrar/extraer" = doc_summary (fetch existing)

12b. GENERIC DOCUMENT REFERENCES (Sprint 5.1.1 - Critical Fix):
    When user says "el documento" / "the document" / "ese documento" WITHOUT a specific name:

    ✅ IF "RECENTLY REFERENCED DOCUMENT" section exists above:
       → Use the doc_id/doc_url from that section
       → Example: {{"type": "doc_summary", "props": {{"doc_id": "abc123"}}}}

    ❌ IF NO "RECENTLY REFERENCED DOCUMENT" section exists:
       → DO NOT use meeting_search="documento" - that searches for a MEETING named "documento"!
       → Return error: {{"error": "no_document_context", "message": "No document in context. Please specify which document."}}

    WRONG: {{"type": "doc_summary", "props": {{"meeting_search": "documento"}}}} ← Searches for MEETING, not doc!
    RIGHT: {{"type": "doc_summary", "props": {{"doc_id": "<from context above>"}}}}

    REMEMBER: "meeting_search" is for finding MEETINGS by name, NOT documents!

13. CRITICAL - USE CONVERSATION CONTEXT: If previous conversation contains content generated by another AI, use that content! Display what was already generated, don't say you can't do something.

13a. DISPLAY INTENT SEQUENCING (Sprint 4.4.0 - GAP #11): When user said "create X AND show it":
    - Step 1 already happened (content was generated by Gemini)
    - You are Step 2 (display the generated content)
    - Look for generated_content in conversation context above
    - Use that content in a text_block component
    - DON'T try to generate new content - display what already exists

14. CONVERSATION SUMMARY REQUESTS: If the user asks to "summarize this conversation" / "resume esta conversación" / "show what we discussed":
    - Create a text_block component
    - In props.content, write a CLEAR SUMMARY of the conversation history provided
    - Include key points discussed, conclusions reached, and interesting insights
    - Format nicely with bullet points or sections
    - The summary should be 3-5 paragraphs capturing the essence of the conversation

STYLE CHECKLIST (verify before responding):
□ Every component has "style" object (not null)
□ Every style has: background, text_color, border_radius, padding
□ global_style has: background, font_family, text_color, accent_color
□ Primary components use #1a1a2e background
□ Secondary components use #16213e background

Respond with ONLY the JSON Scene Graph. No explanation, no markdown."""


# ---------------------------------------------------------------------------
# BUILDER FUNCTIONS
# ---------------------------------------------------------------------------

def build_scene_system_prompt(components_context: str) -> str:
    """
    Build the complete system prompt for scene generation.

    Args:
        components_context: Output from component_registry.to_prompt_context()

    Returns:
        Formatted system prompt
    """
    # Sprint 4.4.0: Use .replace() instead of .format() to avoid conflicts with JSON examples
    return SCENE_SYSTEM_PROMPT.replace(
        "__COMPONENTS__", components_context
    ).replace(
        "__SCHEMA__", SCENE_GRAPH_SCHEMA
    )


def build_scene_generation_prompt(
    user_request: str,
    layout_hints: list,
    info_type: str,
    device_count: int = 1,
    realtime_data: dict = None,
    conversation_context: dict = None,
) -> str:
    """
    Build the generation prompt for a scene request.
    
    Sprint 4.1: Now accepts realtime_data for dynamic scene content.
    Sprint 4.2: Now accepts conversation_context for multi-turn awareness.
    
    Args:
        user_request: Original user request
        layout_hints: List of LayoutHint objects or strings
        info_type: Content type (calendar, weather, mixed)
        device_count: Number of target devices
        realtime_data: Pre-fetched real-time data from Gemini
        conversation_context: Previous conversation history and generated content
        
    Returns:
        Formatted generation prompt
    """
    import json
    
    # Format hints for prompt
    if layout_hints:
        hints_str = ", ".join([
            h.raw_hint if hasattr(h, 'raw_hint') and h.raw_hint else str(h)
            for h in layout_hints
        ])
    else:
        hints_str = "None specified"
    
    # Build realtime data section for prompt
    realtime_section = ""
    if realtime_data:
        realtime_section = "\n\nREAL-TIME DATA AVAILABLE (include in component data fields):\n"
        for component_type, data in realtime_data.items():
            realtime_section += f"\n{component_type}:\n{json.dumps(data, indent=2)}\n"
        realtime_section += "\nIMPORTANT: Include this real data in the 'data' field of matching components with 'is_placeholder': false!"
        realtime_section += "\nIf 'raw_weather_info' is provided, extract temperature, condition, humidity, wind_speed values from the text.\n"
    
    # Sprint 4.2: Build conversation context section
    conversation_section = ""
    if conversation_context:
        conversation_section = "\n\nPREVIOUS CONVERSATION CONTEXT (CRITICAL - USE THIS):\n"
        
        # Detect if user wants a conversation summary
        is_summary_request = any(kw in user_request.lower() for kw in [
            'resume', 'resumen', 'resumas', 'summarize', 'summary',
            'lo que hablamos', 'what we discussed', 'esta conversación',
            'this conversation', 'nuestra conversación', 'our conversation',
        ])
        
        # Include conversation history
        if conversation_context.get("history"):
            history = conversation_context["history"]
            
            if is_summary_request:
                conversation_section += "\n*** USER WANTS A SUMMARY - FULL CONVERSATION HISTORY: ***\n"
                # Include ALL turns for summary requests
                for i, turn in enumerate(history):
                    conversation_section += f"\n--- Turn {i+1} ---\n"
                    conversation_section += f"  User: {turn.get('user', '')}\n"
                    if turn.get('assistant'):
                        # Include more content for summaries
                        response = turn['assistant'][:1500]
                        if len(turn['assistant']) > 1500:
                            response += "..."
                        conversation_section += f"  Assistant: {response}\n"
                conversation_section += "\n*** CREATE A CLEAR SUMMARY OF THIS CONVERSATION as a text_block! ***\n"
            else:
                conversation_section += "\nRecent conversation turns:\n"
                for turn in history[-3:]:  # Last 3 turns
                    conversation_section += f"  User: {turn.get('user', '')}\n"
                    if turn.get('assistant'):
                        # Truncate long responses (Sprint 4.5.0: increased from 500 to 1000)
                        response = turn['assistant'][:1000]
                        if len(turn['assistant']) > 1000:
                            response += "..."
                        conversation_section += f"  Assistant: {response}\n"
                    conversation_section += "\n"
        
        # Sprint 4.4.0 - GAP #2: Use shared helper for consistent generated_content injection
        conversation_section = inject_generated_content_context(
            conversation_section,
            conversation_context,
            format_style="scene"
        )
        
        # Sprint 4.4.0 - GAP #4: Use shared helper for consistent last_event injection
        conversation_section = inject_last_event_context(
            conversation_section,
            conversation_context,
            format_style="scene"
        )

        # Sprint 4.4.0 - GAP #5: Use shared helper for consistent last_doc injection
        conversation_section = inject_last_doc_context(
            conversation_section,
            conversation_context,
            format_style="scene"
        )

        # Sprint 4.5.0: Inject content memory for multi-content display
        if conversation_context.get("content_memory"):
            memory = conversation_context["content_memory"]
            conversation_section += "\n\n*** CONTENT MEMORY (Sprint 4.5.0 - Full content available) ***\n"
            conversation_section += "Previously generated contents that user may reference:\n"

            for i, item in enumerate(memory[-5:], 1):  # Last 5 items
                conversation_section += f"\n[Content #{i}]\n"
                conversation_section += f"  Title: {item.get('title', 'Untitled')}\n"
                conversation_section += f"  Type: {item.get('type', 'unknown')}\n"
                # Include FULL content (not truncated!) - this is the key fix
                content = item.get('content', '')
                if len(content) > 4000:
                    content = content[:4000] + "\n... [truncated for prompt length]"
                conversation_section += f"  Content:\n{content}\n"

            conversation_section += """
⚠️ CRITICAL - CONTENT MEMORY USAGE (Sprint 4.5.0):
===================================================
When user references previously generated content ("la nota", "el plan", "the template"):

❌ WRONG - NEVER DO THIS:
   {"type": "doc_summary", "props": {"meeting_search": "nota"}}  ← WRONG! doc_summary searches Google Docs!

✅ CORRECT - ALWAYS DO THIS:
   {"type": "text_block", "props": {"title": "Tips ABA", "content": "<COPY FULL CONTENT FROM MEMORY ABOVE>"}}

HOW TO USE CONTENT MEMORY:
1. User says "muestra la nota" → Find matching content in [Content #1], [Content #2], etc. above
2. COPY the FULL "Content:" text from that memory item
3. Put it in a text_block component with props.content = that full text

EXAMPLE - User: "muestra la nota y el plan juntos"
→ Find [Content #1] with title "Tips ABA" and [Content #2] with title "Plan Intervención"
→ Create JSON:
{
  "layout": {"intent": "two_column", ...},
  "components": [
    {"type": "text_block", "props": {"title": "Tips ABA", "content": "<FULL text from Content #1>"}},
    {"type": "text_block", "props": {"title": "Plan Intervención", "content": "<FULL text from Content #2>"}}
  ]
}

REMEMBER: Content Memory items are YOUR PREVIOUS RESPONSES - use text_block to display them!
"""

        # Include last assistant response (useful context)
        if conversation_context.get("last_response") and not conversation_context.get("generated_content"):
            conversation_section += f"\nLast AI Response:\n{conversation_context['last_response'][:800]}\n"
            conversation_section += "\nIMPORTANT: If the user wants to display this response, use a text_block component!\n"
    
    return SCENE_GENERATION_TEMPLATE.format(
        user_request=user_request,
        info_type=info_type,
        layout_hints=hints_str,
        device_count=device_count,
        realtime_data=realtime_section,
        conversation_context=conversation_section,
    )


# ---------------------------------------------------------------------------
# EXAMPLE SCENES (for few-shot learning if needed)
# ---------------------------------------------------------------------------

EXAMPLE_SIDEBAR_SCENE = """{
    "scene_id": "example-sidebar-001",
    "version": "1.1",
    "target_devices": ["device-1"],
    "layout": {
        "intent": "sidebar",
        "engine": "grid",
        "columns": 4,
        "rows": 1,
        "gap": "16px"
    },
    "components": [
        {
            "id": "calendar_main",
            "type": "calendar_week",
            "priority": "primary",
            "position": {
                "grid_column": "1 / 4",
                "grid_row": "1"
            },
            "props": {
                "show_times": true,
                "start_hour": 8,
                "end_hour": 20
            },
            "style": {
                "background": "#1a1a2e",
                "text_color": "#ffffff",
                "border_radius": "16px",
                "padding": "24px"
            },
            "data": {}
        },
        {
            "id": "clock_sidebar",
            "type": "clock_digital",
            "priority": "secondary",
            "position": {
                "grid_column": "4",
                "grid_row": "1"
            },
            "props": {
                "format": "12h",
                "show_seconds": false
            },
            "style": {
                "background": "#16213e",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "20px"
            },
            "data": {}
        }
    ],
    "global_style": {
        "background": "#0f0f23",
        "font_family": "Inter",
        "text_color": "#ffffff",
        "accent_color": "#7b2cbf"
    },
    "metadata": {
        "created_at": "2025-12-22T10:00:00Z",
        "refresh_seconds": 300,
        "user_request": "calendar on the left with clock in the corner",
        "generated_by": "claude_sonnet"
    }
}"""


EXAMPLE_DASHBOARD_SCENE = """{
    "scene_id": "example-dashboard-001",
    "version": "1.1",
    "target_devices": ["device-1"],
    "layout": {
        "intent": "dashboard",
        "engine": "grid",
        "columns": 2,
        "rows": 2,
        "gap": "16px"
    },
    "components": [
        {
            "id": "calendar_widget",
            "type": "calendar_widget",
            "priority": "primary",
            "position": {
                "grid_column": "1",
                "grid_row": "1"
            },
            "props": {
                "max_events": 5
            },
            "style": {
                "background": "#1a1a2e",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "24px"
            },
            "data": {}
        },
        {
            "id": "clock_widget",
            "type": "clock_digital",
            "priority": "secondary",
            "position": {
                "grid_column": "2",
                "grid_row": "1"
            },
            "props": {
                "format": "12h",
                "show_date": true
            },
            "style": {
                "background": "#16213e",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "20px"
            },
            "data": {}
        },
        {
            "id": "weather_widget",
            "type": "weather_current",
            "priority": "secondary",
            "position": {
                "grid_column": "1",
                "grid_row": "2"
            },
            "props": {
                "units": "fahrenheit"
            },
            "style": {
                "background": "#0f3460",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "20px"
            },
            "data": {}
        },
        {
            "id": "agenda_widget",
            "type": "calendar_agenda",
            "priority": "secondary",
            "position": {
                "grid_column": "2",
                "grid_row": "2"
            },
            "props": {
                "max_events": 5
            },
            "style": {
                "background": "#1a1a2e",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "20px"
            },
            "data": {}
        }
    ],
    "global_style": {
        "background": "#0f0f23",
        "font_family": "Inter",
        "text_color": "#ffffff",
        "accent_color": "#7b2cbf"
    },
    "metadata": {
        "created_at": "2025-12-22T10:00:00Z",
        "refresh_seconds": 300,
        "user_request": "dashboard with weather, clock, and calendar",
        "generated_by": "claude_sonnet"
    }
}"""
