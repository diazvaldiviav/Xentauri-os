"""
Intent Router - API endpoint for natural language command processing.

This router handles the /intent endpoint which is the main entry point
for natural language commands. It:

1. Receives natural language text (e.g., "Show the calendar on living room TV")
2. Parses the intent using LLM
3. Maps device names to device IDs
4. Sends commands to devices via WebSocket
5. Returns structured response

Flow:
=====
┌─────────────────┐
│ "Show calendar  │
│  on living      │
│  room TV"       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Intent Parser  │  ← Gemini Flash extracts intent
│  (LLM)          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Device Mapper  │  ← Match "living room TV" to device
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Command Service │  ← Send via WebSocket
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response       │  ← Structured result
│  to client      │
└─────────────────┘
"""

import logging
import time
import uuid as uuid_module
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
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
    ParsedCommand,
)
from app.ai.router.orchestrator import ai_router
from app.ai.monitoring import ai_monitor
from app.ai.providers.base import ProviderType, TokenUsage

# ---------------------------------------------------------------------------
# LOGGER SETUP
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/intent", tags=["intent"])


# ---------------------------------------------------------------------------
# REQUEST/RESPONSE SCHEMAS
# ---------------------------------------------------------------------------

class IntentRequest(BaseModel):
    """
    Request schema for the /intent endpoint.
    
    Example request:
    {
        "text": "Show the calendar on living room TV"
    }
    """
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="Natural language command or question"
    )
    
    # Optional: force processing with a specific device
    device_id: Optional[UUID] = Field(
        default=None,
        description="Optional: Target a specific device by ID"
    )


class IntentResponse(BaseModel):
    """
    Response schema for the /intent endpoint.
    
    Example response (device command):
    {
        "success": true,
        "intent_type": "device_command",
        "device": {
            "id": "uuid...",
            "name": "Living Room TV"
        },
        "action": "set_input",
        "parameters": {"app": "calendar"},
        "command_sent": true,
        "command_id": "uuid...",
        "message": "Showing calendar on Living Room TV"
    }
    """
    success: bool = Field(description="Whether the request was processed successfully")
    
    # Intent details
    intent_type: str = Field(description="Type of intent detected")
    confidence: float = Field(description="Confidence score 0-1")
    
    # Device info (for device commands/queries)
    device: Optional[Dict[str, Any]] = Field(default=None, description="Target device info")
    
    # Action info
    action: Optional[str] = Field(default=None, description="Action to perform")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    
    # Execution result
    command_sent: bool = Field(default=False, description="Whether command was sent to device")
    command_id: Optional[str] = Field(default=None, description="Command ID if sent")
    
    # Human-readable response
    message: str = Field(description="Human-readable response message")
    response: Optional[str] = Field(default=None, description="AI response for conversations")
    
    # Debug/metrics
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time")
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")


