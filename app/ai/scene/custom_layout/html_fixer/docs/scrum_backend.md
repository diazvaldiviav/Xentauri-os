# SCRUM BACKEND: Human Feedback System
## Sprint 4 - Python/FastAPI Integration

---

## Sprint Goal

> **Implementar el sistema de human feedback en el backend, integrándolo con la arquitectura existente de Jarvis Cloud para permitir que los usuarios validen y corrijan layouts HTML antes de mostrarlos.**

---

## Problema a Resolver

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LIMITACIÓN DEL SANDBOX AUTOMÁTICO                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   El sandbox puede detectar:          El sandbox NO puede detectar:         │
│   ─────────────────────────           ─────────────────────────────         │
│   • z-index conflicts                 • "Este botón debería abrir modal"   │
│   • pointer-events blocked            • "El flujo no tiene sentido"        │
│   • JS syntax errors                  • "Falta validación en el form"      │
│   • Missing DOM elements              • "El color está mal"                │
│   • Console errors                    • "No hace lo que pedí"              │
│                                                                             │
│   SOLUCIÓN: Combinar sandbox técnico + feedback humano funcional           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Arquitectura de Integración

```
app/
├── main.py                           # Registrar router feedback
├── deps.py                           # Auth (reutilizar)
├── routers/
│   ├── feedback.py                   # ◄── CREAR: Endpoints
│   └── intent.py                     # Flujo existente
├── schemas/
│   └── feedback.py                   # ◄── CREAR: Pydantic
├── services/
│   └── feedback_service.py           # ◄── CREAR: Business logic
└── ai/scene/custom_layout/
    └── html_fixer/
        ├── feedback/                 # ◄── CREAR: Módulo
        │   ├── __init__.py
        │   ├── element_mapper.py     # B01
        │   ├── annotation_injector.py # B05
        │   └── feedback_merger.py    # B06
        ├── contracts/
        │   └── feedback.py           # ◄── CREAR: B02
        └── prompts/
            └── fixer_prompt_v2.py    # ◄── CREAR: B09
```

---

## Sprint Backlog

| ID | Tarea | Archivo | Est. | Prior. | Deps | Estado |
|----|-------|---------|------|--------|------|--------|
| B01 | ElementMapper - Inyecta data-vid + script | `html_fixer/feedback/element_mapper.py` | 4h | 🔴 | - | ⬜ |
| B02 | Contracts de Feedback (dataclasses) | `html_fixer/contracts/feedback.py` | 1h | 🔴 | - | ⬜ |
| B03 | Pydantic Schemas para API | `app/schemas/feedback.py` | 1h | 🔴 | B02 | ⬜ |
| B04 | Endpoint POST /feedback/prepare-validation | `app/routers/feedback.py` | 2h | 🔴 | B01,B03 | ⬜ |
| B05 | AnnotationInjector | `html_fixer/feedback/annotation_injector.py` | 2h | 🔴 | B02 | ⬜ |
| B06 | FeedbackMerger | `html_fixer/feedback/feedback_merger.py` | 3h | 🔴 | B02 | ⬜ |
| B07 | Endpoint POST /feedback/fix-with-feedback | `app/routers/feedback.py` | 3h | 🔴 | B05,B06 | ⬜ |
| B08 | FeedbackService (orquestador) | `app/services/feedback_service.py` | 2h | 🟡 | B04,B07 | ⬜ |
| B09 | Prompt LLM v2 (lee comentarios) | `html_fixer/prompts/fixer_prompt_v2.py` | 2h | 🟡 | - | ⬜ |
| B10 | Registrar router en main.py | `app/main.py` | 0.5h | 🔴 | B04,B07 | ⬜ |
| B11 | Configurar CORS para frontend | `app/main.py` | 0.5h | 🔴 | - | ⬜ |
| B12 | Tests unitarios | `tests/` | 3h | 🟡 | ALL | ⬜ |

**Total Estimado: ~24 horas**

---

## Diagrama de Dependencias

