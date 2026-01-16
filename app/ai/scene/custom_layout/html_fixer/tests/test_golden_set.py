"""
Golden set regression tests.
Sprint 8 - Ensures fixes don't regress on known-good fixtures.

The golden set consists of HTML fixtures that the fixer should be able to
improve consistently. We track pass rate over time to catch regressions.
"""

import pytest
from pathlib import Path
from typing import List, Dict, Any

from html_fixer.fixers.deterministic import create_default_engine
from html_fixer.fixers.tailwind_injector import TailwindInjector
from html_fixer.validators.classification_pipeline import ErrorClassificationPipeline


# Paths to fixture directories
FIXTURES_ROOT = Path(__file__).parent.parent.parent / "tests" / "fixtures"
EDGE_CASES_DIR = Path(__file__).parent / "fixtures" / "edge_cases"

# Expected minimum pass rate for the golden set
EXPECTED_PASS_RATE = 0.70  # 70% minimum for deterministic-only fixes


class GoldenSetFixture:
    """Represents a fixture in the golden set."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem.replace("_broken", "")
        self.html = path.read_text()
        self.category = path.parent.name

    @property
    def is_broken(self) -> bool:
        return "_broken" in self.path.name


def discover_golden_fixtures() -> List[GoldenSetFixture]:
    """Discover all fixtures that should be in the golden set."""
    fixtures = []

    # Include trivia fixtures (known working from previous sprints)
    if FIXTURES_ROOT.exists():
        for category_dir in FIXTURES_ROOT.iterdir():
            if category_dir.is_dir():
                for html_file in category_dir.glob("*_broken.html"):
                    fixtures.append(GoldenSetFixture(html_file))

    # Include edge case fixtures
    if EDGE_CASES_DIR.exists():
        for html_file in EDGE_CASES_DIR.glob("*.html"):
            fixtures.append(GoldenSetFixture(html_file))

    return fixtures


# Discover fixtures at module load time
GOLDEN_FIXTURES = discover_golden_fixtures()
FIXTURE_NAMES = [f.name for f in GOLDEN_FIXTURES]


class TestGoldenSetDeterministic:
    """
    Golden set tests using only deterministic fixes.

    These tests verify that the deterministic rule engine can improve
    HTML fixtures without requiring LLM assistance.
    """

    @pytest.fixture
    def pipeline(self):
        return ErrorClassificationPipeline()

    @pytest.fixture
    def engine(self):
        return create_default_engine()

    @pytest.fixture
    def injector(self):
        return TailwindInjector()

    @pytest.mark.asyncio
    async def test_golden_set_deterministic_pass_rate(
        self, pipeline, engine, injector
    ):
        """Verify overall pass rate meets threshold."""
        if not GOLDEN_FIXTURES:
            pytest.skip("No golden fixtures found")

        results = []

        for fixture in GOLDEN_FIXTURES:
            # Classify errors
            classification_result = await pipeline.classify_static(fixture.html)
            errors = classification_result.errors if hasattr(classification_result, 'errors') else []

            if not errors:
                # No errors found = already passing
                results.append({
                    "fixture": fixture.name,
                    "passed": True,
                    "errors_before": 0,
                    "errors_after": 0,
                    "improvement": 0,
                })
                continue

            # Apply deterministic fixes
            patch_set = engine.apply_rules(errors)

            if not patch_set.patches:
                # No patches generated
                results.append({
                    "fixture": fixture.name,
                    "passed": False,
                    "errors_before": len(errors),
                    "errors_after": len(errors),
                    "improvement": 0,
                })
                continue

            # Inject patches
            injection_result = injector.inject(fixture.html, patch_set.patches)

            if not injection_result.success:
                results.append({
                    "fixture": fixture.name,
                    "passed": False,
                    "errors_before": len(errors),
                    "errors_after": len(errors),
                    "improvement": 0,
                })
                continue

            # Re-classify to check improvement
            re_classification = await pipeline.classify_static(injection_result.html)
            new_errors = re_classification.errors if hasattr(re_classification, 'errors') else []

            improvement = len(errors) - len(new_errors)
            passed = improvement > 0 or len(new_errors) == 0

            results.append({
                "fixture": fixture.name,
                "passed": passed,
                "errors_before": len(errors),
                "errors_after": len(new_errors),
                "improvement": improvement,
            })

        # Calculate pass rate
        passed_count = sum(1 for r in results if r["passed"])
        pass_rate = passed_count / len(results) if results else 0

        # Report results
        print(f"\n{'='*60}")
        print(f"GOLDEN SET RESULTS ({len(results)} fixtures)")
        print(f"{'='*60}")
        for r in sorted(results, key=lambda x: (not x["passed"], x["fixture"])):
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['fixture']}: {r['errors_before']} -> {r['errors_after']}")
        print(f"{'='*60}")
        print(f"Pass Rate: {pass_rate:.1%} (threshold: {EXPECTED_PASS_RATE:.1%})")
        print(f"{'='*60}\n")

        # Assert pass rate meets threshold
        assert pass_rate >= EXPECTED_PASS_RATE, \
            f"Golden set pass rate {pass_rate:.1%} < {EXPECTED_PASS_RATE:.1%}"


class TestIndividualGoldenFixtures:
    """Individual tests for critical golden fixtures."""

    @pytest.fixture
    def pipeline(self):
        return ErrorClassificationPipeline()

    @pytest.fixture
    def engine(self):
        return create_default_engine()

    @pytest.fixture
    def injector(self):
        return TailwindInjector()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fixture_name", [
        "flashcard_3d",
        "multiple_choice",
        "quiz_modal",
    ], ids=lambda x: x)
    async def test_trivia_fixture(
        self, pipeline, engine, injector, fixture_name
    ):
        """Test individual trivia fixtures."""
        fixture_path = FIXTURES_ROOT / "trivia" / f"{fixture_name}_broken.html"

        if not fixture_path.exists():
            pytest.skip(f"Fixture {fixture_name} not found")

        html = fixture_path.read_text()

        # Classify and fix
        classification = await pipeline.classify_static(html)
        errors = classification.errors if hasattr(classification, 'errors') else []

        if errors:
            patch_set = engine.apply_rules(errors)
            if patch_set.patches:
                result = injector.inject(html, patch_set.patches)
                assert result.success, f"Injection failed for {fixture_name}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fixture_name", [
        "deeply_nested",
        "scroll_container",
        "svg_interactive",
    ], ids=lambda x: x)
    async def test_edge_case_fixture(
        self, pipeline, engine, injector, fixture_name
    ):
        """Test individual edge case fixtures."""
        fixture_path = EDGE_CASES_DIR / f"{fixture_name}.html"

        if not fixture_path.exists():
            pytest.skip(f"Fixture {fixture_name} not found")

        html = fixture_path.read_text()

        # Classify errors
        classification = await pipeline.classify_static(html)
        errors = classification.errors if hasattr(classification, 'errors') else []

        # Should detect some errors in edge cases
        # (they're designed to have visibility/interaction issues)
        if errors:
            patch_set = engine.apply_rules(errors)
            # Edge cases should generate some patches
            if patch_set.patches:
                result = injector.inject(html, patch_set.patches)
                assert result.success


class TestGoldenSetMetrics:
    """Tests for golden set metrics tracking."""

    def test_fixture_discovery(self):
        """Test that we discover the expected fixtures."""
        fixtures = discover_golden_fixtures()

        # Should have at least edge case fixtures
        assert len(fixtures) >= 10, \
            f"Expected at least 10 fixtures, found {len(fixtures)}"

    def test_fixture_categories(self):
        """Test that fixtures are from expected categories."""
        fixtures = discover_golden_fixtures()
        categories = set(f.category for f in fixtures)

        # Should have edge_cases at minimum
        assert "edge_cases" in categories


class TestRegressionPrevention:
    """Tests to prevent specific regressions."""

    @pytest.fixture
    def engine(self):
        return create_default_engine()

    @pytest.fixture
    def injector(self):
        return TailwindInjector()

    def test_opacity_fix_regression(self, engine, injector):
        """Ensure opacity-0 is consistently fixed."""
        from html_fixer.contracts.errors import ErrorType
        from html_fixer.contracts.validation import ClassifiedError, TailwindInfo

        error = ClassifiedError(
            error_type=ErrorType.INVISIBLE_OPACITY,
            selector=".btn",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"opacity-0", "bg-blue-500"}),
        )

        patch_set = engine.apply_rules([error])

        assert len(patch_set.patches) >= 1
        patch = patch_set.patches[0]
        assert "opacity-100" in patch.add_classes
        assert "opacity-0" in patch.remove_classes

    def test_zindex_fix_regression(self, engine, injector):
        """Ensure z-index conflicts are consistently fixed."""
        from html_fixer.contracts.errors import ErrorType
        from html_fixer.contracts.validation import ClassifiedError, TailwindInfo

        error = ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector=".btn",
            element_tag="button",
            tailwind_info=TailwindInfo(
                all_classes={"z-10", "relative"},
                z_index=10,
                has_relative=True,
            ),
            confidence=0.9,
        )

        patch_set = engine.apply_rules([error])

        assert len(patch_set.patches) >= 1
        patch = patch_set.patches[0]
        # Should elevate z-index
        assert any(c.startswith("z-") for c in patch.add_classes)

    def test_pointer_events_fix_regression(self, engine, injector):
        """Ensure pointer-events issues are consistently fixed."""
        from html_fixer.contracts.errors import ErrorType
        from html_fixer.contracts.validation import ClassifiedError, TailwindInfo

        error = ClassifiedError(
            error_type=ErrorType.POINTER_BLOCKED,
            selector=".btn",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"bg-blue-500"}),
            blocking_element=".overlay",
        )

        patch_set = engine.apply_rules([error])

        assert len(patch_set.patches) >= 1
        # Should add pointer-events-auto to target
        target_patches = [p for p in patch_set.patches if p.selector == ".btn"]
        assert len(target_patches) >= 1
        assert "pointer-events-auto" in target_patches[0].add_classes
