"""
Google Auth Router - OAuth 2.0 endpoints for Google integration.

This router handles the Google OAuth flow, allowing users to connect
their Google account to Jarvis for calendar and other integrations.

Endpoints:
==========
- GET /auth/google/login    → Redirect to Google OAuth consent screen
- GET /auth/google/callback → Handle OAuth callback, store tokens
- DELETE /auth/google       → Disconnect Google account

OAuth Flow:
===========
1. User clicks "Connect Google" in the app
2. Frontend calls GET /auth/google/login
3. Backend redirects to Google's consent screen
4. User grants permissions
5. Google redirects to /auth/google/callback with code
6. Backend exchanges code for tokens, stores them
7. User is redirected back to the app

Security:
=========
- CSRF protection via state parameter
- Tokens stored encrypted (TODO: implement encryption)
- Refresh tokens used to maintain access
"""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.oauth_credential import OAuthCredential
from app.environments.google import GoogleAuthClient, CALENDAR_SCOPES, DOCS_SCOPES


logger = logging.getLogger("jarvis.routers.google_auth")


# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/auth/google", tags=["google-auth"])


# ---------------------------------------------------------------------------
# STATE STORAGE (In-memory for MVP)
# ---------------------------------------------------------------------------
# In production, use Redis or database for state storage
# This simple dict works for single-server MVP
_oauth_states: dict[str, dict] = {}


def _store_state(state: str, data: dict) -> None:
    """Store OAuth state data (CSRF protection)."""
    _oauth_states[state] = data


