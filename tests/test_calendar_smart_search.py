"""
Tests for Sprint 3.9 - Smart Calendar Search with LLM Semantic Matching.

These tests verify the calendar semantic search functionality that:
- Handles typos: "birday" -> "birthday"
- Handles translations: "birthday" -> "cumpleaños"
- Handles synonyms: "bday" -> "birthday"
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.ai.prompts.calendar_search_prompts import (
    CALENDAR_SEMANTIC_MATCHER_PROMPT,
    format_events_for_prompt,
    build_matcher_prompt,
)
from app.services.calendar_search_service import (
    CalendarSearchService,
    SmartSearchResult,
    calendar_search_service,
)
from app.environments.google.calendar.schemas import CalendarEvent


# ---------------------------------------------------------------------------
# TEST FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_events():
    """Create mock calendar events for testing."""
    now = datetime.now(timezone.utc)
    
    event1 = MagicMock(spec=CalendarEvent)
    event1.get_display_title.return_value = "Cumpleaños de Victor"
    event1.get_time_display.return_value = "Dec 15, 3:00 PM"
    event1.start_datetime = now + timedelta(days=3)
    
    event2 = MagicMock(spec=CalendarEvent)
    event2.get_display_title.return_value = "Team Meeting"
    event2.get_time_display.return_value = "Dec 12, 9:00 AM"
    event2.start_datetime = now + timedelta(days=1)
    
    event3 = MagicMock(spec=CalendarEvent)
    event3.get_display_title.return_value = "Aniversario de boda"
    event3.get_time_display.return_value = "Dec 20, 12:00 PM"
    event3.start_datetime = now + timedelta(days=8)
    
    event4 = MagicMock(spec=CalendarEvent)
    event4.get_display_title.return_value = "Birthday party"
    event4.get_time_display.return_value = "Dec 16, 2:00 PM"
    event4.start_datetime = now + timedelta(days=4)
    
    return [event1, event2, event3, event4]


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_credentials():
    """Create mock OAuth credentials."""
    cred = MagicMock()
    cred.access_token = "test_access_token"
    cred.user_id = uuid4()
    cred.provider = "google"
    return cred


# ---------------------------------------------------------------------------
# PROMPT FORMATTING TESTS
# ---------------------------------------------------------------------------

class TestPromptFormatting:
    """Test prompt formatting utilities."""
    
    def test_format_events_for_prompt_empty(self):
        """Test formatting empty event list."""
        result = format_events_for_prompt([])
        assert result == "(No events found)"
    
    def test_format_events_for_prompt_with_events(self, mock_events):
        """Test formatting event list."""
        result = format_events_for_prompt(mock_events)
        
        assert "1. Cumpleaños de Victor" in result
        assert "2. Team Meeting" in result
        assert "3. Aniversario de boda" in result
        assert "4. Birthday party" in result
    
    def test_build_matcher_prompt_includes_query(self, mock_events):
        """Test that matcher prompt includes the query."""
        prompt = build_matcher_prompt("birthday", mock_events)
        
        assert "birthday" in prompt
        assert "Cumpleaños de Victor" in prompt
    
    def test_prompt_template_has_required_sections(self):
        """Test that prompt template has all required sections."""
        assert "TYPO TOLERANCE" in CALENDAR_SEMANTIC_MATCHER_PROMPT
        assert "CROSS-LANGUAGE MATCHING" in CALENDAR_SEMANTIC_MATCHER_PROMPT
        assert "SYNONYM HANDLING" in CALENDAR_SEMANTIC_MATCHER_PROMPT
        assert "PARTIAL MATCHING" in CALENDAR_SEMANTIC_MATCHER_PROMPT
        assert "matched_events" in CALENDAR_SEMANTIC_MATCHER_PROMPT
        assert "no_match_found" in CALENDAR_SEMANTIC_MATCHER_PROMPT
        assert "corrected_query" in CALENDAR_SEMANTIC_MATCHER_PROMPT


# ---------------------------------------------------------------------------
# SMART SEARCH RESULT TESTS
# ---------------------------------------------------------------------------

class TestSmartSearchResult:
    """Test SmartSearchResult dataclass."""
    
    def test_create_success_result(self, mock_events):
        """Test creating a successful search result."""
        result = SmartSearchResult(
            events=mock_events[:2],
            corrected_query="birthday",
            no_match_found=False,
        )
        
        assert len(result.events) == 2
        assert result.corrected_query == "birthday"
        assert result.no_match_found is False
        assert result.error is None
    
    def test_create_no_match_result(self):
        """Test creating a no-match result."""
        result = SmartSearchResult(
            events=[],
            corrected_query="doctor",
            no_match_found=True,
        )
        
        assert len(result.events) == 0
        assert result.no_match_found is True
    
    def test_create_error_result(self):
        """Test creating an error result."""
        result = SmartSearchResult(
            events=[],
            error="Google Calendar not connected.",
        )
        
        assert result.error is not None
        assert "not connected" in result.error


# ---------------------------------------------------------------------------
# CALENDAR SEARCH SERVICE TESTS
# ---------------------------------------------------------------------------

class TestCalendarSearchServiceInit:
    """Test service initialization."""
    
    def test_singleton_exists(self):
        """Test that singleton instance exists."""
        assert calendar_search_service is not None
        assert isinstance(calendar_search_service, CalendarSearchService)
    
    def test_create_instance(self):
        """Test creating a new instance."""
        service = CalendarSearchService()
        assert service is not None


class TestSmartSearchNoCredentials:
    """Test smart search when user has no credentials."""
    
    @pytest.mark.asyncio
    async def test_returns_error_when_no_credentials(self, mock_db):
        """Test that search returns error when no OAuth credentials."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = CalendarSearchService()
        result = await service.smart_search(
            user_query="birthday",
            user_id=uuid4(),
            db=mock_db,
        )
        
        assert result.error is not None
        assert "not connected" in result.error
        assert len(result.events) == 0


