"""
Display Simulator Router - Simulates a Raspberry Pi display for development.

This module provides a web-based display simulator that:
- Acts as a virtual Raspberry Pi screen
- Connects via WebSocket (same as real Pi)
- Receives SHOW_CONTENT commands
- Displays content in an iframe

Usage:
======
1. Open http://localhost:8000/simulator in a browser window
2. Keep it visible (this is your "TV screen")
3. Use the API or iOS app to send commands
4. The simulator displays content automatically

This is a development tool that mirrors real Pi behavior without hardware.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import HTMLResponse

from app.services.websocket_manager import connection_manager
from app.db.session import SessionLocal
from app.models.device import Device


logger = logging.getLogger("jarvis.simulator")


# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/simulator", tags=["simulator"])


# ---------------------------------------------------------------------------
# SIMULATOR HTML PAGE
# ---------------------------------------------------------------------------

def get_simulator_html(device_id: str, device_name: str, ws_url: str) -> str:
    """
    Generate the simulator HTML page.
    
    This page:
    - Connects to WebSocket as if it were a Pi agent
    - Listens for SHOW_CONTENT commands
    - Displays content in a full-screen iframe
    - Shows connection status
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jarvis Display Simulator - {device_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            height: 100vh;
            overflow: hidden;
        }}
        
        /* Status bar at top */
        .status-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 40px;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 1rem;
            z-index: 1000;
            border-bottom: 1px solid #333;
        }}
        
        .status-bar.hidden {{
            transform: translateY(-100%);
            transition: transform 0.3s ease;
        }}
        
        .status-bar:hover {{
            transform: translateY(0);
        }}
        
        .device-info {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .device-name {{
            font-weight: 600;
            color: #4a90d9;
        }}
        
        .connection-status {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .status-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ef5350;
        }}
        
        .status-dot.connected {{
            background: #4caf50;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        /* Content area */
        .content-frame {{
            position: fixed;
            top: 40px;
            left: 0;
            right: 0;
            bottom: 0;
            background: #1a1a1a;
        }}
        
        .content-frame iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        
        /* Idle screen */
        .idle-screen {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            padding: 2rem;
        }}
        
        .idle-screen h1 {{
            font-size: 3rem;
            color: #4a90d9;
            margin-bottom: 1rem;
        }}
        
        .idle-screen p {{
            color: #888;
            font-size: 1.2rem;
            margin-bottom: 0.5rem;
        }}
        
        .idle-screen .waiting {{
            margin-top: 2rem;
            color: #666;
        }}
        
        .idle-screen .command-hint {{
            margin-top: 1rem;
            padding: 1rem;
            background: #222;
            border-radius: 8px;
            font-family: monospace;
            color: #4a90d9;
        }}
        
        /* Log panel */
        .log-panel {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            max-height: 150px;
            background: rgba(0, 0, 0, 0.9);
            border-top: 1px solid #333;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            padding: 0.5rem;
            z-index: 1000;
            display: none;
        }}
        
        .log-panel.visible {{
            display: block;
        }}
        
        .log-entry {{
            padding: 2px 0;
            color: #888;
        }}
        
        .log-entry.info {{ color: #4a90d9; }}
        .log-entry.success {{ color: #4caf50; }}
        .log-entry.error {{ color: #ef5350; }}
        .log-entry.command {{ color: #ffa726; }}
    </style>
</head>
<body>
    <!-- Status Bar -->
    <div class="status-bar" id="statusBar">
        <div class="device-info">
            <span>📺</span>
            <span class="device-name">{device_name}</span>
            <span style="color: #666">| Simulator</span>
        </div>
        <div class="connection-status">
            <span id="statusText">Connecting...</span>
            <div class="status-dot" id="statusDot"></div>
        </div>
    </div>
    
    <!-- Content Frame -->
    <div class="content-frame" id="contentFrame">
        <div class="idle-screen" id="idleScreen">
            <h1>🖥️ Jarvis Display</h1>
            <p>Device: <strong>{device_name}</strong></p>
            <p>ID: <code>{device_id[:8]}...</code></p>
            <p class="waiting">Waiting for commands...</p>
            <div class="command-hint">
                Try: "Show the calendar on {device_name}"
            </div>
        </div>
    </div>
    
    <!-- Log Panel (toggle with 'L' key) -->
    <div class="log-panel" id="logPanel"></div>
    
    <script>
        // Configuration
        const DEVICE_ID = "{device_id}";
        const DEVICE_NAME = "{device_name}";
        const WS_URL = "{ws_url}";
        
        // DOM elements
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const contentFrame = document.getElementById('contentFrame');
        const idleScreen = document.getElementById('idleScreen');
        const logPanel = document.getElementById('logPanel');
        
        // WebSocket connection
        let ws = null;
        let reconnectAttempts = 0;
        const MAX_RECONNECT_ATTEMPTS = 10;
        const RECONNECT_DELAY = 3000;
        
        // Logging
        function log(message, type = 'info') {{
            const entry = document.createElement('div');
            entry.className = `log-entry ${{type}}`;
            entry.textContent = `[${{new Date().toLocaleTimeString()}}] ${{message}}`;
            logPanel.appendChild(entry);
            logPanel.scrollTop = logPanel.scrollHeight;
            console.log(`[${{type.toUpperCase()}}] ${{message}}`);
        }}
        
        // Update connection status
        function setConnected(connected) {{
            if (connected) {{
                statusDot.classList.add('connected');
                statusText.textContent = 'Connected';
                log('Connected to Jarvis Cloud', 'success');
            }} else {{
                statusDot.classList.remove('connected');
                statusText.textContent = 'Disconnected';
            }}
        }}
        
        // Storage key for persisting content state
        const STORAGE_KEY = `jarvis_simulator_${{DEVICE_ID}}`;
        
        // Save current content state to localStorage
        function saveContentState(url, contentType) {{
            const state = {{ url, contentType, timestamp: Date.now() }};
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }}
        
        // Clear saved content state
        function clearContentState() {{
            localStorage.removeItem(STORAGE_KEY);
        }}
        
        // Restore content state from localStorage
        function restoreContentState() {{
            try {{
                const saved = localStorage.getItem(STORAGE_KEY);
                if (saved) {{
                    const state = JSON.parse(saved);
                    // Only restore if saved within last hour
                    const ageMinutes = (Date.now() - state.timestamp) / 1000 / 60;
                    if (ageMinutes < 60 && state.url) {{
                        log(`Restoring previous content (saved ${{Math.round(ageMinutes)}} min ago)`, 'info');
                        showContent(state.url, state.contentType, false);
                        return true;
                    }}
                }}
            }} catch (e) {{
                log(`Failed to restore state: ${{e.message}}`, 'error');
            }}
            return false;
        }}
        
        // Show content in iframe
        function showContent(url, contentType, persist = true) {{
            log(`Showing content: ${{contentType}} - ${{url}}`, 'command');
            
            // Save state for restoration after refresh
            if (persist) {{
                saveContentState(url, contentType);
            }}
            
            // Create or reuse iframe
            let iframe = contentFrame.querySelector('iframe');
            if (!iframe) {{
                iframe = document.createElement('iframe');
                contentFrame.innerHTML = '';
                contentFrame.appendChild(iframe);
            }}
            
            // Handle relative URLs
            if (url.startsWith('/')) {{
                url = window.location.origin + url;
            }}
            
            iframe.src = url;
            idleScreen.style.display = 'none';
        }}
        
        // Clear content
        function clearContent() {{
            log('Clearing content', 'command');
            clearContentState();
            contentFrame.innerHTML = '';
            contentFrame.appendChild(idleScreen);
            idleScreen.style.display = 'flex';
        }}
        
        // Handle incoming command
        function handleCommand(data) {{
            log(`Received command: ${{data.command_type}}`, 'command');
            
            switch (data.command_type) {{
                case 'show_content':
                    const url = data.parameters?.url || '/cloud/calendar';
                    const contentType = data.parameters?.content_type || 'url';
                    showContent(url, contentType);
                    sendAck(data.command_id, 'completed');
                    break;
                    
                case 'clear_content':
                    clearContent();
                    sendAck(data.command_id, 'completed');
                    break;
                    
                case 'power_off':
                    log('Power off received - showing idle screen', 'info');
                    clearContent();
                    sendAck(data.command_id, 'completed');
                    break;
                    
                default:
                    log(`Unhandled command: ${{data.command_type}}`, 'info');
                    sendAck(data.command_id, 'completed');
            }}
        }}
        
        // Send acknowledgment
        function sendAck(commandId, status) {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'ack',
                    command_id: commandId,
                    status: status
                }}));
            }}
        }}
        
        // Send heartbeat
        function sendHeartbeat() {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{ type: 'heartbeat' }}));
            }}
        }}
        
        // Connect to WebSocket
        function connect() {{
            log(`Connecting to ${{WS_URL}}...`);
            
            try {{
                ws = new WebSocket(WS_URL);
                
                ws.onopen = () => {{
                    setConnected(true);
                    reconnectAttempts = 0;
                    
                    // Start heartbeat
                    setInterval(sendHeartbeat, 30000);
                }};
                
                ws.onmessage = (event) => {{
                    try {{
                        const data = JSON.parse(event.data);
                        log(`Message: ${{data.type}}`, 'info');
                        
                        if (data.type === 'command') {{
                            handleCommand(data);
                        }} else if (data.type === 'connected') {{
                            log(`Welcome: ${{data.message}}`, 'success');
                        }}
                    }} catch (e) {{
                        log(`Parse error: ${{e.message}}`, 'error');
                    }}
                }};
                
                ws.onclose = (event) => {{
                    setConnected(false);
                    log(`Disconnected: ${{event.reason || 'Connection closed'}}`, 'error');
                    
                    // Attempt reconnect
                    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {{
                        reconnectAttempts++;
                        log(`Reconnecting in ${{RECONNECT_DELAY/1000}}s (attempt ${{reconnectAttempts}})...`);
                        setTimeout(connect, RECONNECT_DELAY);
                    }}
                }};
                
                ws.onerror = (error) => {{
                    log('WebSocket error', 'error');
                }};
                
            }} catch (e) {{
                log(`Connection failed: ${{e.message}}`, 'error');
            }}
        }}
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'l' || e.key === 'L') {{
                logPanel.classList.toggle('visible');
            }}
            if (e.key === 'Escape') {{
                clearContent();
            }}
            if (e.key === 'f' || e.key === 'F') {{
                document.documentElement.requestFullscreen?.();
            }}
        }});
        
        // Auto-hide status bar after 5 seconds
        setTimeout(() => {{
            document.getElementById('statusBar').classList.add('hidden');
        }}, 5000);
        
        // Start connection
        log('Jarvis Display Simulator starting...');
        log('Press L to toggle logs, ESC to clear, F for fullscreen');
        
        // Restore previous content if available
        if (restoreContentState()) {{
            log('Content restored from previous session', 'success');
        }}
        
        connect();
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# SIMULATOR ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def simulator_page(request: Request):
    """
    Display Simulator page.
    
    Opens a web page that simulates a Raspberry Pi display.
    The simulator connects via WebSocket and displays content.
    
    Usage:
        1. Open http://localhost:8000/simulator in a browser
        2. The page will prompt you to select or create a device
    """
    # Generate the device selection page
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
    finally:
        db.close()
    
    if not devices:
        # No devices - show setup instructions
        return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head>
    <title>Jarvis Simulator - Setup</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #1a1a2e;
            color: #eee;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
        }}
        h1 {{ color: #4a90d9; }}
        code {{
            background: #333;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            display: block;
            margin: 1rem 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ Jarvis Display Simulator</h1>
        <p>No devices found. Create a device first:</p>
        <code>POST /devices</code>
        <p>Then refresh this page.</p>
    </div>
</body>
</html>
""")
    
    # Show device selection
    device_options = "\n".join([
        f'<option value="{d.id}">{d.name}</option>'
        for d in devices
    ])
    
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head>
    <title>Jarvis Simulator - Select Device</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #1a1a2e;
            color: #eee;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            max-width: 400px;
        }}
        h1 {{ color: #4a90d9; margin-bottom: 2rem; }}
        select {{
            width: 100%;
            padding: 1rem;
            font-size: 1rem;
            border-radius: 8px;
            border: 1px solid #333;
            background: #222;
            color: #eee;
            margin-bottom: 1rem;
        }}
        button {{
            width: 100%;
            padding: 1rem;
            font-size: 1rem;
            border-radius: 8px;
            border: none;
            background: #4a90d9;
            color: white;
            cursor: pointer;
        }}
        button:hover {{ background: #3a7fc9; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ Jarvis Display Simulator</h1>
        <p>Select a device to simulate:</p>
        <select id="deviceSelect">
            {device_options}
        </select>
        <button onclick="startSimulator()">Start Simulator</button>
    </div>
    <script>
        function startSimulator() {{
            const deviceId = document.getElementById('deviceSelect').value;
            window.location.href = '/simulator/' + deviceId;
        }}
    </script>
</body>
</html>
""")


@router.get("/{device_id}", response_class=HTMLResponse)
async def simulator_device(device_id: str, request: Request):
    """
    Display Simulator for a specific device.
    
    This page connects as the device and receives commands.
    """
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        
        if not device:
            return HTMLResponse(
                content="<h1>Device not found</h1><p><a href='/simulator'>Back</a></p>",
                status_code=404
            )
        
        # Generate a simulator agent ID
        # The simulator uses the device's existing agent_id or creates one
        if not device.agent_id:
            device.agent_id = f"simulator-{secrets.token_hex(4)}"
            db.commit()
        
        agent_id = device.agent_id
        device_name = device.name
        
    finally:
        db.close()
    
    # Build WebSocket URL
    host = request.headers.get("host", "localhost:8000")
    ws_protocol = "wss" if request.url.scheme == "https" else "ws"
    ws_url = f"{ws_protocol}://{host}/ws/devices?agent_id={agent_id}"
    
    # Return the simulator page
    html = get_simulator_html(device_id, device_name, ws_url)
    return HTMLResponse(content=html)