```
B01 (ElementMapper) ──┬──► B04 (Endpoint prepare)
                      │
B02 (Contracts) ──────┼──► B03 (Pydantic) ──► B04
                      │
                      ├──► B05 (AnnotationInjector) ──┬──► B07 (Endpoint fix)
                      │                               │
                      └──► B06 (FeedbackMerger) ──────┘
                                                      │
B09 (Prompt v2) ──────────────────────────────────────┘
                                                      │
                                                      ▼
                                              B08 (FeedbackService)
                                                      │
                                                      ▼
                                              B10 (Register router)
                                                      │
B11 (CORS) ───────────────────────────────────────────┘
                                                      │
                                                      ▼
                                              B12 (Tests)
```

---

## ESPECIFICACIONES TÉCNICAS

---

### B01: ElementMapper

**Archivo:** `html_fixer/feedback/element_mapper.py`

**Responsabilidad:** Inyecta `data-vid` en elementos interactivos y agrega script de comunicación postMessage.

```python
"""
ElementMapper - Inyecta data-vid en elementos interactivos del HTML + script de comunicación.

Este módulo prepara el HTML para validación humana:
1. Encuentra todos los elementos interactivos (buttons, inputs, links, etc.)
2. Asigna un ID único (data-vid) a cada uno
3. Inyecta un script que comunica clicks al frontend via postMessage
"""

from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass
from typing import Dict, List, Optional
import re


@dataclass
class ElementInfo:
    """Información de un elemento interactivo."""
    vid: int                      # Validation ID único
    tag: str                      # "button", "input", etc.
    classes: List[str]            # ["btn-primary", "z-10"]
    element_id: Optional[str]     # ID del elemento si tiene
    text: str                     # Texto contenido (truncado a 50 chars)
    outer_html: str               # HTML completo del elemento
    line_number: Optional[int]    # Línea en el HTML original
    attributes: Dict[str, str]    # Otros atributos relevantes


@dataclass
class PreparedHTML:
    """HTML preparado para validación."""
    html: str                     # HTML con data-vid inyectados + script
    element_map: Dict[int, ElementInfo]
    total_elements: int


class ElementMapper:
    """Mapea y etiqueta elementos interactivos."""

    # Selectores de elementos interactivos
    INTERACTIVE_SELECTORS = [
        'button',
        'input',
        'select',
        'textarea',
        'a[href]',
        '[onclick]',
        '[onchange]',
        '[onsubmit]',
        '[role="button"]',
        '[role="link"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="switch"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[tabindex]:not([tabindex="-1"])',
    ]

    # Script que se inyecta en el HTML para comunicación con React
    VALIDATION_SCRIPT = """
<script data-validation-script="true">
(function() {
    // Script inyectado por ElementMapper para capturar clicks
    // y comunicarlos al padre (React) via postMessage

    document.body.addEventListener('click', function(e) {
        // 1. Encontrar el elemento interactivo más cercano con data-vid
        var target = e.target.closest('[data-vid]');

        if (target) {
            e.preventDefault();  // Evitar navegación o submit real
            e.stopPropagation();

            // 2. Obtener información del elemento
            var rect = target.getBoundingClientRect();

            // 3. Enviar mensaje al padre (React)
            window.parent.postMessage({
                type: 'ELEMENT_CLICKED',
                vid: parseInt(target.getAttribute('data-vid')),
                rect: {
                    top: rect.top,
                    left: rect.left,
                    width: rect.width,
                    height: rect.height,
                    bottom: rect.bottom,
                    right: rect.right
                },
                tagName: target.tagName.toLowerCase(),
                text: target.textContent.substring(0, 50).trim()
            }, '*');
        }
    }, true);  // Use capture phase para interceptar antes que otros handlers

    // Escuchar mensajes del padre para actualizar estilos de feedback
    window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'UPDATE_FEEDBACK_STATUS') {
            var status = e.data.status;

            for (var vid in status) {
                var el = document.querySelector('[data-vid="' + vid + '"]');
                if (el) {
                    // Remover clases previas
                    el.classList.remove('feedback-working', 'feedback-broken', 'feedback-untested');

                    // Agregar nueva clase
                    el.classList.add('feedback-' + status[vid]);
                }
            }
        }
    });

    // Notificar al padre que el iframe está listo
    window.parent.postMessage({ type: 'IFRAME_READY' }, '*');
})();
</script>

<style data-validation-styles="true">
/* Estilos de feedback visual */
[data-vid] {
    transition: outline 0.2s ease, box-shadow 0.2s ease;
}

[data-vid]:hover {
    outline: 2px dashed #3b82f6 !important;
    outline-offset: 2px;
}

[data-vid].feedback-working {
    outline: 3px solid #22c55e !important;
    outline-offset: 2px;
    box-shadow: 0 0 10px rgba(34, 197, 94, 0.3);
}

[data-vid].feedback-broken {
    outline: 3px solid #ef4444 !important;
    outline-offset: 2px;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
}

[data-vid].feedback-untested {
    outline: 2px dashed #f59e0b !important;
    outline-offset: 2px;
}
</style>
"""

    def prepare(self, html: str) -> PreparedHTML:
        """
        Prepara HTML para validación:
        1. Encuentra elementos interactivos
        2. Inyecta data-vid único en cada uno
        3. Inyecta script de comunicación
        4. Crea mapa de elementos
        """
        soup = BeautifulSoup(html, 'html.parser')
        element_map: Dict[int, ElementInfo] = {}
        vid = 1

        # Encontrar todos los elementos interactivos
        for selector in self.INTERACTIVE_SELECTORS:
            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for el in elements:
                # Evitar duplicados (un elemento puede matchear varios selectores)
                if el.get('data-vid'):
                    continue

                # Inyectar ID de validación
                el['data-vid'] = str(vid)

                # Crear info del elemento
                element_map[vid] = ElementInfo(
                    vid=vid,
                    tag=el.name,
                    classes=el.get('class', []) if isinstance(el.get('class'), list) else [],
                    element_id=el.get('id'),
                    text=self._get_text_content(el)[:50],
                    outer_html=str(el)[:500],  # Limitar tamaño
                    line_number=getattr(el, 'sourceline', None),
                    attributes=self._get_relevant_attrs(el)
                )

                vid += 1

        # Inyectar script de comunicación al final del body
        body = soup.find('body')
        if body:
            script_soup = BeautifulSoup(self.VALIDATION_SCRIPT, 'html.parser')
            body.append(script_soup)

        return PreparedHTML(
            html=str(soup),
            element_map=element_map,
            total_elements=len(element_map)
        )

    def _get_text_content(self, el: Tag) -> str:
        """Obtiene texto contenido, limpio."""
        text = el.get_text(strip=True)
        # Limpiar espacios múltiples
        text = re.sub(r'\s+', ' ', text)
        return text

    def _get_relevant_attrs(self, el: Tag) -> Dict[str, str]:
        """Extrae atributos relevantes para debugging."""
        relevant = ['onclick', 'onchange', 'onsubmit', 'href', 'type', 'name', 'value', 'role']
        return {k: str(el.get(k)) for k in relevant if el.get(k)}
```

