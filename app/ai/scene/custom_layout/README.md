# Custom Layout - HTML Fixer

> Tailwind-based HTML validation and repair system for interactive layouts.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HTML FIXER PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │   PROMPT     │ →  │  LLM GENERA  │ →  │  VALIDATOR   │                │
│   │  (generation │    │  HTML+Tailwind│    │  (Playwright)│                │
│   │   _prompt.md)│    │              │    │              │                │
│   └──────────────┘    └──────────────┘    └──────┬───────┘                │
│                                                   │                         │
│                                    ┌──────────────▼───────────┐            │
│                                    │     PASS?                │            │
│                                    │  ┌─────┐    ┌─────┐     │            │
│                                    │  │ YES │    │ NO  │     │            │
│                                    │  └──┬──┘    └──┬──┘     │            │
│                                    └─────┼──────────┼────────┘            │
│                                          │          │                       │
│                                          ▼          ▼                       │
│                                    ┌─────────┐ ┌─────────────┐             │
│                                    │ RETURN  │ │   FIXER     │             │
│                                    │  HTML   │ │ (Tailwind   │             │
│                                    └─────────┘ │  patches)   │             │
│                                                └──────┬──────┘             │
│                                                       │                     │
│                                                       ▼                     │
│                                                ┌─────────────┐             │
│                                                │ RE-VALIDATE │             │
│                                                └─────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
custom_layout/
├── html_fixer/              # Core fixer implementation
│   ├── contracts/           # Data structures
│   │   ├── errors.py        # ErrorType enum
│   │   ├── patches.py       # TailwindPatch dataclass
│   │   └── validation.py    # TailwindInfo, ClassifiedError, FixResult
│   ├── analyzers/           # DOM/CSS analysis (Sprint 1)
│   ├── fixers/              # Repair implementations
│   │   ├── deterministic/   # Rule-based fixes (Sprint 3)
│   │   └── llm/             # LLM-powered fixes (Sprint 6)
│   ├── validators/          # Playwright validation (Sprint 2)
│   ├── orchestrator/        # Pipeline coordination (Sprint 5)
│   └── tailwind_rules.py    # Tailwind class definitions
├── prompts/
│   └── generation_prompt.md # Rules for LLM HTML generation
├── tests/
│   ├── fixtures/            # Test HTML files
│   │   ├── trivia/          # Quiz/flashcard layouts
│   │   ├── dashboard/       # Dashboard layouts
│   │   └── modals/          # Modal/overlay layouts
│   ├── unit/                # Unit tests
│   └── conftest.py          # Pytest configuration
└── README.md
```

## Key Concepts

### TailwindPatch

Instead of injecting CSS rules, we modify Tailwind classes directly:

```python
patch = TailwindPatch(
    selector=".option-btn",
    add_classes=["z-50", "pointer-events-auto", "relative"],
    remove_classes=["z-10"]
)
```

### ErrorType

Errors are classified by root cause:

| Error Type | Description | Fix Strategy |
|------------|-------------|--------------|
| `ZINDEX_CONFLICT` | Element behind another | Add higher `z-*` class |
| `POINTER_BLOCKED` | Overlay blocking clicks | Add `pointer-events-none` |
| `TRANSFORM_3D_HIDDEN` | Backface visibility issue | Add `[backface-visibility:hidden]` |
| `FEEDBACK_TOO_SUBTLE` | Click feedback < 2% pixels | Add `active:scale-95 active:bg-*` |

### TailwindFixes

Predefined classes for common fixes:

```python
from app.ai.scene.custom_layout.html_fixer import TailwindFixes

# Get appropriate z-index fix
fix_class = TailwindFixes.get_zindex_fix(current_z=10)  # Returns "z-50"

# Get feedback amplification classes
feedback = TailwindFixes.get_feedback_amplification()
# Returns ["active:scale-95", "active:brightness-75", "transition-all", "duration-150"]
```

## Validation Pipeline

The validator uses Playwright to test interactivity:

1. **Render** - Load HTML in headless browser
2. **Detect** - Find interactive elements (buttons, inputs)
3. **Click** - Simulate user clicks
4. **Compare** - Screenshot before/after comparison
5. **Report** - Classify failures by error type

### Pass Criteria

An element passes validation if clicking it produces:
- **Global threshold**: ≥2% of viewport pixels change, OR
- **Element threshold**: ≥30% of element pixels change

## Test Fixtures

Each fixture demonstrates a specific bug:

| Fixture | Bug | Error Type |
|---------|-----|------------|
| `flashcard_3d_broken.html` | Missing preserve-3d | `TRANSFORM_3D_HIDDEN` |
| `multiple_choice_broken.html` | Overlay blocks buttons | `POINTER_BLOCKED` |
| `quiz_modal_broken.html` | Modal never dismisses | `POINTER_BLOCKED` |
| `sequential_broken.html` | Border-only feedback | `FEEDBACK_TOO_SUBTLE` |
| `sidebar_broken.html` | Gradient overlay blocks | `POINTER_BLOCKED` |
| `card_grid_broken.html` | Inherited pointer-events-none | `POINTER_BLOCKED` |
| `data_table_broken.html` | Opacity-only hover | `FEEDBACK_TOO_SUBTLE` |
| `nested_broken.html` | Same z-index on nested modals | `ZINDEX_CONFLICT` |
| `form_modal_broken.html` | Form inputs blocked | `POINTER_BLOCKED` |

## Running Tests

```bash
# From project root
cd app/ai/scene/custom_layout

# Run all tests
pytest tests/ -v

# Run only fast tests (no Playwright)
pytest tests/ -v -m "not playwright"

# Run with Playwright visual tests
pytest tests/ -v -m "playwright"

# Test specific fixture category
pytest tests/ -v -k "trivia"
```

## Sprint Roadmap

| Sprint | Focus | Status |
|--------|-------|--------|
| 0 | Foundation, fixtures, contracts | ✅ Complete |
| 1 | TailwindAnalyzer, DOMParser | 🔜 Next |
| 2 | Playwright validator | ⬜ Planned |
| 3 | Deterministic fixers | ⬜ Planned |
| 4 | Transform/feedback rules | ⬜ Planned |
| 5 | Orchestrator, rollback | ⬜ Planned |
| 6 | LLM surgical fixer | ⬜ Planned |

## Dependencies

Required:
- `beautifulsoup4` - HTML parsing
- `playwright` - Browser automation
- `Pillow` - Screenshot comparison

Install:
```bash
pip install beautifulsoup4 playwright Pillow
playwright install chromium
```
