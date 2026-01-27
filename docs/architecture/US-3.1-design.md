# Architecture Design: US-3.1 - Extract CalendarHandler

## Overview

Extract all calendar-related logic from `IntentService` (~1,765 lines) into a specialized `CalendarHandler` class implementing the `IntentHandler` ABC. Handles three intent types: `CalendarQueryIntent`, `CalendarCreateIntent`, and `CalendarEditIntent`.

---

## Module/Class Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  IntentService                                       │
│                       (Orchestrator - delegates to handlers)                        │
│                                                                                     │
│  _handle_simple_task_internal()                                                     │
│    └──► if isinstance(intent, CalendarQueryIntent|CalendarCreateIntent|             │
│                               CalendarEditIntent):                                  │
│          return await CalendarHandler().handle(intent, context)                     │
└───────────────────────────────────┬─────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                CalendarHandler                                       │
│                  app/services/intent_handlers/calendar_handler.py                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Properties (from IntentHandler ABC):                                               │
│  ├── handler_name: str = "calendar"                                                 │
│  └── supported_intent_types: List[str] = ["calendar_query",                        │
│                                            "calendar_create", "calendar_edit"]      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Public Methods:                                                                    │
│  ├── can_handle(intent, context) -> bool                                            │
│  └── handle(intent, context) -> IntentResult                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Calendar Query Methods:                                                            │
│  ├── _handle_calendar_query(intent, context) -> IntentResult                       │
│  ├── _smart_find_event(search_term, context) -> str                                │
│  ├── _smart_next_event(search_term, context) -> str                                │
│  ├── _smart_count_events(date_range, search_term, context) -> str                  │
│  ├── _smart_list_events(date_range, search_term, context) -> str                   │
│  └── _generate_calendar_response(template_type, context, **kwargs) -> str          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Calendar Create Methods:                                                           │
│  ├── _handle_calendar_create(intent, context) -> IntentResult                      │
│  ├── _handle_create_event(intent, context) -> IntentResult                         │
│  ├── _handle_confirm_create(context, intent?) -> IntentResult                      │
│  ├── _handle_cancel_create(context) -> IntentResult                                │
│  └── _handle_edit_pending(intent, context) -> IntentResult                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Calendar Edit/Delete Methods:                                                      │
│  ├── _handle_calendar_edit(intent, context) -> IntentResult                        │
│  ├── _handle_edit_existing_event(intent, context) -> IntentResult                  │
│  ├── _handle_delete_existing_event(intent, context) -> IntentResult                │
│  ├── _handle_select_event(intent, context) -> IntentResult                         │
│  ├── _handle_confirm_edit(context) -> IntentResult                                 │
│  ├── _handle_confirm_delete(context) -> IntentResult                               │
│  └── _handle_cancel_edit(context) -> IntentResult                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Utility Methods:                                                                   │
│  ├── _resolve_date_string(date_str) -> Optional[date]                              │
│  ├── _build_confirmation_message(pending, highlight_field?) -> str                 │
│  ├── _build_calendar_success_message(pending, response) -> str                     │
│  ├── _format_recurrence(recurrence, lang) -> str                                   │
│  ├── _get_period_text(date_range) -> str                                           │
│  ├── _store_event_context(user_id, event) -> None                                  │
│  └── _get_action_value(action) -> Optional[str]                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                    External Services                           │
    ├───────────────────────────────────────────────────────────────┤
    │ calendar_search_service   - Smart semantic event search        │
    │ pending_event_service     - CREATE confirmation flow state     │
    │ pending_edit_service      - EDIT/DELETE confirmation flow      │
    │ conversation_context_service - Context for anaphoric refs      │
    │ gemini_provider           - Multilingual response generation   │
    │ GoogleCalendarClient      - Google Calendar API operations     │
    └───────────────────────────────────────────────────────────────┘
```

---

## State Machine: Create Event Flow

```
                          ┌──────────────────┐
                          │   User Request   │
                          │ "schedule mtg"   │
                          └────────┬─────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   CREATE_EVENT Action                             │
