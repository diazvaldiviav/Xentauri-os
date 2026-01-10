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
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

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
    (lambda n: "data-option" in n.attributes, "option", 2, 0.95),
    (lambda n: "data-submit" in n.attributes, "button", 2, 0.92),
    (lambda n: "data-start" in n.attributes, "button", 2, 0.92),
    (lambda n: "data-restart" in n.attributes, "button", 3, 0.90),
    (lambda n: "data-answer" in n.attributes, "option", 2, 0.95),
    (lambda n: "data-choice" in n.attributes, "option", 2, 0.95),

    # Form inputs (checkboxes, radios)
    (lambda n: n.tag == "input" and n.attributes.get("type") == "radio", "radio", 3, 0.90),
    (lambda n: n.tag == "input" and n.attributes.get("type") == "checkbox", "checkbox", 3, 0.90),

    # Selects
    (lambda n: n.tag == "select", "select", 3, 0.90),

    # Elements with onclick (explicit handlers) - HIGH PRIORITY for trivia
    (lambda n: "onclick" in n.attributes, "custom", 3, 0.90),

    # Cursor pointer (CSS indicates clickable) - improved priority
    (lambda n: n.attributes.get("cursor") == "pointer", "custom", 4, 0.80),

    # Labels (often clickable in form contexts)
    (lambda n: n.tag == "label" and n.attributes.get("for"), "label", 5, 0.65),

    # ARIA states (often interactive)
    (lambda n: "aria-pressed" in n.attributes, "toggle", 4, 0.80),
    (lambda n: "aria-selected" in n.attributes, "option", 3, 0.85),
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

        # EOR: Resolve children to their event owners
        # This is the primary deduplication - groups children under their parent handlers
        candidates = self._resolve_event_owners(candidates, scene_graph)

        # Fallback filter for edge cases where EOR didn't detect ownership
        # If parent has onclick, don't test its children (they won't work independently)
        candidates = self._filter_nested_elements(candidates)

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

    def _resolve_event_owners(
        self,
        candidates: List[InputCandidate],
        scene_graph: ObservedSceneGraph,
    ) -> List[InputCandidate]:
        """
        EOR: Resolve child elements to their event owners.

        Problem: Child elements (span.option-letter) inherit cursor:pointer
        from parent (div.option with onclick). Clicking the child doesn't
        trigger the parent's handler in Playwright's click simulation.

        Solution: Use event_owner_candidate from scene graph to resolve
        children to their actual event owner.

        Process:
        1. Group candidates by their event_owner_candidate.selector
        2. For each group, create ONE InputCandidate with owner's selector
        3. Store child selectors in source_elements for traceability

        Returns:
            Deduplicated list with owners instead of children
        """
        if len(candidates) <= 1:
            return candidates

        # Group by owner selector
        # Key: owner selector (or self if no owner)
        # Value: list of (candidate, is_owner_itself)
        owner_groups: Dict[str, List[InputCandidate]] = {}

        for candidate in candidates:
            node = candidate.node

            # Check if this node has an event owner
            if node.event_owner_candidate:
                owner_selector = node.event_owner_candidate.selector
            else:
                # Self-owned - use own selector as key
                owner_selector = candidate.selector

            if owner_selector not in owner_groups:
                owner_groups[owner_selector] = []
            owner_groups[owner_selector].append(candidate)

        # Build resolved candidates
        resolved: List[InputCandidate] = []

        for owner_selector, group in owner_groups.items():
            # Check if the owner itself is in our candidates
            owner_candidate = None
            source_selectors = []

            for c in group:
                if c.selector == owner_selector:
                    # This is the owner itself
                    owner_candidate = c
                else:
                    # This is a child that resolved to owner
                    source_selectors.append(c.selector)

            if owner_candidate:
                # Owner was directly detected - use it with sources
                resolved.append(InputCandidate(
                    selector=owner_candidate.selector,
                    node=owner_candidate.node,
                    confidence=owner_candidate.confidence,
                    input_type=owner_candidate.input_type,
                    priority=owner_candidate.priority,
                    source_elements=source_selectors,
                ))
            else:
                # Owner not in candidates - need to find owner node in scene graph
                owner_node = scene_graph.find_by_selector(owner_selector)

                if owner_node:
                    # Use the best candidate's type/confidence as base
                    best = max(group, key=lambda c: c.confidence)
                    resolved.append(InputCandidate(
                        selector=owner_selector,
                        node=owner_node,
                        confidence=best.confidence,
                        input_type=best.input_type,
                        priority=best.priority,
                        source_elements=[c.selector for c in group],
                    ))
                else:
                    # Owner not found in scene graph - use first child as fallback
                    # This can happen if owner is outside viewport
                    logger.warning(
                        f"EOR: Owner {owner_selector} not in scene graph, "
                        f"using first child as fallback"
                    )
                    fallback = group[0]
                    resolved.append(InputCandidate(
                        selector=fallback.selector,
                        node=fallback.node,
                        confidence=fallback.confidence,
                        input_type=fallback.input_type,
                        priority=fallback.priority,
                        source_elements=[c.selector for c in group[1:]],
                    ))

        # Log EOR resolution
        original_count = len(candidates)
        resolved_count = len(resolved)
        if original_count != resolved_count:
            logger.info(
                f"EOR resolved {original_count} candidates -> {resolved_count} owners"
            )

        return resolved

    def _filter_nested_elements(
        self,
        candidates: List[InputCandidate],
    ) -> List[InputCandidate]:
        """
        Filter out children of already-detected interactive elements.

        NOTE: This is now a fallback. EOR (_resolve_event_owners) handles
        most child-parent resolution. This catches edge cases where
        event_owner_candidate wasn't detected but selector nesting exists.

        Problem: If a div.option has onclick, its children (span.option-letter)
        also get detected but clicking them doesn't trigger the parent's handler
        properly for visual validation.

        Solution: If selector B starts with selector A (B is child of A),
        remove B from candidates.

        Example:
        - Keep: 'div.options-grid > div:nth-of-type(1)'
        - Remove: 'div.options-grid > div:nth-of-type(1) > span.option-letter'
        """
        if len(candidates) <= 1:
            return candidates

        # Get all selectors
        selectors = [c.selector for c in candidates]

        # Find which selectors are children of others
        children_to_remove = set()

        for i, sel_a in enumerate(selectors):
            for j, sel_b in enumerate(selectors):
                if i == j:
                    continue
                # If sel_b starts with sel_a and is longer, sel_b is a child
                if sel_b.startswith(sel_a) and len(sel_b) > len(sel_a):
                    # sel_b is child of sel_a, mark for removal
                    children_to_remove.add(sel_b)

        # Filter out children
        filtered = [c for c in candidates if c.selector not in children_to_remove]

        if children_to_remove:
            logger.debug(
                f"Filtered {len(children_to_remove)} nested elements: "
                f"{list(children_to_remove)[:3]}"
            )

        return filtered

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
