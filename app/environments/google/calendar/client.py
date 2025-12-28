"""
Google Calendar API Client - Fetch and manage calendar events.

This client provides methods to interact with the Google Calendar API.
It handles API requests, error handling, and response parsing.

Key Features:
=============
1. List upcoming events from primary calendar
2. List available calendars
3. Automatic token refresh (when integrated with credential store)
4. Clean error handling with specific exceptions

API Reference:
==============
- Events API: https://developers.google.com/calendar/api/v3/reference/events
- CalendarList API: https://developers.google.com/calendar/api/v3/reference/calendarList

Usage Example:
==============
    from app.environments.google.calendar import GoogleCalendarClient
    
    client = GoogleCalendarClient(access_token="ya29.xxx")
    
    # Get upcoming events
    events = await client.list_upcoming_events(max_results=10)
    for event in events:
        print(f"{event.get_time_display()} - {event.get_display_title()}")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx

from app.environments.base import EnvironmentService, APIError
from app.environments.google.calendar.schemas import (
    CalendarEvent,
    CalendarInfo,
    CalendarEventsResponse,
    CalendarListResponse,
)


logger = logging.getLogger("jarvis.environments.google.calendar")


class GoogleCalendarClient(EnvironmentService):
    """
    Google Calendar API client.
    
    Provides methods to fetch calendar events and calendar metadata.
    Requires a valid access token with calendar.readonly scope.
    
    Attributes:
        access_token: Google OAuth access token with calendar scope
        
    Example:
        client = GoogleCalendarClient(access_token="ya29.xxx")
        events = await client.list_upcoming_events()
    """
    
    # Service identification
    service_name = "calendar"
    required_scopes = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",  # Sprint 3.8: Write access for event creation
    ]
    
    # Google Calendar API base URL
    BASE_URL = "https://www.googleapis.com/calendar/v3"
    
    def __init__(self, access_token: str):
        """
        Initialize the Calendar client.
        
        Args:
            access_token: Valid Google OAuth access token with calendar scope
        """
        self.access_token = access_token
        self._http_client: Optional[httpx.AsyncClient] = None
    
    # -------------------------------------------------------------------------
    # HTTP CLIENT MANAGEMENT
    # -------------------------------------------------------------------------
    
    def _get_headers(self) -> dict:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Make an authenticated request to the Calendar API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/calendars/primary/events")
            params: Query parameters
        
        Returns:
            Parsed JSON response
        
        Raises:
            APIError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )
                
                if response.status_code == 401:
                    logger.error("Calendar API: Unauthorized (token may be expired)")
                    raise APIError(
                        "Unauthorized - access token may be expired",
                        status_code=401,
                        response=response.text,
                    )
                
                if response.status_code == 403:
                    logger.error("Calendar API: Forbidden (scope may be missing)")
                    raise APIError(
                        "Forbidden - calendar scope may not be granted",
                        status_code=403,
                        response=response.text,
                    )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Calendar API error: {response.status_code} - {error_detail}")
                    raise APIError(
                        f"API request failed: {error_detail}",
                        status_code=response.status_code,
                        response=error_detail,
                    )
                
                return response.json()
                
            except httpx.RequestError as e:
                logger.error(f"Network error in Calendar API: {e}")
                raise APIError(f"Network error: {e}")
    
    # -------------------------------------------------------------------------
    # CALENDAR EVENTS
    # -------------------------------------------------------------------------
    
    async def list_upcoming_events(
        self,
        calendar_id: str = "primary",
        max_results: int = 10,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> List[CalendarEvent]:
        """
        List upcoming events from a calendar.
        
        Args:
            calendar_id: Calendar identifier ("primary" for user's main calendar)
            max_results: Maximum number of events to return (1-2500)
            time_min: Start of time range (defaults to now)
            time_max: End of time range (optional)
            single_events: Expand recurring events into individual instances
            order_by: Sort order ("startTime" or "updated")
        
        Returns:
            List of CalendarEvent objects
        
        Example:
            # Get next 10 events starting from now
            events = await client.list_upcoming_events(max_results=10)
            
            # Get events for the next 7 days
            events = await client.list_upcoming_events(
                time_min=datetime.now(timezone.utc),
                time_max=datetime.now(timezone.utc) + timedelta(days=7),
            )
        """
        # Default time_min to now if not specified
        if time_min is None:
            time_min = datetime.now(timezone.utc)
        
        # Format times in RFC3339 format
        params = {
            "maxResults": min(max_results, 2500),
            "timeMin": time_min.isoformat(),
            "singleEvents": str(single_events).lower(),
            "orderBy": order_by,
        }
        
        if time_max:
            params["timeMax"] = time_max.isoformat()
        
        logger.info(
            f"Fetching calendar events",
            extra={
                "calendar_id": calendar_id,
                "max_results": max_results,
                "time_min": time_min.isoformat(),
            }
        )
        
        # Make API request
        response_data = await self._make_request(
            method="GET",
            endpoint=f"/calendars/{calendar_id}/events",
            params=params,
        )
        
        # Parse response
        events_response = CalendarEventsResponse(**response_data)
        
        logger.info(f"Fetched {len(events_response.items)} calendar events")
        
        return events_response.items
    
    async def list_today_events(
        self,
        calendar_id: str = "primary",
        max_results: int = 50,
    ) -> List[CalendarEvent]:
        """
        List events for today only.
        
        Convenience method to get all events from midnight to midnight.
        
        Args:
            calendar_id: Calendar identifier
            max_results: Maximum events to return
        
        Returns:
            List of CalendarEvent objects for today
        """
        now = datetime.now(timezone.utc)
        
        # Start of today (midnight UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # End of today (just before midnight UTC)
        today_end = today_start + timedelta(days=1)
        
        return await self.list_upcoming_events(
            calendar_id=calendar_id,
            max_results=max_results,
            time_min=today_start,
            time_max=today_end,
        )
    
    async def list_events_for_date(
        self,
        date: str,
        calendar_id: str = "primary",
        max_results: int = 50,
    ) -> List[CalendarEvent]:
        """
        List events for a specific date.
        
        Sprint 3.6: Support date-specific calendar queries.
        
        Args:
            date: Date in ISO format (YYYY-MM-DD) or datetime object
            calendar_id: Calendar identifier
            max_results: Maximum events to return
        
        Returns:
            List of CalendarEvent objects for the specified date
            
        Example:
            # Get events for December 6, 2025
            events = await client.list_events_for_date("2025-12-06")
        """
        # Parse the date
        if isinstance(date, str):
            try:
                # Parse YYYY-MM-DD format
                date_obj = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                logger.error(f"Invalid date format: {date}")
                raise ValueError(f"Date must be in YYYY-MM-DD format, got: {date}")
        else:
            date_obj = date
        
        # Start of the day (midnight UTC)
        day_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # End of the day (just before midnight UTC)
        day_end = day_start + timedelta(days=1)
        
        logger.info(f"Fetching events for date: {date_obj.date()}")
        
        return await self.list_upcoming_events(
            calendar_id=calendar_id,
            max_results=max_results,
            time_min=day_start,
            time_max=day_end,
        )
    
    async def list_week_events(
        self,
        calendar_id: str = "primary",
        max_results: int = 100,
    ) -> List[CalendarEvent]:
        """
        List events for the next 7 days.
        
        Convenience method for weekly view.
        
        Args:
            calendar_id: Calendar identifier
            max_results: Maximum events to return
        
        Returns:
            List of CalendarEvent objects for the next 7 days
        """
        now = datetime.now(timezone.utc)
        week_end = now + timedelta(days=7)
        
        return await self.list_upcoming_events(
            calendar_id=calendar_id,
            max_results=max_results,
            time_min=now,
            time_max=week_end,
        )
    
    # -------------------------------------------------------------------------
    # CALENDAR SEARCH (Sprint 3.7)
    # -------------------------------------------------------------------------
    
    async def search_events(
        self,
        query: str,
        calendar_id: str = "primary",
        max_results: int = 50,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        """
        Search calendar events by text query.
        
        Sprint 3.7: Search events using Google Calendar API 'q' parameter.
        Searches event title, description, location, and attendees.
        
        Args:
            query: Search text (searches title, description, location)
            calendar_id: Calendar identifier ("primary" for main calendar)
            max_results: Maximum number of events to return (1-2500)
            time_min: Start of time range (defaults to now)
            time_max: End of time range (optional, defaults to 1 year ahead)
        
        Returns:
            List of CalendarEvent objects matching the query, sorted by start time
        
        Example:
            # Find birthday events
            events = await client.search_events("birthday")
            
            # Find dentist appointments this month
            events = await client.search_events(
                "dentist",
                time_max=datetime.now(timezone.utc) + timedelta(days=30),
            )
        """
        # Return empty list for empty query (don't error)
        if not query or not query.strip():
            logger.info("Search called with empty query, returning empty list")
            return []
        
        query = query.strip()
        
        # Default time_min to now if not specified
        if time_min is None:
            time_min = datetime.now(timezone.utc)
        
        # Default time_max to 1 year ahead if not specified
        if time_max is None:
            time_max = time_min + timedelta(days=365)
        
        params = {
            "q": query,
            "maxResults": min(max_results, 2500),
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        
        logger.info(
            f"Searching calendar events",
            extra={
                "calendar_id": calendar_id,
                "query": query,
                "max_results": max_results,
            }
        )
        
        try:
            response_data = await self._make_request(
                method="GET",
                endpoint=f"/calendars/{calendar_id}/events",
                params=params,
            )
            
            events_response = CalendarEventsResponse(**response_data)
            
            logger.info(
                f"Search found {len(events_response.items)} events for query '{query}'"
            )
            
            return events_response.items
            
        except APIError as e:
            logger.error(f"Calendar search failed for query '{query}': {e}")
            raise
    
    async def find_event_by_name(
        self,
        name: str,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
    ) -> Optional[CalendarEvent]:
        """
        Find the nearest upcoming event matching a name.
        
        Sprint 3.7: Convenience method for finding a specific event.
        Returns the first (nearest) matching event.
        
        Args:
            name: Event name to search for (partial match)
            calendar_id: Calendar identifier
            time_min: Start of time range (defaults to now)
            time_max: End of time range (optional)
        
        Returns:
            The nearest matching CalendarEvent, or None if not found
        
        Example:
            # Find next dentist appointment
            event = await client.find_event_by_name("dentist")
            if event:
                print(f"Found: {event.get_display_title()} at {event.get_time_display()}")
        """
        events = await self.search_events(
            query=name,
            calendar_id=calendar_id,
            max_results=1,
            time_min=time_min,
            time_max=time_max,
        )
        
        return events[0] if events else None
    
    # -------------------------------------------------------------------------
    # CALENDAR QUERY METHODS (Sprint 3.8)
    # -------------------------------------------------------------------------
    # These methods return text responses for calendar questions
    
    async def get_event_count_text(
        self,
        date_range: Optional[str] = None,
        search_term: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> str:
        """
        Get a text response for "How many events?" queries.
        
        Sprint 3.8: Returns human-readable count of events.
        
        Args:
            date_range: "today", "tomorrow", "this_week", or YYYY-MM-DD
            search_term: Optional filter (e.g., "meeting")
            calendar_id: Calendar identifier
        
        Returns:
            Human-readable text response
        
        Example:
            # "How many events do I have today?"
            text = await client.get_event_count_text(date_range="today")
            # Returns: "You have 3 events scheduled for today."
        """
        # Get user's timezone for accurate date parsing
        user_timezone = await self.get_user_timezone(calendar_id)
        time_min, time_max = self._parse_date_range(date_range, user_timezone)
        
        try:
            if search_term:
                events = await self.search_events(
                    query=search_term,
                    calendar_id=calendar_id,
                    time_min=time_min,
                    time_max=time_max,
                )
            else:
                events = await self.list_upcoming_events(
                    calendar_id=calendar_id,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=100,
                )
            
            count = len(events)
            period = self._get_period_text(date_range)
            
            if count == 0:
                if search_term:
                    return f"You don't have any {search_term} events scheduled{period}."
                return f"You don't have any events scheduled{period}."
            elif count == 1:
                event = events[0]
                if search_term:
                    return f"You have 1 {search_term} event{period}: {event.get_display_title()} at {event.get_time_display()}."
                return f"You have 1 event{period}: {event.get_display_title()} at {event.get_time_display()}."
            else:
                if search_term:
                    return f"You have {count} {search_term} events scheduled{period}."
                return f"You have {count} events scheduled{period}."
                
        except APIError as e:
            logger.error(f"Failed to count events: {e}")
            return "I couldn't access your calendar. Please check your connection."
    
    async def get_next_event_text(
        self,
        search_term: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> str:
        """
        Get a text response for "What's my next event?" queries.
        
        Sprint 3.8: Returns details about the next upcoming event.
        
        Args:
            search_term: Optional filter (e.g., "meeting")
            calendar_id: Calendar identifier
        
        Returns:
            Human-readable text response
        
        Example:
            # "What's my next meeting?"
            text = await client.get_next_event_text(search_term="meeting")
            # Returns: "Your next meeting is 'Team Standup' at 9:00 AM today."
        """
        try:
            if search_term:
                events = await self.search_events(
                    query=search_term,
                    calendar_id=calendar_id,
                    max_results=1,
                )
            else:
                events = await self.list_upcoming_events(
                    calendar_id=calendar_id,
                    max_results=1,
                )
            
            if not events:
                if search_term:
                    return f"You don't have any upcoming {search_term} events."
                return "You don't have any upcoming events."
            
            event = events[0]
            title = event.get_display_title()
            time_str = event.get_time_display()
            
            # Format relative time
            if event.start_datetime:
                now = datetime.now(timezone.utc)
                delta = event.start_datetime - now
                
                if delta.days == 0:
                    relative = "today"
                elif delta.days == 1:
                    relative = "tomorrow"
                elif delta.days < 7:
                    relative = f"on {event.start_datetime.strftime('%A')}"
                else:
                    relative = f"on {event.start_datetime.strftime('%B %d')}"
                
                if search_term:
                    return f"Your next {search_term} is '{title}' at {time_str} {relative}."
                return f"Your next event is '{title}' at {time_str} {relative}."
            
            if search_term:
                return f"Your next {search_term} is '{title}' at {time_str}."
            return f"Your next event is '{title}' at {time_str}."
            
        except APIError as e:
            logger.error(f"Failed to get next event: {e}")
            return "I couldn't access your calendar. Please check your connection."
    
    async def get_events_list_text(
        self,
        date_range: Optional[str] = None,
        search_term: Optional[str] = None,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> str:
        """
        Get a text list of events for "List my events" queries.
        
        Sprint 3.8: Returns formatted list of events.
        
        Args:
            date_range: "today", "tomorrow", "this_week", or YYYY-MM-DD
            search_term: Optional filter (e.g., "meeting")
            calendar_id: Calendar identifier
            max_results: Maximum events to list
        
        Returns:
            Human-readable list of events
        
        Example:
            # "List my events for tomorrow"
            text = await client.get_events_list_text(date_range="tomorrow")
            # Returns: "Your events for tomorrow:\n• 9:00 AM - Team standup\n• 2:00 PM - Design review"
        """
        # Get user's timezone for accurate date parsing
        user_timezone = await self.get_user_timezone(calendar_id)
        time_min, time_max = self._parse_date_range(date_range, user_timezone)
        
        try:
            if search_term:
                events = await self.search_events(
                    query=search_term,
                    calendar_id=calendar_id,
                    max_results=max_results,
                    time_min=time_min,
                    time_max=time_max,
                )
            else:
                events = await self.list_upcoming_events(
                    calendar_id=calendar_id,
                    max_results=max_results,
                    time_min=time_min,
                    time_max=time_max,
                )
            
            period = self._get_period_text(date_range)
            
            if not events:
                if search_term:
                    return f"You don't have any {search_term} events scheduled{period}."
                return f"You don't have any events scheduled{period}."
            
            # Build header
            if search_term:
                header = f"Your {search_term} events{period}:"
            else:
                header = f"Your events{period}:"
            
            # Build event list
            event_lines = []
            for event in events:
                time_str = event.get_time_display()
                title = event.get_display_title()
                event_lines.append(f"• {time_str} - {title}")
            
            result = header + "\n" + "\n".join(event_lines)
            
            if len(events) == max_results:
                result += f"\n\n(Showing first {max_results} events)"
            
            return result
            
        except APIError as e:
            logger.error(f"Failed to list events: {e}")
            return "I couldn't access your calendar. Please check your connection."
    
    async def find_event_text(
        self,
        search_term: str,
        calendar_id: str = "primary",
    ) -> str:
        """
        Get a text response for "When is my X?" queries.
        
        Sprint 3.8: Finds and describes a specific event.
        
        Args:
            search_term: Event name to search (e.g., "birthday", "dentist")
            calendar_id: Calendar identifier
        
        Returns:
            Human-readable description of the event
        
        Example:
            # "When is my birthday?"
            text = await client.find_event_text(search_term="birthday")
            # Returns: "Your 'Birthday Party' is on December 15 at 3:00 PM."
        """
        try:
            event = await self.find_event_by_name(
                name=search_term,
                calendar_id=calendar_id,
            )
            
            if not event:
                return f"I couldn't find any '{search_term}' events on your calendar."
            
            title = event.get_display_title()
            time_str = event.get_time_display()
            
            # Get date info
            if event.start_datetime:
                date_str = event.start_datetime.strftime("%B %d")
                return f"Your '{title}' is on {date_str} at {time_str}."
            elif event.start_date:
                return f"Your '{title}' is on {event.start_date}."
            
            return f"Your '{title}' is scheduled at {time_str}."
            
        except APIError as e:
            logger.error(f"Failed to find event: {e}")
            return "I couldn't access your calendar. Please check your connection."
    
    def _parse_date_range(
        self,
        date_range: Optional[str],
        user_timezone: str = "UTC",
    ) -> tuple[datetime, Optional[datetime]]:
        """
        Parse date_range string into time_min and time_max datetimes.
        
        Uses user's timezone to correctly interpret "today", "tomorrow", etc.
        The returned datetimes are in UTC for the Google Calendar API.
        
        Args:
            date_range: "today", "tomorrow", "yesterday", "this_week", or YYYY-MM-DD
            user_timezone: User's timezone (e.g., "America/New_York")
        
        Returns:
            Tuple of (time_min, time_max) in UTC
        """
        from zoneinfo import ZoneInfo
        
        # Get user's timezone
        try:
            tz = ZoneInfo(user_timezone)
        except Exception:
            tz = ZoneInfo("UTC")
        
        now = datetime.now(tz)
        
        if not date_range:
            return now.astimezone(timezone.utc), None
        
        date_range = date_range.lower().strip()
        
        if date_range == "today":
            # Start and end of TODAY in user's timezone
            local_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            local_end = local_start + timedelta(days=1)
            # Convert to UTC for API
            time_min = local_start.astimezone(timezone.utc)
            time_max = local_end.astimezone(timezone.utc)
        elif date_range == "today_after":
            # Sprint 4.3.4: From NOW until end of today (for "events after X time today")
            time_min = now.astimezone(timezone.utc)
            local_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            time_max = local_end.astimezone(timezone.utc)
        elif date_range == "tomorrow":
            local_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            local_end = local_start + timedelta(days=1)
            time_min = local_start.astimezone(timezone.utc)
            time_max = local_end.astimezone(timezone.utc)
        elif date_range == "yesterday":
            local_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            local_end = local_start + timedelta(days=1)
            time_min = local_start.astimezone(timezone.utc)
            time_max = local_end.astimezone(timezone.utc)
        elif date_range == "this_week":
            time_min = now.astimezone(timezone.utc)
            time_max = (now + timedelta(days=7)).astimezone(timezone.utc)
        else:
            # Try to parse as YYYY-MM-DD in user's timezone
            try:
                date_obj = datetime.strptime(date_range, "%Y-%m-%d")
                local_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
                local_end = local_start + timedelta(days=1)
                time_min = local_start.astimezone(timezone.utc)
                time_max = local_end.astimezone(timezone.utc)
            except ValueError:
                # Default to now if can't parse
                time_min = now.astimezone(timezone.utc)
                time_max = None
        
        return time_min, time_max
    
    def _get_period_text(self, date_range: Optional[str]) -> str:
        """Get human-readable period description for messages."""
        if not date_range:
            return ""
        
        date_range = date_range.lower().strip()
        
        if date_range == "today":
            return " for today"
        elif date_range == "today_after":
            # Sprint 4.3.4: More descriptive text for remaining events today
            return " for the rest of today"
        elif date_range == "tomorrow":
            return " for tomorrow"
        elif date_range == "yesterday":
            return " for yesterday"
        elif date_range == "this_week":
            return " for this week"
        else:
            # Try to format as a date
            try:
                date_obj = datetime.strptime(date_range, "%Y-%m-%d")
                return f" for {date_obj.strftime('%B %d')}"
            except ValueError:
                return ""
    
    # -------------------------------------------------------------------------
    # CALENDAR LIST
    # -------------------------------------------------------------------------
    
    async def list_calendars(
        self,
        max_results: int = 100,
        show_hidden: bool = False,
    ) -> List[CalendarInfo]:
        """
        List calendars the user has access to.
        
        Args:
            max_results: Maximum calendars to return
            show_hidden: Include hidden calendars
        
        Returns:
            List of CalendarInfo objects
        """
        params = {
            "maxResults": min(max_results, 250),
            "showHidden": str(show_hidden).lower(),
        }
        
        logger.info("Fetching calendar list")
        
        response_data = await self._make_request(
            method="GET",
            endpoint="/users/me/calendarList",
            params=params,
        )
        
        # Parse response
        calendar_list = CalendarListResponse(**response_data)
        
        logger.info(f"Found {len(calendar_list.items)} calendars")
        
        return calendar_list.items
    
    async def get_primary_calendar(self) -> Optional[CalendarInfo]:
        """
        Get the user's primary calendar.
        
        Returns:
            CalendarInfo for the primary calendar, or None if not found
        """
        calendars = await self.list_calendars()
        for cal in calendars:
            if cal.primary:
                return cal
        return None
    
    # -------------------------------------------------------------------------
    # ACCESS VALIDATION
    # -------------------------------------------------------------------------
    
    async def validate_access(self, access_token: str) -> bool:
        """
        Verify the access token is valid for calendar operations.
        
        Makes a lightweight API call to check if the token works.
        
        Args:
            access_token: OAuth access token to validate
        
        Returns:
            True if token is valid and has calendar access
        """
        # Temporarily update token for this check
        original_token = self.access_token
        self.access_token = access_token
        
        try:
            # Try to list calendars (lightweight call)
            await self.list_calendars(max_results=1)
            return True
        except APIError:
            return False
        finally:
            # Restore original token
            self.access_token = original_token
    
    # -------------------------------------------------------------------------
    # EVENT CREATION (Sprint 3.8)
    # -------------------------------------------------------------------------
    
    async def get_user_timezone(self, calendar_id: str = "primary") -> str:
        """
        Fetch user's primary calendar timezone setting.
        
        Sprint 3.8: Used to ensure events are created in user's timezone.
        
        Args:
            calendar_id: Calendar identifier (default: "primary")
        
        Returns:
            Timezone string (e.g., "America/New_York") or "UTC" if not available
        
        Example:
            tz = await client.get_user_timezone()
            # Returns: "America/Los_Angeles"
        """
        try:
            response_data = await self._make_request(
                method="GET",
                endpoint=f"/calendars/{calendar_id}",
            )
            
            timezone_str = response_data.get("timeZone", "UTC")
            logger.info(f"User timezone: {timezone_str}")
            return timezone_str
            
        except APIError as e:
            logger.error(f"Failed to get user timezone: {e}")
            return "UTC"
    
    async def create_event(
        self,
        request: "EventCreateRequest",
        calendar_id: str = "primary",
    ) -> "EventCreateResponse":
        """
        Create a timed calendar event.
        
        Sprint 3.8: Creates an event with specific start and end times.
        
        Args:
            request: EventCreateRequest with event details
            calendar_id: Calendar identifier (default: "primary")
        
        Returns:
            EventCreateResponse with created event details
        
        Raises:
            APIError: If event creation fails
            ValueError: If request is invalid
        
        Example:
            from datetime import datetime
            from app.environments.google.calendar.schemas import EventCreateRequest
            
            request = EventCreateRequest(
                summary="Team Meeting",
                start_datetime=datetime(2025, 1, 15, 18, 0),
                end_datetime=datetime(2025, 1, 15, 19, 0),
                timezone="America/New_York",
            )
            response = await client.create_event(request)
            print(f"Created: {response.summary} - {response.html_link}")
        """
        from app.environments.google.calendar.schemas import EventCreateRequest, EventCreateResponse
        
        if not request.is_valid():
            raise ValueError("Request must have either datetime pair or date pair")
        
        # Build the event body for the API
        event_body: dict = {
            "summary": request.summary,
        }
        
        # Add time information
        if request.start_datetime and request.end_datetime:
            # Timed event - use dateTime format
            event_body["start"] = {
                "dateTime": request.start_datetime.isoformat(),
                "timeZone": request.timezone,
            }
            event_body["end"] = {
                "dateTime": request.end_datetime.isoformat(),
                "timeZone": request.timezone,
            }
        elif request.start_date and request.end_date:
            # All-day event - use date format
            event_body["start"] = {
                "date": request.start_date.isoformat(),
            }
            event_body["end"] = {
                "date": request.end_date.isoformat(),
            }
        
        # Optional fields
        if request.location:
            event_body["location"] = request.location
        if request.description:
            event_body["description"] = request.description
        if request.recurrence:
            event_body["recurrence"] = request.recurrence
        
        logger.info(
            f"Creating calendar event",
            extra={
                "summary": request.summary,
                "calendar_id": calendar_id,
                "is_all_day": request.is_all_day(),
            }
        )
        
        # Make the API request
        response_data = await self._make_post_request(
            endpoint=f"/calendars/{calendar_id}/events",
            json_body=event_body,
        )
        
        # Parse the response
        created_event = self._parse_create_response(response_data, request)
        
        logger.info(f"Created event: {created_event.event_id}")
        
        return created_event
    
    async def create_all_day_event(
        self,
        request: "EventCreateRequest",
        calendar_id: str = "primary",
    ) -> "EventCreateResponse":
        """
        Create an all-day calendar event.
        
        Sprint 3.8: Convenience method for creating all-day events.
        Ensures dates are properly set if only start_date is provided.
        
        Args:
            request: EventCreateRequest with event details (uses date fields)
            calendar_id: Calendar identifier (default: "primary")
        
        Returns:
            EventCreateResponse with created event details
        
        Example:
            from datetime import date
            from app.environments.google.calendar.schemas import EventCreateRequest
            
            request = EventCreateRequest(
                summary="Birthday",
                start_date=date(2025, 1, 15),
            )
            response = await client.create_all_day_event(request)
        """
        from datetime import timedelta as td
        from app.environments.google.calendar.schemas import EventCreateRequest
        
        # Ensure we have a valid all-day request
        if not request.start_date:
            raise ValueError("All-day events require start_date")
        
        # If end_date is not set, default to next day (exclusive)
        if not request.end_date:
            request = EventCreateRequest(
                summary=request.summary,
                start_date=request.start_date,
                end_date=request.start_date + td(days=1),
                location=request.location,
                description=request.description,
                recurrence=request.recurrence,
                timezone=request.timezone,
            )
        
        return await self.create_event(request, calendar_id)
    
    async def _make_post_request(
        self,
        endpoint: str,
        json_body: dict,
    ) -> dict:
        """
        Make an authenticated POST request to the Calendar API.
        
        Args:
            endpoint: API endpoint path
            json_body: JSON body to send
        
        Returns:
            Parsed JSON response
        
        Raises:
            APIError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url=url,
                    headers=self._get_headers(),
                    json=json_body,
                    timeout=30.0,
                )
                
                if response.status_code == 401:
                    logger.error("Calendar API: Unauthorized (token may be expired)")
                    raise APIError(
                        "Unauthorized - access token may be expired",
                        status_code=401,
                        response=response.text,
                    )
                
                if response.status_code == 403:
                    logger.error("Calendar API: Forbidden (write scope may be missing)")
                    raise APIError(
                        "Forbidden - calendar write scope may not be granted",
                        status_code=403,
                        response=response.text,
                    )
                
                if response.status_code not in (200, 201):
                    error_detail = response.text
                    logger.error(f"Calendar API error: {response.status_code} - {error_detail}")
                    raise APIError(
                        f"API request failed: {error_detail}",
                        status_code=response.status_code,
                        response=error_detail,
                    )
                
                return response.json()
                
            except httpx.RequestError as e:
                logger.error(f"Network error in Calendar API: {e}")
                raise APIError(f"Network error: {e}")
    
    def _parse_create_response(
        self,
        response_data: dict,
        request: "EventCreateRequest",
    ) -> "EventCreateResponse":
        """Parse the API response into an EventCreateResponse."""
        from app.environments.google.calendar.schemas import EventCreateResponse
        from datetime import datetime
        
        event_id = response_data.get("id", "")
        summary = response_data.get("summary", request.summary)
        html_link = response_data.get("htmlLink", "")
        
        # Parse start time/date
        start_data = response_data.get("start", {})
        if "dateTime" in start_data:
            start = datetime.fromisoformat(start_data["dateTime"].replace("Z", "+00:00"))
        elif "date" in start_data:
            start = datetime.strptime(start_data["date"], "%Y-%m-%d").date()
        else:
            start = request.start_datetime or request.start_date
        
        # Parse end time/date
        end_data = response_data.get("end", {})
        if "dateTime" in end_data:
            end = datetime.fromisoformat(end_data["dateTime"].replace("Z", "+00:00"))
        elif "date" in end_data:
            end = datetime.strptime(end_data["date"], "%Y-%m-%d").date()
        else:
            end = request.end_datetime or request.end_date
        
        # Check for recurrence
        is_recurring = "recurrence" in response_data
        
        return EventCreateResponse(
            event_id=event_id,
            summary=summary,
            start=start,
            end=end,
            html_link=html_link,
            timezone=start_data.get("timeZone") or request.timezone,
            location=response_data.get("location"),
            is_recurring=is_recurring,
        )

    # -------------------------------------------------------------------------
    # EVENT UPDATE & DELETE (Sprint 3.9)
    # -------------------------------------------------------------------------
    
    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> Optional["CalendarEvent"]:
        """
        Get a single calendar event by ID.
        
        Sprint 3.9: Retrieve event details before update/delete.
        
        Args:
            event_id: The Google Calendar event ID
            calendar_id: Calendar identifier (default: "primary")
        
        Returns:
            CalendarEvent if found, None if not found
        
        Raises:
            APIError: If the request fails (except 404)
        """
        try:
            response_data = await self._make_request(
                method="GET",
                endpoint=f"/calendars/{calendar_id}/events/{event_id}",
            )
            
            return CalendarEvent(**response_data)
            
        except APIError as e:
            if e.status_code == 404:
                logger.info(f"Event not found: {event_id}")
                return None
            raise
    
    async def update_event(
        self,
        event_id: str,
        updates: "EventUpdateRequest",
        calendar_id: str = "primary",
    ) -> "CalendarEvent":
        """
        Update an existing calendar event.
        
        Sprint 3.9: Modify event fields using PATCH request.
        Only specified fields are updated; others remain unchanged.
        
        Args:
            event_id: The Google Calendar event ID to update
            updates: EventUpdateRequest with fields to change
            calendar_id: Calendar identifier (default: "primary")
        
        Returns:
            Updated CalendarEvent
        
        Raises:
            APIError: If update fails
            ValueError: If no updates provided
        
        Example:
            from app.environments.google.calendar.schemas import EventUpdateRequest
            
            # Change event time to 3pm
            updates = EventUpdateRequest(
                start_datetime=datetime(2025, 1, 15, 15, 0),
                end_datetime=datetime(2025, 1, 15, 16, 0),
                timezone="America/New_York",
            )
            updated = await client.update_event("event-id-123", updates)
        """
        from app.environments.google.calendar.schemas import EventUpdateRequest
        
        if not updates.has_changes():
            raise ValueError("No updates provided")
        
        # First, get the existing event to preserve unchanged fields
        existing = await self.get_event(event_id, calendar_id)
        if not existing:
            raise APIError(f"Event not found: {event_id}", status_code=404)
        
        # Build the update body - only include changed fields
        update_body: dict = {}
        
        if updates.summary is not None:
            update_body["summary"] = updates.summary
        
        if updates.location is not None:
            update_body["location"] = updates.location
        
        if updates.description is not None:
            update_body["description"] = updates.description
        
        # Handle time updates
        if updates.start_datetime and updates.end_datetime:
            timezone = updates.timezone or "UTC"
            update_body["start"] = {
                "dateTime": updates.start_datetime.isoformat(),
                "timeZone": timezone,
            }
            update_body["end"] = {
                "dateTime": updates.end_datetime.isoformat(),
                "timeZone": timezone,
            }
        elif updates.start_date and updates.end_date:
            update_body["start"] = {
                "date": updates.start_date.isoformat(),
            }
            update_body["end"] = {
                "date": updates.end_date.isoformat(),
            }
        
        logger.info(
            f"Updating calendar event",
            extra={
                "event_id": event_id,
                "calendar_id": calendar_id,
                "update_fields": list(update_body.keys()),
            }
        )
        
        # Make the PATCH request
        response_data = await self._make_patch_request(
            endpoint=f"/calendars/{calendar_id}/events/{event_id}",
            json_body=update_body,
        )
        
        # Parse and return updated event
        updated_event = CalendarEvent(**response_data)
        
        logger.info(f"Updated event: {event_id}")
        
        return updated_event
    
    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> bool:
        """
        Delete a calendar event.
        
        Sprint 3.9: Remove an event from the calendar.
        
        Args:
            event_id: The Google Calendar event ID to delete
            calendar_id: Calendar identifier (default: "primary")
        
        Returns:
            True if deleted successfully
        
        Raises:
            APIError: If deletion fails
        
        Example:
            success = await client.delete_event("event-id-123")
            if success:
                print("Event deleted")
        """
        logger.info(
            f"Deleting calendar event",
            extra={
                "event_id": event_id,
                "calendar_id": calendar_id,
            }
        )
        
        await self._make_delete_request(
            endpoint=f"/calendars/{calendar_id}/events/{event_id}",
        )
        
        logger.info(f"Deleted event: {event_id}")
        
        return True
    
    async def search_events_for_edit(
        self,
        query: str,
        calendar_id: str = "primary",
        max_results: int = 10,
        include_past: bool = False,
    ) -> "EventSearchResult":
        """
        Search for events that can be edited/deleted.
        
        Sprint 3.9: Returns an EventSearchResult for edit/delete flows.
        
        Args:
            query: Search text (title, description, location)
            calendar_id: Calendar identifier
            max_results: Maximum events to return
            include_past: Whether to include past events
        
        Returns:
            EventSearchResult with matching events
        
        Example:
            result = await client.search_events_for_edit("dentist")
            if result.has_single_match():
                event = result.events[0]
            elif result.needs_disambiguation():
                # Show list to user
                pass
        """
        from app.environments.google.calendar.schemas import EventSearchResult
        
        if not query or not query.strip():
            return EventSearchResult(query="", events=[], total_count=0)
        
        query = query.strip()
        
        # Set time range
        now = datetime.now(timezone.utc)
        if include_past:
            time_min = now - timedelta(days=365)  # 1 year back
        else:
            time_min = now
        time_max = now + timedelta(days=365)  # 1 year ahead
        
        try:
            events = await self.search_events(
                query=query,
                calendar_id=calendar_id,
                max_results=max_results,
                time_min=time_min,
                time_max=time_max,
            )
            
            return EventSearchResult(
                query=query,
                events=events,
                total_count=len(events),
            )
            
        except APIError as e:
            logger.error(f"Search for edit failed: {e}")
            return EventSearchResult(query=query, events=[], total_count=0)
    
    async def _make_patch_request(
        self,
        endpoint: str,
        json_body: dict,
    ) -> dict:
        """
        Make an authenticated PATCH request to the Calendar API.
        
        Args:
            endpoint: API endpoint path
            json_body: JSON body with fields to update
        
        Returns:
            Parsed JSON response
        
        Raises:
            APIError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    url=url,
                    headers=self._get_headers(),
                    json=json_body,
                    timeout=30.0,
                )
                
                if response.status_code == 401:
                    logger.error("Calendar API: Unauthorized (token may be expired)")
                    raise APIError(
                        "Unauthorized - access token may be expired",
                        status_code=401,
                        response=response.text,
                    )
                
                if response.status_code == 403:
                    logger.error("Calendar API: Forbidden (write scope may be missing)")
                    raise APIError(
                        "Forbidden - calendar write scope may not be granted",
                        status_code=403,
                        response=response.text,
                    )
                
                if response.status_code == 404:
                    logger.error("Calendar API: Event not found")
                    raise APIError(
                        "Event not found",
                        status_code=404,
                        response=response.text,
                    )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Calendar API error: {response.status_code} - {error_detail}")
                    raise APIError(
                        f"API request failed: {error_detail}",
                        status_code=response.status_code,
                        response=error_detail,
                    )
                
                return response.json()
                
            except httpx.RequestError as e:
                logger.error(f"Network error in Calendar API: {e}")
                raise APIError(f"Network error: {e}")
    
    async def _make_delete_request(
        self,
        endpoint: str,
    ) -> None:
        """
        Make an authenticated DELETE request to the Calendar API.
        
        Args:
            endpoint: API endpoint path
        
        Raises:
            APIError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    url=url,
                    headers=self._get_headers(),
                    timeout=30.0,
                )
                
                if response.status_code == 401:
                    logger.error("Calendar API: Unauthorized (token may be expired)")
                    raise APIError(
                        "Unauthorized - access token may be expired",
                        status_code=401,
                        response=response.text,
                    )
                
                if response.status_code == 403:
                    logger.error("Calendar API: Forbidden (write scope may be missing)")
                    raise APIError(
                        "Forbidden - calendar write scope may not be granted",
                        status_code=403,
                        response=response.text,
                    )
                
                if response.status_code == 404:
                    logger.error("Calendar API: Event not found")
                    raise APIError(
                        "Event not found",
                        status_code=404,
                        response=response.text,
                    )
                
                # 204 No Content is the expected success response for DELETE
                if response.status_code not in (200, 204):
                    error_detail = response.text
                    logger.error(f"Calendar API error: {response.status_code} - {error_detail}")
                    raise APIError(
                        f"API request failed: {error_detail}",
                        status_code=response.status_code,
                        response=error_detail,
                    )
                
            except httpx.RequestError as e:
                logger.error(f"Network error in Calendar API: {e}")
                raise APIError(f"Network error: {e}")
