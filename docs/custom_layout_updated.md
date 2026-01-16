# 📋 SCRUM PLAN COMPLETO (v2.0 - Tailwind Edition)
## HTML Validator & Fixer - "Chirurgical Fixer"

**Proyecto:** HTML Fixer Infalible  
**Duración Total:** 12 semanas (6 sprints de 2 semanas)  
**Equipo:** 1 Developer + 1 AI Assistant (Scrum Master)  
**Metodología:** Scrum con sprints de 2 semanas  

---

## 🆕 CONTEXTO IMPORTANTE (v2.0)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARQUITECTURA DEL SISTEMA                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Este Validator/Fixer es parte de un sistema más grande:                  │
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │   PROMPT     │ →  │  LLM GENERA  │ →  │  VALIDATOR   │                │
│   │  del usuario │    │  HTML+Tailwind│    │  + FIXER     │                │
│   └──────────────┘    └──────────────┘    └──────────────┘                │
│                                                                             │
│   IMPLICACIONES:                                                            │
│   • El HTML siempre usa Tailwind CSS (no CSS libre)                        │
│   • Los fixes deben inyectar clases Tailwind, no CSS raw                   │
│   • Podemos PREVENIR errores mejorando el prompt de generación             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 📦 PRODUCT BACKLOG (Priorizado)

## Épicas

| ID | Épica | Prioridad | Business Value |
|----|-------|-----------|----------------|
| E0 | **🆕 Prevención de Errores (Prompt)** | 🔴 Crítica | Reduce 50% errores |
| E1 | Análisis Estático de HTML/CSS | 🔴 Crítica | Fundación de todo el sistema |
| E2 | Fixer Determinístico (Sin LLM) | 🔴 Crítica | 70% de fixes automáticos |
| E3 | Sandbox de Validación Visual | 🔴 Crítica | Verificación de reparaciones |
| E4 | LLM Surgical Fixer | 🟡 Alta | Fixes complejos restantes |
| E5 | Orquestador y Rollback | 🟡 Alta | Coordinación del pipeline |
| E6 | Test Suite y CI/CD | 🟢 Media | Calidad y mantenibilidad |

---

## User Stories Completas

### 🆕 Épica 0: Prevención de Errores (E0)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-00 | Como sistema, necesito un prompt optimizado que prevenga errores CSS comunes | 5 | 🔴 |
| US-00b | Como sistema, necesito reglas Tailwind obligatorias para overlays y modales | 3 | 🔴 |

### Épica 1: Análisis Estático (E1)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-01 | Como sistema, necesito parsear HTML para extraer el DOM tree | 5 | 🔴 |
| US-02 | Como sistema, necesito analizar clases Tailwind de cada elemento | 8 | 🔴 |
| US-03 | Como sistema, necesito mapear event handlers (onclick, etc.) | 5 | 🔴 |
| US-04 | Como sistema, necesito construir jerarquía de z-index (z-10, z-20, etc.) | 5 | 🔴 |
| US-05 | Como sistema, necesito detectar elementos con pointer-events bloqueados | 5 | 🔴 |
| US-06 | Como sistema, necesito clasificar errores en categorías predefinidas | 8 | 🔴 |

### Épica 2: Fixer Determinístico (E2)

| ID | User Story | Puntos | Prioridad |
|----|------------|--------|-----------|
| US-07 | Como sistema, necesito regla para arreglar conflictos de z-index con clases Tailwind | 3 | 🔴 |
| US-08 | Como sistema, necesito regla para arreglar pointer-events con clases Tailwind | 5 | 🔴 |
| US-09 | Como sistema, necesito regla para restaurar visibilidad con clases Tailwind | 3 | 🔴 |
| US-10 | Como sistema, necesito regla para arreglar transforms 3D | 5 | 🔴 |
| US-11 | Como sistema, necesito regla para amplificar feedback visual con clases Tailwind | 3 | 🔴 |
| US-12 | Como sistema, necesito inyectar clases Tailwind sin modificar estructura | 5 | 🔴 |

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
| US-19 | Como sistema, necesito que LLM genere patches con clases Tailwind | 8 | 🟡 |
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
| US-26 | Como developer, necesito fixtures HTML (Tailwind) para cada tipo de layout | 8 | 🟢 |
| US-27 | Como developer, necesito tests automatizados para cada regla | 5 | 🟢 |
| US-28 | Como developer, necesito métricas de success rate por tipo de error | 5 | 🟢 |
| US-29 | Como developer, necesito CI/CD que ejecute tests en cada PR | 5 | 🟢 |

