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
    has_docs: bool = False  # Sprint 3.9: Google Docs Intelligence
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
            "has_docs": self.has_docs,
            "scopes": self.scopes,
            "token_valid": self.token_valid,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class PendingOperationState:
    """
    State of any pending operation (create/edit/delete) for the user.
    
    This is critical for context-aware routing and intent parsing.
    When a user has a pending operation, confirmations like "yes" or
    edits like "change it to 2pm" should apply to that operation.
    
    Sprint 3.9.1: Context-Aware Confirmation Flow
    """
    # Operation flags
    has_pending_create: bool = False
    has_pending_edit: bool = False
    has_pending_delete: bool = False
    
    # The most recent/relevant pending operation type
    # Resolves conflicts when multiple pending ops exist
    pending_op_type: Optional[str] = None  # "create", "edit", "delete", None
    
    # Age of the most recent pending operation in seconds
    pending_op_age_seconds: Optional[int] = None
    
    # Hint about what the pending operation involves
    pending_op_hint: Optional[str] = None  # e.g., "Meeting with John" or "dentist appointment"
    
    # For create operations
    pending_create_title: Optional[str] = None
    pending_create_time: Optional[str] = None
    
    # For edit operations
    pending_edit_event: Optional[str] = None  # Event being edited
    pending_edit_changes: Optional[str] = None  # What's being changed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for prompt injection."""
        return {
            "has_pending_create": self.has_pending_create,
            "has_pending_edit": self.has_pending_edit,
            "has_pending_delete": self.has_pending_delete,
            "pending_op_type": self.pending_op_type,
            "pending_op_age_seconds": self.pending_op_age_seconds,
            "pending_op_hint": self.pending_op_hint,
            "pending_create_title": self.pending_create_title,
            "pending_create_time": self.pending_create_time,
            "pending_edit_event": self.pending_edit_event,
            "pending_edit_changes": self.pending_edit_changes,
        }
    
    def has_any_pending(self) -> bool:
        """Check if any pending operation exists."""
        return self.has_pending_create or self.has_pending_edit or self.has_pending_delete


