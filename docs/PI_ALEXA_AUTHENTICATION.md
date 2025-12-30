# Pi Alexa Authentication Implementation Plan

## Overview

This document describes the plan to add `agent_id` authentication to the `/intent` system, allowing the "Pi Alexa" device (voice input Raspberry Pi) to send natural language commands without requiring JWT tokens.

**Status:** Planned (Not Implemented)
**Sprint:** TBD
**Priority:** High

---

## Problem Statement

Currently, the `/intent` endpoint only accepts JWT authentication (designed for iOS app). The Pi Alexa device needs to send voice commands but doesn't have a way to obtain JWT tokens like a mobile app does.

| Device | Purpose | Current Auth | Can Use `/intent`? |
|--------|---------|--------------|-------------------|
| iOS App | Mobile interface | JWT | ✅ Yes |
| Pi Pantalla | Display output | agent_id | N/A (uses WebSocket) |
| Pi Alexa | Voice input | agent_id | ❌ No (needs JWT) |

---

## Solution: New Endpoint `/intent/agent`

Create a dedicated endpoint for Pi devices that authenticates via `agent_id` instead of JWT.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION LAYER                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  iOS App ──── JWT ────► /intent ─────┐                          │
│                                      │                          │
│                                      ▼                          │
│                              ┌──────────────┐                   │
│                              │ IntentService │ ◄── Same logic   │
│                              │   .process()  │     for both     │
│                              └──────────────┘                   │
│                                      ▲                          │
│                                      │                          │
│  Pi Alexa ── agent_id ──► /intent/agent ──┘                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Points

1. **Same Business Logic**: Both endpoints call `intent_service.process()`
2. **Different Authentication**: JWT vs agent_id
3. **Same Response Format**: `IntentResponse` schema
4. **No Breaking Changes**: Existing `/intent` endpoint unchanged

---

## Implementation Details

### Files to Modify

| File | Change | Risk |
|------|--------|------|
| `app/routers/intent.py` | Add new endpoint `/intent/agent` | Low - additive only |
| `app/deps.py` | Add `get_user_from_agent()` dependency | Low - new function |

### Files NOT Modified (Reused As-Is)

| File | Purpose |
|------|---------|
| `app/services/intent_service.py` | All business logic (parsing, AI, execution) |
| `app/ai/intent/parser.py` | Intent parsing with Gemini |
| `app/ai/router/orchestrator.py` | Complexity routing |
| `app/services/commands.py` | Device command execution |

---

## Step-by-Step Implementation

### Step 1: Add Agent Validation Dependency

**File:** `app/deps.py`

```python
from fastapi import Header, HTTPException
from app.models.device import Device
from app.models.user import User

async def get_user_from_agent(
    x_agent_id: str = Header(..., alias="X-Agent-ID"),
    db: Session = Depends(get_db),
) -> User:
    """
    Get user from agent_id header.

    Used by Pi devices that authenticate via agent_id instead of JWT.
    The agent_id must be linked to a device, which is linked to a user.

    Chain: agent_id → Device → User
    """
    # Find device by agent_id
    device = db.query(Device).filter(Device.agent_id == x_agent_id).first()

    if not device:
        raise HTTPException(
            status_code=401,
            detail="Agent not paired. Use the pairing flow first."
        )

    # Get the device owner
    user = db.query(User).filter(User.id == device.user_id).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found for this agent."
        )

    return user
```

### Step 2: Add New Endpoint

**File:** `app/routers/intent.py`

