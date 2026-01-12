# Custom Layout Generation - Technical Plan

> **Status:** PLANNED (MVP)
> **Created:** January 6, 2026
> **Sprint:** 5.2.0 (Proposed)
> **Priority:** High - Core Educational Feature

## Overview

This document describes the architecture for generating professional, responsive custom layouts using AI (Claude Sonnet 4.5) while maintaining the existing Scene Graph as a fallback mechanism.

---

## Problem Statement

The current Scene Graph system generates structured JSON that the frontend renders. While functional, it produces basic layouts. For educational use cases (schools, classrooms), teachers need:

- Visually engaging content (timelines, diagrams, interactive grids)
- Professional responsive layouts
- Dynamic educational content (math tables, historical timelines, scientific diagrams)
- Single natural language command to display complex visuals

---

## Proposed Solution

### Architecture

```
User Command: "Muestra la tabla del 7 con colores"
                              │
                              ▼
                    IntentService.process()
                              │
                              ▼
                    SceneService.generate_scene()
                              │
                              ▼
                    scene (SceneGraph JSON)  ← FALLBACK
                              │
                              ▼
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               │
    LayoutGenerationService                   │
    (Claude Sonnet 4.5)                       │
              │                               │
              ▼                               │
    custom_layout (HTML/CSS)                  │
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
                    WebSocket Message
                    {
                      "parameters": {
                        "scene": {...},           ← Fallback (always present)
                        "custom_layout": {...}    ← Enhanced layout
                      }
                    }
                              │
                              ▼
                    Frontend (Raspberry Pi)
                              │
                    ┌─────────┴─────────┐
                    │   Try Render      │
                    │   custom_layout   │
                    └─────────┬─────────┘
                              │
              ┌───────────────┴───────────────┐
              │ SUCCESS                   ERROR│
              ▼                               ▼
    Display custom_layout           Display scene (fallback)
```

---

## Message Structure

### Current Structure (Scene Only)

```json
{
  "type": "command",
  "command_type": "display_scene",
  "command_id": "uuid",
  "parameters": {
    "scene": {
      "scene_id": "uuid",
      "layout": {"intent": "sidebar", "engine": "grid"},
      "components": [...],
      "global_style": {...},
      "metadata": {...}
    }
  },
  "timestamp": "2026-01-06T..."
}
```

### New Structure (Scene + Custom Layout)

```json
{
  "type": "command",
  "command_type": "display_scene",
  "command_id": "uuid",
  "parameters": {
    "scene": {
      "scene_id": "uuid",
      "layout": {"intent": "sidebar", "engine": "grid"},
      "components": [...],
      "global_style": {...},
      "metadata": {...}
    },
    "custom_layout": {
      "html": "<div class='educational-grid'>...</div>",
      "css": ".educational-grid { display: grid; ... }",
      "version": "1.0",
      "generated_by": "claude-sonnet-4.5",
      "generation_time_ms": 1250,
      "fallback_reason": null
    }
  },
  "timestamp": "2026-01-06T..."
}
```

### Custom Layout Schema

```python
class CustomLayout(BaseModel):
    """
    AI-generated custom HTML/CSS layout for enhanced visual display.

    This is an optional enhancement to the base SceneGraph.
    If rendering fails, the frontend falls back to the scene field.
    """
    html: str = Field(description="Complete HTML structure with embedded data")
    css: str = Field(description="Scoped CSS for the layout")
    version: str = Field(default="1.0", description="Layout schema version")
    generated_by: str = Field(description="Model that generated the layout")
    generation_time_ms: int = Field(description="Time taken to generate in ms")
    fallback_reason: Optional[str] = Field(
        default=None,
        description="If set, indicates why custom_layout should not be used"
    )
```

---

## Implementation Plan

### Phase 1: Backend Service

#### 1.1 Create LayoutGenerationService

**File:** `app/services/layout_generation_service.py`

