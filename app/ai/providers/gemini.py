"""
Gemini Provider - Google's GenAI SDK (New Standard).

Compatible with Gemini 2.0 and 2.5 Flash-Lite.
"""

import time
import json
import logging
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
        **kwargs
    ) -> AIResponse:
        start_time = time.time()

        if not self._client:
            return self._error("API key missing", start_time)

        try:
            # Construcción de configuración V2
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt,  # En v2 el system prompt va aquí directo
            )

            # Llamada al modelo V2
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )

            latency_ms = self._measure_latency(start_time)
            usage = self._extract_usage(response)

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
            logger.error(f"Gemini generation failed: {e}")
            return self._error(str(e), start_time)

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        start_time = time.time()
        if not self._client:
            return self._error("API Key missing", start_time)

        try:
            # En v2, JSON mode es nativo y más estricto
            config = types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1024,
                response_mime_type="application/json",
                system_instruction=system_prompt
            )

            response = self._client.models.generate_content(
                model=self.model,
                contents=f"{prompt}\n\nIMPORTANT: Respond ONLY with valid JSON.",
                config=config
            )

            content = response.text.strip()
            # Limpieza básica por si acaso
            if content.startswith("```json"):
                content = content[7:-3].strip()

            latency_ms = self._measure_latency(start_time)
            usage = self._extract_usage(response)

            return AIResponse(
                content=content,
                provider=self.provider_type,
                model=self.model,
                usage=usage,
                latency_ms=latency_ms,
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
