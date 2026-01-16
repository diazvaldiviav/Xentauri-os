# 🏃 SPRINT 4: HUMAN FEEDBACK SYSTEM
## Frontend React + Backend Endpoints - 3 Semanas

---

## 📎 Sprint Goal
> **Implementar sistema completo de feedback humano: frontend React con iframe para preview, captura de feedback ✅/❌, y endpoints de backend para procesar y aplicar el feedback al HTML.**

---

## 🎯 Problema a Resolver

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

## 📋 Sprint Backlog

### 🔵 BACKEND (Python)

| Task ID | Tarea | Estimación | Prioridad | Estado |
|---------|-------|------------|-----------|--------|
| T4-B01 | Crear `element_mapper.py` - Inyecta data-vid + **script postMessage** | 4h | 🔴 | ⬜ |
| T4-B02 | Crear `ElementInfo` dataclass y contracts | 1h | 🔴 | ⬜ |
| T4-B03 | Endpoint `POST /api/prepare-validation` | 2h | 🔴 | ⬜ |
| T4-B04 | Crear `annotation_injector.py` - Inyecta comentarios | 2h | 🔴 | ⬜ |
| T4-B05 | Crear `feedback_merger.py` - Combina sandbox + feedback | 3h | 🔴 | ⬜ |
| T4-B06 | Endpoint `POST /api/fix-with-feedback` | 3h | 🔴 | ⬜ |
| T4-B07 | Actualizar prompt LLM para leer comentarios de feedback | 2h | 🟡 | ⬜ |
| **T4-B09** | **🆕 Soporte para Global Feedback (elementos faltantes)** | **2h** | 🟡 | ⬜ |
| T4-B08 | Tests unitarios backend | 3h | 🟡 | ⬜ |

### 🟢 FRONTEND (React + TypeScript)

| Task ID | Tarea | Estimación | Prioridad | Estado |
|---------|-------|------------|-----------|--------|
| T4-F01 | Setup proyecto React + TypeScript + Tailwind | 2h | 🔴 | ⬜ |
| T4-F02 | Crear types en `validation.ts` | 1h | 🔴 | ⬜ |
| T4-F03 | Crear `PreviewFrame.tsx` - iframe con **postMessage** | 5h | 🔴 | ⬜ |
| T4-F04 | Crear `FeedbackPopup.tsx` - Modal ✅/❌ | 3h | 🔴 | ⬜ |
| T4-F05 | Crear `ControlPanel.tsx` - Progreso, botones + **Global Feedback** | 3h | 🔴 | ⬜ |
| T4-F06 | Crear `useLayoutValidation.ts` hook | 4h | 🔴 | ⬜ |
| T4-F07 | Crear `LayoutValidator.tsx` - Componente principal | 3h | 🔴 | ⬜ |
| T4-F08 | Crear `validationApi.ts` - Llamadas al backend | 1h | 🔴 | ⬜ |
| T4-F09 | Crear `WarningModal.tsx` - Advertencia feedback incompleto | 1h | 🟡 | ⬜ |
| **T4-F12** | **🆕 Crear `GlobalFeedbackModal.tsx` - Feedback de elementos faltantes** | **2h** | 🟡 | ⬜ |
| T4-F10 | Estilos y animaciones del popup | 2h | 🟢 | ⬜ |
| T4-F11 | Tests de componentes | 3h | 🟡 | ⬜ |

### 🟣 INTEGRACIÓN

| Task ID | Tarea | Estimación | Prioridad | Estado |
|---------|-------|------------|-----------|--------|
| T4-I01 | Configurar CORS en backend | 1h | 🔴 | ⬜ |
| T4-I02 | Test E2E flujo completo | 3h | 🟡 | ⬜ |
| T4-I03 | Documentación de API | 1h | 🟢 | ⬜ |

**Total Estimado:** 51 horas (~3 semanas)

---

## ⚠️ NOTAS TÉCNICAS CRÍTICAS

