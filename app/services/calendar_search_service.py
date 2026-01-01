"""
Calendar Search Service - Smart semantic search for calendar events.

Sprint 3.9: Smart Calendar Search with LLM Semantic Matching
Sprint 4.1: Consolidated smart_search with date_range parameter (DRY fix)

This service provides intelligent calendar event search that handles:
- Typos: "birday" matches "birthday" or "Cumpleaños"
- Translations: "anniversary" matches "aniversario"
- Synonyms: "bday" matches "birthday"
- Date filtering: "today", "tomorrow", "this_week", or search all

Architecture:
=============
1. Fetch calendar events for specified time range (or next 365 days by default)
2. Send events + user query to OpenAI GPT for semantic matching
3. GPT returns matched events (handles typos, translations, synonyms)
4. Return only matched events

Usage:
======
    from app.services.calendar_search_service import calendar_search_service
    
    # Search all upcoming events
    events = await calendar_search_service.smart_search("birday", user_id, db)
    
    # Search only today
    events = await calendar_search_service.smart_search("meeting", user_id, db, date_range="today")
    
    # Search this week
    events = await calendar_search_service.smart_search("reunion", user_id, db, date_range="this_week")
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
    
    This service fetches calendar events and uses GPT to intelligently
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
        date_range: Optional[str] = None,
        max_events: int = 100,
        days_ahead: int = 365,
    ) -> SmartSearchResult:
        """
        Perform semantic search on calendar events using LLM matching.
        
        Sprint 4.1: Consolidated method with date_range support.
        
        Args:
            user_query: The user's search query (may contain typos, translations)
            user_id: The user's UUID
            db: Database session
            date_range: Optional date filter ("today", "tomorrow", "this_week", None=all)
            max_events: Maximum events to fetch from calendar
            days_ahead: How many days ahead to search (only used if date_range=None)
        
        Returns:
            SmartSearchResult with matched events
        
        Examples:
            # Search all upcoming events
            result = await service.smart_search("birthday", user_id, db)
            
            # Search only today
            result = await service.smart_search("meeting", user_id, db, date_range="today")
            
            # Search this week
            result = await service.smart_search("reunion", user_id, db, date_range="this_week")
        """
        query = user_query.strip()
        if not query:
            return SmartSearchResult(events=[], no_match_found=True)
        
        logger.info(f"Smart search for query: '{query}' for user {user_id}, date_range={date_range}")
        
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
        
        # Step 2: Create calendar client and fetch events
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            
            # Determine time range based on date_range parameter
            if date_range:
                # Use calendar client's date parsing for proper timezone handling
                user_timezone = await calendar_client.get_user_timezone("primary")
                time_min, time_max = calendar_client._parse_date_range(date_range, user_timezone)
                logger.info(f"Date range '{date_range}' parsed to: {time_min} - {time_max}")
            else:
                # No date filter - search from start of today to include past events
                # Sprint 5.1.1: Start from midnight today so we can edit/delete past events
                now = datetime.now(timezone.utc)
                time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
                time_max = now + timedelta(days=days_ahead)
            
            # Fetch events for the time range
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
            
            # Log LLM response for debugging
            logger.info(f"LLM response: matched_events={result_data.get('matched_events', [])}, no_match={no_match_found}")
            
            # Sprint 5.1.1: Normalize accents for matching (reunión = reunion)
            import unicodedata
            def normalize_text(text: str) -> str:
                """Remove accents and normalize text for comparison."""
                normalized = unicodedata.normalize('NFD', text.lower().strip())
                return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

            # Extract matched event titles
            for match in result_data.get("matched_events", []):
                title = match.get("event_title", "")
                confidence = match.get("confidence", 0)

                if title and confidence >= 0.50:
                    matched_titles.add(normalize_text(title))
                    logger.info(
                        f"LLM matched: '{title}' with confidence {confidence:.2f}"
                    )

            # Filter original events by matched titles
            matched_events = []
            for event in events:
                event_title_normalized = normalize_text(event.get_display_title())

                # Check if this event's title matches any LLM-identified titles
                if event_title_normalized in matched_titles:
                    matched_events.append(event)
                else:
                    # Also check for partial matches (LLM might return shorter titles)
                    for matched_title in matched_titles:
                        if matched_title in event_title_normalized or event_title_normalized in matched_title:
                            matched_events.append(event)
                            break
            
            # IMPORTANT: If query exactly matches an event title, include it!
            # This handles cases where user types the exact event name
            query_normalized = normalize_text(query)
            for event in events:
                event_title = event.get_display_title()
                event_normalized = normalize_text(event_title)
                if query_normalized == event_normalized or query_normalized in event_normalized or event_normalized in query_normalized:
                    if event not in matched_events:
                        logger.info(f"Added exact/partial match: '{event_title}' for query '{query}' (normalized: {query_normalized} vs {event_normalized})")
                        matched_events.append(event)
            
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


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
calendar_search_service = CalendarSearchService()
