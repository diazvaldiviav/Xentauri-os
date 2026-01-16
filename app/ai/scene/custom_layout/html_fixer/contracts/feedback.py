"""
Contratos de datos para el sistema de feedback.

Estos dataclasses son internos al módulo html_fixer.
Para la API pública, usar los schemas Pydantic en app/schemas/feedback.py
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum


class FeedbackStatus(Enum):
    """Estado del feedback de un elemento."""
    WORKING = "working"
    BROKEN = "broken"
    UNTESTED = "untested"


@dataclass
class UserFeedback:
    """Feedback de un elemento dado por el usuario."""
    vid: int
    status: FeedbackStatus
    message: Optional[str] = None  # Solo si status == BROKEN


@dataclass
class GlobalFeedback:
    """Feedback global (elementos faltantes, cambios generales)."""
    message: str
    category: str = "missing"  # "missing", "style", "behavior", "other"


@dataclass
class FeedbackRequest:
    """Request completo de feedback del frontend."""
    html: str
    element_feedback: List[UserFeedback]
    global_feedback: List[str] = field(default_factory=list)


@dataclass
class MergedError:
    """Error combinado: técnico (sandbox) + funcional (usuario)."""
    vid: int
    element_selector: str

    # Del sandbox (puede ser None si sandbox no detectó nada)
    technical_error: Optional[str] = None
    technical_type: Optional[str] = None  # "z_index", "pointer_events", etc.

    # Del usuario
    user_status: FeedbackStatus = FeedbackStatus.UNTESTED
    user_feedback: Optional[str] = None

    # Metadata
    has_technical_cause: bool = False
    requires_llm: bool = True
    confidence: float = 0.5


@dataclass
class AnnotatedHTML:
    """HTML con comentarios de feedback inyectados."""
    html: str
    annotations_count: int
    working_elements: List[int]
    broken_elements: List[int]
    global_feedback_count: int = 0


@dataclass
class FeedbackFixResult:
    """Resultado del proceso de fix con feedback."""
    success: bool
    fixed_html: str
    changes_made: List[Dict]
    errors_found: int
    errors_fixed: int
    sandbox_errors: int
    user_reported_errors: int
    global_feedback_applied: int = 0
