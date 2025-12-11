"""
AI Monitor - Unified logging and metrics tracking.

This module consolidates AILogger and AIMetrics into a single
interface following the DRY principle. One call tracks everything:
- Structured JSON logs
- In-memory metrics aggregation
- Cost estimation

Usage:
    from app.ai.monitoring import ai_monitor
    
    # Track a complete request-response cycle
    ai_monitor.track_request(
        request_id="abc123",
        prompt="Turn on the TV",
        provider="gemini",
        model="gemini-2.5-flash-lite",
        user_id=user.id,
    )
    
    ai_monitor.track_response(
        request_id="abc123",
        provider="gemini",
        model="gemini-2.5-flash-lite",
        content="Turning on TV...",
        prompt_tokens=50,
        completion_tokens=20,
        latency_ms=250.5,
        success=True,
    )
    
    # Get aggregated stats
    stats = ai_monitor.get_stats()
"""

import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.ai.providers.base import ProviderType, TokenUsage, AIResponse


# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
logger = logging.getLogger("jarvis.ai")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ---------------------------------------------------------------------------
# METRICS DATA CLASSES
# ---------------------------------------------------------------------------
@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    request_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    success: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    estimated_cost: float = 0.0


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    estimated_total_cost: float = 0.0
    requests_by_provider: Dict[str, int] = field(default_factory=dict)
    tokens_by_provider: Dict[str, int] = field(default_factory=dict)
    
    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    def to_dict(self) -> Dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{self.success_rate:.1f}%",
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "estimated_total_cost": f"${self.estimated_total_cost:.4f}",
            "requests_by_provider": self.requests_by_provider,
            "tokens_by_provider": self.tokens_by_provider,
        }


