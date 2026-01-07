"""
Anthropic Provider - Claude client for deep reasoning.

Claude (by Anthropic) is used for tasks requiring:
- Deep logical reasoning
- Complex planning and strategy
- Critical decision making
- Nuanced analysis and explanations

Role in Jarvis:
==============
When Gemini Flash (orchestrator) determines a task requires
deep reasoning or critical thinking, it routes to Claude.

Examples:
- "Help me plan a complex automation..."
- "Analyze why X is happening and suggest solutions..."
- "What's the best approach for..."

API Documentation: https://docs.anthropic.com/en/api
"""

import time
import json
import logging
from typing import Optional, Any, Dict

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.ai.providers.base import (
    AIProvider,
    AIResponse,
    ProviderType,
    TokenUsage
)

logger = logging.getLogger("jarvis.ai.anthropic")


class AnthropicProvider(AIProvider):
    """
    Anthropic Claude provider implementation.
    
    Claude is our "thinker" - used for tasks that require:
    - Deep multi-step reasoning
    - Complex analysis and evaluation
    - Critical decision support
    - Strategic planning
    
    Usage:
        provider = AnthropicProvider()
        response = await provider.generate("Analyze this situation...")
        
        # For structured output:
        response = await provider.generate_json(
            prompt="Evaluate these options and rank them...",
            system_prompt="Return JSON with 'rankings' array"
        )
    """
    
    provider_type = ProviderType.ANTHROPIC
    
    def __init__(self, model: str = None, api_key: str = None):
        """
        Initialize the Anthropic provider.
        
        Args:
            model: Model name (default: from settings.ANTHROPIC_MODEL)
            api_key: API key (default: from settings.ANTHROPIC_API_KEY)
        """
        self.model = model or settings.ANTHROPIC_MODEL
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        
        # Initialize async client
        if self.api_key:
            self._client = AsyncAnthropic(api_key=self.api_key)
            logger.info(f"Anthropic provider initialized with model: {self.model}")
        else:
            self._client = None
            logger.warning("Anthropic API key not configured - provider unavailable")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response using Claude.
        
        Args:
            prompt: The user's message
            system_prompt: Optional system instructions
            temperature: Creativity (0-1)
            max_tokens: Maximum response length
            
        Returns:
            AIResponse with the generated content
        """
        start_time = time.time()
        
        if not self._client:
            return self._create_error_response(
                error="Anthropic API key not configured",
                model=self.model,
                latency_ms=self._measure_latency(start_time)
            )
        
        try:
            # Build the request
            request_params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            
            # Add system prompt if provided
            if system_prompt:
                request_params["system"] = system_prompt
            
            # Make the API request
            response = await self._client.messages.create(**request_params)
            
            latency_ms = self._measure_latency(start_time)
            
            # Extract content (Claude returns a list of content blocks)
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
            
            # Extract usage
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
            )
            
            logger.info(f"Anthropic request completed in {latency_ms:.0f}ms, tokens: {usage.total_tokens}")
            
            return AIResponse(
                content=content,
                provider=self.provider_type,
                model=self.model,
                usage=usage,
                latency_ms=latency_ms,
                success=True,
                raw_response=response,
            )
            
        except Exception as e:
            latency_ms = self._measure_latency(start_time)
            logger.error(f"Anthropic generation failed: {e}")
            return self._create_error_response(
                error=str(e),
                model=self.model,
                latency_ms=latency_ms
            )
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        Generate a JSON response using Claude.
        
        Claude doesn't have a native JSON mode, but is very good
        at following instructions for structured output.
        
        Args:
            prompt: The user's message
            system_prompt: System prompt (should include JSON schema)
            
        Returns:
            AIResponse with JSON content string
        """
        start_time = time.time()
        
        if not self._client:
            return self._create_error_response(
                error="Anthropic API key not configured",
                model=self.model,
                latency_ms=self._measure_latency(start_time)
            )
        
        try:
            # Build system prompt with JSON instruction
            json_system = system_prompt or ""
            json_system += "\n\nIMPORTANT: You must respond with valid JSON only. No explanation, no markdown code blocks - just the raw JSON object."
            
            request_params = {
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,  # Low for consistency
                "system": json_system,
            }
            
            response = await self._client.messages.create(**request_params)
            
            latency_ms = self._measure_latency(start_time)
            
            # Extract content
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
            content = content.strip()
            
            # Sprint 5.3: Validate JSON with intelligent repair
            is_valid, content, error = await self._validate_json_with_repair(
                content=content,
                original_prompt=prompt,
                original_system_prompt=system_prompt,
            )
            
            if not is_valid:
                return self._create_error_response(
                    error=error,
                    model=self.model,
                    latency_ms=latency_ms
                )
            
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
            )
            
            logger.info(f"Anthropic JSON request completed in {latency_ms:.0f}ms")
            
            return AIResponse(
                content=content,
                provider=self.provider_type,
                model=self.model,
                usage=usage,
                latency_ms=latency_ms,
                success=True,
                raw_response=response,
            )
            
        except Exception as e:
            latency_ms = self._measure_latency(start_time)
            logger.error(f"Anthropic JSON generation failed: {e}")
            return self._create_error_response(
                error=str(e),
                model=self.model,
                latency_ms=latency_ms
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
anthropic_provider = AnthropicProvider()
