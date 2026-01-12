"""
Validation Contracts - Data structures for visual validation pipeline.

Sprint 6: Visual-based validation system to eliminate false positives.

This module defines all dataclasses used throughout the 7-phase validation:
- Phase 0: ValidationContract (input)
- Phase 1-6: PhaseResult, various snapshots
- Final: SandboxResult (output)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# INTERACTION CATEGORIES
# ---------------------------------------------------------------------------

class InteractionCategory(Enum):
    """
    Sprint 6.4: Semantic classification of detected elements.

    "No todo lo clickeable debe reaccionar;
     pero todo lo reactivo debe ser visible."

    Categories determine how elements are tested and counted:
    - INTERACTIVE_UI: Click-tested, counted in responsive ratio
    - NAVIGATION: Excluded from click-delta test (links navigate away)
    - DISPLAY_ONLY: Excluded from testing (informational widgets)

    Only INTERACTIVE_UI elements enter the responsive ratio denominator.
    """
    INTERACTIVE_UI = "interactive_ui"  # Buttons, toggles, filters, options - TESTED
    NAVIGATION = "navigation"          # Links, sidebar items - EXCLUDED (navigate away)
    DISPLAY_ONLY = "display_only"      # Clocks, weather, charts - EXCLUDED (no click handler)


# ---------------------------------------------------------------------------
# PHASE 0: INPUT CONTRACT
# ---------------------------------------------------------------------------

@dataclass
class ValidationContract:
    """
    Input contract for validation pipeline.

    Defines what to validate and the thresholds for pass/fail decisions.
    Nothing enters the sandbox without this contract.
    """
    html: str
    viewport_width: int = 1920
    viewport_height: int = 1080
    layout_type: Optional[str] = None  # dashboard|trivia|mini_game|static|unknown
    max_retries: int = 2
    interaction_timeout_ms: int = 2000
    visual_change_threshold: float = 0.02  # 2% pixel difference = change detected
    blank_page_threshold: float = 0.95     # 95% uniform color = blank page
    max_inputs_to_test: int = 10
    stabilization_ms: int = 1000  # Wait after click for animations (1s for flips, transitions)


# ---------------------------------------------------------------------------
# GEOMETRIC PRIMITIVES
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    """Geometric bounding box for DOM elements."""
    x: float
    y: float
    width: float
    height: float

    def area(self) -> float:
        """Calculate area in pixels."""
        return self.width * self.height

    def in_viewport(self, viewport_width: int, viewport_height: int) -> bool:
        """Check if box is at least partially visible in viewport."""
        return (
            self.x < viewport_width and
            self.y < viewport_height and
            self.x + self.width > 0 and
            self.y + self.height > 0
        )

    def center(self) -> Tuple[float, float]:
        """Get center point of box."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def expand(self, padding: int) -> "BoundingBox":
        """Return new box expanded by padding pixels."""
        return BoundingBox(
            x=max(0, self.x - padding),
            y=max(0, self.y - padding),
            width=self.width + 2 * padding,
            height=self.height + 2 * padding,
        )


# ---------------------------------------------------------------------------
# SCENE GRAPH (Phase 3)
# ---------------------------------------------------------------------------

@dataclass
class EventOwnerCandidate:
    """
    EOR: Proposed event owner for an element.

    When a child element (like span.option-letter) inherits cursor:pointer
    from a parent with onclick, this captures the parent as the "owner".

    Phase 3 proposes, Phase 4 decides.
    """
    selector: str  # CSS selector of the owner element
    reason: str    # Why this is the owner (ancestor_with_onclick, ancestor_with_role_button, etc.)


@dataclass
class SceneNode:
    """
    Single node in the observed scene graph.

    Represents a visible DOM element with its geometry and properties.
    """
    selector: str  # CSS selector to locate this element
    tag: str       # HTML tag name (lowercase)
    node_type: str  # text|button|input|container|image|unknown
    bounding_box: BoundingBox
    visible: bool   # Currently visible in viewport
    z_index: int    # Stacking order
    text_content: Optional[str] = None  # Inner text (truncated)
    attributes: Dict[str, str] = field(default_factory=dict)
    event_owner_candidate: Optional[EventOwnerCandidate] = None  # EOR: proposed owner

    def is_interactive(self) -> bool:
        """Check if node is likely interactive."""
        return self.node_type in ("button", "input") or "onclick" in self.attributes