---

# 🏃 SPRINT 0: FUNDACIÓN
## Semana 1

### 📎 Sprint Goal
> **Establecer la estructura del proyecto, crear el prompt de generación optimizado, y crear los primeros fixtures Tailwind de prueba.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Estimación | Responsable | Estado |
|---------|-------|------------|-------------|--------|
| T0-01 | Crear estructura de carpetas del proyecto | 2h | Dev | ⬜ |
| T0-02 | Configurar pyproject.toml con dependencias | 1h | Dev | ⬜ |
| T0-03 | Instalar y configurar Playwright | 2h | Dev | ⬜ |
| T0-04 | Configurar pytest con plugins necesarios | 1h | Dev | ⬜ |
| T0-05 | Crear 5 fixtures HTML Tailwind de trivia | 4h | Dev | ⬜ |
| T0-06 | Crear 3 fixtures HTML Tailwind de dashboard | 3h | Dev | ⬜ |
| T0-07 | Crear 2 fixtures HTML Tailwind de modales | 2h | Dev | ⬜ |
| T0-08 | Documentar contratos de datos (dataclasses) | 3h | Dev | ⬜ |
| T0-09 | Crear README con arquitectura | 2h | Dev | ⬜ |
| T0-10 | Setup logging estructurado | 1h | Dev | ⬜ |
| **T0-11** | **🆕 Crear generation_prompt.md con reglas Tailwind** | **3h** | Dev | ⬜ |
| **T0-12** | **🆕 Crear tailwind_rules.py con clases permitidas/requeridas** | **2h** | Dev | ⬜ |

**Total Estimado:** 26 horas (~4 días de trabajo)

---

### 🆕 T0-11: Generation Prompt (Prevención de Errores)

```markdown
# generation_prompt.md
# Prompt para el LLM que GENERA los layouts

## REGLAS OBLIGATORIAS DE TAILWIND

### 1. Z-Index (SIEMPRE explícito en overlays)
- Contenedor base: `z-0`
- Contenido normal: `z-10`
- Dropdowns/tooltips: `z-20`
- Modales backdrop: `z-40`
- Modales content: `z-50`
- Toasts/alerts: `z-[100]`

### 2. Pointer Events (SIEMPRE en overlays)
```html
<!-- CORRECTO: Overlay que NO bloquea -->
<div class="absolute inset-0 pointer-events-none">
  <button class="pointer-events-auto">Click me</button>
</div>

<!-- INCORRECTO: Overlay sin pointer-events -->
<div class="absolute inset-0">
  <button>Click me</button>  <!-- BLOQUEADO! -->
</div>
```

### 3. Transforms 3D (SIEMPRE con estas clases)
```html
<!-- CORRECTO: Card flip -->
<div class="[perspective:1000px]">
  <div class="relative [transform-style:preserve-3d]">
    <div class="absolute inset-0 [backface-visibility:hidden]">Front</div>
    <div class="absolute inset-0 [backface-visibility:hidden] [transform:rotateY(180deg)]">Back</div>
  </div>
</div>
```

### 4. Elementos Interactivos (SIEMPRE)
- Botones: `relative z-10` mínimo
- Inputs: `relative z-10` mínimo
- Links clickeables: `relative z-10` mínimo

### 5. Feedback Visual (SIEMPRE visible)
```html
<!-- CORRECTO: Feedback obvio -->
<button class="bg-blue-500 hover:bg-blue-700 active:bg-blue-900 
               active:scale-95 transition-all">
  Click
</button>

<!-- INCORRECTO: Feedback sutil -->
<button class="bg-blue-500 hover:bg-blue-600">
  Click
