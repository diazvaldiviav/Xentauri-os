"""
Interaction Validator - Phase 5: Core visual delta testing.

Sprint 6: Visual-based validation system.

This is the CORE module that eliminates false positives:
- Takes screenshot BEFORE click
- Clicks element
- Waits for stabilization (animations)
- Takes screenshot AFTER click
- Compares visual delta

If no visual change detected, the input is considered broken.
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple, TYPE_CHECKING

from .contracts import (
    InputCandidate,
    InteractionResult,
    ObservedSceneGraph,
    PhaseResult,
    ValidationContract,
    VisualDelta,
    VisualSnapshot,
)
from .visual_analyzer import visual_analyzer
from .scene_graph import scene_graph_extractor

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.interaction")


# ---------------------------------------------------------------------------
# INTERACTION VALIDATOR
# ---------------------------------------------------------------------------

class InteractionValidator:
    """
    Phase 5: Test each input with visual delta comparison.

    For each input candidate:
    1. Capture screenshot + scene graph (BEFORE)
    2. Click the element
    3. Wait for animations to stabilize
    4. Capture screenshot + scene graph (AFTER)
    5. Compare visual delta

    An input is considered "responsive" if:
    - Visual delta exceeds threshold, OR
    - Scene graph shows new/hidden nodes
    """

    # Padding around clicked element for region comparison
    REGION_PADDING = 100

    async def validate(
        self,
        page: "Page",
        inputs: List[InputCandidate],
        contract: ValidationContract,
    ) -> Tuple[PhaseResult, List[InteractionResult]]:
        """
        Test each input element with visual comparison.

        Args:
            page: Playwright page with HTML loaded
            inputs: List of input candidates from Phase 4
            contract: Validation contract with thresholds

        Returns:
            (PhaseResult, List[InteractionResult])
        """
        start_time = time.time()
        results: List[InteractionResult] = []

        if not inputs:
            # No inputs to test - this is OK for static content
            return PhaseResult(
                phase=5,
                phase_name="interaction",
                passed=True,
                details={
                    "tested": 0,
                    "responsive": 0,
                    "note": "No inputs to test",
                },
                duration_ms=(time.time() - start_time) * 1000,
            ), []

        # Test each input
        for input_candidate in inputs:
            result = await self._test_single_input(page, input_candidate, contract)
            results.append(result)

            # Log each result
            status = "RESPONSIVE" if result.responsive else "NO RESPONSE"
            delta = result.visual_delta.pixel_diff_ratio if result.visual_delta else 0
            logger.debug(
                f"  {input_candidate.selector}: {status} "
                f"(delta={delta:.3f}, threshold={contract.visual_change_threshold})"
            )

        # Count responsive inputs
        responsive_count = sum(1 for r in results if r.responsive)
        total_duration_ms = (time.time() - start_time) * 1000

        # Phase passes if at least one input is responsive
        passed = responsive_count > 0

        if not passed:
            logger.warning(
                f"Phase 5 (interaction): No inputs responded - "
                f"tested {len(results)}, all failed visual delta check"
            )
        else:
            logger.info(
                f"Phase 5 (interaction) passed - "
                f"{responsive_count}/{len(results)} inputs responsive"
            )

        return PhaseResult(
            phase=5,
            phase_name="interaction",
            passed=passed,
            error=f"No inputs responded to interaction ({len(results)} tested)" if not passed else None,
            details={
                "tested": len(results),
                "responsive": responsive_count,
                "responsive_selectors": [r.input.selector for r in results if r.responsive],
                "failed_selectors": [r.input.selector for r in results if not r.responsive],
            },
            duration_ms=total_duration_ms,
        ), results

    async def _test_single_input(
        self,
        page: "Page",
        input_candidate: InputCandidate,
        contract: ValidationContract,
    ) -> InteractionResult:
        """Test a single input element."""
        start_time = time.time()

        try:
            # 1. Capture BEFORE state
            before_screenshot = await visual_analyzer.capture(page)
            before_scene = await scene_graph_extractor.extract_quick(page)

            # 2. Click the element
            locator = page.locator(input_candidate.selector).first

            # Check if element exists and is visible
            if await locator.count() == 0:
                return InteractionResult(
                    input=input_candidate,
                    action="click",
                    visual_delta=None,
                    scene_before=before_scene,
                    scene_after=None,
                    responsive=False,
                    error=f"Element not found: {input_candidate.selector}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            if not await locator.is_visible():
                return InteractionResult(
                    input=input_candidate,
                    action="click",
                    visual_delta=None,
                    scene_before=before_scene,
                    scene_after=None,
                    responsive=False,
                    error=f"Element not visible: {input_candidate.selector}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Perform click
            await locator.click(timeout=contract.interaction_timeout_ms)

            # 3. Wait for stabilization (animations, transitions)
            await asyncio.sleep(contract.stabilization_ms / 1000)

            # 4. Capture AFTER state
            after_screenshot = await visual_analyzer.capture(page)
            after_scene = await scene_graph_extractor.extract_quick(page)

            # 5. Compare visual delta
            # Focus on region around the clicked element
            region = input_candidate.node.bounding_box.expand(self.REGION_PADDING)
            visual_delta = visual_analyzer.compare(before_screenshot, after_screenshot, region)

            # Also check full-page delta as fallback
            if visual_delta.pixel_diff_ratio < contract.visual_change_threshold:
                full_delta = visual_analyzer.compare(before_screenshot, after_screenshot)
                if full_delta.pixel_diff_ratio > visual_delta.pixel_diff_ratio:
                    visual_delta = full_delta

            # Determine if responsive
            responsive = visual_delta.has_visible_change(contract.visual_change_threshold)

            # If visual delta is low, also check scene graph changes
            if not responsive:
                responsive = self._scene_changed_significantly(before_scene, after_scene)

            return InteractionResult(
                input=input_candidate,
                action="click",
                visual_delta=visual_delta,
                scene_before=before_scene,
                scene_after=after_scene,
                responsive=responsive,
                duration_ms=(time.time() - start_time) * 1000,
            )

        except asyncio.TimeoutError:
            return InteractionResult(
                input=input_candidate,
                action="click",
                visual_delta=None,
                scene_before=None,
                scene_after=None,
                responsive=False,
                error=f"Timeout clicking: {input_candidate.selector}",
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return InteractionResult(
                input=input_candidate,
                action="click",
                visual_delta=None,
                scene_before=None,
                scene_after=None,
                responsive=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _scene_changed_significantly(
        self,
        before: ObservedSceneGraph,
        after: ObservedSceneGraph,
    ) -> bool:
        """
        Check if scene graph changed significantly.

        Significant changes:
        - New nodes appeared (more than just count change)
        - Nodes became visible/hidden
        - Node positions changed significantly
        """
        if before is None or after is None:
            return False

        # Check node count change
        before_count = len(before.visible_nodes())
        after_count = len(after.visible_nodes())

        if abs(after_count - before_count) >= 2:
            # Multiple nodes appeared/disappeared
            return True

        # Check for new nodes
        before_selectors = {n.selector for n in before.visible_nodes()}
        after_selectors = {n.selector for n in after.visible_nodes()}

        new_nodes = after_selectors - before_selectors
        hidden_nodes = before_selectors - after_selectors

        if new_nodes or hidden_nodes:
            # New elements appeared or existing ones disappeared
            return True

        # Check for position changes
        for node in after.visible_nodes():
            before_node = before.find_by_selector(node.selector)
            if before_node:
                # Check if position changed significantly
                dx = abs(node.bounding_box.x - before_node.bounding_box.x)
                dy = abs(node.bounding_box.y - before_node.bounding_box.y)
                if dx > 10 or dy > 10:
                    return True

                # Check if size changed significantly
                dw = abs(node.bounding_box.width - before_node.bounding_box.width)
                dh = abs(node.bounding_box.height - before_node.bounding_box.height)
                if dw > 10 or dh > 10:
                    return True

        return False


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

interaction_validator = InteractionValidator()
