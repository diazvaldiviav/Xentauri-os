"""
FeedbackMerger - Combina errores del sandbox con feedback del usuario.

Prioriza la información del usuario sobre el sandbox cuando hay conflicto,
ya que el usuario tiene contexto funcional que el sandbox no puede detectar.
"""

from typing import List, Dict, Optional, Any
import logging

from ..contracts.feedback import (
    UserFeedback,
    FeedbackStatus,
    MergedError,
)

logger = logging.getLogger(__name__)


class FeedbackMerger:
    """Combina información técnica del sandbox con feedback del usuario."""

    def merge(
        self,
        sandbox_errors: List[Any],
        user_feedback: List[UserFeedback],
        element_map: Dict[int, dict],
    ) -> List[MergedError]:
        """
        Combina errores técnicos con feedback del usuario.

        Casos manejados:
        1. Sandbox detectó error + Usuario confirmó broken → Alta confianza, fix prioritario
        2. Sandbox detectó error + Usuario dijo working → Posible falso positivo (ignorar)
        3. Sandbox no detectó + Usuario dijo broken → Error funcional, necesita LLM
        4. Sandbox no detectó + Usuario dijo working → OK, no hacer nada

        Args:
            sandbox_errors: Errores detectados por el sandbox automático
            user_feedback: Feedback del usuario por elemento
            element_map: Mapa vid -> ElementInfo para referencia

        Returns:
            Lista de MergedError para procesar
        """
        merged = []

        # Indexar errores del sandbox por vid
        sandbox_by_vid = self._index_sandbox_errors(sandbox_errors, element_map)

        # Indexar feedback por vid
        feedback_by_vid = {f.vid: f for f in user_feedback}

        # Procesar todos los elementos con feedback
        for feedback in user_feedback:
            if feedback.status == FeedbackStatus.UNTESTED:
                continue

            vid = feedback.vid
            element_info = element_map.get(vid, {})
            selector = self._get_selector(element_info)

            sandbox_error = sandbox_by_vid.get(vid)

            # Caso 1 & 3: Usuario dijo que no funciona
            if feedback.status == FeedbackStatus.BROKEN:
                merged.append(MergedError(
                    vid=vid,
                    element_selector=selector,
                    technical_error=sandbox_error.get('message') if sandbox_error else None,
                    technical_type=sandbox_error.get('type') if sandbox_error else None,
                    user_status=FeedbackStatus.BROKEN,
                    user_feedback=feedback.message,
                    has_technical_cause=sandbox_error is not None,
                    requires_llm=True,
                    confidence=0.95 if sandbox_error else 0.8,
                ))

                logger.debug(
                    f"Element #{vid} marked broken. "
                    f"Technical cause: {sandbox_error is not None}"
                )

            # Caso 2: Sandbox detectó pero usuario dijo que funciona
            elif feedback.status == FeedbackStatus.WORKING and sandbox_error:
                logger.info(
                    f"Element #{vid} marked working by user but sandbox detected error. "
                    f"Treating as false positive: {sandbox_error.get('message')}"
                )
                # No agregamos a merged porque el usuario dijo que funciona

        # Procesar errores del sandbox que no tienen feedback explícito
        # (elementos no testeados pero con error técnico)
        for vid, sandbox_error in sandbox_by_vid.items():
            if vid not in feedback_by_vid or feedback_by_vid[vid].status == FeedbackStatus.UNTESTED:
                element_info = element_map.get(vid, {})
                selector = self._get_selector(element_info)

                merged.append(MergedError(
                    vid=vid,
                    element_selector=selector,
                    technical_error=sandbox_error.get('message'),
                    technical_type=sandbox_error.get('type'),
                    user_status=FeedbackStatus.UNTESTED,
                    user_feedback=None,
                    has_technical_cause=True,
                    requires_llm=True,
                    confidence=0.6,  # Menor confianza sin validación humana
                ))

        return merged

    def _index_sandbox_errors(
        self,
        errors: List[Any],
        element_map: Dict[int, dict],
    ) -> Dict[int, dict]:
        """Indexa errores del sandbox por vid."""
        indexed = {}

        for error in errors:
            # Buscar qué vid corresponde a este error
            vid = self._find_vid_for_error(error, element_map)
            if vid:
                indexed[vid] = {
                    'message': str(error),
                    'type': error.error_type.value if hasattr(error, 'error_type') else 'unknown',
                }

        return indexed

    def _find_vid_for_error(
        self,
        error: Any,
        element_map: Dict[int, dict],
    ) -> Optional[int]:
        """Encuentra el vid del elemento que tiene el error."""
        error_selector = getattr(error, 'selector', '')

        for vid, info in element_map.items():
            if self._selectors_match(error_selector, info):
                return vid

        return None

    def _selectors_match(self, error_selector: str, element_info: dict) -> bool:
        """Verifica si un selector de error corresponde a un elemento."""
        if not error_selector:
            return False

        # Por ID
        if error_selector.startswith('#'):
            return element_info.get('element_id') == error_selector[1:]

        # Por clase
        if error_selector.startswith('.'):
            classes = element_info.get('classes', [])
            return error_selector[1:] in classes

        # Por data-vid
        if 'data-vid' in error_selector:
            try:
                vid_in_selector = int(error_selector.split('data-vid')[1].strip('="\'[]'))
                return element_info.get('vid') == vid_in_selector
            except (ValueError, IndexError):
                pass

        # Por tag
        return element_info.get('tag') == error_selector

    def _get_selector(self, element_info: dict) -> str:
        """Genera selector CSS para un elemento."""
        if element_info.get('element_id'):
            return f"#{element_info['element_id']}"

        classes = element_info.get('classes', [])
        if classes:
            tag = element_info.get('tag', 'div')
            return f"{tag}.{'.'.join(classes[:2])}"  # Max 2 clases

        vid = element_info.get('vid', 0)
        return f'[data-vid="{vid}"]'
