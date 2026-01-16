"""
Benchmarks for error classification.

Sprint 8: Tests performance of classification pipeline.

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

# Create a conditional benchmark decorator
if not HAS_BENCHMARK:
    def benchmark_mark(group):
        return pytest.mark.skipif(
            not HAS_BENCHMARK,
            reason="pytest-benchmark not installed"
        )
else:
    def benchmark_mark(group):
        return pytest.mark.benchmark(group=group)


class TestStaticClassificationBenchmarks:
    """Benchmarks for static HTML analysis (no browser)."""

    @pytest.fixture
    def parser(self):
        from html_fixer.validators.dom_parser import DOMParser
        return DOMParser()

    @pytest.fixture
    def analyzer(self):
        from html_fixer.validators.tailwind_analyzer import TailwindAnalyzer
        return TailwindAnalyzer()

    @benchmark_mark("classification")
    def test_dom_parser_simple(self, benchmark, parser, benchmark_html_simple):
        """Benchmark DOM parsing on simple HTML."""
        result = benchmark(lambda: parser.parse(benchmark_html_simple))

        assert result is not None

    @benchmark_mark("classification")
    def test_dom_parser_complex(self, benchmark, parser, benchmark_html_complex):
        """Benchmark DOM parsing on complex HTML."""
        result = benchmark(lambda: parser.parse(benchmark_html_complex))

        assert result is not None

    @benchmark_mark("classification")
    def test_tailwind_analyzer_simple(self, benchmark, analyzer, benchmark_html_simple):
        """Benchmark Tailwind analysis on simple HTML."""
        result = benchmark(lambda: analyzer.analyze(benchmark_html_simple))

        assert result is not None

    @benchmark_mark("classification")
    def test_tailwind_analyzer_complex(self, benchmark, analyzer, benchmark_html_complex):
        """Benchmark Tailwind analysis on complex HTML."""
        result = benchmark(lambda: analyzer.analyze(benchmark_html_complex))

        assert result is not None

    # Non-benchmark versions for CI
    def test_dom_parser_basic(self, parser, benchmark_html_complex):
        """Basic DOM parser test (no benchmark)."""
        result = parser.parse(benchmark_html_complex)
        assert result is not None

    def test_tailwind_analyzer_basic(self, analyzer, benchmark_html_complex):
        """Basic Tailwind analyzer test (no benchmark)."""
        result = analyzer.analyze(benchmark_html_complex)
        assert result is not None


class TestClassificationPipelineBenchmarks:
    """Benchmarks for full classification pipeline."""

    @pytest.fixture
    def pipeline(self):
        from html_fixer.validators.classification_pipeline import ErrorClassificationPipeline
        return ErrorClassificationPipeline()

    @benchmark_mark("classification-pipeline")
    def test_static_classification_simple(self, benchmark, pipeline, benchmark_html_simple):
        """Benchmark static classification on simple HTML."""
        import asyncio

        async def classify():
            return await pipeline.classify_static(benchmark_html_simple)

        result = benchmark(lambda: asyncio.run(classify()))

        assert result is not None

    @benchmark_mark("classification-pipeline")
    def test_static_classification_complex(self, benchmark, pipeline, benchmark_html_complex):
        """Benchmark static classification on complex HTML."""
        import asyncio

        async def classify():
            return await pipeline.classify_static(benchmark_html_complex)

        result = benchmark(lambda: asyncio.run(classify()))

        assert result is not None

    # Non-benchmark version for CI
    @pytest.mark.asyncio
    async def test_static_classification_basic(self, pipeline, benchmark_html_complex):
        """Basic classification test (no benchmark)."""
        result = await pipeline.classify_static(benchmark_html_complex)
        assert result is not None


class TestErrorTypeDetectionBenchmarks:
    """Benchmarks for specific error type detection."""

    @pytest.fixture
    def analyzer(self):
        from html_fixer.validators.tailwind_analyzer import TailwindAnalyzer
        return TailwindAnalyzer()

    @benchmark_mark("detection")
    def test_visibility_detection(self, benchmark, analyzer):
        """Benchmark visibility issue detection."""
        html_with_visibility_issues = """
        <div class="container">
            <button class="opacity-0">Hidden 1</button>
            <button class="invisible">Hidden 2</button>
            <button class="hidden">Hidden 3</button>
            <button class="opacity-50">Partial</button>
            <button class="visible">Visible</button>
        </div>
        """

        result = benchmark(lambda: analyzer.analyze(html_with_visibility_issues))

        assert result is not None

    @benchmark_mark("detection")
    def test_zindex_detection(self, benchmark, analyzer):
        """Benchmark z-index issue detection."""
        html_with_zindex_issues = """
        <div class="relative z-10">
            <button class="z-5">Lower</button>
            <div class="absolute inset-0 z-50">Overlay</div>
            <button class="z-20">Higher but blocked</button>
        </div>
        """

        result = benchmark(lambda: analyzer.analyze(html_with_zindex_issues))

        assert result is not None
