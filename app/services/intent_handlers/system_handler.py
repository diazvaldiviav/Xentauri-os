"""
System Handler - Handles system-level queries.

This handler is responsible for:
- System queries (list_devices, help, system info)

Sprint US-2.3: Extracted from DeviceHandler
Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import time
from typing import Any, List

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import SystemQuery


logger = logging.getLogger("jarvis.services.intent_handlers.system")


class SystemHandler(IntentHandler):
    """
    Handler for system-level intents.

    Handles:
    - SystemQuery: List devices, help, and system info queries
    """

    @property
    def handler_name(self) -> str:
        """Return the handler name for logging."""
        return "system"

    @property
    def supported_intent_types(self) -> List[str]:
        """Return list of supported intent types."""
        return ["system_query"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The parsed intent object
            context: Handler context

        Returns:
            True if intent is SystemQuery
        """
        return isinstance(intent, SystemQuery)

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Process the system query intent and return a result.

        Args:
            intent: The parsed intent object (SystemQuery)
            context: Handler context with user, devices, etc.

        Returns:
            IntentResult with processing outcome
        """
        self._log_entry(intent, context)

        try:
            if isinstance(intent, SystemQuery):
                result = await self._handle_system_query(intent, context)
            else:
                processing_time = (time.time() - context.start_time) * 1000
                result = IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Unsupported intent type for SystemHandler",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            self._log_exit(context, success=result.success, processing_time_ms=result.processing_time_ms)
            return result

        except Exception as e:
            processing_time = (time.time() - context.start_time) * 1000
            logger.error(f"[{context.request_id}] SystemHandler error: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error processing system query: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    # -----------------------------------------------------------------------
    # SYSTEM QUERY HANDLER
    # -----------------------------------------------------------------------

    async def _handle_system_query(
        self,
        intent: SystemQuery,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle system queries with multilingual, context-aware responses.

        Sprint 4.1: Uses Gemini to generate natural responses in the user's language.

        Args:
            intent: SystemQuery intent
            context: Handler context (uses context.original_text for language detection)

        Returns:
            IntentResult with system query response
        """
        from app.ai.providers.gemini import gemini_provider
        from app.ai.context import build_unified_context
        from app.db.session import SessionLocal

        action = self._get_action_value(intent.action) or "help"

        # Build context
        db = SessionLocal()
        try:
            unified_context = await build_unified_context(user_id=context.user_id, db=db)
        finally:
            db.close()

        # System prompt with multilingual rule
        system_prompt = f"""You are Jarvis, a helpful assistant.

CRITICAL: ALWAYS respond in the SAME LANGUAGE the user is speaking.
- Spanish input -> Spanish output
- English input -> English output
- French input -> French output

USER SETUP:
- Name: {unified_context.user_name}
- Devices: {unified_context.device_count} total, {len(unified_context.online_devices)} online
- Calendar: {"Connected" if unified_context.has_google_calendar else "Not connected"}
- Docs: {"Connected" if unified_context.has_google_docs else "Not connected"}

Respond naturally and concisely (1-3 sentences)."""

        # Build action-specific prompts
        if action == "list_devices":
            if not context.devices:
                user_prompt = f'User asked to list devices: "{context.original_text}"\n\nThey have none. Explain kindly and suggest adding one. Respond in their language.'
            else:
                device_list = "\n".join([f"- {d.name} ({'online' if d.is_online else 'offline'})" for d in context.devices])
                user_prompt = f'''User asked to list devices: "{context.original_text}"

Their devices:
{device_list}

Present with emojis (green circle online, red circle offline) in the SAME language as the user's request.'''

        elif action == "help":
            device_examples = [d.device_name for d in unified_context.online_devices[:2]] if unified_context.online_devices else ["your TV", "your screen"]
            user_prompt = f'''User asked for help: "{context.original_text}"

Their setup:
- {unified_context.device_count} device(s): {", ".join(device_examples)}
- Calendar: {"available" if unified_context.has_google_calendar else "not connected"}
- Docs: {"available" if unified_context.has_google_docs else "not connected"}

Provide 3-5 example commands customized to their setup.
Respond in the SAME language as their request.'''

        else:
            user_prompt = f'User said: "{context.original_text}"\n\nRespond helpfully in their language.'

        # Generate response
        response = await gemini_provider.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=400,
        )

        processing_time = (time.time() - context.start_time) * 1000
        message = response.content.strip() if response.success else "How can I help with your devices?"

        return IntentResult(
            success=True,
            intent_type=IntentResultType.SYSTEM_QUERY,
            confidence=intent.confidence,
            action=action,
            message=message,
            processing_time_ms=processing_time,
            request_id=context.request_id,
        )

    # -----------------------------------------------------------------------
    # STATIC HELPER METHODS
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_action_value(action: Any) -> str | None:
        """
        Extract action value from enum or string.

        Args:
            action: Action enum or string

        Returns:
            String value of the action, or None if action is None
        """
        if action is None:
            return None
        if hasattr(action, 'value'):
            return action.value
        return str(action)
