"""
Display Content Handler - Handles scene-based content display.

This handler is responsible for:
- Memory-based content display (fast path)
- Device resolution for display
- Scene type detection
- Custom layout generation with human feedback mode
- Scene graph generation (fallback)
- WebSocket content delivery

Sprint US-3.2: Extracted from IntentService
CRITICAL: Fixes require_feedback/human_feedback_mode bug

Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import DisplayContentIntent
from app.ai.intent.device_mapper import device_mapper
from app.ai.monitoring import ai_monitor
from app.core.config import settings


logger = logging.getLogger("jarvis.services.intent_handlers.display_content")


class DisplayContentHandler(IntentHandler):
    """
    Handler for display content intents.

    Handles:
    - DisplayContentIntent: Scene-based content display on devices

    CRITICAL: This handler GUARANTEES that require_feedback is always
    passed correctly as human_feedback_mode to custom_layout_service.
    This fixes the bug where complex_execution path didn't pass the flag,
    causing full CSS validation (~40s) instead of JS-only (~5s).
    """

    @property
    def handler_name(self) -> str:
        """Return the handler name for logging."""
        return "display_content"

    @property
    def supported_intent_types(self) -> List[str]:
        """Return list of supported intent types."""
        return ["display_content"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The parsed intent object
            context: Handler context

        Returns:
            True if intent is DisplayContentIntent
        """
        return isinstance(intent, DisplayContentIntent)

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Process the display content intent and return a result.

        Args:
            intent: The parsed intent object (DisplayContentIntent)
            context: Handler context with user, devices, etc.

        Returns:
            IntentResult with processing outcome

        CRITICAL: This method GUARANTEES require_feedback is passed
        as human_feedback_mode to ALL custom_layout_service calls.
        """
        self._log_entry(intent, context)

        # GUARANTEE: Extract require_feedback from context ONCE at entry
        human_feedback_mode = context.require_feedback
        logger.info(
            f"[{context.request_id}] [DISPLAY_HANDLER] require_feedback={human_feedback_mode}"
        )

        try:
            result = await self._handle_display_content(
                intent=intent,
                context=context,
                human_feedback_mode=human_feedback_mode,
            )

            self._log_exit(
                context,
                success=result.success,
                processing_time_ms=result.processing_time_ms,
            )
            return result

        except Exception as e:
            processing_time = (time.time() - context.start_time) * 1000
            logger.error(
                f"[{context.request_id}] DisplayContentHandler error: {e}",
                exc_info=True,
            )
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error processing display content: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    # -------------------------------------------------------------------------
    # MAIN DISPLAY CONTENT HANDLER
    # -------------------------------------------------------------------------

    async def _handle_display_content(
        self,
        intent: DisplayContentIntent,
        context: HandlerContext,
        human_feedback_mode: bool,
    ) -> IntentResult:
        """
        Handle display content intents by generating and sending scene graphs.

        Sprint 4.0: Scene Graph implementation for creative device layouts.
        Sprint 4.2: Memory-aware content display - check generated content first.
        Sprint 5.1.4: Uses context for anaphoric resolution.
        Sprint US-3.2: CRITICAL - human_feedback_mode passed explicitly.

        Args:
            intent: The DisplayContentIntent
            context: Handler context
            human_feedback_mode: CRITICAL - If True, return HTML for validation

        Returns:
            IntentResult with display outcome
        """
        from app.ai.scene.service import scene_service
        from app.ai.scene.defaults import detect_default_scene_type
        from app.services.conversation_context_service import conversation_context_service
        from app.services.commands import command_service
        from app.services.websocket_manager import connection_manager

        request_id = context.request_id
        user_id = context.user_id
        start_time = context.start_time

        logger.info(
            f"[{request_id}] ENTERING _handle_display_content for user {str(user_id)[:8]}..."
        )

        # Sprint 4.2: Check for recently generated content in memory
        generated_content = conversation_context_service.get_generated_content(str(user_id))
        logger.info(f"[{request_id}] generated_content exists: {generated_content is not None}")

        # Also get conversation history for context
        conversation_history = conversation_context_service.get_conversation_history(
            str(user_id), max_turns=5
        )
        logger.info(
            f"[{request_id}] conversation_history turns: "
            f"{len(conversation_history) if conversation_history else 0}"
        )

        # Check for memory-based fast path
        if generated_content:
            fast_path_result = await self._try_memory_fast_path(
                intent=intent,
                context=context,
                generated_content=generated_content,
            )
            if fast_path_result:
                return fast_path_result

        logger.info(
            f"[{request_id}] Handling display content intent",
            extra={
                "info_type": intent.info_type,
                "layout_type": intent.layout_type,
                "layout_hints": intent.layout_hints,
                "device_name": intent.device_name,
            },
        )

        try:
            # Resolve target device
            target_device = await self._resolve_target_device(
                intent=intent,
                context=context,
            )
            if isinstance(target_device, IntentResult):
                # Device resolution failed, return error result
                return target_device

            # Sprint 5.2.3: Send initial loading signal - Phase 1
            await connection_manager.send_command(
                device_id=target_device.id,
                command_type="loading_start",
                parameters={"message": "Preparando visualización...", "phase": 1},
            )
            logger.info(f"[{request_id}] Loading Phase 1: Preparing")

            # Detect default scene type for optimized generation
            default_type = detect_default_scene_type(
                info_type=intent.info_type,
                layout_hints=intent.layout_hints,
                user_request=intent.original_text,
            )
            logger.info(f"[{request_id}] Detected default scene type: {default_type}")

            # Normalize layout hints to structured LayoutHint objects
            normalized_hints = scene_service.normalize_layout_hints(intent.layout_hints)

            # Fetch real-time data BEFORE calling Claude for scene generation
            realtime_data = await self._fetch_realtime_data(
                user_request=intent.original_text,
                layout_hints=intent.layout_hints,
            )

            has_realtime_data = bool(
                realtime_data
                and any(k in realtime_data for k in ["calendar", "weather", "events", "documents"])
            )

            if realtime_data:
                logger.info(
                    f"[{request_id}] Fetched real-time data for: "
                    f"{list(realtime_data.keys())} (has_realtime={has_realtime_data})"
                )

            # Build conversation context for scene generation
            conversation_context_dict = self._build_conversation_context(
                user_id=user_id,
                request_id=request_id,
                intent=intent,
                context=context,
                generated_content=generated_content,
            )

            # Sprint 5.2.3: Loading Phase 2 - Generating content
            await connection_manager.send_command(
                device_id=target_device.id,
                command_type="loading_start",
                parameters={"message": "Analizando contenido...", "phase": 2},
            )
            logger.info(f"[{request_id}] Loading Phase 2: Analyzing")

            # Generate scene and layout
            scene_dict, custom_layout, content_data, layout_result = await self._generate_scene_and_layout(
                intent=intent,
                context=context,
                target_device=target_device,
                normalized_hints=normalized_hints,
                realtime_data=realtime_data,
                conversation_context_dict=conversation_context_dict,
                human_feedback_mode=human_feedback_mode,  # CRITICAL: Pass explicitly
            )

            # Build response metadata
            is_direct_flow = scene_dict.get("direct_flow", False) if scene_dict else False

            if is_direct_flow and content_data:
                content_type = content_data.get("content_type", "content")
                content_title = content_data.get("title", "interactive content")
                scene_id = request_id
                layout_intent = content_type
                components_list = [content_type]
            else:
                # SceneGraph flow: use scene_dict directly
                scene_id = scene_dict.get("scene_id", request_id)
                layout_intent = scene_dict.get("layout", {}).get("intent", "unknown")
                components_list = [c.get("type", "unknown") for c in scene_dict.get("components", [])]
                content_type = layout_intent
                content_title = "layout"

            processing_time = (time.time() - start_time) * 1000

            # ================================================================
            # HUMAN FEEDBACK MODE: Return HTML for validation
            # ================================================================
            if human_feedback_mode and custom_layout:
                logger.info(
                    f"[{request_id}] Feedback mode: returning HTML for validation "
                    "(not sending to device)"
                )

                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.DISPLAY_CONTENT,
                    confidence=intent.confidence,
                    device=target_device,
                    message=(
                        f"HTML generated for {content_type}: {content_title}. "
                        "Awaiting human feedback before display."
                    ),
                    data={
                        "scene_id": scene_id,
                        "scene": scene_dict,
                        "target_device": str(target_device.id),
                        "layout_intent": layout_intent,
                        "require_feedback": True,
                        "generated_html": custom_layout,
                        "js_errors": (
                            layout_result.js_errors
                            if layout_result and hasattr(layout_result, "js_errors")
                            else []
                        ),
                    },
                    command_sent=False,
                    command_id=None,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # ================================================================
            # NORMAL MODE: Send to device immediately
            # ================================================================
            result = await command_service.display_scene(
                device_id=target_device.id,
                scene=scene_dict,
                custom_layout=custom_layout,
            )

            if not result.success:
                raise Exception(f"Failed to send scene to device: {result.error}")

            # Track command for monitoring
            ai_monitor.track_command(
                request_id=request_id,
                device_id=target_device.id,
                device_name=target_device.name,
                action="display_scene",
                command_id=result.command_id,
                success=result.success,
                error=result.error,
            )

            # Build response message
            if is_direct_flow and content_data:
                response_message = (
                    f"I've updated {target_device.name} with {content_type}: {content_title}."
                )
            else:
                component_summary = ", ".join(components_list[:3])
                if len(components_list) > 3:
                    component_summary += f" and {len(components_list) - 3} more"
                response_message = f"I've updated {target_device.name} with {component_summary}."

            # Save display content response to conversation context
            conversation_context_service.add_conversation_turn(
                user_id=str(user_id),
                user_message=intent.original_text or "Display content request",
                assistant_response=response_message,
                intent_type="display_content",
            )

            # Save scene metadata for assistant awareness
            conversation_context_service.set_last_scene(
                user_id=str(user_id),
                scene_id=scene_id,
                components=components_list,
                layout_intent=layout_intent,
            )

            return IntentResult(
                success=True,
                intent_type=IntentResultType.DISPLAY_CONTENT,
                confidence=intent.confidence,
                device=target_device,
                message=response_message,
                data={
                    "scene_id": scene_id,
                    "scene": scene_dict,
                    "target_device": str(target_device.id),
                    "layout_intent": layout_intent,
                },
                command_sent=result.success,
                command_id=result.command_id,
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        except Exception as e:
            logger.error(
                f"[{request_id}] Failed to handle display content: {e}",
                exc_info=True,
            )
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to update display: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    async def _try_memory_fast_path(
        self,
        intent: DisplayContentIntent,
        context: HandlerContext,
        generated_content: Dict[str, Any],
    ) -> Optional[IntentResult]:
        """
        Try to display content from memory (fast path).

        Returns IntentResult if fast path applies, None otherwise.
        """
        from app.services.commands import command_service
        from app.services.conversation_context_service import conversation_context_service

        request_id = context.request_id
        original_text_lower = intent.original_text.lower() if intent.original_text else ""

        logger.info(f"[{request_id}] Checking memory keywords in: '{original_text_lower[:50]}...'")

        memory_keywords = [
            "que creaste", "que hiciste", "que generaste", "que acabas",
            "esa nota", "ese email", "la plantilla", "la nota", "el email",
            "you created", "you made", "you generated", "you just wrote",
            "that note", "that email", "the template", "the note",
            "show it", "muéstralo", "muestramelo", "muéstramelo",
            "los resultados", "the results", "lo que encontraste", "what you found",
            "lo que investigaste", "what you researched", "esa información",
            "that information", "eso", "that", "esto", "this",
            "muestrame eso", "show me that", "ponlo", "put it",
            "esas", "esos", "estas", "estos", "those", "these",
        ]

        is_memory_reference = any(kw in original_text_lower for kw in memory_keywords)

        # Detect multi-content requests that need Claude scene generation
        multi_content_keywords = [
            " y ", " and ", "junto", "juntos", "together", "ambos", "both",
            "izquierda", "derecha", "left", "right", "arriba", "abajo",
            "two_column", "dos columnas", "lado a lado", "side by side",
        ]
        is_multi_content_request = any(kw in original_text_lower for kw in multi_content_keywords)

        if is_multi_content_request:
            logger.info(
                f"[{request_id}] Multi-content request detected - "
                "skipping fast path, using Claude scene generation"
            )
            return None

        if not is_memory_reference:
            return None

        logger.info(
            f"[{request_id}] Displaying generated content from memory (fast path): "
            f"type={generated_content['type']}, title={generated_content['title']}"
        )

        # Resolve target device
        target_device = await self._resolve_target_device(
            intent=intent,
            context=context,
        )
        if isinstance(target_device, IntentResult):
            return target_device

        # Build SceneGraph with generated content as text_block
        content_title = generated_content["title"] or "Generated Content"
        content_text = generated_content["content"]

        scene_dict = {
            "scene_id": f"memory-content-{request_id[:8]}",
            "version": "1.1",
            "target_devices": [str(target_device.id)],
            "layout": {
                "intent": "fullscreen",
                "engine": "flex",
                "gap": "16px",
            },
            "components": [
                {
                    "id": "generated_content_display",
                    "type": "text_block",
                    "priority": "primary",
                    "position": {"flex": 1},
                    "style": {
                        "background": "#1a1a2e",
                        "text_color": "#ffffff",
                        "border_radius": "16px",
                        "padding": "32px",
                    },
                    "props": {
                        "content": content_text,
                        "title": content_title,
                        "alignment": "left",
                        "font_size": "18px",
                    },
                    "data": {
                        "content": content_text,
                        "is_placeholder": False,
                    },
                }
            ],
            "global_style": {
                "background": "#0f0f23",
                "font_family": "Inter",
                "text_color": "#ffffff",
                "accent_color": "#7b2cbf",
            },
            "metadata": {
                "user_request": intent.original_text,
                "generated_by": "memory_context",
                "refresh_seconds": 300,
            },
        }

        # Send to device
        result = await command_service.display_scene(
            device_id=target_device.id,
            scene=scene_dict,
        )

        processing_time = (time.time() - context.start_time) * 1000
        memory_message = (
            f"Showing {generated_content['type']}: {content_title} on {target_device.name}"
        )

        # Save to conversation context
        conversation_context_service.add_conversation_turn(
            user_id=str(context.user_id),
            user_message=intent.original_text or "Display generated content",
            assistant_response=memory_message,
            intent_type="display_content",
        )

        return IntentResult(
            success=result.success,
            intent_type=IntentResultType.DISPLAY_CONTENT,
            confidence=0.95,
            device=target_device,
            action="display_scene",
            message=memory_message,
            command_sent=result.success,
            command_id=result.command_id,
            processing_time_ms=processing_time,
            request_id=request_id,
            data={
                "source": "generated_content_memory",
                "content_type": generated_content["type"],
                "content_title": content_title,
            },
        )

    async def _resolve_target_device(
        self,
        intent: DisplayContentIntent,
        context: HandlerContext,
    ) -> Any:  # Returns Device or IntentResult
        """
        Resolve the target device for display.

        Returns Device if found, IntentResult error if not.
        """
        target_device = None

        if intent.device_name:
            target_device, _ = device_mapper.match(intent.device_name, context.devices)
            if not target_device:
                processing_time = (time.time() - context.start_time) * 1000
                alternatives = device_mapper.match_all(intent.device_name, context.devices, limit=3)
                suggestion = ""
                if alternatives:
                    names = [f'"{d.name}"' for d, _ in alternatives]
                    suggestion = f" Did you mean: {', '.join(names)}?"

                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.DISPLAY_CONTENT,
                    message=f"I couldn't find a device matching '{intent.device_name}'.{suggestion}",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )
        else:
            target_device = next((d for d in context.devices if d.is_online), None)

        if not target_device:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DISPLAY_CONTENT,
                message="No display device available. Please connect a device first.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        if not target_device.is_online:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DISPLAY_CONTENT,
                device=target_device,
                message=f"'{target_device.name}' is currently offline.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        return target_device

    async def _fetch_realtime_data(
        self,
        user_request: Optional[str],
        layout_hints: Optional[List[str]],
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time data for scene generation.

        Sprint 4: Now calls local method instead of IntentService.
        """
        return await self._fetch_realtime_data_for_scene(
            user_request=user_request or "",
            layout_hints=layout_hints or [],
        )

    def _build_conversation_context(
        self,
        user_id: UUID,
        request_id: str,
        intent: DisplayContentIntent,
        context: HandlerContext,
        generated_content: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build conversation context for scene generation.
        """
        from app.services.conversation_context_service import conversation_context_service

        conversation_context_dict: Dict[str, Any] = {}
        original_text_lower = (intent.original_text or "").lower()

        # Detect if user wants a conversation summary
        is_summary_request = any(
            kw in original_text_lower
            for kw in [
                "resume", "resumen", "resumas", "summarize", "summary",
                "lo que hablamos", "what we discussed", "esta conversación",
                "this conversation", "nuestra conversación", "our conversation",
            ]
        )

        # Get more turns for summary requests
        max_turns = 10 if is_summary_request else 5
        conversation_history = conversation_context_service.get_conversation_history(
            str(user_id), max_turns=max_turns
        )

        if conversation_history:
            conversation_context_dict["history"] = conversation_history
            if is_summary_request:
                logger.info(
                    f"[{request_id}] SUMMARY REQUEST: Including "
                    f"{len(conversation_history)} conversation turns"
                )
            else:
                logger.info(
                    f"[{request_id}] Including {len(conversation_history)} "
                    "conversation turns in scene context"
                )

        # Get generated content
        if generated_content:
            gc_serialized = {
                k: v.isoformat() if hasattr(v, "isoformat") else v
                for k, v in generated_content.items()
            }
            conversation_context_dict["generated_content"] = gc_serialized
            logger.info(
                f"[{request_id}] Including generated content in scene context: "
                f"type={generated_content.get('type')}"
            )

        # Get last assistant response
        context_state = conversation_context_service.get_context(str(user_id))
        if context_state and context_state.last_assistant_response:
            conversation_context_dict["last_response"] = context_state.last_assistant_response

        # Include resolved references from context
        resolved_refs = context.resolved_references or {}

        # Last event context
        last_event = resolved_refs.get("event")
        if not last_event:
            last_event = conversation_context_service.get_last_event(str(user_id))
        if last_event:
            conversation_context_dict["last_event"] = last_event
            logger.info(
                f"[{request_id}] Including last event in scene context: "
                f"{last_event.get('title')}"
            )

        # Last doc context
        last_doc = resolved_refs.get("document")
        if not last_doc:
            last_doc = conversation_context_service.get_last_doc(str(user_id))
        if last_doc:
            conversation_context_dict["last_doc"] = last_doc
            logger.info(
                f"[{request_id}] Including last doc in scene context: "
                f"{last_doc.get('title')}"
            )

        # Content memory for multi-content display
        content_memory = conversation_context_service.get_content_memory(str(user_id), limit=5)
        if content_memory:
            conversation_context_dict["content_memory"] = content_memory
            logger.info(
                f"[{request_id}] Including content memory in scene context: "
                f"{len(content_memory)} items"
            )

        return conversation_context_dict

    async def _generate_scene_and_layout(
        self,
        intent: DisplayContentIntent,
        context: HandlerContext,
        target_device: Any,
        normalized_hints: List[Any],
        realtime_data: Optional[Dict[str, Any]],
        conversation_context_dict: Dict[str, Any],
        human_feedback_mode: bool,
    ) -> tuple:
        """
        Generate scene and custom layout.

        CRITICAL: human_feedback_mode is passed explicitly to all
        custom_layout_service calls.

        Returns:
            Tuple of (scene_dict, custom_layout, content_data, layout_result)
        """
        from app.ai.scene.service import scene_service
        from app.services.websocket_manager import connection_manager

        request_id = context.request_id
        scene_dict = None
        custom_layout = None
        content_data = None
        layout_result = None

        if settings.CUSTOM_LAYOUT_ENABLED:
            # =================================================================
            # DIRECT FLOW: All content types
            # =================================================================
            logger.info(f"[{request_id}] Using DIRECT flow (no SceneGraph)")

            try:
                from app.ai.scene.custom_layout import custom_layout_service

                # Generate content data with Gemini
                hints_str = ", ".join(intent.layout_hints) if intent.layout_hints else None
                content_data = await scene_service.generate_content_data(
                    user_request=intent.original_text,
                    layout_hints=normalized_hints,
                    realtime_data=realtime_data,
                    conversation_context=conversation_context_dict,
                )

                if content_data:
                    logger.info(
                        f"[{request_id}] Content data generated: "
                        f"{content_data.get('content_type', 'unknown')}"
                    )

                    # Loading Phase 3 - Designing layout
                    await connection_manager.send_command(
                        device_id=target_device.id,
                        command_type="loading_start",
                        parameters={"message": "Diseñando experiencia...", "phase": 3},
                    )
                    logger.info(f"[{request_id}] Loading Phase 3: Designing (direct flow)")

                    # CRITICAL: Pass human_feedback_mode explicitly
                    layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                        content_data=content_data,
                        user_request=intent.original_text or "",
                        layout_hints=hints_str,
                        layout_type=content_data.get("content_type"),
                        human_feedback_mode=human_feedback_mode,  # EXPLICIT
                        conversation_context=conversation_context_dict,
                    )

                    if layout_result.success and layout_result.html:
                        custom_layout = layout_result.html
                        logger.info(
                            f"[{request_id}] Direct HTML generated + validated "
                            f"(latency: {layout_result.latency_ms:.0f}ms)"
                        )
                        scene_dict = {"scene_id": request_id, "direct_flow": True}
                    else:
                        logger.warning(
                            f"[{request_id}] Direct flow failed: {layout_result.error}. "
                            "Falling back to SceneGraph flow."
                        )
                else:
                    logger.warning(
                        f"[{request_id}] Content data generation failed, "
                        "falling back to SceneGraph"
                    )

            except Exception as e:
                logger.error(
                    f"[{request_id}] Direct flow error, falling back to SceneGraph: {e}",
                    exc_info=True,
                )

        # =================================================================
        # SCENOGRAPH FLOW: Fallback
        # =================================================================
        if scene_dict is None:
            logger.info(f"[{request_id}] Using SCENOGRAPH flow (fallback)")

            scene = await scene_service.generate_scene(
                layout_hints=normalized_hints,
                info_type=intent.info_type,
                target_devices=[str(target_device.id)],
                user_id=str(context.user_id),
                user_request=intent.original_text,
                db=context.db,
                realtime_data=realtime_data,
                conversation_context=conversation_context_dict,
            )

            scene_dict = scene.model_dump(mode="json")

            # Generate custom HTML layout if enabled
            if settings.CUSTOM_LAYOUT_ENABLED:
                try:
                    from app.ai.scene.custom_layout import custom_layout_service

                    # Loading Phase 3 - Designing layout
                    await connection_manager.send_command(
                        device_id=target_device.id,
                        command_type="loading_start",
                        parameters={"message": "Diseñando experiencia...", "phase": 3},
                    )
                    logger.info(f"[{request_id}] Loading Phase 3: Designing")

                    # CRITICAL: Pass human_feedback_mode explicitly
                    layout_result = await custom_layout_service.generate_and_validate_html(
                        scene=scene_dict,
                        user_request=intent.original_text or "",
                        human_feedback_mode=human_feedback_mode,  # EXPLICIT
                    )

                    if layout_result.success and layout_result.html:
                        custom_layout = layout_result.html
                        logger.info(
                            f"[{request_id}] Custom HTML layout generated and validated "
                            f"(latency: {layout_result.latency_ms:.0f}ms)"
                        )
                    else:
                        logger.warning(
                            f"[{request_id}] Custom layout generation/validation failed: "
                            f"{layout_result.error}. Falling back to SceneGraph."
                        )
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Custom layout error (falling back to SceneGraph): {e}",
                        exc_info=True,
                    )

        return scene_dict, custom_layout, content_data, layout_result

    # -------------------------------------------------------------------------
    # REAL-TIME DATA HELPERS - Sprint 4 extraction from IntentService
    # -------------------------------------------------------------------------

    async def _fetch_realtime_data_for_scene(
        self,
        user_request: str,
        layout_hints: list,
    ) -> Dict[str, Any]:
        """
        Use Gemini with web search to fetch real-time data for scene components.

        Sprint 4: Moved from IntentService.
        Sprint 4.1: This method detects what type of real-time data is needed
        (weather, news, etc.) and uses Gemini's grounding capability to fetch it
        BEFORE calling Claude for scene generation.

        Args:
            user_request: Original user request
            layout_hints: Parsed layout hints

        Returns:
            Dict with component_type -> data mapping
            Example: {"weather_current": {"temperature": 25, "condition": "snow"}}
        """
        from app.ai.providers.gemini import gemini_provider

        realtime_data = {}

        # Check if user wants weather data
        weather_keywords = ["clima", "weather", "temperatura", "temperature", "tiempo"]
        if any(keyword in user_request.lower() for keyword in weather_keywords):
            # Extract location from request
            location = self._extract_location_from_request(user_request)
            if not location:
                location = "Miami, FL"  # Default to real location (grounding needs specific place)

            # Gemini fetches weather as natural text (simple task)
            # Claude will extract structured data when generating the scene (complex task)
            # Sprint 5.1.4: Simplified prompt works better with grounding
            prompt = f"What is the current temperature and weather conditions in {location} right now?"

            try:
                response = await gemini_provider.generate_with_grounding(
                    prompt=prompt,
                    system_prompt=None,  # No system prompt - let grounding work naturally
                    use_search=True,
                    temperature=0.1,
                    max_tokens=300,  # More tokens to avoid truncation
                )

                if response.success and response.content:
                    weather_text = response.content.strip()
                    # Pass raw text to Claude - it will extract the structured data
                    realtime_data["weather_current"] = {
                        "raw_weather_info": weather_text,
                        "location": location,
                        "is_placeholder": False,
                        "fetched_via": "gemini_grounding",
                    }
                    logger.info(f"Fetched weather for {location}: {weather_text[:100]}...")
            except Exception as e:
                logger.warning(f"Failed to fetch weather data via Gemini: {e}")
                # Don't fail - Claude will use placeholder if needed

        # Future extensibility: Add similar blocks for news, stocks, etc.
        # if any(kw in user_request.lower() for kw in ["news", "noticias"]):
        #     realtime_data["news_feed"] = await self._fetch_news_via_gemini(user_request)

        return realtime_data

    def _extract_location_from_request(self, user_request: str) -> Optional[str]:
        """
        Extract location from user request.

        Sprint 4: Moved from IntentService.

        Examples:
            "clima de Alaska" -> "Alaska"
            "weather in Miami" -> "Miami"
            "temperatura en New York" -> "New York"
            "show weather for London" -> "London"
            "muestra el clima en la pantalla" -> None (not a location!)
        """
        import re

        # Words that are display destinations, NOT locations
        display_words = ["pantalla", "screen", "tv", "monitor", "display", "tele", "television"]

        # Spanish patterns - greedy capture up to end of sentence or punctuation
        spanish_match = re.search(
            r'(?:clima|tiempo|temperatura)\s+(?:de|en)\s+([A-Za-z][A-Za-z\s]*[A-Za-z])',
            user_request,
            re.IGNORECASE
        )
        if spanish_match:
            # Clean up - remove trailing common words
            location = spanish_match.group(1).strip()
            # Remove common trailing words that aren't part of place names
            location = re.sub(r'\s+(en|on|the|la|el|para|for).*$', '', location, flags=re.IGNORECASE)
            location = location.strip()
            # Sprint 5.1.3: Exclude display destinations from being treated as locations
            if location.lower() in display_words or any(dw in location.lower() for dw in display_words):
                return None
            return location

        # English patterns - greedy capture
        english_match = re.search(
            r'(?:weather|climate|temperature)\s+(?:in|for|of)\s+([A-Za-z][A-Za-z\s]*[A-Za-z])',
            user_request,
            re.IGNORECASE
        )
        if english_match:
            location = english_match.group(1).strip()
            # Remove common trailing words
            location = re.sub(r'\s+(on|the|screen|tv|display|pantalla).*$', '', location, flags=re.IGNORECASE)
            location = location.strip()
            # Sprint 5.1.3: Exclude display destinations from being treated as locations
            if location.lower() in display_words or any(dw in location.lower() for dw in display_words):
                return None
            return location

        # Try to find capitalized place names after show/display
        place_match = re.search(
            r'(?:show|display|muestra|mostrar)\s+.*?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            user_request
        )
        if place_match:
            return place_match.group(1).strip()

        return None
