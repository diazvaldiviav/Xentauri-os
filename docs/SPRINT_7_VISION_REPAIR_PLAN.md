# Sprint 7: Vision-Enhanced Visual Repair System

## Problema Actual

El sistema de validación detecta elementos en el DOM pero **no verifica si son visualmente visibles**. El fixer (Sonnet) recibe diagnósticos CSS pero no puede ver lo que realmente se renderiza.

### Ejemplo: Sistema Solar
- Opus genera HTML con planetas creados dinámicamente
- Los planetas existen en el DOM (tienen `cursor: pointer`)
- **PERO** los planetas son invisibles (transform 3D los oculta)
- El validator detecta 4/8 elementos responsive
- El fixer intenta arreglar CSS pero el problema es JS/visibilidad

## Solución: Vision-Enhanced Repair

### Principio
> "Sonnet debe VER lo que el usuario VE, no solo leer el código"

---

## Arquitectura de Cambios

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FLUJO MEJORADO                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Phase 2: Visual Analysis (MEJORADA)                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ + Guardar screenshot en SandboxResult.page_screenshot       │    │
│  │ + Guardar path: /tmp/jarvis_debug_html/screenshots/         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Phase 4: Input Detection (MEJORADA)                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ + Para cada elemento detectado:                             │    │
│  │   - Capturar screenshot del bounding box                    │    │
│  │   - Verificar si tiene píxeles visibles (no transparente)   │    │
│  │   - Marcar como "invisible" si no tiene contenido visual    │    │
│  │ + Nuevo campo: InputCandidate.visibility_status             │    │
│  │   - "visible" | "invisible" | "partial"                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Phase 5: Interaction (MEJORADA)                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ + Guardar screenshot before/after de cada elemento          │    │
│  │ + Si elemento es "invisible", marcar como error especial    │    │
│  │ + Nuevo failure_type: "element_invisible"                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Phase 7: Fixer (REESCRITO)                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ + Usar Sonnet con VISION (enviar imagen)                    │    │
│  │ + Activar EXTENDED THINKING (budget_tokens: 10000)          │    │
│  │ + Enviar:                                                    │    │
│  │   1. Screenshot de la página completa                       │    │
│  │   2. Prompt original del usuario                            │    │
│  │   3. Diagnóstico de cada fase                               │    │
│  │   4. HTML actual                                            │    │
│  │ + Sonnet debe verificar:                                    │    │
│  │   - ¿El render es coherente con lo pedido?                  │    │
│  │   - ¿Los elementos detectados como fallidos son visibles?   │    │
│  │   - ¿Qué está realmente mal? (CSS, JS, o estructura)        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Cambios por Archivo

### 1. `contracts.py` - Nuevos campos

```python
@dataclass
class InputCandidate:
    # ... campos existentes ...

    # Sprint 7: Visibility detection
    visibility_status: str = "unknown"  # "visible" | "invisible" | "partial"
    visibility_pixels: int = 0          # Píxeles no-transparentes en bounding box
    visibility_ratio: float = 0.0       # % del área con contenido visual

@dataclass
class SandboxResult:
    # ... campos existentes ...

    # Sprint 7: Screenshots for vision repair
    page_screenshot: Optional[bytes] = None  # PNG de página completa
    screenshot_path: Optional[str] = None    # Path al archivo guardado

@dataclass
class InteractionResult:
    # ... campos existentes ...

    # Sprint 7: Before/after screenshots
    screenshot_before: Optional[bytes] = None
    screenshot_after: Optional[bytes] = None
```

### 2. `input_detector.py` - Detección de visibilidad

```python
async def detect(self, page, scene_graph, contract) -> Tuple[PhaseResult, List[InputCandidate]]:
    # ... detección existente ...

    # Sprint 7: Verificar visibilidad de cada elemento
    for candidate in candidates:
        visibility = await self._check_element_visibility(page, candidate)
        candidate.visibility_status = visibility["status"]
        candidate.visibility_pixels = visibility["pixels"]
        candidate.visibility_ratio = visibility["ratio"]

    # Reportar elementos invisibles
    invisible_count = sum(1 for c in candidates if c.visibility_status == "invisible")
    if invisible_count > 0:
        logger.warning(f"Phase 4: {invisible_count} elements exist in DOM but are INVISIBLE")

async def _check_element_visibility(self, page, candidate) -> dict:
    """
    Sprint 7: Verificar si un elemento tiene píxeles visibles.

    Un elemento puede existir en el DOM pero ser invisible por:
    - opacity: 0
    - visibility: hidden
    - display: none
    - transform que lo saca del viewport
    - z-index negativo
    - width/height: 0
    """
    try:
        locator = page.locator(candidate.selector).first
        box = candidate.node.bounding_box

        # Capturar screenshot solo del elemento
        element_screenshot = await locator.screenshot(type="png")

        # Analizar si tiene contenido visual
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(element_screenshot)).convert("RGBA")
        pixels = list(img.getdata())

        # Contar píxeles no-transparentes
        visible_pixels = sum(1 for p in pixels if p[3] > 10)  # Alpha > 10
        total_pixels = len(pixels)
        ratio = visible_pixels / total_pixels if total_pixels > 0 else 0

        if ratio < 0.05:
            status = "invisible"
        elif ratio < 0.50:
            status = "partial"
        else:
            status = "visible"

        return {
            "status": status,
            "pixels": visible_pixels,
            "ratio": ratio,
        }
    except Exception as e:
        logger.debug(f"Could not check visibility for {candidate.selector}: {e}")
        return {"status": "unknown", "pixels": 0, "ratio": 0.0}
```

