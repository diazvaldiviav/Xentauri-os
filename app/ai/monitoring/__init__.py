"""
Monitoring Module - Unified logging and metrics tracking for AI operations.

This module provides observability for the AI system:
- Request/response logging
- Token usage tracking
- Latency metrics
- Error tracking
- Cost estimation

Why Monitoring Matters:
======================
1. Cost Control: AI APIs charge per token - track spending
2. Performance: Identify slow requests and bottlenecks
3. Debugging: Trace issues through the system
4. Analytics: Understand usage patterns

Usage:
======
    from app.ai.monitoring import ai_monitor
    
    # Track request + response in unified way
    ai_monitor.track_request(request_id, prompt, provider, model)
    ai_monitor.track_response(request_id, provider, model, content, tokens, latency)
    
    # Get stats
    stats = ai_monitor.get_stats()
"""

from app.ai.monitoring.monitor import AIMonitor, ai_monitor

# Legacy imports for backward compatibility (deprecated)
from app.ai.monitoring.logger import AILogger, ai_logger
from app.ai.monitoring.metrics import AIMetrics, ai_metrics

__all__ = [
    # New unified interface (recommended)
    "AIMonitor",
    "ai_monitor",
    # Legacy (deprecated - use ai_monitor instead)
    "AILogger",
    "ai_logger",
    "AIMetrics",
    "ai_metrics",
]
