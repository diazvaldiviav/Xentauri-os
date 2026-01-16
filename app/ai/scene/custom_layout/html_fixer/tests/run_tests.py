#!/usr/bin/env python3
"""
Standalone test runner for html_fixer JavaScript validation tests.

Run this script directly to execute all tests without pytest dependency issues.

Usage:
    cd app/ai/scene/custom_layout
    python html_fixer/tests/run_tests.py
"""

import sys
from pathlib import Path

# Add custom_layout directory to path
custom_layout_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(custom_layout_dir))

from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.validators.js_validator import JSValidator, JSValidationResult
from html_fixer.validators.js_error_classifier import JSErrorClassifier
from html_fixer.contracts.errors import ErrorType


class TestRunner:
    """Simple test runner with assertion helpers."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_true(self, condition, message=""):
        if condition:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"FAIL: {message}")

    def assert_false(self, condition, message=""):
        self.assert_true(not condition, message)

    def assert_in(self, item, collection, message=""):
        self.assert_true(item in collection, message or f"{item} not in {collection}")

    def assert_not_in(self, item, collection, message=""):
        self.assert_true(item not in collection, message or f"{item} should not be in {collection}")

    def assert_equal(self, a, b, message=""):
        self.assert_true(a == b, message or f"{a} != {b}")

    def report(self):
        print(f"\n{'='*60}")
        print(f"Tests passed: {self.passed}")
        print(f"Tests failed: {self.failed}")
        if self.errors:
            print("\nFailures:")
            for err in self.errors:
                print(f"  - {err}")
        print(f"{'='*60}")
        return self.failed == 0


def test_extract_function_definitions(runner: TestRunner):
    """Test extraction of function definitions."""
    print("\n[TEST] Extract function definitions")

    html = """
    <html>
    <head>
        <script>
            function handleClick() {
                console.log('clicked');
            }

            const handleSubmit = function() {
                console.log('submitted');
            };

            const arrowFunc = () => {
                console.log('arrow');
            };

            let asyncFunc = async () => {
                await fetch('/api');
            };
        </script>
    </head>
    <body>
        <button onclick="handleClick()">Click</button>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    runner.assert_in("handleClick", result.defined_functions, "handleClick should be defined")
    runner.assert_in("handleSubmit", result.defined_functions, "handleSubmit should be defined")
    runner.assert_in("arrowFunc", result.defined_functions, "arrowFunc should be defined")
    runner.assert_in("asyncFunc", result.defined_functions, "asyncFunc should be defined")

    print(f"  Defined functions: {result.defined_functions}")


def test_extract_dom_references(runner: TestRunner):
    """Test extraction of DOM references."""
    print("\n[TEST] Extract DOM references")

    html = """
    <html>
    <body>
        <div id="result">Result here</div>
        <script>
            document.getElementById('result').innerText = 'OK';
            document.querySelector('.button').click();
            document.querySelectorAll('input').forEach(i => i.value = '');
            document.getElementsByClassName('item');
        </script>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    methods = [ref["method"] for ref in result.dom_references]
    runner.assert_in("getElementById", methods, "getElementById should be found")
    runner.assert_in("querySelector", methods, "querySelector should be found")
    runner.assert_in("querySelectorAll", methods, "querySelectorAll should be found")
    runner.assert_in("getElementsByClassName", methods, "getElementsByClassName should be found")

    print(f"  DOM references: {result.dom_references}")


def test_detect_missing_function(runner: TestRunner):
    """Test detection of missing function in onclick handler."""
    print("\n[TEST] Detect missing function")

    html = """
    <html>
    <body>
        <button onclick="handleClick()">Click</button>
        <script>
            function otherFunction() {
                console.log('other');
            }
        </script>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    runner.assert_in("handleClick", result.missing_functions, "handleClick should be missing")
    runner.assert_not_in("otherFunction", result.missing_functions, "otherFunction should not be missing")
    runner.assert_true(result.has_errors, "Should have errors")

    print(f"  Missing functions: {result.missing_functions}")


def test_no_missing_function_when_defined(runner: TestRunner):
    """Test no false positives when function is defined."""
    print("\n[TEST] No missing function when defined")

    html = """
    <html>
    <body>
        <button onclick="handleClick()">Click</button>
        <script>
            function handleClick() {
                console.log('clicked');
            }
        </script>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    runner.assert_not_in("handleClick", result.missing_functions, "handleClick should not be missing")
    runner.assert_false(result.has_errors, "Should not have errors")

    print(f"  Has errors: {result.has_errors}")


def test_detect_missing_dom_element(runner: TestRunner):
    """Test detection of missing DOM element referenced by ID."""
    print("\n[TEST] Detect missing DOM element")

    html = """
    <html>
    <body>
        <div id="output">Output here</div>
        <script>
            // 'result' doesn't exist, only 'output' does
            document.getElementById('result').innerText = 'OK';
        </script>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    missing_selectors = [m["selector"] for m in result.missing_dom_elements]
    runner.assert_in("#result", missing_selectors, "#result should be missing")
    runner.assert_true(result.has_errors, "Should have errors")

    print(f"  Missing DOM elements: {result.missing_dom_elements}")


