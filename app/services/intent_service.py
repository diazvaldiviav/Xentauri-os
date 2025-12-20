"""
Intent Processing Service - Business logic for natural language commands.

This service extracts the core intent processing logic from the router,
following the Single Responsibility Principle.

Responsibilities:
=================
- Process natural language intents
- Execute device commands
- Handle content display actions
- Coordinate with AI providers
- Build responses

NOT Responsible For:
====================
- HTTP request/response handling (router's job)
- Authentication/authorization (deps.py's job)
- Database session management (router provides it)

Architecture:
=============
```
┌─────────────┐
│   Router    │  ← HTTP only
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Service   │  ← Business logic (this file)
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
   ▼       ▼
┌─────┐ ┌─────┐
│ AI  │ │Cmds │  ← Providers
└─────┘ └─────┘
```

Usage:
======
```python
from app.services.intent_service import intent_service

result = await intent_service.process(
    text="Show calendar on living room TV",
    user_id=user.id,
    db=db_session,
)
```
"""

import logging
import time
import uuid as uuid_module
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.device import Device
from app.services.commands import command_service
from app.core.config import settings

# AI imports
from app.ai.intent.parser import intent_parser
from app.ai.intent.device_mapper import device_mapper
from app.ai.intent.schemas import (
    IntentType,
    ActionType,
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
    CalendarQueryIntent,
    CalendarCreateIntent,
    CalendarEditIntent,
    DocQueryIntent,
    ConversationIntent,
)
from app.ai.router.orchestrator import ai_router, TaskComplexity
from app.ai.monitoring import ai_monitor
from app.ai.actions.registry import action_registry, ActionCategory


logger = logging.getLogger("jarvis.services.intent")


# ---------------------------------------------------------------------------
# RESULT DATACLASSES
# ---------------------------------------------------------------------------

class IntentResultType(str, Enum):
    """Types of intent processing results."""
    DEVICE_COMMAND = "device_command"
    DEVICE_QUERY = "device_query"
    SYSTEM_QUERY = "system_query"
    CALENDAR_QUERY = "calendar_query"
    CALENDAR_EDIT = "calendar_edit"  # Sprint 3.9
    DOC_QUERY = "doc_query"          # Sprint 3.9
    CONVERSATION = "conversation"
    COMPLEX_EXECUTION = "complex_execution"
    COMPLEX_REASONING = "complex_reasoning"
    CLARIFICATION = "clarification"
    ACTION_SEQUENCE = "action_sequence"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """
    Result of processing a natural language intent.
    
    This is a service-layer result that the router converts
    to an HTTP response.
    """
    success: bool
    intent_type: IntentResultType
    confidence: float = 0.0
    
    # Device info
    device: Optional[Device] = None
    
    # Action info
    action: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    
    # Extra data for specific intent types (Sprint 3.9: DOC_QUERY)
    data: Optional[Dict[str, Any]] = None
    
    # Execution result
    command_sent: bool = False
    command_id: Optional[str] = None
    
    # Messages
    message: str = ""
    response: Optional[str] = None  # AI conversational response
    
    # Metadata
    processing_time_ms: float = 0.0
    request_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for response."""
        result = {
            "success": self.success,
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "action": self.action,
            "parameters": self.parameters,
            "data": self.data,
            "command_sent": self.command_sent,
            "command_id": self.command_id,
            "message": self.message,
            "response": self.response,
            "processing_time_ms": self.processing_time_ms,
            "request_id": self.request_id,
        }
        
        if self.device:
            result["device"] = {
                "id": str(self.device.id),
                "name": self.device.name,
                "is_online": self.device.is_online,
            }
        
        return result


# ---------------------------------------------------------------------------
# INTENT SERVICE
# ---------------------------------------------------------------------------

class IntentService:
    """
    Service for processing natural language intents.
    
    This class contains all the business logic for:
    - Parsing intents from natural language
    - Routing to appropriate AI models
    - Executing device commands
    - Building responses
    """
    
    def __init__(self):
        """Initialize the intent service."""
        logger.info("Intent service initialized")
    
    # -----------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------------
    
    async def process(
        self,
        text: str,
        user_id: UUID,
        db: Session,
        device_id: Optional[UUID] = None,
    ) -> IntentResult:
        """
        Process a natural language command.
        
        This is the main entry point for intent processing. It:
        1. Analyzes complexity with AI Router
        2. Routes to appropriate handler
        3. Returns structured result
        
        Args:
            text: Natural language command
            user_id: User's ID
            db: Database session
            device_id: Optional specific device to target
            
        Returns:
            IntentResult with processing outcome
        """
        start_time = time.time()
        request_id = str(uuid_module.uuid4())
        
        # Log the request
        ai_monitor.track_request(
            request_id=request_id,
            prompt=text,
            provider="gemini",
            model=settings.GEMINI_MODEL,
            user_id=user_id,
        )
        
        try:
            # Get user's devices for context
            devices = self._get_user_devices(db, user_id)
            device_context = device_mapper.to_device_context(devices)
            
            # Build pending operation state for context-aware routing (Sprint 3.9.1)
            from app.ai.context import _build_pending_state
            pending_state = _build_pending_state(str(user_id))
            
            context = {
                "devices": device_context,
                "user_id": str(user_id),
                # Add pending operation context for routing and parsing
                "pending_operation": pending_state.to_dict() if pending_state else None,
            }
            
            # Log pending state for debugging
            if pending_state and pending_state.has_any_pending():
                logger.info(
                    f"[PENDING_STATE] request_id={request_id}, "
                    f"pending_op_type={pending_state.pending_op_type}, "
                    f"pending_op_age={pending_state.pending_op_age_seconds}s, "
                    f"hint={pending_state.pending_op_hint}"
                )
            
            # Analyze complexity and get routing decision
            routing_decision = await ai_router.analyze_request(text, context)
            
            ai_monitor.track_routing(
                request_id=request_id,
                complexity=routing_decision.complexity.value,
                target_provider=routing_decision.target_provider,
                confidence=routing_decision.confidence,
                reasoning=routing_decision.reasoning,
                is_device_command=routing_decision.is_device_command,
            )
            
            # Route based on complexity
            if routing_decision.complexity == TaskComplexity.COMPLEX_EXECUTION:
                return await self._handle_complex_task(
                    request_id=request_id,
                    text=text,
                    routing_decision=routing_decision,
                    context=context,
                    start_time=start_time,
                    provider="openai",
                    db=db,
                    user_id=user_id,
                )
            
            if routing_decision.complexity == TaskComplexity.COMPLEX_REASONING:
                return await self._handle_complex_task(
                    request_id=request_id,
                    text=text,
                    routing_decision=routing_decision,
                    context=context,
                    start_time=start_time,
                    provider="anthropic",
                    db=db,
                    user_id=user_id,
                )
            
            # Simple tasks → Gemini Intent Parser
            return await self._handle_simple_task(
                request_id=request_id,
                text=text,
                context=context,
                devices=devices,
                device_id=device_id,
                start_time=start_time,
                user_id=user_id,
                db=db,
            )
        
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            ai_monitor.track_error(
                request_id=request_id,
                error=str(e),
                stage="processing",
            )
            logger.error(f"Intent processing failed: {e}", exc_info=True)
            
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to process intent: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    # -----------------------------------------------------------------------
    # SIMPLE TASK HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_simple_task(
        self,
        request_id: str,
        text: str,
        context: Dict[str, Any],
        devices: List[Device],
        device_id: Optional[UUID],
        start_time: float,
        user_id: UUID,
        db: Session = None,
    ) -> IntentResult:
        """Handle simple tasks using Gemini Intent Parser."""
        
        # Parse the intent
        parsed = await intent_parser.create_parsed_command(
            text=text,
            user_id=user_id,
            context=context,
        )
        
        # Log the parsed intent
        ai_monitor.track_intent(
            request_id=request_id,
            original_text=text,
            intent_type=self._get_intent_type_value(parsed.intent.intent_type),
            device_name=parsed.device_name,
            action=parsed.action,
            confidence=parsed.intent.confidence,
            processing_time_ms=parsed.processing_time_ms or 0,
        )
        
        intent = parsed.intent
        
        # Route to appropriate handler
        if isinstance(intent, DeviceCommand):
            return await self._handle_device_command(
                request_id=request_id,
                intent=intent,
                devices=devices,
                forced_device_id=device_id,
                start_time=start_time,
                user_id=user_id,
            )
        
        elif isinstance(intent, DeviceQuery):
            return await self._handle_device_query(
                request_id=request_id,
                intent=intent,
                devices=devices,
                start_time=start_time,
            )
        
        elif isinstance(intent, SystemQuery):
            return await self._handle_system_query(
                request_id=request_id,
                intent=intent,
                devices=devices,
                start_time=start_time,
            )
        
        elif isinstance(intent, CalendarQueryIntent):
            return await self._handle_calendar_query(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        elif isinstance(intent, CalendarCreateIntent):
            return await self._handle_calendar_create(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        elif isinstance(intent, CalendarEditIntent):
            return await self._handle_calendar_edit(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        elif isinstance(intent, DocQueryIntent):
            return await self._handle_doc_query(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        elif isinstance(intent, ConversationIntent):
            return await self._handle_conversation(
                request_id=request_id,
                intent=intent,
                original_text=text,
                start_time=start_time,
            )
        
        else:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.UNKNOWN,
                message="I couldn't understand that request. Try something like 'Turn on the TV'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    # -----------------------------------------------------------------------
    # DEVICE COMMAND HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_device_command(
        self,
        request_id: str,
        intent: DeviceCommand,
        devices: List[Device],
        forced_device_id: Optional[UUID],
        start_time: float,
        user_id: UUID,
    ) -> IntentResult:
        """Handle device command intents."""
        
        # Match device
        if forced_device_id:
            device = next((d for d in devices if d.id == forced_device_id), None)
            match_confidence = 1.0
        else:
            device, match_confidence = device_mapper.match(intent.device_name, devices)
        
        if not device:
            processing_time = (time.time() - start_time) * 1000
            alternatives = device_mapper.match_all(intent.device_name, devices, limit=3)
            suggestion = ""
            if alternatives:
                names = [f'"{d.name}"' for d, _ in alternatives]
                suggestion = f" Did you mean: {', '.join(names)}?"
            
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=intent.confidence,
                action=self._get_action_value(intent.action),
                message=f"I couldn't find a device matching '{intent.device_name}'.{suggestion}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Check if online
        if not device.is_online:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=intent.confidence,
                device=device,
                action=self._get_action_value(intent.action),
                message=f"'{device.name}' is currently offline.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        action = self._get_action_value(intent.action) or "status"
        
        # Content display actions
        if action_registry.is_content_action(action):
            return await self._execute_content_action(
                request_id=request_id,
                device=device,
                action=action,
                user_id=user_id,
                parameters=intent.parameters,
                confidence=intent.confidence,
                start_time=start_time,
            )
        
        # Standard device commands
        return await self._execute_device_command(
            request_id=request_id,
            device=device,
            action=action,
            parameters=intent.parameters,
            confidence=intent.confidence,
            start_time=start_time,
        )
    
    # -----------------------------------------------------------------------
    # DEVICE QUERY HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_device_query(
        self,
        request_id: str,
        intent: DeviceQuery,
        devices: List[Device],
        start_time: float,
    ) -> IntentResult:
        """Handle device query intents."""
        
        device, _ = device_mapper.match(intent.device_name, devices)
        
        if not device:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_QUERY,
                confidence=intent.confidence,
                message=f"I couldn't find a device matching '{intent.device_name}'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        processing_time = (time.time() - start_time) * 1000
        action = self._get_action_value(intent.action) or "status"
        
        if action in ("status", "is_online"):
            status_str = "online and ready" if device.is_online else "currently offline"
            message = f"'{device.name}' is {status_str}."
        elif action == "capabilities":
            caps = device.capabilities or {}
            if caps:
                cap_list = ", ".join(caps.keys())
                message = f"'{device.name}' supports: {cap_list}."
            else:
                message = f"'{device.name}' capabilities are not yet known."
        else:
            message = f"'{device.name}' - Online: {device.is_online}"
        
        return IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_QUERY,
            confidence=intent.confidence,
            device=device,
            action=action,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # -----------------------------------------------------------------------
    # SYSTEM QUERY HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_system_query(
        self,
        request_id: str,
        intent: SystemQuery,
        devices: List[Device],
        start_time: float,
    ) -> IntentResult:
        """Handle system query intents."""
        
        processing_time = (time.time() - start_time) * 1000
        action = self._get_action_value(intent.action) or "help"
        
        if action == "list_devices":
            if not devices:
                message = "You don't have any devices set up yet. Add a device to get started!"
            else:
                device_list = []
                for d in devices:
                    status = "🟢" if d.is_online else "🔴"
                    device_list.append(f"{status} {d.name}")
                message = "Your devices:\n" + "\n".join(device_list)
        
        elif action == "help":
            message = """I can help you control your devices! Try:
