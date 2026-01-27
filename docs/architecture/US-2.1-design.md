# Architecture Design: US-2.1 - Extract DeviceHandler

## Overview

This architecture design extracts the device-related logic from `IntentService` (~6500 lines) into a focused `DeviceHandler` class (~350 lines). The DeviceHandler implements the `IntentHandler` ABC and handles `DeviceCommand`, `DeviceQuery`, and `SystemQuery` intents.

## Class Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          IntentService                                       │
│                     (Orchestrator - delegates to handlers)                  │
│                                                                             │
│  process()                                                                  │
│   └──► _handle_simple_task_internal()                                       │
│         └──► if isinstance(intent, DeviceCommand|DeviceQuery|SystemQuery):  │
│               handler = DeviceHandler()                                     │
│               context = HandlerContext(...)                                 │
│               return await handler.handle(intent, context)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DeviceHandler                                     │
│               app/services/intent_handlers/device_handler.py                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Properties (from IntentHandler ABC):                                       │
│  ├── handler_name: str = "device"                                           │
│  └── supported_intent_types: List[str]                                      │
│                                                                             │
│  Methods (from IntentHandler ABC):                                          │
│  ├── can_handle(intent, context) -> bool                                    │
│  └── handle(intent, context) -> IntentResult                                │
│                                                                             │
│  Private Methods (extracted from IntentService):                            │
│  ├── _handle_device_command(intent, context) -> IntentResult                │
│  ├── _handle_device_query(intent, context) -> IntentResult                  │
│  ├── _handle_system_query(intent, context) -> IntentResult                  │
│  ├── _execute_content_action(...) -> IntentResult                           │
│  ├── _execute_custom_layout_action(...) -> IntentResult                     │
│  ├── _execute_device_command(...) -> IntentResult                           │
│  ├── _execute_sequential_actions(...) -> IntentResult                       │
│  ├── @staticmethod _get_action_value(action) -> Optional[str]               │
│  ├── @staticmethod _build_success_message(...) -> str                       │
│  └── @staticmethod _build_content_message(...) -> str                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DeviceHandler Implementation

**Location:** `app/services/intent_handlers/device_handler.py`

```python
"""
Device Handler - Handles device commands, queries, and system queries.

This handler is responsible for:
- Device command execution (power, input, volume, content display)
- Device status queries (is_online, capabilities)
- System queries (list_devices, help)

Sprint US-2.1: Extracted from IntentService
Design Pattern: Strategy Pattern - implements IntentHandler ABC
"""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.services.intent_handlers.base import IntentHandler, HandlerContext
from app.services.intent_service import IntentResult, IntentResultType
from app.ai.intent.schemas import (
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
    ActionType,
    SequentialAction,
)
from app.ai.intent.device_mapper import device_mapper
from app.ai.actions.registry import action_registry
from app.ai.monitoring import ai_monitor
from app.services.commands import command_service
from app.models.device import Device


logger = logging.getLogger("jarvis.services.intent_handlers.device")


class DeviceHandler(IntentHandler):
    """Handler for device-related intents."""

    @property
    def handler_name(self) -> str:
        return "device"

    @property
    def supported_intent_types(self) -> List[str]:
        return ["device_command", "device_query", "system_query"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        return isinstance(intent, (DeviceCommand, DeviceQuery, SystemQuery))

    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> IntentResult:
        self._log_entry(intent, context)

        try:
            if isinstance(intent, DeviceCommand):
                result = await self._handle_device_command(intent, context)
            elif isinstance(intent, DeviceQuery):
                result = await self._handle_device_query(intent, context)
            elif isinstance(intent, SystemQuery):
                result = await self._handle_system_query(intent, context)
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

    # Private methods extracted from IntentService:
    # - _handle_device_command
    # - _handle_device_query
    # - _handle_system_query
    # - _execute_content_action
    # - _execute_custom_layout_action
    # - _execute_device_command
    # - _execute_sequential_actions
    # - _get_action_value (static)
    # - _build_success_message (static)
    # - _build_content_message (static)
```

---

## Integration Pattern with IntentService

### BEFORE (Current)

```python
# app/services/intent_service.py
async def _handle_simple_task_internal(self, ...):
    if isinstance(intent, DeviceCommand):
        return await self._handle_device_command(...)
    elif isinstance(intent, DeviceQuery):
        return await self._handle_device_query(...)
    elif isinstance(intent, SystemQuery):
        return await self._handle_system_query(...)
```

### AFTER (Delegation)

```python
# app/services/intent_service.py
from app.services.intent_handlers.device_handler import DeviceHandler

class IntentService:
    def __init__(self):
        self._device_handler = DeviceHandler()

    async def _handle_simple_task_internal(self, ...):
        if isinstance(intent, (DeviceCommand, DeviceQuery, SystemQuery)):
            context = HandlerContext(
                user_id=user_id,
                request_id=request_id,
                devices=devices,
                db=db,
                start_time=start_time,
                require_feedback=self._require_feedback,
            )
            if device_id:
                context.forced_device_id = device_id
            return await self._device_handler.handle(intent, context)
```

---

## Implementation Order

| Step | Task | File |
|------|------|------|
| 1 | Create DeviceHandler class with full implementation | `app/services/intent_handlers/device_handler.py` |
| 2 | Update `__init__.py` to export DeviceHandler | `app/services/intent_handlers/__init__.py` |
| 3 | Create unit tests for DeviceHandler | `tests/test_device_handler.py` |
| 4 | Run tests to verify DeviceHandler works | `pytest tests/test_device_handler.py -v` |
| 5 | Modify IntentService to delegate | `app/services/intent_service.py` |
| 6 | Run full test suite | `pytest tests/ -v` |

---

## Methods to Extract from IntentService

| Method | Purpose |
|--------|---------|
| `_handle_device_command` | Handle DeviceCommand intents |
| `_handle_device_query` | Handle DeviceQuery intents |
| `_handle_system_query` | Handle SystemQuery intents |
| `_execute_content_action` | Execute content display actions |
| `_execute_custom_layout_action` | Execute custom HTML generation |
| `_execute_device_command` | Execute standard device commands |
| `_execute_sequential_actions` | Execute multi-action chains |
| `_get_action_value` | Extract action value from enum |
| `_build_success_message` | Build human-readable messages |
| `_build_content_message` | Build content action messages |

---

## Dependencies

| Service | Purpose |
|---------|---------|
| `device_mapper` | Match device names to Device objects |
| `command_service` | Send commands to devices |
| `action_registry` | Detect content actions |
| `ai_monitor` | Telemetry tracking |
| `content_token_service` | Generate calendar tokens |
| `custom_layout_service` | Generate custom HTML |
| `gemini_provider` | System query responses |

---

## AC-to-Component Mapping

| AC | Implementation | Test |
|----|----------------|------|
| AC-1 | `DeviceHandler` class with all methods | `test_device_handler.py::TestDeviceHandlerInterface` |
| AC-2 | Modified `_handle_simple_task_internal()` | `test_device_handler.py::TestIntentServiceDelegation` |
| AC-3 | No behavioral changes | `pytest tests/ -v` (679+ tests) |
| AC-4 | Tests with mocked services | `test_device_handler.py` |

---

*Document created: 2026-01-27*
*Story: US-2.1 - Extract DeviceHandler*
