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
    CALENDAR_CREATE: User wants to create a calendar event (Sprint 3.8)
    CALENDAR_EDIT: User wants to edit or delete an existing event (Sprint 3.9)
    DOC_QUERY: User wants to read, summarize, or link documents (Sprint 3.9)
    CONVERSATION: General chat, greetings, questions not about devices
    UNKNOWN: Could not determine intent
    """
    DEVICE_COMMAND = "device_command"
    DEVICE_QUERY = "device_query"
    SYSTEM_QUERY = "system_query"
    CALENDAR_QUERY = "calendar_query"
    CALENDAR_CREATE = "calendar_create"  # Sprint 3.8: Event creation
    CALENDAR_EDIT = "calendar_edit"      # Sprint 3.9: Edit/delete events
    DOC_QUERY = "doc_query"              # Sprint 3.9: Document intelligence
    DISPLAY_CONTENT = "display_content"  # Sprint 4.0: Scene-based content display
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
    
    # Calendar Create actions (Sprint 3.8)
    CREATE_EVENT = "create_event"           # Initial request to create an event
    CONFIRM_CREATE = "confirm_create"       # Confirm pending event creation
    CANCEL_CREATE = "cancel_create"         # Cancel pending event creation
    EDIT_PENDING_EVENT = "edit_pending_event"  # Edit a pending event before confirmation
    
    # Calendar Edit/Delete actions (Sprint 3.9)
    EDIT_EXISTING_EVENT = "edit_existing_event"  # Edit an existing calendar event
    DELETE_EXISTING_EVENT = "delete_existing_event"  # Delete an existing calendar event
    SELECT_EVENT = "select_event"           # Select from multiple matching events
    CONFIRM_EDIT = "confirm_edit"           # Confirm pending edit
    CONFIRM_DELETE = "confirm_delete"       # Confirm pending delete
    CANCEL_EDIT = "cancel_edit"             # Cancel pending edit/delete operation
    
    # Document actions (Sprint 3.9)
    READ_DOC = "read_doc"                   # Read/summarize a document
    LINK_DOC = "link_doc"                   # Link a document to a meeting
    OPEN_DOC = "open_doc"                   # Open a document (e.g., on screen)
    SUMMARIZE_MEETING_DOC = "summarize_meeting_doc"  # Summarize doc linked to a meeting
    CREATE_EVENT_FROM_DOC = "create_event_from_doc"  # Create calendar event from doc content
    
    # Display Content actions (Sprint 4.0 - Scene Graph)
    DISPLAY_SCENE = "display_scene"          # Display a Scene Graph on device
    REFRESH_DISPLAY = "refresh_display"      # Refresh current display


# ---------------------------------------------------------------------------
# SEQUENTIAL ACTIONS (Sprint 4.0.3 - Multi-Action Support)
# ---------------------------------------------------------------------------

class SequentialAction(BaseModel):
    """
    A single action to execute as part of a multi-action request.
    
    Sprint 4.0.3: When users make compound requests like 
    "clear the screen AND show my calendar", the additional actions
    are captured in a sequential_actions array.
    
    Example:
        {
            "action": "show_calendar",
            "device_name": "Living Room",
            "parameters": {"view": "fullscreen"}
        }
    """
    action: str = Field(description="The action to execute (e.g., show_calendar, power_on)")
    device_name: Optional[str] = Field(default=None, description="Target device name if applicable")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    content_type: Optional[str] = Field(default=None, description="Content type for display actions")


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
    
    Sprint 4.0.3: Supports multi-action requests via sequential_actions.
    - "Clear screen AND show calendar" → action=clear_content, sequential_actions=[show_calendar]
    """
    intent_type: IntentType = IntentType.DEVICE_COMMAND
    device_name: str = Field(description="Device name as spoken by user")
    action: ActionType = Field(description="The action to perform")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    
    # Resolved fields (populated by DeviceMapper)
    device_id: Optional[UUID] = Field(default=None, description="Resolved device UUID")
    matched_device_name: Optional[str] = Field(default=None, description="Exact matched device name")
    
    # Multi-action support (Sprint 4.0.3)
    sequential_actions: List[SequentialAction] = Field(
        default_factory=list,
        description="Additional actions to execute after the primary action"
    )


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


class CalendarCreateIntent(Intent):
    """
    Intent for calendar event creation (Sprint 3.8).
    
    Used for creating, editing, confirming, or canceling calendar events.
    Supports a confirmation flow with pending events.
    
    Examples:
    - "schedule a meeting tomorrow at 6 pm" → action=create_event
    - "yes" (during confirmation) → action=confirm_create
    - "no" (during confirmation) → action=cancel_create
    - "change time to 7 pm" (during confirmation) → action=edit_pending_event
    """
    intent_type: IntentType = IntentType.CALENDAR_CREATE
    action: ActionType = Field(description="Create action: create_event, confirm_create, cancel_create, edit_pending_event")
    
    # Event details (for create_event action)
    event_title: Optional[str] = Field(default=None, description="Title of the event")
    event_date: Optional[str] = Field(default=None, description="Date in YYYY-MM-DD format or relative (tomorrow, next monday)")
    event_time: Optional[str] = Field(default=None, description="Time in HH:MM format (24-hour)")
    duration_minutes: int = Field(default=60, description="Duration in minutes (default 1 hour)")
    is_all_day: bool = Field(default=False, description="True if event has no specific time")
    location: Optional[str] = Field(default=None, description="Event location")
    recurrence: Optional[str] = Field(default=None, description="Recurrence rule (e.g., 'weekly', 'daily', 'RRULE:...')")
    
    # Edit details (for edit_pending_event action)
    edit_field: Optional[str] = Field(default=None, description="Field to edit: event_time, event_date, event_title, duration_minutes, location, recurrence")
    edit_value: Optional[str] = Field(default=None, description="New value for the edited field")


