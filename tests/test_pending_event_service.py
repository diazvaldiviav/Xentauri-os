"""
Tests for the pending event service.

Sprint 3.8: Calendar Event Creation with Confirmation Flow

These tests verify:
- Pending event storage and retrieval
- TTL expiration (60 seconds)
- Field updates during confirmation flow
- Confirm and cancel operations
- Cleanup of expired events
- PendingEvent dataclass methods
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta, timezone
from uuid import uuid4

from app.services.pending_event_service import (
    PendingEvent,
    PendingEventService,
)


# ---------------------------------------------------------------------------
# PENDING EVENT DATACLASS TESTS
# ---------------------------------------------------------------------------

class TestPendingEventDataclass:
    """Tests for the PendingEvent dataclass."""
    
    def test_create_pending_event_minimal(self):
        """Should create pending event with minimal fields."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
        )
        
        assert pending.user_id == "user-123"
        assert pending.event_title == "Meeting"
        assert pending.event_date is None
        assert pending.event_time is None
        assert pending.duration_minutes == 60
        assert pending.is_all_day is False
        assert pending.location is None
        assert pending.recurrence is None
        assert pending.timezone == "UTC"
    
    def test_create_pending_event_full(self):
        """Should create pending event with all fields."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Team Meeting",
            event_date=date(2025, 1, 15),
            event_time="14:30",
            duration_minutes=90,
            is_all_day=False,
            location="Conference Room A",
            recurrence="RRULE:FREQ=WEEKLY;COUNT=4",
            timezone="America/New_York",
        )
        
        assert pending.event_title == "Team Meeting"
        assert pending.event_date == date(2025, 1, 15)
        assert pending.event_time == "14:30"
        assert pending.duration_minutes == 90
        assert pending.location == "Conference Room A"
        assert pending.recurrence == "RRULE:FREQ=WEEKLY;COUNT=4"
        assert pending.timezone == "America/New_York"
    
    def test_is_expired_false_when_fresh(self):
        """Should return False for fresh pending event."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
        )
        
        assert pending.is_expired() is False
    
    def test_is_expired_true_after_ttl(self):
        """Should return True when expires_at is in the past."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        
        assert pending.is_expired() is True
    
    def test_get_end_time_normal_event(self):
        """Should calculate end time correctly."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_time="14:30",
            duration_minutes=90,
        )
        
        # 14:30 + 90 min = 16:00
        assert pending.get_end_time() == "16:00"
    
    def test_get_end_time_crosses_midnight(self):
        """Should handle crossing midnight."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Late Night Event",
            event_time="23:00",
            duration_minutes=120,
        )
        
        # 23:00 + 120 min = 01:00 (next day)
        assert pending.get_end_time() == "01:00"
    
    def test_get_end_time_returns_none_for_all_day(self):
        """Should return None for all-day events."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Holiday",
            event_time="09:00",
            is_all_day=True,
        )
        
        assert pending.get_end_time() is None
    
    def test_get_end_time_returns_none_without_time(self):
        """Should return None when no event_time."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
        )
        
        assert pending.get_end_time() is None
    
    def test_get_start_datetime_with_date_and_time(self):
        """Should combine date and time correctly."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_date=date(2025, 1, 15),
            event_time="14:30",
        )
        
        result = pending.get_start_datetime()
        
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
    
    def test_get_start_datetime_all_day(self):
        """Should return start of day for all-day events."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Holiday",
            event_date=date(2025, 1, 15),
            is_all_day=True,
        )
        
        result = pending.get_start_datetime()
        
        assert result.hour == 0
        assert result.minute == 0
    
    def test_get_start_datetime_returns_none_without_date(self):
        """Should return None when no event_date."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_time="14:30",
        )
        
        assert pending.get_start_datetime() is None
    
    def test_get_end_datetime_normal_event(self):
        """Should calculate end datetime correctly."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_date=date(2025, 1, 15),
            event_time="14:30",
            duration_minutes=90,
        )
        
        result = pending.get_end_datetime()
        
        assert result.hour == 16
        assert result.minute == 0
    
    def test_get_end_datetime_all_day(self):
        """Should return next day for all-day events."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Holiday",
            event_date=date(2025, 1, 15),
            is_all_day=True,
        )
        
        result = pending.get_end_datetime()
        
        assert result.day == 16  # Next day
    
    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        pending = PendingEvent(
            user_id="user-123",
            event_title="Meeting",
            event_date=date(2025, 1, 15),
            event_time="14:30",
        )
        
        result = pending.to_dict()
        
        assert result["user_id"] == "user-123"
        assert result["event_title"] == "Meeting"
        assert result["event_date"] == "2025-01-15"
        assert result["event_time"] == "14:30"
        assert "is_expired" in result


