# Jarvis Project Context

> **Last Updated:** December 12, 2025
> **Current Sprint:** Sprint 4 - Raspberry Pi Agent
> **Tech Debt Cleanup:** ✅ Complete (301 tests, 84% router reduction)
> **Status:** ✅ Ready for Pi Agent development

Jarvis is an intelligent screen control system that lets users operate multiple display devices (TVs, monitors) via voice or text commands from their phone. The system comprises three main components:

- **Jarvis Remote** (iOS app): User-facing mobile application for voice/text commands and device management.
- **Jarvis Cloud Core** (Backend): Cloud services that process commands, manage devices/sessions, orchestrate agents, and provide APIs.
- **Jarvis Stick** (Raspberry Pi Agents): Edge software running on Raspberry Pi devices connected to screens, executing commands locally.

---

## 📊 Project Progress

### Sprint 1: Backend Foundations ✅ COMPLETE
| Task | Status |
|------|--------|
| FastAPI project structure | ✅ Done |
| PostgreSQL + SQLAlchemy + Alembic | ✅ Done |
| User model | ✅ Done |
| Device model | ✅ Done |
| POST /auth/register | ✅ Done |
| POST /auth/login (JWT) | ✅ Done |
| JWT middleware (get_current_user) | ✅ Done |
| GET /users/me (protected route) | ✅ Done |
| Local development running | ✅ Done |
| Database migrations | ✅ Done |
| Deploy to Fly.io | ⏳ Pending |

### Sprint 2: WebSocket Hub + Device Management ✅ COMPLETE
| Task | Status |
|------|--------|
| Device CRUD endpoints | ✅ Done |
| Device schemas (Pydantic) | ✅ Done |
| Pairing code service (generate, validate, consume) | ✅ Done |
| WebSocket connection manager | ✅ Done |
| WebSocket endpoint (ws/devices) | ✅ Done |
| Command routing service | ✅ Done |
| Command endpoints (send, power, status) | ✅ Done |
| Pytest test suite | ✅ Done |

### Sprint 3: AI Router + Intent Processing ✅ COMPLETE
| Task | Status |
|------|--------|
| AI provider clients (Gemini, OpenAI, Anthropic) | ✅ Done |
| AI Router/Orchestrator (Gemini Flash) | ✅ Done |
| Intelligent routing (Simple→Gemini, Execution→GPT, Reasoning→Claude) | ✅ Done |
| Intent Parser (NLU) | ✅ Done |
| Prompt engineering templates | ✅ Done |
| Device name fuzzy matching | ✅ Done |
| POST /intent endpoint with full routing | ✅ Done |
| Unified AI Monitor (DRY: logging + metrics) | ✅ Done |
| Test suite for intent parsing | ✅ Done |

### Sprint 3.5: Google OAuth + Calendar Integration ✅ COMPLETE
| Task | Status |
|------|--------|
| Environment module architecture (modular, extensible) | ✅ Done |
| Google OAuth client (auth code flow) | ✅ Done |
| OAuthCredential model (multi-provider token storage) | ✅ Done |
| Google Calendar API client | ✅ Done |
| Calendar HTML renderer (Chromium kiosk optimized) | ✅ Done |
| GET /auth/google/login endpoint | ✅ Done |
| GET /auth/google/callback endpoint | ✅ Done |
| GET /cloud/calendar endpoint (HTML) | ✅ Done |
| Database migration for oauth_credentials | ✅ Done |
| Display Simulator for development testing | ✅ Done |
| Simulator content persistence (localStorage) | ✅ Done |
| Content token service (signed iframe URLs) | ✅ Done |
| SHOW_CONTENT command type | ✅ Done |
| Intent prompts for calendar display | ✅ Done |

### Sprint 3.6: Unified AI Context + Calendar Intelligence ✅ COMPLETE
| Task | Status |
|------|--------|
| UnifiedContext system (single source of truth) | ✅ Done |
| Base prompt templates (DRY for all AI models) | ✅ Done |
| Action response schemas (structured GPT-4o JSON) | ✅ Done |
| Execution prompts for GPT-4o | ✅ Done |
| Update _handle_complex_task with UnifiedContext | ✅ Done |
| Calendar date parameter in /cloud/calendar | ✅ Done |
| Fix schema mismatch (device_type) | ✅ Done |
| GPT-4o JSON response logging & error handling | ✅ Done |
| Calendar date URL parameter passthrough | ✅ Done |

### Sprint 4: Raspberry Pi Agent (Next)
- Agent project structure (Python)
- WebSocket client to connect to cloud
- Pairing flow implementation
- HDMI-CEC command execution (cec-client)
- Command acknowledgment and status reporting
- Local configuration and persistence

---

## 🏗️ Current Architecture

