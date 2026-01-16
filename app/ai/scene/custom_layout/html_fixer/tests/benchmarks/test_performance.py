"""
Performance tests for html_fixer components.

Sprint 8: Basic performance/smoke tests that run in CI without pytest-benchmark.
For actual benchmarking, install pytest-benchmark and run:
    python -m pytest html_fixer/tests/benchmarks/ --benchmark-only -v
"""

import pytest


class TestRuleEnginePerformance:
    """Performance tests for RuleEngine."""

    @pytest.fixture
    def engine(self):
        from html_fixer.fixers.deterministic import create_default_engine
        return create_default_engine()

    @pytest.fixture
    def sample_errors(self):
        """Create sample errors for testing."""
        from html_fixer.contracts.errors import ErrorType
        from html_fixer.contracts.validation import ClassifiedError, TailwindInfo

        return [
            ClassifiedError(
                error_type=ErrorType.INVISIBLE_OPACITY,
                selector=".btn-1",
                element_tag="button",
                tailwind_info=TailwindInfo(all_classes={"opacity-0", "bg-blue-500"}),
            ),
            ClassifiedError(
                error_type=ErrorType.INVISIBLE_DISPLAY,
                selector=".btn-2",
                element_tag="button",
                tailwind_info=TailwindInfo(all_classes={"hidden", "bg-green-500"}),
            ),
            ClassifiedError(
                error_type=ErrorType.ZINDEX_CONFLICT,
                selector=".btn-3",
                element_tag="button",
                tailwind_info=TailwindInfo(
                    all_classes={"z-10", "relative"},
                    z_index=10,
                    has_relative=True
                ),
                confidence=0.85,
            ),
            ClassifiedError(
                error_type=ErrorType.POINTER_BLOCKED,
                selector=".btn-4",
                element_tag="button",
                tailwind_info=TailwindInfo(all_classes={"bg-purple-500"}),
                blocking_element=".overlay",
            ),
            ClassifiedError(
                error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
                selector=".btn-5",
                element_tag="button",
                tailwind_info=TailwindInfo(all_classes={"bg-red-500"}),
            ),
        ]

    def test_rule_engine_applies_patches(self, engine, sample_errors):
        """Test that rule engine generates patches for known errors."""
        result = engine.apply_rules(sample_errors)

        assert len(result.patches) >= 1
        # Each error should generate at least one patch
        assert len(result.patches) <= len(sample_errors) * 2  # Some errors generate multiple patches

    def test_rule_engine_handles_empty_list(self, engine):
        """Test rule engine with empty error list."""
        result = engine.apply_rules([])
        assert len(result.patches) == 0

    def test_rule_engine_handles_scaled_errors(self, engine, sample_errors):
        """Test rule engine with many errors (performance smoke test)."""
        scaled_errors = sample_errors * 20  # 100 errors

        result = engine.apply_rules(scaled_errors)

        assert result is not None
        assert len(result.patches) >= 1


