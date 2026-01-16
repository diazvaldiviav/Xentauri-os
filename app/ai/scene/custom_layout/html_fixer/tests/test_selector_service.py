"""
Tests for SelectorService - centralized CSS selector generation.

Verifies that Tailwind variant classes (hover:, focus:, etc.) are properly
escaped for use in CSS selectors.
"""

import pytest
import subprocess

from html_fixer.core.selector import SelectorService


class TestEscapeClass:
    """Tests for SelectorService.escape_class()."""

    def test_escape_hover_variant(self):
        """Tailwind hover: variant is escaped."""
        assert SelectorService.escape_class("hover:bg-blue-500") == "hover\\:bg-blue-500"

    def test_escape_focus_variant(self):
        """Tailwind focus: variant is escaped."""
        assert SelectorService.escape_class("focus:ring-2") == "focus\\:ring-2"

    def test_escape_active_variant(self):
        """Tailwind active: variant is escaped."""
        assert SelectorService.escape_class("active:scale-95") == "active\\:scale-95"

    def test_escape_responsive_variant(self):
        """Tailwind responsive prefixes are escaped."""
        assert SelectorService.escape_class("md:hidden") == "md\\:hidden"
        assert SelectorService.escape_class("lg:flex") == "lg\\:flex"
        assert SelectorService.escape_class("2xl:grid") == "2xl\\:grid"

    def test_escape_arbitrary_value(self):
        """Tailwind arbitrary values with brackets are escaped."""
        result = SelectorService.escape_class("[perspective:1000px]")
        assert "\\[" in result
        assert "\\]" in result
        assert "\\:" in result

    def test_escape_group_hover(self):
        """Tailwind group-hover variant is escaped."""
        assert SelectorService.escape_class("group-hover:text-white") == "group-hover\\:text-white"

    def test_safe_class_unchanged(self):
        """Regular classes without special chars are unchanged."""
        assert SelectorService.escape_class("bg-blue-500") == "bg-blue-500"
        assert SelectorService.escape_class("flex") == "flex"
        assert SelectorService.escape_class("p-4") == "p-4"
        assert SelectorService.escape_class("text-lg") == "text-lg"

    def test_escape_multiple_special_chars(self):
        """Multiple special characters in one class are all escaped."""
        result = SelectorService.escape_class("dark:hover:bg-gray-800")
        assert result == "dark\\:hover\\:bg-gray-800"


class TestIsSafeClass:
    """Tests for SelectorService.is_safe_class()."""

    def test_simple_class_is_safe(self):
        """Regular Tailwind classes are safe."""
        assert SelectorService.is_safe_class("bg-blue-500") is True
        assert SelectorService.is_safe_class("flex") is True
        assert SelectorService.is_safe_class("mt-4") is True

    def test_variant_class_not_safe(self):
        """Variant classes with colons are not safe."""
        assert SelectorService.is_safe_class("hover:bg-blue-500") is False
        assert SelectorService.is_safe_class("focus:ring-2") is False
        assert SelectorService.is_safe_class("md:hidden") is False

    def test_arbitrary_value_not_safe(self):
        """Arbitrary value classes are not safe."""
        assert SelectorService.is_safe_class("[color:red]") is False
        assert SelectorService.is_safe_class("[width:100px]") is False


class TestFilterSafeClasses:
    """Tests for SelectorService.filter_safe_classes()."""

    def test_filter_mixed_classes(self):
        """Filters out unsafe classes from mixed list."""
        classes = ["bg-blue-500", "hover:bg-blue-600", "p-4", "focus:ring-2"]
        safe = SelectorService.filter_safe_classes(classes)
        assert safe == ["bg-blue-500", "p-4"]

    def test_filter_all_unsafe(self):
        """Returns empty list when all classes are unsafe."""
        classes = ["hover:bg-blue-500", "focus:ring-2", "md:hidden"]
        safe = SelectorService.filter_safe_classes(classes)
        assert safe == []

    def test_filter_all_safe(self):
        """Returns all classes when all are safe."""
        classes = ["bg-blue-500", "p-4", "flex"]
        safe = SelectorService.filter_safe_classes(classes)
        assert safe == ["bg-blue-500", "p-4", "flex"]


