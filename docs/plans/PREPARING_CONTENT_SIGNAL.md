# Preparing Content Signal - Technical Plan

> **Status:** PLANNED
> **Created:** January 7, 2026
> **Sprint:** 5.3.0 (Proposed)
> **Priority:** Medium - UX Enhancement

## Overview

Implementar una señal simple `preparing_content` que notifica al dispositivo (Pi/Simulator) que se está generando contenido. Esto permite mostrar una pantalla de entretenimiento/loading mientras el backend procesa la solicitud.

---

## Problem Statement

Actualmente cuando un usuario solicita contenido ("Muestra la tabla del 7"):
1. El backend tarda 2-5 minutos generando el scene + custom layout
2. Durante ese tiempo, la pantalla del Pi/Simulator no muestra nada
3. El usuario no sabe si el sistema está procesando o si falló

**Solución:** Enviar una señal inmediata al dispositivo antes de empezar la generación.

---

## Proposed Solution

### Flujo Simple

```
Usuario: "Muestra la tabla del 7"
              │
              ▼
       IntentService._handle_display_content()
              │
              ▼
    ┌─────────────────────────────────────────┐
    │  command_service.preparing_content()    │  ← NUEVO (inmediato)
    └─────────────────────────────────────────┘
              │
              ▼ WebSocket: { "command_type": "preparing_content" }
              │
              ▼ Pi/Simulator: Inicia animación de loading
              │
    ┌─────────────────────────────────────────┐
    │  scene_service.generate_scene()         │
    │  custom_layout_service.generate_html()  │  (2-5 segundos)
    └─────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────┐
    │  command_service.display_scene()        │
    └─────────────────────────────────────────┘
              │
              ▼ WebSocket: { "command_type": "display_scene", ... }
              │
              ▼ Pi/Simulator: Detiene loading, muestra contenido
```

---

## Message Structure

### Preparing Content Signal

```json
{
  "type": "command",
  "command_type": "preparing_content",
  "command_id": "uuid",
  "parameters": {},
  "timestamp": "2026-01-07T10:30:00Z"
}
```

**Nota:** Sin parámetros adicionales. El dispositivo solo necesita saber que debe mostrar loading. La animación puede durar hasta 5 minutos (timeout de seguridad) hasta recibir `display_scene`.

---

## Implementation Plan

### Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `app/services/commands.py` | Add `PREPARING_CONTENT` CommandType | After line 45 |
| `app/services/commands.py` | Add `preparing_content()` method | After line 203 |
| `app/services/intent_service.py` | Send signal before scene generation | Line 5979 |
| `app/routers/simulator.py` | Handle `preparing_content` in JavaScript | Line 545 |

---

## Step 1: Add CommandType

**File:** `app/services/commands.py`

**Location:** After line 45 (after `DISPLAY_SCENE`)

```python
class CommandType:
    """Supported command types for device control."""
    POWER_ON = "power_on"
    POWER_OFF = "power_off"
    SET_INPUT = "set_input"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    MUTE = "mute"
    UNMUTE = "unmute"

    # Content display commands (Sprint 3.5)
    SHOW_CONTENT = "show_content"
    CLEAR_CONTENT = "clear_content"

    # Scene graph display (Sprint 4.0)
    DISPLAY_SCENE = "display_scene"

    # Loading state (Sprint 5.3) - NEW
    PREPARING_CONTENT = "preparing_content"
```

---

## Step 2: Add Helper Method

**File:** `app/services/commands.py`

**Location:** After line 203 (after `clear_content()` method)

```python
async def preparing_content(self, device_id: UUID) -> CommandResult:
    """
    Signal that content is being prepared/generated.

    Sprint 5.3: Sent before scene generation to allow device
    to show a loading/entertainment screen while waiting.

    The device should show loading until it receives:
    - display_scene (content ready)
    - clear_content (cancelled)
    - power_off (device off)

    Args:
        device_id: Target device UUID

    Returns:
        CommandResult with success status
    """
    return await self.send_command(device_id, CommandType.PREPARING_CONTENT)
```

---

## Step 3: Send Signal in Intent Service

**File:** `app/services/intent_service.py`

**Location:** Line 5979 (BEFORE scene generation, AFTER device resolution)

**Current code (lines 5978-5980):**
```python
# Generate scene via SceneService (now with real-time data AND conversation context)
logger.info(f"[{request_id}] Generating scene with {len(normalized_hints)} layout hints")
scene = await scene_service.generate_scene(
```

**New code:**
```python
# Sprint 5.3: Notify device that content is being prepared
# This allows the device to show a loading/entertainment screen
logger.info(f"[{request_id}] Sending preparing_content signal to {target_device.name}")
try:
    await command_service.preparing_content(device_id=target_device.id)
except Exception as e:
    # Non-critical - continue even if signal fails
    logger.warning(f"[{request_id}] Failed to send preparing_content signal: {e}")

# Generate scene via SceneService (now with real-time data AND conversation context)
logger.info(f"[{request_id}] Generating scene with {len(normalized_hints)} layout hints")
scene = await scene_service.generate_scene(
```

---

## Step 4: Handle in Simulator

**File:** `app/routers/simulator.py`

**Location:** Line 545 (inside `handleCommand()` switch statement)

