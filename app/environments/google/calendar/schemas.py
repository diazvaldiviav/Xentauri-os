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


class EventAttachment(BaseModel):
    """
    An attachment on a calendar event.
    
    Attachments can be Google Drive files, Google Docs, etc.
    Reference: https://developers.google.com/calendar/api/v3/reference/events
    """
    file_url: Optional[str] = Field(None, alias="fileUrl", description="URL to the attachment")
    title: Optional[str] = Field(None, description="Attachment title")
    mime_type: Optional[str] = Field(None, alias="mimeType", description="MIME type")
    icon_link: Optional[str] = Field(None, alias="iconLink", description="Icon URL")
    file_id: Optional[str] = Field(None, alias="fileId", description="Drive file ID")
    
    class Config:
        populate_by_name = True
    
    def is_google_doc(self) -> bool:
        """Check if this attachment is a Google Doc."""
        if self.mime_type:
            return "document" in self.mime_type.lower()
        if self.file_url:
            return "docs.google.com/document" in self.file_url
        return False
    
    def get_doc_id(self) -> Optional[str]:
        """Extract Google Doc ID from the attachment."""
        if not self.file_url:
            return self.file_id
        
        # Extract from URL like: https://docs.google.com/document/d/{docId}/...
        import re
        match = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", self.file_url)
        if match:
            return match.group(1)
        return self.file_id


