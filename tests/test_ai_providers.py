"""
Tests for AI Providers - Base classes and mock LLM calls.

This module tests:
- TokenUsage dataclass
- AIResponse dataclass
- Provider type enum
- Mock provider behavior for integration testing

We mock LLM calls to ensure tests are:
- Fast (no network calls)
- Reliable (no API flakiness)
- Free (no token costs)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.ai.providers.base import (
    AIProvider,
    AIResponse,
    TokenUsage,
    ProviderType,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""
    
    def test_create_basic_usage(self):
        """Test creating token usage with all fields."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
    
    def test_auto_calculate_total(self):
        """Test that total is auto-calculated if not provided."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
        )
        
        assert usage.total_tokens == 150
    
    def test_default_values(self):
        """Test default values are zeros."""
        usage = TokenUsage()
        
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
    
    def test_total_overrides_calculation(self):
        """Test that explicit total is not recalculated when it's non-zero."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=200,  # Explicitly set different
        )
        
        # The explicit total should be preserved
        assert usage.total_tokens == 200


class TestAIResponse:
    """Tests for AIResponse dataclass."""
    
    def test_create_success_response(self):
        """Test creating a successful response."""
        response = AIResponse(
            content="Hello, world!",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
        )
        
        assert response.content == "Hello, world!"
        assert response.provider == ProviderType.GEMINI
        assert response.model == "gemini-1.5-flash"
        assert response.success is True
        assert response.error is None
    
    def test_create_error_response(self):
        """Test creating an error response."""
        response = AIResponse(
            content="",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
            success=False,
            error="Rate limit exceeded",
        )
        
        assert response.content == ""
        assert response.success is False
        assert response.error == "Rate limit exceeded"
    
    def test_response_with_usage(self):
        """Test response with token usage."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        
        response = AIResponse(
            content="Generated text",
            provider=ProviderType.ANTHROPIC,
            model="claude-3-haiku",
            usage=usage,
        )
        
        assert response.usage.prompt_tokens == 100
        assert response.usage.completion_tokens == 50
        assert response.usage.total_tokens == 150
    
    def test_response_with_latency(self):
        """Test response with latency tracking."""
        response = AIResponse(
            content="Fast response",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            latency_ms=250.5,
        )
        
        assert response.latency_ms == 250.5
    
    def test_response_with_metadata(self):
        """Test response with custom metadata."""
        response = AIResponse(
            content="With metadata",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
            metadata={"request_id": "abc123", "cached": True},
        )
        
        assert response.metadata["request_id"] == "abc123"
        assert response.metadata["cached"] is True
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        
        response = AIResponse(
            content="Test content",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            usage=usage,
            latency_ms=200.0,
        )
        
        result = response.to_dict()
        
        assert result["content"] == "Test content"
        assert result["provider"] == "gemini"
        assert result["model"] == "gemini-1.5-flash"
        assert result["tokens"]["prompt"] == 100
        assert result["tokens"]["completion"] == 50
        assert result["tokens"]["total"] == 150
        assert result["latency_ms"] == 200.0
        assert result["success"] is True
        assert result["error"] is None
    
    def test_to_dict_truncates_long_content(self):
        """Test that long content is truncated in to_dict."""
        long_content = "x" * 200
        
        response = AIResponse(
            content=long_content,
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
        )
        
        result = response.to_dict()
        
        assert len(result["content"]) == 103  # 100 chars + "..."
        assert result["content"].endswith("...")
    
    def test_created_at_timestamp(self):
        """Test that created_at is set."""
        before = datetime.now(timezone.utc)
        response = AIResponse(
            content="Test",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
        )
        after = datetime.now(timezone.utc)
        
        assert before <= response.created_at <= after
    
    def test_default_usage(self):
        """Test that default usage is empty TokenUsage."""
        response = AIResponse(
            content="Test",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
        )
        
        assert response.usage.prompt_tokens == 0
        assert response.usage.completion_tokens == 0


class TestProviderType:
    """Tests for ProviderType enum."""
    
    def test_all_providers_exist(self):
        """Test that all expected providers exist."""
        assert ProviderType.GEMINI.value == "gemini"
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.ANTHROPIC.value == "anthropic"
    
    def test_provider_type_count(self):
        """Test we have the expected number of providers."""
        assert len(ProviderType) == 3
    
    def test_provider_is_string_enum(self):
        """Test that provider values are strings."""
        for provider in ProviderType:
            assert isinstance(provider.value, str)


class TestMockProvider:
    """Tests using mock providers for integration testing patterns."""
    
    @pytest.fixture
    def mock_ai_response(self):
        """Create a mock AI response."""
        return AIResponse(
            content='{"action": "power_on", "device": "Living Room TV"}',
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            usage=TokenUsage(prompt_tokens=50, completion_tokens=20),
            latency_ms=150.0,
        )
    
    def test_mock_response_is_valid(self, mock_ai_response):
        """Test that mock response is valid for testing."""
        assert mock_ai_response.success is True
        assert mock_ai_response.content != ""
        assert mock_ai_response.latency_ms > 0
    
    def test_mock_response_can_be_parsed_as_json(self, mock_ai_response):
        """Test that mock response content can be parsed."""
        data = json.loads(mock_ai_response.content)
        
        assert data["action"] == "power_on"
        assert data["device"] == "Living Room TV"
    
    def test_create_error_mock(self):
        """Test creating an error mock for testing error handling."""
        error_response = AIResponse(
            content="",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
            success=False,
            error="API key invalid",
        )
        
        assert error_response.success is False
        assert "API key" in error_response.error


class TestMockProviderPatterns:
    """Test patterns for mocking providers in tests."""
    
    @pytest.mark.asyncio
    async def test_mock_generate_method(self):
        """Test pattern for mocking the generate method."""
        # Create a mock provider with async generate
        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(return_value=AIResponse(
            content="Mocked response",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
        ))
        
        # Call the mocked method
        result = await mock_provider.generate("Test prompt")
        
        # Verify behavior
        assert result.content == "Mocked response"
        mock_provider.generate.assert_called_once_with("Test prompt")
    
    @pytest.mark.asyncio
    async def test_mock_provider_with_context_manager(self):
        """Test pattern for patching provider in context."""
        mock_response = AIResponse(
            content='{"intent_type": "device_command"}',
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
        )
        
        with patch('app.ai.providers.gemini.GeminiProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.generate = AsyncMock(return_value=mock_response)
            mock_instance.generate_json = AsyncMock(return_value=mock_response)
            
            # Simulated usage
            result = await mock_instance.generate_json("Test")
            
            assert result.content == '{"intent_type": "device_command"}'
    
    def test_create_various_response_scenarios(self):
        """Test creating various response scenarios for testing."""
        scenarios = {
            "success": AIResponse(
                content="Success!",
                provider=ProviderType.GEMINI,
                model="test",
            ),
            "empty": AIResponse(
                content="",
                provider=ProviderType.GEMINI,
                model="test",
            ),
            "error": AIResponse(
                content="",
                provider=ProviderType.GEMINI,
                model="test",
                success=False,
                error="Test error",
            ),
            "slow": AIResponse(
                content="Slow response",
                provider=ProviderType.GEMINI,
                model="test",
                latency_ms=5000.0,
            ),
            "expensive": AIResponse(
                content="Expensive",
                provider=ProviderType.OPENAI,
                model="gpt-4",
                usage=TokenUsage(prompt_tokens=10000, completion_tokens=5000),
            ),
        }
        
        assert scenarios["success"].success is True
        assert scenarios["empty"].content == ""
        assert scenarios["error"].success is False
        assert scenarios["slow"].latency_ms > 1000
        assert scenarios["expensive"].usage.total_tokens == 15000


class TestResponseComparison:
    """Tests for comparing responses across providers."""
    
    def test_responses_from_different_providers(self):
        """Test that responses from different providers are comparable."""
        gemini_response = AIResponse(
            content="Gemini says hello",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            latency_ms=100.0,
        )
        
        openai_response = AIResponse(
            content="OpenAI says hello",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
            latency_ms=200.0,
        )
        
        anthropic_response = AIResponse(
            content="Claude says hello",
            provider=ProviderType.ANTHROPIC,
            model="claude-3-haiku",
            latency_ms=150.0,
        )
        
        # All should be successful
        assert all(r.success for r in [gemini_response, openai_response, anthropic_response])
        
        # All should have content
        assert all(r.content for r in [gemini_response, openai_response, anthropic_response])
        
        # Can compare latencies
        responses = [gemini_response, openai_response, anthropic_response]
        fastest = min(responses, key=lambda r: r.latency_ms)
        assert fastest.provider == ProviderType.GEMINI
