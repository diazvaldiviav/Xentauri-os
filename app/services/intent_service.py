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
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
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
            
            context = {
                "devices": device_context,
                "user_id": str(user_id),
            }
            
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
        
        if action == "clear_content":
            result = await command_service.clear_content(device.id)
        else:
            content_token = content_token_service.generate(user_id, content_type="calendar")
            
            if action == "show_calendar":
                url = f"/cloud/calendar?token={content_token}"
                if parameters and "date" in parameters:
                    url += f"&date={parameters['date']}"
                content_type = "calendar"
            elif action == "show_content":
                base_url = (parameters or {}).get("url", "/cloud/calendar")
                if base_url.startswith("/cloud/"):
                    separator = "&" if "?" in base_url else "?"
                    url = f"{base_url}{separator}token={content_token}"
                    if parameters and "date" in parameters:
                        url += f"&date={parameters['date']}"
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
            message = self._build_content_message(action, device.name, date)
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
    
    @staticmethod
    def _build_content_message(action: str, device_name: str, date: Optional[str] = None) -> str:
        """Build success message for content actions."""
        if action == "show_calendar":
            if date:
                return f"Displaying calendar for {date} on {device_name}"
            return f"Displaying calendar on {device_name}"
        elif action == "show_content":
            if date:
                return f"Displaying content for {date} on {device_name}"
            return f"Displaying content on {device_name}"
        elif action == "clear_content":
            return f"Cleared display on {device_name}"
        return f"Content action completed on {device_name}"


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

intent_service = IntentService()