### 3. `anthropic_provider.py` - Método con Vision

```python
async def generate_with_vision(
    self,
    prompt: str,
    image_bytes: bytes,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    thinking_budget: int = 10000,  # Extended thinking
    **kwargs
) -> AIResponse:
    """
    Sprint 7: Generate response with image input and extended thinking.

    Uses Claude's vision capabilities to analyze screenshots
    and extended thinking for complex reasoning.
    """
    import base64

    start_time = time.time()

    if not self._client:
        return self._create_error_response(
            error="Anthropic API key not configured",
            model=self.model,
            latency_ms=self._measure_latency(start_time)
        )

    try:
        # Encode image as base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Build message with image
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        request_params = {
            "model": "claude-sonnet-4-20250514",  # Sonnet 4 con vision
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }

        # Add system prompt if provided
        if system_prompt:
            request_params["system"] = system_prompt

        # Add extended thinking if budget > 0
        if thinking_budget > 0:
            request_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget
            }

        response = await self._client.messages.create(**request_params)

        latency_ms = self._measure_latency(start_time)

        # Extract content (may include thinking blocks)
        content = ""
        thinking_content = ""

        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
                elif hasattr(block, 'thinking'):
                    thinking_content = block.thinking

        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens if response.usage else 0,
            completion_tokens=response.usage.output_tokens if response.usage else 0,
        )

        logger.info(
            f"Anthropic vision request completed in {latency_ms:.0f}ms, "
            f"tokens: {usage.total_tokens}, thinking: {len(thinking_content)} chars"
        )

        return AIResponse(
            content=content,
            provider=self.provider_type,
            model="claude-sonnet-4-20250514",
            usage=usage,
            latency_ms=latency_ms,
            success=True,
            raw_response=response,
            metadata={"thinking": thinking_content} if thinking_content else None,
        )

    except Exception as e:
        latency_ms = self._measure_latency(start_time)
        logger.error(f"Anthropic vision generation failed: {e}")
        return self._create_error_response(
            error=str(e),
            model=self.model,
            latency_ms=latency_ms
        )
```

### 4. `fixer.py` - Vision-Enhanced Repair

