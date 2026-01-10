"""
Input Detector - Phase 4: Detect interactive inputs.

Sprint 6: Visual-based validation system.

This module finds clickable elements using heuristics:
- Native inputs (button, input, select)
- Elements with role="button"
- Links with href
- Elements with cursor: pointer
- Elements with onclick handlers
- Data attributes (data-option, data-submit, etc.)
"""

import logging
import time
from typing import List, Optional, Tuple, TYPE_CHECKING

from .contracts import (
    InputCandidate,
    ObservedSceneGraph,
    PhaseResult,
    SceneNode,
    ValidationContract,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.input_detector")


# ---------------------------------------------------------------------------
# INPUT HEURISTICS
# ---------------------------------------------------------------------------

# Priority: Lower number = higher priority (test first)
# Confidence: How sure we are this is clickable (0.0 - 1.0)

INPUT_HEURISTICS = [
    # (match_function, input_type, priority, confidence)

    # Native buttons (highest confidence)
    (lambda n: n.tag == "button", "button", 1, 0.95),
    (lambda n: n.tag == "input" and n.attributes.get("type") == "submit", "button", 1, 0.95),
    (lambda n: n.tag == "input" and n.attributes.get("type") == "button", "button", 1, 0.95),

    # Role-based buttons
    (lambda n: n.attributes.get("role") == "button", "button", 2, 0.90),

    # Links
    (lambda n: n.tag == "a" and n.attributes.get("href"), "link", 2, 0.90),

    # Data attributes (from our prompts)
    (lambda n: "data-option" in n.attributes, "option", 3, 0.92),
    (lambda n: "data-submit" in n.attributes, "button", 2, 0.92),
    (lambda n: "data-start" in n.attributes, "button", 2, 0.92),
    (lambda n: "data-restart" in n.attributes, "button", 3, 0.90),

    # Form inputs (checkboxes, radios)
    (lambda n: n.tag == "input" and n.attributes.get("type") == "radio", "radio", 3, 0.90),
    (lambda n: n.tag == "input" and n.attributes.get("type") == "checkbox", "checkbox", 3, 0.90),

    # Selects
    (lambda n: n.tag == "select", "select", 3, 0.90),

    # Elements with onclick (explicit handlers)
    (lambda n: "onclick" in n.attributes, "custom", 4, 0.85),

    # Cursor pointer (CSS indicates clickable)
    (lambda n: n.attributes.get("cursor") == "pointer", "custom", 5, 0.70),

    # Labels (often clickable in form contexts)
    (lambda n: n.tag == "label" and n.attributes.get("for"), "label", 5, 0.65),

    # ARIA states (often interactive)
    (lambda n: "aria-pressed" in n.attributes, "toggle", 4, 0.80),
    (lambda n: "aria-selected" in n.attributes, "option", 4, 0.80),
    (lambda n: "aria-checked" in n.attributes, "checkbox", 4, 0.80),
]


# ---------------------------------------------------------------------------
# INPUT DETECTOR
# ---------------------------------------------------------------------------

class InputDetector:
    """
    Phase 4: Detect interactive inputs from scene graph.

    Finds elements that can be clicked/interacted with,
    prioritizes them for testing.
    """

    # Minimum clickable area (20x20 pixels)
    MIN_CLICK_AREA = 20 * 20

    # Minimum size in any dimension
    MIN_DIMENSION = 10

    async def detect(
        self,
        page: "Page",
        scene_graph: ObservedSceneGraph,
        contract: ValidationContract,
    ) -> Tuple[PhaseResult, List[InputCandidate]]:
        """
        Find interactive elements in the scene graph.

        Filters:
        - Must be visible
        - Must be in viewport
        - Must have minimum area
        - Must not be disabled

        Args:
            page: Playwright page (for potential additional checks)
            scene_graph: Observed scene graph from Phase 3
            contract: Validation contract with settings

        Returns:
            (PhaseResult, List[InputCandidate]) sorted by priority
        """
        start_time = time.time()
        candidates: List[InputCandidate] = []

        viewport_w, viewport_h = scene_graph.viewport

        for node in scene_graph.visible_nodes():
            # Skip nodes that are too small
            if node.bounding_box.area() < self.MIN_CLICK_AREA:
                continue

            if node.bounding_box.width < self.MIN_DIMENSION:
                continue

            if node.bounding_box.height < self.MIN_DIMENSION:
                continue

            # Skip nodes outside viewport
            if not node.bounding_box.in_viewport(viewport_w, viewport_h):
                continue

            # Skip disabled elements
            if node.attributes.get("disabled") is not None:
                continue

            # Check against heuristics
            for match_fn, input_type, priority, confidence in INPUT_HEURISTICS:
                try:
                    if match_fn(node):
                        candidates.append(InputCandidate(
                            selector=node.selector,
                            node=node,
                            confidence=confidence,
                            input_type=input_type,
                            priority=priority,
                        ))
                        break  # Only match first heuristic
                except Exception:
                    continue

        # Sort by priority (ascending), then confidence (descending)
        candidates.sort()

        # Take top N
        max_inputs = contract.max_inputs_to_test
        top_candidates = candidates[:max_inputs]

        duration_ms = (time.time() - start_time) * 1000

        # Build type distribution for logging
        type_counts = {}
        for c in top_candidates:
            type_counts[c.input_type] = type_counts.get(c.input_type, 0) + 1

        # Phase passes if we found at least one input
        # (For static layouts, this may fail but that's OK)
        passed = len(top_candidates) > 0

        if not passed:
            logger.info(
                f"Phase 4 (input_detection): No interactive inputs found "
                f"(total nodes: {len(scene_graph.nodes)})"
            )
            return PhaseResult(
                phase=4,
                phase_name="input_detection",
                passed=True,  # Not finding inputs is OK (might be static)
                details={
                    "found": 0,
                    "selected": 0,
                    "note": "No interactive elements found - may be static content",
                },
                duration_ms=duration_ms,
            ), []

        logger.info(
            f"Phase 4 (input_detection) - "
            f"found {len(candidates)}, selected {len(top_candidates)}, "
            f"types={type_counts}"
        )

        return PhaseResult(
            phase=4,
            phase_name="input_detection",
            passed=True,
            details={
                "found": len(candidates),
                "selected": len(top_candidates),
                "type_counts": type_counts,
                "selectors": [c.selector for c in top_candidates[:5]],  # First 5 for logging
            },
            duration_ms=duration_ms,
        ), top_candidates

    def filter_by_type(
        self,
        candidates: List[InputCandidate],
        input_types: List[str],
    ) -> List[InputCandidate]:
        """Filter candidates by input type."""
        return [c for c in candidates if c.input_type in input_types]

    def filter_by_region(
        self,
        candidates: List[InputCandidate],
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
    ) -> List[InputCandidate]:
        """Filter candidates to those within a region."""
        filtered = []
        for c in candidates:
            cx, cy = c.node.bounding_box.center()
            if x_min <= cx <= x_max and y_min <= cy <= y_max:
                filtered.append(c)
        return filtered


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

input_detector = InputDetector()