```
Jarvis_Cloud/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── deps.py              # Dependencies (get_current_user)
│   ├── core/
│   │   ├── config.py        # Settings from .env (incl. AI + OAuth keys)
│   │   └── security.py      # Password hashing, JWT creation
│   ├── db/
│   │   ├── base.py          # SQLAlchemy Base class
│   │   └── session.py       # Database engine & session
│   ├── models/
│   │   ├── user.py          # User ORM model
│   │   ├── device.py        # Device ORM model
│   │   └── oauth_credential.py  # OAuth token storage (Sprint 3.5)
│   ├── routers/
│   │   ├── auth.py          # /auth/register, /auth/login
│   │   ├── users.py         # /users/me
│   │   ├── devices.py       # Device CRUD + pairing
│   │   ├── commands.py      # Send commands to devices
│   │   ├── intent.py        # AI intent processing (Sprint 3)
│   │   ├── websocket.py     # WebSocket for Pi agents
│   │   ├── google_auth.py   # Google OAuth endpoints (Sprint 3.5)
│   │   ├── cloud.py         # Cloud content for displays (Sprint 3.5)
│   │   └── simulator.py     # Display simulator for dev testing (Sprint 3.5)
│   ├── services/
│   │   ├── pairing.py           # Pairing code generation/validation
│   │   ├── websocket_manager.py # Connection manager
│   │   ├── commands.py          # Command routing service
│   │   ├── intent_service.py    # Intent processing business logic
│   │   ├── content_token.py     # Signed content tokens for iframes
│   │   ├── calendar_search_service.py # Smart calendar search with LLM (Sprint 3.7)
│   │   ├── pending_event_service.py   # Pending event creation (Sprint 3.8, TTL 120s)
│   │   └── pending_edit_service.py    # Pending edit/delete operations (Sprint 3.9, TTL 120s)
│   ├── schemas/
│   │   ├── auth.py          # Request/response schemas for auth
│   │   ├── user.py          # UserOut schema
│   │   └── device.py        # Device schemas
│   ├── ai/                   # AI Module (Sprint 3) - The Brain
│   │   ├── __init__.py      # Module exports
│   │   ├── context.py       # UnifiedContext system (Sprint 3.6)
│   │   ├── actions/         # Action Registry (Tech Debt Cleanup)
│   │   │   ├── __init__.py  # Module exports
│   │   │   └── registry.py  # ActionDefinition, ActionRegistry (11 actions)
│   │   ├── providers/       # LLM Provider Clients
│   │   │   ├── base.py      # Abstract provider interface
│   │   │   ├── gemini.py    # Google Gemini (orchestrator)
│   │   │   ├── openai_provider.py   # OpenAI GPT (execution)
│   │   │   └── anthropic_provider.py # Claude (reasoning)
│   │   ├── router/          # AI Orchestration
│   │   │   └── orchestrator.py  # Routes requests to models
│   │   ├── intent/          # Natural Language Understanding
│   │   │   ├── schemas.py   # Intent data structures
│   │   │   ├── parser.py    # LLM-based intent extraction
│   │   │   └── device_mapper.py # Fuzzy device name matching
│   │   ├── prompts/         # Prompt Templates (Sprint 3.6)
│   │   │   ├── base_prompt.py      # Shared templates for all models
│   │   │   ├── execution_prompts.py # GPT-4o execution prompts
│   │   │   ├── router_prompts.py   # Routing decision prompts
│   │   │   └── intent_prompts.py   # Intent extraction prompts
│   │   ├── schemas/         # AI Response Schemas (Sprint 3.6)
│   │   │   ├── __init__.py  # Schema exports
│   │   │   └── action_response.py  # Structured GPT-4o responses
│   │   └── monitoring/      # Observability (Unified)
│   │       ├── monitor.py   # AIMonitor: unified logging + metrics (DRY)
│   │       ├── logger.py    # Legacy AILogger (deprecated)
│   │       └── metrics.py   # Legacy AIMetrics (deprecated)
│   └── environments/         # External Service Integrations (Sprint 3.5)
│       ├── __init__.py      # Module exports
│       ├── base.py          # Abstract interfaces for all providers
│       └── google/          # Google Workspace Integration
│           ├── __init__.py  # Google module exports
│           ├── auth/        # Google OAuth 2.0
│           │   ├── __init__.py
│           │   ├── client.py    # OAuth flow implementation
│           │   └── schemas.py   # Auth data structures
│           └── calendar/    # Google Calendar API
│               ├── __init__.py
│               ├── client.py    # Calendar API client
│               ├── schemas.py   # Calendar data structures
│               └── renderer.py  # HTML rendering for Raspberry Pi
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_action_registry.py   # Action registry tests (37 tests)
│   ├── test_action_response.py   # AI response schema tests (47 tests)
│   ├── test_ai_providers.py      # AI provider base tests (23 tests)
│   ├── test_ai_router.py         # AI orchestrator tests (29 tests)
│   ├── test_device_mapper.py     # Device matching tests (42 tests)
│   ├── test_devices.py           # Device CRUD tests
│   ├── test_intent.py            # Intent parsing tests
│   ├── test_intent_parser.py     # Parser edge cases (33 tests)
│   ├── test_intent_service.py    # Service layer tests (32 tests)
│   ├── test_intent_search.py     # Calendar search intent tests
│   ├── test_calendar_query.py    # Calendar query tests
│   ├── test_calendar_search.py   # Calendar search tests
│   ├── test_calendar_smart_search.py # Smart search tests
│   ├── test_calendar_edit_handler.py # Calendar edit/delete tests (21 tests)
│   ├── test_calendar_create_handler.py # Calendar create tests
│   ├── test_sprint_391_bugfixes.py  # Sprint 3.9.1 bug fix tests (13 tests)
│   ├── test_pairing.py           # Pairing service tests
│   └── test_websocket_manager.py # WebSocket manager tests
├── alembic/                  # Database migrations
├── venv/                     # Python virtual environment
├── .env                      # Environment variables (not in git)
├── .env.example              # Template for .env
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build
├── fly.toml                  # Fly.io deployment config
├── RUN_PROJECT.txt           # Instructions to run locally
└── CONTEXT.md                # This file
```

