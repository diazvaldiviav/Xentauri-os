"""
Tests for Action Registry - Phase 2

Tests for:
- ActionDefinition creation and validation
- ActionRegistry registration and lookup
- Alias resolution
- Category filtering
- Custom validators
"""

import pytest
from typing import Dict, Any

from app.ai.actions.registry import (
    ActionRegistry,
    ActionDefinition,
    ActionCategory,
    action_registry,
)


# ===========================================================================
# ACTIONDEFINITION TESTS
# ===========================================================================

class TestActionDefinition:
    """Tests for ActionDefinition dataclass."""
    
    def test_create_basic_action(self):
        """Test creating a basic action definition."""
        action = ActionDefinition(
            name="test_action",
            category=ActionCategory.POWER,
            description="A test action",
        )
        
        assert action.name == "test_action"
        assert action.category == ActionCategory.POWER
        assert action.description == "A test action"
        assert action.required_params == set()
        assert action.optional_params == set()
        assert action.aliases == set()
    
    def test_create_action_with_params(self):
        """Test creating action with required/optional params."""
        action = ActionDefinition(
            name="set_volume",
            category=ActionCategory.VOLUME,
            description="Set volume level",
            required_params={"target_device", "level"},
            optional_params={"mute_first"},
        )
        
        assert "target_device" in action.required_params
        assert "level" in action.required_params
        assert "mute_first" in action.optional_params
    
    def test_create_action_with_aliases(self):
        """Test creating action with aliases."""
        action = ActionDefinition(
            name="power_on",
            category=ActionCategory.POWER,
            description="Turn on device",
            aliases={"turn_on", "switch_on", "start"},
        )
        
        assert "turn_on" in action.aliases
        assert "switch_on" in action.aliases
        assert "start" in action.aliases
    
    def test_validate_with_all_required_params(self):
        """Test validation passes with all required params."""
        action = ActionDefinition(
            name="set_input",
            category=ActionCategory.INPUT,
            description="Set input source",
            required_params={"target_device", "input"},
        )
        
        is_valid, error = action.validate({
            "target_device": "Living Room TV",
            "input": "HDMI2",
        })
        
        assert is_valid is True
        assert error is None
    
    def test_validate_missing_required_param(self):
        """Test validation fails when required param missing."""
        action = ActionDefinition(
            name="set_input",
            category=ActionCategory.INPUT,
            description="Set input source",
            required_params={"target_device", "input"},
        )
        
        is_valid, error = action.validate({
            "target_device": "Living Room TV",
            # Missing 'input'
        })
        
        assert is_valid is False
        assert "input" in error
    
    def test_validate_target_device_aliases(self):
        """Test that device/device_name work as target_device aliases."""
        action = ActionDefinition(
            name="power_on",
            category=ActionCategory.POWER,
            description="Turn on device",
            required_params={"target_device"},
        )
        
        # Using 'device' instead
        is_valid, _ = action.validate({"device": "TV"})
        assert is_valid is True
        
        # Using 'device_name' instead
        is_valid, _ = action.validate({"device_name": "TV"})
        assert is_valid is True
    
    def test_custom_validator(self):
        """Test action with custom validator function."""
        def validate_level(params: Dict[str, Any]) -> tuple[bool, str]:
            level = params.get("level")
            if level and (level < 0 or level > 100):
                return False, "Level must be 0-100"
            return True, None
        
        action = ActionDefinition(
            name="volume_set",
            category=ActionCategory.VOLUME,
            description="Set volume",
            required_params={"target_device", "level"},
            validator=validate_level,
        )
        
        # Valid level
        is_valid, _ = action.validate({"target_device": "TV", "level": 50})
        assert is_valid is True
        
        # Invalid level
        is_valid, error = action.validate({"target_device": "TV", "level": 150})
        assert is_valid is False
        assert "0-100" in error


# ===========================================================================
# ACTIONREGISTRY TESTS
# ===========================================================================

