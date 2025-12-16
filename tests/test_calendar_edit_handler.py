"""
Tests for Calendar Edit/Delete Intent Handlers (Sprint 3.9).

Tests the intent service handlers for editing and deleting calendar events.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.intent_service import IntentService, IntentResult, IntentResultType
from app.ai.intent.schemas import (
    ActionType,
    IntentType,
    CalendarEditIntent,
)
from app.services.pending_edit_service import (
    PendingEditService,
    PendingEdit,
    MatchingEvent,
    PendingOperationType,
    PendingState,
)
from app.services.calendar_search_service import SmartSearchResult
from app.environments.google.calendar.schemas import CalendarEvent, EventTime


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def intent_service():
    """Create an IntentService instance for testing."""
    return IntentService()


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return uuid4()


@pytest.fixture
def mock_credentials():
    """Mock OAuth credentials."""
    cred = MagicMock()
    cred.access_token = "test-access-token"
    cred.refresh_token = "test-refresh-token"
    return cred


@pytest.fixture
def sample_calendar_events():
    """Sample CalendarEvent objects (as returned by smart_search)."""
    return [
        CalendarEvent(
            id="event-abc123",
            summary="Team Meeting",
            start=EventTime(dateTime=datetime(2025, 12, 16, 10, 0, tzinfo=timezone.utc)),
            end=EventTime(dateTime=datetime(2025, 12, 16, 11, 0, tzinfo=timezone.utc)),
            location="Room A",
        ),
        CalendarEvent(
            id="event-def456",
            summary="Dentist Appointment",
            start=EventTime(dateTime=datetime(2025, 12, 16, 14, 0, tzinfo=timezone.utc)),
            end=EventTime(dateTime=datetime(2025, 12, 16, 15, 0, tzinfo=timezone.utc)),
        ),
    ]


# ---------------------------------------------------------------------------
# EDIT EXISTING EVENT HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleEditExistingEvent:
    """Tests for _handle_edit_existing_event."""
    
    @pytest.mark.asyncio
    async def test_edit_single_match_asks_for_confirmation(
        self, intent_service, mock_db, sample_user_id, mock_credentials, sample_calendar_events
    ):
        """Single match should auto-select and ask for confirmation."""
        intent = CalendarEditIntent(
            original_text="reschedule my meeting to 3pm",
            confidence=0.95,
            action=ActionType.EDIT_EXISTING_EVENT,
            search_term="meeting",
            changes={"start_datetime": "15:00"},
        )
        
        # Mock smart_search to return a single match
        mock_search_result = SmartSearchResult(
            events=[sample_calendar_events[0]],
            corrected_query="meeting",
        )
        
        with patch("app.services.calendar_search_service.calendar_search_service") as mock_search_svc:
            mock_search_svc.smart_search = AsyncMock(return_value=mock_search_result)
            
            with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
                mock_pending.store_pending_edit = AsyncMock()
                mock_pending_obj = MagicMock()
                mock_pending_obj.needs_selection.return_value = False
                mock_pending_obj.get_confirmation_text.return_value = "Update 'Team Meeting': change start time to 3:00 PM?"
                mock_pending.store_pending_edit.return_value = mock_pending_obj
                
                result = await intent_service._handle_edit_existing_event(
                    request_id="req-123",
                    intent=intent,
                    user_id=sample_user_id,
                    start_time=0,
                    db=mock_db,
                )
        
        assert result.success is True
        assert result.intent_type == IntentResultType.CALENDAR_EDIT
        assert result.action == "edit_existing_event"
        assert "confirm" in result.message.lower() or "yes" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_edit_multiple_matches_asks_for_selection(
        self, intent_service, mock_db, sample_user_id, mock_credentials, sample_calendar_events
    ):
        """Multiple matches should ask for selection."""
        intent = CalendarEditIntent(
            original_text="reschedule my appointment",
            confidence=0.95,
            action=ActionType.EDIT_EXISTING_EVENT,
            search_term="appointment",
            changes={"start_datetime": "15:00"},
        )
        
        mock_search_result = SmartSearchResult(
            events=sample_calendar_events,
            corrected_query="appointment",
        )
        
        with patch("app.services.calendar_search_service.calendar_search_service") as mock_search_svc:
            mock_search_svc.smart_search = AsyncMock(return_value=mock_search_result)
            
            with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
                mock_pending.store_pending_edit = AsyncMock()
                mock_pending_obj = MagicMock()
                mock_pending_obj.needs_selection.return_value = True
                mock_pending_obj.get_event_options_text.return_value = "1. Team Meeting\n2. Dentist Appointment"
                mock_pending.store_pending_edit.return_value = mock_pending_obj
                
                result = await intent_service._handle_edit_existing_event(
                    request_id="req-123",
                    intent=intent,
                    user_id=sample_user_id,
                    start_time=0,
                    db=mock_db,
                )
        
        assert result.success is True
        assert "which one" in result.message.lower() or "multiple" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_edit_no_search_term_returns_error(
        self, intent_service, mock_db, sample_user_id
    ):
        """Missing search term should return helpful error."""
        intent = CalendarEditIntent(
            original_text="reschedule",
            confidence=0.95,
            action=ActionType.EDIT_EXISTING_EVENT,
            search_term=None,  # No search term
        )
        
        result = await intent_service._handle_edit_existing_event(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "what event" in result.message.lower() or "try" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_edit_no_matches_returns_error(
        self, intent_service, mock_db, sample_user_id, mock_credentials
    ):
        """No matching events should return error."""
        intent = CalendarEditIntent(
            original_text="reschedule my nonexistent event",
            confidence=0.95,
            action=ActionType.EDIT_EXISTING_EVENT,
            search_term="nonexistent",
        )
        
        # Mock smart_search to return no matches
        mock_search_result = SmartSearchResult(
            events=[],
            corrected_query="nonexistent",
            no_match_found=True,
        )
        
        with patch("app.services.calendar_search_service.calendar_search_service") as mock_search_svc:
            mock_search_svc.smart_search = AsyncMock(return_value=mock_search_result)
            
            result = await intent_service._handle_edit_existing_event(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
        
        assert result.success is False
        assert "no events found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_edit_search_error_returns_error(
        self, intent_service, mock_db, sample_user_id
    ):
        """Search service error should return error."""
        intent = CalendarEditIntent(
            original_text="reschedule my meeting",
            confidence=0.95,
            action=ActionType.EDIT_EXISTING_EVENT,
            search_term="meeting",
        )
        
        # Mock smart_search to return an error
        mock_search_result = SmartSearchResult(
            events=[],
            error="Google Calendar not connected.",
        )
        
        with patch("app.services.calendar_search_service.calendar_search_service") as mock_search_svc:
            mock_search_svc.smart_search = AsyncMock(return_value=mock_search_result)
            
            result = await intent_service._handle_edit_existing_event(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
        
        assert result.success is False
        assert "google" in result.message.lower() or "connect" in result.message.lower()


# ---------------------------------------------------------------------------
# DELETE EXISTING EVENT HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleDeleteExistingEvent:
    """Tests for _handle_delete_existing_event."""
    
    @pytest.mark.asyncio
    async def test_delete_single_match_asks_for_confirmation(
        self, intent_service, mock_db, sample_user_id, mock_credentials, sample_calendar_events
    ):
        """Single match should auto-select and ask for confirmation."""
        intent = CalendarEditIntent(
            original_text="delete my meeting",
            confidence=0.95,
            action=ActionType.DELETE_EXISTING_EVENT,
            search_term="meeting",
        )
        
        # Mock smart_search to return a single match
        mock_search_result = SmartSearchResult(
            events=[sample_calendar_events[0]],
            corrected_query="meeting",
        )
        
        with patch("app.services.calendar_search_service.calendar_search_service") as mock_search_svc:
            mock_search_svc.smart_search = AsyncMock(return_value=mock_search_result)
            
            with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
                mock_pending.store_pending_edit = AsyncMock()
                mock_pending_obj = MagicMock()
                mock_pending_obj.needs_selection.return_value = False
                mock_pending_obj.get_confirmation_text.return_value = "Delete 'Team Meeting'? This cannot be undone."
                mock_pending.store_pending_edit.return_value = mock_pending_obj
                
                result = await intent_service._handle_delete_existing_event(
                    request_id="req-123",
                    intent=intent,
                    user_id=sample_user_id,
                    start_time=0,
                    db=mock_db,
                )
        
        assert result.success is True
        assert result.intent_type == IntentResultType.CALENDAR_EDIT
        assert result.action == "delete_existing_event"
    
    @pytest.mark.asyncio
    async def test_delete_no_search_term_returns_error(
        self, intent_service, mock_db, sample_user_id
    ):
        """Missing search term should return helpful error."""
        intent = CalendarEditIntent(
            original_text="delete",
            confidence=0.95,
            action=ActionType.DELETE_EXISTING_EVENT,
            search_term=None,
        )
        
        result = await intent_service._handle_delete_existing_event(
            request_id="req-123",
            intent=intent,
            user_id=sample_user_id,
            start_time=0,
            db=mock_db,
        )
        
        assert result.success is False
        assert "what event" in result.message.lower() or "try" in result.message.lower()


# ---------------------------------------------------------------------------
# SELECT EVENT HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleSelectEvent:
    """Tests for _handle_select_event."""
    
    @pytest.mark.asyncio
    async def test_select_valid_index(self, intent_service, sample_user_id):
        """Valid selection should transition to confirmation."""
        intent = CalendarEditIntent(
            original_text="the first one",
            confidence=0.90,
            action=ActionType.SELECT_EVENT,
            selection_index=1,
        )
        
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.get_pending.return_value = MagicMock()
            mock_updated = MagicMock()
            mock_updated.selected_event.summary = "Team Meeting"
            mock_updated.get_confirmation_text.return_value = "Update 'Team Meeting'?"
            mock_pending.select_event.return_value = mock_updated
            
            result = await intent_service._handle_select_event(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
            )
        
        assert result.success is True
        assert result.action == "select_event"
        assert result.parameters["selected_index"] == 1
    
    @pytest.mark.asyncio
    async def test_select_no_pending_returns_error(self, intent_service, sample_user_id):
        """Selection without pending should return error."""
        intent = CalendarEditIntent(
            original_text="the first one",
            confidence=0.90,
            action=ActionType.SELECT_EVENT,
            selection_index=1,
        )
        
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.get_pending.return_value = None
            
            result = await intent_service._handle_select_event(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
            )
        
        assert result.success is False
        assert "no pending" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_select_invalid_index_returns_error(self, intent_service, sample_user_id):
        """Invalid index should return error."""
        intent = CalendarEditIntent(
            original_text="number 10",
            confidence=0.90,
            action=ActionType.SELECT_EVENT,
            selection_index=10,
        )
        
        mock_pending_obj = MagicMock()
        mock_pending_obj.matching_events = [MagicMock(), MagicMock()]  # Only 2 events
        
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.get_pending.return_value = mock_pending_obj
            mock_pending.select_event.return_value = None  # Invalid index
            
            result = await intent_service._handle_select_event(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
            )
        
        assert result.success is False
        assert "invalid" in result.message.lower()


# ---------------------------------------------------------------------------
# CONFIRM EDIT HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleConfirmEdit:
    """Tests for _handle_confirm_edit."""
    
    @pytest.mark.asyncio
    async def test_confirm_edit_success(
        self, intent_service, mock_db, sample_user_id, mock_credentials
    ):
        """Successful edit should update event and return success."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        mock_selected_event = MagicMock()
        mock_selected_event.event_id = "event-abc123"
        mock_selected_event.summary = "Team Meeting"
        
        mock_pending_obj = MagicMock()
        mock_pending_obj.operation = PendingOperationType.EDIT
        mock_pending_obj.selected_event = mock_selected_event
        mock_pending_obj.changes = {"location": "Room B"}
        mock_pending_obj.is_ready_for_confirmation.return_value = True
        
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.get_pending.return_value = mock_pending_obj
            mock_pending.confirm_pending = AsyncMock()
            
            with patch("app.environments.google.calendar.client.GoogleCalendarClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.update_event.return_value = {"id": "event-abc123", "summary": "Team Meeting"}
                MockClient.return_value = mock_client
                
                result = await intent_service._handle_confirm_edit(
                    request_id="req-123",
                    user_id=sample_user_id,
                    start_time=0,
                    db=mock_db,
                )
        
        assert result.success is True
        assert result.action == "confirm_edit"
        assert "updated" in result.message.lower() or "✓" in result.message
    
    @pytest.mark.asyncio
    async def test_confirm_edit_no_pending_returns_error(
        self, intent_service, mock_db, sample_user_id
    ):
        """No pending edit should return error."""
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.get_pending.return_value = None
            
            result = await intent_service._handle_confirm_edit(
                request_id="req-123",
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
        
        assert result.success is False
        assert "no pending" in result.message.lower()


# ---------------------------------------------------------------------------
# CONFIRM DELETE HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleConfirmDelete:
    """Tests for _handle_confirm_delete."""
    
    @pytest.mark.asyncio
    async def test_confirm_delete_success(
        self, intent_service, mock_db, sample_user_id, mock_credentials
    ):
        """Successful delete should remove event and return success."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_credentials
        
        mock_selected_event = MagicMock()
        mock_selected_event.event_id = "event-abc123"
        mock_selected_event.summary = "Team Meeting"
        
        mock_pending_obj = MagicMock()
        mock_pending_obj.operation = PendingOperationType.DELETE
        mock_pending_obj.selected_event = mock_selected_event
        mock_pending_obj.is_ready_for_confirmation.return_value = True
        
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.get_pending.return_value = mock_pending_obj
            mock_pending.confirm_pending = AsyncMock()
            
            with patch("app.environments.google.calendar.client.GoogleCalendarClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.delete_event.return_value = {"success": True}
                MockClient.return_value = mock_client
                
                result = await intent_service._handle_confirm_delete(
                    request_id="req-123",
                    user_id=sample_user_id,
                    start_time=0,
                    db=mock_db,
                )
        
        assert result.success is True
        assert result.action == "confirm_delete"
        assert "deleted" in result.message.lower() or "✓" in result.message


# ---------------------------------------------------------------------------
# CANCEL EDIT HANDLER TESTS
# ---------------------------------------------------------------------------

class TestHandleCancelEdit:
    """Tests for _handle_cancel_edit."""
    
    @pytest.mark.asyncio
    async def test_cancel_edit_success(self, intent_service, sample_user_id):
        """Cancel should remove pending and return success."""
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.cancel_pending.return_value = True
            
            result = await intent_service._handle_cancel_edit(
                request_id="req-123",
                user_id=sample_user_id,
                start_time=0,
            )
        
        assert result.success is True
        assert result.action == "cancel_edit"
        assert "cancelled" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_cancel_no_pending(self, intent_service, sample_user_id):
        """Cancel with no pending should still succeed with message."""
        with patch("app.services.pending_edit_service.pending_edit_service") as mock_pending:
            mock_pending.cancel_pending.return_value = False
            
            result = await intent_service._handle_cancel_edit(
                request_id="req-123",
                user_id=sample_user_id,
                start_time=0,
            )
        
        assert result.success is True
        assert "no pending" in result.message.lower()


# ---------------------------------------------------------------------------
# CALENDAR EDIT HANDLER ROUTING TESTS
# ---------------------------------------------------------------------------

class TestHandleCalendarEdit:
    """Tests for _handle_calendar_edit routing."""
    
    @pytest.mark.asyncio
    async def test_routes_to_edit_existing_event(self, intent_service, mock_db, sample_user_id):
        """Should route EDIT_EXISTING_EVENT action correctly."""
        intent = CalendarEditIntent(
            original_text="reschedule my meeting",
            confidence=0.95,
            action=ActionType.EDIT_EXISTING_EVENT,
            search_term="meeting",
        )
        
        with patch.object(intent_service, "_handle_edit_existing_event") as mock_handler:
            mock_handler.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
            )
            
            await intent_service._handle_calendar_edit(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_to_delete_existing_event(self, intent_service, mock_db, sample_user_id):
        """Should route DELETE_EXISTING_EVENT action correctly."""
        intent = CalendarEditIntent(
            original_text="delete my meeting",
            confidence=0.95,
            action=ActionType.DELETE_EXISTING_EVENT,
            search_term="meeting",
        )
        
        with patch.object(intent_service, "_handle_delete_existing_event") as mock_handler:
            mock_handler.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
            )
            
            await intent_service._handle_calendar_edit(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_to_select_event(self, intent_service, mock_db, sample_user_id):
        """Should route SELECT_EVENT action correctly."""
        intent = CalendarEditIntent(
            original_text="the first one",
            confidence=0.90,
            action=ActionType.SELECT_EVENT,
            selection_index=1,
        )
        
        with patch.object(intent_service, "_handle_select_event") as mock_handler:
            mock_handler.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
            )
            
            await intent_service._handle_calendar_edit(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_to_confirm_edit(self, intent_service, mock_db, sample_user_id):
        """Should route CONFIRM_EDIT action correctly."""
        intent = CalendarEditIntent(
            original_text="yes",
            confidence=0.85,
            action=ActionType.CONFIRM_EDIT,
        )
        
        with patch.object(intent_service, "_handle_confirm_edit") as mock_handler:
            mock_handler.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
            )
            
            await intent_service._handle_calendar_edit(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_to_confirm_delete(self, intent_service, mock_db, sample_user_id):
        """Should route CONFIRM_DELETE action correctly."""
        intent = CalendarEditIntent(
            original_text="yes",
            confidence=0.85,
            action=ActionType.CONFIRM_DELETE,
        )
        
        with patch.object(intent_service, "_handle_confirm_delete") as mock_handler:
            mock_handler.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
            )
            
            await intent_service._handle_calendar_edit(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
            
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_routes_to_cancel_edit(self, intent_service, mock_db, sample_user_id):
        """Should route CANCEL_EDIT action correctly."""
        intent = CalendarEditIntent(
            original_text="no",
            confidence=0.85,
            action=ActionType.CANCEL_EDIT,
        )
        
        with patch.object(intent_service, "_handle_cancel_edit") as mock_handler:
            mock_handler.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
            )
            
            await intent_service._handle_calendar_edit(
                request_id="req-123",
                intent=intent,
                user_id=sample_user_id,
                start_time=0,
                db=mock_db,
            )
            
            mock_handler.assert_called_once()