**Current code:**
```javascript
function handleCommand(data) {
    switch (data.command_type) {
        case 'show_content':
            // ...
```

**Add new case (before `show_content`):**
```javascript
function handleCommand(data) {
    switch (data.command_type) {
        case 'preparing_content':
            log('Preparing content - showing loading screen', 'info');
            showPreparingScreen();
            sendAck(data.command_id, 'completed');
            break;

        case 'show_content':
            // ... existing code
```

**Add `showPreparingScreen()` function (after `showIdleScreen()`):**
```javascript
function showPreparingScreen() {
    // Clear any existing content
    contentFrame.innerHTML = '';

    // Show loading animation
    contentFrame.innerHTML = `
        <div style="
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
            color: #ffffff;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        ">
            <div style="
                width: 60px;
                height: 60px;
                border: 4px solid rgba(123, 44, 191, 0.3);
                border-top-color: #7b2cbf;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            "></div>
            <div style="
                margin-top: 24px;
                font-size: 24px;
                font-weight: 500;
                opacity: 0.9;
            ">Preparando contenido...</div>
            <div style="
                margin-top: 8px;
                font-size: 14px;
                opacity: 0.6;
            ">Tu contenido estará listo en unos segundos</div>
        </div>
        <style>
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        </style>
    `;

    currentContent = 'preparing';
}
```

**Modify `display_scene` case to clear loading:**
```javascript
case 'display_scene':
    // Scene is ready - this automatically replaces the loading screen
    const scene = data.parameters?.scene;
    const customLayout = data.parameters?.custom_layout;

    if (customLayout) {
        log('Rendering custom HTML layout', 'info');
        renderCustomLayout(customLayout);
    } else if (scene) {
        log('Rendering scene graph', 'info');
        renderScene(scene);
    }
    sendAck(data.command_id, 'completed');
    break;
```

---

## Raspberry Pi Agent (Future)

Cuando se implemente el agente del Pi, deberá manejar `preparing_content` de manera similar:

```python
# pi_agent/handlers/command_handler.py

async def handle_command(command: dict):
    command_type = command.get("command_type")

    if command_type == "preparing_content":
        # Show loading screen in Chromium
        await browser.load_page("file:///opt/xentauri/loading.html")
        return {"status": "completed"}

    elif command_type == "display_scene":
        # Render scene (replaces loading)
        await render_scene(command["parameters"])
        return {"status": "completed"}
```

---

## Timeout Handling

El dispositivo debe tener un timeout de seguridad:

```javascript
let preparingTimeout = null;

function showPreparingScreen() {
    // ... show loading UI ...

    // Safety timeout: 5 minutes max
    preparingTimeout = setTimeout(() => {
        log('Preparing content timeout - showing idle screen', 'warning');
        showIdleScreen();
    }, 5 * 60 * 1000);  // 5 minutes
}

// Clear timeout when content arrives
case 'display_scene':
    if (preparingTimeout) {
        clearTimeout(preparingTimeout);
        preparingTimeout = null;
    }
    // ... render scene ...
```

---

## Testing Checklist

### Unit Tests
- [ ] `CommandType.PREPARING_CONTENT` exists
- [ ] `command_service.preparing_content()` returns `CommandResult`
- [ ] Signal is sent before scene generation

### Integration Tests
- [ ] WebSocket message sent with correct format
- [ ] Simulator shows loading screen on `preparing_content`
- [ ] Simulator replaces loading with content on `display_scene`
- [ ] Timeout works (show idle after 5 min)

### Manual Tests
- [ ] Request "Muestra el calendario" → See loading → See calendar
- [ ] Request complex layout → Loading visible during generation
- [ ] Disconnect during loading → Reconnect shows idle

---

## Message Flow Summary

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  User    │         │  Backend │         │  Device  │
└────┬─────┘         └────┬─────┘         └────┬─────┘
     │                    │                    │
     │ "Show calendar"    │                    │
     │───────────────────>│                    │
     │                    │                    │
     │                    │ preparing_content  │
     │                    │───────────────────>│
     │                    │                    │ Show loading
     │                    │                    │
     │                    │ [Generating...]    │
     │                    │ (2-5 seconds)      │
     │                    │                    │
     │                    │ display_scene      │
     │                    │───────────────────>│
     │                    │                    │ Show content
     │                    │                    │
```

---

## Rollback Plan

Si hay problemas, el rollback es simple:

1. Remover la llamada a `preparing_content()` en `intent_service.py`
2. El sistema funciona exactamente como antes
3. No hay dependencias ni cambios breaking

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Signal latency | < 100ms (inmediato) |
| Loading visible | 100% de requests de contenido |
| User feedback | "Sistema se siente más responsivo" |

---

## Dependencies

- Ninguna dependencia nueva
- Usa infraestructura existente de WebSocket
- Usa patrón existente de CommandType

---

## References

- [commands.py](../../app/services/commands.py) - Command service
- [intent_service.py](../../app/services/intent_service.py) - Intent handler
- [simulator.py](../../app/routers/simulator.py) - Simulator frontend
- [websocket_manager.py](../../app/services/websocket_manager.py) - WebSocket transmission

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-07 | Initial plan created |
