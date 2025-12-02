"""
Pairing service - handles device pairing code generation and validation.

This service manages the pairing flow between the iOS app and Raspberry Pi agents:
1. User creates a device → generates a 6-character pairing code
2. Code is displayed to user and stored temporarily (15 min TTL)
3. User enters code on Pi → Pi calls /devices/pair with the code
4. Service validates code and links agent_id to the device

Using in-memory storage for MVP simplicity. For production, use Redis.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID


class PairingService:
    """
    Manages pairing codes for device onboarding.
    
    Pairing codes are:
    - 6 characters, alphanumeric (uppercase)
    - Valid for 15 minutes
    - One-time use (deleted after successful pairing)
    
    Thread-safety note: For MVP, this is acceptable. 
    In production with multiple workers, use Redis instead.
    """
    
    # Code configuration
    CODE_LENGTH = 6
    CODE_CHARS = string.ascii_uppercase + string.digits  # A-Z, 0-9
    CODE_TTL_MINUTES = 15
    
    def __init__(self):
        # In-memory storage: pairing_code -> {device_id, expires_at}
        # Example: {"A1B2C3": {"device_id": UUID(...), "expires_at": datetime(...)}}
        self._codes: dict[str, dict] = {}
    
    def generate_code(self, device_id: UUID) -> tuple[str, datetime]:
        """
        Generate a new pairing code for a device.
        
        Args:
            device_id: UUID of the device to pair
        
        Returns:
            Tuple of (pairing_code, expires_at)
        
        Example:
            code, expires = pairing_service.generate_code(device.id)
            # code = "A1B2C3"
            # expires = datetime(2025, 12, 2, 10, 45, 0)
        """
        # Remove any existing code for this device (one code per device)
        self._remove_device_codes(device_id)
        
        # Generate a unique code
        code = self._generate_unique_code()
        
        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.CODE_TTL_MINUTES)
        
        # Store the code
        self._codes[code] = {
            "device_id": device_id,
            "expires_at": expires_at,
        }
        
        return code, expires_at
    
    def validate_code(self, pairing_code: str) -> Optional[UUID]:
        """
        Validate a pairing code and return the device ID if valid.
        
        This does NOT consume the code - call consume_code() after successful pairing.
        
        Args:
            pairing_code: The 6-character code to validate
        
        Returns:
            UUID of the device if code is valid, None otherwise
        
        Validation checks:
            1. Code exists in storage
            2. Code has not expired
        """
        # Normalize to uppercase
        code = pairing_code.upper()
        
        # Check if code exists
        if code not in self._codes:
            return None
        
        code_data = self._codes[code]
        
        # Check if code has expired
        if datetime.now(timezone.utc) > code_data["expires_at"]:
            # Clean up expired code
            del self._codes[code]
            return None
        
        return code_data["device_id"]
    
    def consume_code(self, pairing_code: str) -> Optional[UUID]:
        """
        Validate and consume a pairing code (one-time use).
        
        This is the main method for the pairing flow:
        1. Validates the code
        2. Returns the device ID
        3. Deletes the code so it can't be used again
        
        Args:
            pairing_code: The 6-character code to consume
        
        Returns:
            UUID of the device if code is valid, None otherwise
        """
        device_id = self.validate_code(pairing_code)
        
        if device_id is not None:
            # Delete the code (one-time use)
            code = pairing_code.upper()
            del self._codes[code]
        
        return device_id
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired pairing codes.
        
        Call this periodically to prevent memory leaks.
        For MVP, we'll call it on each generate_code().
        
        Returns:
            Number of codes removed
        """
        now = datetime.now(timezone.utc)
        expired_codes = [
            code for code, data in self._codes.items()
            if now > data["expires_at"]
        ]
        
        for code in expired_codes:
            del self._codes[code]
        
        return len(expired_codes)
    
    def _generate_unique_code(self) -> str:
        """
        Generate a unique 6-character alphanumeric code.
        
        Uses secrets module for cryptographically secure random generation.
        Retries if code already exists (extremely unlikely).
        """
        # Clean up expired codes first
        self.cleanup_expired()
        
        # Generate code, retry if collision (very rare)
        for _ in range(10):  # Max 10 attempts
            code = ''.join(secrets.choice(self.CODE_CHARS) for _ in range(self.CODE_LENGTH))
            if code not in self._codes:
                return code
        
        # This should never happen with 6-char codes (36^6 = 2 billion combinations)
        raise RuntimeError("Failed to generate unique pairing code")
    
    def _remove_device_codes(self, device_id: UUID) -> None:
        """
        Remove all existing codes for a device.
        
        Called when generating a new code to ensure only one code per device.
        """
        codes_to_remove = [
            code for code, data in self._codes.items()
            if data["device_id"] == device_id
        ]
        
        for code in codes_to_remove:
            del self._codes[code]


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance to use throughout the application.
# This ensures all requests share the same pairing code storage.
# 
# Usage: from app.services.pairing import pairing_service
pairing_service = PairingService()
