"""
Tests for Pending Edit Service (Sprint 3.9).

Tests the pending edit/delete service that manages the confirmation flow
for editing and deleting calendar events.
"""

import pytest
from datetime import datetime, timedelta, timezone as tz
from unittest.mock import AsyncMock, patch

from app.services.pending_edit_service import (
    PendingEditService,
    PendingEdit,
    MatchingEvent,
    PendingOperationType,
    PendingState,
    pending_edit_service,
)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """Create a fresh PendingEditService for each test."""
    svc = PendingEditService()
    yield svc
    svc.clear_all()


@pytest.fixture
def sample_events():
    """Sample matching events for testing."""
    return [
        {
            "id": "event-1",
            "summary": "Team Meeting",
            "start": {"dateTime": "2025-12-16T10:00:00-05:00"},
            "end": {"dateTime": "2025-12-16T11:00:00-05:00"},
            "location": "Room A",
        },
        {
            "id": "event-2",
            "summary": "Dentist Appointment",
            "start": {"dateTime": "2025-12-16T14:00:00-05:00"},
            "end": {"dateTime": "2025-12-16T15:00:00-05:00"},
        },
        {
            "id": "event-3",
            "summary": "Birthday Party",
            "start": {"date": "2025-12-20"},
            "end": {"date": "2025-12-21"},
        },
    ]


# ---------------------------------------------------------------------------
# STORE PENDING EDIT TESTS
# ---------------------------------------------------------------------------

class TestStorePendingEdit:
    """Tests for store_pending_edit method."""
    
    @pytest.mark.asyncio
    async def test_store_single_match_auto_selects(self, service, sample_events):
        """Single match should auto-select and set awaiting_confirmation."""
        single_event = [sample_events[0]]
        
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=single_event,
            search_term="meeting",
            changes={"start_datetime": "11:00"},
        )
        
        assert pending.user_id == "user-123"
        assert pending.operation == PendingOperationType.EDIT
        assert pending.state == PendingState.AWAITING_CONFIRMATION
        assert pending.selected_event is not None
        assert pending.selected_event.event_id == "event-1"
        assert pending.selected_event.summary == "Team Meeting"
        assert pending.selected_index == 1
        assert pending.changes == {"start_datetime": "11:00"}
    
    @pytest.mark.asyncio
    async def test_store_multiple_matches_awaits_selection(self, service, sample_events):
        """Multiple matches should await selection."""
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=sample_events[:2],
            search_term="appointment",
        )
        
        assert pending.state == PendingState.AWAITING_SELECTION
        assert pending.selected_event is None
        assert pending.selected_index is None
        assert len(pending.matching_events) == 2
        assert pending.needs_selection() is True
    
    @pytest.mark.asyncio
    async def test_store_no_matches_awaits_selection(self, service):
        """No matches should still be stored (empty state)."""
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[],
            search_term="nonexistent",
        )
        
        assert pending.state == PendingState.AWAITING_SELECTION
        assert len(pending.matching_events) == 0
    
    @pytest.mark.asyncio
    async def test_store_overwrites_existing(self, service, sample_events):
        """New store should overwrite existing pending for same user."""
        # Store first
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
            search_term="meeting",
        )
        
        # Store second (should overwrite)
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=[sample_events[1]],
            search_term="dentist",
        )
        
        assert pending.operation == PendingOperationType.DELETE
        assert pending.search_term == "dentist"
        assert service.get_pending_count() == 1
    
    @pytest.mark.asyncio
    async def test_store_sets_expiration(self, service, sample_events):
        """Store should set expiration 60 seconds in future."""
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        
        now = datetime.now(tz.utc)
        assert pending.expires_at > now
        assert pending.expires_at < now + timedelta(seconds=65)
    
    @pytest.mark.asyncio
    async def test_store_detects_all_day_events(self, service, sample_events):
        """Should correctly detect all-day events."""
        # sample_events[2] is an all-day event
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[2]],
            search_term="birthday",
        )
        
        assert pending.selected_event.is_all_day is True


# ---------------------------------------------------------------------------
# GET PENDING TESTS
# ---------------------------------------------------------------------------

