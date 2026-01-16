"""
JavaScript Validator - Static analysis of JavaScript in HTML.

Validates:
1. Extracts all <script> tags and inline handlers
2. Detects function definitions
3. Identifies DOM element references (getElementById, querySelector, etc.)
4. Cross-references called functions with defined functions
5. Validates DOM references against actual elements

Usage:
    from app.ai.scene.custom_layout.html_fixer.validators import JSValidator
    from app.ai.scene.custom_layout.html_fixer.analyzers import DOMParser

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    for fn in result.missing_functions:
        print(f"Missing function: {fn}")
"""

import re
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional

from bs4 import Tag

from ..analyzers.dom_parser import DOMParser
from ..analyzers.event_mapper import EventMapper


@dataclass
class ScriptInfo:
    """Information about a <script> tag."""

    element: Tag
    """The script element."""

    content: str
    """JavaScript content (empty if external)."""

    line_number: Optional[int]
    """Line number in source HTML."""

    is_external: bool
    """True if script has src attribute."""

    src: Optional[str] = None
    """URL if external script."""

    defined_functions: Set[str] = field(default_factory=set)
    """Functions defined in this script."""

    dom_references: List[Dict[str, str]] = field(default_factory=list)
    """DOM references found (getElementById, querySelector, etc.)."""


@dataclass
class JSValidationResult:
    """Result of JavaScript validation."""

    scripts: List[ScriptInfo]
    """All script tags found."""

    defined_functions: Set[str]
    """All functions defined across all scripts."""

    called_functions: Set[str]
    """All functions called from event handlers."""

    dom_references: List[Dict[str, str]]
    """All DOM references found."""

    missing_functions: List[str]
    """Functions called but not defined."""

    missing_dom_elements: List[Dict[str, str]]
    """DOM references that don't match any element."""

    has_errors: bool = False
    """True if any errors were found."""


