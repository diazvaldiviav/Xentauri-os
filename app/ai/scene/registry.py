"""
Component Registry - Centralized registry of available display components.

This module provides a registry of all components that can be used in Scene Graphs.
It follows the pattern established by ActionRegistry in app/ai/actions/registry.py.

Purpose:
========
1. Single source of truth for component definitions
2. Validation of component types in Scene Graphs
3. Prompt context generation for Claude (component capabilities)
4. Easy extensibility for new component types

Usage:
======
    from app.ai.scene.registry import component_registry
    
    # Check if component exists
    if component_registry.exists("calendar_week"):
        definition = component_registry.get("calendar_week")
        
    # Get all calendar components
    calendar_components = component_registry.list_by_category("calendar")
    
    # Generate prompt context for AI
    context = component_registry.to_prompt_context()
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from enum import Enum


logger = logging.getLogger("jarvis.ai.scene.registry")


# ---------------------------------------------------------------------------
# COMPONENT CATEGORIES
# ---------------------------------------------------------------------------

class ComponentCategory(str, Enum):
    """Categories of display components."""
    CALENDAR = "calendar"       # Calendar views and widgets
    UTILITY = "utility"         # Clocks, weather, text blocks
    CONTENT = "content"         # Images, videos, web content
    SYSTEM = "system"           # System info, notifications


# ---------------------------------------------------------------------------
# COMPONENT DEFINITION
# ---------------------------------------------------------------------------

@dataclass
class ComponentDefinition:
    """
    Definition of a display component for Scene Graphs.
    
    This describes what a component is, what it requires, and what data it expects.
    The registry uses these definitions for:
    - Validation (ensuring only valid components are used)
    - Prompt generation (telling Claude what's available)
    - Documentation (describing component capabilities)
    
    Attributes:
        id: Unique component identifier (e.g., "calendar_week")
        name: Human-readable name (e.g., "Week View")
        description: What the component displays
        category: Component category for organization
        required_props: Props that must be provided
        optional_props: Props that may be provided
        data_schema: Description of the data structure this component expects
        examples: Example descriptions of when to use this component
    """
    id: str
    name: str
    description: str
    category: ComponentCategory
    required_props: Set[str] = field(default_factory=set)
    optional_props: Set[str] = field(default_factory=set)
    data_schema: Dict[str, str] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    
    def to_prompt_string(self) -> str:
        """
        Generate a prompt-friendly description for this component.
        
        Used when building prompts for Claude to understand available components.
        
        Returns:
            Formatted string describing the component
        """
        lines = [
            f"- {self.id}: {self.name}",
            f"  Description: {self.description}",
            f"  Category: {self.category.value}",
        ]
        
        if self.required_props:
            lines.append(f"  Required Props: {', '.join(self.required_props)}")
        
        if self.optional_props:
            lines.append(f"  Optional Props: {', '.join(self.optional_props)}")
        
        if self.data_schema:
            schema_items = [f"{k}: {v}" for k, v in self.data_schema.items()]
            lines.append(f"  Data Schema: {', '.join(schema_items)}")
        
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# COMPONENT REGISTRY
# ---------------------------------------------------------------------------

class ComponentRegistry:
    """
    Registry of all display components available for Scene Graphs.
    
    This is a singleton that maintains the master list of components
    with their definitions, validation rules, and metadata.
    
    Following the same pattern as ActionRegistry for consistency.
    """
    
    def __init__(self):
        """Initialize the registry with built-in components."""
        self._components: Dict[str, ComponentDefinition] = {}
        self._register_builtin_components()
        logger.info(f"Component registry initialized with {len(self._components)} components")
    
    def _register_builtin_components(self):
        """Register all built-in display components."""
        
        # -----------------------------------------------------------------------
        # CALENDAR COMPONENTS
        # -----------------------------------------------------------------------
        
        self.register(ComponentDefinition(
            id="calendar_day",
            name="Day View",
            description="Single day calendar with hourly time slots",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"date", "start_hour", "end_hour", "show_times"},
            data_schema={
                "events": "List of CalendarEvent objects for the day",
                "date": "ISO date string for the displayed day",
            },
            examples=[
                "Show today's schedule in detail",
                "Display a single day with all events",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="calendar_week",
            name="Week View",
            description="7-day calendar view showing the full week",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"week_start", "start_hour", "end_hour", "show_times"},
            data_schema={
                "events": "List of CalendarEvent objects for the week",
                "week_start": "ISO date string for the first day of the week",
            },
            examples=[
                "Show my weekly schedule",
                "Display the calendar for this week",
                "Calendar on the main screen",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="calendar_month",
            name="Month View",
            description="Monthly calendar grid showing the entire month",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"month", "year", "highlight_today"},
            data_schema={
                "events": "List of CalendarEvent objects for the month",
                "month": "Month number (1-12)",
                "year": "Year number",
            },
            examples=[
                "Show the monthly view",
                "Display December calendar",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="calendar_widget",
            name="Compact Widget",
            description="Compact calendar showing next 3-5 events",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"max_events", "show_date"},
            data_schema={
                "events": "List of next 3-5 CalendarEvent objects",
            },
            examples=[
                "Small calendar widget in the corner",
                "Compact upcoming events display",
                "Calendar in a dashboard",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="calendar_agenda",
            name="Agenda List",
            description="Vertical list of upcoming events with details",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"max_events", "show_descriptions", "group_by_day"},
            data_schema={
                "events": "List of CalendarEvent objects in chronological order",
            },
            examples=[
                "Show my agenda",
                "List my upcoming meetings",
                "Display schedule as a list",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # UTILITY COMPONENTS
        # -----------------------------------------------------------------------
        
        self.register(ComponentDefinition(
            id="clock_digital",
            name="Digital Clock",
            description="Digital clock display with time and optional date",
            category=ComponentCategory.UTILITY,
            required_props=set(),
            optional_props={"format", "show_seconds", "show_date"},
            data_schema={
                "timezone": "Timezone identifier (e.g., 'America/New_York')",
            },
            examples=[
                "Clock in the corner",
                "Digital time display",
                "Clock showing 24-hour format",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="clock_analog",
            name="Analog Clock",
            description="Traditional analog clock face with hour/minute hands",
            category=ComponentCategory.UTILITY,
            required_props=set(),
            optional_props={"show_numbers", "show_seconds"},
            data_schema={
                "timezone": "Timezone identifier",
            },
            examples=[
                "Classic analog clock",
                "Traditional clock face",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="weather_current",
            name="Current Weather",
            description="Current weather conditions with temperature and icon",
            category=ComponentCategory.UTILITY,
            required_props=set(),
            optional_props={"location", "units", "show_forecast"},
            data_schema={
                "temperature": "Current temperature value",
                "condition": "Weather condition (sunny, cloudy, rain)",
                "icon": "Weather icon identifier",
                "location": "Location name",
                "humidity": "Humidity percentage (optional)",
                "wind": "Wind speed (optional)",
            },
            examples=[
                "Weather widget",
                "Show current weather",
                "Temperature display",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="text_block",
            name="Text Display",
            description="Simple text block for messages or labels",
            category=ComponentCategory.UTILITY,
            required_props={"content"},
            optional_props={"font_size", "alignment", "wrap"},
            data_schema={
                "content": "Text content to display",
            },
            examples=[
                "Display a message",
                "Show text on screen",
                "Welcome message",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="spacer",
            name="Spacer",
            description="Empty space for layout purposes",
            category=ComponentCategory.UTILITY,
            required_props=set(),
            optional_props={"size", "min_size"},
            data_schema={},
            examples=[
                "Add spacing between components",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # CONTENT COMPONENTS
        # -----------------------------------------------------------------------
        
        self.register(ComponentDefinition(
            id="image_display",
            name="Image",
            description="Display an image from URL",
            category=ComponentCategory.CONTENT,
            required_props=set(),
            optional_props={"fit", "alt_text"},
            data_schema={
                "url": "Image URL to display",
                "alt": "Alternative text description",
            },
            examples=[
                "Show an image",
                "Display a photo",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="web_embed",
            name="Web Content",
            description="Embedded web content (iframe)",
            category=ComponentCategory.CONTENT,
            required_props=set(),
            optional_props={"sandbox", "allow"},
            data_schema={
                "url": "URL to embed",
            },
            examples=[
                "Embed a webpage",
                "Show web content",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # MEETING & EVENT DETAIL COMPONENTS (Sprint 4.0.1)
        # -----------------------------------------------------------------------
        
        self.register(ComponentDefinition(
            id="meeting_detail",
            name="Meeting Detail Card",
            description="Single meeting/event with full details including title, time, attendees, description, location, and linked documents. Use event_id or meeting_search props to specify which event to display. Sprint 4.3.2: Supports meeting_search for finding events by title/keywords.",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"show_attendees", "show_description", "show_location", "show_links", "event_id", "meeting_search"},
            data_schema={
                "event_id": "Google Calendar event ID (use in props to fetch specific event)",
                "meeting_search": "Search query to find event by title/keywords (use in props, e.g., 'South Beach plan')",
                "title": "Event title/summary",
                "start_time": "ISO datetime for event start",
                "end_time": "ISO datetime for event end",
                "location": "Event location (optional)",
                "description": "Event description (optional)",
                "attendees": "List of attendee emails (optional)",
                "linked_docs": "List of linked Google Doc URLs (optional)",
                "is_all_day": "Boolean indicating all-day event",
            },
            examples=[
                "Show my next meeting",
                "Display the team standup details",
                "Show meeting info on the left",
                "Show my plan for South Beach",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="countdown_timer",
            name="Countdown Timer",
            description="Timer showing countdown to a specific time or event. Can countdown to next meeting or custom time.",
            category=ComponentCategory.UTILITY,
            required_props=set(),
            optional_props={"target_time", "target_event_id", "format", "show_label"},
            data_schema={
                "target_time": "ISO datetime to count down to",
                "target_label": "Label to show (e.g., 'Team Standup')",
                "auto_next_event": "Boolean - automatically countdown to next event",
            },
            examples=[
                "Timer countdown to my next meeting",
                "Show countdown to 3pm",
                "Display timer in the corner",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="event_countdown",
            name="Event Countdown",
            description="Specialized countdown showing time until next calendar event with event title",
            category=ComponentCategory.CALENDAR,
            required_props=set(),
            optional_props={"show_event_title", "show_location"},
            data_schema={
                "next_event": "Next calendar event object",
                "time_until": "Formatted time string (e.g., '2h 30m')",
                "target_time": "ISO datetime of event start",
            },
            examples=[
                "How long until my next meeting",
                "Show time until standup",
                "Countdown to next event",
            ],
        ))
        
        # -----------------------------------------------------------------------
        # DOCUMENT COMPONENTS (Sprint 4.0.1 - Google Docs Integration)
        # -----------------------------------------------------------------------
        
        self.register(ComponentDefinition(
            id="doc_summary",
            name="Document Summary",
            description="Summary card showing Google Doc title, key points, and metadata. Useful for meeting prep displays. Can fetch doc by ID, URL, or by searching for a meeting's linked document. Use content_request for AI-generated custom content.",
            category=ComponentCategory.CONTENT,
            required_props=set(),
            optional_props={
                "max_points", "show_modified_date", "show_owner", 
                "doc_id", "doc_url", "meeting_search", "event_id",
                "content_request",  # AI: Natural language description of what to generate
                "content_type",     # AI: Category hint (impact_phrases, script, key_points, action_items, summary, custom)
                "max_chars",
            },
            data_schema={
                "doc_id": "Google Doc ID",
                "title": "Document title",
                "summary": "AI-generated summary or first paragraph",
                "key_points": "List of key bullet points (optional)",
                "generated_content": "AI-generated custom content (when content_request is specified)",
                "content_type": "Type of generated content",
                "last_modified": "ISO datetime of last modification",
                "owner": "Document owner name/email",
                "url": "Full document URL",
            },
            examples=[
                "Show summary of the meeting doc",
                "Display document overview",
                "Meeting agenda summary",
                "Generate 3 impact phrases from the document",
                "Create a structured script from the meeting doc",
            ],
        ))
        
        self.register(ComponentDefinition(
            id="doc_preview",
            name="Document Preview",
            description="Preview panel showing document content snippet. Can display first few paragraphs of a Google Doc. Use meeting_search prop to find doc linked to a calendar event. Use content_request for AI-generated custom content.",
            category=ComponentCategory.CONTENT,
            required_props=set(),
            optional_props={
                "max_chars", "show_title", 
                "doc_id", "doc_url", "meeting_search", "event_id",
                "content_request",  # AI: Natural language description of what to generate
                "content_type",     # AI: Category hint (impact_phrases, script, key_points, action_items, summary, custom)
            },
            data_schema={
                "doc_id": "Google Doc ID",
                "title": "Document title",
                "preview_text": "First portion of document text",
                "generated_content": "AI-generated custom content (when content_request is specified)",
                "content_type": "Type of generated content",
                "url": "Full document URL",
            },
            examples=[
                "Preview the notes document",
                "Show meeting notes",
                "Show the document from my standup meeting",
                "Extract key decisions from the doc",
                "Show action items from the meeting",
            ],
        ))
    
    # ---------------------------------------------------------------------------
    # REGISTRY OPERATIONS
    # ---------------------------------------------------------------------------
    
    def register(self, component: ComponentDefinition) -> None:
        """
        Register a component in the registry.
        
        Args:
            component: ComponentDefinition to register
        """
        self._components[component.id] = component
        logger.debug(f"Registered component: {component.id}")
    
    def get(self, component_id: str) -> Optional[ComponentDefinition]:
        """
        Get a component definition by ID.
        
        Args:
            component_id: Component identifier
            
        Returns:
            ComponentDefinition if found, None otherwise
        """
        return self._components.get(component_id)
    
    def exists(self, component_id: str) -> bool:
        """Check if a component exists in the registry."""
        return component_id in self._components
    
    def list_all(self) -> List[ComponentDefinition]:
        """Get all registered components."""
        return list(self._components.values())
    
    def list_by_category(self, category: str) -> List[ComponentDefinition]:
        """
        Get all components in a specific category.
        
        Args:
            category: Category name (string or ComponentCategory enum)
            
        Returns:
            List of ComponentDefinitions in that category
        """
        if isinstance(category, ComponentCategory):
            category_val = category
        else:
            try:
                category_val = ComponentCategory(category.lower())
            except ValueError:
                return []
        
        return [c for c in self._components.values() if c.category == category_val]
    
    def list_ids(self) -> List[str]:
        """Get all registered component IDs."""
        return list(self._components.keys())
    
    def get_by_category(self) -> Dict[ComponentCategory, List[ComponentDefinition]]:
        """Get components grouped by category."""
        result: Dict[ComponentCategory, List[ComponentDefinition]] = {}
        for component in self._components.values():
            if component.category not in result:
                result[component.category] = []
            result[component.category].append(component)
        return result
    
    def validate_component_type(self, component_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate that a component type exists.
        
        Args:
            component_type: The component type to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if self.exists(component_type):
            return True, None
        
        # Suggest similar components
        suggestions = [c for c in self._components.keys() if component_type.split("_")[0] in c]
        if suggestions:
            return False, f"Unknown component '{component_type}'. Did you mean: {', '.join(suggestions)}?"
        return False, f"Unknown component '{component_type}'. Use component_registry.list_ids() to see available components."
    
    def to_prompt_context(self) -> str:
        """
        Generate prompt context string for Claude.
        
        This creates a formatted string describing all available components,
        suitable for injection into Claude's system prompt.
        
        Returns:
            Formatted string describing all components
        """
        lines = ["AVAILABLE DISPLAY COMPONENTS:\n"]
        
        for category in ComponentCategory:
            components = self.list_by_category(category)
            if components:
                lines.append(f"\n## {category.value.upper()}")
                for component in components:
                    lines.append(component.to_prompt_string())
        
        return "\n".join(lines)
    
    def get_calendar_component_types(self) -> List[str]:
        """Get all calendar component type IDs."""
        return [c.id for c in self.list_by_category("calendar")]
    
    def get_component_for_hint(self, hint: str) -> Optional[str]:
        """
        Map a layout hint to a specific component type.
        
        Used when normalizing user hints like "calendar" to specific
        component types like "calendar_week".
        
        Args:
            hint: User hint (e.g., "calendar", "clock", "weather")
            
        Returns:
            Best matching component ID or None
        """
        hint_lower = hint.lower().strip()
        
        # Direct match
        if hint_lower in self._components:
            return hint_lower
        
        # Check with underscores replaced
        hint_normalized = hint_lower.replace(" ", "_")
        if hint_normalized in self._components:
            return hint_normalized
        
        # Category-based defaults
        category_defaults = {
            "calendar": "calendar_week",
            "agenda": "calendar_agenda",
            "schedule": "calendar_week",
            "events": "calendar_agenda",
            "clock": "clock_digital",
            "time": "clock_digital",
            "weather": "weather_current",
            "text": "text_block",
            "message": "text_block",
            # New mappings for Sprint 4.0.1
            "meeting": "meeting_detail",
            "next meeting": "meeting_detail",
            "countdown": "countdown_timer",
            "timer": "countdown_timer",
            "document": "doc_summary",
            "doc": "doc_summary",
            "summary": "doc_summary",
            "notes": "doc_preview",
        }
        
        for keyword, component_id in category_defaults.items():
            if keyword in hint_lower:
                return component_id
        
        return None


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

component_registry = ComponentRegistry()