# ---------------------------------------------------------------------------
# PENDING EVENT SERVICE TESTS - STORAGE
# ---------------------------------------------------------------------------

class TestPendingEventServiceStorage:
    """Tests for storing pending events."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service for each test."""
        service = PendingEventService()
        yield service
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_store_pending_basic(self, service):
        """Should store a pending event."""
        user_id = str(uuid4())
        
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        assert pending.user_id == user_id
        assert pending.event_title == "Meeting"
        assert not pending.is_expired()
    
    @pytest.mark.asyncio
    async def test_store_pending_with_all_fields(self, service):
        """Should store all event details."""
        user_id = str(uuid4())
        
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Team Meeting",
            event_date=date(2025, 1, 15),
            event_time="14:30",
            duration_minutes=90,
            is_all_day=False,
            location="Conference Room A",
            recurrence="RRULE:FREQ=WEEKLY",
            timezone="America/New_York",
            original_text="schedule team meeting for tomorrow at 2:30 pm",
        )
        
        assert pending.event_title == "Team Meeting"
        assert pending.event_date == date(2025, 1, 15)
        assert pending.event_time == "14:30"
        assert pending.duration_minutes == 90
        assert pending.location == "Conference Room A"
        assert pending.recurrence == "RRULE:FREQ=WEEKLY"
        assert pending.timezone == "America/New_York"
        assert pending.original_text == "schedule team meeting for tomorrow at 2:30 pm"
    
    @pytest.mark.asyncio
    async def test_store_pending_sets_expiration(self, service):
        """Should set 120-second TTL (Sprint 3.9.1)."""
        user_id = str(uuid4())
        
        before = datetime.now(timezone.utc)
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        after = datetime.now(timezone.utc)
        
        # Expiration should be ~120 seconds in the future (Sprint 3.9.1: increased from 60s)
        expected_min = before + timedelta(seconds=120)
        expected_max = after + timedelta(seconds=120)
        
        assert expected_min <= pending.expires_at <= expected_max
    
    @pytest.mark.asyncio
    async def test_store_pending_overwrites_existing(self, service):
        """Should overwrite existing pending event for same user."""
        user_id = str(uuid4())
        
        # Store first event
        await service.store_pending(
            user_id=user_id,
            event_title="First Meeting",
        )
        
        # Store second event (should overwrite)
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Second Meeting",
        )
        
        # Should only have the second event
        retrieved = service.get_pending(user_id)
        assert retrieved.event_title == "Second Meeting"
    
    @pytest.mark.asyncio
    async def test_store_pending_multiple_users(self, service):
        """Should store separate events for different users."""
        user1 = str(uuid4())
        user2 = str(uuid4())
        
        await service.store_pending(user_id=user1, event_title="User 1 Meeting")
        await service.store_pending(user_id=user2, event_title="User 2 Meeting")
        
        pending1 = service.get_pending(user1)
        pending2 = service.get_pending(user2)
        
        assert pending1.event_title == "User 1 Meeting"
        assert pending2.event_title == "User 2 Meeting"


# ---------------------------------------------------------------------------
# PENDING EVENT SERVICE TESTS - RETRIEVAL
# ---------------------------------------------------------------------------

