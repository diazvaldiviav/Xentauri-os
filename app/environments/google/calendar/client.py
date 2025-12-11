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
