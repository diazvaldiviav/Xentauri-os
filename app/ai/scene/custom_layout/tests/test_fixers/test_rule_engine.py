"""
Unit tests for RuleEngine.

Tests rule registration, execution, and patch generation.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.patches import PatchSet
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.fixers.deterministic import (
    RuleEngine,
    create_default_engine,
    FixRule,
    VisibilityRestoreRule,
    ZIndexFixRule,
    PointerEventsFixRule,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def make_error(
    error_type: ErrorType,
    selector: str = "#btn",
    element_tag: str = "button",
    z_index: int = None,
    has_pointer_none: bool = False,
    has_pointer_auto: bool = False,
    has_relative: bool = False,
    blocking_element: str = None,
    requires_llm: bool = False,
    confidence: float = 1.0,
) -> ClassifiedError:
    """Helper to create ClassifiedError for tests."""
    info = TailwindInfo(
        all_classes=set(),
        z_index=z_index,
        has_pointer_none=has_pointer_none,
        has_pointer_auto=has_pointer_auto,
        has_relative=has_relative,
    )
    return ClassifiedError(
        error_type=error_type,
        selector=selector,
        element_tag=element_tag,
        tailwind_info=info,
        blocking_element=blocking_element,
        requires_llm=requires_llm,
        confidence=confidence,
    )


# ============================================================================
# REGISTRATION TESTS
# ============================================================================


class TestRuleRegistration:
    """Tests for rule registration."""

    def test_register_single_rule(self, engine):
        """Should register a single rule."""
        engine.register(ZIndexFixRule())

        assert len(engine) == 1
        assert isinstance(engine.rules[0], ZIndexFixRule)

    def test_register_multiple_rules(self, engine):
        """Should register multiple rules."""
        engine.register(ZIndexFixRule())
        engine.register(VisibilityRestoreRule())

        assert len(engine) == 2

    def test_register_all(self, engine):
        """Should register multiple rules at once."""
        engine.register_all([
            ZIndexFixRule(),
            VisibilityRestoreRule(),
            PointerEventsFixRule(),
        ])

        assert len(engine) == 3

    def test_rules_sorted_by_priority(self, engine):
        """Rules should be sorted by priority after registration."""
        # Register in wrong order
        engine.register(PointerEventsFixRule())  # priority 25
        engine.register(ZIndexFixRule())         # priority 15
        engine.register(VisibilityRestoreRule()) # priority 5

        rules = engine.rules
        assert rules[0].priority <= rules[1].priority <= rules[2].priority

    def test_unregister_rule(self, engine):
        """Should unregister a rule by class."""
        engine.register(ZIndexFixRule())
        engine.register(VisibilityRestoreRule())

        result = engine.unregister(ZIndexFixRule)

        assert result is True
        assert len(engine) == 1
        assert isinstance(engine.rules[0], VisibilityRestoreRule)

    def test_unregister_nonexistent_rule(self, engine):
        """Should return False when unregistering nonexistent rule."""
        engine.register(VisibilityRestoreRule())

        result = engine.unregister(ZIndexFixRule)

        assert result is False
        assert len(engine) == 1


# ============================================================================
# TYPE INDEX TESTS
# ============================================================================


class TestTypeIndex:
    """Tests for error type indexing."""

    def test_get_rules_for_type(self, engine):
        """Should return rules that handle a specific error type."""
        engine.register(ZIndexFixRule())
        engine.register(VisibilityRestoreRule())

        rules = engine.get_rules_for_type(ErrorType.ZINDEX_CONFLICT)

        assert len(rules) == 1
        assert isinstance(rules[0], ZIndexFixRule)

    def test_get_rules_for_unhandled_type(self, engine):
        """Should return empty list for unhandled type."""
        engine.register(ZIndexFixRule())

        rules = engine.get_rules_for_type(ErrorType.FEEDBACK_MISSING)

        assert rules == []

    def test_handled_types_property(self, engine):
        """Should list all handled error types."""
        engine.register(ZIndexFixRule())
        engine.register(VisibilityRestoreRule())

        handled = engine.handled_types

        assert ErrorType.ZINDEX_CONFLICT in handled
        assert ErrorType.INVISIBLE_OPACITY in handled


# ============================================================================
# APPLY RULES TESTS
# ============================================================================


class TestApplyRules:
    """Tests for applying rules to errors."""

    def test_apply_rules_returns_patchset(self, engine):
        """Should return a PatchSet."""
        engine.register(VisibilityRestoreRule())
        error = make_error(ErrorType.INVISIBLE_OPACITY)

        result = engine.apply_rules([error])

        assert isinstance(result, PatchSet)
        assert result.source == "deterministic"

    def test_apply_rules_generates_patches(self, engine):
        """Should generate patches for matching errors."""
        engine.register(VisibilityRestoreRule())
        error = make_error(ErrorType.INVISIBLE_OPACITY)

        result = engine.apply_rules([error])

        assert len(result) >= 1

    def test_apply_rules_skips_llm_required(self, engine):
        """Should skip errors marked as requiring LLM."""
        engine.register(VisibilityRestoreRule())
        error = make_error(ErrorType.INVISIBLE_OPACITY, requires_llm=True)

        result = engine.apply_rules([error])

        assert len(result) == 0

    def test_apply_rules_handles_multiple_errors(self, engine):
        """Should process multiple errors."""
        engine.register(VisibilityRestoreRule())
        engine.register(ZIndexFixRule())
        errors = [
            make_error(ErrorType.INVISIBLE_OPACITY, selector="#btn1"),
            make_error(ErrorType.ZINDEX_CONFLICT, selector="#btn2"),
        ]

        result = engine.apply_rules(errors)

        assert len(result) >= 2

    def test_apply_rules_empty_list(self, engine):
        """Should handle empty error list."""
        engine.register(VisibilityRestoreRule())

        result = engine.apply_rules([])

        assert len(result) == 0

    def test_apply_rules_no_matching_rule(self, engine):
        """Should handle errors with no matching rule."""
        engine.register(VisibilityRestoreRule())
        error = make_error(ErrorType.FEEDBACK_MISSING)

        result = engine.apply_rules([error])

        assert len(result) == 0

    def test_apply_single(self, engine):
        """Should apply rules to a single error."""
        engine.register(VisibilityRestoreRule())
        error = make_error(ErrorType.INVISIBLE_OPACITY)

        result = engine.apply_single(error)

        assert result is not None
        assert len(result) >= 1

    def test_apply_single_no_match(self, engine):
        """Should return None when no rule matches."""
        engine.register(VisibilityRestoreRule())
        error = make_error(ErrorType.FEEDBACK_MISSING)

        result = engine.apply_single(error)

        assert result is None


# ============================================================================
# DEFAULT ENGINE TESTS
# ============================================================================


class TestDefaultEngine:
    """Tests for create_default_engine."""

    def test_create_default_engine(self):
        """Should create engine with all default rules."""
        engine = create_default_engine()

        assert len(engine) == 5

    def test_default_engine_handles_visibility(self):
        """Default engine should handle visibility errors."""
        engine = create_default_engine()
        error = make_error(ErrorType.INVISIBLE_OPACITY)

        result = engine.apply_rules([error])

        assert len(result) >= 1

    def test_default_engine_handles_zindex(self):
        """Default engine should handle z-index errors."""
        engine = create_default_engine()
        error = make_error(ErrorType.ZINDEX_CONFLICT)

        result = engine.apply_rules([error])

        assert len(result) >= 1

    def test_default_engine_handles_pointer(self):
        """Default engine should handle pointer events errors."""
        engine = create_default_engine()
        error = make_error(ErrorType.POINTER_BLOCKED, blocking_element="#overlay")

        result = engine.apply_rules([error])

        # Should have patches for both target and blocker
        assert len(result) >= 1

    def test_default_engine_handles_transform(self):
        """Default engine should handle transform errors."""
        engine = create_default_engine()
        error = make_error(ErrorType.TRANSFORM_3D_HIDDEN)

        result = engine.apply_rules([error])

        assert len(result) >= 1


# ============================================================================
# REPR TESTS
# ============================================================================


class TestEngineRepr:
    """Tests for engine string representation."""

    def test_repr_empty(self, engine):
        """Should show 0 rules when empty."""
        assert "0 rules" in repr(engine)

    def test_repr_with_rules(self, engine):
        """Should show rule count."""
        engine.register(ZIndexFixRule())
        engine.register(VisibilityRestoreRule())

        assert "2 rules" in repr(engine)
