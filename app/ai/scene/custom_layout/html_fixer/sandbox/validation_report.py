"""
ValidationReport - Comprehensive validation report generation.

Sprint 5: Detailed reports with all metadata for debugging and analysis.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .contracts import ElementResult, ValidationResult, ElementStatus
from .result_classifier import InteractionClassification, ClassificationResult


@dataclass
class ElementReport:
    """Detailed report for a single element."""

    selector: str
    tag: str
    status: ElementStatus
    classification: Optional[InteractionClassification]
    diff_ratios: Dict[str, float]  # tight, local, global
    bounding_box: Dict[str, float]
    reasoning: str
    screenshots_saved: bool
    screenshot_paths: Dict[str, str]  # {before, after, diff}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "selector": self.selector,
            "tag": self.tag,
            "status": self.status.value,
            "classification": (
                self.classification.value if self.classification else None
            ),
            "diff_ratios": self.diff_ratios,
            "bounding_box": self.bounding_box,
            "reasoning": self.reasoning,
            "screenshots": self.screenshot_paths if self.screenshots_saved else {},
        }


@dataclass
class ValidationReport:
    """
    Comprehensive validation report with all metadata.

    Builds on ErrorReport pattern but includes:
    - Multi-scale diff results per element
    - Classification reasoning
    - Screenshot paths
    - Performance metrics
    """

    html_hash: str
    """SHA256 hash of validated HTML (first 16 chars)."""

    timestamp: str
    """ISO format timestamp."""

    passed: bool
    """Overall validation result."""

    total_elements: int
    """Total interactive elements found."""

    responsive_count: int
    """Elements classified as RESPONSIVE."""

    navigation_count: int
    """Elements classified as NAVIGATION."""

    cascade_count: int
    """Elements classified as CASCADE_EFFECT."""

    weak_feedback_count: int
    """Elements classified as WEAK_FEEDBACK."""

    no_response_count: int
    """Elements classified as NO_RESPONSE."""

    element_reports: List[ElementReport] = field(default_factory=list)
    """Detailed report per element."""

    js_errors: List[str] = field(default_factory=list)
    """JavaScript errors captured."""

    viewport_size: Dict[str, int] = field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )
    """Viewport dimensions used."""

    validation_time_ms: float = 0.0
    """Total validation time."""

    diff_engine_config: Dict[str, Any] = field(default_factory=dict)
    """DiffEngine configuration used."""

    screenshots_dir: Optional[str] = None
    """Directory where screenshots were saved."""

    @property
    def success_rate(self) -> float:
        """Percentage of passing elements."""
        if self.total_elements == 0:
            return 1.0
        passing = (
            self.responsive_count +
            self.navigation_count +
            self.cascade_count
        )
        return passing / self.total_elements

    @property
    def failed_count(self) -> int:
        """Number of failing elements."""
        return self.weak_feedback_count + self.no_response_count

    @property
    def summary(self) -> Dict[str, int]:
        """Summary by classification."""
        return {
            "responsive": self.responsive_count,
            "navigation": self.navigation_count,
            "cascade_effect": self.cascade_count,
            "weak_feedback": self.weak_feedback_count,
            "no_response": self.no_response_count,
        }

    def get_failing_elements(self) -> List[ElementReport]:
        """Get elements that failed validation."""
        return [
            e for e in self.element_reports
            if e.classification in (
                InteractionClassification.WEAK_FEEDBACK,
                InteractionClassification.NO_RESPONSE,
            )
        ]

    def get_passing_elements(self) -> List[ElementReport]:
        """Get elements that passed validation."""
        return [
            e for e in self.element_reports
            if e.classification in (
                InteractionClassification.RESPONSIVE,
                InteractionClassification.NAVIGATION,
                InteractionClassification.CASCADE_EFFECT,
            )
        ]

    def describe(self) -> str:
        """Generate human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"ValidationReport ({self.timestamp}): {status}",
            f"  HTML Hash: {self.html_hash}",
            f"  Elements: {self.total_elements}",
            f"  Success Rate: {self.success_rate:.1%}",
            "",
            "  Classification Summary:",
            f"    RESPONSIVE: {self.responsive_count}",
            f"    NAVIGATION: {self.navigation_count}",
            f"    CASCADE_EFFECT: {self.cascade_count}",
            f"    WEAK_FEEDBACK: {self.weak_feedback_count}",
            f"    NO_RESPONSE: {self.no_response_count}",
            "",
            f"  Validation Time: {self.validation_time_ms:.0f}ms",
        ]

        if self.js_errors:
            lines.append(f"  JS Errors: {len(self.js_errors)}")

        if self.screenshots_dir:
            lines.append(f"  Screenshots: {self.screenshots_dir}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "html_hash": self.html_hash,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "total_elements": self.total_elements,
            "success_rate": self.success_rate,
            "summary": self.summary,
            "elements": [e.to_dict() for e in self.element_reports],
            "js_errors": self.js_errors,
            "viewport_size": self.viewport_size,
            "validation_time_ms": self.validation_time_ms,
            "diff_engine_config": self.diff_engine_config,
            "screenshots_dir": self.screenshots_dir,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationReport":
        """Create from dictionary (partial deserialization)."""
        return cls(
            html_hash=data["html_hash"],
            timestamp=data["timestamp"],
            passed=data["passed"],
            total_elements=data["total_elements"],
            responsive_count=data["summary"]["responsive"],
            navigation_count=data["summary"]["navigation"],
            cascade_count=data["summary"]["cascade_effect"],
            weak_feedback_count=data["summary"]["weak_feedback"],
            no_response_count=data["summary"]["no_response"],
            js_errors=data.get("js_errors", []),
            viewport_size=data.get("viewport_size", {"width": 1920, "height": 1080}),
            validation_time_ms=data.get("validation_time_ms", 0.0),
            diff_engine_config=data.get("diff_engine_config", {}),
            screenshots_dir=data.get("screenshots_dir"),
        )


class ValidationReportGenerator:
    """
    Generates ValidationReport from validation results.

    Usage:
        generator = ValidationReportGenerator()
        report = generator.generate(validation_result, html)
    """

    def __init__(self, pass_threshold: float = 0.9):
        """
        Initialize the generator.

        Args:
            pass_threshold: Minimum success rate to pass (default 90%)
        """
        self.pass_threshold = pass_threshold

    def generate(
        self,
        result: ValidationResult,
        html: str,
        classifications: Optional[Dict[str, ClassificationResult]] = None,
        screenshots_dir: Optional[str] = None,
        diff_engine_config: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        """
        Generate comprehensive report from ValidationResult.

        Args:
            result: ValidationResult from sandbox
            html: Original HTML that was validated
            classifications: Optional dict mapping selector -> ClassificationResult
            screenshots_dir: Directory where screenshots are saved
            diff_engine_config: DiffEngine configuration used

        Returns:
            ValidationReport with all details
        """
        html_hash = hashlib.sha256(html.encode()).hexdigest()[:16]
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Initialize counts
        counts = {c: 0 for c in InteractionClassification}
        element_reports = []

        classifications = classifications or {}

        for elem_result in result.element_results:
            # Get classification if available
            class_result = classifications.get(elem_result.selector)

            if class_result:
                classification = class_result.classification
                counts[classification] += 1
                diff_ratios = class_result.diff_ratios
                reasoning = class_result.reasoning
            else:
                # Fallback: infer from status
                classification = self._status_to_classification(elem_result.status)
                counts[classification] += 1
                diff_ratios = {"tight": elem_result.diff_ratio, "local": 0.0, "global": 0.0}
                reasoning = f"Inferred from status: {elem_result.status.value}"

            element_reports.append(ElementReport(
                selector=elem_result.selector,
                tag="unknown",  # Would need ElementInfo
                status=elem_result.status,
                classification=classification,
                diff_ratios=diff_ratios,
                bounding_box={},
                reasoning=reasoning,
                screenshots_saved=screenshots_dir is not None,
                screenshot_paths={},
            ))

        # Determine overall pass/fail
        passing = (
            counts[InteractionClassification.RESPONSIVE] +
            counts[InteractionClassification.NAVIGATION] +
            counts[InteractionClassification.CASCADE_EFFECT]
        )
        total = result.total_elements
        passed = (passing / total >= self.pass_threshold) if total > 0 else True
        passed = passed and not result.has_js_errors

        return ValidationReport(
            html_hash=html_hash,
            timestamp=timestamp,
            passed=passed,
            total_elements=total,
            responsive_count=counts[InteractionClassification.RESPONSIVE],
            navigation_count=counts[InteractionClassification.NAVIGATION],
            cascade_count=counts[InteractionClassification.CASCADE_EFFECT],
            weak_feedback_count=counts[InteractionClassification.WEAK_FEEDBACK],
            no_response_count=counts[InteractionClassification.NO_RESPONSE],
            element_reports=element_reports,
            js_errors=result.js_errors,
            viewport_size={
                "width": result.viewport_width,
                "height": result.viewport_height
            },
            validation_time_ms=result.validation_time_ms,
            diff_engine_config=diff_engine_config or {},
            screenshots_dir=screenshots_dir,
        )

    def _status_to_classification(
        self,
        status: ElementStatus
    ) -> InteractionClassification:
        """
        Map ElementStatus to InteractionClassification (fallback).

        Args:
            status: ElementStatus from validation

        Returns:
            Best-guess InteractionClassification
        """
        mapping = {
            ElementStatus.RESPONSIVE: InteractionClassification.RESPONSIVE,
            ElementStatus.NO_VISUAL_CHANGE: InteractionClassification.NO_RESPONSE,
            ElementStatus.INTERCEPTED: InteractionClassification.NO_RESPONSE,
            ElementStatus.TIMEOUT: InteractionClassification.NO_RESPONSE,
            ElementStatus.ERROR: InteractionClassification.NO_RESPONSE,
            ElementStatus.NOT_TESTED: InteractionClassification.NO_RESPONSE,
        }
        return mapping.get(status, InteractionClassification.NO_RESPONSE)