class TestSmartSearchEmptyQuery:
    """Test smart search with empty query."""
    
    @pytest.mark.asyncio
    async def test_empty_query_returns_no_match(self, mock_db):
        """Test that empty query returns no match."""
        service = CalendarSearchService()
        
        result = await service.smart_search(
            user_query="",
            user_id=uuid4(),
            db=mock_db,
        )
        
        assert result.no_match_found is True
        assert len(result.events) == 0
    
    @pytest.mark.asyncio
    async def test_whitespace_query_returns_no_match(self, mock_db):
        """Test that whitespace-only query returns no match."""
        service = CalendarSearchService()
        
        result = await service.smart_search(
            user_query="   ",
            user_id=uuid4(),
            db=mock_db,
        )
        
        assert result.no_match_found is True


class TestSmartSearchWithMockedLLM:
    """Test smart search with mocked LLM responses."""
    
    @pytest.mark.asyncio
    async def test_typo_matching_birday(self, mock_db, mock_credentials, mock_events):
        """Test that 'birday' matches 'Cumpleaños de Victor'."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        # Mock LLM response for typo correction
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [
                {
                    "event_title": "Cumpleaños de Victor",
                    "event_date": "Dec 15",
                    "match_reason": "typo 'birday' -> 'birthday' + translation",
                    "confidence": 0.88
                }
            ],
            "no_match_found": False,
            "corrected_query": "birthday"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="birday",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.corrected_query == "birthday"
            assert len(result.events) == 1
            assert result.events[0].get_display_title() == "Cumpleaños de Victor"
    
    @pytest.mark.asyncio
    async def test_translation_matching_anniversary(self, mock_db, mock_credentials, mock_events):
        """Test that 'anniversary' matches 'Aniversario de boda'."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [
                {
                    "event_title": "Aniversario de boda",
                    "event_date": "Dec 20",
                    "match_reason": "translation 'anniversary' = 'aniversario'",
                    "confidence": 0.95
                }
            ],
            "no_match_found": False,
            "corrected_query": "anniversary"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="anniversary",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.corrected_query == "anniversary"
            assert len(result.events) == 1
            assert "Aniversario" in result.events[0].get_display_title()
    
    @pytest.mark.asyncio
    async def test_multiple_matches_birthday(self, mock_db, mock_credentials, mock_events):
        """Test that 'birthday' matches both Spanish and English events."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [
                {
                    "event_title": "Cumpleaños de Victor",
                    "event_date": "Dec 15",
                    "match_reason": "translation 'cumpleaños' = 'birthday'",
                    "confidence": 0.95
                },
                {
                    "event_title": "Birthday party",
                    "event_date": "Dec 16",
                    "match_reason": "exact match 'birthday'",
                    "confidence": 0.98
                }
            ],
            "no_match_found": False,
            "corrected_query": "birthday"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="birthday",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert len(result.events) == 2
            titles = [e.get_display_title() for e in result.events]
            assert "Cumpleaños de Victor" in titles
            assert "Birthday party" in titles
    
    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, mock_db, mock_credentials, mock_events):
        """Test that unrelated query returns no matches."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [],
            "no_match_found": True,
            "corrected_query": "doctor"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="doctor",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.no_match_found is True
            assert len(result.events) == 0
    
    @pytest.mark.asyncio
    async def test_synonym_matching_bday(self, mock_db, mock_credentials, mock_events):
        """Test that 'bday' matches birthday events."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [
                {
                    "event_title": "Cumpleaños de Victor",
                    "event_date": "Dec 15",
                    "match_reason": "synonym 'bday' = 'birthday' + translation",
                    "confidence": 0.90
                },
                {
                    "event_title": "Birthday party",
                    "event_date": "Dec 16",
                    "match_reason": "synonym 'bday' = 'birthday'",
                    "confidence": 0.95
                }
            ],
            "no_match_found": False,
            "corrected_query": "birthday"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="my bday",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.corrected_query == "birthday"
            assert len(result.events) == 2


class TestSmartSearchWithDateRange:
    """Test smart search with date_range parameter (Sprint 4.1 consolidated API)."""
    
    @pytest.mark.asyncio
    async def test_search_with_date_range(self, mock_db, mock_credentials, mock_events):
        """Test search scoped to a date range (Sprint 4.1 consolidated API)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [
                {
                    "event_title": "Team Meeting",
                    "event_date": "Dec 12",
                    "match_reason": "exact match",
                    "confidence": 0.98
                }
            ],
            "no_match_found": False,
            "corrected_query": "meeting"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=[mock_events[1]])
            mock_client.get_user_timezone = AsyncMock(return_value="America/New_York")
            mock_client._parse_date_range = MagicMock(return_value=(
                MagicMock(), MagicMock()
            ))
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            # Sprint 4.1: Use date_range parameter instead of separate method
            result = await service.smart_search(
                user_query="meeting",
                user_id=uuid4(),
                db=mock_db,
                date_range="today",
            )
            
            assert len(result.events) == 1
            assert "Meeting" in result.events[0].get_display_title()
    
    @pytest.mark.asyncio
    async def test_search_with_this_week_range(self, mock_db, mock_credentials, mock_events):
        """Test search scoped to this_week date range."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = json.dumps({
            "matched_events": [
                {
                    "event_title": "Team Meeting",
                    "match_reason": "exact match",
                    "confidence": 0.95
                }
            ],
            "no_match_found": False,
            "corrected_query": "meeting"
        })
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=[mock_events[1]])
            mock_client.get_user_timezone = AsyncMock(return_value="America/New_York")
            mock_client._parse_date_range = MagicMock(return_value=(
                MagicMock(), MagicMock()
            ))
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="meeting",
                user_id=uuid4(),
                db=mock_db,
                date_range="this_week",
            )
            
            assert len(result.events) == 1


class TestLLMErrorHandling:
    """Test error handling for LLM failures."""
    
    @pytest.mark.asyncio
    async def test_handles_llm_failure(self, mock_db, mock_credentials, mock_events):
        """Test graceful handling of LLM failures."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = False
        llm_response.error = "API rate limit exceeded"
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="birthday",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.error is not None
            assert len(result.events) == 0
    
    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self, mock_db, mock_credentials, mock_events):
        """Test handling of invalid JSON from LLM."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        llm_response = MagicMock()
        llm_response.success = True
        llm_response.content = "This is not valid JSON"
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class, patch(
            'app.services.calendar_search_service.openai_provider'
        ) as mock_openai:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(return_value=mock_events)
            mock_client_class.return_value = mock_client
            
            mock_openai.generate_json = AsyncMock(return_value=llm_response)
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="birthday",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.error is not None
            assert "parse" in result.error.lower()


class TestCalendarAPIErrorHandling:
    """Test error handling for Calendar API failures."""
    
    @pytest.mark.asyncio
    async def test_handles_calendar_api_error(self, mock_db, mock_credentials):
        """Test handling of Calendar API errors."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        from app.environments.base import APIError
        
        with patch(
            'app.services.calendar_search_service.GoogleCalendarClient'
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.list_upcoming_events = AsyncMock(
                side_effect=APIError("Token expired")
            )
            mock_client_class.return_value = mock_client
            
            service = CalendarSearchService()
            result = await service.smart_search(
                user_query="birthday",
                user_id=uuid4(),
                db=mock_db,
            )
            
            assert result.error is not None
            assert len(result.events) == 0
