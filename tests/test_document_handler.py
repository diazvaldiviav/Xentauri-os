"""
Tests for DocumentHandler - US-3.3

Tests for:
- DocumentHandler interface implementation
- DocQueryIntent handling
- Action routing
- Compound intent (also_display)
- IntentService delegation

Note: These tests use mocks for external dependencies
to test the handler logic in isolation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
import time

from app.services.intent_handlers.document_handler import DocumentHandler
from app.services.intent_handlers.base import HandlerContext
from app.services.intent_result import IntentResult, IntentResultType
from app.ai.intent.schemas import (
    DocQueryIntent,
    DisplayContentIntent,  # For testing can_handle returns False
    ActionType,
)


# ===========================================================================
# FIXTURES
# ===========================================================================

class MockDevice:
    """Mock Device for testing without database."""

    def __init__(self, name: str, is_online: bool = True):
        self.id = uuid4()
        self.name = name
        self.is_online = is_online
        self.capabilities = {"display": True}
        self.user_id = uuid4()


@pytest.fixture
def handler():
    """Create a fresh DocumentHandler instance."""
    return DocumentHandler()


@pytest.fixture
def mock_devices():
    """Create mock devices."""
    return [
        MockDevice("Living Room TV", is_online=True),
        MockDevice("Bedroom Monitor", is_online=True),
        MockDevice("Kitchen Display", is_online=False),
    ]


@pytest.fixture
def mock_context(mock_devices):
    """Create a mock HandlerContext."""
    return HandlerContext(
        user_id=uuid4(),
        request_id="test-req-123",
        devices=mock_devices,
        db=MagicMock(),
        start_time=time.time(),
        require_feedback=False,
        original_text="Summarize the meeting document",
        forced_device_id=None,
    )


@pytest.fixture
def doc_query_intent():
    """Create a DocQueryIntent for testing."""
    return DocQueryIntent(
        confidence=0.95,
        original_text="Summarize the meeting document",
        action=ActionType.SUMMARIZE_MEETING_DOC,
        meeting_search="standup",
    )


# ===========================================================================
# INTERFACE TESTS
# ===========================================================================

class TestDocumentHandlerInterface:
    """Tests for DocumentHandler ABC implementation."""

    def test_handler_name(self, handler):
        """Test handler_name property."""
        assert handler.handler_name == "document"

    def test_supported_intent_types(self, handler):
        """Test supported_intent_types property."""
        types = handler.supported_intent_types
        assert "doc_query" in types
        assert len(types) == 1

    def test_can_handle_doc_query_intent(self, handler, mock_context, doc_query_intent):
        """Test can_handle returns True for DocQueryIntent."""
        assert handler.can_handle(doc_query_intent, mock_context) is True

    def test_can_handle_display_content_intent(self, handler, mock_context):
        """Test can_handle returns False for DisplayContentIntent."""
        intent = DisplayContentIntent(
            confidence=0.9,
            original_text="Show calendar",
        )
        assert handler.can_handle(intent, mock_context) is False

    def test_can_handle_other_intent(self, handler, mock_context):
        """Test can_handle returns False for other intents."""
        mock_intent = MagicMock()
        mock_intent.__class__ = type("OtherIntent", (), {})
        assert handler.can_handle(mock_intent, mock_context) is False


# ===========================================================================
# ACTION ROUTING TESTS
# ===========================================================================

class TestActionRouting:
    """Tests for action routing in _handle_doc_query."""

    @pytest.mark.asyncio
    async def test_route_link_doc(self, handler, mock_context):
        """Test LINK_DOC action routes correctly."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Link this doc to my standup",
            action=ActionType.LINK_DOC,
            doc_url="https://docs.google.com/document/d/123/edit",
            meeting_search="standup",
        )

        with patch.object(handler, '_handle_link_doc', new_callable=AsyncMock) as mock_link:
            mock_link.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                message="Linked",
                request_id=mock_context.request_id,
            )

            result = await handler.handle(intent, mock_context)

            mock_link.assert_called_once()
            assert result.success is True

    @pytest.mark.asyncio
    async def test_route_open_doc(self, handler, mock_context):
        """Test OPEN_DOC action routes correctly."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Open my meeting document",
            action=ActionType.OPEN_DOC,
            meeting_search="standup",
        )

        with patch.object(handler, '_handle_open_doc', new_callable=AsyncMock) as mock_open:
            mock_open.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                message="Opened",
                request_id=mock_context.request_id,
            )

            result = await handler.handle(intent, mock_context)

            mock_open.assert_called_once()
            assert result.success is True

    @pytest.mark.asyncio
    async def test_route_read_doc(self, handler, mock_context):
        """Test READ_DOC action routes correctly."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Read this document",
            action=ActionType.READ_DOC,
            doc_url="https://docs.google.com/document/d/123/edit",
        )

        with patch.object(handler, '_handle_read_doc', new_callable=AsyncMock) as mock_read:
            mock_read.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                message="Read content",
                request_id=mock_context.request_id,
            )

            result = await handler.handle(intent, mock_context)

            mock_read.assert_called_once()
            assert result.success is True

    @pytest.mark.asyncio
    async def test_route_summarize_meeting_doc(self, handler, mock_context):
        """Test SUMMARIZE_MEETING_DOC action routes correctly."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Summarize my meeting doc",
            action=ActionType.SUMMARIZE_MEETING_DOC,
            meeting_search="standup",
        )

        with patch.object(handler, '_handle_summarize_meeting_doc', new_callable=AsyncMock) as mock_summarize:
            mock_summarize.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                message="Summary here",
                request_id=mock_context.request_id,
            )

            result = await handler.handle(intent, mock_context)

            mock_summarize.assert_called_once()
            assert result.success is True

    @pytest.mark.asyncio
    async def test_route_create_event_from_doc(self, handler, mock_context):
        """Test CREATE_EVENT_FROM_DOC action routes correctly."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Create event from this doc",
            action=ActionType.CREATE_EVENT_FROM_DOC,
            doc_url="https://docs.google.com/document/d/123/edit",
        )

        with patch.object(handler, '_handle_create_event_from_doc', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                message="Event created",
                request_id=mock_context.request_id,
            )

            result = await handler.handle(intent, mock_context)

            mock_create.assert_called_once()
            assert result.success is True

    def test_all_supported_actions_are_valid(self, handler):
        """Test all supported actions are valid ActionTypes."""
        # DocQueryIntent uses ActionType enum, so all actions are validated
        # This test documents the supported actions
        valid_actions = [
            ActionType.LINK_DOC,
            ActionType.OPEN_DOC,
            ActionType.READ_DOC,
            ActionType.SUMMARIZE_MEETING_DOC,
            ActionType.CREATE_EVENT_FROM_DOC,
        ]
        for action in valid_actions:
            intent = DocQueryIntent(
                confidence=0.9,
                original_text="Test",
                action=action,
            )
            assert intent.action == action


