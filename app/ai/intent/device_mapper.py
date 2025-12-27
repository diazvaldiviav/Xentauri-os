"""
Device Mapper - Maps friendly device names to device IDs.

This module handles the resolution of device names from natural language
to actual Device records in the database.

Problem it Solves:
=================
Users say things like:
- "living room TV"
- "the TV in the living room"
- "Living Room Television"
- "livingroom tv"

We need to match these to: Device(id=uuid, name="Living Room TV")

Matching Strategies:
===================
1. Exact match (case-insensitive)
2. Fuzzy match (Levenshtein distance)
3. Token matching (word overlap)
4. Alias support (future: "my TV" → "Living Room TV")
"""

import logging
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.device import Device

logger = logging.getLogger("jarvis.ai.device_mapper")


class DeviceMapper:
    """
    Maps device names from natural language to database records.
    
    This class provides fuzzy matching capabilities to handle
    variations in how users refer to their devices.
    
    Usage:
        mapper = DeviceMapper()
        
        # Get user's devices from database
        devices = db.query(Device).filter(Device.user_id == user_id).all()
        
        # Match a spoken name to a device
        device, score = mapper.match("living room tv", devices)
        if device:
            print(f"Matched: {device.name} (confidence: {score})")
    """
    
    # Minimum similarity score to consider a match
    MIN_MATCH_SCORE = 0.6
    
    # Common words to ignore in matching (English + Spanish)
    STOP_WORDS = {
        "the", "my", "a", "an", "in", "on", "at",  # English
        "de", "la", "el", "mi", "del", "en", "un", "una",  # Spanish
    }
    
    def __init__(self):
        """Initialize the device mapper."""
        logger.info("Device mapper initialized")
    
    def match(
        self,
        spoken_name: str,
        devices: List[Device],
    ) -> Tuple[Optional[Device], float]:
        """
        Match a spoken device name to a device record.
        
        Args:
            spoken_name: The name as spoken by the user
            devices: List of Device records to match against
            
        Returns:
            Tuple of (matched_device, confidence_score)
            Returns (None, 0.0) if no match found
        """
        if not devices:
            logger.warning("No devices provided for matching")
            return None, 0.0
        
        if not spoken_name:
            logger.warning("Empty device name provided")
            return None, 0.0
        
        # Normalize the spoken name
        normalized_spoken = self._normalize(spoken_name)
        logger.debug(f"Matching '{spoken_name}' (normalized: '{normalized_spoken}')")
        
        best_match = None
        best_score = 0.0
        
        for device in devices:
            # Normalize device name
            normalized_device = self._normalize(device.name)
            
            # Calculate similarity score
            score = self._calculate_similarity(normalized_spoken, normalized_device)
            
            logger.debug(f"  '{device.name}' → score: {score:.2f}")
            
            if score > best_score:
                best_score = score
                best_match = device
        
        # Check if score meets threshold
        if best_score >= self.MIN_MATCH_SCORE:
            logger.info(f"Matched '{spoken_name}' to '{best_match.name}' (score: {best_score:.2f})")
            return best_match, best_score
        else:
            logger.warning(f"No match found for '{spoken_name}' (best score: {best_score:.2f})")
            return None, best_score
    
    def match_all(
        self,
        spoken_name: str,
        devices: List[Device],
        limit: int = 3,
    ) -> List[Tuple[Device, float]]:
        """
        Get all potential matches ranked by score.
        
        Useful for presenting alternatives when there's ambiguity.
        
        Args:
            spoken_name: The name as spoken by the user
            devices: List of Device records to match against
            limit: Maximum number of matches to return
            
        Returns:
            List of (device, score) tuples, sorted by score descending
        """
        if not devices or not spoken_name:
            return []
        
        normalized_spoken = self._normalize(spoken_name)
        
        # Score all devices
        scored = []
        for device in devices:
            normalized_device = self._normalize(device.name)
            score = self._calculate_similarity(normalized_spoken, normalized_device)
            if score > 0.3:  # Lower threshold for alternatives
                scored.append((device, score))
        
        # Sort by score descending and limit
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
    
    def _normalize(self, name: str) -> str:
        """
        Normalize a device name for comparison.
        
        - Convert to lowercase
        - Remove extra whitespace
        - Remove stop words
        - Translate Spanish terms to English
        - Sort words for word-order independence
        """
        # Lowercase and split into words
        words = name.lower().split()
        
        # Remove stop words
        words = [w for w in words if w not in self.STOP_WORDS]
        
        # English synonyms - e.g., "TV" vs "Television"
        word_map = {
            "television": "tv",
            "telly": "tv",
            "monitor": "display",
            "screen": "display",
        }
        
        # Spanish to English translations for common room/device terms
        spanish_translations = {
            # Device terms
            "pantalla": "display",
            "televisor": "tv",
            "tele": "tv",
            "televisión": "tv",
            # Room terms
            "sala": "living room",
            "salón": "living room",
            "salon": "living room",
            "cuarto": "room",
            "habitación": "room",
            "habitacion": "room",
            "dormitorio": "bedroom",
            "recámara": "bedroom",
            "recamara": "bedroom",
            "cocina": "kitchen",
            "oficina": "office",
            "estudio": "office",
            "baño": "bathroom",
            "bano": "bathroom",
        }
        
        # Apply English word mappings first
        words = [word_map.get(w, w) for w in words]
        
        # Apply Spanish translations
        translated = []
        for w in words:
            if w in spanish_translations:
                translation = spanish_translations[w]
                if translation:  # Non-empty translation
                    translated.extend(translation.split())
            else:
                translated.append(w)
        words = translated
        
        # Join back
        return " ".join(words)
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two normalized names.
        
        Uses a combination of:
        1. SequenceMatcher ratio (Levenshtein-like)
        2. Word overlap score
        """
        # Sequence matching (character-level similarity)
        seq_score = SequenceMatcher(None, name1, name2).ratio()
        
        # Word overlap (token-level similarity)
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if not words1 or not words2:
            return seq_score
        
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        word_score = overlap / total if total > 0 else 0
        
        # Combine scores (weighted average)
        combined = (seq_score * 0.6) + (word_score * 0.4)
        
        return combined
    
    def get_device_by_id(
        self,
        device_id: UUID,
        devices: List[Device],
    ) -> Optional[Device]:
        """
        Get a device by its ID from a list of devices.
        
        Args:
            device_id: The device UUID
            devices: List of Device records
            
        Returns:
            Device if found, None otherwise
        """
        for device in devices:
            if device.id == device_id:
                return device
        return None
    
    def to_device_context(self, devices: List[Device]) -> List[Dict[str, Any]]:
        """
        Convert devices to a context dict for prompts.
        
        Args:
            devices: List of Device records
            
        Returns:
            List of device info dicts
        """
        return [
            {
                "id": str(device.id),
                "name": device.name,
                "is_online": device.is_online,
                "capabilities": device.capabilities,
            }
            for device in devices
        ]


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
device_mapper = DeviceMapper()
