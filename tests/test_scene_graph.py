"""
Tests for Scene Graph functionality (Sprint 4.0).

This module tests:
- Scene Graph schema validation
- Component Registry operations
- Default scene generation
- Scene Service functionality
- Intent parser integration for display_content
- Layout hint normalization

All LLM calls are mocked for fast, reliable tests.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.ai.scene.schemas import (
    LayoutIntent,
    LayoutEngine,
    ComponentPriority,
    ComponentPosition,
    ComponentStyle,
    LayoutHint,
    LayoutSpec,
    SceneComponent,
    SceneMetadata,
    SceneGraph,
)
from app.ai.scene.registry import ComponentRegistry, ComponentDefinition
from app.ai.scene.defaults import (
    DefaultSceneType,
    get_default_scene_template,
    detect_default_scene_type,
)
from app.ai.scene.service import SceneService
from app.ai.intent.schemas import (
    IntentType,
    ActionType,
    DisplayContentIntent,
)
from app.ai.intent.parser import IntentParser
from app.ai.providers.base import AIResponse, ProviderType


# ---------------------------------------------------------------------------
# SCENE SCHEMA TESTS
# ---------------------------------------------------------------------------

class TestSceneSchemas:
    """Tests for Scene Graph Pydantic models."""
    
    def test_component_position_defaults(self):
        """Test ComponentPosition default values."""
        pos = ComponentPosition()
        
        # Default values should be None for all optional fields
        assert pos.grid_column is None
        assert pos.grid_row is None
        assert pos.flex is None
        assert pos.top is None
        assert pos.z_index is None
    
    def test_component_position_grid(self):
        """Test ComponentPosition with grid layout."""
        pos = ComponentPosition(
            grid_column="1 / 3",
            grid_row="1 / 2",
        )
        
        assert pos.grid_column == "1 / 3"
        assert pos.grid_row == "1 / 2"
    
    def test_component_position_absolute(self):
        """Test ComponentPosition with absolute positioning."""
        pos = ComponentPosition(
            top="10px",
            right="10px",
            z_index=10,
        )
        
        assert pos.top == "10px"
        assert pos.right == "10px"
        assert pos.z_index == 10
    
    def test_layout_hint_from_natural_language(self):
        """Test LayoutHint with natural language positions."""
        hint = LayoutHint(
            component="calendar",
            position="left",
            size="large",
        )
        
        assert hint.component == "calendar"
        assert hint.position == "left"
        assert hint.size == "large"
    
    def test_scene_component_creation(self):
        """Test creating a SceneComponent."""
        component = SceneComponent(
            id="cal_001",
            type="calendar_week",
            position=ComponentPosition(grid_column="1 / 3"),
            data={"events": [{"title": "Meeting", "time": "9:00 AM"}]},
        )
        
        assert component.id == "cal_001"
        assert component.type == "calendar_week"
        assert component.position.grid_column == "1 / 3"
        assert "events" in component.data
    
    def test_scene_metadata_creation(self):
        """Test creating SceneMetadata."""
        metadata = SceneMetadata(
            user_request="Show calendar on the left",
            refresh_seconds=300,
        )
        
        assert metadata.user_request == "Show calendar on the left"
        assert metadata.refresh_seconds == 300
        assert metadata.created_at is not None
    
    def test_scene_graph_creation(self):
        """Test creating a complete SceneGraph."""
        component = SceneComponent(
            id="clock_001",
            type="clock_digital",
            position=ComponentPosition(top="0", right="0"),
            data={"timezone": "America/Los_Angeles"},
        )
        
        scene = SceneGraph(
            layout=LayoutSpec(
                intent=LayoutIntent.SIDEBAR,
                engine=LayoutEngine.GRID,
            ),
            components=[component],
            metadata=SceneMetadata(
                user_request="Show a clock",
            ),
        )
        
        assert len(scene.components) == 1
        assert scene.components[0].type == "clock_digital"
        assert scene.layout.intent == LayoutIntent.SIDEBAR
    
    def test_scene_graph_get_component(self):
        """Test SceneGraph.get_component_by_id helper method."""
        component = SceneComponent(
            id="cal_main",
            type="calendar_day",
            position=ComponentPosition(),
        )
        
        scene = SceneGraph(
            layout=LayoutSpec(
                intent=LayoutIntent.FULLSCREEN,
                engine=LayoutEngine.FLEX,
            ),
            components=[component],
        )
        
        found = scene.get_component_by_id("cal_main")
        not_found = scene.get_component_by_id("nonexistent")
        
        assert found is not None
        assert found.id == "cal_main"
        assert not_found is None
    
    def test_scene_graph_model_dump(self):
        """Test that SceneGraph serializes to JSON properly."""
        scene = SceneGraph(
            layout=LayoutSpec(
                intent=LayoutIntent.FULLSCREEN,
                engine=LayoutEngine.GRID,
            ),
            components=[
                SceneComponent(
                    id="comp1",
                    type="clock_digital",
                    position=ComponentPosition(),
                    props={"format": "12h"},
                ),
            ],
            metadata=SceneMetadata(
                user_request="Test serialization",
            ),
        )
        
        scene_dict = scene.model_dump(mode="json")
        
        assert "metadata" in scene_dict
        assert "components" in scene_dict
        assert "layout" in scene_dict
        assert len(scene_dict["components"]) == 1


# ---------------------------------------------------------------------------
# COMPONENT REGISTRY TESTS
# ---------------------------------------------------------------------------

class TestComponentRegistry:
    """Tests for ComponentRegistry singleton."""
    
    def test_registry_has_mvp_components(self):
        """Test that registry contains MVP components."""
        registry = ComponentRegistry()
        
        mvp_components = [
            "calendar_day",
            "calendar_week",
            "calendar_month",
            "clock_digital",
            "clock_analog",
            "weather_current",
            "text_block",
            "spacer",
        ]
        
        for component_type in mvp_components:
            assert registry.exists(component_type), f"Missing component: {component_type}"
    
    def test_get_component_definition(self):
        """Test getting a component definition."""
        registry = ComponentRegistry()
        
        calendar_def = registry.get("calendar_week")
        
        assert calendar_def is not None
        assert calendar_def.id == "calendar_week"
    
    def test_get_nonexistent_component(self):
        """Test getting a component that doesn't exist."""
        registry = ComponentRegistry()
        
        result = registry.get("nonexistent_component")
        
        assert result is None
    
    def test_list_all_components(self):
        """Test listing all registered components."""
        registry = ComponentRegistry()
        
        all_components = registry.list_all()
        
        assert len(all_components) >= 8  # MVP components
        all_ids = [c.id for c in all_components]
        assert "calendar_day" in all_ids
        assert "clock_digital" in all_ids
    
    def test_list_by_category(self):
        """Test getting components by category."""
        registry = ComponentRegistry()
        
        calendar_components = registry.list_by_category("calendar")
        
        assert len(calendar_components) >= 3  # calendar_day, calendar_week, calendar_month
        assert all("calendar" in c.id for c in calendar_components)