@dataclass
class ObservedSceneGraph:
    """
    Complete scene graph extracted from DOM inspection.

    This is the geometric truth - actual positions and visibility
    of elements, not what the HTML says should be there.
    """
    nodes: List[SceneNode]
    viewport: Tuple[int, int]  # (width, height)
    capture_time_ms: float

    def visible_nodes(self) -> List[SceneNode]:
        """Get only visible nodes."""
        return [n for n in self.nodes if n.visible]

    def by_type(self, node_type: str) -> List[SceneNode]:
        """Filter nodes by type."""
        return [n for n in self.nodes if n.node_type == node_type]

    def interactive_nodes(self) -> List[SceneNode]:
        """Get nodes that appear interactive."""
        return [n for n in self.visible_nodes() if n.is_interactive()]

    def find_by_selector(self, selector: str) -> Optional[SceneNode]:
        """Find node by CSS selector."""
        for node in self.nodes:
            if node.selector == selector:
                return node
        return None


# ---------------------------------------------------------------------------
# VISUAL SNAPSHOTS (Phase 2)
# ---------------------------------------------------------------------------

@dataclass
class VisualSnapshot:
    """
    Screenshot with computed visual statistics.

    Used to detect blank pages and measure visual changes.
    """
    image_bytes: bytes      # PNG image data
    width: int
    height: int
    histogram: List[int]    # 256-bin grayscale histogram
    mean_pixel: float       # Average pixel value (0-255)
    variance: float         # Pixel variance (uniformity measure)
    non_background_ratio: float  # % of pixels different from background

    def is_blank(self, threshold: float = 0.95) -> bool:
        """
        Check if image is mostly uniform (blank).

        A page is NOT blank if:
        - non_background_ratio >= (1 - threshold), OR
        - variance is high (>100) indicating visual differentiation

        This handles dark-themed content like space visualizations where
        background dominates but content has meaningful visual variance.
        """
        # If variance is high, there's visual content even if background dominates
        # A truly blank page has variance near 0
        MIN_VARIANCE_FOR_CONTENT = 100
        if self.variance > MIN_VARIANCE_FOR_CONTENT:
            return False  # High variance = not blank

        return self.non_background_ratio < (1 - threshold)


@dataclass
class VisualDelta:
    """
    Comparison result between two screenshots.

    Used to detect if a click produced visible changes.

    Sprint 6.2: Now includes absolute pixel counts for fixer context.
    Sprint 6.3: Adaptive threshold - element-relative detection.
    "El fixer necesita números concretos, no solo porcentajes."
    """
    before: VisualSnapshot
    after: VisualSnapshot
    pixel_diff_ratio: float  # 0.0 to 1.0 (% of pixels that changed)
    structural_change: bool   # Major layout change detected
    region_analyzed: Optional[BoundingBox] = None  # If comparison was regional
    # Sprint 6.2: Absolute pixel counts for concrete fixer guidance
    diff_count: int = 0       # Number of pixels that changed (absolute)
    total_pixels: int = 0     # Total pixels compared (viewport or region)
    # Sprint 6.3: Element-relative metrics for adaptive threshold
    element_pixels: int = 0   # Pixels in the clicked element's bounding box
    element_diff_ratio: float = 0.0  # % of ELEMENT pixels that changed (not viewport)

    def has_visible_change(self, threshold: float = 0.02, element_threshold: float = 0.30) -> bool:
        """
        Check if change exceeds threshold using adaptive detection.
        
        Sprint 6.3: Dual-threshold system:
        1. Global threshold (2%): For large visual changes (overlays, panels)
        2. Element threshold (30%): For small interactive elements (buttons, options)
        
        An element is responsive if EITHER:
        - Global change >= threshold (2% of viewport), OR
        - Element-local change >= element_threshold (30% of element area)
        
        This fixes the impossible math for small buttons:
        - Button 100x40 = 4000px = 0.19% of viewport (never reaches 2%)
        - But if 30% of button pixels change, that's clearly responsive
        """
        # Primary: global threshold (catches large changes)
        if self.pixel_diff_ratio >= threshold:
            return True
        
        # Secondary: element-relative threshold (catches small element changes)
        # A button that changes 30%+ of its own pixels is clearly responsive
        if self.element_diff_ratio >= element_threshold:
            return True
        
        return False

    def get_pixels_needed(self, threshold: float = 0.02) -> int:
        """Calculate how many pixels need to change to meet threshold."""
        return int(self.total_pixels * threshold)

    def get_pixels_gap(self, threshold: float = 0.02) -> int:
        """Calculate how many MORE pixels need to change."""
        needed = self.get_pixels_needed(threshold)
        return max(0, needed - self.diff_count)


