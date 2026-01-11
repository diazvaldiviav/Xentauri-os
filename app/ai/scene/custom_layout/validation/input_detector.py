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
    InteractionCategory,
    InteractionUnit,
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
                        # Sprint 6.2: Classify by interaction category
                        # Links are NAVIGATION - they navigate, don't produce local visual feedback
                        if input_type == "link":
                            category = InteractionCategory.NAVIGATION
                            testable = False
                        else:
                            category = InteractionCategory.INTERACTIVE_UI
                            testable = True

                        candidates.append(InputCandidate(
                            selector=node.selector,
                            node=node,
                            confidence=confidence,
                            input_type=input_type,
                            priority=priority,
                            interaction_category=category,
                            testable=testable,
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

        # Sprint 6.2: Count by interaction category
        interactive_count = sum(1 for c in top_candidates if c.testable)
        navigation_count = sum(1 for c in top_candidates if not c.testable)

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
                    "interactive_ui": 0,
                    "navigation": 0,
                    "note": "No interactive elements found - may be static content",
                },
                duration_ms=duration_ms,
            ), []

        logger.info(
            f"Phase 4 (input_detection) - "
            f"found {len(candidates)}, selected {len(top_candidates)} "
            f"({interactive_count} interactive, {navigation_count} navigation), "
            f"types={type_counts}"
        )

        return PhaseResult(
            phase=4,
            phase_name="input_detection",
            passed=True,
            details={
                "found": len(candidates),
                "selected": len(top_candidates),
                "interactive_ui": interactive_count,
                "navigation": navigation_count,
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
        EOR: Resolve child elements to their event owners with Interaction Units.

        Sprint 6.2: "El evento puede ser uno solo, pero las decisiones del usuario
        nunca lo son."

        Problem: Old EOR collapsed ALL children to their parent owner.
        This was correct for decorative children (spans, icons), but WRONG
        for semantic children (trivia options A, B, C, D).

        New Solution:
        1. Group candidates by their event_owner_candidate.selector
        2. Check if group members have SEMANTIC IDENTITY:
           - Distinct data-* attributes (data-option="A" vs "B")
           - Different text content
           - Non-overlapping bounding boxes
        3. If semantic identity exists: create InteractionUnits
        4. If no semantic identity: collapse as before

        Returns:
            List of InputCandidates, some with interaction_units populated
        """
        if len(candidates) <= 1:
            return candidates

        # Group by owner selector
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
            if len(group) == 1:
                # Single element - no resolution needed
                resolved.append(group[0])
                continue

            # Sprint 6.2: Atomic owner compuerta
            # If owner is an atomic control (button/a/input/select/textarea/role=button),
            # do NOT extract interaction units - children are decorative (spans, icons)
            owner_node = scene_graph.find_by_selector(owner_selector)
            if owner_node and self._is_atomic_control(owner_node):
                # Atomic control - collapse to owner without semantic units
                best = max(group, key=lambda c: c.confidence)
                resolved.append(InputCandidate(
                    selector=owner_selector,
                    node=owner_node,
                    confidence=best.confidence,
                    input_type=best.input_type,
                    priority=best.priority,
                    source_elements=[c.selector for c in group if c.selector != owner_selector],
                ))
                continue

            # Check for semantic identity in the group
            semantic_units = self._extract_semantic_units(group, scene_graph)

            if semantic_units:
                # Group has semantic identity - create owner with interaction_units
                owner_node = scene_graph.find_by_selector(owner_selector)
                if not owner_node:
                    # Use first group element's node as fallback
                    owner_node = group[0].node

                best = max(group, key=lambda c: c.confidence)

                resolved.append(InputCandidate(
                    selector=owner_selector,
                    node=owner_node,
                    confidence=best.confidence,
                    input_type="option",  # Multiple-choice type
                    priority=best.priority,
                    source_elements=[c.selector for c in group],
                    interaction_units=semantic_units,
                ))

                logger.info(
                    f"EOR: Owner {owner_selector} has {len(semantic_units)} interaction units"
                )
            else:
                # No semantic identity - collapse to owner (old behavior)
                owner_candidate = None
                source_selectors = []

                for c in group:
                    if c.selector == owner_selector:
                        owner_candidate = c
                    else:
                        source_selectors.append(c.selector)

                if owner_candidate:
                    resolved.append(InputCandidate(
                        selector=owner_candidate.selector,
                        node=owner_candidate.node,
                        confidence=owner_candidate.confidence,
                        input_type=owner_candidate.input_type,
                        priority=owner_candidate.priority,
                        source_elements=source_selectors,
                    ))
                else:
                    owner_node = scene_graph.find_by_selector(owner_selector)
                    if owner_node:
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
                        # Fallback to first child
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
        total_units = sum(len(c.interaction_units) for c in resolved)

        if original_count != resolved_count or total_units > 0:
            logger.info(
                f"EOR resolved {original_count} candidates -> "
                f"{resolved_count} owners, {total_units} interaction units"
            )

        return resolved

    def _extract_semantic_units(
        self,
        group: List[InputCandidate],
        scene_graph: ObservedSceneGraph,
    ) -> List[InteractionUnit]:
        """
        Extract interaction units from a group of candidates with semantic identity.

        Semantic identity markers (in priority order):
        1. data-option, data-answer, data-choice attributes with distinct values
        2. Different text content (not just whitespace differences)
        3. Non-overlapping bounding boxes in a grid/list pattern

        Returns:
            List of InteractionUnits if semantic identity found, empty list otherwise
        """
        # Data attributes that indicate semantic identity
        SEMANTIC_DATA_ATTRS = ["data-option", "data-answer", "data-choice", "data-value", "data-id"]

        units: List[InteractionUnit] = []
        seen_values = set()

        for candidate in group:
            node = candidate.node
            attrs = node.attributes

            # Check for semantic data attributes
            # Sprint 6.2 Fix: Empty data-* must NOT block fallback to text_content
            # "data-option='' debe tratarse como None, no como valor encontrado"
            semantic_value = None
            for attr in SEMANTIC_DATA_ATTRS:
                if attr in attrs:
                    val = attrs[attr]
                    if val and val.strip():  # Only accept non-empty values
                        semantic_value = val
                        break
                    # Empty value - continue searching other attrs

            # If no data attribute, use text content as value
            if semantic_value is None:
                text = (node.text_content or "").strip()
                if text and len(text) < 100:  # Reasonable text length
                    semantic_value = text

            if semantic_value and semantic_value not in seen_values:
                seen_values.add(semantic_value)
                units.append(InteractionUnit(
                    selector=candidate.selector,
                    value=semantic_value,
                    node=node,
                    text_content=node.text_content,
                ))

        # Need at least 2 distinct units to qualify as semantic group
        if len(units) < 2:
            return []

        # Additional validation: check for non-overlapping bounding boxes
        # This filters out cases where "distinct" values are just nested elements
        if not self._has_distinct_positions(units):
            return []

        return units

    def _has_distinct_positions(self, units: List[InteractionUnit]) -> bool:
        """
        Check if units have distinct, non-overlapping positions.

        This filters out false positives where nested elements have
        different text but are visually the same element.

        Returns:
            True if units are in distinct visual positions
        """
        if len(units) < 2:
            return False

        # Check that at least 50% of pairs don't overlap significantly
        non_overlapping = 0
        total_pairs = 0

        for i, unit_a in enumerate(units):
            for j, unit_b in enumerate(units):
                if i >= j:
                    continue

                total_pairs += 1
                box_a = unit_a.node.bounding_box
                box_b = unit_b.node.bounding_box

                # Calculate overlap
                overlap_x = max(0, min(box_a.x + box_a.width, box_b.x + box_b.width) - max(box_a.x, box_b.x))
                overlap_y = max(0, min(box_a.y + box_a.height, box_b.y + box_b.height) - max(box_a.y, box_b.y))
                overlap_area = overlap_x * overlap_y

                min_area = min(box_a.area(), box_b.area())
                overlap_ratio = overlap_area / min_area if min_area > 0 else 0

                # Less than 30% overlap = distinct
                if overlap_ratio < 0.30:
                    non_overlapping += 1

        # At least 50% of pairs must be distinct
        return total_pairs > 0 and (non_overlapping / total_pairs) >= 0.50

    def _is_atomic_control(self, node: SceneNode) -> bool:
        """
        Sprint 6.2: Check if node is an atomic control.

        Atomic controls should NOT have their children extracted as
        interaction units - children are decorative (spans, icons, text).

        Examples:
        - <button><span>Click</span><svg>...</svg></button> -> atomic
        - <a href="..."><span>Link</span></a> -> atomic
        - <div data-trivia="container">...</div> -> NOT atomic (container)

        Returns:
            True if node is an atomic control
        """
        # Atomic HTML elements
        ATOMIC_TAGS = {"button", "a", "input", "select", "textarea"}

        if node.tag in ATOMIC_TAGS:
            return True

        # Role-based atomic controls
        if node.attributes.get("role") == "button":
            return True

        return False

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
