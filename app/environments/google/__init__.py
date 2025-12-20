"""
Google Environment Module - Google Workspace Integration

This module provides integration with Google services including:
- Google Calendar (Sprint 3.5) ✅
- Google Docs (Sprint 3.9) ✅
- Google Drive (planned)
- Google Slides (planned)
- Gmail (planned)

Architecture:
=============
google/
├── __init__.py           # Module exports
├── auth/                 # Shared OAuth authentication
│   ├── __init__.py
│   ├── client.py         # Google OAuth implementation
│   └── schemas.py        # Auth data structures
├── calendar/             # Google Calendar API
│   ├── __init__.py
│   ├── client.py         # Calendar API client
│   ├── schemas.py        # Calendar data structures
│   └── renderer.py       # HTML rendering for display
├── docs/                 # Google Docs API (Sprint 3.9)
│   ├── __init__.py
│   ├── client.py         # Docs API client
│   └── schemas.py        # Docs data structures
├── drive/                # Google Drive API (future)
└── gmail/                # Gmail API (future)

Key Design Decisions:
=====================
1. Shared Auth: All Google services use the same OAuth credentials
2. Incremental Scopes: Each service adds only the scopes it needs
3. Service Independence: Calendar, Drive, Docs are independent modules
4. Lazy Loading: Services are only initialized when needed

Usage:
======
    from app.environments.google import GoogleAuthClient, GoogleCalendarClient, GoogleDocsClient
    
    # OAuth flow
    auth_client = GoogleAuthClient()
    auth_url = auth_client.get_authorization_url(scopes=CALENDAR_SCOPES, state="...")
    
    # After callback
    tokens = await auth_client.exchange_code_for_tokens(code)
    
    # Use Calendar API
    calendar = GoogleCalendarClient(access_token=tokens.access_token)
    events = await calendar.list_upcoming_events()
    
    # Use Docs API (Sprint 3.9)
    docs = GoogleDocsClient(access_token=tokens.access_token)
    doc = await docs.get_document("1abc123...")
"""

from app.environments.google.auth import GoogleAuthClient, CALENDAR_SCOPES, DOCS_SCOPES
from app.environments.google.calendar import GoogleCalendarClient, CalendarEvent
from app.environments.google.docs import GoogleDocsClient, GoogleDoc, DocContent

__all__ = [
    "GoogleAuthClient",
    "GoogleCalendarClient",
    "GoogleDocsClient",
    "CalendarEvent",
    "GoogleDoc",
    "DocContent",
    "CALENDAR_SCOPES",
    "DOCS_SCOPES",
]
