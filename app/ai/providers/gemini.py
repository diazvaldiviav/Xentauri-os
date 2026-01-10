"""
Gemini Provider - Google's GenAI SDK (New Standard).

Compatible with Gemini 2.0, 2.5 Flash-Lite, and Gemini 3 Flash.
"""

import time
import json
import logging
import warnings
from typing import Optional, Any, Dict

# --- NUEVO IMPORT PARA EL SDK V2 ---
from google import genai
from google.genai import types

from app.core.config import settings
from app.ai.providers.base import (
    AIProvider,
    AIResponse,
    ProviderType,
    TokenUsage
)

logger = logging.getLogger("jarvis.ai.gemini")

class GeminiProvider(AIProvider):
    provider_type = ProviderType.GEMINI

    def __init__(self, model: str = None, api_key: str = None):
        self.model = model or settings.GEMINI_MODEL
        self.api_key = api_key or settings.GEMINI_API_KEY

        # --- INICIALIZACIÓN CLIENTE V2 ---
        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini provider initialized (v2 SDK) with model: {self.model}")
        else:
            self._client = None
            logger.warning("Gemini API key not configured")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        response_mime_type: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        model_override: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        start_time = time.time()

        if not self._client:
            return self._error("API key missing", start_time)

        # Use model_override if provided, otherwise use default
        model = model_override or self.model

        try:
            # Build config kwargs dynamically
            config_kwargs = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "system_instruction": system_prompt,
            }
            
            # Only add response_mime_type and response_schema if provided
            if response_mime_type is not None:
                config_kwargs["response_mime_type"] = response_mime_type
            if response_schema is not None:
                config_kwargs["response_schema"] = response_schema
            
            # Construcción de configuración V2
            config = types.GenerateContentConfig(**config_kwargs)

            # Llamada al modelo V2
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            latency_ms = self._measure_latency(start_time)
            usage = self._extract_usage(response)

            # Check for truncation (finish_reason other than STOP)
            finish_reason = None
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, 'finish_reason', None)
                if finish_reason and str(finish_reason) not in ['STOP', 'FinishReason.STOP', '1']:
                    logger.warning(f"Gemini response may be truncated: finish_reason={finish_reason}")

            return AIResponse(
                content=response.text,
                provider=self.provider_type,
                model=model,
                usage=usage,
                latency_ms=latency_ms,
                success=True,
                raw_response=response,
            )

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return self._error(str(e), start_time)

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        use_reasoning_model: bool = True,
    ) -> AIResponse:
        """
        Generate structured JSON with schema validation using Gemini 3 Flash.
        
        Args:
            prompt: The prompt to generate content
            schema: JSON schema to validate response (use Model.model_json_schema())
            system_prompt: Optional system prompt
            temperature: Generation temperature (default 0.3 for consistency)
            max_tokens: Maximum tokens (default 4096 for large Scene Graphs)
            use_reasoning_model: If True, uses GEMINI_REASONING_MODEL from settings
            
        Returns:
            AIResponse with validated structured JSON
        """
        model = settings.GEMINI_REASONING_MODEL if use_reasoning_model else self.model

        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_mime_type="application/json",
            response_schema=schema,
            model_override=model,
        )

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        DEPRECATED: Use generate() with response_mime_type='application/json' or generate_structured() instead.
        
        This method is kept for backward compatibility but will be removed in a future version.
        """
        warnings.warn(
            "generate_json() is deprecated. Use generate() with response_mime_type='application/json' "
            "or generate_structured() for schema validation.",
            DeprecationWarning,
            stacklevel=2
        )
        start_time = time.time()
        if not self._client:
            return self._error("API Key missing", start_time)

        try:
            response = await self.generate(
                prompt=f"{prompt}\n\nIMPORTANT: Respond ONLY with valid JSON.",
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=1024,
                response_mime_type="application/json",
            )

            if not response.success:
                return response

            content = response.content.strip()
            # Limpieza básica por si acaso
            if content.startswith("```json"):
                content = content[7:-3].strip()

            return AIResponse(
                content=content,
                provider=self.provider_type,
                model=self.model,
                usage=response.usage,
                latency_ms=response.latency_ms,
                success=True,
            )

        except Exception as e:
            return self._error(str(e), start_time)

    async def generate_with_grounding(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_search: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> AIResponse:
        start_time = time.time()
        if not self._client:
            return self._error("API Key missing", start_time)

        try:
            # --- CONFIGURACIÓN DE HERRAMIENTAS V2 (SOLUCIÓN AL ERROR) ---
            tools_list = []
            if use_search:
                # Esta es la sintaxis correcta para google.genai y modelos 2.5
                tools_list.append(types.Tool(google_search=types.GoogleSearch()))

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt,
                tools=tools_list
            )

            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )

            latency_ms = self._measure_latency(start_time)
            usage = self._extract_usage(response)
            metadata = self._extract_grounding_metadata(response)

            return AIResponse(
                content=response.text,
                provider=self.provider_type,
                model=self.model,
                usage=usage,
                latency_ms=latency_ms,
                success=True,
                raw_response=response,
                metadata=metadata,
            )

        except Exception as e:
            return self._error(str(e), start_time)

    # --- HELPERS PRIVADOS ACTUALIZADOS ---

    def _extract_usage(self, response):
        # El SDK v2 a veces devuelve None si no hay uso reportado
        prompt_t = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        comp_t = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        return TokenUsage(prompt_tokens=prompt_t, completion_tokens=comp_t)

    def _extract_grounding_metadata(self, response):
        metadata = {}
        # En v2 la estructura es candidates[0].grounding_metadata
        if response.candidates and response.candidates[0].grounding_metadata:
            gm = response.candidates[0].grounding_metadata
            metadata['grounded'] = True
            metadata['search_queries'] = gm.search_entry_point.rendered_content if gm.search_entry_point else None

            sources = []
            if gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    if chunk.web:
                        sources.append({'uri': chunk.web.uri, 'title': chunk.web.title})
            if sources:
                metadata['sources'] = sources
        return metadata

    def _error(self, msg, start_time):
        return self._create_error_response(
            error=msg, model=self.model, latency_ms=self._measure_latency(start_time)
        )

# Instancia singleton
gemini_provider = GeminiProvider()