```python
from app.deps import get_user_from_agent

@router.post("/agent", response_model=IntentResponse)
async def process_intent_agent(
    request: IntentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_agent),  # ← agent_id auth
):
    """
    Process natural language intent from Pi Alexa device.

    This endpoint is identical to POST /intent but authenticates
    via X-Agent-ID header instead of JWT Bearer token.

    Authentication:
    - Header: X-Agent-ID: <agent_id>
    - The agent_id must be paired to a device owned by the user

    Example:
        curl -X POST https://api.xentauri.com/intent/agent \
          -H "X-Agent-ID: pi-alexa-abc123" \
          -H "Content-Type: application/json" \
          -d '{"text": "what events do I have today"}'
    """
    # Exact same logic as /intent endpoint
    result = await intent_service.process(
        text=request.text,
        user_id=current_user.id,
        db=db,
        device_id=request.device_id,
    )

    return IntentResponse(
        success=result.success,
        intent_type=result.intent_type.value,
        confidence=result.confidence,
        device=DeviceInfo(...) if result.device else None,
        action=result.action,
        parameters=result.parameters,
        command_sent=result.command_sent,
        command_id=result.command_id,
        message=result.message,
        response=result.response,
        processing_time_ms=result.processing_time_ms,
        request_id=result.request_id,
    )
```

---

## API Specification

### Endpoint

```
POST /intent/agent
```

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Agent-ID` | Yes | The agent_id of the paired Pi device |
| `Content-Type` | Yes | `application/json` |

### Request Body

Same as `/intent`:

```json
{
  "text": "what events do I have today",
  "device_id": null
}
```

### Response

Same as `/intent`:

```json
{
  "success": true,
  "intent_type": "calendar_query",
  "confidence": 0.95,
  "device": null,
  "action": "count_events",
  "parameters": {
    "date_range": "today"
  },
  "command_sent": false,
  "command_id": null,
  "message": "Tienes 3 eventos para hoy.",
  "response": "Tienes 3 eventos para hoy.",
  "processing_time_ms": 245.3,
  "request_id": "abc123-def456"
}
```

### Error Responses

| Status | Reason | Response |
|--------|--------|----------|
| 401 | Missing X-Agent-ID header | `{"detail": "X-Agent-ID header required"}` |
| 401 | Agent not paired | `{"detail": "Agent not paired. Use the pairing flow first."}` |
| 401 | User not found | `{"detail": "User not found for this agent."}` |

---

## Pi Alexa Client Implementation

### Python Example

```python
import httpx

CLOUD_URL = "https://xentauri-cloud-core.fly.dev"
AGENT_ID = "pi-alexa-abc123"  # From pairing process

