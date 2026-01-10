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
        reasoning: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response using OpenAI GPT.

        Args:
            prompt: The user's message
            system_prompt: Optional system instructions
            temperature: Creativity (0-1)
            max_tokens: Maximum response length
            reasoning: Optional reasoning config (e.g., {"effort": "high"})

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
            # Combine system prompt and user prompt into single input
            input_text = prompt
            if system_prompt:
                input_text = f"{system_prompt}\n\n{prompt}"

            # Build API request params
            request_params = {
                "model": self.model,
                "input": input_text,
                "max_output_tokens": max_tokens,
            }

            # Models that don't support temperature (require reasoning instead)
            NO_TEMPERATURE_MODELS = {"gpt-5-mini", "gpt-5-nano", "codex", "o1", "o3"}
            model_requires_reasoning = any(m in self.model.lower() for m in NO_TEMPERATURE_MODELS)

            # Add reasoning if provided OR if model requires it (disables temperature)
            if reasoning:
                request_params["reasoning"] = reasoning
            elif model_requires_reasoning:
                # Use low effort for speed (testing fixer with weaker output)
                request_params["reasoning"] = {"effort": "low"}
            else:
                request_params["temperature"] = temperature

            # Make the API request with new responses API
            response = await self._client.responses.create(**request_params)
            
            latency_ms = self._measure_latency(start_time)
            
            # Extract content from new response format
            content = response.output_text or ""

            # Extract usage (Responses API uses input_tokens/output_tokens)
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
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
            # Combine system prompt with JSON instruction
            system_content = system_prompt or ""
            system_content += "\n\nYou must respond with valid JSON only, no explanation."
            input_text = f"{system_content}\n\n{prompt}"

            # Call responses API (JSON mode via prompt instructions)
            # Note: Responses API doesn't use response_format like Chat Completions
            # Instead, we rely on explicit instructions in the prompt
            response = await self._client.responses.create(
                model=self.model,
                input=input_text,
                temperature=0.2,  # Low temperature for consistency
                max_output_tokens=1024,
            )
            
            latency_ms = self._measure_latency(start_time)
            
            content = response.output_text or "{}"
            
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
            
            # Extract usage (Responses API uses input_tokens/output_tokens)
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
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

    async def generate_with_reasoning(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        effort: str = "high",
        max_tokens: int = 16384,
        **kwargs
    ) -> AIResponse:
        """
        Generate using Codex-Max with reasoning for complex code generation.

        Sprint 5.2.2: Optimized for HTML/CSS layout generation.

        Args:
            prompt: The user's message
            system_prompt: Optional system instructions
            effort: Reasoning effort ("low", "medium", "high")
            max_tokens: Maximum response length

        Returns:
            AIResponse with the generated content
        """
        start_time = time.time()
        model = settings.OPENAI_CODE_MODEL

        if not self._client:
            return self._create_error_response(
                error="OpenAI API key not configured",
                model=model,
                latency_ms=self._measure_latency(start_time)
            )

        try:
            input_text = prompt
            if system_prompt:
                input_text = f"{system_prompt}\n\n{prompt}"

            response = await self._client.responses.create(
                model=model,
                input=input_text,
                reasoning={"effort": effort},
                max_output_tokens=max_tokens,
            )

            latency_ms = self._measure_latency(start_time)
            content = response.output_text or ""

            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
            )

            logger.info(f"Codex-Max completed in {latency_ms:.0f}ms, tokens: {usage.total_tokens}")

            return AIResponse(
                content=content,
                provider=self.provider_type,
                model=model,
                usage=usage,
                latency_ms=latency_ms,
                success=True,
                raw_response=response,
            )

        except Exception as e:
            latency_ms = self._measure_latency(start_time)
            logger.error(f"Codex-Max generation failed: {e}")
            return self._create_error_response(
                error=str(e),
                model=model,
                latency_ms=latency_ms
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
openai_provider = OpenAIProvider()
