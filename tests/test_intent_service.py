"""
Tests for Intent Service - Phase 2

Tests for:
- IntentService.process() main entry point
- IntentResult dataclass
- Helper methods
- Message building

Note: These tests use mocks for AI providers and database
to test the service logic in isolation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from typing import List

from app.services.intent_service import (
    IntentService,
    IntentResult,
    IntentResultType,
    intent_service,
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
        self.capabilities = {"power": True}
        self.user_id = uuid4()


@pytest.fixture
def service():
    """Create a fresh IntentService instance."""
    return IntentService()


@pytest.fixture
def mock_devices() -> List[MockDevice]:
    """Create mock devices."""
    return [
        MockDevice("Living Room TV", is_online=True),
        MockDevice("Bedroom Monitor", is_online=True),
        MockDevice("Kitchen Display", is_online=False),
    ]


# ===========================================================================
# INTENTRESULT TESTS
# ===========================================================================

class TestIntentResult:
    """Tests for IntentResult dataclass."""
    
    def test_create_success_result(self):
        """Test creating a successful result."""
        result = IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_COMMAND,
            confidence=0.95,
            message="Command executed successfully",
        )
        
        assert result.success is True
        assert result.intent_type == IntentResultType.DEVICE_COMMAND
        assert result.confidence == 0.95
        assert result.message == "Command executed successfully"
    
    def test_create_error_result(self):
        """Test creating an error result."""
        result = IntentResult(
            success=False,
            intent_type=IntentResultType.ERROR,
            message="Something went wrong",
        )
        
        assert result.success is False
        assert result.intent_type == IntentResultType.ERROR
    
    def test_result_with_device(self):
        """Test result with device info."""
        device = MockDevice("Test TV")
        
        result = IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_COMMAND,
            device=device,
            message="Command sent",
        )
        
        assert result.device == device
    
    def test_result_with_command_info(self):
        """Test result with command info."""
        result = IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_COMMAND,
            action="power_on",
            parameters={"target_device": "TV"},
            command_sent=True,
            command_id="cmd-123",
            message="Turned on TV",
        )
        
        assert result.action == "power_on"
        assert result.parameters["target_device"] == "TV"
        assert result.command_sent is True
        assert result.command_id == "cmd-123"
    
    def test_to_dict_basic(self):
        """Test serialization to dictionary."""
        result = IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_COMMAND,
            confidence=0.9,
            action="power_on",
            message="Done",
            processing_time_ms=150.5,
            request_id="req-123",
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["intent_type"] == "device_command"
        assert d["confidence"] == 0.9
        assert d["action"] == "power_on"
        assert d["message"] == "Done"
        assert d["processing_time_ms"] == 150.5
        assert d["request_id"] == "req-123"
    
    def test_to_dict_with_device(self):
        """Test serialization includes device info."""
        device = MockDevice("Test TV")
        device.id = uuid4()
        device.is_online = True
        
        result = IntentResult(
            success=True,
            intent_type=IntentResultType.DEVICE_COMMAND,
            device=device,
            message="Done",
        )
        
        d = result.to_dict()
        
        assert "device" in d
        assert d["device"]["name"] == "Test TV"
        assert d["device"]["is_online"] is True
    
    def test_to_dict_without_device(self):
        """Test serialization without device."""
        result = IntentResult(
            success=True,
            intent_type=IntentResultType.SYSTEM_QUERY,
            message="Your devices: ...",
        )
        
        d = result.to_dict()
        
        assert "device" not in d or d.get("device") is None


# ===========================================================================
# INTENTRESULTTYPE TESTS
# ===========================================================================

class TestIntentResultType:
    """Tests for IntentResultType enum."""
    
    def test_all_types_exist(self):
        """Test all expected types exist."""
        assert IntentResultType.DEVICE_COMMAND
        assert IntentResultType.DEVICE_QUERY
        assert IntentResultType.SYSTEM_QUERY
        assert IntentResultType.CONVERSATION
        assert IntentResultType.COMPLEX_EXECUTION
        assert IntentResultType.COMPLEX_REASONING
        assert IntentResultType.CLARIFICATION
        assert IntentResultType.ACTION_SEQUENCE
        assert IntentResultType.ERROR
        assert IntentResultType.UNKNOWN
    
    def test_type_values(self):
        """Test type values are lowercase strings."""
        assert IntentResultType.DEVICE_COMMAND.value == "device_command"
        assert IntentResultType.ERROR.value == "error"


# ===========================================================================
# HELPER METHOD TESTS
# ===========================================================================

class TestHelperMethods:
    """Tests for IntentService helper methods."""
    
    def test_get_action_value_from_enum(self, service):
        """Test extracting value from enum-like object."""
        class MockEnum:
            value = "power_on"
        
        result = service._get_action_value(MockEnum())
        assert result == "power_on"
    
    def test_get_action_value_from_string(self, service):
        """Test extracting value from string."""
        result = service._get_action_value("power_on")
        assert result == "power_on"
    
    def test_get_action_value_from_none(self, service):
        """Test extracting value from None."""
        result = service._get_action_value(None)
        assert result is None
    
    def test_build_success_message_power_on(self, service):
        """Test building power_on message."""
        msg = service._build_success_message("power_on", "Living Room TV", None)
        assert "Turning on" in msg
        assert "Living Room TV" in msg
    
    def test_build_success_message_power_off(self, service):
        """Test building power_off message."""
        msg = service._build_success_message("power_off", "TV", None)
        assert "Turning off" in msg
    
    def test_build_success_message_volume_up(self, service):
        """Test building volume_up message."""
        msg = service._build_success_message("volume_up", "TV", None)
        assert "volume" in msg.lower()
    
    def test_build_success_message_set_input(self, service):
        """Test building set_input message with input param."""
        msg = service._build_success_message("set_input", "TV", {"input": "HDMI2"})
        assert "HDMI2" in msg
        assert "TV" in msg
    
    def test_build_success_message_volume_set(self, service):
        """Test building volume_set message with level."""
        msg = service._build_success_message("volume_set", "TV", {"level": 50})
        assert "50" in msg
    
    def test_build_success_message_unknown_action(self, service):
        """Test building message for unknown action."""
        msg = service._build_success_message("unknown_action", "TV", None)
        assert "TV" in msg
    
    def test_build_content_action_response_show(self, service):
        """Test building show_content message."""
        msg = service._build_content_action_response("show_content", "Living Room TV")
        assert "Living Room TV" in msg
        assert "content" in msg.lower()

    def test_build_content_action_response_with_search(self, service):
        """Test building show_content message with search."""
        msg = service._build_content_action_response("show_content", "TV", search="weather")
        assert "weather" in msg.lower()

    def test_build_content_action_response_clear(self, service):
        """Test building clear_content message."""
        msg = service._build_content_action_response("clear_content", "TV")
        assert "Cleared" in msg


# ===========================================================================
# SINGLETON INSTANCE TESTS
# ===========================================================================

class TestSingletonInstance:
    """Tests for the module-level intent_service singleton."""
    
    def test_singleton_exists(self):
        """Test that singleton exists."""
        assert intent_service is not None
        assert isinstance(intent_service, IntentService)
    
    def test_singleton_has_methods(self):
        """Test that singleton has expected methods."""
        # Core orchestration methods
        assert hasattr(intent_service, "process")
        assert hasattr(intent_service, "_handle_simple_task")
        assert hasattr(intent_service, "_handle_complex_task")
        # Helper methods
        assert hasattr(intent_service, "_build_success_message")
        assert hasattr(intent_service, "_build_content_action_response")
        # Handler references
        assert hasattr(intent_service, "_device_handler")
        assert hasattr(intent_service, "_system_handler")
        assert hasattr(intent_service, "_conversation_handler")
        assert hasattr(intent_service, "_calendar_handler")
        assert hasattr(intent_service, "_display_content_handler")
        assert hasattr(intent_service, "_document_handler")


# ===========================================================================
# SERVICE INITIALIZATION TESTS
# ===========================================================================

class TestServiceInitialization:
    """Tests for IntentService initialization."""
    
    def test_service_can_be_created(self):
        """Test that service can be instantiated."""
        service = IntentService()
        assert service is not None
    
    def test_multiple_instances_are_independent(self):
        """Test that multiple instances work independently."""
        service1 = IntentService()
        service2 = IntentService()
        
        assert service1 is not service2


# ===========================================================================
# INTEGRATION-LIKE TESTS (WITH MOCKS)
# ===========================================================================

class TestProcessWithMocks:
    """Tests for process() with mocked dependencies."""
    
    @pytest.mark.asyncio
    async def test_process_handles_exception(self, service):
        """Test that process handles exceptions gracefully."""
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database error")
        
        with patch.object(service, '_get_user_devices', side_effect=Exception("DB error")):
            # Should not raise, should return error result
            result = await service.process(
                text="turn on the tv",
                user_id=uuid4(),
                db=mock_db,
            )
        
        assert result.success is False
        assert result.intent_type == IntentResultType.ERROR
        assert "error" in result.message.lower() or "failed" in result.message.lower()


# ===========================================================================
# NOTE: Device, System, and Conversation handler tests moved to respective
# handler test files (test_device_handler.py, test_system_handler.py,
# test_conversation_handler.py) as part of Sprint 3.4 refactoring.
# ===========================================================================
