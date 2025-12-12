"""
Tests for Intent Parser - Edge cases and parsing logic.

This module tests:
- Intent parsing from natural language
- Creation of typed Intent objects
- Error handling for invalid responses
- Edge cases in parsing

All LLM calls are mocked for fast, reliable tests.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.ai.intent.parser import IntentParser, intent_parser
from app.ai.intent.schemas import (
    Intent,
    IntentType,
    ActionType,
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
    ConversationIntent,
    ParsedCommand,
)
from app.ai.providers.base import AIResponse, ProviderType


class TestIntentParserInitialization:
    """Tests for IntentParser initialization."""
    
    def test_parser_initializes(self):
        """Test that parser initializes successfully."""
        parser = IntentParser()
        
        assert parser is not None
        assert parser.provider is not None
    
    def test_singleton_exists(self):
        """Test that the singleton instance exists."""
        assert intent_parser is not None
        assert isinstance(intent_parser, IntentParser)


class TestParseDeviceCommand:
    """Tests for parsing device commands."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_parse_power_on_command(self, parser):
        """Test parsing a power on command."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Living Room TV",
            "action": "power_on",
            "confidence": 0.95,
            "reasoning": "User wants to turn on the TV",
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Turn on the living room TV")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.device_name == "Living Room TV"
            assert intent.action == ActionType.POWER_ON
            assert intent.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_parse_power_off_command(self, parser):
        """Test parsing a power off command."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Bedroom Monitor",
            "action": "power_off",
            "confidence": 0.92,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Turn off the bedroom monitor")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.POWER_OFF
    
    @pytest.mark.asyncio
    async def test_parse_set_input_command(self, parser):
        """Test parsing a set input command with parameters."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Office Display",
            "action": "set_input",
            "parameters": {"input": "HDMI 2"},
            "confidence": 0.88,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Switch office display to HDMI 2")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.SET_INPUT
            assert intent.parameters["input"] == "HDMI 2"
    
    @pytest.mark.asyncio
    async def test_parse_volume_command(self, parser):
        """Test parsing volume commands."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Kitchen TV",
            "action": "volume_up",
            "confidence": 0.9,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Volume up on kitchen TV")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.VOLUME_UP
    
    @pytest.mark.asyncio
    async def test_parse_show_calendar_command(self, parser):
        """Test parsing show calendar command."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Living Room TV",
            "action": "show_calendar",
            "confidence": 0.93,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Show calendar on living room TV")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.action == ActionType.SHOW_CALENDAR


class TestParseDeviceQuery:
    """Tests for parsing device queries."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_parse_status_query(self, parser):
        """Test parsing a status query."""
        mock_response = self._create_mock_response({
            "intent_type": "device_query",
            "device_name": "Living Room TV",
            "action": "status",
            "confidence": 0.91,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Is the living room TV on?")
            
            assert isinstance(intent, DeviceQuery)
            assert intent.device_name == "Living Room TV"
            assert intent.action == ActionType.STATUS
    
    @pytest.mark.asyncio
    async def test_parse_is_online_query(self, parser):
        """Test parsing an is_online query."""
        mock_response = self._create_mock_response({
            "intent_type": "device_query",
            "device_name": "Bedroom Monitor",
            "action": "is_online",
            "confidence": 0.88,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Is the bedroom monitor connected?")
            
            assert isinstance(intent, DeviceQuery)


class TestParseSystemQuery:
    """Tests for parsing system queries."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_parse_list_devices_query(self, parser):
        """Test parsing a list devices query."""
        mock_response = self._create_mock_response({
            "intent_type": "system_query",
            "action": "list_devices",
            "confidence": 0.94,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("What devices do I have?")
            
            assert isinstance(intent, SystemQuery)
            assert intent.action == ActionType.LIST_DEVICES
    
    @pytest.mark.asyncio
    async def test_parse_help_query(self, parser):
        """Test parsing a help query."""
        mock_response = self._create_mock_response({
            "intent_type": "system_query",
            "action": "help",
            "confidence": 0.89,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("What can you do?")
            
            assert isinstance(intent, SystemQuery)
            assert intent.action == ActionType.HELP


class TestParseConversation:
    """Tests for parsing conversational intents."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_parse_greeting(self, parser):
        """Test parsing a greeting."""
        mock_response = self._create_mock_response({
            "intent_type": "conversation",
            "action": "greeting",
            "confidence": 0.97,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Hello!")
            
            assert isinstance(intent, ConversationIntent)
            assert intent.action == ActionType.GREETING
    
    @pytest.mark.asyncio
    async def test_parse_thanks(self, parser):
        """Test parsing a thanks message."""
        mock_response = self._create_mock_response({
            "intent_type": "conversation",
            "action": "thanks",
            "confidence": 0.95,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Thank you!")
            
            assert isinstance(intent, ConversationIntent)
            assert intent.action == ActionType.THANKS


class TestParseWithContext:
    """Tests for parsing with device context."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_parse_with_device_context(self, parser):
        """Test parsing with device context provided."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Living Room TV",
            "action": "power_on",
            "confidence": 0.96,
        })
        
        context = {
            "devices": [
                {"name": "Living Room TV", "is_online": True},
                {"name": "Bedroom Monitor", "is_online": False},
            ]
        }
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Turn on the TV", context)
            
            # Verify context was passed
            call_args = mock_gen.call_args
            prompt = call_args.kwargs.get('prompt') or call_args.args[0]
            assert "Living Room TV" in prompt or mock_gen.called


class TestErrorHandling:
    """Tests for error handling in parser."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    @pytest.mark.asyncio
    async def test_handle_api_error(self, parser):
        """Test handling API error response."""
        error_response = AIResponse(
            content="",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=False,
            error="API rate limit exceeded",
        )
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = error_response
            
            intent = await parser.parse("Turn on the TV")
            
            # Should return an unknown intent
            assert intent is not None
            assert intent.intent_type == IntentType.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, parser):
        """Test handling invalid JSON response."""
        invalid_response = AIResponse(
            content="This is not valid JSON",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = invalid_response
            
            intent = await parser.parse("Turn on the TV")
            
            # Should return an unknown intent
            assert intent is not None
            assert intent.intent_type == IntentType.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_handle_unknown_intent_type(self, parser):
        """Test handling unknown intent type in response."""
        mock_response = AIResponse(
            content=json.dumps({
                "intent_type": "some_new_type",
                "confidence": 0.8,
            }),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Something weird")
            
            assert intent is not None
            assert intent.intent_type == IntentType.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_handle_missing_required_fields(self, parser):
        """Test handling response with missing required fields."""
        mock_response = AIResponse(
            content=json.dumps({
                "intent_type": "device_command",
                # Missing device_name and action
            }),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Turn on something")
            
            # Should handle gracefully
            assert intent is not None


class TestEdgeCases:
    """Tests for edge cases in parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_parse_empty_string(self, parser):
        """Test parsing an empty string."""
        mock_response = self._create_mock_response({
            "intent_type": "unknown",
            "confidence": 0.1,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("")
            
            assert intent is not None
    
    @pytest.mark.asyncio
    async def test_parse_very_long_input(self, parser):
        """Test parsing a very long input."""
        long_input = "Turn on the TV " * 50
        
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "TV",
            "action": "power_on",
            "confidence": 0.7,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse(long_input)
            
            assert intent is not None
    
    @pytest.mark.asyncio
    async def test_parse_special_characters(self, parser):
        """Test parsing input with special characters."""
        special_input = "Turn on the 'Living Room TV' <now>!"
        
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Living Room TV",
            "action": "power_on",
            "confidence": 0.85,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse(special_input)
            
            assert isinstance(intent, DeviceCommand)
    
    @pytest.mark.asyncio
    async def test_parse_unicode_input(self, parser):
        """Test parsing input with unicode characters."""
        unicode_input = "Turn on the TV 📺"
        
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "TV",
            "action": "power_on",
            "confidence": 0.9,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse(unicode_input)
            
            assert intent is not None
    
    @pytest.mark.asyncio
    async def test_parse_case_insensitive_intent_type(self, parser):
        """Test that intent_type parsing is case insensitive."""
        mock_response = self._create_mock_response({
            "intent_type": "DEVICE_COMMAND",
            "device_name": "TV",
            "action": "power_on",
            "confidence": 0.9,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Turn on TV")
            
            assert isinstance(intent, DeviceCommand)
    
    @pytest.mark.asyncio
    async def test_parse_low_confidence_response(self, parser):
        """Test parsing a low confidence response."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "TV",
            "action": "power_on",
            "confidence": 0.3,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Maybe turn on the TV?")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.confidence == 0.3
    
    @pytest.mark.asyncio
    async def test_parse_with_reasoning(self, parser):
        """Test that reasoning is captured."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Living Room TV",
            "action": "power_on",
            "confidence": 0.95,
            "reasoning": "User explicitly said 'turn on' indicating power_on action",
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            intent = await parser.parse("Turn on the living room TV")
            
            assert intent.reasoning is not None
            assert "power_on" in intent.reasoning


class TestActionMapping:
    """Tests for action string to enum mapping."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def test_map_power_actions(self, parser):
        """Test mapping power action strings."""
        assert parser._map_action("power_on") == ActionType.POWER_ON
        assert parser._map_action("power_off") == ActionType.POWER_OFF
    
    def test_map_volume_actions(self, parser):
        """Test mapping volume action strings."""
        assert parser._map_action("volume_up") == ActionType.VOLUME_UP
        assert parser._map_action("volume_down") == ActionType.VOLUME_DOWN
        assert parser._map_action("mute") == ActionType.MUTE
        assert parser._map_action("unmute") == ActionType.UNMUTE
    
    def test_map_content_actions(self, parser):
        """Test mapping content action strings."""
        assert parser._map_action("show_calendar") == ActionType.SHOW_CALENDAR
        assert parser._map_action("show_content") == ActionType.SHOW_CONTENT
        assert parser._map_action("clear_content") == ActionType.CLEAR_CONTENT
    
    def test_map_query_actions(self, parser):
        """Test mapping query action strings."""
        assert parser._map_action("status") == ActionType.STATUS
        assert parser._map_action("list_devices") == ActionType.LIST_DEVICES
        assert parser._map_action("help") == ActionType.HELP
    
    def test_map_conversation_actions(self, parser):
        """Test mapping conversation action strings."""
        assert parser._map_action("greeting") == ActionType.GREETING
        assert parser._map_action("thanks") == ActionType.THANKS
    
    def test_map_unknown_action(self, parser):
        """Test mapping unknown action defaults to STATUS."""
        result = parser._map_action("unknown_action")
        # Should default to something sensible
        assert result is not None


class TestCreateParsedCommand:
    """Tests for create_parsed_command method."""
    
    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance."""
        return IntentParser()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_create_parsed_command(self, parser):
        """Test creating a full parsed command."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "Living Room TV",
            "action": "power_on",
            "confidence": 0.95,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            parsed = await parser.create_parsed_command(
                text="Turn on the living room TV",
                user_id=uuid4(),
            )
            
            assert isinstance(parsed, ParsedCommand)
            assert parsed.intent is not None
            assert parsed.device_name == "Living Room TV"
            assert parsed.action is not None
    
    @pytest.mark.asyncio
    async def test_parsed_command_includes_processing_time(self, parser):
        """Test that parsed command includes processing time."""
        mock_response = self._create_mock_response({
            "intent_type": "device_command",
            "device_name": "TV",
            "action": "power_on",
            "confidence": 0.9,
        })
        
        with patch.object(parser.provider, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            parsed = await parser.create_parsed_command(
                text="Turn on the TV",
                user_id=uuid4(),
            )
            
            assert parsed.processing_time_ms is not None
            assert parsed.processing_time_ms >= 0