</button>
```

## PATRONES PROHIBIDOS

❌ `absolute inset-0` sin `pointer-events-none`
❌ `z-auto` en elementos posicionados
❌ Transforms sin `[transform-style:preserve-3d]` en parent
❌ Cards 3D sin `[backface-visibility:hidden]`
❌ Overlays sin z-index explícito
```

---

### 🆕 T0-12: Tailwind Rules (Para el Fixer)

```python
# tailwind_rules.py
"""Clases Tailwind para fixes automáticos."""

class TailwindFixes:
    """Mapeo de errores a clases Tailwind."""
    
    # Z-Index fixes
    ZINDEX_LOW = "z-10"
    ZINDEX_MED = "z-20"
    ZINDEX_HIGH = "z-50"
    ZINDEX_MODAL = "z-[100]"
    ZINDEX_MAX = "z-[9999]"
    
    # Pointer events fixes
    POINTER_NONE = "pointer-events-none"
    POINTER_AUTO = "pointer-events-auto"
    
    # Position fixes
    POSITION_RELATIVE = "relative"
    POSITION_ABSOLUTE = "absolute"
    
    # Visibility fixes
    VISIBLE = "visible"
    OPACITY_100 = "opacity-100"
    BLOCK = "block"
    
    # Transform fixes (custom Tailwind)
    PRESERVE_3D = "[transform-style:preserve-3d]"
    BACKFACE_HIDDEN = "[backface-visibility:hidden]"
    BACKFACE_VISIBLE = "[backface-visibility:visible]"
    PERSPECTIVE = "[perspective:1000px]"
    
    # Feedback amplification
    FEEDBACK_ACTIVE = "active:scale-95 active:brightness-75"
    FEEDBACK_RING = "focus:ring-4 focus:ring-blue-500"
    TRANSITION = "transition-all duration-150"

    @classmethod
    def get_zindex_fix(cls, current_z: int) -> str:
        """Retorna clase z-index superior al actual."""
        if current_z < 10:
            return cls.ZINDEX_MED
        elif current_z < 50:
            return cls.ZINDEX_HIGH
        else:
            return cls.ZINDEX_MAX
    
    @classmethod
    def get_pointer_fix(cls, is_interactive: bool) -> str:
        """Retorna clase pointer-events apropiada."""
        return cls.POINTER_AUTO if is_interactive else cls.POINTER_NONE
```

---

### 📁 Entregables

```
custom_layout/
├
├
├── prompts/
│   └── generation_prompt.md          # 🆕 Prompt para LLM generador
├── src/
│   └── html_fixer/
│       ├── __init__.py
│       ├── tailwind_rules.py         # 🆕 Clases Tailwind para fixes
│       ├── contracts/
│       │   ├── __init__.py
│       │   ├── errors.py
│       │   ├── patches.py            # 🔄 Ahora con TailwindPatch
│       │   └── validation.py
│       ├── analyzers/
│       │   ├── __init__.py
│       │   └── tailwind_analyzer.py  # 🆕 Analiza clases Tailwind
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
    │   │   ├── flashcard_3d_broken.html      # Tailwind
    │   │   ├── flashcard_3d_expected.html
    │   │   ├── multiple_choice_broken.html
    │   │   ├── quiz_modal_broken.html
    │   │   └── sequential_broken.html
    │   ├── dashboard/
    │   │   ├── sidebar_broken.html           # Tailwind
    │   │   ├── card_grid_broken.html
    │   │   └── data_table_broken.html
    │   └── modals/
    │       ├── nested_broken.html            # Tailwind
    │       └── form_modal_broken.html
    └── unit/
        └── __init__.py
```

---

### ✅ Definition of Done (Sprint 0)

- [ ] `pytest` ejecuta sin errores
- [ ] Playwright puede abrir un fixture y tomar screenshot
- [ ] 10 fixtures HTML **con Tailwind** creados
- [ ] Cada fixture tiene comentarios indicando qué está "roto"
- [ ] **🆕 generation_prompt.md documenta reglas para el LLM generador**
- [ ] **🆕 tailwind_rules.py tiene todas las clases de fix**
- [ ] README documenta la arquitectura

