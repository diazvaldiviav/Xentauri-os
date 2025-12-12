"""
Tests for Calendar Search - Sprint 3.7

Tests for:
- GoogleCalendarClient.search_events()
- GoogleCalendarClient.find_event_by_name()
- Calendar API search functionality

All API calls are mocked for fast, reliable tests.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.environments.google.calendar.client import GoogleCalendarClient
from app.environments.google.calendar.schemas import (
    CalendarEvent,
    CalendarEventsResponse,
    EventTime,
)
from app.environments.base import APIError


# ===========================================================================
# FIXTURES
# ===========================================================================

@pytest.fixture
def calendar_client():
    """Create a calendar client with mock token."""
    return GoogleCalendarClient(access_token="mock_access_token")


@pytest.fixture
def mock_events():
    """Create sample calendar events for testing."""
    now = datetime.now(timezone.utc)
    return [
        CalendarEvent(
            id="1",
            summary="Birthday Party",
            description="John's birthday celebration",
            location="Home",
            start=EventTime(dateTime=now + timedelta(days=1)),
            end=EventTime(dateTime=now + timedelta(days=1, hours=2)),
            status="confirmed",
        ),
        CalendarEvent(
            id="2",
            summary="Dentist Appointment",
            description="Regular checkup",
            location="Dr. Smith's Office",
            start=EventTime(dateTime=now + timedelta(days=3)),
            end=EventTime(dateTime=now + timedelta(days=3, hours=1)),
            status="confirmed",
        ),
        CalendarEvent(
            id="3",
            summary="Team Meeting",
            description="Weekly standup meeting",
            location="Conference Room A",
            start=EventTime(dateTime=now + timedelta(days=2)),
            end=EventTime(dateTime=now + timedelta(days=2, hours=1)),
            status="confirmed",
        ),
    ]


def _create_api_response(events: list) -> dict:
    """Helper to create mock API response."""
    return {
        "kind": "calendar#events",
        "summary": "Primary",
        "timeZone": "UTC",
        "items": [
            {
                "id": e.id,
                "summary": e.summary,
                "description": e.description,
                "location": e.location,
                "start": {"dateTime": e.start.date_time.isoformat()} if e.start and e.start.date_time else {},
                "end": {"dateTime": e.end.date_time.isoformat()} if e.end and e.end.date_time else {},
                "status": e.status,
            }
            for e in events
        ],
    }


# ===========================================================================
# SEARCH_EVENTS TESTS
# ===========================================================================

class TestSearchEvents:
    """Tests for search_events() method."""
    
    @pytest.mark.asyncio
    async def test_search_events_with_results(self, calendar_client, mock_events):
        """Test search returns matching events."""
        # Filter to birthday event
        birthday_event = [e for e in mock_events if "birthday" in e.summary.lower()]
        
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _create_api_response(birthday_event)
            
            results = await calendar_client.search_events("birthday")
            
            assert len(results) == 1
            assert results[0].summary == "Birthday Party"
            
            # Verify API was called with correct params
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["params"]["q"] == "birthday"
    
    @pytest.mark.asyncio
    async def test_search_events_empty_query(self, calendar_client):
        """Test empty query returns empty list without API call."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            results = await calendar_client.search_events("")
            
            assert results == []
            mock_request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_search_events_whitespace_query(self, calendar_client):
        """Test whitespace-only query returns empty list."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            results = await calendar_client.search_events("   ")
            
            assert results == []
            mock_request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_search_events_no_results(self, calendar_client):
        """Test search with no matching events."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _create_api_response([])
            
            results = await calendar_client.search_events("nonexistent")
            
            assert results == []
    
    @pytest.mark.asyncio
    async def test_search_events_with_date_range(self, calendar_client, mock_events):
        """Test search with custom date range."""
        now = datetime.now(timezone.utc)
        time_min = now
        time_max = now + timedelta(days=7)
        
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _create_api_response(mock_events[:1])
            
            results = await calendar_client.search_events(
                query="meeting",
                time_min=time_min,
                time_max=time_max,
            )
            
            # Verify time range was passed to API
            call_args = mock_request.call_args
            assert "timeMin" in call_args[1]["params"]
            assert "timeMax" in call_args[1]["params"]
    
    @pytest.mark.asyncio
    async def test_search_events_api_error(self, calendar_client):
        """Test search handles API errors gracefully."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.side_effect = APIError("API error", status_code=500)
            
            with pytest.raises(APIError) as exc_info:
                await calendar_client.search_events("meeting")
            
            assert "API error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_search_events_special_characters(self, calendar_client, mock_events):
        """Test search with special characters in query."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _create_api_response([])
            
            # Should not raise, query should be passed as-is
            results = await calendar_client.search_events("meeting & lunch")
            
            call_args = mock_request.call_args
            assert call_args[1]["params"]["q"] == "meeting & lunch"


