"""
Commands router - handles sending commands to devices.

This module provides REST endpoints for sending commands to devices.
Commands are delivered via WebSocket to the connected Pi agents.

The command flow:
1. iOS app calls POST /commands/{device_id}
2. Server validates user owns the device
3. Server sends command via WebSocket to the Pi agent
4. Pi executes the command (HDMI-CEC, IR, etc.)
5. Pi sends acknowledgment back via WebSocket
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.device import Device
from app.services.commands import command_service, CommandType
from app.services.websocket_manager import connection_manager

# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/commands", tags=["commands"])


# ---------------------------------------------------------------------------
# REQUEST/RESPONSE SCHEMAS
# ---------------------------------------------------------------------------

class CommandRequest(BaseModel):
    """
    Schema for sending a command to a device.
    
    Example request body:
    {
        "command_type": "set_input",
        "parameters": {"input": "hdmi2"}
    }
    """
    # command_type: The type of command to send
    # Supported: power_on, power_off, set_input, volume_up, volume_down, 
    #            volume_set, mute, unmute
    command_type: str = Field(..., description="Type of command to send")
    
    # parameters: Optional parameters for the command
    # - set_input: {"input": "hdmi1"}
    # - volume_set: {"level": 50}
    parameters: Optional[dict] = Field(default=None, description="Command parameters")


class CommandResponse(BaseModel):
    """
    Schema for command response.
    
    Example response:
    {
        "success": true,
        "command_id": "550e8400-e29b-41d4-a716-446655440000",
        "message": "Command sent successfully"
    }
    """
    success: bool
    command_id: str
    message: str


class DeviceStatusResponse(BaseModel):
    """
    Schema for device connection status.
    
    Example response:
    {
        "device_id": "550e8400-e29b-41d4-a716-446655440000",
        "is_online": true,
        "last_seen": "2025-12-02T10:30:00Z"
    }
    """
    device_id: UUID
    is_online: bool
    last_seen: Optional[str]


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_user_device_or_404(db: Session, device_id: UUID, user_id: UUID) -> Device:
    """
    Get a device by ID, ensuring it belongs to the user.
    
    Raises 404 if not found, 403 if device belongs to another user.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    if device.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this device"
        )
    
    return device


# ---------------------------------------------------------------------------
# SEND COMMAND ENDPOINT
# ---------------------------------------------------------------------------

@router.post("/{device_id}", response_model=CommandResponse)
async def send_command(
    device_id: UUID,
    payload: CommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a command to a device.
    
    The command is sent via WebSocket to the connected Pi agent.
    
    Supported command types:
    - power_on: Turn the device on
    - power_off: Turn the device off
    - set_input: Switch input (requires parameters.input)
    - volume_up: Increase volume
    - volume_down: Decrease volume
    - volume_set: Set volume level (requires parameters.level)
    - mute: Mute audio
    - unmute: Unmute audio
    
    Returns immediately after sending. Use the command_id to track status.
    """
    # Verify user owns this device
    device = get_user_device_or_404(db, device_id, current_user.id)
    
    # Check if device is connected
    if not connection_manager.is_connected(device_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Device is offline"
        )
    
    # Send the command
    result = await command_service.send_command(
        device_id=device_id,
        command_type=payload.command_type,
        parameters=payload.parameters,
    )
    
    if result.success:
        return CommandResponse(
            success=True,
            command_id=result.command_id,
            message="Command sent successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Failed to send command"
        )


# ---------------------------------------------------------------------------
# QUICK COMMAND ENDPOINTS (convenience methods)
# ---------------------------------------------------------------------------

@router.post("/{device_id}/power/on", response_model=CommandResponse)
async def power_on(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Turn the device on."""
    device = get_user_device_or_404(db, device_id, current_user.id)
    
    if not connection_manager.is_connected(device_id):
        raise HTTPException(status_code=503, detail="Device is offline")
    
    result = await command_service.power_on(device_id)
    
    return CommandResponse(
        success=result.success,
        command_id=result.command_id,
        message="Power on command sent" if result.success else result.error
    )


@router.post("/{device_id}/power/off", response_model=CommandResponse)
async def power_off(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Turn the device off."""
    device = get_user_device_or_404(db, device_id, current_user.id)
    
    if not connection_manager.is_connected(device_id):
        raise HTTPException(status_code=503, detail="Device is offline")
    
    result = await command_service.power_off(device_id)
    
    return CommandResponse(
        success=result.success,
        command_id=result.command_id,
        message="Power off command sent" if result.success else result.error
    )


# ---------------------------------------------------------------------------
# CONNECTION STATUS ENDPOINT
# ---------------------------------------------------------------------------

@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
def get_device_status(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if a device is currently connected via WebSocket.
    
    Returns the connection status and last seen timestamp.
    """
    device = get_user_device_or_404(db, device_id, current_user.id)
    
    is_online = connection_manager.is_connected(device_id)
    last_seen = connection_manager.get_last_seen(device_id)
    
    return DeviceStatusResponse(
        device_id=device_id,
        is_online=is_online,
        last_seen=last_seen.isoformat() if last_seen else None
    )