---

# 🏃 SPRINT 1: CLASIFICADOR DE ERRORES (Parte 1)
## Semanas 2-3

### 📎 Sprint Goal
> **Construir el analizador de DOM y clases Tailwind que detecta y clasifica errores con precisión.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T1-01 | Implementar DOMParser con BeautifulSoup | US-01 | 4h | ⬜ |
| T1-02 | Implementar extractor de elementos interactivos | US-01 | 3h | ⬜ |
| T1-03 | **🆕 Crear TailwindAnalyzer (extrae clases Tailwind)** | US-02 | 6h | ⬜ |
| T1-04 | **🆕 Implementar detector de clases faltantes (z-*, pointer-*)** | US-02 | 4h | ⬜ |
| T1-05 | Crear EventMapper para onclick/handlers | US-03 | 4h | ⬜ |
| T1-06 | **🆕 Implementar ZIndexHierarchyBuilder (z-10, z-20, etc.)** | US-04 | 5h | ⬜ |
| T1-07 | Crear detector de pointer-events bloqueados | US-05 | 6h | ⬜ |
| T1-08 | Implementar elementFromPoint analysis | US-05 | 4h | ⬜ |
| T1-09 | Tests unitarios para cada analizador | - | 4h | ⬜ |

**Total Estimado:** 40 horas (~2 semanas)

---

### 🆕 TailwindAnalyzer

```python
# tailwind_analyzer.py
"""Analiza clases Tailwind en elementos HTML."""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

@dataclass
class TailwindInfo:
    """Información de clases Tailwind de un elemento."""
    all_classes: Set[str]
    z_index: Optional[int]          # None si no tiene z-*
    has_pointer_none: bool
    has_pointer_auto: bool
    has_relative: bool
    has_absolute: bool
    has_fixed: bool
    has_transform: bool
    has_preserve_3d: bool
    has_backface_hidden: bool
    missing_recommended: List[str]  # Clases que debería tener

class TailwindAnalyzer:
    """Analiza y extrae información de clases Tailwind."""
    
    # Regex para extraer z-index
    Z_INDEX_PATTERN = re.compile(r'z-(\d+|auto|\[\d+\])')
    
    # Clases que elementos interactivos DEBERÍAN tener
    INTERACTIVE_RECOMMENDED = {"relative", "z-10"}
    
    # Clases que overlays DEBERÍAN tener
    OVERLAY_RECOMMENDED = {"pointer-events-none", "z-40"}
    
    def analyze_element(self, element) -> TailwindInfo:
        """Analiza un elemento y extrae info de Tailwind."""
        classes = set(element.get("class", []))
        
        # Extraer z-index
        z_index = self._extract_z_index(classes)
        
        # Detectar clases importantes
        info = TailwindInfo(
            all_classes=classes,
            z_index=z_index,
            has_pointer_none="pointer-events-none" in classes,
            has_pointer_auto="pointer-events-auto" in classes,
            has_relative="relative" in classes,
            has_absolute="absolute" in classes,
            has_fixed="fixed" in classes,
            has_transform=any("transform" in c for c in classes),
            has_preserve_3d="[transform-style:preserve-3d]" in classes,
            has_backface_hidden="[backface-visibility:hidden]" in classes,
            missing_recommended=[]
        )
        
        # Detectar clases faltantes
        if self._is_interactive(element):
            missing = self.INTERACTIVE_RECOMMENDED - classes
            info.missing_recommended.extend(missing)
        
        if self._is_overlay(element, info):
            missing = self.OVERLAY_RECOMMENDED - classes
            info.missing_recommended.extend(missing)
        
        return info
    
    def _extract_z_index(self, classes: Set[str]) -> Optional[int]:
        """Extrae valor de z-index de clases Tailwind."""
        for cls in classes:
            match = self.Z_INDEX_PATTERN.match(cls)
            if match:
                value = match.group(1)
                if value == "auto":
                    return None
                elif value.startswith("["):
                    return int(value[1:-1])
                else:
                    return int(value)
        return None
    
    def _is_interactive(self, element) -> bool:
        """Determina si un elemento es interactivo."""
        tag = element.name.lower()
        has_onclick = element.get("onclick") is not None
        return tag in ("button", "a", "input", "select") or has_onclick
    
    def _is_overlay(self, element, info: TailwindInfo) -> bool:
        """Determina si un elemento es un overlay."""
        has_inset = "inset-0" in info.all_classes
        return info.has_absolute and has_inset
```