class AIStatsResponse(BaseModel):
    """Response schema for /intent/stats endpoint."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: str
    total_tokens: int
    avg_latency_ms: float
    estimated_total_cost: str
    requests_by_provider: Dict[str, int]


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_user_devices(db: Session, user_id: UUID) -> List[Device]:
    """Get all devices for a user."""
    return db.query(Device).filter(Device.user_id == user_id).all()


def format_device_info(device: Device) -> Dict[str, Any]:
    """Format device info for response."""
    return {
        "id": str(device.id),
        "name": device.name,
        "is_online": device.is_online,
    }


def get_action_value(action) -> Optional[str]:
    """Safely extract action value from enum or string."""
    if action is None:
        return None
    if hasattr(action, 'value'):
        return action.value
    return str(action)


def get_intent_type_value(intent_type) -> str:
    """Safely extract intent_type value from enum or string."""
    if hasattr(intent_type, 'value'):
        return intent_type.value
    return str(intent_type)


# ---------------------------------------------------------------------------
# CONTENT DISPLAY HELPERS (Sprint 3.5)
# ---------------------------------------------------------------------------

async def _handle_content_action(
    device: Device,
    action: str,
    user_id: UUID,
    parameters: Optional[Dict] = None,
):
    """
    Handle content display actions (show_calendar, show_content, clear_content).
    
    This maps abstract content actions to the appropriate URLs with signed tokens.
    
    Args:
        device: Target device
        action: The action type (show_calendar, show_content, clear_content)
        user_id: The user's ID (needed for generating content token)
        parameters: Optional parameters (may include url, content_type, date)
        
    Returns:
        CommandResult from command_service
    """
    from app.services.commands import command_service, CommandResult
    from app.services.content_token import content_token_service
    
    if action == "clear_content":
        return await command_service.clear_content(device.id)
    
    # Generate signed content token for the user
    content_token = content_token_service.generate(user_id, content_type="calendar")
    
    # Determine the URL to display (with token)
    if action == "show_calendar":
        # Calendar endpoint with signed token and optional date
        url = f"/cloud/calendar?token={content_token}"
        
        # Add date parameter if provided (Sprint 3.6)
        if parameters and "date" in parameters:
            url += f"&date={parameters['date']}"
        
        content_type = "calendar"
    elif action == "show_content":
        # Use provided URL or default to calendar
        base_url = (parameters or {}).get("url", "/cloud/calendar")
        # Add token if it's a cloud endpoint
        if base_url.startswith("/cloud/"):
            separator = "&" if "?" in base_url else "?"
            url = f"{base_url}{separator}token={content_token}"
            
            # Add date parameter if provided (Sprint 3.6 fix)
            # This handles cases where AI returns show_content with date instead of show_calendar
            if parameters and "date" in parameters:
                url += f"&date={parameters['date']}"
        else:
            url = base_url
        content_type = (parameters or {}).get("content_type", "url")
    else:
        url = f"/cloud/calendar?token={content_token}"
        content_type = "url"
    
    return await command_service.show_content(
        device_id=device.id,
        url=url,
        content_type=content_type,
    )


def _build_content_message(action: str, device_name: str, date: Optional[str] = None) -> str:
    """Build success message for content display actions."""
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
# GPT ACTION EXECUTOR (Sprint 3.6)
# ---------------------------------------------------------------------------

async def _execute_gpt_action(
    action_response,  # ActionResponse from GPT
    request_id: str,
    user_id: Optional[UUID],
    db: Optional[Session],
    processing_time: float,
    routing_confidence: float,
    skip_response: bool = False,
) -> IntentResponse:
    """
    Execute an action returned by GPT-4o.
    
    This takes a structured ActionResponse and routes it to the appropriate
    handler (content actions, device commands, etc.).
    
    Args:
        action_response: ActionResponse from GPT
        request_id: Request tracking ID
        user_id: User ID
        db: Database session
        processing_time: Time elapsed so far
        routing_confidence: Confidence from routing decision
        skip_response: If True, return minimal response (for sequences)
        
    Returns:
        IntentResponse with execution result
    """
    from app.ai.schemas.action_response import (
        is_content_action,
        is_device_control_action,
    )
    
    if not db or not user_id:
        return IntentResponse(
            success=False,
            intent_type="action",
            confidence=routing_confidence,
            message="Cannot execute action: missing database or user context",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # Get target device
    target_device_name = action_response.get_target_device()
    
    if not target_device_name:
        return IntentResponse(
            success=False,
            intent_type="action",
            confidence=action_response.confidence,
            message=f"No target device specified for action: {action_response.action_name}",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # Get user's devices
    devices = get_user_devices(db, user_id)
    
    # Match device
    device, match_confidence = device_mapper.match(target_device_name, devices)
    
    if not device:
        alternatives = device_mapper.match_all(target_device_name, devices, limit=3)
        suggestion = ""
        if alternatives:
            names = [f'"{d.name}"' for d, _ in alternatives]
            suggestion = f" Did you mean: {', '.join(names)}?"
        
        return IntentResponse(
            success=False,
            intent_type="action",
            confidence=action_response.confidence,
            message=f"Could not find device '{target_device_name}'.{suggestion}",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # Check if online
    if not device.is_online:
        return IntentResponse(
            success=False,
            intent_type="action",
            confidence=action_response.confidence,
            device=format_device_info(device),
            message=f"'{device.name}' is currently offline.",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    action_name = action_response.action_name
    
    # ---------------------------------------------------------------------------
    # EXECUTE CONTENT ACTIONS
    # ---------------------------------------------------------------------------
    if is_content_action(action_name):
        result = await _handle_content_action(
            device=device,
            action=action_name,
            user_id=user_id,
            parameters=action_response.parameters,
        )
        
        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action_name,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )
        
        if result.success:
            # Extract date if present
            date = action_response.get_date()
            message = _build_content_message(action_name, device.name, date)
        else:
            message = f"Failed: {result.error}"
        
        return IntentResponse(
            success=result.success,
            intent_type="action",
            confidence=action_response.confidence,
            device=format_device_info(device),
            action=action_name,
            parameters=action_response.parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # ---------------------------------------------------------------------------
    # EXECUTE DEVICE CONTROL ACTIONS
    # ---------------------------------------------------------------------------
    elif is_device_control_action(action_name):
        result = await command_service.send_command(
            device_id=device.id,
            command_type=action_name,
            parameters=action_response.parameters,
        )
        
        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action_name,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )
        
        if result.success:
            message = _build_success_message(action_name, device.name, action_response.parameters)
        else:
            message = f"Failed: {result.error}"
        
        return IntentResponse(
            success=result.success,
            intent_type="action",
            confidence=action_response.confidence,
            device=format_device_info(device),
            action=action_name,
            parameters=action_response.parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # ---------------------------------------------------------------------------
    # UNKNOWN ACTION
    # ---------------------------------------------------------------------------
    else:
        return IntentResponse(
            success=False,
            intent_type="action",
            confidence=action_response.confidence,
            message=f"Unknown action type: {action_name}",
            processing_time_ms=processing_time,
            request_id=request_id,
        )


# ---------------------------------------------------------------------------
# COMPLEX TASK HANDLER
# ---------------------------------------------------------------------------

async def _handle_complex_task(
    request_id: str,
    text: str,
    routing_decision,  # RoutingDecision from orchestrator
    context: Dict[str, Any],
    start_time: float,
    provider: str,
    db: Session = None,
    user_id: Optional[UUID] = None,
) -> IntentResponse:
    """
    Handle complex tasks that require GPT (execution) or Claude (reasoning).
    
    Sprint 3.6 Update:
    - For GPT-4o (execution): Returns structured JSON actions that can be executed
    - For Claude (reasoning): Returns thoughtful analysis/recommendations
    - Uses UnifiedContext for consistent context across all models
    
    Args:
        request_id: Tracking ID for the request
        text: Original user request
        routing_decision: Routing decision from orchestrator
        context: User context (devices, etc.) - legacy format
        start_time: Request start time
        provider: "openai" for execution tasks, "anthropic" for reasoning
        db: Database session (optional, for UnifiedContext)
        user_id: User ID (optional, for UnifiedContext)
        
    Returns:
        IntentResponse with AI-generated response or executable actions
    """
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
    
    # Select the appropriate provider
    if provider == "openai":
        ai_provider = openai_provider
        model_name = settings.OPENAI_MODEL
        task_type = "execution"
    else:  # anthropic
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
            "reasoning": routing_decision.reasoning,
        }
    )
    
    # ---------------------------------------------------------------------------
    # Build UnifiedContext (if db available)
    # ---------------------------------------------------------------------------
    unified_context = None
    if db and user_id:
        try:
            unified_context = await build_unified_context(
                user_id=user_id,
                db=db,
                request_id=request_id,
            )
        except Exception as e:
            # Sprint 3.6 Bug Fix: Fail fast instead of continuing with broken context
            # See BUG_REPORT_SPRINT_3.6.txt for details
            logger.error(f"Failed to build unified context: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to build context: {str(e)}"
            )
    
    # ---------------------------------------------------------------------------
    # EXECUTION TASKS (GPT-4o) - Return structured JSON actions
    # ---------------------------------------------------------------------------
    if task_type == "execution":
        # Build execution prompt
        if unified_context:
            prompt = build_execution_prompt(unified_context, text)
        else:
            # Fallback to legacy prompt style
            prompt = f"""You are Jarvis, an execution specialist for smart displays.

