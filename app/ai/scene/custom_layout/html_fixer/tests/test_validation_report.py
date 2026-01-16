"""
Tests for ValidationReport (Sprint 5).

Tests the validation report generation.
"""

import json
import pytest
from html_fixer.sandbox.validation_report import (
    ValidationReport,
    ValidationReportGenerator,
    ElementReport,
)
from html_fixer.sandbox.contracts import (
    ValidationResult,
    ElementResult,
    ElementStatus,
)
from html_fixer.sandbox.result_classifier import (
    InteractionClassification,
    ClassificationResult,
)
from html_fixer.sandbox.diff_engine import ComparisonScale


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_success_rate_calculation(self):
        """Test success rate with mixed results."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=True,
            total_elements=10,
            responsive_count=6,
            navigation_count=2,
            cascade_count=1,
            weak_feedback_count=0,
            no_response_count=1,
        )

        # 6 + 2 + 1 = 9 passing out of 10
        assert report.success_rate == 0.9

    def test_empty_report(self):
        """Test empty report has 100% success rate."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=True,
            total_elements=0,
            responsive_count=0,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=0,
            no_response_count=0,
        )

        assert report.success_rate == 1.0

    def test_failed_count(self):
        """Test failed_count property."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=False,
            total_elements=10,
            responsive_count=6,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=2,
            no_response_count=2,
        )

        assert report.failed_count == 4

    def test_summary_property(self):
        """Test summary property."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=True,
            total_elements=10,
            responsive_count=5,
            navigation_count=2,
            cascade_count=1,
            weak_feedback_count=1,
            no_response_count=1,
        )

        summary = report.summary
        assert summary["responsive"] == 5
        assert summary["navigation"] == 2
        assert summary["cascade_effect"] == 1
        assert summary["weak_feedback"] == 1
        assert summary["no_response"] == 1

    def test_to_json(self):
        """Test JSON serialization."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=True,
            total_elements=5,
            responsive_count=5,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=0,
            no_response_count=0,
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert parsed["html_hash"] == "abc123"
        assert parsed["passed"] is True
        assert parsed["total_elements"] == 5

    def test_to_dict(self):
        """Test dictionary conversion."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=True,
            total_elements=5,
            responsive_count=5,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=0,
            no_response_count=0,
            js_errors=["error1"],
            validation_time_ms=1500.0,
        )

        d = report.to_dict()

        assert d["html_hash"] == "abc123"
        assert d["passed"] is True
        assert d["js_errors"] == ["error1"]
        assert d["validation_time_ms"] == 1500.0

    def test_describe(self):
        """Test human-readable description."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=False,
            total_elements=5,
            responsive_count=3,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=1,
            no_response_count=1,
            validation_time_ms=1500.0,
        )

        desc = report.describe()

        assert "FAILED" in desc
        assert "RESPONSIVE: 3" in desc
        assert "NO_RESPONSE: 1" in desc
        assert "1500ms" in desc

    def test_describe_passed(self):
        """Test description for passed report."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=True,
            total_elements=5,
            responsive_count=5,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=0,
            no_response_count=0,
        )

        desc = report.describe()
        assert "PASSED" in desc

    def test_get_failing_elements(self):
        """Test getting failing elements."""
        report = ValidationReport(
            html_hash="abc123",
            timestamp="2024-01-01T00:00:00Z",
            passed=False,
            total_elements=3,
            responsive_count=1,
            navigation_count=0,
            cascade_count=0,
            weak_feedback_count=1,
            no_response_count=1,
            element_reports=[
                ElementReport(
                    selector=".btn1",
                    tag="button",
                    status=ElementStatus.RESPONSIVE,
                    classification=InteractionClassification.RESPONSIVE,
                    diff_ratios={},
                    bounding_box={},
                    reasoning="",
                    screenshots_saved=False,
                    screenshot_paths={},
                ),
                ElementReport(
                    selector=".btn2",
                    tag="button",
                    status=ElementStatus.NO_VISUAL_CHANGE,
                    classification=InteractionClassification.WEAK_FEEDBACK,
                    diff_ratios={},
                    bounding_box={},
                    reasoning="",
                    screenshots_saved=False,
                    screenshot_paths={},
                ),
                ElementReport(
                    selector=".btn3",
                    tag="button",
                    status=ElementStatus.NO_VISUAL_CHANGE,
                    classification=InteractionClassification.NO_RESPONSE,
                    diff_ratios={},
                    bounding_box={},
                    reasoning="",
                    screenshots_saved=False,
                    screenshot_paths={},
                ),
            ],
        )

        failing = report.get_failing_elements()
        assert len(failing) == 2
        assert failing[0].selector == ".btn2"
        assert failing[1].selector == ".btn3"

    def test_from_dict(self):
        """Test creating report from dictionary."""
        data = {
            "html_hash": "abc123",
            "timestamp": "2024-01-01T00:00:00Z",
            "passed": True,
            "total_elements": 5,
            "summary": {
                "responsive": 4,
                "navigation": 1,
                "cascade_effect": 0,
                "weak_feedback": 0,
                "no_response": 0,
            },
            "js_errors": [],
            "viewport_size": {"width": 1920, "height": 1080},
            "validation_time_ms": 1000.0,
        }

        report = ValidationReport.from_dict(data)

        assert report.html_hash == "abc123"
        assert report.passed is True
        assert report.responsive_count == 4
        assert report.navigation_count == 1


