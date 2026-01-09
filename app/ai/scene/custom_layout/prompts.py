"""
Custom Layout Prompts - Optimized prompt templates for GPT-5.2 HTML generation.

Sprint 5.2.2: Optimized prompts with:
- ~70% fewer tokens than original
- CSS-only interactivity (touch-enabled, no JS for security)
- Educational, visually engaging layouts
- Chromium-compatible CSS techniques

Design Goals:
=============
- Generate standalone HTML (inline CSS, no external dependencies)
- Optimize for touchscreen TV (1920x1080)
- Dark theme matching SceneGraph global_style
- Support CSS-only interactivity patterns
"""

import json
from typing import Dict, Any


def build_custom_layout_prompt(scene: Dict[str, Any], user_request: str = None) -> str:
    """
    Build optimized prompt for GPT-5.2 to generate custom HTML layout.

    Sprint 5.2.2: Reduced token count by ~70% while adding CSS interactivity.
    Sprint 5.2.3: Added animation_hints support for CSS @keyframes animations.

    Args:
        scene: SceneGraph dictionary from Gemini
        user_request: Original user request (falls back to scene metadata)

    Returns:
        Complete prompt string for GPT-5.2
    """
    # Get user request from parameter or scene metadata
    if not user_request:
        metadata = scene.get("metadata", {})
        user_request = metadata.get("user_request", "Display content")

    # Extract only essential data (reduce tokens)
    global_style = scene.get("global_style", {})
    layout = scene.get("layout", {})

    # Build minimal component list with only necessary data
    components_data = []
    for comp in scene.get("components", []):
        components_data.append({
            "type": comp.get("type"),
            "data": comp.get("data", {}),
        })

    # Extract animation hints if present
    animation_hints = scene.get("animation_hints", [])

    # Extract scroll hints if present
    scroll_hints = scene.get("scroll_hints", [])

    # Minimal scene for prompt
    minimal_scene = {
        "layout_intent": layout.get("intent", "fullscreen"),
        "style": {
            "background": global_style.get("background", "#0f0f23"),
            "text_color": global_style.get("text_color", "#ffffff"),
            "accent": global_style.get("accent_color", "#7b2cbf"),
        },
        "components": components_data,
    }

    # Add animation hints only if present
    if animation_hints:
        minimal_scene["animation_hints"] = animation_hints

    # Add scroll hints only if present
    if scroll_hints:
        minimal_scene["scroll_hints"] = scroll_hints

    prompt = f"""Create STUDENT-FACING content for a classroom display board.

## CONTEXT
- A TEACHER requested: "{user_request}"
- Your HTML will be shown on a CLASSROOM BOARD for STUDENTS to learn from
- Create VISUAL LEARNING CONTENT like an interactive whiteboard

## SCENE DATA
```json
{json.dumps(minimal_scene, ensure_ascii=False, default=str)}
```

## WHAT TO CREATE
Visual content that helps STUDENTS understand the topic:
- Clear visual explanations with icons/emojis/diagrams
- Concepts broken into simple, digestible pieces
- Examples and visual demonstrations
- Interactive elements (tabs, expandable sections) for exploration

## WHAT NOT TO CREATE
- Lesson plans, schedules, or teacher notes
- "Learning objectives" or curriculum goals
- Task lists or homework assignments
- Tips for teachers on how to teach

## CSS INTERACTIVITY (Chromium, NO JavaScript)
Use as needed for student engagement:
- `<details>/<summary>` - Expandable sections
- Checkbox/Radio hack - Tabs, toggles
- `:target` - Navigation anchors
- `:hover/:active` - Touch feedback
- CSS Scroll Snap - Carousels
- Transitions/@keyframes - Animations

## CSS ANIMATIONS (when animation_hints present in SCENE DATA)
If "animation_hints" array exists, implement CSS @keyframes:
- "orbit" → `transform: rotate()` around center point, `transform-origin` for radius
- "rotate" → `transform: rotate(360deg)` on element axis
- "flow" → `transform: translateX/Y()` along path
- "pulse" → `transform: scale()` expansion/contraction
- "scale" → gradual size change
- "bounce" → `translateY()` oscillation

Duration mapping:
- "fast" → 2-5s
- "medium" → 5-15s
- "slow" → 15-60s

Use `animation: name duration linear infinite;` for continuous motion.

## CSS SCROLLING (when scroll_hints present in SCENE DATA)
If "scroll_hints" array exists, implement appropriate scroll behavior:
- "vertical" → `overflow-y: auto; max-height: 100vh;` with styled scrollbar
- "horizontal" → `overflow-x: auto; white-space: nowrap;` or flex row
- "snap-carousel" → `scroll-snap-type: x mandatory;` with `scroll-snap-align: start;` on children
- "paginated" → Use CSS scroll-snap with full-page snaps, optional page indicators

Touch-friendly scrollbar styling (example):
- ::-webkit-scrollbar with width: 8px
- ::-webkit-scrollbar-thumb with background: rgba(255,255,255,0.3), border-radius: 4px

For snap-carousel, add navigation dots or swipe indicators for discoverability.

## TECHNICAL
- Standalone HTML, inline CSS, no external deps
- 1920x1080, dark theme, large readable fonts
- Complete: <!DOCTYPE html> to </html>

Output ONLY raw HTML."""

    return prompt


def get_system_prompt() -> str:
    """
    Get optimized system prompt for GPT-5.2 HTML generation.

    Returns:
        System prompt string
    """
    return """You are an expert HTML/CSS designer creating STUDENT-FACING educational displays.

CRITICAL CONTEXT:
- The INPUT comes from a TEACHER/INSTRUCTOR
- The OUTPUT (your HTML) is displayed on a CLASSROOM BOARD for STUDENTS to see
- You are creating VISUAL LEARNING CONTENT, not lesson plans or teacher notes

Create content that STUDENTS will look at to LEARN - like an interactive whiteboard:
- Visual explanations with diagrams, icons, illustrations
- Simple, clear concepts broken into digestible pieces
- Examples and demonstrations
- Interactive elements students can explore (tabs, expandable sections)
- Engaging visuals that capture student attention

DO NOT create:
- Lesson plans or class schedules
- Teacher tips or teaching strategies
- "Objectives" lists or curriculum goals
- "Tasks for students" or homework lists
- Meta-content about HOW to teach

ANIMATIONS (when animation_hints provided):
If the scene data includes "animation_hints", implement CSS @keyframes animations:
- Match target elements to the "target" field
- Use appropriate transform for the "type" (orbit/rotate/flow/pulse/scale/bounce)
- Map duration_range: fast=2-5s, medium=5-15s, slow=15-60s
- Use `animation: name duration linear infinite;` for continuous motion
- Animations help students visualize dynamic concepts (orbits, flows, cycles)

SCROLLING (when scroll_hints provided):
If the scene data includes "scroll_hints", implement appropriate overflow handling:
- "vertical" → scrollable list with styled scrollbar
- "horizontal" → horizontally scrollable row
- "snap-carousel" → swipeable cards with scroll-snap
- "paginated" → full-page sections with snap points
- Always style scrollbars for dark theme (subtle, touch-friendly)
- Add visual indicators (dots, arrows) for carousels

Target: 1920x1080 Chromium touchscreen, dark theme.
Technical: Standalone HTML, inline CSS, NO JavaScript.
Output: ONLY valid HTML code, no explanations."""
