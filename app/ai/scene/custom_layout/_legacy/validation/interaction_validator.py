"""
Interaction Validator - Phase 5: Core visual delta testing.

Sprint 6: Visual-based validation system.
Sprint 7: Added JS error detection after clicks.
Sprint 12: Cascading validation for modal/overlay content.

This is the CORE module that eliminates false positives:
- Takes screenshot BEFORE click
- Clicks element
- Waits for stabilization (animations)
- Takes screenshot AFTER click
- Compares visual delta
- Checks for JS errors that occurred during interaction
- Sprint 12: If click opens modal, re-scan and test modal's elements

If no visual change detected OR JS errors occurred, the input is considered broken.
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple, Set, TYPE_CHECKING

from .contracts import (
    InputCandidate,
    InteractionResult,
    InteractionUnit,
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
    from .sandbox import RenderContext

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.interaction")


# ---------------------------------------------------------------------------
# SPRINT 12: CASCADING VALIDATION CONSTANTS
# ---------------------------------------------------------------------------

# Threshold for detecting modal/overlay opening (% of viewport changed)
MODAL_OPEN_THRESHOLD = 0.15  # 15% of viewport = likely modal opened

# Maximum cascade depth (avoid infinite loops)
MAX_CASCADE_DEPTH = 2

# Maximum elements to test per cascade level
MAX_CASCADE_ELEMENTS = 4


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
        render_ctx: Optional["RenderContext"] = None,
    ) -> Tuple[PhaseResult, List[InteractionResult]]:
        """
        Test each input element with visual comparison.

        Sprint 6.2: Now tests InteractionUnits individually when present.
        Sprint 7: Now checks for JS errors after each click.
        "El evento puede ser uno solo, pero las decisiones del usuario nunca lo son."

        Args:
            page: Playwright page with HTML loaded
            inputs: List of input candidates from Phase 4
            contract: Validation contract with thresholds
            render_ctx: Optional render context with JS error tracking

        Returns:
            (PhaseResult, List[InteractionResult])
        """
        start_time = time.time()
        results: List[InteractionResult] = []

        # Sprint 7: Track JS errors count before interactions
        js_errors_before = len(render_ctx.js_errors) if render_ctx else 0

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

        # Sprint 6.2/6.4: Filter out non-testable elements (navigation + display_only)
        testable_inputs = [inp for inp in inputs if inp.testable]
        navigation_count = sum(1 for inp in inputs if inp.interaction_category.value == "navigation")
        display_only_count = sum(1 for inp in inputs if inp.is_display_only())
        excluded_count = len(inputs) - len(testable_inputs)

        if excluded_count > 0:
            logger.info(
                f"Phase 5: Skipping {excluded_count} non-testable element(s) "
                f"(navigation={navigation_count}, display_only={display_only_count})"
            )

        # Calculate total testable units
        # Sprint 6.2: Each interaction_unit counts as a separate test
        total_units = sum(
            len(inp.interaction_units) if inp.interaction_units else 1
            for inp in testable_inputs
        )

        # Limits for testing
        # Sprint 6.2: Increased limits for multi-option layouts (trivia, etc.)
        MAX_UNITS_TO_TEST = 8  # Test up to 8 units total
        EARLY_STOP_RESPONSIVE = 5  # Stop after 5 responsive (62.5%+ pass rate)
        units_tested = 0
        responsive_count = 0

        for input_candidate in testable_inputs:
            if units_tested >= MAX_UNITS_TO_TEST:
                break
            if responsive_count >= EARLY_STOP_RESPONSIVE:
                logger.info(f"Early stopping: found {responsive_count} responsive units")
                break

            if input_candidate.interaction_units:
                # Sprint 6.2: Test each interaction unit individually
                for unit in input_candidate.interaction_units:
                    if units_tested >= MAX_UNITS_TO_TEST:
                        break
                    if responsive_count >= EARLY_STOP_RESPONSIVE:
                        break

                    result = await self._test_interaction_unit(
                        page, input_candidate, unit, contract
                    )
                    results.append(result)
                    units_tested += 1

                    # Log result
                    status = "RESPONSIVE" if result.responsive else "NO RESPONSE"
                    delta = result.visual_delta.pixel_diff_ratio if result.visual_delta else 0
                    logger.debug(
                        f"  Unit {unit.value}: {status} "
                        f"(delta={delta:.3f}, threshold={contract.visual_change_threshold})"
                    )

                    if result.responsive:
                        responsive_count += 1
            else:
                # Original behavior: test the owner directly
                result = await self._test_single_input(page, input_candidate, contract)
                results.append(result)
                units_tested += 1

                # Log result
                status = "RESPONSIVE" if result.responsive else "NO RESPONSE"
                delta = result.visual_delta.pixel_diff_ratio if result.visual_delta else 0
                logger.debug(
                    f"  {input_candidate.selector}: {status} "
                    f"(delta={delta:.3f}, threshold={contract.visual_change_threshold})"
                )

                if result.responsive:
                    responsive_count += 1

        total_duration_ms = (time.time() - start_time) * 1000

        # Sprint 7: Check for JS errors that occurred during interactions
        js_errors_during_interaction = []
        if render_ctx:
            js_errors_during_interaction = render_ctx.js_errors[js_errors_before:]
            if js_errors_during_interaction:
                logger.warning(
                    f"Sprint 7: {len(js_errors_during_interaction)} JS error(s) detected during interaction: "
                    f"{js_errors_during_interaction[:3]}"  # Log first 3
                )

        # Phase passes if at least one input is responsive AND no JS errors
        passed = responsive_count > 0 and not js_errors_during_interaction

        if js_errors_during_interaction:
            logger.warning(
                f"Phase 5 (interaction): FAILED due to JS errors - "
                f"{len(js_errors_during_interaction)} error(s) detected"
            )
        elif not passed:
            logger.warning(
                f"Phase 5 (interaction): No units responded - "
                f"tested {len(results)}, all failed visual delta check"
            )
        else:
            logger.info(
                f"Phase 5 (interaction) passed - "
                f"{responsive_count}/{len(results)} units responsive"
            )

        # Build error message
        error_msg = None
        if js_errors_during_interaction:
            error_msg = f"JS errors during interaction: {js_errors_during_interaction[0]}"
        elif responsive_count == 0:
            error_msg = f"No inputs responded to interaction ({len(results)} tested)"

        return PhaseResult(
            phase=5,
            phase_name="interaction",
            passed=passed,
            error=error_msg,
            details={
                "tested": len(results),
                "responsive": responsive_count,
                "total_units_available": total_units,
                "navigation_excluded": navigation_count,  # Sprint 6.2: Links excluded from testing
                "responsive_selectors": [r.input.selector for r in results if r.responsive],
                "failed_selectors": [r.input.selector for r in results if not r.responsive],
                # Sprint 7: JS errors detected during clicks
                "js_errors_during_interaction": js_errors_during_interaction,
                "js_error_count": len(js_errors_during_interaction),
            },
            duration_ms=total_duration_ms,
        ), results

    async def _pause_animations(self, page: "Page") -> None:
        """
        Sprint 6.5: Pause all CSS animations before taking screenshots.
        
        This prevents false negatives from orbiting planets, spinning loaders,
        or any other continuous animations that would cause pixel differences
        unrelated to the click interaction.
        """
        logger.debug("Pausing all CSS animations for screenshot comparison")
        await page.evaluate("""
            () => {
                // Pause all CSS animations
                let count = 0;
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.animationName !== 'none') {
                        el.style.animationPlayState = 'paused';
                        count++;
                    }
                });
                return count;
            }
        """)

    async def _resume_animations(self, page: "Page") -> None:
        """Sprint 6.5: Resume CSS animations after screenshots."""
        await page.evaluate("""
            () => {
                document.querySelectorAll('*').forEach(el => {
                    el.style.animationPlayState = '';
                });
            }
        """)

    async def _test_single_input(
        self,
        page: "Page",
        input_candidate: InputCandidate,
        contract: ValidationContract,
    ) -> InteractionResult:
        """Test a single input element."""
        start_time = time.time()

        try:
            # Sprint 6.5: Pause animations before capturing screenshots
            await self._pause_animations(page)
            
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

            # ─────────────────────────────────────────────────────────────
            # Sprint 6.1 Fix: Skip disabled elements
            # ─────────────────────────────────────────────────────────────
            # Playwright can physically click disabled buttons, but the JS
            # handler won't execute. Visual changes from hover/cursor don't
            # mean the button actually works. A disabled button is NOT
            # a valid interactive element.
            # ─────────────────────────────────────────────────────────────
            is_disabled = await locator.is_disabled()
            if is_disabled:
                return InteractionResult(
                    input=input_candidate,
                    action="click",
                    visual_delta=None,
                    scene_before=before_scene,
                    scene_after=None,
                    responsive=False,
                    error=f"Element is disabled: {input_candidate.selector}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Perform click
            await locator.click(timeout=contract.interaction_timeout_ms)

            # 3. Wait for stabilization (animations, transitions)
            await asyncio.sleep(contract.stabilization_ms / 1000)

            # 4. Capture AFTER state
            after_screenshot = await visual_analyzer.capture(page)
            after_scene = await scene_graph_extractor.extract_quick(page)

            # 5. Compare visual delta using MULTI-SCALE comparison
            # Sprint 6.5: Compare at 3 scales and use MAXIMUM to catch changes at any level
            # This fixes subtle button feedback that gets lost at large regions
            element_box = input_candidate.node.bounding_box
            
            # Scale 1: Tight region (20px padding) - catches small button changes
            tight_region = element_box.expand(20)
            tight_delta = visual_analyzer.compare(before_screenshot, after_screenshot, tight_region)
            
            # Scale 2: Normal region (100px padding) - catches nearby changes
            normal_region = element_box.expand(self.REGION_PADDING)
            normal_delta = visual_analyzer.compare(before_screenshot, after_screenshot, normal_region)
            
            # Scale 3: Full-page - catches global changes (modals, toasts)
            full_delta = visual_analyzer.compare(before_screenshot, after_screenshot)
            
            # Use the MAXIMUM of all three scales
            # "El cambio es real si aparece en cualquier escala"
            best_delta = tight_delta
            if normal_delta.pixel_diff_ratio > best_delta.pixel_diff_ratio:
                best_delta = normal_delta
            if full_delta.pixel_diff_ratio > best_delta.pixel_diff_ratio:
                best_delta = full_delta
            
            visual_delta = best_delta

            # Sprint 6.3: Adaptive threshold - use BOTH global and element-relative detection
            # This fixes the impossible math for small buttons (100x40 = 0.19% of viewport)
            responsive = visual_delta.has_visible_change(
                threshold=contract.visual_change_threshold,  # 2% of viewport
                element_threshold=0.30,  # 30% of element area
            )

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
                # Sprint 10: Save screenshots for vision-based repair
                screenshot_before=before_screenshot.image_bytes,
                screenshot_after=after_screenshot.image_bytes,
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

    async def _test_interaction_unit(
        self,
        page: "Page",
        owner: InputCandidate,
        unit: InteractionUnit,
        contract: ValidationContract,
    ) -> InteractionResult:
        """
        Sprint 6.2: Test a single interaction unit.

        Similar to _test_single_input but clicks the unit's selector
        instead of the owner's. This handles cases where event delegation
        is used but each unit needs individual testing.

        The result is attributed to the unit, but uses owner for metadata.
        """
        start_time = time.time()

        # Create a temporary InputCandidate for the unit
        # This allows reusing the same InteractionResult structure
        unit_as_candidate = InputCandidate(
            selector=unit.selector,
            node=unit.node,
            confidence=owner.confidence,
            input_type="option",
            priority=owner.priority,
        )

        try:
            # Sprint 6.5: Pause animations before capturing screenshots
            await self._pause_animations(page)
            
            # 1. Capture BEFORE state
            before_screenshot = await visual_analyzer.capture(page)
            before_scene = await scene_graph_extractor.extract_quick(page)

            # 2. Click the unit element
            locator = page.locator(unit.selector).first

            # Check if element exists and is visible
            if await locator.count() == 0:
                return InteractionResult(
                    input=unit_as_candidate,
                    action="click",
                    visual_delta=None,
                    scene_before=before_scene,
                    scene_after=None,
                    responsive=False,
                    error=f"Unit not found: {unit.selector} (value={unit.value})",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            if not await locator.is_visible():
                return InteractionResult(
                    input=unit_as_candidate,
                    action="click",
                    visual_delta=None,
                    scene_before=before_scene,
                    scene_after=None,
                    responsive=False,
                    error=f"Unit not visible: {unit.selector}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Skip disabled elements
            is_disabled = await locator.is_disabled()
            if is_disabled:
                return InteractionResult(
                    input=unit_as_candidate,
                    action="click",
                    visual_delta=None,
                    scene_before=before_scene,
                    scene_after=None,
                    responsive=False,
                    error=f"Unit is disabled: {unit.selector}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Perform click
            await locator.click(timeout=contract.interaction_timeout_ms)

            # 3. Wait for stabilization
            await asyncio.sleep(contract.stabilization_ms / 1000)

            # 4. Capture AFTER state
            after_screenshot = await visual_analyzer.capture(page)
            after_scene = await scene_graph_extractor.extract_quick(page)

            # 5. Compare visual delta (focus on region around unit)
            # Sprint 6.3: Use element bounding box for element-relative comparison
            element_box = unit.node.bounding_box
            region = element_box.expand(self.REGION_PADDING)
            visual_delta = visual_analyzer.compare(before_screenshot, after_screenshot, region)

            # Full-page fallback
            if visual_delta.pixel_diff_ratio < contract.visual_change_threshold:
                full_delta = visual_analyzer.compare(before_screenshot, after_screenshot)
                if full_delta.pixel_diff_ratio > visual_delta.pixel_diff_ratio:
                    visual_delta = full_delta

            # Sprint 6.3: Adaptive threshold - use BOTH global and element-relative detection
            responsive = visual_delta.has_visible_change(
                threshold=contract.visual_change_threshold,  # 2% of viewport
                element_threshold=0.30,  # 30% of element area
            )

            # Scene graph fallback
            if not responsive:
                responsive = self._scene_changed_significantly(before_scene, after_scene)

            return InteractionResult(
                input=unit_as_candidate,
                action="click",
                visual_delta=visual_delta,
                scene_before=before_scene,
                scene_after=after_scene,
                responsive=responsive,
                duration_ms=(time.time() - start_time) * 1000,
                # Sprint 10: Save screenshots for vision-based repair
                screenshot_before=before_screenshot.image_bytes,
                screenshot_after=after_screenshot.image_bytes,
            )

        except asyncio.TimeoutError:
            return InteractionResult(
                input=unit_as_candidate,
                action="click",
                visual_delta=None,
                scene_before=None,
                scene_after=None,
                responsive=False,
                error=f"Timeout clicking unit: {unit.selector}",
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return InteractionResult(
                input=unit_as_candidate,
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

    # -------------------------------------------------------------------------
    # SPRINT 12: CASCADING VALIDATION METHODS
    # -------------------------------------------------------------------------

    def _modal_likely_opened(
        self,
        result: InteractionResult,
        before_scene: ObservedSceneGraph,
        after_scene: ObservedSceneGraph,
    ) -> bool:
        """
        Sprint 12: Detect if a modal/overlay likely opened after a click.

        Indicators:
        1. Large visual change (>15% of viewport)
        2. New container nodes appeared
        3. Scene graph shows significant new visible elements
        """
        if not result.responsive:
            return False

        # Check 1: Large visual change
        if result.visual_delta:
            if result.visual_delta.pixel_diff_ratio >= MODAL_OPEN_THRESHOLD:
                logger.debug(
                    f"Sprint 12: Large visual change detected ({result.visual_delta.pixel_diff_ratio:.1%}), "
                    "likely modal opened"
                )
                return True

        # Check 2: Significant scene graph change
        if before_scene and after_scene:
            before_count = len(before_scene.visible_nodes())
            after_count = len(after_scene.visible_nodes())

            # If many new nodes appeared, likely a modal/panel
            if after_count - before_count >= 5:
                logger.debug(
                    f"Sprint 12: {after_count - before_count} new nodes appeared, "
                    "likely modal opened"
                )
                return True

        return False

    async def _find_new_interactive_elements(
        self,
        page: "Page",
        already_tested: Set[str],
        contract: ValidationContract,
    ) -> List[InputCandidate]:
        """
        Sprint 12: Find NEW interactive elements that weren't in the original set.

        This is used after a modal opens to find buttons/inputs inside it.
        """
        from .input_detector import input_detector

        # Re-run input detection on current page state
        try:
            # First extract fresh scene graph (modal content is now visible)
            new_scene_graph = await scene_graph_extractor.extract_quick(page)

            # Then detect inputs using the new scene graph
            _, new_inputs = await input_detector.detect(page, new_scene_graph, contract)

            # Filter to only NEW elements (not already tested)
            new_elements = [
                inp for inp in new_inputs
                if inp.selector not in already_tested and inp.testable
            ]

            if new_elements:
                logger.info(
                    f"Sprint 12: Found {len(new_elements)} NEW interactive elements "
                    f"after modal opened (from {len(new_inputs)} total)"
                )

            return new_elements

        except Exception as e:
            logger.warning(f"Sprint 12: Failed to re-scan for elements: {e}")
            return []

    async def _reset_page_state(
        self,
        page: "Page",
        html_content: str,
    ) -> bool:
        """
        Sprint 12: Reset page to initial state after testing modal content.

        Strategy:
        1. Try to find and click a "close" button
        2. Try pressing Escape key
        3. If all else fails, reload the HTML
        """
        # Strategy 1: Look for close button
        close_selectors = [
            'button:has-text("close")',
            'button:has-text("cerrar")',
            'button:has-text("×")',
            'button:has-text("x")',
            '[class*="close"]',
            '[class*="back"]',
            'button:has-text("regresar")',
            'button:has-text("volver")',
            'button:has-text("return")',
        ]

        for selector in close_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() > 0 and await locator.is_visible():
                    await locator.click(timeout=1000)
                    await asyncio.sleep(0.3)  # Wait for animation
                    logger.debug(f"Sprint 12: Closed modal via {selector}")
                    return True
            except Exception:
                continue

        # Strategy 2: Press Escape
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            logger.debug("Sprint 12: Attempted to close modal via Escape key")
            # Check if modal closed by looking for overlay
            overlay = page.locator('[class*="overlay"]:visible, [class*="modal"]:visible').first
            if await overlay.count() == 0:
                return True
        except Exception:
            pass

        # Strategy 3: Reload HTML
        try:
            await page.set_content(html_content, wait_until="networkidle")
            await asyncio.sleep(0.5)  # Wait for JS to initialize
            logger.debug("Sprint 12: Reset page by reloading HTML")
            return True
        except Exception as e:
            logger.warning(f"Sprint 12: Failed to reset page: {e}")
            return False

    async def validate_with_cascade(
        self,
        page: "Page",
        inputs: List[InputCandidate],
        contract: ValidationContract,
        render_ctx: Optional["RenderContext"] = None,
        html_content: Optional[str] = None,
    ) -> Tuple[PhaseResult, List[InteractionResult]]:
        """
        Sprint 12: Enhanced validation with cascading support.

        When a click opens a modal/overlay:
        1. Detect the modal opened (large visual change)
        2. Re-scan for new interactive elements inside the modal
        3. Test those new elements
        4. Reset page state before testing next original element

        Args:
            page: Playwright page with HTML loaded
            inputs: List of input candidates from Phase 4
            contract: Validation contract with thresholds
            render_ctx: Optional render context with JS error tracking
            html_content: Original HTML for page reset (optional)

        Returns:
            (PhaseResult, List[InteractionResult])
        """
        start_time = time.time()
        results: List[InteractionResult] = []
        tested_selectors: Set[str] = set()

        # Sprint 7: Track JS errors count before interactions
        js_errors_before = len(render_ctx.js_errors) if render_ctx else 0

        if not inputs:
            return PhaseResult(
                phase=5,
                phase_name="interaction",
                passed=True,
                details={"tested": 0, "responsive": 0, "note": "No inputs to test"},
                duration_ms=(time.time() - start_time) * 1000,
            ), []

        # Filter testable inputs
        testable_inputs = [inp for inp in inputs if inp.testable]
        navigation_count = sum(1 for inp in inputs if inp.interaction_category.value == "navigation")
        display_only_count = sum(1 for inp in inputs if inp.is_display_only())

        if len(inputs) - len(testable_inputs) > 0:
            logger.info(
                f"Phase 5: Skipping {len(inputs) - len(testable_inputs)} non-testable element(s)"
            )

        # Counters
        MAX_UNITS_TO_TEST = 12  # Sprint 12: Increased for cascade
        EARLY_STOP_RESPONSIVE = 8
        units_tested = 0
        responsive_count = 0
        cascade_responsive = 0  # Track cascade-level responses

        for input_candidate in testable_inputs:
            if units_tested >= MAX_UNITS_TO_TEST:
                break
            if responsive_count >= EARLY_STOP_RESPONSIVE:
                logger.info(f"Early stopping: found {responsive_count} responsive units")
                break

            # Track this selector as tested
            tested_selectors.add(input_candidate.selector)

            # Capture before state for modal detection
            before_scene = await scene_graph_extractor.extract_quick(page)

            # Test the element
            if input_candidate.interaction_units:
                # Test first unit only for modal detection
                unit = input_candidate.interaction_units[0]
                result = await self._test_interaction_unit(page, input_candidate, unit, contract)
                tested_selectors.add(unit.selector)
            else:
                result = await self._test_single_input(page, input_candidate, contract)

            results.append(result)
            units_tested += 1

            if result.responsive:
                responsive_count += 1

                # Sprint 12: Check if modal opened
                after_scene = result.scene_after
                if self._modal_likely_opened(result, before_scene, after_scene):
                    logger.info(
                        f"Sprint 12: Modal detected after clicking {input_candidate.selector}, "
                        "starting cascade validation"
                    )

                    # Find and test new elements inside modal
                    cascade_results, cascade_count = await self._cascade_validate(
                        page=page,
                        validation_contract=contract,
                        tested_selectors=tested_selectors,
                        depth=1,
                        trigger_selector=input_candidate.selector,
                    )
                    results.extend(cascade_results)
                    cascade_responsive += cascade_count
                    units_tested += len(cascade_results)

                    # Reset page state before testing next original element
                    if html_content and len(testable_inputs) > 1:
                        await self._reset_page_state(page, html_content)
                        await asyncio.sleep(0.3)  # Wait for reset
            else:
                # Log non-responsive
                delta = result.visual_delta.pixel_diff_ratio if result.visual_delta else 0
                logger.debug(
                    f"  {input_candidate.selector}: NO RESPONSE (delta={delta:.3f})"
                )

        total_duration_ms = (time.time() - start_time) * 1000

        # Sprint 7: Check for JS errors
        js_errors_during_interaction = []
        if render_ctx:
            js_errors_during_interaction = render_ctx.js_errors[js_errors_before:]

        # Phase passes if sufficient inputs are responsive
        total_responsive = responsive_count + cascade_responsive
        passed = total_responsive > 0 and not js_errors_during_interaction

        logger.info(
            f"Phase 5 (interaction) {'passed' if passed else 'FAILED'} - "
            f"{responsive_count} original + {cascade_responsive} cascade = "
            f"{total_responsive}/{units_tested} responsive"
        )

        return PhaseResult(
            phase=5,
            phase_name="interaction",
            passed=passed,
            error=js_errors_during_interaction[0] if js_errors_during_interaction else None,
            details={
                "tested": units_tested,
                "responsive": total_responsive,
                "original_responsive": responsive_count,
                "cascade_responsive": cascade_responsive,
                "navigation_excluded": navigation_count,
                "display_only_excluded": display_only_count,
                "js_errors_during_interaction": js_errors_during_interaction,
            },
            duration_ms=total_duration_ms,
        ), results

    async def _cascade_validate(
        self,
        page: "Page",
        validation_contract: ValidationContract,
        tested_selectors: Set[str],
        depth: int,
        trigger_selector: str = "",
    ) -> Tuple[List[InteractionResult], int]:
        """
        Sprint 12: Recursively validate elements inside opened modals.

        Args:
            page: Current page state (with modal open)
            validation_contract: Validation contract for input detection
            tested_selectors: Set of already tested selectors
            depth: Current cascade depth
            trigger_selector: What element triggered this cascade (e.g., "#mercury")

        Returns:
            (results, responsive_count)
        """
        if depth > MAX_CASCADE_DEPTH:
            logger.debug(f"Sprint 12: Max cascade depth ({MAX_CASCADE_DEPTH}) reached")
            return [], 0

        # Find new interactive elements
        new_elements = await self._find_new_interactive_elements(
            page, tested_selectors, validation_contract
        )

        if not new_elements:
            logger.debug("Sprint 12: No new elements found in modal")
            return [], 0

        results: List[InteractionResult] = []
        responsive_count = 0

        # Test up to MAX_CASCADE_ELEMENTS new elements
        for element in new_elements[:MAX_CASCADE_ELEMENTS]:
            tested_selectors.add(element.selector)

            result = await self._test_single_input(page, element, validation_contract)

            # Sprint 12: Mark this result as coming from cascade
            result.cascade_level = depth
            result.cascade_trigger = trigger_selector

            results.append(result)

            if result.responsive:
                responsive_count += 1
                logger.debug(
                    f"Sprint 12 (depth={depth}): {element.selector} RESPONSIVE"
                )
            else:
                logger.debug(
                    f"Sprint 12 (depth={depth}): {element.selector} no response"
                )

        logger.info(
            f"Sprint 12: Cascade level {depth} complete - "
            f"{responsive_count}/{len(results)} responsive"
        )

        return results, responsive_count


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

interaction_validator = InteractionValidator()