User's devices: {context.get('devices', [])}
User request: "{text}"

Return a JSON action in this format:
{{
  "type": "action",
  "action_name": "show_calendar|power_on|etc.",
  "parameters": {{"target_device": "device name", "date": "YYYY-MM-DD"}}
}}

If you need clarification:
{{
  "type": "clarification",
  "message": "What you need to ask"
}}

Your JSON response:"""
        
        # Call GPT-4o
        response = await ai_provider.generate(
            prompt=prompt,
            system_prompt="You are a smart display execution assistant. Always return valid JSON.",
        )
        
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
            
            return IntentResponse(
                success=False,
                intent_type="complex_execution",
                confidence=routing_decision.confidence,
                message=f"Failed to process: {response.error}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        
        # Parse structured JSON response
        try:
            action_response = parse_action_response(response.content, strict=False)
            
            # Log successful response
            ai_monitor.track_response(
                request_id=request_id,
                provider=provider,
                model=model_name,
                content=response.content[:500],
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                latency_ms=processing_time,
                success=True,
            )
            
            # ---------------------------------------------------------------------------
            # HANDLE CLARIFICATION
            # ---------------------------------------------------------------------------
            if isinstance(action_response, ClarificationResponse):
                return IntentResponse(
                    success=True,
                    intent_type="clarification",
                    confidence=routing_decision.confidence,
                    message=action_response.message,
                    response=action_response.message,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            # ---------------------------------------------------------------------------
            # HANDLE SINGLE ACTION
            # ---------------------------------------------------------------------------
            elif isinstance(action_response, ActionResponse):
                # Execute the action
                return await _execute_gpt_action(
                    action_response=action_response,
                    request_id=request_id,
                    user_id=user_id,
                    db=db,
                    processing_time=processing_time,
                    routing_confidence=routing_decision.confidence,
                )
            
            # ---------------------------------------------------------------------------
            # HANDLE ACTION SEQUENCE
            # ---------------------------------------------------------------------------
            elif isinstance(action_response, ActionSequenceResponse):
                # Execute actions in sequence
                results = []
                for action in action_response.actions:
                    result = await _execute_gpt_action(
                        action_response=action,
                        request_id=request_id,
                        user_id=user_id,
                        db=db,
                        processing_time=processing_time,
                        routing_confidence=routing_decision.confidence,
                        skip_response=True,  # Don't return yet
                    )
                    results.append(result)
                
                # Return summary of all actions
                all_success = all(r.success for r in results)
                messages = [r.message for r in results if r.message]
                
                return IntentResponse(
                    success=all_success,
                    intent_type="action_sequence",
                    confidence=routing_decision.confidence,
                    message="\n".join(messages),
                    command_sent=any(r.command_sent for r in results),
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            
            else:
                # Unexpected response type
                return IntentResponse(
                    success=False,
                    intent_type="complex_execution",
                    confidence=routing_decision.confidence,
                    message="Received unexpected response format from AI",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
        
        except Exception as e:
            logger.error(f"Failed to parse GPT response: {e}", exc_info=True)
            
            return IntentResponse(
                success=False,
                intent_type="complex_execution",
                confidence=routing_decision.confidence,
                message=f"Failed to parse AI response: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    # ---------------------------------------------------------------------------
    # REASONING TASKS (Claude) - Return thoughtful analysis
    # ---------------------------------------------------------------------------
    else:  # reasoning
        # Build reasoning prompt
        if unified_context:
            prompt = build_reasoner_prompt(unified_context, text)
        else:
            # Fallback
            prompt = f"""You are Jarvis, a strategic advisor for smart displays.

