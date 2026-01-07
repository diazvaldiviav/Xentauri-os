"""
Custom Layout Prompts - Prompt templates for GPT-5.2 HTML generation.

Sprint 5.2: These prompts instruct GPT-5.2 to generate standalone HTML
layouts based on SceneGraph data from Claude.

Design Goals:
=============
- Generate standalone HTML (inline CSS, no external dependencies)
- Optimize for TV screens (1920x1080)
- Dark theme matching SceneGraph global_style
- Support all SceneGraph component types
"""

import json
from typing import Dict, Any


def build_custom_layout_prompt(scene: Dict[str, Any], user_request: str) -> str:
    """
    Build the prompt for GPT-5.2 to generate custom HTML layout.
    
    Args:
        scene: SceneGraph dictionary from Claude
        user_request: Original user request for context
        
    Returns:
        Complete prompt string for GPT-5.2
    """
    # Extract global styles for consistency
    global_style = scene.get("global_style", {})
    background = global_style.get("background", "#0f0f23")
    font_family = global_style.get("font_family", "Inter")
    text_color = global_style.get("text_color", "#ffffff")
    accent_color = global_style.get("accent_color", "#7b2cbf")
    
    # Extract layout info
    layout = scene.get("layout", {})
    layout_intent = layout.get("intent", "fullscreen")
    
    # Extract components for rendering instructions
    components = scene.get("components", [])
    component_descriptions = []
    
    for comp in components:
        comp_type = comp.get("type", "unknown")
        comp_data = comp.get("data", {})
        comp_props = comp.get("props", {})
        comp_style = comp.get("style", {})

        desc = f"""
- **{comp_type}** (id: {comp.get('id', 'unknown')}):
  - Data: {json.dumps(comp_data, ensure_ascii=False, default=str)}
  - Props: {json.dumps(comp_props, ensure_ascii=False)}
  - Style: {json.dumps(comp_style, ensure_ascii=False)}"""
        component_descriptions.append(desc)
    
    components_text = "\n".join(component_descriptions) if component_descriptions else "No components defined"
    
    prompt = f"""You are an expert HTML/CSS designer creating a display layout for a large TV screen (1920x1080).

## USER REQUEST
"{user_request}"

## SCENE GRAPH DATA (from Claude)
The following SceneGraph describes the layout structure and data:

```json
{json.dumps(scene, ensure_ascii=False, indent=2, default=str)}
```

## LAYOUT INTENT
{layout_intent}

## COMPONENTS TO RENDER
{components_text}

## DESIGN REQUIREMENTS

### CRITICAL: NON-INTERACTIVE DISPLAY
This is a PASSIVE DISPLAY SCREEN. The user CANNOT interact with it:
- NO clicks, NO scrolls, NO hover effects, NO touch
- NO buttons that say "Click here", "Tap to continue", "Learn more"
- NO links or interactive elements
- NO pagination or "next/previous" controls
- ALL content must be visible at once without scrolling
- If content is too long, use smaller fonts or summarize - NEVER require scrolling

### Technical Requirements
1. Generate STANDALONE HTML - all CSS must be inline or in <style> tags
2. NO external dependencies (no CDN links, no external fonts except system fonts)
3. Target resolution: 1920x1080 (TV screen)
4. Use semantic HTML5 elements where appropriate
5. Ensure all text is readable from 3 meters away (large fonts, good contrast)
6. COMPLETE HTML - always include closing </html> tag

### Style Requirements
1. Background: {background}
2. Font Family: {font_family}, -apple-system, BlinkMacSystemFont, sans-serif
3. Text Color: {text_color}
4. Accent Color: {accent_color}
5. Use modern, clean design with rounded corners (border-radius: 16px)
6. Add subtle shadows for depth (box-shadow with low opacity)
7. Ensure proper padding (32px on containers)

### Component Rendering Guidelines

**calendar_week / calendar_agenda / calendar_month:**
- Display events as cards with time, title, and optional description
- Use accent color for event indicators
- Show date headers clearly

**clock_digital / clock_analog:**
- Large, centered display
- Show static time from data (no JavaScript - display is sandboxed for security)
- Use large, readable font (minimum 72px for TV viewing)

**weather_current / weather_forecast:**
- Show temperature prominently
- Include weather icon or emoji
- Display location and conditions

**text_block:**
- Render markdown-like content
- Support titles and body text
- Preserve line breaks and formatting

**countdown_timer:**
- Large countdown display
- Show event name and remaining time

**meeting_detail:**
- Show meeting title, time, and attendees
- Include join link if available

**doc_summary / doc_preview:**
- Display document content with proper formatting
- Show title and source

### Layout Guidelines (based on intent: {layout_intent})
- **fullscreen**: Single component centered, fills viewport
- **sidebar**: Main content 70%, sidebar 30%
- **two_column**: Two equal columns
- **dashboard**: 2x2 or 3x2 grid of widgets
- **stack**: Vertical stack with gaps

## OUTPUT FORMAT
Return ONLY the HTML code, starting with <!DOCTYPE html> and ending with </html>.
Do NOT include any explanation, markdown code blocks, or additional text.
The HTML must be complete and self-contained.
"""
    
    return prompt


def get_system_prompt() -> str:
    """
    Get the system prompt for GPT-5.2 HTML generation.

    Returns:
        System prompt string
    """
    return """You are an expert HTML/CSS designer specializing in TV display layouts.
Your task is to generate beautiful, functional HTML layouts for smart TV screens.

Key principles:
1. STANDALONE: No external dependencies - everything inline
2. READABLE: Large fonts, high contrast for viewing from distance
3. MODERN: Clean design with rounded corners and subtle shadows
4. RESPONSIVE: Works well on 1920x1080 screens
5. DARK THEME: Optimized for ambient lighting in living rooms
6. NON-INTERACTIVE: This is a passive display - NO clicks, NO scrolls, NO buttons, NO "click here" text
7. COMPLETE: Always generate complete HTML with proper closing tags (</body>, </html>)

You output ONLY valid HTML code, no explanations or markdown.
The HTML MUST be complete - always end with </html>."""
