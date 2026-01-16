"""
Tests for Patch Validators (Sprint 6).

Tests validation of Tailwind and JavaScript patches.
"""

import pytest
from html_fixer.fixers.llm.validators import (
    PatchValidator,
    TailwindPatchValidator,
    JSPatchValidator,
)
from html_fixer.contracts.patches import TailwindPatch
from html_fixer.fixers.llm.contracts import JSPatch, JSPatchType


class TestTailwindPatchValidator:
    """Tests for TailwindPatchValidator."""

    def test_validates_valid_patch(self):
        """Test validation of a valid patch."""
        validator = TailwindPatchValidator()
        html = '<button class="btn">Click</button>'

        patch = TailwindPatch(
            selector=".btn",
            add_classes=["hover:bg-blue-600", "active:scale-95", "transition-all"],
            remove_classes=[],
        )

        assert validator.validate(patch, html) is True

    def test_rejects_invalid_selector(self):
        """Test rejection of patches with non-existent selectors."""
        validator = TailwindPatchValidator()
        html = '<button class="btn">Click</button>'

        patch = TailwindPatch(
            selector=".nonexistent",
            add_classes=["hover:bg-blue-600"],
            remove_classes=[],
        )

        assert validator.validate(patch, html) is False

    def test_validates_standard_tailwind_classes(self):
        """Test validation of standard Tailwind classes."""
        validator = TailwindPatchValidator()
        html = '<button class="btn">Click</button>'

        # Valid classes
        valid_patches = [
            TailwindPatch(".btn", ["z-50"], []),
            TailwindPatch(".btn", ["hover:bg-blue-600"], []),
            TailwindPatch(".btn", ["active:scale-95"], []),
            TailwindPatch(".btn", ["transition-all"], []),
            TailwindPatch(".btn", ["duration-150"], []),
            TailwindPatch(".btn", ["shadow-lg"], []),
            TailwindPatch(".btn", ["opacity-50"], []),
        ]

        for patch in valid_patches:
            assert validator.validate(patch, html) is True, f"Failed for {patch.add_classes}"

    def test_allows_arbitrary_values(self):
        """Test that arbitrary values like [color:#fff] are allowed."""
        validator = TailwindPatchValidator()
        html = '<button class="btn">Click</button>'

        patch = TailwindPatch(
            selector=".btn",
            add_classes=["[transform:scale(1.1)]", "[color:#ff0000]"],
            remove_classes=[],
        )

        assert validator.validate(patch, html) is True

    def test_rejects_forbidden_on_interactive(self):
        """Test rejection of forbidden classes on interactive elements."""
        validator = TailwindPatchValidator()
        html = '<button class="btn" onclick="test()">Click</button>'

        # These should be rejected on interactive elements
        forbidden_patches = [
            TailwindPatch(".btn", ["hidden"], []),
            TailwindPatch(".btn", ["invisible"], []),
            TailwindPatch(".btn", ["opacity-0"], []),
            TailwindPatch(".btn", ["pointer-events-none"], []),
        ]

        for patch in forbidden_patches:
            assert validator.validate(patch, html) is False, f"Should reject {patch.add_classes}"

    def test_validates_state_variants(self):
        """Test validation of state variant classes."""
        validator = TailwindPatchValidator()
        html = '<button class="btn">Click</button>'

        variants = [
            "hover:bg-blue-600",
            "active:scale-95",
            "focus:ring-2",
            "disabled:opacity-50",
            "group-hover:text-white",
        ]

        for variant in variants:
            patch = TailwindPatch(".btn", [variant], [])
            assert validator.validate(patch, html) is True, f"Failed for {variant}"

    def test_batch_validation(self):
        """Test batch validation filters invalid patches."""
        validator = TailwindPatchValidator()
        html = '<button class="btn">Click</button>'

        patches = [
            TailwindPatch(".btn", ["hover:bg-blue-600"], []),  # Valid
            TailwindPatch(".nonexistent", ["hover:bg-red-600"], []),  # Invalid selector
            TailwindPatch(".btn", ["active:scale-95"], []),  # Valid
        ]

        valid = validator.validate_batch(patches, html)

        assert len(valid) == 2
        assert all(p.selector == ".btn" for p in valid)