# ---------------------------------------------------------------------------
# INPUT DETECTION (Phase 4)
# ---------------------------------------------------------------------------

@dataclass
class InteractionUnit:
    """
    Sprint 6.2: Individual interaction unit within an event owner.

    "El evento puede ser uno solo, pero las decisiones del usuario nunca lo son."

    An InteractionUnit represents a distinct user choice, even when the event
    is delegated to a parent. Examples:
    - Option A, B, C, D in a trivia
    - Cards in a grid
    - Menu items

    The parent may handle the event via delegation, but each unit is
    a separate interaction that must be tested independently.
    """
    selector: str           # CSS selector to click this specific unit
    value: Optional[str]    # Semantic value (e.g., "A", "B", "correct", etc.)
    node: SceneNode         # Reference to scene graph node
    text_content: Optional[str] = None  # Display text for logging


@dataclass
class InputCandidate:
    """
    Detected clickable element or event owner.

    Ranked by confidence and priority for testing.

    Sprint 6.4: Classification by interaction category:
    - INTERACTIVE_UI: Tested for visual feedback, counted in ratio
    - NAVIGATION: Excluded (links navigate away)
    - DISPLAY_ONLY: Excluded (informational widgets without handlers)

    Sprint 7: Visibility detection:
    - Elements can exist in DOM but be invisible (transform, opacity, z-index)
    - visibility_status tracks if element has visible pixels

    The owner handles the event, but each unit is a distinct user decision.
    """
    selector: str           # CSS selector of the event owner
    node: SceneNode         # Reference to scene graph node
    confidence: float       # 0.0 to 1.0 (how sure we are it's clickable)
    input_type: str         # button|link|checkbox|radio|option|custom|display
    priority: int           # Lower = test first
    source_elements: List[str] = field(default_factory=list)  # Legacy: child selectors
    interaction_units: List[InteractionUnit] = field(default_factory=list)  # Sprint 6.2: distinct clickable units
    # Sprint 6.4: Semantic classification with reason tracking
    interaction_category: InteractionCategory = InteractionCategory.INTERACTIVE_UI
    testable: bool = True  # False for NAVIGATION and DISPLAY_ONLY
    category_reason: str = ""  # Why this category was assigned (for debugging/fixer)
    # Sprint 7: Visibility detection
    visibility_status: str = "unknown"  # "visible" | "invisible" | "partial" | "unknown"
    visibility_pixels: int = 0          # Non-transparent pixels in bounding box
    visibility_ratio: float = 0.0       # % of bounding box with visible content

    def __lt__(self, other: "InputCandidate") -> bool:
        """Sort by priority (ascending), then confidence (descending)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.confidence > other.confidence

    def get_test_count(self) -> int:
        """Return number of interactions to test for this candidate."""
        if not self.testable:
            return 0  # NAVIGATION and DISPLAY_ONLY elements don't get tested
        if self.interaction_units:
            return len(self.interaction_units)
        return 1  # Just the owner itself

    def is_navigation(self) -> bool:
        """Check if this is a navigation element (excluded from ratio)."""
        return self.interaction_category == InteractionCategory.NAVIGATION

    def is_display_only(self) -> bool:
        """Check if this is a display-only element (excluded from ratio)."""
        return self.interaction_category == InteractionCategory.DISPLAY_ONLY

    def is_excluded(self) -> bool:
        """Check if this element is excluded from testing and ratio."""
        return self.interaction_category in (
            InteractionCategory.NAVIGATION,
            InteractionCategory.DISPLAY_ONLY,
        )

    def is_invisible(self) -> bool:
        """
        Sprint 7: Check if element exists in DOM but has no visible pixels.

        An invisible element should not be tested for interaction -
        clicking invisible elements always fails, but it's not a CSS feedback issue.
        """
        return self.visibility_status == "invisible"

    def is_visible(self) -> bool:
        """Sprint 7: Check if element has visible pixels."""
        return self.visibility_status in ("visible", "partial", "unknown")


# ---------------------------------------------------------------------------
# INTERACTION RESULTS (Phase 5)
# ---------------------------------------------------------------------------

@dataclass
class InteractionResult:
    """
    Result of testing a single input element.

    Contains before/after state and whether the input responded.

    Sprint 7: Now includes screenshots for vision-based repair.
    """
    input: InputCandidate
    action: str  # click|hover|focus
    visual_delta: Optional[VisualDelta]
    scene_before: Optional[ObservedSceneGraph]
    scene_after: Optional[ObservedSceneGraph]
    responsive: bool  # Did the interaction produce observable change?
    error: Optional[str] = None
    duration_ms: float = 0.0
    # Sprint 7: Screenshots for vision repair
    screenshot_before: Optional[bytes] = None  # PNG before click
    screenshot_after: Optional[bytes] = None   # PNG after click

    def get_failure_type(self, threshold: float = 0.02) -> str:
        """
        Classify the type of failure for repair context.

        Returns:
            - "passed": Element responded adequately
            - "element_invisible": Element exists in DOM but has no visible pixels (Sprint 7)
            - "no_change": Zero or near-zero visual change (broken handler)
            - "under_threshold": Some change but below threshold (needs amplification)
            - "error": JavaScript or interaction error occurred
        """
        if self.responsive:
            return "passed"

        # Sprint 7: Check if element is invisible
        if self.input.is_invisible():
            return "element_invisible"

        if self.error:
            return "error"

        if not self.visual_delta:
            return "no_change"

        ratio = self.visual_delta.pixel_diff_ratio

        # Near-zero change = handler likely broken
        if ratio < 0.001:  # Less than 0.1%
            return "no_change"

        # Some change but not enough = needs visual amplification
        if ratio < threshold:
            return "under_threshold"

        return "passed"

    def get_repair_context(self, threshold: float = 0.02) -> Dict[str, Any]:
        """
        Get rich context for the fixer, including failure classification.

        Sprint 6.2: Now includes SEMANTIC context and CONCRETE PIXEL COUNTS
        so the fixer understands WHAT the element is, WHAT it should do,
        and EXACTLY how much more visual change is needed.

        "El fixer necesita números concretos, no solo porcentajes."
        """
        ratio = self.visual_delta.pixel_diff_ratio if self.visual_delta else 0.0
        failure_type = self.get_failure_type(threshold)

        # Sprint 6.2: Get concrete pixel counts
        pixels_changed = self.visual_delta.diff_count if self.visual_delta else 0
        total_pixels = self.visual_delta.total_pixels if self.visual_delta else 0
        pixels_needed = int(total_pixels * threshold) if total_pixels > 0 else 0
        pixels_gap = max(0, pixels_needed - pixels_changed)

        # Element area from bounding box
        node = self.input.node
        element_area = int(node.bounding_box.area())
        element_pct = (element_area / total_pixels * 100) if total_pixels > 0 else 0

        # Build interpretation with concrete guidance
        # Sprint 6.3: Safer strategies that don't break other elements
        # Sprint 7: Added element_invisible case
        if failure_type == "passed":
            interpretation = "Working correctly"
            strategy = None
        elif failure_type == "element_invisible":
            # Sprint 7: Element exists in DOM but has no visible pixels
            interpretation = (
                f"CRITICAL: Element exists in DOM but is INVISIBLE (has no visible pixels). "
                f"Visibility ratio: {self.input.visibility_ratio:.1%}"
            )
            strategy = (
                "This is NOT a CSS feedback issue - the element doesn't render at all! "
                "Possible causes: (1) JavaScript not executing/creating element properly, "
                "(2) CSS transform hiding element (e.g., rotateX/Y placing it out of view), "
                "(3) opacity: 0 or visibility: hidden, (4) z-index placing it behind other elements, "
                "(5) display: none or width/height: 0. "
                "FIX: Check if element is created by JavaScript that may be failing. "
                "If using 3D transforms, ensure elements stay in viewport."
            )
        elif failure_type == "no_change":
            interpretation = "Handler broken or not triggering visual change"
            strategy = (
                "Check onclick handler is properly connected. "
                "Ensure it modifies THIS element's CSS (background-color, transform, opacity). "
                "Use element-specific selector like [data-option='X'] or #unique-id."
            )
        elif failure_type == "under_threshold":
            interpretation = f"Visual feedback too subtle. Changed {pixels_changed:,} pixels but validator uses SCREENSHOT comparison."
            # Sprint 6.5: Aligned strategy with validator - background change is MANDATORY
            strategy = (
                f"MANDATORY: Change background-color on click (e.g., background: #ffffff or rgba(0,255,0,0.3)). "
                f"OPTIONAL additions: border: 4px solid #00ff00, transform: scale(1.05), box-shadow: 0 0 20px #00ff00. "
                f"PROHIBITED (will fail validation): var(--anything), filter: brightness/opacity, border-only, opacity-only. "
                f"Use CONCRETE colors only: #ffffff, #00ff00, rgba(0,255,0,0.3) - NOT CSS variables."
            )
        else:  # error
            interpretation = f"Error: {self.error}"
            strategy = "Fix the JavaScript error first"

        # Extract semantic information from the node
        text_content = node.text_content[:50] if node.text_content else None

        # Extract key attributes (data-*, role, aria-*, onclick presence)
        key_attrs = {}
        for attr, val in node.attributes.items():
            if attr.startswith("data-") or attr.startswith("aria-") or attr in ("role", "type", "value"):
                key_attrs[attr] = val[:50] if isinstance(val, str) and len(val) > 50 else val
            elif attr == "onclick":
                key_attrs["onclick"] = "present"

        return {
            "selector": self.input.selector,
            "action": self.action,
            "pixel_diff_ratio": ratio,
            "pixel_diff_pct": f"{ratio * 100:.2f}%",
            "threshold": f"{threshold * 100:.1f}%",
            "failure_type": failure_type,
            "interpretation": interpretation,
            "responsive": self.responsive,
            # Sprint 6.2: Concrete pixel counts for intelligent repair
            "pixels": {
                "changed": pixels_changed,
                "needed": pixels_needed,
                "gap": pixels_gap,
                "total_viewport": total_pixels,
            },
            # Sprint 6.2: Semantic context
            # Sprint 7: Added visibility info
            "element": {
                "tag": node.tag,
                "input_type": self.input.input_type,
                "text_content": text_content,
                "key_attributes": key_attrs,
                "area_pixels": element_area,
                "area_pct": f"{element_pct:.2f}%",
                "visibility_status": self.input.visibility_status,
                "visibility_ratio": f"{self.input.visibility_ratio:.1%}",
            },
            # Sprint 6.2: Concrete repair strategy
            "strategy": strategy,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "selector": self.input.selector,
            "action": self.action,
            "responsive": self.responsive,
            "pixel_diff": self.visual_delta.pixel_diff_ratio if self.visual_delta else 0,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# PHASE RESULTS
# ---------------------------------------------------------------------------

@dataclass
class PhaseResult:
    """
    Result of a single validation phase.

    Each phase produces one of these, which are aggregated into SandboxResult.
    """
    phase: int          # 1-6
    phase_name: str     # render|visual|scene_graph|input_detection|interaction|aggregation
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": self.phase,
            "name": self.phase_name,
            "passed": self.passed,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# REPAIR HISTORY (Sprint 8)
# ---------------------------------------------------------------------------

@dataclass
class FailedRepairAttempt:
    """
    Sprint 8: Record of a failed repair attempt.

    This is passed to subsequent repair attempts so Sonnet doesn't
    repeat the same mistakes.

    "El fixer debe aprender de sus errores anteriores."
    """
    attempt_number: int
    failure_reason: str  # "destructive" | "insufficient" | "no_html"
    inputs_before: int   # Original interactive count
    inputs_after: int    # After repair (for destructive detection)
    responsive_before: int
    responsive_after: int
    # What the fixer tried that didn't work
    key_changes_attempted: List[str] = field(default_factory=list)

    def to_summary(self) -> str:
        """Generate human-readable summary for prompt."""
        if self.failure_reason == "destructive":
            return (
                f"Attempt {self.attempt_number}: REJECTED (destructive) - "
                f"Removed {self.inputs_before - self.inputs_after} interactive elements "
                f"(had {self.inputs_before}, now {self.inputs_after})"
            )
        elif self.failure_reason == "insufficient":
            return (
                f"Attempt {self.attempt_number}: FAILED (insufficient) - "
                f"Only {self.responsive_after}/{self.inputs_after} responsive "
                f"(was {self.responsive_before}/{self.inputs_before})"
            )
        else:
            return f"Attempt {self.attempt_number}: FAILED - {self.failure_reason}"


# ---------------------------------------------------------------------------
# FINAL RESULT (Phase 6 output)
# ---------------------------------------------------------------------------

@dataclass
class SandboxResult:
    """
    Final aggregated validation result.

    This is what gets returned from the validation pipeline and
    passed to the fixer if validation fails.

    Sprint 7: Now includes page screenshot for vision-based repair.
    """
    valid: bool
    phases: List[PhaseResult]
    inputs_tested: int
    inputs_responsive: int
    confidence: float  # 0.0 to 1.0
    layout_type: str
    total_duration_ms: float
    failure_summary: Optional[str] = None
    interaction_results: List[InteractionResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    # Sprint 7: Screenshot for vision repair
    page_screenshot: Optional[bytes] = None  # PNG of full page
    screenshot_path: Optional[str] = None    # Path where screenshot was saved
    # Sprint 7: Count of invisible elements
    invisible_elements_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization/logging."""
        return {
            "valid": self.valid,
            "phases": [p.to_dict() for p in self.phases],
            "inputs_tested": self.inputs_tested,
            "inputs_responsive": self.inputs_responsive,
            "confidence": self.confidence,
            "layout_type": self.layout_type,
            "total_duration_ms": self.total_duration_ms,
            "failure_summary": self.failure_summary,
        }

    def to_repair_context(self) -> str:
        """
        Format for LLM repair prompt.

        Provides structured failure information to Codex-Max.
        """
        lines = [
            f"Validation Result: {'PASS' if self.valid else 'FAIL'}",
            f"Layout Type: {self.layout_type}",
            f"Confidence: {self.confidence:.2f}",
            "",
            "## Phase Results",
        ]

        for p in self.phases:
            status = "PASS" if p.passed else "FAIL"
            lines.append(f"  Phase {p.phase} ({p.phase_name}): {status}")
            if not p.passed:
                if p.error:
                    lines.append(f"    Error: {p.error}")
                if p.details:
                    for key, value in p.details.items():
                        lines.append(f"    {key}: {value}")

        if self.inputs_tested > 0:
            lines.append("")
            lines.append("## Interaction Results")
            lines.append(f"  Inputs Tested: {self.inputs_tested}")
            lines.append(f"  Inputs Responsive: {self.inputs_responsive}")

            if self.interaction_results:
                lines.append("  Details:")
                for ir in self.interaction_results:
                    status = "OK" if ir.responsive else "NO RESPONSE"
                    diff = ir.visual_delta.pixel_diff_ratio if ir.visual_delta else 0
                    lines.append(f"    - {ir.input.selector}: {status} (delta={diff:.3f})")
                    if ir.error:
                        lines.append(f"      Error: {ir.error}")

        if self.failure_summary:
            lines.append("")
            lines.append(f"## Failure Summary")
            lines.append(f"  {self.failure_summary}")

        return "\n".join(lines)

    def get_failed_phases(self) -> List[PhaseResult]:
        """Get list of phases that failed."""
        return [p for p in self.phases if not p.passed]

    def get_unresponsive_inputs(self) -> List[InteractionResult]:
        """Get inputs that didn't respond to interaction."""
        return [ir for ir in self.interaction_results if not ir.responsive]
