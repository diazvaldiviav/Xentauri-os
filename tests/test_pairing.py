"""
Tests for the pairing service.

These tests verify:
- Pairing code generation
- Code validation
- Code consumption (one-time use)
- Code expiration
- Multiple codes per device handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.pairing import PairingService


class TestPairingCodeGeneration:
    """Tests for pairing code generation."""
    
    def test_generate_code_format(self):
        """Should generate a 6-character alphanumeric code."""
        service = PairingService()
        device_id = uuid4()
        
        code, expires_at = service.generate_code(device_id)
        
        assert len(code) == 6
        assert code.isalnum()
        assert code.isupper()
    
    def test_generate_code_expiration(self):
        """Should set expiration 15 minutes in the future."""
        service = PairingService()
        device_id = uuid4()
        
        before = datetime.now(timezone.utc)
        code, expires_at = service.generate_code(device_id)
        after = datetime.now(timezone.utc)
        
        # Should expire in 15 minutes (with small tolerance)
        expected_min = before + timedelta(minutes=15)
        expected_max = after + timedelta(minutes=15)
        
        assert expected_min <= expires_at <= expected_max
    
    def test_generate_unique_codes(self):
        """Should generate unique codes for different devices."""
        service = PairingService()
        
        code1, _ = service.generate_code(uuid4())
        code2, _ = service.generate_code(uuid4())
        code3, _ = service.generate_code(uuid4())
        
        # All codes should be different
        assert len({code1, code2, code3}) == 3
    
    def test_regenerate_invalidates_old_code(self):
        """Should invalidate old code when generating new one for same device."""
        service = PairingService()
        device_id = uuid4()
        
        old_code, _ = service.generate_code(device_id)
        new_code, _ = service.generate_code(device_id)
        
        # Old code should no longer work
        assert service.validate_code(old_code) is None
        
        # New code should work
        assert service.validate_code(new_code) == device_id


class TestPairingCodeValidation:
    """Tests for pairing code validation."""
    
    def test_validate_valid_code(self):
        """Should return device_id for valid code."""
        service = PairingService()
        device_id = uuid4()
        
        code, _ = service.generate_code(device_id)
        
        result = service.validate_code(code)
        
        assert result == device_id
    
    def test_validate_code_case_insensitive(self):
        """Should accept lowercase code."""
        service = PairingService()
        device_id = uuid4()
        
        code, _ = service.generate_code(device_id)
        
        # Validate with lowercase
        result = service.validate_code(code.lower())
        
        assert result == device_id
    
    def test_validate_invalid_code(self):
        """Should return None for non-existent code."""
        service = PairingService()
        
        result = service.validate_code("ABCDEF")
        
        assert result is None
    
    def test_validate_expired_code(self):
        """Should return None for expired code."""
        service = PairingService()
        device_id = uuid4()
        
        code, _ = service.generate_code(device_id)
        
        # Manually expire the code
        service._codes[code]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        result = service.validate_code(code)
        
        assert result is None


class TestPairingCodeConsumption:
    """Tests for pairing code consumption (one-time use)."""
    
    def test_consume_valid_code(self):
        """Should return device_id and delete code."""
        service = PairingService()
        device_id = uuid4()
        
        code, _ = service.generate_code(device_id)
        
        # Consume the code
        result = service.consume_code(code)
        
        assert result == device_id
        
        # Code should no longer exist
        assert service.validate_code(code) is None
    
    def test_consume_code_only_once(self):
        """Should only work once."""
        service = PairingService()
        device_id = uuid4()
        
        code, _ = service.generate_code(device_id)
        
        # First consumption should work
        result1 = service.consume_code(code)
        assert result1 == device_id
        
        # Second consumption should fail
        result2 = service.consume_code(code)
        assert result2 is None
    
    def test_consume_invalid_code(self):
        """Should return None for invalid code."""
        service = PairingService()
        
        result = service.consume_code("INVALID")
        
        assert result is None


class TestPairingCodeCleanup:
    """Tests for expired code cleanup."""
    
    def test_cleanup_expired_codes(self):
        """Should remove expired codes."""
        service = PairingService()
        
        # Generate some codes
        code1, _ = service.generate_code(uuid4())
        code2, _ = service.generate_code(uuid4())
        code3, _ = service.generate_code(uuid4())
        
        # Expire two of them
        service._codes[code1]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        service._codes[code2]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        # Run cleanup
        removed = service.cleanup_expired()
        
        assert removed == 2
        
        # Only code3 should remain
        assert code1 not in service._codes
        assert code2 not in service._codes
        assert code3 in service._codes
