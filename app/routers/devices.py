"""
Devices router - handles device CRUD operations and pairing.

This module provides REST endpoints for:
- Creating devices (with pairing code generation)
- Listing user's devices
- Getting device details
- Updating device info
- Deleting devices
- Generating new pairing codes
- Pairing agents with devices

All endpoints except pairing require authentication.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.device import Device
from app.schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceOut,
    DeviceWithPairingCode,
    DevicePair,
    PairingCodeResponse,
)
from app.services.pairing import pairing_service
from app.services.websocket_manager import connection_manager

# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/devices", tags=["devices"])


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS (DRY principle)
# ---------------------------------------------------------------------------

def get_device_or_404(db: Session, device_id: UUID, user_id: UUID) -> Device:
    """
    Get a device by ID, ensuring it belongs to the user.
    
    Args:
        db: Database session
        device_id: UUID of the device
        user_id: UUID of the user (owner)
    
    Returns:
        Device object
    
    Raises:
        404: If device not found or doesn't belong to user
    """
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == user_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return device


def enrich_device_with_status(device: Device) -> dict:
    """
    Add real-time connection status to device data.
    
    The is_online field in the database might be stale.
    This checks the actual WebSocket connection status.
    
    Args:
        device: Device ORM object
    
    Returns:
        Dict with device data including live status
    """
    return {
        "id": device.id,
        "name": device.name,
        "agent_id": device.agent_id,
        "capabilities": device.capabilities,
        "is_online": connection_manager.is_connected(device.id),
        "last_seen": connection_manager.get_last_seen(device.id) or device.last_seen,
        "created_at": device.created_at,
    }


# ---------------------------------------------------------------------------
# CREATE DEVICE
# ---------------------------------------------------------------------------

@router.post("", response_model=DeviceWithPairingCode, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new device and generate a pairing code.
    
    The pairing code is displayed to the user and entered on the Raspberry Pi
    to link the physical device with this record.
    
    Returns the device info plus a 6-character pairing code valid for 15 minutes.
    """
    # Create the device record
    device = Device(
        name=payload.name,
        user_id=current_user.id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    # Generate pairing code
    pairing_code, expires_at = pairing_service.generate_code(device.id)
    
    # Build response with device and pairing info
    device_data = enrich_device_with_status(device)
    
    return DeviceWithPairingCode(
        device=DeviceOut(**device_data),
        pairing_code=pairing_code,
        pairing_expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# LIST DEVICES
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    online_only: bool = Query(False, description="Filter to only online devices"),
):
    """
    List all devices belonging to the current user.
    
    Query params:
        online_only: If true, only return devices with active WebSocket connections
    
    Returns a list of devices with real-time online status.
    """
    # Query user's devices
    devices = db.query(Device).filter(Device.user_id == current_user.id).all()
    
    # Enrich with live status
    result = [enrich_device_with_status(device) for device in devices]
    
    # Filter if requested
    if online_only:
        result = [d for d in result if d["is_online"]]
    
    return result


# ---------------------------------------------------------------------------
# GET SINGLE DEVICE
# ---------------------------------------------------------------------------

@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific device.
    
    Returns device info with real-time online status.
    """
    device = get_device_or_404(db, device_id, current_user.id)
    return enrich_device_with_status(device)


# ---------------------------------------------------------------------------
# UPDATE DEVICE
# ---------------------------------------------------------------------------

@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a device's information.
    
    Only provided fields will be updated.
    """
    device = get_device_or_404(db, device_id, current_user.id)
    
    # Update only provided fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)
    
    db.commit()
    db.refresh(device)
    
    return enrich_device_with_status(device)


# ---------------------------------------------------------------------------
# DELETE DEVICE
# ---------------------------------------------------------------------------

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a device.
    
    This will also disconnect any active WebSocket connection for this device.
    """
    device = get_device_or_404(db, device_id, current_user.id)
    
    # Disconnect if connected
    if connection_manager.is_connected(device.id):
        connection_manager.disconnect(device.id)
    
    db.delete(device)
    db.commit()
    
    return None


# ---------------------------------------------------------------------------
# GENERATE NEW PAIRING CODE
# ---------------------------------------------------------------------------

@router.post("/{device_id}/pairing-code", response_model=PairingCodeResponse)
def generate_pairing_code(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a new pairing code for an existing device.
    
    Use this if:
    - The original pairing code expired
    - You need to re-pair the device with a new agent
    - The device needs to be moved to a different Pi
    
    Any existing pairing code for this device is invalidated.
    """
    device = get_device_or_404(db, device_id, current_user.id)
    
    # Generate new code (invalidates any existing code)
    pairing_code, expires_at = pairing_service.generate_code(device.id)
    
    return PairingCodeResponse(
        pairing_code=pairing_code,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# PAIR DEVICE WITH AGENT (Public endpoint - called by Pi agent)
# ---------------------------------------------------------------------------

@router.post("/pair", response_model=DeviceOut)
def pair_device(
    payload: DevicePair,
    agent_id: str = Query(..., description="Unique identifier of the Pi agent"),
    db: Session = Depends(get_db),
):
    """
    Pair a Raspberry Pi agent with a device using a pairing code.
    
    This endpoint is called by the Raspberry Pi agent, NOT the iOS app.
    
    Flow:
    1. User creates device in app → gets pairing code (e.g., "A1B2C3")
    2. User enters code on Raspberry Pi
    3. Pi calls this endpoint with the code and its agent_id
    4. Server validates code and links agent to device
    
    Query params:
        agent_id: Unique identifier for the Pi agent (e.g., hostname or MAC)
    
    Note: This endpoint doesn't require user authentication because the
    pairing code serves as the authentication mechanism.
    """
    # Validate and consume the pairing code
    device_id = pairing_service.consume_code(payload.pairing_code)
    
    if device_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired pairing code"
        )
    
    # Check if agent_id is already used by another device
    existing = db.query(Device).filter(Device.agent_id == agent_id).first()
    if existing and existing.id != device_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This agent is already paired with another device"
        )
    
    # Get the device and update with agent_id
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Link the agent to the device
    device.agent_id = agent_id
    db.commit()
    db.refresh(device)
    
    return enrich_device_with_status(device)
