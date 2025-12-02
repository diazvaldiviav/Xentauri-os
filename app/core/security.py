"""
Security utilities - password hashing and JWT token creation.
These are the core security functions used by authentication endpoints.
"""

from datetime import datetime, timedelta, timezone  # For token expiration

from jose import jwt  # python-jose library for JWT encoding/decoding
from passlib.context import CryptContext  # Password hashing library

from app.core.config import settings  # App configuration

# ---------------------------------------------------------------------------
# PASSWORD HASHING CONTEXT
# ---------------------------------------------------------------------------
# CryptContext: Passlib's high-level interface for password hashing
# - schemes=["bcrypt"]: Use bcrypt algorithm (industry standard, slow by design)
# - deprecated="auto": If we add new schemes later, old hashes still work
# 
# Why bcrypt?
# - Intentionally slow (prevents brute-force attacks)
# - Includes salt automatically (prevents rainbow table attacks)
# - Adjustable cost factor (can be made slower as hardware improves)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    
    Args:
        password: The user's plaintext password (e.g., "mySecretPass123")
    
    Returns:
        A bcrypt hash string (e.g., "$2b$12$LQv3c1yqBw...")
        This is what gets stored in the database.
    
    Security notes:
        - Never log or print the plaintext password
        - The hash includes the salt, so same password → different hash each time
        - Hash is ~60 characters, one-way (cannot be reversed)
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored hash.
    
    Args:
        plain_password: The password the user just typed in
        hashed_password: The hash stored in the database from registration
    
    Returns:
        True if passwords match, False otherwise
    
    How it works:
        1. Extract the salt from the stored hash
        2. Hash the plaintext password with that same salt
        3. Compare the result with the stored hash
        4. Return True if they match (timing-safe comparison)
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT (JSON Web Token) access token.
    
    Args:
        subject: The token's subject claim - typically the user's ID
                 This is stored in the "sub" field of the JWT payload
        expires_delta: Optional custom expiration time
                      If None, uses ACCESS_TOKEN_EXPIRE_MINUTES from settings
    
    Returns:
        A signed JWT string (e.g., "eyJhbGciOiJIUzI1NiIs...")
    
    JWT Structure (3 parts separated by dots):
        1. Header: {"alg": "HS256", "typ": "JWT"} (base64 encoded)
        2. Payload: {"sub": "user-uuid", "exp": 1234567890} (base64 encoded)
        3. Signature: HMAC-SHA256(header + payload, SECRET_KEY)
    
    Security notes:
        - The payload is NOT encrypted, just base64 encoded (anyone can read it)
        - The signature proves the token wasn't tampered with
        - Only someone with SECRET_KEY can create valid signatures
        - Store tokens securely (iOS Keychain, not UserDefaults)
    """
    # Calculate expiration time
    # - Use provided delta, or default from settings
    # - Always use UTC to avoid timezone issues
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Build the JWT payload (claims)
    # - sub (subject): Who this token is for (user ID)
    # - exp (expiration): When the token expires (Unix timestamp)
    # - Other common claims: iat (issued at), iss (issuer), aud (audience)
    to_encode = {"sub": subject, "exp": expire}
    
    # Sign and encode the token
    # - jwt.encode creates the final "xxxxx.yyyyy.zzzzz" string
    # - Uses SECRET_KEY and ALGORITHM from settings
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
