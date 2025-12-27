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
        
        .status-dot.reconnecting {{
            background: #ff9800;
            animation: blink 0.5s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.2; }}
        }}
        
        /* Reconnection overlay */
        .reconnect-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }}
        
        .reconnect-overlay.visible {{
            opacity: 1;
            pointer-events: auto;
        }}
        
        .reconnect-spinner {{
            width: 48px;
            height: 48px;
            border: 3px solid #333;
            border-top-color: #4a90d9;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .reconnect-message {{
            font-size: 18px;
            color: #fff;
            margin-bottom: 8px;
        }}
        
        .reconnect-detail {{
            font-size: 14px;
            color: #888;
            margin-bottom: 20px;
        }}
        
        .reconnect-btn {{
            background: #4a90d9;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s;
        }}
        
        .reconnect-btn:hover {{
            background: #3a7bc8;
        }}
        
        .reconnect-btn:disabled {{
            background: #555;
            cursor: not-allowed;
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
        
        /* Scene Graph Styles */
        .scene-container {{
            overflow: hidden;
        }}
        
        .component {{
            overflow: hidden;
        }}
        
        .calendar-agenda {{
            overflow-y: auto;
            max-height: 100%;
        }}
        
        .agenda-event:last-child {{
            margin-bottom: 0;
        }}
        
        .clock-digital {{
            text-align: center;
        }}
        
        .calendar-widget {{
            overflow-y: auto;
        }}
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
    
    <!-- Reconnection Overlay -->
    <div class="reconnect-overlay" id="reconnectOverlay">
        <div class="reconnect-spinner"></div>
        <div class="reconnect-message" id="reconnectMessage">Reconnecting...</div>
        <div class="reconnect-detail" id="reconnectDetail">Attempt 1 of ∞</div>
        <button class="reconnect-btn" id="reconnectBtn" onclick="forceReconnect()">Reconnect Now</button>
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
        // Debug: Confirm script is running
        console.log('[Jarvis Simulator] Script starting...');
        
        // Configuration
        const DEVICE_ID = "{device_id}";
        const DEVICE_NAME = "{device_name}";
        const WS_URL = "{ws_url}";
        
        console.log('[Jarvis Simulator] Config:', {{ DEVICE_ID, DEVICE_NAME, WS_URL }});
        
        // DOM elements
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const contentFrame = document.getElementById('contentFrame');
        const idleScreen = document.getElementById('idleScreen');
        const logPanel = document.getElementById('logPanel');
        
        // WebSocket connection
        let ws = null;
        let reconnectAttempts = 0;
        let reconnectTimer = null;
        const BASE_RECONNECT_DELAY = 1000;  // Start at 1 second
        const MAX_RECONNECT_DELAY = 30000;  // Max 30 seconds
        
        // DOM elements for reconnection
        const reconnectOverlay = document.getElementById('reconnectOverlay');
        const reconnectMessage = document.getElementById('reconnectMessage');
        const reconnectDetail = document.getElementById('reconnectDetail');
        const reconnectBtn = document.getElementById('reconnectBtn');
        
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
                statusDot.classList.remove('reconnecting');
                statusDot.classList.add('connected');
                statusText.textContent = 'Connected';
                log('Connected to Jarvis Cloud', 'success');
                
                // Hide reconnection overlay
                if (reconnectOverlay) {{
                    reconnectOverlay.classList.remove('visible');
                }}
                if (reconnectBtn) {{
                    reconnectBtn.disabled = false;
                    reconnectBtn.textContent = 'Reconnect Now';
                }}
            }} else {{
                statusDot.classList.remove('connected');
                statusDot.classList.add('reconnecting');
                statusText.textContent = 'Reconnecting...';
            }}
        }}
        
        // Show reconnection overlay after a delay
        function showReconnectOverlay(attempt, delay) {{
            if (reconnectOverlay && attempt >= 2) {{
                reconnectOverlay.classList.add('visible');
                reconnectMessage.textContent = 'Connection Lost';
                reconnectDetail.textContent = `Reconnecting in ${{Math.round(delay/1000)}}s (attempt ${{attempt}})`;
            }}
        }}
        
        // Force manual reconnection
        function forceReconnect() {{
            log('Manual reconnect requested', 'info');
            if (reconnectTimer) {{
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }}
            reconnectAttempts = 0;
            if (reconnectBtn) {{
                reconnectBtn.disabled = true;
                reconnectBtn.textContent = 'Connecting...';
            }}
            connect();
        }}
        
        // Make forceReconnect available globally
        window.forceReconnect = forceReconnect;
        
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
                    
                    // Sprint 3.9: Log Google Docs display
                    if (contentType === 'google_doc') {{
                        log(`📄 Displaying Google Doc: ${{url}}`, 'info');
                    }}
                    
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
                
                case 'display_scene':
                    const scene = data.parameters?.scene;
                    if (scene) {{
                        log(`Rendering scene: ${{scene.scene_id}} with ${{scene.components?.length || 0}} components`, 'command');
                        renderScene(scene);
                    }} else {{
                        log('display_scene: No scene data received', 'error');
                    }}
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
        // Heartbeat interval reference
        let heartbeatInterval = null;
        
        function connect() {{
            log(`Connecting to ${{WS_URL}}...`, 'info');
            console.log('[Jarvis Simulator] Attempting WebSocket connection to:', WS_URL);
            
            // Clear any existing heartbeat
            if (heartbeatInterval) {{
                clearInterval(heartbeatInterval);
                heartbeatInterval = null;
            }}
            
            try {{
                ws = new WebSocket(WS_URL);
                
                ws.onopen = () => {{
                    console.log('[Jarvis Simulator] WebSocket connected successfully');
                    setConnected(true);
                    reconnectAttempts = 0;
                    
                    // Start heartbeat
                    heartbeatInterval = setInterval(sendHeartbeat, 30000);
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
                        console.error('[Jarvis Simulator] Message parse error:', e);
                    }}
                }};
                
                ws.onclose = (event) => {{
                    console.log('[Jarvis Simulator] WebSocket closed:', event.code, event.reason);
                    setConnected(false);
                    
                    // Clear heartbeat
                    if (heartbeatInterval) {{
                        clearInterval(heartbeatInterval);
                        heartbeatInterval = null;
                    }}
                    
                    const reason = event.reason || (event.code === 1000 ? 'Normal closure' : `Code ${{event.code}}`);
                    log(`Disconnected: ${{reason}}`, 'error');
                    
                    // Calculate exponential backoff delay
                    reconnectAttempts++;
                    const delay = Math.min(
                        BASE_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts - 1),
                        MAX_RECONNECT_DELAY
                    );
                    
                    log(`Reconnecting in ${{Math.round(delay/1000)}}s (attempt ${{reconnectAttempts}})...`, 'info');
                    showReconnectOverlay(reconnectAttempts, delay);
                    
                    // Schedule reconnection (unlimited attempts)
                    reconnectTimer = setTimeout(connect, delay);
                }};
                
                ws.onerror = (error) => {{
                    console.error('[Jarvis Simulator] WebSocket error:', error);
                    log('WebSocket error - check browser console', 'error');
                }};
                
            }} catch (e) {{
                console.error('[Jarvis Simulator] Connection exception:', e);
                log(`Connection failed: ${{e.message}}`, 'error');
                
                // Still try to reconnect on exception
                reconnectAttempts++;
                const delay = Math.min(
                    BASE_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts - 1),
                    MAX_RECONNECT_DELAY
                );
                showReconnectOverlay(reconnectAttempts, delay);
                reconnectTimer = setTimeout(connect, delay);
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
            if (e.key === 'r' || e.key === 'R') {{
                // Force reconnect
                forceReconnect();
            }}
        }});
        
        // Auto-hide status bar after 5 seconds
        setTimeout(() => {{
            document.getElementById('statusBar').classList.add('hidden');
        }}, 5000);
        
        // Start connection
        console.log('[Jarvis Simulator] About to initialize...');
        log('Jarvis Display Simulator starting...');
        log('Keys: L=logs, ESC=clear, F=fullscreen, R=reconnect');
        
        // Restore previous content if available
        if (restoreContentState()) {{
            log('Content restored from previous session', 'success');
        }}
        
        console.log('[Jarvis Simulator] Calling connect()...');
        connect();
        console.log('[Jarvis Simulator] connect() called');
        
        // =========================================================================
        // SCENE GRAPH RENDERER (Sprint 4.0)
        // =========================================================================
        
        function renderScene(scene) {{
            // Clear current content
            contentFrame.innerHTML = '';
            
            // Create scene container with global styles
            const container = document.createElement('div');
            container.className = 'scene-container';
            container.style.cssText = `
                width: 100%;
                height: 100%;
                background: ${{scene.global_style?.background || '#0f0f23'}};
                font-family: ${{scene.global_style?.font_family || 'Inter'}}, sans-serif;
                color: ${{scene.global_style?.text_color || '#ffffff'}};
                padding: 16px;
                box-sizing: border-box;
            `;
            
            // Apply layout based on intent
            applyLayout(container, scene.layout);
            
            // Render each component
            (scene.components || []).forEach(comp => {{
                const element = renderComponent(comp);
                container.appendChild(element);
            }});
            
            contentFrame.appendChild(container);
            
            // Hide idle screen
            if (idleScreen) idleScreen.style.display = 'none';
            
            // Store scene for refresh
            window.currentScene = scene;
            
            log(`Scene rendered: ${{scene.layout?.intent || 'default'}} layout with ${{scene.components?.length || 0}} components`, 'success');
        }}
        
        function applyLayout(container, layout) {{
            const intent = layout?.intent || 'fullscreen';
            
            switch(intent) {{
                case 'fullscreen':
                    container.style.display = 'flex';
                    break;
                    
                case 'sidebar':
                    container.style.display = 'grid';
                    container.style.gridTemplateColumns = '3fr 1fr';
                    container.style.gap = layout?.gap || '16px';
                    break;
                    
                case 'dashboard':
                    container.style.display = 'grid';
                    container.style.gridTemplateColumns = '1fr 1fr';
                    container.style.gridTemplateRows = '1fr 1fr';
                    container.style.gap = layout?.gap || '16px';
                    break;
                    
                case 'stack':
                    container.style.display = 'flex';
                    container.style.flexDirection = 'column';
                    container.style.gap = layout?.gap || '16px';
                    break;
                    
                case 'overlay':
                    container.style.position = 'relative';
                    break;
                    
                default:
                    container.style.display = 'flex';
            }}
        }}
        
        function renderComponent(component) {{
            const wrapper = document.createElement('div');
            wrapper.className = `component component-${{component.type}}`;
            wrapper.id = component.id;
            
            // Apply position (for grid layouts)
            if (component.position) {{
                if (component.position.grid_column) {{
                    wrapper.style.gridColumn = component.position.grid_column;
                }}
                if (component.position.grid_row) {{
                    wrapper.style.gridRow = component.position.grid_row;
                }}
                if (component.position.flex) {{
                    wrapper.style.flex = component.position.flex;
                }}
            }}
            
            // Apply component style with fallback defaults
            const defaultStyle = {{
                background: component.priority === 'primary' ? '#1a1a2e' : '#16213e',
                text_color: '#ffffff',
                border_radius: '12px',
                padding: '20px'
            }};
            const style = {{ ...defaultStyle, ...(component.style || {{}}) }};
            wrapper.style.background = style.background;
            wrapper.style.color = style.text_color;
            wrapper.style.borderRadius = style.border_radius;
            wrapper.style.padding = style.padding;
            
            // Render content based on type
            const content = renderComponentContent(component);
            wrapper.appendChild(content);
            
            return wrapper;
        }}
        
        function renderComponentContent(component) {{
            const {{ type, data, props }} = component;
            
            switch(type) {{
                case 'calendar_week':
                    return renderCalendarWeek(data, props);
                case 'calendar_agenda':
                    return renderCalendarAgenda(data, props);
                case 'calendar_widget':
                    return renderCalendarWidget(data, props);
                case 'calendar_day':
                    return renderCalendarDay(data, props);
                case 'calendar_month':
                    return renderCalendarMonth(data, props);
                case 'clock_digital':
                    return renderClockDigital(data, props);
                case 'clock_analog':
                    return renderClockAnalog(data, props);
                case 'weather_current':
                    return renderWeather(data, props);
                case 'text_block':
                    return renderTextBlock(data, props);
                case 'spacer':
                    return renderSpacer(props);
                case 'image_display':
                    return renderImage(data, props);
                case 'web_embed':
                    return renderWebEmbed(data, props);
                // NEW COMPONENTS - Sprint 4.0.1
                case 'meeting_detail':
                    return renderMeetingDetail(data, props);
                case 'countdown_timer':
                case 'event_countdown':
                    return renderCountdownTimer(data, props);
                case 'doc_summary':
                    return renderDocSummary(data, props);
                case 'doc_preview':
                    return renderDocSummary(data, props);  // Reuse with slight variation
                default:
                    return renderUnknown(type);
            }}
        }}
        
        // Calendar Agenda renderer
        function renderCalendarAgenda(data, props) {{
            const container = document.createElement('div');
            container.className = 'calendar-agenda';
            
            const events = data?.events || [];
            
            if (events.length === 0) {{
                container.innerHTML = '<p style="opacity: 0.6;">No upcoming events</p>';
                return container;
            }}
            
            const maxEvents = props?.max_events || 10;
            const displayEvents = events.slice(0, maxEvents);
            
            displayEvents.forEach(event => {{
                const eventEl = document.createElement('div');
                eventEl.className = 'agenda-event';
                eventEl.style.cssText = `
                    padding: 12px;
                    margin-bottom: 8px;
                    background: rgba(255,255,255,0.05);
                    border-radius: 8px;
                    border-left: 4px solid ${{event.color || '#4285f4'}};
                `;
                
                const time = event.is_all_day ? 'All Day' : formatTime(event.start);
                eventEl.innerHTML = `
                    <div style="font-weight: 600; margin-bottom: 4px;">${{escapeHtml(event.title)}}</div>
                    <div style="font-size: 0.85em; opacity: 0.7;">${{time}}${{event.location ? ' • ' + escapeHtml(event.location) : ''}}</div>
                `;
                container.appendChild(eventEl);
            }});
            
            return container;
        }}
        
        // Clock Digital renderer
        function renderClockDigital(data, props) {{
            const container = document.createElement('div');
            container.className = 'clock-digital';
            container.style.cssText = `
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
            `;
            
            const timeEl = document.createElement('div');
            timeEl.className = 'clock-time';
            timeEl.style.cssText = 'font-size: 4em; font-weight: 300;';
            
            const dateEl = document.createElement('div');
            dateEl.className = 'clock-date';
            dateEl.style.cssText = 'font-size: 1.2em; opacity: 0.7; margin-top: 8px;';
            
            function updateClock() {{
                const now = new Date();
                const format = props?.format || '12h';
                
                let hours = now.getHours();
                let ampm = '';
                if (format === '12h') {{
                    ampm = hours >= 12 ? ' PM' : ' AM';
                    hours = hours % 12 || 12;
                }}
                
                const minutes = String(now.getMinutes()).padStart(2, '0');
                const seconds = props?.show_seconds ? ':' + String(now.getSeconds()).padStart(2, '0') : '';
                
                timeEl.textContent = `${{hours}}:${{minutes}}${{seconds}}${{ampm}}`;
                
                if (props?.show_date !== false) {{
                    dateEl.textContent = now.toLocaleDateString('en-US', {{
                        weekday: 'long',
                        month: 'long',
                        day: 'numeric'
                    }});
                }}
            }}
            
            updateClock();
            setInterval(updateClock, 1000);
            
            container.appendChild(timeEl);
            if (props?.show_date !== false) {{
                container.appendChild(dateEl);
            }}
            
            return container;
        }}
        
        // Calendar Widget renderer
        function renderCalendarWidget(data, props) {{
            const container = document.createElement('div');
            container.className = 'calendar-widget';
            
            const events = data?.events || [];
            const maxEvents = props?.max_events || 5;
            
            const title = document.createElement('h3');
            title.textContent = 'Upcoming';
            title.style.cssText = 'margin: 0 0 12px 0; font-size: 1.1em; opacity: 0.8;';
            container.appendChild(title);
            
            if (events.length === 0) {{
                container.innerHTML += '<p style="opacity: 0.6;">No upcoming events</p>';
                return container;
            }}
            
            events.slice(0, maxEvents).forEach(event => {{
                const eventEl = document.createElement('div');
                eventEl.style.cssText = `
                    padding: 8px 0;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                    display: flex;
                    align-items: center;
                    gap: 8px;
                `;
                
                const dot = document.createElement('div');
                dot.style.cssText = `
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: ${{event.color || '#4285f4'}};
                `;
                
                const info = document.createElement('div');
                info.innerHTML = `
                    <div style="font-weight: 500;">${{escapeHtml(event.title)}}</div>
                    <div style="font-size: 0.8em; opacity: 0.6;">${{formatTime(event.start)}}</div>
                `;
                
                eventEl.appendChild(dot);
                eventEl.appendChild(info);
                container.appendChild(eventEl);
            }});
            
            return container;
        }}
        
        // Weather renderer
        function renderWeather(data, props) {{
            const container = document.createElement('div');
            container.className = 'weather-current';
            container.style.cssText = `
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
            `;
            
            const icon = getWeatherIcon(data?.condition || 'sunny');
            const temp = data?.temperature || '--';
            const unit = props?.units === 'celsius' ? '°C' : '°F';
            
            container.innerHTML = `
                <div style="font-size: 3em;">${{icon}}</div>
                <div style="font-size: 2.5em; font-weight: 300; margin: 8px 0;">${{temp}}${{unit}}</div>
                <div style="opacity: 0.7;">${{data?.location || ''}}</div>
                ${{data?.is_placeholder ? '<div style="font-size: 0.7em; opacity: 0.5; margin-top: 8px;">Demo data</div>' : ''}}
            `;
            
            return container;
        }}
        
        function getWeatherIcon(condition) {{
            const icons = {{
                'sunny': '☀️',
                'partly_cloudy': '⛅',
                'cloudy': '☁️',
                'rain': '🌧️',
                'snow': '❄️',
                'thunder': '⛈️',
            }};
            return icons[condition] || '🌤️';
        }}
        
        // Helper functions
        function formatTime(isoString) {{
            if (!isoString) return '';
            const date = new Date(isoString);
            return date.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit' }});
        }}
        
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        function renderTextBlock(data, props) {{
            const el = document.createElement('div');
            el.className = 'text-block';
            el.style.fontSize = props?.font_size || '1em';
            el.textContent = data?.content || '';
            return el;
        }}
        
        function renderSpacer(props) {{
            const el = document.createElement('div');
            el.className = 'spacer';
            el.style.minHeight = props?.size || '16px';
            return el;
        }}
        
        function renderImage(data, props) {{
            const img = document.createElement('img');
            img.src = data?.url || '';
            img.alt = data?.alt || '';
            img.style.cssText = `max-width: 100%; height: auto; object-fit: ${{props?.fit || 'contain'}};`;
            return img;
        }}
        
        function renderWebEmbed(data, props) {{
            const iframe = document.createElement('iframe');
            iframe.src = data?.url || '';
            iframe.style.cssText = 'width: 100%; height: 100%; border: none;';
            return iframe;
        }}
        
        function renderUnknown(type) {{
            const el = document.createElement('div');
            el.style.cssText = 'opacity: 0.5; padding: 16px;';
            el.textContent = `Unknown component: ${{type}}`;
            return el;
        }}
        
        function renderCalendarWeek(data, props) {{
            // Simplified week view - uses agenda for now
            return renderCalendarAgenda(data, {{ ...props, max_events: 20 }});
        }}
        
        function renderCalendarDay(data, props) {{
            return renderCalendarAgenda(data, {{ ...props, max_events: 15 }});
        }}
        
        function renderCalendarMonth(data, props) {{
            const container = document.createElement('div');
            container.className = 'calendar-month';
            
            const header = document.createElement('h3');
            header.textContent = new Date().toLocaleDateString('en-US', {{ month: 'long', year: 'numeric' }});
            header.style.cssText = 'margin: 0 0 12px 0; font-size: 1.2em;';
            container.appendChild(header);
            
            // Add agenda below
            const agenda = renderCalendarAgenda(data, {{ ...props, max_events: 10 }});
            container.appendChild(agenda);
            
            return container;
        }}
        
        function renderClockAnalog(data, props) {{
            // Fallback to digital for now
            return renderClockDigital(data, props);
        }}
        
        // -----------------------------------------------------------------------
        // NEW COMPONENT RENDERERS - Sprint 4.0.1
        // -----------------------------------------------------------------------
        
        // Meeting Detail renderer
        function renderMeetingDetail(data, props) {{
            const container = document.createElement('div');
            container.className = 'meeting-detail';
            container.style.cssText = 'padding: 20px;';
            
            if (data?.empty) {{
                container.innerHTML = `<p class="no-events">No upcoming meetings</p>`;
                return container;
            }}
            
            if (data?.error) {{
                container.innerHTML = `<p class="error">${{data.error}}</p>`;
                return container;
            }}
            
            const startTime = data?.start_time ? new Date(data.start_time).toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : '';
            const endTime = data?.end_time ? new Date(data.end_time).toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : '';
            
            container.innerHTML = `
                <h2 style="margin: 0 0 16px 0; font-size: 28px;">${{data?.title || 'Meeting'}}</h2>
                <div style="font-size: 20px; opacity: 0.8; margin-bottom: 12px;">
                    ${{data?.is_all_day ? 'All Day' : `${{startTime}} - ${{endTime}}`}}
                </div>
                ${{data?.location ? `<div style="font-size: 18px; opacity: 0.7; margin-bottom: 8px;">📍 ${{data.location}}</div>` : ''}}
                ${{data?.description ? `<div style="font-size: 16px; opacity: 0.6; margin-top: 16px; white-space: pre-wrap;">${{data.description.substring(0, 300)}}${{data.description.length > 300 ? '...' : ''}}</div>` : ''}}
                ${{data?.attendees && data.attendees.length > 0 ? `
                    <div style="margin-top: 16px; font-size: 14px; opacity: 0.6;">
                        👥 ${{data.attendees.length}} attendee${{data.attendees.length > 1 ? 's' : ''}}
                    </div>
                ` : ''}}
            `;
            return container;
        }}
        
        // Countdown Timer renderer
        function renderCountdownTimer(data, props) {{
            const container = document.createElement('div');
            container.className = 'countdown-timer';
            container.style.cssText = 'text-align: center; padding: 20px;';
            
            if (data?.error) {{
                container.innerHTML = `<p class="error">${{data.error}}</p>`;
                return container;
            }}
            
            if (data?.empty) {{
                container.innerHTML = `<p>No upcoming events</p>`;
                return container;
            }}
            
            // Calculate time components
            let seconds = data?.seconds_until || 0;
            const hours = Math.floor(seconds / 3600);
            seconds %= 3600;
            const minutes = Math.floor(seconds / 60);
            seconds %= 60;
            
            container.innerHTML = `
                <div style="font-size: 16px; opacity: 0.7; margin-bottom: 8px;">${{data?.target_label || 'Countdown'}}</div>
                <div class="countdown-display" style="font-size: 64px; font-weight: bold; font-family: monospace;">
                    ${{String(hours).padStart(2, '0')}}:${{String(minutes).padStart(2, '0')}}:${{String(Math.floor(seconds)).padStart(2, '0')}}
                </div>
            `;
            
            // Store seconds_until on the container for the interval
            container.dataset.secondsUntil = data?.seconds_until || 0;
            
            // Start live countdown
            const timerId = setInterval(() => {{
                if (!document.contains(container)) {{
                    clearInterval(timerId);
                    return;
                }}
                const timeDisplay = container.querySelector('.countdown-display');
                let remaining = parseInt(container.dataset.secondsUntil);
                if (timeDisplay && remaining > 0) {{
                    remaining--;
                    container.dataset.secondsUntil = remaining;
                    const h = Math.floor(remaining / 3600);
                    const m = Math.floor((remaining % 3600) / 60);
                    const s = remaining % 60;
                    timeDisplay.textContent = `${{String(h).padStart(2, '0')}}:${{String(m).padStart(2, '0')}}:${{String(s).padStart(2, '0')}}`;
                }}
            }}, 1000);
            
            return container;
        }}
        
        // Document Summary renderer
        function renderDocSummary(data, props) {{
            const container = document.createElement('div');
            container.className = 'doc-summary';
            container.style.cssText = 'padding: 20px; overflow-y: auto; max-height: 100%;';
            
            if (data?.error) {{
                container.innerHTML = `<p class="error" style="color: #ff6b6b;">${{data.error}}</p>`;
                return container;
            }}
            
            // Check if we have AI-generated content (takes priority)
            if (data?.generated_content) {{
                // Format the generated content - preserve line breaks and structure
                const formattedContent = formatGeneratedContent(data.generated_content, data.content_type);
                
                container.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
                        <h3 style="margin: 0; font-size: 20px;">📄 ${{data?.title || 'Document'}}</h3>
                        <span style="font-size: 10px; padding: 2px 8px; background: rgba(123, 44, 191, 0.3); border-radius: 4px; color: #b388ff;">✨ AI</span>
                    </div>
                    <div class="ai-content" style="font-size: 16px; line-height: 1.6;">
                        ${{formattedContent}}
                    </div>
                `;
                return container;
            }}
            
            // Fallback to standard display
            const keyPointsHtml = data?.key_points && data.key_points.length > 0 
                ? `<ul style="margin-top: 16px; padding-left: 20px;">
                     ${{data.key_points.map(point => `<li style="margin-bottom: 8px;">${{point}}</li>`).join('')}}
                   </ul>`
                : '';
            
            container.innerHTML = `
                <h3 style="margin: 0 0 12px 0; font-size: 22px;">📄 ${{data?.title || 'Document'}}</h3>
                ${{data?.summary ? `<p style="font-size: 16px; opacity: 0.8; line-height: 1.5;">${{data.summary}}</p>` : ''}}
                ${{data?.preview_text ? `<p style="font-size: 14px; opacity: 0.7; line-height: 1.5;">${{data.preview_text}}</p>` : ''}}
                ${{keyPointsHtml}}
                ${{data?.last_modified ? `<div style="font-size: 12px; opacity: 0.5; margin-top: 16px;">Last modified: ${{new Date(data.last_modified).toLocaleDateString()}}</div>` : ''}}
            `;
            return container;
        }}
        
        // Format AI-generated content for display
        function formatGeneratedContent(content, contentType) {{
            try {{
                if (!content) return '';
                
                // Escape HTML first
                let formatted = escapeHtml(content);
                
                // Convert markdown-style formatting
                // Bold: **text** or __text__
                formatted = formatted.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
                formatted = formatted.replace(/__(.*?)__/g, '<strong>$1</strong>');
                
                // Italic: *text* or _text_
                formatted = formatted.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
                formatted = formatted.replace(/_([^_]+)_/g, '<em>$1</em>');
                
                // Convert numbered lists (1. item, 2. item)
                formatted = formatted.replace(/^(\\d+)\\.\\s+(.+)$/gm, '<div style="margin: 8px 0; padding-left: 20px;"><span style="color: #7b2cbf; font-weight: bold;">$1.</span> $2</div>');
                
                // Convert bullet points (- item or • item)
                formatted = formatted.replace(/^[-•]\\s+(.+)$/gm, '<div style="margin: 8px 0; padding-left: 20px;">• $1</div>');
                
                // Convert line breaks to HTML
                formatted = formatted.replace(/\\n\\n/g, '</p><p style="margin: 12px 0;">');
                formatted = formatted.replace(/\\n/g, '<br>');
                
                // Wrap in paragraph if not already structured
                if (!formatted.includes('<div') && !formatted.includes('<p')) {{
                    formatted = `<p style="margin: 0;">${{formatted}}</p>`;
                }}
                
                // Add special styling based on content type
                if (contentType === 'impact_phrases') {{
                    // Make impact phrases larger and more prominent
                    formatted = `<div style="font-size: 1.1em; font-weight: 500;">${{formatted}}</div>`;
                }} else if (contentType === 'script') {{
                    // Script style - monospace-ish, clear structure
                    formatted = `<div style="font-family: 'Georgia', serif; line-height: 1.8;">${{formatted}}</div>`;
                }} else if (contentType === 'action_items') {{
                    // Action items - checkbox style
                    formatted = formatted.replace(/•/g, '☐');
                }}
                
                return formatted;
            }} catch (e) {{
                console.error('[Jarvis Simulator] Error formatting AI content:', e);
                // Return plain escaped content on error
                return escapeHtml(content || '');
            }}
        }}
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
