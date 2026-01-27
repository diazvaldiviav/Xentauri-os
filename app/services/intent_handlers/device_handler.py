"""
Device Handler - Handles device commands and queries.

This handler is responsible for:
- Device command execution (power, input, volume, content display)
- Device status queries (is_online, capabilities)

Sprint US-2.1: Extracted from IntentService
Sprint US-2.3: SystemQuery moved to SystemHandler
Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from uuid import UUID

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import (
    DeviceCommand,
    DeviceQuery,
    SequentialAction,
)
from app.ai.intent.device_mapper import device_mapper
from app.ai.actions.registry import action_registry
from app.ai.monitoring import ai_monitor
from app.services.commands import command_service
from app.models.device import Device
from app.core.config import settings


logger = logging.getLogger("jarvis.services.intent_handlers.device")


class DeviceHandler(IntentHandler):
    """
    Handler for device-related intents.

    Handles:
    - DeviceCommand: Power, volume, input, content display actions
    - DeviceQuery: Device status and capabilities queries

    Note: SystemQuery is handled by SystemHandler (Sprint US-2.3)
    """

    @property
    def handler_name(self) -> str:
        """Return the handler name for logging."""
        return "device"

    @property
    def supported_intent_types(self) -> List[str]:
        """Return list of supported intent types."""
        return ["device_command", "device_query"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The parsed intent object
            context: Handler context

        Returns:
            True if intent is DeviceCommand or DeviceQuery
        """
        return isinstance(intent, (DeviceCommand, DeviceQuery))

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Process the device-related intent and return a result.

        Args:
            intent: The parsed intent object (DeviceCommand or DeviceQuery)
            context: Handler context with user, devices, etc.

        Returns:
            IntentResult with processing outcome
        """
        self._log_entry(intent, context)

        try:
            if isinstance(intent, DeviceCommand):
                result = await self._handle_device_command(intent, context)
            elif isinstance(intent, DeviceQuery):
                result = await self._handle_device_query(intent, context)
            else:
                processing_time = (time.time() - context.start_time) * 1000
                result = IntentResult(
                    success=False,
                    intent_type=IntentResultType.ERROR,
                    message="Unsupported intent type for DeviceHandler",
                    processing_time_ms=processing_time,
                    request_id=context.request_id,
                )

            self._log_exit(context, success=result.success, processing_time_ms=result.processing_time_ms)
            return result

        except Exception as e:
            processing_time = (time.time() - context.start_time) * 1000
            logger.error(f"[{context.request_id}] DeviceHandler error: {e}", exc_info=True)
            return IntentResult(
                success=False,
                intent_type=IntentResultType.ERROR,
                message=f"Error processing device intent: {str(e)}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

    # -----------------------------------------------------------------------
    # DEVICE COMMAND HANDLER
    # -----------------------------------------------------------------------

    async def _handle_device_command(
        self,
        intent: DeviceCommand,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle device command intents.

        Args:
            intent: DeviceCommand intent with action and parameters
            context: Handler context

        Returns:
            IntentResult with command execution outcome
        """
        # Match device
        if context.forced_device_id:
            device = next((d for d in context.devices if d.id == context.forced_device_id), None)
            match_confidence = 1.0
        else:
            device, match_confidence = device_mapper.match(intent.device_name, context.devices)

        if not device:
            processing_time = (time.time() - context.start_time) * 1000
            alternatives = device_mapper.match_all(intent.device_name, context.devices, limit=3)
            suggestion = ""
            if alternatives:
                names = [f'"{d.name}"' for d, _ in alternatives]
                suggestion = f" Did you mean: {', '.join(names)}?"

            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=intent.confidence,
                action=self._get_action_value(intent.action),
                message=f"I couldn't find a device matching '{intent.device_name}'.{suggestion}",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        # Check if online
        if not device.is_online:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=intent.confidence,
                device=device,
                action=self._get_action_value(intent.action),
                message=f"'{device.name}' is currently offline.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        action = self._get_action_value(intent.action) or "status"

        # Content display actions
        if action_registry.is_content_action(action):
            primary_result = await self._execute_content_action(
                request_id=context.request_id,
                device=device,
                action=action,
                user_id=context.user_id,
                parameters=intent.parameters,
                confidence=intent.confidence,
                start_time=context.start_time,
                require_feedback=context.require_feedback,
            )
        else:
            # Standard device commands
            primary_result = await self._execute_device_command(
                request_id=context.request_id,
                device=device,
                action=action,
                parameters=intent.parameters,
                confidence=intent.confidence,
                start_time=context.start_time,
            )

        # Sprint 4.0.3: Process sequential actions if present
        if intent.sequential_actions and primary_result.success:
            primary_result = await self._execute_sequential_actions(
                primary_result=primary_result,
                sequential_actions=intent.sequential_actions,
                devices=context.devices,
                user_id=context.user_id,
                primary_device=device,
                start_time=context.start_time,
                require_feedback=context.require_feedback,
            )

        return primary_result

    # -----------------------------------------------------------------------
    # DEVICE QUERY HANDLER
    # -----------------------------------------------------------------------

    async def _handle_device_query(
        self,
        intent: DeviceQuery,
        context: HandlerContext,
    ) -> IntentResult:
        """
        Handle device query intents.

        Args:
            intent: DeviceQuery intent with query type
            context: Handler context

        Returns:
            IntentResult with device status information
        """
        device, _ = device_mapper.match(intent.device_name, context.devices)

        if not device:
            processing_time = (time.time() - context.start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_QUERY,
                confidence=intent.confidence,
                message=f"I couldn't find a device matching '{intent.device_name}'.",
                processing_time_ms=processing_time,
                request_id=context.request_id,
            )

        processing_time = (time.time() - context.start_time) * 1000
        action = self._get_action_value(intent.action) or "status"

        if action in ("status", "is_online"):
            status_str = "online and ready" if device.is_online else "currently offline"
            message = f"'{device.name}' is {status_str}."
        elif action == "capabilities":
            caps = device.capabilities or {}
            if caps:
                cap_list = ", ".join(caps.keys())
                message = f"'{device.name}' supports: {cap_list}."
            else:
                message = f"'{device.name}' capabilities are not yet known."
        else:
            message = f"'{device.name}' - Online: {device.is_online}"

        return IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_QUERY,
            confidence=intent.confidence,
            device=device,
            action=action,
            message=message,
            processing_time_ms=processing_time,
            request_id=context.request_id,
        )

    # -----------------------------------------------------------------------
    # CONTENT ACTION EXECUTION
    # -----------------------------------------------------------------------

    async def _execute_content_action(
        self,
        request_id: str,
        device: Device,
        action: str,
        user_id: UUID,
        parameters: Optional[Dict],
        confidence: float,
        start_time: float,
        require_feedback: bool = False,
    ) -> IntentResult:
        """
        Execute content display actions.

        Args:
            request_id: Unique request identifier
            device: Target device
            action: Action to execute (show_calendar, show_content, clear_content)
            user_id: User's UUID
            parameters: Action parameters
            confidence: AI confidence score
            start_time: Start time for latency tracking
            require_feedback: Whether human feedback mode is enabled

        Returns:
            IntentResult with execution outcome
        """
        from app.services.content_token import content_token_service

        if action == "clear_content":
            result = await command_service.clear_content(device.id)
        else:
            # Sprint 9: Check for custom_layout content type -> route to Scene Graph
            content_type = (parameters or {}).get("content_type", "url")
            logger.info(f"[{request_id}] _execute_content_action: action={action}, content_type={content_type}, params={parameters}")

            if content_type == "custom_layout":
                # Route to Scene Graph for custom HTML generation (games, quizzes, etc.)
                return await self._execute_custom_layout_action(
                    request_id=request_id,
                    device=device,
                    user_id=user_id,
                    parameters=parameters,
                    confidence=confidence,
                    start_time=start_time,
                    require_feedback=require_feedback,
                )

            content_token = content_token_service.generate(user_id, content_type="calendar")

            if action == "show_calendar":
                url = f"/cloud/calendar?token={content_token}"
                if parameters and "date" in parameters:
                    url += f"&date={parameters['date']}"
                # Sprint 3.7: Add search parameter with URL encoding
                if parameters and "search" in parameters:
                    search_encoded = quote(str(parameters['search']), safe='')
                    url += f"&search={search_encoded}"
                content_type = "calendar"
            elif action == "show_content":
                base_url = (parameters or {}).get("url", "/cloud/calendar")
                if base_url.startswith("/cloud/"):
                    separator = "&" if "?" in base_url else "?"
                    url = f"{base_url}{separator}token={content_token}"
                    if parameters and "date" in parameters:
                        url += f"&date={parameters['date']}"
                    # Sprint 3.7: Add search parameter with URL encoding
                    if parameters and "search" in parameters:
                        search_encoded = quote(str(parameters['search']), safe='')
                        url += f"&search={search_encoded}"
                else:
                    url = base_url
                content_type = (parameters or {}).get("content_type", "url")
            else:
                url = f"/cloud/calendar?token={content_token}"
                content_type = "url"

            result = await command_service.show_content(
                device_id=device.id,
                url=url,
                content_type=content_type,
            )

        processing_time = (time.time() - start_time) * 1000

        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )

        if result.success:
            date = parameters.get("date") if parameters else None
            search = parameters.get("search") if parameters else None
            message = self._build_content_message(action, device.name, date, search)
        else:
            message = f"Failed: {result.error}"

        return IntentResult(
            success=result.success,
            intent_type=IntentResultType.DEVICE_COMMAND,
            confidence=confidence,
            device=device,
            action=action,
            parameters=parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )

    # -----------------------------------------------------------------------
    # CUSTOM LAYOUT ACTION EXECUTION
    # -----------------------------------------------------------------------

    async def _execute_custom_layout_action(
        self,
        request_id: str,
        device: Device,
        user_id: UUID,
        parameters: Optional[Dict],
        confidence: float,
        start_time: float,
        require_feedback: bool = False,
    ) -> IntentResult:
        """
        Execute custom layout generation via Scene Graph.

        Sprint 9: Routes content_type="custom_layout" requests to the Scene Graph
        system for HTML generation by Opus 4.5.

        Args:
            request_id: Unique request identifier
            device: Target device for display
            user_id: User's UUID
            parameters: Must contain 'layout_description' with the user's request
            confidence: AI confidence score
            start_time: Start time for latency tracking
            require_feedback: Whether human feedback mode is enabled

        Returns:
            IntentResult with layout generation outcome
        """
        from app.ai.scene.custom_layout import custom_layout_service
        from app.ai.scene import scene_service
        from app.services.websocket_manager import connection_manager

        layout_description = (parameters or {}).get("layout_description", "")

        # Log human_feedback_mode propagation
        logger.info(
            f"[{request_id}] _execute_custom_layout_action: "
            f"human_feedback_mode={require_feedback}"
        )

        if not layout_description:
            processing_time = (time.time() - start_time) * 1000
            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=confidence,
                device=device,
                action="show_content",
                parameters=parameters,
                command_sent=False,
                message="Missing layout_description for custom layout",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        logger.info(f"[{request_id}] Routing to Scene Graph for custom layout: {layout_description[:100]}...")

        try:
            # Send loading indicator to device
            await connection_manager.send_command(
                device_id=device.id,
                command_type="loading_start",
                parameters={"message": "Generando contenido...", "phase": 1},
            )

            # Generate content data with Gemini
            content_data = await scene_service.generate_content_data(
                user_request=layout_description,
            )

            if content_data and settings.CUSTOM_LAYOUT_ENABLED:
                # Loading Phase 2
                await connection_manager.send_command(
                    device_id=device.id,
                    command_type="loading_start",
                    parameters={"message": "Disenando experiencia...", "phase": 2},
                )

                # Log validation type
                validation_type = "JS-only" if require_feedback else "Full CSS+JS"
                logger.info(f"[{request_id}] Custom layout validation type: {validation_type}")

                # Generate HTML with visual validation
                layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                    content_data=content_data,
                    user_request=layout_description,
                    layout_type=content_data.get("content_type"),
                    human_feedback_mode=require_feedback,
                )

                if layout_result.success and layout_result.html:
                    # Log result with timing
                    logger.info(
                        f"[{request_id}] Custom layout generated: "
                        f"latency={layout_result.latency_ms:.0f}ms, "
                        f"human_feedback_mode={require_feedback}, "
                        f"has_js_errors={bool(getattr(layout_result, 'js_errors', None))}"
                    )

                    custom_layout = layout_result.html
                    scene_dict = {"scene_id": request_id, "direct_flow": True}

                    # Send to device
                    result = await command_service.display_scene(
                        device_id=device.id,
                        scene=scene_dict,
                        custom_layout=custom_layout,
                    )

                    processing_time = (time.time() - start_time) * 1000

                    ai_monitor.track_command(
                        request_id=request_id,
                        device_id=device.id,
                        device_name=device.name,
                        action="display_scene",
                        command_id=result.command_id,
                        success=result.success,
                        error=result.error,
                    )

                    return IntentResult(
                        success=result.success,
                        intent_type=IntentResultType.DISPLAY_CONTENT,
                        confidence=confidence,
                        device=device,
                        action="display_scene",
                        parameters=parameters,
                        command_sent=result.success,
                        command_id=result.command_id if result.success else None,
                        message=f"Displaying custom content on {device.name}",
                        processing_time_ms=processing_time,
                        request_id=request_id,
                    )

            # Fallback: Layout generation failed
            processing_time = (time.time() - start_time) * 1000
            error_msg = "Content generation failed"
            if content_data is None:
                error_msg = "Failed to generate content data"
            elif 'layout_result' in dir() and layout_result:
                error_msg = layout_result.error or "Unknown layout error"
            logger.warning(f"[{request_id}] Custom layout failed: {error_msg}")

            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=confidence,
                device=device,
                action="show_content",
                parameters=parameters,
                command_sent=False,
                message=f"Failed to generate custom layout: {error_msg}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"[{request_id}] Custom layout error: {e}", exc_info=True)

            return IntentResult(
                success=False,
                intent_type=IntentResultType.DEVICE_COMMAND,
                confidence=confidence,
                device=device,
                action="show_content",
                parameters=parameters,
                command_sent=False,
                message=f"Error generating custom layout: {str(e)}",
                processing_time_ms=processing_time,
                request_id=request_id,
            )

    # -----------------------------------------------------------------------
    # DEVICE COMMAND EXECUTION
    # -----------------------------------------------------------------------

    async def _execute_device_command(
        self,
        request_id: str,
        device: Device,
        action: str,
        parameters: Optional[Dict],
        confidence: float,
        start_time: float,
    ) -> IntentResult:
        """
        Execute standard device commands.

        Args:
            request_id: Unique request identifier
            device: Target device
            action: Command action (power_on, volume_up, etc.)
            parameters: Command parameters
            confidence: AI confidence score
            start_time: Start time for latency tracking

        Returns:
            IntentResult with command execution outcome
        """
        result = await command_service.send_command(
            device_id=device.id,
            command_type=action,
            parameters=parameters,
        )

        processing_time = (time.time() - start_time) * 1000

        ai_monitor.track_command(
            request_id=request_id,
            device_id=device.id,
            device_name=device.name,
            action=action,
            command_id=result.command_id,
            success=result.success,
            error=result.error,
        )

        if result.success:
            message = self._build_success_message(action, device.name, parameters)
        else:
            message = f"Failed: {result.error}"

        return IntentResult(
            success=result.success,
            intent_type=IntentResultType.DEVICE_COMMAND,
            confidence=confidence,
            device=device,
            action=action,
            parameters=parameters,
            command_sent=result.success,
            command_id=result.command_id if result.success else None,
            message=message,
            processing_time_ms=processing_time,
            request_id=request_id,
        )

    # -----------------------------------------------------------------------
    # SEQUENTIAL ACTIONS (Sprint 4.0.3 - Multi-Action Support)
    # -----------------------------------------------------------------------

    async def _execute_sequential_actions(
        self,
        primary_result: IntentResult,
        sequential_actions: List[SequentialAction],
        devices: List[Device],
        user_id: UUID,
        primary_device: Device,
        start_time: float,
        require_feedback: bool = False,
    ) -> IntentResult:
        """
        Execute sequential actions after a primary action.

        Sprint 4.0.3: Allows users to chain multiple actions in a single request,
        e.g., "clear the screen AND show my calendar".

        Args:
            primary_result: Result from the primary action
            sequential_actions: List of additional actions to execute
            devices: Available devices for the user
            user_id: User's UUID
            primary_device: The device from the primary action
            start_time: Start time for total processing time calculation
            require_feedback: Whether human feedback mode is enabled

        Returns:
            Updated IntentResult with all actions executed
        """
        actions_executed = [
            {
                "action": primary_result.action,
                "success": primary_result.success,
                "command_id": primary_result.command_id,
                "device": primary_result.device.name if primary_result.device else None,
            }
        ]

        all_messages = [primary_result.message] if primary_result.message else []
        total_commands_sent = 1 if primary_result.command_sent else 0
        all_success = primary_result.success

        logger.info(
            f"Executing {len(sequential_actions)} sequential actions after '{primary_result.action}'"
        )

        for seq_action in sequential_actions:
            try:
                # Resolve device: use specified device_name or inherit from primary
                target_device = primary_device
                if seq_action.device_name:
                    matched_device, _ = device_mapper.match(seq_action.device_name, devices)
                    if matched_device:
                        target_device = matched_device
                    else:
                        logger.warning(
                            f"Device '{seq_action.device_name}' not found for sequential action, "
                            f"using primary device '{primary_device.name}'"
                        )

                action_name = seq_action.action
                params = seq_action.parameters or {}

                # Execute based on action type
                if action_registry.is_content_action(action_name):
                    action_result = await self._execute_content_action(
                        request_id=primary_result.request_id,
                        device=target_device,
                        action=action_name,
                        user_id=user_id,
                        parameters=params,
                        confidence=primary_result.confidence,
                        start_time=start_time,
                        require_feedback=require_feedback,
                    )
                else:
                    action_result = await self._execute_device_command(
                        request_id=primary_result.request_id,
                        device=target_device,
                        action=action_name,
                        parameters=params,
                        confidence=primary_result.confidence,
                        start_time=start_time,
                    )

                actions_executed.append({
                    "action": action_name,
                    "success": action_result.success,
                    "command_id": action_result.command_id,
                    "device": target_device.name,
                })

                if action_result.message:
                    all_messages.append(action_result.message)

                if action_result.command_sent:
                    total_commands_sent += 1

                if not action_result.success:
                    all_success = False
                    logger.warning(
                        f"Sequential action '{action_name}' failed: {action_result.message}"
                    )
                else:
                    logger.info(f"Sequential action '{action_name}' succeeded on '{target_device.name}'")

            except Exception as e:
                logger.error(f"Error executing sequential action '{seq_action.action}': {e}")
                actions_executed.append({
                    "action": seq_action.action,
                    "success": False,
                    "error": str(e),
                })
                all_messages.append(f"Failed: {seq_action.action} - {str(e)}")
                all_success = False

        # Build combined response
        processing_time = (time.time() - start_time) * 1000
        combined_message = " -> ".join(all_messages) if all_messages else "Actions executed"

        # Update primary result with combined info
        return IntentResult(
            success=all_success,
            intent_type=primary_result.intent_type,
            confidence=primary_result.confidence,
            device=primary_result.device,
            action=primary_result.action,
            parameters=primary_result.parameters,
            data={
                **(primary_result.data or {}),
                "actions_executed": actions_executed,
                "commands_sent": total_commands_sent,
            },
            command_sent=total_commands_sent > 0,
            command_id=primary_result.command_id,  # Primary command ID
            message=combined_message,
            processing_time_ms=processing_time,
            request_id=primary_result.request_id,
        )

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

    @staticmethod
    def _build_success_message(action: str, device_name: str, parameters: Optional[Dict]) -> str:
        """
        Build human-readable success message.

        Args:
            action: The action that was executed
            device_name: Name of the target device
            parameters: Action parameters

        Returns:
            Human-readable success message
        """
        messages = {
            "power_on": f"Turning on {device_name}",
            "power_off": f"Turning off {device_name}",
            "volume_up": f"Increasing volume on {device_name}",
            "volume_down": f"Decreasing volume on {device_name}",
            "mute": f"Muting {device_name}",
            "unmute": f"Unmuting {device_name}",
        }

        if action in messages:
            return messages[action]

        if action == "set_input" and parameters:
            input_name = parameters.get("input") or parameters.get("app") or parameters.get("source")
            if input_name:
                return f"Switching {device_name} to {input_name}"

        if action == "volume_set" and parameters:
            level = parameters.get("level", "?")
            return f"Setting volume to {level}% on {device_name}"

        return f"Command sent to {device_name}"

    @staticmethod
    def _build_content_message(
        action: str,
        device_name: str,
        date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> str:
        """
        Build success message for content actions.

        Args:
            action: Content action (show_calendar, show_content, clear_content)
            device_name: Name of the target device
            date: Optional date filter
            search: Optional search filter

        Returns:
            Human-readable success message
        """
        if action == "show_calendar":
            # Sprint 3.7: Include search context in message
            if search and date:
                return f"Displaying '{search}' events for {date} on {device_name}"
            elif search:
                return f"Displaying '{search}' events on {device_name}"
            elif date:
                return f"Displaying calendar for {date} on {device_name}"
            return f"Displaying calendar on {device_name}"
        elif action == "show_content":
            if search and date:
                return f"Displaying '{search}' content for {date} on {device_name}"
            elif search:
                return f"Displaying '{search}' content on {device_name}"
            elif date:
                return f"Displaying content for {date} on {device_name}"
            return f"Displaying content on {device_name}"
        elif action == "clear_content":
            return f"Cleared display on {device_name}"
        return f"Content action completed on {device_name}"
