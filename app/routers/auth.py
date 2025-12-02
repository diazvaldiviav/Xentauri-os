"""
Auth router - handles user registration and login endpoints.
These are public endpoints (no authentication required).
"""

from fastapi import APIRouter, Depends, HTTPException, status  # FastAPI components
from sqlalchemy.orm import Session  # Database session type

from app.db.session import get_db  # Dependency that provides a database session
from app.models.user import User  # User ORM model
from app.schemas.auth import UserRegister, UserLogin, Token  # Pydantic schemas for request/response
from app.schemas.user import UserOut  # Pydantic schema for user output (without password)
from app.core.security import hash_password, verify_password, create_access_token  # Security utilities

# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
# Create an APIRouter instance for auth-related endpoints
# - prefix="/auth": All routes here will be under /auth (e.g., /auth/register)
# - tags=["auth"]: Groups these endpoints together in the OpenAPI docs
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/register - Create a new user account
# ---------------------------------------------------------------------------
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Args:
        payload: UserRegister schema containing email, password, and optional display_name
                 FastAPI automatically validates the request body against this schema
        db: Database session, injected by FastAPI's dependency injection via Depends(get_db)
    
    Returns:
        UserOut: The created user's public information (without password)
    
    Raises:
        400 Bad Request: If email is already registered
    """
    
    # Step 1: Check if a user with this email already exists
    # - Query the users table, filter by email, get the first match (or None)
    existing = db.query(User).filter(User.email == payload.email).first()
    
    # Step 2: If email exists, reject the registration
    # - We don't want duplicate accounts with the same email
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # 400 = client error
            detail="Email already registered",  # Message returned to client
        )

    # Step 3: Create a new User instance
    # - hash_password(): Convert plain text password to bcrypt hash (never store plain passwords!)
    # - display_name is optional, so it might be None
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
    )
    
    # Step 4: Add the user to the database session (stages it for insertion)
    db.add(user)
    
    # Step 5: Commit the transaction (actually writes to the database)
    db.commit()
    
    # Step 6: Refresh the user object to get database-generated values (id, created_at, etc.)
    db.refresh(user)
    
    # Step 7: Return the user (FastAPI converts it to JSON using UserOut schema)
    return user


# ---------------------------------------------------------------------------
# POST /auth/login - Authenticate and get a JWT token
# ---------------------------------------------------------------------------
@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.
    
    Args:
        payload: UserLogin schema containing email and password
        db: Database session from dependency injection
    
    Returns:
        Token: Contains access_token (JWT string) and token_type ("bearer")
    
    Raises:
        401 Unauthorized: If email doesn't exist or password is wrong
        403 Forbidden: If the account is deactivated
    
    The iOS app will:
    1. Call this endpoint with email/password
    2. Store the returned JWT token securely (Keychain)
    3. Include the token in the Authorization header for all subsequent requests
    """
    
    # Step 1: Look up the user by email
    user = db.query(User).filter(User.email == payload.email).first()
    
    # Step 2: Verify credentials
    # - If user doesn't exist OR password doesn't match the hash, reject
    # - We use the same error message for both cases to prevent email enumeration attacks
    #   (attackers can't tell if an email exists or if just the password is wrong)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # 401 = not authenticated
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},  # Standard header for bearer token auth
        )

    # Step 3: Check if the account is active
    # - Admins can deactivate accounts without deleting them
    # - Deactivated users cannot log in
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 403 = authenticated but not allowed
            detail="Account is inactive",
        )

    # Step 4: Generate a JWT access token
    # - subject=str(user.id): The token contains the user's UUID as the "sub" claim
    # - This token will be validated on every protected request
    # - Token expires after ACCESS_TOKEN_EXPIRE_MINUTES (default 24 hours)
    access_token = create_access_token(subject=str(user.id))
    
    # Step 5: Return the token
    # - The iOS app stores this and sends it as: Authorization: Bearer <token>
    return Token(access_token=access_token)
