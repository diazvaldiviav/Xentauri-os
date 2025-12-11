"""
AI Module - The "Brain" of Jarvis

This module handles all AI/LLM integration for natural language understanding
and intelligent command routing. It's designed to be clean, modular, and 
well-documented as this is the core intelligence of the system.

Architecture Overview:
=====================

┌─────────────────────────────────────────────────────────────────────────┐
│                        AI Router (Orchestrator)                          │
│                         [Gemini Flash - Fast]                            │
│                                                                          │
│    Analyzes: Is the task simple? Direct command? Can I handle it?        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  Simple Task  │     │  Complex Task │     │   Critical    │
│   (Direct)    │     │   (Coding)    │     │  (Reasoning)  │
│               │     │               │     │               │
│ Gemini Flash  │     │   GPT-4o      │     │ Claude Opus   │
│ handles it    │     │   handles it  │     │ handles it    │
└───────────────┘     └───────────────┘     └───────────────┘

Module Structure:
================
- providers/: AI provider clients (Gemini, OpenAI, Anthropic)
- router/: The AI orchestrator that routes requests to appropriate models
- intent/: Intent parsing and structured output extraction
- prompts/: Prompt templates for consistent LLM interactions
- monitoring/: Logging, metrics, and usage tracking

Flow:
=====
1. User: "Show the calendar on living room TV"
2. Intent Parser (Gemini Flash): Extract intent and entities
3. Device Mapper: Resolve "living room TV" → device_id
4. AI Router: Determine if simple or needs escalation
5. Command Builder: Create structured command
6. Send to device via WebSocket
"""

# Version of the AI module
__version__ = "0.1.0"

# Re-export main components for easy imports
from app.ai.router.orchestrator import AIRouter, ai_router
from app.ai.intent.parser import IntentParser, intent_parser
from app.ai.intent.schemas import Intent, IntentType, ParsedCommand

__all__ = [
    "AIRouter",
    "ai_router",
    "IntentParser", 
    "intent_parser",
    "Intent",
    "IntentType",
    "ParsedCommand",
]
