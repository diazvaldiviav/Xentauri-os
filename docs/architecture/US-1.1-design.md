# Architecture Design: US-1.1 - Fix human_feedback_mode Bug

## Overview

This is a bug fix for the missing `human_feedback_mode` parameter in the `_execute_custom_layout_action()` method. The fix is a single-line addition at line 2277 of `intent_service.py`. When `require_feedback=true` is passed to the `/intent` endpoint, all HTML generation routes must pass `human_feedback_mode=True` to skip CSS validation and enable the faster JS-only validation path (~5 seconds instead of ~12 seconds).

## Module/Class Call Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              POST /intent                                        │
│                         (require_feedback=true)                                  │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         IntentService.process()                                  │
│                    self._require_feedback = True                                 │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────────┐
│  simple complexity   │  │ complex_execution    │  │  complex_execution           │
│  _handle_display_    │  │ _handle_complex_     │  │  _handle_display_content()   │
│  content()           │  │ task()               │  │  (SceneGraph flow)           │
│  line 6266-6271      │  │                      │  │  line 6333-6336              │
│  FIXED ✓             │  │                      │  │  FIXED ✓                     │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────────┬───────────────┘
           │                         │                              │
           │                         ▼                              │
           │              ┌──────────────────────┐                  │
           │              │ _execute_gpt_action()│                  │
           │              │ content_type=        │                  │
           │              │ "custom_layout"      │                  │
           │              └──────────┬───────────┘                  │
           │                         │                              │
           │                         ▼                              │
           │              ┌──────────────────────────────────────┐  │
           │              │ _execute_custom_layout_action()      │  │
           │              │ line 2277                            │  │
           │              │ human_feedback_mode=??? <── BUG      │  │
           │              └──────────┬───────────────────────────┘  │
           │                         │                              │
           └─────────────┬───────────┴──────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              CustomLayoutService.generate_and_validate_html_from_data()          │
│              app/ai/scene/custom_layout/__init__.py:124-175                      │
│              human_feedback_mode parameter determines validation type            │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CustomLayoutPipeline.process()                                │
│                    app/ai/scene/custom_layout/pipeline.py:159-208                │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
┌──────────────────────────────┐       ┌──────────────────────────────────────────┐
│ human_feedback_mode=True     │       │ human_feedback_mode=False (default)      │
│ lines 159-172                │       │ lines 186-208                            │
│                              │       │                                          │
│ _validate_and_fix_js_only()  │       │ Full validation + CSS repair             │
│ ~5 seconds                   │       │ ~12 seconds                              │
│                              │       │                                          │
│ Returns: js_errors only      │       │ Returns: full validation metrics         │
└──────────────────────────────┘       └──────────────────────────────────────────┘
```

## Exact Code Change

### File: `app/services/intent_service.py`

### Location: Line 2277-2281

### BEFORE (Current Buggy Code)

```python
                # Generate HTML with visual validation
                layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                    content_data=content_data,
                    user_request=layout_description,
                    layout_type=content_data.get("content_type"),
                )
```

### AFTER (Fixed Code)

```python
                # Generate HTML with visual validation
                layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                    content_data=content_data,
                    user_request=layout_description,
                    layout_type=content_data.get("content_type"),
                    human_feedback_mode=getattr(self, '_require_feedback', False),
                )
```

### Diff View

```diff
--- a/app/services/intent_service.py
+++ b/app/services/intent_service.py
@@ -2277,6 +2277,7 @@ class IntentService:
                 layout_result = await custom_layout_service.generate_and_validate_html_from_data(
                     content_data=content_data,
                     user_request=layout_description,
                     layout_type=content_data.get("content_type"),
+                    human_feedback_mode=getattr(self, '_require_feedback', False),
                 )
```

## Logging Statements to Add

### Location 1: Entry to `_execute_custom_layout_action()` (after line 2236)

```python
        layout_description = (parameters or {}).get("layout_description", "")

        # Log human_feedback_mode propagation
        logger.info(
            f"[{request_id}] _execute_custom_layout_action: "
            f"human_feedback_mode={getattr(self, '_require_feedback', False)}"
        )
