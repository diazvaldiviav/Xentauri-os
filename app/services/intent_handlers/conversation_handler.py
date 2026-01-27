"""
Conversation Handler - Handles conversational intents.

This handler is responsible for:
- General conversation (greetings, thanks, questions)
- Context-aware AI responses
- Conversation history management
- Content generation and memory storage

Sprint US-2.2: Extracted from IntentService
Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import re
import time
from typing import Any, List, Optional

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import ConversationIntent


logger = logging.getLogger("jarvis.services.intent_handlers.conversation")


class ConversationHandler(IntentHandler):
    """
    Handler for conversational intents.

    Handles:
    - ConversationIntent: Greetings, thanks, questions, general chat

    Features:
    - Maintains conversation history across turns
    - Handles follow-up confirmations like "si", "hazlo", "do it"
    - Uses web search for real-time information
    - Responds in the user's language
    """

    @property
    def handler_name(self) -> str:
        """Return the handler name for logging."""
        return "conversation"

    @property
    def supported_intent_types(self) -> List[str]:
        """Return list of supported intent types."""
        return ["conversation"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The parsed intent object
            context: Handler context

        Returns:
            True if intent is ConversationIntent
        """
        return isinstance(intent, ConversationIntent)

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Process the conversational intent and return a result.

        Args:
            intent: The parsed intent object (ConversationIntent)
            context: Handler context with user, original_text, etc.

        Returns:
            IntentResult with processing outcome
        """
        self._log_entry(intent, context)

        try:
            result = await self._handle_conversation(intent, context)
            self._log_exit(context, success=result.success, processing_time_ms=result.processing_time_ms)
            return result

        except Exception as e:
            processing_time = (time.time() - context.start_time) * 1000
            logger.error(f"[{context.request_id}] ConversationHandler error: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error processing conversation: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    # -----------------------------------------------------------------------
    # CONVERSATION HANDLER
    # -----------------------------------------------------------------------

    async def _handle_conversation(
        self,
        intent: ConversationIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle conversational intents with context-aware, multilingual responses.

        Sprint 4.1: Uses Gemini with context awareness, conversation history,
        and Google Search grounding for intelligent, personalized answers.

        Features:
        - Maintains conversation history across turns
        - Handles follow-up confirmations like "si", "hazlo", "do it"
        - Uses web search for real-time information
        - Responds in the user's language

        Args:
            intent: ConversationIntent with action and confidence
            context: Handler context with user_id, original_text, etc.

        Returns:
            IntentResult with conversation response
        """
        from app.ai.providers.gemini import gemini_provider
        from app.ai.prompts.assistant_prompts import (
            build_assistant_system_prompt,
            build_assistant_prompt,
        )
        from app.ai.context import build_unified_context
        from app.db.session import SessionLocal
        from app.services.conversation_context_service import conversation_context_service

        request_id = context.request_id
        user_id = context.user_id
        original_text = context.original_text
        start_time = context.start_time

        # Build context
        db = SessionLocal()
        try:
            unified_context = await build_unified_context(user_id=user_id, db=db)
        finally:
            db.close()

        # Sprint 4.1: Get conversation history for context
        conversation_history = conversation_context_service.get_conversation_summary(str(user_id))
        pending_content = conversation_context_service.get_pending_content_request(str(user_id))

        # Build prompts with context and conversation history
        system_prompt = build_assistant_system_prompt(unified_context)

        # Check if this is a follow-up/confirmation to previous request
        follow_up_keywords = [
            'si', 'sí', 'yes', 'ok', 'okay', 'hazlo', 'do it', 'adelante',
            'proceed', 'confirma', 'confirmo', 'confirm', 'solo', 'just',
            'redactalo', 'redáctalo', 'escribelo', 'escríbelo', 'write it',
            'generate it', 'crealo', 'créalo', 'create it', 'muéstramelo',
            'muestramelo', 'show it', 'go ahead', 'sure', 'claro',
        ]

        is_follow_up = (
            pending_content and
            any(kw in original_text.lower() for kw in follow_up_keywords)
        )

        # Build user prompt with conversation context
        if is_follow_up and pending_content:
            # User is confirming a previous content generation request
            logger.info(
                f"[{request_id}] Follow-up detected for pending content: "
                f"{pending_content['type']} - {pending_content['request'][:50]}..."
            )
            user_prompt = f"""The user previously asked for: {pending_content['request']}

Now they're confirming with: "{original_text}"

Please fulfill their original request and generate the content they asked for.
Respond in the same language they used originally.
"""
            # Clear the pending content after fulfilling
            conversation_context_service.clear_pending_content(str(user_id))
        elif conversation_history:
            # Include conversation history for context
            # Sprint 4.2.4: Clearer prompt to prevent model confusion
            user_prompt = f"""=== PREVIOUS CONVERSATION (for context only) ===
{conversation_history}
=== END OF HISTORY ===

>>> CURRENT USER MESSAGE (respond to THIS): <<<
"{original_text}"

IMPORTANT INSTRUCTIONS:
1. Answer ONLY the current message above, NOT previous questions from the history
2. Use the conversation history ONLY as background context
3. If the user is correcting you or changing topic, acknowledge it and respond to their NEW question
4. Respond in the same language as the current message"""
        else:
            user_prompt = build_assistant_prompt(original_text, unified_context)

        # Determine if web search is needed
        # Sprint 4.5.0: Expanded keywords for Spanish queries and general updates
        search_keywords = [
            # Weather
            'weather', 'temperature', 'forecast', 'clima', 'tiempo', 'pronóstico',
            # Time
            'time', 'clock', 'timezone', 'hora',
            # News/Updates (Sprint 4.5.0: Added Spanish equivalents)
            'news', 'latest', 'today', 'noticias',
            'últimas', 'actualizaciones', 'updates', 'novedades',
            'recent', 'reciente', 'cambios', 'changes',
            # Sports
            'score', 'game', 'match', 'partido',
            # Finance
            'stock', 'price', 'precio',
            # Current/Now
            'current', 'now', 'hoy', 'ahora', 'actual',
        ]

        use_search = any(keyword in original_text.lower() for keyword in search_keywords)

        # Detect if this is a content generation request to save for follow-up
        content_gen_keywords = [
            'template', 'plantilla', 'nota', 'notes', 'checklist',
            'lista', 'resumen', 'summary', 'tutorial', 'tips',
            'redacta', 'crea', 'create', 'hazme', 'dame', 'give me',
            'necesito', 'i need', 'generate', 'genera',
        ]
        is_content_request = any(kw in original_text.lower() for kw in content_gen_keywords)

        # Generate intelligent response
        if use_search:
            response = await gemini_provider.generate_with_grounding(
                prompt=user_prompt,
                system_prompt=system_prompt,
                use_search=True,
                temperature=0.8,
                max_tokens=1024,  # Increased for content generation
            )
        else:
            response = await gemini_provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=1024,  # Increased for content generation
            )

        processing_time = (time.time() - start_time) * 1000

        if not response.success:
            # Fallback: Generate error message in user's language WITHOUT grounding
            try:
                error_response = await gemini_provider.generate(
                    prompt=f"User said: '{original_text}'\n\nRespond with a brief, friendly apology that you're having trouble right now. Ask them to rephrase or try again.",
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=100,
                )
                if error_response.success:
                    message = error_response.content.strip()
                else:
                    message = "Lo siento, estoy teniendo problemas procesando eso. ¿Podrías reformular? / I apologize, I'm having trouble processing that. Could you rephrase?"
            except Exception as e:
                logger.error(f"Error generating fallback message: {e}")
                message = "Lo siento, estoy teniendo problemas procesando eso. ¿Podrías reformular? / I apologize, I'm having trouble processing that. Could you rephrase?"
        else:
            message = response.content.strip()

        # Sprint 4.2: Detect and store generated content for memory-aware display
        content_type = self._detect_content_type(original_text, message)
        if content_type:
            title = self._extract_content_title(original_text, message)
            conversation_context_service.set_generated_content(
                user_id=str(user_id),
                content=message,
                content_type=content_type,
                title=title,
            )
            logger.info(
                f"[{request_id}] Stored generated content: type={content_type}, title={title}"
            )

        # Sprint 4.1: Save conversation turn for future context
        conversation_context_service.add_conversation_turn(
            user_id=str(user_id),
            user_message=original_text,
            assistant_response=message,
            intent_type="conversation",
        )

        # If this was a content generation request, save it for potential follow-up
        # (only if the response seems like it's asking for confirmation)
        if is_content_request and not is_follow_up:
            # Detect if AI is asking for clarification/confirmation
            clarification_indicators = [
                '?', '¿', 'could you', 'podrías', 'would you like',
                'te gustaría', 'quieres que', 'do you want', 'should i',
                'more details', 'más detalles', 'clarify', 'especifica',
            ]
            if any(ind in message.lower() for ind in clarification_indicators):
                # AI is asking for more info, save the request for follow-up
                conversation_context_service.set_pending_content_request(
                    user_id=str(user_id),
                    content_request=original_text,
                    content_type="content_generation",
                )

        action = self._get_action_value(intent.action) or "general_conversation"

        return IntentResult(
            success=True,
            intent_type=IntentResultType.CONVERSATION,
            confidence=intent.confidence,
            action=action,
            message=message,
            response=message,
            processing_time_ms=processing_time,
            request_id=request_id,
            data={
                'grounded': response.metadata.get('grounded', False) if response.metadata else False,
                'sources': response.metadata.get('sources', []) if response.metadata else [],
                'conversation_context_used': bool(conversation_history),
                'was_follow_up': is_follow_up,
            } if response.success else None,
        )

    # -----------------------------------------------------------------------
    # CONTENT DETECTION METHODS
    # -----------------------------------------------------------------------

    def _detect_content_type(self, request: str, response: str) -> Optional[str]:
        """
        Detect if response is generated content (note, email, template, etc.)

        Sprint 4.2: Memory-aware content display.
        Sprint 4.2.1: Added research/search detection.
        Sprint 4.5.0: Added weather/query detection for display context.

        Args:
            request: The user's original request
            response: The AI-generated response

        Returns:
            Content type string if detected, None otherwise
        """
        request_lower = request.lower()
        response_lower = response.lower()

        # Sprint 4.5.0: Weather/info query detection (Problem #2 fix)
        weather_keywords = ["clima", "weather", "temperatura", "temperature", "forecast", "pronóstico", "tiempo"]
        if any(kw in request_lower for kw in weather_keywords):
            return "weather_info"

        # Sprint 4.5.0: Detect weather by response characteristics
        if len(response) > 100:
            weather_indicators = ["°c", "°f", "grados", "degrees", "humidity", "humedad", "lluvia", "rain", "soleado", "sunny"]
            if any(ind in response_lower for ind in weather_indicators):
                return "weather_info"

        # Content creation keywords
        content_keywords = {
            "note": ["nota", "note", "apunte", "notes", "notas", "tips"],
            "email": ["email", "correo", "mensaje de correo", "mail"],
            "template": ["plantilla", "template", "formato"],
            "script": ["script", "guión", "guion"],
            "document": ["documento", "document", "doc"],
            "list": ["lista", "list", "checklist"],
            "message": ["mensaje", "message"],
            "summary": ["resumen", "summary"],
            "tutorial": ["tutorial", "guía", "guide"],
            # Sprint 4.5.0: Plan/intervention content
            "plan": ["plan", "intervención", "intervention", "protocolo", "protocol", "estrategia", "strategy"],
            # Sprint 4.2.1: Research/search content
            "research": ["investiga", "investigate", "research", "búsqueda", "busca", "search", "find", "encuentra"],
            "analysis": ["analiza", "analyze", "analysis", "análisis"],
            "explanation": ["explica", "explain", "qué es", "what is", "cuéntame", "tell me about"],
        }

        # Check if request contains creation intent
        creation_verbs = [
            "crear", "create", "escribe", "write", "genera", "generate",
            "redacta", "draft", "hazme", "dame", "give me", "necesito",
            "i need", "make", "haz", "crea",
            # Sprint 4.2.1: Research/search verbs (these also generate content)
            "investiga", "investigate", "busca", "search", "find",
            "analiza", "analyze", "explica", "explain", "cuéntame", "tell me",
        ]
        has_creation_intent = any(verb in request_lower for verb in creation_verbs)

        if has_creation_intent:
            for content_type, keywords in content_keywords.items():
                if any(keyword in request_lower for keyword in keywords):
                    return content_type

        # Check if response is structured content (longer than 100 chars with creation intent)
        if len(response) > 100 and has_creation_intent:
            return "research" if any(v in request_lower for v in ["investiga", "busca", "search", "find"]) else "document"

        return None

    def _extract_content_title(self, request: str, response: str) -> Optional[str]:
        """
        Extract title from request or first line of response.

        Sprint 4.2: Memory-aware content display.

        Args:
            request: The user's original request
            response: The AI-generated response

        Returns:
            Title string if extracted, None otherwise
        """
        # Try to extract from request (e.g., "crear nota ABA" -> "ABA")
        # Pattern: content type word followed by name/title
        patterns = [
            r'(nota|note|email|correo|documento|document|plantilla|template)\s+(?:de\s+|sobre\s+|para\s+)?["\']?([A-Za-z0-9áéíóúÁÉÍÓÚñÑ\s]+)["\']?',
            r'(nota|note|email|correo|documento|document|plantilla|template)\s+["\']?([A-Z][A-Za-z0-9\s]+)["\']?',
        ]

        for pattern in patterns:
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                title = match.group(2).strip()
                # Clean up common trailing words
                title = re.sub(r'\s+(y|and|en|on|para|for)\s*$', '', title, flags=re.IGNORECASE)
                if len(title) > 2:  # Avoid single letters
                    return title[:50]  # Max 50 chars

        # Fallback: use first line of response (max 50 chars)
        first_line = response.split('\n')[0].strip()
        # Remove markdown headers
        first_line = re.sub(r'^#+\s*', '', first_line)
        # Remove common prefixes
        first_line = re.sub(r'^(Aquí|Here|Este|This)\s+(está|is|es)?\s*:?\s*', '', first_line, flags=re.IGNORECASE)

        if first_line and len(first_line) > 3:
            return first_line[:50]

        return None

    # -----------------------------------------------------------------------
    # STATIC HELPER METHODS
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_action_value(action: Any) -> Optional[str]:
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
