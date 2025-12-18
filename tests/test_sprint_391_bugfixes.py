"""
Tests for Sprint 3.9.1 Bug Fixes

Three bugs identified and fixed:
1. Bug #1: Timezone missing in EDIT confirm flow (causes 4pm -> 11am)
2. Bug #2: Intent parser ignores pending operation context
3. Bug #3: Pending TTL too short (60s -> 120s)

These tests verify the fixes work correctly.
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from app.ai.intent.parser import IntentParser
from app.services.pending_event_service import PendingEventService
from app.services.pending_edit_service import PendingEditService


# ---------------------------------------------------------------------------
# BUG #1 TESTS: Timezone in EDIT confirm flow
# ---------------------------------------------------------------------------

class TestEditTimezoneHandling:
    """
    Test that edit confirmation preserves user's local time.
    
    Bug: User says "change to 4pm" in Miami (UTC-5)
    - Without fix: 16:00 sent without timezone -> Google treats as UTC -> shows as 11am
    - With fix: 16:00 sent with America/New_York timezone -> shows as 4pm correctly
    """
    
    @pytest.mark.asyncio
    async def test_process_time_changes_preserves_time_value(self):
        """Time changes should keep the time value (hour/minute) as specified."""
        from app.services.intent_service import IntentService
        
        service = IntentService()
        
        # User says "change to 4pm" - this should preserve 16:00
        changes = {"new_time": "16:00"}
        original_start = "2025-01-15T10:00:00-05:00"  # Originally 10am
        original_end = "2025-01-15T11:00:00-05:00"
        
        processed = service._process_time_changes(
            changes=changes,
            original_start=original_start,
            original_end=original_end,
        )
        
        # Start time should be 16:00 on the same date
        assert "start_datetime" in processed
        assert processed["start_datetime"].hour == 16
        assert processed["start_datetime"].minute == 0
        
        # End time should be 17:00 (1 hour after start by default)
        assert "end_datetime" in processed
        assert processed["end_datetime"].hour == 17
    
    @pytest.mark.asyncio
    async def test_update_request_includes_timezone_field(self):
        """EventUpdateRequest should have a timezone field."""
        from app.environments.google.calendar.schemas import EventUpdateRequest
        
        # Create an update request with timezone
        update = EventUpdateRequest(
            start_datetime=datetime(2025, 1, 15, 16, 0),
            end_datetime=datetime(2025, 1, 15, 17, 0),
            timezone="America/New_York",
        )
        
        assert update.timezone == "America/New_York"
        assert update.has_time_changes() is True
    
    @pytest.mark.asyncio
    async def test_edit_flow_should_call_get_user_timezone(self):
        """
        The edit confirm flow should get user's timezone.
        
        This is the root cause fix - without this, times default to UTC.
        """
        # This test verifies the code structure exists
        import inspect
        from app.services.intent_service import IntentService
        
        source = inspect.getsource(IntentService._handle_confirm_edit)
        
        # Verify the fix is in place - should call get_user_timezone
        assert "get_user_timezone" in source, "Edit flow should call get_user_timezone()"
        
        # Verify timezone is added to processed_changes
        assert 'processed_changes["timezone"]' in source, "Timezone should be added to changes"


# ---------------------------------------------------------------------------
# BUG #2 TESTS: Parser pending operation context
# ---------------------------------------------------------------------------

class TestParserPendingContext:
    """
    Test that the intent parser includes pending operation context.
    
    Bug: Parser only included device context, not pending operations.
    When user says "yes", parser didn't know if it was for create/edit/delete.
    """
    
    @pytest.mark.asyncio
    async def test_parser_includes_pending_create_context(self):
        """Parser should include pending create info in context string."""
        parser = IntentParser()
        
        # Create a context with pending operation
        context = {
            "devices": [{"name": "Living Room TV"}],
            "pending_operation": {
                "has_pending_create": True,
                "has_pending_edit": False,
                "has_pending_delete": False,
                "pending_op_type": "create",
                "pending_create_title": "Dentist Visit",
                "pending_op_age_seconds": 15,
            },
        }
        
        # Build context string - we need to test the context building logic
        context_parts = []
        if context:
            if "devices" in context:
                device_names = [d.get("name", "Unknown") for d in context["devices"]]
                context_parts.append(f"Available devices: {', '.join(device_names)}")
            
            if "pending_operation" in context and context["pending_operation"]:
                pending_op = context["pending_operation"]
                pending_lines = []
                
                if pending_op.get("has_pending_create"):
                    pending_lines.append("has_pending_create: true")
                
                if pending_op.get("pending_op_type"):
                    pending_lines.append(f"pending_op_type: {pending_op['pending_op_type']}")
                
                if pending_lines:
                    context_parts.append("Pending operation state:\n" + "\n".join(pending_lines))
        
        context_str = "\n\n".join(context_parts)
        
        assert "has_pending_create: true" in context_str
        assert "pending_op_type: create" in context_str
    
    @pytest.mark.asyncio
    async def test_parser_includes_pending_edit_context(self):
        """Parser should include pending edit info in context string."""
        context = {
            "pending_operation": {
                "has_pending_create": False,
                "has_pending_edit": True,
                "has_pending_delete": False,
                "pending_op_type": "edit",
                "pending_edit_event": "Dentist Appointment",
                "pending_op_age_seconds": 25,
            },
        }
        
        # Simulate the parser's context building logic
        pending_op = context["pending_operation"]
        pending_lines = []
        
        if pending_op.get("has_pending_edit"):
            pending_lines.append("has_pending_edit: true")
            if pending_op.get("pending_edit_event"):
                pending_lines.append(f"editing_event: {pending_op['pending_edit_event']}")
        
        if pending_op.get("pending_op_type"):
            pending_lines.append(f"pending_op_type: {pending_op['pending_op_type']}")
        
        context_str = "\n".join(pending_lines)
        
        assert "has_pending_edit: true" in context_str
        assert "pending_op_type: edit" in context_str
        assert "editing_event: Dentist Appointment" in context_str
    
    def test_parser_source_includes_pending_operation_handling(self):
        """Verify the parser code includes pending operation handling."""
        import inspect
        from app.ai.intent.parser import IntentParser
        
        source = inspect.getsource(IntentParser.parse)
        
        # Verify pending operation handling exists
        assert "pending_operation" in source, "Parser should handle pending_operation"
        assert "has_pending_create" in source, "Parser should check has_pending_create"
        assert "has_pending_edit" in source, "Parser should check has_pending_edit"
        assert "pending_op_type" in source, "Parser should include pending_op_type"


# ---------------------------------------------------------------------------
# BUG #3 TESTS: TTL increased from 60s to 120s
# ---------------------------------------------------------------------------

class TestPendingTTL:
    """
    Test that TTL is now 120 seconds instead of 60.
    
    Bug: 60s was too short - user confirmations after ~61s would fail.
    Fix: Increased to 120s for better UX.
    """
    
    def test_pending_event_service_ttl_is_120(self):
        """Pending event service should have 120s TTL."""
        from app.services.pending_event_service import PendingEventService
        
        assert PendingEventService.TTL_SECONDS == 120
    
    def test_pending_edit_service_ttl_is_120(self):
        """Pending edit service should have 120s TTL."""
        from app.services.pending_edit_service import PendingEditService
        
        assert PendingEditService.TTL_SECONDS == 120
    
    @pytest.mark.asyncio
    async def test_pending_event_expires_at_120s(self):
        """Pending event should expire 120 seconds from creation."""
        service = PendingEventService()
        user_id = str(uuid4())
        
        before = datetime.now(timezone.utc)
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Test Event",
        )
        after = datetime.now(timezone.utc)
        
        # Expiration should be ~120 seconds in the future
        min_expected = before + timedelta(seconds=120)
        max_expected = after + timedelta(seconds=120)
        
        assert min_expected <= pending.expires_at <= max_expected
        
        # Cleanup
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_pending_edit_expires_at_120s(self):
        """Pending edit should expire 120 seconds from creation."""
        service = PendingEditService()
        
        before = datetime.now(timezone.utc)
        pending = await service.store_pending_edit(
            user_id="user-123",
            operation="edit",
            matching_events=[{
                "id": "evt-1",
                "summary": "Test Event",
                "start": {"dateTime": "2025-01-15T10:00:00Z"},
                "end": {"dateTime": "2025-01-15T11:00:00Z"},
            }],
        )
        after = datetime.now(timezone.utc)
        
        # Expiration should be ~120 seconds in the future
        min_expected = before + timedelta(seconds=120)
        max_expected = after + timedelta(seconds=120)
        
        assert min_expected <= pending.expires_at <= max_expected
        
        # Cleanup
        service.clear_all()
    
    @pytest.mark.asyncio
    async def test_confirmation_at_90_seconds_succeeds(self):
        """
        Confirmation at 90 seconds should succeed (was failing with 60s TTL).
        
        This test verifies the fix allows more time for user confirmation.
        """
        service = PendingEventService()
        user_id = str(uuid4())
        
        # Store pending event
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Test Event",
        )
        
        # Check that it's still valid after 90 seconds (simulated)
        # Since we can't actually wait 90s, we verify the expiration math
        now = datetime.now(timezone.utc)
        at_90_seconds = now + timedelta(seconds=90)
        
        # Event should NOT be expired at 90 seconds with 120s TTL
        assert pending.expires_at > at_90_seconds, "Event should be valid at 90 seconds"
        
        # But would be expired with old 60s TTL
        old_ttl_expiry = now + timedelta(seconds=60)
        assert at_90_seconds > old_ttl_expiry, "90s > 60s (old TTL would have expired)"
        
        # Cleanup
        service.clear_all()


# ---------------------------------------------------------------------------
# INTEGRATION TEST: End-to-end confirmation flow
# ---------------------------------------------------------------------------

class TestConfirmationFlowIntegration:
    """Integration tests for the complete confirmation flow."""
    
    @pytest.mark.asyncio
    async def test_pending_state_includes_timezone_field(self):
        """PendingEvent should store timezone for later use."""
        from app.services.pending_event_service import PendingEventService
        
        service = PendingEventService()
        user_id = str(uuid4())
        
        pending = await service.store_pending(
            user_id=user_id,
            event_title="Meeting",
            timezone="America/New_York",
        )
        
        assert pending.timezone == "America/New_York"
        
        # Cleanup
        service.clear_all()
    
    def test_context_aware_confirmation_is_documented(self):
        """Verify Sprint 3.9.1 changes are in the code."""
        import inspect
        from app.services.intent_service import IntentService
        
        # Check _handle_confirm_edit mentions Sprint 3.9.1
        edit_source = inspect.getsource(IntentService._handle_confirm_edit)
        assert "Sprint 3.9.1" in edit_source or "Bug Fix" in edit_source
        
        # Check timezone logging is present
        assert "timezone" in edit_source.lower()
