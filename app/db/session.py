"""
Database session management - SQLAlchemy engine and session factory.
This module provides the database connection and session dependency for FastAPI.
"""

from sqlalchemy import create_engine  # Creates the database connection pool
from sqlalchemy.orm import sessionmaker  # Factory for creating database sessions

from app.core.config import settings  # App configuration with DATABASE_URL

# ---------------------------------------------------------------------------
# DATABASE ENGINE
# ---------------------------------------------------------------------------
# create_engine: Establishes the connection to PostgreSQL
# - settings.DATABASE_URL: Connection string from environment/config
#   Format: postgresql+psycopg://user:password@host:port/database
# 
# - pool_pre_ping=True: Before using a connection from the pool, send a
#   simple query ("SELECT 1") to check if the connection is still alive.
#   This prevents errors from stale connections (e.g., after DB restart).
#   Small performance cost, but much better reliability.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# ---------------------------------------------------------------------------
# SESSION FACTORY
# ---------------------------------------------------------------------------
# sessionmaker: Creates a factory that produces database sessions
# 
# - autocommit=False: Transactions don't auto-commit; you must call db.commit()
#   This gives you control over when changes are saved (important for error handling)
# 
# - autoflush=False: Don't automatically sync Python objects to DB before queries
#   More predictable behavior; you control when flushes happen
# 
# - bind=engine: All sessions use our PostgreSQL engine
# 
# SessionLocal is a class (factory), not an instance. Call SessionLocal() to get a session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that provides a database session.
    
    This is used with FastAPI's Depends() to inject a database session
    into route handlers. It ensures proper cleanup after each request.
    
    Usage in a route:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    
    How it works (generator pattern):
        1. Request comes in
        2. FastAPI calls get_db()
        3. We create a new Session: db = SessionLocal()
        4. We 'yield' it to the route handler (route executes here)
        5. Route finishes (success or exception)
        6. 'finally' block runs: db.close()
        7. Session is returned to the connection pool
    
    Why this pattern?
        - Guaranteed cleanup: close() always runs, even if route raises an exception
        - One session per request: prevents threading issues
        - Connection pooling: sessions are recycled efficiently
    """
    # Create a new database session
    db = SessionLocal()
    try:
        # Yield the session to the route handler
        # Execution pauses here while the route runs
        yield db
    finally:
        # Always close the session when done
        # This returns the connection to the pool
        db.close()
