# Scene Graph Migration: Claude → Gemini 3 Flash

> **Status:** PLANNED
> **Created:** January 7, 2026
> **Sprint:** 5.4.0 (Proposed)
> **Priority:** High - Performance Optimization

## Overview

Migrar la generación de Scene Graph de Claude (Anthropic) a Gemini 3 Flash (Google) para reducir latencia de ~2-4 minutos a ~10-20 segundos.

---

## Problem Statement

| Métrica | Actual (Claude) | Objetivo (Gemini 3 Flash) |
|---------|-----------------|---------------------------|
| Latencia Scene Graph | ~30-60s | ~5-10s |
| Latencia Total (Scene + HTML) | ~4 min | ~40-70s |
| Costo por request | $$$ | $ |

---

## Architecture Change

### Actual

```
User Request
     │
     ▼
Claude Sonnet 4.5 → Scene Graph JSON (~30-60s)
     │
     ▼
GPT-5.2 → Custom HTML Layout (~2-3 min)
     │
     ▼
Total: ~4 minutos
```

### Propuesto

```
User Request
     │
     ▼
Gemini 3 Flash → Scene Graph JSON (~5-10s)
     │
     ▼
Sonnet 4.5 → Custom HTML Layout (~30-60s)
     │
     ▼
Total: ~40-70 segundos
```

---

## Implementation Plan

### Step 1: Add New Model in Config

**File:** `app/core/config.py`

**Location:** After line 92 (AI MODEL CONFIGURATION section)

```python
# ---------------------------------------------------------------------------
# AI MODEL CONFIGURATION
# ---------------------------------------------------------------------------
# Default models for each provider (can be overridden per-request)
GEMINI_MODEL: str = "gemini-2.5-flash"  # Fast, cheap orchestrator
GEMINI_SCENE_MODEL: str = "gemini-3-flash"  # Scene Graph generation (Sprint 5.4)
OPENAI_MODEL: str = "gpt-5.2"  # Capable model for complex tasks
ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"  # Most powerful Claude model
```

---

### Step 2: Add Schema-Based Generation to Gemini Provider

**File:** `app/ai/providers/gemini.py`

**Location:** After `generate_json()` method (after line 129)

```python
async def generate_scene_graph(
    self,
    prompt: str,
    system_prompt: Optional[str] = None,
    response_schema: Any = None,
    max_tokens: int = 4096,
    **kwargs
) -> AIResponse:
    """
    Generate Scene Graph JSON with optional schema validation.

    Sprint 5.4: Dedicated method for Scene Graph generation using
    Gemini's structured output with response_schema.

    Uses GEMINI_SCENE_MODEL (Gemini 3 Flash) for optimal performance.

    Args:
        prompt: Scene generation prompt
        system_prompt: System instructions (component registry, schema)
        response_schema: Optional Gemini schema for structured output
        max_tokens: Max output tokens (default 4096 for complex scenes)

    Returns:
        AIResponse with Scene Graph JSON
    """
    start_time = time.time()

    if not self._client:
        return self._error("API Key missing", start_time)

    try:
        # Use dedicated scene model
        scene_model = settings.GEMINI_SCENE_MODEL

        # Build config with optional schema
        config_params = {
            "temperature": 0.2,  # Low for consistent structure
            "max_output_tokens": max_tokens,
            "response_mime_type": "application/json",
            "system_instruction": system_prompt,
        }

        # Add schema if provided
        if response_schema:
            config_params["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_params)

        # Call Gemini 3 Flash
        response = self._client.models.generate_content(
            model=scene_model,
            contents=prompt,
            config=config
        )

        content = response.text.strip()

        # Clean markdown if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        latency_ms = self._measure_latency(start_time)
        usage = self._extract_usage(response)

        logger.info(
            f"Scene Graph generated in {latency_ms:.0f}ms using {scene_model}",
            extra={"tokens": usage.total_tokens}
        )

        return AIResponse(
            content=content,
            provider=self.provider_type,
            model=scene_model,
            usage=usage,
            latency_ms=latency_ms,
            success=True,
        )

    except Exception as e:
        logger.error(f"Scene Graph generation failed: {e}")
        return self._error(str(e), start_time)
```