---

### 🆕 Clasificador con Tailwind Context

```python
@dataclass
class ClassifiedError:
    """Error clasificado con información Tailwind."""
    
    error_type: ErrorType
    selector: str
    element_tag: str
    
    # Contexto del error
    blocking_element: Optional[str]
    tailwind_info: TailwindInfo      # 🆕 Info de clases Tailwind
    bounding_box: Dict[str, float]
    
    # Para el fixer - 🆕 Ahora con clases Tailwind
    suggested_classes: List[str]     # 🆕 Clases a agregar
    classes_to_remove: List[str]     # 🆕 Clases a quitar
    requires_llm: bool
    
    # Metadata
    confidence: float
    line_number: Optional[int]
```

---

# 🏃 SPRINT 2: CLASIFICADOR DE ERRORES (Parte 2) + PLAYWRIGHT DIAGNOSTICS
## Semanas 4-5

*(Sin cambios mayores - solo ajustar para que devuelva TailwindInfo)*

---

# 🏃 SPRINT 3: FIXER DETERMINÍSTICO (Parte 1)
## Semanas 6-7

### 📎 Sprint Goal
> **Implementar las reglas de reparación automática usando clases Tailwind - sin LLM.**

---

### 📋 Sprint Backlog

| Task ID | Tarea | Story | Estimación | Estado |
|---------|-------|-------|------------|--------|
| T3-01 | Crear RuleEngine base class | US-07 | 3h | ⬜ |
| T3-02 | **🔄 Implementar ZIndexFixRule (agrega z-50, etc.)** | US-07 | 4h | ⬜ |
| T3-03 | **🔄 Implementar PointerEventsFixRule (agrega pointer-events-auto)** | US-08 | 5h | ⬜ |
| T3-04 | **🔄 Implementar VisibilityRestoreRule (agrega opacity-100, etc.)** | US-09 | 3h | ⬜ |
| T3-05 | **🆕 Crear TailwindInjector (agrega clases, no CSS)** | US-12 | 4h | ⬜ |
| T3-06 | Implementar regla de passthrough selectivo | US-08 | 4h | ⬜ |
| T3-07 | Tests para ZIndexFixRule | - | 3h | ⬜ |
| T3-08 | Tests para PointerEventsFixRule | - | 4h | ⬜ |
| T3-09 | Tests para VisibilityRestoreRule | - | 3h | ⬜ |
| T3-10 | Integration test: fix + validate cycle | - | 5h | ⬜ |

**Total Estimado:** 38 horas

---

### 🆕 Reglas con Tailwind (CAMBIO PRINCIPAL)

