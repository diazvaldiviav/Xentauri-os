"""
Tests for the ConversationContext feature (Sprint 3.9).

This feature enables multi-turn conversation awareness by tracking
recent events, documents, and searches for each user.

Example flow:
1. User: "show reunion de producto" → System displays event
2. User: "is there a doc for this event?" → System resolves "this event" from context
"""

import pytest
import time
from datetime import datetime, timezone


class TestConversationContextService:
    """Tests for ConversationContextService."""
    
    def test_set_and_get_last_event(self):
        """Test storing and retrieving event context."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        user_id = "test-user-1"
        
        # Set event context
        service.set_last_event(
            user_id=user_id,
            event_title="Reunion de Producto",
            event_id="event-123",
            event_date="2025-01-15T14:00:00Z",
        )
        
        # Get event context
        event = service.get_last_event(user_id)
        
        assert event is not None
        assert event["title"] == "Reunion de Producto"
        assert event["id"] == "event-123"
        assert event["date"] == "2025-01-15T14:00:00Z"
    
    def test_set_and_get_last_doc(self):
        """Test storing and retrieving document context."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        user_id = "test-user-2"
        
        # Set doc context
        service.set_last_doc(
            user_id=user_id,
            doc_id="doc-456",
            doc_url="https://docs.google.com/document/d/doc-456/edit",
            doc_title="Meeting Notes",
        )
        
        # Get doc context
        doc = service.get_last_doc(user_id)
        
        assert doc is not None
        assert doc["id"] == "doc-456"
        assert doc["url"] == "https://docs.google.com/document/d/doc-456/edit"
        assert doc["title"] == "Meeting Notes"
    
    def test_set_and_get_last_search(self):
        """Test storing and retrieving search context."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        user_id = "test-user-3"
        
        # Set search context
        service.set_last_search(
            user_id=user_id,
            search_term="reunion",
            search_type="calendar",
        )
        
        # Get search context
        search = service.get_last_search(user_id)
        
        assert search is not None
        assert search["term"] == "reunion"
        assert search["type"] == "calendar"
    
    def test_ttl_expiry(self):
        """Test that context expires after TTL."""
        from app.services.conversation_context_service import ConversationContextService
        
        # Create service with very short TTL (0.1 seconds)
        service = ConversationContextService(ttl_seconds=0.1)
        user_id = "test-user-ttl"
        
        # Set event context
        service.set_last_event(
            user_id=user_id,
            event_title="Expiring Event",
            event_id="exp-123",
            event_date="2025-01-15",
        )
        
        # Should exist immediately
        event = service.get_last_event(user_id)
        assert event is not None
        
        # Wait for expiry
        time.sleep(0.15)
        
        # Should be expired now
        expired_event = service.get_last_event(user_id)
        assert expired_event is None
    
    def test_different_users_have_separate_contexts(self):
        """Test that different users have isolated contexts."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        
        # Set different events for different users
        service.set_last_event("user-a", "Event A", "id-a", "2025-01-15")
        service.set_last_event("user-b", "Event B", "id-b", "2025-01-16")
        
        # Verify isolation
        event_a = service.get_last_event("user-a")
        event_b = service.get_last_event("user-b")
        
        assert event_a["title"] == "Event A"
        assert event_b["title"] == "Event B"
    
    def test_get_full_context(self):
        """Test retrieving full context state."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        user_id = "test-user-full"
        
        # Set multiple context items
        service.set_last_event(user_id, "My Meeting", "meet-123", "2025-01-15")
        service.set_last_doc(user_id, "doc-456", "https://docs.google.com/...", "Notes")
        service.set_last_search(user_id, "meeting", "calendar")
        
        # Get full context
        ctx = service.get_context(user_id)
        
        assert ctx.last_event_title == "My Meeting"
        assert ctx.last_doc_id == "doc-456"
        assert ctx.last_search_term == "meeting"
    
    def test_clear_context(self):
        """Test clearing user context."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        user_id = "test-user-clear"
        
        # Set context
        service.set_last_event(user_id, "Event", "id", "date")
        
        # Clear it
        service.clear(user_id)
        
        # Should be empty now
        event = service.get_last_event(user_id)
        assert event is None
    
    def test_nonexistent_user_returns_empty_context(self):
        """Test that nonexistent user gets empty context."""
        from app.services.conversation_context_service import ConversationContextService
        
        service = ConversationContextService()
        
        ctx = service.get_context("nonexistent-user")
        
        assert ctx.last_event_title is None
        assert ctx.last_doc_id is None
        assert ctx.last_search_term is None


class TestConversationContextDataclass:
    """Tests for ConversationContext dataclass."""
    
    def test_has_recent_event_true(self):
        """Test has_recent_event returns True for recent events."""
        from app.ai.context import ConversationContext
        
        ctx = ConversationContext(
            last_event_title="Test Event",
            last_event_id="123",
            last_event_timestamp=datetime.now(timezone.utc),
        )
        
        assert ctx.has_recent_event() is True
    
    def test_has_recent_event_false_when_empty(self):
        """Test has_recent_event returns False when no event."""
        from app.ai.context import ConversationContext
        
        ctx = ConversationContext()
        
        assert ctx.has_recent_event() is False
    
    def test_to_dict_with_event(self):
        """Test to_dict includes event info."""
        from app.ai.context import ConversationContext
        
        ctx = ConversationContext(
            last_event_title="Meeting",
            last_event_id="id-123",
            last_event_date="2025-01-15",
            last_event_timestamp=datetime.now(timezone.utc),
        )
        
        d = ctx.to_dict()
        
        assert d["last_event"] is not None
        assert d["last_event"]["title"] == "Meeting"
        assert d["last_event"]["is_recent"] is True
    
    def test_to_dict_without_event(self):
        """Test to_dict returns None for empty event."""
        from app.ai.context import ConversationContext
        
        ctx = ConversationContext()
        
        d = ctx.to_dict()
        
        assert d["last_event"] is None
        assert d["last_doc"] is None


class TestContextFlowIntegration:
    """Integration tests for the context flow."""
    
    def test_event_to_doc_query_flow(self):
        """
        Test the flow:
        1. Calendar query finds event → stores in context
        2. Doc query without meeting_search → uses context
        """
        from app.services.conversation_context_service import conversation_context_service
        
        user_id = "flow-test-user"
        
        # Step 1: Simulate calendar query result storing event
        conversation_context_service.set_last_event(
            user_id=user_id,
            event_title="Team Standup",
            event_id="standup-123",
            event_date="2025-01-15T10:00:00Z",
        )
        
        # Step 2: Simulate doc query checking context
        event = conversation_context_service.get_last_event(user_id)
        
        # This is what _get_event_from_context does:
        if event:
            meeting_search = event["title"]
        else:
            meeting_search = None
        
        assert meeting_search == "Team Standup"
        
        # Cleanup
        conversation_context_service.clear(user_id)
