"""
Pydantic schemas para la API de Human Feedback.

Estos schemas definen el contrato de la API REST.
Se usan en app/routers/feedback.py
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


# ============== ENUMS ==============

class FeedbackStatusEnum(str, Enum):
    """Estado del feedback de un elemento."""
    working = "working"
    broken = "broken"
    untested = "untested"


# ============== PREPARE VALIDATION ==============

class PrepareValidationRequest(BaseModel):
    """Request para preparar HTML para validación."""
    html: str = Field(..., min_length=10, description="HTML a preparar")

    class Config:
        json_schema_extra = {
            "example": {
                "html": "<!DOCTYPE html><html>...</html>"
            }
        }


class ElementInfoResponse(BaseModel):
    """Información de un elemento interactivo."""
    vid: int
    tag: str
    classes: List[str]
    element_id: Optional[str] = None
    text: str
    outer_html: str
    line_number: Optional[int] = None
    attributes: Dict[str, str]


class PrepareValidationResponse(BaseModel):
    """Response con HTML preparado y mapa de elementos."""
    html: str
    element_map: Dict[int, ElementInfoResponse]
    total_elements: int


# ============== FIX WITH FEEDBACK ==============

class FeedbackItem(BaseModel):
    """Feedback de un elemento individual."""
    vid: int = Field(..., ge=1, description="Validation ID del elemento")
    status: FeedbackStatusEnum
    message: Optional[str] = Field(None, max_length=500, description="Descripción del problema")

    class Config:
        json_schema_extra = {
            "example": {
                "vid": 3,
                "status": "broken",
                "message": "El botón debería abrir el modal de pago"
            }
        }


class FixWithFeedbackRequest(BaseModel):
    """Request para arreglar HTML con feedback del usuario."""
    html: str = Field(..., min_length=10, description="HTML original con data-vid")
    feedback: List[FeedbackItem] = Field(..., description="Lista de feedback por elemento")
    global_feedback: List[str] = Field(default=[], description="Feedback global (elementos faltantes)")

    class Config:
        json_schema_extra = {
            "example": {
                "html": "<!DOCTYPE html>...",
                "feedback": [
                    {"vid": 1, "status": "working"},
                    {"vid": 2, "status": "broken", "message": "No abre el modal"}
                ],
                "global_feedback": ["Falta botón de volver al inicio"]
            }
        }


class ChangeMade(BaseModel):
    """Descripción de un cambio realizado."""
    vid: Optional[int] = None
    description: str
    fix_type: str  # "css", "js", "html"


class FixWithFeedbackResponse(BaseModel):
    """Response con HTML arreglado."""
    success: bool
    fixed_html: str
    changes_made: List[ChangeMade]
    errors_found: int
    errors_fixed: int
    sandbox_errors: int
    user_reported_errors: int
    global_feedback_applied: int = 0


# ============== APPROVAL ==============

class ApproveLayoutRequest(BaseModel):
    """Request para aprobar layout final."""
    html: str
    device_id: Optional[str] = None


class ApproveLayoutResponse(BaseModel):
    """Response de aprobación."""
    success: bool
    message: str
    display_url: Optional[str] = None
