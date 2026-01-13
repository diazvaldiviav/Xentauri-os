"""
Visual Analyzer - Phase 2: Screenshot capture and visual analysis.

Sprint 6: Visual-based validation system.
Sprint 7: Added screenshot saving for vision-based repair.
Sprint 11: Added visual concordance check (screenshot vs user request).

This module handles visual analysis:
- Capture screenshots from Playwright page
- Analyze image statistics (histogram, variance, uniformity)
- Detect blank/solid color pages
- Compare before/after screenshots for visual deltas
- Save screenshots for vision-based repair (Sprint 7)
- Visual concordance check with Gemini Flash (Sprint 11)
"""

import base64
import io
import logging
import os
import time
from datetime import datetime
from typing import Optional, Tuple, TYPE_CHECKING

from .contracts import (
    BoundingBox,
    PhaseResult,
    ValidationContract,
    VisualDelta,
    VisualSnapshot,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.visual_analyzer")


# ---------------------------------------------------------------------------
# VISUAL ANALYZER
# ---------------------------------------------------------------------------

class VisualAnalyzer:
    """
    Phase 2: Screenshot capture and visual analysis.

    Detects blank pages and measures visual changes between states.
    Uses PIL for image processing.
    """

    def __init__(self):
        self._pil_available: Optional[bool] = None

    def _check_pil_available(self) -> bool:
        """Check if PIL/Pillow is installed."""
        if self._pil_available is not None:
            return self._pil_available

        try:
            from PIL import Image
            self._pil_available = True
            logger.debug("PIL/Pillow is available")
        except ImportError:
            self._pil_available = False
            logger.error("PIL not installed - pip install Pillow")

        return self._pil_available

    async def analyze(
        self,
        page: "Page",
        contract: ValidationContract,
    ) -> Tuple[PhaseResult, Optional[VisualSnapshot]]:
        """
        Capture screenshot and analyze visual properties.

        Checks:
        - Histogram variance (uniform = blank)
        - Non-background pixel ratio
        - Visual content presence

        Args:
            page: Playwright page with HTML loaded
            contract: Validation contract with thresholds

        Returns:
            (PhaseResult, VisualSnapshot) - Snapshot is None if analysis failed
        """
        start_time = time.time()

        if not self._check_pil_available():
            return PhaseResult(
                phase=2,
                phase_name="visual_analysis",
                passed=False,
                error="PIL/Pillow not installed",
                duration_ms=(time.time() - start_time) * 1000,
            ), None

        try:
            # Capture screenshot
            screenshot_bytes = await page.screenshot(type="png")

            # Analyze image
            snapshot = self._analyze_image(screenshot_bytes)

            # Check if page is blank (too uniform)
            is_blank = snapshot.is_blank(contract.blank_page_threshold)

            duration_ms = (time.time() - start_time) * 1000

            if is_blank:
                logger.warning(
                    f"Phase 2 (visual): Page is blank - "
                    f"non_background_ratio={snapshot.non_background_ratio:.3f}, "
                    f"threshold={1 - contract.blank_page_threshold:.3f}"
                )
                return PhaseResult(
                    phase=2,
                    phase_name="visual_analysis",
                    passed=False,
                    error=f"Page is visually blank ({snapshot.non_background_ratio:.1%} content)",
                    details={
                        "non_background_ratio": snapshot.non_background_ratio,
                        "mean_pixel": snapshot.mean_pixel,
                        "variance": snapshot.variance,
                        "threshold": 1 - contract.blank_page_threshold,
                    },
                    duration_ms=duration_ms,
                ), snapshot

            logger.info(
                f"Phase 2 (visual) passed - "
                f"content={snapshot.non_background_ratio:.1%}, "
                f"variance={snapshot.variance:.1f}"
            )

            return PhaseResult(
                phase=2,
                phase_name="visual_analysis",
                passed=True,
                details={
                    "non_background_ratio": snapshot.non_background_ratio,
                    "mean_pixel": snapshot.mean_pixel,
                    "variance": snapshot.variance,
                    "image_size": f"{snapshot.width}x{snapshot.height}",
                },
                duration_ms=duration_ms,
            ), snapshot

        except Exception as e:
            logger.error(f"Visual analysis error: {e}", exc_info=True)
            return PhaseResult(
                phase=2,
                phase_name="visual_analysis",
                passed=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            ), None

    def _analyze_image(self, image_bytes: bytes) -> VisualSnapshot:
        """
        Compute image statistics using PIL.

        Converts to grayscale and computes:
        - 256-bin histogram
        - Mean pixel value
        - Pixel variance
        - Ratio of pixels different from background
        """
        from PIL import Image

        # Load image and convert to grayscale
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        width, height = img.size
        pixels = list(img.getdata())
        total_pixels = len(pixels)

        # Compute histogram (256 bins for grayscale)
        histogram = [0] * 256
        for p in pixels:
            histogram[p] += 1

        # Compute mean
        mean_pixel = sum(pixels) / total_pixels

        # Compute variance
        variance = sum((p - mean_pixel) ** 2 for p in pixels) / total_pixels

        # Find mode (most common pixel value = background)
        mode_value = histogram.index(max(histogram))

        # Count pixels different from background (with tolerance)
        tolerance = 15  # Pixels within 15 of mode are considered background
        non_background = sum(
            1 for p in pixels if abs(p - mode_value) > tolerance
        )
        non_background_ratio = non_background / total_pixels

        return VisualSnapshot(
            image_bytes=image_bytes,
            width=width,
            height=height,
            histogram=histogram,
            mean_pixel=mean_pixel,
            variance=variance,
            non_background_ratio=non_background_ratio,
        )

    async def capture(self, page: "Page") -> VisualSnapshot:
        """
        Capture screenshot and return snapshot (for interaction testing).

        Raises:
            Exception if capture fails
        """
        screenshot_bytes = await page.screenshot(type="png")
        return self._analyze_image(screenshot_bytes)

    def compare(
        self,
        before: VisualSnapshot,
        after: VisualSnapshot,
        region: Optional[BoundingBox] = None,
    ) -> VisualDelta:
        """
        Compare two snapshots and compute visual delta.

        Args:
            before: Snapshot before interaction
            after: Snapshot after interaction
            region: Optional region to focus comparison (e.g., near clicked element)

        Returns:
            VisualDelta with pixel difference ratio
        """
        from PIL import Image

        # Load images
        img1 = Image.open(io.BytesIO(before.image_bytes))
        img2 = Image.open(io.BytesIO(after.image_bytes))

        # Crop to region if specified
        if region:
            # Ensure region is within image bounds
            x1 = max(0, int(region.x))
            y1 = max(0, int(region.y))
            x2 = min(img1.width, int(region.x + region.width))
            y2 = min(img1.height, int(region.y + region.height))

            if x2 > x1 and y2 > y1:
                box = (x1, y1, x2, y2)
                img1 = img1.crop(box)
                img2 = img2.crop(box)

        # Convert to RGB for comparison
        img1 = img1.convert("RGB")
        img2 = img2.convert("RGB")

        # Ensure same size
        if img1.size != img2.size:
            # Resize to smaller
            min_size = (min(img1.width, img2.width), min(img1.height, img2.height))
            img1 = img1.resize(min_size)
            img2 = img2.resize(min_size)

        # Pixel-by-pixel comparison
        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        diff_count = 0
        total_pixels = len(pixels1)

        # Threshold for considering a pixel "different"
        # Sprint 6.5: Lowered from 30 to 20 to detect subtler hover/click feedback
        # 20 = catches 4px borders and subtle color shifts that 30 missed
        pixel_threshold = 20  # RGB difference per channel

        for p1, p2 in zip(pixels1, pixels2):
            # Calculate per-channel difference
            channel_diff = sum(abs(a - b) for a, b in zip(p1, p2)) / 3
            if channel_diff > pixel_threshold:
                diff_count += 1

        pixel_diff_ratio = diff_count / total_pixels if total_pixels > 0 else 0

        # Structural change if more than 5% of pixels changed
        structural_change = pixel_diff_ratio > 0.05

        # Sprint 6.3: Calculate element-relative diff ratio
        # If a region was specified (the clicked element), calculate what % of IT changed
        element_pixels = 0
        element_diff_ratio = 0.0
        if region:
            element_pixels = int(region.width * region.height)
            if element_pixels > 0:
                # For element-relative, we use the cropped image comparison
                # which already happened above, so diff_count is for the region
                element_diff_ratio = diff_count / element_pixels

        # Sprint 6.2: Include absolute counts for fixer context
        # Sprint 6.3: Include element-relative metrics for adaptive threshold
        return VisualDelta(
            before=before,
            after=after,
            pixel_diff_ratio=pixel_diff_ratio,
            structural_change=structural_change,
            region_analyzed=region,
            diff_count=diff_count,
            total_pixels=total_pixels,
            element_pixels=element_pixels,
            element_diff_ratio=element_diff_ratio,
        )

    def compare_regions(
        self,
        before: VisualSnapshot,
        after: VisualSnapshot,
        regions: list[BoundingBox],
    ) -> list[Tuple[BoundingBox, float]]:
        """
        Compare multiple regions and return per-region deltas.

        Useful for detecting which specific area changed after interaction.

        Args:
            before: Snapshot before
            after: Snapshot after
            regions: List of regions to check

        Returns:
            List of (region, diff_ratio) tuples sorted by diff_ratio descending
        """
        results = []

        for region in regions:
            delta = self.compare(before, after, region)
            results.append((region, delta.pixel_diff_ratio))

        # Sort by difference (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    async def check_visual_concordance(
        self,
        screenshot_bytes: bytes,
        user_request: str,
    ) -> Tuple[bool, str, float]:
        """
        Sprint 11: Check if screenshot matches user request using Gemini Flash.

        Uses Gemini Flash (NO thinking) to compare the visual output
        against what the user originally requested.

        Args:
            screenshot_bytes: PNG screenshot of rendered page
            user_request: Original user request (what they asked for)

        Returns:
            Tuple of (passed, diagnosis, confidence):
            - passed: True if visual matches request
            - diagnosis: Explanation of what matches or doesn't
            - confidence: 0.0-1.0 score
        """
        from app.ai.providers.gemini import gemini_provider
        from app.core.config import settings

        start_time = time.time()

        # Resize screenshot for API
        optimized_screenshot = resize_image_for_api(screenshot_bytes)

        # Build concordance check prompt
        prompt = f"""Analyze this screenshot and compare it to the user's request.

## USER REQUEST
"{user_request}"

## YOUR TASK
1. Look at the screenshot carefully
2. Determine if the visual output matches what the user requested
3. Check for:
   - Correct content displayed (text, images, data)
   - Appropriate layout for the request type
   - Required elements present (buttons, inputs, charts, etc.)
   - No obvious visual bugs (overlapping elements, cut-off text)

## OUTPUT FORMAT
Respond with EXACTLY this format:

CONCORDANCE: [PASS/FAIL]
CONFIDENCE: [0.0-1.0]
DIAGNOSIS: [1-2 sentences explaining what matches or doesn't match]

Examples:
- CONCORDANCE: PASS
  CONFIDENCE: 0.95
  DIAGNOSIS: Screenshot shows a trivia interface with question and 4 answer options as requested.

- CONCORDANCE: FAIL
  CONFIDENCE: 0.85
  DIAGNOSIS: User requested a solar system but only the sun is visible, planets are missing.
"""

        system_prompt = """You are a visual QA specialist. Your job is to verify that web page screenshots match user requirements.

Be strict but fair:
- PASS if the core request is satisfied even if styling differs
- FAIL if key elements are missing, invisible, or clearly broken
- Always explain your reasoning briefly

Output ONLY the specified format, nothing else."""

        try:
            response = await gemini_provider.generate_with_vision(
                prompt=prompt,
                images=[optimized_screenshot],
                system_prompt=system_prompt,
                max_tokens=256,
                model_override=settings.GEMINI_REASONING_MODEL,  # Flash 3
            )

            if not response.success:
                logger.warning(f"Visual concordance check failed: {response.error}")
                # On API failure, pass through (don't block on concordance)
                return True, f"Concordance check unavailable: {response.error}", 0.5

            # Parse response
            content = response.content.strip()
            passed, diagnosis, confidence = self._parse_concordance_response(content)

            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Visual concordance: {'PASS' if passed else 'FAIL'} "
                f"(confidence={confidence:.2f}, latency={latency_ms:.0f}ms)"
            )

            return passed, diagnosis, confidence

        except Exception as e:
            logger.error(f"Visual concordance error: {e}", exc_info=True)
            # On error, pass through
            return True, f"Concordance check error: {e}", 0.5

    def _parse_concordance_response(self, content: str) -> Tuple[bool, str, float]:
        """Parse the structured concordance response from Flash."""
        import re

        # Default values
        passed = True
        diagnosis = "Unable to parse concordance response"
        confidence = 0.5

        # Parse CONCORDANCE
        concordance_match = re.search(r'CONCORDANCE:\s*(PASS|FAIL)', content, re.IGNORECASE)
        if concordance_match:
            passed = concordance_match.group(1).upper() == "PASS"

        # Parse CONFIDENCE
        confidence_match = re.search(r'CONFIDENCE:\s*([0-9.]+)', content)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                pass

        # Parse DIAGNOSIS
        diagnosis_match = re.search(r'DIAGNOSIS:\s*(.+?)(?:\n|$)', content, re.DOTALL)
        if diagnosis_match:
            diagnosis = diagnosis_match.group(1).strip()

        return passed, diagnosis, confidence


