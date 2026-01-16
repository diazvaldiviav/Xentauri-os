"""
Sandbox - Visual validation for HTML with Playwright.

Sprint 4: Basic sandbox for testing interactive elements.
Sprint 5: Multi-scale diff engine, result classification, and reporting.

This module provides browser-based validation of HTML to ensure
that interactive elements are clickable and provide visual feedback.

Usage:
    from ..sandbox import Sandbox, quick_validate

    # Full control
    sandbox = Sandbox(viewport_width=1920, viewport_height=1080)
    result = await sandbox.validate(html)

    # Quick validation
    result = await quick_validate(html)

    # Check results
    if result.passed:
        print("All elements work!")
    else:
        for element in result.get_blocked():
            print(f"{element.selector} blocked by {element.blocking_element}")

    # Sprint 5: Generate detailed report
    from ..sandbox import ValidationReportGenerator
    generator = ValidationReportGenerator()
    report = generator.generate(result, html)
    print(report.describe())
"""

from .contracts import (
    ElementInfo,
    ElementResult,
    ElementStatus,
    ValidationResult,
)
from .sandbox import Sandbox, quick_validate

# Sprint 5: DiffEngine
from .diff_engine import (
    DiffEngine,
    DiffResult,
    RegionDiff,
    ComparisonScale,
)

# Sprint 5: ResultClassifier
from .result_classifier import (
    ResultClassifier,
    InteractionClassification,
    ClassificationResult,
)

# Sprint 5: ValidationReport
from .validation_report import (
    ValidationReport,
    ValidationReportGenerator,
    ElementReport,
)

# Sprint 5: ScreenshotExporter
from .screenshot_exporter import (
    ScreenshotExporter,
    ExportedScreenshots,
)


__all__ = [
    # Main class
    "Sandbox",
    "quick_validate",
    # Contracts
    "ElementInfo",
    "ElementResult",
    "ElementStatus",
    "ValidationResult",
    # Sprint 5: DiffEngine
    "DiffEngine",
    "DiffResult",
    "RegionDiff",
    "ComparisonScale",
    # Sprint 5: Classification
    "ResultClassifier",
    "InteractionClassification",
    "ClassificationResult",
    # Sprint 5: Reporting
    "ValidationReport",
    "ValidationReportGenerator",
    "ElementReport",
    # Sprint 5: Screenshot export
    "ScreenshotExporter",
    "ExportedScreenshots",
]
