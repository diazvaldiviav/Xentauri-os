"""
OAuth Credential model - stores OAuth tokens for external service integrations.

This model enables the Jarvis system to authenticate with external providers
(Google, Microsoft, Apple, etc.) on behalf of users. It stores access tokens,
refresh tokens, and metadata needed to maintain persistent API access.

Design Principles:
==================
1. Provider Agnostic: Works with any OAuth2 provider (Google, Microsoft, etc.)
2. Multi-Service Ready: One user can have tokens for multiple providers
3. Token Reusability: Same Google tokens work for Calendar, Drive, Gmail, etc.
4. Secure Storage: Tokens are stored securely (consider encryption in production)
5. Automatic Refresh: Stores refresh tokens for seamless token renewal

Example Usage:
    # Store Google tokens after OAuth callback
    credential = OAuthCredential(
        user_id=user.id,
        provider="google",
        access_token="ya29.xxx",
        refresh_token="1//xxx",
        token_type="Bearer",
        expires_at=datetime.now() + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar.readonly"]
    )
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class OAuthCredential(Base):
    """
    SQLAlchemy ORM model for the 'oauth_credentials' table.
    
    Stores OAuth2 credentials for external service integrations.
    Each record represents a user's authorization with a specific provider.
    
    Key Features:
    - One user can have multiple providers (Google, Microsoft, etc.)
    - One provider per user (unique constraint on user_id + provider)
    - Stores both access and refresh tokens for persistent access
    - Tracks token expiration for proactive refresh
    - Stores granted scopes for permission verification
    """
    
    __tablename__ = "oauth_credentials"

    # ---------------------------------------------------------------------------
    # PRIMARY KEY
    # ---------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ---------------------------------------------------------------------------
    # FOREIGN KEY - USER RELATIONSHIP
    # ---------------------------------------------------------------------------
    # user_id: The Jarvis user who authorized this connection
    # - ForeignKey with CASCADE: If user is deleted, remove their credentials too
    # - A user can have credentials for multiple providers
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # ---------------------------------------------------------------------------
    # PROVIDER INFORMATION
    # ---------------------------------------------------------------------------
    # provider: Identifier for the OAuth provider
    # - Examples: "google", "microsoft", "apple", "notion", "slack"
    # - Used to route token refresh and API calls to the correct module
    # - Combined with user_id forms a unique constraint
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # ---------------------------------------------------------------------------
    # TOKEN DATA
    # ---------------------------------------------------------------------------
    # access_token: Short-lived token for API access
    # - Used in Authorization header for API requests
    # - Typically expires in 1 hour (provider-dependent)
    # - Text type to handle long tokens (some providers use long JWTs)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    # refresh_token: Long-lived token for obtaining new access tokens
    # - Used to get a new access_token when the current one expires
    # - May be None for some OAuth flows (implicit grant)
    # - Should be stored securely (consider encryption in production)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # token_type: The type of token (usually "Bearer")
    # - Determines how to include the token in API requests
    # - Most OAuth2 providers use "Bearer" tokens
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")

    # ---------------------------------------------------------------------------
    # TOKEN METADATA
    # ---------------------------------------------------------------------------
    # expires_at: When the access_token expires
    # - Used to check if token needs refresh before making API calls
    # - Proactive refresh prevents failed requests
    # - Nullable for tokens that don't expire (rare)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # scopes: List of OAuth scopes granted by the user
    # - Stored as JSON array for flexibility
    # - Used to verify we have permission for specific API actions
    # - Example: ["calendar.readonly", "drive.readonly"]
    scopes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # ---------------------------------------------------------------------------
    # PROVIDER-SPECIFIC DATA
    # ---------------------------------------------------------------------------
    # extra_data: Additional provider-specific information
    # - Google: May include id_token, user info
    # - Microsoft: May include tenant_id
    # - Flexible JSON field for future needs
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ---------------------------------------------------------------------------
    # TIMESTAMPS
    # ---------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ---------------------------------------------------------------------------
    # RELATIONSHIPS
    # ---------------------------------------------------------------------------
    # owner: Reference back to the User who owns these credentials
    owner: Mapped["User"] = relationship("User", back_populates="oauth_credentials")

    # ---------------------------------------------------------------------------
    # HELPER METHODS
    # ---------------------------------------------------------------------------
    def is_expired(self) -> bool:
        """
        Check if the access token has expired.
        
        Returns:
            True if token is expired or about to expire (within 5 min buffer)
            False if token is still valid
            True if expires_at is not set (assume expired for safety)
        """
        if self.expires_at is None:
            return True  # Assume expired if we don't know
        
        # Add 5-minute buffer to account for clock skew and request time
        from datetime import timedelta
        buffer = timedelta(minutes=5)
        return datetime.now(timezone.utc) >= (self.expires_at - buffer)
    
    def has_scope(self, scope: str) -> bool:
        """
        Check if a specific scope was granted.
        
        Args:
            scope: The OAuth scope to check (e.g., "calendar.readonly")
        
        Returns:
            True if the scope is in the granted scopes list
        """
        if self.scopes is None:
            return False
        return scope in self.scopes

    def __repr__(self) -> str:
        return f"<OAuthCredential(user_id={self.user_id}, provider='{self.provider}')>"
