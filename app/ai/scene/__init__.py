"""
Scene Graph module - Dynamic layout generation for display devices.

Sprint 4.0: Enables creative, user-defined layouts via natural language.

The Scene Graph system allows users to request custom layouts like:
- "Show my calendar on the left with a clock in the corner"
- "Display a dashboard with weather, clock, and calendar"
- "Fullscreen agenda view"

Architecture:
=============
1. User request → IntentParser extracts DisplayContentIntent
2. DisplayContentIntent includes layout_hints (e.g., ["calendar left", "clock corner"])
3. SceneService generates layout via Claude or uses defaults
4. Data is fetched for each component (calendar events, etc.)
5. Complete SceneGraph is sent to device via WebSocket

Example:
    from app.ai.scene import scene_service, LayoutHint
    
    # Generate a scene
    scene = await scene_service.generate_scene(
        layout_hints=[LayoutHint(component="calendar", position="left")],
        info_type="calendar",
        target_devices=["device-uuid"],
        user_id="user-uuid",
        user_request="calendar on the left",
        db=db,
    )
    
    # Send to device
    await command_service.send_command(
        device_id=device_id,
        command_type="display_scene",
        payload=scene.model_dump()
    )

Components:
===========
- schemas.py: Pydantic models for Scene Graph structure
- registry.py: Available display components (calendar_week, clock_digital, etc.)
- defaults.py: Predefined scene templates for common requests
- service.py: Scene generation and data population
- prompts/scene_prompts.py: Claude prompts for custom layouts
"""

from app.ai.scene.schemas import (
    SceneGraph,
    SceneComponent,
    LayoutSpec,
    LayoutIntent,
    LayoutEngine,
    ComponentPriority,
    ComponentPosition,
    ComponentStyle,
    SceneMetadata,
    LayoutHint,
    GlobalStyle,
)
from app.ai.scene.registry import (
    ComponentRegistry,
    ComponentDefinition,
    ComponentCategory,
    component_registry,
)
from app.ai.scene.service import SceneService, scene_service
from app.ai.scene.defaults import (
    get_default_scene,
    get_default_scene_template,
    detect_default_scene_type,
    DefaultSceneType,
)


__all__ = [
    # Schemas
    "SceneGraph",
    "SceneComponent",
    "LayoutSpec",
    "LayoutIntent",
    "LayoutEngine",
    "ComponentPriority",
    "ComponentPosition",
    "ComponentStyle",
    "SceneMetadata",
    "LayoutHint",
    "GlobalStyle",
    # Registry
    "ComponentRegistry",
    "ComponentDefinition",
    "ComponentCategory",
    "component_registry",
    # Service
    "SceneService",
    "scene_service",
    # Defaults
    "get_default_scene",
    "get_default_scene_template",
    "detect_default_scene_type",
    "DefaultSceneType",
]