│  • Extract event details from intent                             │
│  • Store PendingEvent via pending_event_service                  │
│  • Return confirmation prompt                                    │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  PENDING STATE    │
                         │  (TTL: 120s)      │
                         └────────┬──────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
    ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
    │ "yes" / "sí"  │     │  "no" / "no"  │     │ "change X"    │
    │ CONFIRM_CREATE│     │ CANCEL_CREATE │     │ EDIT_PENDING  │
    └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
            │                     │                     │
            ▼                     ▼                     │
    ┌───────────────┐     ┌───────────────┐            │
    │ Create event  │     │ Clear pending │            │
    │ via Google    │     │ Return cancel │            │
    │ Calendar API  │     │ message       │            │
    └───────────────┘     └───────────────┘            │
                                                       ▼
                                              ┌───────────────┐
                                              │ Update field  │
                                              │ Loop back to  │
                                              │ PENDING STATE │
                                              └───────────────┘
```

---

## State Machine: Edit/Delete Event Flow

```
                          ┌──────────────────┐
                          │   User Request   │
                          │ "reschedule X"   │
                          └────────┬─────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│              EDIT_EXISTING / DELETE_EXISTING Action              │
│  • Smart semantic search via calendar_search_service             │
│  • Store PendingEdit via pending_edit_service                    │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
         ┌───────────────────┐         ┌───────────────────┐
         │  Single Match     │         │  Multiple Matches │
         │  AWAITING_        │         │  AWAITING_        │
         │  CONFIRMATION     │         │  SELECTION        │
         └────────┬──────────┘         └────────┬──────────┘
                  │                             │
                  │                             ▼
                  │                    ┌───────────────────┐
                  │                    │ SELECT_EVENT      │
                  │                    │ "the first one"   │
                  │                    └────────┬──────────┘
                  │◄────────────────────────────┘
                  ▼
         ┌───────────────────┐
         │  AWAITING_        │
         │  CONFIRMATION     │
         └────────┬──────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌──────────┐
│  "yes" │  │   "no"   │  │  TIMEOUT │
│CONFIRM │  │ CANCEL   │  │  Clear   │
└───┬────┘  └────┬─────┘  └──────────┘
    │            │
    ▼            ▼
