"""
Playwright Element Diagnosis - Browser-based element analysis.

Uses Playwright to get actual computed styles, bounding boxes,
and elementFromPoint data for accurate interactivity diagnosis.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from ..contracts.errors import ErrorType


@dataclass
class BoundingRect:
    """Element bounding rectangle from getBoundingClientRect()."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center_x(self) -> float:
        """Get horizontal center point."""
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        """Get vertical center point."""
        return self.y + self.height / 2

    @property
    def is_visible_size(self) -> bool:
        """Check if element has visible dimensions (> 0)."""
        return self.width > 0 and self.height > 0

    def is_in_viewport(
        self, viewport_width: int = 1920, viewport_height: int = 1080
    ) -> bool:
        """Check if element is within viewport bounds."""
        return (
            self.x < viewport_width
            and self.y < viewport_height
            and self.x + self.width > 0
            and self.y + self.height > 0
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class VisibilityInfo:
    """Computed visibility information for an element."""

    display: str  # e.g., "block", "none", "flex"
    visibility: str  # e.g., "visible", "hidden"
    opacity: float  # 0.0 to 1.0
    width: float
    height: float
    in_viewport: bool

    @property
    def is_visible(self) -> bool:
        """Check if element is visually visible."""
        return (
            self.display != "none"
            and self.visibility != "hidden"
            and self.opacity > 0.01
            and self.width > 0
            and self.height > 0
        )

    @property
    def visibility_issue(self) -> Optional[ErrorType]:
        """Get the specific visibility error type if any."""
        if self.display == "none":
            return ErrorType.INVISIBLE_DISPLAY
        if self.visibility == "hidden":
            return ErrorType.INVISIBLE_VISIBILITY
        if self.opacity < 0.1:
            return ErrorType.INVISIBLE_OPACITY
        return None


@dataclass
class InterceptorInfo:
    """Information about an element intercepting clicks."""

    selector: str  # CSS selector for interceptor
    tag_name: str  # Tag name (e.g., "div")
    classes: List[str]  # Class list
    is_overlay: bool  # Has inset-0 or similar
    has_pointer_events_none: bool  # Has pointer-events: none
    z_index: Optional[int]  # Computed z-index

    def describe(self) -> str:
        """Generate human-readable description."""
        class_str = ".".join(self.classes[:3]) if self.classes else ""
        z_str = f"z-index {self.z_index}" if self.z_index is not None else "auto"
        return f"{self.tag_name}.{class_str} at {z_str}"


@dataclass
class StackingInfo:
    """CSS stacking context information."""

    z_index: Optional[int]  # Computed z-index (None if "auto")
    position: str  # "static", "relative", "absolute", "fixed"
    has_transform: bool  # Has CSS transform
    transform_value: Optional[str]  # The transform value if any
    creates_stacking_context: bool  # Whether element creates new stacking context


@dataclass
class PointerEventsInfo:
    """Pointer-events CSS property information."""

    value: str  # "auto", "none", etc.
    inherited: bool  # Whether value is inherited from parent
    effective: bool  # Whether element can receive pointer events

    @classmethod
    def from_computed(cls, value: str, parent_value: str) -> "PointerEventsInfo":
        """Create from computed style values."""
        inherited = value == parent_value and value == "none"
        effective = value != "none"
        return cls(value=value, inherited=inherited, effective=effective)


@dataclass
class ElementDiagnosis:
    """
    Complete diagnosis of an element's interactivity state.

    Combines visibility, stacking, pointer-events, and interceptor
    information to provide a full picture of why an element may
    not be clickable.
    """

    found: bool  # Whether element was found in DOM
    selector: str  # The selector used to find it
    visibility: Optional[VisibilityInfo]  # Visibility info
    interceptor: Optional[InterceptorInfo]  # Element blocking clicks (if any)
    stacking: Optional[StackingInfo]  # Stacking context info
    pointer_events: Optional[PointerEventsInfo]  # Pointer events info
    rect: Optional[BoundingRect]  # Bounding rectangle

    @property
    def is_clickable(self) -> bool:
        """Determine if element can receive clicks."""
        if not self.found:
            return False
        if self.visibility and not self.visibility.is_visible:
            return False
        if self.interceptor and not self.interceptor.has_pointer_events_none:
            return False
        if self.pointer_events and not self.pointer_events.effective:
            return False
        if self.rect and not self.rect.is_visible_size:
            return False
        return True

    @property
    def blocking_reason(self) -> Optional[ErrorType]:
        """Get the primary reason element is not clickable."""
        if not self.found:
            return ErrorType.UNKNOWN
        if self.visibility:
            issue = self.visibility.visibility_issue
            if issue:
                return issue
        if self.interceptor and not self.interceptor.has_pointer_events_none:
            return ErrorType.POINTER_BLOCKED
        if self.pointer_events and not self.pointer_events.effective:
            return ErrorType.POINTER_INTERCEPTED
        if self.stacking and self.stacking.has_transform:
            return ErrorType.TRANSFORM_OFFSCREEN
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return {
            "found": self.found,
            "selector": self.selector,
            "is_clickable": self.is_clickable,
            "blocking_reason": self.blocking_reason.value if self.blocking_reason else None,
            "visibility": {
                "display": self.visibility.display,
                "visibility": self.visibility.visibility,
                "opacity": self.visibility.opacity,
                "in_viewport": self.visibility.in_viewport,
            }
            if self.visibility
            else None,
            "interceptor": {
                "selector": self.interceptor.selector,
                "is_overlay": self.interceptor.is_overlay,
            }
            if self.interceptor
            else None,
            "rect": self.rect.to_dict() if self.rect else None,
        }


class PlaywrightDiagnostic:
    """
    Browser-based element diagnostic using Playwright.

    Provides accurate diagnosis by using actual browser rendering
    and computed styles rather than static analysis.
    """

    def __init__(self, viewport_width: int = 1920, viewport_height: int = 1080):
        """
        Initialize diagnostic.

        Args:
            viewport_width: Expected viewport width
            viewport_height: Expected viewport height
        """
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height

    async def diagnose_element(self, page, selector: str) -> ElementDiagnosis:
        """
        Diagnose an element's interactivity state.

        Args:
            page: Playwright Page instance
            selector: CSS selector for target element

        Returns:
            ElementDiagnosis with complete information
        """
        from .js_evaluators import JSEvaluators

        # Get all diagnosis data via JavaScript
        result = await page.evaluate(JSEvaluators.DIAGNOSE_ELEMENT, selector)

        if not result.get("found"):
            return ElementDiagnosis(
                found=False,
                selector=selector,
                visibility=None,
                interceptor=None,
                stacking=None,
                pointer_events=None,
                rect=None,
            )

        return self._parse_diagnosis_result(selector, result)

    async def diagnose_elements(
        self, page, selectors: List[str]
    ) -> Dict[str, ElementDiagnosis]:
        """
        Diagnose multiple elements.

        Args:
            page: Playwright Page instance
            selectors: List of CSS selectors

        Returns:
            Dictionary mapping selector to diagnosis
        """
        results = {}
        for selector in selectors:
            results[selector] = await self.diagnose_element(page, selector)
        return results

    async def find_interceptor_at_point(
        self, page, x: float, y: float
    ) -> Optional[InterceptorInfo]:
        """
        Find what element is at a specific point.

        Args:
            page: Playwright Page instance
            x: X coordinate
            y: Y coordinate

        Returns:
            InterceptorInfo for element at point, or None
        """
        from .js_evaluators import JSEvaluators

        result = await page.evaluate(JSEvaluators.ELEMENT_FROM_POINT, {"x": x, "y": y})

        if not result:
            return None

        return InterceptorInfo(
            selector=result["selector"],
            tag_name=result["tagName"],
            classes=result["classes"],
            is_overlay=result["isOverlay"],
            has_pointer_events_none=result["hasPointerEventsNone"],
            z_index=result.get("zIndex"),
        )

    async def test_click_reachable(self, page, selector: str) -> Dict[str, Any]:
        """
        Test if an element is reachable for clicking.

        Args:
            page: Playwright Page instance
            selector: CSS selector for target element

        Returns:
            Dict with 'reachable' bool and 'reason' if not reachable
        """
        from .js_evaluators import JSEvaluators

        return await page.evaluate(JSEvaluators.TEST_CLICK_REACHABLE, selector)

    def _parse_diagnosis_result(
        self, selector: str, result: Dict[str, Any]
    ) -> ElementDiagnosis:
        """Parse JavaScript evaluation result into ElementDiagnosis."""

        visibility = None
        if result.get("visibility"):
            v = result["visibility"]
            visibility = VisibilityInfo(
                display=v["display"],
                visibility=v["visibility"],
                opacity=v["opacity"],
                width=v["width"],
                height=v["height"],
                in_viewport=v["inViewport"],
            )

        interceptor = None
        if result.get("interceptor"):
            i = result["interceptor"]
            interceptor = InterceptorInfo(
                selector=i["selector"],
                tag_name=i["tagName"],
                classes=i["classes"],
                is_overlay=i["isOverlay"],
                has_pointer_events_none=i["hasPointerEventsNone"],
                z_index=i.get("zIndex"),
            )

        stacking = None
        if result.get("stacking"):
            s = result["stacking"]
            stacking = StackingInfo(
                z_index=s.get("zIndex"),
                position=s["position"],
                has_transform=s["hasTransform"],
                transform_value=s.get("transformValue"),
                creates_stacking_context=s["createsStackingContext"],
            )

        pointer_events = None
        if result.get("pointerEvents"):
            p = result["pointerEvents"]
            pointer_events = PointerEventsInfo(
                value=p["value"],
                inherited=p["inherited"],
                effective=p["effective"],
            )

        rect = None
        if result.get("rect"):
            r = result["rect"]
            rect = BoundingRect(
                x=r["x"],
                y=r["y"],
                width=r["width"],
                height=r["height"],
            )

        return ElementDiagnosis(
            found=True,
            selector=selector,
            visibility=visibility,
            interceptor=interceptor,
            stacking=stacking,
            pointer_events=pointer_events,
            rect=rect,
        )


# Convenience function matching the spec
async def diagnose_element(page, selector: str) -> ElementDiagnosis:
    """
    Diagnose a single element.

    Args:
        page: Playwright Page instance
        selector: CSS selector for target element

    Returns:
        ElementDiagnosis with complete information
    """
    diagnostic = PlaywrightDiagnostic()
    return await diagnostic.diagnose_element(page, selector)
