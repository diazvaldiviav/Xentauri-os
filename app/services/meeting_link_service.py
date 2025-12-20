"""
Meeting Link Service - Links Google Docs to Calendar Events.

Sprint 3.9: Google Docs Intelligence

This service provides the bridge between calendar events and documents:
- Find events matching a query
- Get linked documents from events
- Link documents to events (via extended properties)
- Extract doc URLs from meeting descriptions

The calendar is the single source of truth for meeting-document relationships.

Usage:
======
    from app.services.meeting_link_service import meeting_link_service
    
    # Find a meeting and get its linked doc
    result = await meeting_link_service.find_meeting_with_doc(
        query="3pm meeting",
        user_id=user.id,
        db=db,
    )
    
    if result.doc_id:
        # Fetch and summarize the doc
        ...
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.oauth_credential import OAuthCredential
from app.environments.google.calendar import GoogleCalendarClient, CalendarEvent
from app.environments.google.docs import GoogleDocsClient
from app.environments.base import APIError
from app.services.calendar_search_service import calendar_search_service, SmartSearchResult


logger = logging.getLogger("jarvis.services.meeting_link")


# ---------------------------------------------------------------------------
# RESULT DATACLASSES
# ---------------------------------------------------------------------------

@dataclass
class MeetingDocResult:
    """Result of finding a meeting with linked document."""
    found: bool
    event: Optional[CalendarEvent] = None
    doc_id: Optional[str] = None
    doc_ids: Optional[List[str]] = None  # Multiple docs if any
    meet_link: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def has_linked_doc(self) -> bool:
        """Check if the meeting has a linked document."""
        return self.doc_id is not None or (self.doc_ids is not None and len(self.doc_ids) > 0)


@dataclass
class LinkDocResult:
    """Result of linking a document to an event."""
    success: bool
    event_id: Optional[str] = None
    doc_id: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# ERROR MESSAGES (from Error Handling Matrix)
# ---------------------------------------------------------------------------
ERROR_NO_LINKED_DOC = "This meeting doesn't have a linked document."
ERROR_NO_MEETING_FOUND = "I couldn't find that meeting. Please try a different search."
ERROR_MULTIPLE_MEETINGS = "I found multiple meetings matching that. Please be more specific."


# ---------------------------------------------------------------------------
# SERVICE CLASS
# ---------------------------------------------------------------------------

class MeetingLinkService:
    """
    Service for linking documents to calendar events.
    
    This service:
    1. Uses calendar search to find events
    2. Extracts linked document IDs from events
    3. Can link documents to events via extended properties
    """
    
    def __init__(self):
        """Initialize the meeting link service."""
        logger.info("Meeting link service initialized")
    
    async def find_meeting_with_doc(
        self,
        query: str,
        user_id: UUID,
        db: Session,
        date_filter: Optional[str] = None,
    ) -> MeetingDocResult:
        """
        Find a meeting matching the query and get its linked documents.
        
        Uses semantic search to find the meeting, then extracts any
        linked document IDs from the event.
        
        Args:
            query: Search query for the meeting (e.g., "3pm meeting", "standup")
            user_id: User's UUID
            db: Database session
            date_filter: Optional date filter (e.g., "today", "tomorrow")
        
        Returns:
            MeetingDocResult with event and document info
        """
        logger.info(f"Finding meeting with doc for query: '{query}'")
        
        # Step 1: Search for the meeting
        try:
            search_result = await calendar_search_service.smart_search(
                user_query=query,
                user_id=user_id,
                db=db,
                max_events=10,  # Limit to recent/relevant events
            )
        except Exception as e:
            logger.error(f"Calendar search failed: {e}")
            return MeetingDocResult(
                found=False,
                error=f"Failed to search calendar: {str(e)}",
            )
        
        # Step 2: Check if we found events
        if search_result.no_match_found or not search_result.events:
            return MeetingDocResult(
                found=False,
                error=ERROR_NO_MEETING_FOUND,
            )
        
        # Step 3: Get the first matching event
        # (for multiple matches, the search service already ranks them)
        event = search_result.events[0]
        
        # Step 4: Extract document IDs from the event
        doc_ids = event.get_all_linked_doc_ids()
        doc_id = doc_ids[0] if doc_ids else None
        
        # Step 5: Get Meet link if available
        meet_link = event.get_meet_link()
        
        # If no linked doc, return with helpful message
        if not doc_id:
            return MeetingDocResult(
                found=True,
                event=event,
                doc_id=None,
                doc_ids=[],
                meet_link=meet_link,
                error=ERROR_NO_LINKED_DOC,
            )
        
        return MeetingDocResult(
            found=True,
            event=event,
            doc_id=doc_id,
            doc_ids=doc_ids,
            meet_link=meet_link,
        )
    
    async def get_meeting_by_time(
        self,
        time_reference: str,
        user_id: UUID,
        db: Session,
    ) -> MeetingDocResult:
        """
        Find a meeting by time reference.
        
        Handles queries like:
        - "my 3pm meeting"
        - "the 2 o'clock"
        - "my next meeting"
        
        Args:
            time_reference: Time reference string
            user_id: User's UUID
            db: Database session
        
        Returns:
            MeetingDocResult with event and document info
        """
        # This uses the same search logic but focuses on time
        return await self.find_meeting_with_doc(
            query=time_reference,
            user_id=user_id,
            db=db,
        )
    
    async def get_linked_doc(
        self,
        event_id: str,
        user_id: UUID,
        db: Session,
    ) -> Optional[str]:
        """
        Get the linked document ID for a specific event.
        
        Args:
            event_id: Google Calendar event ID
            user_id: User's UUID
            db: Database session
        
        Returns:
            Document ID if linked, None otherwise
        """
        # Get user's Google credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            logger.warning(f"No Google credentials for user {user_id}")
            return None
        
        # Fetch the specific event
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            # Note: This would need a get_event() method on the calendar client
            # For now, we rely on the events from search
            return None
        except Exception as e:
            logger.error(f"Failed to fetch event: {e}")
            return None
    
    def extract_doc_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract a Google Doc ID from a URL.
        
        Args:
            url: URL that might be a Google Doc
        
        Returns:
            Document ID if valid, None otherwise
        """
        if not GoogleDocsClient.validate_doc_url(url):
            return None
        
        try:
            return GoogleDocsClient.extract_doc_id(url)
        except APIError:
            return None
    
    async def find_events_with_docs(
        self,
        user_id: UUID,
        db: Session,
        days_ahead: int = 7,
    ) -> List[MeetingDocResult]:
        """
        Find all upcoming events that have linked documents.
        
        Args:
            user_id: User's UUID
            db: Database session
            days_ahead: How many days to look ahead
        
        Returns:
            List of MeetingDocResult for events with docs
        """
        # Get user's Google credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            logger.warning(f"No Google credentials for user {user_id}")
            return []
        
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            
            time_min = datetime.now(timezone.utc)
            time_max = time_min + timedelta(days=days_ahead)
            
            events = await calendar_client.list_upcoming_events(
                max_results=50,
                time_min=time_min,
                time_max=time_max,
            )
            
            results = []
            for event in events:
                doc_ids = event.get_all_linked_doc_ids()
                if doc_ids:
                    results.append(MeetingDocResult(
                        found=True,
                        event=event,
                        doc_id=doc_ids[0],
                        doc_ids=doc_ids,
                        meet_link=event.get_meet_link(),
                    ))
            
            return results
        
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return []


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

meeting_link_service = MeetingLinkService()
