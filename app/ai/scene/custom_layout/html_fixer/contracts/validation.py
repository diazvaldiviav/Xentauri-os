"""
Validation - Data structures for HTML analysis and fix results.

These structures carry information through the fix pipeline:
1. TailwindInfo: Extracted Tailwind class information
2. ClassifiedError: An error with its Tailwind context
3. FixResult: Result of applying fixes
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set

from .errors import ErrorType
from .patches import TailwindPatch


@dataclass
class TailwindInfo:
    """
    Information about Tailwind classes on an element.

    Extracted by TailwindAnalyzer for use in error classification
    and fix generation.
    """

    all_classes: Set[str] = field(default_factory=set)
    """All Tailwind classes on the element."""

    z_index: Optional[int] = None
    """Extracted z-index value (None if no z-* class)."""

    has_pointer_none: bool = False
    """Element has pointer-events-none."""

    has_pointer_auto: bool = False
    """Element has pointer-events-auto."""

    has_relative: bool = False
    """Element has relative positioning."""

    has_absolute: bool = False
    """Element has absolute positioning."""

    has_fixed: bool = False
    """Element has fixed positioning."""

    has_transform: bool = False
    """Element has transform classes."""

    has_preserve_3d: bool = False
    """Element has [transform-style:preserve-3d]."""

    has_backface_hidden: bool = False
    """Element has [backface-visibility:hidden]."""

    missing_recommended: List[str] = field(default_factory=list)
    """Classes the element should have but doesn't."""

    @property
    def is_positioned(self) -> bool:
        """Check if element has explicit positioning."""
        return self.has_relative or self.has_absolute or self.has_fixed

    @property
    def has_explicit_zindex(self) -> bool:
        """Check if element has explicit z-index."""
        return self.z_index is not None

    @property
    def is_stacking_context(self) -> bool:
        """Check if element creates a stacking context."""
        return self.is_positioned and self.has_explicit_zindex

    def get_position_classes(self) -> List[str]:
        """Get all position-related classes."""
        classes = []
        if self.has_relative:
            classes.append("relative")
        if self.has_absolute:
            classes.append("absolute")
        if self.has_fixed:
            classes.append("fixed")
        return classes

    def get_zindex_class(self) -> Optional[str]:
        """Get the z-index class if present."""
        for cls in self.all_classes:
            if cls.startswith("z-"):
                return cls
        return None


@dataclass
class ClassifiedError:
    """
    An error classified with full Tailwind context.

    Contains all information needed by fixers to generate appropriate patches.
    """

    error_type: ErrorType
    """Type of error detected."""

    selector: str
    """CSS selector for the affected element."""

    element_tag: str
    """HTML tag name (e.g., 'button', 'div')."""

    tailwind_info: TailwindInfo
    """Tailwind class information for this element."""

    bounding_box: Optional[Dict[str, float]] = None
    """Element's position and size {x, y, width, height}."""

    blocking_element: Optional[str] = None
    """Selector of element blocking this one (for POINTER_* errors)."""

    confidence: float = 1.0
    """Confidence score for this classification (0.0-1.0)."""

    line_number: Optional[int] = None
    """Line number in source HTML (if available)."""

    # Fix hints
    suggested_classes: List[str] = field(default_factory=list)
    """Tailwind classes that might fix this error."""

    classes_to_remove: List[str] = field(default_factory=list)
    """Tailwind classes that should be removed."""

    requires_llm: bool = False
    """Whether this error likely needs LLM for repair."""

    @property
    def has_blocking_element(self) -> bool:
        """Check if error involves a blocking element."""
        return self.blocking_element is not None

    def to_patch(self) -> TailwindPatch:
        """Convert error to a suggested patch."""
        return TailwindPatch(
            selector=self.selector,
            add_classes=self.suggested_classes.copy(),
            remove_classes=self.classes_to_remove.copy(),
            reason=f"Fix {self.error_type.value}",
        )

    def describe(self) -> str:
        """Generate human-readable description."""
        parts = [
            f"[{self.error_type.value}] {self.selector} <{self.element_tag}>",
        ]
        if self.blocking_element:
            parts.append(f"  Blocked by: {self.blocking_element}")
        if self.suggested_classes:
            parts.append(f"  Suggested: +{' '.join(self.suggested_classes)}")
        if self.classes_to_remove:
            parts.append(f"  Remove: -{' '.join(self.classes_to_remove)}")
        if self.confidence < 1.0:
            parts.append(f"  Confidence: {self.confidence:.0%}")
        return "\n".join(parts)


@dataclass
class FixResult:
    """
    Result of applying fixes to HTML.

    Tracks what was changed and whether the fix was successful.
    """

    success: bool
    """Whether fixes were applied successfully."""

    original_html: str
    """HTML before fixes."""

    fixed_html: Optional[str] = None
    """HTML after fixes (None if failed)."""

    patches_applied: List[TailwindPatch] = field(default_factory=list)
    """Patches that were applied."""

    errors_fixed: List[ClassifiedError] = field(default_factory=list)
    """Errors that were addressed by the patches."""

    errors_remaining: List[ClassifiedError] = field(default_factory=list)
    """Errors that could not be fixed."""

    validation_passed: bool = False
    """Whether the fixed HTML passed validation."""

    error_message: Optional[str] = None
    """Error message if fix failed."""

    @property
    def all_errors_fixed(self) -> bool:
        """Check if all errors were fixed."""
        return len(self.errors_remaining) == 0

    @property
    def fix_rate(self) -> float:
        """Calculate percentage of errors fixed."""
        total = len(self.errors_fixed) + len(self.errors_remaining)
        if total == 0:
            return 1.0
        return len(self.errors_fixed) / total

    def describe(self) -> str:
        """Generate human-readable summary."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [f"FixResult: {status}"]

        if self.patches_applied:
            lines.append(f"  Patches applied: {len(self.patches_applied)}")
        if self.errors_fixed:
            lines.append(f"  Errors fixed: {len(self.errors_fixed)}")
        if self.errors_remaining:
            lines.append(f"  Errors remaining: {len(self.errors_remaining)}")
        if self.validation_passed:
            lines.append("  Validation: PASSED")
        elif self.fixed_html:
            lines.append("  Validation: PENDING")
        if self.error_message:
            lines.append(f"  Error: {self.error_message}")

        return "\n".join(lines)
