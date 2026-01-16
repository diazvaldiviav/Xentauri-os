# 📋 SCRUM PLAN COMPLETO
## HTML Validator & Fixer - "Chirurgical Fixer"

**Proyecto:** HTML Fixer Infalible  
**Duración Total:** 12 semanas (6 sprints de 2 semanas)  
**Equipo:** 1 Developer + 1 AI Assistant (Scrum Master)  
**Metodología:** Scrum con sprints de 2 semanas  

---

# 📦 PRODUCT BACKLOG (Priorizado)

## Épicas

| ID | Épica | Prioridad | Business Value |
|----|-------|-----------|----------------|
| E1 | Análisis Estático de HTML/CSS | 🔴 Crítica | Fundación de todo el sistema |
| E2 | Fixer Determinístico (Sin LLM) | 🔴 Crítica | 70% de fixes automáticos |
| E3 | Sandbox de Validación Visual | 🔴 Crítica | Verificación de reparaciones |
| E4 | LLM Surgical Fixer | 🟡 Alta | Fixes complejos restantes |
| E5 | Orquestador y Rollback | 🟡 Alta | Coordinación del pipeline |
| E6 | Test Suite y CI/CD | 🟢 Media | Calidad y mantenibilidad |

---

## User Stories Completas

### Épica 1: Análisis Estático (E1)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-01 | Como sistema, necesito parsear HTML para extraer el DOM tree | 5 | 🔴 |
| US-02 | Como sistema, necesito analizar CSS computed styles de cada elemento | 8 | 🔴 |
| US-03 | Como sistema, necesito mapear event handlers (onclick, etc.) | 5 | 🔴 |
| US-04 | Como sistema, necesito construir jerarquía de z-index | 5 | 🔴 |
| US-05 | Como sistema, necesito detectar elementos con pointer-events bloqueados | 5 | 🔴 |
| US-06 | Como sistema, necesito clasificar errores en categorías predefinidas | 8 | 🔴 |

### Épica 2: Fixer Determinístico (E2)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-07 | Como sistema, necesito regla para arreglar conflictos de z-index | 3 | 🔴 |
| US-08 | Como sistema, necesito regla para arreglar pointer-events bloqueados | 5 | 🔴 |
| US-09 | Como sistema, necesito regla para restaurar visibilidad de elementos | 3 | 🔴 |
| US-10 | Como sistema, necesito regla para arreglar transforms 3D | 5 | 🔴 |
| US-11 | Como sistema, necesito regla para amplificar feedback visual débil | 3 | 🔴 |
| US-12 | Como sistema, necesito inyectar CSS patches sin modificar estructura | 5 | 🔴 |

### Épica 3: Sandbox Visual (E3)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-13 | Como sistema, necesito renderizar HTML en Playwright headless | 5 | 🔴 |
| US-14 | Como sistema, necesito capturar screenshots before/after de clicks | 8 | 🔴 |
| US-15 | Como sistema, necesito comparar screenshots con pixel diff | 5 | 🔴 |
| US-16 | Como sistema, necesito detectar qué elemento intercepta clicks | 8 | 🔴 |
| US-17 | Como sistema, necesito generar reporte estructurado de validación | 5 | 🟡 |

### Épica 4: LLM Surgical Fixer (E4)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-18 | Como sistema, necesito generar prompts con contexto mínimo necesario | 8 | 🟡 |
| US-19 | Como sistema, necesito que LLM genere patches JSON, no HTML completo | 8 | 🟡 |
| US-20 | Como sistema, necesito validar que patches no sean destructivos | 5 | 🟡 |
| US-21 | Como sistema, necesito aplicar patches de forma reversible | 5 | 🟡 |

### Épica 5: Orquestador (E5)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-22 | Como sistema, necesito coordinar el pipeline completo de fix | 8 | 🟡 |
| US-23 | Como sistema, necesito mantener historial para rollback | 5 | 🟡 |
| US-24 | Como sistema, necesito decidir cuándo usar reglas vs LLM | 5 | 🟡 |
| US-25 | Como sistema, necesito retornar siempre el mejor resultado encontrado | 3 | 🟡 |

### Épica 6: Test Suite (E6)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-26 | Como developer, necesito fixtures HTML para cada tipo de layout | 8 | 🟢 |
| US-27 | Como developer, necesito tests automatizados para cada regla | 5 | 🟢 |
| US-28 | Como developer, necesito métricas de success rate por tipo de error | 5 | 🟢 |
| US-29 | Como developer, necesito CI/CD que ejecute tests en cada PR | 5 | 🟢 |

---

# 🏃 SPRINT 0: FUNDACIÓN
## Semana 1

### 📎 Sprint Goal
> **Establecer la estructura del proyecto, dependencias, y crear los primeros fixtures de prueba que guiarán el desarrollo.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Estimación | Responsable | Estado |
|---------|-------|------------|-------------|--------|
| T0-01 | Crear estructura de carpetas del proyecto | 2h | Dev | ⬜ |
| T0-02 | Configurar pyproject.toml con dependencias | 1h | Dev | ⬜ |
| T0-03 | Instalar y configurar Playwright | 2h | Dev | ⬜ |
| T0-04 | Configurar pytest con plugins necesarios | 1h | Dev | ⬜ |
| T0-05 | Crear 5 fixtures HTML de trivia (incluyendo el caso actual) | 4h | Dev | ⬜ |
| T0-06 | Crear 3 fixtures HTML de dashboard | 3h | Dev | ⬜ |
| T0-07 | Crear 2 fixtures HTML de modales | 2h | Dev | ⬜ |
| T0-08 | Documentar contratos de datos (dataclasses) | 3h | Dev | ⬜ |
| T0-09 | Crear README con arquitectura | 2h | Dev | ⬜ |
| T0-10 | Setup logging estructurado | 1h | Dev | ⬜ |

**Total Estimado:** 21 horas (~3 días de trabajo)

---

### 📁 Entregables

```
html_fixer/
├── pyproject.toml
├── README.md
├── src/
│   └── html_fixer/
│       ├── __init__.py
│       ├── contracts/
│       │   ├── __init__.py
│       │   ├── errors.py          # ErrorType, ClassifiedError
│       │   ├── patches.py         # Patch, PatchResult
│       │   └── validation.py      # ValidationResult, ElementResult
│       ├── analyzers/
│       │   └── __init__.py
│       ├── fixers/
│       │   ├── __init__.py
│       │   ├── deterministic/
│       │   │   └── __init__.py
│       │   └── llm/
│       │       └── __init__.py
│       ├── validators/
│       │   └── __init__.py
│       └── orchestrator/
│           └── __init__.py
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── trivia/
    │   │   ├── flashcard_3d_broken.html      # Tu caso actual
    │   │   ├── flashcard_3d_expected.html    # Versión corregida
    │   │   ├── multiple_choice_broken.html
    │   │   ├── quiz_modal_broken.html
    │   │   └── sequential_broken.html
    │   ├── dashboard/
    │   │   ├── sidebar_broken.html
    │   │   ├── card_grid_broken.html
    │   │   └── data_table_broken.html
    │   └── modals/
    │       ├── nested_broken.html
    │       └── form_modal_broken.html
    └── unit/
        └── __init__.py
```

---

### ✅ Definition of Done (Sprint 0)

- [ ] Proyecto se puede instalar con `pip install -e .`
- [ ] `pytest` ejecuta sin errores (aunque no haya tests aún)
- [ ] Playwright puede abrir un fixture y tomar screenshot
- [ ] 10 fixtures HTML creados y documentados
- [ ] Cada fixture tiene comentarios indicando qué está "roto"
- [ ] README documenta la arquitectura propuesta

---

### 🎯 Criterios de Aceptación

