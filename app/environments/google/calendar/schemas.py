"""
Google Calendar Schemas - Data structures for calendar operations.

These Pydantic models represent Google Calendar API responses
in a clean, typed format for use throughout the application.

Reference: https://developers.google.com/calendar/api/v3/reference
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EventTime(BaseModel):
    """
    Event start or end time.
    
    Google Calendar API returns times in one of two formats:
    - dateTime: For timed events (e.g., "2024-01-15T10:00:00-05:00")
    - date: For all-day events (e.g., "2024-01-15")
    
    We normalize this into a consistent structure.
    """
    date_time: Optional[datetime] = Field(None, alias="dateTime")
    date: Optional[str] = Field(None)  # YYYY-MM-DD format for all-day events
    time_zone: Optional[str] = Field(None, alias="timeZone")
    
    def is_all_day(self) -> bool:
        """Check if this is an all-day event (date only, no time)."""
        return self.date is not None and self.date_time is None
    
    def get_datetime(self) -> Optional[datetime]:
        """Get the datetime, parsing date string if needed."""
        if self.date_time:
            return self.date_time
        if self.date:
            # Parse YYYY-MM-DD string to datetime
            return datetime.strptime(self.date, "%Y-%m-%d")
        return None
    
    class Config:
        populate_by_name = True


class EventAttendee(BaseModel):
    """
    Event attendee information.
    
    Represents a person invited to a calendar event.
    """
    email: str = Field(..., description="Attendee's email address")
    display_name: Optional[str] = Field(None, alias="displayName")
    organizer: Optional[bool] = Field(False, description="Is this person the organizer?")
    self_: Optional[bool] = Field(False, alias="self", description="Is this the current user?")
    response_status: Optional[str] = Field(None, alias="responseStatus")
    
    class Config:
        populate_by_name = True


class CalendarEvent(BaseModel):
    """
    A Google Calendar event.
    
    Contains the essential fields from the Google Calendar API event resource.
    Additional fields can be added as needed.
    
    Reference: https://developers.google.com/calendar/api/v3/reference/events
    """
    id: str = Field(..., description="Unique event identifier")
    summary: Optional[str] = Field(None, description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    
    # Times
    start: Optional[EventTime] = Field(None, description="Event start time")
    end: Optional[EventTime] = Field(None, description="Event end time")
    
    # Status
    status: Optional[str] = Field(None, description="confirmed, tentative, cancelled")
    
    # Meeting info
    hangout_link: Optional[str] = Field(None, alias="hangoutLink")
    html_link: Optional[str] = Field(None, alias="htmlLink")
    
    # Attendees (optional, requires additional scope)
    attendees: Optional[List[EventAttendee]] = Field(None)
    
    # Recurrence
    recurring_event_id: Optional[str] = Field(None, alias="recurringEventId")
    
    # Visual
    color_id: Optional[str] = Field(None, alias="colorId")
    
    # Creator/Organizer
    creator: Optional[Dict[str, Any]] = Field(None)
    organizer: Optional[Dict[str, Any]] = Field(None)
    
    class Config:
        populate_by_name = True
    
    def is_all_day(self) -> bool:
        """Check if this is an all-day event."""
        if self.start:
            return self.start.is_all_day()
        return False
    
    def get_display_title(self) -> str:
        """Get a display-friendly title (with fallback)."""
        return self.summary or "(No title)"
    
    def get_time_display(self) -> str:
        """Get a formatted time string for display."""
        if not self.start:
            return ""
        
        if self.is_all_day():
            return "All Day"
        
        start_dt = self.start.get_datetime()
        if start_dt:
            return start_dt.strftime("%I:%M %p").lstrip("0")
        
        return ""


class CalendarInfo(BaseModel):
    """
    Information about a Google Calendar.
    
    Used when listing available calendars.
    """
    id: str = Field(..., description="Calendar identifier (usually email)")
    summary: str = Field(..., description="Calendar title")
    description: Optional[str] = Field(None)
    primary: Optional[bool] = Field(False, description="Is this the primary calendar?")
    background_color: Optional[str] = Field(None, alias="backgroundColor")
    foreground_color: Optional[str] = Field(None, alias="foregroundColor")
    access_role: Optional[str] = Field(None, alias="accessRole")
    
    class Config:
        populate_by_name = True


class CalendarEventsResponse(BaseModel):
    """
    Response from the Calendar Events list API.
    
    Contains a list of events and pagination info.
    """
    kind: Optional[str] = Field(None)
    summary: Optional[str] = Field(None, description="Calendar title")
    time_zone: Optional[str] = Field(None, alias="timeZone")
    items: List[CalendarEvent] = Field(default_factory=list)
    next_page_token: Optional[str] = Field(None, alias="nextPageToken")
    
    class Config:
        populate_by_name = True


class CalendarListResponse(BaseModel):
    """
    Response from the CalendarList API.
    
    Contains a list of calendars the user has access to.
    """
    kind: Optional[str] = Field(None)
    items: List[CalendarInfo] = Field(default_factory=list)
    next_page_token: Optional[str] = Field(None, alias="nextPageToken")
    
    class Config:
        populate_by_name = True
