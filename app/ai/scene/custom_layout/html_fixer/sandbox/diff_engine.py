"""
DiffEngine - Pixel-level image comparison with multi-scale support.

Sprint 5: Advanced visual comparison for interaction validation.

Uses PIL for image processing with configurable pixel tolerance
and multi-scale region comparison (tight, local, global).
"""

import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from PIL import Image, ImageChops


class ComparisonScale(Enum):
    """Scale levels for multi-region comparison."""

    TIGHT = "tight"    # Element bounding box + 20px padding
    LOCAL = "local"    # Element bounding box + 100px padding
    GLOBAL = "global"  # Full page comparison


@dataclass
class RegionDiff:
    """Result of comparing a specific region."""

    scale: ComparisonScale
    diff_ratio: float              # 0.0-1.0, percentage of pixels changed
    diff_count: int                # Absolute pixel count
    total_pixels: int              # Total pixels in region
    region_box: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
    diff_image: Optional[bytes] = None  # PNG of highlighted differences

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for reporting."""
        return {
            "scale": self.scale.value,
            "diff_ratio": self.diff_ratio,
            "diff_count": self.diff_count,
            "total_pixels": self.total_pixels,
            "region_box": self.region_box,
        }


@dataclass
class DiffResult:
    """Complete result of multi-scale comparison."""

    tight: RegionDiff              # Element + 20px
    local: RegionDiff              # Element + 100px
    global_: RegionDiff            # Full page (global_ to avoid keyword)
    element_box: Dict[str, float]  # Original element bounding box
    has_significant_change: bool   # Any scale exceeded threshold
    primary_change_location: ComparisonScale  # Where change was detected

    @property
    def max_diff_ratio(self) -> float:
        """Get maximum diff ratio across all scales."""
        return max(
            self.tight.diff_ratio,
            self.local.diff_ratio,
            self.global_.diff_ratio
        )

    @property
    def tight_diff_ratio(self) -> float:
        """Shortcut for tight region diff ratio."""
        return self.tight.diff_ratio

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for reporting."""
        return {
            "tight": self.tight.to_dict(),
            "local": self.local.to_dict(),
            "global": self.global_.to_dict(),
            "element_box": self.element_box,
            "has_significant_change": self.has_significant_change,
            "primary_change_location": self.primary_change_location.value,
            "max_diff_ratio": self.max_diff_ratio,
        }