---

## 🔌 API Endpoints (Current)

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /auth/register | No | Create new user account |
| POST | /auth/login | No | Login, returns JWT token |

### Users
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /users/me | Yes | Get current user profile |

### Devices
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /devices | Yes | Create a new device |
| GET | /devices | Yes | List user's devices |
| GET | /devices/{id} | Yes | Get device details |
| PATCH | /devices/{id} | Yes | Update device |
| DELETE | /devices/{id} | Yes | Delete device |
| POST | /devices/{id}/pairing-code | Yes | Generate pairing code |
| POST | /devices/pair | No | Pair agent with device (uses pairing code) |

### Commands
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /commands/{device_id} | Yes | Send custom command |
| POST | /commands/{device_id}/power/on | Yes | Turn device on |
| POST | /commands/{device_id}/power/off | Yes | Turn device off |
| GET | /commands/{device_id}/status | Yes | Check if device is online |

### Intent (AI - Sprint 3)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /intent | Yes | Process natural language command |
| GET | /intent/stats | Yes | Get AI usage statistics |

### Google OAuth (Sprint 3.5)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /auth/google/login | Yes | Initiate Google OAuth flow |
| GET | /auth/google/callback | No | Handle OAuth callback |
| DELETE | /auth/google | Yes | Disconnect Google account |
| GET | /auth/google/status | Yes | Check Google connection status |

### Cloud Content (Sprint 3.5)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /cloud/calendar | Yes | Rendered HTML calendar for Pi |
| GET | /cloud/calendar/preview | No | Demo calendar (no auth) |
| GET | /cloud/calendar/status | Yes | Calendar integration status |

### Display Simulator (Sprint 3.5)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /simulator | No | Device selection page |
| GET | /simulator/{device_id} | No | Simulator for specific device |

### WebSocket
| Endpoint | Auth | Description |
|----------|------|-------------|
| ws://.../ws/devices?agent_id=xxx | No | Agent connection (Pi connects here) |

### System
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /health | No | Health check |

**API Docs:** http://localhost:8000/docs

---

## 🛠️ Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | FastAPI | 0.115.2 |
| Server | Uvicorn | 0.32.0 |
| Database | PostgreSQL | 16 |
| ORM | SQLAlchemy | 2.0.36 |
| Migrations | Alembic | 1.13.2 |
| Auth | JWT (python-jose) | 3.3.0 |
| Password | bcrypt (passlib) | 1.7.4 |
| Validation | Pydantic | 2.9.2 |
| HTTP Client | httpx | 0.27.2 |
| Testing | Pytest | 8.3.3 |
| Deployment | Fly.io | - |
| AI - Gemini | google-generativeai | 0.8.3 |
| AI - OpenAI | openai | 1.55.3 |
| AI - Claude | anthropic | 0.39.0 |

---

## 🚀 How to Run

```bash
# Quick start (one command):
cd /Users/victordiaz/Jarvis/Jarvis_Cloud && source venv/bin/activate && docker start jarvis-postgres && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

See `RUN_PROJECT.txt` for detailed instructions.

---

## 🔐 Environment Variables

```bash
# .env file
DATABASE_URL=postgresql+psycopg://jarvis:jarvis123@localhost:5432/jarvis_db
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# AI API Keys (Sprint 3)
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Google OAuth (Sprint 3.5)
# Get these from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

---

## 🧠 AI Router Architecture (Sprint 3)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     POST /intent - Full Flow                             │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AI Router (Orchestrator)                             │
│                      [Gemini 2.5 Flash Lite]                             │
│                                                                          │
│         Analyzes request complexity and decides routing                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    SIMPLE     │     │   COMPLEX     │     │   COMPLEX     │
│               │     │  EXECUTION    │     │  REASONING    │
│ Device cmds,  │     │               │     │               │
│ simple Q&A    │     │ Code, tools,  │     │ Analysis,     │
│               │     │ step-by-step  │     │ planning,     │
│ Gemini Flash  │     │   GPT-4o      │     │ Claude Haiku  │
│ Intent Parser │     │               │     │               │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Device Mapper │     │ Direct AI     │     │ Direct AI     │
│ + Command Svc │     │ Response      │     │ Response      │
└───────────────┘     └───────────────┘     └───────────────┘

Example Flows:

1. Simple Command: "Turn on the living room TV"
   → Router: SIMPLE → Gemini Intent Parser → Device Mapper → WebSocket → TV On

