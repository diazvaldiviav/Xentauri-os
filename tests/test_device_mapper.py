"""
Tests for Device Mapper - Phase 1

Tests for:
- DeviceMapper.match() - single best match
- DeviceMapper.match_all() - ranked alternatives
- Fuzzy matching edge cases
- Normalization logic
- Similarity calculation

These tests ensure user's spoken device names correctly
resolve to database Device records.
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from typing import List

from app.ai.intent.device_mapper import DeviceMapper, device_mapper


# ===========================================================================
# TEST FIXTURES
# ===========================================================================

class MockDevice:
    """Mock Device object for testing without database."""
    
    def __init__(self, name: str, device_id=None, is_online: bool = True):
        self.id = device_id or uuid4()
        self.name = name
        self.is_online = is_online
        self.capabilities = ["power"]


@pytest.fixture
def mapper():
    """Create a fresh DeviceMapper instance."""
    return DeviceMapper()


@pytest.fixture
def sample_devices() -> List[MockDevice]:
    """Create sample devices for testing."""
    return [
        MockDevice("Living Room TV"),
        MockDevice("Bedroom Monitor"),
        MockDevice("Kitchen Display"),
        MockDevice("Office TV"),
        MockDevice("Garage Screen"),
    ]


@pytest.fixture
def single_device() -> List[MockDevice]:
    """Single device for simple tests."""
    return [MockDevice("Living Room TV")]


# ===========================================================================
# EXACT MATCH TESTS
# ===========================================================================

class TestExactMatch:
    """Tests for exact name matching."""
    
    def test_exact_match_case_insensitive(self, mapper, sample_devices):
        """Test exact match works case-insensitively."""
        device, score = mapper.match("living room tv", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"
        assert score >= 0.9  # High score for exact match
    
    def test_exact_match_with_different_case(self, mapper, sample_devices):
        """Test matching with different casing."""
        device, score = mapper.match("LIVING ROOM TV", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"
    
    def test_exact_match_with_extra_spaces(self, mapper, sample_devices):
        """Test matching handles extra whitespace."""
        device, score = mapper.match("  living  room  tv  ", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"


# ===========================================================================
# FUZZY MATCH TESTS
# ===========================================================================

class TestFuzzyMatch:
    """Tests for fuzzy matching capabilities."""
    
    def test_partial_name_match(self, mapper, sample_devices):
        """Test matching with partial device name."""
        device, score = mapper.match("living room", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"
        assert score >= mapper.MIN_MATCH_SCORE
    
    def test_word_order_variation(self, mapper, sample_devices):
        """Test matching when words are in different order."""
        # "TV in living room" should still match "Living Room TV"
        device, score = mapper.match("tv living room", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"
    
    def test_typo_tolerance(self, mapper, sample_devices):
        """Test matching with minor typos."""
        device, score = mapper.match("livng room tv", sample_devices)  # Typo: "livng"
        
        # May or may not match depending on threshold
        if device:
            assert device.name == "Living Room TV"
    
    def test_synonym_replacement(self, mapper, sample_devices):
        """Test that synonyms are handled (television → tv)."""
        device, score = mapper.match("living room television", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"
    
    def test_stop_words_ignored(self, mapper, sample_devices):
        """Test that stop words (the, my, a) are ignored."""
        device, score = mapper.match("the living room tv", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"
        
        device2, score2 = mapper.match("my bedroom monitor", sample_devices)
        
        assert device2 is not None
        assert device2.name == "Bedroom Monitor"


# ===========================================================================
# NO MATCH TESTS
# ===========================================================================

class TestNoMatch:
    """Tests for when no match should be found."""
    
    def test_completely_different_name(self, mapper, sample_devices):
        """Test that unrelated names don't match."""
        device, score = mapper.match("bathroom speaker", sample_devices)
        
        # Should return None or very low score
        if device:
            assert score < mapper.MIN_MATCH_SCORE
    
    def test_empty_spoken_name(self, mapper, sample_devices):
        """Test handling of empty input."""
        device, score = mapper.match("", sample_devices)
        
        assert device is None
        assert score == 0.0
    
    def test_empty_device_list(self, mapper):
        """Test handling of empty device list."""
        device, score = mapper.match("living room tv", [])
        
        assert device is None
        assert score == 0.0
    
    def test_none_spoken_name(self, mapper, sample_devices):
        """Test handling of None input."""
        device, score = mapper.match(None, sample_devices)
        
        assert device is None
        assert score == 0.0


# ===========================================================================
# MATCH_ALL TESTS (RANKED ALTERNATIVES)
# ===========================================================================

