"""
Intent Result Types - Shared data structures for intent processing.

This module contains the result types used by IntentService and handlers.
Extracted to a separate module to avoid circular imports between
intent_service.py and intent handlers.

Sprint US-2.1: Extracted from intent_service.py
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


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

    Attributes:
        success: Whether the intent was processed successfully
        intent_type: Type of intent that was processed
        confidence: AI confidence score (0.0 - 1.0)
        device: Target device for device-related intents
        action: The action that was executed
        parameters: Action parameters
        data: Extra data for specific intent types
        command_sent: Whether a command was sent to a device
        command_id: ID of the sent command
        message: Human-readable result message
        response: AI conversational response
        processing_time_ms: Processing time in milliseconds
        request_id: Unique request identifier for tracing
    """
    success: bool
    intent_type: IntentResultType
    confidence: float = 0.0

    # Device info - using Any to avoid circular import with Device model
    device: Optional[Any] = None

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
