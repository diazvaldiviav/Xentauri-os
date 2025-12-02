"""
WebSocket router - handles real-time connections with Pi agents.

This module provides the WebSocket endpoint for Raspberry Pi agents to:
- Connect to the cloud server
- Receive commands in real-time
- Send status updates and acknowledgments

The WebSocket uses a simple JSON message protocol:
- Server → Agent: Commands (power_on, set_input, etc.)
- Agent → Server: Acknowledgments and status updates
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.device import Device
from app.services.websocket_manager import connection_manager

# Configure logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/ws", tags=["websocket"])


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_db():
    """Create a database session for WebSocket handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_agent(db: Session, agent_id: str) -> Device:
    """
    Validate that an agent_id is paired with a device.
    
    Args:
        db: Database session
        agent_id: The agent identifier from the connection request
    
    Returns:
        Device object if valid
    
    Raises:
        HTTPException: If agent is not paired with any device
    """
    device = db.query(Device).filter(Device.agent_id == agent_id).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent not paired with any device"
        )
    
    return device


# ---------------------------------------------------------------------------
# WEBSOCKET ENDPOINT
# ---------------------------------------------------------------------------

@router.websocket("/devices")
async def websocket_endpoint(
    websocket: WebSocket,
    agent_id: str = Query(..., description="Unique identifier of the Pi agent"),
):
    """
    WebSocket endpoint for Raspberry Pi agents.
    
    Connection URL: ws://host:port/ws/devices?agent_id=<agent_id>
    
    The agent must be paired with a device before connecting.
    Use the /devices/pair endpoint to pair first.
    
    Message Protocol (JSON):
    
    Server → Agent (Commands):
    {
        "type": "command",
        "command_id": "uuid-string",
        "command_type": "power_on" | "power_off" | "set_input" | "set_volume" | ...,
        "parameters": { ... },
        "timestamp": "ISO-8601"
    }
    
    Agent → Server (Acknowledgment):
    {
        "type": "ack",
        "command_id": "uuid-string",
        "status": "received" | "executing" | "completed" | "failed",
        "error": "optional error message"
    }
    
    Agent → Server (Heartbeat):
    {
        "type": "heartbeat"
    }
    
    Server → Agent (Heartbeat response):
    {
        "type": "heartbeat_ack",
        "timestamp": "ISO-8601"
    }
    """
    # Create database session
    db = SessionLocal()
    
    try:
        # Validate the agent is paired
        device = validate_agent(db, agent_id)
        device_id = device.id
        
        logger.info(f"Agent {agent_id} attempting to connect for device {device_id}")
        
        # Register the connection
        await connection_manager.connect(device_id, websocket)
        
        # Update device status in database
        device.is_online = True
        db.commit()
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "device_id": str(device_id),
            "message": "Successfully connected to Jarvis Cloud"
        })
        
        # Main message loop - receive and process messages
        while True:
            try:
                # Wait for message from agent
                data = await websocket.receive_json()
                
                # Update last seen timestamp
                connection_manager.update_last_seen(device_id)
                
                # Process message based on type
                message_type = data.get("type", "unknown")
                
                if message_type == "heartbeat":
                    # Respond to heartbeat
                    from datetime import datetime, timezone
                    await websocket.send_json({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                
                elif message_type == "ack":
                    # Command acknowledgment from agent
                    command_id = data.get("command_id")
                    status = data.get("status")
                    logger.info(f"Device {device_id}: Command {command_id} status: {status}")
                    # TODO: Update command status in database when Command model is added
                
                elif message_type == "status":
                    # Status update from agent (capabilities, etc.)
                    if "capabilities" in data:
                        device.capabilities = data["capabilities"]
                        db.commit()
                        logger.info(f"Device {device_id}: Updated capabilities")
                
                else:
                    logger.warning(f"Device {device_id}: Unknown message type: {message_type}")
            
            except json.JSONDecodeError:
                logger.warning(f"Device {device_id}: Received invalid JSON")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
    
    except WebSocketDisconnect:
        logger.info(f"Agent {agent_id}: WebSocket disconnected")
    
    except HTTPException as e:
        # Agent validation failed
        logger.warning(f"Agent {agent_id}: Connection rejected: {e.detail}")
        # Can't send error on rejected WebSocket, just close
        await websocket.close(code=4001, reason=e.detail)
    
    except Exception as e:
        logger.error(f"Agent {agent_id}: Unexpected error: {e}")
    
    finally:
        # Clean up on disconnect
        if 'device_id' in locals():
            connection_manager.disconnect(device_id)
            
            # Update device status in database
            try:
                device = db.query(Device).filter(Device.id == device_id).first()
                if device:
                    device.is_online = False
                    from datetime import datetime, timezone
                    device.last_seen = datetime.now(timezone.utc)
                    db.commit()
            except Exception:
                pass  # Best effort
        
        db.close()
