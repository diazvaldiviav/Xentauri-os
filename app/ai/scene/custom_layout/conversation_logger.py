"""
Conversation Logger - Registro tipo "chat de WhatsApp" del flujo de modelos.

Sprint 11: Nuevo flujo de modelos:
1. Flash (NO thinking) → Genera HTML
2. Flash (NO thinking) → Visual concordance check
3. Flash (WITH thinking) → Technical diagnosis
4. Claude Opus → Repair con contexto completo

Permite analizar exactamente qué recibe y responde cada modelo.
"""

import os
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger("jarvis.ai.conversation_logger")

# Directorio para guardar las conversaciones
CONVERSATION_DIR = Path("/tmp/jarvis_conversations")


class ConversationLogger:
    """Logger tipo chat de WhatsApp para el flujo de modelos."""

    def __init__(self, request_id: str, user_request: str):
        """
        Inicializa una nueva conversación.

        Args:
            request_id: ID único del request
            user_request: Lo que pidió el usuario
        """
        self.request_id = request_id[:8]  # Primeros 8 chars para brevedad
        self.start_time = datetime.now()
        self.messages = []

        # Crear directorio si no existe
        CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)

        # Nombre del archivo: conversation_YYYYMMDD_HHMMSS_requestid.txt
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.file_path = CONVERSATION_DIR / f"conversation_{timestamp}_{self.request_id}.txt"

        # Escribir header
        self._write_header(user_request)

    def _write_header(self, user_request: str):
        """Escribe el header del archivo."""
        header = f"""{'='*80}
CONVERSACIÓN DE MODELOS - {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}
Request ID: {self.request_id}
{'='*80}

👤 USUARIO:
{user_request}

{'='*80}
FLUJO DE MODELOS (Sprint 11)
1. Flash (NO thinking) → Genera HTML
2. Flash (NO thinking) → Visual concordance
3. Flash (WITH thinking) → Technical diagnosis
4. Claude Opus → Repair
{'='*80}
"""
        self._write(header)

    def _write(self, content: str):
        """Escribe contenido al archivo."""
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.warning(f"Error writing to conversation log: {e}")

    def _format_timestamp(self) -> str:
        """Formato de timestamp tipo WhatsApp."""
        return datetime.now().strftime("%H:%M:%S")

    def _truncate(self, text: str, max_chars: int = 50000) -> str:
        """Trunca texto largo con indicador."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"\n\n[... TRUNCADO - {len(text) - max_chars} chars más ...]"

    # =========================================================================
    # STEP 1: Flash genera HTML
    # =========================================================================

    def log_flash_html_prompt(self, system_prompt: str, user_prompt: str):
        """Registra el prompt enviado a Flash para generar HTML."""
        content = f"""
[{self._format_timestamp()}] 📤 STEP 1: PROMPT A FLASH (HTML Generation - NO thinking)
{'─'*60}

## SYSTEM PROMPT:
{self._truncate(system_prompt, 10000)}

## USER PROMPT:
{self._truncate(user_prompt, 20000)}

"""
        self._write(content)

    def log_flash_html_response(self, response: str, latency_ms: float, tokens: int = 0):
        """Registra la respuesta de Flash (HTML generado)."""
        content = f"""
[{self._format_timestamp()}] 📥 STEP 1: RESPUESTA DE FLASH - HTML ({latency_ms:.0f}ms, {tokens} tokens)
{'─'*60}

{self._truncate(response)}

"""
        self._write(content)

    # =========================================================================
    # STEP 2: Flash Visual Concordance
    # =========================================================================

    def log_flash_concordance_prompt(self, prompt: str, has_screenshot: bool = True):
        """Registra el prompt de concordance a Flash."""
        screenshot_info = " + screenshot" if has_screenshot else ""
        content = f"""
[{self._format_timestamp()}] 📤 STEP 2: PROMPT A FLASH (Visual Concordance - NO thinking){screenshot_info}
{'─'*60}

## CONCORDANCE PROMPT:
{self._truncate(prompt, 5000)}

"""
        self._write(content)

    def log_flash_concordance_response(self, response: str, passed: bool, confidence: float, latency_ms: float):
        """Registra la respuesta de concordance de Flash."""
        status = "✅ PASS" if passed else "❌ FAIL"
        content = f"""
[{self._format_timestamp()}] 📥 STEP 2: RESPUESTA DE FLASH - Concordance {status} ({latency_ms:.0f}ms)
{'─'*60}
Confidence: {confidence:.2f}

{self._truncate(response)}

"""
        self._write(content)

    # =========================================================================
    # STEP 3: Flash Technical Diagnosis (WITH thinking)
    # =========================================================================

    def log_flash_diagnosis_prompt(self, system_prompt: str, user_prompt: str, num_images: int = 0):
        """Registra el prompt de diagnóstico a Flash."""
        images_info = f" + {num_images} imágenes" if num_images > 0 else ""
        content = f"""
[{self._format_timestamp()}] 📤 STEP 3: PROMPT A FLASH (Diagnosis - WITH thinking){images_info}
{'─'*60}

## SYSTEM PROMPT:
{self._truncate(system_prompt, 10000)}

