"""
AI Router Module - The Orchestrator.

This module contains the AI Router that acts as the brain's traffic controller.
It analyzes incoming requests and routes them to the appropriate AI model.
"""

from app.ai.router.orchestrator import AIRouter, ai_router, TaskComplexity

__all__ = [
    "AIRouter",
    "ai_router",
    "TaskComplexity",
]