2. Code Request: "Write a Python script to schedule my TV"
   → Router: COMPLEX_EXECUTION → GPT-4o → Returns Python code

3. Analysis Request: "Analyze my device setup for efficiency"
   → Router: COMPLEX_REASONING → Claude → Returns analysis
```

### Intent Processing Architecture (Refactored)

After the technical debt cleanup, the intent processing follows a clean separation:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Clean Architecture                                   │
└─────────────────────────────────────────────────────────────────────────┘

Before (1319 lines):                After (205 + 1056 lines):
┌───────────────────┐               ┌───────────────────┐
│   intent.py       │               │   intent.py       │  ← HTTP only (205 lines)
│   (ROUTER)        │               │   (ROUTER)        │
│                   │               └─────────┬─────────┘
│ - HTTP handling   │                         │
│ - Intent parsing  │                         ▼
│ - Device matching │               ┌───────────────────┐
│ - Command exec    │               │ intent_service.py │  ← Business logic (1056 lines)
│ - Content display │               │   (SERVICE)       │
│ - Complex tasks   │               └─────────┬─────────┘
│ - Message build   │                         │
│ - Error handling  │               ┌─────────┴─────────┐
└───────────────────┘               │                   │
                                    ▼                   ▼
                          ┌──────────────┐    ┌──────────────┐
                          │ ActionRegistry│    │   AI/Cmds    │
                          │ (11 actions) │    │   Providers  │
                          └──────────────┘    └──────────────┘
```

**IntentService** (Single Responsibility):
- `process()` - Main entry point
- `_handle_simple_task()` - Gemini intent parsing
- `_handle_complex_task()` - GPT/Claude routing
- `_handle_device_command()` - Device commands
- `_handle_device_query()` - Status queries
- `_handle_system_query()` - System info
- `_handle_conversation()` - Greetings, thanks
- `_execute_content_action()` - Calendar display
- `_execute_device_command()` - Power, volume, etc.

**ActionRegistry** (Centralized Definitions):
- 11 built-in actions: power_on, power_off, volume_up, volume_down, mute, unmute, set_input, volume_set, show_calendar, show_content, clear_content
- Parameter validation with custom validators
- Action aliases (e.g., "turn_on" → "power_on")
- Category-based queries

### Unified AI Monitoring (DRY Principle)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AIMonitor (Unified)                                  │
│                                                                          │
│  One call = Structured Logs + In-Memory Metrics + Cost Tracking          │
│                                                                          │
│  ai_monitor.track_request()   → Logs request start                       │
│  ai_monitor.track_response()  → Logs response + updates metrics          │
│  ai_monitor.track_routing()   → Logs routing decisions                   │
│  ai_monitor.track_intent()    → Logs parsed intents                      │
│  ai_monitor.track_command()   → Logs device commands                     │
│  ai_monitor.track_error()     → Logs errors                              │
│  ai_monitor.get_stats()       → Returns aggregated metrics               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Environment Integrations Architecture (Sprint 3.5)

The environments module provides a modular, extensible architecture for integrating
with external services (Google, Microsoft, Apple, etc.).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Environment Architecture                             │
└─────────────────────────────────────────────────────────────────────────┘

environments/
├── base.py                    # Abstract interfaces
│   ├── EnvironmentProvider    # OAuth provider contract
│   ├── EnvironmentService     # API service contract
│   └── Custom Exceptions      # AuthError, TokenExpired, etc.
│
├── google/                    # Google Workspace ✅ Implemented
│   ├── auth/                  # Shared OAuth for all Google services
│   │   ├── client.py          # GoogleAuthClient
│   │   └── schemas.py         # Scopes, token responses
│   ├── calendar/              # ✅ Google Calendar API
│   │   ├── client.py          # GoogleCalendarClient
│   │   ├── schemas.py         # CalendarEvent, etc.
│   │   └── renderer.py        # HTML for Raspberry Pi
│   ├── drive/                 # 🔜 Planned
│   ├── docs/                  # 🔜 Planned
│   └── gmail/                 # 🔜 Planned
│
├── microsoft/                 # 🔜 Microsoft 365 (future)
│   ├── auth/                  # Microsoft OAuth
│   ├── outlook/               # Outlook Calendar
│   └── onedrive/              # OneDrive
│
└── apple/                     # 🔜 Apple Services (future)
    └── calendar/              # iCloud Calendar
```

### Google Calendar Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Google Calendar Display Flow                         │
└─────────────────────────────────────────────────────────────────────────┘

1. AUTHENTICATION (One-time setup)
   ┌─────────┐     ┌─────────────────┐     ┌──────────────┐
   │   User  │────▶│ /auth/google    │────▶│   Google     │
   │   App   │     │ /login          │     │ OAuth Screen │
   └─────────┘     └─────────────────┘     └──────┬───────┘
                                                   │
                                                   ▼
   ┌─────────────────┐     ┌─────────────────┐     │
   │ OAuthCredential │◀────│ /auth/google    │◀────┘
   │    (DB)         │     │ /callback       │
   └─────────────────┘     └─────────────────┘

2. DISPLAY (Raspberry Pi)
   ┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
   │ Raspberry   │────▶│ GET /cloud      │────▶│ Google       │
   │ Pi Browser  │     │ /calendar       │     │ Calendar API │
   └─────────────┘     └────────┬────────┘     └──────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ CalendarRenderer│
                       │ (HTML Output)   │
                       └─────────────────┘
```