class TestActionRegistry:
    """Tests for ActionRegistry class."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return ActionRegistry()
    
    def test_builtin_actions_registered(self, registry):
        """Test that built-in actions are registered on init."""
        # Power actions
        assert registry.has_action("power_on")
        assert registry.has_action("power_off")
        
        # Content actions
        assert registry.has_action("show_calendar")
        assert registry.has_action("show_content")
        assert registry.has_action("clear_content")
        
        # Volume actions
        assert registry.has_action("volume_up")
        assert registry.has_action("volume_down")
        assert registry.has_action("volume_set")
        assert registry.has_action("mute")
        assert registry.has_action("unmute")
        
        # Input actions
        assert registry.has_action("set_input")
    
    def test_get_action_by_name(self, registry):
        """Test getting action by canonical name."""
        action = registry.get_action("power_on")
        
        assert action is not None
        assert action.name == "power_on"
        assert action.category == ActionCategory.POWER
    
    def test_get_action_by_alias(self, registry):
        """Test getting action by alias."""
        action = registry.get_action("turn_on")  # Alias for power_on
        
        assert action is not None
        assert action.name == "power_on"  # Returns canonical action
    
    def test_get_action_case_insensitive(self, registry):
        """Test that action lookup is case-insensitive."""
        action = registry.get_action("POWER_ON")
        
        assert action is not None
        assert action.name == "power_on"
    
    def test_get_action_with_whitespace(self, registry):
        """Test that whitespace is trimmed."""
        action = registry.get_action("  power_on  ")
        
        assert action is not None
        assert action.name == "power_on"
    
    def test_get_nonexistent_action(self, registry):
        """Test getting action that doesn't exist."""
        action = registry.get_action("nonexistent_action")
        
        assert action is None
    
    def test_has_action_with_alias(self, registry):
        """Test has_action works with aliases."""
        assert registry.has_action("turn_on") is True  # Alias
        assert registry.has_action("power_on") is True  # Canonical
        assert registry.has_action("fake_action") is False
    
    def test_validate_action(self, registry):
        """Test validating action parameters through registry."""
        is_valid, error = registry.validate("power_on", {"target_device": "TV"})
        
        assert is_valid is True
        assert error is None
    
    def test_validate_action_missing_param(self, registry):
        """Test validation catches missing params."""
        is_valid, error = registry.validate("set_input", {"target_device": "TV"})
        
        assert is_valid is False
        assert "input" in error
    
    def test_validate_unknown_action(self, registry):
        """Test validating unknown action."""
        is_valid, error = registry.validate("unknown_action", {})
        
        assert is_valid is False
        assert "Unknown action" in error
    
    def test_get_canonical_name(self, registry):
        """Test getting canonical name from alias."""
        assert registry.get_canonical_name("turn_on") == "power_on"
        assert registry.get_canonical_name("power_on") == "power_on"
        assert registry.get_canonical_name("nonexistent") is None
    
    def test_list_actions(self, registry):
        """Test listing all actions."""
        actions = registry.list_actions()
        
        assert len(actions) >= 10  # At least the built-in actions
        assert all(isinstance(a, ActionDefinition) for a in actions)
    
    def test_list_actions_by_category(self, registry):
        """Test listing actions filtered by category."""
        power_actions = registry.list_actions(category=ActionCategory.POWER)
        
        assert len(power_actions) >= 2  # power_on, power_off
        assert all(a.category == ActionCategory.POWER for a in power_actions)
    
    def test_list_action_names(self, registry):
        """Test listing action names."""
        names = registry.list_action_names()
        
        assert "power_on" in names
        assert "show_calendar" in names
        assert "turn_on" not in names  # Aliases not included
    
    def test_get_actions_by_category(self, registry):
        """Test grouping actions by category."""
        grouped = registry.get_actions_by_category()
        
        assert ActionCategory.POWER in grouped
        assert ActionCategory.CONTENT in grouped
        assert ActionCategory.VOLUME in grouped
    
    def test_is_content_action(self, registry):
        """Test is_content_action helper."""
        assert registry.is_content_action("show_calendar") is True
        assert registry.is_content_action("show_content") is True
        assert registry.is_content_action("clear_content") is True
        assert registry.is_content_action("power_on") is False
    
    def test_is_power_action(self, registry):
        """Test is_power_action helper."""
        assert registry.is_power_action("power_on") is True
        assert registry.is_power_action("power_off") is True
        assert registry.is_power_action("show_calendar") is False
    
    def test_is_volume_action(self, registry):
        """Test is_volume_action helper."""
        assert registry.is_volume_action("volume_up") is True
        assert registry.is_volume_action("mute") is True
        assert registry.is_volume_action("power_on") is False
    
    def test_register_custom_action(self, registry):
        """Test registering a custom action."""
        custom_action = ActionDefinition(
            name="custom_action",
            category=ActionCategory.OTHER,
            description="A custom action",
            required_params={"target_device", "custom_param"},
        )
        
        registry.register(custom_action)
        
        assert registry.has_action("custom_action")
        assert registry.get_action("custom_action") == custom_action
    
    def test_register_action_with_aliases(self, registry):
        """Test that aliases are registered when registering action."""
        custom_action = ActionDefinition(
            name="my_action",
            category=ActionCategory.OTHER,
            description="My action",
            aliases={"my_alias", "another_alias"},
        )
        
        registry.register(custom_action)
        
        assert registry.has_action("my_alias")
        assert registry.has_action("another_alias")
        assert registry.get_canonical_name("my_alias") == "my_action"


