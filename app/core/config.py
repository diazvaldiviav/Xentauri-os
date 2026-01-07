"""
Configuration module - centralized settings for the entire application.
Uses pydantic-settings to load values from environment variables and .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Pydantic-settings automatically:
    1. Reads from environment variables (highest priority)
    2. Falls back to .env file values
    3. Uses default values if neither exists
    
    To override in production, set environment variables:
        export DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
        export SECRET_KEY=your-super-secret-random-string
    """
    
    # ---------------------------------------------------------------------------
    # PYDANTIC SETTINGS CONFIGURATION
    # ---------------------------------------------------------------------------
    # model_config: Tells pydantic-settings how to load configuration
    model_config = SettingsConfigDict(
        env_file=".env",        # Load from .env file in project root
        env_file_encoding="utf-8",  # File encoding
        extra="ignore",         # Ignore extra env vars not defined here
    )

    # ---------------------------------------------------------------------------
    # APPLICATION SETTINGS
    # ---------------------------------------------------------------------------
    # APP_NAME: Display name shown in API docs and logging
    APP_NAME: str = "Xentauri Cloud Core"
    
    # DEBUG: Enable debug mode (more verbose errors, auto-reload in dev)
    # Set to False in production for security
    DEBUG: bool = False

    # ---------------------------------------------------------------------------
    # DATABASE SETTINGS
    # ---------------------------------------------------------------------------
    # DATABASE_URL: PostgreSQL connection string
    # Format: postgresql+psycopg://username:password@host:port/database_name
    # - postgresql+psycopg: Use psycopg3 driver (async-capable, modern)
    # - For Fly.io, this will be set automatically when you attach a Postgres cluster
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/jarvis"

    # ---------------------------------------------------------------------------
    # JWT (JSON Web Token) SETTINGS
    # ---------------------------------------------------------------------------
    # SECRET_KEY: Used to sign JWT tokens
    # - MUST be changed in production to a long, random string
    # - Anyone with this key can forge valid tokens!
    # - Generate with: openssl rand -hex 32
    SECRET_KEY: str = "change-me-in-production"
    
    # ALGORITHM: JWT signing algorithm
    # - HS256: HMAC with SHA-256 (symmetric - uses SECRET_KEY for both sign and verify)
    # - Fast and suitable for single-server or trusted environments
    ALGORITHM: str = "HS256"
    
    # ACCESS_TOKEN_EXPIRE_MINUTES: How long tokens are valid
    # - 60 * 24 = 1440 minutes = 24 hours
    # - After expiration, users must log in again
    # - Balance security (shorter) vs UX (longer)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ---------------------------------------------------------------------------
    # AI/LLM PROVIDER SETTINGS (Sprint 3)
    # ---------------------------------------------------------------------------
    # GEMINI_API_KEY: Google's Gemini API for the orchestrator (fast, cheap)
    # - Gemini Flash is used as the router/orchestrator
    # - Handles simple tasks directly, routes complex ones to other models
    GEMINI_API_KEY: str = ""
    
    # OPENAI_API_KEY: OpenAI's GPT API for code generation and tool usage
    # - Used for tasks requiring code, API calls, or structured execution
    OPENAI_API_KEY: str = ""
    
    # ANTHROPIC_API_KEY: Anthropic's Claude API for deep reasoning
    # - Used for complex planning, critical decisions, and nuanced analysis
    ANTHROPIC_API_KEY: str = ""
    
    # ---------------------------------------------------------------------------
    # AI MODEL CONFIGURATION
    # ---------------------------------------------------------------------------
    # Default models for each provider (can be overridden per-request)
    GEMINI_MODEL: str = "gemini-2.5-flash"  # Fast, cheap orchestrator
    OPENAI_MODEL: str = "gpt-5.2"  # Capable model for complex tasks
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"  # Most powerful Claude model

    #Fallback model if the specified one is unavailable
    GPT_FALLBACK_MODEL: str = "gpt-5-mini-2025-08-07"
    
    # AI Request timeout in seconds
    AI_REQUEST_TIMEOUT: int = 30

    # ---------------------------------------------------------------------------
    # GOOGLE OAUTH SETTINGS (Sprint 3.5)
    # ---------------------------------------------------------------------------
    # Google Cloud Console: https://console.cloud.google.com/apis/credentials
    # 
    # Setup Instructions:
    # 1. Create a new project in Google Cloud Console
    # 2. Enable the Google Calendar API
    # 3. Configure OAuth consent screen (External, add test users)
    # 4. Create OAuth 2.0 Client ID (Web application)
    # 5. Add authorized redirect URI: http://localhost:8000/auth/google/callback
    # 6. Copy Client ID and Client Secret to .env file
    
    # GOOGLE_CLIENT_ID: OAuth 2.0 Client ID from Google Cloud Console
    GOOGLE_CLIENT_ID: str = ""
    
    # GOOGLE_CLIENT_SECRET: OAuth 2.0 Client Secret from Google Cloud Console
    GOOGLE_CLIENT_SECRET: str = ""
    
    # GOOGLE_REDIRECT_URI: Where Google sends users after authorization
    # - Must match exactly what's configured in Google Cloud Console
    # - For local dev: http://localhost:8000/auth/google/callback
    # - For production: https://your-domain.com/auth/google/callback
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ---------------------------------------------------------------------------
    # CUSTOM LAYOUT FEATURE (Sprint 5.2)
    # ---------------------------------------------------------------------------
    # Enable GPT-5.2 powered custom HTML layouts for Scene Graphs
    # When enabled, after Claude generates a SceneGraph, GPT-5.2 creates enhanced HTML
    
    # CUSTOM_LAYOUT_ENABLED: Master switch for the feature
    # - False: Use SceneGraph rendering only (current behavior)
    # - True: Generate custom HTML layouts via GPT-5.2
    CUSTOM_LAYOUT_ENABLED: bool = True
    
    # CUSTOM_LAYOUT_TIMEOUT_SECONDS: Max time for HTML generation
    # - GPT-5.2 call + Playwright validation combined
    CUSTOM_LAYOUT_TIMEOUT_SECONDS: int = 10
    
    # CUSTOM_LAYOUT_VALIDATION_ENABLED: Whether to validate HTML with Playwright
    # - True: Validate HTML renders without JS errors and is not blank
    # - False: Skip validation (use generated HTML directly)
    CUSTOM_LAYOUT_VALIDATION_ENABLED: bool = True

    # ---------------------------------------------------------------------------
    # JSON REPAIR SETTINGS (Sprint 5.3)
    # ---------------------------------------------------------------------------
    # Enable intelligent JSON repair when LLMs return malformed JSON
    # Uses Gemini for fast diagnosis, then original provider for repair
    
    # JSON_REPAIR_ENABLED: Master switch for JSON repair feature
    # - False: Return error on invalid JSON (current behavior)
    # - True: Attempt to diagnose and repair malformed JSON
    JSON_REPAIR_ENABLED: bool = True
    
    # JSON_REPAIR_MAX_RETRIES: Maximum repair attempts before giving up
    # - 1 is usually sufficient (diagnosis + single repair)
    # - Higher values increase latency but may fix complex issues
    JSON_REPAIR_MAX_RETRIES: int = 1

    # ---------------------------------------------------------------------------
    # HTML REPAIR SETTINGS (Sprint 5.2.1)
    # ---------------------------------------------------------------------------
    # Enable intelligent HTML repair when GPT-5.2 generates invalid HTML
    # Uses Gemini for fast diagnosis, then GPT-5.2 for repair
    
    # HTML_REPAIR_ENABLED: Master switch for HTML repair feature
    # - False: Return error on invalid HTML (fallback to SceneGraph immediately)
    # - True: Attempt to diagnose and repair malformed HTML before fallback
    HTML_REPAIR_ENABLED: bool = True
    
    # HTML_REPAIR_MAX_RETRIES: Maximum repair attempts before giving up
    # - 1 is usually sufficient (diagnosis + single repair)
    HTML_REPAIR_MAX_RETRIES: int = 1


# ---------------------------------------------------------------------------
# GLOBAL SETTINGS INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance to import throughout the app
# Usage: from app.core.config import settings
# Then:  settings.DATABASE_URL, settings.SECRET_KEY, etc.
settings = Settings()