```

### Location 2: Before the generate call (before line 2276)

```python
                # Log validation type
                validation_type = "JS-only" if getattr(self, '_require_feedback', False) else "Full CSS+JS"
                logger.info(f"[{request_id}] Custom layout validation type: {validation_type}")
```

### Location 3: After successful generation (after line 2283)

```python
                if layout_result.success and layout_result.html:
                    # Log result with timing
                    logger.info(
                        f"[{request_id}] Custom layout generated: "
                        f"latency={layout_result.latency_ms:.0f}ms, "
                        f"human_feedback_mode={getattr(self, '_require_feedback', False)}, "
                        f"has_js_errors={bool(getattr(layout_result, 'js_errors', None))}"
                    )
```

## Test File Structure

### File: `tests/test_human_feedback_mode.py`

```python
"""
Regression tests for human_feedback_mode propagation.

Story: US-1.1 - require_feedback=true must ALWAYS skip CSS validation

These tests verify that the human_feedback_mode parameter is correctly
passed to CustomLayoutService from ALL HTML generation routes in IntentService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import time

from app.services.intent_service import IntentService


class MockDevice:
    """Mock Device for testing."""
    def __init__(self, name: str = "Test TV"):
        self.id = uuid4()
        self.name = name
        self.is_online = True
        self.capabilities = {"power": True}
        self.user_id = uuid4()


@pytest.fixture
def intent_service():
    """Create IntentService instance."""
    return IntentService()


@pytest.fixture
def mock_device():
    """Create mock device."""
    return MockDevice("Living Room TV")


class TestExecuteCustomLayoutActionHumanFeedbackMode:
    """Tests for human_feedback_mode in _execute_custom_layout_action."""

    @pytest.mark.asyncio
    async def test_human_feedback_mode_true_passed_to_service(
        self,
        intent_service,
        mock_device,
    ):
        """
        AC-2: GIVEN require_feedback=true AND complexity='complex_execution'
        THEN human_feedback_mode=True is passed to generate_and_validate_html_from_data
        """
        intent_service._require_feedback = True

        with patch('app.services.intent_service.custom_layout_service') as mock_cls, \
             patch('app.services.intent_service.scene_service') as mock_scene, \
             patch('app.services.intent_service.connection_manager') as mock_cm, \
             patch('app.services.intent_service.command_service') as mock_cmd, \
             patch('app.services.intent_service.settings') as mock_settings:

            mock_settings.CUSTOM_LAYOUT_ENABLED = True
            mock_scene.generate_content_data = AsyncMock(return_value={
                "content_type": "trivia",
                "title": "Test",
                "data": {},
            })
            mock_cls.generate_and_validate_html_from_data = AsyncMock(return_value=MagicMock(
                success=True,
                html="<div>Test</div>",
                latency_ms=5000,
                js_errors=None,
            ))
            mock_cm.send_command = AsyncMock()
            mock_cmd.display_scene = AsyncMock(return_value=MagicMock(
                success=True,
                command_id="cmd-123",
            ))

            await intent_service._execute_custom_layout_action(
                request_id="req-123",
                device=mock_device,
                user_id=uuid4(),
                parameters={"layout_description": "Show me trivia"},
                confidence=0.95,
                start_time=time.time(),
            )

            mock_cls.generate_and_validate_html_from_data.assert_called_once()
            call_kwargs = mock_cls.generate_and_validate_html_from_data.call_args[1]
            assert call_kwargs.get('human_feedback_mode') is True, \
                "human_feedback_mode should be True when _require_feedback=True"

    @pytest.mark.asyncio
    async def test_human_feedback_mode_false_when_not_set(
        self,
        intent_service,
        mock_device,
    ):
        """
        AC-3: GIVEN require_feedback is not set
        THEN human_feedback_mode=False is passed (default behavior)
        """
        with patch('app.services.intent_service.custom_layout_service') as mock_cls, \
             patch('app.services.intent_service.scene_service') as mock_scene, \
             patch('app.services.intent_service.connection_manager') as mock_cm, \
             patch('app.services.intent_service.command_service') as mock_cmd, \
             patch('app.services.intent_service.settings') as mock_settings:

            mock_settings.CUSTOM_LAYOUT_ENABLED = True
            mock_scene.generate_content_data = AsyncMock(return_value={
                "content_type": "trivia",
                "title": "Test",
                "data": {},
            })
            mock_cls.generate_and_validate_html_from_data = AsyncMock(return_value=MagicMock(
                success=True,
                html="<div>Test</div>",
                latency_ms=12000,
            ))
            mock_cm.send_command = AsyncMock()
            mock_cmd.display_scene = AsyncMock(return_value=MagicMock(
                success=True,
                command_id="cmd-123",
            ))

            await intent_service._execute_custom_layout_action(
                request_id="req-456",
                device=mock_device,
                user_id=uuid4(),
                parameters={"layout_description": "Show me trivia"},
                confidence=0.95,
                start_time=time.time(),
            )

            call_kwargs = mock_cls.generate_and_validate_html_from_data.call_args[1]
            assert call_kwargs.get('human_feedback_mode') is False, \
                "human_feedback_mode should be False when _require_feedback not set"

    @pytest.mark.asyncio
    async def test_human_feedback_mode_explicit_false(
        self,
        intent_service,
        mock_device,
    ):
        """
        AC-3: GIVEN require_feedback=false explicitly
        THEN human_feedback_mode=False is passed
        """
        intent_service._require_feedback = False

        with patch('app.services.intent_service.custom_layout_service') as mock_cls, \
             patch('app.services.intent_service.scene_service') as mock_scene, \
             patch('app.services.intent_service.connection_manager') as mock_cm, \
             patch('app.services.intent_service.command_service') as mock_cmd, \
             patch('app.services.intent_service.settings') as mock_settings:

            mock_settings.CUSTOM_LAYOUT_ENABLED = True
            mock_scene.generate_content_data = AsyncMock(return_value={
                "content_type": "trivia",
                "title": "Test",
                "data": {},
            })
            mock_cls.generate_and_validate_html_from_data = AsyncMock(return_value=MagicMock(
                success=True,
                html="<div>Test</div>",
                latency_ms=12000,
            ))
            mock_cm.send_command = AsyncMock()
            mock_cmd.display_scene = AsyncMock(return_value=MagicMock(
                success=True,
                command_id="cmd-123",
            ))

            await intent_service._execute_custom_layout_action(
                request_id="req-789",
                device=mock_device,
                user_id=uuid4(),
                parameters={"layout_description": "Show me trivia"},
                confidence=0.95,
                start_time=time.time(),
            )

            call_kwargs = mock_cls.generate_and_validate_html_from_data.call_args[1]
            assert call_kwargs.get('human_feedback_mode') is False
```

## Implementation Order

| Step | Task | File |
|------|------|------|
| 1 | Add `human_feedback_mode` parameter to line 2277 | `app/services/intent_service.py` |
| 2 | Add logging statement at entry (after line 2236) | `app/services/intent_service.py` |
| 3 | Add logging statement before generate call | `app/services/intent_service.py` |
| 4 | Add logging statement after success | `app/services/intent_service.py` |
| 5 | Create test file | `tests/test_human_feedback_mode.py` |
| 6 | Run new tests: `pytest tests/test_human_feedback_mode.py -v` | CLI |
| 7 | Run full test suite: `pytest tests/ -v` | CLI |

## Acceptance Criteria to Component Mapping

| AC ID | Description | Implementation | Test Method |
|-------|-------------|----------------|-------------|
| AC-1 | require_feedback=true + simple -> JS-only (~5s) | Line 6271 (already fixed) | Existing tests |
| AC-2 | require_feedback=true + complex_execution -> JS-only (~5s) | **Line 2277 (THIS FIX)** | `test_human_feedback_mode_true_passed_to_service` |
| AC-3 | require_feedback=false -> full CSS validation (~12s) | Default behavior | `test_human_feedback_mode_false_when_not_set` |
| AC-4 | 679 tests continue passing | No breaking changes | `pytest tests/ -v` |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Typo in parameter name | Low | High | Copy exact pattern from line 6271 |
| Test mock incorrect | Medium | Low | Use same mock pattern as existing tests |
| Regression in other routes | Low | High | Run full test suite |

## Rollback Plan

If issues arise after deployment:
1. Revert the single line change at 2277 (remove the `human_feedback_mode` parameter)
2. The system will return to previous behavior (full CSS validation for complex_execution route)
3. No data migration or schema changes to revert

---
End of Architecture Design