```python
# AC-01: Proyecto instalable
def test_project_installable():
    result = subprocess.run(["pip", "install", "-e", "."])
    assert result.returncode == 0

# AC-02: Playwright funcional
def test_playwright_can_screenshot(fixture_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(open(fixture_path).read())
        screenshot = await page.screenshot()
        assert len(screenshot) > 0

# AC-03: Fixtures tienen errores conocidos
def test_fixtures_have_documented_errors():
    for fixture in glob("tests/fixtures/**/*.html"):
        content = open(fixture).read()
        assert "<!-- ERROR:" in content  # Documentar errores
```

---

# 🏃 SPRINT 1: CLASIFICADOR DE ERRORES (Parte 1)
## Semanas 2-3

### 📎 Sprint Goal
> **Construir el analizador de DOM y CSS que detecta y clasifica errores con precisión, identificando el tipo exacto de problema.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T1-01 | Implementar DOMParser con BeautifulSoup | US-01 | 4h | ⬜ |
| T1-02 | Implementar extractor de elementos interactivos | US-01 | 3h | ⬜ |
| T1-03 | Crear CSSAnalyzer base con Playwright | US-02 | 6h | ⬜ |
| T1-04 | Implementar getComputedStyle para cada elemento | US-02 | 4h | ⬜ |
| T1-05 | Crear EventMapper para onclick/handlers | US-03 | 4h | ⬜ |
| T1-06 | Implementar ZIndexHierarchyBuilder | US-04 | 5h | ⬜ |
| T1-07 | Crear detector de pointer-events bloqueados | US-05 | 6h | ⬜ |
| T1-08 | Implementar elementFromPoint analysis | US-05 | 4h | ⬜ |
| T1-09 | Tests unitarios para cada analizador | - | 4h | ⬜ |

**Total Estimado:** 40 horas (~2 semanas)

---

### 📝 Especificación Técnica

#### ErrorType Enum
```python
class ErrorType(Enum):
    """Clasificación de errores CSS/DOM detectables."""
    
    # Errores de visibilidad (RULE-FIXABLE)
    INVISIBLE_OPACITY = "invisible_opacity"      # opacity: 0
    INVISIBLE_DISPLAY = "invisible_display"      # display: none
    INVISIBLE_VISIBILITY = "invisible_visibility" # visibility: hidden
    INVISIBLE_OFFSCREEN = "invisible_offscreen"  # fuera del viewport
    
    # Errores de stacking (RULE-FIXABLE)
    ZINDEX_CONFLICT = "zindex_conflict"          # z-index inferior
    ZINDEX_MISSING = "zindex_missing"            # sin z-index en positioned
    
    # Errores de pointer (RULE-FIXABLE)
    POINTER_BLOCKED = "pointer_blocked"          # pointer-events: none
    POINTER_INTERCEPTED = "pointer_intercepted"  # otro elemento encima
    
    # Errores de transform (RULE-FIXABLE)
    TRANSFORM_3D_HIDDEN = "transform_3d_hidden"  # rotateY hace elemento thin
    TRANSFORM_OFFSCREEN = "transform_offscreen"  # translate fuera de viewport
    BACKFACE_HIDDEN = "backface_hidden"          # backface-visibility issue
    
    # Errores de feedback (RULE-FIXABLE)
    FEEDBACK_TOO_SUBTLE = "feedback_too_subtle"  # click funciona pero no se ve
    
    # Errores de eventos (LLM-REQUIRED)
    EVENT_NOT_BOUND = "event_not_bound"          # onclick no existe
    EVENT_HANDLER_ERROR = "event_handler_error"  # JS error en handler
    
    # Errores complejos (LLM-REQUIRED)
    COMPLEX_LAYOUT_ISSUE = "complex_layout"      # múltiples problemas
```

#### ClassifiedError Dataclass
```python
@dataclass
class ClassifiedError:
    """Error clasificado con toda la información necesaria para el fix."""
    
    error_type: ErrorType
    selector: str                    # CSS selector del elemento afectado
    element_tag: str                 # button, div, input, etc.
    
    # Contexto del error
    blocking_element: Optional[str]  # Selector del elemento que bloquea
    computed_styles: Dict[str, str]  # Estilos relevantes
    bounding_box: Dict[str, float]   # {x, y, width, height}
    
    # Para el fixer
    suggested_fix: Optional[str]     # CSS sugerido (para RULE-FIXABLE)
    requires_llm: bool               # True si necesita LLM
    
    # Metadata
    confidence: float                # 0.0 - 1.0
    line_number: Optional[int]       # Línea en el HTML original
```

---

### 🧪 Tests Requeridos

```python
# test_dom_parser.py
class TestDOMParser:
    def test_extracts_buttons(self, trivia_fixture):
        parser = DOMParser(trivia_fixture)
        buttons = parser.get_interactive_elements()
        assert len(buttons) >= 4  # 4 option buttons
    
    def test_extracts_onclick_handlers(self, trivia_fixture):
        parser = DOMParser(trivia_fixture)
        handlers = parser.get_event_handlers()
        assert "handleSelection" in str(handlers)

# test_css_analyzer.py
class TestCSSAnalyzer:
    async def test_detects_opacity_zero(self, invisible_fixture):
        analyzer = CSSAnalyzer()
        errors = await analyzer.analyze(invisible_fixture)
        assert any(e.error_type == ErrorType.INVISIBLE_OPACITY for e in errors)
    
    async def test_detects_pointer_intercept(self, flashcard_fixture):
        analyzer = CSSAnalyzer()
        errors = await analyzer.analyze(flashcard_fixture)
        assert any(e.error_type == ErrorType.POINTER_INTERCEPTED for e in errors)

# test_zindex_hierarchy.py
class TestZIndexHierarchy:
    def test_builds_hierarchy(self, modal_fixture):
        builder = ZIndexHierarchyBuilder()
        hierarchy = builder.build(modal_fixture)
        assert hierarchy.get_level(".modal") > hierarchy.get_level(".background")
```

---

### ✅ Definition of Done (Sprint 1)

- [ ] DOMParser extrae todos los elementos interactivos
- [ ] CSSAnalyzer detecta los 6 tipos de errores de visibilidad/stacking
- [ ] EventMapper identifica onclick handlers
- [ ] ZIndexHierarchyBuilder construye árbol de stacking
- [ ] Detector de pointer-events identifica bloqueos
- [ ] 90%+ de errores en fixtures son clasificados correctamente
- [ ] Tests unitarios con >80% coverage

---

### 📊 Métricas de Éxito

| Métrica | Target |
|---------|--------|
| Errores clasificados correctamente | ≥90% |
| Tiempo de análisis por fixture | <500ms |
| False positives | <5% |
| Coverage de tests | >80% |

---

# 🏃 SPRINT 2: CLASIFICADOR DE ERRORES (Parte 2) + PLAYWRIGHT DIAGNOSTICS
## Semanas 4-5

### 📎 Sprint Goal
> **Completar el sistema de clasificación integrando Playwright para diagnóstico en tiempo real, detectando exactamente qué elemento bloquea cada click.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T2-01 | Crear diagnóstico de elemento con Playwright | US-06 | 6h | ⬜ |
| T2-02 | Implementar elementFromPoint analysis | US-06 | 4h | ⬜ |
| T2-03 | Crear detector de backface-visibility issues | US-06 | 4h | ⬜ |
| T2-04 | Implementar detector de transforms problemáticos | US-06 | 5h | ⬜ |
| T2-05 | Crear aggregador de errores por elemento | US-06 | 3h | ⬜ |
| T2-06 | Implementar priorizador de errores | US-06 | 3h | ⬜ |
| T2-07 | Crear ErrorReport generator (JSON) | US-06 | 4h | ⬜ |
| T2-08 | Integrar todos los analizadores en pipeline | - | 5h | ⬜ |
| T2-09 | Tests de integración del clasificador | - | 6h | ⬜ |