```python
# Antes (CSS raw):
class ZIndexFixRule(FixRule):
    def generate_fix(self, error: ClassifiedError) -> CSSPatch:
        return CSSPatch(
            type="css_inject",
            content=f"{error.selector} {{ z-index: 1000 !important; }}"
        )

# 🆕 Después (Clases Tailwind):
class ZIndexFixRule(FixRule):
    """Arregla conflictos de z-index agregando clases Tailwind."""
    
    handles = [ErrorType.ZINDEX_CONFLICT, ErrorType.ZINDEX_MISSING]
    priority = 10
    
    def generate_fix(self, error: ClassifiedError) -> TailwindPatch:
        current_z = error.tailwind_info.z_index or 0
        new_z_class = TailwindFixes.get_zindex_fix(current_z)
        
        return TailwindPatch(
            selector=error.selector,
            add_classes=[new_z_class, "relative"],
            remove_classes=self._get_old_z_classes(error.tailwind_info)
        )
    
    def _get_old_z_classes(self, info: TailwindInfo) -> List[str]:
        """Obtiene clases z-* a remover."""
        return [c for c in info.all_classes if c.startswith("z-")]


class PointerEventsFixRule(FixRule):
    """Arregla elementos bloqueados con clases Tailwind."""
    
    handles = [ErrorType.POINTER_BLOCKED, ErrorType.POINTER_INTERCEPTED]
    priority = 20
    
    def generate_fix(self, error: ClassifiedError) -> List[TailwindPatch]:
        patches = []
        
        # 1. Agregar pointer-events-none al bloqueador
        if error.blocking_element:
            patches.append(TailwindPatch(
                selector=error.blocking_element,
                add_classes=["pointer-events-none"]
            ))
        
        # 2. Agregar pointer-events-auto al target
        patches.append(TailwindPatch(
            selector=error.selector,
            add_classes=["pointer-events-auto", "relative", "z-50"]
        ))
        
        return patches


class VisibilityRestoreRule(FixRule):
    """Restaura visibilidad con clases Tailwind."""
    
    handles = [
        ErrorType.INVISIBLE_OPACITY,
        ErrorType.INVISIBLE_DISPLAY,
        ErrorType.INVISIBLE_VISIBILITY
    ]
    priority = 5
    
    FIXES = {
        ErrorType.INVISIBLE_OPACITY: (["opacity-100"], ["opacity-0"]),
        ErrorType.INVISIBLE_DISPLAY: (["block"], ["hidden"]),
        ErrorType.INVISIBLE_VISIBILITY: (["visible"], ["invisible"]),
    }
    
    def generate_fix(self, error: ClassifiedError) -> TailwindPatch:
        add_classes, remove_classes = self.FIXES[error.error_type]
        
        return TailwindPatch(
            selector=error.selector,
            add_classes=add_classes,
            remove_classes=remove_classes
        )
```

---

### 🆕 TailwindPatch Dataclass

```python
@dataclass
class TailwindPatch:
    """Patch que modifica clases Tailwind de un elemento."""
    
    selector: str
    add_classes: List[str] = field(default_factory=list)
    remove_classes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "selector": self.selector,
            "add": self.add_classes,
            "remove": self.remove_classes
        }
    
    def describe(self) -> str:
        parts = []
        if self.add_classes:
            parts.append(f"Add: {' '.join(self.add_classes)}")
        if self.remove_classes:
            parts.append(f"Remove: {' '.join(self.remove_classes)}")
        return f"{self.selector} → {', '.join(parts)}"
```

---

### 🆕 TailwindInjector (Reemplaza CSSInjector)

```python
class TailwindInjector:
    """Inyecta clases Tailwind en elementos HTML."""
    
    def apply(self, html: str, patches: List[TailwindPatch]) -> str:
        """
        Aplica patches de Tailwind al HTML.
        
        A diferencia del CSSInjector, este modifica el atributo class
        de los elementos, no inyecta CSS nuevo.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        for patch in patches:
            elements = soup.select(patch.selector)
            
            for element in elements:
                current_classes = set(element.get("class", []))
                
                # Remover clases
                current_classes -= set(patch.remove_classes)
                
                # Agregar clases
                current_classes |= set(patch.add_classes)
                
                # Actualizar elemento
                element["class"] = list(current_classes)
        
        return str(soup)
    
    def preview(self, patches: List[TailwindPatch]) -> str:
        """Genera preview legible de los cambios."""
        lines = ["Tailwind Patches:"]
        for i, patch in enumerate(patches, 1):
            lines.append(f"  {i}. {patch.describe()}")
        return "\n".join(lines)
```

---

# 🏃 SPRINT 4: FIXER DETERMINÍSTICO (Parte 2) + SANDBOX BÁSICO
## Semanas 8-9

### 🔄 Cambios en Reglas de Transform

