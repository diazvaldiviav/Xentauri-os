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
    APP_NAME: str = "Jarvis Cloud Core"
    
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
# GLOBAL SETTINGS INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance to import throughout the app
# Usage: from app.core.config import settings
# Then:  settings.DATABASE_URL, settings.SECRET_KEY, etc.
settings = Settings()
