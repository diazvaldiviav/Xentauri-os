"""
Tests for Sprint 3.8 - Calendar Text Queries.

These tests verify the calendar query functionality that returns
text answers to questions like:
- "How many events do I have today?"
- "What's my next meeting?"
- "When is my birthday?"
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.intent.schemas import (
    IntentType,
    ActionType,
    CalendarQueryIntent,
)
from app.environments.google.calendar.client import GoogleCalendarClient
from app.environments.google.calendar.schemas import CalendarEvent


# ---------------------------------------------------------------------------
# TEST FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_events():
    """Create mock calendar events for testing."""
    now = datetime.now(timezone.utc)
    
    event1 = MagicMock(spec=CalendarEvent)
    event1.get_display_title.return_value = "Team Standup"
    event1.get_time_display.return_value = "9:00 AM"
    event1.start_datetime = now + timedelta(hours=1)
    event1.start_date = None
    
    event2 = MagicMock(spec=CalendarEvent)
    event2.get_display_title.return_value = "Design Review"
    event2.get_time_display.return_value = "2:00 PM"
    event2.start_datetime = now + timedelta(hours=5)
    event2.start_date = None
    
    event3 = MagicMock(spec=CalendarEvent)
    event3.get_display_title.return_value = "Birthday Party"
    event3.get_time_display.return_value = "3:00 PM"
    event3.start_datetime = now + timedelta(days=3)
    event3.start_date = None
    
    return [event1, event2, event3]


@pytest.fixture
def calendar_client():
    """Create a calendar client for testing."""
    return GoogleCalendarClient(access_token="test_token")


# ---------------------------------------------------------------------------
# CALENDAR QUERY INTENT SCHEMA TESTS
# ---------------------------------------------------------------------------

class TestCalendarQueryIntentSchema:
    """Test the CalendarQueryIntent schema."""
    
    def test_create_count_events_intent(self):
        """Test creating a count_events calendar query intent."""
        intent = CalendarQueryIntent(
            confidence=0.95,
            original_text="How many events do I have today?",
            action=ActionType.COUNT_EVENTS,
            date_range="today",
            search_term=None,
        )
        
        assert intent.intent_type == IntentType.CALENDAR_QUERY
        assert intent.action == ActionType.COUNT_EVENTS
        assert intent.date_range == "today"
        assert intent.search_term is None
    
    def test_create_next_event_intent(self):
        """Test creating a next_event calendar query intent."""
        intent = CalendarQueryIntent(
            confidence=0.95,
            original_text="What's my next meeting?",
            action=ActionType.NEXT_EVENT,
            date_range=None,
            search_term="meeting",
        )
        
        assert intent.intent_type == IntentType.CALENDAR_QUERY
        assert intent.action == ActionType.NEXT_EVENT
        assert intent.search_term == "meeting"
    
    def test_create_list_events_intent(self):
        """Test creating a list_events calendar query intent."""
        intent = CalendarQueryIntent(
            confidence=0.95,
            original_text="List my events for tomorrow",
            action=ActionType.LIST_EVENTS,
            date_range="tomorrow",
            search_term=None,
        )
        
        assert intent.intent_type == IntentType.CALENDAR_QUERY
        assert intent.action == ActionType.LIST_EVENTS
        assert intent.date_range == "tomorrow"
    
    def test_create_find_event_intent(self):
        """Test creating a find_event calendar query intent."""
        intent = CalendarQueryIntent(
            confidence=0.92,
            original_text="When is my birthday?",
            action=ActionType.FIND_EVENT,
            date_range=None,
            search_term="birthday",
        )
        
        assert intent.intent_type == IntentType.CALENDAR_QUERY
        assert intent.action == ActionType.FIND_EVENT
        assert intent.search_term == "birthday"
    
    def test_intent_with_date_and_search(self):
        """Test calendar query with both date_range and search_term."""
        intent = CalendarQueryIntent(
            confidence=0.95,
            original_text="What meetings do I have this week?",
            action=ActionType.LIST_EVENTS,
            date_range="this_week",
            search_term="meeting",
        )
        
        assert intent.date_range == "this_week"
        assert intent.search_term == "meeting"


# ---------------------------------------------------------------------------
# CALENDAR CLIENT TEXT QUERY TESTS
# ---------------------------------------------------------------------------

class TestCalendarClientEventCountText:
    """Test the get_event_count_text method."""
    
    @pytest.mark.asyncio
    async def test_count_events_today_zero(self, calendar_client):
        """Test count when no events today."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = []
            
            result = await calendar_client.get_event_count_text(date_range="today")
            
            assert "don't have any events" in result
            assert "for today" in result
    
    @pytest.mark.asyncio
    async def test_count_events_today_one(self, calendar_client, mock_events):
        """Test count when one event today."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [mock_events[0]]
            
            result = await calendar_client.get_event_count_text(date_range="today")
            
            assert "1 event" in result
            assert "Team Standup" in result
    
    @pytest.mark.asyncio
    async def test_count_events_today_multiple(self, calendar_client, mock_events):
        """Test count when multiple events today."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = mock_events[:2]
            
            result = await calendar_client.get_event_count_text(date_range="today")
            
            assert "2 events" in result
            assert "for today" in result
    
    @pytest.mark.asyncio
    async def test_count_events_with_search_term(self, calendar_client, mock_events):
        """Test count with a search filter."""
        with patch.object(
            calendar_client,
            'search_events',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [mock_events[0]]
            
            result = await calendar_client.get_event_count_text(
                date_range="today",
                search_term="meeting",
            )
            
            assert "1 meeting event" in result


class TestCalendarClientNextEventText:
    """Test the get_next_event_text method."""
    
    @pytest.mark.asyncio
    async def test_next_event_none(self, calendar_client):
        """Test when no upcoming events."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = []
            
            result = await calendar_client.get_next_event_text()
            
            assert "don't have any upcoming events" in result
    
    @pytest.mark.asyncio
    async def test_next_event_found(self, calendar_client, mock_events):
        """Test when next event is found."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [mock_events[0]]
            
            result = await calendar_client.get_next_event_text()
            
            assert "Team Standup" in result
            assert "9:00 AM" in result
    
    @pytest.mark.asyncio
    async def test_next_event_with_search(self, calendar_client, mock_events):
        """Test finding next event with search term."""
        with patch.object(
            calendar_client,
            'search_events',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [mock_events[0]]
            
            result = await calendar_client.get_next_event_text(search_term="standup")
            
            assert "next standup" in result
            assert "Team Standup" in result


class TestCalendarClientEventsListText:
    """Test the get_events_list_text method."""
    
    @pytest.mark.asyncio
    async def test_list_events_empty(self, calendar_client):
        """Test listing when no events."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = []
            
            result = await calendar_client.get_events_list_text(date_range="tomorrow")
            
            assert "don't have any events" in result
            assert "for tomorrow" in result
    
    @pytest.mark.asyncio
    async def test_list_events_multiple(self, calendar_client, mock_events):
        """Test listing multiple events."""
        with patch.object(
            calendar_client,
            'list_upcoming_events',
            new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = mock_events[:2]
            
            result = await calendar_client.get_events_list_text(date_range="today")
            
            assert "Your events for today:" in result
            assert "Team Standup" in result
            assert "Design Review" in result
            assert "•" in result  # Bullet points
    
    @pytest.mark.asyncio
    async def test_list_events_with_search(self, calendar_client, mock_events):
        """Test listing events with search filter."""
        with patch.object(
            calendar_client,
            'search_events',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [mock_events[0]]
            
            result = await calendar_client.get_events_list_text(
                date_range="this_week",
                search_term="standup",
            )
            
            assert "Your standup events" in result


class TestCalendarClientFindEventText:
    """Test the find_event_text method."""
    
    @pytest.mark.asyncio
    async def test_find_event_not_found(self, calendar_client):
        """Test when event not found."""
        with patch.object(
            calendar_client,
            'find_event_by_name',
            new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = None
            
            result = await calendar_client.find_event_text(search_term="dentist")
            
            assert "couldn't find any 'dentist' events" in result
    
    @pytest.mark.asyncio
    async def test_find_event_found(self, calendar_client, mock_events):
        """Test when event is found."""
        with patch.object(
            calendar_client,
            'find_event_by_name',
            new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_events[2]  # Birthday Party
            
            result = await calendar_client.find_event_text(search_term="birthday")
            
            assert "Birthday Party" in result


# ---------------------------------------------------------------------------
# DATE RANGE PARSING TESTS
# ---------------------------------------------------------------------------

class TestDateRangeParsing:
    """Test the _parse_date_range helper method."""
    
    def test_parse_today(self, calendar_client):
        """Test parsing 'today'."""
        time_min, time_max = calendar_client._parse_date_range("today")
        
        assert time_min.hour == 0
        assert time_min.minute == 0
        assert time_max is not None
        # time_max should be start of next day
        assert (time_max - time_min).days == 1
    
    def test_parse_tomorrow(self, calendar_client):
        """Test parsing 'tomorrow'."""
        now = datetime.now(timezone.utc)
        time_min, time_max = calendar_client._parse_date_range("tomorrow")
        
        # time_min should be tomorrow at midnight
        assert time_min.day == (now + timedelta(days=1)).day
        assert time_min.hour == 0
    
    def test_parse_this_week(self, calendar_client):
        """Test parsing 'this_week'."""
        time_min, time_max = calendar_client._parse_date_range("this_week")
        
        assert time_max is not None
        # time_max should be 7 days from time_min
        delta = time_max - time_min
        assert delta.days == 7
    
    def test_parse_specific_date(self, calendar_client):
        """Test parsing a specific YYYY-MM-DD date."""
        time_min, time_max = calendar_client._parse_date_range("2025-12-25")
        
        assert time_min.year == 2025
        assert time_min.month == 12
        assert time_min.day == 25
        assert time_min.hour == 0
    
    def test_parse_none(self, calendar_client):
        """Test parsing None returns now."""
        time_min, time_max = calendar_client._parse_date_range(None)
        
        # Should be close to now
        now = datetime.now(timezone.utc)
        assert abs((time_min - now).total_seconds()) < 2
        assert time_max is None


class TestPeriodText:
    """Test the _get_period_text helper method."""
    
    def test_period_today(self, calendar_client):
        """Test period text for today."""
        result = calendar_client._get_period_text("today")
        assert result == " for today"
    
    def test_period_tomorrow(self, calendar_client):
        """Test period text for tomorrow."""
        result = calendar_client._get_period_text("tomorrow")
        assert result == " for tomorrow"
    
    def test_period_this_week(self, calendar_client):
        """Test period text for this week."""
        result = calendar_client._get_period_text("this_week")
        assert result == " for this week"
    
    def test_period_specific_date(self, calendar_client):
        """Test period text for specific date."""
        result = calendar_client._get_period_text("2025-12-25")
        assert "December 25" in result
    
    def test_period_none(self, calendar_client):
        """Test period text for None."""
        result = calendar_client._get_period_text(None)
        assert result == ""


# ---------------------------------------------------------------------------
# INTENT PARSER TESTS
# ---------------------------------------------------------------------------

class TestCalendarQueryParsing:
    """Test that the intent parser creates CalendarQueryIntent correctly."""
    
    def test_create_calendar_query_from_data(self):
        """Test _create_calendar_query method."""
        from app.ai.intent.parser import IntentParser
        from datetime import datetime
        
        parser = IntentParser()
        
        data = {
            "intent_type": "calendar_query",
            "action": "count_events",
            "date_range": "today",
            "search_term": None,
            "confidence": 0.95,
            "reasoning": "Calendar question",
        }
        
        intent = parser._create_calendar_query(
            data=data,
            original_text="How many events today?",
            confidence=0.95,
            reasoning="Calendar question",
        )
        
        assert isinstance(intent, CalendarQueryIntent)
        assert intent.action == ActionType.COUNT_EVENTS
        # "today" should be resolved to actual ISO date
        expected_date = datetime.now().strftime("%Y-%m-%d")
        assert intent.date_range == expected_date
    
    def test_action_mapping_includes_calendar_actions(self):
        """Test that _map_action handles calendar query actions."""
        from app.ai.intent.parser import IntentParser
        
        parser = IntentParser()
        
        assert parser._map_action("count_events") == ActionType.COUNT_EVENTS
        assert parser._map_action("next_event") == ActionType.NEXT_EVENT
        assert parser._map_action("list_events") == ActionType.LIST_EVENTS
        assert parser._map_action("find_event") == ActionType.FIND_EVENT


class TestSearchTermExtraction:
    """Tests for extracting search terms from natural language (Sprint 3.9 fix)."""
    
    def test_extract_birthday_from_when_is_my(self):
        """Test extraction from 'when is my birthday?'"""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._extract_search_term_from_text("when is my birthday?")
        assert result == "birthday"
    
    def test_extract_anniversary_from_when_is_my(self):
        """Test extraction from 'when is my anniversary?'"""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._extract_search_term_from_text("when is my anniversary?")
        assert result == "anniversary"
    
    def test_extract_meeting_with_today_suffix(self):
        """Test extraction removes 'today' suffix."""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._extract_search_term_from_text("do I have any meeting today?")
        assert result == "meeting"
    
    def test_extract_appointment_from_whens(self):
        """Test extraction from contraction 'when's'."""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._extract_search_term_from_text("when's my dentist appointment?")
        assert result == "dentist appointment"
    
    def test_extract_from_find_pattern(self):
        """Test extraction from 'find my X' pattern."""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._extract_search_term_from_text("find my doctor appointment")
        assert result == "doctor appointment"


class TestDateRangeResolution:
    """Tests for resolving relative dates to ISO dates (Sprint 3.9 fix)."""
    
    def test_resolve_today_to_iso_date(self):
        """Test 'today' resolves to current ISO date."""
        from app.ai.intent.parser import IntentParser
        from datetime import datetime
        
        parser = IntentParser()
        today = datetime.now().strftime("%Y-%m-%d")
        
        result = parser._resolve_date_range("today", "any text")
        assert result == today
    
    def test_resolve_tomorrow_to_iso_date(self):
        """Test 'tomorrow' resolves to next day's ISO date."""
        from app.ai.intent.parser import IntentParser
        from datetime import datetime, timedelta
        
        parser = IntentParser()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        result = parser._resolve_date_range("tomorrow", "any text")
        assert result == tomorrow
    
    def test_extract_today_from_text_when_no_date_range(self):
        """Test extraction of 'today' from text when date_range is None."""
        from app.ai.intent.parser import IntentParser
        from datetime import datetime
        
        parser = IntentParser()
        today = datetime.now().strftime("%Y-%m-%d")
        
        result = parser._resolve_date_range(None, "do I have any event today?")
        assert result == today
    
    def test_this_week_preserved(self):
        """Test 'this_week' is preserved as-is for range queries."""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._resolve_date_range("this_week", "any text")
        assert result == "this_week"
    
    def test_iso_date_passthrough(self):
        """Test ISO date format is passed through unchanged."""
        from app.ai.intent.parser import IntentParser
        parser = IntentParser()
        
        result = parser._resolve_date_range("2025-12-25", "any text")
        assert result == "2025-12-25"
