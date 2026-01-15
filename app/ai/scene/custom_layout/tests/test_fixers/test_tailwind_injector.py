"""
Unit tests for TailwindInjector.

Tests HTML modification via Tailwind class patches.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.contracts.patches import TailwindPatch, PatchSet
from html_fixer.fixers import TailwindInjector, InjectionResult


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def make_patch(
    selector: str = "#btn",
    add: list = None,
    remove: list = None,
    reason: str = None,
) -> TailwindPatch:
    """Helper to create TailwindPatch for tests."""
    return TailwindPatch(
        selector=selector,
        add_classes=add or [],
        remove_classes=remove or [],
        reason=reason,
    )


def make_patchset(patches: list = None, source: str = "test") -> PatchSet:
    """Helper to create PatchSet for tests."""
    return PatchSet(patches=patches or [], source=source)


# ============================================================================
# INJECTION RESULT TESTS
# ============================================================================


class TestInjectionResult:
    """Tests for InjectionResult dataclass."""

    def test_all_applied_true(self):
        """Should return True when all patches applied."""
        result = InjectionResult(
            success=True,
            html="<div></div>",
            applied=[make_patch()],
            failed=[],
        )
        assert result.all_applied is True

    def test_all_applied_false(self):
        """Should return False when some patches failed."""
        result = InjectionResult(
            success=True,
            html="<div></div>",
            applied=[make_patch()],
            failed=[(make_patch(selector="#missing"), "Not found")],
        )
        assert result.all_applied is False

    def test_applied_count(self):
        """Should count applied patches."""
        result = InjectionResult(
            success=True,
            html="<div></div>",
            applied=[make_patch(), make_patch(selector="#btn2")],
            failed=[],
        )
        assert result.applied_count == 2

    def test_describe(self):
        """Should generate human-readable description."""
        result = InjectionResult(
            success=True,
            html="<div></div>",
            applied=[make_patch()],
            failed=[],
        )
        desc = result.describe()

        assert "SUCCESS" in desc
        assert "1" in desc


# ============================================================================
# BASIC INJECTION TESTS
# ============================================================================


class TestBasicInjection:
    """Tests for basic injection operations."""

    def test_inject_adds_classes(self, injector):
        """Should add classes to element."""
        html = '<button class="bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-50", "relative"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert "z-50" in result.html
        assert "relative" in result.html

    def test_inject_removes_classes(self, injector):
        """Should remove classes from element."""
        html = '<button class="bg-blue-500 hidden">Click</button>'
        patch = make_patch(selector="button", remove=["hidden"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert "hidden" not in result.html
        assert "bg-blue-500" in result.html

    def test_inject_add_and_remove(self, injector):
        """Should add and remove classes in same patch."""
        html = '<button class="opacity-0 z-10">Click</button>'
        patch = make_patch(
            selector="button",
            add=["opacity-100", "z-50"],
            remove=["opacity-0", "z-10"],
        )
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert "opacity-100" in result.html
        assert "z-50" in result.html
        assert "opacity-0" not in result.html
        assert "z-10" not in result.html

    def test_inject_no_duplicate_classes(self, injector):
        """Should not add duplicate classes."""
        html = '<button class="z-50">Click</button>'
        patch = make_patch(selector="button", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        # Count occurrences of z-50
        count = result.html.count("z-50")
        assert count == 1

    def test_inject_single(self, injector):
        """Should inject a single patch."""
        html = '<button class="bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-50"])

        result = injector.inject_single(html, patch)

        assert result.success is True
        assert "z-50" in result.html


# ============================================================================
# SELECTOR TESTS
# ============================================================================


class TestSelectors:
    """Tests for CSS selector handling."""

    def test_inject_by_id(self, injector):
        """Should select element by ID."""
        html = '<button id="btn" class="bg-blue-500">Click</button>'
        patch = make_patch(selector="#btn", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert "z-50" in result.html

    def test_inject_by_class(self, injector):
        """Should select element by class."""
        html = '<button class="my-btn bg-blue-500">Click</button>'
        patch = make_patch(selector=".my-btn", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert "z-50" in result.html

    def test_inject_multiple_matches(self, injector):
        """Should apply to all matching elements."""
        html = """
        <button class="btn">One</button>
        <button class="btn">Two</button>
        """
        patch = make_patch(selector=".btn", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        # Both buttons should have z-50
        assert result.html.count("z-50") == 2

    def test_inject_missing_selector(self, injector):
        """Should track failed patches for missing selectors."""
        html = '<button class="bg-blue-500">Click</button>'
        patch = make_patch(selector="#nonexistent", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is False
        assert len(result.failed) == 1
        assert "nonexistent" in result.failed[0][0].selector


# ============================================================================
# Z-INDEX DEDUPLICATION TESTS
# ============================================================================


class TestZIndexDeduplication:
    """Tests for z-index class deduplication."""

    def test_replaces_old_zindex(self, injector):
        """Should remove old z-index when adding new."""
        html = '<button class="z-10 bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert "z-50" in result.html
        assert "z-10" not in result.html

    def test_replaces_arbitrary_zindex(self, injector):
        """Should replace arbitrary z-index values."""
        html = '<button class="z-[100] bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-[200]"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert "z-[200]" in result.html
        assert "z-[100]" not in result.html

    def test_keeps_non_zindex_classes(self, injector):
        """Should not affect non-z-index classes."""
        html = '<button class="z-10 relative bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert "relative" in result.html
        assert "bg-blue-500" in result.html


# ============================================================================
# MULTIPLE PATCHES TESTS
# ============================================================================


class TestMultiplePatches:
    """Tests for applying multiple patches."""

    def test_multiple_patches_different_selectors(self, injector):
        """Should apply patches to different elements."""
        html = """
        <button id="btn1" class="bg-blue-500">One</button>
        <button id="btn2" class="bg-red-500">Two</button>
        """
        patchset = make_patchset([
            make_patch(selector="#btn1", add=["z-50"]),
            make_patch(selector="#btn2", add=["z-40"]),
        ])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert result.applied_count == 2

    def test_multiple_patches_same_selector(self, injector):
        """Should merge patches for same selector."""
        html = '<button id="btn" class="bg-blue-500">Click</button>'
        patchset = PatchSet(source="test")
        patchset.add(make_patch(selector="#btn", add=["z-50"]))
        patchset.add(make_patch(selector="#btn", add=["relative"]))

        result = injector.inject(html, patchset)

        assert result.success is True
        assert "z-50" in result.html
        assert "relative" in result.html


# ============================================================================
# PREVIEW TESTS
# ============================================================================


class TestPreview:
    """Tests for preview_changes method."""

    def test_preview_shows_before_after(self, injector):
        """Should show before and after classes."""
        html = '<button class="z-10 bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-50"], remove=["z-10"])
        patchset = make_patchset([patch])

        preview = injector.preview_changes(html, patchset)

        assert "button" in preview
        assert "z-10" in preview["button"]["before"]
        assert "z-50" in preview["button"]["after"]
        assert "z-10" not in preview["button"]["after"]

    def test_preview_handles_missing_selector(self, injector):
        """Should indicate missing elements in preview."""
        html = '<button class="bg-blue-500">Click</button>'
        patch = make_patch(selector="#missing", add=["z-50"])
        patchset = make_patchset([patch])

        preview = injector.preview_changes(html, patchset)

        assert "#missing" in preview
        assert "error" in preview["#missing"]


# ============================================================================
# EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_patchset(self, injector):
        """Should handle empty patchset."""
        html = '<button class="bg-blue-500">Click</button>'
        patchset = make_patchset([])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert result.html == html

    def test_element_without_class(self, injector):
        """Should add class attribute if not present."""
        html = '<button>Click</button>'
        patch = make_patch(selector="button", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        assert result.success is True
        assert 'class="z-50"' in result.html or "class='z-50'" in result.html

    def test_preserve_formatting_option(self):
        """Should prettify HTML when preserve_formatting=True."""
        injector = TailwindInjector(preserve_formatting=True)
        html = '<button class="bg-blue-500">Click</button>'
        patch = make_patch(selector="button", add=["z-50"])
        patchset = make_patchset([patch])

        result = injector.inject(html, patchset)

        # Prettified HTML has newlines
        assert "\n" in result.html

    def test_repr(self, injector):
        """Should have useful repr."""
        repr_str = repr(injector)

        assert "TailwindInjector" in repr_str
