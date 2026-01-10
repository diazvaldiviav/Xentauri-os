"""
Visual Analyzer - Phase 2: Screenshot capture and visual analysis.

Sprint 6: Visual-based validation system.

This module handles visual analysis:
- Capture screenshots from Playwright page
- Analyze image statistics (histogram, variance, uniformity)
- Detect blank/solid color pages
- Compare before/after screenshots for visual deltas
"""

import io
import logging
import time
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
        pixel_threshold = 10  # RGB difference per channel

        for p1, p2 in zip(pixels1, pixels2):
            # Calculate per-channel difference
            channel_diff = sum(abs(a - b) for a, b in zip(p1, p2)) / 3
            if channel_diff > pixel_threshold:
                diff_count += 1

        pixel_diff_ratio = diff_count / total_pixels if total_pixels > 0 else 0

        # Structural change if more than 5% of pixels changed
        structural_change = pixel_diff_ratio > 0.05

        return VisualDelta(
            before=before,
            after=after,
            pixel_diff_ratio=pixel_diff_ratio,
            structural_change=structural_change,
            region_analyzed=region,
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


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

visual_analyzer = VisualAnalyzer()
