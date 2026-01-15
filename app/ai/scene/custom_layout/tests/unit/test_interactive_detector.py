"""
Unit tests for InteractiveDetector.

Tests detection of interactive elements.
"""

import sys
from pathlib import Path

import pytest

# Add custom_layout to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from html_fixer.analyzers.dom_parser import DOMParser
from html_fixer.analyzers.interactive_detector import (
    InteractiveDetector,
    InteractionType,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def detector():
    """InteractiveDetector instance."""
    return InteractiveDetector()


@pytest.fixture
def basic_html():
    """HTML with various interactive elements."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <button id="btn1">Click me</button>
        <a href="/page" id="link1">Go to page</a>
        <input type="text" id="input1" />
        <input type="checkbox" id="checkbox1" />
        <input type="submit" id="submit1" />
        <select id="select1"><option>Option</option></select>
        <textarea id="textarea1"></textarea>
        <div id="plain">Not interactive</div>
    </body>
    </html>
    """


@pytest.fixture
def onclick_html():
    """HTML with onclick handlers."""
    return """
    <body>
        <div id="clickable" onclick="handleClick()">Clickable div</div>
        <span id="touch" ontouchstart="handleTouch()">Touch span</span>
        <div id="plain">Plain div</div>
    </body>
    """


@pytest.fixture
def role_html():
    """HTML with ARIA roles."""
    return """
    <body>
        <div role="button" id="btn-role">Button by role</div>
        <div role="link" id="link-role">Link by role</div>
        <div role="checkbox" id="checkbox-role">Checkbox by role</div>
        <div role="textbox" id="textbox-role">Textbox by role</div>
        <div role="presentation" id="present-role">Presentation</div>
    </body>
    """


@pytest.fixture
def disabled_html():
    """HTML with disabled elements."""
    return """
    <body>
        <button id="enabled">Enabled</button>
        <button id="disabled" disabled>Disabled</button>
        <button id="aria-disabled" aria-disabled="true">ARIA Disabled</button>
    </body>
    """


@pytest.fixture
def parser(basic_html):
    """Parser with basic HTML."""
    return DOMParser(basic_html)


# ============================================================================
# BASIC DETECTION TESTS
# ============================================================================


class TestBasicDetection:
    """Tests for basic interactive element detection."""

    def test_detect_button(self, detector, parser):
        """Should detect button elements."""
        elements = detector.find_interactive_elements(parser)
        btn = next((e for e in elements if e.selector == "#btn1"), None)

        assert btn is not None
        assert btn.interaction_type == InteractionType.CLICK

    def test_detect_link(self, detector, parser):
        """Should detect link elements."""
        elements = detector.find_interactive_elements(parser)
        link = next((e for e in elements if e.selector == "#link1"), None)

        assert link is not None
        assert link.is_link is True

    def test_detect_text_input(self, detector, parser):
        """Should detect text input elements."""
        elements = detector.find_interactive_elements(parser)
        inp = next((e for e in elements if e.selector == "#input1"), None)

        assert inp is not None
        assert inp.interaction_type == InteractionType.INPUT
        assert inp.is_form_element is True

    def test_detect_checkbox(self, detector, parser):
        """Should detect checkbox input."""
        elements = detector.find_interactive_elements(parser)
        cb = next((e for e in elements if e.selector == "#checkbox1"), None)

        assert cb is not None
        assert cb.interaction_type == InteractionType.SELECT

    def test_detect_submit(self, detector, parser):
        """Should detect submit button."""
        elements = detector.find_interactive_elements(parser)
        submit = next((e for e in elements if e.selector == "#submit1"), None)

        assert submit is not None
        assert submit.interaction_type == InteractionType.CLICK

    def test_detect_select(self, detector, parser):
        """Should detect select elements."""
        elements = detector.find_interactive_elements(parser)
        select = next((e for e in elements if e.selector == "#select1"), None)

        assert select is not None
        assert select.interaction_type == InteractionType.SELECT

    def test_detect_textarea(self, detector, parser):
        """Should detect textarea elements."""
        elements = detector.find_interactive_elements(parser)
        ta = next((e for e in elements if e.selector == "#textarea1"), None)

        assert ta is not None
        assert ta.interaction_type == InteractionType.INPUT

    def test_ignore_plain_div(self, detector, parser):
        """Should not detect plain div as interactive."""
        elements = detector.find_interactive_elements(parser)
        plain = next((e for e in elements if e.selector == "#plain"), None)

        assert plain is None


# ============================================================================
# EVENT HANDLER TESTS
# ============================================================================


class TestEventHandlerDetection:
    """Tests for onclick handler detection."""

    def test_detect_onclick(self, detector, onclick_html):
        """Should detect onclick elements."""
        parser = DOMParser(onclick_html)
        elements = detector.find_interactive_elements(parser)
        clickable = next((e for e in elements if e.selector == "#clickable"), None)

        assert clickable is not None
        assert clickable.has_handler is True

    def test_detect_touch_handler(self, detector, onclick_html):
        """Should detect touch event handlers."""
        parser = DOMParser(onclick_html)
        elements = detector.find_interactive_elements(parser)
        touch = next((e for e in elements if e.selector == "#touch"), None)

        assert touch is not None
        assert touch.has_handler is True

    def test_ignore_plain_without_handler(self, detector, onclick_html):
        """Should not detect plain div without handler."""
        parser = DOMParser(onclick_html)
        elements = detector.find_interactive_elements(parser)
        plain = next((e for e in elements if e.selector == "#plain"), None)

        assert plain is None


# ============================================================================
# ARIA ROLE TESTS
# ============================================================================


class TestAriaRoleDetection:
    """Tests for ARIA role detection."""

    def test_detect_button_role(self, detector, role_html):
        """Should detect role=button."""
        parser = DOMParser(role_html)
        elements = detector.find_interactive_elements(parser)
        btn = next((e for e in elements if e.selector == "#btn-role"), None)

        assert btn is not None
        assert btn.interaction_type == InteractionType.CLICK

    def test_detect_link_role(self, detector, role_html):
        """Should detect role=link."""
        parser = DOMParser(role_html)
        elements = detector.find_interactive_elements(parser)
        link = next((e for e in elements if e.selector == "#link-role"), None)

        assert link is not None

    def test_detect_checkbox_role(self, detector, role_html):
        """Should detect role=checkbox."""
        parser = DOMParser(role_html)
        elements = detector.find_interactive_elements(parser)
        cb = next((e for e in elements if e.selector == "#checkbox-role"), None)

        assert cb is not None
        assert cb.interaction_type == InteractionType.SELECT

    def test_detect_textbox_role(self, detector, role_html):
        """Should detect role=textbox."""
        parser = DOMParser(role_html)
        elements = detector.find_interactive_elements(parser)
        tb = next((e for e in elements if e.selector == "#textbox-role"), None)

        assert tb is not None
        assert tb.interaction_type == InteractionType.INPUT

    def test_ignore_presentation_role(self, detector, role_html):
        """Should not detect role=presentation."""
        parser = DOMParser(role_html)
        elements = detector.find_interactive_elements(parser)
        present = next((e for e in elements if e.selector == "#present-role"), None)

        assert present is None


# ============================================================================
# DISABLED STATE TESTS
# ============================================================================


class TestDisabledState:
    """Tests for disabled element handling."""

    def test_detect_enabled_button(self, detector, disabled_html):
        """Should detect enabled button."""
        parser = DOMParser(disabled_html)
        elements = detector.find_interactive_elements(parser)
        enabled = next((e for e in elements if e.selector == "#enabled"), None)

        assert enabled is not None
        assert enabled.is_disabled is False

    def test_ignore_disabled_button(self, detector, disabled_html):
        """Should ignore disabled button."""
        parser = DOMParser(disabled_html)
        elements = detector.find_interactive_elements(parser)
        disabled = next((e for e in elements if e.selector == "#disabled"), None)

        assert disabled is None

    def test_ignore_aria_disabled(self, detector, disabled_html):
        """Should ignore aria-disabled button."""
        parser = DOMParser(disabled_html)
        elements = detector.find_interactive_elements(parser)
        aria_disabled = next((e for e in elements if e.selector == "#aria-disabled"), None)

        assert aria_disabled is None


# ============================================================================
# FILTERING TESTS
# ============================================================================


class TestFiltering:
    """Tests for filtering methods."""

    def test_find_clickable_elements(self, detector, parser):
        """Should filter to clickable elements only."""
        clickable = detector.find_clickable_elements(parser)

        # Should include button, link, submit, checkbox, select but not text input
        interaction_types = {e.interaction_type for e in clickable}
        assert InteractionType.CLICK in interaction_types
        assert InteractionType.SELECT in interaction_types
        # INPUT type elements should be excluded
        assert not any(e.interaction_type == InteractionType.INPUT for e in clickable)

    def test_find_form_elements(self, detector, parser):
        """Should filter to form elements only."""
        form_elements = detector.find_form_elements(parser)

        assert len(form_elements) >= 4  # input, checkbox, submit, select, textarea
        assert all(e.is_form_element for e in form_elements)

    def test_get_elements_by_type(self, detector, parser):
        """Should filter by interaction type."""
        click_elements = detector.get_elements_by_type(parser, InteractionType.CLICK)

        assert len(click_elements) >= 2  # button, link, submit
        assert all(e.interaction_type == InteractionType.CLICK for e in click_elements)
