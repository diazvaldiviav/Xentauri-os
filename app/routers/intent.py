"""
Intent Router - API endpoint for natural language command processing.

This router handles the /intent endpoint which is the main entry point
for natural language commands. It delegates all business logic to IntentService.

Architecture:
=============
```
┌─────────────────┐
│ "Show calendar  │
│  on living      │
│  room TV"       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Intent Router  │  ← HTTP handling only (this file)
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Intent Service  │  ← All business logic
│                 │
└────────┬────────┘
         │
   ┌─────┴─────┐
   │           │
   ▼           ▼
┌───────┐  ┌────────┐
│  AI   │  │Commands│
└───────┘  └────────┘
```
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, get_user_from_agent
from app.models.user import User
from app.services.intent_service import intent_service, IntentResult
from app.ai.monitoring import ai_monitor


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
    
    Example:
    {
        "text": "Show the calendar on living room TV"
    }
    """
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Natural language command or question (supports data payloads up to 10K chars)"
    )
    device_id: Optional[UUID] = Field(
        default=None,
        description="Optional: Target a specific device by ID"
    )


class IntentResponse(BaseModel):
    """
    Response schema for the /intent endpoint.
    
    Example (single action):
    {
        "success": true,
        "intent_type": "device_command",
        "device": {"id": "uuid...", "name": "Living Room TV"},
        "action": "show_calendar",
        "command_sent": true,
        "message": "Displaying calendar on Living Room TV"
    }
    
    Example (multi-action, Sprint 4.0.3):
    {
        "success": true,
        "intent_type": "device_command",
        "action": "clear_content",
        "command_sent": true,
        "data": {
            "actions_executed": [
                {"action": "clear_content", "success": true, "command_id": "xxx"},
                {"action": "show_calendar", "success": true, "command_id": "yyy"}
            ],
            "commands_sent": 2
        },
        "message": "Cleared Living Room TV → Displaying calendar"
    }
    """
    success: bool = Field(description="Whether the request was processed successfully")
    intent_type: str = Field(description="Type of intent detected")
    confidence: float = Field(description="Confidence score 0-1")
    device: Optional[Dict[str, Any]] = Field(default=None, description="Target device info")
    action: Optional[str] = Field(default=None, description="Primary action performed")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    data: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Additional data (for multi-action: actions_executed[], commands_sent)"
    )
    command_sent: bool = Field(default=False, description="Whether any command was sent")
    command_id: Optional[str] = Field(default=None, description="Primary command ID if sent")
    message: str = Field(description="Human-readable response message (chained with → for multi-action)")
    response: Optional[str] = Field(default=None, description="AI response for conversations")
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

def _result_to_response(result: IntentResult) -> IntentResponse:
    """Convert IntentResult to IntentResponse."""
    result_dict = result.to_dict()
    return IntentResponse(**result_dict)


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
    5. Saves conversation history for context (Sprint 4.2)
    
    **Examples:**
    - "Turn on the living room TV"
    - "Show the calendar on bedroom monitor"
    - "Switch the office display to HDMI 2"
    - "What devices do I have?"
    - "Is the kitchen TV on?"
    """
    try:
        result = await intent_service.process(
            text=request.text,
            user_id=current_user.id,
            db=db,
            device_id=request.device_id,
        )
        
        # Sprint 4.2: Save conversation history for context-aware processing
        # This ensures conversation_history is populated for future requests
        from app.services.conversation_context_service import conversation_context_service
        
        conversation_context_service.add_conversation_turn(
            user_id=str(current_user.id),
            user_message=request.text,
            assistant_response=result.message or "",
            intent_type=result.intent_type,
        )
        
        return _result_to_response(result)

    except Exception as e:
        logger.error(f"Failed to process intent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process intent: {str(e)}"
        )


@router.post("/agent", response_model=IntentResponse)
async def process_intent_agent(
    request: IntentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_agent),
):
    """
    Process a natural language command from a Pi Alexa device.

    This endpoint is identical to POST /intent but authenticates via
    X-Agent-ID header instead of JWT Bearer token. Designed for Pi devices
    that send voice commands but don't have JWT tokens.

    **Authentication:**
    - Header: `X-Agent-ID: <agent_id>`
    - The agent_id must be paired to a device owned by the user

    **Example:**
    ```bash
    curl -X POST https://api.xentauri.com/intent/agent \\
      -H "X-Agent-ID: pi-alexa-abc123" \\
      -H "Content-Type: application/json" \\
      -d '{"text": "what events do I have today"}'
    ```

    **Examples of commands:**
    - "Turn on the living room TV"
    - "Show the calendar on bedroom monitor"
    - "What's on my schedule today?"
    - "Create a meeting tomorrow at 3pm"
    """
    try:
        # Same logic as /intent - reuse IntentService
        result = await intent_service.process(
            text=request.text,
            user_id=current_user.id,
            db=db,
            device_id=request.device_id,
        )

        # Save conversation history for context-aware processing
        from app.services.conversation_context_service import conversation_context_service

        conversation_context_service.add_conversation_turn(
            user_id=str(current_user.id),
            user_message=request.text,
            assistant_response=result.message or "",
            intent_type=result.intent_type,
        )

        return _result_to_response(result)

    except Exception as e:
        logger.error(f"[INTENT_AGENT] Failed to process intent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process intent: {str(e)}"
        )


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