**Total Estimado:** 40 horas

---

### 📝 Especificación Técnica

#### Playwright Diagnostic Function
```python
async def diagnose_element(page: Page, selector: str) -> ElementDiagnosis:
    """
    Diagnóstico completo de un elemento usando Playwright.
    
    Returns:
        ElementDiagnosis con toda la información del problema
    """
    diagnosis = await page.evaluate('''
        (selector) => {
            const el = document.querySelector(selector);
            if (!el) return { found: false };
            
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            
            // 1. Verificar visibilidad
            const visibility = {
                display: style.display,
                visibility: style.visibility,
                opacity: parseFloat(style.opacity),
                width: rect.width,
                height: rect.height,
                inViewport: (
                    rect.top < window.innerHeight &&
                    rect.bottom > 0 &&
                    rect.left < window.innerWidth &&
                    rect.right > 0
                )
            };
            
            // 2. Verificar qué elemento recibe el click
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const topElement = document.elementFromPoint(centerX, centerY);
            
            const interceptor = topElement !== el ? {
                tag: topElement?.tagName,
                id: topElement?.id,
                className: topElement?.className,
                selector: generateSelector(topElement)
            } : null;
            
            // 3. Verificar z-index y stacking
            const stacking = {
                zIndex: style.zIndex,
                position: style.position,
                transform: style.transform,
                transformStyle: style.transformStyle
            };
            
            // 4. Verificar pointer-events
            const pointerEvents = {
                value: style.pointerEvents,
                inherited: isPointerEventsInherited(el)
            };
            
            return {
                found: true,
                visibility,
                interceptor,
                stacking,
                pointerEvents,
                rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
            };
        }
    ''', selector)
    
    return ElementDiagnosis.from_dict(diagnosis)
```

#### Error Classification Pipeline
```python
class ErrorClassificationPipeline:
    """Pipeline que integra todos los analizadores."""
    
    def __init__(self):
        self.dom_parser = DOMParser()
        self.css_analyzer = CSSAnalyzer()
        self.event_mapper = EventMapper()
        self.zindex_builder = ZIndexHierarchyBuilder()
    
    async def classify(self, html: str) -> List[ClassifiedError]:
        """
        Ejecuta todos los analizadores y devuelve errores clasificados.
        """
        errors = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(html)
            
            # 1. Obtener elementos interactivos
            interactive = self.dom_parser.get_interactive_elements(html)
            
            # 2. Diagnosticar cada elemento
            for element in interactive:
                diagnosis = await diagnose_element(page, element.selector)
                
                # 3. Clasificar el error
                error = self._classify_diagnosis(element, diagnosis)
                if error:
                    errors.append(error)
            
            await browser.close()
        
        # 4. Priorizar errores
        return self._prioritize(errors)
    
    def _classify_diagnosis(
        self, 
        element: InteractiveElement, 
        diagnosis: ElementDiagnosis
    ) -> Optional[ClassifiedError]:
        """Clasifica el diagnóstico en un tipo de error."""
        
        # Regla 1: Elemento no encontrado
        if not diagnosis.found:
            return ClassifiedError(
                error_type=ErrorType.INVISIBLE_DISPLAY,
                selector=element.selector,
                requires_llm=False
            )
        
        # Regla 2: Elemento interceptado
        if diagnosis.interceptor:
            return ClassifiedError(
                error_type=ErrorType.POINTER_INTERCEPTED,
                selector=element.selector,
                blocking_element=diagnosis.interceptor.selector,
                requires_llm=False,
                suggested_fix=self._generate_pointer_fix(diagnosis)
            )
        
        # Regla 3: Z-index issue
        if diagnosis.stacking.position != 'static' and diagnosis.stacking.zIndex == 'auto':
            return ClassifiedError(
                error_type=ErrorType.ZINDEX_MISSING,
                selector=element.selector,
                requires_llm=False,
                suggested_fix=f"{element.selector} {{ z-index: 1000; }}"
            )
        
        # ... más reglas
        
        return None
```

---

### ✅ Definition of Done (Sprint 2)

- [ ] Playwright diagnóstico funciona para todos los fixtures
- [ ] Sistema clasifica 100% de errores en una categoría
- [ ] Cada error tiene selector del bloqueador (si aplica)
- [ ] ErrorReport genera JSON estructurado
- [ ] Pipeline integrado ejecuta en <2 segundos por fixture
- [ ] Tests de integración pasan con 90%+ accuracy

---

### 📊 Métricas de Éxito

| Métrica | Target |
|---------|--------|
| Accuracy de clasificación | ≥95% |
| Errores con suggested_fix | ≥70% |
| Tiempo total de clasificación | <2s |
| Bloqueadores identificados correctamente | 100% |

---

# 🏃 SPRINT 3: FIXER DETERMINÍSTICO (Parte 1)
## Semanas 6-7

### 📎 Sprint Goal
> **Implementar las reglas de reparación automática para errores de z-index, pointer-events, y visibilidad - sin usar LLM.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T3-01 | Crear RuleEngine base class | US-07 | 3h | ⬜ |
| T3-02 | Implementar ZIndexFixRule | US-07 | 4h | ⬜ |
| T3-03 | Implementar PointerEventsFixRule | US-08 | 5h | ⬜ |
| T3-04 | Implementar VisibilityRestoreRule | US-09 | 3h | ⬜ |
| T3-05 | Crear CSSInjector (inserta CSS sin modificar DOM) | US-12 | 4h | ⬜ |
| T3-06 | Implementar regla de passthrough selectivo | US-08 | 4h | ⬜ |
| T3-07 | Tests para ZIndexFixRule | - | 3h | ⬜ |
| T3-08 | Tests para PointerEventsFixRule | - | 4h | ⬜ |
| T3-09 | Tests para VisibilityRestoreRule | - | 3h | ⬜ |
| T3-10 | Integration test: fix + validate cycle | - | 5h | ⬜ |

**Total Estimado:** 38 horas

---

### 📝 Especificación Técnica

#### Rule Engine Base
```python
from abc import ABC, abstractmethod
from typing import Optional

class FixRule(ABC):
    """Base class para todas las reglas de reparación."""
    
    # Tipos de error que esta regla puede arreglar
    handles: List[ErrorType] = []
    
    # Prioridad de ejecución (menor = antes)
    priority: int = 100
    
    @abstractmethod
    def can_fix(self, error: ClassifiedError) -> bool:
        """Determina si esta regla puede arreglar el error."""
        pass
    
    @abstractmethod
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        """Genera el CSS patch para arreglar el error."""
        pass
    
    def validate_fix(self, original: str, patched: str) -> bool:
        """Valida que el fix no sea destructivo (opcional override)."""
        return True


class RuleEngine:
    """Motor que ejecuta reglas en orden de prioridad."""
    
    def __init__(self):
        self.rules: List[FixRule] = []
    
    def register(self, rule: FixRule):
        """Registra una regla en el engine."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
    
    def fix(self, html: str, errors: List[ClassifiedError]) -> str:
        """Aplica todas las reglas aplicables a los errores."""
        patches = []
        
        for error in errors:
            for rule in self.rules:
                if rule.can_fix(error):
                    patch = rule.generate_fix(error)
                    patches.append(patch)
                    break  # Solo una regla por error
        
        return self._apply_patches(html, patches)
```

