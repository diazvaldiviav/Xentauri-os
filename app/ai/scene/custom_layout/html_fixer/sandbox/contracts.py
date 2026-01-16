"""
Sandbox Contracts - Data structures for visual validation.

Sprint 4: Basic sandbox contracts for HTML validation with Playwright.
Sprint 5: Added DiffResult and ClassificationResult fields.

These structures carry information through the validation pipeline:
1. ElementInfo: Information about an interactive element
2. ElementResult: Result of testing a single element
3. ValidationResult: Complete validation results
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from enum import Enum

if TYPE_CHECKING:
    from .diff_engine import DiffResult
    from .result_classifier import ClassificationResult


class ElementStatus(Enum):
    """Status of an element after validation."""

    RESPONSIVE = "responsive"
    """Element responded to click with visual change."""

    NO_VISUAL_CHANGE = "no_visual_change"
    """Element was clicked but no visual change detected."""

    INTERCEPTED = "intercepted"
    """Click was intercepted by another element."""

    TIMEOUT = "timeout"
    """Click timed out waiting for element."""

    ERROR = "error"
    """An error occurred during validation."""

    NOT_TESTED = "not_tested"
    """Element was not tested."""


@dataclass
class ElementInfo:
    """
    Information about an interactive element to test.

    Collected by the sandbox when finding interactive elements
    in the rendered HTML.
    """

    selector: str
    """CSS selector to locate the element."""

    tag: str
    """HTML tag name (e.g., 'button', 'a', 'div')."""

    bounding_box: Dict[str, float] = field(default_factory=dict)
    """Element's position and size {x, y, width, height}."""

    has_handler: bool = False
    """Whether element has an onclick or similar handler."""

    inner_text: Optional[str] = None
    """Text content of the element (truncated)."""

    classes: List[str] = field(default_factory=list)
    """CSS classes on the element."""

    def __repr__(self) -> str:
        text = f'"{self.inner_text[:20]}..."' if self.inner_text else ""
        return f"ElementInfo({self.selector} <{self.tag}> {text})"


@dataclass
class ElementResult:
    """
    Result of testing a single element.

    Contains the outcome of attempting to click an element
    and observing the visual response.
    """

    selector: str
    """CSS selector of the tested element."""

    status: ElementStatus
    """Outcome of the test."""

    diff_ratio: float = 0.0
    """Screenshot difference ratio (0.0-1.0). Higher = more change."""

    blocking_element: Optional[str] = None
    """Selector of element that blocked the click (if intercepted)."""

    error: Optional[str] = None
    """Error message if status is ERROR or TIMEOUT."""

    before_screenshot: Optional[bytes] = None
    """Screenshot before clicking."""

    after_screenshot: Optional[bytes] = None
    """Screenshot after clicking."""

    # Sprint 5: Multi-scale diff result
    diff_result: Optional["DiffResult"] = None
    """Multi-scale diff result from DiffEngine (Sprint 5)."""

    # Sprint 5: Classification result
    classification: Optional["ClassificationResult"] = None
    """Semantic classification of the interaction result (Sprint 5)."""

    def __repr__(self) -> str:
        return f"ElementResult({self.selector}, {self.status.value})"

    @property
    def is_success(self) -> bool:
        """Check if the test passed (element is responsive)."""
        return self.status == ElementStatus.RESPONSIVE

    @property
    def is_blocked(self) -> bool:
        """Check if element was blocked by another element."""
        return self.status == ElementStatus.INTERCEPTED

    @property
    def has_feedback(self) -> bool:
        """Check if element showed any visual feedback."""
        return self.diff_ratio > 0.02


@dataclass
class ValidationResult:
    """
    Complete validation results for an HTML document.

    Aggregates results from testing all interactive elements
    plus any JavaScript errors encountered.
    """

    element_results: List[ElementResult] = field(default_factory=list)
    """Results for each tested element."""

    js_errors: List[str] = field(default_factory=list)
    """JavaScript errors captured during validation."""

    console_errors: List[str] = field(default_factory=list)
    """Console errors captured during validation."""

    initial_screenshot: Optional[bytes] = None
    """Screenshot of initial page state."""

    validation_time_ms: float = 0.0
    """Total time taken for validation in milliseconds."""

    viewport_width: int = 1920
    """Width of the viewport used."""

    viewport_height: int = 1080
    """Height of the viewport used."""

    @property
    def total_elements(self) -> int:
        """Total number of elements tested."""
        return len(self.element_results)

    @property
    def responsive_elements(self) -> int:
        """Number of elements that responded to clicks."""
        return sum(1 for r in self.element_results if r.is_success)

    @property
    def blocked_elements(self) -> int:
        """Number of elements blocked by other elements."""
        return sum(1 for r in self.element_results if r.is_blocked)

    @property
    def success_rate(self) -> float:
        """Percentage of elements that passed validation."""
        if not self.element_results:
            return 1.0
        return self.responsive_elements / len(self.element_results)

    @property
    def has_js_errors(self) -> bool:
        """Check if any JavaScript errors occurred."""
        return len(self.js_errors) > 0

    @property
    def all_errors(self) -> List[str]:
        """Get all captured errors."""
        return self.js_errors + self.console_errors

    @property
    def passed(self) -> bool:
        """Check if validation passed overall."""
        return (
            self.success_rate >= 0.9 and
            not self.has_js_errors and
            self.blocked_elements == 0
        )

    def get_blocked(self) -> List[ElementResult]:
        """Get all blocked element results."""
        return [r for r in self.element_results if r.is_blocked]

    def get_failed(self) -> List[ElementResult]:
        """Get all failed element results."""
        return [r for r in self.element_results if not r.is_success]

    def describe(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"ValidationResult: {'PASSED' if self.passed else 'FAILED'}",
            f"  Elements: {self.responsive_elements}/{self.total_elements} responsive",
        ]

        if self.blocked_elements:
            lines.append(f"  Blocked: {self.blocked_elements}")

        if self.js_errors:
            lines.append(f"  JS Errors: {len(self.js_errors)}")

        lines.append(f"  Time: {self.validation_time_ms:.0f}ms")

        return "\n".join(lines)
