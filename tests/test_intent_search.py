"""
Tests for Intent Search - Sprint 3.7

Tests for:
- Intent parsing of search-related commands
- _execute_content_action with search parameter
- URL encoding of search terms
- _build_content_message with search context

All LLM calls are mocked for fast, reliable tests.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.ai.intent.parser import IntentParser, intent_parser
from app.ai.intent.schemas import (
    IntentType,
    ActionType,
    DeviceCommand,
)
from app.ai.providers.base import AIResponse, ProviderType
from app.services.intent_service import IntentService, IntentResult, IntentResultType


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
def parser():
    """Create a fresh parser instance."""
    return IntentParser()


@pytest.fixture
def service():
    """Create a fresh IntentService instance."""
    return IntentService()


@pytest.fixture
def mock_device():
    """Create a mock online device."""
    return MockDevice("Living Room TV", is_online=True)


def _create_mock_response(content: dict) -> AIResponse:
    """Helper to create mock AI response."""
    return AIResponse(
        content=json.dumps(content),
        provider=ProviderType.GEMINI,
        model="gemini-1.5-flash",
        success=True,
    )


# ===========================================================================
# INTENT PARSER SEARCH TESTS
# ===========================================================================

class TestParseCalendarSearch:
    """Tests for parsing calendar search commands."""
    
    @pytest.mark.asyncio
    async def test_parse_calendar_search_birthday(self, parser):
        """Test parsing 'show my birthday' extracts search term."""
        mock_response = _create_mock_response({
            "intent_type": "device_command",
            "device_name": "living room TV",
            "action": "show_calendar",
            "parameters": {"search": "birthday"},
            "confidence": 0.95,
            "reasoning": "Calendar search for birthday events",
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Show my birthday on the living room TV")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.SHOW_CALENDAR
            assert intent.parameters is not None
            assert intent.parameters.get("search") == "birthday"
    
    @pytest.mark.asyncio
    async def test_parse_calendar_search_dentist(self, parser):
        """Test parsing 'when is my dentist' extracts search term.
        
        Note: DeviceCommand requires a device_name, so when device is null,
        the parser falls back to a default device or returns as a system query.
        For this test, we include a device name.
        """
        mock_response = _create_mock_response({
            "intent_type": "device_command",
            "device_name": "living room TV",  # Device required for DeviceCommand
            "action": "show_calendar",
            "parameters": {"search": "dentist"},
            "confidence": 0.92,
            "reasoning": "Calendar search for dentist",
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("When is my dentist appointment on the TV")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.SHOW_CALENDAR
            assert intent.parameters.get("search") == "dentist"
    
    @pytest.mark.asyncio
    async def test_parse_calendar_search_with_date(self, parser):
        """Test parsing combined date + search query."""
        mock_response = _create_mock_response({
            "intent_type": "device_command",
            "device_name": "office display",
            "action": "show_calendar",
            "parameters": {"date": "2025-12-13", "search": "meeting"},
            "confidence": 0.95,
            "reasoning": "Combined date and search query",
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Show meetings tomorrow on the office display")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.SHOW_CALENDAR
            assert intent.parameters.get("date") == "2025-12-13"
            assert intent.parameters.get("search") == "meeting"
    
    @pytest.mark.asyncio
    async def test_parse_calendar_search_with_device(self, parser):
        """Test parsing search with specific device."""
        mock_response = _create_mock_response({
            "intent_type": "device_command",
            "device_name": "bedroom monitor",
            "action": "show_calendar",
            "parameters": {"search": "team standup"},
            "confidence": 0.94,
            "reasoning": "Search for team standup events",
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Find my team standup on the bedroom monitor")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.device_name == "bedroom monitor"
            assert intent.parameters.get("search") == "team standup"


# ===========================================================================
# INTENT SERVICE SEARCH TESTS
# ===========================================================================

class TestExecuteContentActionWithSearch:
    """Tests for _execute_content_action with search parameter."""
    
    @pytest.mark.asyncio
    async def test_execute_content_action_with_search(self, service, mock_device):
        """Test that search parameter is included in URL."""
        from app.services.commands import command_service
        
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.command_id = "cmd-123"
        mock_result.error = None
        
        with patch.object(command_service, 'show_content', new_callable=AsyncMock) as mock_show:
            mock_show.return_value = mock_result
            
            with patch('app.services.content_token.content_token_service.generate') as mock_token:
                mock_token.return_value = "test_token"
                
                result = await service._execute_content_action(
                    request_id="req-123",
                    device=mock_device,
                    action="show_calendar",
                    user_id=mock_device.user_id,
                    parameters={"search": "birthday"},
                    confidence=0.95,
                    start_time=0,
                )
                
                # Verify URL includes search parameter
                call_args = mock_show.call_args
                url = call_args[1]["url"]
                assert "search=birthday" in url
    
    @pytest.mark.asyncio
    async def test_execute_content_action_search_url_encoded(self, service, mock_device):
        """Test that search term is URL encoded."""
        from app.services.commands import command_service
        
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.command_id = "cmd-123"
        mock_result.error = None
        
        with patch.object(command_service, 'show_content', new_callable=AsyncMock) as mock_show:
            mock_show.return_value = mock_result
            
            with patch('app.services.content_token.content_token_service.generate') as mock_token:
                mock_token.return_value = "test_token"
                
                result = await service._execute_content_action(
                    request_id="req-123",
                    device=mock_device,
                    action="show_calendar",
                    user_id=mock_device.user_id,
                    parameters={"search": "team meeting"},
                    confidence=0.95,
                    start_time=0,
                )
                
                call_args = mock_show.call_args
                url = call_args[1]["url"]
                # Space should be URL encoded
                assert "team%20meeting" in url or "team+meeting" in url
    
    @pytest.mark.asyncio
    async def test_execute_content_action_date_and_search(self, service, mock_device):
        """Test that both date and search are included."""
        from app.services.commands import command_service
        
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.command_id = "cmd-123"
        mock_result.error = None
        
        with patch.object(command_service, 'show_content', new_callable=AsyncMock) as mock_show:
            mock_show.return_value = mock_result
            
            with patch('app.services.content_token.content_token_service.generate') as mock_token:
                mock_token.return_value = "test_token"
                
                result = await service._execute_content_action(
                    request_id="req-123",
                    device=mock_device,
                    action="show_calendar",
                    user_id=mock_device.user_id,
                    parameters={"date": "2025-12-15", "search": "meeting"},
                    confidence=0.95,
                    start_time=0,
                )
                
                call_args = mock_show.call_args
                url = call_args[1]["url"]
                assert "date=2025-12-15" in url
                assert "search=meeting" in url


# ===========================================================================
# BUILD CONTENT MESSAGE TESTS
# ===========================================================================

class TestBuildContentMessage:
    """Tests for _build_content_message with search context."""
    
    def test_message_with_search_only(self, service):
        """Test message includes search context."""
        message = service._build_content_message(
            action="show_calendar",
            device_name="Living Room TV",
            search="birthday",
        )
        
        assert "birthday" in message
        assert "Living Room TV" in message
    
    def test_message_with_date_and_search(self, service):
        """Test message includes both date and search."""
        message = service._build_content_message(
            action="show_calendar",
            device_name="Office Display",
            date="2025-12-15",
            search="meeting",
        )
        
        assert "meeting" in message
        assert "2025-12-15" in message
        assert "Office Display" in message
    
    def test_message_without_search(self, service):
        """Test message without search is normal."""
        message = service._build_content_message(
            action="show_calendar",
            device_name="Bedroom Monitor",
        )
        
        assert "Displaying calendar on Bedroom Monitor" in message
    
    def test_message_clear_content(self, service):
        """Test clear content message unchanged."""
        message = service._build_content_message(
            action="clear_content",
            device_name="Living Room TV",
            search="birthday",  # Should be ignored
        )
        
        assert "Cleared display" in message
        assert "birthday" not in message


# ===========================================================================
# ACTION REGISTRY SEARCH TESTS
# ===========================================================================

class TestActionRegistrySearch:
    """Tests for search parameter in action registry."""
    
    def test_show_calendar_has_search_param(self):
        """Test show_calendar action accepts search parameter."""
        from app.ai.actions.registry import action_registry
        
        action = action_registry.get_action("show_calendar")
        
        assert action is not None
        assert "search" in action.optional_params
    
    def test_show_calendar_validates_with_search(self):
        """Test show_calendar validates with search parameter."""
        from app.ai.actions.registry import action_registry
        
        is_valid, error = action_registry.validate(
            "show_calendar",
            {"target_device": "TV", "search": "birthday"},
        )
        
        assert is_valid is True
        assert error is None
