"""
User schemas - Pydantic models for user-related API responses.
These control what user data is exposed in API responses (never the password!).
"""

import uuid  # For UUID type hint
from datetime import datetime  # For timestamp type hint

from pydantic import BaseModel, EmailStr  # Pydantic base and email type


class UserOut(BaseModel):
    """
    Schema for user data in API responses.
    
    This is used as response_model in endpoints like:
    - POST /auth/register (returns the created user)
    - GET /users/me (returns current user profile)
    
    IMPORTANT: This schema intentionally EXCLUDES sensitive fields:
    - hashed_password: Never expose password hashes
    - updated_at: Not typically needed by clients
    
    Example response:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "victor@example.com",
        "display_name": "Victor",
        "is_active": true,
        "created_at": "2025-12-02T10:30:00Z"
    }
    """
    
    # id: The user's unique identifier
    # - uuid.UUID: Python's UUID type, serialized as string in JSON
    id: uuid.UUID
    
    # email: The user's email address
    # - EmailStr: Validated email format
    email: EmailStr
    
    # display_name: User's friendly display name
    # - Can be None if user didn't set one during registration
    display_name: str | None
    
    # is_active: Whether the account is enabled
    # - False means account is deactivated (can't log in)
    is_active: bool
    
    # created_at: When the user registered
    # - datetime: Serialized as ISO 8601 string in JSON
    created_at: datetime

    class Config:
        """
        Pydantic model configuration.
        """
        # from_attributes=True: Allows creating this schema from SQLAlchemy ORM objects
        # 
        # Without this, you'd have to manually convert:
        #   return UserOut(id=user.id, email=user.email, ...)
        # 
        # With this, you can just return the ORM object:
        #   return user  # Pydantic reads attributes from the User object
        # 
        # This is why routes can do: return user (SQLAlchemy model)
        # and FastAPI automatically converts it to the UserOut JSON format
        from_attributes = True
