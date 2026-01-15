"""
Fixtures for fixer tests.

Provides common test data and helper functions.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports - use absolute path to avoid
# triggering parent package imports
_custom_layout_path = Path(__file__).resolve().parent.parent.parent
if str(_custom_layout_path) not in sys.path:
    sys.path.insert(0, str(_custom_layout_path))

# Import from html_fixer directly (not through app.ai.scene.custom_layout)
from html_fixer.contracts.errors import ErrorType
from html_fixer.contracts.patches import TailwindPatch, PatchSet
from html_fixer.contracts.validation import ClassifiedError, TailwindInfo
from html_fixer.fixers import TailwindInjector
from html_fixer.fixers.deterministic import (
    RuleEngine,
    create_default_engine,
    VisibilityRestoreRule,
    ZIndexFixRule,
    PointerEventsFixRule,
    PassthroughRule,
    Transform3DFixRule,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def injector():
    """TailwindInjector instance."""
    return TailwindInjector()


@pytest.fixture
def engine():
    """Empty RuleEngine instance."""
    return RuleEngine()


@pytest.fixture
def default_engine():
    """RuleEngine with all default rules."""
    return create_default_engine()


@pytest.fixture
def simple_html():
    """Simple HTML for testing."""
    return '<button class="bg-blue-500 z-10">Click me</button>'


@pytest.fixture
def html_with_overlay():
    """HTML with overlay blocking button."""
    return """
    <div class="relative">
        <button id="btn" class="z-10">Button</button>
        <div id="overlay" class="absolute inset-0 z-40 bg-black/50"></div>
    </div>
    """


@pytest.fixture
def html_with_hidden():
    """HTML with hidden element."""
    return '<button class="hidden">Hidden Button</button>'


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
