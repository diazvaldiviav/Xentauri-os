# Xentauri Cloud Core

> **Intelligent Screen Control System - Backend API**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.2-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Xentauri is an intelligent screen control system that lets users operate multiple display devices (TVs, monitors) via voice or text commands from their phone. This repository contains the **Cloud Core** backend that powers the entire system.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [AI System](#ai-system)
- [Google Integration](#google-integration)
- [Scene Graph System](#scene-graph-system)
- [Services](#services)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

Xentauri consists of three main components:

| Component | Description | Status |
|-----------|-------------|--------|
| **Xentauri Remote** | iOS app for voice/text commands | Planned |
| **Xentauri Cloud Core** | Backend API (this repo) | Complete |
| **Xentauri Stick** | Raspberry Pi agent for screen control | Planned |

### What Can It Do?

- **Natural Language Control**: "Turn on the living room TV", "Show my calendar"
- **Multi-Model AI**: Routes requests to the best AI model (Gemini, GPT, Claude)
- **Google Calendar Integration**: Full CRUD operations with smart search
- **Google Docs Intelligence**: Read, analyze, and create events from documents
- **Dynamic Layouts**: Scene Graph system for custom display arrangements
- **Real-Time Communication**: WebSocket connections to Raspberry Pi devices

---

## Architecture

```
                    ┌─────────────────┐
                    │   iOS App       │
                    │ (Xentauri Remote)│
                    └────────┬────────┘
                             │ REST API
                             ▼
┌────────────────────────────────────────────────────────────┐
│                   XENTAURI CLOUD CORE                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    FastAPI Server                     │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │  │
│  │  │  Auth   │  │ Devices │  │ Intent  │  │  Cloud  │ │  │
│  │  │ Router  │  │ Router  │  │ Router  │  │ Router  │ │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘ │  │
│  │       │            │            │            │       │  │
│  │       ▼            ▼            ▼            ▼       │  │
│  │  ┌─────────────────────────────────────────────────┐│  │
│  │  │              Service Layer                      ││  │
│  │  │  IntentService │ PairingService │ SceneService  ││  │
│  │  └─────────────────────────────────────────────────┘│  │
│  │       │            │            │            │       │  │
│  │       ▼            ▼            ▼            ▼       │  │
│  │  ┌─────────────────────────────────────────────────┐│  │
│  │  │                AI Module                        ││  │
│  │  │  Gemini │ OpenAI (GPT) │ Anthropic (Claude)     ││  │
│  │  └─────────────────────────────────────────────────┘│  │
│  └──────────────────────────────────────────────────────┘  │
│                             │                               │
│  ┌──────────────────────────┴───────────────────────────┐  │
│  │                    PostgreSQL                         │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                             │ WebSocket
                             ▼
                    ┌─────────────────┐
                    │  Raspberry Pi   │
                    │ (Xentauri Stick)│
                    └─────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Framework** | FastAPI 0.115.2 | High-performance async API |
| **Server** | Uvicorn 0.32.0 | ASGI server |
| **Database** | PostgreSQL 16 | Data persistence |
| **ORM** | SQLAlchemy 2.0.36 | Database abstraction |
| **Migrations** | Alembic 1.13.2 | Schema versioning |
| **Auth** | JWT (python-jose) | Token-based authentication |
| **Validation** | Pydantic 2.9.2 | Data validation |
| **AI - Router** | Gemini 2.5 Flash | Request orchestration |
| **AI - Execution** | GPT-5.2 | Code generation, tools |
| **AI - Reasoning** | Claude Opus 4.5 | Analysis, layouts |
| **Deployment** | Fly.io | Cloud hosting |

---

## Project Structure

```
Xentauri_Cloud/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── deps.py                 # Dependency injection (get_current_user)
│   │
│   ├── core/                   # Core configuration
│   │   ├── config.py           # Settings from environment variables
│   │   └── security.py         # Password hashing, JWT utilities
│   │
│   ├── db/                     # Database layer
│   │   ├── base.py             # SQLAlchemy Base class
│   │   └── session.py          # Database engine & session factory
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py             # User model
│   │   ├── device.py           # Device model
│   │   └── oauth_credential.py # OAuth token storage
│   │
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── auth.py             # Auth schemas (login, register)
│   │   ├── user.py             # User schemas
│   │   └── device.py           # Device schemas
│   │
│   ├── routers/                # API route handlers
│   │   ├── auth.py             # /auth/* endpoints
│   │   ├── users.py            # /users/* endpoints
│   │   ├── devices.py          # /devices/* endpoints
│   │   ├── commands.py         # /commands/* endpoints
│   │   ├── intent.py           # /intent endpoint (AI)
│   │   ├── google_auth.py      # /auth/google/* endpoints
│   │   ├── cloud.py            # /cloud/* content endpoints
│   │   ├── simulator.py        # /simulator display emulator
│   │   └── websocket.py        # WebSocket for Pi agents
│   │
│   ├── services/               # Business logic layer
│   │   ├── intent_service.py   # Main AI intent processing
│   │   ├── pairing.py          # Device pairing codes
│   │   ├── websocket_manager.py# WebSocket connection manager
│   │   ├── commands.py         # Command routing
│   │   ├── content_token.py    # Signed iframe tokens
│   │   ├── calendar_search_service.py  # Smart calendar search
│   │   ├── pending_event_service.py    # Pending event creation
│   │   ├── pending_edit_service.py     # Pending edit/delete
│   │   ├── doc_intelligence_service.py # Document analysis
│   │   ├── conversation_context_service.py # Conversation tracking
│   │   └── meeting_link_service.py     # Doc-meeting linking
│   │
│   ├── ai/                     # AI Module
│   │   ├── context.py          # UnifiedContext system
│   │   ├── providers/          # LLM provider clients
│   │   │   ├── base.py         # Abstract provider interface
│   │   │   ├── gemini.py       # Google Gemini client
│   │   │   ├── openai_provider.py  # OpenAI GPT client
│   │   │   └── anthropic_provider.py # Anthropic Claude client
│   │   ├── router/             # AI orchestration
│   │   │   └── orchestrator.py # Routes to appropriate model
│   │   ├── intent/             # Natural Language Understanding
│   │   │   ├── schemas.py      # Intent data structures
│   │   │   ├── parser.py       # LLM-based intent extraction
│   │   │   └── device_mapper.py# Fuzzy device name matching
│   │   ├── scene/              # Scene Graph system
│   │   │   ├── schemas.py      # SceneGraph, Component models
│   │   │   ├── registry.py     # 17 available components
│   │   │   ├── defaults.py     # 5 preset templates
│   │   │   └── service.py      # Scene generation service
│   │   ├── prompts/            # AI prompt templates
│   │   │   ├── base_prompt.py  # Shared prompt utilities
│   │   │   ├── intent_prompts.py   # Intent extraction prompts
│   │   │   ├── router_prompts.py   # Routing decision prompts
│   │   │   ├── execution_prompts.py# GPT execution prompts
│   │   │   ├── scene_prompts.py    # Scene generation prompts
│   │   │   └── doc_prompts.py      # Document analysis prompts
│   │   ├── actions/            # Action registry
│   │   │   └── registry.py     # 11 built-in actions
│   │   ├── schemas/            # AI response schemas
│   │   │   └── action_response.py # Structured GPT responses
│   │   └── monitoring/         # Observability
│   │       └── monitor.py      # Unified logging + metrics
│   │
│   └── environments/           # External service integrations
│       ├── base.py             # Abstract interfaces
│       └── google/             # Google Workspace
│           ├── auth/           # Google OAuth 2.0
│           │   ├── client.py   # OAuth flow implementation
│           │   └── schemas.py  # Scopes and auth schemas
│           ├── calendar/       # Google Calendar API
│           │   ├── client.py   # Calendar API client
│           │   ├── schemas.py  # Event schemas
│           │   └── renderer.py # HTML rendering for Pi
│           └── docs/           # Google Docs API
│               └── client.py   # Document fetching
│
├── tests/                      # Test suite (679+ tests)
├── alembic/                    # Database migrations
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container build
├── fly.toml                    # Fly.io deployment config
└── DEPLOYMENT.md               # Deployment guide
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Docker (optional, for database)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/diazvaldiviav/Xentauri-os.git
   cd Xentauri-os
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL**
   ```bash
   # Using Docker
   docker run --name xentauri-postgres \
     -e POSTGRES_USER=postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=xentauri_db \
     -p 5432:5432 \
     -d postgres:16
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

6. **Run migrations**
   ```bash
   alembic upgrade head
   ```

7. **Start the server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Access the API**
   - API Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - Health: http://localhost:8000/health

### Environment Variables

```bash
# .env file
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xentauri_db
SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# AI API Keys
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Google OAuth (from Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | No | Create new user account |
| POST | `/auth/login` | No | Login, returns JWT token |

**Example: Register**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'
```

**Example: Login**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'
```

### Users

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/users/me` | Yes | Get current user profile |

### Devices

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/devices` | Yes | Create a new device |
| GET | `/devices` | Yes | List user's devices |
| GET | `/devices/{id}` | Yes | Get device details |
| PATCH | `/devices/{id}` | Yes | Update device |
| DELETE | `/devices/{id}` | Yes | Delete device |
| POST | `/devices/{id}/pairing-code` | Yes | Generate pairing code |
| POST | `/devices/pair` | No | Pair agent with device |

### Commands

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/commands/{device_id}` | Yes | Send custom command |
| POST | `/commands/{device_id}/power/on` | Yes | Turn device on |
| POST | `/commands/{device_id}/power/off` | Yes | Turn device off |
| GET | `/commands/{device_id}/status` | Yes | Check if device is online |

### Intent (AI Processing)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/intent` | JWT | Process natural language command (iOS app) |
| POST | `/intent/agent` | X-Agent-ID | Process intent from Pi devices (agent_id auth) |
| GET | `/intent/stats` | JWT | Get AI usage statistics |

**Example: Process Intent (iOS App)**
```bash
curl -X POST http://localhost:8000/intent \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Turn on the living room TV"}'
```

**Example: Process Intent (Pi Alexa)**
```bash
curl -X POST http://localhost:8000/intent/agent \
  -H "X-Agent-ID: pi-alexa-abc123" \
  -H "Content-Type: application/json" \
  -d '{"text": "what events do I have today"}'
```

### Google OAuth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/auth/google/login` | Yes | Initiate Google OAuth flow |
| GET | `/auth/google/callback` | No | Handle OAuth callback |
| DELETE | `/auth/google` | Yes | Disconnect Google account |
| GET | `/auth/google/status` | Yes | Check connection status |

### Cloud Content

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/cloud/calendar` | Token | Rendered HTML calendar |
| GET | `/cloud/calendar/preview` | No | Demo calendar |
| GET | `/cloud/calendar/status` | Yes | Integration status |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/devices?agent_id=xxx` | Pi agent connection |

---

## AI System

### Architecture

The AI system uses a **multi-model routing architecture** where requests are analyzed and sent to the most appropriate model:

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI Router                                │
│                     (Gemini 2.5 Flash)                          │
│                                                                  │
│   Analyzes request complexity and decides routing                │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │   SIMPLE    │    │  EXECUTION  │    │  REASONING  │
   │             │    │             │    │             │
   │ Device cmds │    │ Code gen,   │    │ Analysis,   │
   │ Simple Q&A  │    │ API calls   │    │ Planning    │
   │             │    │             │    │             │
   │ Gemini Flash│    │  GPT-5.2    │    │Claude Opus  │
   └─────────────┘    └─────────────┘    └─────────────┘
```

### Intent Types

| Intent Type | Description | Example |
|-------------|-------------|---------|
| `device_command` | Control a device | "Turn on the TV" |
| `device_query` | Query device status | "Is the TV on?" |
| `calendar_query` | Search calendar | "What's on my schedule?" |
| `calendar_create` | Create event | "Schedule meeting tomorrow" |
| `calendar_edit` | Edit event | "Move dentist to 4pm" |
| `calendar_delete` | Delete event | "Cancel my gym session" |
| `doc_query` | Document operations | "Read this document" |
| `display_content` | Show on screen | "Show calendar on TV" |
| `conversation` | General chat | "Hello", "Thank you" |

### Providers

#### Gemini Provider (`app/ai/providers/gemini.py`)

Used as the **orchestrator** and for **simple tasks**:

```python
from app.ai.providers.gemini import GeminiProvider

provider = GeminiProvider()
response = await provider.generate(
    prompt="What's the weather like?",
    system_prompt="You are a helpful assistant."
)
```

#### OpenAI Provider (`app/ai/providers/openai_provider.py`)

Used for **code generation** and **complex execution**:

```python
from app.ai.providers.openai_provider import OpenAIProvider

provider = OpenAIProvider()
response = await provider.generate(
    prompt="Write a Python function to sort a list",
    system_prompt="You are an expert programmer."
)
```

#### Anthropic Provider (`app/ai/providers/anthropic_provider.py`)

Used for **reasoning** and **scene generation**:

```python
from app.ai.providers.anthropic_provider import AnthropicProvider

provider = AnthropicProvider()
response = await provider.generate_json(
    prompt="Create a dashboard layout",
    system_prompt="You are a UI designer."
)
```

---

## Google Integration

### OAuth Flow

```
┌─────────┐     ┌─────────────────┐     ┌──────────────┐
│   User  │────▶│ /auth/google    │────▶│   Google     │
│   App   │     │ /login          │     │ OAuth Screen │
└─────────┘     └─────────────────┘     └──────┬───────┘
                                               │
┌─────────────────┐     ┌─────────────────┐    │
│ OAuthCredential │◀────│ /auth/google    │◀───┘
│    (DB)         │     │ /callback       │
└─────────────────┘     └─────────────────┘
```

### Google Calendar Client

Located in `app/environments/google/calendar/client.py`:

```python
from app.environments.google.calendar.client import GoogleCalendarClient

client = GoogleCalendarClient(credentials)
events = await client.get_events(
    start_date="2025-01-01",
    end_date="2025-01-31"
)
```

**Features:**
- List events (today, week, custom range)
- Create events
- Update events
- Delete events
- Smart search with LLM

### Google Docs Client

Located in `app/environments/google/docs/client.py`:

```python
from app.environments.google.docs.client import GoogleDocsClient

client = GoogleDocsClient(credentials)
document = await client.get_document(doc_id="your-doc-id")
```

**Features:**
- Read document content
- Extract meeting details via AI
- Create calendar events from documents

---

## Scene Graph System

The Scene Graph system creates dynamic display layouts for Raspberry Pi screens.

### Architecture

```
┌─────────────────┐
│  User Request   │  "Calendar on the left with clock"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Scene Service   │  Normalizes layout hints
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Claude/Default  │  Generates layout
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Populate Data   │  Fetches calendar, weather, etc.
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Scene Graph    │  JSON sent to Pi
└─────────────────┘
```

### Layout Types

| Type | Description | Use Case |
|------|-------------|----------|
| `fullscreen` | Single component | Calendar only |
| `sidebar` | Main + sidebar (70/30) | Calendar + clock |
| `dashboard` | 2x2 grid | Multiple widgets |
| `agenda` | Agenda list | Event list |
| `clock` | Large clock | Time display |

### Available Components (17 total)

**Calendar (5):**
- `calendar_day` - Single day view
- `calendar_week` - Week view
- `calendar_month` - Month grid
- `calendar_widget` - Compact widget
- `calendar_agenda` - Agenda list

**Time (2):**
- `clock_digital` - Digital clock
- `clock_analog` - Analog clock face

**Weather (1):**
- `weather_current` - Current conditions

**Document (2):**
- `doc_summary` - Document summary
- `doc_preview` - Document preview

**Utility (7):**
- `text_block` - Rich text content
- `spacer` - Empty space
- `image_display` - Image display
- `web_embed` - Web content iframe
- `meeting_detail` - Meeting info
- `countdown_timer` - Countdown
- `event_countdown` - Next event countdown

### Example Scene Graph

```json
{
  "layout": {
    "intent": "sidebar",
    "engine": "grid",
    "columns": "70% 30%"
  },
  "components": [
    {
      "id": "main-calendar",
      "type": "calendar_week",
      "position": {"grid_area": "1 / 1 / 2 / 2"},
      "data": {
        "events": [...],
        "is_placeholder": false
      }
    },
    {
      "id": "sidebar-clock",
      "type": "clock_digital",
      "position": {"grid_area": "1 / 2 / 2 / 3"},
      "data": {
        "format": "24h",
        "timezone": "America/New_York"
      }
    }
  ]
}
```

---

## Services

### IntentService (`app/services/intent_service.py`)

The main service that processes natural language commands:

```python
from app.services.intent_service import IntentService

service = IntentService(db_session)
result = await service.process(
    text="Turn on the living room TV",
    user_id=user.id
)
```

### PairingService (`app/services/pairing.py`)

Manages 6-character pairing codes with 15-minute TTL:

```python
from app.services.pairing import PairingService

service = PairingService()
code, expires_at = service.generate_code(device_id)
device_id = service.consume_code(code)  # One-time use
```

### WebSocketManager (`app/services/websocket_manager.py`)

Manages WebSocket connections to Pi agents:

```python
from app.services.websocket_manager import connection_manager

await connection_manager.connect(device_id, websocket)
await connection_manager.send_command(device_id, "power_on", {})
```

### CalendarSearchService (`app/services/calendar_search_service.py`)

LLM-powered semantic calendar search:

```python
from app.services.calendar_search_service import CalendarSearchService

service = CalendarSearchService(db_session)
result = await service.smart_search(
    query="dentist appt",  # Handles typos!
    user_id=user.id
)
# Returns: {"events": [...], "corrected_query": "Dentist Appointment"}
```

### SceneService (`app/ai/scene/service.py`)

Generates dynamic display layouts:

```python
from app.ai.scene.service import SceneService

service = SceneService(db_session)
scene = await service.generate_scene(
    layout_hints=["calendar", "left", "clock"],
    info_type="calendar",
    user_id=user.id
)
```

---

## Testing

The project has 679+ tests covering all functionality.

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_intent_service.py
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

### Test Categories

| File | Tests | Description |
|------|-------|-------------|
| `test_intent_service.py` | 32 | Intent processing |
| `test_action_response.py` | 47 | AI response schemas |
| `test_device_mapper.py` | 42 | Fuzzy name matching |
| `test_action_registry.py` | 37 | Action definitions |
| `test_ai_router.py` | 29 | AI orchestration |
| `test_intent_parser.py` | 33 | Parser edge cases |
| `test_scene_graph.py` | 31 | Scene graph system |
| `test_calendar_*.py` | 50+ | Calendar operations |

---

## Deployment

### Fly.io Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete instructions.

**Quick Deploy:**

```bash
# Login to Fly.io
fly auth login

# Create PostgreSQL database
fly postgres create --name xentauri-db --region iad

# Create and deploy app
fly apps create xentauri-cloud-core
fly deploy

# Attach database
fly postgres attach xentauri-db --app xentauri-cloud-core

# Set secrets
fly secrets set \
  DATABASE_URL="postgresql+psycopg://..." \
  SECRET_KEY="your-secret-key" \
  GEMINI_API_KEY="..." \
  OPENAI_API_KEY="..." \
  ANTHROPIC_API_KEY="..." \
  --app xentauri-cloud-core
```

### Production URLs

- **API:** https://xentauri-cloud-core.fly.dev
- **Docs:** https://xentauri-cloud-core.fly.dev/docs
- **Health:** https://xentauri-cloud-core.fly.dev/health

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Use Python type hints
- Follow PEP 8 guidelines
- Write docstrings for public functions
- Add tests for new features

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com) - Modern, fast web framework
- [SQLAlchemy](https://sqlalchemy.org) - SQL toolkit and ORM
- [Pydantic](https://pydantic-docs.helpmanual.io) - Data validation
- [Google APIs](https://developers.google.com) - Calendar and Docs integration
- [OpenAI](https://openai.com) - GPT models
- [Anthropic](https://anthropic.com) - Claude models
- [Google AI](https://ai.google.dev) - Gemini models

---

*Built with passion by the Xentauri team*
