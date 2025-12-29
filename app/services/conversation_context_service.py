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
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging
import time

logger = logging.getLogger("jarvis.conversation")


@dataclass
class ConversationTurn:
    """
    A single turn in the conversation (user message + assistant response).
    
    Sprint 4.1: Enables multi-turn conversation memory.
    """
    user_message: str
    assistant_response: str
    intent_type: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "user": self.user_message,
            "assistant": self.assistant_response[:500] if self.assistant_response else None,  # Sprint 4.5.0: Increased from 200
            "intent": self.intent_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class GeneratedContent:
    """
    Single piece of generated content with metadata.

    Sprint 4.5.0: Content Memory System - stores multiple generated contents
    instead of overwriting previous ones.
    """
    content: str
    content_type: str
    title: Optional[str] = None
    timestamp: Optional[datetime] = None
    token_count: int = 0  # Estimated tokens for memory management

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "type": self.content_type,
            "title": self.title,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "token_count": self.token_count,
        }


@dataclass
class UserConversationState:
    """
    State for a single user's conversation.
    
    Tracks recent event, document, and search references
    to enable context-aware intent parsing.
    
    Sprint 4.1: Now includes conversation history for multi-turn awareness.
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
    
    # Sprint 4.1: Conversation history for multi-turn context
    conversation_history: list = None  # List[ConversationTurn]
    last_user_request: Optional[str] = None  # Most recent user message
    last_assistant_response: Optional[str] = None  # Most recent AI response
    last_intent_type: Optional[str] = None  # Type of the last intent
    last_conversation_timestamp: Optional[datetime] = None
    
    # Pending content generation (for follow-ups like "si, hazlo")
    pending_content_request: Optional[str] = None  # What user asked to generate
    pending_content_type: Optional[str] = None  # "template", "notes", "checklist", etc.
    
    # Generated content tracking (Sprint 4.2: Memory-aware content display)
    generated_content: Optional[str] = None  # The actual generated content
    generated_content_type: Optional[str] = None  # note, email, template, script, etc.
    generated_content_title: Optional[str] = None  # Title extracted from request/response
    generated_content_timestamp: Optional[datetime] = None  # When content was generated

    # Scene metadata tracking (Sprint 4.4.0 - GAP #8: Assistant awareness of displayed content)
    last_scene_id: Optional[str] = None  # ID of last displayed scene
    last_scene_components: list = None  # List of component types shown
    last_scene_layout: Optional[str] = None  # Layout intent (sidebar, fullscreen, etc.)
    last_scene_timestamp: Optional[datetime] = None  # When scene was displayed

    # Sprint 4.5.0: Content Memory System - stores multiple generated contents
    content_memory: List[GeneratedContent] = None  # List of generated contents
    max_content_items: int = 10  # Keep last N generated contents
    max_content_tokens: int = 20000  # ~20k tokens total limit for memory

    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.last_scene_components is None:
            self.last_scene_components = []
        if self.content_memory is None:
            self.content_memory = []

    # -------------------------------------------------------------------------
    # CONTENT MEMORY METHODS (Sprint 4.5.0)
    # -------------------------------------------------------------------------

    def add_to_content_memory(self, content: GeneratedContent) -> None:
        """
        Add content to memory with automatic cleanup.

        Sprint 4.5.0: Stores multiple contents instead of overwriting.
        """
        self.content_memory.append(content)
        self._enforce_content_limits()

    def _enforce_content_limits(self) -> None:
        """Enforce item count and token limits for content memory."""
        # Remove oldest if over item limit
        while len(self.content_memory) > self.max_content_items:
            self.content_memory.pop(0)

        # Remove oldest if over token limit
        total_tokens = sum(c.token_count for c in self.content_memory)
        while total_tokens > self.max_content_tokens and self.content_memory:
            removed = self.content_memory.pop(0)
            total_tokens -= removed.token_count

    def get_content_by_title(self, title_query: str) -> Optional[GeneratedContent]:
        """
        Find content by title (fuzzy match).

        Args:
            title_query: Partial or full title to search for

        Returns:
            Most recent matching GeneratedContent or None
        """
        title_lower = title_query.lower()
        for content in reversed(self.content_memory):  # Most recent first
            if content.title and title_lower in content.title.lower():
                return content
        return None

    def get_content_by_type(self, content_type: str) -> List[GeneratedContent]:
        """
        Find all content of a specific type.

        Args:
            content_type: Type to filter by (e.g., "note", "template", "weather_info")

        Returns:
            List of matching GeneratedContent objects
        """
        return [c for c in self.content_memory if c.content_type == content_type]

    def get_recent_contents(self, limit: int = 5) -> List[GeneratedContent]:
        """
        Get most recent generated contents.

        Args:
            limit: Maximum number of contents to return

        Returns:
            List of most recent GeneratedContent objects
        """
        return self.content_memory[-limit:] if self.content_memory else []

    def get_content_memory_for_prompt(self, limit: int = 5) -> List[Dict]:
        """
        Get content memory formatted for injection into prompts.

        Sprint 4.5.0: Provides full content (not truncated) for Claude.

        Args:
            limit: Maximum number of contents to include

        Returns:
            List of content dictionaries with full content
        """
        return [c.to_dict() for c in self.content_memory[-limit:]]
    
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
            "conversation": {
                "last_user": self.last_user_request[:100] if self.last_user_request else None,
                "last_assistant": self.last_assistant_response[:100] if self.last_assistant_response else None,
                "last_intent": self.last_intent_type,
                "pending_content": self.pending_content_request,
                "history_length": len(self.conversation_history),
            } if self.last_user_request else None,
            "last_scene": {
                "scene_id": self.last_scene_id,
                "components": self.last_scene_components,
                "layout": self.last_scene_layout,
            } if self.last_scene_id else None,
            # Sprint 4.5.0: Content memory info
            "content_memory": {
                "count": len(self.content_memory) if self.content_memory else 0,
                "titles": [c.title for c in self.content_memory[-5:]] if self.content_memory else [],
                "total_tokens": sum(c.token_count for c in self.content_memory) if self.content_memory else 0,
            } if self.content_memory else None,
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

    def set_last_scene(
        self,
        user_id: str,
        scene_id: str,
        components: list,
        layout_intent: str,
    ) -> None:
        """
        Record that a scene was just displayed.

        Sprint 4.4.0 - GAP #8: Track displayed scenes for assistant awareness.

        This allows the assistant to reference what's currently on screen in
        follow-up conversations.

        Args:
            user_id: User identifier
            scene_id: Scene graph ID
            components: List of component types (e.g., ["meeting_detail", "text_block"])
            layout_intent: Layout type (e.g., "sidebar", "fullscreen")
        """
        context = self._get_or_create(user_id)
        context.last_scene_id = scene_id
        context.last_scene_components = components
        context.last_scene_layout = layout_intent
        context.last_scene_timestamp = datetime.now(timezone.utc)
        logger.info(
            f"Context set - last_scene: '{scene_id[:20]}...' with {len(components)} components "
            f"({layout_intent}) for user {user_id[:8]}..."
        )

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
    
    # -------------------------------------------------------------------------
    # CONVERSATION HISTORY (Sprint 4.1)
    # -------------------------------------------------------------------------
    
    def add_conversation_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        intent_type: Optional[str] = None,
    ) -> None:
        """
        Add a conversation turn to the history.
        
        Sprint 4.1: Tracks multi-turn conversations for context awareness.
        
        Args:
            user_id: User identifier
            user_message: What the user said
            assistant_response: What the AI responded
            intent_type: The intent type that was processed
        """
        context = self._get_or_create(user_id)
        
        # Create turn
        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
            intent_type=intent_type,
            timestamp=datetime.now(timezone.utc),
        )
        
        # Add to history (keep last 15 turns max for better context)
        context.conversation_history.append(turn)
        if len(context.conversation_history) > 15:
            context.conversation_history = context.conversation_history[-15:]
        
        # Update last turn fields
        context.last_user_request = user_message
        context.last_assistant_response = assistant_response
        context.last_intent_type = intent_type
        context.last_conversation_timestamp = datetime.now(timezone.utc)
        
        logger.debug(
            f"Conversation turn added for user {user_id[:8]}... "
            f"intent={intent_type}, history_len={len(context.conversation_history)}"
        )
    
    def set_pending_content_request(
        self,
        user_id: str,
        content_request: str,
        content_type: str = "general",
    ) -> None:
        """
        Set a pending content generation request.
        
        Sprint 4.1: Tracks when user asks for generated content
        so follow-ups like "si, hazlo" can continue the generation.
        
        Args:
            user_id: User identifier
            content_request: What the user wants generated
            content_type: Type of content (template, notes, checklist, etc.)
        """
        context = self._get_or_create(user_id)
        context.pending_content_request = content_request
        context.pending_content_type = content_type
        logger.info(
            f"Pending content set for user {user_id[:8]}... "
            f"type={content_type}, request='{content_request[:50]}...'"
        )
    
    def get_pending_content_request(self, user_id: str) -> Optional[Dict]:
        """
        Get pending content generation request if still valid.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with request and type if valid, None otherwise
        """
        context = self._contexts.get(user_id)
        if not context or not context.pending_content_request:
            return None
        
        # Check TTL based on last conversation
        if context.last_conversation_timestamp:
            age = (datetime.now(timezone.utc) - context.last_conversation_timestamp).total_seconds()
            if age > self._ttl:
                return None
        
        return {
            "request": context.pending_content_request,
            "type": context.pending_content_type,
        }
    
    def clear_pending_content(self, user_id: str) -> None:
        """Clear pending content request after it's been fulfilled."""
        context = self._contexts.get(user_id)
        if context:
            context.pending_content_request = None
            context.pending_content_type = None
            logger.debug(f"Pending content cleared for user {user_id[:8]}...")
    
    def get_conversation_history(
        self,
        user_id: str,
        max_turns: int = 5,
    ) -> list:
        """
        Get recent conversation history for context.
        
        Args:
            user_id: User identifier
            max_turns: Maximum number of turns to return
            
        Returns:
            List of ConversationTurn dicts
        """
        context = self._contexts.get(user_id)
        if not context or not context.conversation_history:
            return []
        
        # Return most recent turns
        recent = context.conversation_history[-max_turns:]
        return [turn.to_dict() for turn in recent]
    
    def get_conversation_summary(self, user_id: str, max_turns: int = 5) -> Optional[str]:
        """
        Get a summary of recent conversation for AI prompts.
        
        Sprint 4.1: Provides formatted conversation history for AI context.
        Sprint 4.2.3: Prioritizes CONVERSATION turns over device commands.
        
        Returns:
            Formatted string with recent conversation or None
        """
        context = self._contexts.get(user_id)
        if not context or not context.conversation_history:
            return None
        
        # Check TTL
        if context.last_conversation_timestamp:
            age = (datetime.now(timezone.utc) - context.last_conversation_timestamp).total_seconds()
            if age > self._ttl:
                return None
        
        # Sprint 4.2.3: Prioritize conversation turns over device commands
        # This ensures that meaningful discussions aren't pushed out by simple commands
        conversation_turns = [
            t for t in context.conversation_history 
            if t.intent_type in ('conversation', 'IntentResultType.CONVERSATION', None)
        ]
        command_turns = [
            t for t in context.conversation_history 
            if t.intent_type not in ('conversation', 'IntentResultType.CONVERSATION', None)
        ]
        
        # Include more conversation turns + some command context
        prioritized_turns = conversation_turns[-max_turns:] + command_turns[-2:]
        
        # Sort by timestamp to maintain chronological order
        prioritized_turns.sort(key=lambda t: t.timestamp if t.timestamp else datetime.min.replace(tzinfo=timezone.utc))
        
        # Take the last max_turns after sorting
        recent_turns = prioritized_turns[-max_turns:]
        
        lines = []
        for turn in recent_turns:
            lines.append(f"User: {turn.user_message}")
            if turn.assistant_response:
                # Truncate long responses (Sprint 4.5.0: increased from 150 to 300)
                response = turn.assistant_response[:300]
                if len(turn.assistant_response) > 300:
                    response += "..."
                lines.append(f"Assistant: {response}")
        
        return "\n".join(lines)
    
    def _get_or_create(self, user_id: str) -> UserConversationState:
        """Get or create context for user."""
        if user_id not in self._contexts:
            self._contexts[user_id] = UserConversationState()
        return self._contexts[user_id]
    
    # -------------------------------------------------------------------------
    # GENERATED CONTENT TRACKING (Sprint 4.2)
    # -------------------------------------------------------------------------
    
    def set_generated_content(
        self,
        user_id: str,
        content: str,
        content_type: str,
        title: Optional[str] = None,
    ) -> None:
        """
        Store generated content with 300s TTL (same as conversation context).

        Sprint 4.2: Memory-aware content display.
        Sprint 4.5.0: Also adds to content_memory for multi-content retrieval.

        This allows the AI to remember generated content (notes, emails, templates)
        so users can reference it later with "show the note on the screen".

        Args:
            user_id: User identifier
            content: The actual generated content
            content_type: Type of content (note, email, template, script, etc.)
            title: Optional title extracted from request or response
        """
        context = self._get_or_create(user_id)

        # Sprint 4.5.0: Add to content memory (stores multiple contents)
        token_count = len(content) // 4  # Estimate ~4 chars per token
        generated = GeneratedContent(
            content=content,
            content_type=content_type,
            title=title,
            timestamp=datetime.now(timezone.utc),
            token_count=token_count,
        )
        context.add_to_content_memory(generated)

        # Backwards compatibility: also set singleton fields
        context.generated_content = content
        context.generated_content_type = content_type
        context.generated_content_title = title
        context.generated_content_timestamp = generated.timestamp

        logger.info(
            f"Generated content stored for user {user_id[:8]}... "
            f"type={content_type}, title={title}, length={len(content)}, "
            f"memory_size={len(context.content_memory)}"
        )
    
    def get_generated_content(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve generated content if still valid (within 300s TTL).
        
        Sprint 4.2: Memory-aware content display.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with content, type, title, timestamp if valid, None otherwise
        """
        context = self._contexts.get(user_id)
        if not context or not context.generated_content:
            return None
        
        # Check TTL (5 minutes = 300 seconds, same as pending_event_service)
        if context.generated_content_timestamp:
            age = (datetime.now(timezone.utc) - context.generated_content_timestamp).total_seconds()
            if age > self._ttl:
                logger.debug(f"Generated content expired for user {user_id[:8]}... (age: {age:.0f}s)")
                self.clear_generated_content(user_id)
                return None
        
        return {
            "content": context.generated_content,
            "type": context.generated_content_type,
            "title": context.generated_content_title,
            "timestamp": context.generated_content_timestamp,
        }
    
    def clear_generated_content(self, user_id: str) -> None:
        """
        Clear generated content from memory.

        Args:
            user_id: User identifier
        """
        context = self._contexts.get(user_id)
        if context:
            context.generated_content = None
            context.generated_content_type = None
            context.generated_content_title = None
            context.generated_content_timestamp = None
            logger.debug(f"Generated content cleared for user {user_id[:8]}...")

    def get_content_memory(self, user_id: str, limit: int = 5) -> List[Dict]:
        """
        Get content memory for a user.

        Sprint 4.5.0: Returns list of generated contents for prompt injection.

        Args:
            user_id: User identifier
            limit: Maximum number of contents to return

        Returns:
            List of content dictionaries with full content
        """
        context = self._contexts.get(user_id)
        if not context or not context.content_memory:
            return []
        return context.get_content_memory_for_prompt(limit)

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
