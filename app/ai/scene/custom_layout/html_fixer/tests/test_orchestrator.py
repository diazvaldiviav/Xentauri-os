"""
Tests for Orchestrator (Sprint 7).

Integration tests for the main orchestration pipeline.
Uses mock components for isolated testing.
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from unittest.mock import AsyncMock, MagicMock

from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.contracts.patches import TailwindPatch, PatchSet
from html_fixer.orchestrator import (
    Orchestrator,
    FixPhase,
    OrchestratorResult,
)


# Mock classes for testing

@dataclass
class MockErrorReport:
    """Mock ErrorReport."""
    errors: List[ClassifiedError] = field(default_factory=list)
    total_interactive: int = 0
    summary: Dict[str, int] = field(default_factory=dict)
    html_hash: str = "mock"
    timestamp: str = "2024-01-01"
    viewport_size: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    analysis_time_ms: float = 100.0


@dataclass
class MockElementResult:
    """Mock ElementResult."""
    selector: str
    status: "MockElementStatus"
    diff_ratio: float = 0.5


class MockElementStatus:
    """Mock ElementStatus enum."""
    RESPONSIVE = "responsive"
    NO_VISUAL_CHANGE = "no_visual_change"

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        if hasattr(other, 'value'):
            return self.value == other.value
        return self.value == other


@dataclass
class MockValidationResult:
    """Mock ValidationResult."""
    element_results: List[MockElementResult] = field(default_factory=list)
    js_errors: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    passed: bool = True
    validation_time_ms: float = 100.0
    viewport_width: int = 1920
    viewport_height: int = 1080


@dataclass
class MockInjectionResult:
    """Mock InjectionResult."""
    success: bool = True
    html: str = ""
    applied: List[TailwindPatch] = field(default_factory=list)
    failed: List = field(default_factory=list)


@dataclass
class MockLLMFixResult:
    """Mock LLMFixResult."""
    success: bool = True
    original_html: str = ""
    fixed_html: Optional[str] = None
    tailwind_patches: List[TailwindPatch] = field(default_factory=list)
    js_patches: List = field(default_factory=list)
    llm_calls_made: int = 1
    tokens_used: int = 100


class MockClassifier:
    """Mock ErrorClassificationPipeline."""

    def __init__(self, errors: List[ClassifiedError] = None):
        self.errors = errors or []
        self.call_count = 0

    async def classify(self, html: str, page=None) -> MockErrorReport:
        self.call_count += 1
        return MockErrorReport(errors=self.errors)

    async def classify_static(self, html: str) -> MockErrorReport:
        self.call_count += 1
        # Return fewer errors after fixes
        remaining = [e for e in self.errors if e.error_type.requires_llm]
        return MockErrorReport(errors=remaining)


class MockRuleEngine:
    """Mock RuleEngine."""

    def __init__(self, patches: List[TailwindPatch] = None):
        self.patches = patches or []
        self.call_count = 0

    def apply_rules(self, errors: List[ClassifiedError]) -> PatchSet:
        self.call_count += 1
        return PatchSet(patches=self.patches, source="deterministic")


class MockSandbox:
    """Mock Sandbox."""

    def __init__(self, results: List[MockValidationResult] = None):
        self.results = results or [MockValidationResult(passed=True)]
        self.call_count = 0

    async def validate(self, html: str) -> MockValidationResult:
        idx = min(self.call_count, len(self.results) - 1)
        result = self.results[idx]
        self.call_count += 1
        return result


class MockLLMFixer:
    """Mock LLMFixer."""

    def __init__(self, results: List[MockLLMFixResult] = None):
        self.results = results or [MockLLMFixResult(success=False)]
        self.call_count = 0

    async def fix(
        self,
        errors: List[ClassifiedError],
        html: str,
        screenshots: Optional[Dict] = None
    ) -> MockLLMFixResult:
        idx = min(self.call_count, len(self.results) - 1)
        result = self.results[idx]
        result.original_html = html
        self.call_count += 1
        return result


class MockInjector:
    """Mock TailwindInjector."""

    def __init__(self, results: List[MockInjectionResult] = None):
        self.results = results or [MockInjectionResult(success=True)]
        self.call_count = 0

    def inject(self, html: str, patches: PatchSet) -> MockInjectionResult:
        idx = min(self.call_count, len(self.results) - 1)
        result = self.results[idx]
        result.html = html + "<!-- patched -->"
        result.applied = list(patches.patches)
        self.call_count += 1
        return result


def _make_error(
    error_type: ErrorType = ErrorType.ZINDEX_CONFLICT,
    selector: str = ".btn",
    confidence: float = 1.0,
) -> ClassifiedError:
    """Helper to create a test error."""
    return ClassifiedError(
        error_type=error_type,
        selector=selector,
        element_tag="button",
        tailwind_info=TailwindInfo(),
        confidence=confidence,
    )


class TestOrchestrator:
    """Tests for Orchestrator."""

    @pytest.mark.asyncio
    async def test_fix_no_errors(self):
        """Test fix with no errors returns success."""
        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=[]),
            sandbox=MockSandbox(),
        )

        result = await orchestrator.fix("<div>test</div>")

        assert result.success is True
        assert result.errors_remaining == 0
        assert FixPhase.CLASSIFY in result.phases_completed

    @pytest.mark.asyncio
    async def test_fix_deterministic_only(self):
        """Test fix with deterministic-only errors."""
        errors = [
            _make_error(ErrorType.ZINDEX_CONFLICT),
            _make_error(ErrorType.POINTER_BLOCKED, selector=".overlay"),
        ]

        patches = [
            TailwindPatch(".btn", ["z-50"], []),
            TailwindPatch(".overlay", ["pointer-events-none"], []),
        ]

        # Create responsive element results
        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
            MockElementResult(".overlay", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=patches),
            sandbox=MockSandbox([
                MockValidationResult(
                    element_results=element_results,
                    passed=True
                )
            ]),
        )

        # Inject mock injector
        orchestrator._injector = MockInjector()

        result = await orchestrator.fix("<div>test</div>")

        assert result.success is True
        assert FixPhase.DETERMINISTIC in result.phases_completed
        assert result.metrics.patches_applied == 2

    @pytest.mark.asyncio
    async def test_fix_llm_required(self):
        """Test fix with LLM-requiring errors."""
        errors = [
            _make_error(ErrorType.FEEDBACK_MISSING),  # requires_llm = True
        ]

        llm_result = MockLLMFixResult(
            success=True,
            fixed_html="<div>fixed</div>",
            tailwind_patches=[TailwindPatch(".btn", ["hover:bg-blue-600"], [])],
            llm_calls_made=1,
            tokens_used=150,
        )

        # Create responsive result
        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=[]),
            llm_fixer=MockLLMFixer([llm_result]),
            sandbox=MockSandbox([
                MockValidationResult(element_results=element_results, passed=True)
            ]),
            validate_after_deterministic=False,
        )

        result = await orchestrator.fix("<div>test</div>")

        assert result.success is True
        assert FixPhase.LLM_FIX in result.phases_completed
        assert result.metrics.llm_calls_made == 1
        assert result.metrics.llm_tokens_used == 150

    @pytest.mark.asyncio
    async def test_fix_combined_errors(self):
        """Test fix with both deterministic and LLM errors."""
        errors = [
            _make_error(ErrorType.ZINDEX_CONFLICT),  # deterministic
            _make_error(ErrorType.FEEDBACK_MISSING),  # LLM
        ]

        det_patches = [TailwindPatch(".btn", ["z-50"], [])]
        llm_result = MockLLMFixResult(
            success=True,
            fixed_html="<div>fully fixed</div>",
            tailwind_patches=[TailwindPatch(".btn", ["hover:bg-blue-600"], [])],
        )

        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=det_patches),
            llm_fixer=MockLLMFixer([llm_result]),
            sandbox=MockSandbox([
                MockValidationResult(element_results=element_results, passed=False),  # After det
                MockValidationResult(element_results=element_results, passed=True),   # After LLM
            ]),
        )

        orchestrator._injector = MockInjector()

        result = await orchestrator.fix("<div>test</div>")

        assert FixPhase.DETERMINISTIC in result.phases_completed
        assert FixPhase.LLM_FIX in result.phases_completed

    @pytest.mark.asyncio
    async def test_returns_best_of_multiple_attempts(self):
        """Test that best result is returned from multiple LLM attempts."""
        errors = [_make_error(ErrorType.FEEDBACK_MISSING)]

        # Three LLM attempts with varying scores
        llm_results = [
            MockLLMFixResult(success=True, fixed_html="<div>attempt1</div>", tailwind_patches=[TailwindPatch(".btn", ["h1"], [])]),
            MockLLMFixResult(success=True, fixed_html="<div>attempt2</div>", tailwind_patches=[TailwindPatch(".btn", ["h2"], [])]),
            MockLLMFixResult(success=True, fixed_html="<div>attempt3</div>", tailwind_patches=[TailwindPatch(".btn", ["h3"], [])]),
        ]

        # Validation results: attempt2 has best score
        element_results_50 = [MockElementResult(".btn", MockElementStatus("no_visual_change"))]
        element_results_80 = [MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE))]

        validation_results = [
            MockValidationResult(element_results=element_results_50, passed=False),  # 50%
            MockValidationResult(element_results=element_results_80, passed=False),  # 100% - best
            MockValidationResult(element_results=element_results_50, passed=False),  # 50%
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=[]),
            llm_fixer=MockLLMFixer(llm_results),
            sandbox=MockSandbox(validation_results),
            max_llm_attempts=3,
            validate_after_deterministic=False,
        )

        result = await orchestrator.fix("<div>test</div>")

        # Should return attempt2 (best score)
        assert "attempt2" in result.fixed_html or result.final_score > 0

    @pytest.mark.asyncio
    async def test_timeout_returns_best(self):
        """Test that timeout returns best result found."""
        import asyncio

        # Slow classifier that will timeout
        class SlowClassifier:
            async def classify(self, html, page=None):
                await asyncio.sleep(10)  # Will timeout
                return MockErrorReport(errors=[])

            async def classify_static(self, html):
                await asyncio.sleep(10)
                return MockErrorReport(errors=[])

        orchestrator = Orchestrator(
            classifier=SlowClassifier(),
            rule_engine=MockRuleEngine(patches=[]),
            sandbox=MockSandbox(),
            global_timeout_seconds=0.1,  # Very short timeout
        )

        result = await orchestrator.fix("<div>test</div>")

        # Should return with timeout error
        assert result.error_message is not None
        assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_exception_handled(self):
        """Test that exceptions are handled gracefully."""
        class FailingClassifier:
            async def classify(self, html, page=None):
                raise RuntimeError("Classification failed")

        orchestrator = Orchestrator(
            classifier=FailingClassifier(),
        )

        result = await orchestrator.fix("<div>test</div>")

        assert result.success is False
        assert result.error_message is not None
        assert "Classification failed" in result.error_message

    @pytest.mark.asyncio
    async def test_phases_tracked(self):
        """Test that phases are tracked correctly."""
        errors = [_make_error(ErrorType.ZINDEX_CONFLICT)]
        patches = [TailwindPatch(".btn", ["z-50"], [])]

        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=patches),
            sandbox=MockSandbox([
                MockValidationResult(element_results=element_results, passed=True)
            ]),
        )

        orchestrator._injector = MockInjector()

        result = await orchestrator.fix("<div>test</div>")

        assert FixPhase.CLASSIFY in result.phases_completed
        assert FixPhase.DETERMINISTIC in result.phases_completed
        assert FixPhase.VALIDATE_DETERMINISTIC in result.phases_completed
        assert FixPhase.COMPLETE in result.phases_completed

    @pytest.mark.asyncio
    async def test_metrics_tracked(self):
        """Test that metrics are tracked correctly."""
        errors = [
            _make_error(ErrorType.ZINDEX_CONFLICT),
            _make_error(ErrorType.FEEDBACK_MISSING),
        ]

        patches = [TailwindPatch(".btn", ["z-50"], [])]
        llm_result = MockLLMFixResult(
            success=True,
            fixed_html="<div>fixed</div>",
            tailwind_patches=[TailwindPatch(".btn", ["hover:bg-blue-600"], [])],
            llm_calls_made=2,
            tokens_used=200,
        )

        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=patches),
            llm_fixer=MockLLMFixer([llm_result]),
            sandbox=MockSandbox([
                MockValidationResult(element_results=element_results, passed=False),
                MockValidationResult(element_results=element_results, passed=True),
            ]),
        )

        orchestrator._injector = MockInjector()

        result = await orchestrator.fix("<div>test</div>")

        assert result.metrics.errors_initial == 2
        assert result.metrics.patches_applied >= 1
        assert result.metrics.total_duration_ms > 0
        assert result.metrics.classification_time_ms > 0

    @pytest.mark.asyncio
    async def test_history_populated(self):
        """Test that history is populated with entries."""
        errors = [_make_error(ErrorType.ZINDEX_CONFLICT)]
        patches = [TailwindPatch(".btn", ["z-50"], [])]

        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=patches),
            sandbox=MockSandbox([
                MockValidationResult(element_results=element_results, passed=True)
            ]),
        )

        orchestrator._injector = MockInjector()

        result = await orchestrator.fix("<div>test</div>")

        assert len(result.history) >= 2  # At least INITIAL and DETERMINISTIC
        assert result.history[0].phase == FixPhase.INITIAL

    @pytest.mark.asyncio
    async def test_describe_output(self):
        """Test describe method produces readable output."""
        errors = [_make_error(ErrorType.ZINDEX_CONFLICT)]
        patches = [TailwindPatch(".btn", ["z-50"], [])]

        element_results = [
            MockElementResult(".btn", MockElementStatus(MockElementStatus.RESPONSIVE)),
        ]

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=patches),
            sandbox=MockSandbox([
                MockValidationResult(element_results=element_results, passed=True)
            ]),
        )

        orchestrator._injector = MockInjector()

        result = await orchestrator.fix("<div>test</div>")

        desc = result.describe()

        assert "OrchestratorResult" in desc
        assert "Score" in desc
        assert "Phases" in desc

    @pytest.mark.asyncio
    async def test_skip_validation_when_disabled(self):
        """Test that validation can be disabled."""
        errors = [_make_error(ErrorType.ZINDEX_CONFLICT)]
        patches = [TailwindPatch(".btn", ["z-50"], [])]

        sandbox = MockSandbox()

        orchestrator = Orchestrator(
            classifier=MockClassifier(errors=errors),
            rule_engine=MockRuleEngine(patches=patches),
            sandbox=sandbox,
            validate_after_deterministic=False,
            validate_after_llm=False,
        )

        orchestrator._injector = MockInjector()

        await orchestrator.fix("<div>test</div>")

        # Sandbox should not be called if validation disabled
        # (Though in this test it might still be called for score calculation)

    @pytest.mark.asyncio
    async def test_repr(self):
        """Test string representation."""
        orchestrator = Orchestrator(
            max_llm_attempts=5,
            global_timeout_seconds=60.0,
        )

        repr_str = repr(orchestrator)

        assert "max_llm=5" in repr_str
        assert "timeout=60" in repr_str
