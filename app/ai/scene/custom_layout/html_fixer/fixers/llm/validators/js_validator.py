"""
JSPatchValidator - Validates JavaScript patches before application.

Sprint 6: Ensures LLM-generated JavaScript patches are safe and syntactically valid.
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from ..contracts.js_patch import JSPatch, JSPatchType

logger = logging.getLogger(__name__)


class JSPatchValidator:
    """
    Validates JavaScript patches before application.

    Checks that:
    - Function code is syntactically valid
    - DOM references exist
    - Patches don't introduce obvious errors
    """

    # Patterns that indicate potentially dangerous code
    # Note: Function constructor uses capital F to distinguish from 'function' keyword
    DANGEROUS_PATTERNS = [
        r"eval\s*\(",                    # eval()
        r"new\s+Function\s*\(",          # Function constructor (must have 'new')
        r"document\.write\s*\(",         # document.write
        r"innerHTML\s*=.*<script",       # Script injection via innerHTML
        r"fetch\s*\(['\"]https?:",       # External fetch calls with http(s)
        r"XMLHttpRequest",               # XHR to external
        r"localStorage\.clear",          # Clear storage
        r"sessionStorage\.clear",        # Clear storage
    ]

    def __init__(self, allow_external_calls: bool = False):
        """
        Initialize validator.

        Args:
            allow_external_calls: If True, allow fetch/XHR patterns
        """
        self.allow_external_calls = allow_external_calls
        # Note: Don't use IGNORECASE to avoid matching 'function()' as 'Function()'
        self._dangerous_compiled = [re.compile(p) for p in self.DANGEROUS_PATTERNS]

    def validate(self, patch: JSPatch, html: str) -> bool:
        """
        Validate a JavaScript patch.

        Args:
            patch: The patch to validate
            html: Original HTML content

        Returns:
            True if patch is valid, False otherwise
        """
        if patch.patch_type == JSPatchType.ADD_FUNCTION:
            return self._validate_add_function(patch)

        elif patch.patch_type == JSPatchType.REPLACE_FUNCTION:
            return self._validate_replace_function(patch)

        elif patch.patch_type == JSPatchType.FIX_SYNTAX:
            return self._validate_fix_syntax(patch)

        elif patch.patch_type == JSPatchType.FIX_DOM_REFERENCE:
            return self._validate_dom_reference(patch, html)

        elif patch.patch_type == JSPatchType.ADD_VARIABLE:
            return self._validate_add_variable(patch)

        elif patch.patch_type == JSPatchType.MODIFY_HANDLER:
            return self._validate_modify_handler(patch, html)

        logger.warning(f"Unknown patch type: {patch.patch_type}")
        return False

    def _validate_add_function(self, patch: JSPatch) -> bool:
        """Validate ADD_FUNCTION patch."""
        if not patch.function_name:
            logger.warning("ADD_FUNCTION patch missing function_name")
            return False

        if not patch.function_code:
            logger.warning("ADD_FUNCTION patch missing function_code")
            return False

        # Check basic syntax
        if not self._is_valid_function_code(patch.function_code):
            logger.warning(f"Invalid function code for '{patch.function_name}'")
            return False

        # Check for dangerous patterns
        if self._contains_dangerous_patterns(patch.function_code):
            logger.warning(f"Function code contains dangerous patterns")
            return False

        return True

    def _validate_replace_function(self, patch: JSPatch) -> bool:
        """Validate REPLACE_FUNCTION patch."""
        # Same validation as ADD_FUNCTION
        return self._validate_add_function(patch)

    def _validate_fix_syntax(self, patch: JSPatch) -> bool:
        """Validate FIX_SYNTAX patch."""
        if patch.script_index is None:
            logger.warning("FIX_SYNTAX patch missing script_index")
            return False

        if patch.line_start is None:
            logger.warning("FIX_SYNTAX patch missing line_start")
            return False

        if not patch.replacement_code:
            logger.warning("FIX_SYNTAX patch missing replacement_code")
            return False

        # Check for dangerous patterns in replacement
        if self._contains_dangerous_patterns(patch.replacement_code):
            logger.warning("Replacement code contains dangerous patterns")
            return False

        return True

    def _validate_dom_reference(self, patch: JSPatch, html: str) -> bool:
        """Validate FIX_DOM_REFERENCE patch."""
        if not patch.old_reference:
            logger.warning("FIX_DOM_REFERENCE patch missing old_reference")
            return False

        if not patch.new_reference:
            logger.warning("FIX_DOM_REFERENCE patch missing new_reference")
            return False

        # Check that new reference exists in HTML
        if not self._dom_id_exists(patch.new_reference, html):
            logger.warning(
                f"New DOM reference '{patch.new_reference}' not found in HTML"
            )
            return False

        return True

    def _validate_add_variable(self, patch: JSPatch) -> bool:
        """Validate ADD_VARIABLE patch."""
        if not patch.function_code:
            logger.warning("ADD_VARIABLE patch missing function_code (variable declaration)")
            return False

        # Should be a variable declaration
        code = patch.function_code.strip()
        if not (code.startswith("let ") or code.startswith("const ") or
                code.startswith("var ")):
            logger.warning("ADD_VARIABLE code doesn't look like a variable declaration")
            return False

        return True

    def _validate_modify_handler(self, patch: JSPatch, html: str) -> bool:
        """Validate MODIFY_HANDLER patch."""
        if not patch.selector:
            logger.warning("MODIFY_HANDLER patch missing selector")
            return False

        if not patch.new_handler:
            logger.warning("MODIFY_HANDLER patch missing new_handler")
            return False

        # Check selector exists
        try:
            soup = BeautifulSoup(html, "html.parser")
            if not soup.select(patch.selector):
                logger.warning(f"Selector '{patch.selector}' not found in HTML")
                return False
        except Exception as e:
            logger.warning(f"Error checking selector: {e}")
            return False

        return True

    def _is_valid_function_code(self, code: str) -> bool:
        """
        Basic syntax validation for function code.

        This is a simple check - not a full JS parser.
        """
        if not code:
            return False

        code = code.strip()

        # Must contain function keyword or arrow
        has_function = (
            "function " in code or
            "function(" in code or
            "async function" in code or
            "=>" in code
        )

        if not has_function:
            logger.debug("Code doesn't contain function definition")
            return False

        # Must have balanced braces
        if code.count("{") != code.count("}"):
            logger.debug("Unbalanced braces in function code")
            return False

        # Must have balanced parentheses
        if code.count("(") != code.count(")"):
            logger.debug("Unbalanced parentheses in function code")
            return False

        return True

    def _contains_dangerous_patterns(self, code: str) -> bool:
        """Check if code contains potentially dangerous patterns."""
        if self.allow_external_calls:
            # Skip fetch/XHR checks if external calls are allowed
            patterns_to_check = self._dangerous_compiled[:6]
        else:
            patterns_to_check = self._dangerous_compiled

        for pattern in patterns_to_check:
            if pattern.search(code):
                return True

        return False

    def _dom_id_exists(self, element_id: str, html: str) -> bool:
        """Check if an element with given ID exists in HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.find(id=element_id) is not None
        except Exception:
            return False
