"""
Command service - handles sending commands to devices via WebSocket.

This service provides a clean interface for sending commands to devices:
- Abstracts WebSocket communication details
- Provides typed command methods (power_on, set_input, etc.)
- Handles command tracking (for future status updates)

Separation of concerns:
- Router handles HTTP request/response
- This service handles command logic
- WebSocket manager handles connection details
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.services.websocket_manager import connection_manager


# ---------------------------------------------------------------------------
# COMMAND TYPES
# ---------------------------------------------------------------------------
# Define the supported command types as constants for consistency

class CommandType:
    """Supported command types for device control."""
    POWER_ON = "power_on"
    POWER_OFF = "power_off"
    SET_INPUT = "set_input"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    MUTE = "mute"
    UNMUTE = "unmute"


# ---------------------------------------------------------------------------
# COMMAND RESULT
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    """
    Result of sending a command to a device.
    
    Attributes:
        success: Whether the command was sent successfully
        command_id: Unique ID for tracking the command
        error: Error message if failed
    """
    success: bool
    command_id: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# COMMAND SERVICE
# ---------------------------------------------------------------------------

class CommandService:
    """
    Service for sending commands to devices.
    
    This is the main interface for sending commands from the API.
    
    Usage:
        from app.services.commands import command_service
        
        result = await command_service.power_on(device_id)
        if result.success:
            print(f"Command sent: {result.command_id}")
    """
    
    async def send_command(
        self,
        device_id: UUID,
        command_type: str,
        parameters: Optional[dict] = None,
    ) -> CommandResult:
        """
        Send a command to a device.
        
        Args:
            device_id: UUID of the target device
            command_type: Type of command (use CommandType constants)
            parameters: Optional command parameters
        
        Returns:
            CommandResult with success status and command_id
        """
        # Generate unique command ID for tracking
        command_id = str(uuid.uuid4())
        
        # Check if device is connected
        if not connection_manager.is_connected(device_id):
            return CommandResult(
                success=False,
                command_id=command_id,
                error="Device is not connected"
            )
        
        # Send the command via WebSocket
        success = await connection_manager.send_command(
            device_id=device_id,
            command_type=command_type,
            parameters=parameters,
            command_id=command_id,
        )
        
        if success:
            return CommandResult(success=True, command_id=command_id)
        else:
            return CommandResult(
                success=False,
                command_id=command_id,
                error="Failed to send command"
            )
    
    # ---------------------------------------------------------------------------
    # CONVENIENCE METHODS (typed commands)
    # ---------------------------------------------------------------------------
    
    async def power_on(self, device_id: UUID) -> CommandResult:
        """Turn the device on."""
        return await self.send_command(device_id, CommandType.POWER_ON)
    
    async def power_off(self, device_id: UUID) -> CommandResult:
        """Turn the device off."""
        return await self.send_command(device_id, CommandType.POWER_OFF)
    
    async def set_input(self, device_id: UUID, input_name: str) -> CommandResult:
        """
        Switch the device input.
        
        Args:
            device_id: Target device
            input_name: Input name (e.g., "hdmi1", "hdmi2", "av1")
        """
        return await self.send_command(
            device_id,
            CommandType.SET_INPUT,
            {"input": input_name}
        )
    
    async def volume_up(self, device_id: UUID) -> CommandResult:
        """Increase volume by one step."""
        return await self.send_command(device_id, CommandType.VOLUME_UP)
    
    async def volume_down(self, device_id: UUID) -> CommandResult:
        """Decrease volume by one step."""
        return await self.send_command(device_id, CommandType.VOLUME_DOWN)
    
    async def volume_set(self, device_id: UUID, level: int) -> CommandResult:
        """
        Set volume to a specific level.
        
        Args:
            device_id: Target device
            level: Volume level (0-100)
        """
        return await self.send_command(
            device_id,
            CommandType.VOLUME_SET,
            {"level": max(0, min(100, level))}  # Clamp to 0-100
        )
    
    async def mute(self, device_id: UUID) -> CommandResult:
        """Mute the device."""
        return await self.send_command(device_id, CommandType.MUTE)
    
    async def unmute(self, device_id: UUID) -> CommandResult:
        """Unmute the device."""
        return await self.send_command(device_id, CommandType.UNMUTE)


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
command_service = CommandService()
