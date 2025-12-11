"""
OpenAI Provider - GPT client for complex tasks.

OpenAI's models (GPT-4o, etc.) are used for tasks requiring:
- Tool/function calling
- Code generation and execution
- Complex structured reasoning
- Multi-step task planning

Role in Jarvis:
==============
When Gemini Flash (orchestrator) determines a task is complex and
involves coding, tool usage, or execution, it routes to GPT.

Examples:
- "Write a script to..."
- "Search for X and summarize..."
- "Calculate the difference between..."

API Documentation: https://platform.openai.com/docs/api-reference
"""

import time
import json
import logging
from typing import Optional, Any, Dict

from openai import AsyncOpenAI

from app.core.config import settings
from app.ai.providers.base import (
    AIProvider,
    AIResponse,
    ProviderType,
    TokenUsage
)

logger = logging.getLogger("jarvis.ai.openai")


class OpenAIProvider(AIProvider):
    """
    OpenAI GPT provider implementation.
    
    GPT is our "executor" - used for complex tasks that require:
    - Multi-step reasoning with tools
    - Code generation and explanation
    - Structured data processing
    
    Usage:
        provider = OpenAIProvider()
        response = await provider.generate("Write a Python function to...")
        
        # For structured output:
        response = await provider.generate_json(
            prompt="Analyze this code and return bugs...",
            system_prompt="Return JSON with 'bugs' array"
        )
    """
    
    provider_type = ProviderType.OPENAI
    
    def __init__(self, model: str = None, api_key: str = None):
        """
        Initialize the OpenAI provider.
        
        Args:
            model: Model name (default: from settings.OPENAI_MODEL)
            api_key: API key (default: from settings.OPENAI_API_KEY)
        """
        self.model = model or settings.OPENAI_MODEL
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        # Initialize async client
        if self.api_key:
            self._client = AsyncOpenAI(api_key=self.api_key)
            logger.info(f"OpenAI provider initialized with model: {self.model}")
        else:
            self._client = None
            logger.warning("OpenAI API key not configured - provider unavailable")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response using OpenAI GPT.
        
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
                error="OpenAI API key not configured",
                model=self.model,
                latency_ms=self._measure_latency(start_time)
            )
        
        try:
            # Build messages array
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Make the API request
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            latency_ms = self._measure_latency(start_time)
            
            # Extract content
            content = response.choices[0].message.content or ""
            
            # Extract usage
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
            )
            
            logger.info(f"OpenAI request completed in {latency_ms:.0f}ms, tokens: {usage.total_tokens}")
            
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
            logger.error(f"OpenAI generation failed: {e}")
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
        Generate a JSON response using OpenAI.
        
        Uses OpenAI's JSON mode for reliable structured output.
        
        Args:
            prompt: The user's message
            system_prompt: System prompt (should include JSON schema)
            
        Returns:
            AIResponse with JSON content string
        """
        start_time = time.time()
        
        if not self._client:
            return self._create_error_response(
                error="OpenAI API key not configured",
                model=self.model,
                latency_ms=self._measure_latency(start_time)
            )
        
        try:
            # Build messages with JSON instruction
            messages = []
            system_content = system_prompt or ""
            system_content += "\n\nYou must respond with valid JSON only, no explanation."
            messages.append({"role": "system", "content": system_content})
            messages.append({"role": "user", "content": prompt})
            
            # Use JSON response format
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,  # Low temperature for consistency
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            
            latency_ms = self._measure_latency(start_time)
            
            content = response.choices[0].message.content or "{}"
            
            # Validate JSON
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"OpenAI returned invalid JSON: {e}")
                return self._create_error_response(
                    error=f"Invalid JSON response: {e}",
                    model=self.model,
                    latency_ms=latency_ms
                )
            
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
            )
            
            logger.info(f"OpenAI JSON request completed in {latency_ms:.0f}ms")
            
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
            logger.error(f"OpenAI JSON generation failed: {e}")
            return self._create_error_response(
                error=str(e),
                model=self.model,
                latency_ms=latency_ms
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
openai_provider = OpenAIProvider()