User's devices: {context.get('devices', [])}
User question: "{text}"

Provide thoughtful analysis and recommendations.
Be thorough but concise."""
        
        # Call Claude
        response = await ai_provider.generate(
            prompt=prompt,
            system_prompt="You are a strategic advisor for smart home systems.",
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        # Log the response
        if response.success:
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
            
            return IntentResponse(
                success=True,
                intent_type="complex_reasoning",
                confidence=routing_decision.confidence,
                action="reasoning",
                message=f"Analysis by {model_name}",
                response=response.content,
                processing_time_ms=processing_time,
                request_id=request_id,
            )
        else:
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
            
            return IntentResponse(
                success=False,
                intent_type="complex_reasoning",
                confidence=routing_decision.confidence,
                message=f"Failed to process: {response.error}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("", response_model=IntentResponse)
async def process_intent(
    request: IntentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process a natural language command.
    
    This is the main endpoint for voice/text commands. It:
    1. Parses the intent from natural language
    2. Maps device names to your devices
    3. Sends commands to connected devices
    4. Returns the result
    
    **Examples:**
    - "Turn on the living room TV"
    - "Show the calendar on bedroom monitor"
    - "Switch the office display to HDMI 2"
    - "What devices do I have?"
    - "Is the kitchen TV on?"
    
    **Returns:**
    - Structured intent with action and parameters
    - Command ID if a command was sent
    - Human-readable message
    """
    start_time = time.time()
    request_id = str(uuid_module.uuid4())
    
    # Log the request
    ai_monitor.track_request(
        request_id=request_id,
        prompt=request.text,
        provider="gemini",
        model=settings.GEMINI_MODEL,
        user_id=current_user.id,
    )
    
    try:
        # Get user's devices for context
        devices = get_user_devices(db, current_user.id)
        device_context = device_mapper.to_device_context(devices)
        
        context = {
            "devices": device_context,
            "user_name": current_user.email.split("@")[0],  # Simple name extraction
        }
        
        # ---------------------------------------------------------------------------
        # STEP 1: Use AI Router to analyze complexity and decide routing
        # ---------------------------------------------------------------------------
        routing_decision = await ai_router.analyze_request(request.text, context)
        
        ai_monitor.track_routing(
            request_id=request_id,
            complexity=routing_decision.complexity.value,
            target_provider=routing_decision.target_provider,
            confidence=routing_decision.confidence,
            reasoning=routing_decision.reasoning,
            is_device_command=routing_decision.is_device_command,
        )
        
        # ---------------------------------------------------------------------------
        # STEP 2: Route based on complexity
        # ---------------------------------------------------------------------------
        from app.ai.router.orchestrator import TaskComplexity
        
        # Complex execution tasks (code, tools) → GPT
        if routing_decision.complexity == TaskComplexity.COMPLEX_EXECUTION:
            return await _handle_complex_task(
                request_id=request_id,
                text=request.text,
                routing_decision=routing_decision,
                context=context,
                start_time=start_time,
                provider="openai",
                db=db,
                user_id=current_user.id,
            )
        
        # Complex reasoning tasks (analysis, planning) → Claude
        if routing_decision.complexity == TaskComplexity.COMPLEX_REASONING:
            return await _handle_complex_task(
                request_id=request_id,
                text=request.text,
                routing_decision=routing_decision,
                context=context,
                start_time=start_time,
                provider="anthropic",
                db=db,
                user_id=current_user.id,
            )
        
        # ---------------------------------------------------------------------------
        # STEP 3: Simple tasks → Gemini Intent Parser (original flow)
        # ---------------------------------------------------------------------------
        # Parse the intent
        parsed = await intent_parser.create_parsed_command(
            text=request.text,
            user_id=current_user.id,
            context=context,
        )
        
        # Log the parsed intent
        ai_monitor.track_intent(
            request_id=request_id,
            original_text=request.text,
            intent_type=get_intent_type_value(parsed.intent.intent_type),
            device_name=parsed.device_name,
            action=parsed.action,
            confidence=parsed.intent.confidence,
            processing_time_ms=parsed.processing_time_ms or 0,
        )
        
        # Handle based on intent type
        intent = parsed.intent
        
        # ---------------------------------------------------------------------------
        # DEVICE COMMAND
        # ---------------------------------------------------------------------------
        if isinstance(intent, DeviceCommand):
            return await _handle_device_command(
                request_id=request_id,
                intent=intent,
                devices=devices,
                forced_device_id=request.device_id,
                start_time=start_time,
                user_id=current_user.id,
            )
        
        # ---------------------------------------------------------------------------
        # DEVICE QUERY
        # ---------------------------------------------------------------------------
        elif isinstance(intent, DeviceQuery):
            return await _handle_device_query(
                request_id=request_id,
                intent=intent,
                devices=devices,
                start_time=start_time,
            )
        
        # ---------------------------------------------------------------------------
        # SYSTEM QUERY
        # ---------------------------------------------------------------------------
        elif isinstance(intent, SystemQuery):
            return await _handle_system_query(
                request_id=request_id,
                intent=intent,
                devices=devices,
                start_time=start_time,
            )
        
        # ---------------------------------------------------------------------------
        # CONVERSATION
        # ---------------------------------------------------------------------------
        elif isinstance(intent, ConversationIntent):
            return await _handle_conversation(
                request_id=request_id,
                intent=intent,
                original_text=request.text,
                start_time=start_time,
            )
        
        # ---------------------------------------------------------------------------
        # UNKNOWN
        # ---------------------------------------------------------------------------
        else:
            processing_time = (time.time() - start_time) * 1000
            return IntentResponse(
                success=False,
                intent_type="unknown",
                confidence=0.0,
                message="I couldn't understand that request. Try something like 'Turn on the TV' or 'What devices do I have?'",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
    
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        ai_monitor.track_error(
            request_id=request_id,
            error=str(e),
            stage="processing",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process intent: {str(e)}"
        )


async def _handle_device_command(
    request_id: str,
    intent: DeviceCommand,
    devices: List[Device],
    forced_device_id: Optional[UUID],
    start_time: float,
    user_id: Optional[UUID] = None,
) -> IntentResponse:
    """Handle a device command intent."""
    
    # Match device by name or use forced device ID
    if forced_device_id:
        device = next((d for d in devices if d.id == forced_device_id), None)
        match_confidence = 1.0
    else:
        device, match_confidence = device_mapper.match(intent.device_name, devices)
    
    if not device:
        processing_time = (time.time() - start_time) * 1000
        
        # Suggest alternatives if available
        alternatives = device_mapper.match_all(intent.device_name, devices, limit=3)
        suggestion = ""
        if alternatives:
            names = [f'"{d.name}"' for d, _ in alternatives]
            suggestion = f" Did you mean: {', '.join(names)}?"
        
        return IntentResponse(
            success=False,
            intent_type="device_command",
            confidence=intent.confidence,
            action=get_action_value(intent.action),
            message=f"I couldn't find a device matching '{intent.device_name}'.{suggestion}",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # Check if device is online
    if not device.is_online:
        processing_time = (time.time() - start_time) * 1000
        return IntentResponse(
            success=False,
            intent_type="device_command",
            confidence=intent.confidence,
            device=format_device_info(device),
            action=get_action_value(intent.action),
            message=f"'{device.name}' is currently offline. Please check the connection.",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # Get the action type
    action = get_action_value(intent.action) or "status"
    
    # ---------------------------------------------------------------------------
    # SPECIAL HANDLING: Content Display Actions (Sprint 3.5)
    # ---------------------------------------------------------------------------
    # Handle show_calendar and show_content specially by calling show_content
    # with the appropriate URL
    if action in ("show_calendar", "show_content", "clear_content"):
        result = await _handle_content_action(
            device=device,
            action=action,
            user_id=user_id,
            parameters=intent.parameters,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        # Log the command
        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )
        
        # Build message
        if result.success:
            message = _build_content_message(action, device.name)
        else:
            message = f"Failed to display content on {device.name}: {result.error}"
        
        return IntentResponse(
            success=result.success,
            intent_type="device_command",
            confidence=intent.confidence,
            device=format_device_info(device),
            action=action,
            parameters=intent.parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    # ---------------------------------------------------------------------------
    # STANDARD DEVICE COMMANDS
    # ---------------------------------------------------------------------------
    # Send the command
    result = await command_service.send_command(
        device_id=device.id,
        command_type=action,
        parameters=intent.parameters,
    )
    
    processing_time = (time.time() - start_time) * 1000
    
    # Log the command
    ai_monitor.track_command(
        request_id=request_id,
        device_id=device.id,
        device_name=device.name,
        action=action,
        command_id=result.command_id,
        success=result.success,
        error=result.error,
    )
    
    # Build human-readable message
    if result.success:
        message = _build_success_message(action, device.name, intent.parameters)
    else:
        message = f"Failed to send command to {device.name}: {result.error}"
    
    return IntentResponse(
        success=result.success,
        intent_type="device_command",
        confidence=intent.confidence,
        device=format_device_info(device),
        action=action,
        parameters=intent.parameters,
        command_sent=result.success,
        command_id=result.command_id if result.success else None,
        message=message,
        processing_time_ms=processing_time,
        request_id=request_id,
    )


async def _handle_device_query(
    request_id: str,
    intent: DeviceQuery,
    devices: List[Device],
    start_time: float,
) -> IntentResponse:
    """Handle a device query intent."""
    
    # Match device
    device, _ = device_mapper.match(intent.device_name, devices)
    
    if not device:
        processing_time = (time.time() - start_time) * 1000
        return IntentResponse(
            success=False,
            intent_type="device_query",
            confidence=intent.confidence,
            message=f"I couldn't find a device matching '{intent.device_name}'.",
            processing_time_ms=processing_time,
            request_id=request_id,
        )
    
    processing_time = (time.time() - start_time) * 1000
    
    # Handle different query types
    action = get_action_value(intent.action) or "status"
    
    if action == "status" or action == "is_online":
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
    
    return IntentResponse(
        success=True,
        intent_type="device_query",
        confidence=intent.confidence,
        device=format_device_info(device),
        action=action,
        message=message,
        processing_time_ms=processing_time,
        request_id=request_id,
    )


async def _handle_system_query(
    request_id: str,
    intent: SystemQuery,
    devices: List[Device],
    start_time: float,
) -> IntentResponse:
    """Handle a system query intent."""
    
    processing_time = (time.time() - start_time) * 1000
    action = get_action_value(intent.action) or "help"
    
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
    
    return IntentResponse(
        success=True,
        intent_type="system_query",
        confidence=intent.confidence,
        action=action,
        message=message,
        processing_time_ms=processing_time,
        request_id=request_id,
    )


async def _handle_conversation(
    request_id: str,
    intent: ConversationIntent,
    original_text: str,
    start_time: float,
) -> IntentResponse:
    """Handle a conversational intent."""
    
    processing_time = (time.time() - start_time) * 1000
    action = get_action_value(intent.action) or "greeting"
    
    # Simple responses for common conversation types
    responses = {
        "greeting": "Hello! I'm Jarvis, your display control assistant. How can I help you today?",
        "thanks": "You're welcome! Let me know if you need anything else.",
        "question": "That's an interesting question! I'm specialized in controlling display devices. Is there something specific about your TVs or monitors I can help with?",
    }
    
    message = responses.get(action, "I'm here to help you control your displays. What would you like to do?")
    
    return IntentResponse(
        success=True,
        intent_type="conversation",
        confidence=intent.confidence,
        action=action,
        message=message,
        response=message,
        processing_time_ms=processing_time,
        request_id=request_id,
    )


def _build_success_message(action: str, device_name: str, parameters: Optional[Dict]) -> str:
    """Build a human-readable success message."""
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
    
    if action == "set_input":
        if parameters:
            input_name = parameters.get("input") or parameters.get("app") or parameters.get("source")
            if input_name:
                return f"Switching {device_name} to {input_name}"
        return f"Changing input on {device_name}"
    
    if action == "volume_set" and parameters:
        level = parameters.get("level", "?")
        return f"Setting volume to {level}% on {device_name}"
    
    return f"Command sent to {device_name}"


# ---------------------------------------------------------------------------
# STATS ENDPOINT
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=AIStatsResponse)
async def get_ai_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get AI usage statistics.
    
    Returns aggregated metrics about AI usage including:
    - Total requests processed
    - Success/failure rates
    - Token usage
    - Estimated costs
    """
    stats = ai_monitor.get_stats()
    return AIStatsResponse(
        total_requests=stats.total_requests,
        successful_requests=stats.successful_requests,
        failed_requests=stats.failed_requests,
        success_rate=f"{stats.success_rate:.1f}%",
        total_tokens=stats.total_tokens,
        avg_latency_ms=round(stats.avg_latency_ms, 2),
        estimated_total_cost=f"${stats.estimated_total_cost:.4f}",
        requests_by_provider=stats.requests_by_provider,
    )
