"""
Intent Schemas - Pydantic models for structured intents.

These schemas define the structure of extracted intents.
Using Pydantic ensures type safety and validation.

Design Philosophy:
=================
- Immutable data classes for thread safety
- Validation at construction time
- Easy serialization to JSON/dict
- Self-documenting with type hints
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """
    Types of intents that can be extracted from user requests.
    
    DEVICE_COMMAND: User wants to control a device (turn on, change input)
    DEVICE_QUERY: User wants info about a specific device
    SYSTEM_QUERY: User wants info about the system (list devices, help)
    CALENDAR_QUERY: User wants info about calendar events (Sprint 3.8)
    CONVERSATION: General chat, greetings, questions not about devices
    UNKNOWN: Could not determine intent
    """
    DEVICE_COMMAND = "device_command"
    DEVICE_QUERY = "device_query"
    SYSTEM_QUERY = "system_query"
    CALENDAR_QUERY = "calendar_query"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """
    Supported device actions.
    
    These map to the CommandType in services/commands.py
    """
    # Power actions
    POWER_ON = "power_on"
    POWER_OFF = "power_off"
    
    # Input/Source actions
    SET_INPUT = "set_input"
    
    # Volume actions
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    MUTE = "mute"
    UNMUTE = "unmute"
    
    # Content display actions (Sprint 3.5)
    SHOW_CONTENT = "show_content"  # Display content on screen
    SHOW_CALENDAR = "show_calendar"  # Display calendar specifically
    CLEAR_CONTENT = "clear_content"  # Clear displayed content
    
    # Query actions
    STATUS = "status"
    CAPABILITIES = "capabilities"
    IS_ONLINE = "is_online"
    
    # System actions
    LIST_DEVICES = "list_devices"
    HELP = "help"
    
    # Conversation
    GREETING = "greeting"
    THANKS = "thanks"
    QUESTION = "question"
    
    # Calendar Query actions (Sprint 3.8)
    COUNT_EVENTS = "count_events"
    NEXT_EVENT = "next_event"
    LIST_EVENTS = "list_events"
    FIND_EVENT = "find_event"


class Intent(BaseModel):
    """
    Base intent class - common fields for all intents.
    
    This is the raw extracted intent before device resolution.
    """
    intent_type: IntentType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    original_text: str = Field(description="The original user request")
    reasoning: Optional[str] = Field(default=None, description="Why this intent was extracted")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceCommand(Intent):
    """
    Intent for device control commands.
    
    Examples:
    - "Turn on the TV" → action=power_on, device_name="TV"
    - "Switch to HDMI 2" → action=set_input, parameters={"input": "hdmi2"}
    """
    intent_type: IntentType = IntentType.DEVICE_COMMAND
    device_name: str = Field(description="Device name as spoken by user")
    action: ActionType = Field(description="The action to perform")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    
    # Resolved fields (populated by DeviceMapper)
    device_id: Optional[UUID] = Field(default=None, description="Resolved device UUID")
    matched_device_name: Optional[str] = Field(default=None, description="Exact matched device name")


class DeviceQuery(Intent):
    """
    Intent for querying device information.
    
    Examples:
    - "Is the TV on?" → action=status
    - "What inputs does the bedroom TV have?" → action=capabilities
    """
    intent_type: IntentType = IntentType.DEVICE_QUERY
    device_name: str = Field(description="Device name as spoken")
    action: ActionType = Field(description="Query type")
    
    # Resolved fields
    device_id: Optional[UUID] = Field(default=None)
    matched_device_name: Optional[str] = Field(default=None)


class SystemQuery(Intent):
    """
    Intent for system-level queries.
    
    Examples:
    - "What devices do I have?" → action=list_devices
    - "Help" → action=help
    """
    intent_type: IntentType = IntentType.SYSTEM_QUERY
    action: ActionType = Field(description="Query type")
    parameters: Optional[Dict[str, Any]] = Field(default=None)


class CalendarQueryIntent(Intent):
    """
    Intent for calendar data queries (Sprint 3.8).
    
    These are QUESTIONS about calendar events that return TEXT responses,
    not display commands that show content on a screen.
    
    Examples:
    - "How many events today?" → action=count_events
    - "What's my next meeting?" → action=next_event
    - "List my events for tomorrow" → action=list_events
    - "When is my birthday?" → action=find_event, search_term="birthday"
    """
    intent_type: IntentType = IntentType.CALENDAR_QUERY
    action: ActionType = Field(description="Query type: count_events, next_event, list_events, find_event")
    date_range: Optional[str] = Field(default=None, description="Date context: today, tomorrow, this_week, or YYYY-MM-DD")
    search_term: Optional[str] = Field(default=None, description="Event search term (birthday, meeting, etc.)")


class ConversationIntent(Intent):
    """
    Intent for general conversation (not device-related).
    
    Examples:
    - "Hello!" → action=greeting
    - "Thanks!" → action=thanks
    - "What is HDMI-CEC?" → action=question
    """
    intent_type: IntentType = IntentType.CONVERSATION
    action: Optional[ActionType] = Field(default=None)
    response_hint: Optional[str] = Field(default=None, description="Suggested response type")


class ParsedCommand(BaseModel):
    """
    Final processed command ready for execution.
    
    This is the output after:
    1. Intent extraction (from user text)
    2. Device resolution (matching name to device)
    3. Validation (checking action is supported)
    
    This can be directly passed to the command service.
    """
    # Identification
    request_id: str = Field(description="Unique request identifier")
    user_id: Optional[UUID] = Field(default=None, description="User who made the request")
    
    # Intent info
    intent: Intent = Field(description="The extracted intent")
    
    # Device info (for device commands/queries)
    device_id: Optional[UUID] = Field(default=None, description="Target device UUID")
    device_name: Optional[str] = Field(default=None, description="Resolved device name")
    
    # Command info
    action: Optional[str] = Field(default=None, description="Action to execute")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    
    # Execution status
    can_execute: bool = Field(default=False, description="Whether command can be executed")
    error: Optional[str] = Field(default=None, description="Error if can't execute")
    
    # Metadata
    ai_provider: Optional[str] = Field(default=None, description="AI provider used")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_command_dict(self) -> Dict[str, Any]:
        """Convert to dict for command service."""
        return {
            "device_id": str(self.device_id) if self.device_id else None,
            "command_type": self.action,
            "parameters": self.parameters,
        }


class IntentResponse(BaseModel):
    """
    API response schema for the /intent endpoint.
    
    Includes the parsed command plus any AI-generated response.
    """
    success: bool = Field(description="Whether parsing succeeded")
    parsed_command: Optional[ParsedCommand] = Field(default=None)
    message: Optional[str] = Field(default=None, description="Human-readable message")
    response: Optional[str] = Field(default=None, description="AI response for conversations")
    
    # Execution result (if command was sent)
    command_sent: bool = Field(default=False)
    command_id: Optional[str] = Field(default=None)
    
    # Debug info
    debug: Optional[Dict[str, Any]] = Field(default=None, description="Debug information")
