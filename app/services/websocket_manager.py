"""
WebSocket Connection Manager - handles real-time connections with Pi agents.

This service manages WebSocket connections for device agents:
- Maintains a map of device_id -> WebSocket connection
- Handles connect/disconnect lifecycle
- Broadcasts commands to specific devices
- Tracks connection status (online/offline)

Using in-memory storage for MVP simplicity. Works with single server instance.
For production with multiple workers, use Redis Pub/Sub.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import WebSocket

# Configure logger for this module
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for device agents (Raspberry Pi).
    
    Each device can have ONE active connection at a time.
    If a device connects while already connected, the old connection is closed.
    
    Thread-safety note: FastAPI handles each WebSocket in its own async task,
    so dictionary operations are safe for MVP. Use async locks in production.
    """
    
    def __init__(self):
        # Map of device_id (UUID) -> WebSocket connection
        # Only connected devices are in this map
        self._connections: dict[UUID, WebSocket] = {}
        
        # Map of device_id -> last activity timestamp
        # Used to track when devices were last seen
        self._last_seen: dict[UUID, datetime] = {}
    
    async def connect(self, device_id: UUID, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection for a device.
        
        If the device already has a connection, the old one is closed first.
        This ensures one device = one connection.
        
        Args:
            device_id: UUID of the device (from pairing)
            websocket: The WebSocket connection object
        """
        # Close existing connection if any (device reconnecting)
        if device_id in self._connections:
            old_ws = self._connections[device_id]
            try:
                await old_ws.close(code=1000, reason="New connection established")
            except Exception:
                pass  # Connection might already be closed
            logger.info(f"Device {device_id}: Closed old connection")
        
        # Accept the new WebSocket connection
        await websocket.accept()
        
        # Store the connection
        self._connections[device_id] = websocket
        self._last_seen[device_id] = datetime.now(timezone.utc)
        
        logger.info(f"Device {device_id}: Connected. Total connections: {len(self._connections)}")
    
    def disconnect(self, device_id: UUID) -> None:
        """
        Remove a device's WebSocket connection.
        
        Called when the WebSocket is closed (by client or server).
        
        Args:
            device_id: UUID of the device to disconnect
        """
        if device_id in self._connections:
            del self._connections[device_id]
            logger.info(f"Device {device_id}: Disconnected. Total connections: {len(self._connections)}")
    
    def is_connected(self, device_id: UUID) -> bool:
        """
        Check if a device is currently connected.
        
        Args:
            device_id: UUID of the device to check
        
        Returns:
            True if device has an active WebSocket connection
        """
        return device_id in self._connections
    
    def get_last_seen(self, device_id: UUID) -> Optional[datetime]:
        """
        Get the last activity timestamp for a device.
        
        Args:
            device_id: UUID of the device
        
        Returns:
            Datetime of last activity, or None if never connected
        """
        return self._last_seen.get(device_id)
    
    def update_last_seen(self, device_id: UUID) -> None:
        """
        Update the last seen timestamp for a device.
        
        Call this when receiving any message from the device.
        """
        self._last_seen[device_id] = datetime.now(timezone.utc)
    
    async def send_to_device(self, device_id: UUID, message: dict[str, Any]) -> bool:
        """
        Send a JSON message to a specific device.
        
        Args:
            device_id: UUID of the target device
            message: Dictionary to send (will be JSON encoded)
        
        Returns:
            True if message was sent successfully, False if device not connected
        
        Example:
            success = await manager.send_to_device(
                device_id,
                {"type": "command", "action": "power_on"}
            )
        """
        if device_id not in self._connections:
            logger.warning(f"Device {device_id}: Not connected, cannot send message")
            return False
        
        websocket = self._connections[device_id]
        
        try:
            # Send as JSON text
            await websocket.send_json(message)
            logger.debug(f"Device {device_id}: Sent message: {message.get('type', 'unknown')}")
            return True
        except Exception as e:
            # Connection might be broken
            logger.error(f"Device {device_id}: Failed to send message: {e}")
            self.disconnect(device_id)
            return False
    
    async def send_command(
        self,
        device_id: UUID,
        command_type: str,
        parameters: Optional[dict] = None,
        command_id: Optional[str] = None,
    ) -> bool:
        """
        Send a command to a device.
        
        This is a convenience method that wraps send_to_device with a
        standard command message format.
        
        Args:
            device_id: UUID of the target device
            command_type: Type of command (e.g., "power_on", "set_input")
            parameters: Optional command parameters (e.g., {"input": "hdmi2"})
            command_id: Optional unique ID for tracking command status
        
        Returns:
            True if command was sent successfully
        
        Message format sent to device:
        {
            "type": "command",
            "command_id": "abc123",
            "command_type": "power_on",
            "parameters": {},
            "timestamp": "2025-12-02T10:30:00Z"
        }
        """
        message = {
            "type": "command",
            "command_type": command_type,
            "parameters": parameters or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if command_id:
            message["command_id"] = command_id
        
        return await self.send_to_device(device_id, message)
    
    async def broadcast_to_all(self, message: dict[str, Any]) -> dict[UUID, bool]:
        """
        Send a message to ALL connected devices.
        
        Useful for system-wide announcements or shutdown notices.
        
        Args:
            message: Dictionary to send to all devices
        
        Returns:
            Dict of device_id -> success (True/False for each device)
        """
        results = {}
        
        # Create a copy of keys to avoid dict modification during iteration
        device_ids = list(self._connections.keys())
        
        for device_id in device_ids:
            results[device_id] = await self.send_to_device(device_id, message)
        
        return results
    
    def get_connected_device_ids(self) -> list[UUID]:
        """
        Get a list of all currently connected device IDs.
        
        Returns:
            List of UUIDs for connected devices
        """
        return list(self._connections.keys())
    
    def get_connection_count(self) -> int:
        """
        Get the total number of active connections.
        
        Returns:
            Number of connected devices
        """
        return len(self._connections)


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance to use throughout the application.
# This ensures all WebSocket connections are managed in one place.
# 
# Usage: from app.services.websocket_manager import connection_manager
connection_manager = ConnectionManager()