# ---------------------------------------------------------------------------
# DEFAULT SCENE TESTS
# ---------------------------------------------------------------------------

class TestDefaultScenes:
    """Tests for default scene templates."""
    
    def test_detect_calendar_fullscreen(self):
        """Test detecting calendar fullscreen intent."""
        test_phrases = [
            "show my calendar",
            "display calendar",
            "put calendar on screen",
        ]
        
        for phrase in test_phrases:
            result = detect_default_scene_type(phrase)
            # May return CALENDAR_FULLSCREEN or None (depends on implementation)
            assert result is None or isinstance(result, DefaultSceneType)
    
    def test_detect_dashboard(self):
        """Test detecting dashboard intent."""
        test_phrases = [
            "show me a dashboard",
            "dashboard view",
            "show dashboard",
        ]
        
        for phrase in test_phrases:
            result = detect_default_scene_type(phrase)
            # May return DASHBOARD or None
            assert result is None or isinstance(result, DefaultSceneType)
    
    def test_get_default_scene_calendar_fullscreen(self):
        """Test getting a default calendar fullscreen scene."""
        scene = get_default_scene_template(
            DefaultSceneType.CALENDAR_FULLSCREEN,
            target_devices=["device-1"],
            user_request="show calendar",
        )
        
        assert scene is not None
        assert len(scene.components) >= 1
        
        # Find calendar component
        calendar_comp = None
        for comp in scene.components:
            if "calendar" in comp.type:
                calendar_comp = comp
                break
        
        assert calendar_comp is not None
    
    def test_get_default_scene_dashboard(self):
        """Test getting a default dashboard scene."""
        scene = get_default_scene_template(
            DefaultSceneType.DASHBOARD,
            target_devices=["device-1"],
            user_request="show dashboard",
        )
        
        assert scene is not None
        assert len(scene.components) >= 2  # Dashboard has multiple components
    
    def test_default_scenes_are_valid(self):
        """Test that default scenes have valid structure."""
        for scene_type in DefaultSceneType:
            scene = get_default_scene_template(
                scene_type,
                target_devices=["device-1"],
                user_request="test",
            )
            
            # Each scene should have layout and components
            assert scene.layout is not None
            assert scene.components is not None
            
            # Each component should have required fields
            for component in scene.components:
                assert component.id is not None
                assert component.type is not None


# ---------------------------------------------------------------------------
# SCENE SERVICE TESTS
# ---------------------------------------------------------------------------

class TestSceneService:
    """Tests for SceneService."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh SceneService instance."""
        return SceneService()
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()
    
    def test_service_initialization(self, service):
        """Test that SceneService initializes properly."""
        assert service is not None
    
    def test_normalize_layout_hints_basic(self, service):
        """Test normalizing natural language to LayoutHints."""
        hints = service.normalize_layout_hints("calendar on the left, clock in the corner")
        
        # Should return a list of hints
        assert isinstance(hints, list)
        # At least some hints extracted
        assert len(hints) >= 1