class TestGetPending:
    """Tests for get_pending method."""
    
    @pytest.mark.asyncio
    async def test_get_existing_pending(self, service, sample_events):
        """Should return pending if exists and not expired."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        
        pending = service.get_pending("user-123")
        
        assert pending is not None
        assert pending.user_id == "user-123"
    
    def test_get_nonexistent_pending(self, service):
        """Should return None for nonexistent user."""
        pending = service.get_pending("user-nonexistent")
        assert pending is None
    
    @pytest.mark.asyncio
    async def test_get_expired_pending_returns_none(self, service, sample_events):
        """Should return None and cleanup expired pending."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        
        # Manually expire it
        service._pending["user-123"].expires_at = datetime.now(tz.utc) - timedelta(seconds=1)
        
        pending = service.get_pending("user-123")
        
        assert pending is None
        assert "user-123" not in service._pending


# ---------------------------------------------------------------------------
# SELECT EVENT TESTS
# ---------------------------------------------------------------------------

class TestSelectEvent:
    """Tests for select_event method."""
    
    @pytest.mark.asyncio
    async def test_select_valid_index(self, service, sample_events):
        """Should select event and transition to awaiting_confirmation."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=sample_events[:2],
            search_term="event",
        )
        
        updated = service.select_event("user-123", index=2)
        
        assert updated is not None
        assert updated.selected_index == 2
        assert updated.selected_event.event_id == "event-2"
        assert updated.selected_event.summary == "Dentist Appointment"
        assert updated.state == PendingState.AWAITING_CONFIRMATION
    
    @pytest.mark.asyncio
    async def test_select_first_event(self, service, sample_events):
        """Should select first event correctly."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=sample_events,
        )
        
        updated = service.select_event("user-123", index=1)
        
        assert updated.selected_index == 1
        assert updated.selected_event.event_id == "event-1"
    
    @pytest.mark.asyncio
    async def test_select_invalid_index_zero(self, service, sample_events):
        """Should return None for index 0 (1-based indexing)."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=sample_events,
        )
        
        result = service.select_event("user-123", index=0)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_select_invalid_index_too_high(self, service, sample_events):
        """Should return None for index beyond list length."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=sample_events[:2],
        )
        
        result = service.select_event("user-123", index=5)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_select_nonexistent_user(self, service):
        """Should return None for nonexistent user."""
        result = service.select_event("nonexistent", index=1)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_select_already_confirmed_returns_none(self, service, sample_events):
        """Cannot select on already confirmed pending."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],  # Single match - auto-selected
        )
        
        # Already in AWAITING_CONFIRMATION state
        result = service.select_event("user-123", index=1)
        assert result is None


# ---------------------------------------------------------------------------
# CONFIRM PENDING TESTS
# ---------------------------------------------------------------------------

class TestConfirmPending:
    """Tests for confirm_pending method."""
    
    @pytest.mark.asyncio
    async def test_confirm_ready_pending(self, service, sample_events):
        """Should confirm and remove pending."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
            changes={"summary": "Updated Meeting"},
        )
        
        confirmed = await service.confirm_pending("user-123")
        
        assert confirmed is not None
        assert confirmed.state == PendingState.CONFIRMED
        assert confirmed.selected_event.event_id == "event-1"
        assert confirmed.changes == {"summary": "Updated Meeting"}
        
        # Should be removed from pending
        assert service.get_pending("user-123") is None
    
    @pytest.mark.asyncio
    async def test_confirm_not_ready_returns_none(self, service, sample_events):
        """Cannot confirm if not in awaiting_confirmation state."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=sample_events,  # Multiple - needs selection
        )
        
        result = await service.confirm_pending("user-123")
        assert result is None
        
        # Should still be pending
        assert service.get_pending("user-123") is not None
    
    @pytest.mark.asyncio
    async def test_confirm_nonexistent_returns_none(self, service):
        """Should return None for nonexistent pending."""
        result = await service.confirm_pending("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# CANCEL PENDING TESTS
# ---------------------------------------------------------------------------

class TestCancelPending:
    """Tests for cancel_pending method."""
    
    @pytest.mark.asyncio
    async def test_cancel_existing_pending(self, service, sample_events):
        """Should cancel and remove pending."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=[sample_events[0]],
        )
        
        result = service.cancel_pending("user-123")
        
        assert result is True
        assert service.get_pending("user-123") is None
    
    def test_cancel_nonexistent_returns_false(self, service):
        """Should return False for nonexistent pending."""
        result = service.cancel_pending("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# UPDATE CHANGES TESTS
# ---------------------------------------------------------------------------

class TestUpdateChanges:
    """Tests for update_changes method."""
    
    @pytest.mark.asyncio
    async def test_update_changes(self, service, sample_events):
        """Should merge new changes with existing."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
            changes={"start_datetime": "11:00"},
        )
        
        updated = service.update_changes("user-123", {"location": "Room B"})
        
        assert updated is not None
        assert updated.changes == {
            "start_datetime": "11:00",
            "location": "Room B",
        }
    
    @pytest.mark.asyncio
    async def test_update_changes_on_delete_returns_none(self, service, sample_events):
        """Should return None for delete operation (no changes allowed)."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=[sample_events[0]],
        )
        
        result = service.update_changes("user-123", {"location": "Room B"})
        assert result is None