async def send_voice_command(text: str) -> dict:
    """Send voice command to Xentauri Cloud."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{CLOUD_URL}/intent/agent",
            headers={
                "X-Agent-ID": AGENT_ID,
                "Content-Type": "application/json",
            },
            json={"text": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

# Usage
result = await send_voice_command("muestra mi calendario en la pantalla")
print(result["message"])  # "Mostrando calendario en Pantalla Sala"
```

### Bash/cURL Example

```bash
curl -X POST "https://xentauri-cloud-core.fly.dev/intent/agent" \
  -H "X-Agent-ID: pi-alexa-abc123" \
  -H "Content-Type: application/json" \
  -d '{"text": "qué eventos tengo mañana"}'
```

---

## Security Considerations

### Agent ID Security

| Aspect | Implementation |
|--------|----------------|
| **Uniqueness** | UUID v4, cryptographically random |
| **Storage** | Stored on Pi device, never exposed publicly |
| **Revocation** | User can unpair device via iOS app |
| **Rotation** | Can be regenerated by re-pairing |

### Network Security

| Aspect | Implementation |
|--------|----------------|
| **Transport** | HTTPS only (TLS 1.3) |
| **Header** | X-Agent-ID in header, not URL |
| **Rate Limiting** | Same limits as /intent |

### Attack Vectors Mitigated

| Attack | Mitigation |
|--------|------------|
| Agent ID guessing | UUID v4 = 2^122 possibilities |
| Replay attacks | HTTPS prevents interception |
| Unauthorized access | Agent must be paired first |
| Brute force | Rate limiting on endpoint |

---

## Testing Plan

### Unit Tests

```python
# tests/test_intent_agent.py

async def test_intent_agent_valid():
    """Test valid agent_id authentication."""
    response = client.post(
        "/intent/agent",
        headers={"X-Agent-ID": paired_agent_id},
        json={"text": "what time is it"},
    )
    assert response.status_code == 200
    assert response.json()["success"] == True

async def test_intent_agent_missing_header():
    """Test missing X-Agent-ID header."""
    response = client.post(
        "/intent/agent",
        json={"text": "hello"},
    )
    assert response.status_code == 422  # Validation error

async def test_intent_agent_invalid_agent():
    """Test invalid/unpaired agent_id."""
    response = client.post(
        "/intent/agent",
        headers={"X-Agent-ID": "invalid-agent-id"},
        json={"text": "hello"},
    )
    assert response.status_code == 401
    assert "not paired" in response.json()["detail"]

async def test_intent_agent_same_logic():
    """Test that /intent/agent returns same results as /intent."""
    text = "how many events today"

    # Call via JWT
    jwt_response = client.post(
        "/intent",
        headers={"Authorization": f"Bearer {user_jwt}"},
        json={"text": text},
    )

    # Call via agent_id (same user)
    agent_response = client.post(
        "/intent/agent",
        headers={"X-Agent-ID": user_agent_id},
        json={"text": text},
    )

    # Results should be equivalent
    assert jwt_response.json()["intent_type"] == agent_response.json()["intent_type"]
    assert jwt_response.json()["action"] == agent_response.json()["action"]
```

### Integration Tests

1. **Pairing Flow**: Pair Pi device → Get agent_id → Use /intent/agent
2. **Full Voice Flow**: Voice → Text → /intent/agent → Response → TTS
3. **Cross-Device**: Pi Alexa command → Pi Pantalla display

---

## Rollout Plan

### Phase 1: Development
- [ ] Implement `get_user_from_agent()` in deps.py
- [ ] Add `/intent/agent` endpoint in intent.py
- [ ] Write unit tests
- [ ] Local testing with mock Pi

### Phase 2: Staging
- [ ] Deploy to staging environment
- [ ] Test with real Pi Alexa device
- [ ] Verify logging and monitoring
- [ ] Security review

### Phase 3: Production
- [ ] Deploy to production
- [ ] Monitor error rates
- [ ] Update Pi Alexa firmware/software
- [ ] Documentation for users

---

## Monitoring

### Metrics to Track

| Metric | Purpose |
|--------|---------|
| `/intent/agent` request count | Usage volume |
| `/intent/agent` error rate | Reliability |
| `/intent/agent` latency p95 | Performance |
| Auth failures by agent_id | Security (detect attacks) |

### Logging

```python
logger.info(
    f"[INTENT_AGENT] agent_id={agent_id[:8]}..., "
    f"user_id={user.id}, text={text[:50]}..."
)
```

---

## FAQ

### Why not modify `/intent` to accept both JWT and agent_id?

Option A (dual auth) was considered but rejected for:
1. **Separation of concerns**: Mobile vs IoT have different needs
2. **Zero risk**: No changes to existing endpoint
3. **Clearer API**: Explicit endpoint for Pi devices
4. **Easier debugging**: Know which auth method was used

### Can Pi Pantalla use `/intent/agent`?

Yes, but it's not needed. Pi Pantalla:
- Receives commands via WebSocket (already uses agent_id)
- Doesn't send voice commands
- Only displays content

### What if agent_id is compromised?

User can unpair the device from iOS app, which:
1. Removes agent_id from device record
2. Invalidates the agent_id immediately
3. Pi device stops working until re-paired

---

## Related Documentation

- [DEPLOYMENT.md](../DEPLOYMENT.md) - Fly.io deployment
- [README.md](../README.md) - Project overview
- [Device Pairing Flow](../app/routers/devices.py) - How pairing works

---

*Document created: December 29, 2025*
*Last updated: December 29, 2025*