```python
VISION_REPAIR_SYSTEM_PROMPT = """You are an HTML repair specialist with VISUAL INSPECTION capabilities.

## YOUR TASK

You will receive:
1. A SCREENSHOT of the rendered page
2. The ORIGINAL USER REQUEST
3. A VALIDATION REPORT with phase-by-phase diagnosis
4. The HTML code that needs repair

## VISUAL INSPECTION FIRST

Before making any changes, ANALYZE THE SCREENSHOT:

1. **Coherence Check**: Does the screenshot match what the user requested?
   - If user asked for "sistema solar", do you see a sun and planets?
   - If user asked for "trivia", do you see questions and options?
   - Rate coherence: FULL | PARTIAL | NONE

2. **Visibility Check**: Look at the elements marked as "failed" in the validation
   - Can you SEE them in the screenshot?
   - If elements exist in DOM but are invisible, the problem is NOT CSS styling
   - The problem is likely: JS not executing, transform hiding elements, z-index

3. **Root Cause Analysis**:
   - If coherence = NONE: The generation fundamentally failed, need major rewrite
   - If coherence = PARTIAL but elements invisible: Fix JS/visibility, not CSS
   - If coherence = FULL but interactions fail: Fix CSS feedback only

## REPAIR STRATEGY

Based on visual inspection:

### If elements are INVISIBLE (exist in DOM but not rendered):
- Check JavaScript that creates/shows elements
- Check CSS: transform, opacity, visibility, display, z-index
- Check if animations are preventing display
- DO NOT just add background-color - the element isn't visible!

### If elements are VISIBLE but don't respond:
- Check onclick handlers
- Check CSS .selected/.active rules
- Add dramatic visual feedback (background-color change)

### If page is completely wrong:
- Report that the HTML needs regeneration
- Return the original HTML with a comment: <!-- NEEDS_REGENERATION: reason -->

## OUTPUT

Return ONLY the fixed HTML from <!DOCTYPE html> to </html>.
If the HTML needs complete regeneration, return it unchanged with the NEEDS_REGENERATION comment.
"""


async def repair_with_vision(
    self,
    html: str,
    sandbox_result: SandboxResult,
    user_request: str,
    page_screenshot: bytes,
    max_tokens: int = 16384,
) -> Optional[str]:
    """
    Sprint 7: Repair HTML using Sonnet's vision capabilities.

    Sends the actual screenshot so Sonnet can see what's rendered,
    not just read the code.
    """
    if sandbox_result.valid:
        return html

    logger.info(
        f"Starting Vision-Enhanced repair - "
        f"failures: {sandbox_result.failure_summary}"
    )

    try:
        from app.ai.providers.anthropic_provider import anthropic_provider

        # Build comprehensive prompt
        prompt = self._build_vision_repair_prompt(
            html=html,
            sandbox_result=sandbox_result,
            user_request=user_request,
        )

        # Call Sonnet with vision + extended thinking
        response = await anthropic_provider.generate_with_vision(
            prompt=prompt,
            image_bytes=page_screenshot,
            system_prompt=VISION_REPAIR_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=max_tokens,
            thinking_budget=10000,  # Extended thinking for analysis
        )

        if not response.success:
            logger.warning(f"Vision repair failed: {response.error}")
            return None

        # Check for NEEDS_REGENERATION marker
        if "NEEDS_REGENERATION" in response.content:
            logger.warning("Vision repair determined HTML needs complete regeneration")
            return None  # Signal to caller that regeneration is needed

        repaired_html = self._clean_html_response(response.content)

        if repaired_html:
            logger.info(
                f"Vision repair completed - "
                f"original: {len(html)} chars, "
                f"repaired: {len(repaired_html)} chars"
            )
            return repaired_html
        else:
            logger.warning("Failed to extract valid HTML from vision repair")
            return None

    except Exception as e:
        logger.error(f"Vision repair error: {e}", exc_info=True)
        return None


def _build_vision_repair_prompt(
    self,
    html: str,
    sandbox_result: SandboxResult,
    user_request: str,
) -> str:
    """Build prompt for vision-enhanced repair."""

    # Phase summary with visibility info
    phase_summary = _build_phase_summary(sandbox_result)

    # CSS diagnosis with visibility status
    css_diagnosis = self._build_visibility_aware_diagnosis(html, sandbox_result)

    # Coherence check section
    coherence_section = f"""
## COHERENCE CHECK

The user requested: "{user_request}"

Look at the screenshot and answer:
1. Does the rendered page match what the user asked for?
2. Are the key elements (mentioned in the request) visible?
3. What is missing or broken?
"""

    # Truncate HTML
    max_html_len = 10000
    if len(html) > max_html_len:
        half = max_html_len // 2
        truncated_html = html[:half] + "\n<!-- ... TRUNCATED ... -->\n" + html[-half:]
    else:
        truncated_html = html

    return f"""Analyze this screenshot and fix the HTML.

## ORIGINAL USER REQUEST

"{user_request}"

{coherence_section}

---

{phase_summary}

---

{css_diagnosis}

---

## HTML TO FIX

```html
{truncated_html}
```

## INSTRUCTIONS

1. First, describe what you SEE in the screenshot (2-3 sentences)
2. Compare with what the user requested
3. Identify the root cause of failures (JS? CSS? Visibility? Structure?)
4. Make targeted fixes
5. Return the complete fixed HTML

## OUTPUT

Return ONLY the corrected HTML from <!DOCTYPE html> to </html>.
"""


def _build_visibility_aware_diagnosis(self, html: str, sandbox_result: SandboxResult) -> str:
    """Build diagnosis that includes visibility status."""
    lines = []
    lines.append("## ELEMENT DIAGNOSIS\n")

    for ir in sandbox_result.interaction_results:
        ctx = ir.get_repair_context(threshold=0.02)

        selector = ctx["selector"]
        elem = ctx.get("element", {})
        visibility = elem.get("visibility_status", "unknown")

        status_emoji = {
            "visible": "👁️",
            "invisible": "👻",
            "partial": "🌓",
            "unknown": "❓"
        }.get(visibility, "❓")

        responsive = "✅ WORKS" if ir.responsive else "❌ FAILS"

        lines.append(f"### {status_emoji} `{selector}` - {responsive}")
        lines.append(f"**Visibility:** {visibility}")

        if visibility == "invisible":
            lines.append("⚠️ **CRITICAL:** Element exists in DOM but has NO VISIBLE PIXELS")
            lines.append("   This is NOT a CSS styling issue - the element doesn't render!")
            lines.append("   Possible causes: JS not creating it, transform hiding it, z-index, opacity:0")

        if not ir.responsive:
            lines.append(f"**Failure Type:** {ctx['failure_type']}")
            lines.append(f"**Pixel Change:** {ctx['pixel_diff_pct']}")

        lines.append("")

    return "\n".join(lines)
```

