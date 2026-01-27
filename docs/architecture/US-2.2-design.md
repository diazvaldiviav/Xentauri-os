# Architecture Design: US-2.2 - Extract ConversationHandler

## Overview

This architecture extracts conversation handling logic from `IntentService` into a focused `ConversationHandler` class. Follows the same pattern as US-2.1 (DeviceHandler).

## Class Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          IntentService                                       │
│                     (Orchestrator - delegates to handlers)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│       DeviceHandler           │   │     ConversationHandler       │
│  (Existing - US-2.1)          │   │  (NEW - US-2.2)               │
├───────────────────────────────┤   ├───────────────────────────────┤
│  handler_name = "device"      │   │  handler_name = "conversation"│
│  Handles:                     │   │  Handles:                     │
│  - DeviceCommand              │   │  - ConversationIntent         │
│  - DeviceQuery                │   │    (greeting, thanks,         │
│  - SystemQuery                │   │     question, general chat)   │
└───────────────────────────────┘   └───────────────────────────────┘
```

---

## Methods to Extract from IntentService

| Method | Lines | Purpose |
|--------|-------|---------|
| `_handle_conversation` | 1465-1680 | Main conversation processing |
| `_detect_content_type` | 2502-2570 | Detect generated content type |
| `_extract_content_title` | 2572-2613 | Extract title from response |
| `_get_action_value` | 2487-2493 | Static helper (already in DeviceHandler) |

---

## Integration Pattern

### BEFORE
```python
elif isinstance(intent, ConversationIntent):
    return await self._handle_conversation(...)
```

### AFTER
```python
elif isinstance(intent, ConversationIntent):
    handler_context = HandlerContext(
        user_id=user_id,
        request_id=request_id,
        devices=devices,
        db=db,
        start_time=start_time,
        original_text=text,
    )
    return await self._conversation_handler.handle(intent, handler_context)
```

---

## Implementation Order

| Step | Task | File |
|------|------|------|
| 1 | Create ConversationHandler | `app/services/intent_handlers/conversation_handler.py` |
| 2 | Update exports | `app/services/intent_handlers/__init__.py` |
| 3 | Create unit tests | `tests/test_conversation_handler.py` |
| 4 | Modify IntentService to delegate | `app/services/intent_service.py` |
| 5 | Run full test suite | `pytest tests/ -v` |

---

## Dependencies

| Service | Purpose |
|---------|---------|
| `gemini_provider` | AI response generation |
| `conversation_context_service` | History and memory |
| `build_unified_context` | User context |
| `build_assistant_system_prompt` | System prompt |
| `build_assistant_prompt` | User prompt |

---

## AC-to-Component Mapping

| AC | Implementation | Test |
|----|----------------|------|
| AC-1 | ConversationHandler class | TestConversationHandlerInterface |
| AC-2 | IntentService delegation | TestIntentServiceDelegation |
| AC-3 | No behavioral changes | Full test suite |
| AC-4 | Unit tests with mocks | test_conversation_handler.py |

---

*Story: US-2.2 - Extract ConversationHandler*