---

### Step 3: Update Scene Service to Use Gemini

**File:** `app/ai/scene/service.py`

**Location:** Method `_generate_layout_via_claude()` (lines 285-387)

**Change:** Replace Claude with Gemini

```python
async def _generate_layout_via_gemini(
    self,
    hints: List[LayoutHint],
    info_type: str,
    user_request: str,
    target_devices: List[str],
    realtime_data: Dict[str, Any] = None,
    conversation_context: Dict[str, Any] = None,
) -> SceneGraph:
    """
    Use Gemini 3 Flash to generate a creative layout.

    Sprint 5.4: Migrated from Claude to Gemini for faster generation.

    Args:
        hints: Normalized layout hints
        info_type: Content type
        user_request: Original user request
        target_devices: Target device IDs
        realtime_data: Pre-fetched real-time data
        conversation_context: Previous conversation history

    Returns:
        SceneGraph from Gemini's response
    """
    from app.ai.providers.gemini import gemini_provider
    from app.ai.prompts.scene_prompts import (
        build_scene_system_prompt,
        build_scene_generation_prompt,
    )

    # Build prompts (same as before)
    system_prompt = build_scene_system_prompt(
        components_context=component_registry.to_prompt_context()
    )

    generation_prompt = build_scene_generation_prompt(
        user_request=user_request,
        layout_hints=hints,
        info_type=info_type,
        device_count=len(target_devices),
        realtime_data=realtime_data or {},
        conversation_context=conversation_context or {},
    )

    logger.debug("Calling Gemini 3 Flash for scene generation")

    # Call Gemini instead of Claude
    response = await gemini_provider.generate_scene_graph(
        prompt=generation_prompt,
        system_prompt=system_prompt,
        # response_schema=SCENE_GRAPH_SCHEMA,  # Optional: Enable later
    )

    if not response.success:
        raise Exception(f"Gemini generation failed: {response.error}")

    # Parse response into SceneGraph (same logic as before)
    try:
        scene_data = json.loads(response.content)

        # Check for error response
        if "error" in scene_data and "message" in scene_data:
            raise Exception(scene_data.get("message", "Unknown error"))

        scene = self._parse_scene_response(
            scene_data,
            target_devices,
            user_request,
            generated_by_model=response.model
        )
        return scene

    except json.JSONDecodeError as e:
        logger.error(f"Gemini JSON parsing failed: {e}")
        raise Exception(f"Gemini returned invalid JSON: {e}")
```

**Also update `generate_scene()` to call the new method:**

```python
# Line 137-145: Change from
scene = await self._generate_layout_via_claude(...)

# To
scene = await self._generate_layout_via_gemini(...)
```

---

### Step 4: Add Environment Variable

**File:** `.env`

```bash
# Scene Graph Generation Model (Sprint 5.4)
GEMINI_SCENE_MODEL=gemini-3-flash
```

---

### Step 5: Update Custom Layout Service (Optional)

If you want to also change the HTML generation from GPT-5.2 to Sonnet 4.5:

**File:** `app/ai/scene/custom_layout/service.py`

**Change:** Line 144

```python
# From
response = await openai_provider.generate(...)

# To
response = await anthropic_provider.generate(...)
```

---

## Model Roles After Migration

| Task | Current Model | New Model | Latency |
|------|---------------|-----------|---------|
| Intent Parsing | Gemini 2.5 Flash | Gemini 2.5 Flash (no change) | ~1-2s |
| Scene Graph | Claude Sonnet 4.5 | **Gemini 3 Flash** | ~5-10s |
| Custom HTML | GPT-5.2 | **Sonnet 4.5** | ~30-60s |
| JSON Repair | Gemini 2.5 Flash | Gemini 2.5 Flash (no change) | ~2-3s |

---

## Files to Modify

| File | Change |
|------|--------|
| `app/core/config.py` | Add `GEMINI_SCENE_MODEL` |
| `app/ai/providers/gemini.py` | Add `generate_scene_graph()` method |
| `app/ai/scene/service.py` | Replace `_generate_layout_via_claude` with `_generate_layout_via_gemini` |
| `.env` | Add `GEMINI_SCENE_MODEL=gemini-3-flash` |

