"""
Intent Handlers Package - Strategy pattern for intent processing.

This package contains the base interface and concrete handlers for
processing different types of intents. Each handler is responsible
for a specific category of intents (device, calendar, conversation, etc.).

Usage:
    from app.services.intent_handlers import IntentHandler, HandlerContext

    class MyHandler(IntentHandler):
        @property
        def handler_name(self) -> str:
            return "my_handler"

        @property
        def supported_intent_types(self) -> List[str]:
            return ["my_intent_type"]

        def can_handle(self, intent, context) -> bool:
            return True

        async def handle(self, intent, context) -> IntentResult:
            # Process intent
            pass

Design Pattern: Strategy Pattern
================================
The IntentHandler ABC defines the contract. Concrete handlers implement
the strategy for processing specific intent types. IntentService acts
as the context that delegates to the appropriate handler.

Reference: app/ai/providers/base.py (AIProvider ABC)
"""

from app.services.intent_handlers.base import (
    IntentHandler,
    HandlerContext,
)
from app.services.intent_handlers.device_handler import DeviceHandler
from app.services.intent_handlers.system_handler import SystemHandler
from app.services.intent_handlers.conversation_handler import ConversationHandler
from app.services.intent_handlers.calendar_handler import CalendarHandler
from app.services.intent_handlers.display_content_handler import DisplayContentHandler
from app.services.intent_handlers.document_handler import DocumentHandler

__all__ = [
    "IntentHandler",
    "HandlerContext",
    "DeviceHandler",
    "SystemHandler",
    "ConversationHandler",
    "CalendarHandler",
    "DisplayContentHandler",
    "DocumentHandler",
]