@dataclass
class ConversationContext:
    """
    Tracks recent conversation context for resolving references like
    "this event", "that doc", "the meeting".
    
    Sprint 3.9: Multi-turn conversation context awareness.
    Sprint 4.1: Extended with full conversation history.
    
    When a user asks "is there a doc for this event?" after viewing
    an event, this context helps resolve "this event" to the actual event.
    
    TTL: Context expires after 5 minutes (300 seconds).
    """
    # Last referenced event (from show_calendar, calendar query, etc.)
    last_event_title: Optional[str] = None
    last_event_id: Optional[str] = None
    last_event_date: Optional[str] = None  # ISO format
    last_event_timestamp: Optional[datetime] = None
    
    # Last referenced document
    last_doc_id: Optional[str] = None
    last_doc_url: Optional[str] = None
    last_doc_title: Optional[str] = None
    last_doc_timestamp: Optional[datetime] = None
    
    # Last search performed
    last_search_term: Optional[str] = None
    last_search_type: Optional[str] = None  # "calendar", "doc", "general"
    last_search_timestamp: Optional[datetime] = None
    
    # Sprint 4.1: Conversation history for multi-turn context
    last_user_request: Optional[str] = None
    last_assistant_response: Optional[str] = None
    last_intent_type: Optional[str] = None
    last_conversation_timestamp: Optional[datetime] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Pending content generation (for follow-ups like "si, hazlo")
    pending_content_request: Optional[str] = None
    pending_content_type: Optional[str] = None
    
    def has_recent_event(self, max_age_seconds: int = 300) -> bool:
        """Check if there's a recent event in context (within TTL)."""
        if not self.last_event_timestamp:
            return False
        age = (datetime.now(timezone.utc) - self.last_event_timestamp).total_seconds()
        return age < max_age_seconds
    
    def has_recent_doc(self, max_age_seconds: int = 300) -> bool:
        """Check if there's a recent document in context (within TTL)."""
        if not self.last_doc_timestamp:
            return False
        age = (datetime.now(timezone.utc) - self.last_doc_timestamp).total_seconds()
        return age < max_age_seconds
    
    def has_recent_conversation(self, max_age_seconds: int = 300) -> bool:
        """Check if there's a recent conversation in context (within TTL)."""
        if not self.last_conversation_timestamp:
            return False
        age = (datetime.now(timezone.utc) - self.last_conversation_timestamp).total_seconds()
        return age < max_age_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for prompt injection."""
        return {
            "last_event": {
                "title": self.last_event_title,
                "id": self.last_event_id,
                "date": self.last_event_date,
                "is_recent": self.has_recent_event(),
            } if self.last_event_title else None,
            "last_doc": {
                "title": self.last_doc_title,
                "id": self.last_doc_id,
                "url": self.last_doc_url,
                "is_recent": self.has_recent_doc(),
            } if self.last_doc_id else None,
            "last_search": {
                "term": self.last_search_term,
                "type": self.last_search_type,
            } if self.last_search_term else None,
            "conversation": {
                "last_user": self.last_user_request[:100] if self.last_user_request else None,
                "last_assistant": self.last_assistant_response[:100] if self.last_assistant_response else None,
                "last_intent": self.last_intent_type,
                "pending_content": self.pending_content_request,
                "is_recent": self.has_recent_conversation(),
            } if self.last_user_request else None,
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
    
    # Fields with defaults must come after fields without defaults
    has_google_docs: bool = False  # Sprint 3.9: Google Docs Intelligence
    
    # Pending operation state (Sprint 3.9.1)
    pending_state: Optional[PendingOperationState] = None
    
    # Conversation context (Sprint 3.9: Multi-turn awareness)
    conversation_context: Optional[ConversationContext] = None
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for prompt building.
        
        This is used to inject context into AI prompts.
        """
        context_dict = {
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
                "google_docs": self.has_google_docs,
                "connections": [o.to_dict() for o in self.oauth_connections],
            },
            "capabilities": {
                "available_actions": self.available_actions,
                "summary": self.capabilities_summary,
            },
            "pending_operation": self.pending_state.to_dict() if self.pending_state else None,
            "conversation_context": self.conversation_context.to_dict() if self.conversation_context else None,
            "created_at": self.created_at.isoformat(),
        }
        
        # Sprint 4.2: Add generated content context if available
        from app.services.conversation_context_service import conversation_context_service
        
        generated_content = conversation_context_service.get_generated_content(str(self.user_id))
        if generated_content:
            elapsed = (datetime.now(timezone.utc) - generated_content["timestamp"]).total_seconds()
            minutes_ago = int(elapsed / 60)
            
            context_dict["generated_content_context"] = f"""
## RECENTLY GENERATED CONTENT (Memory Context)

{minutes_ago} minute(s) ago, you generated this {generated_content['type'].upper()}:
Title: {generated_content['title'] or 'Untitled'}
Content:
{generated_content['content']}

IMPORTANT: If the user asks to "show", "display", "present" or reference this content, use DISPLAY_CONTENT intent (NOT DOC_QUERY). This content is in your working memory, not in Google Docs.

⏱️ TTL (Time To Live): This generated content expires after 5 minutes!
- You're seeing this because it was generated within the last 5 minutes
- If this context is missing, the content has expired or hasn't been generated
- After 5 min, users must regenerate or you should prompt them
"""
        
        return context_dict
    
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
    has_google_docs = False  # Sprint 3.9: Google Docs Intelligence
    
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
        has_docs = any("documents" in s.lower() for s in scopes)  # Sprint 3.9
        
        oauth_status = OAuthStatus(
            provider=cred.provider,
            is_connected=True,
            has_calendar=has_cal,
            has_drive=has_drv,
            has_email=has_mail,
            has_docs=has_docs,
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
            if has_docs and token_valid:
                has_google_docs = True
    
    # Determine available actions based on user's setup
    available_actions = _compute_available_actions(
        device_capabilities,
        online_devices,
        has_google_calendar,
        has_google_docs,
    )
    
    # Build capabilities summary
    capabilities_summary = _build_capabilities_summary(
        device_capabilities,
        online_devices,
        has_google_calendar,
        has_google_drive,
        has_google_docs,
    )
    
    # Build pending operation state (Sprint 3.9.1)
    pending_state = _build_pending_state(str(user_id))
    
    # Build conversation context (Sprint 3.9)
    conversation_context = _build_conversation_context(str(user_id))
    
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
        has_google_docs=has_google_docs,
        available_actions=available_actions,
        capabilities_summary=capabilities_summary,
        pending_state=pending_state,
        conversation_context=conversation_context,
        request_id=request_id,
    )