#### Reglas Específicas
```python
class ZIndexFixRule(FixRule):
    """Arregla conflictos de z-index."""
    
    handles = [ErrorType.ZINDEX_CONFLICT, ErrorType.ZINDEX_MISSING]
    priority = 10  # Alta prioridad
    
    def can_fix(self, error: ClassifiedError) -> bool:
        return error.error_type in self.handles
    
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        return CSSPatch(
            type="css_inject",
            location="end_of_style",
            content=f"""
/* Fix: Z-Index for {error.selector} */
{error.selector} {{
    position: relative !important;
    z-index: 1000 !important;
}}
"""
        )


class PointerEventsFixRule(FixRule):
    """Arregla elementos bloqueados por pointer-events."""
    
    handles = [ErrorType.POINTER_BLOCKED, ErrorType.POINTER_INTERCEPTED]
    priority = 20
    
    def can_fix(self, error: ClassifiedError) -> bool:
        return error.error_type in self.handles and error.blocking_element is not None
    
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        blocker = error.blocking_element
        target = error.selector
        
        return CSSPatch(
            type="css_inject",
            location="end_of_style",
            content=f"""
/* Fix: Pointer passthrough for {target} */
{blocker} {{
    pointer-events: none !important;
}}
{blocker} button,
{blocker} [onclick],
{blocker} input,
{blocker} a {{
    pointer-events: auto !important;
}}
{target} {{
    position: relative !important;
    z-index: 1001 !important;
    pointer-events: auto !important;
}}
"""
        )


class VisibilityRestoreRule(FixRule):
    """Restaura visibilidad de elementos ocultos."""
    
    handles = [
        ErrorType.INVISIBLE_OPACITY,
        ErrorType.INVISIBLE_DISPLAY,
        ErrorType.INVISIBLE_VISIBILITY
    ]
    priority = 5  # Muy alta prioridad
    
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        fixes = {
            ErrorType.INVISIBLE_OPACITY: "opacity: 1 !important;",
            ErrorType.INVISIBLE_DISPLAY: "display: block !important;",
            ErrorType.INVISIBLE_VISIBILITY: "visibility: visible !important;",
        }
        
        return CSSPatch(
            type="css_inject",
            location="end_of_style",
            content=f"""
/* Fix: Visibility restore for {error.selector} */
{error.selector} {{
    {fixes[error.error_type]}
}}
"""
        )
```

#### CSS Injector
```python
class CSSInjector:
    """Inyecta CSS patches sin modificar la estructura del DOM."""
    
    def inject(self, html: str, patches: List[CSSPatch]) -> str:
        """
        Inyecta todos los patches en el HTML.
        
        Estrategia:
        1. Encontrar el tag </style> existente
        2. Insertar patches justo antes de </style>
        3. Si no hay <style>, crear uno antes de </head>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar o crear tag style
        style_tag = soup.find('style')
        if not style_tag:
            style_tag = soup.new_tag('style')
            head = soup.find('head')
            if head:
                head.append(style_tag)
            else:
                # Crear head si no existe
                html_tag = soup.find('html')
                head = soup.new_tag('head')
                html_tag.insert(0, head)
                head.append(style_tag)
        
        # Agregar patches
        patch_css = "\n\n/* === AUTO-GENERATED FIXES === */\n"
        for patch in patches:
            patch_css += f"\n{patch.content}\n"
        
        style_tag.string = (style_tag.string or "") + patch_css
        
        return str(soup)
```

---

### 🧪 Tests Requeridos

```python
class TestZIndexFixRule:
    def test_generates_correct_css(self):
        error = ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector=".option-btn",
            blocking_element=".card-front"
        )
        rule = ZIndexFixRule()
        patch = rule.generate_fix(error)
        
        assert "z-index: 1000" in patch.content
        assert "position: relative" in patch.content
    
    async def test_fix_actually_works(self, flashcard_broken_fixture):
        # Arrange
        engine = RuleEngine()
        engine.register(ZIndexFixRule())
        classifier = ErrorClassificationPipeline()
        
        # Classify errors
        errors = await classifier.classify(flashcard_broken_fixture)
        
        # Fix
        fixed = engine.fix(flashcard_broken_fixture, errors)
        
        # Validate
        new_errors = await classifier.classify(fixed)
        zindex_errors = [e for e in new_errors if e.error_type == ErrorType.ZINDEX_CONFLICT]
        
        assert len(zindex_errors) == 0  # Error debe estar arreglado
```

---

### ✅ Definition of Done (Sprint 3)

- [ ] RuleEngine ejecuta reglas en orden de prioridad
- [ ] ZIndexFixRule arregla 100% de conflictos z-index en fixtures
- [ ] PointerEventsFixRule arregla 100% de bloqueos pointer
- [ ] VisibilityRestoreRule restaura elementos ocultos
- [ ] CSSInjector no modifica estructura DOM
- [ ] 60%+ de errores en fixtures se arreglan sin LLM
- [ ] Tests unitarios y de integración pasan

---

# 🏃 SPRINT 4: FIXER DETERMINÍSTICO (Parte 2) + SANDBOX BÁSICO
## Semanas 8-9

### 📎 Sprint Goal
> **Completar todas las reglas de reparación automática y crear el sandbox básico de validación visual.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T4-01 | Implementar Transform3DFixRule | US-10 | 6h | ⬜ |
| T4-02 | Implementar BackfaceVisibilityFixRule | US-10 | 4h | ⬜ |
| T4-03 | Implementar VisualFeedbackAmplifierRule | US-11 | 5h | ⬜ |
| T4-04 | Crear Sandbox base con Playwright | US-13 | 6h | ⬜ |
| T4-05 | Implementar screenshot capture | US-14 | 4h | ⬜ |
| T4-06 | Implementar click con detección de intercept | US-16 | 5h | ⬜ |
| T4-07 | Crear ValidationResult dataclass | US-17 | 2h | ⬜ |
| T4-08 | Tests de reglas transform | - | 4h | ⬜ |
| T4-09 | Tests del sandbox básico | - | 4h | ⬜ |

**Total Estimado:** 40 horas

---

### 📝 Especificación Técnica

#### Transform Fix Rules
```python
class Transform3DFixRule(FixRule):
    """Arregla elementos ocultos por transforms 3D."""
    
    handles = [ErrorType.TRANSFORM_3D_HIDDEN, ErrorType.TRANSFORM_OFFSCREEN]
    priority = 30
    
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        # Encontrar el contenedor con transform-style
        parent_selector = self._find_transform_container(error)
        
        return CSSPatch(
            type="css_inject",
            location="end_of_style",
            content=f"""
/* Fix: 3D Transform for {error.selector} */
{parent_selector} {{
    transform-style: preserve-3d !important;
    perspective: 1000px !important;
}}
{error.selector} {{
    transform: translateZ(1px) !important;
    backface-visibility: visible !important;
    -webkit-backface-visibility: visible !important;
}}
"""
        )


class VisualFeedbackAmplifierRule(FixRule):
    """Amplifica feedback visual débil."""
    
    handles = [ErrorType.FEEDBACK_TOO_SUBTLE]
    priority = 50
    
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        return CSSPatch(
            type="css_inject",
            location="end_of_style",
            content=f"""
/* Fix: Visual feedback amplification for {error.selector} */
{error.selector}:active,
{error.selector}.selected,
{error.selector}.active,
{error.selector}:focus {{
    background: #ffffff !important;
    color: #000000 !important;
    border: 4px solid #00ff00 !important;
    transform: scale(1.05) !important;
    box-shadow: 0 0 20px 5px rgba(0, 255, 0, 0.5) !important;
    transition: all 0.1s ease !important;
}}
"""
        )
```