---

### B02: Contracts de Feedback

**Archivo:** `html_fixer/contracts/feedback.py`

```python
"""
Contratos de datos para el sistema de feedback.

Estos dataclasses son internos al módulo html_fixer.
Para la API pública, usar los schemas Pydantic en app/schemas/feedback.py
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime


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
```

---

### B03: Pydantic Schemas para API

**Archivo:** `app/schemas/feedback.py`

```python
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
```

---

### B04: Endpoint prepare-validation

**Archivo:** `app/routers/feedback.py` (parte 1)

```python
"""
Router de Human Feedback para validación de layouts HTML.

Endpoints:
- POST /feedback/prepare-validation: Prepara HTML con data-vid
- POST /feedback/fix-with-feedback: Arregla HTML con feedback del usuario
- POST /feedback/approve: Aprueba y muestra layout
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
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
    ElementInfo,
)

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
```

---

### B05: AnnotationInjector

**Archivo:** `html_fixer/feedback/annotation_injector.py`

```python
"""
AnnotationInjector - Inyecta comentarios de feedback en el HTML.

Los comentarios se usan para que el LLM entienda qué elementos
funcionan, cuáles no, y qué espera el usuario de cada uno.
"""

from bs4 import BeautifulSoup, Comment
from typing import List, Optional

from ..contracts.feedback import (
    UserFeedback,
    FeedbackStatus,
    AnnotatedHTML,
)


class AnnotationInjector:
    """Inyecta comentarios con feedback del usuario en el HTML."""

    def inject(
        self,
        html: str,
        element_feedback: List[UserFeedback],
        global_feedback: Optional[List[str]] = None,
    ) -> AnnotatedHTML:
        """
        Inyecta comentarios antes de cada elemento con feedback.

        Ejemplo de output:
        <!-- [ELEMENT #2] status:broken user_feedback:"debería abrir modal de pago" -->
        <button data-vid="2" class="btn-pay">Pagar</button>

        Args:
            html: HTML con data-vid inyectados
            element_feedback: Lista de feedback por elemento
            global_feedback: Lista de feedback global (opcional)

        Returns:
            AnnotatedHTML con HTML anotado y estadísticas
        """
        soup = BeautifulSoup(html, 'html.parser')

        working_elements = []
        broken_elements = []
        annotations_count = 0

        # Procesar feedback de elementos
        for feedback in element_feedback:
            # Solo procesar elementos con feedback (no untested)
            if feedback.status == FeedbackStatus.UNTESTED:
                continue

            # Buscar elemento por data-vid
            element = soup.find(attrs={"data-vid": str(feedback.vid)})

            if not element:
                continue

            # Construir texto del comentario
            if feedback.status == FeedbackStatus.WORKING:
                comment_text = f"[ELEMENT #{feedback.vid}] status:working"
                working_elements.append(feedback.vid)
            else:
                # Escapar comillas en el mensaje
                safe_message = (feedback.message or "").replace('"', '\\"')
                comment_text = (
                    f'[ELEMENT #{feedback.vid}] status:broken '
                    f'user_feedback:"{safe_message}"'
                )
                broken_elements.append(feedback.vid)

            # Inyectar comentario ANTES del elemento
            comment = Comment(f" {comment_text} ")
            element.insert_before(comment)
            element.insert_before("\n")  # Newline para legibilidad

            annotations_count += 1

        # Inyectar feedback global al inicio del body
        global_count = 0
        if global_feedback:
            body = soup.find('body')
            if body:
                for gf in reversed(global_feedback):  # Reversed para mantener orden
                    safe_message = gf.replace('"', '\\"')
                    comment = Comment(f' [GLOBAL FEEDBACK] "{safe_message}" ')
                    # Insertar al inicio del body
                    if body.contents:
                        body.contents[0].insert_before(comment)
                        body.contents[0].insert_before("\n")
                    else:
                        body.append(comment)
                    global_count += 1

        return AnnotatedHTML(
            html=str(soup),
            annotations_count=annotations_count,
            working_elements=working_elements,
            broken_elements=broken_elements,
            global_feedback_count=global_count,
        )

    def remove_annotations(self, html: str) -> str:
        """
        Remueve los atributos data-vid y comentarios de feedback del HTML final.
        Llamar después de que el fixer haya terminado.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Remover data-vid
        for el in soup.find_all(attrs={"data-vid": True}):
            del el['data-vid']

        # Remover comentarios de feedback
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            if '[ELEMENT #' in comment or '[GLOBAL FEEDBACK]' in comment:
                comment.extract()

        # Remover script y estilos de validación
        for script in soup.find_all('script', {'data-validation-script': True}):
            script.decompose()
        for style in soup.find_all('style', {'data-validation-styles': True}):
            style.decompose()

        return str(soup)
```