class ExtendedProperties(BaseModel):
    """
    Extended properties for a calendar event.
    
    Custom key-value pairs stored on an event.
    - private: Only visible to the user who set them
    - shared: Visible to all attendees
    
    Sprint 3.9: Used to store linked document IDs.
    """
    private: Optional[Dict[str, str]] = Field(None)
    shared: Optional[Dict[str, str]] = Field(None)
    
    class Config:
        populate_by_name = True
    
    def get_linked_doc_id(self) -> Optional[str]:
        """Get the linked Google Doc ID if one is stored."""
        if self.private and "linked_doc_id" in self.private:
            return self.private["linked_doc_id"]
        if self.shared and "linked_doc_id" in self.shared:
            return self.shared["linked_doc_id"]
        return None


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
    
    # Attachments (Sprint 3.9 - for linked documents)
    attachments: Optional[List[EventAttachment]] = Field(None, description="File attachments")
    
    # Extended properties (Sprint 3.9 - for custom data like linked doc IDs)
    extended_properties: Optional[ExtendedProperties] = Field(None, alias="extendedProperties")
    
    # Conference data (for Meet/Zoom links)
    conference_data: Optional[Dict[str, Any]] = Field(None, alias="conferenceData")
    
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
    
    def get_linked_doc_id(self) -> Optional[str]:
        """
        Get the linked Google Doc ID from this event.
        
        Sprint 3.9: Checks extended properties first, then attachments.
        
        Returns:
            Document ID if found, None otherwise
        """
        # First check extended properties (manually linked)
        if self.extended_properties:
            doc_id = self.extended_properties.get_linked_doc_id()
            if doc_id:
                return doc_id
        
        # Then check attachments (Drive attachments)
        if self.attachments:
            for attachment in self.attachments:
                if attachment.is_google_doc():
                    doc_id = attachment.get_doc_id()
                    if doc_id:
                        return doc_id
        
        # Check description for embedded doc links
        if self.description:
            import re
            match = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", self.description)
            if match:
                return match.group(1)
        
        return None
    
    def get_all_linked_doc_ids(self) -> List[str]:
        """
        Get all linked Google Doc IDs from this event.
        
        Returns all document IDs found in:
        - Extended properties
        - Attachments
        - Description links
        
        Returns:
            List of document IDs (may be empty)
        """
        doc_ids = []
        
        # From extended properties
        if self.extended_properties:
            doc_id = self.extended_properties.get_linked_doc_id()
            if doc_id and doc_id not in doc_ids:
                doc_ids.append(doc_id)
        
        # From attachments
        if self.attachments:
            for attachment in self.attachments:
                if attachment.is_google_doc():
                    doc_id = attachment.get_doc_id()
                    if doc_id and doc_id not in doc_ids:
                        doc_ids.append(doc_id)
        
        # From description
        if self.description:
            import re
            matches = re.findall(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", self.description)
            for doc_id in matches:
                if doc_id not in doc_ids:
                    doc_ids.append(doc_id)
        
        return doc_ids
    
    def get_meet_link(self) -> Optional[str]:
        """
        Get the Google Meet link for this event.
        
        Returns:
            Meet URL if available, None otherwise
        """
        # Check hangoutLink first (older style)
        if self.hangout_link:
            return self.hangout_link
        
        # Check conferenceData (newer style)
        if self.conference_data:
            entry_points = self.conference_data.get("entryPoints", [])
            for entry in entry_points:
                if entry.get("entryPointType") == "video":
                    return entry.get("uri")
        
        return None


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


# ---------------------------------------------------------------------------
# EVENT CREATION SCHEMAS (Sprint 3.8)
# ---------------------------------------------------------------------------

class EventCreateRequest(BaseModel):
    """
    Request schema for creating a calendar event.
    
    Supports both timed events (with start_datetime/end_datetime)
    and all-day events (with start_date/end_date).
    
    For timed events:
        EventCreateRequest(
            summary="Team Meeting",
            start_datetime=datetime(2025, 1, 15, 18, 0),
            end_datetime=datetime(2025, 1, 15, 19, 0),
            timezone="America/New_York",
        )
    
    For all-day events:
        EventCreateRequest(
            summary="Birthday",
            start_date=date(2025, 1, 15),
            end_date=date(2025, 1, 16),  # All-day events are exclusive
        )
    """
    summary: str = Field(..., description="Event title/summary")
    
    # For timed events
    start_datetime: Optional[datetime] = Field(None, description="Start time for timed events")
    end_datetime: Optional[datetime] = Field(None, description="End time for timed events")
    
    # For all-day events
    start_date: Optional[date] = Field(None, description="Start date for all-day events")
    end_date: Optional[date] = Field(None, description="End date for all-day events (exclusive)")
    
    # Common fields
    timezone: str = Field(default="UTC", description="Timezone for the event (e.g., America/New_York)")
    location: Optional[str] = Field(None, description="Event location")
    description: Optional[str] = Field(None, description="Event description")
    recurrence: Optional[List[str]] = Field(None, description="Recurrence rules (RRULE format)")
    
    def is_all_day(self) -> bool:
        """Check if this is an all-day event."""
        return self.start_date is not None and self.start_datetime is None
    
    def is_valid(self) -> bool:
        """Check if the request has valid time/date fields."""
        # Must have either datetime pair or date pair
        has_datetime = self.start_datetime is not None and self.end_datetime is not None
        has_date = self.start_date is not None and self.end_date is not None
        return has_datetime or has_date


class EventCreateResponse(BaseModel):
    """
    Response schema after creating a calendar event.
    
    Contains the key details of the created event.
    """
    event_id: str = Field(..., description="Google Calendar event ID")
    summary: str = Field(..., description="Event title/summary")
    start: datetime | date = Field(..., description="Event start time/date")
    end: datetime | date = Field(..., description="Event end time/date")
    html_link: str = Field(..., description="Link to view event in Google Calendar")
    
    # Optional fields
    timezone: Optional[str] = Field(None, description="Event timezone")
    location: Optional[str] = Field(None, description="Event location")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring event")


# ---------------------------------------------------------------------------
# EVENT UPDATE SCHEMAS (Sprint 3.9)
# ---------------------------------------------------------------------------

class EventUpdateRequest(BaseModel):
    """
    Request schema for updating an existing calendar event.
    
    Only include fields that should be changed.
    None values are ignored (field will remain unchanged).
    
    Example:
        # Change just the time
        EventUpdateRequest(
            start_datetime=datetime(2025, 1, 15, 15, 0),
            end_datetime=datetime(2025, 1, 15, 16, 0),
        )
        
        # Change title and location
        EventUpdateRequest(
            summary="New Title",
            location="Conference Room B",
        )
    """
    summary: Optional[str] = Field(None, description="New event title")
    
    # For timed events
    start_datetime: Optional[datetime] = Field(None, description="New start time")
    end_datetime: Optional[datetime] = Field(None, description="New end time")
    
    # For all-day events
    start_date: Optional[date] = Field(None, description="New start date (all-day)")
    end_date: Optional[date] = Field(None, description="New end date (all-day)")
    
    # Common fields
    timezone: Optional[str] = Field(None, description="Timezone for the event")
    location: Optional[str] = Field(None, description="New location")
    description: Optional[str] = Field(None, description="New description")
    
    def has_changes(self) -> bool:
        """Check if any field is set."""
        return any([
            self.summary,
            self.start_datetime,
            self.end_datetime,
            self.start_date,
            self.end_date,
            self.location,
            self.description,
        ])
    
    def has_time_changes(self) -> bool:
        """Check if time/date fields are being changed."""
        return any([
            self.start_datetime,
            self.end_datetime,
            self.start_date,
            self.end_date,
        ])


class EventSearchResult(BaseModel):
    """
    Result from searching calendar events.
    
    Contains matching events plus metadata about the search.
    """
    events: List[CalendarEvent] = Field(default_factory=list)
    query: str = Field(..., description="The search query used")
    total_count: int = Field(0, description="Number of matching events")
    
    def is_empty(self) -> bool:
        """Check if no events were found."""
        return len(self.events) == 0
    
    def has_single_match(self) -> bool:
        """Check if exactly one event was found."""
        return len(self.events) == 1
    
    def needs_disambiguation(self) -> bool:
        """Check if multiple events need user selection."""
        return len(self.events) > 1