### Design Principles

1. **Provider Isolation**: Google, Microsoft, Apple are completely independent
2. **Service Modularity**: Calendar, Drive, Gmail are separate modules
3. **Shared Authentication**: OAuth tokens reused across services within a provider
4. **Extensibility**: Easy to add new providers or services
5. **Single Responsibility**: Each module has one clear purpose

---

## Vision & Objectives
- Demonstrate end-to-end technical feasibility of voice/text command control.
- Enable basic screen control from iOS (power, input/source, volume, mute, brightness where applicable; HDMI-CEC and vendor APIs).
- Establish a scalable, secure base architecture for future features.
- Create a functional product suitable for investor demonstrations.

---

## Core User Story (MVP)
“As a user, I can open the Jarvis iOS app, select a screen, and send a voice or text command (e.g., ‘Turn on Living Room TV’ or ‘Switch to HDMI 2’). The command is processed in the cloud and executed by the Raspberry Pi attached to that screen, with status and feedback returned to my app.”

## High-Level Architecture (MVP)
- Client (iOS):
  - Auth: Sign-in, session management.
  - Command UI: Voice capture (speech-to-text), text entry.
  - Device list: Discover, link, and select screens.
  - Feedback: Show command status and errors.
- Cloud Core:
  - API Gateway: HTTPS REST endpoints for auth, devices, commands.
  - Command Processor: Validates, routes, and persists command requests.
  - Device Registry: Maps users to devices/agents; stores capabilities.
  - Messaging Layer: Secure channel to agents (e.g., MQTT/WebSocket).
  - Observability: Logs, metrics, traces for demo reliability.
- Raspberry Pi Agent:
  - Secure Connect: Auth to cloud and subscribe to device-specific topics.
  - Command Executor: HDMI-CEC control, IR blaster fallback, vendor APIs.
  - Status Reporter: Ack/complete with result codes and optional telemetry.

## MVP Feature Scope
- Accounts & Auth: Single-user or simple email-based login, basic token auth.
- Device Onboarding: Pair Pi agent with a user and assign a friendly name.
- Basic Commands: Power on/off; input/source change; volume/mute; possibly brightness (monitor-dependent).
- Feedback: Command accepted, executing, success/failure.
- Reliability: Retries, timeouts, and clear error messages.

## Non-Goals (MVP)
- Complex multi-user orgs, roles, or granular RBAC.
- Rich scheduling/automation, scenes, or macros.
- Deep vendor integrations beyond simple HDMI-CEC + limited APIs.
- Offline-first mobile experience.

## Assumptions & Constraints
- Platforms: iOS (Swift/SwiftUI), Raspberry Pi OS (Linux), Cloud (AWS/Azure/GCP TBD).
- Connectivity: Pi agents have internet access; devices support HDMI-CEC or IR.
- Security: Basic authentication and encrypted messaging; device claims verified.
- Scalability: MVP supports small demo scale but designed to grow.
- Observability: Minimal but sufficient logging/metrics for demos.

## Interfaces (Initial)
- Mobile ↔ Cloud: REST/JSON; authentication via tokens.
- Cloud ↔ Agent: MQTT or WebSocket with per-device topics; payloads as JSON.
- Agent ↔ Screen: HDMI-CEC (via `cec-client`/libCEC), IR (via LIRC), vendor SDKs when available.

## Data Model (MVP, conceptual)
- User: id, email, display name.
- Device: id, userId, name, capabilities (power, input, volume), agentId.
- Command: id, deviceId, type (power_on, input_hdmi2, volume_set), parameters, status, timestamps.
- Agent: id, deviceId, status, lastSeen, version.

## Reliability & Safety
- Command lifecycle: received → dispatched → executing → completed/failed.
- Timeouts & retries: bounded; idempotent handling where feasible.
- Error taxonomy: network, auth, capability unsupported, device offline.

## Demo Scenario
- Onboard 2–3 devices with Pi sticks.
- Voice commands from iOS to turn on/off and switch inputs.
- Real-time status and simple analytics (e.g., command success rate).

## Future Extensions (Post-MVP)
- Scenes/macros (e.g., “Movie Night”) and scheduling.
- Multi-user sharing, roles, and orgs.
- Rich vendor integrations and device discovery.
- Cross-platform mobile and web console.
- Advanced telemetry, anomaly detection, and health scoring.

## Open Questions
- Cloud choice and managed services (API Gateway, MQTT broker, DB).
- Preferred auth (OAuth/Sign in with Apple) for iOS.
- Final messaging protocol (MQTT vs WebSocket) and QoS.
- Device onboarding UX (QR code, shared secret, or claim tokens).

## Success Criteria (MVP)
- End-to-end demo with at least two screens controlled via iOS.
- Stable commands for power and input switching under normal network conditions.
- Clear architecture foundation enabling quick iteration on new features.