---

## Optional: Structured Schema

If you want to enforce Scene Graph structure with Gemini's `response_schema`:

**File:** `app/ai/scene/gemini_schema.py` (new file)

```python
"""
Gemini Schema for Scene Graph - Structured output validation.

Sprint 5.4: Defines the expected JSON structure for Gemini's
response_schema parameter.
"""

from google.genai import types

SCENE_GRAPH_GEMINI_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "scene_id": types.Schema(type=types.Type.STRING),
        "version": types.Schema(type=types.Type.STRING),
        "layout": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "intent": types.Schema(
                    type=types.Type.STRING,
                    enum=["fullscreen", "two_column", "three_column",
                          "sidebar", "dashboard", "overlay", "stack"]
                ),
                "engine": types.Schema(
                    type=types.Type.STRING,
                    enum=["grid", "flex", "absolute"]
                ),
                "columns": types.Schema(type=types.Type.INTEGER),
                "rows": types.Schema(type=types.Type.INTEGER),
                "gap": types.Schema(type=types.Type.STRING),
            },
            required=["intent", "engine"]
        ),
        "components": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "id": types.Schema(type=types.Type.STRING),
                    "type": types.Schema(type=types.Type.STRING),
                    "priority": types.Schema(
                        type=types.Type.STRING,
                        enum=["primary", "secondary", "tertiary"]
                    ),
                    "position": types.Schema(type=types.Type.OBJECT),
                    "style": types.Schema(type=types.Type.OBJECT),
                    "props": types.Schema(type=types.Type.OBJECT),
                    "data": types.Schema(type=types.Type.OBJECT),
                },
                required=["id", "type"]
            )
        ),
        "global_style": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "background": types.Schema(type=types.Type.STRING),
                "font_family": types.Schema(type=types.Type.STRING),
                "text_color": types.Schema(type=types.Type.STRING),
                "accent_color": types.Schema(type=types.Type.STRING),
            }
        ),
        "metadata": types.Schema(type=types.Type.OBJECT),
    },
    required=["layout", "components"]
)
```

**Usage:**

```python
from app.ai.scene.gemini_schema import SCENE_GRAPH_GEMINI_SCHEMA

response = await gemini_provider.generate_scene_graph(
    prompt=generation_prompt,
    system_prompt=system_prompt,
    response_schema=SCENE_GRAPH_GEMINI_SCHEMA,  # Enforce structure
)
```

---

## Testing Checklist

### Unit Tests
- [ ] `gemini_provider.generate_scene_graph()` returns valid JSON
- [ ] Scene Graph parses correctly into `SceneGraph` model
- [ ] Error handling works when Gemini fails

### Integration Tests
- [ ] Full flow: Intent → Gemini Scene → Sonnet HTML → WebSocket
- [ ] Latency is < 70 seconds total
- [ ] Fallback to default scene works if Gemini fails

### Manual Tests
- [ ] "Muestra el calendario" → Scene generated in ~10s
- [ ] Complex layout "calendario izquierda, clima derecha" → Works
- [ ] Conversation context preserved correctly

---

## Latency Comparison

| Flow | Before | After | Improvement |
|------|--------|-------|-------------|
| Scene Graph only | ~30-60s | ~5-10s | **80% faster** |
| Scene + Custom HTML | ~4 min | ~40-70s | **75% faster** |

---

## Rollback Plan

Si hay problemas con Gemini:

1. Cambiar `_generate_layout_via_gemini` → `_generate_layout_via_claude`
2. O agregar feature flag:

```python
# config.py
USE_GEMINI_FOR_SCENE: bool = True

# scene/service.py
if settings.USE_GEMINI_FOR_SCENE:
    scene = await self._generate_layout_via_gemini(...)
else:
    scene = await self._generate_layout_via_claude(...)
```

---

## References

- [Gemini Provider](../../app/ai/providers/gemini.py)
- [Scene Service](../../app/ai/scene/service.py)
- [Scene Prompts](../../app/ai/prompts/scene_prompts.py)
- [Config](../../app/core/config.py)
- [Custom Layout Service](../../app/ai/scene/custom_layout/service.py)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-07 | Initial plan created |