```python
"""
Layout Generation Service - Generates custom HTML/CSS layouts using Claude.

This service takes a SceneGraph and generates a professional, responsive
HTML/CSS layout for enhanced visual display on educational screens.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import time
import logging

from app.ai.providers.anthropic_provider import anthropic_provider
from app.ai.scene.schemas import SceneGraph

logger = logging.getLogger("jarvis.layout_generation")


@dataclass
class CustomLayout:
    html: str
    css: str
    version: str = "1.0"
    generated_by: str = "claude-sonnet-4.5"
    generation_time_ms: int = 0
    fallback_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "html": self.html,
            "css": self.css,
            "version": self.version,
            "generated_by": self.generated_by,
            "generation_time_ms": self.generation_time_ms,
            "fallback_reason": self.fallback_reason,
        }


class LayoutGenerationService:
    """
    Generates custom HTML/CSS layouts from SceneGraph using Claude Sonnet 4.5.

    Usage:
        service = LayoutGenerationService()
        custom_layout = await service.generate_layout(scene, user_request)

        if custom_layout.fallback_reason is None:
            # Use custom layout
        else:
            # Use scene fallback
    """

    async def generate_layout(
        self,
        scene: SceneGraph,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> CustomLayout:
        """
        Generate a custom HTML/CSS layout from a SceneGraph.

        Args:
            scene: The base SceneGraph with components and data
            user_request: Original user request for context
            context: Additional context (user preferences, device info)

        Returns:
            CustomLayout with HTML/CSS or fallback_reason if generation failed
        """
        start_time = time.time()

        try:
            # Build prompt with scene data
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(scene, user_request, context)

            # Generate with Claude Sonnet 4.5
            response = await anthropic_provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # Lower for consistent layouts
                max_tokens=4096,  # Enough for complex layouts
            )

            if not response.success:
                return CustomLayout(
                    html="",
                    css="",
                    fallback_reason=f"AI generation failed: {response.error}",
                    generation_time_ms=int((time.time() - start_time) * 1000),
                )

            # Parse HTML and CSS from response
            html, css = self._parse_response(response.content)

            generation_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Layout generated in {generation_time_ms}ms")

            return CustomLayout(
                html=html,
                css=css,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"Layout generation error: {e}")
            return CustomLayout(
                html="",
                css="",
                fallback_reason=f"Generation error: {str(e)}",
                generation_time_ms=int((time.time() - start_time) * 1000),
            )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for layout generation."""
        # See: app/ai/prompts/layout_prompts.py
        pass

    def _build_user_prompt(
        self,
        scene: SceneGraph,
        user_request: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Build user prompt with scene data."""
        pass

    def _parse_response(self, content: str) -> tuple[str, str]:
        """Parse HTML and CSS from Claude's response."""
        pass


# Singleton
layout_generation_service = LayoutGenerationService()
```

#### 1.2 Create Layout Prompts

**File:** `app/ai/prompts/layout_prompts.py`

```python
"""
Layout Generation Prompts - System and user prompts for custom layout generation.

These prompts instruct Claude Sonnet 4.5 to generate professional,
responsive HTML/CSS layouts for educational displays.
"""

LAYOUT_SYSTEM_PROMPT = """You are an expert frontend developer specializing in educational visual displays.

Your task is to generate professional, responsive HTML/CSS layouts for classroom display screens.

REQUIREMENTS:
1. Generate COMPLETE, self-contained HTML with inline data (no placeholders)
2. Generate SCOPED CSS that won't conflict with other styles
3. Layouts must be 100% responsive (work on any screen size)
4. Use modern CSS: Grid, Flexbox, clamp(), container queries
5. Dark theme optimized for projectors/large screens
6. Animations should be subtle and non-distracting
7. Typography must be readable from distance (large fonts)
8. High contrast colors for accessibility

EDUCATIONAL CONTENT TYPES:
- Math: Tables, formulas, step-by-step solutions, graphs
- History: Timelines, maps, event cards, comparisons
- Science: Diagrams, processes, periodic tables, cycles
- Language: Vocabulary grids, conjugation tables, examples
- General: Calendars, schedules, announcements, dashboards

OUTPUT FORMAT:
```html
<div class="xentauri-layout" data-layout-id="unique-id">
  <!-- Your HTML here -->
</div>
```

```css
.xentauri-layout[data-layout-id="unique-id"] {
  /* Your scoped CSS here */
}
```

CRITICAL:
- All data must be embedded in HTML (read from the scene components)
- Never use external resources (images via URL are ok)
- Never use JavaScript (CSS-only animations)
- Always include fallback styles for older browsers
"""

def build_layout_user_prompt(
    scene_json: str,
    user_request: str,
    device_info: dict = None,
) -> str:
    """Build the user prompt with scene data and request."""

    device_context = ""
    if device_info:
        device_context = f"""
DEVICE INFO:
- Screen: {device_info.get('resolution', 'unknown')}
- Orientation: {device_info.get('orientation', 'landscape')}
- Type: {device_info.get('type', 'display')}
"""

    return f"""Generate a professional educational layout for this request:

USER REQUEST: {user_request}

SCENE DATA (use this data in your HTML):
{scene_json}
{device_context}

Generate the HTML and CSS following the requirements in your instructions.
"""
```

#### 1.3 Update CommandService

**File:** `app/services/commands.py` (modify existing)

