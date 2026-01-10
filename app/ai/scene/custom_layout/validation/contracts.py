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
from typing import Any, Dict, List, Optional, Tuple


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
    stabilization_ms: int = 150  # Wait after click for animations (reduced from 300)


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
    """
    before: VisualSnapshot
    after: VisualSnapshot
    pixel_diff_ratio: float  # 0.0 to 1.0 (% of pixels that changed)
    structural_change: bool   # Major layout change detected
    region_analyzed: Optional[BoundingBox] = None  # If comparison was regional

    def has_visible_change(self, threshold: float = 0.02) -> bool:
        """Check if change exceeds threshold."""
        return self.pixel_diff_ratio > threshold


# ---------------------------------------------------------------------------
# INPUT DETECTION (Phase 4)
# ---------------------------------------------------------------------------

@dataclass
class InputCandidate:
    """
    Detected clickable element.

    Ranked by confidence and priority for testing.

    EOR: When source_elements is populated, this candidate represents
    an event owner that was resolved from child elements. The selector
    is the owner, and source_elements lists the children that pointed to it.
    """
    selector: str           # CSS selector to click
    node: SceneNode         # Reference to scene graph node
    confidence: float       # 0.0 to 1.0 (how sure we are it's clickable)
    input_type: str         # button|link|checkbox|radio|custom
    priority: int           # Lower = test first
    source_elements: List[str] = field(default_factory=list)  # EOR: child selectors that resolved to this owner

    def __lt__(self, other: "InputCandidate") -> bool:
        """Sort by priority (ascending), then confidence (descending)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.confidence > other.confidence


# ---------------------------------------------------------------------------
# INTERACTION RESULTS (Phase 5)
# ---------------------------------------------------------------------------

@dataclass
class InteractionResult:
    """
    Result of testing a single input element.

    Contains before/after state and whether the input responded.
    """
    input: InputCandidate
    action: str  # click|hover|focus
    visual_delta: Optional[VisualDelta]
    scene_before: Optional[ObservedSceneGraph]
    scene_after: Optional[ObservedSceneGraph]
    responsive: bool  # Did the interaction produce observable change?
    error: Optional[str] = None
    duration_ms: float = 0.0

    def get_failure_type(self, threshold: float = 0.02) -> str:
        """
        Classify the type of failure for repair context.

        Returns:
            - "passed": Element responded adequately
            - "no_change": Zero or near-zero visual change (broken handler)
            - "under_threshold": Some change but below threshold (needs amplification)
            - "error": JavaScript or interaction error occurred
        """
        if self.responsive:
            return "passed"

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

        This is CRITICAL for the fixer to understand the REAL problem.
        """
        ratio = self.visual_delta.pixel_diff_ratio if self.visual_delta else 0.0
        failure_type = self.get_failure_type(threshold)

        # Build interpretation based on failure type
        if failure_type == "passed":
            interpretation = "Working correctly"
        elif failure_type == "no_change":
            interpretation = "Handler broken or not triggering visual change"
        elif failure_type == "under_threshold":
            multiplier = threshold / ratio if ratio > 0 else 10
            interpretation = f"Visual feedback too subtle. Needs ~{multiplier:.1f}x amplification"
        else:  # error
            interpretation = f"Error: {self.error}"

        return {
            "selector": self.input.selector,
            "action": self.action,
            "pixel_diff_ratio": ratio,
            "pixel_diff_pct": f"{ratio * 100:.2f}%",
            "threshold": f"{threshold * 100:.1f}%",
            "failure_type": failure_type,
            "interpretation": interpretation,
            "responsive": self.responsive,
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
# FINAL RESULT (Phase 6 output)
# ---------------------------------------------------------------------------

@dataclass
class SandboxResult:
    """
    Final aggregated validation result.

    This is what gets returned from the validation pipeline and
    passed to the fixer if validation fails.
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
