"""
Device model - represents a display device (TV, monitor) in the Jarvis system.
Each device is connected to a Raspberry Pi agent (Jarvis Stick) that executes commands.
"""

import uuid  # For generating unique device identifiers
from datetime import datetime, timezone  # For timestamps

from sqlalchemy import String, DateTime, ForeignKey, JSON  # Column types
from sqlalchemy.dialects.postgresql import UUID  # PostgreSQL UUID type
from sqlalchemy.orm import Mapped, mapped_column, relationship  # SQLAlchemy 2.0 ORM

from app.db.base import Base  # Declarative base class


class Device(Base):
    """
    SQLAlchemy ORM model for the 'devices' table.
    
    A Device represents a screen (TV, monitor) that can be controlled.
    It's connected to a Raspberry Pi running the Jarvis Stick agent.
    
    Example: "Living Room TV" connected via HDMI-CEC to a Pi.
    """
    
    # The actual table name in PostgreSQL
    __tablename__ = "devices"

    # ---------------------------------------------------------------------------
    # PRIMARY KEY
    # ---------------------------------------------------------------------------
    # id: Unique identifier for each device
    # - UUID for global uniqueness across distributed systems
    # - Auto-generated on device creation
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ---------------------------------------------------------------------------
    # FOREIGN KEY - OWNER RELATIONSHIP
    # ---------------------------------------------------------------------------
    # user_id: References the user who owns this device
    # - ForeignKey("users.id"): Links to the 'id' column in 'users' table
    # - ondelete="CASCADE": If the user is deleted, delete their devices too
    #   (prevents orphaned devices in the database)
    # - nullable=False: Every device must have an owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # ---------------------------------------------------------------------------
    # DEVICE INFORMATION
    # ---------------------------------------------------------------------------
    # name: Human-friendly name for the device
    # - Examples: "Living Room TV", "Bedroom Monitor", "Office Display"
    # - Shown in the iOS app for device selection
    # - nullable=False: Every device needs a name
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # agent_id: Unique identifier of the Raspberry Pi agent connected to this device
    # - Set when a Jarvis Stick pairs with this device record
    # - unique=True: One agent can only be linked to one device
    # - nullable=True: Device can exist before agent is paired (during onboarding)
    # - Used to route commands to the correct Pi
    agent_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)

    # capabilities: JSON object describing what this device can do
    # - Example: {"power": true, "volume": true, "input": ["hdmi1", "hdmi2"], "brightness": false}
    # - Populated by the agent after it detects the TV's features via HDMI-CEC
    # - The iOS app uses this to show only available controls
    # - nullable=True: May not be known until agent reports
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ---------------------------------------------------------------------------
    # CONNECTION STATUS
    # ---------------------------------------------------------------------------
    # is_online: Whether the Raspberry Pi agent is currently connected
    # - True: Agent has an active connection to the cloud
    # - False: Agent is offline or disconnected
    # - Updated via WebSocket/MQTT heartbeats from the agent
    is_online: Mapped[bool] = mapped_column(default=False)

    # last_seen: Timestamp of the last communication from the agent
    # - Updated on every heartbeat or command acknowledgment
    # - Useful for detecting stale connections and debugging
    # - nullable=True: No contact yet if device was just created
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---------------------------------------------------------------------------
    # TIMESTAMPS
    # ---------------------------------------------------------------------------
    # created_at: When the device was added to the system
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # updated_at: When the device record was last modified
    # - Auto-updates on any change (name, capabilities, status, etc.)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ---------------------------------------------------------------------------
    # RELATIONSHIPS
    # ---------------------------------------------------------------------------
    # owner: Many-to-one relationship with User model
    # - Each device belongs to exactly one user
    # - Mapped["User"]: Type hint for the User object
    # - back_populates="devices": Links to User.devices for bidirectional access
    # - Usage: device.owner returns the User object who owns this device
    owner: Mapped["User"] = relationship("User", back_populates="devices")