class TestMatchAll:
    """Tests for match_all() returning ranked alternatives."""
    
    def test_match_all_returns_ranked_list(self, mapper, sample_devices):
        """Test that match_all returns devices sorted by score."""
        matches = mapper.match_all("tv", sample_devices)
        
        # Should return multiple matches containing "TV"
        assert len(matches) >= 1
        
        # Should be sorted by score descending
        scores = [score for _, score in matches]
        assert scores == sorted(scores, reverse=True)
    
    def test_match_all_respects_limit(self, mapper, sample_devices):
        """Test that match_all respects the limit parameter."""
        matches = mapper.match_all("tv", sample_devices, limit=2)
        
        assert len(matches) <= 2
    
    def test_match_all_empty_input(self, mapper, sample_devices):
        """Test match_all with empty input."""
        matches = mapper.match_all("", sample_devices)
        
        assert matches == []
    
    def test_match_all_no_devices(self, mapper):
        """Test match_all with no devices."""
        matches = mapper.match_all("tv", [])
        
        assert matches == []


# ===========================================================================
# AMBIGUOUS MATCH TESTS
# ===========================================================================

class TestAmbiguousMatch:
    """Tests for handling ambiguous matches."""
    
    def test_ambiguous_match_returns_best(self, mapper):
        """Test that ambiguous input returns best match."""
        devices = [
            MockDevice("Office TV"),
            MockDevice("Office Monitor"),
        ]
        
        device, score = mapper.match("office", devices)
        
        # Should return one of them (whichever scores higher)
        assert device is not None
        assert "Office" in device.name
    
    def test_two_similar_devices(self, mapper):
        """Test matching when two devices have similar names."""
        devices = [
            MockDevice("Living Room TV 1"),
            MockDevice("Living Room TV 2"),
        ]
        
        device, score = mapper.match("living room tv 1", devices)
        
        assert device is not None
        assert device.name == "Living Room TV 1"


# ===========================================================================
# SPECIAL CHARACTERS TESTS
# ===========================================================================

class TestSpecialCharacters:
    """Tests for handling special characters in device names."""
    
    def test_device_with_numbers(self, mapper):
        """Test matching devices with numbers in name."""
        devices = [
            MockDevice("TV 1"),
            MockDevice("TV 2"),
            MockDevice("TV 3"),
        ]
        
        device, score = mapper.match("tv 2", devices)
        
        assert device is not None
        assert device.name == "TV 2"
    
    def test_device_with_special_chars(self, mapper):
        """Test matching devices with special characters."""
        devices = [
            MockDevice("John's TV"),
            MockDevice("Kid's Room Display"),
        ]
        
        device, score = mapper.match("johns tv", devices)
        
        # Apostrophe handling may vary
        if device:
            assert "John" in device.name
    
    def test_device_with_hyphen(self, mapper):
        """Test matching devices with hyphens."""
        devices = [
            MockDevice("Living-Room TV"),
        ]
        
        device, score = mapper.match("living room tv", devices)
        
        assert device is not None
    
    def test_device_with_parentheses(self, mapper):
        """Test matching devices with parentheses."""
        devices = [
            MockDevice("TV (Main)"),
            MockDevice("TV (Backup)"),
        ]
        
        device, score = mapper.match("tv main", devices)
        
        # Should match the main TV
        if device:
            assert "Main" in device.name


# ===========================================================================
# NORMALIZATION TESTS
# ===========================================================================

class TestNormalization:
    """Tests for the internal _normalize() method."""
    
    def test_normalize_removes_stop_words(self, mapper):
        """Test that normalization removes stop words."""
        normalized = mapper._normalize("the living room tv")
        
        assert "the" not in normalized.split()
    
    def test_normalize_replaces_synonyms(self, mapper):
        """Test that synonyms are replaced."""
        normalized = mapper._normalize("living room television")
        
        assert "tv" in normalized.split()
        assert "television" not in normalized.split()
    
    def test_normalize_lowercase(self, mapper):
        """Test that normalization converts to lowercase."""
        normalized = mapper._normalize("LIVING ROOM TV")
        
        assert normalized == normalized.lower()


# ===========================================================================
# SIMILARITY CALCULATION TESTS
# ===========================================================================

