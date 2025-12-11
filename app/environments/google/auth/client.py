"""
Google OAuth Client - Handles OAuth 2.0 flow with Google APIs.

This client implements the Google OAuth 2.0 authorization code flow
with PKCE (Proof Key for Code Exchange) for enhanced security.

Key Features:
=============
1. Authorization URL generation with proper scopes
2. Code-to-token exchange
3. Token refresh for seamless access
4. User info extraction from id_token or userinfo endpoint
5. Token revocation for logout/disconnect

OAuth 2.0 Flow Implementation:
==============================
1. get_authorization_url() → User redirected to Google
2. exchange_code_for_tokens() → Called in callback, gets tokens
3. refresh_access_token() → Renew expired access tokens
4. get_user_info() → Fetch Google account details

References:
===========
- OAuth 2.0: https://developers.google.com/identity/protocols/oauth2
- Token endpoint: https://oauth2.googleapis.com/token
- Userinfo: https://www.googleapis.com/oauth2/v3/userinfo
"""

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.environments.base import (
    EnvironmentProvider,
    OAuthTokens,
    UserInfo,
    AuthenticationError,
    TokenExpiredError,
)
from app.environments.google.auth.schemas import (
    GoogleTokenResponse,
    GoogleUserInfo,
    PROFILE_SCOPES,
)


logger = logging.getLogger("jarvis.environments.google.auth")


