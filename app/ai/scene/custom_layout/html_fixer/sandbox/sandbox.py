"""
Sandbox - Visual validation of HTML with Playwright.

Sprint 4: Basic sandbox for HTML validation.
Sprint 5: Integrated DiffEngine for multi-scale comparison and classification.

This module renders HTML in a headless browser and validates
that interactive elements work correctly.

Features:
- Render HTML in headless Chromium
- Find interactive elements
- Test clicks and capture screenshots
- Detect blocked elements
- Multi-scale screenshot comparison (Sprint 5)
- Semantic result classification (Sprint 5)
"""

import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, TYPE_CHECKING

from .contracts import (
    ElementInfo,
    ElementResult,
    ElementStatus,
    ValidationResult,
)
from .diff_engine import DiffEngine
from .result_classifier import ResultClassifier, InteractionClassification, ClassificationResult
from .screenshot_exporter import ScreenshotExporter
from ..core.selector import SelectorService

if TYPE_CHECKING:
    from playwright.async_api import Page, Browser, BrowserContext

logger = logging.getLogger("jarvis.ai.html_fixer.sandbox")


class Sandbox:
    """
    Sandbox for visual HTML validation with Playwright.

    Renders HTML in a headless browser, finds interactive elements,
    and tests that they respond to clicks appropriately.

    Usage:
        sandbox = Sandbox()
        result = await sandbox.validate(html)

        if result.passed:
            print("All elements work!")
        else:
            for blocked in result.get_blocked():
                print(f"{blocked.selector} blocked by {blocked.blocking_element}")
    """

    def __init__(
        self,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        timeout_ms: int = 2000,
        stabilization_ms: int = 500,
        # Sprint 5: New options
        use_diff_engine: bool = True,
        parallel_comparisons: bool = True,
        max_workers: int = 4,
        save_screenshots: bool = False,
        screenshots_dir: Optional[str] = None,
    ):
        """
        Initialize the sandbox.

        Args:
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height
            timeout_ms: Timeout for click actions
            stabilization_ms: Wait time after clicks for visual changes
            use_diff_engine: Use DiffEngine for multi-scale comparison (Sprint 5)
            parallel_comparisons: Parallelize diff computations (Sprint 5)
            max_workers: Max threads for parallel comparisons (Sprint 5)
            save_screenshots: Save screenshots to disk (Sprint 5)
            screenshots_dir: Directory for screenshots (Sprint 5)
        """
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.timeout_ms = timeout_ms
        self.stabilization_ms = stabilization_ms
        self._playwright_available: Optional[bool] = None

        # Sprint 5: DiffEngine integration
        self._use_diff_engine = use_diff_engine
        self._parallel_comparisons = parallel_comparisons
        self._max_workers = max_workers
        self._save_screenshots = save_screenshots

        # Initialize Sprint 5 components
        self._diff_engine = DiffEngine() if use_diff_engine else None
        self._classifier = ResultClassifier() if use_diff_engine else None
        self._exporter = ScreenshotExporter(screenshots_dir) if save_screenshots else None
        self._executor = ThreadPoolExecutor(max_workers=max_workers) if parallel_comparisons else None

        # Store classifications for report generation
        self._classifications: Dict[str, "ClassificationResult"] = {}

    async def check_playwright_available(self) -> bool:
        """Check if Playwright is installed."""
        if self._playwright_available is not None:
            return self._playwright_available

        try:
            from playwright.async_api import async_playwright
            self._playwright_available = True
            logger.debug("Playwright is available")
        except ImportError:
            self._playwright_available = False
            logger.error(
                "Playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            )

        return self._playwright_available

    async def validate(self, html: str, js_only: bool = False) -> ValidationResult:
        """
        Validate HTML by rendering and testing interactions.

        Args:
            html: HTML content to validate
            js_only: If True, only capture JS errors without testing interactive elements.
                     This is much faster (~5s vs ~60s) for Human Feedback Mode.

        Returns:
            ValidationResult with test results for each element
        """
        start_time = time.time()
        result = ValidationResult(
            viewport_width=self.viewport["width"],
            viewport_height=self.viewport["height"],
        )

        # Check Playwright
        if not await self.check_playwright_available():
            result.js_errors.append("Playwright not available")
            result.validation_time_ms = (time.time() - start_time) * 1000
            return result

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(viewport=self.viewport)
                page = await context.new_page()

                # Capture JS errors
                page.on("pageerror", lambda e: result.js_errors.append(str(e)))
                page.on("console", lambda msg: (
                    result.console_errors.append(msg.text)
                    if msg.type == "error" else None
                ))

                # Render HTML
                await page.set_content(html, wait_until="networkidle")
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(150)  # JS initialization buffer

                # Take initial screenshot
                result.initial_screenshot = await page.screenshot()

                # js_only mode: skip element testing (Human Feedback Mode)
                if js_only:
                    logger.info("JS-only mode: skipping element interaction tests")
                    await browser.close()
                    result.validation_time_ms = (time.time() - start_time) * 1000
                    logger.info(f"JS-only validation completed in {result.validation_time_ms:.0f}ms")
                    return result

                # Find interactive elements
                interactive = await self._find_interactive_elements(page)
                logger.info(f"Found {len(interactive)} interactive elements")

                # Test each element
                for element in interactive:
                    element_result = await self._test_element(page, element)
                    result.element_results.append(element_result)

                await browser.close()

        except Exception as e:
            logger.error(f"Sandbox validation failed: {e}")
            result.js_errors.append(f"Validation error: {e}")

        result.validation_time_ms = (time.time() - start_time) * 1000
        logger.info(result.describe())
        return result

    async def _find_interactive_elements(self, page: "Page") -> List[ElementInfo]:
        """
        Find all interactive elements in the page.

        Uses SelectorService JS helpers for proper escaping of Tailwind
        variant classes (hover:, focus:, etc.) in CSS selectors.

        Looks for:
        - Elements with onclick handlers
        - Buttons and links
        - Elements with role="button"
        - Elements with cursor: pointer style
        """
        # Get JS helper code from SelectorService
        js_helpers = SelectorService.get_js_helper_code()

        elements_data = await page.evaluate(f"""
            () => {{
                {js_helpers}

                const interactive = [];
                const seen = new Set();

                // Selectors for interactive elements
                const selectors = [
                    '[onclick]',
                    'button',
                    'a[href]',
                    '[role="button"]',
                    'input[type="button"]',
                    'input[type="submit"]',
                    '.clickable',
                    '[data-action]',
                ];

                for (const selector of selectors) {{
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {{
                        // Generate unique selector using SelectorService helper
                        const uniqueSelector = generateSelector(el, {{ escapeClasses: true }});

                        // Skip duplicates
                        if (seen.has(uniqueSelector)) continue;
                        seen.add(uniqueSelector);

                        // Get bounding box
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;

                        // Check visibility
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        if (parseFloat(style.opacity) === 0) continue;

                        interactive.push({{
                            selector: uniqueSelector,
                            tag: el.tagName.toLowerCase(),
                            bounding_box: {{
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height,
                            }},
                            has_handler: el.hasAttribute('onclick') || el.onclick !== null,
                            inner_text: (el.innerText || '').substring(0, 50),
                            classes: (() => {{
                                // NOTE: For SVG elements, `className` may be an SVGAnimatedString.
                                let className = '';
                                if (typeof el.className === 'string') {{
                                    className = el.className;
                                }} else if (el.className && typeof el.className.baseVal === 'string') {{
                                    className = el.className.baseVal;
                                }}
                                return className
                                    ? className.split(/\\s+/).filter(function(c) {{ return c; }})
                                    : [];
                            }})(),
                        }});
                    }}
                }}

                return interactive;
            }}
        """)

        return [
            ElementInfo(
                selector=e["selector"],
                tag=e["tag"],
                bounding_box=e["bounding_box"],
                has_handler=e["has_handler"],
                inner_text=e["inner_text"] or None,
                classes=e["classes"],
            )
            for e in elements_data
        ]

    async def _test_element(
        self, page: "Page", element: ElementInfo
    ) -> ElementResult:
        """
        Test a single element by clicking it.

        Captures screenshots before and after to detect visual changes.
        Uses DiffEngine for multi-scale comparison (Sprint 5).
        Handles various error conditions like interception and timeouts.
        """
        try:
            # Screenshot before
            before = await page.screenshot()

            # Try to click
            locator = page.locator(element.selector).first
            await locator.click(timeout=self.timeout_ms)

            # Wait for visual changes
            await page.wait_for_timeout(self.stabilization_ms)

            # Screenshot after
            after = await page.screenshot()

            # Sprint 5: Use DiffEngine if available
            if self._use_diff_engine and self._diff_engine:
                diff_result = self._diff_engine.compare(
                    before,
                    after,
                    element.bounding_box,
                    generate_diff_images=self._save_screenshots,
                )

                # Classify the result
                classification = self._classifier.classify(diff_result, element)
                self._classifications[element.selector] = classification

                # Map classification to status
                status = self._classification_to_status(classification.classification)
                diff_ratio = diff_result.max_diff_ratio

                # Export screenshots if enabled
                if self._save_screenshots and self._exporter:
                    self._exporter.export(
                        element.selector,
                        before,
                        after,
                        diff_result,
                    )

                return ElementResult(
                    selector=element.selector,
                    status=status,
                    diff_ratio=diff_ratio,
                    before_screenshot=before,
                    after_screenshot=after,
                    diff_result=diff_result,
                    classification=classification,
                )
            else:
                # Fallback to Sprint 4 behavior
                diff_ratio = self._compare_screenshots(before, after)

                status = (
                    ElementStatus.RESPONSIVE
                    if diff_ratio > 0.02
                    else ElementStatus.NO_VISUAL_CHANGE
                )

                return ElementResult(
                    selector=element.selector,
                    status=status,
                    diff_ratio=diff_ratio,
                    before_screenshot=before,
                    after_screenshot=after,
                )

        except Exception as e:
            error_msg = str(e)

            # Detect interception
            if "intercepts pointer events" in error_msg:
                blocker = self._extract_blocker(error_msg)
                return ElementResult(
                    selector=element.selector,
                    status=ElementStatus.INTERCEPTED,
                    blocking_element=blocker,
                    error=error_msg,
                )

            # Detect timeout
            if "Timeout" in error_msg or "timeout" in error_msg:
                return ElementResult(
                    selector=element.selector,
                    status=ElementStatus.TIMEOUT,
                    error=error_msg,
                )

            # Other errors
            return ElementResult(
                selector=element.selector,
                status=ElementStatus.ERROR,
                error=error_msg,
            )

    def _classification_to_status(
        self,
        classification: InteractionClassification
    ) -> ElementStatus:
        """
        Map InteractionClassification to ElementStatus.

        Args:
            classification: The classification result

        Returns:
            Corresponding ElementStatus
        """
        mapping = {
            InteractionClassification.RESPONSIVE: ElementStatus.RESPONSIVE,
            InteractionClassification.NAVIGATION: ElementStatus.RESPONSIVE,
            InteractionClassification.CASCADE_EFFECT: ElementStatus.RESPONSIVE,
            InteractionClassification.WEAK_FEEDBACK: ElementStatus.NO_VISUAL_CHANGE,
            InteractionClassification.NO_RESPONSE: ElementStatus.NO_VISUAL_CHANGE,
        }
        return mapping.get(classification, ElementStatus.NO_VISUAL_CHANGE)

    def get_classifications(self) -> Dict[str, "ClassificationResult"]:
        """
        Get all classifications from the last validation.

        Returns:
            Dict mapping selector to ClassificationResult
        """
        return self._classifications.copy()

    def _compare_screenshots(self, before: bytes, after: bytes) -> float:
        """
        Compare two screenshots and return difference ratio.

        Simple byte comparison for Sprint 4. Sprint 5 will add
        proper pixel-level diff with pixelmatch.

        Args:
            before: Screenshot bytes before action
            after: Screenshot bytes after action

        Returns:
            Ratio of difference (0.0 = identical, 1.0 = completely different)
        """
        if before == after:
            return 0.0

        # Simple comparison: count different bytes
        min_len = min(len(before), len(after))
        diff_count = sum(1 for i in range(min_len) if before[i] != after[i])
        diff_count += abs(len(before) - len(after))

        total = max(len(before), len(after))
        return diff_count / total if total > 0 else 0.0

    def _extract_blocker(self, error_msg: str) -> Optional[str]:
        """
        Extract the blocking element selector from Playwright error.

        Playwright errors look like:
        "Element <div class='overlay'> intercepts pointer events"

        Args:
            error_msg: Playwright error message

        Returns:
            CSS selector of blocking element or None
        """
        # Pattern: <tag class="..."> or <tag id="...">
        patterns = [
            r"<(\w+)\s+class=['\"]([^'\"]+)['\"]",
            r"<(\w+)\s+id=['\"]([^'\"]+)['\"]",
            r"<(\w+)>",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_msg)
            if match:
                tag = match.group(1)
                if len(match.groups()) > 1:
                    attr_value = match.group(2)
                    if "class" in pattern:
                        # Use first class for selector
                        first_class = attr_value.split()[0]
                        return f"{tag}.{first_class}"
                    else:
                        return f"#{attr_value}"
                return tag

        return None


async def quick_validate(html: str) -> ValidationResult:
    """
    Convenience function for quick validation.

    Args:
        html: HTML content to validate

    Returns:
        ValidationResult
    """
    sandbox = Sandbox()
    return await sandbox.validate(html)
