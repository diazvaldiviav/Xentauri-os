"""
Error Report - Generate structured reports of classification results.

Provides ErrorReport dataclass and generator for creating
JSON-serializable reports.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..contracts.errors import ErrorType
from ..contracts.validation import ClassifiedError, TailwindInfo


@dataclass
class ErrorReport:
    """
    Complete report of error classification results.

    Contains all errors found, summary statistics, and metadata
    for tracking and debugging.
    """

    html_hash: str
    """SHA256 hash of the analyzed HTML (first 16 chars)."""

    timestamp: str
    """ISO format timestamp of when report was generated."""

    total_interactive: int
    """Total number of interactive elements found."""

    errors: List[ClassifiedError]
    """List of all classified errors."""

    summary: Dict[str, int]
    """Count of errors by type (ErrorType.value -> count)."""

    viewport_size: Dict[str, int] = field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )
    """Viewport size used for analysis."""

    analysis_time_ms: Optional[float] = None
    """Time taken to complete analysis in milliseconds."""

    @property
    def total_errors(self) -> int:
        """Total number of errors found."""
        return len(self.errors)

    @property
    def elements_with_errors(self) -> int:
        """Number of unique elements with errors."""
        return len({e.selector for e in self.errors})

    @property
    def has_critical_errors(self) -> bool:
        """Check if report contains critical errors."""
        critical_types = {
            ErrorType.POINTER_BLOCKED,
            ErrorType.ZINDEX_CONFLICT,
            ErrorType.INVISIBLE_DISPLAY,
        }
        return any(e.error_type in critical_types for e in self.errors)

    @property
    def error_rate(self) -> float:
        """Percentage of interactive elements with errors."""
        if self.total_interactive == 0:
            return 0.0
        return self.elements_with_errors / self.total_interactive

    def get_errors_by_type(self, error_type: ErrorType) -> List[ClassifiedError]:
        """Get all errors of a specific type."""
        return [e for e in self.errors if e.error_type == error_type]

    def get_errors_for_selector(self, selector: str) -> List[ClassifiedError]:
        """Get all errors for a specific element."""
        return [e for e in self.errors if e.selector == selector]

    def describe(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Error Report ({self.timestamp})",
            f"  HTML Hash: {self.html_hash}",
            f"  Total Interactive Elements: {self.total_interactive}",
            f"  Elements with Errors: {self.elements_with_errors}",
            f"  Total Errors: {self.total_errors}",
            "",
            "  Summary by Type:",
        ]

        for error_type, count in sorted(self.summary.items()):
            if count > 0:
                lines.append(f"    - {error_type}: {count}")

        if self.analysis_time_ms:
            lines.append(f"\n  Analysis Time: {self.analysis_time_ms:.2f}ms")

        return "\n".join(lines)


class ErrorReportGenerator:
    """
    Generates ErrorReport instances from classification results.

    Computes summary statistics and metadata for reports.
    """

    def generate(
        self,
        errors: List[ClassifiedError],
        html: str,
        total_interactive: int,
        analysis_time_ms: Optional[float] = None,
        viewport_size: Optional[Dict[str, int]] = None,
    ) -> ErrorReport:
        """
        Generate a complete error report.

        Args:
            errors: List of classified errors
            html: Original HTML that was analyzed
            total_interactive: Total interactive elements found
            analysis_time_ms: Optional analysis duration
            viewport_size: Optional viewport dimensions

        Returns:
            ErrorReport instance
        """
        # Compute HTML hash
        html_hash = hashlib.sha256(html.encode()).hexdigest()[:16]

        # Generate timestamp
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Build summary
        summary = self._build_summary(errors)

        # Default viewport
        if viewport_size is None:
            viewport_size = {"width": 1920, "height": 1080}

        return ErrorReport(
            html_hash=html_hash,
            timestamp=timestamp,
            total_interactive=total_interactive,
            errors=errors,
            summary=summary,
            viewport_size=viewport_size,
            analysis_time_ms=analysis_time_ms,
        )

    def to_json(self, report: ErrorReport) -> str:
        """
        Serialize report to JSON string.

        Args:
            report: ErrorReport to serialize

        Returns:
            JSON string representation
        """
        return json.dumps(self._to_dict(report), indent=2)

    def from_json(self, json_str: str) -> ErrorReport:
        """
        Deserialize report from JSON string.

        Args:
            json_str: JSON string to parse

        Returns:
            ErrorReport instance
        """
        data = json.loads(json_str)
        return self._from_dict(data)

    def _build_summary(self, errors: List[ClassifiedError]) -> Dict[str, int]:
        """Build error count by type."""
        summary: Dict[str, int] = {}

        for error_type in ErrorType:
            count = sum(1 for e in errors if e.error_type == error_type)
            if count > 0:
                summary[error_type.value] = count

        return summary

    def _to_dict(self, report: ErrorReport) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "html_hash": report.html_hash,
            "timestamp": report.timestamp,
            "total_interactive": report.total_interactive,
            "total_errors": report.total_errors,
            "elements_with_errors": report.elements_with_errors,
            "error_rate": round(report.error_rate, 4),
            "summary": report.summary,
            "viewport_size": report.viewport_size,
            "analysis_time_ms": report.analysis_time_ms,
            "errors": [
                {
                    "error_type": e.error_type.value,
                    "selector": e.selector,
                    "element_tag": e.element_tag,
                    "confidence": e.confidence,
                    "blocking_element": e.blocking_element,
                    "suggested_classes": e.suggested_classes,
                    "bounding_box": e.bounding_box,
                }
                for e in report.errors
            ],
        }

    def _from_dict(self, data: Dict[str, Any]) -> ErrorReport:
        """Create report from dictionary."""
        errors = []
        for e in data.get("errors", []):
            errors.append(
                ClassifiedError(
                    error_type=ErrorType(e["error_type"]),
                    selector=e["selector"],
                    element_tag=e["element_tag"],
                    tailwind_info=TailwindInfo(),  # Minimal info on load
                    confidence=e.get("confidence", 1.0),
                    blocking_element=e.get("blocking_element"),
                    suggested_classes=e.get("suggested_classes", []),
                    bounding_box=e.get("bounding_box"),
                )
            )

        return ErrorReport(
            html_hash=data["html_hash"],
            timestamp=data["timestamp"],
            total_interactive=data["total_interactive"],
            errors=errors,
            summary=data["summary"],
            viewport_size=data.get("viewport_size", {"width": 1920, "height": 1080}),
            analysis_time_ms=data.get("analysis_time_ms"),
        )
