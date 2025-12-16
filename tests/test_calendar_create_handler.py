"""
Tests for Calendar Create Handler - Sprint 3.8

Tests for the calendar create handler methods in intent_service.py:
- _handle_calendar_create (router)
- _handle_create_event (stores pending)
- _handle_confirm_create (creates via API)
- _handle_cancel_create (cancels pending)
- _handle_edit_pending (updates pending)
- Helper methods: _build_confirmation_message, _build_success_message, etc.

These tests use mocks for:
- Database session
- OAuth credentials
- Google Calendar API client
- Pending event service
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import date, datetime, timezone, timedelta
import time

from app.services.intent_service import (
    IntentService,
    IntentResult,
    IntentResultType,
)
from app.ai.intent.schemas import (
    CalendarCreateIntent,
    IntentType,
    ActionType,
)
from app.services.pending_event_service import (
    PendingEvent,
    PendingEventService,
)
import app.services.pending_event_service as pending_module
import app.environments.google.calendar.client as calendar_client_module


# ===========================================================================
# FIXTURES
# ===========================================================================

@pytest.fixture
def service():
    """Create a fresh IntentService instance."""
    return IntentService()


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def user_id():
    """Create a test user ID."""
    return uuid4()


@pytest.fixture
def mock_credentials():
    """Create mock OAuth credentials."""
    creds = MagicMock()
    creds.access_token = "test-access-token"
    creds.user_id = uuid4()
    creds.provider = "google"
    return creds


@pytest.fixture
def pending_event_service():
    """Create a fresh pending event service."""
    service = PendingEventService()
    yield service
    service.clear_all()


@pytest.fixture
def sample_pending_event(user_id):
    """Create a sample pending event."""
    return PendingEvent(
        user_id=str(user_id),
        event_title="Team Meeting",
        event_date=date(2025, 1, 15),
        event_time="18:00",
        duration_minutes=60,
        is_all_day=False,
        timezone="America/New_York",
    )


# ===========================================================================
# _HANDLE_CALENDAR_CREATE ROUTER TESTS
# ===========================================================================

class TestHandleCalendarCreateRouter:
    """Tests for the _handle_calendar_create routing method."""
    
    @pytest.mark.asyncio
    async def test_routes_create_event(self, service, mock_db, user_id):
        """Should route CREATE_EVENT action to _handle_create_event."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="schedule a meeting",
            action=ActionType.CREATE_EVENT,
            event_title="Meeting",
        )
        
        with patch.object(service, '_handle_create_event', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Test",
            )
            
            await service._handle_calendar_create(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_confirm_create(self, service, mock_db, user_id):
        """Should route CONFIRM_CREATE action to _handle_confirm_create."""
        intent = CalendarCreateIntent(
            confidence=0.99,
            original_text="yes",
            action=ActionType.CONFIRM_CREATE,
        )
        
        with patch.object(service, '_handle_confirm_create', new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Test",
            )
            
            await service._handle_calendar_create(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            mock_confirm.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_cancel_create(self, service, mock_db, user_id):
        """Should route CANCEL_CREATE action to _handle_cancel_create."""
        intent = CalendarCreateIntent(
            confidence=0.99,
            original_text="no",
            action=ActionType.CANCEL_CREATE,
        )
        
        with patch.object(service, '_handle_cancel_create', new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Test",
            )
            
            await service._handle_calendar_create(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            mock_cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_edit_pending(self, service, mock_db, user_id):
        """Should route EDIT_PENDING_EVENT action to _handle_edit_pending."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="change time to 7 pm",
            action=ActionType.EDIT_PENDING_EVENT,
            edit_field="event_time",
            edit_value="19:00",
        )
        
        with patch.object(service, '_handle_edit_pending', new_callable=AsyncMock) as mock_edit:
            mock_edit.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Test",
            )
            
            await service._handle_calendar_create(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            mock_edit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_action(self, service, mock_db, user_id):
        """Should return error for unknown action."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="unknown action",
            action=ActionType.HELP,  # Not a calendar create action
        )
        
        result = await service._handle_calendar_create(
            request_id="test-req",
            intent=intent,
            user_id=user_id,
            start_time=time.time(),
            db=mock_db,
        )
        
        assert result.success is False
        assert "Unknown" in result.message or "unknown" in result.message.lower()


# ===========================================================================
# _HANDLE_CREATE_EVENT TESTS
# ===========================================================================

class TestHandleCreateEvent:
    """Tests for _handle_create_event method."""
    
    @pytest.mark.asyncio
    async def test_create_event_requires_credentials(self, service, mock_db, user_id):
        """Should return error if no OAuth credentials."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="schedule a meeting",
            action=ActionType.CREATE_EVENT,
            event_title="Meeting",
        )
        
        # Mock no credentials
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = await service._handle_create_event(
            request_id="test-req",
            intent=intent,
            user_id=user_id,
            start_time=time.time(),
            db=mock_db,
        )
        
        assert result.success is False
        assert "connect" in result.message.lower() or "google" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_create_event_stores_pending(self, service, mock_db, user_id, mock_credentials):
        """Should store pending event and return confirmation."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="schedule a meeting tomorrow at 6 pm",
            action=ActionType.CREATE_EVENT,
            event_title="Meeting",
            event_date="2025-01-15",
            event_time="18:00",
        )
        
        # Mock credentials
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        with patch.object(calendar_client_module, 'GoogleCalendarClient') as MockClient, \
             patch.object(pending_module, 'pending_event_service') as mock_pending:
            
            mock_client = AsyncMock()
            mock_client.get_user_timezone = AsyncMock(return_value="America/New_York")
            MockClient.return_value = mock_client
            
            mock_pending_event = PendingEvent(
                user_id=str(user_id),
                event_title="Meeting",
                event_date=date(2025, 1, 15),
                event_time="18:00",
            )
            mock_pending.store_pending = AsyncMock(return_value=mock_pending_event)
            
            result = await service._handle_create_event(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            assert result.success is True
            assert "confirm" in result.message.lower() or "Meeting" in result.message
    
    @pytest.mark.asyncio
    async def test_create_event_returns_confirmation_message(self, service, mock_db, user_id, mock_credentials):
        """Should return message with event details."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="schedule team standup at 10 am",
            action=ActionType.CREATE_EVENT,
            event_title="Team Standup",
            event_time="10:00",
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        with patch.object(calendar_client_module, 'GoogleCalendarClient') as MockClient, \
             patch.object(pending_module, 'pending_event_service') as mock_pending:
            
            mock_client = AsyncMock()
            mock_client.get_user_timezone = AsyncMock(return_value="UTC")
            MockClient.return_value = mock_client
            
            mock_pending_event = PendingEvent(
                user_id=str(user_id),
                event_title="Team Standup",
                event_time="10:00",
                event_date=date.today(),
            )
            mock_pending.store_pending = AsyncMock(return_value=mock_pending_event)
            
            result = await service._handle_create_event(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            assert "Team Standup" in result.message or "yes" in result.message.lower()


# ===========================================================================
# _HANDLE_CONFIRM_CREATE TESTS
# ===========================================================================

class TestHandleConfirmCreate:
    """Tests for _handle_confirm_create method."""
    
    @pytest.mark.asyncio
    async def test_confirm_create_no_pending(self, service, mock_db, user_id):
        """Should return error if no pending event (and no pending edit)."""
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.get_pending.return_value = None
            mock_pending.is_expired.return_value = True
            
            # Also mock pending_edit_service (context-aware flow)
            with patch("app.services.pending_edit_service.pending_edit_service") as mock_edit:
                mock_edit.get_pending.return_value = None
                
                result = await service._handle_confirm_create(
                    request_id="test-req",
                    user_id=user_id,
                    start_time=time.time(),
                    db=mock_db,
                )
            
            assert result.success is False
            assert "timed out" in result.message.lower() or "no pending" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_confirm_create_requires_credentials(self, service, mock_db, user_id, sample_pending_event):
        """Should return error if no credentials."""
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.get_pending.return_value = sample_pending_event
            mock_pending.confirm_pending = AsyncMock()
            
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            result = await service._handle_confirm_create(
                request_id="test-req",
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            assert result.success is False
            assert "connect" in result.message.lower() or "google" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_confirm_create_success(self, service, mock_db, user_id, mock_credentials, sample_pending_event):
        """Should create event via API on confirmation."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending, \
             patch.object(calendar_client_module, 'GoogleCalendarClient') as MockClient:
            
            mock_pending.get_pending.return_value = sample_pending_event
            mock_pending.confirm_pending = AsyncMock()
            
            mock_response = MagicMock()
            mock_response.event_id = "event-123"
            mock_response.summary = "Team Meeting"
            mock_response.html_link = "https://calendar.google.com/event/123"
            
            mock_client = AsyncMock()
            mock_client.create_event = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client
            
            result = await service._handle_confirm_create(
                request_id="test-req",
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            assert result.success is True
            assert "scheduled" in result.message.lower() or "✓" in result.message
    
    @pytest.mark.asyncio
    async def test_confirm_create_all_day_event(self, service, mock_db, user_id, mock_credentials):
        """Should create all-day event correctly."""
        all_day_pending = PendingEvent(
            user_id=str(user_id),
            event_title="Birthday",
            event_date=date(2025, 1, 15),
            is_all_day=True,
            timezone="UTC",
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending, \
             patch.object(calendar_client_module, 'GoogleCalendarClient') as MockClient:
            
            mock_pending.get_pending.return_value = all_day_pending
            mock_pending.confirm_pending = AsyncMock()
            
            mock_response = MagicMock()
            mock_response.event_id = "event-123"
            mock_response.summary = "Birthday"
            mock_response.html_link = "https://calendar.google.com/event/123"
            
            mock_client = AsyncMock()
            mock_client.create_all_day_event = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client
            
            result = await service._handle_confirm_create(
                request_id="test-req",
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            assert result.success is True
            mock_client.create_all_day_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_confirm_create_handles_api_error(self, service, mock_db, user_id, mock_credentials, sample_pending_event):
        """Should handle API errors gracefully."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending, \
             patch.object(calendar_client_module, 'GoogleCalendarClient') as MockClient:
            
            mock_pending.confirm_pending = AsyncMock(return_value=sample_pending_event)
            
            mock_client = AsyncMock()
            mock_client.create_event = AsyncMock(side_effect=Exception("API Error"))
            MockClient.return_value = mock_client
            
            result = await service._handle_confirm_create(
                request_id="test-req",
                user_id=user_id,
                start_time=time.time(),
                db=mock_db,
            )
            
            assert result.success is False
            assert "failed" in result.message.lower() or "error" in result.message.lower()


# ===========================================================================
# _HANDLE_CANCEL_CREATE TESTS
# ===========================================================================

class TestHandleCancelCreate:
    """Tests for _handle_cancel_create method."""
    
    @pytest.mark.asyncio
    async def test_cancel_create_success(self, service, user_id):
        """Should cancel pending event."""
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.cancel_pending.return_value = True
            
            result = await service._handle_cancel_create(
                request_id="test-req",
                user_id=user_id,
                start_time=time.time(),
            )
            
            assert result.success is True
            assert "cancelled" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_cancel_create_no_pending(self, service, user_id):
        """Should handle when no pending event exists."""
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.cancel_pending.return_value = False
            
            result = await service._handle_cancel_create(
                request_id="test-req",
                user_id=user_id,
                start_time=time.time(),
            )
            
            assert result.success is True  # Not an error, just nothing to cancel
            assert "no pending" in result.message.lower()


# ===========================================================================
# _HANDLE_EDIT_PENDING TESTS
# ===========================================================================

class TestHandleEditPending:
    """Tests for _handle_edit_pending method."""
    
    @pytest.mark.asyncio
    async def test_edit_pending_no_pending(self, service, user_id):
        """Should return error if no pending event."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="change time to 7 pm",
            action=ActionType.EDIT_PENDING_EVENT,
            edit_field="event_time",
            edit_value="19:00",
        )
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.get_pending.return_value = None
            mock_pending.is_expired.return_value = True
            
            result = await service._handle_edit_pending(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
            )
            
            assert result.success is False
    
    @pytest.mark.asyncio
    async def test_edit_pending_missing_field(self, service, user_id, sample_pending_event):
        """Should return error if edit_field missing."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="change something",
            action=ActionType.EDIT_PENDING_EVENT,
            edit_field=None,
            edit_value="some value",
        )
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.get_pending.return_value = sample_pending_event
            
            result = await service._handle_edit_pending(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
            )
            
            assert result.success is False
            assert "couldn't understand" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_edit_pending_time_success(self, service, user_id, sample_pending_event):
        """Should update event time."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="change time to 7 pm",
            action=ActionType.EDIT_PENDING_EVENT,
            edit_field="event_time",
            edit_value="7 pm",
        )
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.get_pending.return_value = sample_pending_event
            
            updated_event = PendingEvent(
                user_id=str(user_id),
                event_title="Team Meeting",
                event_date=date(2025, 1, 15),
                event_time="19:00",  # Updated
            )
            mock_pending.update_pending.return_value = updated_event
            
            result = await service._handle_edit_pending(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
            )
            
            assert result.success is True
            assert "updated" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_edit_pending_duration_success(self, service, user_id, sample_pending_event):
        """Should update duration."""
        intent = CalendarCreateIntent(
            confidence=0.9,
            original_text="make it 2 hours",
            action=ActionType.EDIT_PENDING_EVENT,
            edit_field="duration_minutes",
            edit_value="2 hours",
        )
        
        with patch.object(pending_module, 'pending_event_service') as mock_pending:
            mock_pending.get_pending.return_value = sample_pending_event
            
            updated_event = PendingEvent(
                user_id=str(user_id),
                event_title="Team Meeting",
                event_date=date(2025, 1, 15),
                event_time="18:00",
                duration_minutes=120,  # Updated
            )
            mock_pending.update_pending.return_value = updated_event
            
            result = await service._handle_edit_pending(
                request_id="test-req",
                intent=intent,
                user_id=user_id,
                start_time=time.time(),
            )
            
            assert result.success is True


# ===========================================================================
# HELPER METHOD TESTS
# ===========================================================================

class TestHelperMethods:
    """Tests for helper methods in intent_service."""
    
    def test_build_confirmation_message_basic(self, service, sample_pending_event):
        """Should build confirmation message with event details."""
        message = service._build_confirmation_message(sample_pending_event)
        
        assert "Team Meeting" in message
        assert "confirm" in message.lower() or "yes" in message.lower()
    
    def test_build_confirmation_message_all_day(self, service):
        """Should show all-day in message."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Birthday",
            event_date=date(2025, 1, 15),
            is_all_day=True,
        )
        
        message = service._build_confirmation_message(pending)
        
        assert "all" in message.lower() and "day" in message.lower()
    
    def test_build_confirmation_message_with_recurrence(self, service):
        """Should include recurrence info."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Weekly Standup",
            event_date=date(2025, 1, 15),
            event_time="10:00",
            recurrence="RRULE:FREQ=WEEKLY",
        )
        
        message = service._build_confirmation_message(pending)
        
        assert "weekly" in message.lower() or "repeat" in message.lower()
    
    def test_build_confirmation_message_with_location(self, service):
        """Should include location."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_date=date(2025, 1, 15),
            event_time="14:00",
            location="Conference Room A",
        )
        
        message = service._build_confirmation_message(pending)
        
        assert "Conference Room A" in message
    
    def test_build_confirmation_message_with_highlight(self, service, sample_pending_event):
        """Should highlight edited field."""
        message = service._build_confirmation_message(
            sample_pending_event,
            highlight_field="event_time",
        )
        
        assert "updated" in message.lower()
    
    def test_format_recurrence_daily(self, service):
        """Should format daily recurrence."""
        result = service._format_recurrence("RRULE:FREQ=DAILY")
        assert "daily" in result.lower()
    
    def test_format_recurrence_weekly(self, service):
        """Should format weekly recurrence."""
        result = service._format_recurrence("RRULE:FREQ=WEEKLY")
        assert "weekly" in result.lower()
    
    def test_format_recurrence_weekly_monday(self, service):
        """Should format weekly on Monday."""
        result = service._format_recurrence("RRULE:FREQ=WEEKLY;BYDAY=MO")
        assert "monday" in result.lower()
    
    def test_format_recurrence_monthly(self, service):
        """Should format monthly recurrence."""
        result = service._format_recurrence("RRULE:FREQ=MONTHLY")
        assert "monthly" in result.lower()
    
    def test_resolve_date_string_iso(self, service):
        """Should parse ISO date string."""
        result = service._resolve_date_string("2025-01-15")
        assert result == date(2025, 1, 15)
    
    def test_resolve_date_string_today(self, service):
        """Should resolve 'today'."""
        result = service._resolve_date_string("today")
        assert result == datetime.now().date()
    
    def test_resolve_date_string_tomorrow(self, service):
        """Should resolve 'tomorrow'."""
        result = service._resolve_date_string("tomorrow")
        expected = (datetime.now() + timedelta(days=1)).date()
        assert result == expected
    
    def test_resolve_date_string_none(self, service):
        """Should return None for None."""
        result = service._resolve_date_string(None)
        assert result is None
    
    def test_parse_edit_value_time(self, service):
        """Should parse time edit value."""
        with patch('app.ai.intent.parser.intent_parser') as mock_parser:
            mock_parser._resolve_time.return_value = "19:00"
            
            result = service._parse_edit_value("event_time", "7 pm")
            
            mock_parser._resolve_time.assert_called_with("7 pm")
    
    def test_parse_edit_value_duration_hours(self, service):
        """Should parse duration in hours."""
        result = service._parse_edit_value("duration_minutes", "2 hours")
        assert result == 120
    
    def test_parse_edit_value_duration_minutes(self, service):
        """Should parse duration in minutes."""
        result = service._parse_edit_value("duration_minutes", "90 minutes")
        assert result == 90
    
    def test_parse_edit_value_title(self, service):
        """Should strip whitespace from title."""
        result = service._parse_edit_value("event_title", "  New Title  ")
        assert result == "New Title"
    
    def test_parse_edit_value_location(self, service):
        """Should strip whitespace from location."""
        result = service._parse_edit_value("location", "  Room 101  ")
        assert result == "Room 101"
    
    def test_parse_edit_value_all_day_true(self, service):
        """Should parse all-day boolean."""
        assert service._parse_edit_value("is_all_day", "yes") is True
        assert service._parse_edit_value("is_all_day", "true") is True
        assert service._parse_edit_value("is_all_day", "all day") is True
    
    def test_parse_edit_value_all_day_false(self, service):
        """Should parse all-day as False for other values."""
        assert service._parse_edit_value("is_all_day", "no") is False
        assert service._parse_edit_value("is_all_day", "false") is False


# ===========================================================================
# BUILD SUCCESS MESSAGE TESTS
# ===========================================================================

class TestBuildSuccessMessage:
    """Tests for _build_calendar_success_message method."""
    
    def test_build_success_message_timed_event(self, service):
        """Should build success message for timed event."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_date=date(2025, 1, 15),
            event_time="18:00",
        )
        
        response = MagicMock()
        response.summary = "Meeting"
        response.event_id = "event-123"
        response.html_link = "https://calendar.google.com/event/123"
        
        message = service._build_calendar_success_message(pending, response)
        
        assert "Meeting" in message
        assert "scheduled" in message.lower()
        assert "✓" in message
    
    def test_build_success_message_all_day_event(self, service):
        """Should build success message for all-day event."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Birthday",
            event_date=date(2025, 1, 15),
            is_all_day=True,
        )
        
        response = MagicMock()
        response.summary = "Birthday"
        response.event_id = "event-123"
        response.html_link = "https://calendar.google.com/event/123"
        
        message = service._build_calendar_success_message(pending, response)
        
        assert "Birthday" in message
        assert "all day" in message.lower()
    
    def test_build_success_message_with_recurrence(self, service):
        """Should include recurrence in success message."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Standup",
            event_date=date(2025, 1, 15),
            event_time="10:00",
            recurrence="RRULE:FREQ=DAILY",
        )
        
        response = MagicMock()
        response.summary = "Standup"
        response.event_id = "event-123"
        response.html_link = "https://calendar.google.com/event/123"
        
        message = service._build_calendar_success_message(pending, response)
        
        assert "daily" in message.lower() or "repeat" in message.lower()
