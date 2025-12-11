"""
Google Calendar Module - Calendar API Integration

This module provides integration with Google Calendar API, allowing
Jarvis to fetch and display calendar events on Raspberry Pi screens.

Features:
=========
- List upcoming calendar events
- Render events as HTML for display
- Support for multiple calendars
- Event filtering and formatting

Future Extensions:
==================
- Create/update events (with write scopes)
- Calendar color coding
- Recurring event handling
- Meeting room availability
"""

from app.environments.google.calendar.client import GoogleCalendarClient
from app.environments.google.calendar.schemas import (
    CalendarEvent,
    CalendarInfo,
    EventAttendee,
    EventTime,
)
from app.environments.google.calendar.renderer import CalendarRenderer

__all__ = [
    "GoogleCalendarClient",
    "CalendarEvent",
    "CalendarInfo",
    "EventAttendee",
    "EventTime",
    "CalendarRenderer",
]