# ---------------------------------------------------------------------------
# HELPER METHODS TESTS
# ---------------------------------------------------------------------------

class TestHelperMethods:
    """Tests for helper methods."""
    
    @pytest.mark.asyncio
    async def test_has_pending(self, service, sample_events):
        """Should return True if has non-expired pending."""
        assert service.has_pending("user-123") is False
        
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        
        assert service.has_pending("user-123") is True
    
    @pytest.mark.asyncio
    async def test_has_pending_edit(self, service, sample_events):
        """Should distinguish edit vs delete."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        
        assert service.has_pending_edit("user-123") is True
        assert service.has_pending_delete("user-123") is False
    
    @pytest.mark.asyncio
    async def test_has_pending_delete(self, service, sample_events):
        """Should distinguish delete vs edit."""
        await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=[sample_events[0]],
        )
        
        assert service.has_pending_delete("user-123") is True
        assert service.has_pending_edit("user-123") is False
    
    @pytest.mark.asyncio
    async def test_get_pending_count(self, service, sample_events):
        """Should return count of non-expired pending."""
        assert service.get_pending_count() == 0
        
        await service.store_pending_edit(
            user_id="user-1",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        await service.store_pending_edit(
            user_id="user-2",
            operation="delete",
            matching_events=[sample_events[1]],
        )
        
        assert service.get_pending_count() == 2


# ---------------------------------------------------------------------------
# TEXT GENERATION TESTS
# ---------------------------------------------------------------------------

class TestTextGeneration:
    """Tests for text generation methods on PendingEdit."""
    
    @pytest.mark.asyncio
    async def test_get_event_options_text(self, service, sample_events):
        """Should generate numbered options list."""
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=sample_events[:2],
        )
        
        options_text = pending.get_event_options_text()
        
        assert "1." in options_text
        assert "2." in options_text
        assert "Team Meeting" in options_text
        assert "Dentist Appointment" in options_text
    
    @pytest.mark.asyncio
    async def test_get_confirmation_text_delete(self, service, sample_events):
        """Should generate delete confirmation."""
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="delete",
            matching_events=[sample_events[0]],
        )
        
        confirmation = pending.get_confirmation_text()
        
        assert "Delete" in confirmation
        assert "Team Meeting" in confirmation
        assert "cannot be undone" in confirmation
    
    @pytest.mark.asyncio
    async def test_get_confirmation_text_edit_with_changes(self, service, sample_events):
        """Should describe the changes in confirmation."""
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[sample_events[0]],
            changes={"location": "Room B"},
        )
        
        confirmation = pending.get_confirmation_text()
        
        assert "Update" in confirmation
        assert "Team Meeting" in confirmation
        assert "location" in confirmation.lower()
        assert "Room B" in confirmation


# ---------------------------------------------------------------------------
# CLEANUP TESTS
# ---------------------------------------------------------------------------

class TestCleanup:
    """Tests for cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, service, sample_events):
        """Should remove expired entries."""
        await service.store_pending_edit(
            user_id="user-1",
            operation="edit",
            matching_events=[sample_events[0]],
        )
        await service.store_pending_edit(
            user_id="user-2",
            operation="delete",
            matching_events=[sample_events[1]],
        )
        
        # Expire user-1
        service._pending["user-1"].expires_at = datetime.now(tz.utc) - timedelta(seconds=1)
        
        removed = service.cleanup_expired()
        
        assert removed == 1
        assert service.get_pending("user-1") is None
        assert service.get_pending("user-2") is not None
    
    def test_clear_all(self, service):
        """Should clear all pending."""
        service._pending["user-1"] = "dummy"
        service._pending["user-2"] = "dummy"
        
        service.clear_all()
        
        assert len(service._pending) == 0


# ---------------------------------------------------------------------------
# SINGLETON TESTS
# ---------------------------------------------------------------------------

class TestSingleton:
    """Tests for singleton instance."""
    
    def test_singleton_exists(self):
        """Should have a singleton instance available."""
        assert pending_edit_service is not None
        assert isinstance(pending_edit_service, PendingEditService)