# ===========================================================================
# FIND_EVENT_BY_NAME TESTS
# ===========================================================================

class TestFindEventByName:
    """Tests for find_event_by_name() method."""
    
    @pytest.mark.asyncio
    async def test_find_event_by_name_found(self, calendar_client, mock_events):
        """Test finding an event by name."""
        dentist_event = [e for e in mock_events if "dentist" in e.summary.lower()]
        
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _create_api_response(dentist_event)
            
            result = await calendar_client.find_event_by_name("dentist")
            
            assert result is not None
            assert result.summary == "Dentist Appointment"
    
    @pytest.mark.asyncio
    async def test_find_event_by_name_not_found(self, calendar_client):
        """Test finding an event that doesn't exist."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = _create_api_response([])
            
            result = await calendar_client.find_event_by_name("nonexistent")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_find_event_by_name_returns_first(self, calendar_client, mock_events):
        """Test that find_event_by_name returns first match."""
        with patch.object(
            calendar_client,
            '_make_request',
            new_callable=AsyncMock,
        ) as mock_request:
            # Return multiple events
            mock_request.return_value = _create_api_response(mock_events)
            
            result = await calendar_client.find_event_by_name("meeting")
            
            # Should only request max_results=1
            call_args = mock_request.call_args
            assert call_args[1]["params"]["maxResults"] == 1


# ===========================================================================
# CALENDAR RENDERER SEARCH TESTS
# ===========================================================================

class TestCalendarRendererSearch:
    """Tests for search-related rendering."""
    
    def test_render_with_search_term(self, mock_events):
        """Test rendering with search term shows context."""
        from app.environments.google.calendar.renderer import CalendarRenderer
        
        renderer = CalendarRenderer(theme="dark")
        html = renderer.render_events(
            events=mock_events[:1],
            title="Search Results",
            search_term="birthday",
        )
        
        assert "birthday" in html
        assert "Showing events matching" in html
    
    def test_render_no_results_with_search(self):
        """Test rendering no results shows search context."""
        from app.environments.google.calendar.renderer import CalendarRenderer
        
        renderer = CalendarRenderer(theme="dark")
        html = renderer.render_events(
            events=[],
            title="Search Results",
            search_term="nonexistent",
        )
        
        assert "No Events Found" in html
        assert "nonexistent" in html
    
    def test_render_search_term_escaping(self):
        """Test that search term is HTML escaped (XSS prevention)."""
        from app.environments.google.calendar.renderer import CalendarRenderer
        
        renderer = CalendarRenderer(theme="dark")
        html = renderer.render_events(
            events=[],
            title="Search Results",
            search_term="<script>alert('xss')</script>",
        )
        
        # Should be escaped
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
    
    def test_render_without_search_term(self, mock_events):
        """Test rendering without search term shows normal header."""
        from app.environments.google.calendar.renderer import CalendarRenderer
        
        renderer = CalendarRenderer(theme="dark")
        html = renderer.render_events(
            events=mock_events,
            title="Calendar",
        )
        
        assert "Showing events matching" not in html
