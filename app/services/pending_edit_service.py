"""
Pending Edit Service - Manages pending calendar edit/delete operations.

Sprint 3.9: Calendar Event Edit & Delete with Confirmation Flow

This service manages the state of pending edit/delete operations that are
awaiting user confirmation or disambiguation. Operations expire after 60 seconds.

Design follows pending_event_service.py pattern for consistency:
- In-memory storage with TTL
- Singleton instance
- Cleanup on operations

Flow for Edit:
1. User says "reschedule my dentist appointment to 3pm"
2. Service searches for "dentist" events
3. If multiple matches, store search results and ask for selection
4. If single match, show preview and ask for confirmation
5. On confirm: event is updated via Google Calendar API
6. On cancel/timeout: pending edit is removed

Flow for Delete:
1. User says "delete my meeting tomorrow"
2. Service searches for events matching criteria
3. If multiple matches, ask for selection
4. Show confirmation with event details
5. On confirm: event is deleted via Google Calendar API
6. On cancel/timeout: pending delete is removed

Usage:
    from app.services.pending_edit_service import pending_edit_service
    
    # Store a pending edit with search results
    pending = await pending_edit_service.store_pending_edit(
        user_id="user-123",
        operation="edit",
        search_term="dentist",
        matching_events=[event1, event2],
        changes={"start_datetime": "2025-01-15T15:00:00"},
    )
    
    # User selects an event
    pending = pending_edit_service.select_event("user-123", index=1)
    
    # Check for pending
    pending = pending_edit_service.get_pending("user-123")
    
    # Confirm and get event details
    pending = await pending_edit_service.confirm_pending("user-123")
    
    # Or cancel
    pending_edit_service.cancel_pending("user-123")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as tz
from typing import Optional, Dict, Any, List
from enum import Enum


logger = logging.getLogger("jarvis.services.pending_edit")


class PendingOperationType(str, Enum):
    """Type of pending operation."""
    EDIT = "edit"
    DELETE = "delete"


class PendingState(str, Enum):
    """State of the pending operation."""
    AWAITING_SELECTION = "awaiting_selection"  # Multiple matches, needs selection
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Single match or selected, needs confirm
    CONFIRMED = "confirmed"  # User confirmed, ready to execute
    CANCELLED = "cancelled"  # User cancelled


@dataclass
class MatchingEvent:
    """
    Represents an event that matches the user's search criteria.
    
    Stores minimal info needed to display options to user.
    """
    event_id: str
    summary: str
    start_time: Optional[str] = None  # ISO format datetime
    end_time: Optional[str] = None
    location: Optional[str] = None
    is_all_day: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "summary": self.summary,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "location": self.location,
            "is_all_day": self.is_all_day,
        }


@dataclass
class PendingEdit:
    """
    Pending edit/delete operation awaiting user confirmation.
    
    Stores search results, selected event, and proposed changes.
    """
    # User identification
    user_id: str
    
    # Operation type
    operation: PendingOperationType
    
    # Current state
    state: PendingState = PendingState.AWAITING_SELECTION
    
    # Search criteria used
    search_term: Optional[str] = None
    date_filter: Optional[str] = None
    
    # Matching events from search
    matching_events: List[MatchingEvent] = field(default_factory=list)
    
    # Selected event (after disambiguation)
    selected_event: Optional[MatchingEvent] = None
    selected_index: Optional[int] = None
    
    # Proposed changes (for edit operation)
    changes: Optional[Dict[str, Any]] = None
    # Supported change fields:
    # - summary: New event title
    # - start_datetime: New start time (ISO format)
    # - end_datetime: New end time (ISO format)
    # - start_date: New start date (for all-day events)
    # - end_date: New end date (for all-day events)
    # - location: New location
    # - description: New description
    # - recurrence: New recurrence rule
    
    # Tracking
    created_at: datetime = field(default_factory=lambda: datetime.now(tz.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(tz.utc) + timedelta(seconds=60))
    original_text: str = ""
    
    def is_expired(self) -> bool:
        """Check if this pending edit has expired."""
        return datetime.now(tz.utc) > self.expires_at
    
    def needs_selection(self) -> bool:
        """Check if user needs to select from multiple events."""
        return (
            self.state == PendingState.AWAITING_SELECTION and
            len(self.matching_events) > 1
        )
    
    def is_ready_for_confirmation(self) -> bool:
        """Check if an event is selected and ready for confirmation."""
        return (
            self.state == PendingState.AWAITING_CONFIRMATION and
            self.selected_event is not None
        )
    
    def get_event_options_text(self) -> str:
        """Generate numbered list of matching events for disambiguation."""
        if not self.matching_events:
            return "No matching events found."
        
        lines = []
        for i, event in enumerate(self.matching_events, 1):
            time_info = ""
            if event.is_all_day:
                time_info = "(all day)"
            elif event.start_time:
                # Format: "3:00 PM"
                try:
                    dt = datetime.fromisoformat(event.start_time.replace('Z', '+00:00'))
                    time_info = dt.strftime("at %I:%M %p").lstrip("0").replace(" 0", " ")
                except (ValueError, AttributeError):
                    time_info = f"at {event.start_time}"
            
            location_info = f" - {event.location}" if event.location else ""
            lines.append(f"{i}. {event.summary} {time_info}{location_info}")
        
        return "\n".join(lines)
    
    def get_confirmation_text(self) -> str:
        """Generate confirmation prompt showing what will be done."""
        if not self.selected_event:
            return "No event selected."
        
        event = self.selected_event
        
        if self.operation == PendingOperationType.DELETE:
            return f"Delete '{event.summary}'? This cannot be undone."
        
        # Edit operation - describe the changes
        if not self.changes:
            return f"No changes specified for '{event.summary}'."
        
        change_descriptions = []
        for field_name, new_value in self.changes.items():
            if field_name == "summary":
                change_descriptions.append(f"title to '{new_value}'")
            elif field_name == "start_datetime":
                try:
                    dt = datetime.fromisoformat(str(new_value).replace('Z', '+00:00'))
                    change_descriptions.append(f"start time to {dt.strftime('%I:%M %p on %B %d').lstrip('0')}")
                except (ValueError, TypeError):
                    change_descriptions.append(f"start time to {new_value}")
            elif field_name == "end_datetime":
                try:
                    dt = datetime.fromisoformat(str(new_value).replace('Z', '+00:00'))
                    change_descriptions.append(f"end time to {dt.strftime('%I:%M %p').lstrip('0')}")
                except (ValueError, TypeError):
                    change_descriptions.append(f"end time to {new_value}")
            elif field_name == "location":
                change_descriptions.append(f"location to '{new_value}'")
            elif field_name == "description":
                change_descriptions.append(f"description to '{new_value[:30]}...'")
            elif field_name == "recurrence":
                change_descriptions.append(f"recurrence to '{new_value}'")
        
        if change_descriptions:
            changes_text = ", ".join(change_descriptions)
            return f"Update '{event.summary}': change {changes_text}?"
        
        return f"Update '{event.summary}'?"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "user_id": self.user_id,
            "operation": self.operation.value,
            "state": self.state.value,
            "search_term": self.search_term,
            "date_filter": self.date_filter,
            "matching_events_count": len(self.matching_events),
            "selected_event": self.selected_event.to_dict() if self.selected_event else None,
            "selected_index": self.selected_index,
            "changes": self.changes,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired(),
        }


class PendingEditService:
    """
    Service for managing pending calendar edit/delete operations with 60s TTL.
    
    This class handles the confirmation flow for calendar event editing/deletion:
    - Store pending operations with search results
    - Handle event selection for disambiguation
    - Confirm or cancel operations
    - Automatic cleanup of expired entries
    
    Thread-safety note: For MVP, this is acceptable.
    In production with multiple workers, use Redis instead.
    """
    
    # TTL in seconds (60 seconds for confirmation timeout)
    TTL_SECONDS = 60
    
    def __init__(self):
        """Initialize the pending edit service."""
        # In-memory storage: user_id -> PendingEdit
        self._pending: Dict[str, PendingEdit] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info("Pending edit service initialized")
    
    # -------------------------------------------------------------------------
    # CORE OPERATIONS
    # -------------------------------------------------------------------------
    
    async def store_pending_edit(
        self,
        user_id: str,
        operation: str,  # "edit" or "delete"
        matching_events: List[Dict[str, Any]],
        search_term: Optional[str] = None,
        date_filter: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        original_text: str = "",
    ) -> PendingEdit:
        """
        Store a pending edit/delete operation.
        
        Overwrites any existing pending operation for this user.
        Each user can only have one pending operation at a time.
        
        Args:
            user_id: User identifier (UUID as string)
            operation: "edit" or "delete"
            matching_events: List of events matching search criteria
            search_term: Original search term used
            date_filter: Date filter applied
            changes: Proposed changes for edit operation
            original_text: Original user request text
        
        Returns:
            The stored PendingEdit
        """
        # Clean up expired entries first
        self.cleanup_expired()
        
        # Convert matching events to MatchingEvent objects
        # Handle both CalendarEvent objects and dicts
        events = []
        for e in matching_events:
            if hasattr(e, 'id'):
                # CalendarEvent object (Pydantic model)
                events.append(MatchingEvent(
                    event_id=e.id,
                    summary=e.summary or "Untitled",
                    start_time=self._extract_start_time_from_event(e),
                    end_time=self._extract_end_time_from_event(e),
                    location=e.location,
                    is_all_day=e.is_all_day() if hasattr(e, 'is_all_day') else False,
                ))
            else:
                # Dict (legacy support)
                events.append(MatchingEvent(
                    event_id=e.get("id", e.get("event_id", "")),
                    summary=e.get("summary", "Untitled"),
                    start_time=self._extract_start_time(e),
                    end_time=self._extract_end_time(e),
                    location=e.get("location"),
                    is_all_day=self._is_all_day_event(e),
                ))
        
        # Determine initial state based on number of matches
        if len(events) == 0:
            # No matches - will need to report this
            state = PendingState.AWAITING_SELECTION
        elif len(events) == 1:
            # Single match - auto-select and await confirmation
            state = PendingState.AWAITING_CONFIRMATION
            selected_event = events[0]
            selected_index = 1
        else:
            # Multiple matches - need disambiguation
            state = PendingState.AWAITING_SELECTION
            selected_event = None
            selected_index = None
        
        # Create the pending edit
        now = datetime.now(tz.utc)
        op_type = PendingOperationType.EDIT if operation.lower() == "edit" else PendingOperationType.DELETE
        
        pending = PendingEdit(
            user_id=str(user_id),
            operation=op_type,
            state=state,
            search_term=search_term,
            date_filter=date_filter,
            matching_events=events,
            selected_event=selected_event if len(events) == 1 else None,
            selected_index=selected_index if len(events) == 1 else None,
            changes=changes if op_type == PendingOperationType.EDIT else None,
            created_at=now,
            expires_at=now + timedelta(seconds=self.TTL_SECONDS),
            original_text=original_text,
        )
        
        # Store (overwrites any existing)
        self._pending[str(user_id)] = pending
        
        logger.info(
            f"Stored pending {operation} for user",
            extra={
                "user_id": str(user_id)[:8],
                "operation": operation,
                "matching_count": len(events),
                "state": state.value,
                "expires_in": self.TTL_SECONDS,
            }
        )
        
        return pending
    
    def _extract_start_time(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract start time from Google Calendar event dict."""
        start = event.get("start", {})
        if isinstance(start, dict):
            return start.get("dateTime") or start.get("date")
        return event.get("start_time")
    
    def _extract_end_time(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract end time from Google Calendar event dict."""
        end = event.get("end", {})
        if isinstance(end, dict):
            return end.get("dateTime") or end.get("date")
        return event.get("end_time")
    
    def _is_all_day_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is all-day."""
        start = event.get("start", {})
        if isinstance(start, dict):
            return "date" in start and "dateTime" not in start
        return event.get("is_all_day", False)
    
    def _extract_start_time_from_event(self, event) -> Optional[str]:
        """Extract start time from CalendarEvent object."""
        if event.start:
            dt = event.start.get_datetime()
            if dt:
                return dt.isoformat()
            # All-day event - return the date
            if event.start.date:
                return event.start.date
        return None
    
    def _extract_end_time_from_event(self, event) -> Optional[str]:
        """Extract end time from CalendarEvent object."""
        if event.end:
            dt = event.end.get_datetime()
            if dt:
                return dt.isoformat()
            # All-day event - return the date
            if event.end.date:
                return event.end.date
        return None
    
    def get_pending(self, user_id: str) -> Optional[PendingEdit]:
        """
        Get pending edit/delete for user, or None if expired/not found.
        
        Args:
            user_id: User identifier
        
        Returns:
            PendingEdit if exists and not expired, None otherwise
        """
        user_id = str(user_id)
        
        if user_id not in self._pending:
            return None
        
        pending = self._pending[user_id]
        
        # Check expiration
        if pending.is_expired():
            # Clean up expired entry
            del self._pending[user_id]
            logger.info(f"Pending edit expired for user {user_id[:8]}")
            return None
        
        return pending
    
    def select_event(
        self,
        user_id: str,
        index: int,
    ) -> Optional[PendingEdit]:
        """
        Select an event from the matching events list.
        
        Args:
            user_id: User identifier
            index: 1-based index of the event to select
        
        Returns:
            Updated PendingEdit, or None if not found/expired/invalid index
        """
        pending = self.get_pending(user_id)
        if not pending:
            return None
        
        if pending.state != PendingState.AWAITING_SELECTION:
            logger.warning(f"Cannot select event in state {pending.state}")
            return None
        
        # Validate index (1-based)
        if index < 1 or index > len(pending.matching_events):
            logger.warning(f"Invalid event index {index}, have {len(pending.matching_events)} events")
            return None
        
        # Select the event
        pending.selected_index = index
        pending.selected_event = pending.matching_events[index - 1]
        pending.state = PendingState.AWAITING_CONFIRMATION
        
        logger.info(
            f"Selected event {index} for user",
            extra={
                "user_id": str(user_id)[:8],
                "selected_event": pending.selected_event.summary,
            }
        )
        
        return pending
    
    def update_changes(
        self,
        user_id: str,
        changes: Dict[str, Any],
    ) -> Optional[PendingEdit]:
        """
        Update or add changes to a pending edit operation.
        
        Args:
            user_id: User identifier
            changes: Dictionary of field changes
        
        Returns:
            Updated PendingEdit, or None if not found/expired
        """
        pending = self.get_pending(user_id)
        if not pending:
            return None
        
        if pending.operation != PendingOperationType.EDIT:
            logger.warning("Cannot update changes on delete operation")
            return None
        
        # Merge changes
        if pending.changes is None:
            pending.changes = {}
        pending.changes.update(changes)
        
        logger.info(
            f"Updated changes for pending edit",
            extra={
                "user_id": str(user_id)[:8],
                "change_fields": list(changes.keys()),
            }
        )
        
        return pending
    
    async def confirm_pending(self, user_id: str) -> Optional[PendingEdit]:
        """
        Confirm and remove pending edit/delete.
        
        Call this when user confirms the operation.
        Returns the pending details for executing via API.
        
        Args:
            user_id: User identifier
        
        Returns:
            The PendingEdit (for execution), or None if not found/expired/not ready
        """
        pending = self.get_pending(user_id)
        if not pending:
            return None
        
        if not pending.is_ready_for_confirmation():
            logger.warning(f"Pending not ready for confirmation in state {pending.state}")
            return None
        
        # Update state and remove from pending
        pending.state = PendingState.CONFIRMED
        del self._pending[str(user_id)]
        
        logger.info(
            f"Confirmed pending {pending.operation.value}",
            extra={
                "user_id": str(user_id)[:8],
                "event": pending.selected_event.summary if pending.selected_event else None,
            }
        )
        
        return pending
    
    def cancel_pending(self, user_id: str) -> bool:
        """
        Cancel and remove pending edit/delete.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if operation was found and cancelled, False otherwise
        """
        user_id = str(user_id)
        
        if user_id in self._pending:
            pending = self._pending[user_id]
            pending.state = PendingState.CANCELLED
            del self._pending[user_id]
            logger.info(f"Cancelled pending {pending.operation.value} for user {user_id[:8]}")
            return True
        
        return False
    
    def is_expired(self, user_id: str) -> bool:
        """
        Check if user's pending edit has expired.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if no pending edit or if it has expired
        """
        user_id = str(user_id)
        
        if user_id not in self._pending:
            return True
        
        return self._pending[user_id].is_expired()
    
    def has_pending(self, user_id: str) -> bool:
        """
        Check if user has a non-expired pending edit/delete.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if user has a pending operation that hasn't expired
        """
        return self.get_pending(user_id) is not None
    
    def has_pending_edit(self, user_id: str) -> bool:
        """Check if user has a pending edit (not delete)."""
        pending = self.get_pending(user_id)
        return pending is not None and pending.operation == PendingOperationType.EDIT
    
    def has_pending_delete(self, user_id: str) -> bool:
        """Check if user has a pending delete (not edit)."""
        pending = self.get_pending(user_id)
        return pending is not None and pending.operation == PendingOperationType.DELETE
    
    # -------------------------------------------------------------------------
    # CLEANUP
    # -------------------------------------------------------------------------
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Call this periodically or before operations to prevent memory leaks.
        
        Returns:
            Number of entries removed
        """
        now = datetime.now(tz.utc)
        expired_users = [
            user_id for user_id, pending in self._pending.items()
            if now > pending.expires_at
        ]
        
        for user_id in expired_users:
            del self._pending[user_id]
        
        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired pending edits")
        
        return len(expired_users)
    
    async def start_cleanup_loop(self, interval_seconds: int = 30):
        """
        Start background task to cleanup expired entries periodically.
        
        Args:
            interval_seconds: How often to run cleanup (default 30s)
        """
        if self._cleanup_task is not None:
            logger.warning("Cleanup loop already running")
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    self.cleanup_expired()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cleanup loop error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started cleanup loop (interval: {interval_seconds}s)")
    
    async def stop_cleanup_loop(self):
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped cleanup loop")
    
    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    
    def get_pending_count(self) -> int:
        """Get the count of non-expired pending edits."""
        self.cleanup_expired()
        return len(self._pending)
    
    def clear_all(self):
        """Clear all pending edits. Use for testing only."""
        self._pending.clear()
        logger.warning("Cleared all pending edits")


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance to use throughout the application.
# This ensures all requests share the same pending edit storage.
#
# Usage: from app.services.pending_edit_service import pending_edit_service
pending_edit_service = PendingEditService()
