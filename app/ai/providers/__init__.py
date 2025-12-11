"""
AI Providers Module - Unified clients for multiple LLM providers.

This module provides consistent interfaces to different AI providers:
- Google Gemini (gemini-flash for orchestration)
- OpenAI (GPT-4o for complex tasks)
- Anthropic (Claude for deep reasoning)

Each provider has the same interface, making them interchangeable:
    response = await provider.generate(prompt, **kwargs)

Why separate providers?
======================
1. Cost optimization: Use cheaper models for simple tasks
2. Specialization: Each model excels at different things
3. Reliability: Fallback to other providers if one fails
4. A/B testing: Compare model performance easily
"""

from app.ai.providers.base import AIProvider, AIResponse
from app.ai.providers.gemini import GeminiProvider, gemini_provider
from app.ai.providers.openai_provider import OpenAIProvider, openai_provider
from app.ai.providers.anthropic_provider import AnthropicProvider, anthropic_provider

__all__ = [
    "AIProvider",
    "AIResponse",
    "GeminiProvider",
    "gemini_provider",
    "OpenAIProvider", 
    "openai_provider",
    "AnthropicProvider",
    "anthropic_provider",
]
