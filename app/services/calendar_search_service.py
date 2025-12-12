"""
Calendar Search Service - Smart semantic search for calendar events.

Sprint 3.9: Smart Calendar Search with LLM Semantic Matching

This service provides intelligent calendar event search that handles:
- Typos: "birday" matches "birthday" or "Cumpleaños"
- Translations: "anniversary" matches "aniversario"
- Synonyms: "bday" matches "birthday"

Architecture:
=============
1. Fetch ALL calendar events for time range (next 365 days)
2. Send events + user query to OpenAI GPT for semantic matching
3. GPT returns matched events (handles typos, translations, synonyms)
4. Return only matched events

Usage:
======
    from app.services.calendar_search_service import calendar_search_service
    
    events = await calendar_search_service.smart_search(
        user_query="birday",
        user_id=user.id,
        db=db_session,
    )
    # Returns: [CalendarEvent("Cumpleaños de Victor")]
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.oauth_credential import OAuthCredential
from app.environments.google.calendar.client import GoogleCalendarClient
from app.environments.google.calendar.schemas import CalendarEvent
from app.environments.base import APIError
from app.ai.providers.openai_provider import openai_provider
from app.ai.prompts.calendar_search_prompts import build_matcher_prompt


logger = logging.getLogger("jarvis.services.calendar_search")


@dataclass
class SmartSearchResult:
    """Result of a smart calendar search."""
    events: List[CalendarEvent]
    corrected_query: Optional[str] = None
    no_match_found: bool = False
    error: Optional[str] = None


class CalendarSearchService:
    """
    Service for semantic calendar event search using LLM matching.
    
    This service fetches all calendar events and uses GPT to intelligently
    match them against user queries, handling typos, translations, and synonyms.
    """
    
    def __init__(self):
        """Initialize the calendar search service."""
        logger.info("Calendar search service initialized")
    
    async def smart_search(
        self,
        user_query: str,
        user_id: UUID,
        db: Session,
        max_events: int = 100,
        days_ahead: int = 365,
    ) -> SmartSearchResult:
        """
        Perform semantic search on calendar events using LLM matching.
        
        Args:
            user_query: The user's search query (may contain typos, translations)
            user_id: The user's UUID
            db: Database session
            max_events: Maximum events to fetch from calendar
            days_ahead: How many days ahead to search
        
        Returns:
            SmartSearchResult with matched events
        
        Example:
            result = await service.smart_search("birday", user_id, db)
            # result.events contains events matching "birthday" in any language
        """
        query = user_query.strip()
        if not query:
            return SmartSearchResult(events=[], no_match_found=True)
        
        logger.info(f"Smart search for query: '{query}' for user {user_id}")
        
        # Step 1: Get user's OAuth credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            logger.warning(f"No Google credentials for user {user_id}")
            return SmartSearchResult(
                events=[],
                error="Google Calendar not connected. Please connect your Google account.",
            )
        
        # Step 2: Create calendar client and fetch all events
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            
            # Fetch events for the next N days
            time_min = datetime.now(timezone.utc)
            time_max = time_min + timedelta(days=days_ahead)
            
            all_events = await calendar_client.list_upcoming_events(
                max_results=max_events,
                time_min=time_min,
                time_max=time_max,
            )
            
            logger.info(f"Fetched {len(all_events)} events for semantic matching")
            
        except APIError as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return SmartSearchResult(
                events=[],
                error=f"Failed to fetch calendar: {str(e)}",
            )
        
        # Step 3: If no events, return early
        if not all_events:
            return SmartSearchResult(
                events=[],
                no_match_found=True,
                corrected_query=query,
            )
        
        # Step 4: Use LLM for semantic matching
        try:
            matched_events = await self._match_events_with_llm(
                query=query,
                events=all_events,
            )
            
            return matched_events
            
        except Exception as e:
            logger.error(f"LLM matching failed: {e}", exc_info=True)
            # Fallback: return empty result rather than crashing
            return SmartSearchResult(
                events=[],
                error=f"Search matching failed: {str(e)}",
            )
    
    async def _match_events_with_llm(
        self,
        query: str,
        events: List[CalendarEvent],
    ) -> SmartSearchResult:
        """
        Use OpenAI GPT to semantically match query to events.
        
        Args:
            query: User's search query
            events: List of calendar events to match against
        
        Returns:
            SmartSearchResult with matched events
        """
        # Build the prompt
        prompt = build_matcher_prompt(query, events)
        
        # Call OpenAI
        response = await openai_provider.generate_json(
            prompt=prompt,
            system_prompt="You are a calendar event matcher. Return only valid JSON.",
        )
        
        if not response.success:
            logger.error(f"OpenAI request failed: {response.error}")
            return SmartSearchResult(
                events=[],
                error=f"Search service unavailable: {response.error}",
            )
        
        # Parse the LLM response
        try:
            result_data = json.loads(response.content)
            
            matched_titles = set()
            corrected_query = result_data.get("corrected_query", query)
            no_match_found = result_data.get("no_match_found", False)
            
            # Extract matched event titles
            for match in result_data.get("matched_events", []):
                title = match.get("event_title", "")
                confidence = match.get("confidence", 0)
                
                if title and confidence >= 0.50:
                    matched_titles.add(title.lower())
                    logger.debug(
                        f"LLM matched: '{title}' with confidence {confidence:.2f}"
                    )
            
            # Filter original events by matched titles
            matched_events = []
            for event in events:
                event_title = event.get_display_title().lower()
                
                # Check if this event's title matches any LLM-identified titles
                if event_title in matched_titles:
                    matched_events.append(event)
                else:
                    # Also check for partial matches (LLM might return shorter titles)
                    for matched_title in matched_titles:
                        if matched_title in event_title or event_title in matched_title:
                            matched_events.append(event)
                            break
            
            logger.info(
                f"Smart search matched {len(matched_events)} events "
                f"for query '{query}' (corrected: '{corrected_query}')"
            )
            
            return SmartSearchResult(
                events=matched_events,
                corrected_query=corrected_query,
                no_match_found=len(matched_events) == 0,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response.content}")
            return SmartSearchResult(
                events=[],
                error="Failed to parse search results",
            )
    
    async def smart_search_with_date(
        self,
        user_query: str,
        user_id: UUID,
        db: Session,
        date: str,
    ) -> SmartSearchResult:
        """
        Perform semantic search scoped to a specific date.
        
        Args:
            user_query: The user's search query
            user_id: The user's UUID
            db: Database session
            date: Date in YYYY-MM-DD format
        
        Returns:
            SmartSearchResult with matched events for that date
        """
        query = user_query.strip()
        if not query:
            return SmartSearchResult(events=[], no_match_found=True)
        
        logger.info(f"Smart search for '{query}' on date {date}")
        
        # Get credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            return SmartSearchResult(
                events=[],
                error="Google Calendar not connected.",
            )
        
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            
            # Parse the date
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return SmartSearchResult(
                    events=[],
                    error=f"Invalid date format: {date}",
                )
            
            # Fetch events for that specific date
            day_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_events = await calendar_client.list_upcoming_events(
                max_results=50,
                time_min=day_start,
                time_max=day_end,
            )
            
            if not day_events:
                return SmartSearchResult(
                    events=[],
                    no_match_found=True,
                    corrected_query=query,
                )
            
            # Use LLM for semantic matching
            return await self._match_events_with_llm(query, day_events)
            
        except APIError as e:
            logger.error(f"Calendar API error: {e}")
            return SmartSearchResult(
                events=[],
                error=str(e),
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
calendar_search_service = CalendarSearchService()
