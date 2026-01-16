"""
SelectorService - Centralized CSS selector generation.

Handles Tailwind variant classes (hover:, focus:, etc.) and other special
characters that require escaping in CSS selectors.

Usage:
    from ..core.selector import SelectorService

    # Python-side
    selector = SelectorService.build_selector("button", classes=["hover:bg-blue-500"])
    # Returns: "button.hover\\:bg-blue-500"

    # JavaScript-side (inject helper code)
    js_helper = SelectorService.get_js_helper_code()
"""

from typing import List, Optional, Dict, Any


class SelectorService:
    """
    Centralized service for generating valid CSS selectors.

    Handles:
    - Tailwind variant classes with colons (hover:, focus:, sm:, etc.)
    - Arbitrary value classes with brackets ([perspective:1000px])
    - Other special CSS characters that need escaping
    """

    # Characters that need escaping in CSS selectors
    # CSS.escape() specification: https://drafts.csswg.org/cssom/#the-css.escape()-method
    SPECIAL_CHARS = frozenset(":[]()/\\@#!$%^&*+={}'\"<>,")

    @classmethod
    def escape_class(cls, class_name: str) -> str:
        """
        Escape a CSS class name for use in a selector.

        Examples:
            "hover:bg-blue-500" -> "hover\\:bg-blue-500"
            "[perspective:1000px]" -> "\\[perspective\\:1000px\\]"

        Args:
            class_name: Raw CSS class name

        Returns:
            Escaped class name safe for CSS selectors
        """
        result = []
        for char in class_name:
            if char in cls.SPECIAL_CHARS:
                result.append(f"\\{char}")
            else:
                result.append(char)
        return "".join(result)

    @classmethod
    def is_safe_class(cls, class_name: str) -> bool:
        """
        Check if a class name is safe to use without escaping.

        Args:
            class_name: CSS class name to check

        Returns:
            True if class contains no special characters
        """
        return not any(c in cls.SPECIAL_CHARS for c in class_name)

    @classmethod
    def filter_safe_classes(cls, classes: List[str]) -> List[str]:
        """
        Filter classes to only those safe for unescaped use.

        Useful when you want simple selectors without escaping.

        Args:
            classes: List of class names

        Returns:
            Only classes without special characters
        """
        return [c for c in classes if cls.is_safe_class(c)]

    @classmethod
    def build_selector(
        cls,
        tag: str,
        element_id: Optional[str] = None,
        classes: Optional[List[str]] = None,
        nth_child: Optional[int] = None,
        data_attrs: Optional[Dict[str, Any]] = None,
        escape_classes: bool = True,
        max_classes: int = 3,
    ) -> str:
        """
        Build a CSS selector from components.

        Priority order:
        1. ID (if present, returns immediately)
        2. data-* attribute (if present)
        3. tag + escaped classes + nth-child

        Args:
            tag: HTML tag name
            element_id: ID attribute (optional)
            classes: List of class names (optional)
            nth_child: nth-child index, 1-based (optional)
            data_attrs: Dict of data-* attributes (optional)
            escape_classes: Whether to escape special chars in classes
            max_classes: Maximum number of classes to include

        Returns:
            Valid CSS selector string
        """
        # ID is always unique and safe
        if element_id:
            return f"#{element_id}"

        # Try data-* attributes
        if data_attrs:
            for attr, value in data_attrs.items():
                if attr.startswith("data-"):
                    if value and value is not True:
                        return f'[{attr}="{value}"]'
                    return f"[{attr}]"

        # Build tag + classes selector
        selector = tag.lower()

        if classes:
            if escape_classes:
                # Escape all classes
                safe_classes = [cls.escape_class(c) for c in classes[:max_classes]]
            else:
                # Filter to safe classes only
                safe_classes = cls.filter_safe_classes(classes)[:max_classes]

            if safe_classes:
                selector += "." + ".".join(safe_classes)

        # Add nth-of-type for uniqueness
        # NOTE: Our callers compute the index among siblings of the same tag,
        # so the correct pseudo-class is :nth-of-type(), not :nth-child().
        if nth_child is not None:
            selector += f":nth-of-type({nth_child})"

        return selector

    @classmethod
    def get_js_helper_code(cls) -> str:
        """
        Generate JavaScript helper code for selector generation.

        This code should be injected into page.evaluate() calls.
        Provides a `generateSelector(element)` function.

        Returns:
            JavaScript code string defining helper functions
        """
        return '''
// SelectorService helpers (generated from Python)
const SELECTOR_SPECIAL_CHARS = new Set([':', '[', ']', '(', ')', '/', '\\\\', '@', '#', '!', '$', '%', '^', '&', '*', '+', '=', '{', '}', "'", '"', '<', '>', ',']);

function escapeClass(className) {
    // Use CSS.escape if available (modern browsers)
    if (typeof CSS !== 'undefined' && CSS.escape) {
        return CSS.escape(className);
    }
    // Fallback: manual escaping
    let result = '';
    for (const char of className) {
        if (SELECTOR_SPECIAL_CHARS.has(char)) {
            result += '\\\\' + char;
        } else {
            result += char;
        }
    }
    return result;
}

function isSafeClass(className) {
    for (const char of className) {
        if (SELECTOR_SPECIAL_CHARS.has(char)) return false;
    }
    return true;
}

function generateSelector(element, options) {
    options = options || {};
    const escapeClasses = options.escapeClasses !== false;
    const maxClasses = options.maxClasses || 3;

    // ID is unique and safe
    if (element.id) {
        return '#' + element.id;
    }

    // Try data-* attributes
    for (let i = 0; i < element.attributes.length; i++) {
        const attr = element.attributes[i];
        if (attr.name.startsWith('data-')) {
            if (attr.value) {
                return '[' + attr.name + '="' + attr.value + '"]';
            }
            return '[' + attr.name + ']';
        }
    }

    // Build tag + classes selector
    let selector = element.tagName.toLowerCase();

    // NOTE: For SVG elements, `className` may be an SVGAnimatedString.
    let className = '';
    if (typeof element.className === 'string') {
        className = element.className;
    } else if (element.className && typeof element.className.baseVal === 'string') {
        className = element.className.baseVal;
    }

    if (className) {
        const classes = className.trim().split(/\\s+/).filter(function(c) { return c; });
        if (classes.length > 0) {
            let selectorClasses;
            if (escapeClasses) {
                selectorClasses = classes.slice(0, maxClasses).map(escapeClass);
            } else {
                selectorClasses = classes.filter(isSafeClass).slice(0, maxClasses);
            }
            if (selectorClasses.length > 0) {
                selector += '.' + selectorClasses.join('.');
            }
        }
    }

    // Add nth-child for uniqueness
    if (element.parentElement) {
        const siblings = Array.from(element.parentElement.children)
            .filter(function(el) { return el.tagName === element.tagName; });
        if (siblings.length > 1) {
            const index = siblings.indexOf(element) + 1;
            selector += ':nth-of-type(' + index + ')';
        }
    }

    return selector;
}
'''
