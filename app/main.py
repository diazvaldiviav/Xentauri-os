"""
Main application entry point - FastAPI app instance and configuration.
This is where the ASGI application is created and configured.
Run with: uvicorn app.main:app --reload
"""

from fastapi import FastAPI  # The FastAPI framework
from fastapi.middleware.cors import CORSMiddleware  # Cross-Origin Resource Sharing

from app.core.config import settings  # Application settings
from app.routers import auth, users, devices, commands  # Route handlers (endpoints)
from app.routers import websocket as ws_router  # WebSocket router
from app.routers import intent  # AI Intent processing router (Sprint 3)
from app.routers import google_auth  # Google OAuth router (Sprint 3.5)
from app.routers import cloud  # Cloud content router (Sprint 3.5)
from app.routers import simulator  # Display Simulator for development (Sprint 3.5)

# ---------------------------------------------------------------------------
# CREATE FASTAPI APPLICATION
# ---------------------------------------------------------------------------
# FastAPI(): Creates the main ASGI application instance
# 
# - title: Shown in the automatic API documentation (Swagger UI)
# - docs_url: Path for Swagger UI (interactive API docs)
#   Visit http://localhost:8000/docs to test endpoints
# - redoc_url: Path for ReDoc (alternative API docs)
#   Visit http://localhost:8000/redoc for a different view
app = FastAPI(
    title=settings.APP_NAME,  # "Jarvis Cloud Core"
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS MIDDLEWARE
# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing) controls which websites can call your API.
# 
# Why it's needed:
# - Browsers block requests from one domain to another by default (security)
# - The iOS app makes requests from a different origin than the API
# - We need to explicitly allow these cross-origin requests
# 
# Current configuration (MVP - permissive):
# - allow_origins=["*"]: Accept requests from any origin
# - allow_methods=["*"]: Accept any HTTP method (GET, POST, etc.)
# - allow_headers=["*"]: Accept any headers (including Authorization)
# - allow_credentials=True: Allow cookies/auth headers
# 
# PRODUCTION TODO: Restrict to specific origins:
# allow_origins=["https://jarvis-app.com", "https://admin.jarvis-app.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# REGISTER ROUTERS
# ---------------------------------------------------------------------------
# Routers organize endpoints into logical groups.
# include_router() adds all routes from a router to the main app.
# 
# auth.router: /auth/register, /auth/login
# users.router: /users/me
# devices.router: /devices CRUD + pairing
# commands.router: /commands for sending commands to devices
# ws_router.router: /ws/devices WebSocket for Pi agents
# intent.router: /intent for natural language command processing (AI)
# google_auth.router: /auth/google for Google OAuth (Sprint 3.5)
# cloud.router: /cloud for rendered content for Raspberry Pi (Sprint 3.5)
# simulator.router: /simulator for browser-based display testing (Sprint 3.5)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(commands.router)
app.include_router(ws_router.router)
app.include_router(intent.router)
app.include_router(google_auth.router)
app.include_router(cloud.router)
app.include_router(simulator.router)


# ---------------------------------------------------------------------------
# HEALTH CHECK ENDPOINT
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health_check():
    """
    Simple health check endpoint.
    
    Used by:
    - Fly.io to verify the app is running
    - Load balancers to check if the instance is healthy
    - Kubernetes/Docker health probes
    - Monitoring tools (Datadog, New Relic, etc.)
    
    Returns a simple JSON response indicating the service is operational.
    Does NOT check database connectivity (use a separate /ready endpoint for that).
    
    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}
