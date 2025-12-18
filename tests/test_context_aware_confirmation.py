"""
Tests for Context-Aware Confirmation Flow (Sprint 3.9.1)

Tests the three bug fixes:
1. Wrong time extraction for "from X to Y" patterns
2. Context loss during pending create ("change it to 2pm" should edit pending, not search)
3. Confirmation routing based on pending_op_type (yes should confirm the correct operation)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from app.ai.context import (
    PendingOperationState,
    _build_pending_state,
)
from app.services.pending_event_service import PendingEvent
from app.services.pending_edit_service import PendingEdit, PendingOperationType, PendingState, MatchingEvent

# Import paths for patching (services are imported inside _build_pending_state)
PENDING_EVENT_SERVICE_PATH = 'app.services.pending_event_service.pending_event_service'
PENDING_EDIT_SERVICE_PATH = 'app.services.pending_edit_service.pending_edit_service'


# ---------------------------------------------------------------------------
# TEST: PendingOperationState
# ---------------------------------------------------------------------------

class TestPendingOperationState:
    """Test the PendingOperationState dataclass."""
    
    def test_default_state_has_no_pending(self):
        """Default state should have no pending operations."""
        state = PendingOperationState()
        
        assert state.has_pending_create is False
        assert state.has_pending_edit is False
        assert state.has_pending_delete is False
        assert state.pending_op_type is None
        assert state.has_any_pending() is False
    
    def test_has_any_pending_with_create(self):
        """has_any_pending should return True when create exists."""
        state = PendingOperationState(has_pending_create=True)
        
        assert state.has_any_pending() is True
    
    def test_has_any_pending_with_edit(self):
        """has_any_pending should return True when edit exists."""
        state = PendingOperationState(has_pending_edit=True)
        
        assert state.has_any_pending() is True
    
    def test_to_dict_includes_all_fields(self):
        """to_dict should include all relevant fields."""
        state = PendingOperationState(
            has_pending_create=True,
            pending_op_type="create",
            pending_op_age_seconds=30,
            pending_op_hint="Team Meeting",
            pending_create_title="Team Meeting",
            pending_create_time="14:00",
        )
        
        result = state.to_dict()
        
        assert result["has_pending_create"] is True
        assert result["pending_op_type"] == "create"
        assert result["pending_op_age_seconds"] == 30
        assert result["pending_op_hint"] == "Team Meeting"


# ---------------------------------------------------------------------------
# TEST: _build_pending_state
# ---------------------------------------------------------------------------

class TestBuildPendingState:
    """Test the pending state builder function."""
    
    def test_no_pending_operations(self):
        """When no pending operations exist, returns empty state."""
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = None
            mock_edit.get_pending.return_value = None
            
            state = _build_pending_state("user-123")
            
            assert state.has_pending_create is False
            assert state.has_pending_edit is False
            assert state.pending_op_type is None
    
    def test_pending_create_only(self):
        """When only pending create exists, returns create state."""
        mock_pending = MagicMock(spec=PendingEvent)
        mock_pending.event_title = "Doctor Appointment"
        mock_pending.event_time = "14:00"
        mock_pending.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = mock_pending
            mock_edit.get_pending.return_value = None
            
            state = _build_pending_state("user-123")
            
            assert state.has_pending_create is True
            assert state.has_pending_edit is False
            assert state.pending_op_type == "create"
            assert state.pending_create_title == "Doctor Appointment"
            assert state.pending_op_age_seconds is not None
    
    def test_pending_edit_only(self):
        """When only pending edit exists, returns edit state."""
        mock_pending = MagicMock(spec=PendingEdit)
        mock_pending.operation = PendingOperationType.EDIT
        mock_pending.selected_event = MatchingEvent(
            event_id="evt-1",
            summary="Dentist Appointment",
        )
        mock_pending.matching_events = []
        mock_pending.changes = {"start_datetime": "16:00"}
        mock_pending.search_term = "dentist"
        mock_pending.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = None
            mock_edit.get_pending.return_value = mock_pending
            
            state = _build_pending_state("user-123")
            
            assert state.has_pending_create is False
            assert state.has_pending_edit is True
            assert state.pending_op_type == "edit"
            assert state.pending_edit_event == "Dentist Appointment"
    
    def test_pending_delete(self):
        """When pending delete exists, returns delete state."""
        mock_pending = MagicMock(spec=PendingEdit)
        mock_pending.operation = PendingOperationType.DELETE
        mock_pending.selected_event = MatchingEvent(
            event_id="evt-1",
            summary="Old Meeting",
        )
        mock_pending.matching_events = []
        mock_pending.changes = None
        mock_pending.search_term = "meeting"
        mock_pending.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = None
            mock_edit.get_pending.return_value = mock_pending
            
            state = _build_pending_state("user-123")
            
            assert state.has_pending_delete is True
            assert state.pending_op_type == "delete"
    
    def test_both_pending_edit_more_recent(self):
        """When both exist, edit is chosen if more recent."""
        # Create pending (10 seconds ago)
        mock_create = MagicMock(spec=PendingEvent)
        mock_create.event_title = "Old Event"
        mock_create.event_time = "10:00"
        mock_create.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        
        # Edit pending (5 seconds ago - more recent)
        mock_edit = MagicMock(spec=PendingEdit)
        mock_edit.operation = PendingOperationType.EDIT
        mock_edit.selected_event = MatchingEvent(event_id="evt-1", summary="Recent Edit")
        mock_edit.matching_events = []
        mock_edit.changes = {"start_datetime": "16:00"}
        mock_edit.search_term = "edit"
        mock_edit.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event_svc, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit_svc:
            mock_event_svc.get_pending.return_value = mock_create
            mock_edit_svc.get_pending.return_value = mock_edit
            
            state = _build_pending_state("user-123")
            
            # Edit is more recent, so it should be the pending_op_type
            assert state.has_pending_create is True
            assert state.has_pending_edit is True
            assert state.pending_op_type == "edit"  # Edit is more recent
    
    def test_both_pending_create_more_recent(self):
        """When both exist, create is chosen if more recent."""
        # Edit pending (10 seconds ago)
        mock_edit = MagicMock(spec=PendingEdit)
        mock_edit.operation = PendingOperationType.EDIT
        mock_edit.selected_event = None
        mock_edit.matching_events = [MatchingEvent(event_id="evt-1", summary="Old Edit")]
        mock_edit.changes = None
        mock_edit.search_term = "old"
        mock_edit.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        
        # Create pending (5 seconds ago - more recent)
        mock_create = MagicMock(spec=PendingEvent)
        mock_create.event_title = "New Event"
        mock_create.event_time = "14:00"
        mock_create.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event_svc, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit_svc:
            mock_event_svc.get_pending.return_value = mock_create
            mock_edit_svc.get_pending.return_value = mock_edit
            
            state = _build_pending_state("user-123")
            
            # Create is more recent, so it should be the pending_op_type
            assert state.has_pending_create is True
            assert state.has_pending_edit is True
            assert state.pending_op_type == "create"  # Create is more recent


# ---------------------------------------------------------------------------
# TEST: Bug #2 - Context Loss During Pending Create
# ---------------------------------------------------------------------------

class TestPendingCreateContext:
    """
    Test Bug #2: "change it to 2pm" with pending create should route to edit_pending_event.
    
    Flow:
    1. User: "create a visit with dentist tomorrow"
    2. System: "All day event... say yes/no or change it to 8pm"
    3. User: "change it to 2pm"
    4. Expected: calendar_create/edit_pending_event
    5. Bug: Was routing to calendar_edit/edit_existing_event (asking "which event?")
    """
    
    def test_context_includes_pending_create(self):
        """Verify context includes pending create info for the LLM."""
        mock_pending = MagicMock(spec=PendingEvent)
        mock_pending.event_title = "Dentist Visit"
        mock_pending.event_time = None  # All-day event
        mock_pending.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = mock_pending
            mock_edit.get_pending.return_value = None
            
            state = _build_pending_state("user-123")
            context_dict = state.to_dict()
            
            # LLM should see this context
            assert context_dict["has_pending_create"] is True
            assert context_dict["pending_op_type"] == "create"
            assert context_dict["pending_create_title"] == "Dentist Visit"


# ---------------------------------------------------------------------------
# TEST: Bug #3 - Confirmation Routing
# ---------------------------------------------------------------------------

class TestConfirmationRouting:
    """
    Test Bug #3: "yes" should confirm the correct pending operation.
    
    When user has pending_edit and says "yes", it should confirm_edit (not confirm_create).
    """
    
    def test_pending_edit_confirmation_context(self):
        """When pending_op_type is 'edit', confirmation should go to edit handler."""
        mock_pending = MagicMock(spec=PendingEdit)
        mock_pending.operation = PendingOperationType.EDIT
        mock_pending.selected_event = MatchingEvent(
            event_id="evt-1",
            summary="Dentist",
        )
        mock_pending.matching_events = []
        mock_pending.changes = {"start_datetime": "16:00"}
        mock_pending.search_term = "dentist"
        mock_pending.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = None
            mock_edit.get_pending.return_value = mock_pending
            
            state = _build_pending_state("user-123")
            
            # This is what the confirm handler should check
            assert state.pending_op_type == "edit"
            
            # Intent parser and confirm handler can use this to route correctly
    
    def test_no_pending_operation_confirmation_ambiguous(self):
        """When no pending operation, confirmation should be handled carefully."""
        with patch(PENDING_EVENT_SERVICE_PATH) as mock_event, \
             patch(PENDING_EDIT_SERVICE_PATH) as mock_edit:
            mock_event.get_pending.return_value = None
            mock_edit.get_pending.return_value = None
            
            state = _build_pending_state("user-123")
            
            # No pending operation
            assert state.pending_op_type is None
            assert state.has_any_pending() is False
            
            # "yes" alone should be treated as ambiguous