### 🔴 Comunicación Iframe ↔ React (postMessage)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROBLEMA: EVENTOS EN IFRAME                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ❌ INCORRECTO: Intentar capturar eventos desde fuera del iframe          │
│   iframeDoc.addEventListener('click', handler) // NO FUNCIONA              │
│                                                                             │
│   ✅ CORRECTO: Inyectar script DENTRO del HTML que use postMessage         │
│                                                                             │
│   FLUJO:                                                                    │
│   ┌─────────────────┐         postMessage          ┌─────────────────┐    │
│   │     IFRAME      │ ─────────────────────────────▶│      REACT      │    │
│   │                 │                               │                 │    │
│   │  Script inyect. │  { type: 'ELEMENT_CLICKED',  │  window.onmsg   │    │
│   │  captura click  │    vid: 3,                   │  recibe y abre  │    │
│   │                 │    rect: {...} }             │  popup          │    │
│   └─────────────────┘                               └─────────────────┘    │
│                                                                             │
│   REACT → IFRAME (para actualizar estilos):                                │
│   iframe.contentWindow.postMessage({ type: 'UPDATE_STATUS', ... }, '*')   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 🔴 Feedback Global (Elementos Faltantes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROBLEMA: "FALTA UN BOTÓN DE VOLVER"                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   El usuario puede querer reportar:                                        │
│   • "Falta una sección de contacto"                                        │
│   • "Necesita un botón de volver al inicio"                               │
│   • "No tiene footer"                                                      │
│   • "El título debería ser diferente"                                     │
│                                                                             │
│   SOLUCIÓN: Botón "Feedback Global" en ControlPanel                       │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  [🔄 Reset] [📝 Feedback Global] [✅ Enviar (80% probado)]         │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   Se inyecta como comentario al inicio del <body>:                        │
│   <!-- [GLOBAL FEEDBACK] "Falta sección de contacto al final" -->         │
│   <!-- [GLOBAL FEEDBACK] "Necesita breadcrumbs de navegación" -->         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura de Archivos

### Backend (Python)

```
src/html_fixer/
├── api/                              # 🆕 NUEVO
│   ├── __init__.py
│   ├── routes.py                     # Endpoints FastAPI
│   └── schemas.py                    # Pydantic models
├── feedback/                         # 🆕 NUEVO
│   ├── __init__.py
│   ├── element_mapper.py            # T4-B01: Inyecta data-vid
│   ├── annotation_injector.py       # T4-B04: Inyecta comentarios
│   └── feedback_merger.py           # T4-B05: Combina errores
├── contracts/
│   ├── errors.py                    # Ya existe
│   └── feedback.py                  # 🆕 T4-B02: Contracts feedback
└── prompts/
    └── fixer_prompt.py              # 🔄 T4-B07: Actualizar
```

### Frontend (React)

```
frontend/
├── src/
│   ├── components/
│   │   └── layout-validator/
│   │       ├── index.tsx
│   │       ├── LayoutValidator.tsx   # T4-F07
│   │       ├── PreviewFrame.tsx      # T4-F03
│   │       ├── FeedbackPopup.tsx     # T4-F04
│   │       ├── ControlPanel.tsx      # T4-F05
│   │       └── WarningModal.tsx      # T4-F09
│   ├── hooks/
│   │   └── useLayoutValidation.ts    # T4-F06
│   ├── types/
│   │   └── validation.ts             # T4-F02
│   ├── services/
│   │   └── validationApi.ts          # T4-F08
│   └── App.tsx
├── package.json
├── tsconfig.json
└── tailwind.config.js
```

---

## 📝 ESPECIFICACIONES TÉCNICAS

---

### T4-B01: ElementMapper (Backend) - CON SCRIPT INYECTADO

```python
# feedback/element_mapper.py
"""Inyecta data-vid en elementos interactivos del HTML + script de comunicación."""

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
    
    # 🆕 SCRIPT ESPÍA - Se inyecta en el HTML para comunicación con React
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
    
    // Notificar al padre que el iframe está listo
    window.parent.postMessage({ type: 'IFRAME_READY' }, '*');
})();
</script>
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
            elements = soup.select(selector)
            
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
                    classes=el.get('class', []),
                    element_id=el.get('id'),
                    text=self._get_text_content(el)[:50],
                    outer_html=str(el),
                    line_number=getattr(el, 'sourceline', None),
                    attributes=self._get_relevant_attrs(el)
                )
                
                vid += 1
        
        # 🆕 INYECTAR SCRIPT DE COMUNICACIÓN al final del body
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
        relevant = ['onclick', 'onchange', 'onsubmit', 'href', 'type', 'name', 'value']
        return {k: el.get(k) for k in relevant if el.get(k)}
```

---

### T4-B02: Contracts de Feedback

```python
# contracts/feedback.py
"""Contratos de datos para el sistema de feedback."""

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
    message: Optional[str] = None      # Solo si status == BROKEN
    
@dataclass
class FeedbackRequest:
    """Request del frontend para arreglar con feedback."""
    html: str
    feedback: List[UserFeedback]

@dataclass  
class MergedError:
    """Error combinado: técnico (sandbox) + funcional (usuario)."""
    vid: int
    element_selector: str
    
    # Del sandbox (puede ser None si sandbox no detectó nada)
    technical_error: Optional[str] = None
    technical_type: Optional[str] = None      # "z_index", "pointer_events", etc.
    
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

@dataclass
class FixResult:
    """Resultado del proceso de fix."""
    success: bool
    fixed_html: str
    changes_made: List[Dict]
    errors_found: int
    errors_fixed: int
    sandbox_errors: int
    user_reported_errors: int
```

---

### T4-B03: Endpoint prepare-validation

```python
# api/routes.py
"""Endpoints de la API de validación."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from ..feedback.element_mapper import ElementMapper, ElementInfo

router = APIRouter(prefix="/api", tags=["validation"])

# ============== SCHEMAS ==============

class PrepareRequest(BaseModel):
    html: str

class ElementInfoResponse(BaseModel):
    vid: int
    tag: str
    classes: List[str]
    element_id: Optional[str]
    text: str
    outer_html: str
    line_number: Optional[int]
    attributes: Dict[str, str]

class PrepareResponse(BaseModel):
    html: str
    element_map: Dict[int, ElementInfoResponse]
    total_elements: int

# ============== ENDPOINTS ==============

@router.post("/prepare-validation", response_model=PrepareResponse)
async def prepare_validation(request: PrepareRequest):
    """
    Prepara HTML para validación:
    - Inyecta data-vid en cada elemento interactivo
    - Retorna mapa de elementos para el frontend
    
    El frontend usará este HTML en un iframe y mostrará
    el mapa para que el usuario sepa qué elementos probar.
    """
    try:
        mapper = ElementMapper()
        result = mapper.prepare(request.html)
        
        # Convertir dataclasses a dict para response
        element_map_response = {
            vid: ElementInfoResponse(
                vid=info.vid,
                tag=info.tag,
                classes=info.classes,
                element_id=info.element_id,
                text=info.text,
                outer_html=info.outer_html,
                line_number=info.line_number,
                attributes=info.attributes
            )
            for vid, info in result.element_map.items()
        }
        
        return PrepareResponse(
            html=result.html,
            element_map=element_map_response,
            total_elements=result.total_elements
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error preparing HTML: {str(e)}")
```

---

### T4-B04: AnnotationInjector

```python
# feedback/annotation_injector.py
"""Inyecta comentarios de feedback en el HTML."""

from bs4 import BeautifulSoup, Comment
from typing import List
from ..contracts.feedback import UserFeedback, FeedbackStatus, AnnotatedHTML

class AnnotationInjector:
    """Inyecta comentarios con feedback del usuario en el HTML."""
    
    def inject(self, html: str, feedback_list: List[UserFeedback]) -> AnnotatedHTML:
        """
        Inyecta comentarios antes de cada elemento con feedback.
        
        Ejemplo de output:
        <!-- [ELEMENT #2] status:broken user_feedback:"debería abrir modal de pago" -->
        <button data-vid="2" class="btn-pay">Pagar</button>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        working_elements = []
        broken_elements = []
        annotations_count = 0
        
        for feedback in feedback_list:
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
        
        return AnnotatedHTML(
            html=str(soup),
            annotations_count=annotations_count,
            working_elements=working_elements,
            broken_elements=broken_elements
        )
    
    def remove_data_vid(self, html: str) -> str:
        """
        Remueve los atributos data-vid del HTML final.
        Llamar después de que el fixer haya terminado.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        for el in soup.find_all(attrs={"data-vid": True}):
            del el['data-vid']
        
        return str(soup)
```

---

### T4-B05: FeedbackMerger

```python
# feedback/feedback_merger.py
"""Combina errores del sandbox con feedback del usuario."""

from typing import List, Dict, Optional
from ..contracts.feedback import (
    UserFeedback, 
    FeedbackStatus, 
    MergedError
)
from ..contracts.errors import ClassifiedError

class FeedbackMerger:
    """Combina información técnica del sandbox con feedback del usuario."""
    
    def merge(
        self,
        sandbox_errors: List[ClassifiedError],
        user_feedback: List[UserFeedback],
        element_map: Dict[int, dict]
    ) -> List[MergedError]:
        """
        Combina errores técnicos con feedback del usuario.
        
        Casos:
        1. Sandbox detectó error + Usuario confirmó broken → Alta confianza
        2. Sandbox detectó error + Usuario dijo working → Falso positivo? 
        3. Sandbox no detectó + Usuario dijo broken → Error funcional
        4. Sandbox no detectó + Usuario dijo working → OK
        """
        merged = []
        
        # Indexar errores del sandbox por selector
        sandbox_by_vid = self._index_sandbox_errors(sandbox_errors, element_map)
        
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
                    confidence=0.95 if sandbox_error else 0.8
                ))
            
            # Caso 2: Sandbox detectó pero usuario dijo que funciona
            elif feedback.status == FeedbackStatus.WORKING and sandbox_error:
                # Log para análisis - posible falso positivo del sandbox
                # No agregamos a merged porque el usuario dijo que funciona
                pass
        
        return merged
    
    def _index_sandbox_errors(
        self, 
        errors: List[ClassifiedError],
        element_map: Dict[int, dict]
    ) -> Dict[int, dict]:
        """Indexa errores del sandbox por vid."""
        indexed = {}
        
        for error in errors:
            # Buscar qué vid corresponde a este error
            vid = self._find_vid_for_error(error, element_map)
            if vid:
                indexed[vid] = {
                    'message': str(error),
                    'type': error.error_type.value if hasattr(error, 'error_type') else 'unknown'
                }
        
        return indexed
    
    def _find_vid_for_error(
        self, 
        error: ClassifiedError, 
        element_map: Dict[int, dict]
    ) -> Optional[int]:
        """Encuentra el vid del elemento que tiene el error."""
        error_selector = getattr(error, 'selector', '')
        
        for vid, info in element_map.items():
            if self._selectors_match(error_selector, info):
                return vid
        
        return None
    
    def _selectors_match(self, error_selector: str, element_info: dict) -> bool:
        """Verifica si un selector de error corresponde a un elemento."""
        # Por ID
        if error_selector.startswith('#'):
            return element_info.get('element_id') == error_selector[1:]
        
        # Por clase
        if error_selector.startswith('.'):
            classes = element_info.get('classes', [])
            return error_selector[1:] in classes
        
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
        
        return f"[data-vid=\"{element_info.get('vid', 0)}\"]"
```

---

### T4-B06: Endpoint fix-with-feedback

```python
# api/routes.py (continuación)

class FeedbackItem(BaseModel):
    vid: int
    status: str  # "working" | "broken"
    message: Optional[str] = None

class FixWithFeedbackRequest(BaseModel):
    html: str
    feedback: List[FeedbackItem]

class ChangeMade(BaseModel):
    vid: int
    description: str

class FixWithFeedbackResponse(BaseModel):
    success: bool
    fixed_html: str
    changes_made: List[ChangeMade]
    errors_found: int
    errors_fixed: int
    sandbox_errors: int
    user_reported_errors: int

@router.post("/fix-with-feedback", response_model=FixWithFeedbackResponse)
async def fix_with_feedback(request: FixWithFeedbackRequest):
    """
    Recibe HTML + feedback del usuario, ejecuta el pipeline de fix:
    
    1. Inyecta comentarios de feedback en el HTML
    2. Corre sandbox para detectar errores técnicos
    3. Combina errores sandbox + feedback usuario
    4. Aplica reglas determinísticas
    5. Si necesario, llama al LLM fixer
    6. Retorna HTML arreglado
    """
    try:
        from ..feedback.annotation_injector import AnnotationInjector
        from ..feedback.feedback_merger import FeedbackMerger
        from ..sandbox import SandboxValidator          # Tu código existente
        from ..fixer import DeterministicFixer          # Tu código existente
        from ..fixer import LLMFixer                    # Tu código existente
        
        # Convertir feedback a dataclass
        user_feedback = [
            UserFeedback(
                vid=f.vid,
                status=FeedbackStatus(f.status),
                message=f.message
            )
            for f in request.feedback
        ]
        
        # 1. Inyectar comentarios
        injector = AnnotationInjector()
        annotated = injector.inject(request.html, user_feedback)
        
        # 2. Correr sandbox
        sandbox = SandboxValidator()
        sandbox_result = await sandbox.validate(annotated.html)
        sandbox_errors = sandbox_result.errors
        
        # 3. Combinar errores
        # Nota: Necesitamos el element_map, lo re-extraemos
        from ..feedback.element_mapper import ElementMapper
        mapper = ElementMapper()
        prepared = mapper.prepare(request.html)
        
        merger = FeedbackMerger()
        merged_errors = merger.merge(
            sandbox_errors=sandbox_errors,
            user_feedback=user_feedback,
            element_map={k: v.__dict__ for k, v in prepared.element_map.items()}
        )
        
        # 4. Aplicar fixes determinísticos primero
        deterministic_fixer = DeterministicFixer()
        html_after_rules, rules_applied = deterministic_fixer.fix(
            annotated.html, 
            merged_errors
        )
        
        # 5. Si quedan errores, usar LLM
        remaining_errors = [e for e in merged_errors if e.requires_llm]
        
        if remaining_errors:
            llm_fixer = LLMFixer()
            html_final = await llm_fixer.fix(html_after_rules, remaining_errors)
        else:
            html_final = html_after_rules
        
        # 6. Limpiar: remover data-vid y comentarios de debug
        html_clean = injector.remove_data_vid(html_final)
        
        # Construir respuesta
        changes_made = [
            ChangeMade(vid=e.vid, description=f"Fixed: {e.technical_type or 'user-reported issue'}")
            for e in merged_errors
        ]
        
        return FixWithFeedbackResponse(
            success=True,
            fixed_html=html_clean,
            changes_made=changes_made,
            errors_found=len(merged_errors),
            errors_fixed=len(merged_errors),  # Asumimos éxito
            sandbox_errors=len([e for e in merged_errors if e.has_technical_cause]),
            user_reported_errors=len([e for e in merged_errors if not e.has_technical_cause])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fixing HTML: {str(e)}")
```

---

### T4-B07: Prompt LLM Actualizado

```python
# prompts/fixer_prompt_v2.py
"""Prompt actualizado para leer comentarios de feedback."""

class FeedbackAwareLLMPrompt:
    """Prompt que entiende comentarios de feedback del usuario."""
    
    SYSTEM_PROMPT = """You are a Tailwind CSS and JavaScript repair specialist. 

You receive HTML with ANNOTATED FEEDBACK from users. The feedback appears as HTML comments 
BEFORE elements, in this format:

<!-- [ELEMENT #3] status:broken user_feedback:"debería abrir modal de pago" -->
<button class="btn-pay">Pagar</button>

ANNOTATION FORMAT:
- status:working = User confirmed this element works correctly. DO NOT MODIFY.
- status:broken = User reported this element doesn't work.
- user_feedback:"..." = User's description of expected behavior.

YOUR TASK:
1. Find elements marked as status:broken
2. Read the user_feedback to understand expected behavior
3. Fix ONLY those elements
4. DO NOT modify elements marked as status:working

CRITICAL RULES:
- Output ONLY JSON patches with Tailwind classes
- NEVER output raw CSS
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
      "add_classes": ["relative", "z-50"],
      "remove_classes": ["z-10"]
    },
    {
      "vid": 5,
      "selector": "[data-vid='5']",
      "issue": "onclick handler missing",
      "user_wanted": "should validate form",
      "fix_type": "js",
      "js_fix": "Add onclick='validateForm()' handler"
    }
  ]
}

COMMON FIXES:
- "button doesn't work" + no technical error → Check onclick, add z-index
- "should open modal" → Verify modal exists, check trigger function
- "form doesn't submit" → Check form action, onsubmit handler
- "dropdown won't open" → Check z-index, pointer-events
"""
    
    def build(
        self, 
        annotated_html: str,
        merged_errors: list,
        screenshots: dict = None
    ) -> list:
        """Construye mensajes para el LLM."""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        # Construir contexto de errores
        error_context = self._build_error_context(merged_errors)
        
        user_content = f"""
## ANNOTATED HTML

```html
{annotated_html[:5000]}  <!-- Truncated for context -->
```

## ERRORS TO FIX

{error_context}

## INSTRUCTIONS

1. Read the HTML comments to find broken elements
2. Use user_feedback to understand expected behavior
3. Generate JSON patches to fix each broken element
4. Respect working elements - do not modify them
"""
        
        messages.append({"role": "user", "content": user_content})
        return messages
    
    def _build_error_context(self, errors: list) -> str:
        """Construye descripción de errores."""
        if not errors:
            return "No specific errors detected by sandbox. Fix based on user feedback."
        
        lines = []
        for e in errors:
            lines.append(f"""
### Element #{e.vid}
- Selector: `{e.element_selector}`
- Technical error: {e.technical_error or "None detected"}
- User feedback: "{e.user_feedback or "Not provided"}"
- Has technical cause: {e.has_technical_cause}
""")
        return "\n".join(lines)
```

---

### T4-F02: TypeScript Types

```typescript
// types/validation.ts

// ============== ELEMENT INFO ==============

export interface ElementInfo {
  vid: number;                    // Validation ID
  tag: string;                    // "button", "input", etc.
  classes: string[];              // ["btn-primary", "z-10"]
  element_id?: string;            // ID del elemento si tiene
  text: string;                   // Texto contenido (truncado)
  outer_html: string;             // HTML completo del elemento
  line_number?: number;           // Línea en el HTML original
  attributes: Record<string, string>;  // onclick, href, etc.
}

export type ElementMap = Record<number, ElementInfo>;

// ============== FEEDBACK ==============

export type FeedbackStatus = 'working' | 'broken' | 'untested';

export interface FeedbackItem {
  vid: number;
  status: FeedbackStatus;
  message?: string;               // Solo si status === 'broken'
  testedAt?: Date;
}

export type FeedbackState = Record<number, FeedbackItem>;

// ============== API ==============

export interface PrepareValidationRequest {
  html: string;
}

export interface PrepareValidationResponse {
  html: string;                   // HTML con data-vid inyectados
  element_map: ElementMap;
  total_elements: number;
}

export interface FixWithFeedbackRequest {
  html: string;
  feedback: Array<{
    vid: number;
    status: 'working' | 'broken';
    message?: string;
  }>;
}

export interface ChangeMade {
  vid: number;
  description: string;
}

export interface FixWithFeedbackResponse {
  success: boolean;
  fixed_html: string;
  changes_made: ChangeMade[];
  errors_found: number;
  errors_fixed: number;
  sandbox_errors: number;
  user_reported_errors: number;
}

// ============== UI STATE ==============

export interface PopupState {
  isOpen: boolean;
  element: ElementInfo | null;
  position: { x: number; y: number };
}

export interface ValidationStats {
  total: number;
  tested: number;
  working: number;
  broken: number;
  progress: number;  // 0-100
}
```

---

### T4-F08: API Service

```typescript
// services/validationApi.ts

import { 
  PrepareValidationRequest,
  PrepareValidationResponse,
  FixWithFeedbackRequest,
  FixWithFeedbackResponse 
} from '../types/validation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function prepareValidation(
  html: string
): Promise<PrepareValidationResponse> {
  const response = await fetch(`${API_BASE}/api/prepare-validation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html } as PrepareValidationRequest)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to prepare validation');
  }
  
  return response.json();
}

