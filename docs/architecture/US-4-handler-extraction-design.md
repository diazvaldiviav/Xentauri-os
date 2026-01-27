# Sprint 4: Complete Handler Extraction - Architecture Design

## Executive Summary

**Goal**: Eliminate delegation pattern by moving ~1088 lines from IntentService to handlers.

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| IntentService | ~2866 lines | ~1600 lines | -1266 lines |
| DocumentHandler | ~473 lines | ~1500 lines | +1027 lines |
| DisplayContentHandler | ~886 lines | ~1010 lines | +124 lines |

---

## US-4.1: Move Doc Query Action Methods to DocumentHandler

### Files to Modify

- `app/services/intent_handlers/document_handler.py` - Add implementations
- `app/services/intent_service.py` - Remove methods after verification

### Step 1: Add Required Imports to DocumentHandler

Add these imports after line 26:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
```

### Step 2: Add Helper Methods to DocumentHandler

Add these methods after `_handle_also_display` (after line 366):

```python
# -------------------------------------------------------------------------
# HELPER METHODS - Context management
# -------------------------------------------------------------------------

def _get_event_from_context(self, user_id: str):
    """Get the last referenced event from conversation context."""
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
    doc_title: str = None,
    doc_content: str = None,
) -> None:
    """Store a document in conversation context."""
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

def _store_event_context(self, user_id: str, event) -> None:
    """Store an event in conversation context."""
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
```

### Step 3: Replace Delegation Methods with Implementations

Replace the 5 delegation methods (lines 373-472) with actual implementations from IntentService:

| Method | IntentService Lines | Target |
|--------|---------------------|--------|
| `_handle_link_doc` | 1754-1918 | Replace delegation at line 373 |
| `_handle_open_doc` | 1920-2200 | Replace delegation at line 394 |
| `_handle_read_doc` | 2202-2352 | Replace delegation at line 415 |
| `_handle_summarize_meeting_doc` | 2354-2515 | Replace delegation at line 436 |
| `_handle_create_event_from_doc` | 2517-2730 | Replace delegation at line 455 |

**Key modifications during copy:**
1. Remove lazy `from app.services.intent_service import intent_service` imports
2. Change `self._get_event_from_context()` to use local method (already added)
3. Keep other service imports as lazy (inside methods) to avoid circular imports
4. Update docstrings to reference "Sprint 4" extraction

### Step 4: Remove from IntentService

After tests pass, remove from `intent_service.py`:
- Lines 1542-2730: `_handle_doc_query` and all 5 action methods (~1188 lines)

---

## US-4.2: Move Display Scene Helpers to DisplayContentHandler

### Files to Modify

- `app/services/intent_handlers/display_content_handler.py` - Add implementations
- `app/services/intent_service.py` - Remove methods after verification

### Step 1: Add Helper Methods to DisplayContentHandler

Add after `_generate_scene_and_layout` method (around line 886):

```python
# -------------------------------------------------------------------------
# REAL-TIME DATA HELPERS - Sprint 4 extraction
# -------------------------------------------------------------------------

async def _fetch_realtime_data_for_scene(
    self,
    user_request: str,
    layout_hints: list,
) -> Dict[str, Any]:
    """
    Use Gemini with web search to fetch real-time data for scene components.
    Sprint 4: Moved from IntentService.
    """
    # Copy implementation from IntentService lines 2736-2800
    ...

def _extract_location_from_request(self, user_request: str) -> Optional[str]:
    """
    Extract location from user request using regex patterns.
    Sprint 4: Moved from IntentService.
    """
    import re
    # Copy implementation from IntentService lines 2802-2859
    ...
```

### Step 2: Update Existing `_fetch_realtime_data` Method

Change from delegation to local call (lines 620-635):

```python
async def _fetch_realtime_data(
    self,
    user_request: Optional[str],
    layout_hints: Optional[List[str]],
) -> Optional[Dict[str, Any]]:
    """Fetch real-time data for scene generation."""
    # Sprint 4: Now calls local method instead of IntentService
    return await self._fetch_realtime_data_for_scene(
        user_request=user_request or "",
        layout_hints=layout_hints or [],
    )
```

### Step 3: Remove from IntentService

After tests pass, remove from `intent_service.py`:
- Lines 2736-2859: `_fetch_realtime_data_for_scene` and `_extract_location_from_request` (~124 lines)

---

## US-4.3: Final Cleanup and Test Migration

### Step 1: Remove Dead Code from IntentService

After US-4.1 and US-4.2, verify these are removed:
- `_handle_doc_query` method (was lines 1542-1752)
- 5 doc action methods (was lines 1754-2730)
- 2 display helpers (was lines 2736-2859)

### Step 2: Verify No Remaining References

```bash
grep -r "_handle_link_doc\|_handle_open_doc\|_handle_read_doc" app/services/intent_service.py
# Should return empty
```

### Step 3: Run Quality Checks

```bash
# Linting
ruff check app/services/intent_handlers/

# Tests
pytest tests/test_document_handler.py -v
pytest tests/test_display_content_handler.py -v
pytest tests/test_intent_service.py -v

# Full suite
pytest tests/ -v --tb=short
```

### Step 4: Final Line Count Verification

```bash
wc -l app/services/intent_service.py
# Target: ~1600 lines (down from 2866)
```

---

## Implementation Order

1. **US-4.1** - DocumentHandler (Priority: HIGH)
   - Add imports
   - Add 4 helper methods
   - Copy 5 action methods from IntentService
   - Remove delegation imports
   - Run `pytest tests/test_document_handler.py -v`
   - Remove methods from IntentService

2. **US-4.2** - DisplayContentHandler (Priority: MEDIUM)
   - Copy 2 helper methods from IntentService
   - Update `_fetch_realtime_data` to call local method
   - Run `pytest tests/test_display_content_handler.py -v`
   - Remove methods from IntentService

3. **US-4.3** - Cleanup (Priority: LOW)
   - Verify IntentService dead code removed
   - Run full test suite
   - Run ruff check
   - Generate sprint report

---

## Verification Checklist

### Per-Story Verification

- [ ] All imports added without circular dependency errors
- [ ] Helper methods callable from action methods
- [ ] Method signatures match exactly (same parameters, return types)
- [ ] Tests pass for modified handler
- [ ] No regressions in related tests

### Final Verification

```bash
# Run all tests
pytest tests/ -v --tb=short

# Linting
ruff check app/services/intent_handlers/

# Line count
wc -l app/services/intent_service.py  # Target: ~1600

# Verify no IntentService delegation in DocumentHandler
grep -c "intent_service\._handle" app/services/intent_handlers/document_handler.py
# Should return 0
```
