"""
Users router - handles user profile endpoints.
All endpoints here require authentication (JWT token in Authorization header).
"""

from fastapi import APIRouter, Depends  # FastAPI components

from app.deps import get_current_user  # Dependency that validates JWT and returns the User
from app.models.user import User  # User ORM model
from app.schemas.user import UserOut  # Pydantic schema for user output

# ---------------------------------------------------------------------------
# ROUTER SETUP
# ---------------------------------------------------------------------------
# Create an APIRouter for user-related endpoints
# - prefix="/users": All routes here will be under /users (e.g., /users/me)
# - tags=["users"]: Groups these endpoints together in OpenAPI docs
router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# GET /users/me - Get the current user's profile
# ---------------------------------------------------------------------------
@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.
    
    This is a PROTECTED endpoint - requires a valid JWT token.
    
    How it works:
    1. Client sends request with header: Authorization: Bearer <jwt_token>
    2. FastAPI calls get_current_user dependency (from app/deps.py)
    3. get_current_user:
       - Extracts the token from the Authorization header
       - Decodes and validates the JWT
       - Extracts the user ID from the token's "sub" claim
       - Queries the database for that user
       - Returns the User object (or raises 401 if invalid)
    4. The User object is passed to this function as current_user
    5. We return it, and FastAPI serializes it using UserOut schema
    
    Args:
        current_user: The authenticated User object, injected by Depends(get_current_user)
                     If the token is invalid, this function never runs (401 is raised first)
    
    Returns:
        UserOut: The user's public profile (id, email, display_name, is_active, created_at)
                 Note: hashed_password is NOT included (UserOut schema excludes it)
    
    Use case:
        The iOS app calls this after login to display the user's profile
        and to verify the stored token is still valid.
    """
    # Simply return the user - FastAPI handles JSON serialization via UserOut
    return current_user
