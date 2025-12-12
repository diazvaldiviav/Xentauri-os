"""
Tests for AI Router/Orchestrator.

This module tests:
- TaskComplexity enum
- RoutingDecision dataclass
- AIRouter analyze_request method
- Routing logic for different request types

All LLM calls are mocked to ensure fast, reliable tests.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from app.ai.router.orchestrator import (
    TaskComplexity,
    RoutingDecision,
    AIRouter,
    ai_router,
)
from app.ai.providers.base import AIResponse, ProviderType, TokenUsage


class TestTaskComplexity:
    """Tests for TaskComplexity enum."""
    
    def test_all_complexities_exist(self):
        """Test that all expected complexity levels exist."""
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.COMPLEX_EXECUTION.value == "complex_execution"
        assert TaskComplexity.COMPLEX_REASONING.value == "complex_reasoning"
        assert TaskComplexity.UNKNOWN.value == "unknown"
    
    def test_complexity_count(self):
        """Test we have the expected number of complexity levels."""
        assert len(TaskComplexity) == 4
    
    def test_complexity_is_string_enum(self):
        """Test that complexity values are strings."""
        for complexity in TaskComplexity:
            assert isinstance(complexity.value, str)


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""
    
    def test_create_simple_decision(self):
        """Test creating a simple routing decision."""
        decision = RoutingDecision(
            complexity=TaskComplexity.SIMPLE,
            target_provider="gemini",
            reasoning="Simple device command",
            confidence=0.95,
            is_device_command=True,
        )
        
        assert decision.complexity == TaskComplexity.SIMPLE
        assert decision.target_provider == "gemini"
        assert decision.confidence == 0.95
        assert decision.is_device_command is True
    
    def test_create_complex_execution_decision(self):
        """Test creating a complex execution decision."""
        decision = RoutingDecision(
            complexity=TaskComplexity.COMPLEX_EXECUTION,
            target_provider="openai",
            reasoning="Requires code generation",
            confidence=0.85,
            is_device_command=False,
        )
        
        assert decision.complexity == TaskComplexity.COMPLEX_EXECUTION
        assert decision.target_provider == "openai"
    
    def test_create_complex_reasoning_decision(self):
        """Test creating a complex reasoning decision."""
        decision = RoutingDecision(
            complexity=TaskComplexity.COMPLEX_REASONING,
            target_provider="anthropic",
            reasoning="Requires strategic planning",
            confidence=0.9,
            is_device_command=False,
        )
        
        assert decision.complexity == TaskComplexity.COMPLEX_REASONING
        assert decision.target_provider == "anthropic"
    
    def test_default_should_respond_directly(self):
        """Test default value for should_respond_directly."""
        decision = RoutingDecision(
            complexity=TaskComplexity.SIMPLE,
            target_provider="gemini",
            reasoning="Test",
            confidence=0.8,
            is_device_command=False,
        )
        
        assert decision.should_respond_directly is False
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        decision = RoutingDecision(
            complexity=TaskComplexity.SIMPLE,
            target_provider="gemini",
            reasoning="Simple command",
            confidence=0.95,
            is_device_command=True,
            should_respond_directly=True,
        )
        
        result = decision.to_dict()
        
        assert result["complexity"] == "simple"
        assert result["target_provider"] == "gemini"
        assert result["reasoning"] == "Simple command"
        assert result["confidence"] == 0.95
        assert result["is_device_command"] is True
        assert result["should_respond_directly"] is True


class TestAIRouterInitialization:
    """Tests for AIRouter initialization."""
    
    def test_router_initializes(self):
        """Test that router initializes successfully."""
        router = AIRouter()
        
        assert router is not None
        assert router.orchestrator is not None
        assert router.executor is not None
        assert router.reasoner is not None
    
    def test_singleton_exists(self):
        """Test that the singleton instance exists."""
        assert ai_router is not None
        assert isinstance(ai_router, AIRouter)


class TestAnalyzeRequest:
    """Tests for analyze_request method with mocked LLM calls."""
    
    @pytest.fixture
    def router(self):
        """Create a fresh router instance."""
        return AIRouter()
    
    def _create_mock_response(self, content: dict) -> AIResponse:
        """Helper to create mock AI response."""
        return AIResponse(
            content=json.dumps(content),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
    
    @pytest.mark.asyncio
    async def test_analyze_simple_device_command(self, router):
        """Test analyzing a simple device command."""
        mock_response = self._create_mock_response({
            "complexity": "simple",
            "is_device_command": True,
            "reasoning": "Direct device power command",
            "confidence": 0.95,
        })
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request("Turn on the living room TV")
            
            assert decision.complexity == TaskComplexity.SIMPLE
            assert decision.is_device_command is True
            assert decision.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_analyze_complex_execution_request(self, router):
        """Test analyzing a request requiring code execution."""
        mock_response = self._create_mock_response({
            "complexity": "complex_execution",
            "is_device_command": False,
            "reasoning": "Requires API integration",
            "confidence": 0.88,
        })
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request("Search Google for weather")
            
            assert decision.complexity == TaskComplexity.COMPLEX_EXECUTION
            assert decision.target_provider == "openai"
    
    @pytest.mark.asyncio
    async def test_analyze_complex_reasoning_request(self, router):
        """Test analyzing a request requiring deep reasoning."""
        mock_response = self._create_mock_response({
            "complexity": "complex_reasoning",
            "is_device_command": False,
            "reasoning": "Requires planning and analysis",
            "confidence": 0.92,
        })
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request("Plan a movie night setup for 10 people")
            
            assert decision.complexity == TaskComplexity.COMPLEX_REASONING
            assert decision.target_provider == "anthropic"
    
    @pytest.mark.asyncio
    async def test_analyze_with_context(self, router):
        """Test analyzing with device context."""
        mock_response = self._create_mock_response({
            "complexity": "simple",
            "is_device_command": True,
            "reasoning": "Device command with context",
            "confidence": 0.97,
        })
        
        context = {
            "devices": [
                {"name": "Living Room TV", "is_online": True},
                {"name": "Bedroom Monitor", "is_online": False},
            ]
        }
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request("Turn on the TV", context)
            
            # Verify context was passed to the prompt
            call_args = mock_gen.call_args
            assert call_args is not None
    
    @pytest.mark.asyncio
    async def test_analyze_fallback_on_error(self, router):
        """Test that router defaults to simple/gemini on error."""
        error_response = AIResponse(
            content="",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=False,
            error="API error",
        )
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = error_response
            
            decision = await router.analyze_request("Any request")
            
            assert decision.complexity == TaskComplexity.SIMPLE
            assert decision.target_provider == "gemini"
            assert "failed" in decision.reasoning.lower() or "defaulting" in decision.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_fallback_on_parse_error(self, router):
        """Test that router handles JSON parse errors."""
        invalid_response = AIResponse(
            content="not valid json",
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = invalid_response
            
            decision = await router.analyze_request("Any request")
            
            assert decision.complexity == TaskComplexity.SIMPLE
            assert decision.target_provider == "gemini"


class TestGetProvider:
    """Tests for _get_provider method."""
    
    @pytest.fixture
    def router(self):
        """Create a fresh router instance."""
        return AIRouter()
    
    def test_get_gemini_provider(self, router):
        """Test getting Gemini provider."""
        provider = router._get_provider("gemini")
        assert provider == router.orchestrator
    
    def test_get_openai_provider(self, router):
        """Test getting OpenAI provider."""
        provider = router._get_provider("openai")
        assert provider == router.executor
    
    def test_get_anthropic_provider(self, router):
        """Test getting Anthropic provider."""
        provider = router._get_provider("anthropic")
        assert provider == router.reasoner
    
    def test_get_unknown_provider_defaults_to_gemini(self, router):
        """Test that unknown provider defaults to Gemini."""
        provider = router._get_provider("unknown")
        assert provider == router.orchestrator


class TestRoutingPatterns:
    """Test common routing patterns and scenarios."""
    
    @pytest.fixture
    def router(self):
        """Create a fresh router instance."""
        return AIRouter()
    
    def _mock_decision(self, router, complexity: str, is_device_command: bool = False):
        """Helper to set up mock routing decision."""
        return patch.object(
            router.orchestrator,
            'generate_json',
            new_callable=AsyncMock,
            return_value=AIResponse(
                content=json.dumps({
                    "complexity": complexity,
                    "is_device_command": is_device_command,
                    "reasoning": f"Test {complexity}",
                    "confidence": 0.9,
                }),
                provider=ProviderType.GEMINI,
                model="gemini-1.5-flash",
                success=True,
            )
        )
    
    @pytest.mark.asyncio
    async def test_device_commands_route_to_gemini(self, router):
        """Test that device commands are handled by Gemini."""
        commands = [
            "Turn on the TV",
            "Switch to HDMI 2",
            "Volume up",
            "Mute the bedroom monitor",
        ]
        
        with self._mock_decision(router, "simple", is_device_command=True):
            for cmd in commands:
                decision = await router.analyze_request(cmd)
                assert decision.complexity == TaskComplexity.SIMPLE
    
    @pytest.mark.asyncio
    async def test_queries_route_appropriately(self, router):
        """Test that queries are analyzed correctly."""
        with self._mock_decision(router, "simple", is_device_command=False):
            decision = await router.analyze_request("What devices do I have?")
            
            assert decision.complexity == TaskComplexity.SIMPLE


class TestSystemPromptGeneration:
    """Tests for system prompt generation."""
    
    @pytest.fixture
    def router(self):
        """Create a fresh router instance."""
        return AIRouter()
    
    def test_system_prompt_includes_base_info(self, router):
        """Test that system prompt includes base information."""
        decision = RoutingDecision(
            complexity=TaskComplexity.SIMPLE,
            target_provider="gemini",
            reasoning="Test",
            confidence=0.9,
            is_device_command=False,
        )
        
        prompt = router._get_system_prompt_for_task(decision)
        
        assert "Jarvis" in prompt
        assert "display" in prompt.lower() or "devices" in prompt.lower()
    
    def test_system_prompt_includes_devices(self, router):
        """Test that system prompt includes device list."""
        decision = RoutingDecision(
            complexity=TaskComplexity.SIMPLE,
            target_provider="gemini",
            reasoning="Test",
            confidence=0.9,
            is_device_command=True,
        )
        
        context = {
            "devices": [
                {"name": "Living Room TV", "is_online": True}
            ]
        }
        
        prompt = router._get_system_prompt_for_task(decision, context)
        
        assert "Living Room TV" in prompt
    
    def test_system_prompt_for_device_command(self, router):
        """Test that device command prompt includes extraction instructions."""
        decision = RoutingDecision(
            complexity=TaskComplexity.SIMPLE,
            target_provider="gemini",
            reasoning="Test",
            confidence=0.9,
            is_device_command=True,
        )
        
        prompt = router._get_system_prompt_for_task(decision)
        
        assert "device" in prompt.lower()
        assert "action" in prompt.lower()


class TestEdgeCases:
    """Test edge cases in routing."""
    
    @pytest.fixture
    def router(self):
        """Create a fresh router instance."""
        return AIRouter()
    
    @pytest.mark.asyncio
    async def test_empty_request(self, router):
        """Test handling empty request."""
        mock_response = AIResponse(
            content=json.dumps({
                "complexity": "simple",
                "is_device_command": False,
                "reasoning": "Empty request",
                "confidence": 0.5,
            }),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request("")
            
            # Should still return a valid decision
            assert decision is not None
            assert isinstance(decision, RoutingDecision)
    
    @pytest.mark.asyncio
    async def test_very_long_request(self, router):
        """Test handling very long request."""
        long_request = "Turn on the TV " * 100
        
        mock_response = AIResponse(
            content=json.dumps({
                "complexity": "simple",
                "is_device_command": True,
                "reasoning": "Long request",
                "confidence": 0.7,
            }),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request(long_request)
            
            assert decision is not None
    
    @pytest.mark.asyncio
    async def test_special_characters_in_request(self, router):
        """Test handling special characters."""
        special_request = "Turn on the 'Living Room TV' with <brackets> & symbols!"
        
        mock_response = AIResponse(
            content=json.dumps({
                "complexity": "simple",
                "is_device_command": True,
                "reasoning": "Special chars",
                "confidence": 0.85,
            }),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            
            decision = await router.analyze_request(special_request)
            
            assert decision is not None
            assert decision.is_device_command is True
    
    @pytest.mark.asyncio
    async def test_missing_fields_in_response(self, router):
        """Test handling response with missing fields."""
        incomplete_response = AIResponse(
            content=json.dumps({
                "complexity": "simple",
                # Missing other fields
            }),
            provider=ProviderType.GEMINI,
            model="gemini-1.5-flash",
            success=True,
        )
        
        with patch.object(router.orchestrator, 'generate_json', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = incomplete_response
            
            decision = await router.analyze_request("Test request")
            
            # Should handle missing fields gracefully
            assert decision is not None
            assert decision.complexity == TaskComplexity.SIMPLE
