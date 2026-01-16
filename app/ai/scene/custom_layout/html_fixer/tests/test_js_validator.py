"""
Tests for JavaScript validation (Sprint 3.5).

Tests the static JavaScript validation capabilities:
- Function extraction
- DOM reference extraction
- Missing function detection
- Missing DOM element detection
"""

import pytest
from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.validators.js_validator import JSValidator, JSValidationResult, ScriptInfo
from html_fixer.validators.js_error_classifier import JSErrorClassifier
from html_fixer.contracts.errors import ErrorType


class TestJSValidator:
    """Tests for JSValidator static analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = JSValidator()

    def test_extract_function_definitions(self):
        """Test extraction of function definitions."""
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
        result = self.validator.validate(parser)

        assert "handleClick" in result.defined_functions
        assert "handleSubmit" in result.defined_functions
        assert "arrowFunc" in result.defined_functions
        assert "asyncFunc" in result.defined_functions

    def test_extract_dom_references(self):
        """Test extraction of DOM references."""
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
        result = self.validator.validate(parser)

        methods = [ref["method"] for ref in result.dom_references]
        assert "getElementById" in methods
        assert "querySelector" in methods
        assert "querySelectorAll" in methods
        assert "getElementsByClassName" in methods

    def test_detect_missing_function(self):
        """Test detection of missing function in onclick handler."""
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
        result = self.validator.validate(parser)

        assert "handleClick" in result.missing_functions
        assert "otherFunction" not in result.missing_functions

    def test_no_missing_function_when_defined(self):
        """Test no false positives when function is defined."""
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
        result = self.validator.validate(parser)

        assert "handleClick" not in result.missing_functions
        assert result.has_errors is False

    def test_detect_missing_dom_element_by_id(self):
        """Test detection of missing DOM element referenced by ID."""
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
        result = self.validator.validate(parser)

        missing_selectors = [m["selector"] for m in result.missing_dom_elements]
        assert "#result" in missing_selectors

    def test_no_missing_dom_when_exists(self):
        """Test no false positives when DOM element exists."""
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
        result = self.validator.validate(parser)

        assert len(result.missing_dom_elements) == 0

    def test_builtin_functions_not_flagged(self):
        """Test that built-in functions are not flagged as missing."""
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
        result = self.validator.validate(parser)

        assert "alert" not in result.missing_functions
        assert "console" not in result.missing_functions
        assert "setTimeout" not in result.missing_functions

    def test_multiple_script_blocks(self):
        """Test extraction across multiple script blocks."""
        html = """
        <html>
        <head>
            <script>
                function func1() { return 1; }
            </script>
        </head>
        <body>
            <button onclick="func1()">1</button>
            <button onclick="func2()">2</button>
            <script>
                function func2() { return 2; }
            </script>
        </body>
        </html>
        """
        parser = DOMParser(html)
        result = self.validator.validate(parser)

        assert "func1" in result.defined_functions
        assert "func2" in result.defined_functions
        assert len(result.missing_functions) == 0

    def test_external_scripts_skipped(self):
        """Test that external scripts are not analyzed for content."""
        html = """
        <html>
        <head>
            <script src="https://cdn.example.com/lib.js"></script>
        </head>
        <body>
            <button onclick="handleClick()">Click</button>
        </body>
        </html>
        """
        parser = DOMParser(html)
        result = self.validator.validate(parser)

        # External script found
        external_scripts = [s for s in result.scripts if s.is_external]
        assert len(external_scripts) == 1

        # handleClick is missing (not defined in any inline script)
        assert "handleClick" in result.missing_functions

    def test_empty_html_no_errors(self):
        """Test that empty HTML doesn't cause errors."""
        html = "<html><body></body></html>"
        parser = DOMParser(html)
        result = self.validator.validate(parser)

        assert len(result.scripts) == 0
        assert len(result.missing_functions) == 0
        assert len(result.missing_dom_elements) == 0


