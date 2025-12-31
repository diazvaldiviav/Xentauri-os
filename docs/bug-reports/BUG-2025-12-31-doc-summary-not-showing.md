# Bug Report: doc_summary Component Not Showing Document

**Date:** 2025-12-31
**Sprint:** 5.1.1
**Severity:** High
**Status:** Analyzed - Fix Required

---

## Summary

When user creates a calendar event with an associated document URL and then asks to "show the document on screen", the `doc_summary` component returns an error instead of displaying the document content.

**Error Message:**
```json
{"error": "No document found linked to meeting '1o2jiap3u45q3ejqfqv2h03fug'"}
```

---

## Reproduction Steps

1. Create event with document: `"Crea reunion hoy 8pm Lanzamiento Matcha asocia https://docs.google.com/document/d/1RG-..."`
2. Confirm event creation: `"si"`
3. Ask to display document: `"Muestra el documento en la pantalla"`
4. **Expected:** Document content displayed on screen
5. **Actual:** Error "No document found linked to meeting"

---

## Root Cause Analysis

### Flow Diagram

```
User: "Crea reunion... asocia https://docs.google.com/document/d/ABC123"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Intent Parser (parser.py:541)                                   │
│   ✅ Extracts doc_url = "https://docs.google.com/document/..."  │
│   ❌ Does NOT extract doc_id from URL                           │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ store_pending() (intent_service.py:2705-2706)                   │
│   ✅ doc_url = "https://..."                                    │
│   ✅ source = "doc"                                             │
│   ❌ doc_id = None (never extracted!)                           │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ _handle_confirm_create() (intent_service.py:2968)               │
│   Condition: if pending.source == "doc" and pending.doc_id      │
│              and pending.doc_url:                               │
│                                                                 │
│   ❌ FAILS because doc_id is None!                              │
│   ❌ set_last_doc() is NEVER called                             │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
User: "Muestra el documento en la pantalla"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Scene Generation                                                │
│   get_last_doc() returns None (never set!)                      │
│   Claude has NO document context                                │
│   Claude uses event_id instead of doc_id                        │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ _fetch_doc_data() (scene/service.py:1227)                       │
│   Receives: props = {"event_id": "1o2jiap3u45q3ejqfqv2h03fug"}  │
│   Calls: _extract_doc_from_event(event_id=...)                  │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ _extract_doc_from_event() (scene/service.py:1077-1082)          │
│                                                                 │
│   if event_id:                                                  │
│       # TODO: Implement event_id lookup when needed             │
│       return None  ← ALWAYS RETURNS None!                       │
│                                                                 │
│   ❌ TODO not implemented!                                      │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
              ERROR RETURNED
```

---

## Issues Identified

### Issue 1: `doc_id` Not Extracted from URL (PRIMARY)
**Location:** `intent_service.py:2705-2706`

When storing pending event with `doc_url`, the `doc_id` should be extracted from the URL but isn't.

```python
# Current (buggy):
pending = await pending_event_service.store_pending(
    ...
    doc_url=intent.doc_url,  # URL is stored
    source="doc" if intent.doc_url else "manual",
)
# doc_id is never extracted or passed!
```

### Issue 2: Condition Requires Both `doc_id` AND `doc_url`
**Location:** `intent_service.py:2968`

```python
if pending.source == "doc" and pending.doc_id and pending.doc_url:
    conversation_context_service.set_last_doc(...)
```

This condition fails when `doc_id` is None, so `set_last_doc()` is never called.

### Issue 3: `_extract_doc_from_event()` TODO Not Implemented
**Location:** `scene/service.py:1077-1082`

```python
if event_id:
    # TODO: Implement event_id lookup when needed
    return None  # Always fails!
```

---

## Proposed Fix

### Option A: Extract `doc_id` at Pending Event Creation (Recommended)

**File:** `app/services/intent_service.py`

```python
# Before storing pending event, extract doc_id from doc_url
doc_id = None
if intent.doc_url:
    import re
    match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', intent.doc_url)
    if match:
        doc_id = match.group(1)

pending = await pending_event_service.store_pending(
    ...
    doc_url=intent.doc_url,
    doc_id=doc_id,  # Now extracted!
    source="doc" if intent.doc_url else "manual",
)
```

### Option B: Extract `doc_id` Before `set_last_doc()` Call

**File:** `app/services/intent_service.py:2968`

```python
if pending.source == "doc" and pending.doc_url:
    # Extract doc_id from URL if not present
    doc_id = pending.doc_id
    if not doc_id and pending.doc_url:
        import re
        match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', pending.doc_url)
        if match:
            doc_id = match.group(1)

    if doc_id:
        conversation_context_service.set_last_doc(
            user_id=str(user_id),
            doc_id=doc_id,
            doc_url=pending.doc_url,
            doc_title=pending.event_title,
        )
```

### Option C: Implement `_extract_doc_from_event()` for event_id lookup

**File:** `app/ai/scene/service.py:1077-1082`

Parse the event description to extract the document URL.

---

## Recommended Solution

**Option A** is recommended because:
1. Fixes the issue at the source (earliest point in the flow)
2. Ensures `doc_id` is available for all downstream operations
3. DRY - extraction happens once, used everywhere
4. Consistent with SOLID principles (single responsibility)

---

## Files Affected

| File | Line(s) | Issue |
|------|---------|-------|
| `app/services/intent_service.py` | 2705-2706 | `doc_id` not extracted |
| `app/services/intent_service.py` | 2968 | Condition fails |
| `app/ai/scene/service.py` | 1077-1082 | TODO not implemented |

---

## Testing

After fix, verify:
1. Create event with doc URL → `doc_id` extracted correctly
2. Confirm event → `set_last_doc()` called
3. "Muestra el documento" → Document content displayed
4. Run full 5-prompt demo without errors

---

## Author

Analysis by Claude Code (Sprint 5.1.1)
