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
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    pass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.device import Device
from app.services.commands import command_service
from app.core.config import settings

# Sprint US-2.1: Import result types from separate module to avoid circular imports
from app.services.intent_result import IntentResult, IntentResultType

# AI imports
from app.ai.intent.parser import intent_parser
from app.ai.intent.device_mapper import device_mapper
from app.ai.intent.schemas import (
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
from app.ai.actions.registry import action_registry

# Sprint US-2.1: Import DeviceHandler for delegation
# Sprint US-2.2: Import ConversationHandler for delegation
# Sprint US-2.3: Import SystemHandler for delegation
# Sprint US-3.1: Import CalendarHandler for delegation
from app.services.intent_handlers.device_handler import DeviceHandler
from app.services.intent_handlers.system_handler import SystemHandler
from app.services.intent_handlers.conversation_handler import ConversationHandler
from app.services.intent_handlers.calendar_handler import CalendarHandler
from app.services.intent_handlers.display_content_handler import DisplayContentHandler
from app.services.intent_handlers.document_handler import DocumentHandler
from app.services.intent_handlers.base import HandlerContext


logger = logging.getLogger("jarvis.services.intent")


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
        # Sprint US-2.1: Initialize DeviceHandler for delegation
        self._device_handler = DeviceHandler()
        # Sprint US-2.2: Initialize ConversationHandler for delegation
        self._conversation_handler = ConversationHandler()
        # Sprint US-2.3: Initialize SystemHandler for delegation
        self._system_handler = SystemHandler()
        # Sprint US-3.1: Initialize CalendarHandler for delegation
        self._calendar_handler = CalendarHandler()
        # Sprint US-3.2: Initialize DisplayContentHandler for delegation
        self._display_content_handler = DisplayContentHandler()
        # Sprint US-3.3: Initialize DocumentHandler for delegation
        self._document_handler = DocumentHandler()
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
        require_feedback: bool = False,
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
            require_feedback: If True, return HTML for human validation instead of sending to device

        Returns:
            IntentResult with processing outcome
        """
        # Store require_feedback for use in child methods
        self._require_feedback = require_feedback
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

            # Close DB connection BEFORE long AI operations
            # The session won't be used anymore - handlers will open their own session if needed
            db.close()
            
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
                    user_id=user_id,
                    devices=devices,  # Pass pre-loaded devices instead of db
                )

            if routing_decision.complexity == TaskComplexity.COMPLEX_REASONING:
                return await self._handle_complex_task(
                    request_id=request_id,
                    text=text,
                    routing_decision=routing_decision,
                    context=context,
                    start_time=start_time,
                    provider="gemini",  # Sprint 9: Migrated from Anthropic to Gemini
                    user_id=user_id,
                    devices=devices,  # Pass pre-loaded devices instead of db
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
    ) -> IntentResult:
        """Handle simple tasks using Gemini Intent Parser."""
        # Open a fresh DB session for handlers that need it
        # This is closed at the end of the method
        from app.db.session import SessionLocal
        db = SessionLocal()

        try:
            return await self._handle_simple_task_internal(
                request_id=request_id,
                text=text,
                context=context,
                devices=devices,
                device_id=device_id,
                start_time=start_time,
                user_id=user_id,
                db=db,
            )
        finally:
            db.close()

    async def _handle_simple_task_internal(
        self,
        request_id: str,
        text: str,
        context: Dict[str, Any],
        devices: List[Device],
        device_id: Optional[UUID],
        start_time: float,
        user_id: UUID,
        db: Session,
    ) -> IntentResult:
        """Internal handler with DB session."""
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

        # Sprint US-2.3: Delegate SystemQuery to SystemHandler
        if isinstance(intent, SystemQuery):
            handler_context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
                original_text=text,
                forced_device_id=device_id,
            )
            return await self._system_handler.handle(intent, handler_context)

        # Sprint US-2.1: Delegate device-related intents to DeviceHandler
        if isinstance(intent, (DeviceCommand, DeviceQuery)):
            handler_context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
                original_text=text,
                forced_device_id=device_id,
            )
            return await self._device_handler.handle(intent, handler_context)

        # Sprint US-3.1: Delegate calendar-related intents to CalendarHandler
        if isinstance(intent, (CalendarQueryIntent, CalendarCreateIntent, CalendarEditIntent)):
            handler_context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
                original_text=text,
                forced_device_id=device_id,
                resolved_references=context.get("resolved_references", {}),
                conversation_history=context.get("conversation_history"),
                pending_operation=context.get("pending_operation"),
            )
            return await self._calendar_handler.handle(intent, handler_context)

        if isinstance(intent, DocQueryIntent):
            # Sprint US-3.3: Delegate to DocumentHandler
            handler_context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
                original_text=text,
                forced_device_id=device_id,
                resolved_references=context.get("resolved_references", {}),
                conversation_history=context.get("conversation_history"),
                pending_operation=context.get("pending_operation"),
            )
            return await self._document_handler.handle(intent, handler_context)
        
        elif isinstance(intent, DisplayContentIntent):
            # Sprint US-3.2: Delegate to DisplayContentHandler
            # CRITICAL: require_feedback is passed via HandlerContext to fix the bug
            handler_context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
                original_text=text,
                forced_device_id=device_id,
                resolved_references=context.get("resolved_references", {}),
                conversation_history=context.get("conversation_history"),
                pending_operation=context.get("pending_operation"),
            )
            return await self._display_content_handler.handle(intent, handler_context)
        
        elif isinstance(intent, ConversationIntent):
            # Sprint US-2.2: Delegate to ConversationHandler
            handler_context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
                original_text=text,
            )
            return await self._conversation_handler.handle(intent, handler_context)
        
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
    # COMPLEX TASK HANDLER
    # -----------------------------------------------------------------------
    
    async def _handle_complex_task(
        self,
        request_id: str,
        text: str,
        routing_decision,
        _context: Dict[str, Any],  # Reserved for future use
        start_time: float,
        _provider: str,  # Sprint 9: Deprecated - all tasks now use Gemini
        user_id: UUID,
        devices: List[Device] = None,  # Pre-loaded devices from process()
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
        
        # Build unified context - open a fresh DB session for this operation
        from app.db.session import SessionLocal
        unified_context = None
        try:
            db = SessionLocal()
            try:
                unified_context = await build_unified_context(
                    user_id=user_id,
                    db=db,
                    request_id=request_id,
                )
            finally:
                db.close()  # Close immediately after context building
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
            system_prompt = """You are Xentauri, an advanced smart display assistant for educational environments.

You CAN:
- Control smart displays (power, input, volume)
- Show calendars, documents, and web content
- CREATE interactive visual content (games, quizzes, dashboards, presentations)
- Generate custom HTML layouts via Scene Graph

ALWAYS return valid JSON. For visual/interactive requests, use show_content with content_type="custom_layout"."""
        else:
            prompt = build_reasoner_prompt(unified_context, text, conversation_history, routing_decision) if unified_context else text
            system_prompt = "You are a strategic advisor for smart home systems."

        # Sprint 9: Use Gemini 3 Flash for all complex tasks (no thinking mode)
        response = await ai_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model_override=settings.GEMINI_REASONING_MODEL,
            max_tokens=16384,  # Large output for complex HTML/code generation
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
            # Sprint 9: Debug logging for Gemini response
            logger.info(f"[{request_id}] Gemini raw response: {response.content[:1000] if response.content else 'None'}")

            action_response = parse_action_response(response.content, strict=False)

            # Sprint 9: Debug logging for parsed action
            if hasattr(action_response, 'action_name'):
                logger.info(f"[{request_id}] Parsed action: {action_response.action_name}, params: {getattr(action_response, 'parameters', {})}")

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
                    devices=devices,  # Pass pre-loaded devices instead of db
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
                        devices=devices,  # Pass pre-loaded devices instead of db
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
        devices: List[Device],  # Pre-loaded devices instead of db
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

        # Use pre-loaded devices instead of querying DB
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
            # Sprint 9: Check for custom_layout content type → route to Scene Graph
            content_type = (parameters or {}).get("content_type", "url")
            logger.info(f"[{request_id}] _execute_content_action: action={action}, content_type={content_type}, params={parameters}")

            if content_type == "custom_layout":
                # Route to Scene Graph for custom HTML generation (games, quizzes, etc.)
                return await self._execute_custom_layout_action(
                    request_id=request_id,
                    device=device,
                    user_id=user_id,
                    parameters=parameters,
                    confidence=confidence,
                    start_time=start_time,
                )

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
            message = self._build_content_action_response(action, device.name, search, date)
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

    async def _execute_custom_layout_action(
        self,
        request_id: str,
        device: Device,
        _user_id: UUID,  # Reserved for future user-specific layouts
        parameters: Optional[Dict],
        confidence: float,
        start_time: float,
    ) -> IntentResult:
        """
        Execute custom layout generation via Scene Graph.

        Sprint 9: Routes content_type="custom_layout" requests to the Scene Graph
        system for HTML generation by Opus 4.5.

        Args:
            request_id: Unique request identifier
            device: Target device for display
            user_id: User's UUID
            parameters: Must contain 'layout_description' with the user's request
            confidence: AI confidence score
            start_time: Start time for latency tracking
        """
        from app.ai.scene.custom_layout import custom_layout_service
        from app.ai.scene import scene_service
        from app.services.websocket_manager import connection_manager

        layout_description = (parameters or {}).get("layout_description", "")

        # Log human_feedback_mode propagation
        logger.info(
            f"[{request_id}] _execute_custom_layout_action: "
            f"human_feedback_mode={getattr(self, '_require_feedback', False)}"
        )

        if not layout_description:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=confidence,
                device=device,
                action="show_content",
                parameters=parameters,
                command_sent=False,
                message="Missing layout_description for custom layout",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        logger.info(f"[{request_id}] Routing to Scene Graph for custom layout: {layout_description[:100]}...")

        try:
            # Send loading indicator to device
            await connection_manager.send_command(
                device_id=device.id,
                command_type="loading_start",
                parameters={"message": "Generando contenido...", "phase": 1},
            )

            # Generate content data with Gemini
            content_data = await scene_service.generate_content_data(
                user_request=layout_description,
            )

            if content_data and settings.CUSTOM_LAYOUT_ENABLED:
                # Loading Phase 2
                await connection_manager.send_command(
                    device_id=device.id,
                    command_type="loading_start",
                    parameters={"message": "Diseñando experiencia...", "phase": 2},
                )

                # Log validation type
                validation_type = "JS-only" if getattr(self, '_require_feedback', False) else "Full CSS+JS"
                logger.info(f"[{request_id}] Custom layout validation type: {validation_type}")

                # Generate HTML with visual validation
                layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                    content_data=content_data,
                    user_request=layout_description,
                    layout_type=content_data.get("content_type"),
                    human_feedback_mode=getattr(self, '_require_feedback', False),
                )

                if layout_result.success and layout_result.html:
                    # Log result with timing
                    logger.info(
                        f"[{request_id}] Custom layout generated: "
                        f"latency={layout_result.latency_ms:.0f}ms, "
                        f"human_feedback_mode={getattr(self, '_require_feedback', False)}, "
                        f"has_js_errors={bool(getattr(layout_result, 'js_errors', None))}"
                    )

                    custom_layout = layout_result.html
                    scene_dict = {"scene_id": request_id, "direct_flow": True}

                    # Send to device
                    result = await command_service.display_scene(
                        device_id=device.id,
                        scene=scene_dict,
                        custom_layout=custom_layout,
                    )

                    processing_time = (time.time() - start_time) * 1000

                    ai_monitor.track_command(
                        request_id=request_id,
                        device_id=device.id,
                        device_name=device.name,
                        action="display_scene",
                        command_id=result.command_id,
                        success=result.success,
                        error=result.error,
                    )

                    return IntentResult(
                        success=result.success,
                        intent_type=IntentResultType.DISPLAY_CONTENT,
                        confidence=confidence,
                        device=device,
                        action="display_scene",
                        parameters=parameters,
                        command_sent=result.success,
                        command_id=result.command_id if result.success else None,
                        message=f"Displaying custom content on {device.name}",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )

            # Fallback: Layout generation failed
            processing_time = (time.time() - start_time) * 1000
            error_msg = "Content generation failed"
            if content_data is None:
                error_msg = "Failed to generate content data"
            elif 'layout_result' in dir() and layout_result:
                error_msg = layout_result.error or "Unknown layout error"
            logger.warning(f"[{request_id}] Custom layout failed: {error_msg}")

            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=confidence,
                device=device,
                action="show_content",
                parameters=parameters,
                command_sent=False,
                message=f"Failed to generate custom layout: {error_msg}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"[{request_id}] Custom layout error: {e}", exc_info=True)

            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=confidence,
                device=device,
                action="show_content",
                parameters=parameters,
                command_sent=False,
                message=f"Error generating custom layout: {str(e)}",
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

    # NOTE: Calendar create/edit methods removed in Sprint 3.4 (US-3.4)
    # These are now handled by CalendarHandler

    # -----------------------------------------------------------------------
    # CONTENT ACTION HELPER - KEPT FOR COMPLEX TASK
    # -----------------------------------------------------------------------

    def _build_content_action_response(
        self, action: str, device_name: str, search: Optional[str] = None, date: Optional[str] = None
    ) -> str:
        """Build a user-friendly response message for content actions."""
        if action == "show_content":
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

    # NOTE: Calendar create/edit methods (_handle_calendar_create, _handle_create_event,
    # _handle_confirm_create, _handle_cancel_create, _handle_edit_pending,
    # _handle_calendar_edit, _handle_edit_existing_event, _handle_delete_existing_event,
    # _handle_select_event, _handle_confirm_edit, _handle_confirm_delete, _handle_cancel_edit)
    # were removed in Sprint 3.4 (US-3.4). These are now handled by CalendarHandler.

    # NOTE: Doc query methods (_handle_doc_query, _handle_link_doc, _handle_open_doc,
    # _handle_read_doc, _handle_summarize_meeting_doc, _handle_create_event_from_doc)
    # were removed in Sprint 4 (US-4.3). These are now handled by DocumentHandler.

    # NOTE: Display scene helpers (_fetch_realtime_data_for_scene, _extract_location_from_request)
    # were removed in Sprint 4 (US-4.3). These are now handled by DisplayContentHandler.


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

intent_service = IntentService()