# ---------------------------------------------------------------------------
# UNIFIED AI MONITOR
# ---------------------------------------------------------------------------
class AIMonitor:
    """
    Unified AI monitoring: logging + metrics in one call.
    
    This class replaces separate AILogger and AIMetrics classes,
    following DRY principle. Each track_* method:
    1. Writes structured JSON log
    2. Updates in-memory metrics
    
    Cost Model (per 1M tokens):
    - Gemini Flash: ~$0.075 input, ~$0.30 output
    - GPT-4o: ~$5 input, ~$15 output
    - Claude: ~$3 input, ~$15 output
    """
    
    COST_PER_1M_TOKENS = {
        "gemini": {"input": 0.075, "output": 0.30},
        "openai": {"input": 5.0, "output": 15.0},
        "anthropic": {"input": 3.0, "output": 15.0},
    }
    
    def __init__(self, max_history: int = 1000):
        self._logger = logger
        self._history: List[RequestMetrics] = []
        self._max_history = max_history
        self._lock = Lock()
        self._aggregated = AggregatedMetrics()
    
    # -----------------------------------------------------------------------
    # MAIN TRACKING METHODS
    # -----------------------------------------------------------------------
    
    def track_request(
        self,
        request_id: str,
        prompt: str,
        provider: str,
        model: str,
        user_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track the start of an AI request.
        
        Call this when sending a request to an AI provider.
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
    
    def track_response(
        self,
        request_id: str,
        provider: str,
        model: str,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track an AI response (logs + metrics in one call).
        
        Call this after receiving a response from an AI provider.
        """
        total_tokens = prompt_tokens + completion_tokens
        
        # Calculate cost
        cost = self._estimate_cost(provider, prompt_tokens, completion_tokens)
        
        # Create metrics record
        metrics = RequestMetrics(
            request_id=request_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            success=success,
            estimated_cost=cost,
        )
        
        # Update aggregated metrics
        with self._lock:
            self._history.append(metrics)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            self._update_aggregated(metrics)
        
        # Log the response
        log_data = {
            "event": "ai_response",
            "request_id": request_id,
            "provider": provider,
            "model": model,
            "success": success,
            "latency_ms": round(latency_ms, 2),
            "tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": total_tokens,
            },
            "estimated_cost": f"${cost:.6f}",
            "response_length": len(content) if content else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if error:
            log_data["error"] = error
        
        if metadata:
            log_data["metadata"] = metadata
        
        level = logging.INFO if success else logging.WARNING
        self._logger.log(level, f"AI Response: {json.dumps(log_data)}")
    
    def track_response_from_ai_response(
        self,
        request_id: str,
        response: AIResponse,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track response using an AIResponse object directly.
        
        Convenience method when you have the full AIResponse.
        """
        provider = response.provider.value if hasattr(response.provider, 'value') else str(response.provider)
        
        self.track_response(
            request_id=request_id,
            provider=provider,
            model=response.model,
            content=response.content,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            latency_ms=response.latency_ms,
            success=response.success,
            error=response.error,
            metadata=metadata,
        )
    
    def track_intent(
        self,
        request_id: str,
        original_text: str,
        intent_type: str,
        device_name: Optional[str] = None,
        action: Optional[str] = None,
        confidence: float = 0.0,
        processing_time_ms: float = 0.0,
    ) -> None:
        """Track a parsed intent."""
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
    
    def track_routing(
        self,
        request_id: str,
        complexity: str,
        target_provider: str,
        confidence: float,
        reasoning: str,
        is_device_command: bool = False,
    ) -> None:
        """Track a routing decision."""
        log_data = {
            "event": "routing_decision",
            "request_id": request_id,
            "complexity": complexity,
            "target_provider": target_provider,
            "confidence": round(confidence, 3),
            "reasoning": reasoning[:100] + "..." if len(reasoning) > 100 else reasoning,
            "is_device_command": is_device_command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self._logger.info(f"Routing: {json.dumps(log_data)}")
    
    def track_command(
        self,
        request_id: str,
        device_id: UUID,
        device_name: str,
        action: str,
        command_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Track a command sent to a device."""
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
    
    def track_error(
        self,
        request_id: str,
        error: str,
        stage: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track an error in the AI pipeline."""
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
    
    def track_event(
        self,
        request_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a generic event."""
        log_data = {
            "event": event_type,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if data:
            log_data.update(data)
        
        self._logger.info(f"AI Event: {json.dumps(log_data)}")
    
    # -----------------------------------------------------------------------
    # METRICS METHODS
    # -----------------------------------------------------------------------
    
    def get_stats(self) -> AggregatedMetrics:
        """Get current aggregated statistics."""
        with self._lock:
            return self._aggregated
    
    def get_recent_requests(self, limit: int = 10) -> List[RequestMetrics]:
        """Get recent requests."""
        with self._lock:
            return list(reversed(self._history[-limit:]))
    
    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._history = []
            self._aggregated = AggregatedMetrics()
    
    # -----------------------------------------------------------------------
    # PRIVATE METHODS
    # -----------------------------------------------------------------------
    
    def _estimate_cost(self, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD."""
        costs = self.COST_PER_1M_TOKENS.get(provider.lower(), {"input": 0, "output": 0})
        input_cost = (prompt_tokens / 1_000_000) * costs["input"]
        output_cost = (completion_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost
    
    def _update_aggregated(self, metrics: RequestMetrics) -> None:
        """Update aggregated metrics with a new request."""
        self._aggregated.total_requests += 1
        
        if metrics.success:
            self._aggregated.successful_requests += 1
        else:
            self._aggregated.failed_requests += 1
        
        self._aggregated.total_tokens += metrics.total_tokens
        self._aggregated.total_prompt_tokens += metrics.prompt_tokens
        self._aggregated.total_completion_tokens += metrics.completion_tokens
        self._aggregated.total_latency_ms += metrics.latency_ms
        self._aggregated.estimated_total_cost += metrics.estimated_cost
        
        # Track by provider
        provider = metrics.provider
        self._aggregated.requests_by_provider[provider] = \
            self._aggregated.requests_by_provider.get(provider, 0) + 1
        self._aggregated.tokens_by_provider[provider] = \
            self._aggregated.tokens_by_provider.get(provider, 0) + metrics.total_tokens


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
ai_monitor = AIMonitor()
