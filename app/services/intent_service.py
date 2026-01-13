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
    DisplayContentIntent,
    ConversationIntent,
    SequentialAction,  # Sprint 4.0.3: Multi-action support
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
    DISPLAY_CONTENT = "display_content"  # Sprint 4.0: Scene Graph
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
            
            # Sprint 5.1.4: Unified context building with anaphoric resolution
            # Replaces 30+ lines of manual context assembly with single call
            from app.ai.context import build_request_context
            
            request_context = build_request_context(
                text=text,
                user_id=str(user_id),
                devices=device_context,
            )
            
            # Convert to dict for downstream compatibility
            context = request_context.to_dict()
            
            # Log pending state for debugging
            if request_context.has_pending():
                pending_op = request_context.pending_operation
                logger.info(
                    f"[PENDING_STATE] request_id={request_id}, "
                    f"pending_op_type={pending_op.get('pending_op_type')}, "
                    f"pending_op_age={pending_op.get('pending_op_age_seconds')}s, "
                    f"hint={pending_op.get('pending_op_hint')}"
                )
            
            # Log resolved references for debugging
            if request_context.resolved_references:
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] request_id={request_id}, "
                    f"resolved={list(request_context.resolved_references.keys())}"
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
            # Sprint 9: Both complex_execution and complex_reasoning now use Gemini
            if routing_decision.complexity == TaskComplexity.COMPLEX_EXECUTION:
                return await self._handle_complex_task(
                    request_id=request_id,
                    text=text,
                    routing_decision=routing_decision,
                    context=context,
                    start_time=start_time,
                    provider="gemini",  # Sprint 9: Migrated from OpenAI to Gemini
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
                    provider="gemini",  # Sprint 9: Migrated from Anthropic to Gemini
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
                user_id=user_id,
                original_text=text,
                start_time=start_time,
            )
        
        elif isinstance(intent, CalendarQueryIntent):
            return await self._handle_calendar_query(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                original_text=text,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
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
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
            )
        
        elif isinstance(intent, DocQueryIntent):
            return await self._handle_doc_query(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
            )
        
        elif isinstance(intent, DisplayContentIntent):
            return await self._handle_display_content(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                devices=devices,
                start_time=start_time,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
            )
        
        elif isinstance(intent, ConversationIntent):
            return await self._handle_conversation(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
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
            primary_result = await self._execute_content_action(
                request_id=request_id,
                device=device,
                action=action,
                user_id=user_id,
                parameters=intent.parameters,
                confidence=intent.confidence,
                start_time=start_time,
            )
        else:
            # Standard device commands
            primary_result = await self._execute_device_command(
                request_id=request_id,
                device=device,
                action=action,
                parameters=intent.parameters,
                confidence=intent.confidence,
                start_time=start_time,
            )
        
        # Sprint 4.0.3: Process sequential actions if present
        if intent.sequential_actions and primary_result.success:
            primary_result = await self._execute_sequential_actions(
                primary_result=primary_result,
                sequential_actions=intent.sequential_actions,
                devices=devices,
                user_id=user_id,
                primary_device=device,
                start_time=start_time,
            )
        
        return primary_result
    
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
        user_id: UUID,
        original_text: str,
        start_time: float,
    ) -> IntentResult:
        """
        Handle system queries with multilingual, context-aware responses.
        
        Sprint 4.1: Now uses Gemini to generate natural responses in the user's language.
        """
        from app.ai.providers.gemini import gemini_provider
        from app.ai.context import build_unified_context
        from app.db.session import SessionLocal
        
        action = self._get_action_value(intent.action) or "help"
        
        # Build context
        db = SessionLocal()
        try:
            context = await build_unified_context(user_id=user_id, db=db)
        finally:
            db.close()
        
        # System prompt with multilingual rule
        system_prompt = f"""You are Jarvis, a helpful assistant.

CRITICAL: ALWAYS respond in the SAME LANGUAGE the user is speaking.
- Spanish input → Spanish output
- English input → English output
- French input → French output

USER SETUP:
- Name: {context.user_name}
- Devices: {context.device_count} total, {len(context.online_devices)} online
- Calendar: {"Connected" if context.has_google_calendar else "Not connected"}
- Docs: {"Connected" if context.has_google_docs else "Not connected"}

Respond naturally and concisely (1-3 sentences)."""
        
        # Build action-specific prompts
        if action == "list_devices":
            if not devices:
                user_prompt = f'User asked to list devices: "{original_text}"\n\nThey have none. Explain kindly and suggest adding one. Respond in their language.'
            else:
                device_list = "\n".join([f"- {d.name} ({'online' if d.is_online else 'offline'})" for d in devices])
                user_prompt = f'''User asked to list devices: "{original_text}"

Their devices:
{device_list}

Present with emojis (🟢 online, 🔴 offline) in the SAME language as the user's request.'''
        
        elif action == "help":
            device_examples = [d.device_name for d in context.online_devices[:2]] if context.online_devices else ["your TV", "your screen"]
            user_prompt = f'''User asked for help: "{original_text}"

Their setup:
- {context.device_count} device(s): {", ".join(device_examples)}
- Calendar: {"available" if context.has_google_calendar else "not connected"}
- Docs: {"available" if context.has_google_docs else "not connected"}

Provide 3-5 example commands customized to their setup.
Respond in the SAME language as their request.'''
        
        else:
            user_prompt = f'User said: "{original_text}"\n\nRespond helpfully in their language.'
        
        # Generate response
        response = await gemini_provider.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=400,
        )
        
        processing_time = (time.time() - start_time) * 1000
        message = response.content.strip() if response.success else "How can I help with your devices?"
        
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
        original_text: str = "",
        db: Session = None,
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Handle calendar query intents - questions about calendar events.
        
        Sprint 3.8: Returns text answers to calendar questions like:
        - "How many events today?" → count_events
        - "What's my next meeting?" → next_event
        - "List my events for tomorrow" → list_events
        - "When is my birthday?" → find_event
        
        Sprint 3.9: Uses smart semantic search for typos/translations/synonyms.
        Sprint 4.1: Returns context-aware, multilingual responses.
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunión").
        """
        from app.services.calendar_search_service import calendar_search_service
        from app.models.oauth_credential import OAuthCredential
        from app.db.session import SessionLocal
        from datetime import datetime, timezone, timedelta
        
        action = self._get_action_value(intent.action) or "count_events"
        date_range = intent.date_range
        search_term = intent.search_term
        
        # Sprint 5.1.4: Resolve anaphoric reference if no explicit search_term
        if not search_term and context and context.get("resolved_references"):
            resolved_event = context["resolved_references"].get("event")
            if resolved_event and resolved_event.get("title"):
                search_term = resolved_event["title"]
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved event from context: {search_term}"
                )
        
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
            
            # Route to appropriate query method using SMART SEARCH (Sprint 4.1: multilingual)
            if action == "find_event":
                # Find a specific event (e.g., "when is my birthday?")
                message = await self._smart_find_event(
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                    original_text=original_text,
                )
            elif action == "next_event":
                # Find the next event matching a term (e.g., "what's my next meeting?")
                message = await self._smart_next_event(
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                    original_text=original_text,
                )
            elif action == "count_events":
                # Count events (e.g., "how many events today?")
                message = await self._smart_count_events(
                    date_range=date_range,
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                    original_text=original_text,
                )
            elif action == "list_events":
                # List events (e.g., "list my events for tomorrow")
                message = await self._smart_list_events(
                    date_range=date_range,
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                    original_text=original_text,
                )
            else:
                # Fallback to count
                message = await self._smart_count_events(
                    date_range=date_range,
                    search_term=search_term,
                    user_id=user_id,
                    db=db,
                    original_text=original_text,
                )
            
            processing_time = (time.time() - start_time) * 1000

            # Sprint 4.3.0: Save calendar query response to conversation context
            from app.services.conversation_context_service import conversation_context_service
            conversation_context_service.add_conversation_turn(
                user_id=str(user_id),
                user_message=original_text,
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
    # SMART CALENDAR QUERY HELPERS (Sprint 3.9 + Sprint 4.1 Multilingual)
    # -----------------------------------------------------------------------
    
    async def _generate_calendar_response(
        self,
        template_type: str,
        user_request: str,
        user_id: UUID,
        db: Session,
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
            user_id: User's ID
            db: Database session
            **kwargs: Template-specific parameters
        
        Returns:
            Natural, context-aware response in user's language
        """
        from app.ai.providers.gemini import gemini_provider
        from app.ai.context import build_unified_context
        
        # Build context
        context = await build_unified_context(user_id=user_id, db=db)
        
        # Build system prompt with context
        system_prompt = f"""You are Jarvis, {context.user_name}'s intelligent assistant.

CRITICAL: ALWAYS respond in the SAME LANGUAGE the user is speaking.
- Spanish input → Spanish output
- English input → English output
- French input → French output

USER SETUP:
- Name: {context.user_name}
- Google Calendar: {"✓ Connected" if context.has_google_calendar else "✗ Not connected"}
- Devices: {len(context.online_devices)} online

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
- Spanish: "Sí, tienes 1 evento {period}: {title} a las {time_str}"
- English: "Yes, you have 1 event {period}: {title} at {time_str}"

Use EXACTLY 1 event. DO NOT say 100 or any other number. Respond in their language.'''
                else:
                    # Fallback if no event object provided
                    prompt = f'''User asked: "{user_request}"

FACT: Event count = 1 (ONE)

You MUST respond with:
- Spanish: "Sí, tienes 1 evento{' de ' + search if search else ''} {period}"
- English: "Yes, you have 1 {search + ' ' if search else ''}event {period}"

Use EXACTLY the number 1. DO NOT say 100 or any other number. Respond in their language.'''
            else:
                # Sprint 4.3.3: Strict format for multiple events to prevent hallucination
                prompt = f'''User asked: "{user_request}"

FACT: Event count = {count}

You MUST respond with the EXACT count from FACT above:
- Spanish: "Sí, tienes {count} eventos{' de ' + search if search else ''} {period}"
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
                if not any(word in response_text.lower() for word in ['no ', 'zero', 'cero', 'ninguna', 'ningún']):
                    logger.warning(f"Count template hallucination detected: count={count_value}, response='{response_text[:50]}'")
                    # Override with explicit template
                    search_term = kwargs.get('search_term', 'eventos' if ('es' in user_request.lower() or 'ñ' in user_request) else 'events')
                    period = kwargs.get('period', '')
                    if 'es' in user_request.lower() or 'ñ' in user_request:
                        response.content = f"No tienes {search_term} {period}.".strip()
                    else:
                        response.content = f"You don't have any {search_term} {period}.".strip()

        return response.content.strip() if response.success else "I couldn't process that request."
    
    async def _smart_find_event(
        self,
        search_term: str,
        user_id: UUID,
        db: Session,
        original_text: str = "",
    ) -> str:
        """
        Find a specific event using smart semantic search.
        
        Sprint 4.1: Now returns context-aware, multilingual responses.
        
        Handles typos, translations, and synonyms:
        - "birthday" matches "Cumpleaños de Victor"
        - "birday" matches "Birthday party"
        - "cumpleanos" matches "Cumpleaños"
        """
        from app.services.calendar_search_service import calendar_search_service
        
        if not search_term:
            return await self._generate_calendar_response(
                template_type="need_search",
                user_request=original_text or "find event",
                user_id=user_id,
                db=db,
            )
        
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
            return await self._generate_calendar_response(
                template_type="not_found",
                user_request=original_text or search_term,
                user_id=user_id,
                db=db,
                search_term=corrected,
            )
        
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
            
            return await self._generate_calendar_response(
                template_type="find",
                user_request=original_text or search_term,
                user_id=user_id,
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
                user_id=user_id,
                db=db,
                event=event,
                date_str=event.start.date,
                time_str="all day",
                relative="",
            )
        
        return f"Found '{title}' on your calendar."
    
    async def _smart_next_event(
        self,
        search_term: str,
        user_id: UUID,
        db: Session,
        original_text: str = "",
    ) -> str:
        """
        Find the next event matching a term using smart search.
        
        Sprint 4.1: Now returns context-aware, multilingual responses.
        """
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
            return await self._generate_calendar_response(
                template_type="no_events",
                user_request=original_text or f"next {search_term or 'event'}",
                user_id=user_id,
                db=db,
                search_term=search_term or "upcoming",
                period="",
            )
        
        event = result.events[0]
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
            
            return await self._generate_calendar_response(
                template_type="next",
                user_request=original_text or f"next {search_term or 'event'}",
                user_id=user_id,
                db=db,
                event=event,
                time_str=time_str,
                relative=relative,
                search_term=search_term,
            )
        
        return await self._generate_calendar_response(
            template_type="next",
            user_request=original_text or f"next {search_term or 'event'}",
            user_id=user_id,
            db=db,
            event=event,
            time_str=time_str,
            relative="",
            search_term=search_term,
        )
    
    async def _smart_count_events(
        self,
        date_range: str,
        search_term: str,
        user_id: UUID,
        db: Session,
        original_text: str = "",
    ) -> str:
        """
        Count events using smart search for semantic matching.
        
        Sprint 4.1: Now returns context-aware, multilingual responses.
        """
        from app.services.calendar_search_service import calendar_search_service
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential
        
        # If there's a search term, use smart search with date filtering
        if search_term:
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=user_id,
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
                    user_id=user_id,
                    db=db,
                    search_term=corrected,
                    period=period,
                )
            else:
                # If count=1, include event details in response
                kwargs_dict = {
                    "template_type": "count",
                    "user_request": original_text or f"count {search_term}",
                    "user_id": user_id,
                    "db": db,
                    "count": count,
                    "search_term": corrected,
                    "period": period,
                }
                if count == 1 and result.events:
                    kwargs_dict["event"] = result.events[0]

                return await self._generate_calendar_response(**kwargs_dict)
        
        # No search term - fetch events and use multilingual generator
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return await self._generate_calendar_response(
                template_type="not_found",
                user_request=original_text or "count events",
                user_id=user_id,
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
                user_id=user_id,
                db=db,
                search_term="",
                period=period,
            )
        else:
            # If count=1, include event details in response
            kwargs_dict = {
                "template_type": "count",
                "user_request": original_text or "count events",
                "user_id": user_id,
                "db": db,
                "count": count,
                "search_term": "",
                "period": period,
            }
            if count == 1 and events:
                kwargs_dict["event"] = events[0]

            return await self._generate_calendar_response(**kwargs_dict)
    
    async def _smart_list_events(
        self,
        date_range: str,
        search_term: str,
        user_id: UUID,
        db: Session,
        original_text: str = "",
    ) -> str:
        """
        List events using smart search for semantic matching.
        
        Sprint 4.1: Now returns context-aware, multilingual responses.
        """
        from app.services.calendar_search_service import calendar_search_service
        from app.environments.google.calendar.client import GoogleCalendarClient
        from app.models.oauth_credential import OAuthCredential
        
        # If there's a search term, use smart search with date filtering
        if search_term:
            result = await calendar_search_service.smart_search(
                user_query=search_term,
                user_id=user_id,
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
                    user_id=user_id,
                    db=db,
                    search_term=corrected,
                    period=period,
                )
            
            return await self._generate_calendar_response(
                template_type="list",
                user_request=original_text or f"list {search_term}",
                user_id=user_id,
                db=db,
                events=result.events,
                search_term=corrected,
                period=period,
            )
        
        # No search term - fetch events and use multilingual generator
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return await self._generate_calendar_response(
                template_type="not_found",
                user_request=original_text or "list events",
                user_id=user_id,
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
                user_id=user_id,
                db=db,
                search_term="",
                period=period,
            )
        
        return await self._generate_calendar_response(
            template_type="list",
            user_request=original_text or "list events",
            user_id=user_id,
            db=db,
            events=events,
            search_term="",
            period=period,
        )
    
    def _get_period_text(self, date_range: str) -> str:
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
        user_id: UUID,
        original_text: str,
        start_time: float,
    ) -> IntentResult:
        """
        Handle conversational intents with context-aware, multilingual responses.
        
        Sprint 4.1: Uses Gemini with context awareness, conversation history,
        and Google Search grounding for intelligent, personalized answers.
        
        Features:
        - Maintains conversation history across turns
        - Handles follow-up confirmations like "si", "hazlo", "do it"
        - Uses web search for real-time information
        - Responds in the user's language
        """
        from app.ai.providers.gemini import gemini_provider
        from app.ai.prompts.assistant_prompts import (
            build_assistant_system_prompt,
            build_assistant_prompt,
        )
        from app.ai.context import build_unified_context
        from app.db.session import SessionLocal
        from app.services.conversation_context_service import conversation_context_service
        
        # Build context
        db = SessionLocal()
        try:
            context = await build_unified_context(user_id=user_id, db=db)
        finally:
            db.close()
        
        # Sprint 4.1: Get conversation history for context
        conversation_history = conversation_context_service.get_conversation_summary(str(user_id))
        pending_content = conversation_context_service.get_pending_content_request(str(user_id))
        
        # Build prompts with context and conversation history
        system_prompt = build_assistant_system_prompt(context)
        
        # Check if this is a follow-up/confirmation to previous request
        follow_up_keywords = [
            'si', 'sí', 'yes', 'ok', 'okay', 'hazlo', 'do it', 'adelante',
            'proceed', 'confirma', 'confirmo', 'confirm', 'solo', 'just',
            'redactalo', 'redáctalo', 'escribelo', 'escríbelo', 'write it',
            'generate it', 'crealo', 'créalo', 'create it', 'muéstramelo',
            'muestramelo', 'show it', 'go ahead', 'sure', 'claro',
        ]
        
        is_follow_up = (
            pending_content and 
            any(kw in original_text.lower() for kw in follow_up_keywords)
        )
        
        # Build user prompt with conversation context
        if is_follow_up and pending_content:
            # User is confirming a previous content generation request
            logger.info(
                f"[{request_id}] Follow-up detected for pending content: "
                f"{pending_content['type']} - {pending_content['request'][:50]}..."
            )
            user_prompt = f"""The user previously asked for: {pending_content['request']}