```python
class Transform3DFixRule(FixRule):
    """Arregla elementos ocultos por transforms 3D con Tailwind."""
    
    handles = [ErrorType.TRANSFORM_3D_HIDDEN, ErrorType.TRANSFORM_OFFSCREEN]
    priority = 30
    
    def generate_fix(self, error: ClassifiedError) -> List[TailwindPatch]:
        patches = []
        
        # 1. Parent necesita preserve-3d y perspective
        parent_selector = self._find_transform_container(error)
        if parent_selector:
            patches.append(TailwindPatch(
                selector=parent_selector,
                add_classes=[
                    "[transform-style:preserve-3d]",
                    "[perspective:1000px]"
                ]
            ))
        
        # 2. Elemento necesita backface visible
        patches.append(TailwindPatch(
            selector=error.selector,
            add_classes=["[backface-visibility:visible]"],
            remove_classes=["[backface-visibility:hidden]"]
        ))
        
        return patches


class VisualFeedbackAmplifierRule(FixRule):
    """Amplifica feedback visual con clases Tailwind."""
    
    handles = [ErrorType.FEEDBACK_TOO_SUBTLE]
    priority = 50
    
    def generate_fix(self, error: ClassifiedError) -> TailwindPatch:
        return TailwindPatch(
            selector=error.selector,
            add_classes=[
                "active:scale-95",
                "active:brightness-75",
                "focus:ring-4",
                "focus:ring-blue-500",
                "transition-all",
                "duration-150"
            ]
        )
```

---

# 🏃 SPRINT 5: SANDBOX AVANZADO + DIFF ENGINE
## Semanas 10-11

*(Sin cambios - el sandbox no depende de CSS vs Tailwind)*

---

# 🏃 SPRINT 6: LLM SURGICAL FIXER
## Semanas 12-13

### 📎 Sprint Goal
> **Implementar el LLM fixer que genera patches con clases Tailwind, no CSS raw.**

---

### 🆕 Prompt Builder para Tailwind

```python
class PromptBuilder:
    """Construye prompts para LLM con contexto Tailwind."""
    
    SYSTEM_PROMPT = """You are a frontend enginner and Tailwind CSS repair specialist. You receive:
1. An ERROR REPORT with specific element selectors
2. The CURRENT Tailwind classes on problematic elements
3. BEFORE/AFTER screenshots showing the problem

CRITICAL RULES:
- Output ONLY JSON patches with Tailwind classes
- NEVER output raw CSS
- NEVER remove elements or functionality
- Use standard Tailwind classes when possible
- Use arbitrary values [value] only when necessary

OUTPUT FORMAT:
{
  "analysis": "Brief description of the issue",
  "patches": [
    {
      "selector": ".option-btn",
      "add_classes": ["relative", "z-50", "pointer-events-auto"],
      "remove_classes": ["z-10"]
    }
  ]
}

COMMON FIXES:
- Z-index issues: Add "z-50" or "z-[100]", add "relative"
- Pointer blocked: Add "pointer-events-auto" to target, "pointer-events-none" to blocker
- Invisible: Add "opacity-100", "block", "visible"
- 3D transforms: Add "[transform-style:preserve-3d]", "[perspective:1000px]"
- Weak feedback: Add "active:scale-95", "transition-all"

TAILWIND Z-INDEX SCALE:
- z-0, z-10, z-20, z-30, z-40, z-50 (standard)
- z-[100], z-[9999] (arbitrary for edge cases)
"""
    
    def build(
        self, 
        errors: List[ClassifiedError],
        html: str,
        screenshots: Optional[Dict[str, bytes]] = None
    ) -> List[Dict]:
        """Construye mensajes para el LLM."""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        # Construir contexto de errores CON info de Tailwind
        error_context = self._build_error_context(errors)
        
        user_content = f"""
## ERRORS TO FIX

{error_context}

## INSTRUCTIONS

Generate JSON patches with Tailwind classes to fix ONLY the errors listed.
Do NOT output any CSS. Only Tailwind class modifications.
"""
        
        messages.append({"role": "user", "content": user_content})
        return messages
    
    def _build_error_context(self, errors: List[ClassifiedError]) -> str:
        """Construye descripción de errores con clases Tailwind actuales."""
        lines = []
        for i, error in enumerate(errors, 1):
            current_classes = " ".join(error.tailwind_info.all_classes)
            lines.append(f"""
### Error {i}: {error.error_type.value}
- Selector: `{error.selector}`
- Current classes: `{current_classes}`
- Blocking element: `{error.blocking_element or 'N/A'}`
- Missing recommended: `{', '.join(error.tailwind_info.missing_recommended)}`
""")
        return "\n".join(lines)
```

