"""
Tests for the Intent Parser and Device Mapper.

These tests verify:
- Intent parsing from natural language
- Device name matching
- Command structure creation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.ai.intent.schemas import (
    IntentType,
    ActionType,
    DeviceCommand,
    DeviceQuery,
    SystemQuery,
    ConversationIntent,
)
from app.ai.intent.parser import IntentParser
from app.ai.intent.device_mapper import DeviceMapper


# ---------------------------------------------------------------------------
# DEVICE MAPPER TESTS
# ---------------------------------------------------------------------------

class TestDeviceMapper:
    """Tests for the DeviceMapper class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = DeviceMapper()
        
        # Create mock devices
        self.device1 = MagicMock()
        self.device1.id = uuid4()
        self.device1.name = "Living Room TV"
        self.device1.is_online = True
        
        self.device2 = MagicMock()
        self.device2.id = uuid4()
        self.device2.name = "Bedroom Monitor"
        self.device2.is_online = False
        
        self.device3 = MagicMock()
        self.device3.id = uuid4()
        self.device3.name = "Office Display"
        self.device3.is_online = True
        
        self.devices = [self.device1, self.device2, self.device3]
    
    def test_exact_match(self):
        """Test exact name matching."""
        device, score = self.mapper.match("Living Room TV", self.devices)
        assert device is not None
        assert device.id == self.device1.id
        assert score > 0.9
    
    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        device, score = self.mapper.match("living room tv", self.devices)
        assert device is not None
        assert device.id == self.device1.id
        assert score > 0.8
    
    def test_partial_match(self):
        """Test partial name matching."""
        device, score = self.mapper.match("living room", self.devices)
        assert device is not None
        assert device.id == self.device1.id
        assert score > 0.6
    
    def test_fuzzy_match(self):
        """Test fuzzy matching with typos."""
        device, score = self.mapper.match("livingroom tv", self.devices)
        assert device is not None
        assert device.id == self.device1.id
    
    def test_no_match(self):
        """Test when no device matches."""
        device, score = self.mapper.match("Kitchen Display", self.devices)
        # Should return None or low-confidence match
        if device is not None:
            assert score < 0.6
    
    def test_empty_devices(self):
        """Test with empty device list."""
        device, score = self.mapper.match("Living Room TV", [])
        assert device is None
        assert score == 0.0
    
    def test_empty_name(self):
        """Test with empty device name."""
        device, score = self.mapper.match("", self.devices)
        assert device is None
    
    def test_match_all(self):
        """Test getting multiple potential matches."""
        matches = self.mapper.match_all("room", self.devices)
        assert len(matches) > 0
        # Living Room TV should be in the matches
        device_ids = [d.id for d, _ in matches]
        assert self.device1.id in device_ids
    
    def test_tv_television_normalization(self):
        """Test that 'television' matches 'TV'."""
        device, score = self.mapper.match("Living Room Television", self.devices)
        assert device is not None
        assert device.id == self.device1.id
    
    def test_to_device_context(self):
        """Test converting devices to context format."""
        context = self.mapper.to_device_context(self.devices)
        assert len(context) == 3
        assert context[0]["name"] == "Living Room TV"
        assert "id" in context[0]
        assert "is_online" in context[0]


# ---------------------------------------------------------------------------
# INTENT PARSER TESTS (with mocked LLM)
# ---------------------------------------------------------------------------