```python
async def display_scene(
    self,
    device_id: UUID,
    scene: dict,
    custom_layout: Optional[dict] = None,  # NEW PARAMETER
) -> CommandResult:
    """
    Display a scene graph layout on the device screen.

    Args:
        device_id: Target device
        scene: Scene graph JSON (always included as fallback)
        custom_layout: Optional custom HTML/CSS layout (NEW)
    """
    parameters = {"scene": scene}

    if custom_layout:
        parameters["custom_layout"] = custom_layout

    return await self.send_command(
        device_id,
        CommandType.DISPLAY_SCENE,
        parameters
    )
```

#### 1.4 Update IntentService

**File:** `app/services/intent_service.py` (modify `_handle_display_content`)

```python
# After generating scene...
scene = await scene_service.generate_scene(...)
scene_dict = scene.model_dump(mode="json")

# NEW: Generate custom layout
custom_layout = await layout_generation_service.generate_layout(
    scene=scene,
    user_request=intent.original_text,
    context={"user_id": str(user_id)},
)

# Send both to device
custom_layout_dict = None
if custom_layout.fallback_reason is None:
    custom_layout_dict = custom_layout.to_dict()

result = await command_service.display_scene(
    device_id=target_device.id,
    scene=scene_dict,
    custom_layout=custom_layout_dict,
)
```

---

### Phase 2: Frontend Handling

#### 2.1 Raspberry Pi Renderer

**File:** (Raspberry Pi agent - to be created in Sprint 5.0)

```javascript
// Pseudo-code for Pi renderer

async function handleDisplayScene(message) {
    const { scene, custom_layout } = message.parameters;

    if (custom_layout && !custom_layout.fallback_reason) {
        try {
            // Try rendering custom layout
            await renderCustomLayout(custom_layout);
            console.log("Custom layout rendered successfully");
            return;
        } catch (error) {
            console.error("Custom layout failed, using fallback:", error);
            // Fall through to scene fallback
        }
    }

    // Fallback: render scene graph
    await renderSceneGraph(scene);
    console.log("Scene graph fallback rendered");
}

async function renderCustomLayout(layout) {
    const container = document.getElementById("display-container");

    // Inject scoped CSS
    const styleElement = document.createElement("style");
    styleElement.textContent = layout.css;
    document.head.appendChild(styleElement);

    // Inject HTML
    container.innerHTML = layout.html;

    // Validate rendering (optional: use Playwright for validation)
    await validateRendering(container);
}

async function validateRendering(container) {
    // Check for rendering errors
    // - Empty container
    // - Overlapping elements
    // - Text overflow
    // - Missing content

    if (container.children.length === 0) {
        throw new Error("Custom layout rendered empty");
    }

    // Additional Playwright checks can be added here
}
```

#### 2.2 Simulator Update

**File:** `app/routers/simulator.py` (or static JS)

Add handling for custom_layout in the simulator for development testing.

---

### Phase 3: Testing

#### 3.1 Unit Tests

```python
# tests/test_layout_generation.py

import pytest
from app.services.layout_generation_service import LayoutGenerationService
from app.ai.scene.schemas import SceneGraph, LayoutSpec, LayoutIntent

@pytest.fixture
def sample_scene():
    return SceneGraph(
        layout=LayoutSpec(intent=LayoutIntent.DASHBOARD),
        components=[...],
    )

class TestLayoutGenerationService:

    async def test_generate_layout_success(self, sample_scene):
        service = LayoutGenerationService()
        result = await service.generate_layout(
            scene=sample_scene,
            user_request="Show multiplication table for 7",
        )

        assert result.fallback_reason is None
        assert "<div" in result.html
        assert ".xentauri-layout" in result.css

    async def test_generate_layout_contains_data(self, sample_scene):
        """Verify that scene data is embedded in HTML."""
        service = LayoutGenerationService()
        result = await service.generate_layout(
            scene=sample_scene,
            user_request="Show my calendar",
        )

        # Check that event titles from scene are in HTML
        for component in sample_scene.components:
            if component.type == "calendar_week":
                for event in component.data.get("events", []):
                    assert event["title"] in result.html

    async def test_fallback_on_error(self):
        """Verify fallback_reason is set when generation fails."""
        # Mock API failure
        service = LayoutGenerationService()
        result = await service.generate_layout(
            scene=None,  # Invalid scene
            user_request="test",
        )

        assert result.fallback_reason is not None
```

#### 3.2 Integration Tests

