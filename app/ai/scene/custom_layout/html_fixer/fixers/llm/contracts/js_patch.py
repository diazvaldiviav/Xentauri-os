"""
JSPatch - Data structures for JavaScript code modifications.

Sprint 6: LLM-generated patches for JavaScript errors.
Unlike TailwindPatch which modifies class attributes,
JSPatch modifies JavaScript code in <script> tags or event handlers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class JSPatchType(Enum):
    """Types of JavaScript patches."""

    ADD_FUNCTION = "add_function"
    """Add a new function definition to <script> block."""

    REPLACE_FUNCTION = "replace_function"
    """Replace an existing function implementation."""

    FIX_SYNTAX = "fix_syntax"
    """Fix syntax error at specific location."""

    FIX_DOM_REFERENCE = "fix_dom_reference"
    """Replace getElementById('wrong') with correct ID."""

    ADD_VARIABLE = "add_variable"
    """Add missing variable declaration."""

    MODIFY_HANDLER = "modify_handler"
    """Modify onclick="..." attribute value."""


@dataclass
class JSPatch:
    """
    A patch that modifies JavaScript code in HTML.

    Unlike TailwindPatch which only modifies class attributes,
    JSPatch can modify script content or add new script blocks.

    Example:
        patch = JSPatch(
            patch_type=JSPatchType.ADD_FUNCTION,
            function_name="handleClick",
            function_code="function handleClick() { alert('clicked'); }"
        )
    """

    patch_type: JSPatchType
    """Type of JavaScript modification."""

    # For function-related patches
    function_name: Optional[str] = None
    """Name of the function to add/replace."""

    function_code: Optional[str] = None
    """Complete function code (including 'function' keyword)."""

    # For DOM reference fixes
    old_reference: Optional[str] = None
    """The incorrect DOM ID (e.g., 'result')."""

    new_reference: Optional[str] = None
    """The correct DOM ID (e.g., 'output')."""

    # For inline handler modifications
    selector: Optional[str] = None
    """CSS selector for element with handler to modify."""

    old_handler: Optional[str] = None
    """Original handler code."""

    new_handler: Optional[str] = None
    """New handler code."""

    # For script block modifications
    script_index: Optional[int] = None
    """Which <script> tag to modify (0-indexed)."""

    line_start: Optional[int] = None
    """Starting line number for replacement."""

    line_end: Optional[int] = None
    """Ending line number for replacement."""

    replacement_code: Optional[str] = None
    """Code to insert at specified location."""

    # Metadata
    reason: Optional[str] = None
    """Explanation of why this patch is needed."""

    confidence: float = 1.0
    """Confidence score (0.0-1.0)."""

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = {
            "type": self.patch_type.value,
        }

        if self.function_name:
            result["function_name"] = self.function_name
        if self.function_code:
            result["function_code"] = self.function_code
        if self.old_reference:
            result["old_reference"] = self.old_reference
        if self.new_reference:
            result["new_reference"] = self.new_reference
        if self.selector:
            result["selector"] = self.selector
        if self.old_handler:
            result["old_handler"] = self.old_handler
        if self.new_handler:
            result["new_handler"] = self.new_handler
        if self.script_index is not None:
            result["script_index"] = self.script_index
        if self.line_start is not None:
            result["line_start"] = self.line_start
        if self.line_end is not None:
            result["line_end"] = self.line_end
        if self.replacement_code:
            result["replacement_code"] = self.replacement_code
        if self.reason:
            result["reason"] = self.reason

        result["confidence"] = self.confidence

        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "JSPatch":
        """Create from dictionary."""
        return cls(
            patch_type=JSPatchType(data["type"]),
            function_name=data.get("function_name"),
            function_code=data.get("function_code"),
            old_reference=data.get("old_reference"),
            new_reference=data.get("new_reference"),
            selector=data.get("selector"),
            old_handler=data.get("old_handler"),
            new_handler=data.get("new_handler"),
            script_index=data.get("script_index"),
            line_start=data.get("line_start"),
            line_end=data.get("line_end"),
            replacement_code=data.get("replacement_code"),
            reason=data.get("reason"),
            confidence=data.get("confidence", 1.0),
        )

    def describe(self) -> str:
        """Generate human-readable description of the patch."""
        parts = [f"[{self.patch_type.value}]"]

        if self.patch_type == JSPatchType.ADD_FUNCTION:
            parts.append(f"Add function '{self.function_name}'")
        elif self.patch_type == JSPatchType.REPLACE_FUNCTION:
            parts.append(f"Replace function '{self.function_name}'")
        elif self.patch_type == JSPatchType.FIX_SYNTAX:
            parts.append(f"Fix syntax at line {self.line_start}")
        elif self.patch_type == JSPatchType.FIX_DOM_REFERENCE:
            parts.append(f"Change '{self.old_reference}' -> '{self.new_reference}'")
        elif self.patch_type == JSPatchType.ADD_VARIABLE:
            parts.append(f"Add variable declaration")
        elif self.patch_type == JSPatchType.MODIFY_HANDLER:
            parts.append(f"Modify handler on {self.selector}")

        if self.reason:
            parts.append(f"({self.reason})")

        return " ".join(parts)

    def is_function_patch(self) -> bool:
        """Check if patch adds or modifies functions."""
        return self.patch_type in (
            JSPatchType.ADD_FUNCTION,
            JSPatchType.REPLACE_FUNCTION,
        )

    def is_reference_patch(self) -> bool:
        """Check if patch fixes DOM references."""
        return self.patch_type == JSPatchType.FIX_DOM_REFERENCE

    def is_handler_patch(self) -> bool:
        """Check if patch modifies event handlers."""
        return self.patch_type == JSPatchType.MODIFY_HANDLER


@dataclass
class JSPatchSet:
    """
    A collection of JavaScript patches to apply together.

    Provides utilities for grouping and applying patches.
    """

    patches: List[JSPatch] = field(default_factory=list)
    """List of patches in this set."""

    source: str = "llm"
    """Source of these patches (e.g., 'llm', 'manual')."""

    def add(self, patch: JSPatch) -> None:
        """Add a patch to the set."""
        self.patches.append(patch)

    def get_function_patches(self) -> List[JSPatch]:
        """Get all function-related patches."""
        return [p for p in self.patches if p.is_function_patch()]

    def get_reference_patches(self) -> List[JSPatch]:
        """Get all DOM reference patches."""
        return [p for p in self.patches if p.is_reference_patch()]

    def get_handler_patches(self) -> List[JSPatch]:
        """Get all handler modification patches."""
        return [p for p in self.patches if p.is_handler_patch()]

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "patches": [p.to_dict() for p in self.patches],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "JSPatchSet":
        """Create from dictionary."""
        return cls(
            source=data.get("source", "llm"),
            patches=[JSPatch.from_dict(p) for p in data.get("patches", [])],
        )

    def describe(self) -> str:
        """Generate human-readable description of all patches."""
        lines = [f"JSPatchSet ({self.source}): {len(self.patches)} patches"]
        for i, patch in enumerate(self.patches, 1):
            lines.append(f"  {i}. {patch.describe()}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.patches)

    def __iter__(self):
        return iter(self.patches)
