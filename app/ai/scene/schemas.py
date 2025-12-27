"""
Scene Graph Schemas - Pydantic models for dynamic layout generation.

Sprint 4.0: Scene Graph enables creative, user-defined layouts for display devices.
The Scene Graph is a structured JSON that describes WHAT to display, WHERE to position it,
and includes the ACTUAL DATA to render.

Design Philosophy:
==================
- Semantic Intents: Layout intents describe user goals (dashboard, sidebar)
- Technical Engines: Layout engines map to CSS implementations (grid, flex)
- Embedded Data: Each component includes its data (no client-side fetching)
- Priority System: Components have priorities for responsive behavior
- Self-Documenting: Field descriptions provide Claude with generation context

Example Scene Graph:
    {
        "scene_id": "uuid",
        "layout": {"intent": "sidebar", "engine": "grid"},
        "components": [
            {"id": "cal", "type": "calendar_week", "data": {"events": [...]}}
        ]
    }
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LAYOUT ENUMS
# ---------------------------------------------------------------------------

class LayoutIntent(str, Enum):
    """
    Semantic layout intents that describe user goals.
    
    These are high-level descriptions of what the user wants,
    not how it's implemented technically.
    
    The AI (Claude) uses these to understand user requests like:
    - "calendar on the left" → SIDEBAR
    - "dashboard with widgets" → DASHBOARD
    - "fullscreen calendar" → FULLSCREEN
    """
    FULLSCREEN = "fullscreen"       # Single component fills screen
    TWO_COLUMN = "two_column"       # Two equal columns
    THREE_COLUMN = "three_column"   # Three equal columns
    SIDEBAR = "sidebar"             # Main content + sidebar (70/30 or 80/20)
    DASHBOARD = "dashboard"         # Grid of widgets (2x2, 3x2)
    OVERLAY = "overlay"             # Component layered over another
    STACK = "stack"                 # Vertical stack of components


class LayoutEngine(str, Enum):
    """
    Technical layout engine types that map to CSS implementations.
    
    The Raspberry Pi frontend uses these to render layouts:
    - grid: CSS Grid for multi-component layouts
    - flex: Flexbox for single-direction layouts
    - absolute: Absolute positioning for overlays
    """
    GRID = "grid"           # CSS Grid - multi-component layouts
    FLEX = "flex"           # Flexbox - single direction layouts
    ABSOLUTE = "absolute"   # Position absolute - overlays, corners


class ComponentPriority(str, Enum):
    """
    Component priority levels for responsive behavior.
    
    When screen space is limited, the frontend uses priorities:
    - PRIMARY: Never hidden, receives focus
    - SECONDARY: May shrink on small screens
    - TERTIARY: May hide on mobile/small screens
    """
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


# ---------------------------------------------------------------------------
# LAYOUT HINT (from user input)
# ---------------------------------------------------------------------------

class LayoutHint(BaseModel):
    """
    A parsed layout hint from user's natural language request.
    
    Example transformations:
        "calendar left" → LayoutHint(component="calendar", position="left")
        "clock corner" → LayoutHint(component="clock", position="corner")
        "weather small" → LayoutHint(component="weather", size="small")
    
    Attributes:
        component: Component type or category (calendar, clock, weather)
        position: Desired position (left, right, corner, center, top, bottom)
        size: Desired size (small, large, fullscreen)
        raw_hint: Original hint string for debugging
    """
    component: str = Field(description="Component type or category (e.g., 'calendar', 'clock')")
    position: Optional[str] = Field(default=None, description="Position hint: left, right, corner, center, top, bottom")
    size: Optional[str] = Field(default=None, description="Size hint: small, large, fullscreen")
    raw_hint: Optional[str] = Field(default=None, description="Original hint string")


# ---------------------------------------------------------------------------
# COMPONENT POSITIONING
# ---------------------------------------------------------------------------

class ComponentPosition(BaseModel):
    """
    Component position specification for various layout engines.
    
    Supports multiple layout engine types with appropriate properties.
    The frontend interprets these based on the layout.engine setting.
    
    For Grid Engine:
        position = ComponentPosition(grid_column="1 / 3", grid_row="1")
        
    For Flex Engine:
        position = ComponentPosition(flex=1, align_self="stretch")
        
    For Absolute Engine:
        position = ComponentPosition(top="10px", right="10px")
    """
    # Grid positioning (CSS Grid)
    grid_column: Optional[str] = Field(default=None, description="CSS grid-column value (e.g., '1 / 3')")
    grid_row: Optional[str] = Field(default=None, description="CSS grid-row value (e.g., '1 / 2')")
    grid_area: Optional[str] = Field(default=None, description="CSS grid-area name")
    
    # Flex positioning (Flexbox)
    flex: Optional[int] = Field(default=None, description="Flex grow value (1, 2, etc.)")
    align_self: Optional[str] = Field(default=None, description="CSS align-self value")
    order: Optional[int] = Field(default=None, description="CSS order value")
    
    # Absolute positioning
    top: Optional[str] = Field(default=None, description="CSS top value (e.g., '10px', '5%')")
    right: Optional[str] = Field(default=None, description="CSS right value")
    bottom: Optional[str] = Field(default=None, description="CSS bottom value")
    left: Optional[str] = Field(default=None, description="CSS left value")
    z_index: Optional[int] = Field(default=None, description="CSS z-index for layering")


# ---------------------------------------------------------------------------
# COMPONENT STYLING
# ---------------------------------------------------------------------------

class ComponentStyle(BaseModel):
    """
    Visual styling for a component.
    
    These are applied to the component's container for consistent theming.
    The Raspberry Pi frontend interprets these as CSS-like properties.
    
    Example:
        style = ComponentStyle(
            background="#1a1a2e",
            text_color="#ffffff",
            border_radius="12px",
            padding="16px"
        )
    """
    background: Optional[str] = Field(default=None, description="Background color (hex or CSS value)")
    text_color: Optional[str] = Field(default=None, description="Primary text color")
    accent_color: Optional[str] = Field(default=None, description="Accent/highlight color")
    border_radius: Optional[str] = Field(default=None, description="Border radius (e.g., '12px')")
    border: Optional[str] = Field(default=None, description="Border CSS value")
    padding: Optional[str] = Field(default=None, description="Padding value")
    shadow: Optional[str] = Field(default=None, description="Box shadow CSS value")
    opacity: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Opacity 0-1")


# ---------------------------------------------------------------------------
# LAYOUT SPECIFICATION
# ---------------------------------------------------------------------------

class LayoutSpec(BaseModel):
    """
    Complete layout specification for a Scene Graph.
    
    Combines semantic intent with technical engine configuration.
    Claude generates these based on user requests.
    
    Example:
        layout = LayoutSpec(
            intent=LayoutIntent.SIDEBAR,
            engine=LayoutEngine.GRID,
            columns=4,
            gap="16px"
        )
    """
    # Semantic intent (what user wants)
    intent: LayoutIntent = Field(description="Semantic layout intent: fullscreen, sidebar, dashboard, etc.")
    
    # Technical engine (how to render)
    engine: LayoutEngine = Field(default=LayoutEngine.GRID, description="CSS engine: grid, flex, absolute")
    
    # Grid configuration
    columns: Optional[int] = Field(default=None, ge=1, le=12, description="Number of grid columns (1-12)")
    rows: Optional[int] = Field(default=None, ge=1, le=12, description="Number of grid rows (1-12)")
    gap: Optional[str] = Field(default="16px", description="Gap between grid items")
    
    # Flex configuration
    direction: Optional[str] = Field(default=None, description="Flex direction: row, column")
    justify: Optional[str] = Field(default=None, description="Justify content CSS value")
    align: Optional[str] = Field(default=None, description="Align items CSS value")


# ---------------------------------------------------------------------------
# SCENE COMPONENT
# ---------------------------------------------------------------------------

class SceneComponent(BaseModel):
    """
    Individual component within a Scene Graph.
    
    A component represents a single UI widget (calendar, clock, weather)
    with its type, positioning, styling, props, and embedded data.
    
    CRITICAL: The 'data' field contains the actual content to display.
    This is fetched by the service before sending to the device,
    so the Raspberry Pi doesn't need to make any API calls.
    
    Example:
        component = SceneComponent(
            id="calendar_main",
            type="calendar_week",
            priority=ComponentPriority.PRIMARY,
            position=ComponentPosition(grid_column="1 / 3"),
            props={"show_times": True, "start_hour": 8},
            data={"events": [...fetched calendar events...]}
        )
    """
    # Identification
    id: str = Field(description="Unique component ID within the scene (e.g., 'calendar_main')")
    type: str = Field(description="Component type from registry (e.g., 'calendar_week', 'clock_digital')")
    
    # Priority for responsive behavior
    priority: ComponentPriority = Field(
        default=ComponentPriority.SECONDARY,
        description="Render priority: primary (never hide), secondary (may shrink), tertiary (may hide)"
    )
    
    # Positioning
    position: ComponentPosition = Field(
        default_factory=ComponentPosition,
        description="Position specification based on layout engine"
    )
    
    # Visual styling
    style: Optional[ComponentStyle] = Field(default=None, description="Optional visual styling overrides")
    
    # Component-specific configuration
    props: Dict[str, Any] = Field(
        default_factory=dict,
        description="Component-specific props (e.g., show_times, format)"
    )
    
    # Embedded data (populated by service before sending)
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Actual data to display (events, timezone, weather, etc.)"
    )


# ---------------------------------------------------------------------------
# SCENE METADATA
# ---------------------------------------------------------------------------

class SceneMetadata(BaseModel):
    """
    Metadata for a Scene Graph.
    
    Tracks when the scene was created, how it should refresh,
    and the original user request for debugging.
    """
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the scene was generated"
    )
    refresh_seconds: int = Field(
        default=300,
        ge=30,
        description="How often to refresh data (seconds, minimum 30)"
    )
    user_request: Optional[str] = Field(
        default=None,
        description="Original user request that generated this scene"
    )
    generated_by: Optional[str] = Field(
        default=None,
        description="Model that generated the scene (e.g., 'claude_sonnet', 'default')"
    )
    layout_hints_used: Optional[List[str]] = Field(
        default=None,
        description="Layout hints that were used for generation"
    )


# ---------------------------------------------------------------------------
# GLOBAL STYLE
# ---------------------------------------------------------------------------

class GlobalStyle(BaseModel):
    """
    Global styling applied to the entire scene.
    
    Sets defaults that individual components can override.
    """
    background: str = Field(default="#0f0f23", description="Scene background color")
    font_family: str = Field(default="Inter", description="Default font family")
    text_color: str = Field(default="#ffffff", description="Default text color")
    accent_color: str = Field(default="#7b2cbf", description="Accent color for highlights")


# ---------------------------------------------------------------------------
# SCENE GRAPH (Main Output)
# ---------------------------------------------------------------------------

class SceneGraph(BaseModel):
    """
    Complete Scene Graph - the main output model.
    
    This is the final JSON structure sent to Raspberry Pi devices.
    It contains everything needed to render a dynamic layout:
    - Layout specification (how to arrange components)
    - Components (what to display, with embedded data)
    - Global styling (scene-wide defaults)
    - Metadata (refresh rate, original request)
    
    Example Usage:
        scene = SceneGraph(
            scene_id="abc-123",
            target_devices=["device-uuid"],
            layout=LayoutSpec(intent=LayoutIntent.SIDEBAR, engine=LayoutEngine.GRID),
            components=[
                SceneComponent(id="cal", type="calendar_week", data={"events": [...]})
            ]
        )
        
        # Send to device
        await command_service.send_command(
            device_id=device_id,
            command_type="display_scene",
            payload=scene.model_dump()
        )
    """
    # Identification
    scene_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique scene identifier"
    )
    version: str = Field(default="1.1", description="Scene Graph schema version")
    
    # Target devices
    target_devices: List[str] = Field(
        default_factory=list,
        description="List of device IDs to display this scene"
    )
    
    # Layout
    layout: LayoutSpec = Field(description="Layout specification")
    
    # Components
    components: List[SceneComponent] = Field(
        default_factory=list,
        description="Components to render, in order"
    )
    
    # Global styling
    global_style: GlobalStyle = Field(
        default_factory=GlobalStyle,
        description="Scene-wide styling defaults"
    )
    
    # Metadata
    metadata: SceneMetadata = Field(
        default_factory=SceneMetadata,
        description="Scene metadata"
    )
    
    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    
    def get_primary_component(self) -> Optional[SceneComponent]:
        """
        Get the primary (main) component in this scene.
        
        Returns the first component with priority=PRIMARY,
        or the first component if none are marked primary.
        
        Returns:
            Primary SceneComponent or None if scene is empty
        """
        for component in self.components:
            if component.priority == ComponentPriority.PRIMARY:
                return component
        return self.components[0] if self.components else None
    
    def filter_by_priority(self, priority: ComponentPriority) -> List[SceneComponent]:
        """
        Filter components by priority level.
        
        Useful for responsive layouts that need to hide lower-priority
        components on smaller screens.
        
        Args:
            priority: The priority level to filter by
            
        Returns:
            List of components matching the priority
        """
        return [c for c in self.components if c.priority == priority]
    
    def get_component_by_id(self, component_id: str) -> Optional[SceneComponent]:
        """
        Get a component by its ID.
        
        Args:
            component_id: The unique component ID
            
        Returns:
            SceneComponent if found, None otherwise
        """
        for component in self.components:
            if component.id == component_id:
                return component
        return None
    
    def get_components_by_type(self, component_type: str) -> List[SceneComponent]:
        """
        Get all components of a specific type.
        
        Args:
            component_type: Component type (e.g., 'calendar_week')
            
        Returns:
            List of matching components
        """
        return [c for c in self.components if c.type == component_type]
    
    def has_component_type(self, component_type: str) -> bool:
        """Check if the scene contains a component of the given type."""
        return any(c.type == component_type for c in self.components)
    
    def component_count(self) -> int:
        """Get the number of components in this scene."""
        return len(self.components)