def _compute_available_actions(
    devices: List[DeviceCapability],
    online_devices: List[DeviceCapability],
    has_google_calendar: bool,
    has_google_docs: bool = False,
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
    
    # Google Docs actions (Sprint 3.9)
    if has_google_docs:
        actions.extend([
            "read_doc",
            "summarize_doc",
            "link_doc",
            "open_doc",
        ])
    
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
    has_google_docs: bool = False,
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
    if has_google_docs:
        services.append("Google Docs")
    
    if services:
        parts.append(f"Connected services: {', '.join(services)}.")
    
    # Capabilities
    if devices and has_google_calendar:
        parts.append("Can display calendar on screens.")
    if has_google_docs:
        parts.append("Can read and summarize Google Docs.")
    
    return " ".join(parts)


def _build_pending_state(user_id: str) -> PendingOperationState:
    """
    Build pending operation state by querying pending services.
    
    This checks both pending_event_service (for create) and
    pending_edit_service (for edit/delete) and determines the
    most recent operation for context-aware routing.
    
    Sprint 3.9.1: Context-Aware Confirmation Flow
    """
    from app.services.pending_event_service import pending_event_service
    from app.services.pending_edit_service import pending_edit_service
    
    state = PendingOperationState()
    
    # Check for pending create (event creation)
    pending_create = pending_event_service.get_pending(user_id)
    if pending_create:
        state.has_pending_create = True
        state.pending_create_title = pending_create.event_title
        state.pending_create_time = pending_create.event_time
        
        # Calculate age in seconds
        age_seconds = int((datetime.now(timezone.utc) - pending_create.created_at).total_seconds())
        
        # Track as candidate for most recent
        create_timestamp = pending_create.created_at
    else:
        create_timestamp = None
    
    # Check for pending edit/delete
    pending_edit = pending_edit_service.get_pending(user_id)
    if pending_edit:
        if pending_edit.operation.value == "edit":
            state.has_pending_edit = True
        elif pending_edit.operation.value == "delete":
            state.has_pending_delete = True
        
        # Get event hint
        if pending_edit.selected_event:
            state.pending_edit_event = pending_edit.selected_event.summary
        elif pending_edit.matching_events:
            state.pending_edit_event = pending_edit.matching_events[0].summary
        
        # Get changes hint
        if pending_edit.changes:
            changes_list = list(pending_edit.changes.keys())
            state.pending_edit_changes = ", ".join(changes_list[:2])
        
        # Calculate age in seconds
        edit_timestamp = pending_edit.created_at
    else:
        edit_timestamp = None
    
    # Determine most recent pending operation (priority resolution)
    # If both exist, use the more recent one
    if create_timestamp and edit_timestamp:
        if edit_timestamp >= create_timestamp:
            # Edit is more recent
            state.pending_op_type = pending_edit.operation.value  # "edit" or "delete"
            state.pending_op_age_seconds = int((datetime.now(timezone.utc) - edit_timestamp).total_seconds())
            state.pending_op_hint = state.pending_edit_event or pending_edit.search_term
        else:
            # Create is more recent
            state.pending_op_type = "create"
            state.pending_op_age_seconds = int((datetime.now(timezone.utc) - create_timestamp).total_seconds())
            state.pending_op_hint = state.pending_create_title
    elif create_timestamp:
        state.pending_op_type = "create"
        state.pending_op_age_seconds = int((datetime.now(timezone.utc) - create_timestamp).total_seconds())
        state.pending_op_hint = state.pending_create_title
    elif edit_timestamp:
        state.pending_op_type = pending_edit.operation.value
        state.pending_op_age_seconds = int((datetime.now(timezone.utc) - edit_timestamp).total_seconds())
        state.pending_op_hint = state.pending_edit_event or pending_edit.search_term
    
    return state


def _build_conversation_context(user_id: str) -> Optional[ConversationContext]:
    """
    Build conversation context from the conversation_context_service.
    
    Sprint 3.9: Multi-turn conversation context awareness.
    Sprint 4.1: Extended with conversation history.
    
    Retrieves the last referenced event, document, search, and conversation
    from the in-memory cache for context-aware intent parsing.
    
    Returns:
        ConversationContext if user has conversation history, None otherwise.
    """
    from app.services.conversation_context_service import conversation_context_service
    
    # Get context from service (may be None for new users)
    ctx = conversation_context_service.get_context(user_id)
    
    # Return None if user has no conversation context yet
    if ctx is None:
        return None
    
    # Get conversation history
    history = conversation_context_service.get_conversation_history(user_id, max_turns=5)
    
    # Build dataclass from service context
    return ConversationContext(
        # Event context
        last_event_title=ctx.last_event_title,
        last_event_id=ctx.last_event_id,
        last_event_date=ctx.last_event_date,
        last_event_timestamp=ctx.last_event_timestamp,
        # Doc context
        last_doc_id=ctx.last_doc_id,
        last_doc_url=ctx.last_doc_url,
        last_doc_title=ctx.last_doc_title,
        last_doc_timestamp=ctx.last_doc_timestamp,
        # Search context
        last_search_term=ctx.last_search_term,
        last_search_type=ctx.last_search_type,
        last_search_timestamp=ctx.last_search_timestamp,
        # Sprint 4.1: Conversation context
        last_user_request=ctx.last_user_request,
        last_assistant_response=ctx.last_assistant_response,
        last_intent_type=ctx.last_intent_type,
        last_conversation_timestamp=ctx.last_conversation_timestamp,
        conversation_history=history,
        pending_content_request=ctx.pending_content_request,
        pending_content_type=ctx.pending_content_type,
    )