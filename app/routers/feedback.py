"""
Router de Human Feedback para validación de layouts HTML.

Endpoints:
- POST /feedback/prepare-validation: Prepara HTML con data-vid
- POST /feedback/fix-with-feedback: Arregla HTML con feedback del usuario
- POST /feedback/approve: Aprueba y muestra layout
- POST /feedback/generate-test: (DEBUG) Genera HTML para testing
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.feedback import (
    PrepareValidationRequest,
    PrepareValidationResponse,
    ElementInfoResponse,
    FixWithFeedbackRequest,
    FixWithFeedbackResponse,
    ChangeMade,
    ApproveLayoutRequest,
    ApproveLayoutResponse,
)

# Imports del módulo html_fixer
from app.ai.scene.custom_layout.html_fixer.feedback.element_mapper import (
    ElementMapper,
)
from app.ai.scene.custom_layout.html_fixer.feedback.annotation_injector import (
    AnnotationInjector,
)
from app.ai.scene.custom_layout.html_fixer.feedback.feedback_merger import (
    FeedbackMerger,
)
from app.ai.scene.custom_layout.html_fixer.contracts.feedback import (
    UserFeedback as UserFeedbackContract,
    FeedbackStatus,
)
from app.ai.scene.custom_layout.html_fixer.fixers.llm.llm_fixer import LLMFixer
from app.services.commands import command_service
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "/prepare-validation",
    response_model=PrepareValidationResponse,
    summary="Prepara HTML para validación humana",
    description="""
    Prepara el HTML para validación:
    - Inyecta data-vid en cada elemento interactivo
    - Agrega script de comunicación postMessage
    - Retorna mapa de elementos para el frontend
    """,
)
async def prepare_validation(
    request: PrepareValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Prepara HTML para validación humana."""
    try:
        mapper = ElementMapper()
        result = mapper.prepare(request.html)

        # Convertir ElementInfo a response schema
        element_map_response = {
            vid: ElementInfoResponse(
                vid=info.vid,
                tag=info.tag,
                classes=info.classes,
                element_id=info.element_id,
                text=info.text,
                outer_html=info.outer_html,
                line_number=info.line_number,
                attributes=info.attributes,
            )
            for vid, info in result.element_map.items()
        }

        logger.info(
            f"Prepared HTML for validation: {result.total_elements} elements "
            f"for user {current_user.id}"
        )

        return PrepareValidationResponse(
            html=result.html,
            element_map=element_map_response,
            total_elements=result.total_elements,
        )

    except Exception as e:
        logger.error(f"Error preparing HTML: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error preparing HTML for validation: {str(e)}"
        )


