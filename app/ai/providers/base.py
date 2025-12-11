"""
Base AI Provider - Abstract interface for all LLM providers.

This module defines the contract that all AI providers must follow.
It ensures consistent behavior regardless of which provider is used.

Design Pattern: Strategy Pattern
================================
The base class defines the interface, and each provider implements it.
This allows the AI Router to switch between providers without code changes.

Example:
    provider = GeminiProvider()  # or OpenAIProvider() or AnthropicProvider()
    response = await provider.generate("Hello, world!")
    print(response.content)
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from enum import Enum
import logging

# Configure logging for AI operations
logger = logging.getLogger("jarvis.ai")


class ProviderType(str, Enum):
    """Enum of supported AI providers."""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class TokenUsage:
    """
    Token usage statistics for an AI request.
    
    Used for:
    - Cost tracking (tokens = money)
    - Rate limiting awareness
    - Performance optimization
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def __post_init__(self):
        """Calculate total if not provided."""
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class AIResponse:
    """
    Standardized response from any AI provider.
    
    All providers return this same structure, making it easy to:
    - Process responses uniformly
    - Log and monitor across providers
    - Handle errors consistently
    
    Attributes:
        content: The generated text response
        provider: Which provider generated this response
        model: The specific model used
        usage: Token usage statistics
        latency_ms: How long the request took
        success: Whether the request succeeded
        error: Error message if failed
        raw_response: Original provider response (for debugging)
        metadata: Additional provider-specific data
        created_at: Timestamp of the response
    """
    content: str
    provider: ProviderType
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    raw_response: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "provider": self.provider.value,
            "model": self.model,
            "tokens": {
                "prompt": self.usage.prompt_tokens,
                "completion": self.usage.completion_tokens,
                "total": self.usage.total_tokens,
            },
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


class AIProvider(ABC):
    """
    Abstract base class for AI providers.
    
    All AI providers (Gemini, OpenAI, Anthropic) must implement this interface.
    This ensures consistent behavior and makes providers interchangeable.
    
    Responsibilities:
    - Generate text responses from prompts
    - Handle errors gracefully
    - Track token usage and latency
    - Provide structured responses
    
    Usage:
        class MyProvider(AIProvider):
            async def generate(self, prompt, **kwargs):
                # Implementation here
                pass
    """
    
    provider_type: ProviderType
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response from the AI model.
        
        Args:
            prompt: The user's message/query
            system_prompt: Optional system instructions for the model
            temperature: Creativity level (0=deterministic, 1=creative)
            max_tokens: Maximum tokens in the response
            **kwargs: Provider-specific options
            
        Returns:
            AIResponse with the generated content
            
        Raises:
            This method should NOT raise exceptions.
            Errors are captured in AIResponse.error
        """
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        Generate a JSON response from the AI model.
        
        Used when we need structured output (like intent parsing).
        The provider should enforce JSON output format.
        
        Args:
            prompt: The user's message/query
            system_prompt: System prompt with JSON schema instructions
            **kwargs: Provider-specific options
            
        Returns:
            AIResponse with JSON content string
        """
        pass
    
    def _measure_latency(self, start_time: float) -> float:
        """Calculate latency in milliseconds."""
        return (time.time() - start_time) * 1000
    
    def _create_error_response(
        self,
        error: str,
        model: str,
        latency_ms: float = 0.0
    ) -> AIResponse:
        """
        Create a standardized error response.
        
        Used when a provider fails to ensure consistent error handling.
        """
        logger.error(f"AI Provider Error [{self.provider_type.value}]: {error}")
        return AIResponse(
            content="",
            provider=self.provider_type,
            model=model,
            latency_ms=latency_ms,
            success=False,
            error=error,
        )
    
    async def health_check(self) -> bool:
        """
        Check if the provider is available and configured.
        
        Returns:
            True if provider is ready to use, False otherwise
        """
        try:
            response = await self.generate(
                prompt="Say 'ok' and nothing else.",
                max_tokens=10,
            )
            return response.success and len(response.content) > 0
        except Exception as e:
            logger.error(f"Health check failed for {self.provider_type.value}: {e}")
            return False
