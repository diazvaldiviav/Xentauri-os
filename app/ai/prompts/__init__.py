"""
Prompts Module - Centralized prompt templates for AI interactions.

This module contains all prompt templates used by the AI system.
Keeping prompts centralized makes them:
- Easy to update and iterate
- Consistent across the application
- Testable and version-controlled
"""

from app.ai.prompts.router_prompts import (
    ROUTING_SYSTEM_PROMPT,
    ROUTING_ANALYSIS_PROMPT,
)
from app.ai.prompts.intent_prompts import (
    INTENT_SYSTEM_PROMPT,
    INTENT_EXTRACTION_PROMPT,
    DEVICE_COMMAND_PROMPT,
)

__all__ = [
    "ROUTING_SYSTEM_PROMPT",
    "ROUTING_ANALYSIS_PROMPT",
    "INTENT_SYSTEM_PROMPT",
    "INTENT_EXTRACTION_PROMPT",
    "DEVICE_COMMAND_PROMPT",
]