# ---------------------------------------------------------------------------
# SCREENSHOT SAVING - Sprint 7
# ---------------------------------------------------------------------------

# Directory for saving screenshots (same as debug HTML)
SCREENSHOT_DEBUG_DIR = os.environ.get("HTML_DEBUG_DIR", "/tmp/jarvis_debug_html")


def save_screenshot(
    image_bytes: bytes,
    prefix: str = "screenshot",
    suffix: str = "",
) -> Optional[str]:
    """
    Sprint 7: Save screenshot to disk for vision-based repair.

    Args:
        image_bytes: PNG screenshot bytes
        prefix: Filename prefix (e.g., "page", "element")
        suffix: Filename suffix (e.g., "before", "after")

    Returns:
        Path to saved file, or None if save failed
    """
    try:
        os.makedirs(SCREENSHOT_DEBUG_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suffix_part = f"_{suffix}" if suffix else ""
        filename = f"{prefix}_{timestamp}{suffix_part}.png"
        filepath = os.path.join(SCREENSHOT_DEBUG_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        logger.debug(f"Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        logger.warning(f"Failed to save screenshot: {e}")
        return None


def image_to_base64(image_bytes: bytes) -> str:
    """
    Sprint 7: Convert image bytes to base64 string for Claude vision API.

    Args:
        image_bytes: PNG image bytes

    Returns:
        Base64-encoded string
    """
    return base64.b64encode(image_bytes).decode("utf-8")


def resize_image_for_api(
    image_bytes: bytes,
    max_dimension: int = 1568,
) -> bytes:
    """
    Sprint 7: Resize image if too large for Claude vision API.

    Claude's vision has optimal performance at ~1568px max dimension.
    Larger images are resized automatically but it's more efficient to do it here.

    Args:
        image_bytes: Original PNG bytes
        max_dimension: Maximum width or height (default 1568)

    Returns:
        Resized PNG bytes (or original if already small enough)
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        # Check if resize needed
        if width <= max_dimension and height <= max_dimension:
            return image_bytes

        # Calculate new size maintaining aspect ratio
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))

        # Resize with high-quality resampling
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert back to bytes
        output = io.BytesIO()
        resized.save(output, format="PNG")
        return output.getvalue()

    except Exception as e:
        logger.warning(f"Failed to resize image: {e}")
        return image_bytes


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

visual_analyzer = VisualAnalyzer()