class DiffEngine:
    """
    Multi-scale pixel comparison engine.

    Compares before/after screenshots at three scales:
    - tight: Element bounding box + 20px padding (detects direct feedback)
    - local: Element bounding box + 100px padding (detects nearby effects)
    - global: Full page (detects navigation/major changes)

    Usage:
        engine = DiffEngine()
        result = engine.compare(before_bytes, after_bytes, element_box)

        if result.has_significant_change:
            print(f"Change detected at {result.primary_change_location}")
    """

    # Default configuration
    TIGHT_PADDING = 20     # Pixels around element for tight comparison
    LOCAL_PADDING = 100    # Pixels around element for local comparison
    THRESHOLD = 0.02       # 2% = significant change
    PIXEL_TOLERANCE = 20   # Per-channel difference to count as "changed"

    def __init__(
        self,
        tight_padding: int = TIGHT_PADDING,
        local_padding: int = LOCAL_PADDING,
        threshold: float = THRESHOLD,
        pixel_tolerance: int = PIXEL_TOLERANCE,
    ):
        """
        Initialize the DiffEngine.

        Args:
            tight_padding: Pixels around element for tight comparison
            local_padding: Pixels around element for local comparison
            threshold: Percentage threshold for significant change (0.0-1.0)
            pixel_tolerance: Per-channel difference to count as changed (0-255)
        """
        self.tight_padding = tight_padding
        self.local_padding = local_padding
        self.threshold = threshold
        self.pixel_tolerance = pixel_tolerance

    def compare(
        self,
        before: bytes,
        after: bytes,
        element_box: Dict[str, float],
        generate_diff_images: bool = False,
    ) -> DiffResult:
        """
        Perform multi-scale comparison.

        Args:
            before: PNG screenshot before interaction
            after: PNG screenshot after interaction
            element_box: {x, y, width, height} of clicked element
            generate_diff_images: If True, generate visual diff PNGs

        Returns:
            DiffResult with comparison at all scales
        """
        # Load images
        img_before = Image.open(io.BytesIO(before)).convert("RGB")
        img_after = Image.open(io.BytesIO(after)).convert("RGB")

        # Ensure same size
        if img_before.size != img_after.size:
            # Resize to minimum common size
            min_size = (
                min(img_before.width, img_after.width),
                min(img_before.height, img_after.height)
            )
            img_before = img_before.resize(min_size)
            img_after = img_after.resize(min_size)

        # Calculate regions
        tight_box = self._expand_box(
            element_box, self.tight_padding, img_before.size
        )
        local_box = self._expand_box(
            element_box, self.local_padding, img_before.size
        )

        # Compare at each scale
        tight_result = self._compare_region(
            img_before, img_after, tight_box,
            ComparisonScale.TIGHT, generate_diff_images
        )
        local_result = self._compare_region(
            img_before, img_after, local_box,
            ComparisonScale.LOCAL, generate_diff_images
        )
        global_result = self._compare_region(
            img_before, img_after, None,
            ComparisonScale.GLOBAL, generate_diff_images
        )

        # Determine primary change location (prioritize tight -> local -> global)
        if tight_result.diff_ratio >= self.threshold:
            primary = ComparisonScale.TIGHT
        elif local_result.diff_ratio >= self.threshold:
            primary = ComparisonScale.LOCAL
        elif global_result.diff_ratio >= self.threshold:
            primary = ComparisonScale.GLOBAL
        else:
            primary = ComparisonScale.TIGHT  # Default

        has_significant = any([
            tight_result.diff_ratio >= self.threshold,
            local_result.diff_ratio >= self.threshold,
            global_result.diff_ratio >= self.threshold,
        ])

        return DiffResult(
            tight=tight_result,
            local=local_result,
            global_=global_result,
            element_box=element_box,
            has_significant_change=has_significant,
            primary_change_location=primary,
        )

    def _expand_box(
        self,
        box: Dict[str, float],
        padding: int,
        image_size: Tuple[int, int],
    ) -> Tuple[int, int, int, int]:
        """
        Expand bounding box by padding, clamped to image bounds.

        Args:
            box: {x, y, width, height} element bounding box
            padding: Pixels to expand in each direction
            image_size: (width, height) of image

        Returns:
            (x1, y1, x2, y2) tuple for PIL crop
        """
        x1 = max(0, int(box["x"] - padding))
        y1 = max(0, int(box["y"] - padding))
        x2 = min(image_size[0], int(box["x"] + box["width"] + padding))
        y2 = min(image_size[1], int(box["y"] + box["height"] + padding))
        return (x1, y1, x2, y2)

    def _compare_region(
        self,
        img1: Image.Image,
        img2: Image.Image,
        region: Optional[Tuple[int, int, int, int]],
        scale: ComparisonScale,
        generate_diff: bool,
    ) -> RegionDiff:
        """
        Compare a specific region of two images.

        Args:
            img1: Before image
            img2: After image
            region: (x1, y1, x2, y2) or None for full image
            scale: Which comparison scale this is
            generate_diff: Whether to generate diff image

        Returns:
            RegionDiff with comparison results
        """
        # Crop if region specified
        if region:
            crop1 = img1.crop(region)
            crop2 = img2.crop(region)
        else:
            crop1 = img1
            crop2 = img2
            region = (0, 0, img1.width, img1.height)

        # Pixel-by-pixel comparison
        pixels1 = list(crop1.getdata())
        pixels2 = list(crop2.getdata())

        diff_count = 0
        total_pixels = len(pixels1)

        for p1, p2 in zip(pixels1, pixels2):
            # Calculate average channel difference
            channel_diff = sum(abs(a - b) for a, b in zip(p1, p2)) / 3
            if channel_diff > self.pixel_tolerance:
                diff_count += 1

        diff_ratio = diff_count / total_pixels if total_pixels > 0 else 0.0

        # Generate diff image if requested
        diff_image = None
        if generate_diff:
            diff_image = self._generate_diff_image(crop1, crop2)

        return RegionDiff(
            scale=scale,
            diff_ratio=diff_ratio,
            diff_count=diff_count,
            total_pixels=total_pixels,
            region_box=region,
            diff_image=diff_image,
        )

    def _generate_diff_image(
        self,
        img1: Image.Image,
        img2: Image.Image,
    ) -> bytes:
        """
        Generate a visual diff image highlighting changed pixels.

        Changed pixels are shown in red, unchanged pixels are dimmed.

        Args:
            img1: Before image (cropped region)
            img2: After image (cropped region)

        Returns:
            PNG bytes of diff visualization
        """
        # Create output image
        output = Image.new("RGB", img1.size, (0, 0, 0))

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        output_pixels = []
        for p1, p2 in zip(pixels1, pixels2):
            channel_diff = sum(abs(a - b) for a, b in zip(p1, p2)) / 3
            if channel_diff > self.pixel_tolerance:
                # Mark changed pixel as red
                output_pixels.append((255, 0, 0))
            else:
                # Keep original (dimmed)
                output_pixels.append((p1[0] // 2, p1[1] // 2, p1[2] // 2))

        output.putdata(output_pixels)

        # Export as PNG
        buffer = io.BytesIO()
        output.save(buffer, format="PNG")
        return buffer.getvalue()

    def compare_quick(self, before: bytes, after: bytes) -> float:
        """
        Quick global comparison (for backward compatibility).

        This method provides backward compatibility with Sprint 4's
        simple comparison interface.

        Args:
            before: PNG screenshot before interaction
            after: PNG screenshot after interaction

        Returns:
            diff_ratio for full page (0.0-1.0)
        """
        img1 = Image.open(io.BytesIO(before)).convert("RGB")
        img2 = Image.open(io.BytesIO(after)).convert("RGB")

        # Ensure same size
        if img1.size != img2.size:
            min_size = (min(img1.width, img2.width), min(img1.height, img2.height))
            img1 = img1.resize(min_size)
            img2 = img2.resize(min_size)

        result = self._compare_region(
            img1, img2, None, ComparisonScale.GLOBAL, False
        )
        return result.diff_ratio
