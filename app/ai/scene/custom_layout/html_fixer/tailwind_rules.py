"""
Tailwind Rules - Predefined Tailwind classes for fixes.

This module provides a centralized repository of Tailwind classes
used by the deterministic fixer. All fixes are expressed as
Tailwind class additions/removals, not raw CSS.

Usage:
    from app.ai.scene.custom_layout.html_fixer import TailwindFixes

    fix_class = TailwindFixes.get_zindex_fix(current_z=10)
    # Returns "z-50"
"""

from typing import List, Optional


class TailwindFixes:
    """
    Centralized Tailwind class definitions for fixes.

    Organized by error category with helper methods for
    selecting the appropriate fix class.
    """

    # =========================================================================
    # Z-INDEX FIXES
    # =========================================================================

    ZINDEX_0 = "z-0"
    """Base level, behind everything."""

    ZINDEX_LOW = "z-10"
    """Normal content level."""

    ZINDEX_MED = "z-20"
    """Dropdowns, tooltips."""

    ZINDEX_HIGH = "z-30"
    """Elevated content."""

    ZINDEX_MODAL_BACKDROP = "z-40"
    """Modal backdrops."""

    ZINDEX_MODAL = "z-50"
    """Modal content."""

    ZINDEX_TOAST = "z-[100]"
    """Toasts, alerts (arbitrary value)."""

    ZINDEX_MAX = "z-[9999]"
    """Absolute top (use sparingly)."""

    # =========================================================================
    # POINTER EVENTS FIXES
    # =========================================================================

    POINTER_NONE = "pointer-events-none"
    """Element doesn't receive pointer events (pass-through)."""

    POINTER_AUTO = "pointer-events-auto"
    """Element receives pointer events (default behavior)."""

    # =========================================================================
    # POSITION FIXES
    # =========================================================================

    POSITION_RELATIVE = "relative"
    """Relative positioning (creates stacking context with z-index)."""

    POSITION_ABSOLUTE = "absolute"
    """Absolute positioning."""

    POSITION_FIXED = "fixed"
    """Fixed positioning."""

    POSITION_STATIC = "static"
    """Default static positioning."""

    # =========================================================================
    # VISIBILITY FIXES
    # =========================================================================

    VISIBLE = "visible"
    """visibility: visible."""

    INVISIBLE = "invisible"
    """visibility: hidden."""

    OPACITY_0 = "opacity-0"
    """Fully transparent."""

    OPACITY_100 = "opacity-100"
    """Fully opaque."""

    BLOCK = "block"
    """display: block."""

    HIDDEN = "hidden"
    """display: none."""

    FLEX = "flex"
    """display: flex."""

    # =========================================================================
    # TRANSFORM 3D FIXES (Arbitrary values for complex transforms)
    # =========================================================================

    PRESERVE_3D = "[transform-style:preserve-3d]"
    """Children maintain 3D positioning."""

    BACKFACE_HIDDEN = "[backface-visibility:hidden]"
    """Hide element when rotated away."""

    BACKFACE_VISIBLE = "[backface-visibility:visible]"
    """Show element when rotated away."""

    PERSPECTIVE = "[perspective:1000px]"
    """Default perspective for 3D transforms."""

    PERSPECTIVE_NONE = "[perspective:none]"
    """Remove perspective."""

    # =========================================================================
    # VISUAL FEEDBACK AMPLIFICATION
    # =========================================================================

    FEEDBACK_SCALE = "active:scale-95"
    """Scale down slightly on click."""

    FEEDBACK_BRIGHTNESS = "active:brightness-75"
    """Darken on click."""

    FEEDBACK_RING = "focus:ring-4 focus:ring-blue-500"
    """Focus ring for accessibility."""

    FEEDBACK_RING_OFFSET = "focus:ring-offset-2"
    """Ring offset from element."""

    TRANSITION_ALL = "transition-all"
    """Transition all properties."""

    TRANSITION_COLORS = "transition-colors"
    """Transition color properties only."""

    DURATION_150 = "duration-150"
    """150ms transition duration."""

    DURATION_300 = "duration-300"
    """300ms transition duration."""

    # Composite feedback sets
    FEEDBACK_ACTIVE = "active:scale-95 active:brightness-75"
    """Combined active state feedback."""

    FEEDBACK_COMPLETE = "active:scale-95 active:brightness-75 transition-all duration-150"
    """Full feedback with transition."""

    # =========================================================================
    # INTERACTIVE ELEMENT DEFAULTS
    # =========================================================================

    INTERACTIVE_BASE = "relative z-10"
    """Minimum classes for interactive elements."""

    BUTTON_BASE = "relative z-10 cursor-pointer"
    """Base classes for buttons."""

    CLICKABLE_BASE = "relative z-10 pointer-events-auto"
    """Base classes for any clickable element."""

    # =========================================================================
    # OVERLAY DEFAULTS
    # =========================================================================

    OVERLAY_PASSTHROUGH = "absolute inset-0 pointer-events-none"
    """Overlay that doesn't block clicks."""

    OVERLAY_BLOCKING = "absolute inset-0 z-40"
    """Overlay that blocks clicks (modal backdrop)."""

    MODAL_BACKDROP = "fixed inset-0 z-40 bg-black/50"
    """Standard modal backdrop."""

    MODAL_CONTENT = "relative z-50"
    """Modal content positioning."""

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    @classmethod
    def get_zindex_fix(cls, current_z: Optional[int]) -> str:
        """
        Get a z-index class higher than the current value.

        Args:
            current_z: Current z-index value (None = no z-index)

        Returns:
            Appropriate z-index class to elevate the element
        """
        if current_z is None or current_z < 10:
            return cls.ZINDEX_MED
        elif current_z < 50:
            return cls.ZINDEX_MODAL
        else:
            return cls.ZINDEX_MAX

    @classmethod
    def get_zindex_for_layer(cls, layer: str) -> str:
        """
        Get z-index class for a semantic layer.

        Args:
            layer: One of 'base', 'content', 'dropdown', 'modal', 'toast'

        Returns:
            Appropriate z-index class
        """
        layers = {
            "base": cls.ZINDEX_0,
            "content": cls.ZINDEX_LOW,
            "dropdown": cls.ZINDEX_MED,
            "elevated": cls.ZINDEX_HIGH,
            "modal-backdrop": cls.ZINDEX_MODAL_BACKDROP,
            "modal": cls.ZINDEX_MODAL,
            "toast": cls.ZINDEX_TOAST,
            "max": cls.ZINDEX_MAX,
        }
        return layers.get(layer, cls.ZINDEX_LOW)

    @classmethod
    def get_pointer_fix(cls, is_interactive: bool) -> str:
        """
        Get pointer-events class based on element type.

        Args:
            is_interactive: Whether element should receive clicks

        Returns:
            pointer-events-auto or pointer-events-none
        """
        return cls.POINTER_AUTO if is_interactive else cls.POINTER_NONE

    @classmethod
    def get_visibility_fix(cls, issue_type: str) -> tuple[List[str], List[str]]:
        """
        Get visibility fix classes.

        Args:
            issue_type: 'opacity', 'display', or 'visibility'

        Returns:
            Tuple of (classes_to_add, classes_to_remove)
        """
        fixes = {
            "opacity": ([cls.OPACITY_100], [cls.OPACITY_0]),
            "display": ([cls.BLOCK], [cls.HIDDEN]),
            "visibility": ([cls.VISIBLE], [cls.INVISIBLE]),
        }
        return fixes.get(issue_type, ([], []))

    @classmethod
    def get_transform_3d_fix(cls) -> List[str]:
        """
        Get classes to fix 3D transform visibility issues.

        Returns:
            List of classes to add for 3D transform fix
        """
        return [cls.PRESERVE_3D, cls.PERSPECTIVE, cls.BACKFACE_VISIBLE]

    @classmethod
    def get_feedback_amplification(cls) -> List[str]:
        """
        Get classes to amplify visual feedback on interactions.

        Returns:
            List of feedback enhancement classes
        """
        return [
            cls.FEEDBACK_SCALE,
            cls.FEEDBACK_BRIGHTNESS,
            cls.TRANSITION_ALL,
            cls.DURATION_150,
        ]

    @classmethod
    def get_interactive_base(cls) -> List[str]:
        """
        Get minimum classes for an interactive element.

        Returns:
            List of base classes for interactivity
        """
        return [cls.POSITION_RELATIVE, cls.ZINDEX_LOW]

    @classmethod
    def get_overlay_fix(cls, should_block: bool) -> List[str]:
        """
        Get classes for overlay behavior.

        Args:
            should_block: Whether overlay should block clicks

        Returns:
            List of classes for overlay
        """
        if should_block:
            return [cls.POSITION_ABSOLUTE, "inset-0", cls.ZINDEX_MODAL_BACKDROP]
        else:
            return [cls.POSITION_ABSOLUTE, "inset-0", cls.POINTER_NONE]

    @classmethod
    def parse_zindex_class(cls, class_name: str) -> Optional[int]:
        """
        Parse z-index value from a Tailwind class.

        Args:
            class_name: Tailwind class (e.g., 'z-50', 'z-[100]')

        Returns:
            Integer z-index value or None
        """
        if not class_name.startswith("z-"):
            return None

        value = class_name[2:]

        if value == "auto":
            return None

        # Handle arbitrary values like z-[100]
        if value.startswith("[") and value.endswith("]"):
            try:
                return int(value[1:-1])
            except ValueError:
                return None

        # Handle standard values like z-50
        try:
            return int(value)
        except ValueError:
            return None

    @classmethod
    def get_all_zindex_classes(cls) -> List[str]:
        """Get all predefined z-index classes."""
        return [
            cls.ZINDEX_0,
            cls.ZINDEX_LOW,
            cls.ZINDEX_MED,
            cls.ZINDEX_HIGH,
            cls.ZINDEX_MODAL_BACKDROP,
            cls.ZINDEX_MODAL,
            cls.ZINDEX_TOAST,
            cls.ZINDEX_MAX,
        ]