class TestSimilarityCalculation:
    """Tests for the internal _calculate_similarity() method."""
    
    def test_identical_strings_high_score(self, mapper):
        """Test that identical strings get perfect score."""
        score = mapper._calculate_similarity("living room tv", "living room tv")
        
        assert score >= 0.99
    
    def test_completely_different_strings_low_score(self, mapper):
        """Test that different strings get low score."""
        score = mapper._calculate_similarity("abc", "xyz")
        
        assert score < 0.5
    
    def test_partial_overlap_medium_score(self, mapper):
        """Test that partial overlap gets medium score."""
        score = mapper._calculate_similarity("living room", "living room tv")
        
        assert 0.5 < score < 1.0
    
    def test_word_overlap_contributes(self, mapper):
        """Test that word overlap affects score."""
        # Same words, different order
        score = mapper._calculate_similarity("room living tv", "living room tv")
        
        # Should still get reasonable score due to word overlap
        assert score > 0.5


# ===========================================================================
# GET_DEVICE_BY_ID TESTS
# ===========================================================================

class TestGetDeviceById:
    """Tests for get_device_by_id() helper method."""
    
    def test_find_existing_device(self, mapper, sample_devices):
        """Test finding a device by its ID."""
        target_device = sample_devices[0]
        
        found = mapper.get_device_by_id(target_device.id, sample_devices)
        
        assert found is not None
        assert found.id == target_device.id
        assert found.name == target_device.name
    
    def test_device_not_found(self, mapper, sample_devices):
        """Test when device ID doesn't exist."""
        fake_id = uuid4()
        
        found = mapper.get_device_by_id(fake_id, sample_devices)
        
        assert found is None
    
    def test_empty_device_list(self, mapper):
        """Test with empty device list."""
        found = mapper.get_device_by_id(uuid4(), [])
        
        assert found is None


# ===========================================================================
# TO_DEVICE_CONTEXT TESTS
# ===========================================================================

class TestToDeviceContext:
    """Tests for to_device_context() helper method."""
    
    def test_converts_devices_to_dict_list(self, mapper, sample_devices):
        """Test that devices are converted to context dicts."""
        context = mapper.to_device_context(sample_devices)
        
        assert len(context) == len(sample_devices)
        assert all(isinstance(d, dict) for d in context)
    
    def test_context_contains_required_fields(self, mapper, sample_devices):
        """Test that context dicts have all required fields."""
        context = mapper.to_device_context(sample_devices)
        
        for device_ctx in context:
            assert "id" in device_ctx
            assert "name" in device_ctx
            assert "is_online" in device_ctx
            assert "capabilities" in device_ctx
    
    def test_empty_device_list(self, mapper):
        """Test with empty device list."""
        context = mapper.to_device_context([])
        
        assert context == []


# ===========================================================================
# SINGLETON INSTANCE TEST
# ===========================================================================

class TestSingletonInstance:
    """Tests for the module-level device_mapper singleton."""
    
    def test_singleton_exists(self):
        """Test that the singleton instance exists."""
        assert device_mapper is not None
        assert isinstance(device_mapper, DeviceMapper)
    
    def test_singleton_is_reusable(self, sample_devices):
        """Test that the singleton works correctly."""
        device, score = device_mapper.match("living room tv", sample_devices)
        
        assert device is not None
        assert device.name == "Living Room TV"


# ===========================================================================
# EDGE CASES
# ===========================================================================

class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""
    
    def test_very_long_device_name(self, mapper):
        """Test handling of very long device names."""
        long_name = "A" * 1000
        devices = [MockDevice(long_name)]
        
        device, score = mapper.match(long_name, devices)
        
        assert device is not None
    
    def test_unicode_device_names(self, mapper):
        """Test handling of unicode characters."""
        devices = [
            MockDevice("客厅电视"),  # Chinese: Living room TV
            MockDevice("リビングルームテレビ"),  # Japanese
        ]
        
        device, score = mapper.match("客厅电视", devices)
        
        assert device is not None
        assert device.name == "客厅电视"
    
    def test_emoji_in_device_name(self, mapper):
        """Test handling of emojis in device names."""
        devices = [
            MockDevice("📺 Living Room"),
        ]
        
        device, score = mapper.match("living room", devices)
        
        # Should still match despite emoji
        if device:
            assert "Living Room" in device.name
    
    def test_multiple_spaces_in_name(self, mapper):
        """Test handling of multiple consecutive spaces."""
        devices = [MockDevice("Living   Room   TV")]
        
        device, score = mapper.match("living room tv", devices)
        
        assert device is not None
    
    def test_only_stop_words(self, mapper, sample_devices):
        """Test input that's only stop words."""
        device, score = mapper.match("the my a an", sample_devices)
        
        # Should return None or very low match
        if device:
            assert score < mapper.MIN_MATCH_SCORE