---

## 📝 Session Notes

### December 12, 2025 - Technical Debt Cleanup Complete
- **Phase 1: Tests First** (89 tests)
  - `test_action_response.py` - 47 tests for AI response schemas
  - `test_device_mapper.py` - 42 tests for device fuzzy matching
  - Established baseline before refactoring
- **Phase 2: Extract Service Layer** (69 tests added → 158 total)
  - Created `app/ai/actions/registry.py` with ActionRegistry
    - ActionDefinition dataclass for action metadata
    - 11 built-in actions with parameter validation
    - Custom validators (e.g., volume range 0-100)
    - Aliases ("turn_on" → "power_on")
  - Created `app/services/intent_service.py` with IntentService
    - IntentResult dataclass for standardized responses
    - IntentResultType enum for classification
    - All business logic extracted from router
  - `test_action_registry.py` - 37 tests
  - `test_intent_service.py` - 32 tests
- **Phase 3: Slim Down Router** (refactoring, no new tests)
  - Refactored `intent.py` from 1319 lines to 205 lines (84% reduction)
  - Router now delegates all business logic to IntentService
  - Clean separation: HTTP handling vs business logic
- **Phase 4: AI Module Tests** (85 tests added → 301 total)
  - `test_ai_providers.py` - 23 tests for base classes, mock patterns
  - `test_ai_router.py` - 29 tests for orchestrator, routing logic
  - `test_intent_parser.py` - 33 tests for parsing edge cases
  - All LLM calls mocked for fast, reliable tests
- **Phase 5: Documentation**
  - Updated CONTEXT.md with new architecture
  - Added Intent Processing Architecture diagram
  - Documented IntentService and ActionRegistry
  - Updated test file inventory

**Final Stats:**
- 301 tests passing ✅
- Router reduced 84% (1319 → 205 lines)
- Service layer: 1056 lines of business logic
- Action registry: 11 built-in actions with validation

### December 10, 2025 - Sprint 3.6 Complete
- **All Bugs Fixed:**
  - Schema mismatch (device_type) - resolved with getattr() fallback
  - GPT-4o JSON parsing - improved error handling and logging
  - Calendar date parameter - now passes through to simulator iframe URL
- **UnifiedContext System:** Single source of truth for all AI models
  - `UnifiedContext` dataclass with user, devices, OAuth status
  - `DeviceCapability` with can_power_control, can_show_content flags
  - `OAuthStatus` tracking Google Calendar, Drive availability
  - `build_unified_context()` fetches and assembles request-scoped context
- **Base Prompt Templates:** DRY principle for AI prompts
  - `build_router_prompt()` - Gemini orchestrator prompt
  - `build_executor_prompt()` - GPT-4o execution prompt
  - `build_reasoner_prompt()` - Claude reasoning prompt
  - `build_intent_prompt()` - Gemini intent parser prompt
  - All accept UnifiedContext and inject capabilities dynamically
- **Structured Action Responses:** Pydantic schemas for GPT-4o JSON
  - `ActionResponse` - Single action with device, parameters, confidence
  - `ClarificationResponse` - Missing information request
  - `ActionSequenceResponse` - Multi-step actions
  - `parse_action_response()` - Validates and parses GPT-4o output
- **Execution Prompts:** GPT-4o specific prompt engineering
  - System prompt with JSON schema and examples
  - 7 detailed examples: clear requests, ambiguity, sequences, errors
  - Few-shot learning for consistent JSON output
- **Intent Router Updates:**
  - `_handle_complex_task()` now uses UnifiedContext
  - `_execute_gpt_action()` helper for action execution
  - Calendar date parameter passthrough to display URL
- **Calendar Date Support:**
  - Added `date` query parameter to `GET /cloud/calendar`
  - Endpoint accepts YYYY-MM-DD format
  - Date now properly passed to simulator iframe

### December 4, 2025 - Sprint 3.5 Complete
- **Environment Module Architecture:** Modular structure for external integrations
  - Base interfaces: `EnvironmentProvider`, `EnvironmentService`
  - Provider isolation: Google, Microsoft, Apple independent
  - Service modularity: Calendar, Drive, Gmail as separate modules
- **Google OAuth Integration:**
  - Full OAuth 2.0 authorization code flow
  - Token storage in `OAuthCredential` model
  - Automatic token refresh when expired
  - Endpoints: `/auth/google/login`, `/auth/google/callback`, `/auth/google/status`
- **Google Calendar Client:**
  - Fetch upcoming events from user's calendar
  - Support for today, week, and custom date ranges
  - List available calendars
- **Calendar HTML Renderer:**
  - Optimized for Chromium kiosk mode on Raspberry Pi
  - Dark/light theme support
  - Auto-refresh meta tag
  - Clean, readable typography for TV display
- **Cloud Content Endpoints:**
  - `GET /cloud/calendar` - Rendered HTML calendar
  - `GET /cloud/calendar/preview` - Demo without auth
  - `GET /cloud/calendar/status` - Integration status