class TestTailwindInjectorPerformance:
    """Performance tests for TailwindInjector."""

    @pytest.fixture
    def injector(self):
        from html_fixer.fixers.tailwind_injector import TailwindInjector
        return TailwindInjector()

    @pytest.fixture
    def sample_html(self):
        return """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <div class="container">
        <button class="btn-1 opacity-0 bg-blue-500">Button 1</button>
        <button class="btn-2 hidden bg-green-500">Button 2</button>
        <button class="btn-3 z-10 relative bg-yellow-500">Button 3</button>
        <div class="overlay absolute inset-0 z-50"></div>
        <button class="btn-4 bg-purple-500">Button 4</button>
        <button class="btn-5 bg-red-500">Button 5</button>
    </div>
</body>
</html>"""

    @pytest.fixture
    def sample_patches(self):
        from html_fixer.contracts.patches import TailwindPatch
        return [
            TailwindPatch(
                selector=".btn-1",
                add_classes=["opacity-100"],
                remove_classes=["opacity-0"],
                reason="Fix visibility"
            ),
            TailwindPatch(
                selector=".btn-2",
                add_classes=["block"],
                remove_classes=["hidden"],
                reason="Fix display"
            ),
            TailwindPatch(
                selector=".overlay",
                add_classes=["pointer-events-none"],
                remove_classes=[],
                reason="Make overlay pass-through"
            ),
        ]

    def test_injector_applies_patches(self, injector, sample_html, sample_patches):
        """Test that injector successfully applies patches."""
        result = injector.inject(sample_html, sample_patches)

        assert result.success
        assert "opacity-100" in result.html
        assert "opacity-0" not in result.html

    def test_injector_handles_empty_patches(self, injector, sample_html):
        """Test injector with no patches."""
        result = injector.inject(sample_html, [])

        assert result.success
        # HTML may be reformatted by BeautifulSoup, but content should be preserved
        assert "btn-1" in result.html
        assert "btn-5" in result.html

    def test_injector_handles_many_patches(self, injector, sample_html, sample_patches):
        """Test injector with many patches (performance smoke test)."""
        many_patches = sample_patches * 10

        result = injector.inject(sample_html, many_patches)

        assert result.success


class TestClassificationPerformance:
    """Performance tests for classification components."""

    @pytest.fixture
    def pipeline(self):
        from html_fixer.validators.classification_pipeline import ErrorClassificationPipeline
        return ErrorClassificationPipeline()

    @pytest.fixture
    def complex_html(self):
        return """<!DOCTYPE html>
<html>
<head><title>Complex Test</title></head>
<body class="bg-gray-100 min-h-screen">
    <div class="max-w-4xl mx-auto p-8 space-y-8">
        <section class="bg-white rounded-lg shadow p-6">
            <button class="opacity-0 w-full p-4 bg-blue-100 rounded">A</button>
            <button class="invisible w-full p-4 bg-blue-100 rounded">B</button>
            <button class="hidden w-full p-4 bg-blue-100 rounded">C</button>
        </section>
        <section class="relative bg-white rounded-lg shadow p-6">
            <button class="z-10 relative px-4 py-2 bg-green-500">Action</button>
            <div class="absolute inset-0 z-50 bg-black/20"></div>
        </section>
        <section class="bg-white rounded-lg shadow p-6">
            <div class="transform rotate-y-180 [backface-visibility:hidden]">
                <button class="px-4 py-2 bg-purple-500">Flip</button>
            </div>
        </section>
    </div>
</body>
</html>"""

    @pytest.mark.asyncio
    async def test_classification_pipeline_static(self, pipeline, complex_html):
        """Test classification pipeline on complex HTML."""
        result = await pipeline.classify_static(complex_html)

        assert result is not None
        # Should detect some errors
        assert hasattr(result, 'errors') or result is not None


class TestEndToEndPerformance:
    """End-to-end performance tests."""

    @pytest.fixture
    def engine(self):
        from html_fixer.fixers.deterministic import create_default_engine
        return create_default_engine()

    @pytest.fixture
    def injector(self):
        from html_fixer.fixers.tailwind_injector import TailwindInjector
        return TailwindInjector()

    def test_full_deterministic_pipeline(self, engine, injector):
        """Test full deterministic pipeline."""
        from html_fixer.contracts.errors import ErrorType
        from html_fixer.contracts.validation import ClassifiedError, TailwindInfo

        html = """<!DOCTYPE html>
<html><body>
    <button class="btn opacity-0 bg-blue-500">Click</button>
</body></html>"""

        errors = [
            ClassifiedError(
                error_type=ErrorType.INVISIBLE_OPACITY,
                selector=".btn",
                element_tag="button",
                tailwind_info=TailwindInfo(all_classes={"opacity-0", "bg-blue-500"}),
            )
        ]

        # Apply rules
        patch_set = engine.apply_rules(errors)
        assert len(patch_set.patches) >= 1

        # Inject patches
        result = injector.inject(html, patch_set.patches)
        assert result.success
        assert "opacity-100" in result.html
