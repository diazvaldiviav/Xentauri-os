"""
Pending Event Service - Manages pending calendar events during confirmation flow.

Sprint 3.8: Calendar Event Creation with Confirmation Flow

This service manages the state of pending calendar events that are awaiting
user confirmation. Events expire after 120 seconds if not confirmed.

Design follows pairing.py pattern for consistency:
- In-memory storage with TTL
- Singleton instance
- Cleanup on operations

Flow:
1. User says "schedule meeting tomorrow at 6 pm"
2. Service stores pending event (120s TTL - Sprint 3.9.1)
3. User can confirm ("yes"), cancel ("no"), or edit ("change time to 7 pm")
4. On confirm: event is created via Google Calendar API
5. On cancel/timeout: pending event is removed

Usage:
    from app.services.pending_event_service import pending_event_service
    
    # Store a pending event
    pending = await pending_event_service.store_pending(
        user_id="user-123",
        event_title="Meeting",
        event_date=date(2025, 1, 15),
        event_time="18:00",
        timezone="America/New_York",
    )
    
    # Check for pending
    pending = pending_event_service.get_pending("user-123")
    
    # Confirm and get event
    pending = await pending_event_service.confirm_pending("user-123")
    
    # Or cancel
    pending_event_service.cancel_pending("user-123")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone as tz
from typing import Optional, Dict, Any
from uuid import UUID


logger = logging.getLogger("jarvis.services.pending_event")


@dataclass
class PendingEvent:
    """
    Pending event awaiting user confirmation.
    
    Stores all event details extracted from the user's request,
    plus metadata for the confirmation flow.
    """
    # User identification
    user_id: str
    
    # Event details
    event_title: str
    event_date: Optional[date] = None
    event_time: Optional[str] = None  # "18:00" format
    duration_minutes: int = 60
    is_all_day: bool = False
    location: Optional[str] = None
    recurrence: Optional[str] = None  # RRULE string
    
    # Timezone
    timezone: str = "UTC"
    
    # Tracking
    created_at: datetime = field(default_factory=lambda: datetime.now(tz.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(tz.utc) + timedelta(seconds=60))
    original_text: str = ""
    
    def is_expired(self) -> bool:
        """Check if this pending event has expired."""
        return datetime.now(tz.utc) > self.expires_at
    
    def get_end_time(self) -> Optional[str]:
        """Calculate end time based on start time and duration."""
        if not self.event_time or self.is_all_day:
            return None
        
        try:
            # Parse start time
            parts = self.event_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            
            # Add duration
            total_minutes = hour * 60 + minute + self.duration_minutes
            end_hour = (total_minutes // 60) % 24
            end_minute = total_minutes % 60
            
            return f"{end_hour:02d}:{end_minute:02d}"
        except (ValueError, IndexError):
            return None
    
    def get_start_datetime(self) -> Optional[datetime]:
        """Get the full start datetime combining date and time."""
        if not self.event_date:
            return None
        
        if self.is_all_day or not self.event_time:
            return datetime.combine(self.event_date, datetime.min.time())
        
        try:
            parts = self.event_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return datetime.combine(self.event_date, datetime.min.time().replace(hour=hour, minute=minute))
        except (ValueError, IndexError):
            return datetime.combine(self.event_date, datetime.min.time())
    
    def get_end_datetime(self) -> Optional[datetime]:
        """Get the full end datetime."""
        start = self.get_start_datetime()
        if not start:
            return None
        
        if self.is_all_day:
            # All-day events end the next day
            return start + timedelta(days=1)
        
        return start + timedelta(minutes=self.duration_minutes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "user_id": self.user_id,
            "event_title": self.event_title,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "event_time": self.event_time,
            "duration_minutes": self.duration_minutes,
            "is_all_day": self.is_all_day,
            "location": self.location,
            "recurrence": self.recurrence,
            "timezone": self.timezone,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired(),
        }


class PendingEventService:
    """
    Service for managing pending calendar events with 120s TTL.
    
    This class handles the confirmation flow for calendar event creation:
    - Store pending events with TTL
    - Retrieve pending events
    - Update pending event fields
    - Confirm or cancel pending events
    - Automatic cleanup of expired events
    
    Thread-safety note: For MVP, this is acceptable.
    In production with multiple workers, use Redis instead.
    
    Note: TTL increased from 60s to 120s (Sprint 3.9.1) to give users more time
    to confirm operations, especially when they need to think or clarify details.
    """
    
    # TTL in seconds (120 seconds for confirmation timeout - Sprint 3.9.1)
    TTL_SECONDS = 120
    
    def __init__(self):
        """Initialize the pending event service."""
        # In-memory storage: user_id -> PendingEvent
        self._pending: Dict[str, PendingEvent] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info("Pending event service initialized")
    
    # -------------------------------------------------------------------------
    # CORE OPERATIONS
    # -------------------------------------------------------------------------
    
    async def store_pending(
        self,
        user_id: str,
        event_title: str,
        event_date: Optional[date] = None,
        event_time: Optional[str] = None,
        duration_minutes: int = 60,
        is_all_day: bool = False,
        location: Optional[str] = None,
        recurrence: Optional[str] = None,
        timezone: str = "UTC",
        original_text: str = "",
    ) -> PendingEvent:
        """
        Store a pending event for user.
        
        Overwrites any existing pending event for this user.
        Each user can only have one pending event at a time.
        
        Args:
            user_id: User identifier (UUID as string)
            event_title: Title/summary of the event
            event_date: Date of the event
            event_time: Time in "HH:MM" format (24-hour)
            duration_minutes: Duration in minutes (default 60)
            is_all_day: True for all-day events
            location: Event location (optional)
            recurrence: RRULE string for recurring events
            timezone: Timezone string (e.g., "America/New_York")
            original_text: Original user request text
        
        Returns:
            The stored PendingEvent
        """
        # Clean up expired entries first
        self.cleanup_expired()
        
        # Create the pending event
        now = datetime.now(tz.utc)
        pending = PendingEvent(
            user_id=str(user_id),
            event_title=event_title,
            event_date=event_date,
            event_time=event_time,
            duration_minutes=duration_minutes,
            is_all_day=is_all_day,
            location=location,
            recurrence=recurrence,
            timezone=timezone,
            created_at=now,
            expires_at=now + timedelta(seconds=self.TTL_SECONDS),
            original_text=original_text,
        )
        
        # Store (overwrites any existing)
        self._pending[str(user_id)] = pending
        
        logger.info(
            f"Stored pending event for user",
            extra={
                "user_id": str(user_id)[:8],
                "event_title": event_title,
                "expires_in": self.TTL_SECONDS,
            }
        )
        
        return pending
    
    def get_pending(self, user_id: str) -> Optional[PendingEvent]:
        """
        Get pending event for user, or None if expired/not found.
        
        Args:
            user_id: User identifier
        
        Returns:
            PendingEvent if exists and not expired, None otherwise
        """
        user_id = str(user_id)
        
        if user_id not in self._pending:
            return None
        
        pending = self._pending[user_id]
        
        # Check expiration
        if pending.is_expired():
            # Clean up expired entry
            del self._pending[user_id]
            logger.info(f"Pending event expired for user {user_id[:8]}")
            return None
        
        return pending
    
    def update_pending(
        self,
        user_id: str,
        field: str,
        value: Any,
    ) -> Optional[PendingEvent]:
        """
        Update a field on pending event.
        
        Args:
            user_id: User identifier
            field: Field name to update
            value: New value for the field
        
        Returns:
            Updated PendingEvent, or None if not found/expired
        
        Raises:
            ValueError: If field is not editable
        """
        pending = self.get_pending(user_id)
        if not pending:
            return None
        
        # Editable fields
        editable_fields = {
            "event_title",
            "event_date",
            "event_time",
            "duration_minutes",
            "is_all_day",
            "location",
            "recurrence",
        }
        
        if field not in editable_fields:
            raise ValueError(f"Field '{field}' is not editable. Editable fields: {editable_fields}")
        
        # Update the field
        setattr(pending, field, value)
        
        logger.info(
            f"Updated pending event field",
            extra={
                "user_id": str(user_id)[:8],
                "field": field,
                "value": str(value)[:50],
            }
        )
        
        return pending
    
    async def confirm_pending(self, user_id: str) -> Optional[PendingEvent]:
        """
        Confirm and remove pending event.
        
        Call this when user confirms the event creation.
        Returns the event details for creating via API.
        
        Args:
            user_id: User identifier
        
        Returns:
            The PendingEvent (for creation), or None if not found/expired
        """
        pending = self.get_pending(user_id)
        if not pending:
            return None
        
        # Remove from pending (consume)
        del self._pending[str(user_id)]
        
        logger.info(
            f"Confirmed pending event",
            extra={
                "user_id": str(user_id)[:8],
                "event_title": pending.event_title,
            }
        )
        
        return pending
    
    def cancel_pending(self, user_id: str) -> bool:
        """
        Cancel and remove pending event.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if event was found and cancelled, False otherwise
        """
        user_id = str(user_id)
        
        if user_id in self._pending:
            del self._pending[user_id]
            logger.info(f"Cancelled pending event for user {user_id[:8]}")
            return True
        
        return False
    
    def is_expired(self, user_id: str) -> bool:
        """
        Check if user's pending event has expired.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if no pending event or if it has expired
        """
        user_id = str(user_id)
        
        if user_id not in self._pending:
            return True
        
        return self._pending[user_id].is_expired()
    
    def has_pending(self, user_id: str) -> bool:
        """
        Check if user has a non-expired pending event.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if user has a pending event that hasn't expired
        """
        return self.get_pending(user_id) is not None
    
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
            logger.info(f"Cleaned up {len(expired_users)} expired pending events")
        
        return len(expired_users)
    
    async def start_cleanup_loop(self, interval_seconds: int = 30):
        """
        Start background task to cleanup expired events periodically.
        
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
        """Get the count of non-expired pending events."""
        self.cleanup_expired()
        return len(self._pending)
    
    def clear_all(self):
        """Clear all pending events. Use for testing only."""
        self._pending.clear()
        logger.warning("Cleared all pending events")


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance to use throughout the application.
# This ensures all requests share the same pending event storage.
#
# Usage: from app.services.pending_event_service import pending_event_service
pending_event_service = PendingEventService()
