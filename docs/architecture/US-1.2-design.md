# Architecture Design Document: US-1.2 - Design Handler Architecture

## Story Summary
**Story ID:** US-1.2
**Actor:** Developer
**Goal:** A clear handler architecture
**Benefit:** I can extract code without breaking functionality

## Overview

This document outlines the implementation plan for creating the Handler Architecture infrastructure. The current `IntentService` class contains ~6500 lines of monolithic code with 27 `_handle_*` methods. This design introduces the Strategy pattern to extract handlers into separate, testable, single-responsibility classes.

## Codebase Analysis

### Existing Implementations Scanned
- `app/services/intent_service.py` - 6507 lines (monolithic service)
- `app/ai/providers/base.py` - ABC pattern reference (435 lines)
- `app/services/__init__.py` - Services package entry point
- No existing `intent_handlers/` folder

### Decision: CREATE_NEW
**Justification:** No existing handler infrastructure exists. This story creates the foundational folder structure and base interface that future sprints will use to extract handlers.

## Deliverables Checklist

| # | Deliverable | Location | AC |
|---|-------------|----------|-----|
| 1 | Implementation Plan Document | `docs/architecture/US-1.2-design.md` | - |
| 2 | Main Architecture Document | `docs/architecture/INTENT_HANDLERS.md` | AC-1, AC-3, AC-4 |
| 3 | Handler Base Interface | `app/services/intent_handlers/base.py` | AC-2 |
| 4 | Package Init | `app/services/intent_handlers/__init__.py` | AC-2 |

## Implementation Order

### Step 1: Create Folder Structure
```bash
mkdir -p app/services/intent_handlers
```

### Step 2: Create `__init__.py`
Export base classes for easy importing.

### Step 3: Create `base.py`
Define the `IntentHandler` ABC following the pattern in `app/ai/providers/base.py`.

### Step 4: Create `INTENT_HANDLERS.md`
Main architecture document with:
- ASCII diagrams (BEFORE/AFTER)
- Migration plan with 7 phases
- DI decision documentation

### Step 5: Validation
- Run `python -c "from app.services.intent_handlers import IntentHandler"` to verify imports
- No test file creation needed (design-only story)

## Dependencies

- **Existing components to reference:** `app/ai/providers/base.py` (ABC pattern)
- **External libraries:** None new
- **API endpoints:** None new

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import errors in base.py | Low | Medium | Test imports after creation |
| Circular imports with IntentResult | Medium | High | Keep IntentResult in intent_service.py during migration |
| Documentation gaps | Low | Medium | Include code examples in all diagrams |

## Acceptance Criteria Mapping

| AC | Implementation | Test |
|----|----------------|------|
| AC-1: Architecture diagram documented | `INTENT_HANDLERS.md` Section 1-2 | Visual review |
| AC-2: Handler interfaces defined | `base.py` with ABC | Import test |
| AC-3: Migration plan approved | `INTENT_HANDLERS.md` Section 3 | Review |
| AC-4: DI decision made | `INTENT_HANDLERS.md` Section 4 | Review |

---
End of Implementation Plan
