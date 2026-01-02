# Prompt Optimization Plan - Sprint 5.1.3

## Objetivo

Reducir la redundancia en los prompts del sistema aplicando el principio de **"Reglas Inteligentes vs Ejemplos Exhaustivos"**.

Los LLMs ya saben generalizar - no necesitan listas exhaustivas de ejemplos. Una regla semántica bien escrita es más efectiva que 50 ejemplos específicos.

---

## Principio Core

```python
# ANTES (Regla Tonta) - Lista interminable de ejemplos:
"birthday" ↔ "cumpleaños" ↔ "anniversaire" ↔ "Geburtstag"
"meeting" ↔ "reunión" ↔ "réunion" ↔ "Besprechung"
"doctor" ↔ "médico" ↔ "médecin" ↔ "Arzt"
# ... 20 mappings más

# DESPUÉS (Regla Inteligente) - Una instrucción semántica:
"Match semantically across languages. You understand that words like
birthday/cumpleaños/anniversaire are translations of the same concept."
```

---

## Reglas de Optimización

### 1. Confiar en la Capacidad del LLM
- Los LLMs conocen sinónimos, traducciones y abreviaciones
- No necesitan listas explícitas de `bday = birthday = cumpleaños`
- Una regla como "reconoce abreviaciones comunes" es suficiente

### 2. Ejemplos Solo Para Formato
- Mantener ejemplos que muestran **estructura JSON** esperada
- Mantener ejemplos de **casos edge** (no-match, ambiguity)
- Eliminar ejemplos que repiten la misma clasificación

### 3. Preservar Headers de Secciones
- Los tests verifican strings específicos (ej: `"TYPO TOLERANCE" in prompt`)
- Mantener headers, consolidar contenido bajo ellos

### 4. Cambios Quirúrgicos
- Verificar dependencias antes de editar
- Correr tests después de cada cambio
- Un prompt puede depender de otro

---

## Estado de Optimización

| Archivo | Líneas | Estado | Reducción |
|---------|--------|--------|-----------|
| `router_prompts.py` | 252 | ✅ Optimizado | -144 líneas |
| `calendar_search_prompts.py` | 136 | ✅ Optimizado | -46 líneas |
| `assistant_prompts.py` | 240 | ✅ Optimizado (Sprint 5.1.3) | -51 líneas |
| `scene_prompts.py` | 746 | ✅ Optimizado (Sprint 5.1.3) | -54 líneas |
| `execution_prompts.py` | 517 | ✅ Optimizado (Sprint 5.1.3) | -199 líneas |
| `intent_prompts.py` | 570 | ✅ Ya optimizado (Sprint 5.1.2) | - |
| `doc_prompts.py` | 305 | ✅ Aceptable | - |
| `base_prompt.py` | 457 | ✅ Aceptable | - |
| `helpers.py` | 432 | ✅ Contiene helpers inteligentes | - |

**Total reducido hasta ahora: -494 líneas**

---

## Cambios Realizados

### 1. `router_prompts.py` (Sprint 5.1.3)

**Problema:** 50 ejemplos redundantes mostrando "calendar operation = SIMPLE"

**Solución:** Consolidar a 14 ejemplos estratégicos

```python
# ANTES: 15 ejemplos individuales de calendar
Input: "Schedule a meeting tomorrow at 6 pm" → SIMPLE
Input: "Add an event to January 6" → SIMPLE
Input: "Book a 2 hour meeting" → SIMPLE
# ... 12 más

# DESPUÉS: 1 ejemplo con patrón
Input: "Schedule meeting tomorrow" / "Reschedule dentist to 3pm" / "Delete my meeting"
Output: {..., "reasoning": "Calendar create/edit/delete - intent parser handles"}
```

### 2. `calendar_search_prompts.py` (Sprint 5.1.3)

**Problema:** Listas exhaustivas de traducciones y sinónimos

**Solución:** Reglas semánticas que confían en el conocimiento del LLM

```python
# ANTES: 30 mappings de traducción
"birthday" ↔ "cumpleaños" ↔ "anniversaire" ↔ "Geburtstag" ↔ "aniversário"
"meeting" ↔ "reunión" ↔ "réunion" ↔ "Besprechung" ↔ "reunião"
# ... 4 más

# DESPUÉS: 1 regla inteligente
"Match semantically across languages. You understand that words like
birthday/cumpleaños/anniversaire are translations of the same concept."
```

---

## Cambios Sprint 5.1.3 (Completado)

### `assistant_prompts.py` (-51 líneas)
- `UNIVERSAL_MULTILINGUAL_RULE`: De 14 líneas a 3 líneas (regla inteligente)
- Web Search: De 15 líneas a 3 líneas
- Content Generation: De 18 líneas a 3 líneas
- Few-shot examples: De 12 líneas a 2 líneas

### `scene_prompts.py` (-54 líneas)
- Spatial keywords: De 17 líneas a 8 líneas
- Content Gen vs Extract: De 19 líneas a 5 líneas
- Document Intelligence: De 27 líneas a 4 líneas
- Meeting+Doc Combinations: De 9 líneas a 4 líneas

### `execution_prompts.py` (-199 líneas)
- EXECUTION_EXAMPLES: De 228 líneas (13 ejemplos) a 29 líneas (5 patrones + reglas)

---

## Verificación Post-Cambio

Después de cada optimización:

```bash
# 1. Verificar sintaxis Python
python3 -c "from app.ai.prompts.<module> import *; print('OK')"

# 2. Verificar assertions de tests (si existen)
python3 -c "
from app.ai.prompts.<module> import PROMPT_NAME
assert 'REQUIRED_HEADER' in PROMPT_NAME
print('Tests pass')
"

# 3. Test funcional via API
curl -X POST http://localhost:8000/intent \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text": "<test case>"}'
```

---

## Métricas de Éxito

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Total líneas en prompts | ~4,031 | ~3,537 | -494 (12%) |
| Ejemplos redundantes | ~80 | ~15 | -81% |
| Tiempo de contexto LLM | - | - | Reducido |

### Tests de Generalización (Sprint 5.1.3)

Los prompts optimizados fueron testeados con ejemplos NO listados explícitamente:

| Test | Descripción | Resultado |
|------|-------------|-----------|
| Italiano | Idioma no en prompt | ✅ Respondió en italiano |
| "tendencias" | Keyword no listado | ✅ Buscó inmediatamente |
| "elabora" | Verbo no listado | ✅ Generó contenido |
| "esquina superior" | Posición no listada | ✅ Layout correcto |
| "silencia" | Acción no listada | ✅ Mapeó a mute |

**Conclusión:** Las reglas inteligentes permiten que el LLM generalice correctamente sin necesidad de listas exhaustivas de ejemplos.

---

*Última actualización: 2026-01-02*
