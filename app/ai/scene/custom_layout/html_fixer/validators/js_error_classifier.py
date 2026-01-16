"""
JavaScript Error Classifier - Convert JS errors to ClassifiedError.

Maps JavaScript validation results to the standard error classification
system used by the html_fixer pipeline.

All JS errors are marked as requires_llm=True because JavaScript fixes
require code generation rather than simple Tailwind class changes.

Usage:
    from app.ai.scene.custom_layout.html_fixer.validators import (
        JSRuntimeValidator,
        JSErrorClassifier,
    )

    validator = JSRuntimeValidator()
    result = await validator.validate(html, page)

    classifier = JSErrorClassifier()
    errors = classifier.classify(result)
"""

from typing import List, Dict, Any, Optional

from ..contracts.errors import ErrorType
from ..contracts.validation import ClassifiedError, TailwindInfo
from .js_runtime_validator import JSRuntimeResult, RuntimeError
from .js_validator import JSValidationResult


class JSErrorClassifier:
    """
    Classifies JavaScript errors into standard ClassifiedError format.

    Converts JSRuntimeResult into List[ClassifiedError] that can be
    processed by the fix pipeline and reported consistently.
    """

    def classify(self, result: JSRuntimeResult) -> List[ClassifiedError]:
        """
        Classify all JavaScript errors from runtime validation.

        Args:
            result: JSRuntimeResult from runtime validation

        Returns:
            List of ClassifiedError instances
        """
        errors: List[ClassifiedError] = []

        # Syntax errors (highest priority)
        for syntax_err in result.syntax_errors:
            errors.append(self._classify_syntax_error(syntax_err))

        # Missing functions (from static + runtime)
        for fn_name in result.all_missing_functions:
            error = self._classify_missing_function(fn_name, result.static_result)
            if error:
                errors.append(error)

        # Missing DOM elements
        for dom_ref in result.static_result.missing_dom_elements:
            errors.append(self._classify_missing_dom_element(dom_ref))

        # Handler execution errors
        for handler_err in result.handler_errors:
            errors.append(self._classify_handler_error(handler_err))

        # Console errors that indicate undefined variables
        for console_err in result.console_errors:
            if self._is_undefined_variable_error(console_err):
                errors.append(self._classify_undefined_variable(console_err))

        return errors

    def classify_static(self, result: JSValidationResult) -> List[ClassifiedError]:
        """
        Classify errors from static validation only.

        Args:
            result: JSValidationResult from static validation

        Returns:
            List of ClassifiedError instances
        """
        errors: List[ClassifiedError] = []

        # Missing functions
        for fn_name in result.missing_functions:
            error = self._classify_missing_function(fn_name, result)
            if error:
                errors.append(error)

        # Missing DOM elements
        for dom_ref in result.missing_dom_elements:
            errors.append(self._classify_missing_dom_element(dom_ref))

        return errors

    def _classify_syntax_error(self, err: RuntimeError) -> ClassifiedError:
        """Create ClassifiedError for JavaScript syntax error."""
        return ClassifiedError(
            error_type=ErrorType.JS_SYNTAX_ERROR,
            selector="script",
            element_tag="script",
            tailwind_info=TailwindInfo(),
            line_number=err.line_number,
            confidence=1.0,
            requires_llm=True,
            suggested_classes=[],
            classes_to_remove=[],
        )

    def _classify_missing_function(
        self, fn_name: str, static_result: JSValidationResult
    ) -> Optional[ClassifiedError]:
        """Create ClassifiedError for missing function."""
        # Find which element(s) call this function
        # We'll use a generic selector pattern
        selector = f'[onclick*="{fn_name}"]'

        # Try to find the element tag
        element_tag = "unknown"
        from ..analyzers.event_mapper import EventMapper, EventInfo

        # Check if we can find more specific info
        # For now, use generic button/element
        element_tag = "element"

        return ClassifiedError(
            error_type=ErrorType.JS_MISSING_FUNCTION,
            selector=selector,
            element_tag=element_tag,
            tailwind_info=TailwindInfo(),
            confidence=1.0,
            requires_llm=True,
            suggested_classes=[],
            classes_to_remove=[],
        )

    def _classify_missing_dom_element(
        self, dom_ref: Dict[str, str]
    ) -> ClassifiedError:
        """Create ClassifiedError for missing DOM element reference."""
        selector = dom_ref.get("selector", dom_ref.get("argument", "unknown"))
        method = dom_ref.get("method", "getElementById")

        return ClassifiedError(
            error_type=ErrorType.JS_MISSING_DOM_ELEMENT,
            selector=selector,
            element_tag="unknown",
            tailwind_info=TailwindInfo(),
            confidence=0.95,
            requires_llm=True,
            suggested_classes=[],
            classes_to_remove=[],
        )

    def _classify_handler_error(
        self, handler_err: Dict[str, Any]
    ) -> ClassifiedError:
        """Create ClassifiedError for event handler execution error."""
        selector = handler_err.get("selector", "unknown")
        error_type = handler_err.get("error_type", "unknown")

        # Determine the specific error type
        if error_type == "ReferenceError":
            classified_type = ErrorType.JS_UNDEFINED_VARIABLE
        else:
            classified_type = ErrorType.JS_SYNTAX_ERROR

        return ClassifiedError(
            error_type=classified_type,
            selector=selector,
            element_tag="element",
            tailwind_info=TailwindInfo(),
            confidence=0.9,
            requires_llm=True,
            suggested_classes=[],
            classes_to_remove=[],
        )

    def _classify_undefined_variable(
        self, err: RuntimeError
    ) -> ClassifiedError:
        """Create ClassifiedError for undefined variable error."""
        return ClassifiedError(
            error_type=ErrorType.JS_UNDEFINED_VARIABLE,
            selector="script",
            element_tag="script",
            tailwind_info=TailwindInfo(),
            line_number=err.line_number,
            confidence=0.85,
            requires_llm=True,
            suggested_classes=[],
            classes_to_remove=[],
        )

    def _is_undefined_variable_error(self, err: RuntimeError) -> bool:
        """Check if console error indicates undefined variable."""
        if not err.message:
            return False

        undefined_patterns = [
            "is not defined",
            "is undefined",
            "ReferenceError",
            "cannot read property",
            "Cannot read properties of undefined",
            "Cannot read properties of null",
        ]

        message_lower = err.message.lower()
        return any(pattern.lower() in message_lower for pattern in undefined_patterns)

    def __repr__(self) -> str:
        """String representation."""
        return "JSErrorClassifier()"
