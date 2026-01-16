"""
Validators - Playwright-based HTML validation.

Sprint 2 Implementation:
- PlaywrightDiagnostic: Browser-based element diagnosis
- JSEvaluators: JavaScript code for page.evaluate()
- TransformDetector: 3D transform and backface detection
- ErrorAggregator: Combine static and dynamic errors
- ErrorPrioritizer: Sort errors by severity
- ErrorReport: Structured classification results
- ErrorClassificationPipeline: End-to-end classification

Sprint 3.5 Implementation:
- JSValidator: Static JavaScript analysis
- JSRuntimeValidator: Browser-based JS validation
- JSErrorClassifier: Classify JS errors
"""

from .playwright_diagnostic import (
    PlaywrightDiagnostic,
    ElementDiagnosis,
    BoundingRect,
    VisibilityInfo,
    InterceptorInfo,
    StackingInfo,
    PointerEventsInfo,
    diagnose_element,
)

from .js_evaluators import JSEvaluators

from .transform_detector import (
    TransformDetector,
    BackfaceIssue,
    TransformIssue,
)

from .error_aggregator import ErrorAggregator

from .error_prioritizer import ErrorPrioritizer

from .error_report import (
    ErrorReport,
    ErrorReportGenerator,
)

from .classification_pipeline import (
    ErrorClassificationPipeline,
    classify_html,
)

# Sprint 3.5: JavaScript Validation
from .js_validator import (
    JSValidator,
    JSValidationResult,
    ScriptInfo,
)

from .js_runtime_validator import (
    JSRuntimeValidator,
    JSRuntimeResult,
    RuntimeError,
)

from .js_error_classifier import JSErrorClassifier

__all__ = [
    # Playwright Diagnostic
    "PlaywrightDiagnostic",
    "ElementDiagnosis",
    "BoundingRect",
    "VisibilityInfo",
    "InterceptorInfo",
    "StackingInfo",
    "PointerEventsInfo",
    "diagnose_element",
    # JS Evaluators
    "JSEvaluators",
    # Transform Detector
    "TransformDetector",
    "BackfaceIssue",
    "TransformIssue",
    # Error Aggregator
    "ErrorAggregator",
    # Error Prioritizer
    "ErrorPrioritizer",
    # Error Report
    "ErrorReport",
    "ErrorReportGenerator",
    # Pipeline
    "ErrorClassificationPipeline",
    "classify_html",
    # Sprint 3.5: JavaScript Validation
    "JSValidator",
    "JSValidationResult",
    "ScriptInfo",
    "JSRuntimeValidator",
    "JSRuntimeResult",
    "RuntimeError",
    "JSErrorClassifier",
]
