"""
Error Types - Classification of HTML/CSS interactivity errors.

These error types map directly to Tailwind fix strategies:
- ZINDEX_* → Add z-* classes
- POINTER_* → Add pointer-events-* classes
- INVISIBLE_* → Add opacity-100, block, visible classes
- TRANSFORM_* → Add [transform-style:preserve-3d], etc.
- FEEDBACK_* → Add active:*, hover:* classes
"""

from enum import Enum


class ErrorType(Enum):
    """Classification of HTML/CSS errors that block interactivity."""

    # Z-Index Issues
    ZINDEX_CONFLICT = "zindex_conflict"
    """Element is behind another element due to z-index stacking."""

    ZINDEX_MISSING = "zindex_missing"
    """Interactive element lacks explicit z-index in positioned context."""

    # Pointer Events Issues
    POINTER_BLOCKED = "pointer_blocked"
    """Element cannot receive clicks due to overlay without pointer-events-none."""

    POINTER_INTERCEPTED = "pointer_intercepted"
    """Clicks are captured by ancestor element instead of target."""

    # Visibility Issues
    INVISIBLE_OPACITY = "invisible_opacity"
    """Element has opacity: 0 or very low opacity."""

    INVISIBLE_DISPLAY = "invisible_display"
    """Element has display: none or is hidden."""

    INVISIBLE_VISIBILITY = "invisible_visibility"
    """Element has visibility: hidden."""

    # Transform Issues
    TRANSFORM_3D_HIDDEN = "transform_3d_hidden"
    """Element hidden due to 3D transform (backface, rotation, etc.)."""

    TRANSFORM_OFFSCREEN = "transform_offscreen"
    """Element transformed outside visible viewport."""

    # Visual Feedback Issues
    FEEDBACK_TOO_SUBTLE = "feedback_too_subtle"
    """Click feedback exists but is too subtle to detect visually."""

    FEEDBACK_MISSING = "feedback_missing"
    """No visual feedback on click/hover states."""

    # Catch-all
    UNKNOWN = "unknown"
    """Error type could not be determined."""

    @classmethod
    def from_string(cls, value: str) -> "ErrorType":
        """Convert string to ErrorType, defaulting to UNKNOWN."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN

    @property
    def is_zindex_related(self) -> bool:
        """Check if error is related to z-index."""
        return self in (self.ZINDEX_CONFLICT, self.ZINDEX_MISSING)

    @property
    def is_pointer_related(self) -> bool:
        """Check if error is related to pointer events."""
        return self in (self.POINTER_BLOCKED, self.POINTER_INTERCEPTED)

    @property
    def is_visibility_related(self) -> bool:
        """Check if error is related to element visibility."""
        return self in (
            self.INVISIBLE_OPACITY,
            self.INVISIBLE_DISPLAY,
            self.INVISIBLE_VISIBILITY,
        )

    @property
    def is_transform_related(self) -> bool:
        """Check if error is related to CSS transforms."""
        return self in (self.TRANSFORM_3D_HIDDEN, self.TRANSFORM_OFFSCREEN)

    @property
    def is_feedback_related(self) -> bool:
        """Check if error is related to visual feedback."""
        return self in (self.FEEDBACK_TOO_SUBTLE, self.FEEDBACK_MISSING)

    @property
    def requires_llm(self) -> bool:
        """Check if this error type typically requires LLM for repair."""
        # Most errors can be fixed deterministically with Tailwind classes
        # Only UNKNOWN and complex FEEDBACK issues may need LLM
        return self in (self.UNKNOWN, self.FEEDBACK_MISSING)