class TestJSPatchValidator:
    """Tests for JSPatchValidator."""

    def test_validates_add_function(self):
        """Test validation of ADD_FUNCTION patch."""
        validator = JSPatchValidator()
        html = '<button onclick="test()">Click</button>'

        patch = JSPatch(
            patch_type=JSPatchType.ADD_FUNCTION,
            function_name="test",
            function_code="function test() { console.log('test'); }",
        )

        assert validator.validate(patch, html) is True

    def test_rejects_add_function_without_name(self):
        """Test rejection of ADD_FUNCTION without function_name."""
        validator = JSPatchValidator()
        html = '<button>Click</button>'

        patch = JSPatch(
            patch_type=JSPatchType.ADD_FUNCTION,
            function_code="function test() {}",
        )

        assert validator.validate(patch, html) is False

    def test_rejects_add_function_without_code(self):
        """Test rejection of ADD_FUNCTION without function_code."""
        validator = JSPatchValidator()
        html = '<button>Click</button>'

        patch = JSPatch(
            patch_type=JSPatchType.ADD_FUNCTION,
            function_name="test",
        )

        assert validator.validate(patch, html) is False

    def test_validates_function_code_syntax(self):
        """Test validation of function code syntax."""
        validator = JSPatchValidator()
        html = '<button>Click</button>'

        # Valid function codes
        valid_codes = [
            "function test() { return 1; }",
            "const test = function() { return 1; }",
            "const test = () => { return 1; }",
            "async function test() { return await fetch('/'); }",
        ]

        for code in valid_codes:
            patch = JSPatch(
                patch_type=JSPatchType.ADD_FUNCTION,
                function_name="test",
                function_code=code,
            )
            assert validator.validate(patch, html) is True, f"Failed for: {code}"

    def test_rejects_unbalanced_braces(self):
        """Test rejection of code with unbalanced braces."""
        validator = JSPatchValidator()
        html = '<button>Click</button>'

        patch = JSPatch(
            patch_type=JSPatchType.ADD_FUNCTION,
            function_name="test",
            function_code="function test() { return 1; ",  # Missing closing brace
        )

        assert validator.validate(patch, html) is False

    def test_validates_dom_reference_exists(self):
        """Test that new DOM references exist in HTML."""
        validator = JSPatchValidator()
        html = '<div id="output">Result</div>'

        # Valid: new reference exists
        valid_patch = JSPatch(
            patch_type=JSPatchType.FIX_DOM_REFERENCE,
            old_reference="result",
            new_reference="output",
        )
        assert validator.validate(valid_patch, html) is True

        # Invalid: new reference doesn't exist
        invalid_patch = JSPatch(
            patch_type=JSPatchType.FIX_DOM_REFERENCE,
            old_reference="result",
            new_reference="nonexistent",
        )
        assert validator.validate(invalid_patch, html) is False

    def test_validates_fix_syntax(self):
        """Test validation of FIX_SYNTAX patch."""
        validator = JSPatchValidator()
        html = '<script>let x = 1;</script>'

        # Valid
        valid_patch = JSPatch(
            patch_type=JSPatchType.FIX_SYNTAX,
            script_index=0,
            line_start=1,
            replacement_code="const x = 1;",
        )
        assert validator.validate(valid_patch, html) is True

        # Invalid: missing script_index
        invalid_patch = JSPatch(
            patch_type=JSPatchType.FIX_SYNTAX,
            line_start=1,
            replacement_code="const x = 1;",
        )
        assert validator.validate(invalid_patch, html) is False

    def test_validates_modify_handler(self):
        """Test validation of MODIFY_HANDLER patch."""
        validator = JSPatchValidator()
        html = '<button class="btn" onclick="old()">Click</button>'

        # Valid: selector exists
        valid_patch = JSPatch(
            patch_type=JSPatchType.MODIFY_HANDLER,
            selector=".btn",
            new_handler="newHandler()",
        )
        assert validator.validate(valid_patch, html) is True

        # Invalid: selector doesn't exist
        invalid_patch = JSPatch(
            patch_type=JSPatchType.MODIFY_HANDLER,
            selector=".nonexistent",
            new_handler="newHandler()",
        )
        assert validator.validate(invalid_patch, html) is False

    def test_validates_add_variable(self):
        """Test validation of ADD_VARIABLE patch."""
        validator = JSPatchValidator()
        html = '<script></script>'

        # Valid variable declarations
        valid_declarations = [
            "let counter = 0;",
            "const MAX_VALUE = 100;",
            "var oldStyle = 'test';",
        ]

        for decl in valid_declarations:
            patch = JSPatch(
                patch_type=JSPatchType.ADD_VARIABLE,
                function_code=decl,
            )
            assert validator.validate(patch, html) is True, f"Failed for: {decl}"

        # Invalid: not a variable declaration
        invalid_patch = JSPatch(
            patch_type=JSPatchType.ADD_VARIABLE,
            function_code="console.log('test');",
        )
        assert validator.validate(invalid_patch, html) is False

    def test_rejects_dangerous_patterns(self):
        """Test rejection of dangerous code patterns."""
        validator = JSPatchValidator()
        html = '<button>Click</button>'

        dangerous_codes = [
            "function test() { eval('alert(1)'); }",
            "function test() { document.write('<script>'); }",
            "function test() { localStorage.clear(); }",
        ]

        for code in dangerous_codes:
            patch = JSPatch(
                patch_type=JSPatchType.ADD_FUNCTION,
                function_name="test",
                function_code=code,
            )
            assert validator.validate(patch, html) is False, f"Should reject: {code}"