def test_no_missing_dom_when_exists(runner: TestRunner):
    """Test no false positives when DOM element exists."""
    print("\n[TEST] No missing DOM when exists")

    html = """
    <html>
    <body>
        <div id="result">Result here</div>
        <script>
            document.getElementById('result').innerText = 'OK';
        </script>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    runner.assert_equal(len(result.missing_dom_elements), 0, "Should have no missing elements")

    print(f"  Missing DOM elements: {result.missing_dom_elements}")


def test_builtin_functions_not_flagged(runner: TestRunner):
    """Test that built-in functions are not flagged as missing."""
    print("\n[TEST] Built-in functions not flagged")

    html = """
    <html>
    <body>
        <button onclick="alert('Hello')">Alert</button>
        <button onclick="console.log('test')">Log</button>
        <button onclick="setTimeout(fn, 100)">Timeout</button>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    result = validator.validate(parser)

    runner.assert_not_in("alert", result.missing_functions, "alert should not be missing")
    runner.assert_not_in("console", result.missing_functions, "console should not be missing")
    runner.assert_not_in("setTimeout", result.missing_functions, "setTimeout should not be missing")

    print(f"  Missing functions: {result.missing_functions}")


def test_error_type_properties(runner: TestRunner):
    """Test ErrorType properties for JS errors."""
    print("\n[TEST] ErrorType properties")

    runner.assert_true(ErrorType.JS_SYNTAX_ERROR.is_js_related, "JS_SYNTAX_ERROR should be JS related")
    runner.assert_true(ErrorType.JS_MISSING_FUNCTION.is_js_related, "JS_MISSING_FUNCTION should be JS related")
    runner.assert_true(ErrorType.JS_MISSING_DOM_ELEMENT.is_js_related, "JS_MISSING_DOM_ELEMENT should be JS related")
    runner.assert_true(ErrorType.JS_UNDEFINED_VARIABLE.is_js_related, "JS_UNDEFINED_VARIABLE should be JS related")

    runner.assert_false(ErrorType.POINTER_BLOCKED.is_js_related, "POINTER_BLOCKED should not be JS related")
    runner.assert_false(ErrorType.ZINDEX_CONFLICT.is_js_related, "ZINDEX_CONFLICT should not be JS related")

    runner.assert_true(ErrorType.JS_SYNTAX_ERROR.requires_llm, "JS_SYNTAX_ERROR should require LLM")
    runner.assert_true(ErrorType.JS_MISSING_FUNCTION.requires_llm, "JS_MISSING_FUNCTION should require LLM")

    print(f"  JS_MISSING_FUNCTION.is_js_related: {ErrorType.JS_MISSING_FUNCTION.is_js_related}")
    print(f"  JS_MISSING_FUNCTION.requires_llm: {ErrorType.JS_MISSING_FUNCTION.requires_llm}")


def test_classifier(runner: TestRunner):
    """Test JSErrorClassifier."""
    print("\n[TEST] JSErrorClassifier")

    html = """
    <html>
    <body>
        <button onclick="handleClick()">Click</button>
    </body>
    </html>
    """

    parser = DOMParser(html)
    validator = JSValidator()
    classifier = JSErrorClassifier()

    result = validator.validate(parser)
    errors = classifier.classify_static(result)

    runner.assert_equal(len(errors), 1, "Should have 1 error")
    runner.assert_equal(errors[0].error_type, ErrorType.JS_MISSING_FUNCTION, "Should be JS_MISSING_FUNCTION")
    runner.assert_true(errors[0].requires_llm, "Should require LLM")

    print(f"  Classified errors: {len(errors)}")
    print(f"  Error type: {errors[0].error_type}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("HTML Fixer JavaScript Validation Tests (Sprint 3.5)")
    print("=" * 60)

    runner = TestRunner()

    try:
        test_extract_function_definitions(runner)
        test_extract_dom_references(runner)
        test_detect_missing_function(runner)
        test_no_missing_function_when_defined(runner)
        test_detect_missing_dom_element(runner)
        test_no_missing_dom_when_exists(runner)
        test_builtin_functions_not_flagged(runner)
        test_error_type_properties(runner)
        test_classifier(runner)

        success = runner.report()
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
