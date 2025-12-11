"""
Intent Module - Natural Language Understanding for Jarvis.

This module handles the extraction of structured intents from
natural language commands. It's the bridge between what users say
and what the system can execute.

Example Flow:
============
User says: "Show the calendar on living room TV"

IntentParser extracts:
{
    "intent_type": "device_command",
    "device_name": "living room TV",
    "action": "set_input",
    "parameters": {"app": "calendar"}
}

DeviceMapper resolves:
"living room TV" → Device(id=uuid, name="Living Room TV")

Result: Structured command ready for execution
"""

from app.ai.intent.schemas import (
    Intent,
    IntentType,
    ParsedCommand,
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
    ConversationIntent,
)
from app.ai.intent.parser import IntentParser, intent_parser
from app.ai.intent.device_mapper import DeviceMapper, device_mapper

__all__ = [
    "Intent",
    "IntentType",
    "ParsedCommand",
    "DeviceCommand",
    "DeviceQuery",
    "SystemQuery",
    "ConversationIntent",
    "IntentParser",
    "intent_parser",
    "DeviceMapper",
    "device_mapper",
]
