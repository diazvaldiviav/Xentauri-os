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
        "https://www.googleapis.com/auth/calendar.events.readonly",
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
        time_min, time_max = self._parse_date_range(date_range)
        
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
        time_min, time_max = self._parse_date_range(date_range)
        
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
    ) -> tuple[datetime, Optional[datetime]]:
        """Parse date_range string into time_min and time_max datetimes."""
        now = datetime.now(timezone.utc)
        
        if not date_range:
            return now, None
        
        date_range = date_range.lower().strip()
        
        if date_range == "today":
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = time_min + timedelta(days=1)
        elif date_range == "tomorrow":
            time_min = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = time_min + timedelta(days=1)
        elif date_range == "this_week":
            time_min = now
            time_max = now + timedelta(days=7)
        else:
            # Try to parse as YYYY-MM-DD
            try:
                date_obj = datetime.strptime(date_range, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                time_min = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                time_max = time_min + timedelta(days=1)
            except ValueError:
                # Default to now if can't parse
                time_min = now
                time_max = None
        
        return time_min, time_max
    
    def _get_period_text(self, date_range: Optional[str]) -> str:
        """Get human-readable period description for messages."""
        if not date_range:
            return ""
        
        date_range = date_range.lower().strip()
        
        if date_range == "today":
            return " for today"
        elif date_range == "tomorrow":
            return " for tomorrow"
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
