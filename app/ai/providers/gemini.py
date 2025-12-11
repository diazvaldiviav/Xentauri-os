"""
Gemini Provider - Google's Gemini AI client.

Gemini Flash is the PRIMARY model in our AI architecture:
- Fast and cost-effective (perfect for orchestration)
- Excellent at structured output and JSON
- Great for intent parsing and routing decisions

Role in Jarvis:
==============
1. Orchestrator: Analyzes user requests and routes them
2. Intent Parser: Extracts structured intents from natural language
3. Simple Tasks: Handles straightforward requests directly

Gemini Models:
- gemini-1.5-flash: Fast, cheap - our default orchestrator
- gemini-1.5-pro: More capable but slower/expensive

API Documentation: https://ai.google.dev/api/python/google/generativeai
"""

import time
import json
import logging
from typing import Optional, Any, Dict

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.core.config import settings
from app.ai.providers.base import (
    AIProvider, 
    AIResponse, 
    ProviderType, 
    TokenUsage
)

logger = logging.getLogger("jarvis.ai.gemini")


class GeminiProvider(AIProvider):
    """
    Google Gemini AI provider implementation.
    
    Gemini is our orchestrator - the fast, efficient brain that decides
    what to do with each request. It's optimized for:
    - Quick response times (<1 second for most requests)
    - Structured output (JSON extraction)
    - Cost efficiency (handles 80% of requests cheaply)
    
    Usage:
        provider = GeminiProvider()
        response = await provider.generate("Turn on the TV")
        
        # For structured output:
        response = await provider.generate_json(
            prompt="Extract the intent from: 'Turn on the TV'",
            system_prompt="Return JSON with 'action' and 'device' fields"
        )
    """
    
    provider_type = ProviderType.GEMINI
    
    def __init__(self, model: str = None, api_key: str = None):
        """
        Initialize the Gemini provider.
        
        Args:
            model: Model name (default: from settings.GEMINI_MODEL)
            api_key: API key (default: from settings.GEMINI_API_KEY)
        """
        self.model = model or settings.GEMINI_MODEL
        self.api_key = api_key or settings.GEMINI_API_KEY
        
        # Configure the Gemini API
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
            logger.info(f"Gemini provider initialized with model: {self.model}")
        else:
            self._client = None
            logger.warning("Gemini API key not configured - provider unavailable")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response using Gemini.
        
        Args:
            prompt: The user's message
            system_prompt: Optional system instructions
            temperature: Creativity (0-1)
            max_tokens: Maximum response length
            
        Returns:
            AIResponse with the generated content
        """
        start_time = time.time()
        
        # Check if client is available
        if not self._client:
            return self._create_error_response(
                error="Gemini API key not configured",
                model=self.model,
                latency_ms=self._measure_latency(start_time)
            )
        
        try:
            # Build the full prompt with system instructions
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Configure generation parameters
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Generate response
            # Note: Using sync API wrapped in async for simplicity
            # For production, consider google-generativeai's async methods
            response = self._client.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            
            latency_ms = self._measure_latency(start_time)
            
            # Extract usage metadata
            usage = TokenUsage(
                prompt_tokens=response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
                completion_tokens=response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
            )
            
            # Log the successful request
            logger.info(f"Gemini request completed in {latency_ms:.0f}ms, tokens: {usage.total_tokens}")
            
            return AIResponse(
                content=response.text,
                provider=self.provider_type,
                model=self.model,
                usage=usage,
                latency_ms=latency_ms,
                success=True,
                raw_response=response,
            )
            
        except Exception as e:
            latency_ms = self._measure_latency(start_time)
            logger.error(f"Gemini generation failed: {e}")
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
        Generate a JSON response using Gemini.
        
        Gemini is excellent at structured output. This method:
        1. Instructs the model to output valid JSON
        2. Parses and validates the response
        3. Returns clean JSON string
        
        Args:
            prompt: The user's message
            system_prompt: System prompt (should include JSON schema)
            
        Returns:
            AIResponse with JSON content string
        """
        start_time = time.time()
        
        if not self._client:
            return self._create_error_response(
                error="Gemini API key not configured",
                model=self.model,
                latency_ms=self._measure_latency(start_time)
            )
        
        try:
            # Build prompt with JSON instruction
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Add explicit JSON instruction
            json_instruction = "\n\nIMPORTANT: Respond ONLY with valid JSON, no markdown code blocks or explanation."
            full_prompt += json_instruction
            
            # Configure for JSON output
            generation_config = GenerationConfig(
                temperature=0.2,  # Lower temperature for consistent structure
                max_output_tokens=1024,
                response_mime_type="application/json",  # Gemini's JSON mode
            )
            
            response = self._client.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            
            latency_ms = self._measure_latency(start_time)
            
            # Parse the JSON to validate it
            content = response.text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Validate JSON
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"Gemini returned invalid JSON: {e}")
                return self._create_error_response(
                    error=f"Invalid JSON response: {e}",
                    model=self.model,
                    latency_ms=latency_ms
                )
            
            # Extract usage
            usage = TokenUsage(
                prompt_tokens=response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
                completion_tokens=response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
            )
            
            logger.info(f"Gemini JSON request completed in {latency_ms:.0f}ms")
            
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
            logger.error(f"Gemini JSON generation failed: {e}")
            return self._create_error_response(
                error=str(e),
                model=self.model,
                latency_ms=latency_ms
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
# Create a single instance for easy import throughout the app
# Usage: from app.ai.providers.gemini import gemini_provider
gemini_provider = GeminiProvider()
