"""
Classification Pipeline - End-to-end error classification.

Orchestrates all analyzers and validators to produce a complete
ErrorReport from raw HTML.
"""

import time
from typing import List, Dict, Optional

from ..analyzers.dom_parser import DOMParser
from ..analyzers.interactive_detector import InteractiveDetector, InteractiveElement
from ..analyzers.pointer_detector import PointerBlockageDetector, BlockageInfo
from ..analyzers.tailwind_analyzer import TailwindAnalyzer
from ..contracts.validation import TailwindInfo, ClassifiedError

from .playwright_diagnostic import PlaywrightDiagnostic, ElementDiagnosis
from .transform_detector import TransformDetector, BackfaceIssue, TransformIssue
from .error_aggregator import ErrorAggregator
from .error_prioritizer import ErrorPrioritizer
from .error_report import ErrorReport, ErrorReportGenerator


class ErrorClassificationPipeline:
    """
    Complete error classification pipeline.

    Combines Sprint 1 static analyzers with Sprint 2 Playwright
    diagnostics to produce comprehensive error reports.

    Usage:
        pipeline = ErrorClassificationPipeline()

        # With Playwright page
        report = await pipeline.classify(html, page)

        # Static-only mode (no Playwright)
        report = await pipeline.classify_static(html)
    """

    def __init__(self, viewport_width: int = 1920, viewport_height: int = 1080):
        """
        Initialize the pipeline.

        Args:
            viewport_width: Expected viewport width
            viewport_height: Expected viewport height
        """
        # Sprint 1 analyzers
        self.dom_parser: Optional[DOMParser] = None
        self.interactive_detector = InteractiveDetector()
        self.pointer_detector = PointerBlockageDetector()
        self.tailwind_analyzer = TailwindAnalyzer()

        # Sprint 2 validators
        self.playwright_diagnostic = PlaywrightDiagnostic(
            viewport_width, viewport_height
        )
        self.transform_detector = TransformDetector()
        self.error_aggregator = ErrorAggregator()
        self.prioritizer = ErrorPrioritizer()
        self.report_generator = ErrorReportGenerator()

        # Config
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height

        # Cache for last run
        self._last_interactive: List[InteractiveElement] = []
        self._last_static_errors: List[BlockageInfo] = []

    async def classify(self, html: str, page=None) -> ErrorReport:
        """
        Classify all errors in HTML.

        Args:
            html: HTML string to analyze
            page: Optional Playwright Page for dynamic analysis

        Returns:
            ErrorReport with all classified errors
        """
        start_time = time.time()

        # Phase 1: Static analysis (Sprint 1)
        self.dom_parser = DOMParser(html)
        interactive = self.interactive_detector.find_interactive_elements(
            self.dom_parser
        )
        self._last_interactive = interactive

        static_errors = self.pointer_detector.find_blocked_elements(
            self.dom_parser, interactive
        )
        self._last_static_errors = static_errors

        # Get Tailwind info for all interactive elements
        tailwind_infos: Dict[str, TailwindInfo] = {}
        for element in interactive:
            tailwind_infos[element.selector] = self.tailwind_analyzer.analyze_element(
                element.element
            )

        # Phase 2: Dynamic analysis (Sprint 2) - if page provided
        diagnoses: Dict[str, ElementDiagnosis] = {}
        transform_errors: List[ClassifiedError] = []

        if page:
            # Load HTML into page
            await page.set_content(html, wait_until="networkidle")

            # Diagnose each interactive element
            for element in interactive:
                diagnosis = await self.playwright_diagnostic.diagnose_element(
                    page, element.selector
                )
                diagnoses[element.selector] = diagnosis

            # Check for transform issues
            selectors = [e.selector for e in interactive]
            transform_issues = await self.transform_detector.detect_transform_issues(
                page, selectors
            )

            # Convert transform issues to ClassifiedErrors
            for issue in transform_issues:
                element = self._find_element_by_selector(interactive, issue.selector)
                if element:
                    tailwind_info = tailwind_infos.get(
                        issue.selector, TailwindInfo()
                    )
                    transform_errors.append(
                        ClassifiedError(
                            error_type=issue.error_type,
                            selector=issue.selector,
                            element_tag=element.element.name,
                            tailwind_info=tailwind_info,
                            confidence=0.9,
                            suggested_classes=issue.suggested_fix,
                        )
                    )

        # Phase 3: Aggregate errors
        all_errors = self.error_aggregator.aggregate_all(
            elements=interactive,
            static_errors=static_errors,
            diagnoses=diagnoses if diagnoses else None,
            tailwind_infos=tailwind_infos,
        )

        # Add transform errors
        all_errors.extend(transform_errors)

        # Phase 4: Prioritize
        prioritized_errors = self.prioritizer.prioritize(all_errors)

        # Phase 5: Generate report
        elapsed_ms = (time.time() - start_time) * 1000

        report = self.report_generator.generate(
            errors=prioritized_errors,
            html=html,
            total_interactive=len(interactive),
            analysis_time_ms=elapsed_ms,
            viewport_size={
                "width": self._viewport_width,
                "height": self._viewport_height,
            },
        )

        return report

    async def classify_static(self, html: str) -> ErrorReport:
        """
        Classify using only static analysis (no Playwright).

        Args:
            html: HTML string to analyze

        Returns:
            ErrorReport with statically-detectable errors only
        """
        return await self.classify(html, page=None)

    def get_interactive_elements(self) -> List[InteractiveElement]:
        """Get list of interactive elements from last classification."""
        return self._last_interactive

    def get_static_errors(self) -> List[BlockageInfo]:
        """Get static errors from last classification."""
        return self._last_static_errors

    def _find_element_by_selector(
        self, elements: List[InteractiveElement], selector: str
    ) -> Optional[InteractiveElement]:
        """Find element by selector."""
        for element in elements:
            if element.selector == selector:
                return element
        return None


# Convenience function for quick classification
async def classify_html(html: str, page=None) -> ErrorReport:
    """
    Classify errors in HTML using default pipeline.

    Args:
        html: HTML string to analyze
        page: Optional Playwright Page for dynamic analysis

    Returns:
        ErrorReport with all classified errors
    """
    pipeline = ErrorClassificationPipeline()
    return await pipeline.classify(html, page)
