"""
Dependencies module - reusable FastAPI dependencies for route handlers.
The main dependency here is get_current_user which validates JWT tokens.
"""

import uuid  # For parsing user ID from token

from fastapi import Depends, HTTPException, status  # FastAPI components
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # Auth header extraction
from jose import JWTError, jwt  # JWT decoding and error handling
from sqlalchemy.orm import Session  # Database session type

from app.core.config import settings  # App configuration (SECRET_KEY, ALGORITHM)
from app.db.session import get_db  # Database session dependency
from app.models.user import User  # User ORM model

# ---------------------------------------------------------------------------
# SECURITY SCHEME
# ---------------------------------------------------------------------------
# HTTPBearer: Extracts tokens from the "Authorization: Bearer <token>" header
# - auto_error=True (default): Raises 401 if header is missing
# - This also adds the 🔒 lock icon in Swagger UI for protected endpoints
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate JWT token and return the authenticated user.
    
    This is a FastAPI dependency used to protect routes. Any route that
    includes `current_user: User = Depends(get_current_user)` will require
    a valid JWT token.
    
    Args:
        credentials: Extracted from "Authorization: Bearer <token>" header
                    FastAPI's HTTPBearer handles the extraction automatically
        db: Database session for querying the user
    
    Returns:
        User: The authenticated user object from the database
    
    Raises:
        401 Unauthorized: If token is missing, invalid, expired, or user not found
        403 Forbidden: If user account is deactivated
    
    Flow:
        1. Extract token from Authorization header
        2. Decode and validate JWT signature and expiration
        3. Extract user ID from token's "sub" claim
        4. Query database for the user
        5. Verify user exists and is active
        6. Return user object to the route handler
    """
    
    # Extract the actual token string from the credentials object
    # credentials.scheme = "Bearer", credentials.credentials = "<token>"
    token = credentials.credentials
    
    # Prepare the exception we'll raise for any auth failure
    # Using the same error for all cases prevents information leakage
    # (attackers can't tell if token was invalid vs user not found)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},  # Standard header per RFC 6750
    )

    try:
        # ---------------------------------------------------------------------------
        # STEP 1: Decode and validate the JWT
        # ---------------------------------------------------------------------------
        # jwt.decode does several things:
        # - Base64 decodes header and payload
        # - Verifies the signature using SECRET_KEY and ALGORITHM
        # - Checks the "exp" claim (raises ExpiredSignatureError if expired)
        # - Returns the payload as a dictionary
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        
        # ---------------------------------------------------------------------------
        # STEP 2: Extract user ID from the "sub" (subject) claim
        # ---------------------------------------------------------------------------
        # The "sub" claim contains the user's UUID as a string
        # We stored it during login in create_access_token(subject=str(user.id))
        user_id: str | None = payload.get("sub")
        
        # If no subject claim, token is malformed
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        # JWTError catches: ExpiredSignatureError, InvalidTokenError, etc.
        # All JWT-related errors result in 401
        raise credentials_exception

    try:
        # ---------------------------------------------------------------------------
        # STEP 3: Convert string user ID to UUID
        # ---------------------------------------------------------------------------
        # The token stores user ID as a string, but our database uses UUID type
        # uuid.UUID() validates the format and converts it
        uid = uuid.UUID(user_id)
    except ValueError:
        # If user_id isn't a valid UUID string, reject
        raise credentials_exception

    # ---------------------------------------------------------------------------
    # STEP 4: Look up the user in the database
    # ---------------------------------------------------------------------------
    # Query the users table by ID
    # .first() returns None if not found (vs .one() which would raise)
    user = db.query(User).filter(User.id == uid).first()
    
    # If user doesn't exist (was deleted after token was issued), reject
    if user is None:
        raise credentials_exception

    # ---------------------------------------------------------------------------
    # STEP 5: Check if user account is active
    # ---------------------------------------------------------------------------
    # Even with a valid token, deactivated users can't access the API
    # This allows admins to disable accounts without waiting for token expiration
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 403, not 401 (token is valid, just not authorized)
            detail="Account is inactive",
        )

    # ---------------------------------------------------------------------------
    # STEP 6: Return the authenticated user
    # ---------------------------------------------------------------------------
    # The route handler receives this User object
    # Example: def my_route(current_user: User = Depends(get_current_user))
    return user
