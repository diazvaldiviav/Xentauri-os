"""
Auth schemas - Pydantic models for authentication request/response validation.
Pydantic models define the shape of data and automatically validate incoming requests.
"""

from pydantic import BaseModel, EmailStr  # BaseModel for schemas, EmailStr validates email format


class UserRegister(BaseModel):
    """
    Schema for POST /auth/register request body.
    
    Pydantic automatically:
    - Validates email format (must be valid email)
    - Validates types (email must be string, etc.)
    - Returns 422 Unprocessable Entity if validation fails
    
    Example request body:
    {
        "email": "victor@example.com",
        "password": "securePassword123",
        "display_name": "Victor"
    }
    """
    # email: User's email address
    # - EmailStr: Special Pydantic type that validates email format
    # - Invalid emails (like "not-an-email") return 422 error
    email: EmailStr
    
    # password: User's chosen password (plaintext from client)
    # - Will be hashed before storing in database
    # - TODO: Add password strength validation (min length, complexity)
    password: str
    
    # display_name: Optional friendly name
    # - str | None: Can be a string or None (null in JSON)
    # - = None: Default value if not provided in request
    display_name: str | None = None


class UserLogin(BaseModel):
    """
    Schema for POST /auth/login request body.
    
    Example request body:
    {
        "email": "victor@example.com",
        "password": "securePassword123"
    }
    """
    # email: The registered email address
    email: EmailStr
    
    # password: The user's password to verify
    password: str


class Token(BaseModel):
    """
    Schema for POST /auth/login response.
    
    Contains the JWT access token that clients use for authenticated requests.
    
    Example response:
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer"
    }
    
    The iOS app should:
    1. Store access_token securely in Keychain
    2. Include it in subsequent requests: Authorization: Bearer <access_token>
    """
    # access_token: The JWT token string
    access_token: str
    
    # token_type: Always "bearer" for Bearer token authentication
    # - Included for OAuth 2.0 compatibility
    # - Default value so we don't have to specify it every time
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """
    Schema for decoded JWT payload (used internally).
    
    When we decode a JWT, we get a payload like:
    {
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "exp": 1701500000
    }
    
    This schema helps validate the payload structure.
    Not directly used in API responses, but useful for type hints.
    """
    # sub: Subject claim - the user's UUID as a string
    # - Can be None if token is malformed
    sub: str | None = None
