"""
Calendar Handler - Handles all calendar-related intents.

This handler is responsible for:
- Calendar queries (find_event, next_event, count_events, list_events)
- Calendar event creation with confirmation flow
- Calendar event editing and deletion with confirmation flow

Sprint US-3.1: Extracted from IntentService
Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import time
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import (
    CalendarQueryIntent,
    CalendarCreateIntent,
    CalendarEditIntent,
    ActionType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.services.pending_event_service import PendingEvent
    from app.environments.google.calendar.schemas import EventCreateResponse


logger = logging.getLogger("jarvis.services.intent_handlers.calendar")


class CalendarHandler(IntentHandler):
    """
    Handler for calendar-related intents.

    Handles:
    - CalendarQueryIntent: Questions about calendar events
    - CalendarCreateIntent: Event creation with confirmation flow
    - CalendarEditIntent: Event editing/deletion with confirmation flow

    State Machines:
    - CREATE: CREATE_EVENT -> PENDING -> CONFIRM/CANCEL/EDIT_PENDING
    - EDIT: EDIT_EXISTING -> AWAITING_CONFIRMATION/SELECTION -> CONFIRM/CANCEL
    - DELETE: DELETE_EXISTING -> AWAITING_CONFIRMATION/SELECTION -> CONFIRM/CANCEL
    """

    @property
    def handler_name(self) -> str:
        """Return the handler name for logging."""
        return "calendar"

    @property
    def supported_intent_types(self) -> List[str]:
        """Return list of supported intent types."""
        return ["calendar_query", "calendar_create", "calendar_edit"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The parsed intent object
            context: Handler context

        Returns:
            True if intent is CalendarQueryIntent, CalendarCreateIntent, or CalendarEditIntent
        """
        return isinstance(intent, (CalendarQueryIntent, CalendarCreateIntent, CalendarEditIntent))

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Process the calendar-related intent and return a result.

        Args:
            intent: The parsed intent object
            context: Handler context with user, devices, etc.

        Returns:
            IntentResult with processing outcome
        """
        self._log_entry(intent, context)

        try:
            if isinstance(intent, CalendarQueryIntent):
                result = await self._handle_calendar_query(intent, context)
            elif isinstance(intent, CalendarCreateIntent):
                result = await self._handle_calendar_create(intent, context)
            elif isinstance(intent, CalendarEditIntent):
                result = await self._handle_calendar_edit(intent, context)
            else:
                processing_time = (time.time() - context.start_time) * 1000
                result = IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Unsupported intent type for CalendarHandler",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            self._log_exit(context, success=result.success, processing_time_ms=result.processing_time_ms)
            return result

        except Exception as e:
            processing_time = (time.time() - context.start_time) * 1000
            logger.error(f"[{context.request_id}] CalendarHandler error: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error processing calendar intent: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    # -----------------------------------------------------------------------
    # CALENDAR QUERY HANDLER
    # -----------------------------------------------------------------------

    async def _handle_calendar_query(
        self,
        intent: CalendarQueryIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle calendar query intents - questions about calendar events.

        Sprint 3.8: Returns text answers to calendar questions like:
        - "How many events today?" -> count_events
        - "What's my next meeting?" -> next_event
        - "List my events for tomorrow" -> list_events
        - "When is my birthday?" -> find_event

        Sprint 3.9: Uses smart semantic search for typos/translations/synonyms.
        Sprint 4.1: Returns context-aware, multilingual responses.
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunion").
        """
        from app.models.oauth_credential import OAuthCredential
        from app.db.session import SessionLocal

        action = self._get_action_value(intent.action) or "count_events"
        date_range = intent.date_range
        search_term = intent.search_term

        # Sprint 5.1.4: Resolve anaphoric reference if no explicit search_term
        if not search_term and context.resolved_references:
            resolved_event = context.resolved_references.get("event")
            if resolved_event and resolved_event.get("title"):
                search_term = resolved_event["title"]
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved event from context: {search_term}"
                )

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Check for credentials first
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == context.user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    confidence=intent.confidence,
                    action=action,
                    message="Please connect your Google Calendar first to use calendar features.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Route to appropriate query method using SMART SEARCH (Sprint 4.1: multilingual)
            if action == "find_event":
                # Find a specific event (e.g., "when is my birthday?")
                message = await self._smart_find_event(
                    search_term=search_term,
                    context=context,
                    db=db,
                )
            elif action == "next_event":
                # Find the next event matching a term (e.g., "what's my next meeting?")
                message = await self._smart_next_event(
                    search_term=search_term,
                    context=context,
                    db=db,
                )
            elif action == "count_events":
                # Count events (e.g., "how many events today?")
                message = await self._smart_count_events(
                    date_range=date_range,
                    search_term=search_term,
                    context=context,
                    db=db,
                )
            elif action == "list_events":
                # List events (e.g., "list my events for tomorrow")
                message = await self._smart_list_events(
                    date_range=date_range,
                    search_term=search_term,
                    context=context,
                    db=db,
                )
            else:
                # Fallback to count
                message = await self._smart_count_events(
                    date_range=date_range,
                    search_term=search_term,
                    context=context,
                    db=db,
                )

            processing_time = (time.time() - context.start_time) * 1000

            # Sprint 4.3.0: Save calendar query response to conversation context
            from app.services.conversation_context_service import conversation_context_service
            conversation_context_service.add_conversation_turn(
                user_id=str(context.user_id),
                user_message=context.original_text,
                assistant_response=message,
                intent_type="calendar_query",
            )

            return IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_QUERY,
                confidence=intent.confidence,
                action=action,
                parameters={
                    "date_range": date_range,
                    "search_term": search_term,
                },
                message=message,
                response=message,  # Also set as AI response for conversational UI
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        except Exception as e:
            processing_time = (time.time() - context.start_time) * 1000
            logger.error(f"Calendar query failed: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                confidence=intent.confidence,
                action=action,
                message=f"I couldn't access your calendar: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )
        finally:
            if owns_db:
                db.close()

    # -----------------------------------------------------------------------
    # SMART CALENDAR QUERY HELPERS (Sprint 3.9 + Sprint 4.1 Multilingual)
    # -----------------------------------------------------------------------

    async def _generate_calendar_response(
        self,
        template_type: str,
        user_request: str,
        context: HandlerContext,
        db: "Session",
        **kwargs
    ) -> str:
        """
        Generate calendar response with FULL CONTEXT awareness and multilingual support.

        Sprint 4.1: Uses UnifiedContext to personalize responses based on:
        - User's name
        - Connected services
        - Device setup
        - Language preference (auto-detected from user_request)

        Args:
            template_type: Type of response (no_events, count, list, find, not_found, next)
            user_request: Original user request (for language detection)
            context: Handler context
            db: Database session
            **kwargs: Template-specific parameters

        Returns:
            Natural, context-aware response in user's language
        """
        from app.ai.providers.gemini import gemini_provider
        from app.ai.context import build_unified_context

        # Build context
        unified_context = await build_unified_context(user_id=context.user_id, db=db)

        # Build system prompt with context
        system_prompt = f"""You are Jarvis, {unified_context.user_name}'s intelligent assistant.

CRITICAL: ALWAYS respond in the SAME LANGUAGE the user is speaking.
- Spanish input -> Spanish output
- English input -> English output
- French input -> French output

USER SETUP:
- Name: {unified_context.user_name}
- Google Calendar: {"Connected" if unified_context.has_google_calendar else "Not connected"}
- Devices: {len(unified_context.online_devices)} online

Be natural, concise, and friendly. Respond in the user's language (1-3 sentences)."""

        # Build user prompt based on template type
        if template_type == "no_events":
            search_term = kwargs.get('search_term', 'any')
            period = kwargs.get('period', '')
            prompt = f'''User asked: "{user_request}"

They have NO events matching "{search_term}" {period}.

Respond naturally in the SAME language. Be encouraging.'''

        elif template_type == "count":
            count = kwargs.get('count', 0)
            search = kwargs.get('search_term', 'events')
            period = kwargs.get('period', '')

            # Sprint 4.3.3: ANTI-HALLUCINATION - Use strict templates to prevent number hallucination
            if count == 0:
                prompt = f'''User asked: "{user_request}"

FACT: Event count = 0 (ZERO)

You MUST respond with:
- Spanish: "No tienes eventos{' de ' + search if search else ''} {period}"
- English: "You have no {search + ' ' if search else ''}events {period}"

Use the EXACT number from FACT. DO NOT invent numbers. Respond in their language.'''
            elif count == 1:
                # If we have the event details, include them
                event = kwargs.get('event')
                if event:
                    title = event.get_display_title()
                    time_str = event.get_time_display()
                    prompt = f'''User asked: "{user_request}"

FACT: Event count = 1 (ONE)
FACT: Event title = "{title}"
FACT: Event time = {time_str}

You MUST respond with:
- Spanish: "Si, tienes 1 evento {period}: {title} a las {time_str}"
- English: "Yes, you have 1 event {period}: {title} at {time_str}"

Use EXACTLY 1 event. DO NOT say 100 or any other number. Respond in their language.'''
                else:
                    # Fallback if no event object provided
                    prompt = f'''User asked: "{user_request}"

FACT: Event count = 1 (ONE)

You MUST respond with:
- Spanish: "Si, tienes 1 evento{' de ' + search if search else ''} {period}"
- English: "Yes, you have 1 {search + ' ' if search else ''}event {period}"

Use EXACTLY the number 1. DO NOT say 100 or any other number. Respond in their language.'''
            else:
                # Sprint 4.3.3: Strict format for multiple events to prevent hallucination
                prompt = f'''User asked: "{user_request}"

FACT: Event count = {count}

You MUST respond with the EXACT count from FACT above:
- Spanish: "Si, tienes {count} eventos{' de ' + search if search else ''} {period}"
- English: "Yes, you have {count} {search + ' ' if search else ''}events {period}"

CRITICAL: Use EXACTLY {count}, not 100, not 10, EXACTLY {count}. Respond in their language.'''

        elif template_type == "list":
            events = kwargs.get('events', [])
            search = kwargs.get('search_term', '')
            period = kwargs.get('period', '')

            event_details = "\n".join([
                f"- {e.get_time_display()} - {e.get_display_title()}"
                for e in events[:10]
            ])

            showing_count = len(events[:10])
            total_count = len(events)

            prompt = f'''User asked: "{user_request}"

Here are their {search} events {period}:
{event_details}

Present this list with bullet points.
{f"Note: Showing {showing_count} of {total_count} total events" if total_count > 10 else ""}

Respond in the SAME language they asked in.'''

        elif template_type == "find":
            event = kwargs.get('event')
            title = event.get_display_title() if event else ''
            date_str = kwargs.get('date_str', '')
            time_str = kwargs.get('time_str', '')
            relative = kwargs.get('relative', '')

            prompt = f'''User asked: "{user_request}"

Their '{title}' event is on {date_str} at {time_str}{relative}.

Tell them when it is naturally. Respond in their language.'''

        elif template_type == "next":
            event = kwargs.get('event')
            title = event.get_display_title() if event else ''
            time_str = kwargs.get('time_str', '')
            relative = kwargs.get('relative', '')
            search_term = kwargs.get('search_term', '')

            prompt = f'''User asked: "{user_request}"

Their next {search_term if search_term else "event"} is '{title}' at {time_str} {relative}.

Tell them when it is naturally. Respond in their language.'''

        elif template_type == "not_found":
            search = kwargs.get('search_term', '')
            prompt = f'''User asked: "{user_request}"

Couldn't find any '{search}' events.

Tell them we couldn't find it. Be helpful and suggest they check the event name. Respond in their language.'''

        elif template_type == "need_search":
            prompt = f'''User asked: "{user_request}"

They need to specify what event they're looking for.

Ask them politely what event they want to find. Respond in their language.'''

        else:
            prompt = f'User said: "{user_request}"\n\nRespond helpfully in their language.'

        # Generate response with Gemini
        response = await gemini_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=500,  # Sprint 5.1.1: Increased for listing multiple events
        )

        # Validate "count" responses to prevent hallucination
        if template_type == "count" and response.success:
            count_value = kwargs.get('count', 0)
            response_text = response.content.strip()

            # Check if response contradicts the count
            if count_value == 0 and any(word in response_text.lower() for word in ['tienes', 'have', 'hay', 'there are']):
                # Response might be saying "you have X" when count is 0
                if not any(word in response_text.lower() for word in ['no ', 'zero', 'cero', 'ninguna', 'ningun']):
                    logger.warning(f"Count template hallucination detected: count={count_value}, response='{response_text[:50]}'")
                    # Override with explicit template
                    search_term = kwargs.get('search_term', 'eventos' if ('es' in user_request.lower() or 'n' in user_request) else 'events')
                    period = kwargs.get('period', '')
                    if 'es' in user_request.lower() or 'n' in user_request:
                        response.content = f"No tienes {search_term} {period}.".strip()
                    else:
                        response.content = f"You don't have any {search_term} {period}.".strip()

        return response.content.strip() if response.success else "I couldn't process that request."

    async def _smart_find_event(
        self,
        search_term: Optional[str],
        context: HandlerContext,
        db: "Session",
    ) -> str:
        """
        Find a specific event using smart semantic search.

        Sprint 4.1: Now returns context-aware, multilingual responses.

        Handles typos, translations, and synonyms:
        - "birthday" matches "Cumpleanos de Victor"
        - "birday" matches "Birthday party"
        - "cumpleanos" matches "Cumpleanos"
        """
        from app.services.calendar_search_service import calendar_search_service

        original_text = context.original_text

        if not search_term:
            return await self._generate_calendar_response(
                template_type="need_search",
                user_request=original_text or "find event",
                context=context,
                db=db,
            )

        # Use smart search for semantic matching
        result = await calendar_search_service.smart_search(
            user_query=search_term,
            user_id=context.user_id,
            db=db,
        )

        if result.error:
            return result.error

        if result.no_match_found or not result.events:
            corrected = result.corrected_query or search_term
            return await self._generate_calendar_response(
                template_type="not_found",
                user_request=original_text or search_term,
                context=context,
                db=db,
                search_term=corrected,
            )

        # Return the first (nearest) matching event
        event = result.events[0]
        title = event.get_display_title()

        # Sprint 3.9: Store event in conversation context for "this event" references
        self._store_event_context(str(context.user_id), event)

        # Format the date nicely
        start_dt = event.start.get_datetime() if event.start else None
        if start_dt:
            date_str = start_dt.strftime("%B %d, %Y")
            time_str = event.get_time_display()

            # Add relative context
            now = datetime.now(timezone.utc)

            # Ensure start_dt is timezone-aware for comparison
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)

            delta = start_dt - now

            if delta.days == 0:
                relative = " (today)"
            elif delta.days == 1:
                relative = " (tomorrow)"
            elif delta.days < 7:
                relative = f" ({start_dt.strftime('%A')})"
            elif delta.days < 30:
                relative = f" (in {delta.days} days)"
            else:
                relative = ""

            return await self._generate_calendar_response(
                template_type="find",
                user_request=original_text or search_term,
                context=context,
                db=db,
                event=event,
                date_str=date_str,
                time_str=time_str,
                relative=relative,
            )
        elif event.start and event.start.date:
            return await self._generate_calendar_response(
                template_type="find",
                user_request=original_text or search_term,
                context=context,
                db=db,
                event=event,
                date_str=event.start.date,
                time_str="all day",
                relative="",
            )

        return f"Found '{title}' on your calendar."

    async def _smart_next_event(
        self,
        search_term: Optional[str],
        context: HandlerContext,
        db: "Session",
    ) -> str:
        """
        Find the next event matching a term using smart search.

        Sprint 4.1: Now returns context-aware, multilingual responses.
        """
        from app.services.calendar_search_service import calendar_search_service

        original_text = context.original_text

        # Use smart search - it already returns events sorted by time
        result = await calendar_search_service.smart_search(
            user_query=search_term or "event",
            user_id=context.user_id,
            db=db,
            max_events=50,  # Fewer events for "next" query
        )

        if result.error:
            return result.error

        if result.no_match_found or not result.events:
            return await self._generate_calendar_response(
                template_type="no_events",
                user_request=original_text or f"next {search_term or 'event'}",
                context=context,
                db=db,
                search_term=search_term or "upcoming",
                period="",
            )

        event = result.events[0]
        time_str = event.get_time_display()

        # Sprint 3.9: Store event in conversation context for "this event" references
        self._store_event_context(str(context.user_id), event)

        # Format relative time
        start_dt = event.start.get_datetime() if event.start else None
        if start_dt:
            now = datetime.now(timezone.utc)

            # Ensure start_dt is timezone-aware for comparison
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)

            delta = start_dt - now

            if delta.days == 0:
                relative = "today"
            elif delta.days == 1:
                relative = "tomorrow"
            elif delta.days < 7:
                relative = f"on {start_dt.strftime('%A')}"
            else:
                relative = f"on {start_dt.strftime('%B %d')}"

            return await self._generate_calendar_response(
                template_type="next",
                user_request=original_text or f"next {search_term or 'event'}",
                context=context,
                db=db,
                event=event,
                time_str=time_str,
                relative=relative,
                search_term=search_term,
            )

        return await self._generate_calendar_response(
            template_type="next",
            user_request=original_text or f"next {search_term or 'event'}",
            context=context,
            db=db,
            event=event,
            time_str=time_str,
            relative="",
            search_term=search_term,
        )

    async def _smart_count_events(
        self,
        date_range: Optional[str],
        search_term: Optional[str],
        context: HandlerContext,
        db: "Session",
    ) -> str:
        """
        Count events using smart search for semantic matching.

        Sprint 4.1: Now returns context-aware, multilingual responses.
        """
        from app.services.calendar_search_service import calendar_search_service
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential

        original_text = context.original_text

        # If there's a search term, use smart search with date filtering
        if search_term:
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=context.user_id,
                db=db,
                date_range=date_range,  # CRITICAL: Pass date_range to filter!
            )

            if result.error:
                return result.error

            count = len(result.events)
            period = self._get_period_text(date_range)
            corrected = result.corrected_query or search_term

            if count == 0:
                return await self._generate_calendar_response(
                    template_type="no_events",
                    user_request=original_text or f"count {search_term}",
                    context=context,
                    db=db,
                    search_term=corrected,
                    period=period,
                )
            else:
                # If count=1, include event details in response
                event = result.events[0] if count == 1 and result.events else None
                return await self._generate_calendar_response(
                    template_type="count",
                    user_request=original_text or f"count {search_term}",
                    context=context,
                    db=db,
                    count=count,
                    search_term=corrected,
                    period=period,
                    event=event,
                )

        # No search term - fetch events and use multilingual generator
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == context.user_id,
            OAuthCredential.provider == "google",
        ).first()

        if not credentials:
            return await self._generate_calendar_response(
                template_type="not_found",
                user_request=original_text or "count events",
                context=context,
                db=db,
                search_term="Google Calendar connection",
            )

        # Fetch events using the calendar client with proper date filtering
        calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
        user_timezone = await calendar_client.get_user_timezone("primary")
        time_min, time_max = calendar_client._parse_date_range(date_range, user_timezone)

        events = await calendar_client.list_upcoming_events(
            calendar_id="primary",
            time_min=time_min,
            time_max=time_max,
            max_results=100,
        )

        count = len(events)
        period = self._get_period_text(date_range)

        if count == 0:
            return await self._generate_calendar_response(
                template_type="no_events",
                user_request=original_text or "count events",
                context=context,
                db=db,
                search_term="",
                period=period,
            )
        else:
            # If count=1, include event details in response
            event = events[0] if count == 1 and events else None
            return await self._generate_calendar_response(
                template_type="count",
                user_request=original_text or "count events",
                context=context,
                db=db,
                count=count,
                search_term="",
                period=period,
                event=event,
            )

    async def _smart_list_events(
        self,
        date_range: Optional[str],
        search_term: Optional[str],
        context: HandlerContext,
        db: "Session",
    ) -> str:
        """
        List events using smart search for semantic matching.

        Sprint 4.1: Now returns context-aware, multilingual responses.
        """
        from app.services.calendar_search_service import calendar_search_service
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential

        original_text = context.original_text

        # If there's a search term, use smart search with date filtering
        if search_term:
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=context.user_id,
                db=db,
                date_range=date_range,  # CRITICAL: Pass date_range to filter!
            )

            if result.error:
                return result.error

            period = self._get_period_text(date_range)
            corrected = result.corrected_query or search_term

            if not result.events:
                return await self._generate_calendar_response(
                    template_type="no_events",
                    user_request=original_text or f"list {search_term}",
                    context=context,
                    db=db,
                    search_term=corrected,
                    period=period,
                )

            return await self._generate_calendar_response(
                template_type="list",
                user_request=original_text or f"list {search_term}",
                context=context,
                db=db,
                events=result.events,
                search_term=corrected,
                period=period,
            )

        # No search term - fetch events and use multilingual generator
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == context.user_id,
            OAuthCredential.provider == "google",
        ).first()

        if not credentials:
            return await self._generate_calendar_response(
                template_type="not_found",
                user_request=original_text or "list events",
                context=context,
                db=db,
                search_term="Google Calendar connection",
            )

        # Fetch events using the calendar client with proper date filtering
        calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
        user_timezone = await calendar_client.get_user_timezone("primary")
        time_min, time_max = calendar_client._parse_date_range(date_range, user_timezone)

        events = await calendar_client.list_upcoming_events(
            calendar_id="primary",
            time_min=time_min,
            time_max=time_max,
            max_results=100,
        )

        period = self._get_period_text(date_range)

        if not events:
            return await self._generate_calendar_response(
                template_type="no_events",
                user_request=original_text or "list events",
                context=context,
                db=db,
                search_term="",
                period=period,
            )

        return await self._generate_calendar_response(
            template_type="list",
            user_request=original_text or "list events",
            context=context,
            db=db,
            events=events,
            search_term="",
            period=period,
        )

    # -----------------------------------------------------------------------
    # CALENDAR CREATE HANDLER (Sprint 3.8)
    # -----------------------------------------------------------------------

    async def _handle_calendar_create(
        self,
        intent: CalendarCreateIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle calendar event creation with confirmation flow.

        Sprint 3.8: Implements the confirmation flow:
        1. CREATE_EVENT: Extract details -> Store pending -> Return confirmation prompt
        2. CONFIRM_CREATE: Get pending -> Create via API -> Return success
        3. CANCEL_CREATE: Clear pending -> Return cancellation message
        4. EDIT_PENDING_EVENT: Update pending -> Return updated confirmation
        """
        action = intent.action

        # Route based on action type
        if action == ActionType.CREATE_EVENT:
            return await self._handle_create_event(intent, context)
        elif action == ActionType.CONFIRM_CREATE:
            return await self._handle_confirm_create(context, intent)
        elif action == ActionType.CANCEL_CREATE:
            return await self._handle_cancel_create(context)
        elif action == ActionType.EDIT_PENDING_EVENT:
            return await self._handle_edit_pending(intent, context)
        else:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Unknown calendar create action: {action}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    async def _handle_create_event(
        self,
        intent: CalendarCreateIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Extract event details and store pending event.

        Returns confirmation prompt for user.
        """
        from app.services.pending_event_service import pending_event_service
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.db.session import SessionLocal

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Check for Google OAuth credentials
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == context.user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,  # Reuse for calendar errors
                    confidence=intent.confidence,
                    message="Please connect your Google Calendar first. Visit /auth/google/login",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Get user's timezone from calendar
            try:
                calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
                user_timezone = await calendar_client.get_user_timezone()
            except Exception as e:
                logger.warning(f"Could not get user timezone: {e}")
                user_timezone = "UTC"

            # Resolve event_date if it's a string
            event_date = None
            if intent.event_date:
                event_date = self._resolve_date_string(intent.event_date)

            # Sprint 5.1.1: Extract doc_id from doc_url if present
            doc_id = None
            if intent.doc_url:
                try:
                    from app.environments.google.docs import GoogleDocsClient
                    doc_id = GoogleDocsClient.extract_doc_id(intent.doc_url)
                except Exception:
                    pass  # Invalid URL, continue without doc_id

            # Store pending event
            pending = await pending_event_service.store_pending(
                user_id=str(context.user_id),
                event_title=intent.event_title or "Event",
                event_date=event_date,
                event_time=intent.event_time,
                duration_minutes=intent.duration_minutes or 60,
                is_all_day=intent.is_all_day,
                location=intent.location,
                recurrence=intent.recurrence,
                timezone=user_timezone,
                original_text=intent.original_text,
                doc_url=intent.doc_url,
                doc_id=doc_id,
                source="doc" if intent.doc_url else "manual",
            )

            # Build confirmation message
            confirmation_message = self._build_confirmation_message(pending)

            processing_time = (time.time() - context.start_time) * 1000

            return IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_QUERY,
                confidence=intent.confidence,
                action="create_event",
                parameters={
                    "event_title": pending.event_title,
                    "event_date": pending.event_date.isoformat() if pending.event_date else None,
                    "event_time": pending.event_time,
                    "duration_minutes": pending.duration_minutes,
                    "is_all_day": pending.is_all_day,
                    "location": pending.location,
                    "recurrence": pending.recurrence,
                    "pending": True,
                },
                message=confirmation_message,
                response=confirmation_message,
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )
        finally:
            if owns_db:
                db.close()

    async def _handle_confirm_create(
        self,
        context: HandlerContext,
        intent: Optional[CalendarCreateIntent] = None,
    ) -> IntentResult:
        """
        Confirm and create the pending event.

        Context-aware confirmation (Sprint 3.9.1):
        Uses pending_op_type from context to determine which operation to confirm.
        If pending_op_type indicates EDIT/DELETE, delegates to that handler.
        If both exist, uses the most recent operation.

        Sprint 3.9: If intent contains event_date/event_time, update pending before creating.
        """
        from app.services.pending_event_service import pending_event_service
        from app.services.pending_edit_service import pending_edit_service
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.environments.google.calendar.schemas import EventCreateRequest
        from app.ai.context import _build_pending_state
        from app.db.session import SessionLocal

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Get pending state to determine priority (Sprint 3.9.1)
            pending_state = _build_pending_state(str(context.user_id))

            # If pending_op_type indicates EDIT or DELETE, delegate to that handler
            if pending_state.pending_op_type in ("edit", "delete"):
                logger.info(
                    f"Confirmation routed by pending_op_type: {pending_state.pending_op_type}",
                    extra={"user_id": str(context.user_id)[:8], "request_id": context.request_id}
                )
                if pending_state.pending_op_type == "delete":
                    return await self._handle_confirm_delete(context)
                else:
                    return await self._handle_confirm_edit(context)

            # Check for pending CREATE
            pending = pending_event_service.get_pending(str(context.user_id))

            if not pending:
                # No pending CREATE - check for pending EDIT/DELETE as fallback
                pending_edit = pending_edit_service.get_pending(str(context.user_id))

                if pending_edit:
                    # User said "yes" to confirm an edit/delete, not a create
                    logger.info(
                        f"Confirmation fallback: no pending CREATE, found pending {pending_edit.operation.value}",
                        extra={"user_id": str(context.user_id)[:8]}
                    )

                    if pending_edit.operation.value == "delete":
                        return await self._handle_confirm_delete(context)
                    else:
                        return await self._handle_confirm_edit(context)

                # Neither pending CREATE nor EDIT found
                processing_time = (time.time() - context.start_time) * 1000

                # Check if it expired or just doesn't exist
                if pending_event_service.is_expired(str(context.user_id)):
                    message = "Event creation timed out. Please try again: 'schedule a meeting tomorrow at 6 pm'"
                else:
                    message = "No pending operation to confirm. Try 'schedule a meeting tomorrow at 6 pm'"

                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    message=message,
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Sprint 3.9: Update pending with date/time from confirmation intent
            if intent:
                needs_refresh = False

                # Update event_date if provided in confirmation and pending is missing it
                if hasattr(intent, 'event_date') and intent.event_date and not pending.event_date:
                    try:
                        # Parse the date
                        if isinstance(intent.event_date, str):
                            parsed_date = self._resolve_date_string(intent.event_date)
                        elif isinstance(intent.event_date, date_type):
                            parsed_date = intent.event_date
                        else:
                            parsed_date = None

                        if parsed_date:
                            pending_event_service.update_pending(str(context.user_id), "event_date", parsed_date)
                            needs_refresh = True
                            logger.info(f"Updated pending event_date from confirmation: {parsed_date}")
                    except Exception as e:
                        logger.warning(f"Failed to parse event_date from confirmation: {e}")

                # Update event_time if provided in confirmation and pending is missing it
                if hasattr(intent, 'event_time') and intent.event_time and not pending.event_time:
                    pending_event_service.update_pending(str(context.user_id), "event_time", intent.event_time)
                    needs_refresh = True
                    logger.info(f"Updated pending event_time from confirmation: {intent.event_time}")

                # Update duration if provided and different from pending (Sprint 3.9 fix)
                if hasattr(intent, 'duration_minutes') and intent.duration_minutes and intent.duration_minutes != pending.duration_minutes:
                    pending_event_service.update_pending(str(context.user_id), "duration_minutes", intent.duration_minutes)
                    needs_refresh = True
                    logger.info(f"Updated pending duration_minutes from confirmation: {intent.duration_minutes}")

                # Refresh pending after updates
                if needs_refresh:
                    pending = pending_event_service.get_pending(str(context.user_id))
                    if not pending:
                        processing_time = (time.time() - context.start_time) * 1000
                        return IntentResult(
                            success=False,
                            intent_type=IntentResultType.CALENDAR_QUERY,
                            message="Pending event expired. Please try again.",
                            processing_time_ms=processing_time,
                            request_id=context.request_id,
                        )

            # Validate we have required fields
            if not pending.event_date:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    message="I still need the date for this event. When should it be scheduled?",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            if not pending.event_time and not pending.is_all_day:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    message="I still need the time for this event. What time should it start?",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Get credentials
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == context.user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    message="Please connect your Google Calendar first. Visit /auth/google/login",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Build event request
            try:
                calendar_client = GoogleCalendarClient(access_token=credentials.access_token)

                # Build description - include doc link if from doc source (Sprint 3.9)
                description = None
                if pending.source == "doc" and pending.doc_url:
                    description = f"Meeting Document: {pending.doc_url}"

                if pending.is_all_day:
                    # All-day event - Pydantic handles Optional fields with Field(None)
                    request = EventCreateRequest(  # type: ignore[call-arg]
                        summary=pending.event_title,
                        start_date=pending.event_date,
                        end_date=pending.event_date + timedelta(days=1) if pending.event_date else None,
                        location=pending.location,
                        recurrence=[pending.recurrence] if pending.recurrence else None,
                        timezone=pending.timezone,
                        description=description,
                    )
                    response = await calendar_client.create_all_day_event(request)
                else:
                    # Timed event
                    start_dt = pending.get_start_datetime()
                    end_dt = pending.get_end_datetime()

                    # Pydantic handles Optional fields with Field(None)
                    request = EventCreateRequest(  # type: ignore[call-arg]
                        summary=pending.event_title,
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                        location=pending.location,
                        recurrence=[pending.recurrence] if pending.recurrence else None,
                        timezone=pending.timezone,
                        description=description,
                    )
                    response = await calendar_client.create_event(request)

                # Remove from pending after successful creation
                await pending_event_service.confirm_pending(str(context.user_id))

                # Sprint 3.9 fix: Store event and doc in conversation context
                from app.services.conversation_context_service import conversation_context_service

                # Store event context
                conversation_context_service.set_last_event(
                    user_id=str(context.user_id),
                    event_title=pending.event_title,
                    event_id=response.event_id,
                    event_date=pending.event_date.isoformat() if pending.event_date else None,
                )

                # If from doc source, also store doc context
                if pending.source == "doc" and pending.doc_id and pending.doc_url:
                    conversation_context_service.set_last_doc(
                        user_id=str(context.user_id),
                        doc_id=pending.doc_id,
                        doc_url=pending.doc_url,
                        doc_title=pending.event_title,
                    )

                # Build success message
                success_message = self._build_calendar_success_message(pending, response)

                processing_time = (time.time() - context.start_time) * 1000

                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    action="confirm_create",
                    parameters={
                        "event_id": response.event_id,
                        "summary": response.summary,
                        "html_link": response.html_link,
                    },
                    message=success_message,
                    response=success_message,
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            except Exception as e:
                logger.error(f"Failed to create calendar event: {e}", exc_info=True)
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    message=f"Failed to create event: {str(e)}. Please try again.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )
        finally:
            if owns_db:
                db.close()

    async def _handle_cancel_create(
        self,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Cancel the pending event creation.
        """
        from app.services.pending_event_service import pending_event_service

        cancelled = pending_event_service.cancel_pending(str(context.user_id))

        processing_time = (time.time() - context.start_time) * 1000

        if cancelled:
            message = "Event creation cancelled. Let me know if you'd like to schedule something else."
        else:
            message = "No pending event to cancel."

        return IntentResult(
            success=True,
            intent_type=IntentResultType.CALENDAR_QUERY,
            action="cancel_create",
            message=message,
            response=message,
            processing_time_ms=processing_time,
            request_id=context.request_id,
        )

    async def _handle_edit_pending(
        self,
        intent: CalendarCreateIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Edit a field on the pending event.
        """
        from app.services.pending_event_service import pending_event_service

        # Get pending event
        pending = pending_event_service.get_pending(str(context.user_id))

        if not pending:
            processing_time = (time.time() - context.start_time) * 1000

            if pending_event_service.is_expired(str(context.user_id)):
                message = "Event creation timed out. Please try again: 'schedule a meeting tomorrow at 6 pm'"
            else:
                message = "No pending event to edit. Try 'schedule a meeting tomorrow at 6 pm'"

            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=message,
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        edit_field = intent.edit_field
        edit_value = intent.edit_value

        if not edit_field or not edit_value:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="I couldn't understand that edit. Try 'change time to 7 pm' or 'make it 2 hours'",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Parse the value based on field type
        try:
            parsed_value = self._parse_edit_value(edit_field, edit_value)
        except ValueError as e:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=f"Invalid edit: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Update the field
        try:
            updated = pending_event_service.update_pending(str(context.user_id), edit_field, parsed_value)
        except ValueError as e:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=str(e),
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        if not updated:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Failed to update event. Please try again.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Build updated confirmation message
        confirmation_message = self._build_confirmation_message(updated, highlight_field=edit_field)

        processing_time = (time.time() - context.start_time) * 1000

        return IntentResult(
            success=True,
            intent_type=IntentResultType.CALENDAR_QUERY,
            action="edit_pending_event",
            parameters={
                "edit_field": edit_field,
                "edit_value": str(parsed_value),
            },
            message=confirmation_message,
            response=confirmation_message,
            processing_time_ms=processing_time,
            request_id=context.request_id,
        )

    # -----------------------------------------------------------------------
    # CALENDAR EDIT HANDLERS (Sprint 3.9)
    # -----------------------------------------------------------------------

    async def _handle_calendar_edit(
        self,
        intent: CalendarEditIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle calendar event edit/delete with confirmation flow.

        Sprint 3.9: Implements the edit/delete flow:
        1. EDIT_EXISTING_EVENT: Search -> Disambiguate if needed -> Store pending -> Return confirmation
        2. DELETE_EXISTING_EVENT: Search -> Disambiguate if needed -> Store pending -> Return confirmation
        3. SELECT_EVENT: Select from multiple matches -> Update pending -> Return confirmation
        4. CONFIRM_EDIT: Get pending -> Execute update via API -> Return success
        5. CONFIRM_DELETE: Get pending -> Execute delete via API -> Return success
        6. CANCEL_EDIT: Clear pending -> Return cancellation message

        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunion").
        """
        action = intent.action

        # Route based on action type
        if action == ActionType.EDIT_EXISTING_EVENT:
            return await self._handle_edit_existing_event(intent, context)
        elif action == ActionType.DELETE_EXISTING_EVENT:
            return await self._handle_delete_existing_event(intent, context)
        elif action == ActionType.SELECT_EVENT:
            return await self._handle_select_event(intent, context)
        elif action == ActionType.CONFIRM_EDIT:
            return await self._handle_confirm_edit(context)
        elif action == ActionType.CONFIRM_DELETE:
            return await self._handle_confirm_delete(context)
        elif action == ActionType.CANCEL_EDIT:
            return await self._handle_cancel_edit(context)
        else:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Unknown calendar edit action: {action}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    async def _handle_edit_existing_event(
        self,
        intent: CalendarEditIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Search for events matching criteria and initiate edit flow.

        Uses smart semantic search (LLM matching) to find events,
        handling typos, translations, and synonyms.

        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunion").
        """
        from app.services.pending_edit_service import pending_edit_service
        from app.services.calendar_search_service import calendar_search_service
        from app.db.session import SessionLocal

        search_term = intent.search_term
        date_filter = intent.date_filter

        # Sprint 5.1.4: Resolve anaphoric reference if no explicit search_term
        if not search_term and context.resolved_references:
            resolved_event = context.resolved_references.get("event")
            if resolved_event and resolved_event.get("title"):
                search_term = resolved_event["title"]
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved event from context: {search_term}"
                )

        if not search_term:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="What event would you like to edit? Try 'edit my meeting tomorrow' or 'reschedule my dentist appointment'.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Use smart semantic search (handles typos, translations, synonyms)
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=context.user_id,
                db=db,
            )

            if result.error:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message=result.error,
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            if result.no_match_found or not result.events:
                processing_time = (time.time() - context.start_time) * 1000
                corrected = result.corrected_query or search_term
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message=f"No events found matching '{corrected}'. Try a different search term.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Limit to first 5 matches
            matching_events = result.events[:5]

            # DEBUG: Log the extracted changes dict for troubleshooting
            logger.info(
                f"[CALENDAR_EDIT] request_id={context.request_id}, "
                f"search_term='{search_term}', "
                f"original_text='{intent.original_text}', "
                f"extracted_changes={intent.changes}, "
                f"matched_events={len(matching_events)}"
            )

            # Store pending edit operation
            # Convert CalendarEvent objects to dicts for pending_edit_service
            events_as_dicts = [e.model_dump() for e in matching_events]
            pending = await pending_edit_service.store_pending_edit(
                user_id=str(context.user_id),
                operation="edit",
                matching_events=events_as_dicts,
                search_term=search_term,
                date_filter=date_filter,
                changes=intent.changes,
                original_text=intent.original_text,
            )

            processing_time = (time.time() - context.start_time) * 1000

            # Build response based on state
            if pending.needs_selection():
                # Multiple matches - ask for selection
                options_text = pending.get_event_options_text()
                message = f"I found multiple events:\n\n{options_text}\n\nWhich one would you like to edit? Say 'the first one' or a number."
            else:
                # Single match - ask for confirmation
                confirmation_text = pending.get_confirmation_text()
                message = f"{confirmation_text}\n\nSay 'yes' to confirm or 'no' to cancel."

            return IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
                action="edit_existing_event",
                parameters={
                    "search_term": search_term,
                    "matching_count": len(matching_events),
                    "state": pending.state.value,
                },
                message=message,
                response=message,
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )
        finally:
            if owns_db:
                db.close()

    async def _handle_delete_existing_event(
        self,
        intent: CalendarEditIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Search for events matching criteria and initiate delete flow.

        Uses smart semantic search (LLM matching) to find events,
        handling typos, translations, and synonyms.

        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunion").
        """
        from app.services.pending_edit_service import pending_edit_service
        from app.services.calendar_search_service import calendar_search_service
        from app.db.session import SessionLocal

        search_term = intent.search_term
        date_filter = intent.date_filter

        # Sprint 5.1.4: Resolve anaphoric reference if no explicit search_term
        if not search_term and context.resolved_references:
            resolved_event = context.resolved_references.get("event")
            if resolved_event and resolved_event.get("title"):
                search_term = resolved_event["title"]
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved event from context: {search_term}"
                )

        if not search_term:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="What event would you like to delete? Try 'delete my meeting tomorrow' or 'cancel my dentist appointment'.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Use smart semantic search (handles typos, translations, synonyms)
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=context.user_id,
                db=db,
            )

            if result.error:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message=result.error,
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            if result.no_match_found or not result.events:
                processing_time = (time.time() - context.start_time) * 1000
                corrected = result.corrected_query or search_term
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message=f"No events found matching '{corrected}'. Try a different search term.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Limit to first 5 matches
            matching_events = result.events[:5]

            # Store pending delete operation
            # Convert CalendarEvent objects to dicts for pending_edit_service
            events_as_dicts = [e.model_dump() for e in matching_events]
            pending = await pending_edit_service.store_pending_edit(
                user_id=str(context.user_id),
                operation="delete",
                matching_events=events_as_dicts,
                search_term=search_term,
                date_filter=date_filter,
                original_text=intent.original_text,
            )

            processing_time = (time.time() - context.start_time) * 1000

            # Build response based on state
            if pending.needs_selection():
                # Multiple matches - ask for selection
                options_text = pending.get_event_options_text()
                message = f"I found multiple events:\n\n{options_text}\n\nWhich one would you like to delete? Say 'the first one' or a number."
            else:
                # Single match - ask for confirmation
                confirmation_text = pending.get_confirmation_text()
                message = f"{confirmation_text}\n\nSay 'yes' to confirm or 'no' to cancel."

            return IntentResult(
                success=True,
                intent_type=IntentResultType.CALENDAR_EDIT,
                action="delete_existing_event",
                parameters={
                    "search_term": search_term,
                    "matching_count": len(matching_events),
                    "state": pending.state.value,
                },
                message=message,
                response=message,
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )
        finally:
            if owns_db:
                db.close()

    async def _handle_select_event(
        self,
        intent: CalendarEditIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle event selection from multiple matches.
        """
        from app.services.pending_edit_service import pending_edit_service

        pending = pending_edit_service.get_pending(str(context.user_id))

        if not pending:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="No pending edit operation. Try 'reschedule my meeting' or 'delete my appointment'.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        selection_index = intent.selection_index

        if not selection_index:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="Please specify which event. Say 'the first one', 'number 2', etc.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Select the event
        updated = pending_edit_service.select_event(str(context.user_id), selection_index)

        if not updated:
            processing_time = (time.time() - context.start_time) * 1000
            max_index = len(pending.matching_events)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=f"Invalid selection. Please choose a number between 1 and {max_index}.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Build confirmation message
        confirmation_text = updated.get_confirmation_text()
        processing_time = (time.time() - context.start_time) * 1000

        return IntentResult(
            success=True,
            intent_type=IntentResultType.CALENDAR_EDIT,
            action="select_event",
            parameters={
                "selected_index": selection_index,
                "selected_event": updated.selected_event.summary if updated.selected_event else None,
            },
            message=f"{confirmation_text}\n\nSay 'yes' to confirm or 'no' to cancel.",
            response=f"{confirmation_text}\n\nSay 'yes' to confirm or 'no' to cancel.",
            processing_time_ms=processing_time,
            request_id=context.request_id,
        )

    async def _handle_confirm_edit(
        self,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Confirm and execute the pending edit.

        Context-aware confirmation (Sprint 3.9.1):
        Uses pending_op_type to determine which operation to confirm.
        If pending_op_type indicates CREATE, delegates to that handler.
        """
        from app.services.pending_edit_service import pending_edit_service, PendingOperationType
        from app.services.pending_event_service import pending_event_service
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.environments.google.calendar.schemas import EventUpdateRequest
        from app.ai.context import _build_pending_state
        from app.db.session import SessionLocal

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Get pending state to determine priority (Sprint 3.9.1)
            pending_state = _build_pending_state(str(context.user_id))

            # If pending_op_type indicates CREATE, delegate to that handler
            if pending_state.pending_op_type == "create":
                logger.info(
                    "Confirmation routed by pending_op_type: create (from _handle_confirm_edit)",
                    extra={"user_id": str(context.user_id)[:8], "request_id": context.request_id}
                )
                return await self._handle_confirm_create(context)

            pending = pending_edit_service.get_pending(str(context.user_id))

            if not pending:
                # No pending EDIT - check for pending CREATE as fallback
                pending_create = pending_event_service.get_pending(str(context.user_id))

                if pending_create:
                    # User said "yes" to confirm a create, not an edit
                    logger.info(
                        "Confirmation fallback: no pending EDIT, found pending CREATE",
                        extra={"user_id": str(context.user_id)[:8]}
                    )
                    return await self._handle_confirm_create(context)

                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message="No pending operation to confirm. Try 'reschedule my meeting' or 'schedule a meeting'.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            if pending.operation != PendingOperationType.EDIT:
                # Redirect to delete handler
                return await self._handle_confirm_delete(context)

            if not pending.selected_event:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message="No event selected. Please select an event first.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Get credentials
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == context.user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message="Please connect your Google Calendar first.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Execute the update
            try:
                client = GoogleCalendarClient(
                    access_token=credentials.access_token,
                )

                # Get user's timezone to preserve local time intent (Bug Fix: Sprint 3.9.1)
                # Without this, "change to 4pm" sends 16:00 without timezone,
                # Google interprets as UTC, user sees wrong time (e.g., 11am in Miami)
                try:
                    user_timezone = await client.get_user_timezone()
                    logger.debug(
                        f"Edit confirmation using timezone: {user_timezone}",
                        extra={"user_id": str(context.user_id)[:8], "request_id": context.request_id}
                    )
                except Exception as e:
                    logger.warning(f"Could not get user timezone for edit: {e}, defaulting to UTC")
                    user_timezone = "UTC"

                event_id = pending.selected_event.event_id
                changes = pending.changes or {}

                # Process time changes - combine original date with new time if needed
                processed_changes = self._process_time_changes(
                    changes=changes,
                    original_start=pending.selected_event.start_time,
                    original_end=pending.selected_event.end_time,
                )

                # Add timezone to processed changes if we have time changes (Bug Fix: Sprint 3.9.1)
                if "start_datetime" in processed_changes or "end_datetime" in processed_changes:
                    processed_changes["timezone"] = user_timezone
                    logger.info(
                        "Edit event with timezone",
                        extra={
                            "user_id": str(context.user_id)[:8],
                            "timezone": user_timezone,
                            "start": str(processed_changes.get("start_datetime")),
                            "end": str(processed_changes.get("end_datetime")),
                        }
                    )

                # Build update request
                update_request = EventUpdateRequest(**processed_changes)

                await client.update_event(event_id, update_request)

                # Confirm and remove from pending
                await pending_edit_service.confirm_pending(str(context.user_id))

                processing_time = (time.time() - context.start_time) * 1000

                event_name = pending.selected_event.summary
                message = f"'{event_name}' has been updated."

                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    action="confirm_edit",
                    parameters={
                        "event_id": event_id,
                        "changes": changes,
                    },
                    message=message,
                    response=message,
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            except Exception as e:
                logger.error(f"Failed to update calendar event: {e}", exc_info=True)
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message=f"Failed to update event: {str(e)}. Please try again.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )
        finally:
            if owns_db:
                db.close()

    async def _handle_confirm_delete(
        self,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Confirm and execute the pending delete.

        Context-aware confirmation (Sprint 3.9.1):
        Uses pending_op_type to determine which operation to confirm.
        If pending_op_type indicates CREATE/EDIT, delegates accordingly.
        """
        from app.services.pending_edit_service import pending_edit_service, PendingOperationType
        from app.services.pending_event_service import pending_event_service
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.ai.context import _build_pending_state
        from app.db.session import SessionLocal

        # Get or create DB session
        db = context.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        try:
            # Get pending state to determine priority (Sprint 3.9.1)
            pending_state = _build_pending_state(str(context.user_id))

            # If pending_op_type indicates CREATE, delegate to that handler
            if pending_state.pending_op_type == "create":
                logger.info(
                    "Confirmation routed by pending_op_type: create (from _handle_confirm_delete)",
                    extra={"user_id": str(context.user_id)[:8], "request_id": context.request_id}
                )
                return await self._handle_confirm_create(context)

            # If pending_op_type indicates EDIT (not delete), delegate
            if pending_state.pending_op_type == "edit":
                logger.info(
                    "Confirmation routed by pending_op_type: edit (from _handle_confirm_delete)",
                    extra={"user_id": str(context.user_id)[:8], "request_id": context.request_id}
                )
                return await self._handle_confirm_edit(context)

            pending = pending_edit_service.get_pending(str(context.user_id))

            if not pending:
                # No pending EDIT/DELETE - check for pending CREATE as fallback
                pending_create = pending_event_service.get_pending(str(context.user_id))

                if pending_create:
                    logger.info(
                        "Confirmation fallback: no pending DELETE, found pending CREATE",
                        extra={"user_id": str(context.user_id)[:8]}
                    )
                    return await self._handle_confirm_create(context)

                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message="No pending operation to confirm. Try 'delete my meeting' or 'schedule a meeting'.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            if pending.operation != PendingOperationType.DELETE:
                # Redirect to edit handler
                return await self._handle_confirm_edit(context)

            if not pending.selected_event:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message="No event selected. Please select an event first.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Get credentials
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == context.user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message="Please connect your Google Calendar first.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            # Execute the delete
            try:
                client = GoogleCalendarClient(
                    access_token=credentials.access_token,
                )

                event_id = pending.selected_event.event_id
                event_name = pending.selected_event.summary

                await client.delete_event(event_id)

                # Confirm and remove from pending
                await pending_edit_service.confirm_pending(str(context.user_id))

                processing_time = (time.time() - context.start_time) * 1000

                message = f"'{event_name}' has been deleted."

                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    action="confirm_delete",
                    parameters={
                        "event_id": event_id,
                    },
                    message=message,
                    response=message,
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            except Exception as e:
                logger.error(f"Failed to delete calendar event: {e}", exc_info=True)
                processing_time = (time.time() - context.start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_EDIT,
                    message=f"Failed to delete event: {str(e)}. Please try again.",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )
        finally:
            if owns_db:
                db.close()

    async def _handle_cancel_edit(
        self,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Cancel the pending edit/delete operation.
        """
        from app.services.pending_edit_service import pending_edit_service

        cancelled = pending_edit_service.cancel_pending(str(context.user_id))

        processing_time = (time.time() - context.start_time) * 1000

        if cancelled:
            message = "Edit cancelled. Let me know if you'd like to make other changes."
        else:
            message = "No pending edit to cancel."

        return IntentResult(
            success=True,
            intent_type=IntentResultType.CALENDAR_EDIT,
            action="cancel_edit",
            message=message,
            response=message,
            processing_time_ms=processing_time,
            request_id=context.request_id,
        )

    # -----------------------------------------------------------------------
    # UTILITY METHODS
    # -----------------------------------------------------------------------

    def _resolve_date_string(self, date_str: str) -> Optional[date_type]:
        """
        Convert date string to date object.
        """
        import re

        if not date_str:
            return None

        # Handle if already a date object
        if isinstance(date_str, date_type):
            return date_str

        date_str = date_str.lower().strip()
        today = datetime.now()

        # Already ISO format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return datetime.strptime(date_str, "%Y-%m-%d").date()

        # Relative dates
        if date_str == "today":
            return today.date()
        if date_str == "tomorrow":
            return (today + timedelta(days=1)).date()

        # Try to parse as date
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

        return None

    def _parse_edit_value(self, field: str, value: str) -> Any:
        """
        Parse edit value based on field type.
        """
        from app.ai.intent.parser import intent_parser
        import re

        if field == "event_time":
            return intent_parser._resolve_time(value)
        elif field == "event_date":
            date_obj = self._resolve_date_string(value)
            if not date_obj:
                # Try to resolve using parser
                resolved = intent_parser._resolve_event_date(value, value)
                if resolved:
                    date_obj = self._resolve_date_string(resolved)
            return date_obj
        elif field == "event_title":
            return value.strip()
        elif field == "duration_minutes":
            # Parse "2 hours" -> 120, "90 minutes" -> 90
            value_lower = value.lower().strip()

            # Try to extract number
            num_match = re.search(r"(\d+)", value_lower)
            if num_match:
                num = int(num_match.group(1))
                if "hour" in value_lower:
                    return num * 60
                return num
            raise ValueError(f"Could not parse duration: {value}")
        elif field == "location":
            return value.strip()
        elif field == "recurrence":
            return intent_parser._parse_recurrence(value)
        elif field == "is_all_day":
            return value.lower() in ("true", "yes", "all day", "all-day")
        else:
            return value

    def _build_confirmation_message(
        self,
        pending: "PendingEvent",
        highlight_field: Optional[str] = None,
    ) -> str:
        """
        Build human-readable confirmation message (multilingual - Sprint 5.1.2).

        Example output (English):
        "Create 'Meeting' for December 13, 2025 at 7:00 PM (America/New_York)?
         Say 'yes' to confirm, 'no' to cancel, or edit like 'change time to 8 pm'"

        Example output (Spanish):
        "Crear 'Reunion' para December 13, 2025 a las 7:00 PM (America/New_York)?
         Di 'si' para confirmar, 'no' para cancelar, o edita como 'cambiar hora a 8 pm'"
        """
        from app.ai.prompts.helpers import (
            detect_user_language,
            get_confirmation_suffix,
            get_create_event_prefix,
        )

        # Detect language from original user text
        lang = detect_user_language(pending.original_text or "")

        title = pending.event_title

        # Format date
        if pending.event_date:
            date_str = pending.event_date.strftime("%B %d, %Y")
        else:
            date_str = "a date to be determined" if lang == "en" else "fecha por determinar"

        # Format time (localized)
        if pending.is_all_day:
            time_str = "(all day)" if lang == "en" else "(todo el dia)"
        elif pending.event_time:
            # Convert 24h to 12h format
            try:
                parts = pending.event_time.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                am_pm = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                at_word = "at" if lang == "en" else "a las"
                time_str = f"{at_word} {display_hour}:{minute:02d} {am_pm}"
            except Exception:
                time_str = f"at {pending.event_time}"
        else:
            time_str = ""

        # Build base message with localized prefix
        prefix = get_create_event_prefix(lang, pending.is_all_day)
        for_word = "for" if lang == "en" else "para"

        if pending.is_all_day:
            base = f"{prefix} '{title}' {for_word} {date_str}"
        else:
            base = f"{prefix} '{title}' {for_word} {date_str} {time_str}"

        # Add timezone
        if not pending.is_all_day and pending.timezone != "UTC":
            base += f" ({pending.timezone})"

        # Add recurrence
        if pending.recurrence:
            recurrence_text = self._format_recurrence(pending.recurrence, lang)
            base += f", {recurrence_text}"

        # Add location
        if pending.location:
            at_location = "at" if lang == "en" else "en"
            base += f", {at_location} {pending.location}"

        # Sprint 5.1.1: Show linked document
        if pending.doc_url:
            doc_text = "With linked document" if lang == "en" else "Con documento vinculado"
            base += f"\n{doc_text}"

        # Add highlight for edits
        if highlight_field:
            field_display_en = {
                "event_time": "time",
                "event_date": "date",
                "event_title": "title",
                "duration_minutes": "duration",
                "location": "location",
                "recurrence": "recurrence",
            }
            field_display_es = {
                "event_time": "hora",
                "event_date": "fecha",
                "event_title": "titulo",
                "duration_minutes": "duracion",
                "location": "ubicacion",
                "recurrence": "recurrencia",
            }
            field_map = field_display_en if lang == "en" else field_display_es
            field_name = field_map.get(highlight_field, highlight_field)
            updated_word = "Updated" if lang == "en" else "Actualizado"
            suffix = get_confirmation_suffix(lang, include_edit_hint=False)
            message = f"{updated_word} {field_name}. {base}?\n\n{suffix}"
        else:
            suffix = get_confirmation_suffix(lang, include_edit_hint=True)
            message = f"{base}?\n\n{suffix}"

        return message

    def _format_recurrence(self, recurrence: str, lang: str = "en") -> str:
        """Format RRULE to human-readable text (multilingual - Sprint 5.1.2)."""
        if not recurrence:
            return ""

        recurrence = recurrence.upper()

        # Localized recurrence texts
        if lang == "es":
            daily = "repitiendo diariamente"
            weekly = "repitiendo semanalmente"
            monthly = "repitiendo mensualmente"
            yearly = "repitiendo anualmente"
            repeat = "repitiendo"
            days = {
                "MO": "repitiendo cada lunes",
                "TU": "repitiendo cada martes",
                "WE": "repitiendo cada miercoles",
                "TH": "repitiendo cada jueves",
                "FR": "repitiendo cada viernes",
                "SA": "repitiendo cada sabado",
                "SU": "repitiendo cada domingo",
            }
        else:
            daily = "repeating daily"
            weekly = "repeating weekly"
            monthly = "repeating monthly"
            yearly = "repeating yearly"
            repeat = "repeating"
            days = {
                "MO": "repeating every Monday",
                "TU": "repeating every Tuesday",
                "WE": "repeating every Wednesday",
                "TH": "repeating every Thursday",
                "FR": "repeating every Friday",
                "SA": "repeating every Saturday",
                "SU": "repeating every Sunday",
            }

        if "FREQ=DAILY" in recurrence:
            return daily
        elif "FREQ=WEEKLY" in recurrence:
            for day_code, text in days.items():
                if f"BYDAY={day_code}" in recurrence:
                    return text
            return weekly
        elif "FREQ=MONTHLY" in recurrence:
            return monthly
        elif "FREQ=YEARLY" in recurrence:
            return yearly

        return repeat

    def _process_time_changes(
        self,
        changes: Dict[str, Any],
        original_start: Optional[str],
        original_end: Optional[str],
    ) -> Dict[str, Any]:
        """
        Process time changes, combining original event date with new time if needed.

        When user says "reschedule for 7 am", we get new_time="07:00" but need
        to combine it with the original event's date to create a full datetime.

        Args:
            changes: Raw changes dict (may have time-only values)
            original_start: Original event start time (ISO format)
            original_end: Original event end time (ISO format)

        Returns:
            Processed changes with full datetime values
        """
        processed = {}

        for key, value in changes.items():
            if key in ("start_datetime", "new_time") and value:
                # Check if it's a time-only value (HH:MM format)
                if isinstance(value, str) and len(value) <= 8 and ":" in value and "T" not in value:
                    # Time-only value - need to combine with original date
                    if original_start:
                        try:
                            # Parse original start to get the date
                            original_dt = datetime.fromisoformat(original_start.replace("Z", "+00:00"))
                            original_date = original_dt.date()

                            # Parse new time
                            time_parts = value.split(":")
                            hour = int(time_parts[0])
                            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

                            # Combine date + time
                            new_dt = datetime(
                                year=original_date.year,
                                month=original_date.month,
                                day=original_date.day,
                                hour=hour,
                                minute=minute,
                            )
                            processed["start_datetime"] = new_dt

                            # Also calculate end_datetime (1 hour after start by default)
                            if "end_datetime" not in changes and "new_end_time" not in changes:
                                processed["end_datetime"] = new_dt + timedelta(hours=1)

                            logger.debug(
                                f"Combined time: {value} + date from {original_start} = {new_dt.isoformat()}"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to parse time '{value}': {e}")
                            processed[key] = value  # type: ignore[assignment]
                    else:
                        # No original start, use value as-is
                        processed[key] = value  # type: ignore[assignment]
                else:
                    # Already a full datetime or datetime object
                    processed[key] = value

            elif key in ("end_datetime", "new_end_time") and value:
                # Check if it's a time-only value
                if isinstance(value, str) and len(value) <= 8 and ":" in value and "T" not in value:
                    if original_start:  # Use original start date for end time too
                        try:
                            original_dt = datetime.fromisoformat(original_start.replace("Z", "+00:00"))
                            original_date = original_dt.date()

                            time_parts = value.split(":")
                            hour = int(time_parts[0])
                            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

                            new_dt = datetime(
                                year=original_date.year,
                                month=original_date.month,
                                day=original_date.day,
                                hour=hour,
                                minute=minute,
                            )
                            processed["end_datetime"] = new_dt
                        except Exception as e:
                            logger.warning(f"Failed to parse end time '{value}': {e}")
                            processed[key] = value  # type: ignore[assignment]
                    else:
                        processed[key] = value  # type: ignore[assignment]
                else:
                    processed[key] = value

            elif key == "new_time":
                # Skip - handled above as start_datetime
                continue
            elif key == "new_end_time":
                # Skip - handled above as end_datetime
                continue
            else:
                # Pass through other changes (summary, location, etc.)
                processed[key] = value

        return processed

    def _build_calendar_success_message(
        self,
        pending: "PendingEvent",
        response: "EventCreateResponse",
    ) -> str:
        """
        Build success message after calendar event creation (multilingual - Sprint 5.1.2).

        Example (EN): "Meeting scheduled for December 13, 2025 at 7:00 PM"
        Example (ES): "'Reunion' programada para December 13, 2025 a las 7:00 PM"
        """
        from app.ai.prompts.helpers import detect_user_language

        # Detect language from original user text
        lang = detect_user_language(pending.original_text or "")

        title = response.summary

        # Localized words
        scheduled = "programada" if lang == "es" else "scheduled"
        for_word = "para" if lang == "es" else "for"
        all_day = "(todo el dia)" if lang == "es" else "(all day)"
        at_word = "a las" if lang == "es" else "at"

        # Format date/time
        if pending.is_all_day:
            if pending.event_date:
                date_str = pending.event_date.strftime("%B %d, %Y")
            else:
                date_str = "la fecha programada" if lang == "es" else "the scheduled date"
            message = f"'{title}' {scheduled} {for_word} {date_str} {all_day}"
        else:
            if pending.event_date:
                date_str = pending.event_date.strftime("%B %d, %Y")
            else:
                date_str = ""

            if pending.event_time:
                try:
                    parts = pending.event_time.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    am_pm = "AM" if hour < 12 else "PM"
                    display_hour = hour if hour <= 12 else hour - 12
                    if display_hour == 0:
                        display_hour = 12
                    time_str = f"{at_word} {display_hour}:{minute:02d} {am_pm}"
                except Exception:
                    time_str = f"{at_word} {pending.event_time}"
            else:
                time_str = ""

            message = f"'{title}' {scheduled} {for_word} {date_str} {time_str}".strip()

        # Add recurrence info
        if pending.recurrence:
            recurrence_text = self._format_recurrence(pending.recurrence, lang)
            message += f", {recurrence_text}"

        return message

    def _get_period_text(self, date_range: Optional[str]) -> str:
        """Get human-readable period description for messages."""
        if not date_range:
            return ""

        date_range = date_range.lower().strip()

        if date_range == "today":
            return " for today"
        elif date_range == "today_after":
            # Sprint 4.3.4: Descriptive text for remaining events today
            return " for the rest of today"
        elif date_range == "tomorrow":
            return " for tomorrow"
        elif date_range == "yesterday":
            return " for yesterday"
        elif date_range == "this_week":
            return " for this week"
        else:
            # Try to format as a date
            try:
                date_obj = datetime.strptime(date_range, "%Y-%m-%d")
                return f" for {date_obj.strftime('%B %d')}"
            except ValueError:
                return ""

    def _store_event_context(self, user_id: str, event) -> None:
        """
        Store an event in conversation context for "this event" references.

        Called when a calendar query returns/shows an event, so subsequent
        requests like "is there a doc for this event?" can resolve the reference.
        """
        from app.services.conversation_context_service import conversation_context_service

        try:
            # Extract event date
            event_date = None
            if event.start:
                start_dt = event.start.get_datetime()
                if start_dt:
                    event_date = start_dt.isoformat()
                elif event.start.date:
                    event_date = event.start.date

            conversation_context_service.set_last_event(
                user_id=user_id,
                event_title=event.get_display_title(),
                event_id=event.id,
                event_date=event_date,
            )
            logger.debug(f"Stored event context: {event.get_display_title()}")
        except Exception as e:
            logger.warning(f"Failed to store event context: {e}")

    @staticmethod
    def _get_action_value(action: Any) -> Optional[str]:
        """
        Extract action value from enum or string.

        Args:
            action: Action enum or string

        Returns:
            String value of the action, or None if action is None
        """
        if action is None:
            return None
        if hasattr(action, 'value'):
            return action.value
        return str(action)
