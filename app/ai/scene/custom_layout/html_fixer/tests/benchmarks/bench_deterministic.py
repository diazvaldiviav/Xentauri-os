"""
Benchmarks for deterministic fixes.

Sprint 8: Tests performance of RuleEngine and TailwindInjector.

Note: Install pytest-benchmark for actual benchmarking:
    pip install pytest-benchmark

Run benchmarks with:
    python -m pytest html_fixer/tests/benchmarks/ --benchmark-only -v
"""

import pytest

# Check if pytest-benchmark is available
try:
    import pytest_benchmark
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False

# Create a no-op benchmark decorator if pytest-benchmark is not installed
if not HAS_BENCHMARK:
    def benchmark_mark(group):
        return pytest.mark.skipif(
            not HAS_BENCHMARK,
            reason="pytest-benchmark not installed"
        )
else:
    def benchmark_mark(group):
        return pytest.mark.benchmark(group=group)


class TestRuleEngineBenchmarks:
    """Benchmarks for the deterministic RuleEngine."""

    @pytest.fixture
    def engine(self):
        from html_fixer.fixers.deterministic import create_default_engine
        return create_default_engine()

    @benchmark_mark("deterministic")
    def test_rule_engine_single_error(self, benchmark, engine, benchmark_errors):
        """Benchmark applying rules to a single error."""
        single_error = [benchmark_errors[0]]

        result = benchmark(lambda: engine.apply_rules(single_error))

        assert len(result.patches) >= 1

    @benchmark_mark("deterministic")
    def test_rule_engine_multiple_errors(self, benchmark, engine, benchmark_errors):
        """Benchmark applying rules to multiple errors."""
        result = benchmark(lambda: engine.apply_rules(benchmark_errors))

        assert len(result.patches) >= 1

    @benchmark_mark("deterministic")
    def test_rule_engine_scaled(self, benchmark, engine, benchmark_errors):
        """Benchmark with scaled error count (10x)."""
        scaled_errors = benchmark_errors * 10  # 70 errors

        result = benchmark(lambda: engine.apply_rules(scaled_errors))

        assert result is not None

    # Non-benchmark version for CI without pytest-benchmark
    def test_rule_engine_basic(self, engine, benchmark_errors):
        """Basic test for rule engine (no benchmark)."""
        result = engine.apply_rules(benchmark_errors)
        assert len(result.patches) >= 1


class TestTailwindInjectorBenchmarks:
    """Benchmarks for TailwindInjector."""

    @pytest.fixture
    def injector(self):
        from html_fixer.fixers.tailwind_injector import TailwindInjector
        return TailwindInjector()

    @pytest.fixture
    def sample_patches(self):
        from html_fixer.contracts.patches import TailwindPatch
        return [
            TailwindPatch(
                selector=".option-btn:nth-child(1)",
                add_classes=["opacity-100"],
                remove_classes=["opacity-0"],
                reason="Fix visibility"
            ),
            TailwindPatch(
                selector=".option-btn:nth-child(2)",
                add_classes=["visible"],
                remove_classes=["invisible"],
                reason="Fix visibility"
            ),
            TailwindPatch(
                selector=".overlay",
                add_classes=["pointer-events-none"],
                remove_classes=[],
                reason="Make overlay pass-through"
            ),
        ]

    @benchmark_mark("injection")
    def test_injector_simple_html(self, benchmark, injector, benchmark_html_simple, sample_patches):
        """Benchmark injection on simple HTML."""
        single_patch = [sample_patches[0]]

        result = benchmark(lambda: injector.inject(benchmark_html_simple, single_patch))

        assert result.success

    @benchmark_mark("injection")
    def test_injector_medium_html(self, benchmark, injector, benchmark_html_medium, sample_patches):
        """Benchmark injection on medium complexity HTML."""
        result = benchmark(lambda: injector.inject(benchmark_html_medium, sample_patches))

        assert result.success

    @benchmark_mark("injection")
    def test_injector_complex_html(self, benchmark, injector, benchmark_html_complex, sample_patches):
        """Benchmark injection on complex HTML."""
        result = benchmark(lambda: injector.inject(benchmark_html_complex, sample_patches))

        assert result.success

    @benchmark_mark("injection")
    def test_injector_many_patches(self, benchmark, injector, benchmark_html_complex, sample_patches):
        """Benchmark injection with many patches."""
        many_patches = sample_patches * 5  # 15 patches

        result = benchmark(lambda: injector.inject(benchmark_html_complex, many_patches))

        assert result.success

    # Non-benchmark version for CI
    def test_injector_basic(self, injector, benchmark_html_medium, sample_patches):
        """Basic test for injector (no benchmark)."""
        result = injector.inject(benchmark_html_medium, sample_patches)
        assert result.success


class TestEndToEndDeterministicBenchmarks:
    """End-to-end benchmarks for deterministic fixing."""

    @pytest.fixture
    def engine(self):
        from html_fixer.fixers.deterministic import create_default_engine
        return create_default_engine()

    @pytest.fixture
    def injector(self):
        from html_fixer.fixers.tailwind_injector import TailwindInjector
        return TailwindInjector()

    @benchmark_mark("e2e-deterministic")
    def test_full_deterministic_pipeline(
        self, benchmark, engine, injector, benchmark_html_complex, benchmark_errors
    ):
        """Benchmark full deterministic fix pipeline."""
        def run_pipeline():
            patch_set = engine.apply_rules(benchmark_errors)
            result = injector.inject(benchmark_html_complex, patch_set.patches)
            return result

        result = benchmark(run_pipeline)

        assert result.success

    # Non-benchmark version for CI
    def test_full_deterministic_pipeline_basic(
        self, engine, injector, benchmark_html_complex, benchmark_errors
    ):
        """Basic test for full pipeline (no benchmark)."""
        patch_set = engine.apply_rules(benchmark_errors)
        result = injector.inject(benchmark_html_complex, patch_set.patches)
        assert result.success