class TestValidationReportGenerator:
    """Tests for ValidationReportGenerator."""

    def test_generate_from_validation_result(self):
        """Test generating report from ValidationResult."""
        generator = ValidationReportGenerator()

        validation_result = ValidationResult(
            element_results=[
                ElementResult(".btn1", ElementStatus.RESPONSIVE, diff_ratio=0.05),
                ElementResult(".btn2", ElementStatus.NO_VISUAL_CHANGE, diff_ratio=0.0),
            ],
            js_errors=[],
            validation_time_ms=500.0,
        )

        html = "<html><body><button class='btn1'>Test</button></body></html>"

        report = generator.generate(validation_result, html)

        assert report.total_elements == 2
        assert report.html_hash is not None
        assert len(report.html_hash) == 16

    def test_generate_with_classifications(self):
        """Test generating report with explicit classifications."""
        generator = ValidationReportGenerator()

        validation_result = ValidationResult(
            element_results=[
                ElementResult(".btn1", ElementStatus.RESPONSIVE, diff_ratio=0.05),
            ],
            js_errors=[],
            validation_time_ms=500.0,
        )

        classifications = {
            ".btn1": ClassificationResult(
                classification=InteractionClassification.RESPONSIVE,
                confidence=0.95,
                reasoning="Test",
                primary_scale=ComparisonScale.TIGHT,
                diff_ratios={"tight": 0.05, "local": 0.02, "global": 0.01},
            ),
        }

        html = "<html><body><button class='btn1'>Test</button></body></html>"

        report = generator.generate(validation_result, html, classifications=classifications)

        assert report.responsive_count == 1
        assert report.element_reports[0].reasoning == "Test"

    def test_generate_pass_threshold(self):
        """Test pass threshold affects result."""
        generator = ValidationReportGenerator(pass_threshold=0.9)

        # 80% success rate (below 90% threshold)
        validation_result = ValidationResult(
            element_results=[
                ElementResult(".btn1", ElementStatus.RESPONSIVE, diff_ratio=0.05),
                ElementResult(".btn2", ElementStatus.RESPONSIVE, diff_ratio=0.05),
                ElementResult(".btn3", ElementStatus.RESPONSIVE, diff_ratio=0.05),
                ElementResult(".btn4", ElementStatus.RESPONSIVE, diff_ratio=0.05),
                ElementResult(".btn5", ElementStatus.NO_VISUAL_CHANGE, diff_ratio=0.0),
            ],
            js_errors=[],
        )

        html = "<html><body>Test</body></html>"

        report = generator.generate(validation_result, html)

        assert report.passed is False  # 80% < 90% threshold

    def test_generate_with_js_errors(self):
        """Test report fails with JS errors."""
        generator = ValidationReportGenerator()

        validation_result = ValidationResult(
            element_results=[
                ElementResult(".btn1", ElementStatus.RESPONSIVE, diff_ratio=0.05),
            ],
            js_errors=["TypeError: x is not defined"],
            validation_time_ms=500.0,
        )

        html = "<html><body>Test</body></html>"

        report = generator.generate(validation_result, html)

        assert report.passed is False
        assert len(report.js_errors) == 1

    def test_generate_includes_viewport(self):
        """Test report includes viewport dimensions."""
        generator = ValidationReportGenerator()

        validation_result = ValidationResult(
            element_results=[],
            js_errors=[],
            viewport_width=1280,
            viewport_height=720,
        )

        html = "<html><body>Test</body></html>"

        report = generator.generate(validation_result, html)

        assert report.viewport_size["width"] == 1280
        assert report.viewport_size["height"] == 720


class TestElementReport:
    """Tests for ElementReport dataclass."""

    def test_to_dict(self):
        """Test serialization."""
        report = ElementReport(
            selector=".btn",
            tag="button",
            status=ElementStatus.RESPONSIVE,
            classification=InteractionClassification.RESPONSIVE,
            diff_ratios={"tight": 0.05, "local": 0.02, "global": 0.01},
            bounding_box={"x": 10, "y": 20, "width": 100, "height": 40},
            reasoning="Clear visual feedback",
            screenshots_saved=True,
            screenshot_paths={"before": "/tmp/before.png", "after": "/tmp/after.png"},
        )

        d = report.to_dict()

        assert d["selector"] == ".btn"
        assert d["status"] == "responsive"
        assert d["classification"] == "responsive"
        assert d["diff_ratios"]["tight"] == 0.05
        assert d["screenshots"]["before"] == "/tmp/before.png"

    def test_to_dict_without_screenshots(self):
        """Test serialization without screenshots."""
        report = ElementReport(
            selector=".btn",
            tag="button",
            status=ElementStatus.RESPONSIVE,
            classification=InteractionClassification.RESPONSIVE,
            diff_ratios={},
            bounding_box={},
            reasoning="",
            screenshots_saved=False,
            screenshot_paths={},
        )

        d = report.to_dict()

        assert d["screenshots"] == {}
