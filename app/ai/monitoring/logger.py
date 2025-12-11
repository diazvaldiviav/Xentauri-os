"""
AI Logger - Structured logging for AI operations.

This module provides structured logging specifically for AI operations.
It captures:
- Request details (prompt, model, provider)
- Response details (content, tokens, latency)
- Errors and failures
- User context

Log Format:
==========
Each log entry includes:
- Timestamp
- Request ID (for tracing)
- Provider and model
- Token usage
- Latency
- Success/failure status
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from app.ai.providers.base import AIResponse

# Configure the AI logger
logger = logging.getLogger("jarvis.ai")
logger.setLevel(logging.INFO)

# Create console handler if not exists
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class AILogger:
    """
    Structured logger for AI operations.
    
    Provides consistent logging format for all AI interactions,
    making it easy to trace requests and analyze performance.
    
    Usage:
        logger = AILogger()
        
        # Log a request
        logger.log_request(
            request_id="abc123",
            prompt="Turn on the TV",
            provider="gemini",
            model="gemini-1.5-flash"
        )
        
        # Log the response
        logger.log_response(
            request_id="abc123",
            response=ai_response,
        )
    """
    
    def __init__(self):
        """Initialize the AI logger."""
        self._logger = logger
    
    def log_request(
        self,
        request_id: str,
        prompt: str,
        provider: str,
        model: str,
        user_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an AI request.
        
        Args:
            request_id: Unique request identifier
            prompt: The prompt being sent (truncated for privacy)
            provider: AI provider name
            model: Model name
            user_id: Optional user ID
            metadata: Additional metadata
        """
        log_data = {
            "event": "ai_request",
            "request_id": request_id,
            "provider": provider,
            "model": model,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
            "user_id": str(user_id) if user_id else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        self._logger.info(f"AI Request: {json.dumps(log_data)}")
    
    def log_response(
        self,
        request_id: str,
        response: Optional[AIResponse] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # Alternative parameters when response object is not available
        provider: Optional[str] = None,
        model: Optional[str] = None,
        content: Optional[str] = None,
        tokens: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log an AI response.
        
        Can be called with an AIResponse object or with individual parameters.
        
        Args:
            request_id: Request identifier (for correlation)
            response: The AIResponse object (optional if using individual params)
            metadata: Additional metadata
            provider: Provider name (if no response object)
            model: Model name (if no response object)
            content: Response content (if no response object)
            tokens: Total tokens used (if no response object)
            latency_ms: Latency in ms (if no response object)
            success: Whether successful (if no response object)
            error: Error message (if no response object)
        """
        if response:
            # Use AIResponse object
            log_data = {
                "event": "ai_response",
                "request_id": request_id,
                "provider": response.provider.value if hasattr(response.provider, 'value') else str(response.provider),
                "model": response.model,
                "success": response.success,
                "latency_ms": round(response.latency_ms, 2),
                "tokens": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens,
                },
                "response_length": len(response.content),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            if not response.success:
                log_data["error"] = response.error
        else:
            # Use individual parameters
            log_data = {
                "event": "ai_response",
                "request_id": request_id,
                "provider": provider or "unknown",
                "model": model or "unknown",
                "success": success,
                "latency_ms": round(latency_ms, 2),
                "tokens": tokens,
                "response_length": len(content) if content else 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            if error:
                log_data["error"] = error
        
        if metadata:
            log_data["metadata"] = metadata
        
        level = logging.INFO if (response.success if response else success) else logging.WARNING
        self._logger.log(level, f"AI Response: {json.dumps(log_data)}")
    
    
    def log_intent(
        self,
        request_id: str,
        original_text: str,
        intent_type: str,
        device_name: Optional[str] = None,
        action: Optional[str] = None,
        confidence: float = 0.0,
        processing_time_ms: float = 0.0,
    ) -> None:
        """
        Log a parsed intent.
        
        Args:
            request_id: Request identifier
            original_text: Original user input
            intent_type: Extracted intent type
            device_name: Extracted device name
            action: Extracted action
            confidence: Confidence score
            processing_time_ms: Processing time
        """
        log_data = {
            "event": "intent_parsed",
            "request_id": request_id,
            "intent_type": intent_type,
            "device_name": device_name,
            "action": action,
            "confidence": round(confidence, 3),
            "processing_time_ms": round(processing_time_ms, 2),
            "original_text": original_text[:50] + "..." if len(original_text) > 50 else original_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self._logger.info(f"Intent Parsed: {json.dumps(log_data)}")
    
    def log_command_sent(
        self,
        request_id: str,
        device_id: UUID,
        device_name: str,
        action: str,
        command_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Log a command sent to a device.
        
        Args:
            request_id: Request identifier
            device_id: Target device UUID
            device_name: Device name
            action: Command action
            command_id: Generated command ID
            success: Whether send succeeded
            error: Error message if failed
        """
        log_data = {
            "event": "command_sent",
            "request_id": request_id,
            "device_id": str(device_id),
            "device_name": device_name,
            "action": action,
            "command_id": command_id,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if error:
            log_data["error"] = error
        
        level = logging.INFO if success else logging.WARNING
        self._logger.log(level, f"Command Sent: {json.dumps(log_data)}")
    
    def log_error(
        self,
        request_id: str,
        error: str,
        stage: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an error in the AI pipeline.
        
        Args:
            request_id: Request identifier
            error: Error message
            stage: Where the error occurred (parsing, routing, execution)
            metadata: Additional context
        """
        log_data = {
            "event": "ai_error",
            "request_id": request_id,
            "error": error,
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        self._logger.error(f"AI Error: {json.dumps(log_data)}")

    def log_event(
        self,
        request_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a generic event in the AI pipeline.
        
        Args:
            request_id: Request identifier
            event_type: Type of event (routing_decision, complex_task_routing, etc.)
            data: Event-specific data
        """
        log_data = {
            "event": event_type,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if data:
            log_data.update(data)
        
        self._logger.info(f"AI Event: {json.dumps(log_data)}")


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
ai_logger = AILogger()
