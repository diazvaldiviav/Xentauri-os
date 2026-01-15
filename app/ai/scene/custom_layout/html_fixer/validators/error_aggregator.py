"""
Error Aggregator - Combine static and dynamic analysis results.

Merges errors from Sprint 1 static analyzers with Sprint 2
Playwright-based diagnosis to produce final ClassifiedErrors.
"""

from typing import List, Optional, Dict, Set

from ..contracts.errors import ErrorType
from ..contracts.validation import TailwindInfo, ClassifiedError
from ..analyzers.interactive_detector import InteractiveElement
from ..analyzers.pointer_detector import BlockageInfo, BlockageReason
from .playwright_diagnostic import ElementDiagnosis


class ErrorAggregator:
    """
    Aggregates errors from multiple sources.

    Combines:
    - Static analysis (BlockageInfo from PointerBlockageDetector)
    - Dynamic analysis (ElementDiagnosis from Playwright)

    To produce unified ClassifiedError objects.
    """

    # Map BlockageReason to ErrorType
    BLOCKAGE_TO_ERROR: Dict[BlockageReason, ErrorType] = {
        BlockageReason.OVERLAY_BLOCKING: ErrorType.POINTER_BLOCKED,
        BlockageReason.ZINDEX_CONFLICT: ErrorType.ZINDEX_CONFLICT,
        BlockageReason.PARENT_POINTER_NONE: ErrorType.POINTER_INTERCEPTED,
        BlockageReason.SIBLING_OVERLAP: ErrorType.ZINDEX_CONFLICT,
        BlockageReason.MODAL_BACKDROP: ErrorType.POINTER_BLOCKED,
    }

    def aggregate(
        self,
        element: InteractiveElement,
        static_errors: List[BlockageInfo],
        diagnosis: Optional[ElementDiagnosis],
        tailwind_info: Optional[TailwindInfo] = None,
    ) -> List[ClassifiedError]:
        """
        Aggregate errors for a single element.

        Args:
            element: The interactive element being analyzed
            static_errors: Errors from static analysis
            diagnosis: Playwright-based diagnosis (can be None for static-only)
            tailwind_info: Pre-computed Tailwind analysis

        Returns:
            List of ClassifiedError objects
        """
        errors: List[ClassifiedError] = []

        # Get Tailwind info if not provided
        if tailwind_info is None:
            from ..analyzers.tailwind_analyzer import TailwindAnalyzer

            analyzer = TailwindAnalyzer()
            tailwind_info = analyzer.analyze_element(element.element)

        # Process static errors
        for blockage in static_errors:
            if blockage.blocked_element == element.element:
                error = self._blockage_to_error(blockage, element, tailwind_info)
                errors.append(error)

        # Process dynamic diagnosis if available
        if diagnosis and diagnosis.found and not diagnosis.is_clickable:
            # Check if error already captured by static analysis
            existing_types = {e.error_type for e in errors}

            # Add visibility issues
            if diagnosis.visibility:
                vis_issue = diagnosis.visibility.visibility_issue
                if vis_issue and vis_issue not in existing_types:
                    errors.append(
                        self._visibility_error(
                            element, diagnosis, tailwind_info, vis_issue
                        )
                    )

            # Add interceptor issues
            if (
                diagnosis.interceptor
                and not diagnosis.interceptor.has_pointer_events_none
            ):
                if ErrorType.POINTER_BLOCKED not in existing_types:
                    errors.append(
                        self._interceptor_error(element, diagnosis, tailwind_info)
                    )

            # Add pointer-events inheritance issues
            if diagnosis.pointer_events and not diagnosis.pointer_events.effective:
                if ErrorType.POINTER_INTERCEPTED not in existing_types:
                    errors.append(
                        self._pointer_events_error(element, diagnosis, tailwind_info)
                    )

        return errors

    def aggregate_all(
        self,
        elements: List[InteractiveElement],
        static_errors: List[BlockageInfo],
        diagnoses: Optional[Dict[str, ElementDiagnosis]] = None,
        tailwind_infos: Optional[Dict[str, TailwindInfo]] = None,
    ) -> List[ClassifiedError]:
        """
        Aggregate errors for multiple elements.

        Args:
            elements: List of interactive elements
            static_errors: All static analysis errors
            diagnoses: Diagnosis per element selector (optional)
            tailwind_infos: Pre-computed Tailwind info per selector (optional)

        Returns:
            Combined list of all ClassifiedError objects
        """
        all_errors: List[ClassifiedError] = []
        diagnoses = diagnoses or {}
        tailwind_infos = tailwind_infos or {}

        for element in elements:
            selector = element.selector
            diagnosis = diagnoses.get(selector)
            tailwind_info = tailwind_infos.get(selector)

            errors = self.aggregate(
                element=element,
                static_errors=static_errors,
                diagnosis=diagnosis,
                tailwind_info=tailwind_info,
            )
            all_errors.extend(errors)

        return all_errors

    def _blockage_to_error(
        self,
        blockage: BlockageInfo,
        element: InteractiveElement,
        tailwind_info: TailwindInfo,
    ) -> ClassifiedError:
        """Convert BlockageInfo to ClassifiedError."""
        error_type = self.BLOCKAGE_TO_ERROR.get(blockage.reason, ErrorType.UNKNOWN)

        # Determine suggested fix
        suggested = self._get_suggested_classes(error_type, tailwind_info)

        return ClassifiedError(
            error_type=error_type,
            selector=element.selector,
            element_tag=element.element.name,
            tailwind_info=tailwind_info,
            blocking_element=blockage.blocking_selector,
            confidence=1.0,  # Static analysis is definitive
            suggested_classes=suggested,
        )

    def _visibility_error(
        self,
        element: InteractiveElement,
        diagnosis: ElementDiagnosis,
        tailwind_info: TailwindInfo,
        error_type: ErrorType,
    ) -> ClassifiedError:
        """Create ClassifiedError for visibility issue."""
        suggested = self._get_suggested_classes(error_type, tailwind_info)

        bounding_box = None
        if diagnosis.rect:
            bounding_box = {
                "x": diagnosis.rect.x,
                "y": diagnosis.rect.y,
                "width": diagnosis.rect.width,
                "height": diagnosis.rect.height,
            }

        return ClassifiedError(
            error_type=error_type,
            selector=element.selector,
            element_tag=element.element.name,
            tailwind_info=tailwind_info,
            bounding_box=bounding_box,
            confidence=0.95,  # High confidence from browser
            suggested_classes=suggested,
        )

    def _interceptor_error(
        self,
        element: InteractiveElement,
        diagnosis: ElementDiagnosis,
        tailwind_info: TailwindInfo,
    ) -> ClassifiedError:
        """Create ClassifiedError for interceptor blocking."""
        bounding_box = None
        if diagnosis.rect:
            bounding_box = {
                "x": diagnosis.rect.x,
                "y": diagnosis.rect.y,
                "width": diagnosis.rect.width,
                "height": diagnosis.rect.height,
            }

        return ClassifiedError(
            error_type=ErrorType.POINTER_BLOCKED,
            selector=element.selector,
            element_tag=element.element.name,
            tailwind_info=tailwind_info,
            blocking_element=diagnosis.interceptor.selector
            if diagnosis.interceptor
            else None,
            bounding_box=bounding_box,
            confidence=1.0,  # elementFromPoint is definitive
            suggested_classes=["relative", "z-50"],
        )

    def _pointer_events_error(
        self,
        element: InteractiveElement,
        diagnosis: ElementDiagnosis,
        tailwind_info: TailwindInfo,
    ) -> ClassifiedError:
        """Create ClassifiedError for pointer-events inheritance."""
        return ClassifiedError(
            error_type=ErrorType.POINTER_INTERCEPTED,
            selector=element.selector,
            element_tag=element.element.name,
            tailwind_info=tailwind_info,
            confidence=0.9,
            suggested_classes=["pointer-events-auto"],
        )

    def _get_suggested_classes(
        self, error_type: ErrorType, info: TailwindInfo
    ) -> List[str]:
        """Get suggested fix classes for error type."""
        # Determine appropriate z-index fix
        current_z = info.z_index if info.z_index is not None else 0
        new_z = max(current_z + 10, 50)
        z_fix = f"z-{new_z}" if new_z <= 50 else f"z-[{new_z}]"

        suggestions: Dict[ErrorType, List[str]] = {
            ErrorType.ZINDEX_CONFLICT: ["relative", z_fix],
            ErrorType.ZINDEX_MISSING: ["relative", "z-10"],
            ErrorType.POINTER_BLOCKED: ["relative", "z-50"],
            ErrorType.POINTER_INTERCEPTED: ["pointer-events-auto"],
            ErrorType.INVISIBLE_OPACITY: ["opacity-100"],
            ErrorType.INVISIBLE_DISPLAY: ["block"],
            ErrorType.INVISIBLE_VISIBILITY: ["visible"],
            ErrorType.TRANSFORM_3D_HIDDEN: ["[backface-visibility:visible]"],
            ErrorType.TRANSFORM_OFFSCREEN: ["translate-x-0", "translate-y-0"],
        }

        return suggestions.get(error_type, [])
