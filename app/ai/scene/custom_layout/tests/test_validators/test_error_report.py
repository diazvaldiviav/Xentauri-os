"""
Unit tests for ErrorReport and ErrorReportGenerator.

Tests report generation and JSON serialization.
"""

import json
import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.validators.error_report import ErrorReport, ErrorReportGenerator
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def generator():
    """ErrorReportGenerator instance."""
    return ErrorReportGenerator()


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <html>
    <body>
        <button id="btn1">Click me</button>
        <button id="btn2">Click me too</button>
    </body>
    </html>
    """


@pytest.fixture
def sample_errors():
    """Sample errors for testing."""
    return [
        ClassifiedError(
            error_type=ErrorType.POINTER_BLOCKED,
            selector="#btn1",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=1.0,
            blocking_element="#overlay",
            suggested_classes=["relative", "z-50"],
        ),
        ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector="#btn2",
            element_tag="button",
            tailwind_info=TailwindInfo(),
            confidence=0.9,
            suggested_classes=["z-20"],
        ),
    ]


# ============================================================================
# REPORT GENERATION TESTS
# ============================================================================


class TestReportGeneration:
    """Tests for ErrorReportGenerator.generate()."""

    def test_generate_creates_report(self, generator, sample_html, sample_errors):
        """Should create valid ErrorReport."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
            analysis_time_ms=150.5,
        )

        assert isinstance(report, ErrorReport)
        assert report.total_interactive == 5
        assert report.total_errors == 2
        assert report.analysis_time_ms == 150.5

    def test_generate_computes_hash(self, generator, sample_html, sample_errors):
        """Should compute HTML hash."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        assert len(report.html_hash) == 16
        assert report.html_hash.isalnum()

    def test_generate_has_timestamp(self, generator, sample_html, sample_errors):
        """Should have ISO timestamp."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        assert report.timestamp.endswith("Z")
        assert "T" in report.timestamp

    def test_generate_builds_summary(self, generator, sample_html, sample_errors):
        """Should build error type summary."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        assert "pointer_blocked" in report.summary
        assert report.summary["pointer_blocked"] == 1
        assert "zindex_conflict" in report.summary
        assert report.summary["zindex_conflict"] == 1


# ============================================================================
# REPORT PROPERTIES TESTS
# ============================================================================


class TestReportProperties:
    """Tests for ErrorReport properties."""

    def test_total_errors(self, generator, sample_html, sample_errors):
        """Should count total errors."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )
        assert report.total_errors == 2

    def test_elements_with_errors(self, generator, sample_html, sample_errors):
        """Should count unique elements."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )
        assert report.elements_with_errors == 2

    def test_has_critical_errors_true(self, generator, sample_html, sample_errors):
        """Should detect critical errors."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )
        assert report.has_critical_errors is True

    def test_has_critical_errors_false(self, generator, sample_html):
        """Should return False when no critical errors."""
        errors = [
            ClassifiedError(
                error_type=ErrorType.FEEDBACK_MISSING,
                selector="#btn",
                element_tag="button",
                tailwind_info=TailwindInfo(),
            )
        ]
        report = generator.generate(
            errors=errors,
            html=sample_html,
            total_interactive=5,
        )
        assert report.has_critical_errors is False

    def test_error_rate(self, generator, sample_html, sample_errors):
        """Should calculate error rate."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )
        assert report.error_rate == 0.4  # 2 elements / 5 total

    def test_error_rate_zero_interactive(self, generator, sample_html):
        """Should handle zero interactive elements."""
        report = generator.generate(
            errors=[],
            html=sample_html,
            total_interactive=0,
        )
        assert report.error_rate == 0.0


# ============================================================================
# QUERY METHODS TESTS
# ============================================================================


class TestQueryMethods:
    """Tests for report query methods."""

    def test_get_errors_by_type(self, generator, sample_html, sample_errors):
        """Should filter errors by type."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        blocked = report.get_errors_by_type(ErrorType.POINTER_BLOCKED)
        assert len(blocked) == 1
        assert blocked[0].selector == "#btn1"

    def test_get_errors_for_selector(self, generator, sample_html, sample_errors):
        """Should filter errors by selector."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        btn1_errors = report.get_errors_for_selector("#btn1")
        assert len(btn1_errors) == 1
        assert btn1_errors[0].error_type == ErrorType.POINTER_BLOCKED


# ============================================================================
# JSON SERIALIZATION TESTS
# ============================================================================


class TestJsonSerialization:
    """Tests for JSON serialization."""

    def test_to_json(self, generator, sample_html, sample_errors):
        """Should serialize to JSON string."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        json_str = generator.to_json(report)

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["total_interactive"] == 5
        assert data["total_errors"] == 2

    def test_from_json(self, generator, sample_html, sample_errors):
        """Should deserialize from JSON string."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )
        json_str = generator.to_json(report)

        restored = generator.from_json(json_str)

        assert restored.total_interactive == report.total_interactive
        assert restored.total_errors == report.total_errors
        assert restored.html_hash == report.html_hash

    def test_json_roundtrip(self, generator, sample_html, sample_errors):
        """Should survive JSON roundtrip."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
            analysis_time_ms=100.0,
        )

        json_str = generator.to_json(report)
        restored = generator.from_json(json_str)

        assert restored.timestamp == report.timestamp
        assert len(restored.errors) == len(report.errors)
        assert restored.summary == report.summary


# ============================================================================
# DESCRIBE TESTS
# ============================================================================


class TestDescribe:
    """Tests for describe method."""

    def test_describe_includes_hash(self, generator, sample_html, sample_errors):
        """Should include HTML hash in description."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        description = report.describe()
        assert "HTML Hash:" in description
        assert report.html_hash in description

    def test_describe_includes_counts(self, generator, sample_html, sample_errors):
        """Should include error counts."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        description = report.describe()
        assert "Total Interactive Elements: 5" in description
        assert "Total Errors: 2" in description

    def test_describe_includes_summary(self, generator, sample_html, sample_errors):
        """Should include summary by type."""
        report = generator.generate(
            errors=sample_errors,
            html=sample_html,
            total_interactive=5,
        )

        description = report.describe()
        assert "pointer_blocked" in description
        assert "zindex_conflict" in description
