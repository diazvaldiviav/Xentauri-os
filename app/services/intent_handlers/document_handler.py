"""
Document Handler - Handles Google Docs intelligence queries.

This handler is responsible for:
- LINK_DOC: Link a document to a calendar event
- OPEN_DOC: Open a document linked to an event
- READ_DOC: Read/analyze document content
- SUMMARIZE_MEETING_DOC: Summarize document linked to meeting
- CREATE_EVENT_FROM_DOC: Create calendar event from doc content

Sprint US-3.3: Extracted from IntentService
Sprint US-4.1: Full implementation moved from IntentService (removed delegation)

Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import DocQueryIntent, ActionType
from app.ai.intent.device_mapper import device_mapper
from app.models.oauth_credential import OAuthCredential
from app.models.device import Device
from app.environments.google.docs import GoogleDocsClient
from app.environments.google.calendar.client import GoogleCalendarClient
from app.environments.google.calendar.schemas import EventUpdateRequest
from app.services.meeting_link_service import meeting_link_service
from app.services.doc_intelligence_service import doc_intelligence_service
from app.services.pending_event_service import pending_event_service
from app.services.conversation_context_service import conversation_context_service
from app.services.commands import command_service
from app.ai.monitoring import ai_monitor


logger = logging.getLogger("jarvis.services.intent_handlers.document")


class DocumentHandler(IntentHandler):
    """
    Handler for document-related intents.

    Handles:
    - DocQueryIntent: All Google Docs intelligence operations

    Supports compound intents (also_display) to both process
    the document and display it on a device.
    """

    @property
    def handler_name(self) -> str:
        """Return the handler name for logging."""
        return "document"

    @property
    def supported_intent_types(self) -> List[str]:
        """Return list of supported intent types."""
        return ["doc_query"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The parsed intent object
            context: Handler context

        Returns:
            True if intent is DocQueryIntent
        """
        return isinstance(intent, DocQueryIntent)

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Process the document-related intent and return a result.

        Args:
            intent: The parsed intent object (DocQueryIntent)
            context: Handler context with user, devices, etc.

        Returns:
            IntentResult with processing outcome
        """
        self._log_entry(intent, context)

        try:
            result = await self._handle_doc_query(
                intent=intent,
                context=context,
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
                f"[{context.request_id}] DocumentHandler error: {e}",
                exc_info=True,
            )
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error processing document query: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    # -------------------------------------------------------------------------
    # MAIN DOC QUERY HANDLER
    # -------------------------------------------------------------------------

    async def _handle_doc_query(
        self,
        intent: DocQueryIntent,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle Google Docs intelligence queries.

        Sprint 3.9: Routes doc query actions:
        1. LINK_DOC: Link a document to a calendar event
        2. OPEN_DOC: Open a document linked to an event
        3. READ_DOC: Read/analyze document content
        4. SUMMARIZE_MEETING_DOC: Summarize document linked to meeting

        Sprint 4.0.2: Compound intent support
        If intent.also_display is True, ALSO sends show_content command to device.

        Sprint 5.1.4: Anaphoric resolution support
        If intent.doc_url is None, attempts to resolve from context.resolved_references.
        """
        request_id = context.request_id
        user_id = context.user_id
        start_time = context.start_time
        db = context.db

        action = intent.action
        result: Optional[IntentResult] = None

        # Build context dict for helper methods
        ctx_dict: Dict[str, Any] = {
            "resolved_references": context.resolved_references,
        }

        # Route based on action type
        if action == ActionType.LINK_DOC:
            result = await self._handle_link_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=ctx_dict,
            )
        elif action == ActionType.OPEN_DOC:
            result = await self._handle_open_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=ctx_dict,
            )
        elif action == ActionType.READ_DOC:
            result = await self._handle_read_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
                context=ctx_dict,
            )
        elif action == ActionType.SUMMARIZE_MEETING_DOC:
            result = await self._handle_summarize_meeting_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        elif action == ActionType.CREATE_EVENT_FROM_DOC:
            result = await self._handle_create_event_from_doc(
                request_id=request_id,
                intent=intent,
                user_id=user_id,
                start_time=start_time,
                db=db,
            )
        else:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Unknown doc query action: {action}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        # Sprint 4.0.2: Handle compound intent (also_display)
        if result and result.success and getattr(intent, "also_display", False):
            result = await self._handle_also_display(
                result=result,
                intent=intent,
                action=action,
                context=context,
            )

        # Sprint 4.3.0: Save doc query response to conversation context
        if result and result.success and result.message:
            user_message = getattr(intent, "original_text", f"Doc query: {action}")
            conversation_context_service.add_conversation_turn(
                user_id=str(user_id),
                user_message=user_message,
                assistant_response=result.message,
                intent_type="doc_query",
            )

        return result  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # COMPOUND INTENT (ALSO_DISPLAY)
    # -------------------------------------------------------------------------

    async def _handle_also_display(
        self,
        result: IntentResult,
        intent: DocQueryIntent,
        action: ActionType,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle compound intent where user wants both text response AND display.

        Sprint 4.0.2: If user wants BOTH a text response AND to display the doc on screen.
        """
        from app.ai.scene.schemas import (
            SceneGraph, SceneComponent, LayoutSpec, LayoutIntent,
            LayoutEngine, ComponentPriority, ComponentPosition,
            ComponentStyle, GlobalStyle, SceneMetadata
        )
        from uuid import uuid4

        doc_url = result.data.get("doc_url") if result.data else None

        if not doc_url:
            return result

        # Get available devices
        devices = context.devices
        target_device = None

        # Try to match the display_device name if provided
        display_device_name = getattr(intent, "display_device", None)
        if display_device_name and devices:
            target_device, _ = device_mapper.match(display_device_name, devices)

        # If no match or no device specified, use first online device
        if not target_device:
            online_devices = [d for d in devices if d.is_online]
            if online_devices:
                target_device = online_devices[0]

        if not target_device or not target_device.is_online:
            logger.info("Compound intent: also_display requested but no device available")
            return result

        # Decision: Display summary (Scene Graph) or full document (iframe)?
        cmd_result = None
        display_type = "document"

        if action == ActionType.SUMMARIZE_MEETING_DOC:
            # CASE 1: SUMMARY -> Scene Graph with doc_summary component
            doc_id = GoogleDocsClient.extract_doc_id(doc_url)
            scene = SceneGraph(
                scene_id=str(uuid4()),
                target_devices=[str(target_device.id)],
                layout=LayoutSpec(
                    intent=LayoutIntent.FULLSCREEN,
                    engine=LayoutEngine.FLEX,
                ),
                components=[
                    SceneComponent(
                        id="doc_summary_main",
                        type="doc_summary",
                        priority=ComponentPriority.PRIMARY,
                        position=ComponentPosition(flex=1),
                        props={},
                        data={
                            "doc_id": doc_id,
                            "title": (
                                result.data.get("title", "Document Summary")
                                if result.data
                                else "Document Summary"
                            ),
                            "summary": result.message,  # LLM-generated summary
                            "url": doc_url,
                        },
                        style=ComponentStyle(
                            background="#1a1a2e",
                            text_color="#ffffff",
                            border_radius="12px",
                            padding="24px",
                        ),
                    ),
                ],
                global_style=GlobalStyle(
                    background="#0f0f23",
                    font_family="Inter",
                ),
                metadata=SceneMetadata(
                    user_request=(
                        f"Display summary: "
                        f"{result.data.get('title', 'document') if result.data else 'document'}"
                    ),
                    generated_by="document_handler",
                ),
            )

            # Send scene to device
            scene_dict = scene.model_dump(mode="json")
            cmd_result = await command_service.display_scene(
                device_id=target_device.id,
                scene=scene_dict,
            )
            display_type = "summary"

        elif action in [ActionType.READ_DOC, ActionType.OPEN_DOC]:
            # CASE 2: FULL DOCUMENT -> iframe
            cmd_result = await command_service.show_content(
                device_id=target_device.id,
                url=doc_url,
            )
            display_type = "document"

        else:
            logger.info(f"Action {action} does not support also_display")
            return result

        if cmd_result and cmd_result.success:
            logger.info(
                f"Compound intent: Also displayed {display_type} on {target_device.name}"
            )
            result.command_sent = True
            result.command_id = cmd_result.command_id
            result.device = target_device

            # Update message to indicate both actions completed
            original_message = result.message or ""
            display_label = "Summary" if display_type == "summary" else "Document"
            result.message = (
                f"{original_message}\n\n📺 {display_label} also displayed "
                f"on {target_device.name}."
            )
        elif cmd_result:
            logger.warning(
                f"Compound intent: Display failed on {target_device.name}: "
                f"{cmd_result.error}"
            )

        return result

    # -------------------------------------------------------------------------
    # HELPER METHODS - Context management (Sprint 4 extraction)
    # -------------------------------------------------------------------------

    def _get_event_from_context(self, user_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get the last referenced event from conversation context.

        Returns:
            Tuple of (title, event_id, event_date) or (None, None, None) if not found.
        """
        event = conversation_context_service.get_last_event(user_id)
        if event:
            return event.get("title"), event.get("id"), event.get("date")
        return None, None, None

    def _get_user_devices(self, db: Session, user_id: UUID) -> List[Device]:
        """Get all devices for a user."""
        return db.query(Device).filter(Device.user_id == user_id).all()

    def _store_doc_context(
        self,
        user_id: str,
        doc_id: str,
        doc_url: str,
        doc_title: Optional[str] = None,
        doc_content: Optional[str] = None,
    ) -> None:
        """
        Store a document in conversation context.

        Sprint 4: Moved from IntentService.
        """
        try:
            conversation_context_service.set_last_doc(
                user_id=user_id,
                doc_id=doc_id,
                doc_url=doc_url,
                doc_title=doc_title,
                doc_content=doc_content,
            )
            logger.debug(f"Stored doc context: {doc_title or doc_id}")
        except Exception as e:
            logger.warning(f"Failed to store doc context: {e}")

    def _store_event_context(self, user_id: str, event: Any) -> None:
        """
        Store an event in conversation context.

        Sprint 4: Moved from IntentService.
        """
        try:
            event_date = None
            if event.start:
                start_dt = event.start.get_datetime()
                if start_dt:
                    event_date = start_dt.isoformat()
                elif event.start.date:
                    event_date = event.start.date
            conversation_context_service.set_last_event(
                user_id=user_id,
                event_title=event.get_display_title(),
                event_id=event.id,
                event_date=event_date,
            )
            logger.debug(f"Stored event context: {event.get_display_title()}")
        except Exception as e:
            logger.warning(f"Failed to store event context: {e}")

    # -------------------------------------------------------------------------
    # DOC ACTION METHODS - Sprint 4: Moved from IntentService
    # -------------------------------------------------------------------------

    async def _handle_link_doc(
        self,
        request_id: str,
        intent: DocQueryIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """
        Link a Google Doc to a calendar event.

        Note: This feature requires updating calendar event extended properties,
        which needs a calendar API update method. For now, we provide helpful feedback.

        Sprint 4: Moved from IntentService.
        Sprint 5.1.4: Supports anaphoric references for both doc and meeting.
        """
        doc_url = intent.doc_url
        meeting_search = intent.meeting_search

        # Sprint 5.1.4: Resolve anaphoric references from context
        if context and context.get("resolved_references"):
            resolved = context["resolved_references"]
            if not doc_url and resolved.get("document"):
                doc_url = resolved["document"].get("url")
                logger.info(f"[ANAPHORIC_RESOLUTION] Resolved doc from context: {doc_url}")
            if not meeting_search and resolved.get("event"):
                meeting_search = resolved["event"].get("title")
                logger.info(f"[ANAPHORIC_RESOLUTION] Resolved event from context: {meeting_search}")

        processing_time = (time.time() - start_time) * 1000

        # Validate doc URL
        if not doc_url:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please provide a Google Docs URL to link.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Invalid Google Docs URL format.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        # Need meeting_search to find the event
        # Sprint 3.9: Use conversation context if no meeting specified
        if not meeting_search:
            context_title, context_id, context_date = self._get_event_from_context(str(user_id))
            if context_title:
                meeting_search = context_title
                logger.debug(f"Using event from context: {context_title}")
            else:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Please specify which meeting to link the document to.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

        try:
            # Find the meeting first
            meeting_result = await meeting_link_service.find_meeting_with_doc(
                query=meeting_search,
                user_id=user_id,
                db=db,
            )

            if not meeting_result.found:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=f"Could not find meeting '{meeting_search}' in your calendar.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Get OAuth credentials (following _handle_confirm_edit pattern)
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Please connect your Google Calendar first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Create calendar client
            client = GoogleCalendarClient(access_token=credentials.access_token)

            # Build new description - append doc URL to existing description
            doc_id = meeting_link_service.extract_doc_id_from_url(doc_url)
            existing_description = meeting_result.event.description or ""
            doc_link_text = f"\n\n📄 Linked Document: {doc_url}"
            new_description = existing_description + doc_link_text

            # Create EventUpdateRequest - only update description
            update_request = EventUpdateRequest(description=new_description)

            # Call update_event
            await client.update_event(meeting_result.event.id, update_request)

            logger.info(
                "Document linked to event",
                extra={
                    "user_id": str(user_id)[:8],
                    "event_id": meeting_result.event.id,
                    "doc_id": doc_id,
                }
            )

            # Sprint 5.1.3: Store doc in context for future references ("ese documento", "that doc")
            conversation_context_service.set_last_doc(
                user_id=str(user_id),
                doc_id=doc_id,
                doc_url=doc_url,
                doc_title=meeting_result.event.summary,  # Use event title as doc context
            )

            processing_time = (time.time() - start_time) * 1000

            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                confidence=intent.confidence,
                action="link_doc",
                message=f"✓ Document linked to '{meeting_result.event.summary}'",
                response=f"I've added the document link to your '{meeting_result.event.summary}' event.",
                data={"doc_url": doc_url, "doc_id": doc_id, "event_id": meeting_result.event.id},
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        except Exception as e:
            logger.error(f"Error linking doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error linking document: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_open_doc(
        self,
        request_id: str,
        intent: DocQueryIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """
        Get the document linked to a calendar event.

        Uses find_meeting_with_doc to search for the meeting and get its linked docs.
        Returns the document URL for the client to open.

        Sprint 3.9: If device_name is specified, displays the doc on that device.
        Sprint 4: Moved from IntentService.
        Sprint 5.1.4: Supports anaphoric event references ("that meeting", "esa reunion").
        """
        meeting_search = intent.meeting_search
        meeting_time = intent.meeting_time
        device_name = intent.device_name  # Sprint 3.9: Support device display

        # Sprint 5.1.4: Resolve anaphoric reference from context
        if not meeting_search and not meeting_time and context and context.get("resolved_references"):
            resolved_event = context["resolved_references"].get("event")
            if resolved_event and resolved_event.get("title"):
                meeting_search = resolved_event["title"]
                logger.info(f"[ANAPHORIC_RESOLUTION] Resolved event from context: {meeting_search}")

        processing_time = (time.time() - start_time) * 1000

        # Sprint 3.9: Use conversation context if no meeting specified
        # This handles "is there a doc for this event?" after showing an event
        if not meeting_search and not meeting_time:
            context_title, context_id, context_date = self._get_event_from_context(str(user_id))
            if context_title:
                meeting_search = context_title
                logger.debug(f"Using event from context: {context_title}")
            else:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Please specify which meeting's document you want to open.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

        try:
            # Use meeting search query or time reference
            query = meeting_search or meeting_time

            # Find the meeting and its linked doc
            meeting_result = await meeting_link_service.find_meeting_with_doc(
                query=query,
                user_id=user_id,
                db=db,
            )

            processing_time = (time.time() - start_time) * 1000

            if not meeting_result.found:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=f"Could not find meeting '{query}' in your calendar.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            if not meeting_result.has_linked_doc:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="No document linked to this event.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Build doc URL from doc_id
            doc_url = f"https://docs.google.com/document/d/{meeting_result.doc_id}/edit"

            # Sprint 3.9: If device specified, display doc on device
            if device_name:
                # Get user's devices
                devices = self._get_user_devices(db, user_id)

                if devices:
                    # Find the device
                    device, match_confidence = device_mapper.match(device_name, devices)

                    if device:
                        # Send show_content command with doc URL
                        result = await command_service.show_content(
                            device_id=device.id,
                            url=doc_url,
                            content_type="google_doc",
                        )

                        processing_time = (time.time() - start_time) * 1000

                        # Track the command
                        ai_monitor.track_command(
                            request_id=request_id,
                            device_id=device.id,
                            device_name=device.name,
                            action="show_content",
                            command_id=result.command_id,
                            success=result.success,
                            error=result.error,
                        )

                        if result.success:
                            # Store doc in context for future references
                            self._store_doc_context(
                                str(user_id),
                                meeting_result.doc_id,
                                doc_url,
                                meeting_result.event.summary,
                            )

                            return IntentResult(
                                success=True,
                                intent_type=IntentResultType.DOC_QUERY,
                                confidence=intent.confidence,
                                action="open_doc",
                                device=device,
                                command_sent=True,
                                command_id=result.command_id,
                                message=f"Showing document for '{meeting_result.event.summary}' on {device.name}.",
                                response=f"Document displayed on {device.name}.",
                                data={
                                    "doc_url": doc_url,
                                    "doc_id": meeting_result.doc_id,
                                    "event_title": meeting_result.event.summary,
                                },
                                processing_time_ms=processing_time,
                                request_id=request_id,
                            )
                        else:
                            return IntentResult(
                                success=False,
                                intent_type=IntentResultType.ERROR,
                                message=f"Found doc but failed to send to {device.name}: {result.error}",
                                processing_time_ms=processing_time,
                                request_id=request_id,
                            )
                    else:
                        # Device not found
                        processing_time = (time.time() - start_time) * 1000
                        return IntentResult(
                            success=False,
                            intent_type=IntentResultType.ERROR,
                            message=f"Could not find device '{device_name}'. Try 'list devices' to see available devices.",
                            processing_time_ms=processing_time,
                            request_id=request_id,
                        )

            # No device specified - check for display intent to auto-assign device
            # Sprint 3.9: Auto-select device for display-intent phrases
            display_keywords = ['show', 'display', 'see', 'look', 'put on', 'view', 'lemme']
            original_text = (intent.original_text or "").lower()

            has_display_intent = any(keyword in original_text for keyword in display_keywords)

            if has_display_intent:
                # User wants to SEE it - try to auto-assign device
                devices = self._get_user_devices(db, user_id)
                display_devices = [d for d in devices if d.is_online]

                if len(display_devices) == 1:
                    # Auto-select the only available device
                    device = display_devices[0]
                    logger.info(f"Auto-selected display device: {device.name}")

                    # Send show_content command
                    result = await command_service.show_content(
                        device_id=device.id,
                        url=doc_url,
                        content_type="google_doc",
                    )

                    processing_time = (time.time() - start_time) * 1000

                    # Track the command
                    ai_monitor.track_command(
                        request_id=request_id,
                        device_id=device.id,
                        device_name=device.name,
                        action="show_content",
                        command_id=result.command_id,
                        success=result.success,
                        error=result.error,
                    )

                    if result.success:
                        # Store doc in context
                        self._store_doc_context(
                            str(user_id),
                            meeting_result.doc_id,
                            doc_url,
                            meeting_result.event.summary,
                        )

                        return IntentResult(
                            success=True,
                            intent_type=IntentResultType.DOC_QUERY,
                            confidence=intent.confidence,
                            action="open_doc",
                            device=device,
                            command_sent=True,
                            command_id=result.command_id,
                            message=f"Showing document for '{meeting_result.event.summary}' on {device.name}.",
                            response=f"Document displayed on {device.name}.",
                            data={
                                "doc_url": doc_url,
                                "doc_id": meeting_result.doc_id,
                                "event_title": meeting_result.event.summary,
                            },
                            processing_time_ms=processing_time,
                            request_id=request_id,
                        )
                    else:
                        return IntentResult(
                            success=False,
                            intent_type=IntentResultType.ERROR,
                            message=f"Found doc but failed to send to {device.name}: {result.error}",
                            processing_time_ms=processing_time,
                            request_id=request_id,
                        )
                elif len(display_devices) > 1:
                    # Multiple devices - ask user which one
                    device_names = ", ".join([d.name for d in display_devices])
                    processing_time = (time.time() - start_time) * 1000
                    return IntentResult(
                        success=True,
                        intent_type=IntentResultType.DOC_QUERY,
                        confidence=intent.confidence,
                        action="open_doc",
                        message=f"Found document for '{meeting_result.event.summary}'. Which device should I display it on?",
                        response=f"Available devices: {device_names}. Say 'show on [device name]' to display.",
                        data={
                            "doc_url": doc_url,
                            "doc_id": meeting_result.doc_id,
                            "event_title": meeting_result.event.summary,
                            "available_devices": [d.name for d in display_devices],
                        },
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )

            # No display intent or no devices - just return URL (query mode)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                confidence=intent.confidence,
                action="open_doc",
                message=f"Opening document for '{meeting_result.event.summary}'.",
                response=f"Here's the meeting document: {doc_url}",
                data={
                    "doc_url": doc_url,
                    "doc_id": meeting_result.doc_id,
                    "event_id": meeting_result.event.id,
                    "event_title": meeting_result.event.summary,
                },
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        except Exception as e:
            logger.error(f"Error getting linked doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error opening document: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_read_doc(
        self,
        request_id: str,
        intent: DocQueryIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """
        Read and analyze a Google Doc.

        Uses DocIntelligenceService to process the document with AI.

        Sprint 4: Moved from IntentService.
        Sprint 5.1.4: Anaphoric resolution support
        If intent.doc_url is None, attempts to resolve from context.resolved_references.
        Enables "what does that document say?" to work after referencing a doc.
        """
        doc_url = intent.doc_url
        question = intent.question

        processing_time = (time.time() - start_time) * 1000

        # Sprint 5.1.4: Resolve anaphoric reference if no explicit doc_url
        if not doc_url and context and context.get("resolved_references"):
            resolved_doc = context["resolved_references"].get("document")
            if resolved_doc:
                doc_url = resolved_doc.get("url")
                logger.info(
                    f"[ANAPHORIC_RESOLUTION] Resolved doc from context: {doc_url}"
                )

        if not doc_url:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please provide a Google Docs URL to read.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Invalid Google Docs URL format.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        try:
            # Get OAuth credentials from database
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Google account not connected. Please link your account first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Fetch the document
            doc_id = GoogleDocsClient.extract_doc_id(doc_url)
            docs_client = GoogleDocsClient(access_token=credentials.access_token)
            doc = await docs_client.get_document(doc_id)
            doc_content = doc.to_doc_content()

            # Analyze/summarize the document
            summary_result = await doc_intelligence_service.summarize_document(
                doc_content=doc_content,
                question=question,
            )

            processing_time = (time.time() - start_time) * 1000

            if not summary_result.error:
                # Sprint 5.1.1: Store doc context for future references (DRY - reuse helper)
                self._store_doc_context(
                    user_id=str(user_id),
                    doc_id=doc_id,
                    doc_url=doc_url,
                    doc_title=summary_result.title,
                    doc_content=summary_result.summary,  # Sprint 5.1.1: Include content
                )
                # Store summary in content memory for follow-up requests
                conversation_context_service.set_generated_content(
                    user_id=str(user_id),
                    content=summary_result.summary,
                    content_type="doc_summary",
                    title=summary_result.title,
                )

                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.DOC_QUERY,
                    confidence=intent.confidence,
                    action="read_doc",
                    message=summary_result.summary,
                    response=summary_result.summary,
                    data={
                        "doc_url": doc_url,
                        "title": summary_result.title,
                        "word_count": summary_result.word_count,
                        "model_used": summary_result.model_used,
                    },
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            else:
                error_msg = summary_result.error
                # Handle specific error cases
                if "404" in error_msg or "not found" in error_msg.lower():
                    error_msg = "Document not found. Please check the URL."
                elif "403" in error_msg or "permission" in error_msg.lower():
                    error_msg = "You don't have access to this document."

                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=error_msg,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

        except Exception as e:
            logger.error(f"Error reading doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "Document not found. Please check the URL."
            elif "403" in error_msg or "permission" in error_msg.lower():
                error_msg = "You don't have access to this document."
            else:
                error_msg = f"Error reading document: {error_msg}"
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=error_msg,
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_summarize_meeting_doc(
        self,
        request_id: str,
        intent: DocQueryIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Summarize a document linked to a meeting.

        Finds the meeting by search/time reference, gets its linked doc,
        then uses DocIntelligenceService to generate a summary.

        Sprint 4: Moved from IntentService.
        """
        doc_url = intent.doc_url
        meeting_search = intent.meeting_search
        meeting_time = intent.meeting_time

        processing_time = (time.time() - start_time) * 1000

        # If no doc URL, try to find the meeting's linked doc
        if not doc_url:
            # Sprint 3.9: Use conversation context if no meeting specified
            if not meeting_search and not meeting_time:
                context_title, context_id, context_date = self._get_event_from_context(str(user_id))
                if context_title:
                    meeting_search = context_title
                    logger.debug(f"Using event from context: {context_title}")
                else:
                    return IntentResult(
                        success=False,
                        intent_type=IntentResultType.ERROR,
                        message="Please specify which meeting's document you want to summarize, or provide a Google Docs URL.",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )

            # Find the meeting and its linked doc
            query = meeting_search or meeting_time
            meeting_result = await meeting_link_service.find_meeting_with_doc(
                query=query,
                user_id=user_id,
                db=db,
            )

            if not meeting_result.found:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=f"Could not find meeting '{query}' in your calendar.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            if not meeting_result.has_linked_doc:
                processing_time = (time.time() - start_time) * 1000
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="This meeting doesn't have a linked document.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Build doc URL from doc_id
            doc_url = f"https://docs.google.com/document/d/{meeting_result.doc_id}/edit"

        # Now we have a doc_url, validate and summarize
        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Invalid Google Docs URL format.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        try:
            # Get OAuth credentials from database
            credentials = db.query(OAuthCredential).filter(
                OAuthCredential.user_id == user_id,
                OAuthCredential.provider == "google",
            ).first()

            if not credentials or not credentials.access_token:
                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Google account not connected. Please link your account first.",
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

            # Fetch the document
            doc_id = GoogleDocsClient.extract_doc_id(doc_url)
            docs_client = GoogleDocsClient(access_token=credentials.access_token)
            doc = await docs_client.get_document(doc_id)
            doc_content = doc.to_doc_content()

            # Summarize the document
            summary_result = await doc_intelligence_service.summarize_document(
                doc_content=doc_content,
            )

            processing_time = (time.time() - start_time) * 1000

            if not summary_result.error:
                return IntentResult(
                    success=True,
                    intent_type=IntentResultType.DOC_QUERY,
                    confidence=intent.confidence,
                    action="summarize_meeting_doc",
                    message=summary_result.summary,
                    response=summary_result.summary,
                    data={
                        "doc_url": doc_url,
                        "title": summary_result.title,
                        "word_count": summary_result.word_count,
                        "is_complex": summary_result.is_complex,
                        "model_used": summary_result.model_used,
                    },
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )
            else:
                error_msg = summary_result.error
                if "404" in error_msg or "not found" in error_msg.lower():
                    error_msg = "Document not found. Please check the URL."
                elif "403" in error_msg or "permission" in error_msg.lower():
                    error_msg = "You don't have access to this document."

                return IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message=error_msg,
                    processing_time_ms=processing_time,
                    request_id=request_id,
                )

        except Exception as e:
            logger.error(f"Error summarizing doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "Document not found. Please check the URL."
            elif "403" in error_msg or "permission" in error_msg.lower():
                error_msg = "You don't have access to this document."
            else:
                error_msg = f"Error summarizing document: {error_msg}"
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=error_msg,
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    async def _handle_create_event_from_doc(
        self,
        request_id: str,
        intent: DocQueryIntent,
        user_id: UUID,
        start_time: float,
        db: Session,
    ) -> IntentResult:
        """
        Create a calendar event from document content.

        Sprint 3.9: Extract meeting details from doc and create event.
        Sprint 4: Moved from IntentService.

        Flow:
        1. Fetch and read the document
        2. Extract meeting details using LLM
        3. If missing date/time, ask user for clarification
        4. Create the calendar event
        5. Link the document to the event (in description)
        """
        from datetime import datetime as dt

        doc_url = intent.doc_url

        processing_time = (time.time() - start_time) * 1000

        if not doc_url:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please provide a Google Doc URL to create an event from.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        # Validate and extract doc ID
        if not GoogleDocsClient.validate_doc_url(doc_url):
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="That doesn't look like a valid Google Docs URL.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        doc_id = GoogleDocsClient.extract_doc_id(doc_url)

        # Get credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()

        if not credentials or not credentials.access_token:
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message="Please connect Google to create calendar events.",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        try:
            # Fetch document content
            doc_content = await doc_intelligence_service.get_document_for_user(
                doc_id=doc_id,
                user_id=user_id,
                db=db,
            )
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "Document not found. Please check the URL."
            elif "403" in error_msg or "permission" in error_msg.lower():
                error_msg = "I can't access that document. Please check sharing permissions."
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=error_msg,
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        # Extract meeting details using LLM
        details = await doc_intelligence_service.extract_meeting_details(doc_content)

        if details.error:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Could not extract meeting details: {details.error}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        # Check if we need clarification (missing date/time)
        if details.needs_clarification:
            # Get user timezone for pending event
            try:
                calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
                user_tz = await calendar_client.get_user_timezone()
            except Exception:
                user_tz = "UTC"

            # Store pending event with doc metadata for follow-up
            await pending_event_service.store_pending(
                user_id=str(user_id),
                event_title=details.event_title or doc_content.title,
                event_date=None,  # Missing - user will provide
                event_time=None,  # Missing - user will provide
                duration_minutes=details.duration_minutes or 60,
                location=details.location,
                timezone=user_tz,
                original_text=intent.original_text,
                # Doc metadata
                doc_id=doc_id,
                doc_url=doc_url,
                source="doc",
            )

            missing = " and ".join(details.missing_fields)
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DOC_QUERY,
                confidence=intent.confidence,
                action="create_event_from_doc",
                message=f"I found the document '{doc_content.title}' but couldn't find the {missing}. When should this meeting be scheduled?",
                data={
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "extracted_title": details.event_title,
                    "missing_fields": details.missing_fields,
                    "pending": True,  # Flag to indicate pending event stored
                },
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        # Create the calendar event
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)

            # Get user timezone
            user_tz = await calendar_client.get_user_timezone()
            tz = ZoneInfo(user_tz)

            # Parse date and time
            event_date = dt.strptime(details.event_date, "%Y-%m-%d")
            hour, minute = map(int, details.event_time.split(":"))

            start_dt = event_date.replace(hour=hour, minute=minute, tzinfo=tz)
            end_dt = start_dt + timedelta(minutes=details.duration_minutes)

            # Build description with doc link
            description = details.description or ""
            description += f"\n\n📄 Meeting Document: {doc_url}"

            # Create event
            event = await calendar_client.create_event(
                summary=details.event_title,
                start_datetime=start_dt,
                end_datetime=end_dt,
                description=description,
                location=details.location,
            )

            processing_time = (time.time() - start_time) * 1000

            # Store event in conversation context
            self._store_event_context(str(user_id), event)

            # Format time for response
            time_str = start_dt.strftime("%I:%M %p").lstrip("0")
            date_str = start_dt.strftime("%B %d, %Y")

            return IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                confidence=intent.confidence,
                action="create_event_from_doc",
                message=f"Created event '{details.event_title}' on {date_str} at {time_str}.",
                response=f"I've created the meeting '{details.event_title}' for {date_str} at {time_str} and linked the document.",
                data={
                    "event_id": event.id,
                    "event_title": details.event_title,
                    "event_date": details.event_date,
                    "event_time": details.event_time,
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                },
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        except Exception as e:
            logger.error(f"Failed to create event from doc: {e}")
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Failed to create event: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )
