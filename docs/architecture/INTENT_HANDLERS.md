# Intent Handler Architecture

## Table of Contents
1. [Overview](#1-overview)
2. [Architecture Diagrams](#2-architecture-diagrams)
3. [Migration Plan](#3-migration-plan)
4. [Dependency Injection Decision](#4-dependency-injection-decision)
5. [Handler Interface Reference](#5-handler-interface-reference)

---

## 1. Overview

The Intent Handler Architecture refactors the monolithic `IntentService` (~6500 lines) into a collection of focused, single-responsibility handler classes using the **Strategy Pattern**.

### Goals
- **Maintainability:** Each handler < 500 lines
- **Testability:** Handlers mockable in isolation
- **Extensibility:** Add new handlers without modifying IntentService
- **Type Safety:** Full type hints, no `Any` abuse

### Current State
```
IntentService: 6507 lines
├── 27 _handle_* methods
├── 15 _execute_* methods
├── 12 _build_* helper methods
└── Mixed responsibilities (parsing, routing, execution)
```

### Target State
```
IntentService: ~500 lines (orchestrator only)
├── Handler registration
├── Handler routing
└── Result aggregation

Handlers: 5-7 focused classes
├── DeviceHandler: ~300 lines
├── CalendarHandler: ~800 lines
├── ConversationHandler: ~200 lines
├── DisplayContentHandler: ~600 lines
├── DocumentHandler: ~400 lines
└── ComplexTaskHandler: ~500 lines
```

---

## 2. Architecture Diagrams

### 2.1 BEFORE: Current Monolithic Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              POST /intent                                    │
│                           (routers/commands.py)                              │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                    IntentService (~6500 lines)                              │
│                    app/services/intent_service.py                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        process()                                     │    │
│  │  - Get devices                                                       │    │
│  │  - Build context                                                     │    │
│  │  - Analyze complexity (AI Router)                                    │    │
│  │  - Route to handler method                                           │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                           │
│     ┌───────────────────────────┼───────────────────────────────┐           │
│     │           │               │               │               │           │
│     ▼           ▼               ▼               ▼               ▼           │
│  ┌──────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────┐      │
│  │Device│  │Calendar  │  │Conversation│  │ Display  │  │  Document   │      │
│  │~150  │  │~800 lines│  │~220 lines  │  │~615 lines│  │~1320 lines  │      │
│  │lines │  │          │  │            │  │          │  │             │      │
│  └──────┘  └──────────┘  └────────────┘  └──────────┘  └─────────────┘      │
│                                                                             │
│  Problems:                                                                  │
│  ├─ Single 6500-line file                                                   │
│  ├─ Difficult to test individual handlers                                   │
│  ├─ Shared state via self._require_feedback                                 │
│  ├─ Hard to add new intent types                                            │
│  └─ Circular dependency risk with imports                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 AFTER: Handler-Based Architecture (Strategy Pattern)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              POST /intent                                    │
│                           (routers/commands.py)                              │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IntentService (~500 lines)                               │
│                    ORCHESTRATOR ONLY                                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  process()                                                           │    │
│  │  1. Build HandlerContext                                             │    │
│  │  2. Parse intent via intent_parser                                   │    │
│  │  3. Find handler via HandlerRegistry.get_handler(intent)             │    │
│  │  4. Execute: handler.handle(intent, context)                         │    │
│  │  5. Return IntentResult                                              │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                           │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HandlerRegistry                                     │
│                   app/services/intent_handlers/registry.py                  │
│                                                                             │
│  handlers: Dict[str, IntentHandler] = {                                     │
│      "device_command": DeviceHandler(),                                     │
│      "calendar_query": CalendarHandler(),                                   │
│      "conversation": ConversationHandler(),                                 │
│      ...                                                                    │
│  }                                                                          │
│                                                                             │
│  def get_handler(intent_type: str) -> Optional[IntentHandler]               │
│  def register(handler: IntentHandler) -> None                               │
│                                                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐
│  DeviceHandler  │    │ CalendarHandler │    │ ConversationHandler     │
│  (~300 lines)   │    │ (~800 lines)    │    │ (~200 lines)            │
│                 │    │                 │    │                         │
│ can_handle()    │    │ can_handle()    │    │ can_handle()            │
│ handle()        │    │ handle()        │    │ handle()                │
│                 │    │                 │    │                         │
│ Handles:        │    │ Handles:        │    │ Handles:                │
│ - device_cmd    │    │ - calendar_qry  │    │ - conversation          │
│ - device_qry    │    │ - calendar_crt  │    │ - clarification         │
│ - system_qry    │    │ - calendar_edit │    │                         │
└─────────────────┘    └─────────────────┘    └─────────────────────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HandlerContext                                    │
│                     (Shared Immutable Context)                              │
│                                                                             │
│  @dataclass(frozen=True)                                                    │
│  class HandlerContext:                                                      │
│      user_id: UUID                                                          │
│      request_id: str                                                        │
│      devices: List[Device]                                                  │
│      db: Session                                                            │
│      require_feedback: bool                                                 │
│      resolved_references: Dict[str, Any]                                    │
│      conversation_history: Optional[str]                                    │
│      pending_operation: Optional[Dict[str, Any]]                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Data Flow Diagram

```
User Request: "Show my calendar on the TV"
                    │
                    ▼
┌───────────────────────────────────────┐
│ 1. IntentService.process()            │
│    - Creates HandlerContext           │
│    - Calls intent_parser              │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│ 2. intent_parser.create_parsed_cmd()  │
│    - Returns CalendarQueryIntent      │
│    - intent_type = "calendar_query"   │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│ 3. HandlerRegistry.get_handler()      │
│    - Looks up "calendar_query"        │
│    - Returns CalendarHandler          │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│ 4. CalendarHandler.can_handle()       │
│    - Validates it can process         │
│    - Returns True                     │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│ 5. CalendarHandler.handle()           │
│    - Fetches calendar data            │
│    - Generates display content        │
│    - Returns IntentResult             │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│ 6. IntentService returns result       │
│    - Logs metrics                     │
│    - Returns to router                │
└───────────────────────────────────────┘
```

---

## 3. Migration Plan

### 3.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MIGRATION TIMELINE                                   │
│                                                                             │
│  Phase 1 ─────► Phase 2 ─────► Phase 3 ─────► Phase 4 ─────► Phase 5       │
│  (Sprint 1)    (Sprint 2)     (Sprint 3)     (Sprint 4)     (Sprint 5)     │
│                                                                             │
│  Create        Extract        Extract        Extract        Extract         │
│  Infra         Conversation   Device         Calendar       Display/Doc     │
│                                                                             │
│  Risk: LOW     Risk: LOW      Risk: MEDIUM   Risk: HIGH     Risk: HIGH      │
│                                                                             │
│  └── Phase 6 ─────► Phase 7                                                 │
│      (Sprint 6)     (Sprint 7)                                              │
│                                                                             │
│      Extract        Cleanup                                                 │
│      ComplexTask    IntentService                                           │
│                                                                             │
│      Risk: HIGH     Risk: MEDIUM                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Phase Details

#### Phase 1: Create Infrastructure (THIS STORY)
**Status:** Design Only
**Risk:** LOW

**Deliverables:**
- `app/services/intent_handlers/__init__.py`
- `app/services/intent_handlers/base.py`
- `docs/architecture/INTENT_HANDLERS.md`

**Testing Strategy:**
- Import test: `from app.services.intent_handlers import IntentHandler`
- No functional tests (design story)

**Rollback:**
- Delete the `intent_handlers/` folder
- No code depends on it yet

---

#### Phase 2: Extract ConversationHandler
**Risk:** LOW - Simplest handler, minimal dependencies

**What moves:**
```python
# FROM intent_service.py (lines 1553-1750)
_handle_conversation()
_detect_content_type()
_extract_content_title()

# TO intent_handlers/conversation_handler.py
class ConversationHandler(IntentHandler):
    async def handle(self, intent, context) -> IntentResult
```

**Dependencies:**
- `gemini_provider`
- `conversation_context_service`
- `build_unified_context()`

**Testing Strategy:**
1. Unit tests for ConversationHandler
2. Integration test: conversation intent end-to-end
3. Regression: all existing conversation tests pass

**Rollback:**
1. Revert `conversation_handler.py`
2. Restore `_handle_conversation()` in intent_service.py
3. Update registry to not include ConversationHandler

---

#### Phase 3: Extract DeviceHandler
**Risk:** MEDIUM - Core functionality, heavily used

**What moves:**
```python
# FROM intent_service.py (lines 514-650)
_handle_device_command()
_handle_device_query()
_handle_system_query()
_execute_device_command()
_execute_content_action()

# TO intent_handlers/device_handler.py
class DeviceHandler(IntentHandler):
    async def handle(self, intent, context) -> IntentResult
```

**Dependencies:**
- `device_mapper`
- `command_service`
- `action_registry`

**Testing Strategy:**
1. Unit tests for DeviceHandler with mocked command_service
2. Integration tests for device commands
3. E2E test: "Turn on the TV" flow

**Rollback:**
1. Feature flag: `DEVICE_HANDLER_ENABLED=false`
2. IntentService falls back to inline methods

---

#### Phase 4: Extract CalendarHandler
**Risk:** HIGH - Complex logic, many sub-handlers

**What moves:**
```python
# FROM intent_service.py (lines 754-4500 approx)
_handle_calendar_query()
_handle_calendar_create()
_handle_calendar_edit()
_handle_create_event()
_handle_confirm_create()
_handle_cancel_create()
# ... 15+ helper methods

# TO intent_handlers/calendar_handler.py
class CalendarHandler(IntentHandler):
    async def handle(self, intent, context) -> IntentResult
```

**Dependencies:**
- `calendar_search_service`
- `pending_event_service`
- `GoogleCalendarClient`

**Testing Strategy:**
1. Comprehensive unit tests for each sub-handler
2. State machine tests for confirmation flow
3. Integration tests with mocked Google API

**Rollback:**
1. Feature flag: `CALENDAR_HANDLER_ENABLED=false`
2. Keep original methods in intent_service.py until stable

---

#### Phase 5: Extract DisplayContentHandler
**Risk:** HIGH - Visual output, many edge cases

**What moves:**
```python
# FROM intent_service.py (lines 5892-6500)
_handle_display_content()
_execute_custom_layout_action()

# TO intent_handlers/display_handler.py
class DisplayContentHandler(IntentHandler):
    async def handle(self, intent, context) -> IntentResult
```

**Dependencies:**
- `scene_service`
- `custom_layout_service`
- `connection_manager`

---

#### Phase 6: Extract DocumentHandler
**Risk:** HIGH - Complex Google Docs integration

**What moves:**
```python
# FROM intent_service.py (lines 4573-5890)
_handle_doc_query()
_handle_link_doc()
_handle_open_doc()
_handle_read_doc()
_handle_summarize_meeting_doc()
_handle_create_event_from_doc()

# TO intent_handlers/document_handler.py
class DocumentHandler(IntentHandler):
    async def handle(self, intent, context) -> IntentResult
```

---

#### Phase 7: Cleanup IntentService
**Risk:** MEDIUM - Remove dead code, update orchestrator

**Actions:**
1. Remove all migrated `_handle_*` methods
2. Update `process()` to use registry exclusively
3. Move `IntentResult` to `intent_handlers/result.py`
4. Final integration testing

---

### 3.3 Risk Assessment Matrix

| Phase | Handler | Lines | Risk | Key Risk Factor |
|-------|---------|-------|------|-----------------|
| 1 | Infrastructure | 0 | LOW | None - design only |
| 2 | Conversation | ~200 | LOW | Stateless, simple |
| 3 | Device | ~300 | MEDIUM | Core functionality |
| 4 | Calendar | ~800 | HIGH | State machine, many sub-handlers |
| 5 | Display | ~600 | HIGH | Visual validation, WebSocket |
| 6 | Document | ~400 | HIGH | External API (Google Docs) |
| 7 | Cleanup | N/A | MEDIUM | Remove dependencies safely |

---

## 4. Dependency Injection Decision

### 4.1 Options Analyzed

#### Option A: Constructor Injection
```python
class CalendarHandler(IntentHandler):
    def __init__(
        self,
        calendar_service: CalendarSearchService,
        pending_service: PendingEventService,
    ):
        self._calendar_service = calendar_service
        self._pending_service = pending_service

    async def handle(self, intent, context):
        events = await self._calendar_service.search(...)
```

**Pros:**
- Explicit dependencies
- Easy to mock in tests
- Clear contracts

**Cons:**
- Requires wiring at registration time
- More boilerplate

---

#### Option B: Method Injection (via Context)
```python
class CalendarHandler(IntentHandler):
    async def handle(self, intent, context: HandlerContext):
        # Services accessed via context or imported directly
        from app.services.calendar_search_service import calendar_search_service
        events = await calendar_search_service.search(...)
```

**Pros:**
- Simpler handler classes
- Matches current codebase pattern
- Context already provides db, user_id, etc.

**Cons:**
- Import-time coupling
- Harder to mock (must patch imports)

---

#### Option C: Service Locator Pattern
```python
class CalendarHandler(IntentHandler):
    async def handle(self, intent, context):
        calendar_service = context.get_service('calendar_search')
        events = await calendar_service.search(...)
```

**Pros:**
- Flexible, late binding
- Easy to swap implementations

**Cons:**
- Hidden dependencies
- Runtime errors if service missing
- Anti-pattern in modern Python

---

### 4.2 Recommendation: Hybrid Approach (Option B with Context Enhancement)

**Decision:** Use **Method Injection via Enhanced HandlerContext**

**Rationale:**
1. **Matches existing patterns:** Current codebase uses singleton services with module-level imports
2. **Minimal migration friction:** Don't need to rewire all service instantiation
3. **Context already exists:** Request context pattern is established
4. **Testing story:** Use `pytest-mock` with `patch()` for service isolation

**Implementation:**

```python
@dataclass
class HandlerContext:
    """Context shared between all handlers."""
    # Required
    user_id: UUID
    request_id: str
    devices: List[Device]
    start_time: float

    # Database (opened per-request)
    db: Session

    # Behavioral flags
    require_feedback: bool = False

    # Resolved context from build_request_context()
    resolved_references: Dict[str, Any] = field(default_factory=dict)
    conversation_history: Optional[str] = None
    pending_operation: Optional[Dict[str, Any]] = None

    # Optional service overrides (for testing)
    _service_overrides: Dict[str, Any] = field(default_factory=dict)

    def get_service(self, name: str, default_factory=None):
        """Get service with optional override for testing."""
        if name in self._service_overrides:
            return self._service_overrides[name]
        if default_factory:
            return default_factory()
        raise ValueError(f"Service '{name}' not found and no default provided")
```

**Testing Example:**
```python
@pytest.mark.asyncio
async def test_calendar_handler_with_mock_service():
    mock_calendar_service = AsyncMock()
    mock_calendar_service.search.return_value = [{"title": "Meeting"}]

    context = HandlerContext(
        user_id=uuid4(),
        request_id="test-123",
        devices=[],
        db=Mock(),
        start_time=time.time(),
        _service_overrides={"calendar_search": mock_calendar_service},
    )

    handler = CalendarHandler()
    result = await handler.handle(mock_intent, context)

    assert result.success
    mock_calendar_service.search.assert_called_once()
```

---

## 5. Handler Interface Reference

### 5.1 IntentHandler ABC

See: `app/services/intent_handlers/base.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from uuid import UUID
from dataclasses import dataclass, field

@dataclass
class HandlerContext:
    """Context shared between all handlers."""
    user_id: UUID
    request_id: str
    devices: List[Any]
    db: Any  # Session
    start_time: float
    require_feedback: bool = False
    resolved_references: Dict[str, Any] = field(default_factory=dict)
    conversation_history: str | None = None
    pending_operation: Dict[str, Any] | None = None


class IntentHandler(ABC):
    """Abstract base class for intent handlers."""

    @property
    @abstractmethod
    def handler_name(self) -> str:
        """Unique identifier for this handler."""
        pass

    @property
    @abstractmethod
    def supported_intent_types(self) -> List[str]:
        """List of IntentType values this handler can process."""
        pass

    @abstractmethod
    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        """Determine if this handler can process the given intent."""
        pass

    @abstractmethod
    async def handle(
        self,
        intent: Any,
        context: HandlerContext,
    ) -> Any:  # Returns IntentResult
        """Process the intent and return a result."""
        pass
```

### 5.2 Handler Registration (Future)

```python
# Future: app/services/intent_handlers/registry.py

class HandlerRegistry:
    """Registry for intent handlers."""

    def __init__(self):
        self._handlers: Dict[str, IntentHandler] = {}

    def register(self, handler: IntentHandler) -> None:
        for intent_type in handler.supported_intent_types:
            self._handlers[intent_type] = handler

    def get_handler(self, intent_type: str) -> IntentHandler | None:
        return self._handlers.get(intent_type)

# Singleton instance
handler_registry = HandlerRegistry()
```

---

## Appendix A: File Locations

| File | Purpose |
|------|---------|
| `app/services/intent_handlers/__init__.py` | Package exports |
| `app/services/intent_handlers/base.py` | IntentHandler ABC, HandlerContext |
| `app/services/intent_handlers/registry.py` | HandlerRegistry (future) |
| `app/services/intent_handlers/conversation_handler.py` | (Phase 2) |
| `app/services/intent_handlers/device_handler.py` | (Phase 3) |
| `app/services/intent_handlers/calendar_handler.py` | (Phase 4) |
| `app/services/intent_handlers/display_handler.py` | (Phase 5) |
| `app/services/intent_handlers/document_handler.py` | (Phase 6) |

---

## Appendix B: Current Handler Method Inventory

| Method | Lines | Intent Type | Target Handler |
|--------|-------|-------------|----------------|
| `_handle_device_command` | 514-599 | DEVICE_COMMAND | DeviceHandler |
| `_handle_device_query` | 605-652 | DEVICE_QUERY | DeviceHandler |
| `_handle_system_query` | 658-748 | SYSTEM_QUERY | DeviceHandler |
| `_handle_calendar_query` | 754-1550 | CALENDAR_QUERY | CalendarHandler |
| `_handle_conversation` | 1553-1770 | CONVERSATION | ConversationHandler |
| `_handle_complex_task` | 1774-2820 | COMPLEX_* | ComplexTaskHandler |
| `_handle_calendar_create` | 2826-2886 | CALENDAR_CREATE | CalendarHandler |
| `_handle_calendar_edit` | 3395-3470 | CALENDAR_EDIT | CalendarHandler |
| `_handle_doc_query` | 4573-4780 | DOC_QUERY | DocumentHandler |
| `_handle_display_content` | 5892-6507 | DISPLAY_CONTENT | DisplayContentHandler |

---

*Document created: 2026-01-27*
*Story: US-1.2 - Design Handler Architecture*