- **Display Simulator:**
  - Browser-based display that acts as virtual Raspberry Pi
  - WebSocket connection (same as real Pi)
  - Content persistence via localStorage (survives page refresh)
  - Signed content tokens for iframe authentication
  - Keyboard shortcuts: L=logs, ESC=clear, F=fullscreen
- **Content Token Service:**
  - Short-lived JWT tokens (5 min) for iframe URLs
  - Solves iframe authentication problem (can't use headers)
  - Automatic token validation in cloud endpoints
- **Database Migration:** New `oauth_credentials` table
- All code thoroughly documented with learning comments

### December 4, 2025 - Sprint 3 Complete
- **AI Provider Clients:** Unified interface for Gemini, OpenAI, and Anthropic
  - Gemini 2.5 Flash Lite (orchestrator + simple tasks)
  - GPT-4o (complex execution: code, tools)
  - Claude 3 Haiku (complex reasoning: analysis, planning)
- **AI Router (Orchestrator):** Full intelligent routing implemented
  - Analyzes request complexity before processing
  - Routes SIMPLE → Gemini Intent Parser
  - Routes COMPLEX_EXECUTION → GPT-4o direct response
  - Routes COMPLEX_REASONING → Claude direct response
- **Intent Parser:** LLM-powered NLU extracts structured intents
  - Supports: device_command, device_query, system_query, conversation
  - Actions: power_on/off, set_input, volume, mute, status
- **Device Mapper:** Fuzzy matching for device names
  - Handles variations: "living room tv" → "Living Room TV"
  - Token matching and Levenshtein similarity
- **POST /intent Endpoint:** Full natural language command processing with routing
- **Unified AIMonitor (DRY):** Single class for logging + metrics
  - Replaced separate AILogger and AIMetrics
  - One call tracks both logs and metrics
  - Cost estimation per provider
- **Prompt Engineering:** Separate templates for routing and intent extraction
- All code thoroughly documented

### December 2, 2025 - Sprint 2 Complete
- **Device CRUD:** Full REST endpoints for managing devices
- **Pairing Service:** 6-character codes, 15-min TTL, one-time use
- **WebSocket Hub:** Connection manager for Pi agents (device_id → connection)
- **Command Routing:** Send commands through WebSocket to connected devices
- **Test Suite:** Pytest tests for devices, pairing, and WebSocket manager
- All code has detailed comments for learning

### December 2, 2025 - Sprint 1 Complete
- Created project structure with FastAPI
- Implemented User and Device models with SQLAlchemy
- Added auth endpoints: register and login with JWT
- Added protected /users/me endpoint
- Configured PostgreSQL with Docker
- All code files have detailed comments for learning
- API running locally on port 8000

### December 17, 2025 - Sprint 3.9.1 Complete (AI Layer Bug Fixes)
- **Bug #1: Timezone Missing in EDIT Flow** ✅
  - Root cause: `_handle_confirm_edit()` didn't call `get_user_timezone()`
  - Symptom: Events edited to 4pm would display as 11am (UTC interpretation)
  - Fix: Added `get_user_timezone()` call and pass to `processed_changes`
  - Passes timezone to EventUpdateRequest for proper API handling
- **Bug #2: Parser Ignoring Pending Context** ✅
  - Root cause: Parser only extracted "devices" from context, ignored pending_operation
  - Symptom: "Yes" after event creation might not route to CONFIRM_CREATE
  - Fix: Added pending_operation context extraction in `intent/parser.py`
  - Now includes: has_pending_create/edit/delete, pending_op_type, age, hints
- **Bug #3: TTL Too Short** ✅
  - Root cause: TTL_SECONDS = 60 was too aggressive for confirmation flows
  - Symptom: Users saying "yes" after 1 minute got "no pending event" errors
  - Fix: Changed TTL from 60s to 120s in both pending services
  - Updated docstrings and tests to reflect new timeout
- **New Tests:**
  - `tests/test_sprint_391_bugfixes.py` - 13 new tests covering all bug fixes
  - Timezone extraction and pass-through tests
  - Parser pending context extraction tests
  - TTL constant verification tests
- **648 tests passing** ✅

### December 16, 2025 - Sprint 3.9 Complete (Calendar Edit & Delete)
- **Calendar Edit Handler:**
  - `_handle_edit_existing_event()` - Find events by semantic search
  - Uses `calendar_search_service.smart_search()` for LLM matching (typos, synonyms, translations)
  - Stores pending edit in `pending_edit_service` for confirmation
  - `_handle_confirm_edit()` - Context-aware confirmation (checks pending_event first)
  - `_process_time_changes()` - Combines original event date with new time values
  - Validation for time-only changes (e.g., "change to 7am")
- **Calendar Delete Handler:**
  - `_handle_delete_existing_event()` - Find events by semantic search
  - Stores pending delete in `pending_edit_service` for confirmation
  - `_handle_confirm_delete()` - Context-aware confirmation
- **PendingEditService:**
  - `store_pending_edit()` - Handles both CalendarEvent objects and dicts
  - `get_pending()` - Retrieve pending operation (edit/delete)
  - `select_event()` - User selects from multiple matches
  - `confirm_pending()` - Execute the edit or delete
  - Converts CalendarEvent to MatchingEvent format
- **Context-Aware Confirmation:**
  - `_handle_confirm_create()` now checks pending_edit first
  - `_handle_confirm_edit()` checks pending_event first
  - `_handle_confirm_delete()` checks all pending services
  - Prevents "yes confirm" routing to wrong handler
- **Bug Fixes:**
  - Removed invalid `refresh_token` from GoogleCalendarClient (4 locations)
  - Fixed `search_result.get()` to direct list assignment
  - Fixed ValidationError for time-only datetime strings
- **622 tests passing** ✅

### December 15, 2025 - Sprint 3.8 Complete (Calendar Event Creation)
- **Calendar Create Handler:**
  - `_handle_create_event()` - Parse user intent for event creation
  - Extracts title, date, time, duration, description from natural language
  - Uses LLM to parse complex date expressions ("next Friday", "tomorrow at 3pm")
  - Stores pending event in `pending_event_service` for confirmation
  - `_handle_confirm_create()` - Confirms and creates the event
- **PendingEventService:**
  - `store_pending()` - Store event details awaiting confirmation
  - `get_pending()` - Retrieve pending event for user
  - `confirm_pending()` - Create event via Google Calendar API
  - `cancel_pending()` - User cancels creation
- **Natural Language Parsing:**
  - Relative dates: "tomorrow", "next week", "in 3 days"
  - Time expressions: "at 3pm", "from 2-4pm", "for 2 hours"
  - Combined: "meeting with John tomorrow at 10am for 1 hour"

### December 14, 2025 - Sprint 3.7 Complete (Smart Calendar Search)
- **CalendarSearchService:**
  - `smart_search()` - LLM-powered semantic calendar search
  - Handles typos, synonyms, translations, abbreviations
  - Returns `SmartSearchResult` with events, corrected_query, no_match_found
  - Separates search logic from intent handler (Single Responsibility)
- **SmartSearchResult Dataclass:**
  - `events: List[CalendarEvent]` - Matching events
  - `corrected_query: Optional[str]` - LLM-corrected search term
  - `no_match_found: bool` - True if no events match
  - `error: Optional[str]` - Error message if any
- **Query Correction:**
  - "dentist appt" → "Dentist Appointment"
  - "mtg w/ john" → "Meeting with John"
  - "cita médico" → "Doctor Appointment" (translation)
- **Integration:**
  - Used by `_handle_edit_existing_event()`
  - Used by `_handle_delete_existing_event()`
  - Replaces direct Google Calendar API search

### Next Session Tasks (Sprint 4 - Raspberry Pi Agent)
1. Create Jarvis_Stick project structure (Python)
2. Implement WebSocket client to connect to cloud
3. Pairing flow implementation
4. HDMI-CEC command execution (cec-client)
5. Command acknowledgment and status reporting
6. Local configuration and persistence
7. Test end-to-end with real Raspberry Pi hardware

---

## 🚀 Sprint 4.0 Plan: Calendar + Google Docs Intelligence

**Goal:** Enable users to ask "What's in the doc linked to my meeting?" and get intelligent summaries.

### Sprint 4.0.1: Google Docs OAuth Scope
- Add `https://www.googleapis.com/auth/documents.readonly` to Google OAuth scopes
- Single re-auth for existing users (one-time consent flow)
- No database migration needed

### Sprint 4.0.2: Google Docs Client
- Create `app/environments/google/docs/client.py`
- Implement `GoogleDocsClient` with `get_document(doc_id)` method
- Error handling: 403 (no access) → clear message, 404 (deleted) → clear message
- Parse various Google Docs URLs to extract document IDs

### Sprint 4.0.3: Calendar Extended Properties
- Add `attachments` and `conferenceData` fields to `CalendarEvent` schema
- Update `GoogleCalendarClient` to fetch these fields
- Parse Meet/Zoom links and Google Docs URLs from events

### Sprint 4.0.4: DocIntelligenceService
- Create `app/services/doc_intelligence_service.py`
- Route by document size: Gemini for <5000 chars, Claude for complex docs
- Methods: `summarize_document()`, `extract_key_points()`, `find_action_items()`

### Sprint 4.0.5: MeetingLinkService
- Create `app/services/meeting_link_service.py`
- Calendar as single source of truth for meeting links
- Extract all linked documents from a calendar event
- Handle both Meet links and attached Docs

### Sprint 4.0.6: DOC_QUERY Intent
- Add DOC_QUERY to IntentType enum
- Create `_handle_doc_query()` in IntentService
- Query types: meeting_doc (default), standalone doc by URL

### Sprint 4.0.7: Router and Parser Prompts
- Update `intent_prompts.py` with DOC_QUERY examples
- Add document context to UnifiedContext when relevant
- Train intent parser on document-related queries

### Sprint 4.0.8: E2E Test Fixtures (WOW Demo)
- Create realistic test data for demos
- Test: "What's in my 3pm meeting doc?" → Summary with action items
- Complete integration testing across all new components

---

This context file is the foundation for AI-assisted coding. It provides scope, architecture, and assumptions so future tasks can scaffold the repo (API, agent, and iOS stubs), implement minimal features, and prepare a reliable investor demo.