# ===========================================================================
# COMPOUND INTENT TESTS (ALSO_DISPLAY)
# ===========================================================================

class TestCompoundIntent:
    """Tests for compound intent (also_display) handling."""

    @pytest.mark.asyncio
    async def test_also_display_summary_creates_scene(self, handler, mock_context, mock_devices):
        """Test also_display creates scene for summary action."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Summarize and show on screen",
            action=ActionType.SUMMARIZE_MEETING_DOC,
            meeting_search="standup",
            also_display=True,
        )

        base_result = IntentResult(
            success=True,
            intent_type=IntentResultType.DOC_QUERY,
            message="Here's the summary...",
            request_id=mock_context.request_id,
            data={"doc_url": "https://docs.google.com/document/d/123/edit"},
        )

        with patch('app.services.intent_handlers.document_handler.command_service') as mock_cmd:
            mock_cmd.display_scene = AsyncMock(return_value=MagicMock(
                success=True,
                command_id="cmd-123",
            ))

            result = await handler._handle_also_display(
                result=base_result,
                intent=intent,
                action=ActionType.SUMMARIZE_MEETING_DOC,
                context=mock_context,
            )

            # Should display scene
            mock_cmd.display_scene.assert_called_once()
            assert result.command_sent is True
            assert "also displayed" in result.message

    @pytest.mark.asyncio
    async def test_also_display_read_shows_iframe(self, handler, mock_context, mock_devices):
        """Test also_display shows iframe for read action."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Read and show",
            action=ActionType.READ_DOC,
            also_display=True,
        )

        base_result = IntentResult(
            success=True,
            intent_type=IntentResultType.DOC_QUERY,
            message="Content here",
            request_id=mock_context.request_id,
            data={"doc_url": "https://docs.google.com/document/d/123/edit"},
        )

        with patch('app.services.intent_handlers.document_handler.command_service') as mock_cmd:
            mock_cmd.show_content = AsyncMock(return_value=MagicMock(
                success=True,
                command_id="cmd-456",
            ))

            result = await handler._handle_also_display(
                result=base_result,
                intent=intent,
                action=ActionType.READ_DOC,
                context=mock_context,
            )

            # Should show content
            mock_cmd.show_content.assert_called_once()
            assert result.command_sent is True

    @pytest.mark.asyncio
    async def test_also_display_no_device_doesnt_fail(self, handler, mock_devices):
        """Test also_display without available device doesn't fail the query."""
        # Context with no online devices
        context = HandlerContext(
            user_id=uuid4(),
            request_id="test",
            devices=[MockDevice("TV", is_online=False)],
            db=MagicMock(),
            start_time=time.time(),
        )

        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Summarize",
            action=ActionType.SUMMARIZE_MEETING_DOC,
            also_display=True,
        )

        base_result = IntentResult(
            success=True,
            intent_type=IntentResultType.DOC_QUERY,
            message="Summary",
            request_id="test",
            data={"doc_url": "https://docs.google.com/document/d/123/edit"},
        )

        result = await handler._handle_also_display(
            result=base_result,
            intent=intent,
            action=ActionType.SUMMARIZE_MEETING_DOC,
            context=context,
        )

        # Original result should be returned unchanged
        assert result.success is True
        assert result.command_sent is not True