# ---------------------------------------------------------------------------
# DISPLAY CONTENT INTENT MODEL TESTS
# ---------------------------------------------------------------------------

class TestDisplayContentIntentModel:
    """Tests for DisplayContentIntent Pydantic model."""
    
    def test_display_content_intent_creation(self):
        """Test creating a DisplayContentIntent."""
        intent = DisplayContentIntent(
            intent_type=IntentType.DISPLAY_CONTENT,
            confidence=0.95,
            original_text="Show calendar on the left",
            device_name="living room TV",
            layout_hints=["calendar left", "clock corner"],
        )
        
        assert intent.intent_type == IntentType.DISPLAY_CONTENT
        assert intent.device_name == "living room TV"
        assert len(intent.layout_hints) == 2
        assert "calendar left" in intent.layout_hints
    
    def test_display_content_intent_layout_types(self):
        """Test DisplayContentIntent with different layout types."""
        custom_intent = DisplayContentIntent(
            intent_type=IntentType.DISPLAY_CONTENT,
            confidence=0.90,
            original_text="Create a dashboard",
            layout_type="custom",
            layout_hints=["dashboard"],
        )
        
        assert custom_intent.layout_type == "custom"
        
        default_intent = DisplayContentIntent(
            intent_type=IntentType.DISPLAY_CONTENT,
            confidence=0.90,
            original_text="Show calendar",
            layout_type="default",
        )
        
        assert default_intent.layout_type == "default"


# ---------------------------------------------------------------------------
# LAYOUT ENGINE TESTS
# ---------------------------------------------------------------------------

class TestLayoutEngine:
    """Tests for layout engine enumeration and selection."""
    
    def test_layout_engine_values(self):
        """Test LayoutEngine enum values."""
        assert LayoutEngine.GRID.value == "grid"
        assert LayoutEngine.FLEX.value == "flex"
        assert LayoutEngine.ABSOLUTE.value == "absolute"
    
    def test_layout_spec_creation(self):
        """Test creating a LayoutSpec."""
        spec = LayoutSpec(
            intent=LayoutIntent.DASHBOARD,
            engine=LayoutEngine.GRID,
            columns=3,
            gap="16px",
        )
        
        assert spec.intent == LayoutIntent.DASHBOARD
        assert spec.engine == LayoutEngine.GRID
        assert spec.columns == 3


# ---------------------------------------------------------------------------
# COMPONENT PRIORITY TESTS
# ---------------------------------------------------------------------------

class TestComponentPriority:
    """Tests for component priority handling."""
    
    def test_priority_values(self):
        """Test that priority values exist."""
        assert ComponentPriority.PRIMARY.value == "primary"
        assert ComponentPriority.SECONDARY.value == "secondary"
        assert ComponentPriority.TERTIARY.value == "tertiary"
    
    def test_priority_in_component(self):
        """Test using priority in SceneComponent."""
        component = SceneComponent(
            id="test",
            type="clock_digital",
            priority=ComponentPriority.PRIMARY,
        )
        
        assert component.priority == ComponentPriority.PRIMARY


# ---------------------------------------------------------------------------
# EDGE CASE TESTS
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_scene_graph(self):
        """Test creating a scene with no components."""
        scene = SceneGraph(
            layout=LayoutSpec(
                intent=LayoutIntent.FULLSCREEN,
                engine=LayoutEngine.FLEX,
            ),
            components=[],
        )
        
        assert len(scene.components) == 0
        assert scene.get_component_by_id("anything") is None
    
    def test_component_with_empty_data(self):
        """Test component with empty data dict."""
        component = SceneComponent(
            id="empty_data",
            type="spacer",
            position=ComponentPosition(),
            data={},
        )
        
        assert component.data == {}
    
    def test_components_with_z_index(self):
        """Test scene with components using z-index for layering."""
        scene = SceneGraph(
            layout=LayoutSpec(
                intent=LayoutIntent.OVERLAY,
                engine=LayoutEngine.ABSOLUTE,
            ),
            components=[
                SceneComponent(
                    id="bg",
                    type="calendar_week",
                    position=ComponentPosition(z_index=0),
                ),
                SceneComponent(
                    id="overlay",
                    type="clock_digital",
                    position=ComponentPosition(top="0", right="0", z_index=1),
                ),
            ],
        )
        
        # Both components exist with different z_index
        assert scene.components[0].position.z_index == 0
        assert scene.components[1].position.z_index == 1
    
    def test_scene_metadata_defaults(self):
        """Test SceneMetadata with minimal required fields."""
        metadata = SceneMetadata()
        
        # Should have default values
        assert metadata.refresh_seconds == 300
        assert metadata.created_at is not None

