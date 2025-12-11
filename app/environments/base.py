"""
Base classes and interfaces for Environment integrations.

This module defines the abstract contracts that all environment providers
(Google, Microsoft, Apple, etc.) and their services must implement.

Design Pattern: Template Method + Strategy Pattern
==================================================
- EnvironmentProvider: Abstract base for OAuth providers (strategy for auth)
- EnvironmentService: Abstract base for API services (strategy for API calls)

Benefits:
- Consistent interface across all providers
- Easy to add new providers without changing core code
- Type safety and IDE autocompletion
- Clear separation between authentication and API services
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid


# ---------------------------------------------------------------------------
# CUSTOM EXCEPTIONS
# ---------------------------------------------------------------------------
# Specific exceptions for environment operations.
# Using custom exceptions allows for precise error handling in routes.


class EnvironmentError(Exception):
    """Base exception for all environment-related errors."""
    pass


class AuthenticationError(EnvironmentError):
    """Raised when authentication with a provider fails."""
    pass


class TokenExpiredError(EnvironmentError):
    """Raised when an OAuth token has expired and refresh failed."""
    pass


class ScopeNotGrantedError(EnvironmentError):
    """Raised when trying to access an API without the required scope."""
    pass


class APIError(EnvironmentError):
    """Raised when an API call to the provider fails."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------
# Common data structures used across all environment implementations.


@dataclass
class OAuthTokens:
    """
    Standardized token data from any OAuth provider.
    
    Used to transfer token data between OAuth flow and storage.
    Provider-agnostic structure that works with Google, Microsoft, etc.
    """
    access_token: str
    token_type: str = "Bearer"
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: Optional[List[str]] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class UserInfo:
    """
    Basic user information from an OAuth provider.
    
    Extracted from the id_token or userinfo endpoint.
    Used to identify the user across sessions.
    """
    provider_user_id: str  # Unique ID from the provider (e.g., Google's 'sub')
    email: Optional[str] = None
    name: Optional[str] = None
    picture_url: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# ABSTRACT BASE CLASSES
# ---------------------------------------------------------------------------


class EnvironmentProvider(ABC):
    """
    Abstract base class for OAuth providers (Google, Microsoft, etc.).
    
    Each provider must implement these methods to handle the OAuth flow.
    The provider is responsible for:
    - Generating authorization URLs
    - Exchanging authorization codes for tokens
    - Refreshing expired tokens
    - Extracting user information from tokens
    
    Example Implementation:
        class GoogleProvider(EnvironmentProvider):
            provider_name = "google"
            
            def get_authorization_url(self, scopes: List[str], state: str) -> str:
                # Build Google OAuth URL
                ...
    """
    
    # Unique identifier for this provider (e.g., "google", "microsoft")
    provider_name: str = ""
    
    @abstractmethod
    def get_authorization_url(
        self,
        scopes: List[str],
        state: str,
        redirect_uri: Optional[str] = None,
    ) -> str:
        """
        Generate the OAuth authorization URL.
        
        Args:
            scopes: List of OAuth scopes to request
            state: CSRF protection state parameter
            redirect_uri: Override the default redirect URI
        
        Returns:
            URL to redirect the user to for authorization
        """
        pass
    
    @abstractmethod
    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> OAuthTokens:
        """
        Exchange authorization code for access/refresh tokens.
        
        Args:
            code: Authorization code from the callback
            redirect_uri: Must match the redirect_uri used in authorization
        
        Returns:
            OAuthTokens with access_token, refresh_token, etc.
        
        Raises:
            AuthenticationError: If code exchange fails
        """
        pass
    
    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        """
        Use refresh token to get a new access token.
        
        Args:
            refresh_token: The refresh token from initial authorization
        
        Returns:
            OAuthTokens with new access_token (refresh_token may be updated)
        
        Raises:
            TokenExpiredError: If refresh token is invalid/expired
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get user information from the provider.
        
        Args:
            access_token: Valid access token
        
        Returns:
            UserInfo with provider_user_id, email, name, etc.
        """
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access or refresh token.
        
        Args:
            token: The token to revoke
        
        Returns:
            True if revocation succeeded
        """
        pass


class EnvironmentService(ABC):
    """
    Abstract base class for API services within a provider.
    
    Each service (Calendar, Drive, Gmail, etc.) implements this interface.
    Services use the tokens managed by their parent provider.
    
    Example Implementation:
        class GoogleCalendarService(EnvironmentService):
            service_name = "calendar"
            required_scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
            
            async def list_events(self, ...):
                ...
    """
    
    # Unique identifier for this service within the provider
    service_name: str = ""
    
    # OAuth scopes required for this service to function
    required_scopes: List[str] = []
    
    @abstractmethod
    async def validate_access(self, access_token: str) -> bool:
        """
        Verify the access token is valid for this service.
        
        Args:
            access_token: The OAuth access token
        
        Returns:
            True if token is valid and has required scopes
        """
        pass