class JSValidator:
    """
    Static JavaScript validator for HTML documents.

    Performs static analysis to detect:
    - Missing function definitions
    - Invalid DOM references
    - Unreachable element lookups
    """

    # Patterns for function definitions
    FUNCTION_PATTERNS = [
        # function name()
        re.compile(r"function\s+(\w+)\s*\("),
        # const/let/var name = function
        re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*function\s*\("),
        # const/let/var name = () =>
        re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
        # const/let/var name = async function
        re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*async\s+function\s*\("),
        # name: function (object method)
        re.compile(r"^\s*(\w+)\s*:\s*function\s*\(", re.MULTILINE),
        # name() { (shorthand method)
        re.compile(r"^\s*(\w+)\s*\([^)]*\)\s*{", re.MULTILINE),
    ]

    # Patterns for DOM element access
    DOM_ACCESS_PATTERNS = [
        (
            re.compile(r"getElementById\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            "getElementById",
            "id",
        ),
        (
            re.compile(r"querySelector\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            "querySelector",
            "selector",
        ),
        (
            re.compile(r"querySelectorAll\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            "querySelectorAll",
            "selector",
        ),
        (
            re.compile(r"getElementsByClassName\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            "getElementsByClassName",
            "class",
        ),
        (
            re.compile(r"getElementsByTagName\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            "getElementsByTagName",
            "tag",
        ),
        # jQuery-style selector
        (
            re.compile(r"\$\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            "jQuery",
            "selector",
        ),
    ]

    # Built-in functions that are always available
    BUILTIN_FUNCTIONS = {
        # Browser APIs
        "alert",
        "confirm",
        "prompt",
        "console",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "requestAnimationFrame",
        "cancelAnimationFrame",
        "fetch",
        "eval",
        # Type constructors
        "parseInt",
        "parseFloat",
        "isNaN",
        "isFinite",
        "Number",
        "String",
        "Boolean",
        "Array",
        "Object",
        "Date",
        "RegExp",
        "Error",
        "Promise",
        "Map",
        "Set",
        "JSON",
        "Math",
        # DOM
        "document",
        "window",
        "location",
        "history",
        "navigator",
        "localStorage",
        "sessionStorage",
        # Event helpers
        "event",
        "this",
    }

    def __init__(self):
        """Initialize the JavaScript validator."""
        self._event_mapper = EventMapper()

    def validate(self, parser: DOMParser) -> JSValidationResult:
        """
        Validate all JavaScript in the HTML document.

        Args:
            parser: DOMParser instance with loaded HTML

        Returns:
            JSValidationResult with all findings
        """
        # Extract all scripts
        scripts = self._extract_scripts(parser)

        # Collect all defined functions
        defined_functions: Set[str] = set()
        for script in scripts:
            defined_functions.update(script.defined_functions)

        # Get all called functions from event handlers
        events = self._event_mapper.map_events(parser)
        called_functions = self._event_mapper.get_unique_functions(events)

        # Collect all DOM references
        all_dom_refs: List[Dict[str, str]] = []
        for script in scripts:
            all_dom_refs.extend(script.dom_references)

        # Find missing functions (called but not defined)
        available_functions = defined_functions | self.BUILTIN_FUNCTIONS
        missing_functions = [
            fn for fn in called_functions if fn not in available_functions
        ]

        # Find missing DOM elements
        missing_dom = self._find_missing_dom_elements(parser, all_dom_refs)

        has_errors = len(missing_functions) > 0 or len(missing_dom) > 0

        return JSValidationResult(
            scripts=scripts,
            defined_functions=defined_functions,
            called_functions=called_functions,
            dom_references=all_dom_refs,
            missing_functions=missing_functions,
            missing_dom_elements=missing_dom,
            has_errors=has_errors,
        )

    def _extract_scripts(self, parser: DOMParser) -> List[ScriptInfo]:
        """Extract all <script> tags and analyze their content."""
        scripts = []

        for script_tag in parser.get_elements_by_tag("script"):
            src = script_tag.get("src")
            is_external = src is not None
            content = script_tag.string or ""

            script_info = ScriptInfo(
                element=script_tag,
                content=content.strip() if content else "",
                line_number=parser.get_source_line(script_tag),
                is_external=is_external,
                src=src,
            )

            # Only analyze inline scripts
            if not is_external and content:
                script_info.defined_functions = self._extract_defined_functions(content)
                script_info.dom_references = self._extract_dom_references(content)

            scripts.append(script_info)

        return scripts

    def _extract_defined_functions(self, js_content: str) -> Set[str]:
        """
        Extract function names defined in JavaScript code.

        Args:
            js_content: JavaScript code to analyze

        Returns:
            Set of function names
        """
        functions: Set[str] = set()

        for pattern in self.FUNCTION_PATTERNS:
            for match in pattern.finditer(js_content):
                fn_name = match.group(1)
                # Filter out keywords that match patterns
                if fn_name not in ("if", "for", "while", "switch", "catch", "return"):
                    functions.add(fn_name)

        return functions

    def _extract_dom_references(self, js_content: str) -> List[Dict[str, str]]:
        """
        Extract DOM element references from JavaScript code.

        Args:
            js_content: JavaScript code to analyze

        Returns:
            List of dicts with method, argument, and type info
        """
        references: List[Dict[str, str]] = []

        for pattern, method, ref_type in self.DOM_ACCESS_PATTERNS:
            for match in pattern.finditer(js_content):
                selector = match.group(1)
                references.append(
                    {
                        "method": method,
                        "argument": selector,
                        "type": ref_type,
                    }
                )

        return references

    def _find_missing_dom_elements(
        self, parser: DOMParser, dom_references: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Find DOM references that don't match any element in the HTML.

        Args:
            parser: DOMParser with loaded HTML
            dom_references: List of DOM references to check

        Returns:
            List of references that don't have matching elements
        """
        missing: List[Dict[str, str]] = []

        for ref in dom_references:
            method = ref["method"]
            arg = ref["argument"]
            ref_type = ref["type"]

            element_found = False

            if method == "getElementById":
                element_found = parser.get_element_by_id(arg) is not None

            elif method in ("querySelector", "querySelectorAll", "jQuery"):
                try:
                    # Handle jQuery selectors that start with special chars
                    if arg.startswith("#"):
                        # ID selector
                        element_found = parser.get_element_by_id(arg[1:]) is not None
                    elif arg.startswith("."):
                        # Class selector
                        elements = parser.get_elements_by_selector(arg)
                        element_found = len(elements) > 0
                    else:
                        # General selector
                        element_found = parser.get_element_by_selector(arg) is not None
                except Exception:
                    # Invalid selector
                    element_found = False

            elif method == "getElementsByClassName":
                elements = parser.get_elements_by_selector(f".{arg}")
                element_found = len(elements) > 0

            elif method == "getElementsByTagName":
                elements = parser.get_elements_by_tag(arg)
                element_found = len(elements) > 0

            if not element_found:
                missing.append(
                    {
                        "method": method,
                        "argument": arg,
                        "type": ref_type,
                        "selector": (
                            f"#{arg}"
                            if ref_type == "id"
                            else f".{arg}" if ref_type == "class" else arg
                        ),
                    }
                )

        return missing

    def get_defined_functions(self, parser: DOMParser) -> Set[str]:
        """
        Quick method to get all defined functions.

        Args:
            parser: DOMParser instance

        Returns:
            Set of function names
        """
        result = self.validate(parser)
        return result.defined_functions

    def get_called_functions(self, parser: DOMParser) -> Set[str]:
        """
        Quick method to get all functions called from handlers.

        Args:
            parser: DOMParser instance

        Returns:
            Set of function names
        """
        events = self._event_mapper.map_events(parser)
        return self._event_mapper.get_unique_functions(events)

    def __repr__(self) -> str:
        """String representation."""
        return "JSValidator()"
