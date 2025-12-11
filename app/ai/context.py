"""
Unified Context System - Sprint 3.6

Provides a single, request-scoped object that encapsulates all context
needed by AI models (Gemini, GPT, Claude).

This ensures all AI providers have access to:
- User information
- Connected devices and their capabilities
- OAuth status (which services are connected)
- Effective capabilities (what actions can actually be executed)

Design Principles:
==================
1. **Request-scoped**: Built once per request, reused across all AI calls
2. **No global state**: Context is passed explicitly, not stored globally
3. **Lazy loading**: Only fetches what's needed
4. **DRY**: Single source of truth for context across all AI models

Usage:
======
```python
from app.ai.context import build_unified_context

# In an endpoint/handler with database session
context = await build_unified_context(user_id=user.id, db=db)

# Pass to AI providers
prompt = build_router_prompt(context, user_input)
response = await ai_provider.generate(prompt)
```
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.models.device import Device
from app.models.oauth_credential import OAuthCredential


@dataclass
class DeviceCapability:
    """
    Information about a device's capabilities.
    
    This tells AI models what actions are possible on each device.
    """
    device_id: UUID
    device_name: str
    is_online: bool
    device_type: Optional[str] = None
    
    # Capabilities flags
    can_power_control: bool = True
    can_input_control: bool = True
    can_volume_control: bool = True
    can_show_content: bool = True  # Can display web content (calendar, etc.)
    
    # Specific capabilities (from device.capabilities JSON)
    supports_cec: bool = False
    supports_ir: bool = False
    available_inputs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.device_id),
            "name": self.device_name,
            "is_online": self.is_online,
            "type": self.device_type,
            "can_power_control": self.can_power_control,
            "can_input_control": self.can_input_control,
            "can_volume_control": self.can_volume_control,
            "can_show_content": self.can_show_content,
            "supports_cec": self.supports_cec,
            "supports_ir": self.supports_ir,
            "available_inputs": self.available_inputs,
        }


@dataclass
class OAuthStatus:
    """
    OAuth connection status for a service.
    
    Tells AI models which external services are available.
    """
    provider: str  # "google", "microsoft", etc.
    is_connected: bool
    has_calendar: bool = False
    has_drive: bool = False
    has_email: bool = False
    scopes: List[str] = field(default_factory=list)
    
    # Token validity
    token_valid: bool = True
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "provider": self.provider,
            "is_connected": self.is_connected,
            "has_calendar": self.has_calendar,
            "has_drive": self.has_drive,
            "has_email": self.has_email,
            "scopes": self.scopes,
            "token_valid": self.token_valid,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class UnifiedContext:
    """
    Unified context for all AI model requests.
    
    This is the single source of truth for what the user has access to
    and what actions can be performed.
    
    Attributes:
        user_id: The user's UUID
        user_name: Display name for the user
        user_email: User's email
        
        devices: List of all user's devices with capabilities
        device_count: Total number of devices
        online_devices: List of online devices only
        
        oauth_connections: OAuth connection status for each provider
        has_google_calendar: Quick check if Google Calendar is connected
        
        available_actions: List of action types that can be executed
        capabilities_summary: Human-readable summary of what's possible
        
        created_at: When this context was built (for cache expiry)
        request_id: Optional request tracking ID
    """
    # User info
    user_id: UUID
    user_name: str
    user_email: str
    
    # Devices
    devices: List[DeviceCapability]
    device_count: int
    online_devices: List[DeviceCapability]
    
    # OAuth / External services
    oauth_connections: List[OAuthStatus]
    has_google_calendar: bool
    has_google_drive: bool
    
    # Effective capabilities
    available_actions: List[str]
    capabilities_summary: str
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for prompt building.
        
        This is used to inject context into AI prompts.
        """
        return {
            "user": {
                "id": str(self.user_id),
                "name": self.user_name,
                "email": self.user_email,
            },
            "devices": [d.to_dict() for d in self.devices],
            "device_count": self.device_count,
            "online_device_count": len(self.online_devices),
            "oauth": {
                "google_calendar": self.has_google_calendar,
                "google_drive": self.has_google_drive,
                "connections": [o.to_dict() for o in self.oauth_connections],
            },
            "capabilities": {
                "available_actions": self.available_actions,
                "summary": self.capabilities_summary,
            },
            "created_at": self.created_at.isoformat(),
        }
    
    def get_device_by_name(self, name: str) -> Optional[DeviceCapability]:
        """Find a device by name (case-insensitive)."""
        name_lower = name.lower()
        for device in self.devices:
            if device.device_name.lower() == name_lower:
                return device
        return None
    
    def has_capability(self, action: str) -> bool:
        """Check if this action is available given the user's setup."""
        return action in self.available_actions


# ---------------------------------------------------------------------------
# CONTEXT BUILDER
# ---------------------------------------------------------------------------