class TestPendingEventServiceRetrieval:
    """Tests for retrieving pending events."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service for each test."""
        service = PendingEventService()
        yield service
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_get_pending_exists(self, service):
        """Should return pending event when it exists."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        pending = service.get_pending(user_id)
        
        assert pending is not None
        assert pending.event_title == "Meeting"
    
    def test_get_pending_not_found(self, service):
        """Should return None when no pending event."""
        user_id = str(uuid4())
        
        pending = service.get_pending(user_id)
        
        assert pending is None
    
    @pytest.mark.asyncio
    async def test_get_pending_expired(self, service):
        """Should return None for expired event."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        # Manually expire
        service._pending[user_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        pending = service.get_pending(user_id)
        
        assert pending is None
    
    @pytest.mark.asyncio
    async def test_has_pending_true(self, service):
        """Should return True when pending event exists."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        assert service.has_pending(user_id) is True
    
    def test_has_pending_false(self, service):
        """Should return False when no pending event."""
        user_id = str(uuid4())
        
        assert service.has_pending(user_id) is False
    
    @pytest.mark.asyncio
    async def test_is_expired_false_when_exists(self, service):
        """Should return False for valid pending event."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        assert service.is_expired(user_id) is False
    
    def test_is_expired_true_when_not_found(self, service):
        """Should return True when no pending event."""
        user_id = str(uuid4())
        
        assert service.is_expired(user_id) is True


# ---------------------------------------------------------------------------
# PENDING EVENT SERVICE TESTS - UPDATES
# ---------------------------------------------------------------------------

class TestPendingEventServiceUpdates:
    """Tests for updating pending event fields."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service for each test."""
        service = PendingEventService()
        yield service
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_update_pending_title(self, service):
        """Should update event title."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Old Title",
        )
        
        updated = service.update_pending(user_id, "event_title", "New Title")
        
        assert updated.event_title == "New Title"
    
    @pytest.mark.asyncio
    async def test_update_pending_time(self, service):
        """Should update event time."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
            event_time="14:00",
        )
        
        updated = service.update_pending(user_id, "event_time", "15:00")
        
        assert updated.event_time == "15:00"
    
    @pytest.mark.asyncio
    async def test_update_pending_date(self, service):
        """Should update event date."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
            event_date=date(2025, 1, 15),
        )
        
        updated = service.update_pending(user_id, "event_date", date(2025, 1, 20))
        
        assert updated.event_date == date(2025, 1, 20)
    
    @pytest.mark.asyncio
    async def test_update_pending_duration(self, service):
        """Should update duration."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        updated = service.update_pending(user_id, "duration_minutes", 120)
        
        assert updated.duration_minutes == 120
    
    @pytest.mark.asyncio
    async def test_update_pending_location(self, service):
        """Should update location."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        updated = service.update_pending(user_id, "location", "Room 101")
        
        assert updated.location == "Room 101"
    
    @pytest.mark.asyncio
    async def test_update_pending_not_found(self, service):
        """Should return None when no pending event."""
        user_id = str(uuid4())
        
        updated = service.update_pending(user_id, "event_title", "New Title")
        
        assert updated is None
    
    @pytest.mark.asyncio
    async def test_update_pending_invalid_field(self, service):
        """Should raise ValueError for non-editable field."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        with pytest.raises(ValueError) as exc_info:
            service.update_pending(user_id, "user_id", "new-user")
        
        assert "not editable" in str(exc_info.value)


# ---------------------------------------------------------------------------
# PENDING EVENT SERVICE TESTS - CONFIRM/CANCEL
# ---------------------------------------------------------------------------