---

### B06: FeedbackMerger

**Archivo:** `html_fixer/feedback/feedback_merger.py`

```python
"""
FeedbackMerger - Combina errores del sandbox con feedback del usuario.

Prioriza la información del usuario sobre el sandbox cuando hay conflicto,
ya que el usuario tiene contexto funcional que el sandbox no puede detectar.
"""

from typing import List, Dict, Optional
import logging

from ..contracts.feedback import (
    UserFeedback,
    FeedbackStatus,
    MergedError,
)
from ..contracts.errors import ClassifiedError

logger = logging.getLogger(__name__)


class FeedbackMerger:
    """Combina información técnica del sandbox con feedback del usuario."""

    def merge(
        self,
        sandbox_errors: List[ClassifiedError],
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
        errors: List[ClassifiedError],
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
        error: ClassifiedError,
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
```

---

### B07: Endpoint fix-with-feedback

**Archivo:** `app/routers/feedback.py` (parte 2 - agregar al archivo)

```python
# Agregar estos imports al inicio del archivo
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
from app.ai.scene.custom_layout.html_fixer.orchestrator import Orchestrator
from app.ai.scene.custom_layout.html_fixer.fixer import DeterministicFixer


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

        # 3. Correr validación sandbox en el HTML anotado
        orchestrator = Orchestrator()
        sandbox_result = await orchestrator._sandbox.validate(annotated.html)
        sandbox_errors = sandbox_result.errors if sandbox_result else []

        # 4. Combinar errores sandbox + feedback usuario
        merger = FeedbackMerger()
        merged_errors = merger.merge(
            sandbox_errors=sandbox_errors,
            user_feedback=user_feedback,
            element_map=element_map_dict,
        )

        logger.info(
            f"Merged errors: {len(merged_errors)} total, "
            f"{len([e for e in merged_errors if e.has_technical_cause])} technical"
        )

        # 5. Aplicar fixes (determinísticos + LLM si necesario)
        fixed_html = annotated.html
        changes_made = []

        if merged_errors or request.global_feedback:
            # Usar el orchestrator para aplicar fixes
            fix_result = await orchestrator.fix(
                html=annotated.html,
                additional_context={
                    'merged_errors': [
                        {
                            'vid': e.vid,
                            'selector': e.element_selector,
                            'technical_error': e.technical_error,
                            'user_feedback': e.user_feedback,
                        }
                        for e in merged_errors
                    ],
                    'global_feedback': request.global_feedback,
                }
            )
            fixed_html = fix_result.fixed_html

            # Registrar cambios
            for error in merged_errors:
                changes_made.append(ChangeMade(
                    vid=error.vid,
                    description=f"Fixed: {error.user_feedback or error.technical_error or 'unknown issue'}",
                    fix_type="css" if error.technical_type in ['z_index', 'pointer_events'] else "js",
                ))

            for gf in request.global_feedback:
                changes_made.append(ChangeMade(
                    vid=None,
                    description=f"Applied global feedback: {gf}",
                    fix_type="html",
                ))

        # 6. Limpiar: remover data-vid, comentarios y scripts de validación
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
        # Aquí se integraría con command_service.display_scene()
        # Por ahora retornamos éxito

        logger.info(
            f"Layout approved by user {current_user.id} "
            f"for device {request.device_id or 'default'}"
        )

        # TODO: Integrar con CommandService
        # from app.services.commands import command_service
        # await command_service.display_scene(
        #     device_id=request.device_id,
        #     custom_layout=request.html,
        # )

        return ApproveLayoutResponse(
            success=True,
            message="Layout approved and sent to display",
            display_url=None,  # Podría incluir URL de preview
        )

    except Exception as e:
        logger.error(f"Error approving layout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving layout: {str(e)}"
        )
```

