"""
Sandbox Renderer - Phase 1: Render check.

Sprint 6: Visual-based validation system.

This module handles the first phase of validation:
- Load HTML in headless Chromium
- Capture JS errors and console errors
- Detect blank pages
- Check basic DOM structure

Key difference from old validator: Returns Page object for subsequent phases
instead of closing it immediately.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from .contracts import PhaseResult, ValidationContract

if TYPE_CHECKING:
    from playwright.async_api import Page, Browser, BrowserContext

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.sandbox")


# ---------------------------------------------------------------------------
# RENDER CONTEXT
# ---------------------------------------------------------------------------

@dataclass
class RenderContext:
    """
    Context returned by sandbox render.

    Contains the Page object and collected errors for use by subsequent phases.
    Must be closed when validation is complete.
    """
    page: "Page"
    browser: "Browser"
    context: "BrowserContext"
    js_errors: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    render_time_ms: float = 0.0

    async def close(self):
        """Clean up browser resources."""
        try:
            await self.browser.close()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

    def all_errors(self) -> List[str]:
        """Get all captured errors."""
        return self.js_errors + self.console_errors


# ---------------------------------------------------------------------------
# SANDBOX RENDERER
# ---------------------------------------------------------------------------

class SandboxRenderer:
    """
    Phase 1: Render HTML and check for basic issues.

    Responsibilities:
    - Launch headless Chromium
    - Load HTML content
    - Capture JS errors
    - Detect blank pages
    - Return Page object for subsequent phases
    """

    def __init__(self):
        self._playwright_available: Optional[bool] = None

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
            logger.error("Playwright not installed - pip install playwright && playwright install chromium")

        return self._playwright_available

    async def render(
        self,
        contract: ValidationContract,
    ) -> Tuple[PhaseResult, Optional[RenderContext]]:
        """
        Load HTML in headless Chromium and check for render issues.

        Args:
            contract: Validation contract with HTML and settings

        Returns:
            (PhaseResult, RenderContext) - RenderContext is None if render failed.
            IMPORTANT: Caller must close RenderContext when done.
        """
        start_time = time.time()
        errors: List[str] = []
        warnings: List[str] = []

        # Check Playwright availability
        if not await self.check_playwright_available():
            return PhaseResult(
                phase=1,
                phase_name="render",
                passed=False,
                error="Playwright not installed",
                duration_ms=(time.time() - start_time) * 1000,
            ), None

        try:
            from playwright.async_api import async_playwright

            # Launch browser
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": contract.viewport_width, "height": contract.viewport_height}
            )
            page = await context.new_page()

            # Create render context to track errors
            render_ctx = RenderContext(
                page=page,
                browser=browser,
                context=context,
            )

            # Capture JavaScript errors
            page.on("pageerror", lambda err: render_ctx.js_errors.append(str(err)))
            page.on("console", lambda msg: (
                render_ctx.console_errors.append(f"Console error: {msg.text}")
                if msg.type == "error" else None
            ))

            # Load HTML content with timeout
            timeout_seconds = contract.interaction_timeout_ms / 1000 * 5  # 5x interaction timeout
            try:
                await asyncio.wait_for(
                    page.set_content(contract.html, wait_until="networkidle"),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                errors.append(f"Page render timed out after {timeout_seconds:.1f}s")
                await render_ctx.close()
                return PhaseResult(
                    phase=1,
                    phase_name="render",
                    passed=False,
                    error=errors[0],
                    details={"timeout_seconds": timeout_seconds},
                    duration_ms=(time.time() - start_time) * 1000,
                ), None

            # Check for JavaScript errors on load
            if render_ctx.js_errors:
                errors.extend(render_ctx.js_errors)

            # Check if page is blank (no text content)
            body_content = await page.evaluate("document.body?.innerText || ''")
            if not body_content or not body_content.strip():
                # Check for visual content (images, styled elements)
                has_visual_content = await page.evaluate("""
                    () => {
                        const body = document.body;
                        if (!body) return false;

                        const elements = body.querySelectorAll('*');
                        for (const el of elements) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                const style = window.getComputedStyle(el);
                                if (style.visibility !== 'hidden' && style.display !== 'none') {
                                    return true;
                                }
                            }
                        }
                        return false;
                    }
                """)

                if not has_visual_content:
                    errors.append("Page appears to be blank (no visible content)")

            # Check basic structure
            has_structure = await page.evaluate("""
                () => document.body && document.body.children.length > 0
            """)

            if not has_structure:
                warnings.append("Page has no child elements in body")

            # Calculate render time
            render_ctx.render_time_ms = (time.time() - start_time) * 1000

            # Determine if phase passed
            passed = len(errors) == 0

            if not passed:
                logger.warning(f"Phase 1 (render) failed: {errors}")
                await render_ctx.close()
                return PhaseResult(
                    phase=1,
                    phase_name="render",
                    passed=False,
                    error="; ".join(errors),
                    details={
                        "js_errors": len(render_ctx.js_errors),
                        "console_errors": len(render_ctx.console_errors),
                        "warnings": warnings,
                    },
                    duration_ms=render_ctx.render_time_ms,
                ), None

            logger.info(f"Phase 1 (render) passed in {render_ctx.render_time_ms:.0f}ms")

            return PhaseResult(
                phase=1,
                phase_name="render",
                passed=True,
                details={
                    "js_errors": len(render_ctx.js_errors),
                    "console_errors": len(render_ctx.console_errors),
                    "warnings": warnings,
                    "has_structure": has_structure,
                },
                duration_ms=render_ctx.render_time_ms,
            ), render_ctx

        except Exception as e:
            logger.error(f"Sandbox render error: {e}", exc_info=True)
            return PhaseResult(
                phase=1,
                phase_name="render",
                passed=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            ), None


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

sandbox_renderer = SandboxRenderer()