#### Sandbox Básico
```python
class Sandbox:
    """Sandbox para validación de HTML con Playwright."""
    
    def __init__(self, viewport_width: int = 1920, viewport_height: int = 1080):
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.timeout_ms = 2000
        self.stabilization_ms = 500
    
    async def validate(self, html: str) -> ValidationResult:
        """
        Valida HTML renderizándolo y probando interacciones.
        
        Returns:
            ValidationResult con estado de cada elemento
        """
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport=self.viewport)
            
            # Capturar errores JS
            js_errors = []
            page.on("pageerror", lambda e: js_errors.append(str(e)))
            
            # Renderizar
            await page.set_content(html, wait_until="networkidle")
            
            # Screenshot inicial
            initial_screenshot = await page.screenshot()
            
            # Encontrar elementos interactivos
            interactive = await self._find_interactive_elements(page)
            
            # Probar cada elemento
            for element in interactive:
                result = await self._test_element(page, element)
                results.append(result)
            
            await browser.close()
        
        return ValidationResult(
            element_results=results,
            js_errors=js_errors,
            initial_screenshot=initial_screenshot
        )
    
    async def _test_element(self, page: Page, element: ElementInfo) -> ElementResult:
        """Prueba un elemento individual."""
        
        # Screenshot antes
        before = await page.screenshot()
        
        try:
            # Intentar click
            locator = page.locator(element.selector).first
            await locator.click(timeout=self.timeout_ms)
            
            # Esperar estabilización
            await page.wait_for_timeout(self.stabilization_ms)
            
            # Screenshot después
            after = await page.screenshot()
            
            # Comparar
            diff = self._compare_screenshots(before, after)
            
            return ElementResult(
                selector=element.selector,
                status="responsive" if diff > 0.02 else "no_visual_change",
                diff_ratio=diff,
                before_screenshot=before,
                after_screenshot=after
            )
            
        except PlaywrightError as e:
            error_msg = str(e)
            
            # Detectar tipo de error
            if "intercepts pointer events" in error_msg:
                # Extraer elemento bloqueador
                blocker = self._extract_blocker(error_msg)
                return ElementResult(
                    selector=element.selector,
                    status="intercepted",
                    blocking_element=blocker,
                    error=error_msg
                )
            elif "Timeout" in error_msg:
                return ElementResult(
                    selector=element.selector,
                    status="timeout",
                    error=error_msg
                )
            else:
                return ElementResult(
                    selector=element.selector,
                    status="error",
                    error=error_msg
                )
```

---

### ✅ Definition of Done (Sprint 4)

- [ ] Transform3DFixRule arregla elementos con rotateY/rotateX
- [ ] BackfaceVisibilityFixRule arregla issues de backface
- [ ] VisualFeedbackAmplifierRule amplifica feedback débil
- [ ] Sandbox puede renderizar y hacer screenshots
- [ ] Sandbox detecta elementos bloqueadores
- [ ] 70%+ de errores en fixtures se arreglan sin LLM
- [ ] Tests pasan para todas las nuevas reglas

---

### 📊 Milestone Check (Fin Semana 9)

```
┌────────────────────────────────────────────────────────────────────┐
│                    MILESTONE 2: DETERMINISTIC FIXER                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ✓ Clasificador detecta 6 tipos de errores                       │
│   ✓ 5 reglas determinísticas implementadas                        │
│   ✓ 70% de errores en fixtures arreglados sin LLM                 │
│   ✓ Sandbox básico funciona                                       │
│                                                                    │
│   Próximo: Sandbox avanzado + LLM surgical                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

# 🏃 SPRINT 5: SANDBOX AVANZADO + DIFF ENGINE
## Semanas 10-11

### 📎 Sprint Goal
> **Completar el sandbox con comparación multi-escala de screenshots y generación de reportes detallados.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T5-01 | Implementar pixel diff con pixelmatch | US-15 | 5h | ⬜ |
| T5-02 | Crear comparación multi-escala (tight/local/global) | US-15 | 6h | ⬜ |
| T5-03 | Implementar screenshot de elemento específico | US-14 | 4h | ⬜ |
| T5-04 | Crear clasificador de resultado (responsive/cascade/navigation) | US-15 | 4h | ⬜ |
| T5-05 | Implementar ValidationReport generator | US-17 | 5h | ⬜ |
| T5-06 | Crear exportador de screenshots diff | US-17 | 3h | ⬜ |
| T5-07 | Optimizar tiempo de validación (<30s total) | - | 5h | ⬜ |
| T5-08 | Tests de diff engine | - | 4h | ⬜ |
| T5-09 | Tests de integración completa | - | 4h | ⬜ |

**Total Estimado:** 40 horas

---

### 📝 Especificación Técnica

#### Multi-Scale Diff Engine
```python
from PIL import Image
import pixelmatch
from io import BytesIO

class DiffEngine:
    """Motor de comparación de screenshots multi-escala."""
    
    def __init__(self):
        self.tight_padding = 20    # ±20px del elemento
        self.local_padding = 100   # ±100px del elemento
        self.threshold = 0.02      # 2% = cambio significativo
    
    def compare(
        self, 
        before: bytes, 
        after: bytes, 
        element_box: Optional[BoundingBox] = None
    ) -> DiffResult:
        """
        Compara screenshots a múltiples escalas.
        
        Returns:
            DiffResult con ratios en cada escala
        """
        before_img = Image.open(BytesIO(before))
        after_img = Image.open(BytesIO(after))
        
        results = {}
        
        # 1. Comparación global (página completa)
        results['global'] = self._compare_images(before_img, after_img)
        
        if element_box:
            # 2. Comparación tight (solo elemento)
            tight_box = element_box.expand(self.tight_padding)
            before_tight = before_img.crop(tight_box.to_tuple())
            after_tight = after_img.crop(tight_box.to_tuple())
            results['tight'] = self._compare_images(before_tight, after_tight)
            
            # 3. Comparación local (contexto)
            local_box = element_box.expand(self.local_padding)
            before_local = before_img.crop(local_box.to_tuple())
            after_local = after_img.crop(local_box.to_tuple())
            results['local'] = self._compare_images(before_local, after_local)
        
        return DiffResult(
            global_diff=results['global'],
            local_diff=results.get('local', 0),
            tight_diff=results.get('tight', 0),
            classification=self._classify(results)
        )
    
    def _compare_images(self, img1: Image, img2: Image) -> float:
        """Compara dos imágenes y retorna ratio de diferencia."""
        # Asegurar mismo tamaño
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
        
        # Convertir a bytes
        img1_bytes = img1.tobytes()
        img2_bytes = img2.tobytes()
        
        # Usar pixelmatch
        diff_pixels = pixelmatch.pixelmatch(
            img1_bytes, img2_bytes,
            img1.width, img1.height,
            threshold=0.1
        )
        
        total_pixels = img1.width * img1.height
        return diff_pixels / total_pixels
    
    def _classify(self, results: Dict[str, float]) -> InteractionClassification:
        """Clasifica el resultado de la interacción."""
        
        tight = results.get('tight', 0)
        local = results.get('local', 0)
        global_ = results['global']
        
        # Decisión basada en escalas
        if tight > self.threshold:
            return InteractionClassification.RESPONSIVE
        
        if global_ > 0.20:
            return InteractionClassification.NAVIGATION
        
        if local > 0.05 and tight < 0.005:
            return InteractionClassification.CASCADE_EFFECT
        
        if tight > 0 and tight < self.threshold:
            return InteractionClassification.WEAK_FEEDBACK
        
        return InteractionClassification.NO_RESPONSE


class InteractionClassification(Enum):
    """Clasificación del resultado de una interacción."""
    RESPONSIVE = "responsive"          # Click funcionó, feedback visible
    NAVIGATION = "navigation"          # Click navega a otra página
    CASCADE_EFFECT = "cascade_effect"  # Cambio en otro lugar de la página
    WEAK_FEEDBACK = "weak_feedback"    # Feedback muy sutil
    NO_RESPONSE = "no_response"        # Sin cambio visual