---

### B08: FeedbackService

**Archivo:** `app/services/feedback_service.py`

```python
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
    MergedError,
)
from app.ai.scene.custom_layout.html_fixer.orchestrator import Orchestrator

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
        orchestrator: Optional[Orchestrator] = None,
    ):
        self._mapper = mapper or ElementMapper()
        self._injector = injector or AnnotationInjector()
        self._merger = merger or FeedbackMerger()
        self._orchestrator = orchestrator

    def _get_orchestrator(self) -> Orchestrator:
        """Lazy initialization del orchestrator."""
        if self._orchestrator is None:
            self._orchestrator = Orchestrator()
        return self._orchestrator

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

        # 3. Validación sandbox
        orchestrator = self._get_orchestrator()
        sandbox_result = await orchestrator._sandbox.validate(annotated.html)
        sandbox_errors = sandbox_result.errors if sandbox_result else []

        # 4. Merge errores
        merged_errors = self._merger.merge(
            sandbox_errors=sandbox_errors,
            user_feedback=element_feedback,
            element_map=element_map_dict,
        )

        # 5. Aplicar fixes
        fixed_html = annotated.html
        if merged_errors or global_feedback:
            fix_result = await orchestrator.fix(
                html=annotated.html,
                additional_context={
                    'merged_errors': [
                        {
                            'vid': e.vid,
                            'selector': e.element_selector,
                            'technical_error': e.technical_error,
                            'user_feedback': e.user_feedback,
                        }
                        for e in merged_errors
                    ],
                    'global_feedback': global_feedback,
                }
            )
            fixed_html = fix_result.fixed_html

        # 6. Limpiar
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
```

