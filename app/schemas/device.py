"""
Device schemas - Pydantic models for device CRUD operations.
These define the request/response formats for device management endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# REQUEST SCHEMAS (what the client sends)
# ---------------------------------------------------------------------------

class DeviceCreate(BaseModel):
    """
    Schema for creating a new device.
    
    Example request body:
    {
        "name": "Living Room TV"
    }
    """
    # name: Human-friendly name for the device
    # - Required field, 1-100 characters
    # - Will be displayed in the iOS app
    name: str = Field(..., min_length=1, max_length=100, description="Device display name")


class DeviceUpdate(BaseModel):
    """
    Schema for updating an existing device.
    
    All fields are optional - only provided fields will be updated.
    
    Example request body:
    {
        "name": "Bedroom TV"
    }
    """
    # name: Optional new name for the device
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    
    # capabilities: Optional JSON object describing device features
    # - Set by the agent after detecting TV capabilities via HDMI-CEC
    # - Example: {"power": true, "volume": true, "input": ["hdmi1", "hdmi2"]}
    capabilities: Optional[dict] = None


class DevicePair(BaseModel):
    """
    Schema for pairing a device with an agent using a pairing code.
    
    The flow:
    1. User creates a device in the app → gets a pairing code
    2. User enters the code on the Raspberry Pi
    3. Pi calls this endpoint with the code to link itself
    
    Example request body:
    {
        "pairing_code": "A1B2C3"
    }
    """
    # pairing_code: 6-character alphanumeric code
    pairing_code: str = Field(..., min_length=6, max_length=6, description="6-character pairing code")


# ---------------------------------------------------------------------------
# RESPONSE SCHEMAS (what the server returns)
# ---------------------------------------------------------------------------

class DeviceOut(BaseModel):
    """
    Schema for device data in API responses.
    
    Used when returning device information to the client.
    
    Example response:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Living Room TV",
        "agent_id": "pi-agent-abc123",
        "capabilities": {"power": true, "volume": true},
        "is_online": true,
        "is_paired": true,
        "last_seen": "2025-12-02T10:30:00Z",
        "created_at": "2025-12-01T08:00:00Z"
    }
    """
    id: uuid.UUID
    name: str
    agent_id: Optional[str]
    capabilities: Optional[dict]
    is_online: bool
    last_seen: Optional[datetime]
    created_at: datetime
    
    # Computed property: device is paired if it has an agent_id
    @property
    def is_paired(self) -> bool:
        return self.agent_id is not None

    class Config:
        # Allow creating from SQLAlchemy ORM objects
        from_attributes = True


class DeviceWithPairingCode(BaseModel):
    """
    Schema for device creation response that includes the pairing code.
    
    Only returned when a new device is created - the pairing code
    is temporary and should be displayed to the user immediately.
    
    Example response:
    {
        "device": { ... device data ... },
        "pairing_code": "A1B2C3",
        "pairing_expires_at": "2025-12-02T10:45:00Z"
    }
    """
    device: DeviceOut
    pairing_code: str
    pairing_expires_at: datetime


class PairingCodeResponse(BaseModel):
    """
    Schema for generating a new pairing code for an existing device.
    
    Example response:
    {
        "pairing_code": "X9Y8Z7",
        "expires_at": "2025-12-02T10:45:00Z"
    }
    """
    pairing_code: str
    expires_at: datetime