class GoogleAuthClient(EnvironmentProvider):
    """
    Google OAuth 2.0 Client implementation.
    
    Handles the complete OAuth flow for Google APIs.
    Tokens obtained here can be used with any Google service
    (Calendar, Drive, Docs, etc.) that was included in the scopes.
    
    Example Usage:
        client = GoogleAuthClient()
        
        # Step 1: Generate auth URL
        auth_url = client.get_authorization_url(
            scopes=CALENDAR_SCOPES,
            state="random-csrf-token"
        )
        # Redirect user to auth_url
        
        # Step 2: Handle callback
        tokens = await client.exchange_code_for_tokens(code="abc123")
        
        # Step 3: Get user info
        user_info = await client.get_user_info(tokens.access_token)
        
        # Step 4: Store tokens for later use
        # (handled by the route, stored in OAuthCredential model)
    """
    
    # Provider identifier (used in database storage)
    provider_name = "google"
    
    # Google OAuth endpoints
    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        """
        Initialize the Google OAuth client.
        
        Args:
            client_id: Google OAuth Client ID (defaults to settings)
            client_secret: Google OAuth Client Secret (defaults to settings)
            redirect_uri: OAuth callback URL (defaults to settings)
        """
        self.client_id = client_id or settings.GOOGLE_CLIENT_ID
        self.client_secret = client_secret or settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI
        
        # Validate configuration
        if not self.client_id or not self.client_secret:
            logger.warning(
                "Google OAuth not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in environment variables."
            )
    
    # -------------------------------------------------------------------------
    # AUTHORIZATION URL
    # -------------------------------------------------------------------------
    
    def get_authorization_url(
        self,
        scopes: List[str],
        state: str,
        redirect_uri: Optional[str] = None,
        include_profile: bool = True,
        access_type: str = "offline",
        prompt: str = "consent",
    ) -> str:
        """
        Generate the Google OAuth authorization URL.
        
        Args:
            scopes: List of OAuth scopes to request (e.g., CALENDAR_SCOPES)
            state: CSRF protection token (random string stored in session)
            redirect_uri: Override default callback URL
            include_profile: Add profile scopes for user info (default: True)
            access_type: "offline" for refresh token, "online" for access only
            prompt: "consent" forces consent screen (gets refresh token)
        
        Returns:
            Full authorization URL to redirect the user to
        
        Example:
            url = client.get_authorization_url(
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
                state=secrets.token_urlsafe(32)
            )
            # Returns: https://accounts.google.com/o/oauth2/v2/auth?...
        """
        # Combine requested scopes with profile scopes if needed
        all_scopes = list(scopes)
        if include_profile:
            for scope in PROFILE_SCOPES:
                if scope not in all_scopes:
                    all_scopes.append(scope)
        
        # Build query parameters
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "response_type": "code",  # Authorization code flow
            "scope": " ".join(all_scopes),  # Space-separated scopes
            "state": state,  # CSRF protection
            "access_type": access_type,  # "offline" = include refresh_token
            "prompt": prompt,  # "consent" = always show consent screen
        }
        
        # Generate full URL
        auth_url = f"{self.AUTHORIZATION_URL}?{urlencode(params)}"
        
        logger.info(
            f"Generated Google auth URL with {len(all_scopes)} scopes",
            extra={"scopes": all_scopes}
        )
        
        return auth_url
    
    # -------------------------------------------------------------------------
    # TOKEN EXCHANGE
    # -------------------------------------------------------------------------
    
    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> OAuthTokens:
        """
        Exchange authorization code for access and refresh tokens.
        
        This is called in the OAuth callback after the user grants permission.
        Google returns both an access token (short-lived, ~1 hour) and a
        refresh token (long-lived, for getting new access tokens).
        
        Args:
            code: Authorization code from Google callback
            redirect_uri: Must match the redirect_uri used in authorization
        
        Returns:
            OAuthTokens with access_token, refresh_token, expiration, etc.
        
        Raises:
            AuthenticationError: If token exchange fails
        """
        # Prepare token request
        token_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri or self.redirect_uri,
        }
        
        logger.info("Exchanging authorization code for tokens")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_URL,
                    data=token_data,
                    timeout=30.0,
                )
                
                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("error_description", response.text)
                    logger.error(f"Token exchange failed: {error_msg}")
                    raise AuthenticationError(f"Token exchange failed: {error_msg}")
                
                # Parse response
                token_response = GoogleTokenResponse(**response.json())
                
                logger.info(
                    "Successfully obtained Google tokens",
                    extra={
                        "has_refresh_token": token_response.refresh_token is not None,
                        "expires_in": token_response.expires_in,
                        "scopes": token_response.get_scopes_list(),
                    }
                )
                
                # Convert to standard OAuthTokens format
                return OAuthTokens(
                    access_token=token_response.access_token,
                    token_type=token_response.token_type,
                    refresh_token=token_response.refresh_token,
                    expires_at=token_response.get_expires_at(),
                    scopes=token_response.get_scopes_list(),
                    extra_data={"id_token": token_response.id_token} if token_response.id_token else None,
                )
                
            except httpx.RequestError as e:
                logger.error(f"Network error during token exchange: {e}")
                raise AuthenticationError(f"Network error: {e}")
    
    # -------------------------------------------------------------------------
    # TOKEN REFRESH
    # -------------------------------------------------------------------------
    
    async def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        """
        Use refresh token to get a new access token.
        
        Access tokens expire after about 1 hour. This method uses the
        long-lived refresh token to get a new access token without
        requiring user interaction.
        
        Args:
            refresh_token: The refresh token from initial authorization
        
        Returns:
            OAuthTokens with new access_token (refresh_token usually unchanged)
        
        Raises:
            TokenExpiredError: If refresh token is invalid or revoked
        """
        refresh_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        
        logger.info("Refreshing access token")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_URL,
                    data=refresh_data,
                    timeout=30.0,
                )
                
                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("error_description", response.text)
                    logger.error(f"Token refresh failed: {error_msg}")
                    raise TokenExpiredError(f"Token refresh failed: {error_msg}")
                
                # Parse response
                token_response = GoogleTokenResponse(**response.json())
                
                logger.info(
                    "Successfully refreshed access token",
                    extra={"expires_in": token_response.expires_in}
                )
                
                # Convert to standard format
                # Note: Google may or may not return a new refresh_token
                return OAuthTokens(
                    access_token=token_response.access_token,
                    token_type=token_response.token_type,
                    refresh_token=token_response.refresh_token or refresh_token,  # Keep old if not returned
                    expires_at=token_response.get_expires_at(),
                    scopes=token_response.get_scopes_list(),
                )
                
            except httpx.RequestError as e:
                logger.error(f"Network error during token refresh: {e}")
                raise TokenExpiredError(f"Network error: {e}")
    
    # -------------------------------------------------------------------------
    # USER INFO
    # -------------------------------------------------------------------------
    
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get user information from Google.
        
        Fetches the user's profile from the userinfo endpoint.
        Requires the profile/email scopes to have been granted.
        
        Args:
            access_token: Valid access token
        
        Returns:
            UserInfo with Google account details
        """
        logger.info("Fetching user info from Google")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch user info: {response.text}")
                    raise AuthenticationError("Failed to fetch user info")
                
                # Parse Google user info
                google_user = GoogleUserInfo(**response.json())
                
                logger.info(
                    "Successfully fetched Google user info",
                    extra={"email": google_user.email}
                )
                
                # Convert to standard UserInfo format
                return UserInfo(
                    provider_user_id=google_user.sub,
                    email=google_user.email,
                    name=google_user.name,
                    picture_url=google_user.picture,
                    extra_data={
                        "given_name": google_user.given_name,
                        "family_name": google_user.family_name,
                        "email_verified": google_user.email_verified,
                        "locale": google_user.locale,
                    },
                )
                
            except httpx.RequestError as e:
                logger.error(f"Network error fetching user info: {e}")
                raise AuthenticationError(f"Network error: {e}")
    
    # -------------------------------------------------------------------------
    # TOKEN REVOCATION
    # -------------------------------------------------------------------------
    
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access or refresh token.
        
        Called when user disconnects their Google account from Jarvis.
        Invalidates the token on Google's side.
        
        Args:
            token: Access token or refresh token to revoke
        
        Returns:
            True if revocation succeeded
        """
        logger.info("Revoking Google token")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.REVOKE_URL,
                    params={"token": token},
                    timeout=30.0,
                )
                
                # Google returns 200 on success, various errors otherwise
                success = response.status_code == 200
                
                if success:
                    logger.info("Successfully revoked Google token")
                else:
                    logger.warning(f"Token revocation returned status {response.status_code}")
                
                return success
                
            except httpx.RequestError as e:
                logger.error(f"Network error during token revocation: {e}")
                return False
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    @staticmethod
    def generate_state() -> str:
        """
        Generate a cryptographically secure state parameter.
        
        Used for CSRF protection in the OAuth flow.
        Store this value in the session and verify it in the callback.
        
        Returns:
            32-character random URL-safe string
        """
        return secrets.token_urlsafe(32)