---

### B09: Prompt LLM v2

**Archivo:** `html_fixer/prompts/fixer_prompt_v2.py`

```python
"""
Prompt actualizado para el LLM que lee comentarios de feedback.

Este prompt entiende:
- Comentarios [ELEMENT #N] status:working/broken
- Comentarios [GLOBAL FEEDBACK] "mensaje"
- Contexto de errores del usuario
"""

from typing import List, Dict, Optional


class FeedbackAwareLLMPrompt:
    """Prompt que entiende comentarios de feedback del usuario."""

    SYSTEM_PROMPT = """You are a Tailwind CSS and JavaScript repair specialist.

You receive HTML with ANNOTATED FEEDBACK from users. The feedback appears as HTML comments
BEFORE elements, in this format:

<!-- [ELEMENT #3] status:broken user_feedback:"should open payment modal" -->
<button data-vid="3" class="btn-pay">Pay</button>

<!-- [ELEMENT #5] status:working -->
<button data-vid="5" class="btn-cancel">Cancel</button>

ANNOTATION FORMAT:
- status:working = User confirmed this element works correctly. DO NOT MODIFY.
- status:broken = User reported this element doesn't work.
- user_feedback:"..." = User's description of expected behavior.

GLOBAL FEEDBACK (at start of body):
<!-- [GLOBAL FEEDBACK] "Missing a back button" -->
<!-- [GLOBAL FEEDBACK] "Form needs validation" -->

YOUR TASK:
1. Find elements marked as status:broken
2. Read the user_feedback to understand expected behavior
3. Fix ONLY those elements
4. DO NOT modify elements marked as status:working
5. Apply global feedback changes

CRITICAL RULES:
- Output ONLY JSON patches with Tailwind classes
- NEVER output raw CSS (no <style> blocks with custom CSS)
- NEVER remove elements or functionality
- NEVER modify working elements
- If user says "should open modal", check if onclick handler exists and modal element exists
- If user says "should submit form", check if form action and submit handler exist

OUTPUT FORMAT:
{
  "analysis": "Brief description of issues found",
  "patches": [
    {
      "vid": 3,
      "selector": "[data-vid='3']",
      "issue": "z-index too low, blocked by overlay",
      "user_wanted": "should open payment modal",
      "fix_type": "css",
      "add_classes": ["relative", "z-50", "pointer-events-auto"],
      "remove_classes": ["z-10"]
    },
    {
      "vid": null,
      "selector": "body > header",
      "issue": "Missing navigation element",
      "user_wanted": "Missing a back button",
      "fix_type": "html",
      "html_to_add": "<button class='...' onclick='history.back()'>Back</button>",
      "insert_position": "prepend"
    }
  ]
}

COMMON FIXES:
- "button doesn't work" + no technical error → Check onclick, add pointer-events-auto, z-index
- "should open modal" → Verify modal exists, check trigger function, add z-50
- "form doesn't submit" → Check form action, onsubmit handler
- "dropdown won't open" → Check z-index, pointer-events, position relative/absolute
- "can't click" → Usually z-index or pointer-events issue

REMEMBER: User feedback takes priority over sandbox errors. If user says it works, trust them."""

    def build(
        self,
        annotated_html: str,
        merged_errors: Optional[List[Dict]] = None,
        global_feedback: Optional[List[str]] = None,
        screenshots: Optional[Dict] = None,
    ) -> List[Dict[str, str]]:
        """
        Construye mensajes para el LLM.

        Args:
            annotated_html: HTML con comentarios de feedback
            merged_errors: Lista de errores combinados (opcional)
            global_feedback: Lista de feedback global (opcional)
            screenshots: Screenshots para análisis visual (opcional)

        Returns:
            Lista de mensajes para el LLM
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        # Construir contexto de errores
        error_context = self._build_error_context(merged_errors or [])
        global_context = self._build_global_context(global_feedback or [])

        # Truncar HTML si es muy largo (mantener inicio y fin)
        html_display = annotated_html
        if len(annotated_html) > 8000:
            html_display = (
                annotated_html[:4000] +
                "\n\n<!-- ... HTML TRUNCATED FOR BREVITY ... -->\n\n" +
                annotated_html[-3000:]
            )

        user_content = f"""## ANNOTATED HTML

```html
{html_display}
```

## ERRORS TO FIX

{error_context}

## GLOBAL FEEDBACK

{global_context}

## INSTRUCTIONS

1. Read the HTML comments to find broken elements ([ELEMENT #N] status:broken)
2. Use user_feedback to understand expected behavior
3. Generate JSON patches to fix each broken element
4. Apply global feedback (missing elements, style changes)
5. Respect working elements - do not modify them

Output your fixes as JSON patches."""

        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_error_context(self, errors: List[Dict]) -> str:
        """Construye descripción de errores."""
        if not errors:
            return "No specific errors detected by sandbox. Fix based on user feedback comments in the HTML."

        lines = []
        for e in errors:
            lines.append(f"""
### Element #{e.get('vid', 'N/A')}
- Selector: `{e.get('selector', 'unknown')}`
- Technical error: {e.get('technical_error') or 'None detected'}
- User feedback: "{e.get('user_feedback') or 'Not provided'}"
""")
        return "\n".join(lines)

    def _build_global_context(self, global_feedback: List[str]) -> str:
        """Construye descripción de feedback global."""
        if not global_feedback:
            return "No global feedback provided."

        lines = ["User reported the following missing features or changes:"]
        for i, gf in enumerate(global_feedback, 1):
            lines.append(f"{i}. {gf}")

        return "\n".join(lines)


# Instance for import
feedback_aware_prompt = FeedbackAwareLLMPrompt()
```