```

#### Validation Report Generator
```python
@dataclass
class ValidationReport:
    """Reporte completo de validación."""
    
    html_hash: str
    timestamp: datetime
    viewport: Dict[str, int]
    
    # Resultados
    total_elements: int
    responsive_count: int
    failed_count: int
    responsive_ratio: float
    
    # Por elemento
    element_results: List[ElementResult]
    
    # Screenshots
    initial_screenshot: bytes
    diff_screenshots: Dict[str, bytes]  # selector -> diff image
    
    # Errores JS
    js_errors: List[str]
    
    def to_json(self) -> str:
        """Exporta reporte como JSON (sin screenshots)."""
        return json.dumps({
            "html_hash": self.html_hash,
            "timestamp": self.timestamp.isoformat(),
            "viewport": self.viewport,
            "total_elements": self.total_elements,
            "responsive_count": self.responsive_count,
            "failed_count": self.failed_count,
            "responsive_ratio": self.responsive_ratio,
            "element_results": [e.to_dict() for e in self.element_results],
            "js_errors": self.js_errors
        }, indent=2)
    
    def save_screenshots(self, output_dir: Path):
        """Guarda todos los screenshots en un directorio."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initial
        (output_dir / "initial.png").write_bytes(self.initial_screenshot)
        
        # Diffs
        for selector, diff_bytes in self.diff_screenshots.items():
            safe_name = selector.replace(".", "_").replace("#", "_")
            (output_dir / f"diff_{safe_name}.png").write_bytes(diff_bytes)
```

---

### ✅ Definition of Done (Sprint 5)

- [ ] DiffEngine compara screenshots en 3 escalas
- [ ] Clasificación correcta de responsive/navigation/weak_feedback
- [ ] ValidationReport genera JSON estructurado
- [ ] Screenshots diff exportables
- [ ] Tiempo total de validación <30 segundos
- [ ] Tests de integración pasan

---

# 🏃 SPRINT 6: LLM SURGICAL FIXER
## Semanas 12-13

### 📎 Sprint Goal
> **Implementar el LLM fixer que genera patches quirúrgicos, con validación de seguridad para prevenir reparaciones destructivas.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T6-01 | Crear PromptBuilder con contexto mínimo | US-18 | 6h | ⬜ |
| T6-02 | Implementar LLMFixer con output JSON | US-19 | 6h | ⬜ |
| T6-03 | Crear PatchValidator | US-20 | 5h | ⬜ |
| T6-04 | Implementar PatchApplier reversible | US-21 | 4h | ⬜ |
| T6-05 | Crear sistema de retry con diferentes estrategias | US-19 | 4h | ⬜ |
| T6-06 | Integrar screenshots en prompt | US-18 | 4h | ⬜ |
| T6-07 | Tests de PatchValidator | - | 4h | ⬜ |
| T6-08 | Tests de integración LLM | - | 5h | ⬜ |

**Total Estimado:** 38 horas

---

### 📝 Especificación Técnica

#### Prompt Builder
```python
class PromptBuilder:
    """Construye prompts con contexto mínimo necesario."""
    
    SYSTEM_PROMPT = """You are a CSS repair specialist. You receive:
1. An ERROR REPORT with specific element selectors
2. The RELEVANT CSS (only ±10 lines around the issue)
3. BEFORE/AFTER screenshots showing the problem

CRITICAL RULES:
- Output ONLY JSON patches, NEVER full HTML
- Each patch must be < 30 lines
- NEVER remove elements or functionality
- NEVER add display:none or visibility:hidden
- Use !important to override existing styles
- Use concrete colors (#ffffff), NEVER var()

OUTPUT FORMAT:
{
  "analysis": "Brief description of the issue",
  "patches": [
    {
      "type": "css_inject",
      "content": "CSS code here"
    }
  ]
}

PATCH TYPES:
- css_inject: Add CSS at end of <style>
- css_replace: Replace specific CSS rule (include old and new)
- attribute_add: Add attribute to element
"""
    
    def build(
        self, 
        errors: List[ClassifiedError],
        html: str,
        screenshots: Optional[Dict[str, bytes]] = None
    ) -> List[Dict]:
        """
        Construye mensajes para el LLM.
        
        Returns:
            Lista de mensajes en formato OpenAI/Anthropic
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        # Construir contexto de errores
        error_context = self._build_error_context(errors)
        
        # Extraer CSS relevante
        css_context = self._extract_relevant_css(html, errors)
        
        # Mensaje de usuario
        user_content = f"""
## ERRORS TO FIX

{error_context}

## RELEVANT CSS (from the HTML)

```css
{css_context}
```

## INSTRUCTIONS

Generate JSON patches to fix ONLY the errors listed above.
Do NOT modify anything else.
"""
        
        # Agregar screenshots si están disponibles
        if screenshots:
            user_content += "\n\n## SCREENSHOTS\n"
            user_content += "See attached images showing before/after state.\n"
            
            # Agregar imágenes como base64
            for name, img_bytes in screenshots.items():
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Screenshot: {name}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
                            }
                        }
                    ]
                })
        
        messages.append({"role": "user", "content": user_content})
        
        return messages
    
    def _build_error_context(self, errors: List[ClassifiedError]) -> str:
        """Construye descripción de errores."""
        lines = []
        for i, error in enumerate(errors, 1):
            lines.append(f"""
### Error {i}: {error.error_type.value}
- Selector: `{error.selector}`
- Blocking element: `{error.blocking_element or 'N/A'}`
- Computed styles: {json.dumps(error.computed_styles, indent=2)}
""")
        return "\n".join(lines)
    
    def _extract_relevant_css(self, html: str, errors: List[ClassifiedError]) -> str:
        """Extrae solo el CSS relevante a los errores."""
        soup = BeautifulSoup(html, 'html.parser')
        style_tag = soup.find('style')
        
        if not style_tag:
            return "/* No <style> tag found */"
        
        css = style_tag.string or ""
        
        # Extraer selectores de los errores
        selectors = set()
        for error in errors:
            selectors.add(error.selector)
            if error.blocking_element:
                selectors.add(error.blocking_element)
        
        # Filtrar CSS para solo mostrar reglas relevantes
        relevant_rules = []
        for selector in selectors:
            # Buscar reglas que contengan el selector
            pattern = rf"({re.escape(selector)}[^{{]*\{{[^}}]*\}})"
            matches = re.findall(pattern, css)
            relevant_rules.extend(matches)
        
        return "\n\n".join(relevant_rules) if relevant_rules else css[:2000]
```

#### Patch Validator
```python
class PatchValidator:
    """Valida que los patches no sean destructivos."""
    
    FORBIDDEN_CSS = [
        "display: none",
        "display:none",
        "visibility: hidden",
        "visibility:hidden",
        "opacity: 0",
        "opacity:0",
        "pointer-events: none"  # A menos que sea para un bloqueador
    ]
    
    def is_safe(self, original_html: str, patches: List[Patch]) -> ValidationResult:
        """
        Valida que los patches sean seguros de aplicar.
        
        Returns:
            ValidationResult indicando si es seguro y por qué
        """
        # 1. Verificar CSS prohibido
        for patch in patches:
            if patch.type == "css_inject":
                for forbidden in self.FORBIDDEN_CSS:
                    if forbidden in patch.content.lower():
                        return ValidationResult(
                            safe=False,
                            reason=f"Forbidden CSS found: {forbidden}"
                        )
        
        # 2. Aplicar patches y comparar DOM
        patched_html = self._apply_patches(original_html, patches)
        
        original_soup = BeautifulSoup(original_html, 'html.parser')
        patched_soup = BeautifulSoup(patched_html, 'html.parser')
        
        # 3. Contar elementos interactivos
        orig_buttons = len(original_soup.find_all('button'))
        patched_buttons = len(patched_soup.find_all('button'))
        if patched_buttons < orig_buttons:
            return ValidationResult(
                safe=False,
                reason=f"Buttons reduced from {orig_buttons} to {patched_buttons}"
            )
        
        orig_inputs = len(original_soup.find_all('input'))
        patched_inputs = len(patched_soup.find_all('input'))
        if patched_inputs < orig_inputs:
            return ValidationResult(
                safe=False,
                reason=f"Inputs reduced from {orig_inputs} to {patched_inputs}"
            )
        
        # 4. Verificar onclick handlers
        orig_onclick = len(original_soup.find_all(attrs={'onclick': True}))
        patched_onclick = len(patched_soup.find_all(attrs={'onclick': True}))
        if patched_onclick < orig_onclick:
            return ValidationResult(
                safe=False,
                reason=f"Onclick handlers reduced from {orig_onclick} to {patched_onclick}"
            )
        
        return ValidationResult(safe=True, reason="All checks passed")
