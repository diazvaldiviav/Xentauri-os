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

    # -------------------------------------------------------------------------
    # JSON VALIDATION AND REPAIR HELPERS (Sprint 5.3)
    # -------------------------------------------------------------------------
    
    def _clean_markdown_wrapper(self, content: str) -> str:
        """
        Remove markdown code block wrappers from JSON content.
        
        LLMs sometimes wrap JSON in ```json ... ``` blocks despite instructions.
        This method cleans that up for consistent parsing.
        
        Args:
            content: Raw content that may contain markdown wrappers
            
        Returns:
            Cleaned content with markdown wrappers removed
        """
        if not content:
            return content
        
        content = content.strip()
        
        # Remove opening markdown code block
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        
        # Remove closing markdown code block
        if content.endswith("```"):
            content = content[:-3]
        
        return content.strip()
    
    async def _validate_json_with_repair(
        self,
        content: str,
        original_prompt: str,
        original_system_prompt: Optional[str] = None,
    ) -> tuple:
        """
        Validate JSON content and attempt repair if invalid.
        
        This method implements the intelligent JSON repair flow:
        1. Clean markdown wrappers
        2. Try to parse JSON
        3. If valid, return success
        4. If invalid and repair enabled, attempt diagnosis + repair
        5. Return result with repaired content or error
        
        Args:
            content: Raw JSON string from LLM
            original_prompt: The original user prompt (for repair context)
            original_system_prompt: The original system prompt (for repair context)
            
        Returns:
            Tuple of (is_valid: bool, content_or_repaired: str, error_if_failed: Optional[str])
        """
        import json
        from app.core.config import settings
        
        # Step 1: Clean markdown wrappers
        cleaned_content = self._clean_markdown_wrapper(content)
        
        # Step 2: Try to parse JSON
        try:
            json.loads(cleaned_content)
            return (True, cleaned_content, None)
        except json.JSONDecodeError as e:
            original_error = e
            logger.warning(f"[{self.provider_type.value}] Invalid JSON received: {e}")
        
        # Step 3: Check if repair is enabled
        if not getattr(settings, 'JSON_REPAIR_ENABLED', False):
            return (False, cleaned_content, f"Invalid JSON response: {original_error}")
        
        # Step 4: Attempt repair
        max_retries = getattr(settings, 'JSON_REPAIR_MAX_RETRIES', 1)
        
        for attempt in range(max_retries):
            logger.info(f"[{self.provider_type.value}] Attempting JSON repair (attempt {attempt + 1}/{max_retries})")
            
            try:
                # Step 4a: Diagnose the error using Gemini (fast, cheap)
                diagnosis = await self._diagnose_json_error(cleaned_content, original_error)
                
                if not diagnosis:
                    logger.warning(f"[{self.provider_type.value}] JSON diagnosis failed, cannot repair")
                    continue
                
                logger.info(f"[{self.provider_type.value}] JSON diagnosis: {diagnosis}")
                
                # Step 4b: Repair using the original provider
                repaired_content = await self._repair_json(
                    content=cleaned_content,
                    diagnosis=diagnosis,
                    original_prompt=original_prompt,
                    original_system_prompt=original_system_prompt,
                )
                
                if not repaired_content:
                    logger.warning(f"[{self.provider_type.value}] JSON repair returned empty result")
                    continue
                
                # Step 4c: Validate repaired content
                repaired_cleaned = self._clean_markdown_wrapper(repaired_content)
                try:
                    json.loads(repaired_cleaned)
                    logger.info(f"[{self.provider_type.value}] JSON repair successful!")
                    return (True, repaired_cleaned, None)
                except json.JSONDecodeError as repair_error:
                    logger.warning(f"[{self.provider_type.value}] Repaired JSON still invalid: {repair_error}")
                    # Update error for next attempt
                    original_error = repair_error
                    cleaned_content = repaired_cleaned
                    
            except Exception as repair_exception:
                logger.error(f"[{self.provider_type.value}] JSON repair exception: {repair_exception}")
                continue
        
        # All repair attempts failed
        logger.error(f"[{self.provider_type.value}] JSON repair failed after {max_retries} attempts")
        return (False, cleaned_content, f"Invalid JSON response: {original_error}")
    
    async def _diagnose_json_error(
        self,
        content: str,
        error: Exception,
    ) -> Optional[str]:
        """
        Diagnose a JSON parsing error using Gemini (fast, cheap).
        
        Args:
            content: The malformed JSON string
            error: The JSONDecodeError that was raised
            
        Returns:
            Diagnosis string or None if diagnosis failed
        """
        try:
            # Lazy import to avoid circular imports
            from app.ai.providers.gemini import gemini_provider
            from app.ai.prompts.json_repair_prompts import build_diagnosis_prompt
            
            diagnosis_prompt = build_diagnosis_prompt(
                json_content=content,
                error_message=str(error),
            )
            
            response = await gemini_provider.generate(
                prompt=diagnosis_prompt,
                temperature=0.1,  # Very low for consistent diagnosis
                max_tokens=150,   # Diagnosis should be brief
            )
            
            if response.success and response.content:
                return response.content.strip()
            else:
                logger.warning(f"Gemini diagnosis failed: {response.error}")
                return None
                
        except Exception as e:
            logger.error(f"JSON diagnosis exception: {e}")
            return None
    
    async def _repair_json(
        self,
        content: str,
        diagnosis: str,
        original_prompt: str,
        original_system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Repair malformed JSON using the current provider.
        
        This default implementation uses self.generate() to repair.
        Providers can override this for custom repair logic.
        
        Args:
            content: The malformed JSON string
            diagnosis: The diagnosis from Gemini
            original_prompt: The original user prompt
            original_system_prompt: The original system prompt
            
        Returns:
            Repaired JSON string or None if repair failed
        """
        try:
            from app.ai.prompts.json_repair_prompts import build_repair_prompt
            
            repair_prompt = build_repair_prompt(
                json_content=content,
                diagnosis=diagnosis,
                original_prompt=original_prompt,
                original_system_prompt=original_system_prompt,
            )
            
            response = await self.generate(
                prompt=repair_prompt,
                temperature=0.1,  # Very low for accurate repair
                max_tokens=2048,  # May need to regenerate full JSON
            )
            
            if response.success and response.content:
                return response.content.strip()
            else:
                logger.warning(f"JSON repair generation failed: {response.error}")
                return None
                
        except Exception as e:
            logger.error(f"JSON repair exception: {e}")
            return None