---

### 🆕 Patch Validator para Tailwind

```python
class PatchValidator:
    """Valida que los patches Tailwind no sean destructivos."""
    
    FORBIDDEN_CLASSES = [
        "hidden",
        "invisible", 
        "opacity-0",
        "pointer-events-none"  # Solo permitido en bloqueadores, no en targets
    ]
    
    def is_safe(
        self, 
        original_html: str, 
        patches: List[TailwindPatch]
    ) -> ValidationResult:
        """Valida que los patches sean seguros."""
        
        for patch in patches:
            # Verificar clases prohibidas en elementos interactivos
            if self._is_interactive_selector(patch.selector):
                for forbidden in self.FORBIDDEN_CLASSES:
                    if forbidden in patch.add_classes:
                        return ValidationResult(
                            safe=False,
                            reason=f"Cannot add '{forbidden}' to interactive element {patch.selector}"
                        )
        
        # Aplicar y verificar que no se pierdan elementos
        patched_html = TailwindInjector().apply(original_html, patches)
        
        if not self._elements_preserved(original_html, patched_html):
            return ValidationResult(
                safe=False,
                reason="Patch would remove interactive elements"
            )
        
        return ValidationResult(safe=True, reason="All checks passed")
```

---

# 🏃 SPRINT 7 y 8
## Sin cambios mayores

El orquestador y test suite funcionan igual, solo usando `TailwindPatch` en vez de `CSSPatch`.

---

# 📊 COMPARACIÓN: CSS RAW vs TAILWIND

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    BENEFICIOS DE USAR TAILWIND                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ASPECTO                │ CSS RAW        │ TAILWIND                      │
│   ───────────────────────┼────────────────┼──────────────────────────────│
│   Consistencia           │ Variable       │ Siempre igual                 │
│   Tokens LLM             │ ~50 por fix    │ ~15 por fix (-70%)           │
│   Conflictos             │ Posibles       │ Imposibles (clases atómicas) │
│   Especificidad          │ Guerras CSS    │ No aplica                     │
│   Debugging              │ Buscar en CSS  │ Ver clases en HTML           │
│   Rollback               │ Quitar <style> │ Quitar clases                │
│   Preview                │ Difícil        │ Fácil (solo leer clases)     │
│                                                                            │
│   RESULTADO ESPERADO:                                                      │
│   ├── 50% menos errores de generación (prevención)                        │
│   ├── 70% menos tokens en fixes (ahorro)                                  │
│   └── 30% más éxito en fixes (consistencia)                               │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

# 🎯 PROBABILIDADES ACTUALIZADAS

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    NUEVA ESTIMACIÓN CON TAILWIND                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ESCENARIO                      │ ANTES (CSS) │ AHORA (Tailwind)         │
│   ───────────────────────────────┼─────────────┼─────────────────────────│
│   Probabilidad base              │    80%      │    88%   (+8%)          │
│   Con 1 iteración usuario        │    92%      │    95%   (+3%)          │
│   Con 2 iteraciones              │    96%      │    98%   (+2%)          │
│                                                                            │
│   RAZÓN DEL AUMENTO:                                                       │
│   ├── Menos errores generados inicialmente                                │
│   ├── Fixes más predecibles y consistentes                                │
│   ├── Sin conflictos de especificidad CSS                                 │
│   └── LLM conoce mejor Tailwind que CSS arbitrario                        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

# ✅ RESUMEN DE CAMBIOS v2.0

| Componente | Cambio |
|------------|--------|
| Sprint 0 | +2 tasks: generation_prompt.md, tailwind_rules.py |
| Analyzer | Nuevo TailwindAnalyzer |
| Patches | TailwindPatch en vez de CSSPatch |
| Injector | TailwindInjector modifica clases, no inyecta CSS |
| Reglas | Todas usan clases Tailwind |
| LLM Prompt | Pide clases Tailwind, no CSS |
| Validator | Valida clases, no CSS |

**Impacto total: +8% probabilidad de éxito base**