```

#### LLM Fixer
```python
class LLMFixer:
    """Fixer que usa LLM para generar patches."""
    
    def __init__(self, model: str = "claude-3-opus"):
        self.model = model
        self.prompt_builder = PromptBuilder()
        self.patch_validator = PatchValidator()
        self.max_retries = 3
    
    async def generate_patches(
        self,
        html: str,
        errors: List[ClassifiedError],
        screenshots: Optional[Dict[str, bytes]] = None
    ) -> List[Patch]:
        """
        Genera patches usando LLM.
        
        Returns:
            Lista de patches seguros para aplicar
        """
        messages = self.prompt_builder.build(errors, html, screenshots)
        
        for attempt in range(self.max_retries):
            # Llamar al LLM
            response = await self._call_llm(messages)
            
            # Parsear respuesta
            try:
                patches = self._parse_response(response)
            except json.JSONDecodeError:
                # Retry con instrucción más explícita
                messages.append({
                    "role": "user",
                    "content": "Your response was not valid JSON. Please output ONLY JSON."
                })
                continue
            
            # Validar patches
            validation = self.patch_validator.is_safe(html, patches)
            
            if validation.safe:
                return patches
            else:
                # Retry indicando el problema
                messages.append({
                    "role": "user",
                    "content": f"Your patches were rejected: {validation.reason}. Try again without removing elements."
                })
        
        # Si todos los intentos fallaron, retornar lista vacía
        return []
```

---

### ✅ Definition of Done (Sprint 6)

- [ ] PromptBuilder genera prompts con contexto mínimo
- [ ] LLMFixer genera patches JSON válidos
- [ ] PatchValidator bloquea 100% de patches destructivos
- [ ] Sistema de retry funciona con diferentes estrategias
- [ ] Tests muestran 0% de patches destructivos aceptados
- [ ] Integración con screenshots funciona

---

# 🏃 SPRINT 7: ORQUESTADOR Y ROLLBACK
## Semanas 14-15

### 📎 Sprint Goal
> **Crear el orquestador que coordina todo el pipeline con historial para rollback automático y retorno del mejor resultado.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T7-01 | Implementar Orchestrator base | US-22 | 6h | ⬜ |
| T7-02 | Crear History manager para rollback | US-23 | 4h | ⬜ |
| T7-03 | Implementar DecisionEngine (rules vs LLM) | US-24 | 5h | ⬜ |
| T7-04 | Crear BestResultTracker | US-25 | 3h | ⬜ |
| T7-05 | Implementar timeout global | US-22 | 3h | ⬜ |
| T7-06 | Crear métricas y logging detallado | - | 4h | ⬜ |
| T7-07 | Tests de integración end-to-end | - | 8h | ⬜ |
| T7-08 | Optimización de performance | - | 5h | ⬜ |

**Total Estimado:** 38 horas

---

### 📝 Especificación Técnica

#### Orchestrator
```python
class Orchestrator:
    """
    Orquestador principal del pipeline de reparación.
    
    Flujo:
    1. Clasificar errores
    2. Aplicar reglas determinísticas
    3. Validar
    4. Si falla: LLM surgical fix
    5. Validar de nuevo
    6. Rollback si empeoró
    7. Retornar mejor resultado
    """
    
    def __init__(self):
        self.classifier = ErrorClassificationPipeline()
        self.deterministic_fixer = DeterministicFixer()
        self.llm_fixer = LLMFixer()
        self.sandbox = Sandbox()
        self.history = HistoryManager()
        
        # Configuración
        self.max_llm_attempts = 3
        self.global_timeout_seconds = 120
    
    async def fix(self, html: str) -> FixResult:
        """
        Ejecuta el pipeline completo de reparación.
        
        Returns:
            FixResult con el mejor HTML encontrado
        """
        start_time = time.time()
        
        # Inicializar tracking
        self.history.push(html, score=0, label="original")
        best_html = html
        best_score = 0
        
        try:
            # FASE 1: Clasificar errores
            logger.info("Phase 1: Classifying errors")
            errors = await self.classifier.classify(html)
            
            if not errors:
                logger.info("No errors found, returning original")
                return FixResult(html=html, score=1.0, phases_completed=["classify"])
            
            logger.info(f"Found {len(errors)} errors: {[e.error_type.value for e in errors]}")
            
            # FASE 2: Fix determinístico
            logger.info("Phase 2: Applying deterministic fixes")
            rule_fixable = [e for e in errors if not e.requires_llm]
            
            if rule_fixable:
                fixed_html = self.deterministic_fixer.fix(html, rule_fixable)
                self.history.push(fixed_html, score=None, label="deterministic_fix")
                
                # FASE 3: Validar
                logger.info("Phase 3: Validating deterministic fix")
                result = await self.sandbox.validate(fixed_html)
                score = result.responsive_ratio
                
                self.history.update_score(score)
                
                if score > best_score:
                    best_score = score
                    best_html = fixed_html
                
                if result.all_passed:
                    logger.info("All elements responsive after deterministic fix")
                    return FixResult(
                        html=fixed_html, 
                        score=1.0, 
                        phases_completed=["classify", "deterministic", "validate"]
                    )
                
                # Actualizar errores restantes
                errors = await self.classifier.classify(fixed_html)
            
            # FASE 4: LLM Surgical Fix (si necesario)
            llm_required = [e for e in errors if e.requires_llm] or errors
            
            if llm_required and self._time_remaining(start_time) > 30:
                logger.info(f"Phase 4: LLM surgical fix for {len(llm_required)} errors")
                
                current_html = best_html
                
                for attempt in range(self.max_llm_attempts):
                    if self._time_remaining(start_time) < 10:
                        logger.warning("Timeout approaching, stopping LLM attempts")
                        break
                    
                    logger.info(f"LLM attempt {attempt + 1}/{self.max_llm_attempts}")
                    
                    # Generar patches
                    patches = await self.llm_fixer.generate_patches(
                        current_html, 
                        llm_required
                    )
                    
                    if not patches:
                        logger.warning("LLM returned no patches")
                        continue
                    
                    # Aplicar patches
                    candidate = self._apply_patches(current_html, patches)
                    self.history.push(candidate, score=None, label=f"llm_fix_{attempt}")
                    
                    # Validar
                    result = await self.sandbox.validate(candidate)
                    score = result.responsive_ratio
                    
                    self.history.update_score(score)
                    
                    if score > best_score:
                        logger.info(f"LLM fix improved score: {best_score:.2f} -> {score:.2f}")
                        best_score = score
                        best_html = candidate
                        current_html = candidate
                        
                        if result.all_passed:
                            return FixResult(
                                html=candidate,
                                score=1.0,
                                phases_completed=["classify", "deterministic", "validate", "llm_fix"]
                            )
                        
                        # Reclasificar errores restantes
                        llm_required = [
                            e for e in await self.classifier.classify(candidate)
                            if not result.is_element_responsive(e.selector)
                        ]
                    else:
                        logger.warning(f"LLM fix did not improve: {score:.2f} <= {best_score:.2f}")
                        # Rollback implícito: no actualizamos current_html
            
            # Retornar mejor resultado
            return FixResult(
                html=best_html,
                score=best_score,
                phases_completed=self.history.get_phases()
            )
            
        except asyncio.TimeoutError:
            logger.error("Global timeout reached")
            return FixResult(
                html=best_html,
                score=best_score,
                phases_completed=self.history.get_phases(),
                error="Timeout"
            )
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return FixResult(
                html=best_html,
                score=best_score,
                phases_completed=self.history.get_phases(),
                error=str(e)
            )
    
    def _time_remaining(self, start_time: float) -> float:
        """Calcula tiempo restante del timeout global."""
        elapsed = time.time() - start_time
        return self.global_timeout_seconds - elapsed