class TestJSErrorClassifier:
    """Tests for JSErrorClassifier."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = JSValidator()
        self.classifier = JSErrorClassifier()

    def test_classify_missing_function(self):
        """Test classification of missing function errors."""
        html = """
        <html>
        <body>
            <button onclick="handleClick()">Click</button>
        </body>
        </html>
        """
        parser = DOMParser(html)
        result = self.validator.validate(parser)
        errors = self.classifier.classify_static(result)

        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.JS_MISSING_FUNCTION
        assert errors[0].requires_llm is True

    def test_classify_missing_dom_element(self):
        """Test classification of missing DOM element errors."""
        html = """
        <html>
        <body>
            <script>
                document.getElementById('nonexistent').click();
            </script>
        </body>
        </html>
        """
        parser = DOMParser(html)
        result = self.validator.validate(parser)
        errors = self.classifier.classify_static(result)

        dom_errors = [e for e in errors if e.error_type == ErrorType.JS_MISSING_DOM_ELEMENT]
        assert len(dom_errors) == 1
        assert dom_errors[0].requires_llm is True

    def test_no_errors_when_valid(self):
        """Test no errors are generated for valid JS."""
        html = """
        <html>
        <body>
            <div id="result">Result</div>
            <button onclick="handleClick()">Click</button>
            <script>
                function handleClick() {
                    document.getElementById('result').innerText = 'Clicked!';
                }
            </script>
        </body>
        </html>
        """
        parser = DOMParser(html)
        result = self.validator.validate(parser)
        errors = self.classifier.classify_static(result)

        assert len(errors) == 0


class TestErrorTypesJS:
    """Tests for JavaScript ErrorType properties."""

    def test_js_error_types_exist(self):
        """Test that JS error types are defined."""
        assert hasattr(ErrorType, "JS_SYNTAX_ERROR")
        assert hasattr(ErrorType, "JS_MISSING_FUNCTION")
        assert hasattr(ErrorType, "JS_MISSING_DOM_ELEMENT")
        assert hasattr(ErrorType, "JS_UNDEFINED_VARIABLE")

    def test_is_js_related(self):
        """Test is_js_related property."""
        assert ErrorType.JS_SYNTAX_ERROR.is_js_related is True
        assert ErrorType.JS_MISSING_FUNCTION.is_js_related is True
        assert ErrorType.JS_MISSING_DOM_ELEMENT.is_js_related is True
        assert ErrorType.JS_UNDEFINED_VARIABLE.is_js_related is True

        # CSS errors should not be JS related
        assert ErrorType.POINTER_BLOCKED.is_js_related is False
        assert ErrorType.ZINDEX_CONFLICT.is_js_related is False

    def test_requires_llm(self):
        """Test that JS errors require LLM."""
        assert ErrorType.JS_SYNTAX_ERROR.requires_llm is True
        assert ErrorType.JS_MISSING_FUNCTION.requires_llm is True
        assert ErrorType.JS_MISSING_DOM_ELEMENT.requires_llm is True
        assert ErrorType.JS_UNDEFINED_VARIABLE.requires_llm is True


# Fixtures for testing with real HTML examples

HTML_MISSING_FUNCTION = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="p-8">
    <button onclick="handleSelection(1)" class="bg-blue-500 text-white p-4 rounded">
        Option 1
    </button>
    <button onclick="handleSelection(2)" class="bg-blue-500 text-white p-4 rounded">
        Option 2
    </button>

    <div id="result" class="mt-4 p-4 bg-gray-100"></div>

    <script>
        // handleSelection is NOT defined!
        // Only this function exists:
        function showResult(text) {
            document.getElementById('result').innerText = text;
        }
    </script>
</body>
</html>
"""

HTML_MISSING_DOM_ELEMENT = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="p-8">
    <button onclick="handleClick()" class="bg-green-500 text-white p-4 rounded">
        Click Me
    </button>

    <!-- Note: 'result' div does NOT exist, only 'output' -->
    <div id="output" class="mt-4 p-4 bg-gray-100"></div>

    <script>
        function handleClick() {
            // ERROR: 'result' doesn't exist, should be 'output'
            document.getElementById('result').innerText = 'Clicked!';
        }
    </script>
</body>
</html>
"""

HTML_VALID_JS = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="p-8">
    <button onclick="handleClick()" class="bg-blue-500 text-white p-4 rounded">
        Click Me
    </button>

    <div id="result" class="mt-4 p-4 bg-gray-100"></div>

    <script>
        function handleClick() {
            document.getElementById('result').innerText = 'Clicked!';
        }
    </script>
</body>
</html>
"""


class TestFixtureValidation:
    """Tests using fixture HTML examples."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = JSValidator()
        self.classifier = JSErrorClassifier()

    def test_fixture_missing_function(self):
        """Test the missing function fixture."""
        parser = DOMParser(HTML_MISSING_FUNCTION)
        result = self.validator.validate(parser)

        assert "handleSelection" in result.missing_functions
        assert "showResult" in result.defined_functions

    def test_fixture_missing_dom(self):
        """Test the missing DOM element fixture."""
        parser = DOMParser(HTML_MISSING_DOM_ELEMENT)
        result = self.validator.validate(parser)

        missing_ids = [
            m["argument"]
            for m in result.missing_dom_elements
            if m["method"] == "getElementById"
        ]
        assert "result" in missing_ids

    def test_fixture_valid_js(self):
        """Test the valid JS fixture."""
        parser = DOMParser(HTML_VALID_JS)
        result = self.validator.validate(parser)

        assert len(result.missing_functions) == 0
        assert len(result.missing_dom_elements) == 0
        assert result.has_errors is False
