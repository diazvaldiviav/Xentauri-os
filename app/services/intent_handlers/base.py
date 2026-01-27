"""
Base Intent Handler - Abstract interface for all intent handlers.

This module defines the contract that all intent handlers must follow.
It ensures consistent behavior regardless of which handler processes
the intent.

Design Pattern: Strategy Pattern
================================
The base class defines the interface, and each handler implements it.
This allows IntentService to route to handlers without code changes.

Example:
    handler = ConversationHandler()
    if handler.can_handle(intent, context):
        result = await handler.handle(intent, context)

Reference:
    This follows the same ABC pattern as app/ai/providers/base.py
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger("jarvis.services.intent_handlers")


@dataclass
class HandlerContext:
    """
    Context shared between all handlers.

    This dataclass encapsulates all the context needed to process an intent.
    It provides a clean separation between the orchestrator (IntentService)
    and the handlers.

    Attributes:
        user_id: The ID of the user making the request
        request_id: Unique identifier for this request (for logging/tracing)
        devices: List of user's devices (pre-loaded)
        db: Database session for queries
        start_time: Request start time for latency tracking
        require_feedback: If True, return HTML for human validation
        resolved_references: Anaphoric references resolved from context
        conversation_history: Recent conversation turns for context
        pending_operation: Any pending operation awaiting confirmation

    Usage:
        context = HandlerContext(
            user_id=user.id,
            request_id=str(uuid4()),
            devices=user_devices,
            db=db_session,
            start_time=time.time(),
        )

        result = await handler.handle(intent, context)
    """

    # Required fields
    user_id: UUID
    request_id: str
    devices: List[Any]  # List[Device] - using Any to avoid circular import
    db: Any  # Session - using Any to avoid circular import
    start_time: float

    # Behavioral flags
    require_feedback: bool = False

    # Original user text (needed for language detection in system queries)
    original_text: str = ""

    # Optional device override (for API-specified device)
    forced_device_id: Optional[UUID] = None

    # Context from build_request_context()
    resolved_references: Dict[str, Any] = field(default_factory=dict)
    conversation_history: Optional[str] = None
    pending_operation: Optional[Dict[str, Any]] = None

    # Optional service overrides (for testing)
    _service_overrides: Dict[str, Any] = field(default_factory=dict)

    def get_service(self, name: str, default_factory: Any = None) -> Any:
        """
        Get a service with optional override for testing.

        This method allows handlers to be tested in isolation by
        injecting mock services.

        Args:
            name: Service identifier (e.g., 'calendar_search')
            default_factory: Callable that returns the default service

        Returns:
            The service instance (mock or real)

        Raises:
            ValueError: If service not found and no default provided
        """
        if name in self._service_overrides:
            return self._service_overrides[name]
        if default_factory is not None:
            return default_factory()
        raise ValueError(f"Service '{name}' not found and no default provided")


class IntentHandler(ABC):
    """
    Abstract base class for intent handlers.

    All intent handlers (Device, Calendar, Conversation, etc.) must implement
    this interface. This ensures consistent behavior and makes handlers
    interchangeable via the Strategy pattern.

    Responsibilities:
    - Determine if it can handle a given intent (can_handle)
    - Process the intent and return a result (handle)
    - Provide metadata about supported intents

    NOT Responsible For:
    - Parsing intents from text (intent_parser's job)
    - Routing between handlers (IntentService's job)
    - HTTP request/response handling (router's job)

    Usage:
        class ConversationHandler(IntentHandler):
            @property
            def handler_name(self) -> str:
                return "conversation"

            @property
            def supported_intent_types(self) -> List[str]:
                return ["conversation", "clarification"]

            def can_handle(self, intent, context) -> bool:
                return intent.intent_type in self.supported_intent_types

            async def handle(self, intent, context) -> IntentResult:
                # Process conversational intent
                return IntentResult(success=True, ...)
    """

    @property
    @abstractmethod
    def handler_name(self) -> str:
        """
        Unique identifier for this handler.

        Used for logging, monitoring, and debugging.
        Should be a lowercase string with underscores (e.g., "calendar_handler").

        Returns:
            Handler name string
        """
        pass

    @property
    @abstractmethod
    def supported_intent_types(self) -> List[str]:
        """
        List of IntentType values this handler can process.

        These should match the values from IntentType enum
        (e.g., ["device_command", "device_query"]).

        The HandlerRegistry uses this to route intents to handlers.

        Returns:
            List of intent type strings
        """
        pass

    @abstractmethod
    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Determine if this handler can process the given intent.

        This method allows for fine-grained control beyond just intent type.
        For example, a handler might check specific parameters or context.

        Args:
            intent: The parsed intent object
            context: Handler context with user, devices, etc.

        Returns:
            True if this handler can process the intent, False otherwise
        """
        pass

    @abstractmethod
    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> Any:  # Returns IntentResult - using Any to avoid circular import
        """
        Process the intent and return a result.

        This is the main entry point for intent processing. The handler
        should perform all necessary operations and return an IntentResult.

        Args:
            intent: The parsed intent object
            context: Handler context with user, devices, etc.

        Returns:
            IntentResult with processing outcome

        Note:
            This method should NOT raise exceptions.
            Errors should be captured in IntentResult.
        """
        pass

    def _log_entry(self, intent: Any, context: HandlerContext) -> None:
        """
        Log handler entry for monitoring.

        Utility method for consistent logging across handlers.
        """
        logger.info(
            f"[{context.request_id}] {self.handler_name}.handle() called",
            extra={
                "handler": self.handler_name,
                "user_id": str(context.user_id),
                "require_feedback": context.require_feedback,
            },
        )

    def _log_exit(
        self,
        context: HandlerContext,
        success: bool,
        processing_time_ms: float,
    ) -> None:
        """
        Log handler exit for monitoring.

        Utility method for consistent logging across handlers.
        """
        logger.info(
            f"[{context.request_id}] {self.handler_name}.handle() completed",
            extra={
                "handler": self.handler_name,
                "success": success,
                "processing_time_ms": processing_time_ms,
            },
        )