export async function fixWithFeedback(
  request: FixWithFeedbackRequest
): Promise<FixWithFeedbackResponse> {
  const response = await fetch(`${API_BASE}/api/fix-with-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fix HTML');
  }
  
  return response.json();
}
```

---

## 🧪 TESTS REQUERIDOS

### Backend Tests (T4-B08)

```python
# tests/unit/feedback/test_element_mapper.py

class TestElementMapper:
    
    def test_maps_buttons(self):
        html = """
        <html>
        <body>
            <button class="btn-1">Click 1</button>
            <button class="btn-2">Click 2</button>
        </body>
        </html>
        """
        mapper = ElementMapper()
        result = mapper.prepare(html)
        
        assert result.total_elements == 2
        assert 'data-vid="1"' in result.html
        assert 'data-vid="2"' in result.html
        assert result.element_map[1].tag == "button"
        assert result.element_map[2].classes == ["btn-2"]
    
    def test_maps_onclick_elements(self):
        html = """
        <div onclick="handleClick()">Clickable div</div>
        """
        mapper = ElementMapper()
        result = mapper.prepare(html)
        
        assert result.total_elements == 1
        assert result.element_map[1].attributes.get('onclick') == "handleClick()"
    
    def test_no_duplicates(self):
        html = """
        <button onclick="submit()" role="button">Submit</button>
        """
        mapper = ElementMapper()
        result = mapper.prepare(html)
        
        # Solo debe contar una vez aunque matchea múltiples selectores
        assert result.total_elements == 1


class TestAnnotationInjector:
    
    def test_injects_working_comment(self):
        html = '<button data-vid="1">Click</button>'
        feedback = [UserFeedback(vid=1, status=FeedbackStatus.WORKING)]
        
        injector = AnnotationInjector()
        result = injector.inject(html, feedback)
        
        assert "[ELEMENT #1] status:working" in result.html
        assert result.working_elements == [1]
    
    def test_injects_broken_comment_with_message(self):
        html = '<button data-vid="2">Pay</button>'
        feedback = [UserFeedback(
            vid=2, 
            status=FeedbackStatus.BROKEN,
            message="should open payment modal"
        )]
        
        injector = AnnotationInjector()
        result = injector.inject(html, feedback)
        
        assert 'status:broken' in result.html
        assert 'user_feedback:"should open payment modal"' in result.html
        assert result.broken_elements == [2]
```

---

## ✅ Definition of Done (Sprint 4)

### Backend
- [ ] ElementMapper inyecta data-vid en todos los elementos interactivos
- [ ] AnnotationInjector inyecta comentarios correctamente
- [ ] FeedbackMerger combina sandbox + feedback del usuario
- [ ] Endpoint `/prepare-validation` funciona
- [ ] Endpoint `/fix-with-feedback` funciona
- [ ] Prompt LLM lee y entiende comentarios de feedback
- [ ] Tests con >80% coverage

### Frontend
- [ ] PreviewFrame renderiza HTML completo en iframe
- [ ] Clicks en elementos interactivos disparan popup
- [ ] FeedbackPopup permite ✅/❌ y mensaje
- [ ] ControlPanel muestra progreso correcto
- [ ] Warning modal aparece si feedback incompleto
- [ ] Llamadas API funcionan correctamente
- [ ] UI responsive y usable

### Integración
- [ ] CORS configurado correctamente
- [ ] Flujo E2E funciona: prepare → feedback → fix
- [ ] HTML arreglado se muestra correctamente

---

## 📊 Métricas de Éxito

| Métrica | Target |
|---------|--------|
| Elementos detectados | >95% de interactivos |
| Feedback capturado | 100% de clicks |
| Tiempo de prepare | <2s |
| Tiempo de fix | <10s |
| UX - Popup latency | <100ms |
| Errores de integración | 0 |

---

## 📈 Impacto en Probabilidad de Éxito

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPARACIÓN DE APPROACHES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Solo Sandbox Automático:                                                 │
│   ├── Detecta: Errores CSS/JS técnicos                                    │
│   ├── No detecta: Errores funcionales/UX                                  │
│   └── Probabilidad: ~88%                                                  │
│                                                                             │
│   Solo Feedback Humano:                                                    │
│   ├── Detecta: Todo lo que el usuario nota                                │
│   ├── No detecta: Errores técnicos invisibles                             │
│   └── Probabilidad: ~85%                                                  │
│                                                                             │
│   Sandbox + Feedback Humano (ESTE SPRINT):                                │
│   ├── Detecta: Errores técnicos + funcionales                             │
│   ├── LLM recibe: Causa técnica + comportamiento esperado                 │
│   └── Probabilidad: ~95% (+7%)                                            │
│                                                                             │
│   Con 1 iteración adicional: ~98%                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📅 Timeline

```
Semana 1:
├── T4-B01, T4-B02, T4-B03 (Backend prepare)
├── T4-F01, T4-F02 (Frontend setup)
└── T4-F03 (PreviewFrame)

Semana 2:
├── T4-B04, T4-B05, T4-B06 (Backend fix)
├── T4-F04, T4-F05, T4-F06 (Frontend components)
└── T4-F07 (LayoutValidator)

Semana 3:
├── T4-B07, T4-B08 (Backend prompt + tests)
├── T4-F08, T4-F09, T4-F10, T4-F11 (Frontend API + polish)
└── T4-I01, T4-I02, T4-I03 (Integración)
```

---

## 📁 Archivos Entregables

| Archivo | Ubicación |
|---------|-----------|
| element_mapper.py | src/html_fixer/feedback/ |
| annotation_injector.py | src/html_fixer/feedback/ |
| feedback_merger.py | src/html_fixer/feedback/ |
| routes.py | src/html_fixer/api/ |
| feedback.py | src/html_fixer/contracts/ |
| fixer_prompt_v2.py | src/html_fixer/prompts/ |
| LayoutValidator.tsx | frontend/src/components/ |
| PreviewFrame.tsx | frontend/src/components/ |
| FeedbackPopup.tsx | frontend/src/components/ |
| **GlobalFeedbackModal.tsx** | **frontend/src/components/** |
| useLayoutValidation.ts | frontend/src/hooks/ |
| validation.ts | frontend/src/types/ |
| validationApi.ts | frontend/src/services/ |

---

## 🆕 COMPONENTES ADICIONALES (CORRECCIONES)

### T4-F03 ACTUALIZADO: PreviewFrame con postMessage

```tsx
// components/layout-validator/PreviewFrame.tsx

import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import { ElementInfo, ElementMap } from '../../types/validation';

interface PreviewFrameProps {
  html: string;
  elementMap: ElementMap;
  feedbackStatus: Record<number, 'working' | 'broken' | 'untested'>;
  onElementClick: (element: ElementInfo, position: { x: number; y: number }) => void;
  onIframeReady?: () => void;
}

export const PreviewFrame = forwardRef<HTMLIFrameElement, PreviewFrameProps>(
  ({ html, elementMap, feedbackStatus, onElementClick, onIframeReady }, ref) => {
    const iframeRef = useRef<HTMLIFrameElement>(null);
    
    useImperativeHandle(ref, () => iframeRef.current!);

    // 🔑 ESCUCHAR MENSAJES DEL IFRAME via postMessage
    useEffect(() => {
      const handleMessage = (event: MessageEvent) => {
        // Verificar que el mensaje viene de NUESTRO iframe
        if (event.source !== iframeRef.current?.contentWindow) {
          return;
        }
        
        const { type, vid, rect } = event.data;
        
        if (type === 'ELEMENT_CLICKED') {
          const elementInfo = elementMap[vid];
          
          if (elementInfo) {
            // Calcular posición ABSOLUTA del popup
            // rect viene relativo al iframe, sumamos offset del iframe
            const iframeRect = iframeRef.current?.getBoundingClientRect();
            
            if (iframeRect) {
              onElementClick(elementInfo, {
                x: iframeRect.left + rect.left + rect.width / 2,
                y: iframeRect.top + rect.bottom + 10
              });
            }
          }
        }
        
        if (type === 'IFRAME_READY') {
          onIframeReady?.();
        }
      };
      
      window.addEventListener('message', handleMessage);
      return () => window.removeEventListener('message', handleMessage);
    }, [elementMap, onElementClick, onIframeReady]);

    // Escribir HTML en iframe (ya incluye script de validación del backend)
    useEffect(() => {
      const iframe = iframeRef.current;
      if (!iframe) return;

      const doc = iframe.contentDocument;
      if (!doc) return;

      doc.open();
      doc.write(html);
      doc.close();
    }, [html]);

    // Actualizar estilos de feedback via postMessage
    useEffect(() => {
      const iframe = iframeRef.current;
      if (!iframe?.contentWindow) return;
      
      iframe.contentWindow.postMessage({
        type: 'UPDATE_FEEDBACK_STATUS',
        status: feedbackStatus
      }, '*');
    }, [feedbackStatus]);

    return (
      <iframe
        ref={iframeRef}
        className="w-full h-[600px] border-2 border-gray-200 rounded-lg bg-white"
        title="Layout Preview"
        sandbox="allow-scripts allow-same-origin"
      />
    );
  }
);
```

---

### T4-F12: GlobalFeedbackModal (Elementos Faltantes)

```tsx
// components/layout-validator/GlobalFeedbackModal.tsx

import React, { useState } from 'react';

interface GlobalFeedbackModalProps {
  isOpen: boolean;
  existingFeedback: string[];
  onSubmit: (feedback: string) => void;
  onClose: () => void;
}

export function GlobalFeedbackModal({
  isOpen,
  existingFeedback,
  onSubmit,
  onClose
}: GlobalFeedbackModalProps) {
  const [message, setMessage] = useState('');

  if (!isOpen) return null;

  const handleSubmit = () => {
    if (message.trim()) {
      onSubmit(message.trim());
      setMessage('');
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-[9998]" onClick={onClose} />
      
      {/* Modal */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999] bg-white rounded-xl shadow-2xl p-6 w-[500px] max-h-[80vh] overflow-y-auto">
        <h2 className="text-xl font-bold text-gray-900 mb-2">
          📝 Feedback Global
        </h2>
        <p className="text-gray-600 mb-4">
          Reporta elementos o funcionalidades que <strong>faltan</strong> en el layout.
        </p>

        {/* Feedback existente */}
        {existingFeedback.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-2">
              Feedback ya agregado:
            </p>
            <ul className="space-y-1">
              {existingFeedback.map((fb, i) => (
                <li key={i} className="text-sm bg-yellow-50 text-yellow-800 px-3 py-2 rounded">
                  • {fb}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Input de nuevo feedback */}
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 mb-1 block">
            ¿Qué falta o qué debería cambiar?
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ej: Falta un botón de volver al inicio, necesita sección de contacto al final, el título debería ser más grande..."
            className="w-full h-24 p-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
        </div>

        {/* Ejemplos */}
        <div className="mb-4 bg-gray-50 p-3 rounded-lg">
          <p className="text-xs font-medium text-gray-500 mb-2">EJEMPLOS:</p>
          <div className="flex flex-wrap gap-2">
            {[
              'Falta breadcrumb de navegación',
              'Necesita footer con links',
              'Falta botón de volver',
              'Necesita validación en el formulario'
            ].map((example) => (
              <button
                key={example}
                onClick={() => setMessage(example)}
                className="text-xs px-2 py-1 bg-white border border-gray-200 rounded hover:bg-gray-100"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Botones */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 px-4 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={!message.trim()}
            className="flex-1 py-2 px-4 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-lg font-medium"
          >
            Agregar Feedback
          </button>
        </div>
      </div>
    </>
  );
}
```

---

### T4-F05 ACTUALIZADO: ControlPanel con Global Feedback

```tsx
// Agregar al ControlPanel.tsx

// En las props:
interface ControlPanelProps {
  // ... props existentes ...
  globalFeedback: string[];
  onOpenGlobalFeedback: () => void;
}

// En el JSX, agregar botón:
<div className="flex gap-3">
  <button
    onClick={onReset}
    disabled={!hasAnyFeedback || isSubmitting}
    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 rounded-lg font-medium"
  >
    🔄 Resetear
  </button>
  
  {/* 🆕 BOTÓN DE FEEDBACK GLOBAL */}
  <button
    onClick={onOpenGlobalFeedback}
    className="px-4 py-2 bg-yellow-100 hover:bg-yellow-200 text-yellow-800 rounded-lg font-medium flex items-center gap-2"
  >
    📝 Feedback Global
    {globalFeedback.length > 0 && (
      <span className="bg-yellow-500 text-white text-xs px-2 py-0.5 rounded-full">
        {globalFeedback.length}
      </span>
    )}
  </button>
  
  {/* Botón de enviar */}
  {/* ... código existente ... */}
</div>
```

---

### T4-B09: Soporte Backend para Global Feedback

```python
# feedback/annotation_injector.py - ACTUALIZAR

class AnnotationInjector:
    """Inyecta comentarios de feedback en el HTML."""
    
    def inject(
        self, 
        html: str, 
        element_feedback: List[UserFeedback],
        global_feedback: List[str] = None  # 🆕 NUEVO
    ) -> AnnotatedHTML:
        """
        Inyecta comentarios antes de cada elemento con feedback.
        También inyecta feedback global al inicio del body.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # ... código existente para element_feedback ...
        
        # 🆕 INYECTAR FEEDBACK GLOBAL al inicio del body
        if global_feedback:
            body = soup.find('body')
            if body:
                for gf in global_feedback:
                    safe_message = gf.replace('"', '\\"')
                    comment = Comment(f' [GLOBAL FEEDBACK] "{safe_message}" ')
                    # Insertar al inicio del body
                    body.insert(0, comment)
                    body.insert(1, "\n")
        
        return AnnotatedHTML(
            html=str(soup),
            annotations_count=annotations_count + len(global_feedback or []),
            working_elements=working_elements,
            broken_elements=broken_elements,
            global_feedback_count=len(global_feedback or [])  # 🆕
        )
```

---

### Tipos Actualizados (T4-F02)

```typescript
// types/validation.ts - AGREGAR

// 🆕 Feedback global para elementos faltantes
export interface GlobalFeedback {
  message: string;
  createdAt: Date;
}

// Actualizar SubmitPayload
export interface SubmitPayload {
  html: string;
  feedback: Array<{
    vid: number;
    status: 'working' | 'broken';
    message?: string;
  }>;
  globalFeedback: string[];  // 🆕 NUEVO
}
```

---

### Hook Actualizado (T4-F06)

```typescript
// hooks/useLayoutValidation.ts - AGREGAR

// En el estado:
const [globalFeedback, setGlobalFeedback] = useState<string[]>([]);

// Nueva función:
const addGlobalFeedback = useCallback((message: string) => {
  setGlobalFeedback(prev => [...prev, message]);
}, []);

// Actualizar submit:
const submit = useCallback(async () => {
  // ... código existente ...
  
  const payload = {
    html: initialHtml,
    feedback: Object.values(feedback)
      .filter(f => f.status !== 'untested')
      .map(f => ({
        vid: f.vid,
        status: f.status as 'working' | 'broken',
        message: f.message
      })),
    globalFeedback  // 🆕 INCLUIR
  };
  
  // ... resto del código ...
}, [initialHtml, feedback, globalFeedback]);

// Retornar:
return {
  // ... existentes ...
  globalFeedback,
  addGlobalFeedback
};
```

---

## 📊 Resumen de Cambios por el Feedback de Revisión

| Problema | Solución | Task Afectado |
|----------|----------|---------------|
| Eventos no capturables desde fuera del iframe | Inyectar script con `postMessage` | T4-B01, T4-F03 |
| Posicionamiento del popup incorrecto | Sumar offset del iframe a las coords | T4-F03 |
| No se puede reportar elementos faltantes | Global Feedback Modal | T4-F05, T4-F12, T4-B09 |
| Feedback incompleto no advertido | Ya estaba en el plan ✅ | T4-F09 |

---

## ✅ Definition of Done (Sprint 4) - ACTUALIZADO

### Backend
- [ ] ElementMapper inyecta data-vid en todos los elementos interactivos
- [ ] **ElementMapper inyecta script de postMessage** 🆕
- [ ] AnnotationInjector inyecta comentarios correctamente
- [ ] **AnnotationInjector soporta Global Feedback** 🆕
- [ ] FeedbackMerger combina sandbox + feedback del usuario
- [ ] Endpoint `/prepare-validation` funciona
- [ ] Endpoint `/fix-with-feedback` funciona
- [ ] Prompt LLM lee y entiende comentarios de feedback
- [ ] Tests con >80% coverage

### Frontend
- [ ] PreviewFrame renderiza HTML completo en iframe
- [ ] **PreviewFrame usa postMessage para comunicación** 🆕
- [ ] Clicks en elementos interactivos disparan popup
- [ ] **Popup se posiciona correctamente (offset iframe)** 🆕
- [ ] FeedbackPopup permite ✅/❌ y mensaje
- [ ] ControlPanel muestra progreso correcto
- [ ] **ControlPanel incluye botón Global Feedback** 🆕
- [ ] **GlobalFeedbackModal funciona** 🆕
- [ ] Warning modal aparece si feedback incompleto
- [ ] Llamadas API funcionan correctamente
- [ ] UI responsive y usable

### Integración
- [ ] CORS configurado correctamente
- [ ] Flujo E2E funciona: prepare → feedback → fix
- [ ] HTML arreglado se muestra correctamente