Now they're confirming with: "{original_text}"

Please fulfill their original request and generate the content they asked for.
Respond in the same language they used originally.
"""
            # Clear the pending content after fulfilling
            conversation_context_service.clear_pending_content(str(user_id))
        elif conversation_history:
            # Include conversation history for context
            # Sprint 4.2.4: Clearer prompt to prevent model confusion
            user_prompt = f"""=== PREVIOUS CONVERSATION (for context only) ===
{conversation_history}
=== END OF HISTORY ===

>>> CURRENT USER MESSAGE (respond to THIS): <<<
"{original_text}"

IMPORTANT INSTRUCTIONS:
1. Answer ONLY the current message above, NOT previous questions from the history
2. Use the conversation history ONLY as background context
3. If the user is correcting you or changing topic, acknowledge it and respond to their NEW question
4. Respond in the same language as the current message"""
        else:
            user_prompt = build_assistant_prompt(original_text, context)
        
        # Determine if web search is needed
        # Sprint 4.5.0: Expanded keywords for Spanish queries and general updates
        search_keywords = [
            # Weather
            'weather', 'temperature', 'forecast', 'clima', 'tiempo', 'pronóstico',
            # Time
            'time', 'clock', 'timezone', 'hora',
            # News/Updates (Sprint 4.5.0: Added Spanish equivalents)
            'news', 'latest', 'today', 'noticias',
            'últimas', 'actualizaciones', 'updates', 'novedades',
            'recent', 'reciente', 'cambios', 'changes',
            # Sports
            'score', 'game', 'match', 'partido',
            # Finance
            'stock', 'price', 'precio',
            # Current/Now
            'current', 'now', 'hoy', 'ahora', 'actual',
        ]
        
        use_search = any(keyword in original_text.lower() for keyword in search_keywords)
        
        # Detect if this is a content generation request to save for follow-up
        content_gen_keywords = [
            'template', 'plantilla', 'nota', 'notes', 'checklist',
            'lista', 'resumen', 'summary', 'tutorial', 'tips',
            'redacta', 'crea', 'create', 'hazme', 'dame', 'give me',
            'necesito', 'i need', 'generate', 'genera',
        ]
        is_content_request = any(kw in original_text.lower() for kw in content_gen_keywords)
        
        # Generate intelligent response
        if use_search:
            response = await gemini_provider.generate_with_grounding(
                prompt=user_prompt,
                system_prompt=system_prompt,
                use_search=True,
                temperature=0.8,
                max_tokens=1024,  # Increased for content generation
            )
        else:
            response = await gemini_provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=1024,  # Increased for content generation
            )
        
        processing_time = (time.time() - start_time) * 1000

        if not response.success:
            # Fallback: Generate error message in user's language WITHOUT grounding
            try:
                error_response = await gemini_provider.generate(
                    prompt=f"User said: '{original_text}'\n\nRespond with a brief, friendly apology that you're having trouble right now. Ask them to rephrase or try again.",
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=100,
                )
                if error_response.success:
                    message = error_response.content.strip()
                else:
                    message = "Lo siento, estoy teniendo problemas procesando eso. ¿Podrías reformular? / I apologize, I'm having trouble processing that. Could you rephrase?"
            except Exception as e:
                logger.error(f"Error generating fallback message: {e}")
                message = "Lo siento, estoy teniendo problemas procesando eso. ¿Podrías reformular? / I apologize, I'm having trouble processing that. Could you rephrase?"
        else:
            message = response.content.strip()
        
        # Sprint 4.2: Detect and store generated content for memory-aware display
        content_type = self._detect_content_type(original_text, message)
        if content_type:
            title = self._extract_content_title(original_text, message)
            conversation_context_service.set_generated_content(
                user_id=str(user_id),
                content=message,
                content_type=content_type,
                title=title,
            )
            logger.info(
                f"[{request_id}] Stored generated content: type={content_type}, title={title}"
            )
        
        # Sprint 4.1: Save conversation turn for future context
        conversation_context_service.add_conversation_turn(
            user_id=str(user_id),
            user_message=original_text,
            assistant_response=message,
            intent_type="conversation",
        )
        
        # If this was a content generation request, save it for potential follow-up
        # (only if the response seems like it's asking for confirmation)
        if is_content_request and not is_follow_up:
            # Detect if AI is asking for clarification/confirmation
            clarification_indicators = [
                '?', '¿', 'could you', 'podrías', 'would you like',
                'te gustaría', 'quieres que', 'do you want', 'should i',
                'more details', 'más detalles', 'clarify', 'especifica',
            ]
            if any(ind in message.lower() for ind in clarification_indicators):
                # AI is asking for more info, save the request for follow-up
                conversation_context_service.set_pending_content_request(
                    user_id=str(user_id),
                    content_request=original_text,
                    content_type="content_generation",
                )
        
        action = self._get_action_value(intent.action) or "general_conversation"
        
        return IntentResult(
            success=True,
            intent_type=IntentResultType.CONVERSATION,
            confidence=intent.confidence,
            action=action,
            message=message,
            response=message,
            processing_time_ms=processing_time,
            request_id=request_id,
            data={
                'grounded': response.metadata.get('grounded', False) if response.metadata else False,
                'sources': response.metadata.get('sources', []) if response.metadata else [],
                'conversation_context_used': bool(conversation_history),
                'was_follow_up': is_follow_up,
            } if response.success else None,
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
        provider: str,  # Sprint 9: Deprecated - all tasks now use Gemini
        db: Session,
        user_id: UUID,
    ) -> IntentResult:
        """Handle complex tasks using Gemini with thinking mode (Sprint 9)."""
        from app.ai.providers.gemini import gemini_provider
        from app.ai.context import build_unified_context
        from app.ai.prompts.execution_prompts import build_execution_prompt
        from app.ai.prompts.base_prompt import build_reasoner_prompt
        from app.ai.schemas.action_response import (
            parse_action_response,
            ActionResponse,
            ClarificationResponse,
            ActionSequenceResponse,
        )

        # Sprint 9: All complex tasks now use Gemini 3 Flash (cost optimization)
        ai_provider = gemini_provider
        model_name = settings.GEMINI_REASONING_MODEL  # Gemini 3 Flash for complex tasks

        # Determine task type from routing decision
        if routing_decision.complexity == TaskComplexity.COMPLEX_EXECUTION:
            task_type = "execution"
        else:
            task_type = "reasoning"
        
        ai_monitor.track_event(
            request_id=request_id,
            event_type="complex_task_routing",
            data={
                "provider": "gemini",
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
        
        # Sprint 4.2.8: Get conversation history for context-aware delegation
        from app.services.conversation_context_service import conversation_context_service
        conversation_history = conversation_context_service.get_conversation_summary(str(user_id))

        # Build prompt and call AI
        # Sprint 9: All complex tasks use Gemini 3 Flash
        if task_type == "execution":
            prompt = build_execution_prompt(unified_context, text, conversation_history, routing_decision) if unified_context else text
            system_prompt = "You are a smart display execution assistant. Return valid JSON."
        else:
            prompt = build_reasoner_prompt(unified_context, text, conversation_history, routing_decision) if unified_context else text
            system_prompt = "You are a strategic advisor for smart home systems."

        # Sprint 9: Use Gemini 3 Flash for all complex tasks (no thinking mode)
        response = await ai_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model_override=settings.GEMINI_REASONING_MODEL,
            max_tokens=8192,  # Sufficient for complex task responses
        )
        processing_time = (time.time() - start_time) * 1000
        
        if not response.success:
            ai_monitor.track_response(
                request_id=request_id,
                provider="gemini",
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
            provider="gemini",
            model=model_name,
            content=response.content[:500] if response.content else "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            latency_ms=processing_time,
            success=True,
        )
        
        # Handle reasoning tasks (return text response)
        if task_type == "reasoning":
            # Sprint 4.2.9: Save Claude's response to conversation context
            conversation_context_service.add_conversation_turn(
                user_id=str(user_id),
                user_message=text,
                assistant_response=response.content,
                intent_type="complex_reasoning",
            )

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
                # Sprint 4.2.9: Save GPT's clarification to conversation context
                conversation_context_service.add_conversation_turn(
                    user_id=str(user_id),
                    user_message=text,
                    assistant_response=action_response.message,
                    intent_type="complex_execution_clarification",
                )

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
                result = await self._execute_gpt_action(
                    action_response=action_response,
                    request_id=request_id,
                    user_id=user_id,
                    db=db,
                    processing_time=processing_time,
                    routing_confidence=routing_decision.confidence,
                )

                # Sprint 4.2.9: Save GPT's action execution to conversation context
                conversation_context_service.add_conversation_turn(
                    user_id=str(user_id),
                    user_message=text,
                    assistant_response=result.message or f"Executed {action_response.action_name}",
                    intent_type="complex_execution",
                )

                return result
            
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
                combined_message = "\n".join(messages)

                # Sprint 4.2.9: Save GPT's action sequence to conversation context
                conversation_context_service.add_conversation_turn(
                    user_id=str(user_id),
                    user_message=text,
                    assistant_response=combined_message or f"Executed {len(results)} actions",
                    intent_type="complex_execution_sequence",
                )

                return IntentResult(
                    success=all_success,
                    intent_type=IntentResultType.ACTION_SEQUENCE,
                    confidence=routing_decision.confidence,
                    message=combined_message,
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
    # SEQUENTIAL ACTIONS (Sprint 4.0.3 - Multi-Action Support)
    # -----------------------------------------------------------------------
    
    async def _execute_sequential_actions(
        self,
        primary_result: IntentResult,
        sequential_actions: List[SequentialAction],
        devices: List[Device],
        user_id: UUID,
        primary_device: Device,
        start_time: float,
    ) -> IntentResult:
        """
        Execute sequential actions after a primary action.
        
        Sprint 4.0.3: Allows users to chain multiple actions in a single request,
        e.g., "clear the screen AND show my calendar".
        
        Args:
            primary_result: Result from the primary action
            sequential_actions: List of additional actions to execute
            devices: Available devices for the user
            user_id: User's UUID
            primary_device: The device from the primary action
            start_time: Start time for total processing time calculation
            
        Returns:
            Updated IntentResult with all actions executed
        """
        actions_executed = [
            {
                "action": primary_result.action,
                "success": primary_result.success,
                "command_id": primary_result.command_id,
                "device": primary_result.device.name if primary_result.device else None,
            }
        ]
        
        all_messages = [primary_result.message] if primary_result.message else []
        total_commands_sent = 1 if primary_result.command_sent else 0
        all_success = primary_result.success
        
        logger.info(
            f"Executing {len(sequential_actions)} sequential actions after '{primary_result.action}'"
        )
        
        for seq_action in sequential_actions:
            try:
                # Resolve device: use specified device_name or inherit from primary
                target_device = primary_device
                if seq_action.device_name:
                    matched_device, _ = device_mapper.match(seq_action.device_name, devices)
                    if matched_device:
                        target_device = matched_device
                    else:
                        logger.warning(
                            f"Device '{seq_action.device_name}' not found for sequential action, "
                            f"using primary device '{primary_device.name}'"
                        )
                
                action_name = seq_action.action
                params = seq_action.parameters or {}
                
                # Execute based on action type
                if action_registry.is_content_action(action_name):
                    action_result = await self._execute_content_action(
                        request_id=primary_result.request_id,
                        device=target_device,
                        action=action_name,
                        user_id=user_id,
                        parameters=params,
                        confidence=primary_result.confidence,
                        start_time=start_time,
                    )
                else:
                    action_result = await self._execute_device_command(
                        request_id=primary_result.request_id,
                        device=target_device,
                        action=action_name,
                        parameters=params,
                        confidence=primary_result.confidence,
                        start_time=start_time,
                    )
                
                actions_executed.append({
                    "action": action_name,
                    "success": action_result.success,
                    "command_id": action_result.command_id,
                    "device": target_device.name,
                })
                
                if action_result.message:
                    all_messages.append(action_result.message)
                
                if action_result.command_sent:
                    total_commands_sent += 1
                
                if not action_result.success:
                    all_success = False
                    logger.warning(
                        f"Sequential action '{action_name}' failed: {action_result.message}"
                    )
                else:
                    logger.info(f"Sequential action '{action_name}' succeeded on '{target_device.name}'")
                    
            except Exception as e:
                logger.error(f"Error executing sequential action '{seq_action.action}': {e}")
                actions_executed.append({
                    "action": seq_action.action,
                    "success": False,
                    "error": str(e),
                })
                all_messages.append(f"Failed: {seq_action.action} - {str(e)}")
                all_success = False
        
        # Build combined response
        processing_time = (time.time() - start_time) * 1000
        combined_message = " → ".join(all_messages) if all_messages else "Actions executed"
        
        # Update primary result with combined info
        return IntentResult(
            success=all_success,
            intent_type=primary_result.intent_type,
            confidence=primary_result.confidence,
            device=primary_result.device,
            action=primary_result.action,
            parameters=primary_result.parameters,
            data={
                **(primary_result.data or {}),
                "actions_executed": actions_executed,
                "commands_sent": total_commands_sent,
            },
            command_sent=total_commands_sent > 0,
            command_id=primary_result.command_id,  # Primary command ID
            message=combined_message,
            processing_time_ms=processing_time,
            request_id=primary_result.request_id,
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
    
    def _detect_content_type(self, request: str, response: str) -> Optional[str]:
        """
        Detect if response is generated content (note, email, template, etc.)

        Sprint 4.2: Memory-aware content display.
        Sprint 4.2.1: Added research/search detection.
        Sprint 4.5.0: Added weather/query detection for display context.

        Args:
            request: The user's original request
            response: The AI-generated response

        Returns:
            Content type string if detected, None otherwise
        """
        request_lower = request.lower()
        response_lower = response.lower()

        # Sprint 4.5.0: Weather/info query detection (Problem #2 fix)
        weather_keywords = ["clima", "weather", "temperatura", "temperature", "forecast", "pronóstico", "tiempo"]
        if any(kw in request_lower for kw in weather_keywords):
            return "weather_info"

        # Sprint 4.5.0: Detect weather by response characteristics
        if len(response) > 100:
            weather_indicators = ["°c", "°f", "grados", "degrees", "humidity", "humedad", "lluvia", "rain", "soleado", "sunny"]
            if any(ind in response_lower for ind in weather_indicators):
                return "weather_info"

        # Content creation keywords
        content_keywords = {
            "note": ["nota", "note", "apunte", "notes", "notas", "tips"],
            "email": ["email", "correo", "mensaje de correo", "mail"],
            "template": ["plantilla", "template", "formato"],
            "script": ["script", "guión", "guion"],
            "document": ["documento", "document", "doc"],
            "list": ["lista", "list", "checklist"],
            "message": ["mensaje", "message"],
            "summary": ["resumen", "summary"],
            "tutorial": ["tutorial", "guía", "guide"],
            # Sprint 4.5.0: Plan/intervention content
            "plan": ["plan", "intervención", "intervention", "protocolo", "protocol", "estrategia", "strategy"],
            # Sprint 4.2.1: Research/search content
            "research": ["investiga", "investigate", "research", "búsqueda", "busca", "search", "find", "encuentra"],
            "analysis": ["analiza", "analyze", "analysis", "análisis"],
            "explanation": ["explica", "explain", "qué es", "what is", "cuéntame", "tell me about"],
        }
        
        # Check if request contains creation intent
        creation_verbs = [
            "crear", "create", "escribe", "write", "genera", "generate",
            "redacta", "draft", "hazme", "dame", "give me", "necesito",
            "i need", "make", "haz", "crea",
            # Sprint 4.2.1: Research/search verbs (these also generate content)
            "investiga", "investigate", "busca", "search", "find",
            "analiza", "analyze", "explica", "explain", "cuéntame", "tell me",
        ]
        has_creation_intent = any(verb in request_lower for verb in creation_verbs)
        
        if has_creation_intent:
            for content_type, keywords in content_keywords.items():
                if any(keyword in request_lower for keyword in keywords):
                    return content_type
        
        # Check if response is structured content (longer than 100 chars with creation intent)
        if len(response) > 100 and has_creation_intent:
            return "research" if any(v in request_lower for v in ["investiga", "busca", "search", "find"]) else "document"
        
        return None
    
    def _extract_content_title(self, request: str, response: str) -> Optional[str]:
        """
        Extract title from request or first line of response.
        
        Sprint 4.2: Memory-aware content display.
        
        Args:
            request: The user's original request
            response: The AI-generated response
            
        Returns:
            Title string if extracted, None otherwise
        """
        import re
        
        # Try to extract from request (e.g., "crear nota ABA" → "ABA")
        # Pattern: content type word followed by name/title
        patterns = [
            r'(nota|note|email|correo|documento|document|plantilla|template)\s+(?:de\s+|sobre\s+|para\s+)?["\']?([A-Za-z0-9áéíóúÁÉÍÓÚñÑ\s]+)["\']?',
            r'(nota|note|email|correo|documento|document|plantilla|template)\s+["\']?([A-Z][A-Za-z0-9\s]+)["\']?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                title = match.group(2).strip()
                # Clean up common trailing words
                title = re.sub(r'\s+(y|and|en|on|para|for)\s*$', '', title, flags=re.IGNORECASE)
                if len(title) > 2:  # Avoid single letters
                    return title[:50]  # Max 50 chars
        
        # Fallback: use first line of response (max 50 chars)
        first_line = response.split('\n')[0].strip()
        # Remove markdown headers
        first_line = re.sub(r'^#+\s*', '', first_line)
        # Remove common prefixes
        first_line = re.sub(r'^(Aquí|Here|Este|This)\s+(está|is|es)?\s*:?\s*', '', first_line, flags=re.IGNORECASE)
        
        if first_line and len(first_line) > 3:
            return first_line[:50]
        
        return None
    
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
    
    def _store_doc_context(
        self,
        user_id: str,
        doc_id: str,
        doc_url: str,
        doc_title: str = None,
        doc_content: str = None,  # Sprint 5.1.1: Store content for context
    ) -> None:
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
                doc_content=doc_content,  # Sprint 5.1.1
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
            doc_url=intent.doc_url,
            doc_id=doc_id,
            source="doc" if intent.doc_url else "manual",
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
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
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
        
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunión").
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
                context=context,  # Sprint 5.1.4: Pass context
            )
        elif action == ActionType.DELETE_EXISTING_EVENT:
            return await self._handle_delete_existing_event(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context
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
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Search for events matching criteria and initiate edit flow.
        
        Uses smart semantic search (LLM matching) to find events,
        handling typos, translations, and synonyms.
        
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunión").
        """
        from app.services.pending_edit_service import pending_edit_service
        from app.services.calendar_search_service import calendar_search_service
        
        search_term = intent.search_term
        date_filter = intent.date_filter
        
        # Sprint 5.1.4: Resolve anaphoric reference if no explicit search_term
        if not search_term and context and context.get("resolved_references"):
            resolved_event = context["resolved_references"].get("event")
            if resolved_event and resolved_event.get("title"):
                search_term = resolved_event["title"]
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved event from context: {search_term}"
                )
        
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
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Search for events matching criteria and initiate delete flow.
        
        Uses smart semantic search (LLM matching) to find events,
        handling typos, translations, and synonyms.
        
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunión").
        """
        from app.services.pending_edit_service import pending_edit_service
        from app.services.calendar_search_service import calendar_search_service
        
        search_term = intent.search_term
        date_filter = intent.date_filter
        
        # Sprint 5.1.4: Resolve anaphoric reference if no explicit search_term
        if not search_term and context and context.get("resolved_references"):
            resolved_event = context["resolved_references"].get("event")
            if resolved_event and resolved_event.get("title"):
                search_term = resolved_event["title"]
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved event from context: {search_term}"
                )
        
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
        Build human-readable confirmation message (multilingual - Sprint 5.1.2).

        Example output (English):
        "Create 'Meeting' for December 13, 2025 at 7:00 PM (America/New_York)?
         Say 'yes' to confirm, 'no' to cancel, or edit like 'change time to 8 pm'"

        Example output (Spanish):
        "Crear 'Reunion' para December 13, 2025 a las 7:00 PM (America/New_York)?
         Di 'sí' para confirmar, 'no' para cancelar, o edita como 'cambiar hora a 8 pm'"
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
            time_str = "(all day)" if lang == "en" else "(todo el día)"
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
            except:
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
            base += f"\n📄 {doc_text}"

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
                "event_title": "título",
                "duration_minutes": "duración",
                "location": "ubicación",
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
                "WE": "repitiendo cada miércoles",
                "TH": "repitiendo cada jueves",
                "FR": "repitiendo cada viernes",
                "SA": "repitiendo cada sábado",
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
        Build success message after calendar event creation (multilingual - Sprint 5.1.2).

        Example (EN): "✓ Meeting scheduled for December 13, 2025 at 7:00 PM"
        Example (ES): "✓ 'Reunion' programada para December 13, 2025 a las 7:00 PM"
        """
        from app.ai.prompts.helpers import detect_user_language

        # Detect language from original user text
        lang = detect_user_language(pending.original_text or "")

        title = response.summary

        # Localized words
        scheduled = "programada" if lang == "es" else "scheduled"
        for_word = "para" if lang == "es" else "for"
        all_day = "(todo el día)" if lang == "es" else "(all day)"
        at_word = "a las" if lang == "es" else "at"

        # Format date/time
        if pending.is_all_day:
            if pending.event_date:
                date_str = pending.event_date.strftime("%B %d, %Y")
            else:
                date_str = "la fecha programada" if lang == "es" else "the scheduled date"
            message = f"✓ '{title}' {scheduled} {for_word} {date_str} {all_day}"
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
                except:
                    time_str = f"{at_word} {pending.event_time}"
            else:
                time_str = ""

            message = f"✓ '{title}' {scheduled} {for_word} {date_str} {time_str}".strip()

        # Add recurrence info
        if pending.recurrence:
            recurrence_text = self._format_recurrence(pending.recurrence, lang)
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
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Handle Google Docs intelligence queries.
        
        Sprint 3.9: Routes doc query actions:
        1. LINK_DOC: Link a document to a calendar event
        2. OPEN_DOC: Open a document linked to an event
        3. READ_DOC: Read/analyze document content
        4. SUMMARIZE_MEETING_DOC: Summarize document linked to meeting
        
        Sprint 4.0.2: Compound intent support
        If intent.also_display is True, ALSO sends show_content command to device.
        
        Sprint 5.1.4: Anaphoric resolution support
        If intent.doc_url is None, attempts to resolve from context.resolved_references.
        """
        action = intent.action
        result: Optional[IntentResult] = None
        
        # Route based on action type
        if action == ActionType.LINK_DOC:
            result = await self._handle_link_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
            )
        elif action == ActionType.OPEN_DOC:
            result = await self._handle_open_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
            )
        elif action == ActionType.READ_DOC:
            result = await self._handle_read_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=context,  # Sprint 5.1.4: Pass context for anaphoric resolution
            )
        elif action == ActionType.SUMMARIZE_MEETING_DOC:
            result = await self._handle_summarize_meeting_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.CREATE_EVENT_FROM_DOC:
            result = await self._handle_create_event_from_doc(
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
        
        # Sprint 4.0.2: Handle compound intent (also_display)
        # If user wants BOTH a text response AND to display the doc on screen
        if result and result.success and getattr(intent, 'also_display', False):
            doc_url = result.data.get("doc_url") if result.data else None
            
            if doc_url:
                # Get available devices
                devices = self._get_user_devices(db, user_id)
                target_device = None
                
                # Try to match the display_device name if provided
                display_device_name = getattr(intent, 'display_device', None)
                if display_device_name and devices:
                    target_device, _ = device_mapper.match(display_device_name, devices)
                
                # If no match or no device specified, use first online device
                if not target_device:
                    online_devices = [d for d in devices if d.is_online]
                    if len(online_devices) == 1:
                        target_device = online_devices[0]
                    elif len(online_devices) > 1:
                        # Multiple devices - could pick first or leave it
                        target_device = online_devices[0]
                
                if target_device and target_device.is_online:
                    # Decision: Display summary (Scene Graph) or full document (iframe)?
                    cmd_result = None
                    display_type = "document"
                    
                    if action == ActionType.SUMMARIZE_MEETING_DOC:
                        # CASE 1: SUMMARY → Scene Graph with doc_summary component
                        from uuid import uuid4
                        from app.ai.scene.schemas import (
                            SceneGraph, SceneComponent, LayoutSpec, LayoutIntent,
                            LayoutEngine, ComponentPriority, ComponentPosition,
                            ComponentStyle, GlobalStyle, SceneMetadata
                        )
                        from app.environments.google.docs import GoogleDocsClient
                        
                        # Build simple scene with doc_summary
                        doc_id = GoogleDocsClient.extract_doc_id(doc_url)
                        scene = SceneGraph(
                            scene_id=str(uuid4()),
                            target_devices=[str(target_device.id)],
                            layout=LayoutSpec(
                                intent=LayoutIntent.FULLSCREEN,
                                engine=LayoutEngine.FLEX,
                            ),
                            components=[
                                SceneComponent(
                                    id="doc_summary_main",
                                    type="doc_summary",
                                    priority=ComponentPriority.PRIMARY,
                                    position=ComponentPosition(flex=1),
                                    props={},
                                    data={
                                        "doc_id": doc_id,
                                        "title": result.data.get("title", "Document Summary") if result.data else "Document Summary",
                                        "summary": result.message,  # LLM-generated summary
                                        "url": doc_url,
                                    },
                                    style=ComponentStyle(
                                        background="#1a1a2e",
                                        text_color="#ffffff",
                                        border_radius="12px",
                                        padding="24px",
                                    ),
                                ),
                            ],
                            global_style=GlobalStyle(
                                background="#0f0f23",
                                font_family="Inter",
                            ),
                            metadata=SceneMetadata(
                                user_request=f"Display summary: {result.data.get('title', 'document') if result.data else 'document'}",
                                generated_by="intent_service",
                                # refresh_seconds defaults to 300 (5 min)
                            ),
                        )
                        
                        # Send scene to device
                        scene_dict = scene.model_dump(mode="json")
                        cmd_result = await command_service.display_scene(
                            device_id=target_device.id,
                            scene=scene_dict,
                        )
                        display_type = "summary"
                        
                    elif action in [ActionType.READ_DOC, ActionType.OPEN_DOC]:
                        # CASE 2: FULL DOCUMENT → iframe
                        cmd_result = await command_service.show_content(
                            device_id=target_device.id,
                            url=doc_url,
                        )
                        display_type = "document"
                    
                    else:
                        # Other doc_query actions don't support display
                        logger.info(f"Action {action} does not support also_display")
                    
                    if cmd_result and cmd_result.success:
                        logger.info(f"Compound intent: Also displayed {display_type} on {target_device.name}")
                        result.command_sent = True
                        result.command_id = cmd_result.command_id
                        result.device = target_device
                        
                        # Update message to indicate both actions completed
                        original_message = result.message or ""
                        display_label = "Summary" if display_type == "summary" else "Document"
                        result.message = f"{original_message}\n\n📺 {display_label} also displayed on {target_device.name}."
                    elif cmd_result:
                        # Display failed but doc query succeeded - log but don't fail
                        logger.warning(f"Compound intent: Display failed on {target_device.name}: {cmd_result.error}")
                else:
                    # No device available - log but don't fail the doc query
                    logger.info("Compound intent: also_display requested but no device available")

        # Sprint 4.3.0: Save doc query response to conversation context
        if result and result.success and result.message:
            from app.services.conversation_context_service import conversation_context_service
            # Reconstruct original user message from intent
            user_message = getattr(intent, 'original_text', f"Doc query: {action}")
            conversation_context_service.add_conversation_turn(
                user_id=str(user_id),
                user_message=user_message,
                assistant_response=result.message,
                intent_type="doc_query",
            )

        return result

    async def _handle_link_doc(
        self,
        request_id: str,
        intent: "DocQueryIntent",
        user_id: UUID,
        start_time: float,
        db: Session,
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Link a Google Doc to a calendar event.
        
        Note: This feature requires updating calendar event extended properties,
        which needs a calendar API update method. For now, we provide helpful feedback.
        
        Sprint 5.1.4: Supports anaphoric references for both doc and meeting.
        """
        from app.services.meeting_link_service import meeting_link_service
        from app.environments.google.docs import GoogleDocsClient
        
        doc_url = intent.doc_url
        meeting_search = intent.meeting_search
        
        # Sprint 5.1.4: Resolve anaphoric references from context
        if context and context.get("resolved_references"):
            resolved = context["resolved_references"]
            if not doc_url and resolved.get("document"):
                doc_url = resolved["document"].get("url")
                logger.info(f"[ANAPHORIC_RESOLUTION] Resolved doc from context: {doc_url}")
            if not meeting_search and resolved.get("event"):
                meeting_search = resolved["event"].get("title")
                logger.info(f"[ANAPHORIC_RESOLUTION] Resolved event from context: {meeting_search}")
        
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
            
            # Get OAuth credentials (following _handle_confirm_edit pattern)
            from app.models.oauth_credential import OAuthCredential
            from app.environments.google.calendar.client import GoogleCalendarClient
            from app.environments.google.calendar.schemas import EventUpdateRequest
            
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()
            
            if not credentials or not credentials.access_token:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Please connect your Google Calendar first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Create calendar client
            client = GoogleCalendarClient(access_token=credentials.access_token)
            
            # Build new description - append doc URL to existing description
            doc_id = meeting_link_service.extract_doc_id_from_url(doc_url)
            existing_description = meeting_result.event.description or ""
            doc_link_text = f"\n\n📄 Linked Document: {doc_url}"
            new_description = existing_description + doc_link_text
            
            # Create EventUpdateRequest - only update description
            update_request = EventUpdateRequest(description=new_description)
            
            # Call update_event
            await client.update_event(meeting_result.event.id, update_request)
            
            logger.info(
                f"Document linked to event",
                extra={
                    "user_id": str(user_id)[:8],
                    "event_id": meeting_result.event.id,
                    "doc_id": doc_id,
                }
            )

            # Sprint 5.1.3: Store doc in context for future references ("ese documento", "that doc")
            from app.services.conversation_context_service import conversation_context_service
            conversation_context_service.set_last_doc(
                user_id=str(user_id),
                doc_id=doc_id,
                doc_url=doc_url,
                doc_title=meeting_result.event.summary,  # Use event title as doc context
            )

            processing_time = (time.time() - start_time) * 1000

            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                confidence=intent.confidence,
                action="link_doc",
                message=f"✓ Document linked to '{meeting_result.event.summary}'",
                response=f"I've added the document link to your '{meeting_result.event.summary}' event.",
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
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Get the document linked to a calendar event.
        
        Uses find_meeting_with_doc to search for the meeting and get its linked docs.
        Returns the document URL for the client to open.
        
        Sprint 3.9: If device_name is specified, displays the doc on that device.
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunión").
        """
        from app.services.meeting_link_service import meeting_link_service
        
        meeting_search = intent.meeting_search
        meeting_time = intent.meeting_time
        device_name = intent.device_name  # Sprint 3.9: Support device display
        
        # Sprint 5.1.4: Resolve anaphoric reference from context
        if not meeting_search and not meeting_time and context and context.get("resolved_references"):
            resolved_event = context["resolved_references"].get("event")
            if resolved_event and resolved_event.get("title"):
                meeting_search = resolved_event["title"]
                logger.info(f"[ANAPHORIC_RESOLUTION] Resolved event from context: {meeting_search}")
        
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
                                confidence=intent.confidence,
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
                            confidence=intent.confidence,
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
                        confidence=intent.confidence,
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
                confidence=intent.confidence,
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
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Read and analyze a Google Doc.
        
        Uses DocIntelligenceService to process the document with AI.
        
        Sprint 5.1.4: Anaphoric resolution support
        If intent.doc_url is None, attempts to resolve from context.resolved_references.
        Enables "what does that document say?" to work after referencing a doc.
        """
        from app.services.doc_intelligence_service import doc_intelligence_service
        from app.environments.google.docs import GoogleDocsClient
        from app.models.oauth_credential import OAuthCredential
        
        doc_url = intent.doc_url
        question = intent.question
        
        processing_time = (time.time() - start_time) * 1000
        
        # Sprint 5.1.4: Resolve anaphoric reference if no explicit doc_url
        if not doc_url and context and context.get("resolved_references"):
            resolved_doc = context["resolved_references"].get("document")
            if resolved_doc:
                doc_url = resolved_doc.get("url")
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved doc from context: {doc_url}"
                )
        
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
                # Sprint 5.1.1: Store doc context for future references (DRY - reuse helper)
                self._store_doc_context(
                    user_id=str(user_id),
                    doc_id=doc_id,
                    doc_url=doc_url,
                    doc_title=summary_result.title,
                    doc_content=summary_result.summary,  # Sprint 5.1.1: Include content
                )
                # Store summary in content memory for follow-up requests
                from app.services.conversation_context_service import conversation_context_service
                conversation_context_service.set_generated_content(
                    user_id=str(user_id),
                    content=summary_result.summary,
                    content_type="doc_summary",
                    title=summary_result.title,
                )

                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.DOC_QUERY,
                    confidence=intent.confidence,
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
                    confidence=intent.confidence,
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
                confidence=intent.confidence,
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
                confidence=intent.confidence,
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
    # DISPLAY CONTENT (SCENE GRAPH) HANDLING
    # ---------------------------------------------------------------------------

    async def _fetch_realtime_data_for_scene(
        self,
        user_request: str,
        layout_hints: list,
    ) -> Dict[str, Any]:
        """
        Use Gemini with web search to fetch real-time data for scene components.
        
        Sprint 4.1: This method detects what type of real-time data is needed 
        (weather, news, etc.) and uses Gemini's grounding capability to fetch it 
        BEFORE calling Claude for scene generation.
        
        Args:
            user_request: Original user request
            layout_hints: Parsed layout hints
        
        Returns:
            Dict with component_type → data mapping
            Example: {"weather_current": {"temperature": 25, "condition": "snow"}}
        """
        from app.ai.providers.gemini import gemini_provider

        realtime_data = {}
        
        # Check if user wants weather data
        weather_keywords = ["clima", "weather", "temperatura", "temperature", "tiempo"]
        if any(keyword in user_request.lower() for keyword in weather_keywords):
            # Extract location from request
            location = self._extract_location_from_request(user_request)
            if not location:
                location = "Miami, FL"  # Default to real location (grounding needs specific place)

            # Gemini fetches weather as natural text (simple task)
            # Claude will extract structured data when generating the scene (complex task)
            # Sprint 5.1.4: Simplified prompt works better with grounding
            prompt = f"What is the current temperature and weather conditions in {location} right now?"

            try:
                response = await gemini_provider.generate_with_grounding(
                    prompt=prompt,
                    system_prompt=None,  # No system prompt - let grounding work naturally
                    use_search=True,
                    temperature=0.1,
                    max_tokens=300,  # More tokens to avoid truncation
                )

                if response.success and response.content:
                    weather_text = response.content.strip()
                    # Pass raw text to Claude - it will extract the structured data
                    realtime_data["weather_current"] = {
                        "raw_weather_info": weather_text,
                        "location": location,
                        "is_placeholder": False,
                        "fetched_via": "gemini_grounding",
                    }
                    logger.info(f"Fetched weather for {location}: {weather_text[:100]}...")
            except Exception as e:
                logger.warning(f"Failed to fetch weather data via Gemini: {e}")
                # Don't fail - Claude will use placeholder if needed
        
        # Future extensibility: Add similar blocks for news, stocks, etc.
        # if any(kw in user_request.lower() for kw in ["news", "noticias"]):
        #     realtime_data["news_feed"] = await self._fetch_news_via_gemini(user_request)
        
        return realtime_data
    
    def _extract_location_from_request(self, user_request: str) -> Optional[str]:
        """
        Extract location from user request.

        Examples:
            "clima de Alaska" → "Alaska"
            "weather in Miami" → "Miami"
            "temperatura en New York" → "New York"
            "show weather for London" → "London"
            "muestra el clima en la pantalla" → None (not a location!)
        """
        import re

        # Words that are display destinations, NOT locations
        display_words = ["pantalla", "screen", "tv", "monitor", "display", "tele", "television"]

        # Spanish patterns - greedy capture up to end of sentence or punctuation
        spanish_match = re.search(
            r'(?:clima|tiempo|temperatura)\s+(?:de|en)\s+([A-Za-z][A-Za-z\s]*[A-Za-z])',
            user_request,
            re.IGNORECASE
        )
        if spanish_match:
            # Clean up - remove trailing common words
            location = spanish_match.group(1).strip()
            # Remove common trailing words that aren't part of place names
            location = re.sub(r'\s+(en|on|the|la|el|para|for).*$', '', location, flags=re.IGNORECASE)
            location = location.strip()
            # Sprint 5.1.3: Exclude display destinations from being treated as locations
            if location.lower() in display_words or any(dw in location.lower() for dw in display_words):
                return None
            return location
        
        # English patterns - greedy capture
        english_match = re.search(
            r'(?:weather|climate|temperature)\s+(?:in|for|of)\s+([A-Za-z][A-Za-z\s]*[A-Za-z])',
            user_request,
            re.IGNORECASE
        )
        if english_match:
            location = english_match.group(1).strip()
            # Remove common trailing words
            location = re.sub(r'\s+(on|the|screen|tv|display|pantalla).*$', '', location, flags=re.IGNORECASE)
            location = location.strip()
            # Sprint 5.1.3: Exclude display destinations from being treated as locations
            if location.lower() in display_words or any(dw in location.lower() for dw in display_words):
                return None
            return location
        
        # Try to find capitalized place names after show/display
        place_match = re.search(
            r'(?:show|display|muestra|mostrar)\s+.*?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            user_request
        )
        if place_match:
            return place_match.group(1).strip()
        
        return None

    async def _handle_display_content(
        self,
        request_id: str,
        intent: DisplayContentIntent,
        user_id: UUID,
        devices: List[Device],
        start_time: float,
        db: Session,
        context: Optional[Dict[str, Any]] = None,  # Sprint 5.1.4: For anaphoric resolution
    ) -> IntentResult:
        """
        Handle display content intents by generating and sending scene graphs.
        
        Sprint 4.0: Scene Graph implementation for creative device layouts.
        Sprint 4.2: Memory-aware content display - check generated content first.
        Sprint 5.1.4: Uses context for anaphoric resolution instead of manual get_last_* calls.
        
        Flow:
        1. Check for recently generated content in memory (Sprint 4.2)
        2. Resolve target device (from intent.device_name or first online device)
        3. Detect default scene type or use custom layout
        4. Normalize layout hints to LayoutHint objects
        5. Generate scene via SceneService
        6. Send scene to device via WebSocket
        7. Return result with component summary
        """
        from app.ai.scene.service import scene_service
        from app.ai.scene.defaults import detect_default_scene_type
        from app.services.conversation_context_service import conversation_context_service
        from app.services.commands import command_service  # Import at function level for all code paths
        from app.services.websocket_manager import connection_manager  # Sprint 5.2.3: Loading signals

        # DEBUG: Log entry into _handle_display_content
        logger.info(f"[{request_id}] ENTERING _handle_display_content for user {str(user_id)[:8]}...")
        
        # Sprint 4.2: Check for recently generated content in memory
        generated_content = conversation_context_service.get_generated_content(str(user_id))
        logger.info(f"[{request_id}] generated_content exists: {generated_content is not None}")
        
        # Also get conversation history for context
        conversation_history = conversation_context_service.get_conversation_history(str(user_id), max_turns=5)
        logger.info(f"[{request_id}] conversation_history turns: {len(conversation_history) if conversation_history else 0}")
        
        if generated_content:
            # Check if user is referencing the generated content
            original_text_lower = intent.original_text.lower() if intent.original_text else ""
            logger.info(f"[{request_id}] Checking memory keywords in: '{original_text_lower[:50]}...'")
            memory_keywords = [
                'que creaste', 'que hiciste', 'que generaste', 'que acabas',
                'esa nota', 'ese email', 'la plantilla', 'la nota', 'el email',
                'you created', 'you made', 'you generated', 'you just wrote',
                'that note', 'that email', 'the template', 'the note',
                'show it', 'muéstralo', 'muestramelo', 'muéstramelo',
                # Sprint 4.2.1: Research/search result references
                'los resultados', 'the results', 'lo que encontraste', 'what you found',
                'lo que investigaste', 'what you researched', 'esa información',
                'that information', 'eso', 'that', 'esto', 'this',
                'muestrame eso', 'show me that', 'ponlo', 'put it',
                # Note: 'en la pantalla'/'on screen' removed - describes WHERE not WHAT (Sprint 5.1.1)
                # Sprint 4.2.2: Demonstrative references (esas, esos, etc.)
                'esas', 'esos', 'estas', 'estos', 'those', 'these',
            ]
            
            is_memory_reference = any(kw in original_text_lower for kw in memory_keywords)

            # Sprint 4.5.0: Detect multi-content requests that need Claude scene generation
            multi_content_keywords = [
                ' y ', ' and ', 'junto', 'juntos', 'together', 'ambos', 'both',
                'izquierda', 'derecha', 'left', 'right', 'arriba', 'abajo',
                'two_column', 'dos columnas', 'lado a lado', 'side by side',
            ]
            is_multi_content_request = any(kw in original_text_lower for kw in multi_content_keywords)

            # Skip fast path for multi-content requests - let Claude handle layout
            if is_multi_content_request:
                logger.info(
                    f"[{request_id}] Multi-content request detected - skipping fast path, using Claude scene generation"
                )

            if is_memory_reference and not is_multi_content_request:
                logger.info(
                    f"[{request_id}] Displaying generated content from memory (fast path): "
                    f"type={generated_content['type']}, title={generated_content['title']}"
                )
                
                # Resolve target device for displaying generated content
                target_device = None
                if intent.device_name:
                    target_device, _ = device_mapper.match(intent.device_name, devices)
                if not target_device:
                    target_device = next((d for d in devices if d.is_online), None)
                
                if not target_device:
                    processing_time = (time.time() - start_time) * 1000
                    return IntentResult(
                        success=False,
                        intent_type=IntentResultType.DISPLAY_CONTENT,
                        message="No display device available. Please connect a device first.",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )
                
                # Build proper SceneGraph with generated content as text_block
                content_title = generated_content["title"] or "Generated Content"
                content_text = generated_content["content"]
                
                scene_dict = {
                    "scene_id": f"memory-content-{request_id[:8]}",
                    "version": "1.1",
                    "target_devices": [str(target_device.id)],
                    "layout": {
                        "intent": "fullscreen",
                        "engine": "flex",
                        "gap": "16px",
                    },
                    "components": [
                        {
                            "id": "generated_content_display",
                            "type": "text_block",
                            "priority": "primary",
                            "position": {"flex": 1},
                            "style": {
                                "background": "#1a1a2e",
                                "text_color": "#ffffff",
                                "border_radius": "16px",
                                "padding": "32px",
                            },
                            "props": {
                                "content": content_text,
                                "title": content_title,
                                "alignment": "left",
                                "font_size": "18px",
                            },
                            "data": {
                                "content": content_text,
                                "is_placeholder": False,
                            },
                        }
                    ],
                    "global_style": {
                        "background": "#0f0f23",
                        "font_family": "Inter",
                        "text_color": "#ffffff",
                        "accent_color": "#7b2cbf",
                    },
                    "metadata": {
                        "user_request": intent.original_text,
                        "generated_by": "memory_context",
                        "refresh_seconds": 300,
                    },
                }
                
                # Send to device via command service
                result = await command_service.display_scene(
                    device_id=target_device.id,
                    scene=scene_dict,
                )

                processing_time = (time.time() - start_time) * 1000

                memory_message = f"Showing {generated_content['type']}: {content_title} on {target_device.name}"

                # Sprint 4.3.0: Save display content (from memory) response to conversation context
                conversation_context_service.add_conversation_turn(
                    user_id=str(user_id),
                    user_message=intent.original_text or "Display generated content",
                    assistant_response=memory_message,
                    intent_type="display_content",
                )

                return IntentResult(
                    success=result.success,
                    intent_type=IntentResultType.DISPLAY_CONTENT,
                    confidence=0.95,
                    device=target_device,
                    action="display_scene",
                    message=memory_message,
                    command_sent=result.success,
                    command_id=result.command_id,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                    data={
                        "source": "generated_content_memory",
                        "content_type": generated_content["type"],
                        "content_title": content_title,
                    },
                )
        
        logger.info(
            f"[{request_id}] Handling display content intent",
            extra={
                "info_type": intent.info_type,
                "layout_type": intent.layout_type,
                "layout_hints": intent.layout_hints,
                "device_name": intent.device_name,
            }
        )
        
        try:
            # Resolve target device
            target_device = None
            if intent.device_name:
                target_device, match_confidence = device_mapper.match(intent.device_name, devices)
                if not target_device:
                    processing_time = (time.time() - start_time) * 1000
                    alternatives = device_mapper.match_all(intent.device_name, devices, limit=3)
                    suggestion = ""
                    if alternatives:
                        names = [f'"{d.name}"' for d, _ in alternatives]
                        suggestion = f" Did you mean: {', '.join(names)}?"
                    
                    return IntentResult(
                        success=False,
                        intent_type=IntentResultType.DISPLAY_CONTENT,
                        message=f"I couldn't find a device matching '{intent.device_name}'.{suggestion}",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )
            else:
                # Use first online device with display capability
                target_device = next((d for d in devices if d.is_online), None)
            
            if not target_device:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.DISPLAY_CONTENT,
                    message="No display device available. Please connect a device first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # Check if device is online
            if not target_device.is_online:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.DISPLAY_CONTENT,
                    device=target_device,
                    message=f"'{target_device.name}' is currently offline.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Sprint 5.2.3: Send initial loading signal - Phase 1
            await connection_manager.send_command(
                device_id=target_device.id,
                command_type="loading_start",
                parameters={"message": "Preparando visualización...", "phase": 1},
            )
            logger.info(f"[{request_id}] Loading Phase 1: Preparing")

            # Detect default scene type for optimized generation
            # Sprint 4.4.0: Pass user_request to detect generation keywords
            default_type = detect_default_scene_type(
                info_type=intent.info_type,
                layout_hints=intent.layout_hints,
                user_request=intent.original_text,  # Pass original text for keyword detection
            )
            logger.info(f"[{request_id}] Detected default scene type: {default_type}")
            
            # Normalize layout hints to structured LayoutHint objects
            normalized_hints = scene_service.normalize_layout_hints(intent.layout_hints)
            
            # Sprint 4.1: Fetch real-time data BEFORE calling Claude for scene generation
            realtime_data = await self._fetch_realtime_data_for_scene(
                user_request=intent.original_text,
                layout_hints=intent.layout_hints,
            )

            # Sprint 6.1: Determine if we need real data or can use direct flow
            # Real data types: calendar, weather, etc. - require SceneGraph for data fetching
            # Creative types: trivia, games, visualizations - can skip SceneGraph
            needs_real_data = bool(realtime_data and any(
                k in realtime_data for k in ['calendar', 'weather', 'events', 'documents']
            ))

            if realtime_data:
                logger.info(f"[{request_id}] Fetched real-time data for: {list(realtime_data.keys())} (needs_real_data={needs_real_data})")
            
            # Sprint 4.2: Build conversation context for scene generation
            # This ensures Claude knows what was discussed/generated before
            conversation_context_dict = {}
            
            # Detect if user wants a conversation summary (need more history)
            original_text_lower = (intent.original_text or "").lower()
            is_summary_request = any(kw in original_text_lower for kw in [
                'resume', 'resumen', 'resumas', 'summarize', 'summary',
                'lo que hablamos', 'what we discussed', 'esta conversación',
                'this conversation', 'nuestra conversación', 'our conversation',
            ])
            
            # Get more turns for summary requests
            max_turns = 10 if is_summary_request else 5
            conversation_history = conversation_context_service.get_conversation_history(str(user_id), max_turns=max_turns)
            if conversation_history:
                conversation_context_dict["history"] = conversation_history
                if is_summary_request:
                    logger.info(f"[{request_id}] SUMMARY REQUEST: Including {len(conversation_history)} conversation turns for summarization")
                else:
                    logger.info(f"[{request_id}] Including {len(conversation_history)} conversation turns in scene context")
            
            # Get generated content (even if not explicitly referenced)
            if generated_content:
                # Serialize timestamp if present
                gc_serialized = {
                    k: v.isoformat() if hasattr(v, 'isoformat') else v
                    for k, v in generated_content.items()
                }
                conversation_context_dict["generated_content"] = gc_serialized
                logger.info(f"[{request_id}] Including generated content in scene context: type={generated_content.get('type')}")
            
            # Get last assistant response (may contain useful content)
            context_state = conversation_context_service.get_context(str(user_id))
            if context_state and context_state.last_assistant_response:
                conversation_context_dict["last_response"] = context_state.last_assistant_response

            # Sprint 4.3.2: Include last event context (for "mi plan", "my meeting", etc.)
            # Sprint 5.1.4: Also include resolved_references from context
            last_event = None
            if context and (context.get("resolved_references") or {}).get("event"):
                last_event = context["resolved_references"]["event"]
                logger.info(f"[{request_id}] Using resolved event from context: {last_event.get('title')}")
            else:
                last_event = conversation_context_service.get_last_event(str(user_id))
            if last_event:
                conversation_context_dict["last_event"] = last_event
                logger.info(f"[{request_id}] Including last event in scene context: {last_event.get('title')}")

            # Sprint 4.3.2: Include last doc context
            # Sprint 5.1.4: Also include resolved_references from context
            last_doc = None
            if context and (context.get("resolved_references") or {}).get("document"):
                last_doc = context["resolved_references"]["document"]
                logger.info(f"[{request_id}] Using resolved doc from context: {last_doc.get('title')}")
            else:
                last_doc = conversation_context_service.get_last_doc(str(user_id))
            if last_doc:
                conversation_context_dict["last_doc"] = last_doc
                logger.info(f"[{request_id}] Including last doc in scene context: {last_doc.get('title')}")

            # Sprint 4.5.0: Include content memory for multi-content display
            content_memory = conversation_context_service.get_content_memory(str(user_id), limit=5)
            if content_memory:
                conversation_context_dict["content_memory"] = content_memory
                logger.info(f"[{request_id}] Including content memory in scene context: {len(content_memory)} items")

            # Sprint 5.2.3: Loading Phase 2 - Generating content
            await connection_manager.send_command(
                device_id=target_device.id,
                command_type="loading_start",
                parameters={"message": "Analizando contenido...", "phase": 2},
            )
            logger.info(f"[{request_id}] Loading Phase 2: Analyzing")

            # Sprint 6.1: Hybrid flow - direct data for creative content, SceneGraph for real data
            scene_dict = None
            custom_layout = None
            content_data = None  # Initialize for use in response building

            if not needs_real_data and settings.CUSTOM_LAYOUT_ENABLED:
                # =====================================================================
                # DIRECT FLOW: Creative content (trivia, games, visualizations)
                # Skip SceneGraph, generate content data directly → Opus HTML
                # This saves ~10-15 seconds of latency
                # =====================================================================
                logger.info(f"[{request_id}] Using DIRECT flow (no SceneGraph) for creative content")

                try:
                    from app.ai.scene.custom_layout import custom_layout_service

                    # Step 1: Generate content data with Gemini (faster than full SceneGraph)
                    hints_str = ", ".join(intent.layout_hints) if intent.layout_hints else None
                    content_data = await scene_service.generate_content_data(
                        user_request=intent.original_text,
                        layout_hints=normalized_hints,
                        realtime_data=realtime_data,
                        conversation_context=conversation_context_dict,
                    )

                    if content_data:
                        logger.info(f"[{request_id}] Content data generated: {content_data.get('content_type', 'unknown')}")

                        # Loading Phase 3 - Designing layout
                        await connection_manager.send_command(
                            device_id=target_device.id,
                            command_type="loading_start",
                            parameters={"message": "Diseñando experiencia...", "phase": 3},
                        )
                        logger.info(f"[{request_id}] Loading Phase 3: Designing (direct flow)")

                        # Step 2: Generate HTML + validate with visual validation
                        layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                            content_data=content_data,
                            user_request=intent.original_text or "",
                            layout_hints=hints_str,
                            layout_type=content_data.get("content_type"),
                        )

                        if layout_result.success and layout_result.html:
                            custom_layout = layout_result.html
                            logger.info(
                                f"[{request_id}] Direct HTML generated + validated "
                                f"(latency: {layout_result.latency_ms:.0f}ms)"
                            )
                            # Create minimal scene_dict for display_scene command
                            scene_dict = {"scene_id": request_id, "direct_flow": True}
                        else:
                            logger.warning(
                                f"[{request_id}] Direct flow failed: {layout_result.error}. "
                                f"Falling back to SceneGraph flow."
                            )
                    else:
                        logger.warning(f"[{request_id}] Content data generation failed, falling back to SceneGraph")

                except Exception as e:
                    logger.error(
                        f"[{request_id}] Direct flow error, falling back to SceneGraph: {e}",
                        exc_info=True
                    )

            # =====================================================================
            # SCENOGRAPH FLOW: Real data (calendar, weather) or direct flow failed
            # Full SceneGraph generation with Gemini + Opus HTML
            # =====================================================================
            if scene_dict is None:
                logger.info(f"[{request_id}] Using SCENOGRAPH flow (needs_real_data={needs_real_data})")

                # Generate scene via SceneService (now with real-time data AND conversation context)
                logger.info(f"[{request_id}] Generating scene with {len(normalized_hints)} layout hints")
                scene = await scene_service.generate_scene(
                    layout_hints=normalized_hints,
                    info_type=intent.info_type,
                    target_devices=[str(target_device.id)],
                    user_id=str(user_id),
                    user_request=intent.original_text,
                    db=db,
                    realtime_data=realtime_data,
                    conversation_context=conversation_context_dict,
                )

                scene_dict = scene.model_dump(mode="json")

                # Generate custom HTML layout if enabled
                if settings.CUSTOM_LAYOUT_ENABLED:
                    try:
                        from app.ai.scene.custom_layout import custom_layout_service

                        # Loading Phase 3 - Designing layout
                        await connection_manager.send_command(
                            device_id=target_device.id,
                            command_type="loading_start",
                            parameters={"message": "Diseñando experiencia...", "phase": 3},
                        )
                        logger.info(f"[{request_id}] Loading Phase 3: Designing")

                        # Use generate_and_validate_html with visual validation
                        layout_result = await custom_layout_service.generate_and_validate_html(
                            scene=scene_dict,
                            user_request=intent.original_text or "",
                        )

                        if layout_result.success and layout_result.html:
                            custom_layout = layout_result.html
                            logger.info(
                                f"[{request_id}] Custom HTML layout generated and validated "
                                f"(latency: {layout_result.latency_ms:.0f}ms)"
                            )
                        else:
                            logger.warning(
                                f"[{request_id}] Custom layout generation/validation failed: {layout_result.error}. "
                                f"Falling back to SceneGraph."
                            )
                    except Exception as e:
                        logger.error(
                            f"[{request_id}] Custom layout error (falling back to SceneGraph): {e}",
                            exc_info=True
                        )
            
            # Send scene to device using the display_scene command
            # Sprint 5.2: Include custom_layout if generated successfully
            result = await command_service.display_scene(
                device_id=target_device.id,
                scene=scene_dict,
                custom_layout=custom_layout,
            )
            
            if not result.success:
                raise Exception(f"Failed to send scene to device: {result.error}")
            
            processing_time = (time.time() - start_time) * 1000
            
            # Track command for monitoring (same as _execute_content_action)
            ai_monitor.track_command(
                request_id=request_id,
                device_id=target_device.id,
                device_name=target_device.name,
                action="display_scene",
                command_id=result.command_id,
                success=result.success,
                error=result.error,
            )
            
            # Build user-friendly response
            # Sprint 6.1: Handle both direct flow (no scene) and SceneGraph flow
            is_direct_flow = scene_dict.get("direct_flow", False)

            if is_direct_flow and content_data:
                # Direct flow: use content_data for response
                content_type = content_data.get("content_type", "content")
                content_title = content_data.get("title", "interactive content")
                response_message = f"I've updated {target_device.name} with {content_type}: {content_title}."
                scene_id = request_id
                layout_intent = content_type
                components_list = [content_type]
            else:
                # SceneGraph flow: use scene object
                component_summary = ", ".join(
                    [c.type for c in scene.components[:3]]
                )
                if len(scene.components) > 3:
                    component_summary += f" and {len(scene.components) - 3} more"
                response_message = f"I've updated {target_device.name} with {component_summary}."
                scene_id = scene.scene_id
                layout_intent = scene.layout.intent.value
                components_list = [c.type for c in scene.components]

            # Sprint 4.3.0: Save display content response to conversation context
            conversation_context_service.add_conversation_turn(
                user_id=str(user_id),
                user_message=intent.original_text or "Display content request",
                assistant_response=response_message,
                intent_type="display_content",
            )

            # Sprint 4.4.0 - GAP #8: Save scene metadata for assistant awareness
            conversation_context_service.set_last_scene(
                user_id=str(user_id),
                scene_id=scene_id,
                components=components_list,
                layout_intent=layout_intent,
            )

            return IntentResult(
                success=True,
                intent_type=IntentResultType.DISPLAY_CONTENT,
                confidence=intent.confidence,
                device=target_device,
                message=response_message,
                data={
                    "scene_id": scene_id,
                    "scene": scene_dict,
                    "target_device": str(target_device.id),
                    "layout_intent": layout_intent,
                },
                command_sent=result.success,
                command_id=result.command_id,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
                
        except Exception as e:
            logger.error(f"[{request_id}] Failed to handle display content: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to update display: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

intent_service = IntentService()
