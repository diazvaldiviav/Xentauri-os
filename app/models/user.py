"""
User model - represents a registered user in the Jarvis system.
Users can own multiple devices (screens) and authenticate via email/password.
"""

import uuid  # Python's built-in module for generating unique identifiers
from datetime import datetime, timezone  # For timestamps with timezone awareness

from sqlalchemy import String, DateTime  # Column types for database
from sqlalchemy.dialects.postgresql import UUID  # PostgreSQL-specific UUID type
from sqlalchemy.orm import Mapped, mapped_column, relationship  # SQLAlchemy 2.0 ORM tools

from app.db.base import Base  # Our declarative base class that all models inherit from


class User(Base):
    """
    SQLAlchemy ORM model for the 'users' table.
    
    This represents a Jarvis user who can:
    - Register and log in with email/password
    - Own and control multiple display devices
    - Send voice/text commands from the iOS app
    """
    
    # The actual table name in PostgreSQL
    __tablename__ = "users"

    # ---------------------------------------------------------------------------
    # PRIMARY KEY
    # ---------------------------------------------------------------------------
    # id: Unique identifier for each user
    # - UUID (Universally Unique Identifier) is better than auto-increment integers
    #   because it's globally unique, doesn't expose user count, and works in distributed systems
    # - as_uuid=True: Store as native PostgreSQL UUID type (more efficient)
    # - primary_key=True: This is the table's primary key
    # - default=uuid.uuid4: Automatically generate a new UUID when creating a user
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ---------------------------------------------------------------------------
    # USER CREDENTIALS
    # ---------------------------------------------------------------------------
    # email: User's email address for login
    # - String(255): VARCHAR with max 255 characters (standard email length)
    # - unique=True: No two users can have the same email
    # - index=True: Create a database index for fast lookups (important for login)
    # - nullable=False: Email is required, cannot be NULL
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # hashed_password: Bcrypt hash of the user's password
    # - We NEVER store plain text passwords for security
    # - String(255): Bcrypt hashes are ~60 chars, 255 gives buffer for algorithm changes
    # - nullable=False: Password is required
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # ---------------------------------------------------------------------------
    # PROFILE INFORMATION
    # ---------------------------------------------------------------------------
    # display_name: Optional friendly name shown in the app (e.g., "Victor")
    # - String(100): Max 100 characters for the name
    # - nullable=True: This field is optional
    # - Mapped[str | None]: Python type hint indicating it can be str or None
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ---------------------------------------------------------------------------
    # ACCOUNT STATUS
    # ---------------------------------------------------------------------------
    # is_active: Whether the account is enabled
    # - default=True: New accounts are active by default
    # - Can be set to False to disable an account without deleting it
    # - Login will be rejected if is_active=False
    is_active: Mapped[bool] = mapped_column(default=True)

    # ---------------------------------------------------------------------------
    # TIMESTAMPS
    # ---------------------------------------------------------------------------
    # created_at: When the user registered
    # - DateTime(timezone=True): Store with timezone info (always use UTC)
    # - default=lambda: ...: Called when a new row is inserted
    # - datetime.now(timezone.utc): Current time in UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # updated_at: When the user record was last modified
    # - default: Set to now on creation
    # - onupdate: Automatically updated whenever the row changes
    # - Useful for debugging and audit trails
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ---------------------------------------------------------------------------
    # RELATIONSHIPS
    # ---------------------------------------------------------------------------
    # devices: One-to-many relationship with Device model
    # - A user can own multiple devices (screens/TVs)
    # - Mapped[list["Device"]]: Python type hint for a list of Device objects
    # - relationship("Device", ...): SQLAlchemy relationship definition
    # - back_populates="owner": The Device model has an 'owner' attribute pointing back here
    # - This enables: user.devices to get all devices, and device.owner to get the user
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="owner")