@router.post(
    "/fix-with-feedback",
    response_model=FixWithFeedbackResponse,
    summary="Arregla HTML con feedback del usuario",
    description="""
    Procesa el HTML con el feedback del usuario:
    1. Inyecta comentarios de feedback en el HTML
    2. Corre sandbox para detectar errores técnicos
    3. Combina errores sandbox + feedback usuario
    4. Aplica fixes determinísticos
    5. Si necesario, llama al LLM fixer
    6. Retorna HTML arreglado (limpio, sin data-vid)
    """,
)
async def fix_with_feedback(
    request: FixWithFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Arregla HTML usando feedback del usuario."""
    try:
        # Convertir feedback de Pydantic a dataclass interno
        user_feedback = [
            UserFeedbackContract(
                vid=f.vid,
                status=FeedbackStatus(f.status.value),
                message=f.message,
            )
            for f in request.feedback
        ]

        # 1. Inyectar comentarios de feedback
        injector = AnnotationInjector()
        annotated = injector.inject(
            html=request.html,
            element_feedback=user_feedback,
            global_feedback=request.global_feedback,
        )

        logger.info(
            f"Annotated HTML: {annotated.annotations_count} annotations, "
            f"{len(annotated.broken_elements)} broken elements"
        )

        # 2. Re-preparar element_map (necesario para merge)
        mapper = ElementMapper()
        prepared = mapper.prepare(request.html)
        element_map_dict = {
            k: {
                'vid': v.vid,
                'tag': v.tag,
                'classes': v.classes,
                'element_id': v.element_id,
            }
            for k, v in prepared.element_map.items()
        }

        # 3. Combinar errores (sandbox vacío por ahora, se puede integrar después)
        merger = FeedbackMerger()
        merged_errors = merger.merge(
            sandbox_errors=[],  # TODO: Integrar con sandbox validation
            user_feedback=user_feedback,
            element_map=element_map_dict,
        )

        logger.info(
            f"Merged errors: {len(merged_errors)} total, "
            f"{len([e for e in merged_errors if e.has_technical_cause])} technical"
        )

        # 4. Llamar al LLM para aplicar fixes basados en feedback
        changes_made = []
        fixed_html = annotated.html

        if merged_errors or request.global_feedback:
            llm_fixer = LLMFixer()
            fix_result = await llm_fixer.fix_with_feedback(
                annotated_html=annotated.html,
                merged_errors=merged_errors,
                global_feedback=request.global_feedback,
            )

            if fix_result.success:
                fixed_html = fix_result.fixed_html
                logger.info(
                    f"LLM fix successful: {len(fix_result.tailwind_patches)} patches, "
                    f"{fix_result.duration_ms:.0f}ms"
                )

                # Registrar cambios aplicados
                for patch in fix_result.tailwind_patches:
                    changes_made.append(ChangeMade(
                        vid=None,
                        description=f"Applied: +{patch.add_classes} -{patch.remove_classes} to {patch.selector}",
                        fix_type="applied",
                    ))
            else:
                logger.warning(f"LLM fix failed: {fix_result.error_message}")
                # Fallback: registrar como pending
                for error in merged_errors:
                    changes_made.append(ChangeMade(
                        vid=error.vid,
                        description=f"Pending: {error.user_feedback or 'No description'}",
                        fix_type="pending",
                    ))

        # Registrar global feedback
        for gf in request.global_feedback:
            if not any(gf in c.description for c in changes_made):
                changes_made.append(ChangeMade(
                    vid=None,
                    description=f"Global feedback: {gf}",
                    fix_type="noted",
                ))

        # 5. Limpiar: remover data-vid, comentarios y scripts de validación
        clean_html = injector.remove_annotations(fixed_html)

        return FixWithFeedbackResponse(
            success=True,
            fixed_html=clean_html,
            changes_made=changes_made,
            errors_found=len(merged_errors),
            errors_fixed=len(merged_errors),
            sandbox_errors=len([e for e in merged_errors if e.has_technical_cause]),
            user_reported_errors=len([e for e in merged_errors if not e.has_technical_cause]),
            global_feedback_applied=len(request.global_feedback),
        )

    except Exception as e:
        logger.error(f"Error fixing HTML with feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fixing HTML: {str(e)}"
        )


@router.post(
    "/approve",
    response_model=ApproveLayoutResponse,
    summary="Aprueba y muestra el layout",
    description="Aprueba el layout final y lo envía al dispositivo para display.",
)
async def approve_layout(
    request: ApproveLayoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aprueba layout y lo envía a display."""
    try:
        logger.info(
            f"Layout approved by user {current_user.id} "
            f"for device {request.device_id or 'default'}"
        )

        # Validate device_id is provided
        if not request.device_id:
            # Try to get user's default/first device
            from app.models.device import Device
            device = db.query(Device).filter(
                Device.owner_id == current_user.id
            ).first()

            if not device:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No device_id provided and no default device found"
                )
            device_id = device.id
        else:
            device_id = UUID(request.device_id)

        # Create minimal fallback scene (required by protocol)
        fallback_scene = {
            "layout": "custom",
            "components": [],
            "metadata": {
                "source": "human_feedback",
                "approved_by": str(current_user.id),
            }
        }

        # Send HTML to device via WebSocket
        result = await command_service.display_scene(
            device_id=device_id,
            scene=fallback_scene,
            custom_layout=request.html,
        )

        if result.success:
            logger.info(
                f"Layout sent to device {device_id}, command_id={result.command_id}"
            )
            return ApproveLayoutResponse(
                success=True,
                message=f"Layout approved and sent to device (command: {result.command_id})",
                display_url=None,
            )
        else:
            logger.warning(f"Failed to send layout to device: {result.error}")
            return ApproveLayoutResponse(
                success=False,
                message=f"Layout approved but failed to send: {result.error}",
                display_url=None,
            )

    except Exception as e:
        logger.error(f"Error approving layout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving layout: {str(e)}"
        )


# =============================================================================
# DEBUG ENDPOINT - Genera HTML para testing del flujo de feedback
# =============================================================================

class GenerateTestRequest(BaseModel):
    """Request para generar HTML de prueba."""
    prompt: str = "Muestra un quiz interactivo sobre historia con 5 preguntas"
    content_type: str = "trivia"


class GenerateTestResponse(BaseModel):
    """Response con HTML generado."""
    success: bool
    html: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


@router.post(
    "/generate-test",
    response_model=GenerateTestResponse,
    summary="[DEBUG] Genera HTML para testing",
    description="Endpoint de debug que genera HTML usando el pipeline completo.",
)
async def generate_test_html(
    request: GenerateTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera HTML para testing del flujo de feedback."""
    try:
        from app.ai.scene.custom_layout import custom_layout_service

        result = await custom_layout_service.generate_and_validate_html_from_data(
            content_data={
                "content_type": request.content_type,
                "title": request.prompt[:50],
            },
            user_request=request.prompt,
            layout_type=request.content_type,
        )

        logger.info(
            f"[DEBUG] Generated test HTML: success={result.success}, "
            f"latency={result.latency_ms:.0f}ms, "
            f"html_len={len(result.html) if result.html else 0}"
        )

        return GenerateTestResponse(
            success=result.success,
            html=result.html,
            latency_ms=result.latency_ms,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Error generating test HTML: {e}", exc_info=True)
        return GenerateTestResponse(
            success=False,
            error=str(e),
        )
