"""
Test configuration and fixtures for pytest.

This module provides shared fixtures used across all tests:
- Test database (SQLite in-memory for speed)
- Test client (FastAPI TestClient)
- Authentication helpers
- Sample data factories
"""

import pytest
from datetime import datetime, timezone
from typing import Generator
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User
from app.models.device import Device
from app.core.security import hash_password, create_access_token


# ---------------------------------------------------------------------------
# TEST DATABASE SETUP
# ---------------------------------------------------------------------------
# Use SQLite in-memory for fast tests (no PostgreSQL dependency)
# StaticPool keeps the same connection across all operations

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    poolclass=StaticPool,  # Keep connection alive across operations
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# DATABASE FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a fresh database for each test function.
    
    - Creates all tables
    - Yields a session for the test
    - Drops all tables after test (clean slate)
    """
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create a session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Drop all tables for clean slate
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with the test database.
    
    Overrides the get_db dependency to use our test database.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# USER FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def test_user(db: Session) -> User:
    """
    Create a test user in the database.
    
    Returns:
        User with email "test@example.com" and password "testpassword"
    """
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password=hash_password("testpassword"),
        display_name="Test User",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_user_token(test_user: User) -> str:
    """
    Create a JWT token for the test user.
    
    Returns:
        JWT access token string
    """
    return create_access_token(subject=str(test_user.id))


@pytest.fixture
def auth_headers(test_user_token: str) -> dict:
    """
    Create authorization headers with the test user's token.
    
    Returns:
        Dict with Authorization header
    """
    return {"Authorization": f"Bearer {test_user_token}"}


# ---------------------------------------------------------------------------
# DEVICE FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def test_device(db: Session, test_user: User) -> Device:
    """
    Create a test device for the test user.
    
    Returns:
        Device named "Test TV" belonging to test_user
    """
    device = Device(
        id=uuid4(),
        user_id=test_user.id,
        name="Test TV",
        agent_id=None,  # Not paired
        capabilities=None,
        is_online=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@pytest.fixture
def paired_device(db: Session, test_user: User) -> Device:
    """
    Create a paired test device (has agent_id).
    
    Returns:
        Device with agent_id set
    """
    device = Device(
        id=uuid4(),
        user_id=test_user.id,
        name="Paired TV",
        agent_id="test-agent-123",
        capabilities={"power": True, "volume": True},
        is_online=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device
