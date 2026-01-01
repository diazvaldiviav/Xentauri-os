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
| `assistant_prompts.py` | 290 | ⏳ Pendiente | ~25 líneas est. |
| `scene_prompts.py` | 800 | ⏳ Pendiente | ~50 líneas est. |
| `execution_prompts.py` | 716 | ⏳ Pendiente | ~80 líneas est. |
| `intent_prompts.py` | 570 | ✅ Ya optimizado (Sprint 5.1.2) | - |
| `doc_prompts.py` | 305 | ✅ Aceptable | - |
| `base_prompt.py` | 457 | ✅ Aceptable | - |
| `helpers.py` | 432 | ✅ Contiene helpers inteligentes | - |

**Total reducido hasta ahora: -190 líneas**

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

## Pendientes de Optimización

### `assistant_prompts.py` (Prioridad 1)
- Líneas 31-45: `UNIVERSAL_MULTILINGUAL_RULE` con 5 ejemplos de idiomas
- Líneas 113-124: Ejemplos duplicados EN/ES para web search
- Líneas 132-148: Ejemplos duplicados para content generation

### `scene_prompts.py` (Prioridad 2)
- Líneas 112-128: Ejemplos verbosos de spatial keywords
- Líneas 169-219: Múltiples ejemplos de content generation vs extraction
- Líneas 295-312: Ejemplo detallado redundante

### `execution_prompts.py` (Prioridad 3)
- Líneas 253-481: 11 ejemplos cuando 3-4 bastarían

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
| Total líneas en prompts | ~4,031 | ~3,841 | -190 (5%) |
| Ejemplos redundantes | ~80 | ~30 | -62% |
| Tiempo de contexto LLM | - | - | Reducido |

---

*Última actualización: 2026-01-01*
