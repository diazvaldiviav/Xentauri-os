# Contributing to HTML Fixer

## Development Setup

```bash
# Clone repository
git clone <repo-url>
cd Jarvis_Cloud

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov
```

## Running Tests

```bash
cd app/ai/scene/custom_layout

# Run all html_fixer tests
python -m pytest html_fixer/tests/ -v

# Run specific test file
python -m pytest html_fixer/tests/test_rules_parametrized.py -v

# Run with coverage
python -m pytest html_fixer/tests/ --cov=html_fixer --cov-report=term-missing

# Run golden set tests
python -m pytest html_fixer/tests/test_golden_set.py -v

# Run performance tests
python -m pytest html_fixer/tests/benchmarks/test_performance.py -v
```

## Project Structure

```
html_fixer/
├── contracts/           # Data structures (ErrorType, TailwindPatch, etc.)
├── fixers/
│   ├── deterministic/   # Rule-based fixes
│   │   ├── base_rule.py
│   │   ├── visibility_rule.py
│   │   ├── zindex_rule.py
│   │   ├── pointer_events_rule.py
│   │   ├── passthrough_rule.py
│   │   ├── transform_3d_rule.py
│   │   └── visual_feedback_rule.py
│   ├── llm/             # LLM-powered fixes
│   └── tailwind_injector.py
├── validators/          # Error classification
│   └── classification_pipeline.py
├── orchestrator/        # Pipeline coordination
├── metrics/             # Metrics collection and dashboard
├── docs/                # Documentation
└── tests/
    ├── fixtures/        # Test HTML fixtures
    ├── benchmarks/      # Performance tests
    ├── test_rules_parametrized.py
    └── test_golden_set.py
```

## Adding a New Deterministic Rule

1. Create rule file in `html_fixer/fixers/deterministic/`:

```python
from typing import List, Union
from ..base_rule import FixRule
from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch
from ...contracts.validation import ClassifiedError


class MyNewRule(FixRule):
    """Description of what this rule fixes."""

    @property
    def handles(self) -> List[ErrorType]:
        return [ErrorType.MY_ERROR_TYPE]

    @property
    def priority(self) -> int:
        return 35  # Choose appropriate priority (lower = runs first)

    def can_fix(self, error: ClassifiedError) -> bool:
        return error.error_type in self.handles

    def generate_fix(
        self, error: ClassifiedError
    ) -> Union[TailwindPatch, List[TailwindPatch]]:
        return TailwindPatch(
            selector=error.selector,
            add_classes=["my-fix-class"],
            remove_classes=[],
            reason="Applied my fix"
        )
```

2. Register in `rule_engine.py`:

```python
from .my_new_rule import MyNewRule

def create_default_engine() -> RuleEngine:
    engine = RuleEngine()
    engine.register_all([
        # ... existing rules
        MyNewRule(),
    ])
    return engine
```

3. Add tests in `test_rules_parametrized.py`:

```python
MY_RULE_CASES = [
    (ErrorType.MY_ERROR_TYPE, {"existing-class"}, ["my-fix-class"], [], "Description"),
]

class TestMyRuleParametrized:
    @pytest.fixture
    def rule(self):
        return MyNewRule()

    @pytest.mark.parametrize(
        "error_type,input_classes,expected_add,expected_remove,description",
        MY_RULE_CASES,
        ids=[case[4] for case in MY_RULE_CASES]
    )
    def test_my_rule_fix(self, rule, error_type, input_classes, expected_add, expected_remove, description):
        error = make_error(error_type, classes=input_classes)
        assert rule.can_fix(error)
        patch = rule.generate_fix(error)
        assert_patch_contains(patch, expected_add, expected_remove)
```

## Adding a New Fixture

1. Create HTML file in `html_fixer/tests/fixtures/<category>/`:

```html
<!--
  Fixture: my_edge_case
  Sprint: 8
  Error Types: POINTER_BLOCKED, ZINDEX_CONFLICT
  Description: Brief description of the bug
  Expected Fix: What the fixer should do
-->
<!DOCTYPE html>
<html>
<head><title>My Edge Case</title></head>
<body>
    <!-- HTML with issues to fix -->
</body>
</html>
```

2. Add to golden set test if it's a regression test.

## Code Style

- Use type hints for all public functions
- Add docstrings with clear descriptions
- Follow existing patterns in the codebase
- Run linting before committing:

```bash
pip install ruff
ruff check html_fixer/
```

## Pull Request Process

1. Create feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass locally:
   ```bash
   python -m pytest html_fixer/tests/ -v
   ```
4. Update documentation if needed
5. Submit PR with clear description

## Testing Guidelines

- **Unit tests**: Test individual rules and components
- **Parametrized tests**: Use pytest.mark.parametrize for multiple scenarios
- **Golden set tests**: Add fixtures for regression testing
- **Performance tests**: Ensure no significant slowdowns

## Error Type Guidelines

When adding new error types:

1. Add to `ErrorType` enum in `contracts/errors.py`
2. Determine if it can be fixed deterministically
3. If deterministic, create a rule
4. If LLM-required, document the approach
5. Add test cases

## Metrics

Track metrics when running fixes:

```python
from html_fixer.metrics import MetricsCollector

collector = MetricsCollector("metrics.jsonl")
collector.record(result, fixture_name="my_test")
```

View dashboard:

```python
from html_fixer.metrics import MetricsDashboard

dashboard = MetricsDashboard(collector)
print(dashboard.display())
```