┌────────┐  ┌──────────┐
│Execute │  │  Clear   │
│via API │  │ pending  │
└────────┘  └──────────┘
```

---

## Key Method Signatures

```python
class CalendarHandler(IntentHandler):
    """Handler for calendar-related intents."""

    @property
    def handler_name(self) -> str:
        return "calendar"

    @property
    def supported_intent_types(self) -> List[str]:
        return ["calendar_query", "calendar_create", "calendar_edit"]

    def can_handle(self, intent: Any, context: HandlerContext) -> bool:
        return isinstance(intent, (CalendarQueryIntent, CalendarCreateIntent, CalendarEditIntent))

    async def handle(self, intent: Any, context: HandlerContext) -> IntentResult:
        # Route to appropriate sub-handler
        if isinstance(intent, CalendarQueryIntent):
            return await self._handle_calendar_query(intent, context)
        elif isinstance(intent, CalendarCreateIntent):
            return await self._handle_calendar_create(intent, context)
        elif isinstance(intent, CalendarEditIntent):
            return await self._handle_calendar_edit(intent, context)

    # Calendar Query Methods
    async def _handle_calendar_query(self, intent: CalendarQueryIntent, context: HandlerContext) -> IntentResult
    async def _smart_find_event(self, search_term: str, context: HandlerContext) -> str
    async def _smart_next_event(self, search_term: Optional[str], context: HandlerContext) -> str
    async def _smart_count_events(self, date_range: Optional[str], search_term: Optional[str], context: HandlerContext) -> str
    async def _smart_list_events(self, date_range: Optional[str], search_term: Optional[str], context: HandlerContext) -> str
    async def _generate_calendar_response(self, template_type: str, context: HandlerContext, **kwargs) -> str

    # Calendar Create Methods
    async def _handle_calendar_create(self, intent: CalendarCreateIntent, context: HandlerContext) -> IntentResult
    async def _handle_create_event(self, intent: CalendarCreateIntent, context: HandlerContext) -> IntentResult
    async def _handle_confirm_create(self, context: HandlerContext, intent: Optional[CalendarCreateIntent] = None) -> IntentResult
    async def _handle_cancel_create(self, context: HandlerContext) -> IntentResult
    async def _handle_edit_pending(self, intent: CalendarCreateIntent, context: HandlerContext) -> IntentResult

    # Calendar Edit/Delete Methods
    async def _handle_calendar_edit(self, intent: CalendarEditIntent, context: HandlerContext) -> IntentResult
    async def _handle_edit_existing_event(self, intent: CalendarEditIntent, context: HandlerContext) -> IntentResult
    async def _handle_delete_existing_event(self, intent: CalendarEditIntent, context: HandlerContext) -> IntentResult
    async def _handle_select_event(self, intent: CalendarEditIntent, context: HandlerContext) -> IntentResult
    async def _handle_confirm_edit(self, context: HandlerContext) -> IntentResult
    async def _handle_confirm_delete(self, context: HandlerContext) -> IntentResult
    async def _handle_cancel_edit(self, context: HandlerContext) -> IntentResult

    # Utility Methods
    def _resolve_date_string(self, date_str: str) -> Optional[date]
    def _build_confirmation_message(self, pending: "PendingEvent", highlight_field: Optional[str] = None) -> str
    def _build_calendar_success_message(self, pending: "PendingEvent", response: "EventCreateResponse") -> str
    def _format_recurrence(self, recurrence: str, lang: str = "en") -> str
    def _get_period_text(self, date_range: str) -> str
    def _store_event_context(self, user_id: str, event: Any) -> None
    @staticmethod
    def _get_action_value(action: Any) -> Optional[str]
```

---

## Implementation Order

| Step | Description | Files | Est. Lines |
|------|-------------|-------|------------|
| 1 | Create CalendarHandler skeleton with properties and routing | calendar_handler.py | ~100 |
| 2 | Extract Calendar Query methods | calendar_handler.py | ~635 |
| 3 | Extract Calendar Create methods | calendar_handler.py | ~645 |
| 4 | Extract Calendar Edit/Delete methods | calendar_handler.py | ~835 |
| 5 | Extract Utility methods | calendar_handler.py | ~100 |
| 6 | Update __init__.py exports | __init__.py | +2 |
| 7 | Integrate with IntentService | intent_service.py | +20, -1765 |
| 8 | Create unit tests | test_calendar_handler.py | ~500 |

---

## Service Dependencies

| Service | Import Path | Usage |
|---------|-------------|-------|
| calendar_search_service | app.services.calendar_search_service | Smart semantic event search |
| pending_event_service | app.services.pending_event_service | CREATE confirmation flow |
| pending_edit_service | app.services.pending_edit_service | EDIT/DELETE confirmation flow |
| conversation_context_service | app.services.conversation_context_service | Context for anaphoric references |
| gemini_provider | app.ai.providers.gemini | Multilingual response generation |
| GoogleCalendarClient | app.environments.google.calendar.client | Google Calendar API |

---

## AC-to-Component Mapping

| AC | Description | Component | Tests |
|----|-------------|-----------|-------|
| AC-1 | CalendarHandler with all methods | CalendarHandler class, 23 methods | test_can_handle_*, test_handle_* |
| AC-2 | Integration with IntentService | Routing in _handle_simple_task_internal | test_intent_service_delegates_* |
| AC-3 | Comprehensive unit tests | tests/test_calendar_handler.py | 20+ test methods |

---

## Files to Create/Modify

| File | Action | Est. Lines |
|------|--------|------------|
| app/services/intent_handlers/calendar_handler.py | CREATE | ~1,800 |
| app/services/intent_handlers/__init__.py | MODIFY | +2 |
| app/services/intent_service.py | MODIFY | -1,765 |
| tests/test_calendar_handler.py | CREATE | ~500 |
