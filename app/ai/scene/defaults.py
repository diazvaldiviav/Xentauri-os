"""
Default Scenes - Predefined Scene Graph templates for common requests.

Sprint 4.0: When users request simple layouts (fullscreen calendar, etc.),
we use these presets instead of calling Claude, saving time and cost.

These defaults serve as:
1. Quick responses for common requests
2. Fallback when Claude generation fails
3. Templates for learning common patterns

Usage:
======
    from app.ai.scene.defaults import get_default_scene, DefaultSceneType
    
    # Get a preset scene
    scene = await get_default_scene(
        scene_type=DefaultSceneType.CALENDAR_FULLSCREEN,
        target_devices=["device-uuid"],
        user_id="user-uuid",
        user_request="show my calendar fullscreen",
        db=db,
    )
"""

import logging
from enum import Enum
from typing import Optional, List
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.scene.schemas import (
    SceneGraph,
    SceneComponent,
    LayoutSpec,
    LayoutIntent,
    LayoutEngine,
    ComponentPriority,
    ComponentPosition,
    ComponentStyle,
    GlobalStyle,
    SceneMetadata,
)


logger = logging.getLogger("jarvis.ai.scene.defaults")


# ---------------------------------------------------------------------------
# DEFAULT SCENE TYPES
# ---------------------------------------------------------------------------

class DefaultSceneType(str, Enum):
    """Types of predefined scenes available."""
    CALENDAR_FULLSCREEN = "calendar_fullscreen"      # Single calendar filling screen
    CALENDAR_SIDEBAR = "calendar_sidebar"            # Calendar + clock sidebar
    CALENDAR_AGENDA = "agenda_fullscreen"            # Agenda list fullscreen
    DASHBOARD = "dashboard"                          # 2x2 grid with multiple widgets
    CLOCK_FULLSCREEN = "clock_fullscreen"            # Large clock display


# ---------------------------------------------------------------------------
# SCENE TEMPLATES (without data - data added by service)
# ---------------------------------------------------------------------------