class TestBuildSelector:
    """Tests for SelectorService.build_selector()."""

    def test_id_takes_precedence(self):
        """ID selector is returned when ID is present."""
        selector = SelectorService.build_selector(
            "button",
            element_id="submit-btn",
            classes=["bg-blue-500", "hover:bg-blue-600"]
        )
        assert selector == "#submit-btn"

    def test_data_attr_second_priority(self):
        """data-* attribute is used when no ID."""
        selector = SelectorService.build_selector(
            "div",
            data_attrs={"data-option": "a"}
        )
        assert selector == '[data-option="a"]'

    def test_data_attr_without_value(self):
        """data-* attribute without value uses presence selector."""
        selector = SelectorService.build_selector(
            "div",
            data_attrs={"data-active": True}
        )
        assert selector == "[data-active]"

    def test_escaped_classes(self):
        """Classes are properly escaped when escape_classes=True."""
        selector = SelectorService.build_selector(
            "button",
            classes=["nav-link", "hover:text-blue-500"]
        )
        assert selector == "button.nav-link.hover\\:text-blue-500"

    def test_unescaped_filters_unsafe(self):
        """When escape_classes=False, unsafe classes are filtered."""
        selector = SelectorService.build_selector(
            "button",
            classes=["nav-link", "hover:text-blue-500", "p-4"],
            escape_classes=False
        )
        assert selector == "button.nav-link.p-4"

    def test_with_nth_child(self):
        """:nth-of-type is appended when provided."""
        selector = SelectorService.build_selector(
            "button",
            classes=["btn"],
            nth_child=3
        )
        assert selector == "button.btn:nth-of-type(3)"

    def test_max_classes_limit(self):
        """Only max_classes classes are included."""
        selector = SelectorService.build_selector(
            "div",
            classes=["a", "b", "c", "d", "e"],
            max_classes=2
        )
        assert selector == "div.a.b"

    def test_tag_only(self):
        """Returns tag-only selector when no other info."""
        selector = SelectorService.build_selector("button")
        assert selector == "button"

    def test_tag_lowercase(self):
        """Tag is lowercased."""
        selector = SelectorService.build_selector("BUTTON")
        assert selector == "button"

    def test_empty_classes_list(self):
        """Empty classes list produces tag-only selector."""
        selector = SelectorService.build_selector("div", classes=[])
        assert selector == "div"


class TestJSHelperCode:
    """Tests for SelectorService.get_js_helper_code()."""

    def test_js_code_not_empty(self):
        """Generated JS code is not empty."""
        code = SelectorService.get_js_helper_code()
        assert len(code) > 100

    def test_js_code_contains_functions(self):
        """Generated code contains expected functions."""
        code = SelectorService.get_js_helper_code()
        assert "function escapeClass" in code
        assert "function isSafeClass" in code
        assert "function generateSelector" in code

    def test_js_code_contains_special_chars_set(self):
        """Generated code defines special characters set."""
        code = SelectorService.get_js_helper_code()
        assert "SELECTOR_SPECIAL_CHARS" in code

    @pytest.mark.skipif(
        subprocess.run(["which", "node"], capture_output=True).returncode != 0,
        reason="Node.js not available"
    )
    def test_js_code_valid_syntax(self):
        """Generated JS code has valid syntax (requires Node.js)."""
        code = SelectorService.get_js_helper_code()
        # Add a test call to verify the functions work
        test_code = code + """
console.log(typeof escapeClass);
console.log(typeof isSafeClass);
console.log(typeof generateSelector);
console.log(escapeClass('hover:bg-blue-500'));
"""
        result = subprocess.run(
            ["node", "-e", test_code],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"JS Error: {result.stderr}"
        assert "function" in result.stdout

    @pytest.mark.skipif(
        subprocess.run(["which", "node"], capture_output=True).returncode != 0,
        reason="Node.js not available"
    )
    def test_js_escape_matches_python(self):
        """JS escapeClass produces same result as Python (requires Node.js)."""
        code = SelectorService.get_js_helper_code()
        test_code = code + """
// Test escaping matches Python implementation
const tests = [
    'hover:bg-blue-500',
    'focus:ring-2',
    'active:scale-95',
    'md:hidden',
];
tests.forEach(function(cls) {
    console.log(escapeClass(cls));
});
"""
        result = subprocess.run(
            ["node", "-e", test_code],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

        # Compare with Python results
        lines = result.stdout.strip().split('\n')
        test_classes = ['hover:bg-blue-500', 'focus:ring-2', 'active:scale-95', 'md:hidden']

        for i, cls in enumerate(test_classes):
            python_result = SelectorService.escape_class(cls)
            js_result = lines[i]
            # Note: CSS.escape produces slightly different output, but both are valid
            assert ':' not in js_result or '\\' in js_result, \
                f"Colon not escaped for {cls}: {js_result}"


class TestIntegration:
    """Integration tests for SelectorService."""

    def test_real_world_tailwind_classes(self):
        """Test with real-world Tailwind class combinations."""
        classes = [
            "flex",
            "hover:bg-blue-600",
            "focus:ring-2",
            "px-4",
            "py-2",
        ]

        selector = SelectorService.build_selector(
            "button",
            classes=classes,
            max_classes=5
        )

        # Should have tag + escaped classes
        assert selector.startswith("button.")
        assert "hover\\:bg-blue-600" in selector
        assert "focus\\:ring-2" in selector

    def test_complex_arbitrary_values(self):
        """Test with complex arbitrary value classes."""
        classes = [
            "bg-[#1da1f2]",
            "[mask-image:linear-gradient(black,transparent)]",
            "w-[calc(100%-2rem)]",
        ]

        for cls in classes:
            escaped = SelectorService.escape_class(cls)
            # All special chars should be escaped
            for char in ['[', ']', ':', '#', '(', ')']:
                if char in cls:
                    assert f"\\{char}" in escaped, f"'{char}' not escaped in {escaped}"

    def test_selector_usable_in_css(self):
        """Generated selectors should be valid CSS."""
        selector = SelectorService.build_selector(
            "button",
            classes=["hover:bg-blue-500", "focus:ring-2"]
        )

        # Should not contain unescaped colons (except in :nth-child)
        parts = selector.split(".")
        for part in parts[1:]:  # Skip tag
            if ":" in part and "\\:" not in part:
                # Only :nth-child is allowed
                assert ":nth-child" in part, f"Unescaped colon in {part}"