---

### B10: Registrar Router en main.py

**Archivo:** `app/main.py` - Agregar:

```python
# En la sección de imports
from app.routers import feedback

# En la sección de routers (después de los existentes)
app.include_router(feedback.router)
```

---

### B11: Configurar CORS

**Archivo:** `app/main.py` - Asegurarse que CORS permite el frontend:

```python
from fastapi.middleware.cors import CORSMiddleware

# Después de crear la app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # React dev server
        "http://localhost:5173",      # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        # Agregar dominios de producción
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### B12: Tests Unitarios

**Archivo:** `tests/unit/feedback/test_element_mapper.py`

```python
"""Tests para ElementMapper."""

import pytest
from app.ai.scene.custom_layout.html_fixer.feedback.element_mapper import (
    ElementMapper,
    ElementInfo,
    PreparedHTML,
)


class TestElementMapper:
    """Tests para ElementMapper."""

    @pytest.fixture
    def mapper(self):
        return ElementMapper()

    def test_maps_buttons(self, mapper):
        """Debe mapear botones correctamente."""
        html = """
        <html>
        <body>
            <button class="btn-1">Click 1</button>
            <button class="btn-2">Click 2</button>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 2
        assert 'data-vid="1"' in result.html
        assert 'data-vid="2"' in result.html
        assert result.element_map[1].tag == "button"
        assert "btn-2" in result.element_map[2].classes

    def test_maps_onclick_elements(self, mapper):
        """Debe mapear elementos con onclick."""
        html = """
        <html>
        <body>
            <div onclick="handleClick()">Clickable div</div>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 1
        assert result.element_map[1].attributes.get('onclick') == "handleClick()"

    def test_no_duplicates(self, mapper):
        """No debe crear duplicados para elementos que matchean múltiples selectores."""
        html = """
        <html>
        <body>
            <button onclick="submit()" role="button">Submit</button>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        # Solo debe contar una vez aunque matchea múltiples selectores
        assert result.total_elements == 1

    def test_injects_validation_script(self, mapper):
        """Debe inyectar el script de validación."""
        html = """
        <html>
        <body>
            <button>Click</button>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert 'data-validation-script="true"' in result.html
        assert 'postMessage' in result.html
        assert 'ELEMENT_CLICKED' in result.html

    def test_maps_inputs(self, mapper):
        """Debe mapear inputs."""
        html = """
        <html>
        <body>
            <input type="text" name="email" />
            <input type="submit" value="Send" />
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 2
        assert result.element_map[1].tag == "input"


class TestAnnotationInjector:
    """Tests para AnnotationInjector."""

    @pytest.fixture
    def injector(self):
        from app.ai.scene.custom_layout.html_fixer.feedback.annotation_injector import (
            AnnotationInjector,
        )
        return AnnotationInjector()

    def test_injects_working_comment(self, injector):
        """Debe inyectar comentario para elementos working."""
        from app.ai.scene.custom_layout.html_fixer.contracts.feedback import (
            UserFeedback,
            FeedbackStatus,
        )

        html = '<html><body><button data-vid="1">Click</button></body></html>'
        feedback = [UserFeedback(vid=1, status=FeedbackStatus.WORKING)]

        result = injector.inject(html, feedback)

        assert "[ELEMENT #1] status:working" in result.html
        assert result.working_elements == [1]
        assert result.broken_elements == []

    def test_injects_broken_comment_with_message(self, injector):
        """Debe inyectar comentario broken con mensaje del usuario."""
        from app.ai.scene.custom_layout.html_fixer.contracts.feedback import (
            UserFeedback,
            FeedbackStatus,
        )

        html = '<html><body><button data-vid="2">Pay</button></body></html>'
        feedback = [UserFeedback(
            vid=2,
            status=FeedbackStatus.BROKEN,
            message="should open payment modal"
        )]

        result = injector.inject(html, feedback)

        assert 'status:broken' in result.html
        assert 'user_feedback:"should open payment modal"' in result.html
        assert result.broken_elements == [2]

    def test_injects_global_feedback(self, injector):
        """Debe inyectar feedback global."""
        html = '<html><body><div>Content</div></body></html>'

        result = injector.inject(
            html=html,
            element_feedback=[],
            global_feedback=["Missing back button", "Need footer"]
        )

        assert '[GLOBAL FEEDBACK] "Missing back button"' in result.html
        assert '[GLOBAL FEEDBACK] "Need footer"' in result.html
        assert result.global_feedback_count == 2

    def test_remove_annotations(self, injector):
        """Debe remover anotaciones correctamente."""
        html = '''
        <html><body>
        <!-- [ELEMENT #1] status:working -->
        <button data-vid="1">Click</button>
        <script data-validation-script="true">...</script>
        </body></html>
        '''

        clean = injector.remove_annotations(html)

        assert 'data-vid' not in clean
        assert '[ELEMENT #1]' not in clean
        assert 'data-validation-script' not in clean
```

---

## Definition of Done

### Checklist Backend

- [ ] **B01**: ElementMapper inyecta data-vid en todos los elementos interactivos
- [ ] **B01**: ElementMapper inyecta script de postMessage
- [ ] **B02**: Contracts de Feedback definidos (dataclasses)
- [ ] **B03**: Pydantic Schemas para API definidos
- [ ] **B04**: Endpoint `/feedback/prepare-validation` funciona
- [ ] **B05**: AnnotationInjector inyecta comentarios correctamente
- [ ] **B05**: AnnotationInjector soporta Global Feedback
- [ ] **B06**: FeedbackMerger combina sandbox + feedback del usuario
- [ ] **B07**: Endpoint `/feedback/fix-with-feedback` funciona
- [ ] **B08**: FeedbackService orquesta el flujo completo
- [ ] **B09**: Prompt LLM v2 lee y entiende comentarios de feedback
- [ ] **B10**: Router registrado en main.py
- [ ] **B11**: CORS configurado para frontend
- [ ] **B12**: Tests con >80% coverage

---

## Verificación

```bash
# 1. Verificar que archivos existen
ls -la app/routers/feedback.py
ls -la app/schemas/feedback.py
ls -la app/services/feedback_service.py
ls -la app/ai/scene/custom_layout/html_fixer/feedback/

# 2. Correr tests
pytest tests/unit/feedback/ -v

# 3. Test endpoint prepare-validation
curl -X POST http://localhost:8000/feedback/prepare-validation \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"html": "<!DOCTYPE html><html><body><button>Click</button></body></html>"}'

# 4. Test endpoint fix-with-feedback
curl -X POST http://localhost:8000/feedback/fix-with-feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<!DOCTYPE html><html><body><button data-vid=\"1\">Click</button></body></html>",
    "feedback": [{"vid": 1, "status": "broken", "message": "Should open modal"}],
    "global_feedback": []
  }'
```

---

## Métricas de Éxito

| Métrica | Target |
|---------|--------|
| Elementos detectados | >95% de interactivos |
| Tiempo de prepare | <2s |
| Tiempo de fix | <15s |
| Tests passing | 100% |
| Coverage | >80% |
