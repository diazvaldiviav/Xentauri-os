# Jarvis Project Context

> **Last Updated:** December 2, 2025  
> **Current Sprint:** Sprint 2 - WebSocket Hub + Device Management  
> **Status:** ✅ Device CRUD, pairing, WebSocket hub, and command routing implemented

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

### Sprint 3: Raspberry Pi Agent (Next)
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
│   │   ├── config.py        # Settings from .env
│   │   └── security.py      # Password hashing, JWT creation
│   ├── db/
│   │   ├── base.py          # SQLAlchemy Base class
│   │   └── session.py       # Database engine & session
│   ├── models/
│   │   ├── user.py          # User ORM model
│   │   └── device.py        # Device ORM model
│   ├── routers/
│   │   ├── auth.py          # /auth/register, /auth/login
│   │   ├── users.py         # /users/me
│   │   ├── devices.py       # Device CRUD + pairing
│   │   ├── commands.py      # Send commands to devices
│   │   └── websocket.py     # WebSocket for Pi agents
│   ├── services/
│   │   ├── pairing.py       # Pairing code generation/validation
│   │   ├── websocket_manager.py  # Connection manager
│   │   └── commands.py      # Command routing service
│   └── schemas/
│       ├── auth.py          # Request/response schemas for auth
│       ├── user.py          # UserOut schema
│       └── device.py        # Device schemas
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_devices.py      # Device CRUD tests
│   ├── test_pairing.py      # Pairing service tests
│   └── test_websocket_manager.py  # WebSocket manager tests
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
| Testing | Pytest | 8.3.3 |
| Deployment | Fly.io | - |

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
```

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

### Next Session Tasks
1. Install test dependencies: `pip install pytest pytest-asyncio`
2. Run tests: `python -m pytest tests/ -v`
3. Deploy to Fly.io
4. Start Sprint 3: Raspberry Pi Agent

---

This context file is the foundation for AI-assisted coding. It provides scope, architecture, and assumptions so future tasks can scaffold the repo (API, agent, and iOS stubs), implement minimal features, and prepare a reliable investor demo.