# ===========================================================================
# SINGLETON INSTANCE TESTS
# ===========================================================================

class TestSingletonInstance:
    """Tests for the module-level action_registry singleton."""
    
    def test_singleton_exists(self):
        """Test that singleton instance exists."""
        assert action_registry is not None
        assert isinstance(action_registry, ActionRegistry)
    
    def test_singleton_has_actions(self):
        """Test that singleton has built-in actions."""
        assert action_registry.has_action("power_on")
        assert action_registry.has_action("show_calendar")
    
    def test_singleton_validate(self):
        """Test validation through singleton."""
        is_valid, _ = action_registry.validate("power_on", {"target_device": "TV"})
        assert is_valid is True


# ===========================================================================
# VOLUME LEVEL VALIDATOR TESTS
# ===========================================================================

class TestVolumeValidator:
    """Tests for the built-in volume level validator."""
    
    def test_valid_volume_level(self):
        """Test valid volume levels."""
        is_valid, _ = action_registry.validate("volume_set", {
            "target_device": "TV",
            "level": 50,
        })
        assert is_valid is True
    
    def test_volume_level_boundaries(self):
        """Test volume level boundaries."""
        # 0 is valid
        is_valid, _ = action_registry.validate("volume_set", {
            "target_device": "TV",
            "level": 0,
        })
        assert is_valid is True
        
        # 100 is valid
        is_valid, _ = action_registry.validate("volume_set", {
            "target_device": "TV",
            "level": 100,
        })
        assert is_valid is True
    
    def test_volume_level_out_of_range(self):
        """Test volume level out of range."""
        is_valid, error = action_registry.validate("volume_set", {
            "target_device": "TV",
            "level": 150,
        })
        assert is_valid is False
        assert "0-100" in error
    
    def test_volume_level_negative(self):
        """Test negative volume level."""
        is_valid, error = action_registry.validate("volume_set", {
            "target_device": "TV",
            "level": -10,
        })
        assert is_valid is False
    
    def test_volume_level_missing(self):
        """Test missing volume level."""
        is_valid, error = action_registry.validate("volume_set", {
            "target_device": "TV",
            # Missing level
        })
        assert is_valid is False


# ===========================================================================
# ACTION EXAMPLES AND DOCUMENTATION
# ===========================================================================

class TestActionDocumentation:
    """Tests for action documentation features."""
    
    def test_action_has_description(self):
        """Test that actions have descriptions."""
        action = action_registry.get_action("power_on")
        
        assert action.description is not None
        assert len(action.description) > 0
    
    def test_action_has_examples(self):
        """Test that actions have usage examples."""
        action = action_registry.get_action("show_calendar")
        
        assert len(action.examples) > 0
        assert any("calendar" in ex.lower() for ex in action.examples)
