"""
Google OAuth Schemas - Data structures for Google authentication.

This module defines the data structures used in the Google OAuth flow.
Using Pydantic models ensures type safety and validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# OAUTH SCOPE CONSTANTS
# ---------------------------------------------------------------------------
# Google OAuth scopes define what permissions we're requesting.
# Using constants prevents typos and makes scope management easier.
# 
# Reference: https://developers.google.com/identity/protocols/oauth2/scopes

# Profile scopes - basic user information
PROFILE_SCOPES = [
    "openid",                                    # OpenID Connect (user ID)
    "https://www.googleapis.com/auth/userinfo.email",  # User's email
    "https://www.googleapis.com/auth/userinfo.profile", # Name, picture
]

# Calendar scopes - read-only access to calendars and events
# Using readonly for MVP security - we don't need to modify calendars
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",  # Read calendars
    "https://www.googleapis.com/auth/calendar.events.readonly",  # Read events
]

# Drive scopes - for future Sprint (read-only access to files)
DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",  # Read files
    "https://www.googleapis.com/auth/drive.metadata.readonly",  # Read metadata
]

# Gmail scopes - for future Sprint (read-only access to emails)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # Read emails
]


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

class GoogleAuthConfig(BaseModel):
    """
    Configuration for Google OAuth client.
    
    Typically loaded from environment variables via Settings.
    """
    client_id: str = Field(..., description="Google OAuth Client ID")
    client_secret: str = Field(..., description="Google OAuth Client Secret")
    redirect_uri: str = Field(..., description="OAuth callback URL")


# ---------------------------------------------------------------------------
# TOKEN RESPONSES
# ---------------------------------------------------------------------------

class GoogleTokenResponse(BaseModel):
    """
    Response from Google's token endpoint.
    
    This is what Google returns when we exchange an auth code for tokens,
    or when we refresh an access token.
    
    Example response from Google:
    {
        "access_token": "ya29.a0AfB_byC...",
        "expires_in": 3599,
        "refresh_token": "1//0eXyz...",
        "scope": "openid https://www.googleapis.com/auth/calendar.readonly",
        "token_type": "Bearer",
        "id_token": "eyJhbGciOiJSUzI1NiIs..."
    }
    """
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="Bearer", description="Token type (usually Bearer)")
    expires_in: Optional[int] = Field(None, description="Seconds until expiration")
    refresh_token: Optional[str] = Field(None, description="Refresh token for renewal")
    scope: Optional[str] = Field(None, description="Space-separated scopes granted")
    id_token: Optional[str] = Field(None, description="JWT with user info (OpenID)")
    
    def get_scopes_list(self) -> List[str]:
        """Convert space-separated scope string to list."""
        if self.scope:
            return self.scope.split()
        return []
    
    def get_expires_at(self) -> Optional[datetime]:
        """Calculate expiration datetime from expires_in seconds."""
        if self.expires_in:
            from datetime import timedelta, timezone
            return datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)
        return None


# ---------------------------------------------------------------------------
# USER INFO
# ---------------------------------------------------------------------------

class GoogleUserInfo(BaseModel):
    """
    User information from Google's userinfo endpoint or id_token.
    
    Used to identify the Google account that authorized the connection.
    
    Example:
    {
        "sub": "123456789",
        "email": "user@gmail.com",
        "email_verified": true,
        "name": "John Doe",
        "picture": "https://lh3.googleusercontent.com/a/..."
    }
    """
    sub: str = Field(..., description="Unique Google user ID")
    email: Optional[str] = Field(None, description="User's email address")
    email_verified: Optional[bool] = Field(None, description="Is email verified?")
    name: Optional[str] = Field(None, description="User's display name")
    given_name: Optional[str] = Field(None, description="First name")
    family_name: Optional[str] = Field(None, description="Last name")
    picture: Optional[str] = Field(None, description="Profile picture URL")
    locale: Optional[str] = Field(None, description="User's locale (e.g., 'en')")


# ---------------------------------------------------------------------------
# AUTH STATE
# ---------------------------------------------------------------------------

class GoogleAuthState(BaseModel):
    """
    State data for CSRF protection in OAuth flow.
    
    The 'state' parameter is passed to Google and returned in the callback.
    We encode useful data in it while maintaining CSRF protection.
    """
    csrf_token: str = Field(..., description="Random token for CSRF protection")
    user_id: Optional[str] = Field(None, description="Jarvis user ID if logged in")
    redirect_after: Optional[str] = Field(None, description="Where to redirect after auth")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Additional state data")