## USER PROMPT (con contexto de Steps 1-2):
{self._truncate(user_prompt, 30000)}

"""
        self._write(content)

    def log_flash_diagnosis_response(self, response: str, latency_ms: float):
        """Registra la respuesta de diagnóstico de Flash."""
        content = f"""
[{self._format_timestamp()}] 📥 STEP 3: RESPUESTA DE FLASH - Diagnosis ({latency_ms:.0f}ms)
{'─'*60}

{self._truncate(response)}

"""
        self._write(content)

    # =========================================================================
    # STEP 4: Claude Opus Repair
    # =========================================================================

    def log_opus_repair_prompt(self, system_prompt: str, user_prompt: str, num_images: int = 0):
        """Registra el prompt de repair a Opus."""
        images_info = f" + {num_images} imágenes" if num_images > 0 else ""
        content = f"""
[{self._format_timestamp()}] 📤 STEP 4: PROMPT A OPUS (Repair - contexto completo){images_info}
{'─'*60}

## SYSTEM PROMPT:
{self._truncate(system_prompt, 10000)}

## USER PROMPT (con contexto de Steps 1-3):
{self._truncate(user_prompt, 40000)}

"""
        self._write(content)

    def log_opus_repair_response(self, response: str, latency_ms: float, success: bool = True):
        """Registra la respuesta de repair de Opus."""
        status = "✅" if success else "❌"
        content = f"""
[{self._format_timestamp()}] 📥 STEP 4: RESPUESTA DE OPUS - Repair {status} ({latency_ms:.0f}ms)
{'─'*60}

{self._truncate(response)}

"""
        self._write(content)

    # =========================================================================
    # Legacy methods (for backwards compatibility)
    # =========================================================================

    def log_opus_prompt(self, system_prompt: str, user_prompt: str):
        """Legacy: Registra prompt a Opus (now used for repair)."""
        self.log_opus_repair_prompt(system_prompt, user_prompt)

    def log_opus_response(self, response: str, latency_ms: float, tokens: int = 0):
        """Legacy: Registra respuesta de Opus."""
        self.log_opus_repair_response(response, latency_ms)

    def log_flash_prompt(self, system_prompt: str, user_prompt: str, num_images: int = 0):
        """Legacy: Registra prompt a Flash (diagnosis)."""
        self.log_flash_diagnosis_prompt(system_prompt, user_prompt, num_images)

    def log_flash_response(self, response: str, latency_ms: float):
        """Legacy: Registra respuesta de Flash."""
        self.log_flash_diagnosis_response(response, latency_ms)

    def log_pro_prompt(self, system_prompt: str, user_prompt: str, num_images: int = 0):
        """Legacy: Pro ya no se usa, mapea a Opus."""
        self.log_opus_repair_prompt(system_prompt, user_prompt, num_images)

    def log_pro_response(self, response: str, latency_ms: float, success: bool = True):
        """Legacy: Pro ya no se usa, mapea a Opus."""
        self.log_opus_repair_response(response, latency_ms, success)

    # =========================================================================
    # Utility methods
    # =========================================================================

    def log_validation_result(self, passed: bool, responsive: int, total: int, details: str = ""):
        """Registra el resultado de validación."""
        status = "✅ PASSED" if passed else "❌ FAILED"
        content = f"""
[{self._format_timestamp()}] 🔍 VALIDACIÓN: {status} ({responsive}/{total} responsive)
{'─'*60}
{details}

"""
        self._write(content)

    def log_pipeline_context(self, context_summary: str):
        """Registra el estado del PipelineContext acumulado."""
        content = f"""
[{self._format_timestamp()}] 📋 PIPELINE CONTEXT ACUMULADO
{'─'*60}
{context_summary}

"""
        self._write(content)

    def log_event(self, event: str, details: str = ""):
        """Registra un evento genérico."""
        content = f"""
[{self._format_timestamp()}] 📌 {event}
{details}

"""
        self._write(content)

    def log_error(self, error: str):
        """Registra un error."""
        content = f"""
[{self._format_timestamp()}] ❌ ERROR
{'─'*60}
{error}

"""
        self._write(content)

    def finalize(self, success: bool, total_time_ms: float):
        """Finaliza la conversación con resumen."""
        status = "✅ ÉXITO" if success else "❌ FALLO"
        content = f"""
{'='*80}
FIN DE CONVERSACIÓN - {status}
Tiempo total: {total_time_ms/1000:.1f}s
Archivo: {self.file_path}
{'='*80}
"""
        self._write(content)
        logger.info(f"Conversation log saved: {self.file_path}")
        return str(self.file_path)


# Singleton para mantener la conversación actual
_current_conversation: Optional[ConversationLogger] = None


def start_conversation(request_id: str, user_request: str) -> ConversationLogger:
    """Inicia una nueva conversación."""
    global _current_conversation
    _current_conversation = ConversationLogger(request_id, user_request)
    return _current_conversation


def get_current_conversation() -> Optional[ConversationLogger]:
    """Obtiene la conversación actual."""
    return _current_conversation


def end_conversation():
    """Termina la conversación actual."""
    global _current_conversation
    _current_conversation = None