def _get_and_remove_state(state: str) -> Optional[dict]:
    """Retrieve and remove OAuth state data."""
    return _oauth_states.pop(state, None)


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/login")
async def google_login(
    current_user: User = Depends(get_current_user),
    redirect_after: Optional[str] = Query(None, description="URL to redirect after auth"),
):
    """
    Initiate Google OAuth login flow.
    
    Redirects the user to Google's OAuth consent screen where they can
    authorize Jarvis to access their Google Calendar.
    
    Args:
        current_user: Authenticated Jarvis user (from JWT)
        redirect_after: Optional URL to redirect to after successful auth
    
    Returns:
        RedirectResponse to Google's OAuth consent screen
    
    Usage:
        1. Call this endpoint from the frontend
        2. User is redirected to Google
        3. After consent, user lands on /auth/google/callback
    """
    # Create OAuth client
    auth_client = GoogleAuthClient()
    
    # Check if client is configured
    if not auth_client.client_id:
        logger.error("Google OAuth not configured - missing GOOGLE_CLIENT_ID")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    
    # Generate CSRF state token
    state = auth_client.generate_state()
    
    # Store state with user info (for callback)
    _store_state(state, {
        "user_id": str(current_user.id),
        "redirect_after": redirect_after,
    })
    
    # Generate authorization URL with Calendar + Docs scopes
    auth_url = auth_client.get_authorization_url(
        scopes=CALENDAR_SCOPES + DOCS_SCOPES,
        state=state,
    )

    logger.info(
        f"Initiating Google OAuth for user {current_user.id}",
        extra={"scopes": CALENDAR_SCOPES + DOCS_SCOPES}
    )    # Redirect to Google
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def google_callback(
    code: Optional[str] = Query(None, description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="CSRF state token"),
    error: Optional[str] = Query(None, description="Error from Google"),
    error_description: Optional[str] = Query(None, description="Error details"),
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.
    
    This endpoint is called by Google after the user grants (or denies)
    authorization. It exchanges the authorization code for tokens and
    stores them in the database.
    
    Args:
        code: Authorization code from Google (if successful)
        state: CSRF state token (must match what we sent)
        error: Error code if authorization failed
        error_description: Human-readable error description
        db: Database session
    
    Returns:
        RedirectResponse to the app or an error page
    
    Flow:
        1. Validate state token (CSRF protection)
        2. Exchange code for tokens
        3. Get user info from Google
        4. Store tokens in database
        5. Redirect user back to app
    """
    # Check for OAuth errors
    if error:
        logger.warning(f"Google OAuth error: {error} - {error_description}")
        # In production, redirect to an error page in the frontend
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authorization failed: {error_description or error}",
        )
    
    # Validate required parameters
    if not code or not state:
        logger.warning("Missing code or state in OAuth callback")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state parameter",
        )
    
    # Validate state token (CSRF protection)
    state_data = _get_and_remove_state(state)
    if not state_data:
        logger.warning(f"Invalid or expired OAuth state: {state}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state. Please try again.",
        )
    
    user_id = state_data.get("user_id")
    redirect_after = state_data.get("redirect_after", "/")
    
    # Get the user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User not found for OAuth callback: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Exchange code for tokens
    auth_client = GoogleAuthClient()
    
    try:
        tokens = await auth_client.exchange_code_for_tokens(code=code)
    except Exception as e:
        logger.error(f"Failed to exchange code for tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete authentication: {str(e)}",
        )
    
    # Get user info from Google
    try:
        google_user = await auth_client.get_user_info(tokens.access_token)
    except Exception as e:
        logger.warning(f"Failed to get Google user info: {e}")
        google_user = None
    
    # Check if user already has Google credentials
    existing_cred = db.query(OAuthCredential).filter(
        OAuthCredential.user_id == user.id,
        OAuthCredential.provider == "google",
    ).first()
    
    if existing_cred:
        # Update existing credentials
        existing_cred.access_token = tokens.access_token
        existing_cred.refresh_token = tokens.refresh_token or existing_cred.refresh_token
        existing_cred.expires_at = tokens.expires_at
        existing_cred.scopes = tokens.scopes
        if tokens.extra_data:
            existing_cred.extra_data = tokens.extra_data
        
        logger.info(f"Updated Google credentials for user {user.id}")
    else:
        # Create new credentials
        new_cred = OAuthCredential(
            user_id=user.id,
            provider="google",
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_at=tokens.expires_at,
            scopes=tokens.scopes,
            extra_data=tokens.extra_data,
        )
        db.add(new_cred)
        
        logger.info(f"Created Google credentials for user {user.id}")
    
    # Commit to database
    db.commit()
    
    # Redirect to success page or specified URL
    # In production, this would redirect to your frontend
    if redirect_after:
        return RedirectResponse(url=redirect_after)
    
    # Default: return a simple success page
    return {
        "status": "success",
        "message": "Google account connected successfully",
        "google_email": google_user.email if google_user else None,
    }


@router.delete("")
async def disconnect_google(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disconnect Google account from Jarvis.
    
    Revokes the OAuth tokens and removes the stored credentials.
    
    Args:
        current_user: Authenticated Jarvis user
        db: Database session
    
    Returns:
        Success message
    """
    # Find existing credentials
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.user_id == current_user.id,
        OAuthCredential.provider == "google",
    ).first()
    
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Google account connected",
        )
    
    # Revoke token on Google's side
    auth_client = GoogleAuthClient()
    try:
        if cred.access_token:
            await auth_client.revoke_token(cred.access_token)
    except Exception as e:
        logger.warning(f"Failed to revoke token on Google: {e}")
        # Continue anyway - we'll remove our stored credentials
    
    # Delete credentials from database
    db.delete(cred)
    db.commit()
    
    logger.info(f"Disconnected Google account for user {current_user.id}")
    
    return {"status": "success", "message": "Google account disconnected"}


@router.get("/status")
async def google_connection_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check if user has connected their Google account.
    
    Returns connection status and scope information.
    
    Args:
        current_user: Authenticated Jarvis user
        db: Database session
    
    Returns:
        Connection status and granted scopes
    """
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.user_id == current_user.id,
        OAuthCredential.provider == "google",
    ).first()
    
    if not cred:
        return {
            "connected": False,
            "scopes": [],
        }
    
    return {
        "connected": True,
        "scopes": cred.scopes or [],
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
        "is_expired": cred.is_expired(),
    }
