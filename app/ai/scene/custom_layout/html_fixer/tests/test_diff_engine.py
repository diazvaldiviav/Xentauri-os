"""
Tests for DiffEngine (Sprint 5).

Tests the multi-scale pixel comparison engine.
"""

import io
import pytest
from PIL import Image

from html_fixer.sandbox.diff_engine import (
    DiffEngine,
    DiffResult,
    RegionDiff,
    ComparisonScale,
)


class TestDiffEngine:
    """Unit tests for DiffEngine."""

    def _create_solid_image(
        self,
        color: tuple,
        size: tuple = (100, 100)
    ) -> bytes:
        """Create a solid color PNG image."""
        img = Image.new("RGB", size, color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def _create_image_with_region(
        self,
        bg_color: tuple,
        region_color: tuple,
        region_box: tuple,
        size: tuple = (200, 200)
    ) -> bytes:
        """Create image with a colored region."""
        img = Image.new("RGB", size, bg_color)
        for x in range(region_box[0], region_box[2]):
            for y in range(region_box[1], region_box[3]):
                if 0 <= x < size[0] and 0 <= y < size[1]:
                    img.putpixel((x, y), region_color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_identical_images(self):
        """Test comparison of identical images."""
        engine = DiffEngine()
        img = self._create_solid_image((255, 255, 255))

        result = engine.compare(
            img, img,
            {"x": 10, "y": 10, "width": 30, "height": 30}
        )

        assert result.tight.diff_ratio == 0.0
        assert result.local.diff_ratio == 0.0
        assert result.global_.diff_ratio == 0.0
        assert not result.has_significant_change

    def test_completely_different_images(self):
        """Test comparison of completely different images."""
        engine = DiffEngine()
        img1 = self._create_solid_image((0, 0, 0))
        img2 = self._create_solid_image((255, 255, 255))

        result = engine.compare(
            img1, img2,
            {"x": 10, "y": 10, "width": 30, "height": 30}
        )

        assert result.tight.diff_ratio == 1.0
        assert result.global_.diff_ratio == 1.0
        assert result.has_significant_change

    def test_local_change_only(self):
        """Test when only local region changes."""
        engine = DiffEngine()
        size = (200, 200)

        # Before: all white
        img1 = self._create_solid_image((255, 255, 255), size)

        # After: red square near (but not at) element
        # Element at (20, 20), tight = ±20px = (0, 0, 60, 60)
        # Red at (70, 70, 90, 90) - outside tight, inside local
        img2 = self._create_image_with_region(
            (255, 255, 255),
            (255, 0, 0),
            (70, 70, 90, 90),
            size
        )

        result = engine.compare(
            img1, img2,
            {"x": 20, "y": 20, "width": 20, "height": 20}
        )

        # Tight should have low diff (element didn't change)
        # Local should have higher diff (includes the red region)
        assert result.tight.diff_ratio < result.local.diff_ratio

    def test_tight_change_detection(self):
        """Test detection of change in tight region."""
        engine = DiffEngine()
        size = (200, 200)

        # Element at (50, 50) size 40x40
        element_box = {"x": 50, "y": 50, "width": 40, "height": 40}

        # Before: all white
        img1 = self._create_solid_image((255, 255, 255), size)

        # After: element region becomes red
        img2 = self._create_image_with_region(
            (255, 255, 255),
            (255, 0, 0),
            (50, 50, 90, 90),
            size
        )

        result = engine.compare(img1, img2, element_box)

        assert result.tight.diff_ratio > 0.1  # Significant change in tight
        assert result.has_significant_change
        assert result.primary_change_location == ComparisonScale.TIGHT

    def test_quick_compare(self):
        """Test quick comparison method."""
        engine = DiffEngine()
        img1 = self._create_solid_image((0, 0, 0))
        img2 = self._create_solid_image((255, 255, 255))

        ratio = engine.compare_quick(img1, img2)

        assert ratio == 1.0

    def test_quick_compare_identical(self):
        """Test quick comparison with identical images."""
        engine = DiffEngine()
        img = self._create_solid_image((128, 128, 128))

        ratio = engine.compare_quick(img, img)

        assert ratio == 0.0

    def test_diff_image_generation(self):
        """Test that diff images are generated when requested."""
        engine = DiffEngine()
        img1 = self._create_solid_image((0, 0, 0))
        img2 = self._create_solid_image((255, 255, 255))

        result = engine.compare(
            img1, img2,
            {"x": 10, "y": 10, "width": 30, "height": 30},
            generate_diff_images=True
        )

        assert result.tight.diff_image is not None
        assert len(result.tight.diff_image) > 0
        # Verify it's valid PNG
        img = Image.open(io.BytesIO(result.tight.diff_image))
        assert img.format == "PNG"

    def test_diff_image_not_generated_by_default(self):
        """Test that diff images are not generated by default."""
        engine = DiffEngine()
        img1 = self._create_solid_image((0, 0, 0))
        img2 = self._create_solid_image((255, 255, 255))

        result = engine.compare(
            img1, img2,
            {"x": 10, "y": 10, "width": 30, "height": 30},
            generate_diff_images=False
        )

        assert result.tight.diff_image is None
        assert result.local.diff_image is None
        assert result.global_.diff_image is None

    def test_custom_thresholds(self):
        """Test engine with custom thresholds."""
        engine = DiffEngine(
            tight_padding=10,
            local_padding=50,
            threshold=0.05,
            pixel_tolerance=30,
        )

        assert engine.tight_padding == 10
        assert engine.local_padding == 50
        assert engine.threshold == 0.05
        assert engine.pixel_tolerance == 30

    def test_bounding_box_expansion(self):
        """Test bounding box expansion and clamping."""
        engine = DiffEngine(tight_padding=20)

        # Box at edge of image
        box = {"x": 5, "y": 5, "width": 20, "height": 20}
        expanded = engine._expand_box(box, 20, (100, 100))

        # Should clamp to image bounds
        assert expanded[0] == 0  # x1 clamped
        assert expanded[1] == 0  # y1 clamped
        assert expanded[2] == 45  # x2 = 5 + 20 + 20
        assert expanded[3] == 45  # y2 = 5 + 20 + 20


class TestDiffResult:
    """Tests for DiffResult dataclass."""

    def test_max_diff_ratio(self):
        """Test max_diff_ratio property."""
        result = DiffResult(
            tight=RegionDiff(ComparisonScale.TIGHT, 0.05, 100, 2000),
            local=RegionDiff(ComparisonScale.LOCAL, 0.02, 200, 10000),
            global_=RegionDiff(ComparisonScale.GLOBAL, 0.01, 500, 50000),
            element_box={"x": 0, "y": 0, "width": 50, "height": 50},
            has_significant_change=True,
            primary_change_location=ComparisonScale.TIGHT,
        )

        assert result.max_diff_ratio == 0.05

    def test_tight_diff_ratio(self):
        """Test tight_diff_ratio shortcut property."""
        result = DiffResult(
            tight=RegionDiff(ComparisonScale.TIGHT, 0.03, 100, 2000),
            local=RegionDiff(ComparisonScale.LOCAL, 0.02, 200, 10000),
            global_=RegionDiff(ComparisonScale.GLOBAL, 0.01, 500, 50000),
            element_box={"x": 0, "y": 0, "width": 50, "height": 50},
            has_significant_change=True,
            primary_change_location=ComparisonScale.TIGHT,
        )

        assert result.tight_diff_ratio == 0.03

    def test_to_dict(self):
        """Test serialization."""
        result = DiffResult(
            tight=RegionDiff(ComparisonScale.TIGHT, 0.05, 100, 2000),
            local=RegionDiff(ComparisonScale.LOCAL, 0.02, 200, 10000),
            global_=RegionDiff(ComparisonScale.GLOBAL, 0.01, 500, 50000),
            element_box={"x": 0, "y": 0, "width": 50, "height": 50},
            has_significant_change=True,
            primary_change_location=ComparisonScale.TIGHT,
        )

        d = result.to_dict()
        assert "tight" in d
        assert d["has_significant_change"] is True
        assert d["primary_change_location"] == "tight"
        assert d["max_diff_ratio"] == 0.05


class TestRegionDiff:
    """Tests for RegionDiff dataclass."""

    def test_to_dict(self):
        """Test serialization."""
        region = RegionDiff(
            scale=ComparisonScale.TIGHT,
            diff_ratio=0.05,
            diff_count=100,
            total_pixels=2000,
            region_box=(10, 10, 50, 50),
        )

        d = region.to_dict()
        assert d["scale"] == "tight"
        assert d["diff_ratio"] == 0.05
        assert d["diff_count"] == 100
        assert d["total_pixels"] == 2000
        assert d["region_box"] == (10, 10, 50, 50)


class TestComparisonScale:
    """Tests for ComparisonScale enum."""

    def test_all_scales_exist(self):
        """Test all expected scales are defined."""
        assert ComparisonScale.TIGHT.value == "tight"
        assert ComparisonScale.LOCAL.value == "local"
        assert ComparisonScale.GLOBAL.value == "global"