def _create_calendar_fullscreen_template(
    target_devices: List[str],
    user_request: str,
) -> SceneGraph:
    """
    Create a fullscreen calendar week view.
    
    Layout: Single calendar_week component filling the entire screen.
    Best for: "show my calendar", "display my schedule"
    """
    return SceneGraph(
        scene_id=str(uuid4()),
        target_devices=target_devices,
        layout=LayoutSpec(
            intent=LayoutIntent.FULLSCREEN,
            engine=LayoutEngine.FLEX,
        ),
        components=[
            SceneComponent(
                id="calendar_main",
                type="calendar_week",
                priority=ComponentPriority.PRIMARY,
                position=ComponentPosition(flex=1),
                props={
                    "show_times": True,
                    "start_hour": 7,
                    "end_hour": 21,
                },
                style=ComponentStyle(
                    background="#1a1a2e",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
        ],
        global_style=GlobalStyle(
            background="#0f0f23",
            font_family="Inter",
        ),
        metadata=SceneMetadata(
            user_request=user_request,
            generated_by="default",
            refresh_seconds=300,
        ),
    )


def _create_calendar_sidebar_template(
    target_devices: List[str],
    user_request: str,
) -> SceneGraph:
    """
    Create a calendar with clock sidebar layout.
    
    Layout: 3-column grid with calendar (columns 1-3) and clock (column 4).
    Best for: "calendar on the left with clock", "show calendar and time"
    """
    return SceneGraph(
        scene_id=str(uuid4()),
        target_devices=target_devices,
        layout=LayoutSpec(
            intent=LayoutIntent.SIDEBAR,
            engine=LayoutEngine.GRID,
            columns=4,
            rows=1,
            gap="16px",
        ),
        components=[
            SceneComponent(
                id="calendar_main",
                type="calendar_week",
                priority=ComponentPriority.PRIMARY,
                position=ComponentPosition(grid_column="1 / 4", grid_row="1"),
                props={
                    "show_times": True,
                    "start_hour": 8,
                    "end_hour": 20,
                },
                style=ComponentStyle(
                    background="#1a1a2e",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
            SceneComponent(
                id="clock_sidebar",
                type="clock_digital",
                priority=ComponentPriority.SECONDARY,
                position=ComponentPosition(grid_column="4", grid_row="1"),
                props={
                    "format": "12h",
                    "show_seconds": False,
                    "show_date": True,
                },
                style=ComponentStyle(
                    background="#16213e",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
        ],
        global_style=GlobalStyle(
            background="#0f0f23",
            font_family="Inter",
        ),
        metadata=SceneMetadata(
            user_request=user_request,
            generated_by="default",
            refresh_seconds=300,
        ),
    )


def _create_agenda_fullscreen_template(
    target_devices: List[str],
    user_request: str,
) -> SceneGraph:
    """
    Create a fullscreen agenda list view.
    
    Layout: Single calendar_agenda component filling the screen.
    Best for: "show my agenda", "list my upcoming events"
    """
    return SceneGraph(
        scene_id=str(uuid4()),
        target_devices=target_devices,
        layout=LayoutSpec(
            intent=LayoutIntent.FULLSCREEN,
            engine=LayoutEngine.FLEX,
        ),
        components=[
            SceneComponent(
                id="agenda_main",
                type="calendar_agenda",
                priority=ComponentPriority.PRIMARY,
                position=ComponentPosition(flex=1),
                props={
                    "max_events": 15,
                    "show_descriptions": True,
                    "group_by_day": True,
                },
                style=ComponentStyle(
                    background="#1a1a2e",
                    text_color="#ffffff",
                    border_radius="12px",
                    padding="24px",
                ),
            ),
        ],
        global_style=GlobalStyle(
            background="#0f0f23",
            font_family="Inter",
        ),
        metadata=SceneMetadata(
            user_request=user_request,
            generated_by="default",
            refresh_seconds=300,
        ),
    )


def _create_dashboard_template(
    target_devices: List[str],
    user_request: str,
) -> SceneGraph:
    """
    Create a 2x2 dashboard with multiple widgets.
    
    Layout: 2x2 grid with calendar widget, clock, weather, and agenda.
    Best for: "show a dashboard", "display multiple widgets"
    """
    return SceneGraph(
        scene_id=str(uuid4()),
        target_devices=target_devices,
        layout=LayoutSpec(
            intent=LayoutIntent.DASHBOARD,
            engine=LayoutEngine.GRID,
            columns=2,
            rows=2,
            gap="16px",
        ),
        components=[
            SceneComponent(
                id="calendar_widget",
                type="calendar_widget",
                priority=ComponentPriority.PRIMARY,
                position=ComponentPosition(grid_column="1", grid_row="1"),
                props={
                    "max_events": 5,
                    "show_date": True,
                },
                style=ComponentStyle(
                    background="#1a1a2e",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
            SceneComponent(
                id="clock_widget",
                type="clock_digital",
                priority=ComponentPriority.SECONDARY,
                position=ComponentPosition(grid_column="2", grid_row="1"),
                props={
                    "format": "12h",
                    "show_seconds": False,
                    "show_date": True,
                },
                style=ComponentStyle(
                    background="#16213e",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
            SceneComponent(
                id="weather_widget",
                type="weather_current",
                priority=ComponentPriority.SECONDARY,
                position=ComponentPosition(grid_column="1", grid_row="2"),
                props={
                    "units": "fahrenheit",
                    "show_forecast": False,
                },
                style=ComponentStyle(
                    background="#0f3460",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
            SceneComponent(
                id="agenda_widget",
                type="calendar_agenda",
                priority=ComponentPriority.SECONDARY,
                position=ComponentPosition(grid_column="2", grid_row="2"),
                props={
                    "max_events": 5,
                    "show_descriptions": False,
                },
                style=ComponentStyle(
                    background="#1a1a2e",
                    text_color="#ffffff",
                    border_radius="12px",
                ),
            ),
        ],
        global_style=GlobalStyle(
            background="#0f0f23",
            font_family="Inter",
        ),
        metadata=SceneMetadata(
            user_request=user_request,
            generated_by="default",
            refresh_seconds=300,
        ),
    )


def _create_clock_fullscreen_template(
    target_devices: List[str],
    user_request: str,
) -> SceneGraph:
    """
    Create a fullscreen clock display.
    
    Layout: Large clock centered on screen.
    Best for: "show the clock", "display the time"
    """
    return SceneGraph(
        scene_id=str(uuid4()),
        target_devices=target_devices,
        layout=LayoutSpec(
            intent=LayoutIntent.FULLSCREEN,
            engine=LayoutEngine.FLEX,
            justify="center",
            align="center",
        ),
        components=[
            SceneComponent(
                id="clock_main",
                type="clock_digital",
                priority=ComponentPriority.PRIMARY,
                position=ComponentPosition(flex=1, align_self="center"),
                props={
                    "format": "12h",
                    "show_seconds": True,
                    "show_date": True,
                },
                style=ComponentStyle(
                    background="transparent",
                    text_color="#ffffff",
                ),
            ),
        ],
        global_style=GlobalStyle(
            background="#0f0f23",
            font_family="Inter",
        ),
        metadata=SceneMetadata(
            user_request=user_request,
            generated_by="default",
            refresh_seconds=60,  # Clocks can refresh more frequently
        ),
    )


# ---------------------------------------------------------------------------
# TEMPLATE REGISTRY
# ---------------------------------------------------------------------------

_SCENE_TEMPLATES = {
    DefaultSceneType.CALENDAR_FULLSCREEN: _create_calendar_fullscreen_template,
    DefaultSceneType.CALENDAR_SIDEBAR: _create_calendar_sidebar_template,
    DefaultSceneType.CALENDAR_AGENDA: _create_agenda_fullscreen_template,
    DefaultSceneType.DASHBOARD: _create_dashboard_template,
    DefaultSceneType.CLOCK_FULLSCREEN: _create_clock_fullscreen_template,
}


# ---------------------------------------------------------------------------
# DETECTION LOGIC
# ---------------------------------------------------------------------------

def detect_default_scene_type(
    info_type: str,
    layout_hints: Optional[List[str]] = None,
    user_request: Optional[str] = None,
) -> Optional[DefaultSceneType]:
    """
    Detect which default scene type to use based on intent data.

    Sprint 4.4.0: Now returns None when custom generation is needed
    (e.g., when user requests generated content, not just display).
    Also analyzes the original user_request for generation keywords.

    This function analyzes the info_type and layout_hints from a
    DisplayContentIntent to determine the appropriate default scene.

    Args:
        info_type: Content type (calendar, weather, mixed)
        layout_hints: List of layout hints from user request
        user_request: Original user request text (Sprint 4.4.0)

    Returns:
        Most appropriate DefaultSceneType, or None if Claude should generate

    Examples:
        detect_default_scene_type("calendar", []) → CALENDAR_FULLSCREEN
        detect_default_scene_type("calendar", ["sidebar"]) → CALENDAR_SIDEBAR
        detect_default_scene_type("mixed", ["dashboard"]) → DASHBOARD
        detect_default_scene_type("calendar", ["left", "right"], "crea plan") → None (needs Claude)
    """
    hints_lower = [h.lower() for h in (layout_hints or [])]
    info_lower = info_type.lower() if info_type else "calendar"

    # Join all hints for pattern matching
    hints_text = " ".join(hints_lower)

    # Sprint 4.4.0 - CRITICAL: Detect content generation keywords
    # Check BOTH layout_hints AND original user_request
    # (keywords might be in request but not extracted as layout hints)
    generation_keywords = [
        "crea", "genera", "create", "generate", "make", "build",
        "plan", "ideas", "suggestions", "checklist", "summary",
        "resume", "resumen", "list", "outline",
    ]

    # Check layout hints
    has_generation_in_hints = any(kw in hints_text for kw in generation_keywords)

    # Check original user request (if provided)
    has_generation_in_request = False
    if user_request:
        request_lower = user_request.lower()
        has_generation_in_request = any(kw in request_lower for kw in generation_keywords)

    has_generation_request = has_generation_in_hints or has_generation_in_request

    if has_generation_request:
        source = "hints" if has_generation_in_hints else "user_request"
        logger.info(f"Detected content generation keywords in {source}. Skipping defaults, will use Claude.")
        return None  # Force Claude generation
    
    # Check for dashboard keywords
    if "dashboard" in hints_text:
        return DefaultSceneType.DASHBOARD
    
    # Check for sidebar/two-panel layouts
    if any(word in hints_text for word in ["sidebar", "left", "right", "corner", "clock"]):
        if "calendar" in hints_text or "calendar" in info_lower:
            return DefaultSceneType.CALENDAR_SIDEBAR
    
    # Check for agenda
    if "agenda" in hints_text or "list" in hints_text:
        return DefaultSceneType.CALENDAR_AGENDA
    
    # Check for clock-only
    if info_lower == "clock" or ("clock" in hints_text and "calendar" not in hints_text):
        return DefaultSceneType.CLOCK_FULLSCREEN
    
    # Default based on info_type
    if info_lower in ("calendar", "schedule", "events"):
        return DefaultSceneType.CALENDAR_FULLSCREEN
    
    if info_lower == "mixed":
        # For mixed content, use dashboard
        return DefaultSceneType.DASHBOARD
    
    # Fallback to fullscreen calendar
    return DefaultSceneType.CALENDAR_FULLSCREEN


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def get_default_scene_template(
    scene_type: DefaultSceneType,
    target_devices: List[str],
    user_request: str,
) -> SceneGraph:
    """
    Get a default scene template (without data).
    
    This returns the template structure without fetching data.
    Use scene_service.populate_scene_data() to add data.
    
    Args:
        scene_type: Which default scene to create
        target_devices: List of device IDs
        user_request: Original user request for metadata
        
    Returns:
        SceneGraph template (components have empty data)
    """
    template_fn = _SCENE_TEMPLATES.get(scene_type)
    if not template_fn:
        logger.warning(f"Unknown scene type: {scene_type}, falling back to calendar_fullscreen")
        template_fn = _SCENE_TEMPLATES[DefaultSceneType.CALENDAR_FULLSCREEN]
    
    return template_fn(target_devices, user_request)


async def get_default_scene(
    scene_type: DefaultSceneType,
    target_devices: List[str],
    user_id: str,
    user_request: str,
    db: Session,
) -> SceneGraph:
    """
    Get a complete default scene with populated data.
    
    This is the main entry point for getting default scenes.
    It creates the template and then fetches data for all components.
    
    Args:
        scene_type: Which default scene to create
        target_devices: List of device IDs
        user_id: User ID for data fetching (OAuth credentials)
        user_request: Original user request for metadata
        db: Database session
        
    Returns:
        Complete SceneGraph with data
        
    Example:
        scene = await get_default_scene(
            scene_type=DefaultSceneType.CALENDAR_SIDEBAR,
            target_devices=["device-123"],
            user_id="user-456",
            user_request="calendar with clock",
            db=db,
        )
    """
    # Import here to avoid circular imports
    from app.ai.scene.service import scene_service
    
    # Get the template
    scene = get_default_scene_template(scene_type, target_devices, user_request)
    
    # Populate data for all components
    scene = await scene_service.populate_scene_data(
        scene=scene,
        user_id=user_id,
        db=db,
    )
    
    logger.info(
        f"Created default scene: {scene_type.value}",
        extra={
            "scene_id": scene.scene_id,
            "component_count": len(scene.components),
            "user_id": user_id,
        }
    )
    
    return scene


def list_default_scene_types() -> List[str]:
    """Get list of all available default scene types."""
    return [t.value for t in DefaultSceneType]
