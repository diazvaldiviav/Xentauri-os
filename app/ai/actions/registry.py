"""
Action Registry - Centralized action definitions and validation.

This module provides a registry of all actions that Jarvis can execute,
including their required parameters and validation rules.

Purpose:
========
1. Single source of truth for action definitions
2. Parameter validation before execution
3. Easy extensibility for new actions
4. Documentation of action capabilities

Usage:
======
```python
from app.ai.actions.registry import action_registry

# Check if action exists
if action_registry.has_action("show_calendar"):
    action = action_registry.get_action("show_calendar")
    
# Validate parameters
is_valid, error = action_registry.validate("power_on", {"target_device": "TV"})

# Get all actions
all_actions = action_registry.list_actions()
```
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set, Callable
from enum import Enum


logger = logging.getLogger("jarvis.ai.actions.registry")


# ---------------------------------------------------------------------------
# ACTION CATEGORIES
# ---------------------------------------------------------------------------

class ActionCategory(str, Enum):
    """Categories of actions for organization and routing."""
    POWER = "power"           # Power control (on/off)
    CONTENT = "content"       # Content display (calendar, URLs)
    INPUT = "input"           # Input source selection
    VOLUME = "volume"         # Volume control
    SYSTEM = "system"         # System queries
    OTHER = "other"           # Miscellaneous


# ---------------------------------------------------------------------------
# ACTION DEFINITION
# ---------------------------------------------------------------------------

@dataclass
class ActionDefinition:
    """
    Definition of an action that Jarvis can execute.
    
    Attributes:
        name: Unique action identifier (e.g., "power_on")
        category: Action category for routing
        description: Human-readable description
        required_params: Parameters that must be provided
        optional_params: Parameters that may be provided
        aliases: Alternative names for this action
        examples: Example usage phrases
        validator: Optional custom validation function
    """
    name: str
    category: ActionCategory
    description: str
    required_params: Set[str] = field(default_factory=set)
    optional_params: Set[str] = field(default_factory=set)
    aliases: Set[str] = field(default_factory=set)
    examples: List[str] = field(default_factory=list)
    validator: Optional[Callable[[Dict[str, Any]], tuple[bool, Optional[str]]]] = None
    
    def validate(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parameters for this action.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        # Check for required parameters
        for param in self.required_params:
            # Handle device parameter aliases
            if param == "target_device":
                if not (
                    parameters.get("target_device") or
                    parameters.get("device") or
                    parameters.get("device_name")
                ):
                    return False, f"Missing required parameter: {param}"
            elif param not in parameters:
                return False, f"Missing required parameter: {param}"
        
        # Run custom validator if provided
        if self.validator:
            return self.validator(parameters)
        
        return True, None


# ---------------------------------------------------------------------------
# ACTION REGISTRY
# ---------------------------------------------------------------------------

class ActionRegistry:
    """
    Registry of all actions that Jarvis can execute.
    
    This is a singleton that maintains the master list of actions
    with their definitions, validation rules, and metadata.
    """
    
    def __init__(self):
        """Initialize the registry with built-in actions."""
        self._actions: Dict[str, ActionDefinition] = {}
        self._alias_map: Dict[str, str] = {}  # alias -> canonical name
        self._register_builtin_actions()
        logger.info(f"Action registry initialized with {len(self._actions)} actions")
    
    def _register_builtin_actions(self):
        """Register all built-in actions."""
        
        # -----------------------------------------------------------------------
        # POWER ACTIONS
        # -----------------------------------------------------------------------
        self.register(ActionDefinition(
            name="power_on",
            category=ActionCategory.POWER,
            description="Turn on a device",
            required_params={"target_device"},
            aliases={"turn_on", "switch_on", "start"},
            examples=[
                "Turn on the living room TV",
                "Power on bedroom monitor",
            ],
        ))
        
        self.register(ActionDefinition(
            name="power_off",
            category=ActionCategory.POWER,
            description="Turn off a device",
            required_params={"target_device"},
            aliases={"turn_off", "switch_off", "shutdown"},
            examples=[
                "Turn off the kitchen display",
                "Power off office TV",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # CONTENT ACTIONS
        # -----------------------------------------------------------------------
        self.register(ActionDefinition(
            name="show_calendar",
            category=ActionCategory.CONTENT,
            description="Display calendar on a device",
            required_params={"target_device"},
            optional_params={"date"},
            aliases={"display_calendar", "calendar", "show_schedule"},
            examples=[
                "Show the calendar on living room TV",
                "Display my schedule on the bedroom monitor",
                "Show tomorrow's calendar on kitchen display",
            ],
        ))
        
        self.register(ActionDefinition(
            name="show_content",
            category=ActionCategory.CONTENT,
            description="Display content URL on a device",
            required_params={"target_device"},
            optional_params={"url", "content_type", "date"},
            aliases={"display_content", "display_url", "show_url"},
            examples=[
                "Show the weather on office display",
            ],
        ))
        
        self.register(ActionDefinition(
            name="clear_content",
            category=ActionCategory.CONTENT,
            description="Clear content from a device display",
            required_params={"target_device"},
            aliases={"clear_display", "hide_content", "blank_screen"},
            examples=[
                "Clear the living room TV",
                "Hide content on bedroom monitor",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # INPUT ACTIONS
        # -----------------------------------------------------------------------
        self.register(ActionDefinition(
            name="set_input",
            category=ActionCategory.INPUT,
            description="Change the input source of a device",
            required_params={"target_device", "input"},
            aliases={"switch_input", "change_input", "select_input"},
            examples=[
                "Switch living room TV to HDMI 2",
                "Change input to cable on bedroom TV",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # VOLUME ACTIONS
        # -----------------------------------------------------------------------
        self.register(ActionDefinition(
            name="volume_up",
            category=ActionCategory.VOLUME,
            description="Increase device volume",
            required_params={"target_device"},
            optional_params={"step"},
            aliases={"louder", "increase_volume", "turn_up"},
            examples=[
                "Turn up the volume on living room TV",
                "Louder on bedroom monitor",
            ],
        ))
        
        self.register(ActionDefinition(
            name="volume_down",
            category=ActionCategory.VOLUME,
            description="Decrease device volume",
            required_params={"target_device"},
            optional_params={"step"},
            aliases={"quieter", "decrease_volume", "turn_down"},
            examples=[
                "Turn down the volume on kitchen display",
                "Quieter on office TV",
            ],
        ))
        
        self.register(ActionDefinition(
            name="volume_set",
            category=ActionCategory.VOLUME,
            description="Set device volume to specific level",
            required_params={"target_device", "level"},
            aliases={"set_volume"},
            examples=[
                "Set living room TV volume to 50%",
                "Volume 30 on bedroom monitor",
            ],
            validator=self._validate_volume_level,
        ))
        
        self.register(ActionDefinition(
            name="mute",
            category=ActionCategory.VOLUME,
            description="Mute device audio",
            required_params={"target_device"},
            aliases={"silence", "mute_audio"},
            examples=[
                "Mute the living room TV",
            ],
        ))
        
        self.register(ActionDefinition(
            name="unmute",
            category=ActionCategory.VOLUME,
            description="Unmute device audio",
            required_params={"target_device"},
            aliases={"unmute_audio"},
            examples=[
                "Unmute the kitchen display",
            ],
        ))
    
    # ---------------------------------------------------------------------------
    # CUSTOM VALIDATORS
    # ---------------------------------------------------------------------------
    
    @staticmethod
    def _validate_volume_level(params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate volume level is within range."""
        level = params.get("level")
        if level is None:
            return False, "Missing volume level"
        
        try:
            level_int = int(level)
            if level_int < 0 or level_int > 100:
                return False, f"Volume level must be 0-100, got {level_int}"
            return True, None
        except (ValueError, TypeError):
            return False, f"Invalid volume level: {level}"
    
    # ---------------------------------------------------------------------------
    # REGISTRY OPERATIONS
    # ---------------------------------------------------------------------------
    
    def register(self, action: ActionDefinition) -> None:
        """
        Register an action in the registry.
        
        Args:
            action: ActionDefinition to register
        """
        self._actions[action.name] = action
        
        # Register aliases
        for alias in action.aliases:
            self._alias_map[alias] = action.name
        
        logger.debug(f"Registered action: {action.name}")
    
    def get_action(self, name: str) -> Optional[ActionDefinition]:
        """
        Get an action by name or alias.
        
        Args:
            name: Action name or alias
            
        Returns:
            ActionDefinition if found, None otherwise
        """
        # Normalize name
        name = name.lower().strip()
        
        # Direct lookup
        if name in self._actions:
            return self._actions[name]
        
        # Alias lookup
        if name in self._alias_map:
            canonical_name = self._alias_map[name]
            return self._actions.get(canonical_name)
        
        return None
    
    def has_action(self, name: str) -> bool:
        """Check if an action exists (by name or alias)."""
        name = name.lower().strip()
        return name in self._actions or name in self._alias_map
    
    def validate(self, action_name: str, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parameters for an action.
        
        Args:
            action_name: Action name or alias
            parameters: Parameters to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        action = self.get_action(action_name)
        
        if not action:
            return False, f"Unknown action: {action_name}"
        
        return action.validate(parameters)
    
    def get_canonical_name(self, name: str) -> Optional[str]:
        """
        Get the canonical name for an action (resolves aliases).
        
        Args:
            name: Action name or alias
            
        Returns:
            Canonical action name or None if not found
        """
        name = name.lower().strip()
        
        if name in self._actions:
            return name
        
        if name in self._alias_map:
            return self._alias_map[name]
        
        return None
    
    def list_actions(self, category: Optional[ActionCategory] = None) -> List[ActionDefinition]:
        """
        List all registered actions, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of ActionDefinitions
        """
        if category:
            return [a for a in self._actions.values() if a.category == category]
        return list(self._actions.values())
    
    def list_action_names(self) -> List[str]:
        """Get all registered action names (not aliases)."""
        return list(self._actions.keys())
    
    def get_actions_by_category(self) -> Dict[ActionCategory, List[ActionDefinition]]:
        """Get actions grouped by category."""
        result: Dict[ActionCategory, List[ActionDefinition]] = {}
        for action in self._actions.values():
            if action.category not in result:
                result[action.category] = []
            result[action.category].append(action)
        return result
    
    def is_content_action(self, name: str) -> bool:
        """Check if an action is a content action."""
        action = self.get_action(name)
        return action is not None and action.category == ActionCategory.CONTENT
    
    def is_power_action(self, name: str) -> bool:
        """Check if an action is a power action."""
        action = self.get_action(name)
        return action is not None and action.category == ActionCategory.POWER
    
    def is_volume_action(self, name: str) -> bool:
        """Check if an action is a volume action."""
        action = self.get_action(name)
        return action is not None and action.category == ActionCategory.VOLUME


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

action_registry = ActionRegistry()