class HistoryManager:
    """Gestiona historial de versiones para rollback."""
    
    def __init__(self):
        self.history: List[HistoryEntry] = []
    
    def push(self, html: str, score: Optional[float], label: str):
        """Agrega una versión al historial."""
        self.history.append(HistoryEntry(
            html=html,
            score=score,
            label=label,
            timestamp=datetime.now()
        ))
    
    def update_score(self, score: float):
        """Actualiza el score de la última entrada."""
        if self.history:
            self.history[-1].score = score
    
    def get_best(self) -> HistoryEntry:
        """Obtiene la mejor versión del historial."""
        scored = [h for h in self.history if h.score is not None]
        if not scored:
            return self.history[0]
        return max(scored, key=lambda h: h.score)
    
    def rollback(self, steps: int = 1) -> str:
        """Retorna el HTML de N pasos atrás."""
        index = max(0, len(self.history) - steps - 1)
        return self.history[index].html
```

---

### ✅ Definition of Done (Sprint 7)

- [ ] Orchestrator ejecuta pipeline completo
- [ ] HistoryManager permite rollback a cualquier versión
- [ ] DecisionEngine decide correctamente rules vs LLM
- [ ] BestResultTracker siempre retorna la mejor versión
- [ ] Timeout global funciona
- [ ] Tests end-to-end pasan con 90%+ success rate
- [ ] Tiempo total <2 minutos para casos complejos

---

# 🏃 SPRINT 8: TEST SUITE Y DOCUMENTACIÓN
## Semanas 16-17 (Final)

### 📎 Sprint Goal
> **Completar la suite de tests, documentación, y configurar CI/CD para garantizar calidad continua.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T8-01 | Crear 10 fixtures adicionales para edge cases | US-26 | 6h | ⬜ |
| T8-02 | Implementar test parametrizados para todas las reglas | US-27 | 5h | ⬜ |
| T8-03 | Crear dashboard de métricas | US-28 | 4h | ⬜ |
| T8-04 | Configurar GitHub Actions CI | US-29 | 4h | ⬜ |
| T8-05 | Escribir documentación de API | - | 5h | ⬜ |
| T8-06 | Crear guía de contribución | - | 3h | ⬜ |
| T8-07 | Performance benchmarking | - | 4h | ⬜ |
| T8-08 | Tests de regresión automatizados | - | 5h | ⬜ |
| T8-09 | Release v1.0.0 | - | 4h | ⬜ |

**Total Estimado:** 40 horas

---

### 📝 Configuración CI/CD

```yaml
# .github/workflows/test.yml
name: HTML Fixer Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          playwright install chromium
      
      - name: Run unit tests
        run: pytest tests/unit -v --cov=html_fixer
      
      - name: Run integration tests
        run: pytest tests/integration -v
      
      - name: Run golden set tests
        run: pytest tests/golden -v --tb=short
      
      - name: Check coverage
        run: |
          coverage report --fail-under=80
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  benchmark:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run benchmarks
        run: |
          pytest tests/benchmarks --benchmark-only --benchmark-json=benchmark.json
      
      - name: Store benchmark result
        uses: benchmark-action/github-action-benchmark@v1
        with:
          tool: 'pytest'
          output-file-path: benchmark.json
```

---

### 📊 Métricas Finales Esperadas

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         MÉTRICAS DE ÉXITO v1.0                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   MÉTRICA                        │ BASELINE │ ACTUAL  │ TARGET            │
│   ───────────────────────────────┼──────────┼─────────┼──────────         │
│   Responsive Ratio (fixtures)    │   0%     │   ??%   │   ≥90%            │
│   Fix Time (avg)                 │  >300s   │   ??s   │   <30s            │
│   Fix Time (p95)                 │   N/A    │   ??s   │   <120s           │
│   LLM Calls per fix (avg)        │   2+     │   ??    │   ≤1              │
│   Element Preservation           │   57%    │   ??%   │   100%            │
│   Deterministic Fix Rate         │   0%     │   ??%   │   ≥70%            │
│   Test Coverage                  │   0%     │   ??%   │   ≥80%            │
│   Golden Set Pass Rate           │   N/A    │   ??%   │   ≥90%            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### ✅ Definition of Done (Sprint 8 / Proyecto)

- [ ] 20+ fixtures cubriendo todos los tipos de layout
- [ ] Tests parametrizados para cada regla
- [ ] Dashboard de métricas funcional
- [ ] CI/CD ejecuta en cada PR
- [ ] Documentación completa de API
- [ ] Benchmarks automatizados
- [ ] 90%+ pass rate en golden set
- [ ] Release v1.0.0 publicado

---

# 📈 RESUMEN EJECUTIVO

## Timeline Visual Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ROADMAP COMPLETO                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Sem   1    2    3    4    5    6    7    8    9   10   11   12   13   14   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S0    ██   │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  Fund. │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S1    │    ████████  │    │    │    │    │    │    │    │    │    │    │   │
│  Class.│    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S2    │    │    │    ████████  │    │    │    │    │    │    │    │    │   │
│  Diag. │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S3    │    │    │    │    │    ████████  │    │    │    │    │    │    │   │
│  Rules │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S4    │    │    │    │    │    │    │    ████████  │    │    │    │    │   │
│  Sand. │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S5    │    │    │    │    │    │    │    │    │    ████████  │    │    │   │
│  Diff  │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S6    │    │    │    │    │    │    │    │    │    │    │    ████████  │   │
│  LLM   │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S7    │    │    │    │    │    │    │    │    │    │    │    │    ████████ │
│  Orch. │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  S8    │    │    │    │    │    │    │    │    │    │    │    │    │    ████│
│  Tests │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│        │    │    │    │    │    │    │    │    │    │    │    │    │    │   │
│  ──────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴───│
│                                                                             │
│  MILESTONES:                                                                │
│  M1 (Sem 4):  Clasificador completo                                        │
│  M2 (Sem 8):  70% fixes sin LLM ✓                                          │
│  M3 (Sem 12): Pipeline completo funcional                                  │
│  M4 (Sem 14): 90%+ golden set pass rate                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Velocity Esperada

| Sprint | Story Points | Capacidad | Confianza |
|--------|-------------|-----------|-----------|
| S0     | 8           | 100%      | 🟢 Alta |
| S1     | 21          | 100%      | 🟢 Alta |
| S2     | 21          | 100%      | 🟢 Alta |
| S3     | 19          | 100%      | 🟢 Alta |
| S4     | 21          | 100%      | 🟡 Media |
| S5     | 21          | 100%      | 🟡 Media |
| S6     | 19          | 100%      | 🟡 Media |
| S7     | 19          | 100%      | 🟡 Media |
| S8     | 21          | 100%      | 🟢 Alta |

**Total: 170 Story Points en 17 semanas**

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Playwright inestable en CI | Media | Alto | Docker con browser pre-instalado |
| LLM genera patches inválidos | Alta | Medio | PatchValidator + retries |
| Fixtures no representativos | Media | Alto | Agregar fixtures de producción real |
| Performance timeout | Media | Medio | Paralelización + caching |
| CSS edge cases no cubiertos | Alta | Medio | Test suite extensivo |

---

¿Aprobamos este plan y comenzamos? 🚀