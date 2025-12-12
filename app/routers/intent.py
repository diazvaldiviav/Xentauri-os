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
from app.deps import get_current_user
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
        max_length=500,
        description="Natural language command or question"
    )
    device_id: Optional[UUID] = Field(
        default=None,
        description="Optional: Target a specific device by ID"
    )


class IntentResponse(BaseModel):
    """
    Response schema for the /intent endpoint.
    
    Example:
    {
        "success": true,
        "intent_type": "device_command",
        "device": {"id": "uuid...", "name": "Living Room TV"},
        "action": "show_calendar",
        "command_sent": true,
        "message": "Displaying calendar on Living Room TV"
    }
    """
    success: bool = Field(description="Whether the request was processed successfully")
    intent_type: str = Field(description="Type of intent detected")
    confidence: float = Field(description="Confidence score 0-1")
    device: Optional[Dict[str, Any]] = Field(default=None, description="Target device info")
    action: Optional[str] = Field(default=None, description="Action performed")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    command_sent: bool = Field(default=False, description="Whether command was sent")
    command_id: Optional[str] = Field(default=None, description="Command ID if sent")
    message: str = Field(description="Human-readable response message")
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
        return _result_to_response(result)
    
    except Exception as e:
        logger.error(f"Failed to process intent: {e}", exc_info=True)
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
