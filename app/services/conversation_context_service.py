"""
Conversation Context Service - Tracks recent user activity for context-aware parsing.

Sprint 4.0: Enables the AI to understand references like "this event", "that doc".

This service maintains per-user conversation state with a TTL (time-to-live).
Context expires after inactivity to prevent stale references.

Example flow:
1. User: "show reunion de producto on screen" → Records event in context
2. User: "is there a doc for this event?" → Uses context to resolve "this event"
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger("jarvis.conversation")


@dataclass
class UserConversationState:
    """
    State for a single user's conversation.
    
    Tracks recent event, document, and search references
    to enable context-aware intent parsing.
    """
    # Event context - last calendar event referenced/displayed
    last_event_title: Optional[str] = None
    last_event_id: Optional[str] = None
    last_event_date: Optional[str] = None
    last_event_timestamp: Optional[datetime] = None
    
    # Doc context - last document referenced
    last_doc_id: Optional[str] = None
    last_doc_url: Optional[str] = None
    last_doc_title: Optional[str] = None
    last_doc_timestamp: Optional[datetime] = None
    
    # Search context - last search performed
    last_search_term: Optional[str] = None
    last_search_type: Optional[str] = None  # "calendar" or "doc"
    last_search_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert state to dictionary for logging/debugging."""
        return {
            "last_event": {
                "title": self.last_event_title,
                "id": self.last_event_id,
                "date": self.last_event_date,
            } if self.last_event_title else None,
            "last_doc": {
                "id": self.last_doc_id,
                "url": self.last_doc_url,
            } if self.last_doc_id else None,
            "last_search": {
                "term": self.last_search_term,
                "type": self.last_search_type,
            } if self.last_search_term else None,
        }


class ConversationContextService:
    """
    Service to track conversation context per user.
    
    Similar to PendingEventService but for general conversation context.
    Context expires after TTL (default 5 minutes).
    
    Usage:
        # Record an event reference
        conversation_context_service.set_last_event(
            user_id="user-123",
            event_title="reunion de producto",
            event_id="google-event-id",
        )
        
        # Later, retrieve it
        last_event = conversation_context_service.get_last_event("user-123")
        if last_event:
            print(f"Last event: {last_event['title']}")
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the service.
        
        Args:
            ttl_seconds: Time-to-live for context in seconds (default 5 min)
        """
        self._contexts: Dict[str, UserConversationState] = {}
        self._ttl = ttl_seconds
        logger.info(f"Conversation context service initialized (TTL: {ttl_seconds}s)")
    
    def set_last_event(
        self,
        user_id: str,
        event_title: str,
        event_id: Optional[str] = None,
        event_date: Optional[str] = None,
    ) -> None:
        """
        Record that user just referenced/displayed an event.
        
        Args:
            user_id: User identifier
            event_title: The event title/summary
            event_id: Optional Google Calendar event ID
            event_date: Optional event date (YYYY-MM-DD)
        """
        context = self._get_or_create(user_id)
        context.last_event_title = event_title
        context.last_event_id = event_id
        context.last_event_date = event_date
        context.last_event_timestamp = datetime.now(timezone.utc)
        logger.info(f"Context set - last_event: '{event_title}' for user {user_id[:8]}...")
    
    def set_last_doc(
        self,
        user_id: str,
        doc_id: str,
        doc_url: Optional[str] = None,
        doc_title: Optional[str] = None,
    ) -> None:
        """
        Record that user just referenced a document.
        
        Args:
            user_id: User identifier
            doc_id: Google Docs document ID
            doc_url: Optional full document URL
            doc_title: Optional document title
        """
        context = self._get_or_create(user_id)
        context.last_doc_id = doc_id
        context.last_doc_url = doc_url
        context.last_doc_title = doc_title
        context.last_doc_timestamp = datetime.now(timezone.utc)
        logger.info(f"Context set - last_doc: '{doc_id[:20]}...' for user {user_id[:8]}...")
    
    def set_last_search(
        self,
        user_id: str,
        search_term: str,
        search_type: str = "calendar",
    ) -> None:
        """
        Record that user just performed a search.
        
        Args:
            user_id: User identifier
            search_term: The search query
            search_type: Type of search ("calendar" or "doc")
        """
        context = self._get_or_create(user_id)
        context.last_search_term = search_term
        context.last_search_type = search_type
        context.last_search_timestamp = datetime.now(timezone.utc)
        logger.debug(f"Context set - last_search: '{search_term}' ({search_type})")
    
    def get_last_event(self, user_id: str) -> Optional[Dict]:
        """
        Get the last referenced event if still valid (within TTL).
        
        Args:
            user_id: User identifier
        
        Returns:
            Dict with title, id, date if valid, None otherwise
        """
        context = self._contexts.get(user_id)
        if not context or not context.last_event_timestamp:
            return None
        
        age = (datetime.now(timezone.utc) - context.last_event_timestamp).total_seconds()
        if age > self._ttl:
            logger.debug(f"Context expired - last_event age: {age:.0f}s > TTL {self._ttl}s")
            return None
        
        return {
            "title": context.last_event_title,
            "id": context.last_event_id,
            "date": context.last_event_date,
        }
    
    def get_last_doc(self, user_id: str) -> Optional[Dict]:
        """
        Get the last referenced doc if still valid (within TTL).
        
        Args:
            user_id: User identifier
        
        Returns:
            Dict with id, url if valid, None otherwise
        """
        context = self._contexts.get(user_id)
        if not context or not context.last_doc_timestamp:
            return None
        
        age = (datetime.now(timezone.utc) - context.last_doc_timestamp).total_seconds()
        if age > self._ttl:
            logger.debug(f"Context expired - last_doc age: {age:.0f}s > TTL {self._ttl}s")
            return None
        
        return {
            "id": context.last_doc_id,
            "url": context.last_doc_url,
            "title": context.last_doc_title,
        }
    
    def get_last_search(self, user_id: str) -> Optional[Dict]:
        """
        Get the last search if still valid (within TTL).
        
        Args:
            user_id: User identifier
        
        Returns:
            Dict with term, type if valid, None otherwise
        """
        context = self._contexts.get(user_id)
        if not context or not context.last_search_timestamp:
            return None
        
        age = (datetime.now(timezone.utc) - context.last_search_timestamp).total_seconds()
        if age > self._ttl:
            return None
        
        return {
            "term": context.last_search_term,
            "type": context.last_search_type,
        }
    
    def get_context(self, user_id: str) -> Optional[UserConversationState]:
        """
        Get full context for user.
        
        Args:
            user_id: User identifier
        
        Returns:
            UserConversationState or None
        """
        return self._contexts.get(user_id)
    
    def _get_or_create(self, user_id: str) -> UserConversationState:
        """Get or create context for user."""
        if user_id not in self._contexts:
            self._contexts[user_id] = UserConversationState()
        return self._contexts[user_id]
    
    def clear(self, user_id: str) -> None:
        """
        Clear context for user.
        
        Args:
            user_id: User identifier
        """
        if user_id in self._contexts:
            del self._contexts[user_id]
            logger.debug(f"Context cleared for user {user_id[:8]}...")
    
    def clear_all(self) -> None:
        """Clear all contexts (for testing/reset)."""
        self._contexts.clear()
        logger.info("All conversation contexts cleared")


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
conversation_context_service = ConversationContextService()