class TestPendingEventServiceConfirmCancel:
    """Tests for confirm and cancel operations."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service for each test."""
        service = PendingEventService()
        yield service
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_confirm_pending_success(self, service):
        """Should return event and remove from storage."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        confirmed = await service.confirm_pending(user_id)
        
        assert confirmed is not None
        assert confirmed.event_title == "Meeting"
        
        # Should no longer exist
        assert service.get_pending(user_id) is None
    
    @pytest.mark.asyncio
    async def test_confirm_pending_not_found(self, service):
        """Should return None when no pending event."""
        user_id = str(uuid4())
        
        confirmed = await service.confirm_pending(user_id)
        
        assert confirmed is None
    
    @pytest.mark.asyncio
    async def test_confirm_pending_expired(self, service):
        """Should return None for expired event."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        # Manually expire
        service._pending[user_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        confirmed = await service.confirm_pending(user_id)
        
        assert confirmed is None
    
    @pytest.mark.asyncio
    async def test_cancel_pending_success(self, service):
        """Should remove pending event."""
        user_id = str(uuid4())
        
        await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
        )
        
        result = service.cancel_pending(user_id)
        
        assert result is True
        assert service.get_pending(user_id) is None
    
    def test_cancel_pending_not_found(self, service):
        """Should return False when no pending event."""
        user_id = str(uuid4())
        
        result = service.cancel_pending(user_id)
        
        assert result is False


# ---------------------------------------------------------------------------
# PENDING EVENT SERVICE TESTS - CLEANUP
# ---------------------------------------------------------------------------

class TestPendingEventServiceCleanup:
    """Tests for cleanup operations."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service for each test."""
        service = PendingEventService()
        yield service
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_entries(self, service):
        """Should remove expired entries."""
        user1 = str(uuid4())
        user2 = str(uuid4())
        
        await service.store_pending(user_id=user1, event_title="Meeting 1")
        await service.store_pending(user_id=user2, event_title="Meeting 2")
        
        # Expire user1's event
        service._pending[user1].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        removed = service.cleanup_expired()
        
        assert removed == 1
        assert service.get_pending(user1) is None
        assert service.get_pending(user2) is not None
    
    def test_cleanup_expired_no_expired(self, service):
        """Should return 0 when no expired entries."""
        removed = service.cleanup_expired()
        
        assert removed == 0
    
    @pytest.mark.asyncio
    async def test_get_pending_count(self, service):
        """Should return count of non-expired events."""
        user1 = str(uuid4())
        user2 = str(uuid4())
        
        await service.store_pending(user_id=user1, event_title="Meeting 1")
        await service.store_pending(user_id=user2, event_title="Meeting 2")
        
        assert service.get_pending_count() == 2
    
    @pytest.mark.asyncio
    async def test_clear_all(self, service):
        """Should clear all pending events."""
        await service.store_pending(user_id=str(uuid4()), event_title="Meeting 1")
        await service.store_pending(user_id=str(uuid4()), event_title="Meeting 2")
        
        service.clear_all()
        
        assert service.get_pending_count() == 0


# ---------------------------------------------------------------------------
# PENDING EVENT SERVICE TESTS - CLEANUP LOOP
# ---------------------------------------------------------------------------

class TestPendingEventServiceCleanupLoop:
    """Tests for the background cleanup loop."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh service for each test."""
        service = PendingEventService()
        yield service
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_start_cleanup_loop(self, service):
        """Should start background cleanup task."""
        await service.start_cleanup_loop(interval_seconds=1)
        
        assert service._cleanup_task is not None
        
        await service.stop_cleanup_loop()
    
    @pytest.mark.asyncio
    async def test_stop_cleanup_loop(self, service):
        """Should stop background cleanup task."""
        await service.start_cleanup_loop(interval_seconds=1)
        await service.stop_cleanup_loop()
        
        assert service._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_cleanup_loop_cleans_expired(self, service):
        """Should cleanup expired entries periodically."""
        user_id = str(uuid4())
        
        await service.store_pending(user_id=user_id, event_title="Meeting")
        
        # Expire the event
        service._pending[user_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # Start loop with short interval
        await service.start_cleanup_loop(interval_seconds=0.1)
        
        # Wait for cleanup to run
        await asyncio.sleep(0.2)
        
        # Event should be cleaned up
        assert user_id not in service._pending
        
        await service.stop_cleanup_loop()
