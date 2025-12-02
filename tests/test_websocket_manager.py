"""
Tests for the WebSocket connection manager.

These tests verify:
- Connection registration
- Connection removal
- Message sending to specific devices
- Handling of multiple connections
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.websocket_manager import ConnectionManager


class TestConnectionRegistration:
    """Tests for WebSocket connection registration."""
    
    @pytest.mark.asyncio
    async def test_connect_registers_device(self):
        """Should register device connection."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        
        assert manager.is_connected(device_id)
    
    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        """Should accept the WebSocket connection."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        
        websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_replaces_existing_connection(self):
        """Should replace old connection with new one for same device."""
        manager = ConnectionManager()
        device_id = uuid4()
        old_websocket = AsyncMock()
        new_websocket = AsyncMock()
        
        await manager.connect(device_id, old_websocket)
        await manager.connect(device_id, new_websocket)
        
        # Old connection should have been closed
        old_websocket.close.assert_called_once()
        # New connection is active
        assert manager.is_connected(device_id)


class TestConnectionRemoval:
    """Tests for WebSocket disconnection handling."""
    
    @pytest.mark.asyncio
    async def test_disconnect_removes_device(self):
        """Should remove device from active connections."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        manager.disconnect(device_id)
        
        assert not manager.is_connected(device_id)
    
    def test_disconnect_nonexistent_device(self):
        """Should handle disconnecting non-existent device gracefully."""
        manager = ConnectionManager()
        device_id = uuid4()
        
        # Should not raise an error
        manager.disconnect(device_id)
        
        assert not manager.is_connected(device_id)


class TestMessageSending:
    """Tests for sending messages to connected devices."""
    
    @pytest.mark.asyncio
    async def test_send_to_connected_device(self):
        """Should send message to connected device."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        
        message = {"type": "command", "action": "power_on"}
        result = await manager.send_to_device(device_id, message)
        
        assert result is True
        websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_to_disconnected_device(self):
        """Should return False for disconnected device."""
        manager = ConnectionManager()
        device_id = uuid4()
        
        message = {"type": "command", "action": "power_on"}
        result = await manager.send_to_device(device_id, message)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_command_format(self):
        """Should send command with correct message format."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        
        command_type = "power_on"
        result = await manager.send_command(device_id, command_type)
        
        assert result is True
        
        # Verify the message format
        call_args = websocket.send_json.call_args[0][0]
        assert call_args["type"] == "command"
        assert call_args["command_type"] == command_type
        assert "timestamp" in call_args
    
    @pytest.mark.asyncio
    async def test_send_command_with_parameters(self):
        """Should include parameters in command message."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        
        command_type = "set_volume"
        params = {"level": 50}
        await manager.send_command(device_id, command_type, params)
        
        # Verify parameters are included
        call_args = websocket.send_json.call_args[0][0]
        assert call_args["parameters"] == params


class TestConnectionStatus:
    """Tests for checking connection status."""
    
    @pytest.mark.asyncio
    async def test_is_connected_true(self):
        """Should return True for connected device."""
        manager = ConnectionManager()
        device_id = uuid4()
        websocket = AsyncMock()
        
        await manager.connect(device_id, websocket)
        
        assert manager.is_connected(device_id) is True
    
    def test_is_connected_false(self):
        """Should return False for disconnected device."""
        manager = ConnectionManager()
        device_id = uuid4()
        
        assert manager.is_connected(device_id) is False
    
    @pytest.mark.asyncio
    async def test_get_connection_count(self):
        """Should return correct count of connected devices."""
        manager = ConnectionManager()
        
        # Initially no connections
        assert manager.get_connection_count() == 0
        
        # Add some connections
        await manager.connect(uuid4(), AsyncMock())
        await manager.connect(uuid4(), AsyncMock())
        await manager.connect(uuid4(), AsyncMock())
        
        assert manager.get_connection_count() == 3
