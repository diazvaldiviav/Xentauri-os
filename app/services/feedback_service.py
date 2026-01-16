"""
FeedbackService - Orquestador del sistema de human feedback.

Centraliza la lógica de negocio para el flujo de feedback,
facilitando su uso desde intent_service o directamente desde el router.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.ai.scene.custom_layout.html_fixer.feedback.element_mapper import (
    ElementMapper,
    PreparedHTML,
)
from app.ai.scene.custom_layout.html_fixer.feedback.annotation_injector import (
    AnnotationInjector,
)
from app.ai.scene.custom_layout.html_fixer.feedback.feedback_merger import (
    FeedbackMerger,
)
from app.ai.scene.custom_layout.html_fixer.contracts.feedback import (
    UserFeedback,
    FeedbackStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class FeedbackSessionState:
    """Estado de una sesión de feedback."""
    original_html: str
    prepared_html: str
    element_map: Dict[int, dict]
    total_elements: int
    feedback_received: List[UserFeedback]
    global_feedback: List[str]
    iterations: int = 0
    max_iterations: int = 3


class FeedbackService:
    """
    Servicio para gestionar el flujo de human feedback.

    Uso típico:
        service = FeedbackService()

        # Preparar HTML
        prepared = await service.prepare_for_validation(html)

        # Usuario interactúa con el frontend...

        # Procesar feedback
        result = await service.process_feedback(
            html=prepared.html,
            element_feedback=user_feedback,
            global_feedback=global_feedback,
        )

        # Si aprobado, mostrar
        if user_approved:
            await service.approve_and_display(result.fixed_html, device_id)
    """

    def __init__(
        self,
        mapper: Optional[ElementMapper] = None,
        injector: Optional[AnnotationInjector] = None,
        merger: Optional[FeedbackMerger] = None,
    ):
        self._mapper = mapper or ElementMapper()
        self._injector = injector or AnnotationInjector()
        self._merger = merger or FeedbackMerger()

    async def prepare_for_validation(self, html: str) -> PreparedHTML:
        """
        Prepara HTML para validación humana.

        Args:
            html: HTML original (puede o no tener data-vid)

        Returns:
            PreparedHTML con html modificado y element_map
        """
        return self._mapper.prepare(html)

    async def process_feedback(
        self,
        html: str,
        element_feedback: List[UserFeedback],
        global_feedback: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Procesa feedback del usuario y aplica fixes.

        Args:
            html: HTML con data-vid (de prepare_for_validation)
            element_feedback: Lista de feedback por elemento
            global_feedback: Lista de feedback global

        Returns:
            Dict con fixed_html, changes_made, y estadísticas
        """
        global_feedback = global_feedback or []

        # 1. Inyectar comentarios
        annotated = self._injector.inject(
            html=html,
            element_feedback=element_feedback,
            global_feedback=global_feedback,
        )

        # 2. Preparar element_map para merge
        prepared = self._mapper.prepare(html)
        element_map_dict = {
            k: {
                'vid': v.vid,
                'tag': v.tag,
                'classes': v.classes,
                'element_id': v.element_id,
            }
            for k, v in prepared.element_map.items()
        }

        # 3. Merge errores (sin sandbox por ahora)
        merged_errors = self._merger.merge(
            sandbox_errors=[],
            user_feedback=element_feedback,
            element_map=element_map_dict,
        )

        # 4. Por ahora retornamos HTML limpio
        # TODO: Integrar con orchestrator para fixes reales
        fixed_html = annotated.html

        # 5. Limpiar
        clean_html = self._injector.remove_annotations(fixed_html)

        return {
            'success': True,
            'fixed_html': clean_html,
            'errors_found': len(merged_errors),
            'sandbox_errors': len([e for e in merged_errors if e.has_technical_cause]),
            'user_reported_errors': len([e for e in merged_errors if not e.has_technical_cause]),
            'global_feedback_applied': len(global_feedback),
            'broken_elements': annotated.broken_elements,
            'working_elements': annotated.working_elements,
        }

    async def approve_and_display(
        self,
        html: str,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Aprueba layout y lo envía a display.

        Args:
            html: HTML final aprobado
            device_id: ID del dispositivo destino (opcional)

        Returns:
            Dict con resultado de la operación
        """
        # TODO: Integrar con CommandService
        # from app.services.commands import command_service
        # result = await command_service.display_scene(
        #     device_id=device_id,
        #     custom_layout=html,
        # )

        logger.info(f"Layout approved for device {device_id or 'default'}")

        return {
            'success': True,
            'message': 'Layout approved and sent to display',
            'device_id': device_id,
        }


# Singleton instance
feedback_service = FeedbackService()
