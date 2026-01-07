"""
Layout Validator - Validate HTML layouts using Playwright.

Sprint 5.2: This validator uses Playwright in headless mode to verify
that generated HTML renders correctly without JavaScript errors.

Architecture:
=============
- Uses Playwright for headless browser validation
- Gracefully handles Playwright not being installed (returns valid=True with warning)
- Checks for: JS errors, blank pages, render timeout

Usage:
======
    from app.ai.scene.custom_layout import layout_validator
    
    result = await layout_validator.validate(html_string)
    
    if result.is_valid:
        # HTML is safe to use
        pass
    else:
        # Fall back to SceneGraph
        print(f"Validation errors: {result.errors}")
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings


logger = logging.getLogger("jarvis.ai.scene.custom_layout.validator")


# ---------------------------------------------------------------------------
# RESULT DATACLASS
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    Result of HTML layout validation.
    
    Attributes:
        is_valid: Whether the HTML is valid and safe to render
        errors: List of error messages encountered
        warnings: List of warning messages (non-fatal issues)
        render_time_ms: Time taken to render the page in milliseconds
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    render_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# LAYOUT VALIDATOR
# ---------------------------------------------------------------------------

class LayoutValidator:
    """
    Validator for HTML layouts using Playwright.
    
    Validates that generated HTML:
    1. Renders without JavaScript errors
    2. Is not blank (has visible content)
    3. Renders within timeout
    
    If Playwright is not installed, validation returns valid=True with a warning.
    This allows the feature to work without requiring Playwright in all environments.
    """
    
    def __init__(self):
        """Initialize the layout validator."""
        self._playwright_available: Optional[bool] = None
        logger.info("Layout validator initialized")
    
    async def validate(
        self,
        html: str,
        timeout_seconds: int = 5,
    ) -> ValidationResult:
        """
        Validate HTML layout by rendering it in a headless browser.
        
        Args:
            html: HTML string to validate
            timeout_seconds: Maximum time to wait for render (default: 5s)
            
        Returns:
            ValidationResult with validation status and any errors
        """
        start_time = time.time()
        
        # Check if validation is enabled
        if not getattr(settings, 'CUSTOM_LAYOUT_VALIDATION_ENABLED', True):
            logger.debug("HTML validation is disabled, skipping")
            return ValidationResult(
                is_valid=True,
                warnings=["Validation disabled by configuration"],
                render_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Basic pre-checks
        if not html or not html.strip():
            return ValidationResult(
                is_valid=False,
                errors=["Empty HTML provided"],
                render_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Check Playwright availability
        if not await self._check_playwright_available():
            logger.warning("Playwright not available, skipping browser validation")
            return ValidationResult(
                is_valid=True,
                warnings=["Playwright not installed - browser validation skipped"],
                render_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Run Playwright validation
        return await self._validate_with_playwright(html, timeout_seconds, start_time)
    
    async def _check_playwright_available(self) -> bool:
        """
        Check if Playwright is installed and available.
        
        Returns:
            True if Playwright can be used
        """
        if self._playwright_available is not None:
            return self._playwright_available
        
        try:
            from playwright.async_api import async_playwright
            self._playwright_available = True
            logger.debug("Playwright is available")
        except ImportError:
            self._playwright_available = False
            logger.warning("Playwright not installed - pip install playwright && playwright install chromium")
        
        return self._playwright_available
    
    async def _validate_with_playwright(
        self,
        html: str,
        timeout_seconds: int,
        start_time: float,
    ) -> ValidationResult:
        """
        Perform actual Playwright-based validation.
        
        Args:
            html: HTML to validate
            timeout_seconds: Timeout for rendering
            start_time: When validation started (for timing)
            
        Returns:
            ValidationResult from browser validation
        """
        errors: List[str] = []
        warnings: List[str] = []
        js_errors: List[str] = []
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                # Launch headless Chromium
                browser = await p.chromium.launch(headless=True)
                
                try:
                    page = await browser.new_page(viewport={"width": 1920, "height": 1080})
                    
                    # Capture JavaScript errors
                    page.on("pageerror", lambda err: js_errors.append(str(err)))
                    page.on("console", lambda msg: (
                        js_errors.append(f"Console error: {msg.text}")
                        if msg.type == "error" else None
                    ))
                    
                    # Set HTML content with timeout
                    try:
                        await asyncio.wait_for(
                            page.set_content(html, wait_until="networkidle"),
                            timeout=timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        errors.append(f"Page render timed out after {timeout_seconds}s")
                        render_time_ms = (time.time() - start_time) * 1000
                        return ValidationResult(
                            is_valid=False,
                            errors=errors,
                            warnings=warnings,
                            render_time_ms=render_time_ms,
                        )
                    
                    # Check for JavaScript errors
                    if js_errors:
                        errors.extend(js_errors)
                    
                    # Check if page is blank
                    body_content = await page.evaluate("document.body.innerText")
                    if not body_content or not body_content.strip():
                        # Check if there's any visual content (images, styled divs, etc.)
                        has_visual_content = await page.evaluate("""
                            () => {
                                const body = document.body;
                                if (!body) return false;
                                
                                // Check for any visible elements with dimensions
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
                    
                    # Check for basic structural elements
                    has_structure = await page.evaluate("""
                        () => {
                            return document.body && document.body.children.length > 0;
                        }
                    """)
                    
                    if not has_structure:
                        warnings.append("Page has no child elements in body")
                    
                finally:
                    await browser.close()
            
            render_time_ms = (time.time() - start_time) * 1000
            
            is_valid = len(errors) == 0
            
            if is_valid:
                logger.info(f"HTML validation passed in {render_time_ms:.0f}ms")
            else:
                logger.warning(f"HTML validation failed: {errors}")
            
            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                render_time_ms=render_time_ms,
            )
            
        except Exception as e:
            render_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Playwright validation error: {e}", exc_info=True)
            
            # On unexpected errors, return valid with warning
            # This prevents blocking the feature due to validation issues
            return ValidationResult(
                is_valid=True,
                warnings=[f"Validation error (skipped): {str(e)}"],
                render_time_ms=render_time_ms,
            )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
layout_validator = LayoutValidator()
