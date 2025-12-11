"""
Google Auth Module - OAuth 2.0 Authentication for Google Services

This module handles the OAuth 2.0 flow for Google APIs.
It provides a reusable authentication layer that all Google services
(Calendar, Drive, Docs, etc.) can share.

OAuth 2.0 Flow Overview:
========================
1. User clicks "Connect Google" in the app
2. Backend generates authorization URL with required scopes
3. User is redirected to Google's consent screen
4. User grants permissions
5. Google redirects back with an authorization code
6. Backend exchanges code for access + refresh tokens
7. Tokens are stored for future API calls

Scope Management:
=================
Different Google services require different OAuth scopes.
This module defines scope constants that services can request.
Scopes are requested incrementally - only what's needed.
"""

from app.environments.google.auth.client import GoogleAuthClient
from app.environments.google.auth.schemas import (
    GoogleAuthConfig,
    GoogleTokenResponse,
    GoogleUserInfo,
    CALENDAR_SCOPES,
    DRIVE_SCOPES,
    GMAIL_SCOPES,
    PROFILE_SCOPES,
)

__all__ = [
    "GoogleAuthClient",
    "GoogleAuthConfig",
    "GoogleTokenResponse",
    "GoogleUserInfo",
    "CALENDAR_SCOPES",
    "DRIVE_SCOPES",
    "GMAIL_SCOPES",
    "PROFILE_SCOPES",
]