### 5. `service.py` - Integración del flujo

```python
async def generate_and_validate_html(self, ...):
    # ... generación existente ...

    # Validación con screenshots
    validation_result = await visual_validator.validate(contract)

    # Sprint 7: Si falló, usar vision repair
    if not validation_result.valid and validation_result.page_screenshot:
        for attempt in range(max_repair_attempts):
            logger.info(f"Vision repair attempt {attempt + 1}/{max_repair_attempts}")

            repaired_html = await direct_fixer.repair_with_vision(
                html=html,
                sandbox_result=validation_result,
                user_request=user_request,
                page_screenshot=validation_result.page_screenshot,
            )

            if repaired_html is None:
                # NEEDS_REGENERATION signal - try regenerating from scratch
                logger.warning("Vision repair requested regeneration")
                break

            # Re-validate
            repair_validation = await visual_validator.validate(
                ValidationContract(html=repaired_html, ...)
            )

            if repair_validation.valid:
                return CustomLayoutResult(html=repaired_html, success=True)

            html = repaired_html
            validation_result = repair_validation

    # ... resto del flujo ...
```

---

## Resumen de Cambios

| Archivo | Cambio | Impacto |
|---------|--------|---------|
| `contracts.py` | Agregar campos de visibilidad y screenshots | Bajo |
| `input_detector.py` | Verificar visibilidad de elementos | Medio |
| `visual_analyzer.py` | Guardar screenshots en resultado | Bajo |
| `anthropic_provider.py` | Nuevo método `generate_with_vision` | Medio |
| `fixer.py` | Nuevo `repair_with_vision` con prompt mejorado | Alto |
| `service.py` | Integrar vision repair en el flujo | Medio |

## Beneficios Esperados

1. **Detección de invisibles**: El sistema sabrá que elementos existen pero no se ven
2. **Diagnóstico visual**: Sonnet VE lo que está mal, no solo lee código
3. **Coherencia**: Verificación de que el render coincide con lo pedido
4. **Mejor repair**: Con thinking + vision, Sonnet puede razonar sobre el problema real
5. **Menos loops**: Con mejor diagnóstico, menos intentos de repair fallidos

## Métricas de Éxito

- Reducir intentos de repair fallidos de ~50% a <20%
- Detectar 100% de elementos invisibles antes de Phase 5
- Tiempo de repair no debe aumentar más de 30% (thinking budget limitado)

---

## Estado de Implementación

| Tarea | Estado | Notas |
|-------|--------|-------|
| `contracts.py` - Campos de visibilidad | ✅ COMPLETADO | Campos visibility_status, visibility_pixels, visibility_ratio |
| `contracts.py` - Screenshots en SandboxResult | ✅ COMPLETADO | page_screenshot, screenshot_path, invisible_elements_count |
| `input_detector.py` - Check de visibilidad | ✅ COMPLETADO | check_elements_visibility(), _check_single_element_visibility() |
| `visual_analyzer.py` - Guardar screenshots | ✅ COMPLETADO | save_screenshot(), image_to_base64(), resize_image_for_api() |
| `anthropic_provider.py` - Vision API | ✅ COMPLETADO | generate_with_vision() con extended thinking |
| `fixer.py` - Vision repair | ✅ COMPLETADO | repair_with_vision(), VISION_REPAIR_SYSTEM_PROMPT |
| `__init__.py` - Integración validator | ✅ COMPLETADO | Captura screenshot, check visibilidad, repair_with_vision() |
| `service.py` - Flujo de repair | ✅ COMPLETADO | Usa vision repair cuando hay screenshot disponible |
| `config.py` - Settings | ✅ COMPLETADO | VISION_REPAIR_ENABLED toggle |
| Pruebas con sistema solar | ⏳ PENDIENTE | Necesita testing manual |

### Fecha de Implementación
- **Inicio**: 2026-01-11
- **Completado**: 2026-01-11

### Siguiente Paso
Probar el sistema con una simulación del sistema solar para verificar:
1. Detección de planetas invisibles en Phase 4
2. Screenshot guardado correctamente
3. Vision repair identificando elementos faltantes
4. Reparación exitosa con planetas visibles
