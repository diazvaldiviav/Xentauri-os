"""
Environments Module - External Service Integrations

This module provides a modular architecture for integrating with external
services and APIs (Google, Microsoft, Apple, Notion, Slack, etc.).

Architecture Overview:
======================
environments/
├── __init__.py           # Module exports
├── base.py               # Abstract base classes for all environments
├── google/               # Google Workspace integration
│   ├── __init__.py
│   ├── auth/             # Google OAuth authentication
│   │   ├── __init__.py
│   │   ├── client.py     # OAuth flow implementation
│   │   └── schemas.py    # Auth-related data structures
│   ├── calendar/         # Google Calendar API
│   │   ├── __init__.py
│   │   ├── client.py     # Calendar API client
│   │   ├── schemas.py    # Calendar data structures
│   │   └── renderer.py   # HTML rendering for Raspberry Pi
│   ├── drive/            # Google Drive API (future)
│   ├── docs/             # Google Docs API (future)
│   └── gmail/            # Gmail API (future)
├── microsoft/            # Microsoft 365 integration (future)
└── apple/                # Apple services integration (future)

Design Principles:
==================
1. Single Responsibility: Each service has its own module (calendar, drive, etc.)
2. Shared Authentication: OAuth tokens are reused across services within a provider
3. Provider Isolation: Google, Microsoft, Apple are completely independent
4. Extensibility: Easy to add new providers or services
5. Testability: Each module can be tested independently

Current Status (Sprint 3.5):
============================
- Google OAuth: ✅ Implemented (Calendar scope)
- Google Calendar: ✅ Implemented (List events)
- Google Drive: 🔜 Planned
- Google Docs: 🔜 Planned
- Microsoft: 🔜 Planned
- Apple: 🔜 Planned
"""

from app.environments.base import (
    EnvironmentProvider,
    EnvironmentService,
    EnvironmentError,
    AuthenticationError,
    TokenExpiredError,
    ScopeNotGrantedError,
)

__all__ = [
    "EnvironmentProvider",
    "EnvironmentService",
    "EnvironmentError",
    "AuthenticationError",
    "TokenExpiredError",
    "ScopeNotGrantedError",
]
