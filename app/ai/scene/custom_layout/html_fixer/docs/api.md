# HTML Fixer API Reference

## Quick Start

```python
from html_fixer.orchestrator import Orchestrator

# Basic usage
orchestrator = Orchestrator()
result = await orchestrator.fix(html)

if result.success:
    fixed_html = result.fixed_html
    print(f"Score: {result.final_score:.0%}")
```

## Core Classes

### Orchestrator

Main entry point for HTML repair. Coordinates the classification, deterministic fixing, and optional LLM fixing pipeline.

```python
class Orchestrator:
    def __init__(
        self,
        classifier: ErrorClassificationPipeline = None,
        rule_engine: RuleEngine = None,
        llm_fixer: LLMFixer = None,
        sandbox: Sandbox = None,
        decision_engine: DecisionEngine = None,
        max_llm_attempts: int = 3,
        global_timeout_seconds: float = 120.0,
        validate_after_deterministic: bool = True,
        validate_after_llm: bool = True,
        enable_rollback: bool = True,
    )

    async def fix(
        self,
        html: str,
        page: Optional[Page] = None,
        screenshots: Optional[Dict[str, bytes]] = None,
    ) -> OrchestratorResult
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_llm_attempts` | int | 3 | Maximum LLM retry attempts |
| `global_timeout_seconds` | float | 120.0 | Total timeout for fix operation |
| `validate_after_deterministic` | bool | True | Run validation after deterministic fixes |
| `validate_after_llm` | bool | True | Run validation after LLM fixes |
| `enable_rollback` | bool | True | Enable rollback on score degradation |

### OrchestratorResult

Result of the repair pipeline.

```python
@dataclass
class OrchestratorResult:
    success: bool              # True if fixes improved the HTML
    original_html: str         # HTML before fixes
    fixed_html: str            # Best HTML found
    final_score: float         # Validation score (0.0-1.0)
    phases_completed: List[FixPhase]
    errors_fixed: int
    errors_remaining: int
    validation_passed: bool    # True if score >= 0.9
    metrics: OrchestratorMetrics
    error_message: Optional[str]
    history: List[HistoryEntry]

    @property
    def fix_rate(self) -> float  # Percentage of errors fixed
```

### RuleEngine

Deterministic rule engine for applying Tailwind class fixes.

```python
from html_fixer.fixers.deterministic import create_default_engine

engine = create_default_engine()
patch_set = engine.apply_rules(classified_errors)
```

### TailwindInjector

Applies TailwindPatch objects to HTML.

```python
from html_fixer.fixers.tailwind_injector import TailwindInjector

injector = TailwindInjector()
result = injector.inject(html, patches)
```

### ErrorType

Enum of classified error types.

| Error Type | Deterministic | Description |
|------------|---------------|-------------|
| `INVISIBLE_OPACITY` | Yes | Element hidden by opacity: 0 |
| `INVISIBLE_DISPLAY` | Yes | Element hidden by display: none |
| `INVISIBLE_VISIBILITY` | Yes | Element hidden by visibility: hidden |
| `ZINDEX_CONFLICT` | Yes | Z-index stacking issue |
| `ZINDEX_MISSING` | Yes | Missing z-index on positioned element |
| `POINTER_BLOCKED` | Yes | Pointer events blocked by overlay |
| `POINTER_INTERCEPTED` | Yes | Clicks intercepted by parent |
| `TRANSFORM_3D_HIDDEN` | Yes | 3D transform causing visibility issue |
| `TRANSFORM_OFFSCREEN` | Yes | Transform moving element off-screen |
| `FEEDBACK_TOO_SUBTLE` | Yes | Weak visual feedback |
| `FEEDBACK_MISSING` | No | No feedback (requires LLM) |
| `JS_SYNTAX_ERROR` | No | JavaScript syntax error |
| `JS_MISSING_FUNCTION` | No | Missing JS function |
| `JS_MISSING_DOM_ELEMENT` | No | Missing DOM element reference |
| `JS_UNDEFINED_VARIABLE` | No | Undefined JS variable |
| `UNKNOWN` | No | Unclassified error |

### TailwindPatch

Atomic unit of CSS repair.

```python
@dataclass
class TailwindPatch:
    selector: str              # CSS selector
    add_classes: List[str]     # Classes to add
    remove_classes: List[str]  # Classes to remove
    reason: str                # Human-readable explanation

    def to_dict(self) -> Dict
    def describe(self) -> str
    def merge_with(other: TailwindPatch) -> TailwindPatch
```

### ClassifiedError

An error with full Tailwind context.

```python
@dataclass
class ClassifiedError:
    error_type: ErrorType
    selector: str
    element_tag: str
    tailwind_info: TailwindInfo
    bounding_box: Optional[Dict[str, float]]
    blocking_element: Optional[str]
    confidence: float
    requires_llm: bool
```

## Deterministic Rules

The rule engine includes 6 deterministic rules:

| Rule | Priority | Handles |
|------|----------|---------|
| VisibilityRestoreRule | 5 | INVISIBLE_OPACITY, INVISIBLE_DISPLAY, INVISIBLE_VISIBILITY |
| ZIndexFixRule | 15 | ZINDEX_CONFLICT, ZINDEX_MISSING |
| PointerEventsFixRule | 25 | POINTER_BLOCKED, POINTER_INTERCEPTED |
| PassthroughRule | 26 | POINTER_BLOCKED (blocker element) |
| Transform3DFixRule | 30 | TRANSFORM_3D_HIDDEN, TRANSFORM_OFFSCREEN |
| VisualFeedbackAmplifierRule | 50 | FEEDBACK_TOO_SUBTLE |

## Metrics

```python
from html_fixer.metrics import MetricsCollector, MetricsDashboard

# Collect metrics
collector = MetricsCollector("metrics.jsonl")
collector.record(result, fixture_name="my_fixture")

# Display dashboard
dashboard = MetricsDashboard(collector)
print(dashboard.display())
```

## Examples

### Deterministic-Only Fixing

```python
from html_fixer.fixers.deterministic import create_default_engine
from html_fixer.fixers.tailwind_injector import TailwindInjector
from html_fixer.validators.classification_pipeline import ErrorClassificationPipeline

# Setup
pipeline = ErrorClassificationPipeline()
engine = create_default_engine()
injector = TailwindInjector()

# Classify
result = await pipeline.classify_static(html)
errors = result.errors

# Apply deterministic fixes
patch_set = engine.apply_rules(errors)
injection_result = injector.inject(html, patch_set.patches)

print(f"Applied {len(patch_set.patches)} patches")
```

### With Full Orchestration

```python
from html_fixer.orchestrator import Orchestrator

orchestrator = Orchestrator(
    max_llm_attempts=2,
    global_timeout_seconds=60.0,
)

result = await orchestrator.fix(html)

print(f"Success: {result.success}")
print(f"Score: {result.final_score:.1%}")
print(f"Phases: {[p.value for p in result.phases_completed]}")
print(f"Duration: {result.metrics.total_duration_ms:.0f}ms")
```

### Accessing Metrics

```python
result = await orchestrator.fix(html)
print(f"Duration: {result.metrics.total_duration_ms}ms")
print(f"LLM calls: {result.metrics.llm_calls_made}")
print(f"Tokens used: {result.metrics.llm_tokens_used}")
print(f"Rollbacks: {result.metrics.rollbacks_performed}")
```