class TestPatchValidator:
    """Tests for PatchValidator orchestrator."""

    def test_validates_tailwind_patch(self):
        """Test routing Tailwind patch to correct validator."""
        validator = PatchValidator()
        html = '<button class="btn">Click</button>'

        patch = TailwindPatch(".btn", ["hover:bg-blue-600"], [])

        assert validator.validate(patch, html) is True

    def test_validates_js_patch(self):
        """Test routing JS patch to correct validator."""
        validator = PatchValidator()
        html = '<button>Click</button>'

        patch = JSPatch(
            patch_type=JSPatchType.ADD_FUNCTION,
            function_name="test",
            function_code="function test() {}",
        )

        assert validator.validate(patch, html) is True

    def test_batch_with_mixed_patches(self):
        """Test batch validation with mixed patch types."""
        validator = PatchValidator()
        html = '<button class="btn" id="output">Click</button>'

        patches = [
            TailwindPatch(".btn", ["hover:bg-blue-600"], []),
            JSPatch(
                patch_type=JSPatchType.ADD_FUNCTION,
                function_name="test",
                function_code="function test() {}",
            ),
            TailwindPatch(".nonexistent", ["active:scale-95"], []),  # Invalid
        ]

        valid = validator.validate_batch(patches, html)

        assert len(valid) == 2

    def test_domain_filter_tailwind(self):
        """Test domain filter for Tailwind only."""
        validator = PatchValidator()
        html = '<button class="btn">Click</button>'

        patches = [
            TailwindPatch(".btn", ["hover:bg-blue-600"], []),
            JSPatch(
                patch_type=JSPatchType.ADD_FUNCTION,
                function_name="test",
                function_code="function test() {}",
            ),
        ]

        valid = validator.validate_batch(patches, html, domain="tailwind")

        assert len(valid) == 1
        assert isinstance(valid[0], TailwindPatch)

    def test_domain_filter_js(self):
        """Test domain filter for JS only."""
        validator = PatchValidator()
        html = '<button class="btn">Click</button>'

        patches = [
            TailwindPatch(".btn", ["hover:bg-blue-600"], []),
            JSPatch(
                patch_type=JSPatchType.ADD_FUNCTION,
                function_name="test",
                function_code="function test() {}",
            ),
        ]

        valid = validator.validate_batch(patches, html, domain="js")

        assert len(valid) == 1
        assert isinstance(valid[0], JSPatch)
