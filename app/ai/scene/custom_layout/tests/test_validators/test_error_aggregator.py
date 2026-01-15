"""
Unit tests for ErrorAggregator.

Tests combining static and dynamic error analysis.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.validators.error_aggregator import ErrorAggregator
from html_fixer.validators.playwright_diagnostic import (
    ElementDiagnosis,
    VisibilityInfo,
    InterceptorInfo,
    PointerEventsInfo,
    BoundingRect,
)
from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.analyzers.interactive_detector import InteractiveDetector
from html_fixer.analyzers.pointer_detector import BlockageInfo, BlockageReason
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.validation import TailwindInfo


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def aggregator():
    """ErrorAggregator instance."""
    return ErrorAggregator()


@pytest.fixture
def sample_html():
    """Sample HTML with interactive elements."""
    return """
    <html>
    <body>
        <div id="overlay" class="absolute inset-0 bg-black/50"></div>
        <button id="btn1" class="relative z-10">Button 1</button>
        <button id="btn2">Button 2</button>
    </body>
    </html>
    """


@pytest.fixture
def parser(sample_html):
    """DOMParser instance."""
    return DOMParser(sample_html)


@pytest.fixture
def interactive_detector():
    """InteractiveDetector instance."""
    return InteractiveDetector()


# ============================================================================
# STATIC ERROR AGGREGATION TESTS
# ============================================================================


class TestStaticErrorAggregation:
    """Tests for aggregating static analysis errors."""

    def test_aggregate_blockage_info(
        self, aggregator, parser, interactive_detector
    ):
        """Should convert BlockageInfo to ClassifiedError."""
        interactive = interactive_detector.find_interactive_elements(parser)
        btn1 = next(e for e in interactive if e.selector == "#btn1")
        btn1_element = btn1.element

        blockage = BlockageInfo(
            blocked_element=btn1_element,
            blocked_selector="#btn1",
            blocking_element=parser.get_element_by_id("overlay"),
            blocking_selector="#overlay",
            reason=BlockageReason.OVERLAY_BLOCKING,
            suggested_fix="Add pointer-events-none to overlay",
        )

        errors = aggregator.aggregate(
            element=btn1,
            static_errors=[blockage],
            diagnosis=None,
        )

        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.POINTER_BLOCKED
        assert errors[0].selector == "#btn1"
        assert errors[0].blocking_element == "#overlay"

    def test_aggregate_zindex_conflict(
        self, aggregator, parser, interactive_detector
    ):
        """Should handle z-index conflict blockage."""
        interactive = interactive_detector.find_interactive_elements(parser)
        btn1 = next(e for e in interactive if e.selector == "#btn1")
        btn1_element = btn1.element

        blockage = BlockageInfo(
            blocked_element=btn1_element,
            blocked_selector="#btn1",
            blocking_element=parser.get_element_by_id("overlay"),
            blocking_selector="#overlay",
            reason=BlockageReason.ZINDEX_CONFLICT,
            suggested_fix="Increase z-index",
        )

        errors = aggregator.aggregate(
            element=btn1,
            static_errors=[blockage],
            diagnosis=None,
        )

        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.ZINDEX_CONFLICT


# ============================================================================
# DYNAMIC DIAGNOSIS AGGREGATION TESTS
# ============================================================================


class TestDynamicDiagnosisAggregation:
    """Tests for aggregating Playwright diagnosis."""

    def test_aggregate_visibility_issue(
        self, aggregator, parser, interactive_detector
    ):
        """Should detect visibility issues from diagnosis."""
        interactive = interactive_detector.find_interactive_elements(parser)
        btn1 = next(e for e in interactive if e.selector == "#btn1")

        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn1",
            visibility=VisibilityInfo(
                display="none",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=40,
                in_viewport=True,
            ),
            interceptor=None,
            stacking=None,
            pointer_events=None,
            rect=BoundingRect(x=100, y=100, width=100, height=40),
        )

        errors = aggregator.aggregate(
            element=btn1,
            static_errors=[],
            diagnosis=diagnosis,
        )

        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.INVISIBLE_DISPLAY

    def test_aggregate_interceptor_issue(
        self, aggregator, parser, interactive_detector
    ):
        """Should detect interceptor from diagnosis."""
        interactive = interactive_detector.find_interactive_elements(parser)
        btn1 = next(e for e in interactive if e.selector == "#btn1")

        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn1",
            visibility=VisibilityInfo(
                display="block",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=40,
                in_viewport=True,
            ),
            interceptor=InterceptorInfo(
                selector="#overlay",
                tag_name="div",
                classes=["absolute", "inset-0"],
                is_overlay=True,
                has_pointer_events_none=False,
                z_index=40,
            ),
            stacking=None,
            pointer_events=None,
            rect=BoundingRect(x=100, y=100, width=100, height=40),
        )

        errors = aggregator.aggregate(
            element=btn1,
            static_errors=[],
            diagnosis=diagnosis,
        )

        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.POINTER_BLOCKED
        assert errors[0].blocking_element == "#overlay"

    def test_aggregate_pointer_events_issue(
        self, aggregator, parser, interactive_detector
    ):
        """Should detect pointer-events inheritance issue."""
        interactive = interactive_detector.find_interactive_elements(parser)
        btn1 = next(e for e in interactive if e.selector == "#btn1")

        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn1",
            visibility=VisibilityInfo(
                display="block",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=40,
                in_viewport=True,
            ),
            interceptor=None,
            stacking=None,
            pointer_events=PointerEventsInfo(
                value="none",
                inherited=True,
                effective=False,
            ),
            rect=BoundingRect(x=100, y=100, width=100, height=40),
        )

        errors = aggregator.aggregate(
            element=btn1,
            static_errors=[],
            diagnosis=diagnosis,
        )

        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.POINTER_INTERCEPTED


# ============================================================================
# DEDUPLICATION TESTS
# ============================================================================


class TestDeduplication:
    """Tests for error deduplication."""

    def test_no_duplicate_pointer_blocked(
        self, aggregator, parser, interactive_detector
    ):
        """Should not duplicate POINTER_BLOCKED from static and dynamic."""
        interactive = interactive_detector.find_interactive_elements(parser)
        btn1 = next(e for e in interactive if e.selector == "#btn1")
        btn1_element = btn1.element

        # Static blockage
        blockage = BlockageInfo(
            blocked_element=btn1_element,
            blocked_selector="#btn1",
            blocking_element=parser.get_element_by_id("overlay"),
            blocking_selector="#overlay",
            reason=BlockageReason.OVERLAY_BLOCKING,
            suggested_fix="Add pointer-events-none",
        )

        # Dynamic diagnosis with same issue
        diagnosis = ElementDiagnosis(
            found=True,
            selector="#btn1",
            visibility=VisibilityInfo(
                display="block",
                visibility="visible",
                opacity=1.0,
                width=100,
                height=40,
                in_viewport=True,
            ),
            interceptor=InterceptorInfo(
                selector="#overlay",
                tag_name="div",
                classes=["absolute"],
                is_overlay=True,
                has_pointer_events_none=False,
                z_index=40,
            ),
            stacking=None,
            pointer_events=None,
            rect=BoundingRect(x=100, y=100, width=100, height=40),
        )

        errors = aggregator.aggregate(
            element=btn1,
            static_errors=[blockage],
            diagnosis=diagnosis,
        )

        # Should only have one POINTER_BLOCKED error, not two
        pointer_blocked = [
            e for e in errors if e.error_type == ErrorType.POINTER_BLOCKED
        ]
        assert len(pointer_blocked) == 1


# ============================================================================
# AGGREGATE ALL TESTS
# ============================================================================


class TestAggregateAll:
    """Tests for aggregate_all method."""

    def test_aggregate_all_multiple_elements(
        self, aggregator, parser, interactive_detector
    ):
        """Should aggregate errors for multiple elements."""
        interactive = interactive_detector.find_interactive_elements(parser)

        errors = aggregator.aggregate_all(
            elements=interactive,
            static_errors=[],
            diagnoses=None,
        )

        # Should return empty list when no errors
        assert isinstance(errors, list)

    def test_aggregate_all_with_diagnoses(
        self, aggregator, parser, interactive_detector
    ):
        """Should use diagnoses dict when provided."""
        interactive = interactive_detector.find_interactive_elements(parser)

        diagnoses = {
            "#btn1": ElementDiagnosis(
                found=True,
                selector="#btn1",
                visibility=VisibilityInfo(
                    display="none",
                    visibility="visible",
                    opacity=1.0,
                    width=0,
                    height=0,
                    in_viewport=False,
                ),
                interceptor=None,
                stacking=None,
                pointer_events=None,
                rect=None,
            )
        }

        errors = aggregator.aggregate_all(
            elements=interactive,
            static_errors=[],
            diagnoses=diagnoses,
        )

        # Should detect visibility issue for #btn1
        btn1_errors = [e for e in errors if e.selector == "#btn1"]
        assert len(btn1_errors) >= 1