```python
# tests/test_layout_integration.py

async def test_websocket_message_includes_both():
    """Verify WebSocket message contains scene AND custom_layout."""
    # Send intent
    # Capture WebSocket message
    # Assert both fields present
    pass

async def test_frontend_fallback():
    """Verify frontend falls back to scene when custom_layout fails."""
    # Send malformed custom_layout
    # Assert scene is rendered
    pass
```

---

## Educational Use Cases

### Examples

| Teacher Command | Generated Layout |
|-----------------|------------------|
| "Muestra la tabla del 7" | Color-coded multiplication grid with results |
| "Timeline de la Segunda Guerra Mundial" | Horizontal timeline with events, dates, images |
| "Diagrama del ciclo del agua" | Circular diagram with stages and arrows |
| "Conjugación del verbo 'ser'" | Table with tenses, pronouns, conjugations |
| "Fórmula cuadrática explicada" | Step-by-step cards with formula breakdown |
| "Mapa de los continentes" | Visual map with labels and facts |
| "Tabla periódica" | Interactive-looking periodic table grid |
| "Horario de clases" | Weekly schedule grid with colors per subject |

---

## Message Size Analysis

### Current (Scene Only)
- Average: 2-5 KB
- Maximum: ~10 KB (complex dashboard)

### With Custom Layout
- Scene: 2-5 KB
- Custom HTML: 5-30 KB
- Custom CSS: 3-10 KB
- **Total: 10-45 KB**

### WebSocket Limits
- FastAPI/Starlette default: 16 MB
- Browser default: ~16 MB
- Our max expected: ~50 KB

**Conclusion:** No optimization needed for MVP. WebSocket handles this easily.

---

## Future Optimizations (Post-MVP)

### 1. Compression (Reduces 60-70%)
```python
import gzip
import base64

compressed = base64.b64encode(gzip.compress(html.encode())).decode()
# 30KB → ~10KB
```

### 2. Template Caching
```python
# Cache generated templates by content type
cache_key = f"{scene.layout.intent}:{component_types_hash}"
cached_template = await cache.get(cache_key)
```

### 3. CSS Base Library
```css
/* Pre-loaded on Pi, reduces CSS sent per message */
.xentauri-grid { display: grid; }
.xentauri-card { border-radius: 12px; }
/* etc. */
```

### 4. Incremental Updates
```json
{
  "custom_layout": {
    "type": "update",
    "target": "#calendar-events",
    "html": "<li>New Event</li>"
  }
}
```

---

## Configuration

### Environment Variables

```bash
# Layout generation settings
LAYOUT_GENERATION_ENABLED=true
LAYOUT_GENERATION_MODEL=claude-sonnet-4.5
LAYOUT_GENERATION_MAX_TOKENS=4096
LAYOUT_GENERATION_TEMPERATURE=0.3
LAYOUT_GENERATION_TIMEOUT_MS=10000
```

### Feature Flags

```python
# app/core/config.py
class Settings:
    # Layout Generation
    LAYOUT_GENERATION_ENABLED: bool = True
    LAYOUT_GENERATION_MODEL: str = "claude-sonnet-4.5"
```

---

## Rollout Plan

### Phase 1: Backend Implementation
1. Create `LayoutGenerationService`
2. Create `layout_prompts.py`
3. Update `CommandService.display_scene()`
4. Update `IntentService._handle_display_content()`
5. Write unit tests

### Phase 2: Frontend Implementation
1. Update Simulator to handle `custom_layout`
2. Implement fallback logic
3. Test with various layouts

### Phase 3: Raspberry Pi Agent
1. Implement `handleDisplayScene()` with fallback
2. Add Playwright validation (optional)
3. Test on real hardware

### Phase 4: Testing & Iteration
1. Run 1000+ test cases
2. Measure latency and success rate
3. Tune prompts based on failures
4. Document edge cases

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Custom layout success rate | > 95% |
| Average generation time | < 2000ms |
| Fallback rate | < 5% |
| Message size (avg) | < 30KB |
| Teacher satisfaction | High (qualitative) |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| AI generates invalid HTML | Fallback to scene; improve prompts |
| Latency too high | UX loading animation; cache templates |
| Layout looks bad | Iterate on prompts; add examples |
| CSS conflicts | Scoped CSS with unique IDs |
| Large messages | Monitor size; compress if needed |

---

## References

- [Scene Graph Schemas](../app/ai/scene/schemas.py)
- [OpenAI Provider](../app/ai/providers/openai_provider.py)
- [Anthropic Provider](../app/ai/providers/anthropic_provider.py)
- [WebSocket Manager](../app/services/websocket_manager.py)
- [Command Service](../app/services/commands.py)
- [Intent Service](../app/services/intent_service.py)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-06 | Initial plan created |