class TestIntentParser:
    """Tests for the IntentParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IntentParser()
    
    @pytest.mark.asyncio
    async def test_parse_power_on_command(self):
        """Test parsing a power on command."""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = '''
        {
            "intent_type": "device_command",
            "confidence": 0.95,
            "device_name": "living room TV",
            "action": "power_on",
            "parameters": null,
            "original_text": "Turn on the living room TV",
            "reasoning": "Power on command"
        }
        '''
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            intent = await self.parser.parse("Turn on the living room TV")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.device_name == "living room TV"
            assert intent.action == ActionType.POWER_ON
            assert intent.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_parse_set_input_command(self):
        """Test parsing an input change command."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = '''
        {
            "intent_type": "device_command",
            "confidence": 0.9,
            "device_name": "bedroom monitor",
            "action": "set_input",
            "parameters": {"app": "calendar"},
            "original_text": "Show the calendar on bedroom monitor",
            "reasoning": "Display app command"
        }
        '''
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            intent = await self.parser.parse("Show the calendar on bedroom monitor")
            
            assert isinstance(intent, DeviceCommand)
            assert intent.device_name == "bedroom monitor"
            assert intent.action == ActionType.SET_INPUT
            assert intent.parameters == {"app": "calendar"}
    
    @pytest.mark.asyncio
    async def test_parse_device_query(self):
        """Test parsing a device status query."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = '''
        {
            "intent_type": "device_query",
            "confidence": 0.9,
            "device_name": "kitchen TV",
            "action": "status",
            "parameters": null,
            "original_text": "Is the kitchen TV on?",
            "reasoning": "Status query"
        }
        '''
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            intent = await self.parser.parse("Is the kitchen TV on?")
            
            assert isinstance(intent, DeviceQuery)
            assert intent.device_name == "kitchen TV"
            assert intent.action == ActionType.STATUS
    
    @pytest.mark.asyncio
    async def test_parse_system_query(self):
        """Test parsing a system query."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = '''
        {
            "intent_type": "system_query",
            "confidence": 0.9,
            "device_name": null,
            "action": "list_devices",
            "parameters": null,
            "original_text": "What devices do I have?",
            "reasoning": "Device list query"
        }
        '''
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            intent = await self.parser.parse("What devices do I have?")
            
            assert isinstance(intent, SystemQuery)
            assert intent.action == ActionType.LIST_DEVICES
    
    @pytest.mark.asyncio
    async def test_parse_conversation(self):
        """Test parsing a conversational input."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = '''
        {
            "intent_type": "conversation",
            "confidence": 0.95,
            "device_name": null,
            "action": "greeting",
            "parameters": null,
            "original_text": "Hello!",
            "reasoning": "Greeting"
        }
        '''
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            intent = await self.parser.parse("Hello!")
            
            assert isinstance(intent, ConversationIntent)
            assert intent.action == ActionType.GREETING
    
    @pytest.mark.asyncio
    async def test_parse_failure_returns_unknown(self):
        """Test that parse failures return unknown intent."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "API error"
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            intent = await self.parser.parse("Something random")
            
            assert intent.intent_type == IntentType.UNKNOWN
            assert intent.confidence == 0.0
    
    @pytest.mark.asyncio
    async def test_create_parsed_command(self):
        """Test the full parsed command creation."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = '''
        {
            "intent_type": "device_command",
            "confidence": 0.95,
            "device_name": "living room TV",
            "action": "power_on",
            "parameters": null,
            "original_text": "Turn on the TV",
            "reasoning": "Power command"
        }
        '''
        
        with patch.object(self.parser.provider, 'generate_json', return_value=mock_response):
            parsed = await self.parser.create_parsed_command("Turn on the TV")
            
            assert parsed.request_id is not None
            assert parsed.device_name == "living room TV"
            assert parsed.action == "power_on"
            assert parsed.processing_time_ms is not None


# ---------------------------------------------------------------------------
# INTEGRATION-LIKE TESTS
# ---------------------------------------------------------------------------

class TestIntentToCommand:
    """Tests for the full intent-to-command flow."""
    
    def test_action_mapping(self):
        """Test that all action strings map correctly."""
        parser = IntentParser()
        
        mappings = {
            "power_on": ActionType.POWER_ON,
            "power_off": ActionType.POWER_OFF,
            "set_input": ActionType.SET_INPUT,
            "volume_up": ActionType.VOLUME_UP,
            "volume_down": ActionType.VOLUME_DOWN,
            "volume_set": ActionType.VOLUME_SET,
            "mute": ActionType.MUTE,
            "unmute": ActionType.UNMUTE,
            "status": ActionType.STATUS,
            "list_devices": ActionType.LIST_DEVICES,
            "greeting": ActionType.GREETING,
        }
        
        for action_str, expected_type in mappings.items():
            result = parser._map_action(action_str)
            assert result == expected_type, f"Failed for {action_str}"