async def build_unified_context(
    user_id: UUID,
    db: Session,
    request_id: Optional[str] = None,
) -> UnifiedContext:
    """
    Build a UnifiedContext for the given user.
    
    This fetches all necessary data from the database and constructs
    a complete picture of what the user can do.
    
    Args:
        user_id: The user's UUID
        db: Database session
        request_id: Optional request tracking ID
        
    Returns:
        UnifiedContext instance ready to use in AI prompts
        
    Example:
        ```python
        context = await build_unified_context(user.id, db)
        prompt = f"User {context.user_name} has {context.device_count} devices..."
        ```
    """
    # Fetch user
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    # Fetch devices (eagerly load to avoid N+1 queries)
    devices = db.execute(
        select(Device).where(Device.user_id == user_id)
    ).scalars().all()
    
    # Fetch OAuth credentials
    oauth_creds = db.execute(
        select(OAuthCredential).where(OAuthCredential.user_id == user_id)
    ).scalars().all()
    
    # Build device capabilities
    device_capabilities = []
    for device in devices:
        # Parse device capabilities from JSON
        caps = device.capabilities or {}
        
        capability = DeviceCapability(
            device_id=device.id,
            device_name=device.name,
            is_online=device.is_online,
            # Use getattr for device_type - field doesn't exist in Device model yet
            # See BUG_REPORT_SPRINT_3.6.txt for details
            device_type=getattr(device, 'device_type', None),
            can_power_control=True,  # Assume all devices support basic power
            can_input_control=True,
            can_volume_control=True,
            can_show_content=True,  # All devices can show content
            supports_cec=caps.get("cec", False),
            supports_ir=caps.get("ir", False),
            available_inputs=caps.get("inputs", []),
        )
        device_capabilities.append(capability)
    
    # Determine online devices
    online_devices = [d for d in device_capabilities if d.is_online]
    
    # Build OAuth status
    oauth_statuses = []
    has_google_calendar = False
    has_google_drive = False
    
    for cred in oauth_creds:
        # Parse scopes to determine what services are available
        # Note: scopes is a JSON list in the model, not a space-separated string
        scopes = cred.scopes or []
        
        # Check token validity (simple check based on expiry)
        token_valid = True
        if cred.expires_at:
            token_valid = cred.expires_at > datetime.now(timezone.utc)
        
        # Determine available services from scopes
        has_cal = any("calendar" in s.lower() for s in scopes)
        has_drv = any("drive" in s.lower() for s in scopes)
        has_mail = any("gmail" in s.lower() or "mail" in s.lower() for s in scopes)
        
        oauth_status = OAuthStatus(
            provider=cred.provider,
            is_connected=True,
            has_calendar=has_cal,
            has_drive=has_drv,
            has_email=has_mail,
            scopes=scopes,
            token_valid=token_valid,
            expires_at=cred.expires_at,
        )
        oauth_statuses.append(oauth_status)
        
        # Update top-level flags
        if cred.provider == "google":
            if has_cal and token_valid:
                has_google_calendar = True
            if has_drv and token_valid:
                has_google_drive = True
    
    # Determine available actions based on user's setup
    available_actions = _compute_available_actions(
        device_capabilities,
        online_devices,
        has_google_calendar,
    )
    
    # Build capabilities summary
    capabilities_summary = _build_capabilities_summary(
        device_capabilities,
        online_devices,
        has_google_calendar,
        has_google_drive,
    )
    
    # Construct UnifiedContext
    return UnifiedContext(
        user_id=user_id,
        user_name=user.display_name or user.email.split("@")[0],
        user_email=user.email,
        devices=device_capabilities,
        device_count=len(device_capabilities),
        online_devices=online_devices,
        oauth_connections=oauth_statuses,
        has_google_calendar=has_google_calendar,
        has_google_drive=has_google_drive,
        available_actions=available_actions,
        capabilities_summary=capabilities_summary,
        request_id=request_id,
    )


def _compute_available_actions(
    devices: List[DeviceCapability],
    online_devices: List[DeviceCapability],
    has_google_calendar: bool,
) -> List[str]:
    """
    Compute which actions are actually available.
    
    An action is available if:
    1. There are devices that support it
    2. Required integrations are connected (e.g., Google Calendar for show_calendar)
    """
    actions = []
    
    # Basic device actions (need at least one device)
    if devices:
        actions.extend([
            "power_on",
            "power_off",
            "set_input",
            "volume_up",
            "volume_down",
            "volume_set",
            "mute",
            "unmute",
            "status",
        ])
    
    # Content actions (need devices that can show content)
    content_devices = [d for d in devices if d.can_show_content]
    if content_devices:
        actions.extend([
            "show_content",
            "clear_content",
        ])
    
    # Calendar actions (need Google Calendar + content display devices)
    if has_google_calendar and content_devices:
        actions.append("show_calendar")
    
    # System actions (always available)
    actions.extend([
        "list_devices",
        "help",
    ])
    
    return actions


def _build_capabilities_summary(
    devices: List[DeviceCapability],
    online_devices: List[DeviceCapability],
    has_google_calendar: bool,
    has_google_drive: bool,
) -> str:
    """
    Build a human-readable summary of capabilities.
    
    This is used in AI prompts to give models a quick overview.
    """
    parts = []
    
    # Devices
    if not devices:
        parts.append("No devices configured yet.")
    else:
        parts.append(f"{len(devices)} device(s) total, {len(online_devices)} online.")
        if online_devices:
            device_names = ", ".join([d.device_name for d in online_devices[:3]])
            if len(online_devices) > 3:
                device_names += f", and {len(online_devices) - 3} more"
            parts.append(f"Online devices: {device_names}.")
    
    # Services
    services = []
    if has_google_calendar:
        services.append("Google Calendar")
    if has_google_drive:
        services.append("Google Drive")
    
    if services:
        parts.append(f"Connected services: {', '.join(services)}.")
    
    # Capabilities
    if devices and has_google_calendar:
        parts.append("Can display calendar on screens.")
    
    return " ".join(parts)
