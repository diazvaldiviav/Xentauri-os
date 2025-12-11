"""
Content Token Service - Generates signed tokens for content URLs.

This service creates short-lived, signed tokens that allow the simulator
iframe to access protected content endpoints like /cloud/calendar.

Why this is needed:
- iframes cannot send Authorization headers
- We need to pass authentication via URL query parameter
- Token is signed with SECRET_KEY so it can't be forged
- Token expires quickly (5 minutes) for security

Usage:
    from app.services.content_token import content_token_service
    
    # Generate token
    token = content_token_service.generate(user_id)
    url = f"/cloud/calendar?token={token}"
    
    # Validate token
    user_id = content_token_service.validate(token)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError

from app.core.config import settings


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Token expires in 5 minutes (enough to load content, short enough for security)
CONTENT_TOKEN_EXPIRE_MINUTES = 5


# ---------------------------------------------------------------------------
# CONTENT TOKEN SERVICE
# ---------------------------------------------------------------------------

class ContentTokenService:
    """
    Service for generating and validating content access tokens.
    
    These tokens are used for iframe-based content loading where
    traditional Authorization headers cannot be used.
    """
    
    def generate(self, user_id: UUID, content_type: str = "calendar") -> str:
        """
        Generate a signed content access token.
        
        Args:
            user_id: The user ID to encode in the token
            content_type: Type of content (for future use: calendar, dashboard, etc.)
            
        Returns:
            Signed JWT token string
        """
        expire = datetime.now(timezone.utc) + timedelta(minutes=CONTENT_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": str(user_id),
            "type": "content",
            "content_type": content_type,
            "exp": expire,
        }
        
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return token
    
    def validate(self, token: str) -> Optional[UUID]:
        """
        Validate a content access token and extract the user ID.
        
        Args:
            token: The JWT token to validate
            
        Returns:
            User ID if valid, None if invalid or expired
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            
            # Verify this is a content token
            if payload.get("type") != "content":
                return None
            
            user_id_str = payload.get("sub")
            if not user_id_str:
                return None
            
            return UUID(user_id_str)
            
        except JWTError:
            return None
        except ValueError:
            # Invalid UUID
            return None


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

content_token_service = ContentTokenService()