# ===========================================================================
# CONVERSATION CONTEXT TESTS
# ===========================================================================

class TestConversationContext:
    """Tests for conversation context saving."""

    @pytest.mark.asyncio
    async def test_saves_response_to_conversation_context(self, handler, mock_context):
        """Test successful responses are saved to conversation context."""
        intent = DocQueryIntent(
            confidence=0.9,
            original_text="Summarize my meeting doc",
            action=ActionType.SUMMARIZE_MEETING_DOC,
            meeting_search="standup",
        )

        with patch.object(handler, '_handle_summarize_meeting_doc', new_callable=AsyncMock) as mock_summarize, \
             patch('app.services.intent_handlers.document_handler.conversation_context_service') as mock_conv:

            mock_summarize.return_value = IntentResult(
                success=True,
                intent_type=IntentResultType.DOC_QUERY,
                message="Summary here",
                request_id=mock_context.request_id,
            )

            await handler.handle(intent, mock_context)

            # Verify conversation turn was saved
            mock_conv.add_conversation_turn.assert_called_once()
            call_kwargs = mock_conv.add_conversation_turn.call_args.kwargs
            assert call_kwargs["intent_type"] == "doc_query"


# ===========================================================================
# INTEGRATION TESTS
# ===========================================================================

class TestIntentServiceDelegation:
    """Tests for IntentService delegation to DocumentHandler."""

    def test_handler_is_initialized(self):
        """Test IntentService initializes DocumentHandler."""
        from app.services.intent_service import intent_service

        assert hasattr(intent_service, '_document_handler')
        assert isinstance(intent_service._document_handler, DocumentHandler)


# ===========================================================================
# ERROR HANDLING TESTS
# ===========================================================================

class TestErrorHandling:
    """Tests for error handling in DocumentHandler."""

    @pytest.mark.asyncio
    async def test_handle_exception_returns_error_result(self, handler, mock_context, doc_query_intent):
        """Test that exceptions are caught and returned as IntentResult."""
        with patch.object(handler, '_handle_doc_query', side_effect=Exception("Test error")):
            result = await handler.handle(doc_query_intent, mock_context)

            assert result.success is False
            assert result.intent_type == IntentResultType.ERROR
            assert "Test error" in result.message
