"""
AI Metrics - Usage tracking and cost estimation.

This module tracks AI usage metrics for:
- Cost estimation (tokens × price)
- Rate limit awareness
- Performance analysis
- Usage patterns

Cost Model (Approximate):
========================
- Gemini Flash: ~$0.075 / 1M input, ~$0.30 / 1M output
- GPT-4o: ~$5 / 1M input, ~$15 / 1M output  
- Claude Sonnet: ~$3 / 1M input, ~$15 / 1M output

Most requests are handled by Gemini Flash (cheap!), so average
cost per request should be very low (<$0.001).
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from threading import Lock

from app.ai.providers.base import ProviderType, TokenUsage


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    request_id: str
    provider: ProviderType
    model: str
    tokens: TokenUsage
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
        """Average latency per request."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
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


class AIMetrics:
    """
    Tracks and aggregates AI usage metrics.
    
    This class maintains in-memory metrics for monitoring.
    For production, you'd want to persist these to a database
    or send to a metrics service (Prometheus, DataDog, etc.).
    
    Usage:
        metrics = AIMetrics()
        
        # Record a request
        metrics.record_request(
            request_id="abc123",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            tokens=TokenUsage(100, 50),
            latency_ms=250.5,
            success=True,
        )
        
        # Get aggregated stats
        stats = metrics.get_stats()
        print(f"Total requests: {stats.total_requests}")
    """
    
    # Approximate costs per 1M tokens (as of late 2024)
    COST_PER_1M_TOKENS = {
        ProviderType.GEMINI: {"input": 0.075, "output": 0.30},
        ProviderType.OPENAI: {"input": 5.0, "output": 15.0},
        ProviderType.ANTHROPIC: {"input": 3.0, "output": 15.0},
    }
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics tracker.
        
        Args:
            max_history: Maximum number of requests to keep in memory
        """
        self._history: List[RequestMetrics] = []
        self._max_history = max_history
        self._lock = Lock()
        self._aggregated = AggregatedMetrics()
    
    def record_request(
        self,
        request_id: str,
        provider: ProviderType,
        model: str,
        tokens: TokenUsage,
        latency_ms: float,
        success: bool,
    ) -> RequestMetrics:
        """
        Record metrics for a completed request.
        
        Args:
            request_id: Unique request identifier
            provider: AI provider used
            model: Model name
            tokens: Token usage
            latency_ms: Request latency
            success: Whether request succeeded
            
        Returns:
            The recorded metrics
        """
        # Calculate estimated cost
        cost = self._estimate_cost(provider, tokens)
        
        metrics = RequestMetrics(
            request_id=request_id,
            provider=provider,
            model=model,
            tokens=tokens,
            latency_ms=latency_ms,
            success=success,
            estimated_cost=cost,
        )
        
        with self._lock:
            # Add to history
            self._history.append(metrics)
            
            # Trim history if needed
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            
            # Update aggregated metrics
            self._update_aggregated(metrics)
        
        return metrics
    
    def _estimate_cost(self, provider: ProviderType, tokens: TokenUsage) -> float:
        """Estimate cost in USD."""
        costs = self.COST_PER_1M_TOKENS.get(provider, {"input": 0, "output": 0})
        input_cost = (tokens.prompt_tokens / 1_000_000) * costs["input"]
        output_cost = (tokens.completion_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost
    
    def _update_aggregated(self, metrics: RequestMetrics) -> None:
        """Update aggregated metrics with a new request."""
        self._aggregated.total_requests += 1
        
        if metrics.success:
            self._aggregated.successful_requests += 1
        else:
            self._aggregated.failed_requests += 1
        
        self._aggregated.total_tokens += metrics.tokens.total_tokens
        self._aggregated.total_prompt_tokens += metrics.tokens.prompt_tokens
        self._aggregated.total_completion_tokens += metrics.tokens.completion_tokens
        self._aggregated.total_latency_ms += metrics.latency_ms
        self._aggregated.estimated_total_cost += metrics.estimated_cost
        
        # Track by provider
        provider_name = metrics.provider.value if hasattr(metrics.provider, 'value') else str(metrics.provider)
        self._aggregated.requests_by_provider[provider_name] = \
            self._aggregated.requests_by_provider.get(provider_name, 0) + 1
        self._aggregated.tokens_by_provider[provider_name] = \
            self._aggregated.tokens_by_provider.get(provider_name, 0) + metrics.tokens.total_tokens
    
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


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
ai_metrics = AIMetrics()