class CalendarEditIntent(Intent):
    """
    Intent for editing or deleting existing calendar events (Sprint 3.9).
    
    Supports a multi-step flow:
    1. Search for events matching criteria
    2. Disambiguate if multiple matches
    3. Confirm edit/delete
    4. Execute change
    
    Examples:
    - "reschedule my dentist appointment to 3pm" → action=edit_existing_event
    - "delete my meeting tomorrow" → action=delete_existing_event
    - "the first one" → action=select_event
    - "yes" (during edit confirmation) → action=confirm_edit
    - "no" (during edit confirmation) → action=cancel_edit
    """
    intent_type: IntentType = IntentType.CALENDAR_EDIT
    action: ActionType = Field(description="Edit action: edit_existing_event, delete_existing_event, select_event, confirm_edit, confirm_delete, cancel_edit")
    
    # Search criteria (for finding the event to edit/delete)
    search_term: Optional[str] = Field(default=None, description="Event name or keyword to search for")
    date_filter: Optional[str] = Field(default=None, description="Date filter: today, tomorrow, this_week, or YYYY-MM-DD")
    
    # Event selection (for select_event action)
    selection_index: Optional[int] = Field(default=None, description="1-based index when selecting from multiple events")
    event_id: Optional[str] = Field(default=None, description="Direct event ID if known")
    
    # Edit details (for edit_existing_event action)
    changes: Optional[Dict[str, Any]] = Field(default=None, description="Fields to update: {field_name: new_value}")
    # Supported change fields:
    # - summary: New event title
    # - start_datetime: New start time (ISO format or relative)
    # - end_datetime: New end time (ISO format or relative)
    # - start_date: New start date (for all-day events)
    # - end_date: New end date (for all-day events)
    # - location: New location
    # - description: New description
    # - recurrence: New recurrence rule


class DocQueryIntent(Intent):
    """
    Intent for document-related queries (Sprint 3.9).
    
    Supports reading, summarizing, and linking Google Docs.
    Now supports compound requests (Sprint 4.0.2): summarize AND display.
    
    Examples:
    - "What's in my meeting doc?" → action=summarize_meeting_doc
    - "Summarize the doc from my 3pm meeting" → action=summarize_meeting_doc
    - "Link this doc to my standup" → action=link_doc
    - "Read https://docs.google.com/..." → action=read_doc
    - "Open the meeting document" → action=open_doc
    
    Compound examples (also_display=True):
    - "Dame un resumen Y ábreme el documento en la pantalla" → summarize + display
    - "Summarize this AND show it on the TV" → summarize + display
    """
    intent_type: IntentType = IntentType.DOC_QUERY
    action: ActionType = Field(description="Doc action: read_doc, link_doc, open_doc, summarize_meeting_doc")
    
    # Document identification
    doc_url: Optional[str] = Field(default=None, description="Google Doc URL if provided")
    doc_id: Optional[str] = Field(default=None, description="Extracted document ID")
    
    # Meeting reference (for summarize_meeting_doc)
    meeting_search: Optional[str] = Field(default=None, description="Search term for the meeting (e.g., '3pm meeting', 'standup')")
    meeting_time: Optional[str] = Field(default=None, description="Time reference (e.g., '3pm', 'tomorrow at 2')")
    
    # Query details
    question: Optional[str] = Field(default=None, description="Specific question about the document")
    
    # Display target (for open_doc)
    device_name: Optional[str] = Field(default=None, description="Device to display the doc on")
    
    # Compound intent support (Sprint 4.0.2)
    also_display: bool = Field(default=False, description="True if user ALSO wants to display doc on a device")
    display_device: Optional[str] = Field(default=None, description="Target device for display (if also_display=True)")


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


class DisplayContentIntent(Intent):
    """
    Intent for scene-based content display on devices (Sprint 4.0).
    
    Used when users request custom visual layouts like:
    - "Show my calendar on the left with a clock in the corner"
    - "Display a dashboard with weather and events"
    - "Fullscreen calendar on the living room TV"
    
    The layout_hints are raw strings extracted by Gemini, which the
    SceneService normalizes into structured LayoutHint objects.
    
    Distinguishing from device_command:
    - display_content: Has positioning/layout requirements ("on the left", "dashboard", "sidebar")
    - device_command with show_calendar: Simple display without layout ("show my calendar")
    
    Examples:
    - "calendar on the left with clock" → layout_hints=["calendar left", "clock corner"]
    - "fullscreen agenda" → layout_hints=["fullscreen"], info_type="calendar"
    - "dashboard with weather and calendar" → layout_hints=["dashboard", "weather", "calendar"]
    """
    intent_type: IntentType = IntentType.DISPLAY_CONTENT
    
    # Classification
    info_type: str = Field(
        default="calendar",
        description="Primary content type: calendar, clock, weather, mixed"
    )
    output_type: str = Field(
        default="display",
        description="Output type: display (visual) vs query (text answer)"
    )
    layout_type: str = Field(
        default="default",
        description="Layout type: default (use preset) vs custom (Claude generates)"
    )
    
    # Layout hints (raw strings from Gemini, normalized by service)
    layout_hints: List[str] = Field(
        default_factory=list,
        description="Raw layout hints: 'calendar left', 'clock corner', 'dashboard'"
    )
    
    # Target device (if specified by user)
    device_name: Optional[str] = Field(
        default=None,
        description="Target device name if specified (e.g., 'living room TV')"
    )


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
