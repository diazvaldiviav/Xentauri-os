# Custom Layout - Behavior Validation System

## Contexto del Problema

El sistema genera HTML interactivo (trivias, flash cards, mini-games) usando Opus 4.5. El problema es **validar que el HTML realmente funciona** antes de enviarlo al dispositivo.

### Flujo Actual

```
Usuario pide "crea una trivia flash cards"
    ↓
Gemini 3 Flash genera SceneGraph (contenido)
    ↓
Opus 4.5 genera HTML + TEST_MANIFEST (diseño)
    ↓
Playwright valida usando el manifest
    ↓
Si falla → Gemini diagnostica → Codex-Max repara
    ↓
Si pasa → Se envía al dispositivo
```

## Archivos Clave

| Archivo | Propósito |
|---------|-----------|
| `app/ai/scene/custom_layout/prompts.py` | Prompt a Opus 4.5 para generar HTML |
| `app/ai/scene/custom_layout/validator.py` | ManifestValidator + BehaviorValidator |
| `app/ai/scene/custom_layout/service.py` | Orquesta generación y repair loop |
| `app/ai/providers/anthropic_provider.py` | Cliente Anthropic con thinking mode |
| `app/core/config.py` | Settings (thinking budget, retries, etc.) |

## Lo Que Funciona

1. **Experience Detection** - Detecta trivia/game/dashboard via `[data-trivia]`, `[data-game]`
2. **TEST_MANIFEST** - Opus genera un manifest con tests específicos
3. **Manifest Validation** - Playwright ejecuta los tests del manifest
4. **Repair Loop** - Si falla, Gemini diagnostica y Codex repara
5. **Extended Thinking** - Opus piensa antes de generar (10k tokens)
6. **HTML Debug Saving** - HTML se guarda en `/app/debug_html/` para inspección

## El Problema Actual: Falsos Positivos

Los tests del manifest pasan pero el HTML no funciona en la realidad.

### Ejemplo:

```
Logs dicen:
  Manifest validation: 2/2 passed ✅

Pero en el dispositivo:
  Flash cards no se voltean ❌
```

### Por qué pasa esto:

1. El manifest dice: `{"click": ".card", "expect": {"class_added": [".card", "flipped"]}}`
2. Playwright verifica: ¿Se agregó la clase `flipped`? → Sí ✅
3. Pero el CSS de `.flipped` puede estar roto, o la animación no funciona
4. O Opus genera manifests con expectativas vacías: `{"class_added": [".card", ""]}`

### Lo que verificamos vs lo que deberíamos verificar:

| Verificamos | Deberíamos verificar |
|-------------|---------------------|
| Clase agregada | Elemento visualmente cambió |
| Texto cambió | Contenido oculto se hizo visible |
| Selector existe | Interacción produce resultado esperado |

## Intentos de Solución

### 1. Mejorar `_get_state_hash` ✅
Agregamos detección de clases CSS, `:checked`, `data-*` attributes.
**Resultado**: Mejor pero insuficiente.

### 2. TEST_MANIFEST ✅
Opus dice qué testear en vez de nosotros adivinar.
**Resultado**: Funciona pero Opus genera manifests incorrectos a veces.

### 3. Prompt con MANIFEST RULES ✅
Reglas para que Opus no genere expectativas vacías/inválidas.
**Resultado**: Pendiente de probar.

### 4. Extended Thinking ✅
10k tokens para que Opus piense mejor.
**Resultado**: Pendiente de probar.

### 5. HTML Debug Saving ✅
Guardar HTML para inspección manual.
**Resultado**: Ahora podemos ver qué genera Opus.

## Próximos Pasos Sugeridos

1. **Probar flash cards** y revisar el HTML guardado en `/app/debug_html/`
2. **Analizar el manifest** que Opus genera vs el HTML
3. **Verificar si el CSS/JS funciona** abriendo el HTML en navegador
4. **Opciones si sigue fallando**:
   - Agregar verificación visual real (computed styles, bounding box)
   - Validar manifest antes de ejecutar tests (rechazar expectativas vacías)
   - Simplificar: solo verificar que no hay JS errors y contenido es visible

## Comandos Útiles

```bash
# Ver logs en tiempo real
fly logs --app xentauri-cloud-core

# SSH al servidor
fly ssh console --app xentauri-cloud-core

# Ver HTMLs guardados
ls -la /app/debug_html/

# Ver último HTML
cat /app/debug_html/$(ls -t /app/debug_html/ | head -1)

# Copiar HTML a local
fly ssh sftp get /app/debug_html/layout_*.html ./
```

## Configuración Actual

```python
# config.py
CUSTOM_LAYOUT_ENABLED = True
CUSTOM_LAYOUT_BEHAVIOR_VALIDATION_ENABLED = True
CUSTOM_LAYOUT_THINKING_BUDGET = 10000  # tokens para thinking
VALIDATION_REPAIR_MAX_RETRIES = 2
```

## Tokens/Costos

- Input: ~1,200 tokens
- Output HTML: ~7,000 tokens
- Thinking: hasta 10,000 tokens
- **Costo por request**: ~$1.29 (con thinking) vs ~$0.54 (sin thinking)
- **Latencia**: ~70-90s (con thinking) vs ~50-70s (sin thinking)

---

*Última actualización: 2026-01-10 01:00 UTC*