• "Turn on the [device name]"
• "Switch [device] to HDMI 2"
• "What devices do I have?"
• "Is the [device] on?"
• "Volume up on [device]"
"""
        else:
            message = "How can I help you with your devices?"
        
        return IntentResult(
            success=True,
            intent_type=IntentResultType.SYSTEM_QUERY,
            confidence=intent.confidence,
            action=action,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # -----------------------------------------------------------------------
    # CALENDAR QUERY HANDLER (Sprint 3.8 + 3.9)
    # -----------------------------------------------------------------------
    
    async def _handle_calendar_query(
        self,
        request_id: str,
        intent: CalendarQueryIntent,
        user_id: UUID,
        start_time: float,
        db: Session = None,
    ) -> IntentResult:
        """
        Handle calendar query intents - questions about calendar events.
        
        Sprint 3.8: Returns text answers to calendar questions like:
        - "How many events today?" → count_events
        - "What's my next meeting?" → next_event
        - "List my events for tomorrow" → list_events
        - "When is my birthday?" → find_event
        
        Sprint 3.9: Uses smart semantic search for typos/translations/synonyms.
        """
        from app.services.calendar_search_service import calendar_search_service
        from app.models.oauth_credential import OAuthCredential
        from app.db.session import SessionLocal
        from datetime import datetime, timezone, timedelta
        
        action = self._get_action_value(intent.action) or "count_events"
        date_range = intent.date_range
        search_term = intent.search_term
        
        # Get or create DB session
        owns_db = db is None
        if owns_db:
            db = SessionLocal()
        
        try:
            # Check for credentials first
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()
            
            if not credentials or not credentials.access_token:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.CALENDAR_QUERY,
                    confidence=intent.confidence,
                    action=action,
                    message="Please connect your Google Calendar first to use calendar features.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Route to appropriate query method using SMART SEARCH
            if action == "find_event":
                # Find a specific event (e.g., "when is my birthday?")
                message = await self._smart_find_event(
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                )
            elif action == "next_event":
                # Find the next event matching a term (e.g., "what's my next meeting?")
                message = await self._smart_next_event(
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                )
            elif action == "count_events":
                # Count events (e.g., "how many events today?")
                message = await self._smart_count_events(
                    date_range=date_range,
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                )
            elif action == "list_events":
                # List events (e.g., "list my events for tomorrow")
                message = await self._smart_list_events(
                    date_range=date_range,
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                )
            else:
                # Fallback to count
                message = await self._smart_count_events(
                    date_range=date_range,
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                )
            
            processing_time = (time.time() - start_time) * 1000
            
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
                request_id=request_id,
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"Calendar query failed: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                confidence=intent.confidence,
                action=action,
                message=f"I couldn't access your calendar: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        finally:
            if owns_db:
                db.close()
    
    # -----------------------------------------------------------------------
    # SMART CALENDAR QUERY HELPERS (Sprint 3.9)
    # -----------------------------------------------------------------------
    
    async def _smart_find_event(
        self,
        search_term: str,
        user_id: UUID,
        db: Session,
    ) -> str:
        """
        Find a specific event using smart semantic search.
        
        Handles typos, translations, and synonyms:
        - "birthday" matches "Cumpleaños de Victor"
        - "birday" matches "Birthday party"
        - "cumpleanos" matches "Cumpleaños"
        """
        from app.services.calendar_search_service import calendar_search_service
        
        if not search_term:
            return "What event are you looking for? Try 'When is my [event name]?'"
        
        # Use smart search for semantic matching
        result = await calendar_search_service.smart_search(
            user_query=search_term,
            user_id=user_id,
            db=db,
        )
        
        if result.error:
            return result.error
        
        if result.no_match_found or not result.events:
            corrected = result.corrected_query or search_term
            return f"I couldn't find any '{corrected}' events on your calendar."
        
        # Return the first (nearest) matching event
        event = result.events[0]
        title = event.get_display_title()
        
        # Sprint 3.9: Store event in conversation context for "this event" references
        self._store_event_context(str(user_id), event)
        
        # Format the date nicely
        start_dt = event.start.get_datetime() if event.start else None
        if start_dt:
            date_str = start_dt.strftime("%B %d, %Y")
            time_str = event.get_time_display()
            
            # Add relative context
            from datetime import datetime, timezone
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
            
            return f"Your '{title}' is on {date_str} at {time_str}{relative}."
        elif event.start and event.start.date:
            return f"Your '{title}' is on {event.start.date}."
        
        return f"Found '{title}' on your calendar."
    
    async def _smart_next_event(
        self,
        search_term: str,
        user_id: UUID,
        db: Session,
    ) -> str:
        """Find the next event matching a term using smart search."""
        from app.services.calendar_search_service import calendar_search_service
        
        # Use smart search - it already returns events sorted by time
        result = await calendar_search_service.smart_search(
            user_query=search_term or "event",
            user_id=user_id,
            db=db,
            max_events=50,  # Fewer events for "next" query
        )
        
        if result.error:
            return result.error
        
        if result.no_match_found or not result.events:
            if search_term:
                return f"You don't have any upcoming {search_term} events."
            return "You don't have any upcoming events."
        
        event = result.events[0]
        title = event.get_display_title()
        time_str = event.get_time_display()
        
        # Sprint 3.9: Store event in conversation context for "this event" references
        self._store_event_context(str(user_id), event)
        
        # Format relative time
        start_dt = event.start.get_datetime() if event.start else None
        if start_dt:
            from datetime import datetime, timezone
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
            
            if search_term:
                return f"Your next {search_term} is '{title}' at {time_str} {relative}."
            return f"Your next event is '{title}' at {time_str} {relative}."
        
        if search_term:
            return f"Your next {search_term} is '{title}' at {time_str}."
        return f"Your next event is '{title}' at {time_str}."
    
    async def _smart_count_events(
        self,
        date_range: str,
        search_term: str,
        user_id: UUID,
        db: Session,
    ) -> str:
        """Count events using smart search for semantic matching."""
        from app.services.calendar_search_service import calendar_search_service
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential
        
        # If there's a search term, use smart search
        if search_term:
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=user_id,
                db=db,
            )
            
            if result.error:
                return result.error
            
            count = len(result.events)
            period = self._get_period_text(date_range)
            corrected = result.corrected_query or search_term
            
            if count == 0:
                return f"You don't have any {corrected} events scheduled{period}."
            elif count == 1:
                event = result.events[0]
                return f"You have 1 {corrected} event{period}: {event.get_display_title()} at {event.get_time_display()}."
            else:
                return f"You have {count} {corrected} events scheduled{period}."
        
        # No search term - just count all events for the period
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return "Please connect your Google Calendar first."
        
        calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
        return await calendar_client.get_event_count_text(date_range=date_range)
    
    async def _smart_list_events(
        self,
        date_range: str,
        search_term: str,
        user_id: UUID,
        db: Session,
    ) -> str:
        """List events using smart search for semantic matching."""
        from app.services.calendar_search_service import calendar_search_service
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential
        
        # If there's a search term, use smart search
        if search_term:
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=user_id,
                db=db,
            )
            
            if result.error:
                return result.error
            
            period = self._get_period_text(date_range)
            corrected = result.corrected_query or search_term
            
            if not result.events:
                return f"You don't have any {corrected} events scheduled{period}."
            
            # Build header
            header = f"Your {corrected} events{period}:"
            
            # Build event list
            event_lines = []
            for event in result.events[:10]:  # Limit to 10 for text response
                time_str = event.get_time_display()
                title = event.get_display_title()
                event_lines.append(f"• {time_str} - {title}")
            
            text = header + "\n" + "\n".join(event_lines)
            
            if len(result.events) > 10:
                text += f"\n\n(Showing first 10 of {len(result.events)} events)"
            
            return text
        
        # No search term - list all events for the period
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return "Please connect your Google Calendar first."
        
        calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
        return await calendar_client.get_events_list_text(date_range=date_range)
    
    def _get_period_text(self, date_range: str) -> str:
        """Get human-readable period description for messages."""
        if not date_range:
            return ""
        
        date_range = date_range.lower().strip()
        
        if date_range == "today":
            return " for today"
        elif date_range == "tomorrow":
            return " for tomorrow"
        elif date_range == "yesterday":
            return " for yesterday"
        elif date_range == "this_week":
            return " for this week"
        else:
            # Try to format as a date
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date_range, "%Y-%m-%d")
                return f" for {date_obj.strftime('%B %d')}"
            except ValueError:
                return ""
    
    # -----------------------------------------------------------------------
    # CONVERSATION HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_conversation(
        self,
        request_id: str,
        intent: ConversationIntent,
        original_text: str,
        start_time: float,
    ) -> IntentResult:
        """Handle conversational intents."""
        
        processing_time = (time.time() - start_time) * 1000
        action = self._get_action_value(intent.action) or "greeting"
        
        responses = {
            "greeting": "Hello! I'm Jarvis, your display control assistant. How can I help?",
            "thanks": "You're welcome! Let me know if you need anything else.",
            "question": "That's an interesting question! I'm specialized in controlling displays.",
        }
        
        message = responses.get(action, "I'm here to help you control your displays.")
        
        return IntentResult(
            success=True,
            intent_type=IntentResultType.CONVERSATION,
            confidence=intent.confidence,
            action=action,
            message=message,
            response=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # -----------------------------------------------------------------------
    # COMPLEX TASK HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_complex_task(
        self,
        request_id: str,
        text: str,
        routing_decision,
        context: Dict[str, Any],
        start_time: float,
        provider: str,
        db: Session,
        user_id: UUID,
    ) -> IntentResult:
        """Handle complex tasks requiring GPT or Claude."""
        from app.ai.providers.openai_provider import openai_provider
        from app.ai.providers.anthropic_provider import anthropic_provider
        from app.ai.context import build_unified_context
        from app.ai.prompts.execution_prompts import build_execution_prompt
        from app.ai.prompts.base_prompt import build_reasoner_prompt
        from app.ai.schemas.action_response import (
            parse_action_response,
            ActionResponse,
            ClarificationResponse,
            ActionSequenceResponse,
        )
        
        if provider == "openai":
            ai_provider = openai_provider
            model_name = settings.OPENAI_MODEL
            task_type = "execution"
        else:
            ai_provider = anthropic_provider
            model_name = settings.ANTHROPIC_MODEL
            task_type = "reasoning"
        
        ai_monitor.track_event(
            request_id=request_id,
            event_type="complex_task_routing",
            data={
                "provider": provider,
                "model": model_name,
                "task_type": task_type,
            }
        )
        
        # Build unified context
        unified_context = None
        try:
            unified_context = await build_unified_context(
                user_id=user_id,
                db=db,
                request_id=request_id,
            )
        except Exception as e:
            logger.error(f"Failed to build unified context: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to build context: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Build prompt and call AI
        if task_type == "execution":
            prompt = build_execution_prompt(unified_context, text) if unified_context else text
            system_prompt = "You are a smart display execution assistant. Return valid JSON."
        else:
            prompt = build_reasoner_prompt(unified_context, text) if unified_context else text
            system_prompt = "You are a strategic advisor for smart home systems."
        
        response = await ai_provider.generate(prompt=prompt, system_prompt=system_prompt)
        processing_time = (time.time() - start_time) * 1000
        
        if not response.success:
            ai_monitor.track_response(
                request_id=request_id,
                provider=provider,
                model=model_name,
                content="",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=processing_time,
                success=False,
                error=response.error or "Unknown error",
            )
            
            return IntentResult(
                success=False,
                intent_type=IntentResultType.COMPLEX_EXECUTION if task_type == "execution" else IntentResultType.COMPLEX_REASONING,
                confidence=routing_decision.confidence,
                message=f"Failed to process: {response.error}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Log successful response
        ai_monitor.track_response(
            request_id=request_id,
            provider=provider,
            model=model_name,
            content=response.content[:500] if response.content else "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            latency_ms=processing_time,
            success=True,
        )
        
        # Handle reasoning tasks (return text response)
        if task_type == "reasoning":
            return IntentResult(
                success=True,
                intent_type=IntentResultType.COMPLEX_REASONING,
                confidence=routing_decision.confidence,
                action="reasoning",
                message=f"Analysis by {model_name}",
                response=response.content,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Handle execution tasks (parse and execute JSON)
        try:
            action_response = parse_action_response(response.content, strict=False)
            
            if isinstance(action_response, ClarificationResponse):
                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.CLARIFICATION,
                    confidence=routing_decision.confidence,
                    message=action_response.message,
                    response=action_response.message,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            elif isinstance(action_response, ActionResponse):
                return await self._execute_gpt_action(
                    action_response=action_response,
                    request_id=request_id,
                    user_id=user_id,
                    db=db,
                    processing_time=processing_time,
                    routing_confidence=routing_decision.confidence,
                )
            
            elif isinstance(action_response, ActionSequenceResponse):
                results = []
                for action in action_response.actions:
                    result = await self._execute_gpt_action(
                        action_response=action,
                        request_id=request_id,
                        user_id=user_id,
                        db=db,
                        processing_time=processing_time,
                        routing_confidence=routing_decision.confidence,
                    )
                    results.append(result)
                
                all_success = all(r.success for r in results)
                messages = [r.message for r in results if r.message]
                
                return IntentResult(
                    success=all_success,
                    intent_type=IntentResultType.ACTION_SEQUENCE,
                    confidence=routing_decision.confidence,
                    message="\n".join(messages),
                    command_sent=any(r.command_sent for r in results),
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            else:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Unexpected response format from AI",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
        
        except Exception as e:
            logger.error(f"Failed to parse GPT response: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to parse AI response: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    # -----------------------------------------------------------------------
    # ACTION EXECUTION
    # -----------------------------------------------------------------------
    
    async def _execute_gpt_action(
        self,
        action_response,
        request_id: str,
        user_id: UUID,
        db: Session,
        processing_time: float,
        routing_confidence: float,
    ) -> IntentResult:
        """Execute an action from GPT-4o response."""
        
        target_device_name = action_response.get_target_device()
        
        if not target_device_name:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=routing_confidence,
                message=f"No target device specified for action: {action_response.action_name}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        devices = self._get_user_devices(db, user_id)
        device, _ = device_mapper.match(target_device_name, devices)
        
        if not device:
            alternatives = device_mapper.match_all(target_device_name, devices, limit=3)
            suggestion = ""
            if alternatives:
                names = [f'"{d.name}"' for d, _ in alternatives]
                suggestion = f" Did you mean: {', '.join(names)}?"
            
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=routing_confidence,
                message=f"Could not find device '{target_device_name}'.{suggestion}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if not device.is_online:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=routing_confidence,
                device=device,
                message=f"'{device.name}' is currently offline.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        action_name = action_response.action_name
        
        if action_registry.is_content_action(action_name):
            return await self._execute_content_action(
                request_id=request_id,
                device=device,
                action=action_name,
                user_id=user_id,
                parameters=action_response.parameters,
                confidence=routing_confidence,
                start_time=time.time() - (processing_time / 1000),
            )
        
        return await self._execute_device_command(
            request_id=request_id,
            device=device,
            action=action_name,
            parameters=action_response.parameters,
            confidence=routing_confidence,
            start_time=time.time() - (processing_time / 1000),
        )
    
    async def _execute_content_action(
        self,
        request_id: str,
        device: Device,
        action: str,
        user_id: UUID,
        parameters: Optional[Dict],
        confidence: float,
        start_time: float,
    ) -> IntentResult:
        """Execute content display actions."""
        from app.services.content_token import content_token_service
        from urllib.parse import quote
        
        if action == "clear_content":
            result = await command_service.clear_content(device.id)
        else:
            content_token = content_token_service.generate(user_id, content_type="calendar")
            
            if action == "show_calendar":
                url = f"/cloud/calendar?token={content_token}"
                if parameters and "date" in parameters:
                    url += f"&date={parameters['date']}"
                # Sprint 3.7: Add search parameter with URL encoding
                if parameters and "search" in parameters:
                    search_encoded = quote(str(parameters['search']), safe='')
                    url += f"&search={search_encoded}"
                content_type = "calendar"
            elif action == "show_content":
                base_url = (parameters or {}).get("url", "/cloud/calendar")
                if base_url.startswith("/cloud/"):
                    separator = "&" if "?" in base_url else "?"
                    url = f"{base_url}{separator}token={content_token}"
                    if parameters and "date" in parameters:
                        url += f"&date={parameters['date']}"
                    # Sprint 3.7: Add search parameter with URL encoding
                    if parameters and "search" in parameters:
                        search_encoded = quote(str(parameters['search']), safe='')
                        url += f"&search={search_encoded}"
                else:
                    url = base_url
                content_type = (parameters or {}).get("content_type", "url")
            else:
                url = f"/cloud/calendar?token={content_token}"
                content_type = "url"
            
            result = await command_service.show_content(
                device_id=device.id,
                url=url,
                content_type=content_type,
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )
        
        if result.success:
            date = parameters.get("date") if parameters else None
            search = parameters.get("search") if parameters else None
            message = self._build_content_message(action, device.name, date, search)
        else:
            message = f"Failed: {result.error}"
        
        return IntentResult(
            success=result.success,
            intent_type=IntentResultType.DEVICE_COMMAND,
            confidence=confidence,
            device=device,
            action=action,
            parameters=parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    async def _execute_device_command(
        self,
        request_id: str,
        device: Device,
        action: str,
        parameters: Optional[Dict],
        confidence: float,
        start_time: float,
    ) -> IntentResult:
        """Execute standard device commands."""
        
        result = await command_service.send_command(
            device_id=device.id,
            command_type=action,
            parameters=parameters,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )
        
        if result.success:
            message = self._build_success_message(action, device.name, parameters)
        else:
            message = f"Failed: {result.error}"
        
        return IntentResult(
            success=result.success,
            intent_type=IntentResultType.DEVICE_COMMAND,
            confidence=confidence,
            device=device,
            action=action,
            parameters=parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # -----------------------------------------------------------------------
    # HELPERS
    # -----------------------------------------------------------------------
    
    def _get_user_devices(self, db: Session, user_id: UUID) -> List[Device]:
        """Get all devices for a user."""
        return db.query(Device).filter(Device.user_id == user_id).all()
    
    @staticmethod
    def _get_action_value(action) -> Optional[str]:
        """Extract action value from enum or string."""
        if action is None:
            return None
        if hasattr(action, 'value'):
            return action.value
        return str(action)
    
    @staticmethod
    def _get_intent_type_value(intent_type) -> str:
        """Extract intent_type value from enum or string."""
        if hasattr(intent_type, 'value'):
            return intent_type.value
        return str(intent_type)
    
    @staticmethod
    def _build_success_message(action: str, device_name: str, parameters: Optional[Dict]) -> str:
        """Build human-readable success message."""
        messages = {
            "power_on": f"Turning on {device_name}",
            "power_off": f"Turning off {device_name}",
            "volume_up": f"Increasing volume on {device_name}",
            "volume_down": f"Decreasing volume on {device_name}",
            "mute": f"Muting {device_name}",
            "unmute": f"Unmuting {device_name}",
        }
        
        if action in messages:
            return messages[action]
        
        if action == "set_input" and parameters:
            input_name = parameters.get("input") or parameters.get("app") or parameters.get("source")
            if input_name:
                return f"Switching {device_name} to {input_name}"
        
        if action == "volume_set" and parameters:
            level = parameters.get("level", "?")
            return f"Setting volume to {level}% on {device_name}"
        
        return f"Command sent to {device_name}"
    
    # -----------------------------------------------------------------------
    # CONVERSATION CONTEXT HELPERS (Sprint 3.9)
    # -----------------------------------------------------------------------
    
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
    
    def _store_doc_context(self, user_id: str, doc_id: str, doc_url: str, doc_title: str = None) -> None:
        """
        Store a document in conversation context for "this doc" references.
        
        Called when a doc query returns/shows a document, so subsequent
        requests can reference it.
        """
        from app.services.conversation_context_service import conversation_context_service
        
        try:
            conversation_context_service.set_last_doc(
                user_id=user_id,
                doc_id=doc_id,
                doc_url=doc_url,
                doc_title=doc_title,
            )
            logger.debug(f"Stored doc context: {doc_title or doc_id}")
        except Exception as e:
            logger.warning(f"Failed to store doc context: {e}")
    
    def _store_search_context(self, user_id: str, search_term: str, search_type: str) -> None:
        """
        Store a search in conversation context.
        
        Called when a search is performed, so subsequent requests can
        reference "the same search".
        """
        from app.services.conversation_context_service import conversation_context_service
        
        try:
            conversation_context_service.set_last_search(
                user_id=user_id,
                search_term=search_term,
                search_type=search_type,
            )
            logger.debug(f"Stored search context: {search_term} ({search_type})")
        except Exception as e:
            logger.warning(f"Failed to store search context: {e}")
    
    def _get_event_from_context(self, user_id: str):
        """
        Get the last referenced event from conversation context.
        
        Returns (title, event_id, event_date) or (None, None, None) if not found.
        """
        from app.services.conversation_context_service import conversation_context_service
        
        event = conversation_context_service.get_last_event(user_id)
        if event:
            return event.get("title"), event.get("id"), event.get("date")
        return None, None, None
    
    # -----------------------------------------------------------------------
    # CALENDAR CREATE HANDLER (Sprint 3.8)
    # -----------------------------------------------------------------------
    
    async def _handle_calendar_create(
        self,
        request_id: str,
        intent: CalendarCreateIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Handle calendar event creation with confirmation flow.
        
        Sprint 3.8: Implements the confirmation flow:
        1. CREATE_EVENT: Extract details → Store pending → Return confirmation prompt
        2. CONFIRM_CREATE: Get pending → Create via API → Return success
        3. CANCEL_CREATE: Clear pending → Return cancellation message
        4. EDIT_PENDING_EVENT: Update pending → Return updated confirmation
        """
        from app.services.pending_event_service import pending_event_service
        from app.models.oauth_credential import OAuthCredential
        
        action = intent.action
        
        # Route based on action type
        if action == ActionType.CREATE_EVENT:
            return await self._handle_create_event(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.CONFIRM_CREATE:
            return await self._handle_confirm_create(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
                intent=intent,
            )
        elif action == ActionType.CANCEL_CREATE:
            return await self._handle_cancel_create(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
            )
        elif action == ActionType.EDIT_PENDING_EVENT:
            return await self._handle_edit_pending(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
            )
        else:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Unknown calendar create action: {action}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    async def _handle_create_event(
        self,
        request_id: str,
        intent: CalendarCreateIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Extract event details and store pending event.
        
        Returns confirmation prompt for user.
        """
        from app.services.pending_event_service import pending_event_service
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        from datetime import datetime, date as date_type
        
        processing_time_start = time.time()
        
        # Check for Google OAuth credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,  # Reuse for calendar errors
                confidence=intent.confidence,
                message="Please connect your Google Calendar first. Visit /auth/google/login",
                processing_time_ms=processing_time,
                request_id=request_id,
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
        
        # Store pending event
        pending = await pending_event_service.store_pending(
            user_id=str(user_id),
            event_title=intent.event_title or "Event",
            event_date=event_date,
            event_time=intent.event_time,
            duration_minutes=intent.duration_minutes or 60,
            is_all_day=intent.is_all_day,
            location=intent.location,
            recurrence=intent.recurrence,
            timezone=user_timezone,
            original_text=intent.original_text,
        )
        
        # Build confirmation message
        confirmation_message = self._build_confirmation_message(pending)
        
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )
    
    async def _handle_confirm_create(
        self,
        request_id: str,
        user_id: UUID,
        start_time: float,
        db: Session,
        intent: Optional["CalendarCreateIntent"] = None,
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
        from datetime import datetime, timedelta
        from app.ai.context import _build_pending_state
        
        # Get pending state to determine priority (Sprint 3.9.1)
        pending_state = _build_pending_state(str(user_id))
        
        # If pending_op_type indicates EDIT or DELETE, delegate to that handler
        if pending_state.pending_op_type in ("edit", "delete"):
            logger.info(
                f"Confirmation routed by pending_op_type: {pending_state.pending_op_type}",
                extra={"user_id": str(user_id)[:8], "request_id": request_id}
            )
            if pending_state.pending_op_type == "delete":
                return await self._handle_confirm_delete(
                    request_id=request_id,
                    user_id=user_id,
                    start_time=start_time,
                    db=db,
                )
            else:
                return await self._handle_confirm_edit(
                    request_id=request_id,
                    user_id=user_id,
                    start_time=start_time,
                    db=db,
                )
        
        # Check for pending CREATE
        pending = pending_event_service.get_pending(str(user_id))
        
        if not pending:
            # No pending CREATE - check for pending EDIT/DELETE as fallback
            pending_edit = pending_edit_service.get_pending(str(user_id))
            
            if pending_edit:
                # User said "yes" to confirm an edit/delete, not a create
                logger.info(
                    f"Confirmation fallback: no pending CREATE, found pending {pending_edit.operation.value}",
                    extra={"user_id": str(user_id)[:8]}
                )
                
                if pending_edit.operation.value == "delete":
                    return await self._handle_confirm_delete(
                        request_id=request_id,
                        user_id=user_id,
                        start_time=start_time,
                        db=db,
                    )
                else:
                    return await self._handle_confirm_edit(
                        request_id=request_id,
                        user_id=user_id,
                        start_time=start_time,
                        db=db,
                    )
            
            # Neither pending CREATE nor EDIT found
            processing_time = (time.time() - start_time) * 1000
            
            # Check if it expired or just doesn't exist
            if pending_event_service.is_expired(str(user_id)):
                message = "Event creation timed out. Please try again: 'schedule a meeting tomorrow at 6 pm'"
            else:
                message = "No pending operation to confirm. Try 'schedule a meeting tomorrow at 6 pm'"
            
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=message,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Sprint 3.9: Update pending with date/time from confirmation intent
        if intent:
            needs_refresh = False
            
            # Update event_date if provided in confirmation and pending is missing it
            if hasattr(intent, 'event_date') and intent.event_date and not pending.event_date:
                try:
                    from datetime import date as date_type
                    # Parse the date
                    if isinstance(intent.event_date, str):
                        parsed_date = self._resolve_date_string(intent.event_date)
                    elif isinstance(intent.event_date, date_type):
                        parsed_date = intent.event_date
                    else:
                        parsed_date = None
                    
                    if parsed_date:
                        pending_event_service.update_pending(str(user_id), "event_date", parsed_date)
                        needs_refresh = True
                        logger.info(f"Updated pending event_date from confirmation: {parsed_date}")
                except Exception as e:
                    logger.warning(f"Failed to parse event_date from confirmation: {e}")
            
            # Update event_time if provided in confirmation and pending is missing it
            if hasattr(intent, 'event_time') and intent.event_time and not pending.event_time:
                pending_event_service.update_pending(str(user_id), "event_time", intent.event_time)
                needs_refresh = True
                logger.info(f"Updated pending event_time from confirmation: {intent.event_time}")
            
            # Update duration if provided and different from pending (Sprint 3.9 fix)
            if hasattr(intent, 'duration_minutes') and intent.duration_minutes and intent.duration_minutes != pending.duration_minutes:
                pending_event_service.update_pending(str(user_id), "duration_minutes", intent.duration_minutes)
                needs_refresh = True
                logger.info(f"Updated pending duration_minutes from confirmation: {intent.duration_minutes}")
            
            # Refresh pending after updates
            if needs_refresh:
                pending = pending_event_service.get_pending(str(user_id))
                if not pending:
                    processing_time = (time.time() - start_time) * 1000
                    return IntentResult(
                        success=False,
                        intent_type=IntentResultType.CALENDAR_QUERY,
                        message="Pending event expired. Please try again.",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )
        
        # Validate we have required fields
        if not pending.event_date:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="I still need the date for this event. When should it be scheduled?",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if not pending.event_time and not pending.is_all_day:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="I still need the time for this event. What time should it start?",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Get credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Please connect your Google Calendar first. Visit /auth/google/login",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Build event request
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            
            # Build description - include doc link if from doc source (Sprint 3.9)
            description = None
            if pending.source == "doc" and pending.doc_url:
                description = f"📄 Meeting Document: {pending.doc_url}"
            
            if pending.is_all_day:
                # All-day event
                request = EventCreateRequest(
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
                
                request = EventCreateRequest(
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
            await pending_event_service.confirm_pending(str(user_id))
            
            # Sprint 3.9 fix: Store event and doc in conversation context
            from app.services.conversation_context_service import conversation_context_service
            
            # Store event context
            conversation_context_service.set_last_event(
                user_id=str(user_id),
                event_title=pending.event_title,
                event_id=response.event_id,
                event_date=pending.event_date.isoformat() if pending.event_date else None,
            )
            
            # If from doc source, also store doc context
            if pending.source == "doc" and pending.doc_id and pending.doc_url:
                conversation_context_service.set_last_doc(
                    user_id=str(user_id),
                    doc_id=pending.doc_id,
                    doc_url=pending.doc_url,
                    doc_title=pending.event_title,
                )
            
            # Build success message
            success_message = self._build_calendar_success_message(pending, response)
            
            processing_time = (time.time() - start_time) * 1000
            
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
                request_id=request_id,
            )
            
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=f"Failed to create event: {str(e)}. Please try again.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    async def _handle_cancel_create(
        self,
        request_id: str,
        user_id: UUID,
        start_time: float,
    ) -> IntentResult:
        """
        Cancel the pending event creation.
        """
        from app.services.pending_event_service import pending_event_service
        
        cancelled = pending_event_service.cancel_pending(str(user_id))
        
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )
    
    async def _handle_edit_pending(
        self,
        request_id: str,
        intent: CalendarCreateIntent,
        user_id: UUID,
        start_time: float,
    ) -> IntentResult:
        """
        Edit a field on the pending event.
        """
        from app.services.pending_event_service import pending_event_service
        
        # Get pending event
        pending = pending_event_service.get_pending(str(user_id))
        
        if not pending:
            processing_time = (time.time() - start_time) * 1000
            
            if pending_event_service.is_expired(str(user_id)):
                message = "Event creation timed out. Please try again: 'schedule a meeting tomorrow at 6 pm'"
            else:
                message = "No pending event to edit. Try 'schedule a meeting tomorrow at 6 pm'"
            
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=message,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        edit_field = intent.edit_field
        edit_value = intent.edit_value
        
        if not edit_field or not edit_value:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="I couldn't understand that edit. Try 'change time to 7 pm' or 'make it 2 hours'",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Parse the value based on field type
        try:
            parsed_value = self._parse_edit_value(edit_field, edit_value)
        except ValueError as e:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=f"Invalid edit: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Update the field
        try:
            updated = pending_event_service.update_pending(str(user_id), edit_field, parsed_value)
        except ValueError as e:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message=str(e),
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if not updated:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_QUERY,
                message="Failed to update event. Please try again.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Build updated confirmation message
        confirmation_message = self._build_confirmation_message(updated, highlight_field=edit_field)
        
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )
    
    # -----------------------------------------------------------------------
    # CALENDAR EDIT HANDLERS (Sprint 3.9)
    # -----------------------------------------------------------------------
    
    async def _handle_calendar_edit(
        self,
        request_id: str,
        intent: CalendarEditIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Handle calendar event edit/delete with confirmation flow.
        
        Sprint 3.9: Implements the edit/delete flow:
        1. EDIT_EXISTING_EVENT: Search → Disambiguate if needed → Store pending → Return confirmation
        2. DELETE_EXISTING_EVENT: Search → Disambiguate if needed → Store pending → Return confirmation
        3. SELECT_EVENT: Select from multiple matches → Update pending → Return confirmation
        4. CONFIRM_EDIT: Get pending → Execute update via API → Return success
        5. CONFIRM_DELETE: Get pending → Execute delete via API → Return success
        6. CANCEL_EDIT: Clear pending → Return cancellation message
        """
        action = intent.action
        
        # Route based on action type
        if action == ActionType.EDIT_EXISTING_EVENT:
            return await self._handle_edit_existing_event(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.DELETE_EXISTING_EVENT:
            return await self._handle_delete_existing_event(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.SELECT_EVENT:
            return await self._handle_select_event(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
            )
        elif action == ActionType.CONFIRM_EDIT:
            return await self._handle_confirm_edit(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.CONFIRM_DELETE:
            return await self._handle_confirm_delete(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.CANCEL_EDIT:
            return await self._handle_cancel_edit(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
            )
        else:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Unknown calendar edit action: {action}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    async def _handle_edit_existing_event(
        self,
        request_id: str,
        intent: CalendarEditIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Search for events matching criteria and initiate edit flow.
        
        Uses smart semantic search (LLM matching) to find events,
        handling typos, translations, and synonyms.
        """
        from app.services.pending_edit_service import pending_edit_service
        from app.services.calendar_search_service import calendar_search_service
        
        search_term = intent.search_term
        date_filter = intent.date_filter
        
        if not search_term:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="What event would you like to edit? Try 'edit my meeting tomorrow' or 'reschedule my dentist appointment'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Use smart semantic search (handles typos, translations, synonyms)
        result = await calendar_search_service.smart_search(
            user_query=search_term,
            user_id=user_id,
            db=db,
        )
        
        if result.error:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=result.error,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if result.no_match_found or not result.events:
            processing_time = (time.time() - start_time) * 1000
            corrected = result.corrected_query or search_term
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=f"No events found matching '{corrected}'. Try a different search term.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Limit to first 5 matches
        matching_events = result.events[:5]
        
        # DEBUG: Log the extracted changes dict for troubleshooting
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"[CALENDAR_EDIT] request_id={request_id}, "
            f"search_term='{search_term}', "
            f"original_text='{intent.original_text}', "
            f"extracted_changes={intent.changes}, "
            f"matched_events={len(matching_events)}"
        )
        
        # Store pending edit operation
        # (pending_edit_service handles CalendarEvent -> MatchingEvent conversion)
        pending = await pending_edit_service.store_pending_edit(
            user_id=str(user_id),
            operation="edit",
            matching_events=matching_events,
            search_term=search_term,
            date_filter=date_filter,
            changes=intent.changes,
            original_text=intent.original_text,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )
    
    async def _handle_delete_existing_event(
        self,
        request_id: str,
        intent: CalendarEditIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Search for events matching criteria and initiate delete flow.
        
        Uses smart semantic search (LLM matching) to find events,
        handling typos, translations, and synonyms.
        """
        from app.services.pending_edit_service import pending_edit_service
        from app.services.calendar_search_service import calendar_search_service
        
        search_term = intent.search_term
        date_filter = intent.date_filter
        
        if not search_term:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="What event would you like to delete? Try 'delete my meeting tomorrow' or 'cancel my dentist appointment'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Use smart semantic search (handles typos, translations, synonyms)
        result = await calendar_search_service.smart_search(
            user_query=search_term,
            user_id=user_id,
            db=db,
        )
        
        if result.error:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=result.error,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if result.no_match_found or not result.events:
            processing_time = (time.time() - start_time) * 1000
            corrected = result.corrected_query or search_term
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=f"No events found matching '{corrected}'. Try a different search term.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Limit to first 5 matches
        matching_events = result.events[:5]
        
        # Store pending delete operation
        # (pending_edit_service handles CalendarEvent -> MatchingEvent conversion)
        pending = await pending_edit_service.store_pending_edit(
            user_id=str(user_id),
            operation="delete",
            matching_events=matching_events,
            search_term=search_term,
            date_filter=date_filter,
            original_text=intent.original_text,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )
    
    async def _handle_select_event(
        self,
        request_id: str,
        intent: CalendarEditIntent,
        user_id: UUID,
        start_time: float,
    ) -> IntentResult:
        """
        Handle event selection from multiple matches.
        """
        from app.services.pending_edit_service import pending_edit_service
        
        pending = pending_edit_service.get_pending(str(user_id))
        
        if not pending:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="No pending edit operation. Try 'reschedule my meeting' or 'delete my appointment'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        selection_index = intent.selection_index
        
        if not selection_index:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="Please specify which event. Say 'the first one', 'number 2', etc.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Select the event
        updated = pending_edit_service.select_event(str(user_id), selection_index)
        
        if not updated:
            processing_time = (time.time() - start_time) * 1000
            max_index = len(pending.matching_events)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=f"Invalid selection. Please choose a number between 1 and {max_index}.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Build confirmation message
        confirmation_text = updated.get_confirmation_text()
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )
    
    async def _handle_confirm_edit(
        self,
        request_id: str,
        user_id: UUID,
        start_time: float,
        db: Session,
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
        
        # Get pending state to determine priority (Sprint 3.9.1)
        pending_state = _build_pending_state(str(user_id))
        
        # If pending_op_type indicates CREATE, delegate to that handler
        if pending_state.pending_op_type == "create":
            logger.info(
                f"Confirmation routed by pending_op_type: create (from _handle_confirm_edit)",
                extra={"user_id": str(user_id)[:8], "request_id": request_id}
            )
            return await self._handle_confirm_create(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        pending = pending_edit_service.get_pending(str(user_id))
        
        if not pending:
            # No pending EDIT - check for pending CREATE as fallback
            pending_create = pending_event_service.get_pending(str(user_id))
            
            if pending_create:
                # User said "yes" to confirm a create, not an edit
                logger.info(
                    f"Confirmation fallback: no pending EDIT, found pending CREATE",
                    extra={"user_id": str(user_id)[:8]}
                )
                return await self._handle_confirm_create(
                    request_id=request_id,
                    user_id=user_id,
                    start_time=start_time,
                    db=db,
                )
            
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="No pending operation to confirm. Try 'reschedule my meeting' or 'schedule a meeting'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if pending.operation != PendingOperationType.EDIT:
            # Redirect to delete handler
            return await self._handle_confirm_delete(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        if not pending.selected_event:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="No event selected. Please select an event first.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Get credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="Please connect your Google Calendar first.",
                processing_time_ms=processing_time,
                request_id=request_id,
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
                    extra={"user_id": str(user_id)[:8], "request_id": request_id}
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
                    f"Edit event with timezone",
                    extra={
                        "user_id": str(user_id)[:8],
                        "timezone": user_timezone,
                        "start": str(processed_changes.get("start_datetime")),
                        "end": str(processed_changes.get("end_datetime")),
                    }
                )
            
            # Build update request
            update_request = EventUpdateRequest(**processed_changes)
            
            response = await client.update_event(event_id, update_request)
            
            # Confirm and remove from pending
            await pending_edit_service.confirm_pending(str(user_id))
            
            processing_time = (time.time() - start_time) * 1000
            
            event_name = pending.selected_event.summary
            message = f"✓ '{event_name}' has been updated."
            
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
                request_id=request_id,
            )
            
        except Exception as e:
            logger.error(f"Failed to update calendar event: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=f"Failed to update event: {str(e)}. Please try again.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    async def _handle_confirm_delete(
        self,
        request_id: str,
        user_id: UUID,
        start_time: float,
        db: Session,
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
        
        # Get pending state to determine priority (Sprint 3.9.1)
        pending_state = _build_pending_state(str(user_id))
        
        # If pending_op_type indicates CREATE, delegate to that handler
        if pending_state.pending_op_type == "create":
            logger.info(
                f"Confirmation routed by pending_op_type: create (from _handle_confirm_delete)",
                extra={"user_id": str(user_id)[:8], "request_id": request_id}
            )
            return await self._handle_confirm_create(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        # If pending_op_type indicates EDIT (not delete), delegate
        if pending_state.pending_op_type == "edit":
            logger.info(
                f"Confirmation routed by pending_op_type: edit (from _handle_confirm_delete)",
                extra={"user_id": str(user_id)[:8], "request_id": request_id}
            )
            return await self._handle_confirm_edit(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        pending = pending_edit_service.get_pending(str(user_id))
        
        if not pending:
            # No pending EDIT/DELETE - check for pending CREATE as fallback
            pending_create = pending_event_service.get_pending(str(user_id))
            
            if pending_create:
                logger.info(
                    f"Confirmation fallback: no pending DELETE, found pending CREATE",
                    extra={"user_id": str(user_id)[:8]}
                )
                return await self._handle_confirm_create(
                    request_id=request_id,
                    user_id=user_id,
                    start_time=start_time,
                    db=db,
                )
            
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="No pending operation to confirm. Try 'delete my meeting' or 'schedule a meeting'.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if pending.operation != PendingOperationType.DELETE:
            # Redirect to edit handler
            return await self._handle_confirm_edit(
                request_id=request_id,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        
        if not pending.selected_event:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="No event selected. Please select an event first.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Get credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message="Please connect your Google Calendar first.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Execute the delete
        try:
            client = GoogleCalendarClient(
                access_token=credentials.access_token,
            )
            
            event_id = pending.selected_event.event_id
            event_name = pending.selected_event.summary
            
            response = await client.delete_event(event_id)
            
            # Confirm and remove from pending
            await pending_edit_service.confirm_pending(str(user_id))
            
            processing_time = (time.time() - start_time) * 1000
            
            message = f"✓ '{event_name}' has been deleted."
            
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
                request_id=request_id,
            )
            
        except Exception as e:
            logger.error(f"Failed to delete calendar event: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.CALENDAR_EDIT,
                message=f"Failed to delete event: {str(e)}. Please try again.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    async def _handle_cancel_edit(
        self,
        request_id: str,
        user_id: UUID,
        start_time: float,
    ) -> IntentResult:
        """
        Cancel the pending edit/delete operation.
        """
        from app.services.pending_edit_service import pending_edit_service
        
        cancelled = pending_edit_service.cancel_pending(str(user_id))
        
        processing_time = (time.time() - start_time) * 1000
        
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
            request_id=request_id,
        )

    def _resolve_date_string(self, date_str: str) -> Optional["date_type"]:
        """
        Convert date string to date object.
        """
        from datetime import datetime, timedelta, date as date_type
        import re
        
        if not date_str:
            return None
        
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
            # Parse "2 hours" → 120, "90 minutes" → 90
            value_lower = value.lower().strip()
            import re
            
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
        Build human-readable confirmation message.
        
        Example output:
        "Create 'Meeting' for December 13, 2025 at 7:00 PM (America/New_York)?
         Say 'yes' to confirm, 'no' to cancel, or edit like 'change time to 8 pm'"
        """
        from datetime import datetime
        
        title = pending.event_title
        
        # Format date
        if pending.event_date:
            date_str = pending.event_date.strftime("%B %d, %Y")
        else:
            date_str = "a date to be determined"
        
        # Format time
        if pending.is_all_day:
            time_str = "(all day)"
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
                time_str = f"at {display_hour}:{minute:02d} {am_pm}"
            except:
                time_str = f"at {pending.event_time}"
        else:
            time_str = ""
        
        # Build base message
        if pending.is_all_day:
            base = f"Create all-day event '{title}' for {date_str}"
        else:
            base = f"Create '{title}' for {date_str} {time_str}"
        
        # Add timezone
        if not pending.is_all_day and pending.timezone != "UTC":
            base += f" ({pending.timezone})"
        
        # Add recurrence
        if pending.recurrence:
            recurrence_text = self._format_recurrence(pending.recurrence)
            base += f", {recurrence_text}"
        
        # Add location
        if pending.location:
            base += f", at {pending.location}"
        
        # Add highlight for edits
        if highlight_field:
            field_display = {
                "event_time": "time",
                "event_date": "date",
                "event_title": "title",
                "duration_minutes": "duration",
                "location": "location",
                "recurrence": "recurrence",
            }
            field_name = field_display.get(highlight_field, highlight_field)
            message = f"Updated {field_name}. {base}?\n\nSay 'yes' to confirm or 'no' to cancel."
        else:
            message = f"{base}?\n\nSay 'yes' to confirm, 'no' to cancel, or edit like 'change time to 8 pm'"
        
        return message
    
    def _format_recurrence(self, recurrence: str) -> str:
        """Format RRULE to human-readable text."""
        if not recurrence:
            return ""
        
        recurrence = recurrence.upper()
        
        if "FREQ=DAILY" in recurrence:
            return "repeating daily"
        elif "FREQ=WEEKLY" in recurrence:
            if "BYDAY=MO" in recurrence:
                return "repeating every Monday"
            elif "BYDAY=TU" in recurrence:
                return "repeating every Tuesday"
            elif "BYDAY=WE" in recurrence:
                return "repeating every Wednesday"
            elif "BYDAY=TH" in recurrence:
                return "repeating every Thursday"
            elif "BYDAY=FR" in recurrence:
                return "repeating every Friday"
            elif "BYDAY=SA" in recurrence:
                return "repeating every Saturday"
            elif "BYDAY=SU" in recurrence:
                return "repeating every Sunday"
            return "repeating weekly"
        elif "FREQ=MONTHLY" in recurrence:
            return "repeating monthly"
        elif "FREQ=YEARLY" in recurrence:
            return "repeating yearly"
        
        return "repeating"
    
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
        from datetime import datetime, timedelta
        
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
                            processed[key] = value
                    else:
                        # No original start, use value as-is
                        processed[key] = value
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
                            processed[key] = value
                    else:
                        processed[key] = value
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
        Build success message after calendar event creation.
        
        Example: "✓ Meeting scheduled for December 13, 2025 at 7:00 PM"
        """
        title = response.summary
        
        # Format date/time
        if pending.is_all_day:
            if pending.event_date:
                date_str = pending.event_date.strftime("%B %d, %Y")
            else:
                date_str = "the scheduled date"
            message = f"✓ '{title}' scheduled for {date_str} (all day)"
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
                    time_str = f"at {display_hour}:{minute:02d} {am_pm}"
                except:
                    time_str = f"at {pending.event_time}"
            else:
                time_str = ""
            
            message = f"✓ '{title}' scheduled for {date_str} {time_str}".strip()
        
        # Add recurrence info
        if pending.recurrence:
            recurrence_text = self._format_recurrence(pending.recurrence)
            message += f", {recurrence_text}"
        
        return message
    
    @staticmethod
    def _build_content_message(
        action: str,
        device_name: str,
        date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> str:
        """Build success message for content actions."""
        if action == "show_calendar":
            # Sprint 3.7: Include search context in message
            if search and date:
                return f"Displaying '{search}' events for {date} on {device_name}"
            elif search:
                return f"Displaying '{search}' events on {device_name}"
            elif date:
                return f"Displaying calendar for {date} on {device_name}"
            return f"Displaying calendar on {device_name}"
        elif action == "show_content":
            if search and date:
                return f"Displaying '{search}' content for {date} on {device_name}"
            elif search:
                return f"Displaying '{search}' content on {device_name}"
            elif date:
                return f"Displaying content for {date} on {device_name}"
            return f"Displaying content on {device_name}"
        elif action == "clear_content":
            return f"Cleared display on {device_name}"
        return f"Content action completed on {device_name}"

    # -----------------------------------------------------------------------
    # DOC QUERY HANDLERS (Sprint 3.9)
    # -----------------------------------------------------------------------

    async def _handle_doc_query(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Handle Google Docs intelligence queries.
        
        Sprint 3.9: Routes doc query actions:
        1. LINK_DOC: Link a document to a calendar event
        2. OPEN_DOC: Open a document linked to an event
        3. READ_DOC: Read/analyze document content
        4. SUMMARIZE_MEETING_DOC: Summarize document linked to meeting
        """
        action = intent.action
        
        # Route based on action type
        if action == ActionType.LINK_DOC:
            return await self._handle_link_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.OPEN_DOC:
            return await self._handle_open_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.READ_DOC:
            return await self._handle_read_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.SUMMARIZE_MEETING_DOC:
            return await self._handle_summarize_meeting_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.CREATE_EVENT_FROM_DOC:
            return await self._handle_create_event_from_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        else:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Unknown doc query action: {action}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_link_doc(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Link a Google Doc to a calendar event.
        
        Note: This feature requires updating calendar event extended properties,
        which needs a calendar API update method. For now, we provide helpful feedback.
        """
        from app.services.meeting_link_service import meeting_link_service
        from app.environments.google.docs import GoogleDocsClient
        
        doc_url = intent.doc_url
        meeting_search = intent.meeting_search
        
        processing_time = (time.time() - start_time) * 1000
        
        # Validate doc URL
        if not doc_url:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please provide a Google Docs URL to link.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Invalid Google Docs URL format.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Need meeting_search to find the event
        # Sprint 3.9: Use conversation context if no meeting specified
        if not meeting_search:
            context_title, context_id, context_date = self._get_event_from_context(str(user_id))
            if context_title:
                meeting_search = context_title
                logger.debug(f"Using event from context: {context_title}")
            else:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Please specify which meeting to link the document to.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
        
        try:
            # Find the meeting first
            meeting_result = await meeting_link_service.find_meeting_with_doc(
                query=meeting_search,
                user_id=user_id,
                db=db,
            )
            
            if not meeting_result.found:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=f"Could not find meeting '{meeting_search}' in your calendar.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # For now, we can't actually link the doc (requires event update API)
            # But we can provide helpful information
            doc_id = meeting_link_service.extract_doc_id_from_url(doc_url)
            processing_time = (time.time() - start_time) * 1000
            
            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                action="link_doc",
                message=f"Found meeting '{meeting_result.event.summary}'. Document linking requires calendar API update support.",
                response=f"To link documents, add the doc URL to the meeting description in Google Calendar.",
                data={"doc_url": doc_url, "doc_id": doc_id, "event_id": meeting_result.event.id},
                processing_time_ms=processing_time,
                request_id=request_id,
            )
                
        except Exception as e:
            logger.error(f"Error linking doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error linking document: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_open_doc(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Get the document linked to a calendar event.
        
        Uses find_meeting_with_doc to search for the meeting and get its linked docs.
        Returns the document URL for the client to open.
        
        Sprint 3.9: If device_name is specified, displays the doc on that device.
        """
        from app.services.meeting_link_service import meeting_link_service
        
        meeting_search = intent.meeting_search
        meeting_time = intent.meeting_time
        device_name = intent.device_name  # Sprint 3.9: Support device display
        
        processing_time = (time.time() - start_time) * 1000
        
        # Sprint 3.9: Use conversation context if no meeting specified
        # This handles "is there a doc for this event?" after showing an event
        if not meeting_search and not meeting_time:
            context_title, context_id, context_date = self._get_event_from_context(str(user_id))
            if context_title:
                meeting_search = context_title
                logger.debug(f"Using event from context: {context_title}")
            else:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Please specify which meeting's document you want to open.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
        
        try:
            # Use meeting search query or time reference
            query = meeting_search or meeting_time
            
            # Find the meeting and its linked doc
            meeting_result = await meeting_link_service.find_meeting_with_doc(
                query=query,
                user_id=user_id,
                db=db,
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            if not meeting_result.found:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=f"Could not find meeting '{query}' in your calendar.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            if not meeting_result.has_linked_doc:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="No document linked to this event.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Build doc URL from doc_id
            doc_url = f"https://docs.google.com/document/d/{meeting_result.doc_id}/edit"
            
            # Sprint 3.9: If device specified, display doc on device
            if device_name:
                # Get user's devices
                devices = self._get_user_devices(db, user_id)
                
                if devices:
                    # Find the device
                    device, match_confidence = device_mapper.match(device_name, devices)
                    
                    if device:
                        # Send show_content command with doc URL
                        result = await command_service.show_content(
                            device_id=device.id,
                            url=doc_url,
                            content_type="google_doc",
                        )
                        
                        processing_time = (time.time() - start_time) * 1000
                        
                        # Track the command
                        ai_monitor.track_command(
                            request_id=request_id,
                            device_id=device.id,
                            device_name=device.name,
                            action="show_content",
                            command_id=result.command_id,
                            success=result.success,
                            error=result.error,
                        )
                        
                        if result.success:
                            # Store doc in context for future references
                            self._store_doc_context(
                                str(user_id), 
                                meeting_result.doc_id, 
                                doc_url,
                                meeting_result.event.summary,
                            )
                            
                            return IntentResult(
                                success=True,
                                intent_type=IntentResultType.DOC_QUERY,
                                action="open_doc",
                                device=device,
                                command_sent=True,
                                command_id=result.command_id,
                                message=f"Showing document for '{meeting_result.event.summary}' on {device.name}.",
                                response=f"Document displayed on {device.name}.",
                                data={
                                    "doc_url": doc_url,
                                    "doc_id": meeting_result.doc_id,
                                    "event_title": meeting_result.event.summary,
                                },
                                processing_time_ms=processing_time,
                                request_id=request_id,
                            )
                        else:
                            return IntentResult(
                                success=False,
                                intent_type=IntentResultType.ERROR,
                                message=f"Found doc but failed to send to {device.name}: {result.error}",
                                processing_time_ms=processing_time,
                                request_id=request_id,
                            )
                    else:
                        # Device not found
                        processing_time = (time.time() - start_time) * 1000
                        return IntentResult(
                            success=False,
                            intent_type=IntentResultType.ERROR,
                            message=f"Could not find device '{device_name}'. Try 'list devices' to see available devices.",
                            processing_time_ms=processing_time,
                            request_id=request_id,
                        )
            
            # No device specified - check for display intent to auto-assign device
            # Sprint 3.9: Auto-select device for display-intent phrases
            display_keywords = ['show', 'display', 'see', 'look', 'put on', 'view', 'lemme']
            original_text = (intent.original_text or "").lower()
            
            has_display_intent = any(keyword in original_text for keyword in display_keywords)
            
            if has_display_intent:
                # User wants to SEE it - try to auto-assign device
                devices = self._get_user_devices(db, user_id)
                display_devices = [d for d in devices if d.is_online]
                
                if len(display_devices) == 1:
                    # Auto-select the only available device
                    device = display_devices[0]
                    logger.info(f"Auto-selected display device: {device.name}")
                    
                    # Send show_content command
                    result = await command_service.show_content(
                        device_id=device.id,
                        url=doc_url,
                        content_type="google_doc",
                    )
                    
                    processing_time = (time.time() - start_time) * 1000
                    
                    # Track the command
                    ai_monitor.track_command(
                        request_id=request_id,
                        device_id=device.id,
                        device_name=device.name,
                        action="show_content",
                        command_id=result.command_id,
                        success=result.success,
                        error=result.error,
                    )
                    
                    if result.success:
                        # Store doc in context
                        self._store_doc_context(
                            str(user_id),
                            meeting_result.doc_id,
                            doc_url,
                            meeting_result.event.summary,
                        )
                        
                        return IntentResult(
                            success=True,
                            intent_type=IntentResultType.DOC_QUERY,
                            action="open_doc",
                            device=device,
                            command_sent=True,
                            command_id=result.command_id,
                            message=f"Showing document for '{meeting_result.event.summary}' on {device.name}.",
                            response=f"Document displayed on {device.name}.",
                            data={
                                "doc_url": doc_url,
                                "doc_id": meeting_result.doc_id,
                                "event_title": meeting_result.event.summary,
                            },
                            processing_time_ms=processing_time,
                            request_id=request_id,
                        )
                    else:
                        return IntentResult(
                            success=False,
                            intent_type=IntentResultType.ERROR,
                            message=f"Found doc but failed to send to {device.name}: {result.error}",
                            processing_time_ms=processing_time,
                            request_id=request_id,
                        )
                elif len(display_devices) > 1:
                    # Multiple devices - ask user which one
                    device_names = ", ".join([d.name for d in display_devices])
                    processing_time = (time.time() - start_time) * 1000
                    return IntentResult(
                        success=True,
                        intent_type=IntentResultType.DOC_QUERY,
                        action="open_doc",
                        message=f"Found document for '{meeting_result.event.summary}'. Which device should I display it on?",
                        response=f"Available devices: {device_names}. Say 'show on [device name]' to display.",
                        data={
                            "doc_url": doc_url,
                            "doc_id": meeting_result.doc_id,
                            "event_title": meeting_result.event.summary,
                            "available_devices": [d.name for d in display_devices],
                        },
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )
            
            # No display intent or no devices - just return URL (query mode)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                action="open_doc",
                message=f"Opening document for '{meeting_result.event.summary}'.",
                response=f"Here's the meeting document: {doc_url}",
                data={
                    "doc_url": doc_url,
                    "doc_id": meeting_result.doc_id,
                    "event_id": meeting_result.event.id,
                    "event_title": meeting_result.event.summary,
                },
                processing_time_ms=processing_time,
                request_id=request_id,
            )
                
        except Exception as e:
            logger.error(f"Error getting linked doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error opening document: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_read_doc(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Read and analyze a Google Doc.
        
        Uses DocIntelligenceService to process the document with AI.
        """
        from app.services.doc_intelligence_service import doc_intelligence_service
        from app.environments.google.docs import GoogleDocsClient
        from app.models.oauth_credential import OAuthCredential
        
        doc_url = intent.doc_url
        question = intent.question
        
        processing_time = (time.time() - start_time) * 1000
        
        if not doc_url:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please provide a Google Docs URL to read.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Invalid Google Docs URL format.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        try:
            # Get OAuth credentials from database
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()
            
            if not credentials or not credentials.access_token:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Google account not connected. Please link your account first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Fetch the document
            doc_id = GoogleDocsClient.extract_doc_id(doc_url)
            docs_client = GoogleDocsClient(access_token=credentials.access_token)
            doc = await docs_client.get_document(doc_id)
            doc_content = doc.to_doc_content()
            
            # Analyze/summarize the document
            summary_result = await doc_intelligence_service.summarize_document(
                doc_content=doc_content,
                question=question,
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            if not summary_result.error:
                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.DOC_QUERY,
                    action="read_doc",
                    message=summary_result.summary,
                    response=summary_result.summary,
                    data={
                        "doc_url": doc_url,
                        "title": summary_result.title,
                        "word_count": summary_result.word_count,
                        "model_used": summary_result.model_used,
                    },
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            else:
                error_msg = summary_result.error
                # Handle specific error cases
                if "404" in error_msg or "not found" in error_msg.lower():
                    error_msg = "Document not found. Please check the URL."
                elif "403" in error_msg or "permission" in error_msg.lower():
                    error_msg = "You don't have access to this document."
                    
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=error_msg,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
                
        except Exception as e:
            logger.error(f"Error reading doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "Document not found. Please check the URL."
            elif "403" in error_msg or "permission" in error_msg.lower():
                error_msg = "You don't have access to this document."
            else:
                error_msg = f"Error reading document: {error_msg}"
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=error_msg,
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_summarize_meeting_doc(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Summarize a document linked to a meeting.
        
        Finds the meeting by search/time reference, gets its linked doc,
        then uses DocIntelligenceService to generate a summary.
        """
        from app.services.doc_intelligence_service import doc_intelligence_service
        from app.services.meeting_link_service import meeting_link_service
        from app.environments.google.docs import GoogleDocsClient
        from app.models.oauth_credential import OAuthCredential
        
        doc_url = intent.doc_url
        meeting_search = intent.meeting_search
        meeting_time = intent.meeting_time
        
        processing_time = (time.time() - start_time) * 1000
        
        # If no doc URL, try to find the meeting's linked doc
        if not doc_url:
            # Sprint 3.9: Use conversation context if no meeting specified
            if not meeting_search and not meeting_time:
                context_title, context_id, context_date = self._get_event_from_context(str(user_id))
                if context_title:
                    meeting_search = context_title
                    logger.debug(f"Using event from context: {context_title}")
                else:
                    return IntentResult(
                        success=False,
                        intent_type=IntentResultType.ERROR,
                        message="Please specify which meeting's document you want to summarize, or provide a Google Docs URL.",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )
            
            # Find the meeting and its linked doc
            query = meeting_search or meeting_time
            meeting_result = await meeting_link_service.find_meeting_with_doc(
                query=query,
                user_id=user_id,
                db=db,
            )
            
            if not meeting_result.found:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=f"Could not find meeting '{query}' in your calendar.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            if not meeting_result.has_linked_doc:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="This meeting doesn't have a linked document.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Build doc URL from doc_id
            doc_url = f"https://docs.google.com/document/d/{meeting_result.doc_id}/edit"
        
        # Now we have a doc_url, validate and summarize
        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Invalid Google Docs URL format.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        try:
            # Get OAuth credentials from database
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()
            
            if not credentials or not credentials.access_token:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Google account not connected. Please link your account first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Fetch the document
            doc_id = GoogleDocsClient.extract_doc_id(doc_url)
            docs_client = GoogleDocsClient(access_token=credentials.access_token)
            doc = await docs_client.get_document(doc_id)
            doc_content = doc.to_doc_content()
            
            # Summarize the document
            summary_result = await doc_intelligence_service.summarize_document(
                doc_content=doc_content,
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            if not summary_result.error:
                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.DOC_QUERY,
                    action="summarize_meeting_doc",
                    message=summary_result.summary,
                    response=summary_result.summary,
                    data={
                        "doc_url": doc_url,
                        "title": summary_result.title,
                        "word_count": summary_result.word_count,
                        "is_complex": summary_result.is_complex,
                        "model_used": summary_result.model_used,
                    },
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            else:
                error_msg = summary_result.error
                if "404" in error_msg or "not found" in error_msg.lower():
                    error_msg = "Document not found. Please check the URL."
                elif "403" in error_msg or "permission" in error_msg.lower():
                    error_msg = "You don't have access to this document."
                    
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=error_msg,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
                
        except Exception as e:
            logger.error(f"Error summarizing doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "Document not found. Please check the URL."
            elif "403" in error_msg or "permission" in error_msg.lower():
                error_msg = "You don't have access to this document."
            else:
                error_msg = f"Error summarizing document: {error_msg}"
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=error_msg,
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_create_event_from_doc(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Create a calendar event from document content.
        
        Sprint 3.9: Extract meeting details from doc and create event.
        
        Flow:
        1. Fetch and read the document
        2. Extract meeting details using LLM
        3. If missing date/time, ask user for clarification
        4. Create the calendar event
        5. Link the document to the event (in description)
        """
        from app.services.doc_intelligence_service import doc_intelligence_service
        from app.environments.google.docs import GoogleDocsClient
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        
        doc_url = intent.doc_url
        
        processing_time = (time.time() - start_time) * 1000
        
        if not doc_url:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please provide a Google Doc URL to create an event from.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Validate and extract doc ID
        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="That doesn't look like a valid Google Docs URL.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        doc_id = GoogleDocsClient.extract_doc_id(doc_url)
        
        # Get credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials or not credentials.access_token:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please connect Google to create calendar events.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        try:
            # Fetch document content
            doc_content = await doc_intelligence_service.get_document_for_user(
                doc_id=doc_id,
                user_id=user_id,
                db=db,
            )
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "Document not found. Please check the URL."
            elif "403" in error_msg or "permission" in error_msg.lower():
                error_msg = "I can't access that document. Please check sharing permissions."
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=error_msg,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Extract meeting details using LLM
        details = await doc_intelligence_service.extract_meeting_details(doc_content)
        
        if details.error:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Could not extract meeting details: {details.error}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Check if we need clarification (missing date/time)
        if details.needs_clarification:
            # Get user timezone for pending event
            try:
                calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
                user_tz = await calendar_client.get_user_timezone()
            except Exception:
                user_tz = "UTC"
            
            # Store pending event with doc metadata for follow-up
            from app.services.pending_event_service import pending_event_service
            await pending_event_service.store_pending(
                user_id=str(user_id),
                event_title=details.event_title or doc_content.title,
                event_date=None,  # Missing - user will provide
                event_time=None,  # Missing - user will provide
                duration_minutes=details.duration_minutes or 60,
                location=details.location,
                timezone=user_tz,
                original_text=intent.original_text,
                # Doc metadata
                doc_id=doc_id,
                doc_url=doc_url,
                source="doc",
            )
            
            missing = " and ".join(details.missing_fields)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DOC_QUERY,
                action="create_event_from_doc",
                message=f"I found the document '{doc_content.title}' but couldn't find the {missing}. When should this meeting be scheduled?",
                data={
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "extracted_title": details.event_title,
                    "missing_fields": details.missing_fields,
                    "pending": True,  # Flag to indicate pending event stored
                },
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Create the calendar event
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            
            # Get user timezone
            user_tz = await calendar_client.get_user_timezone()
            tz = ZoneInfo(user_tz)
            
            # Parse date and time
            from datetime import datetime as dt
            event_date = dt.strptime(details.event_date, "%Y-%m-%d")
            hour, minute = map(int, details.event_time.split(":"))
            
            start_dt = event_date.replace(hour=hour, minute=minute, tzinfo=tz)
            end_dt = start_dt + timedelta(minutes=details.duration_minutes)
            
            # Build description with doc link
            description = details.description or ""
            description += f"\n\n📄 Meeting Document: {doc_url}"
            
            # Create event
            event = await calendar_client.create_event(
                summary=details.event_title,
                start_datetime=start_dt,
                end_datetime=end_dt,
                description=description,
                location=details.location,
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            # Store event in conversation context
            self._store_event_context(str(user_id), event)
            
            # Format time for response
            time_str = start_dt.strftime("%I:%M %p").lstrip("0")
            date_str = start_dt.strftime("%B %d, %Y")
            
            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                action="create_event_from_doc",
                message=f"Created event '{details.event_title}' on {date_str} at {time_str}.",
                response=f"I've created the meeting '{details.event_title}' for {date_str} at {time_str} and linked the document.",
                data={
                    "event_id": event.id,
                    "event_title": details.event_title,
                    "event_date": details.event_date,
                    "event_time": details.event_time,
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                },
                processing_time_ms=processing_time,
                request_id=request_id,
            )
            
        except Exception as e:
            logger.error(f"Failed to create event from doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to create event: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

intent_service = IntentService()
