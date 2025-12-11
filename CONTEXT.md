# Jarvis Project Context

> **Last Updated:** December 10, 2025
> **Current Sprint:** Sprint 4 - Raspberry Pi Agent
> **Status:** ✅ Sprint 3.6 Complete - Ready for Pi Agent development

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
│   │   ├── pairing.py       # Pairing code generation/validation
│   │   ├── websocket_manager.py  # Connection manager
│   │   └── commands.py      # Command routing service
│   ├── schemas/
│   │   ├── auth.py          # Request/response schemas for auth
│   │   ├── user.py          # UserOut schema
│   │   └── device.py        # Device schemas
│   ├── ai/                   # AI Module (Sprint 3) - The Brain
│   │   ├── __init__.py      # Module exports
│   │   ├── context.py       # UnifiedContext system (Sprint 3.6)
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
│   ├── test_devices.py      # Device CRUD tests
│   ├── test_pairing.py      # Pairing service tests
│   ├── test_websocket_manager.py  # WebSocket manager tests
│   └── test_intent.py       # Intent parsing tests (Sprint 3)
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

### Next Session Tasks (Sprint 4 - Raspberry Pi Agent)
1. Create Jarvis_Stick project structure (Python)
2. Implement WebSocket client to connect to cloud
3. Pairing flow implementation
4. HDMI-CEC command execution (cec-client)
5. Command acknowledgment and status reporting
6. Local configuration and persistence
7. Test end-to-end with real Raspberry Pi hardware

---

This context file is the foundation for AI-assisted coding. It provides scope, architecture, and assumptions so future tasks can scaffold the repo (API, agent, and iOS stubs), implement minimal features, and prepare a reliable investor demo.