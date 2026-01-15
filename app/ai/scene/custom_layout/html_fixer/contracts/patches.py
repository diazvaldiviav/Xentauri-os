"""
Patches - Data structures for Tailwind class modifications.

TailwindPatch is the atomic unit of HTML repair in this system.
Instead of injecting CSS rules, we modify Tailwind classes directly.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class TailwindPatch:
    """
    A patch that modifies Tailwind classes on an HTML element.

    Unlike CSS injection, this modifies the class attribute directly,
    which is more predictable and easier to rollback.

    Example:
        patch = TailwindPatch(
            selector=".option-btn",
            add_classes=["z-50", "pointer-events-auto"],
            remove_classes=["z-10"]
        )
    """

    selector: str
    """CSS selector to identify the target element(s)."""

    add_classes: List[str] = field(default_factory=list)
    """Tailwind classes to add to the element."""

    remove_classes: List[str] = field(default_factory=list)
    """Tailwind classes to remove from the element."""

    reason: Optional[str] = None
    """Optional explanation of why this patch is needed."""

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = {
            "selector": self.selector,
            "add": self.add_classes,
            "remove": self.remove_classes,
        }
        if self.reason:
            result["reason"] = self.reason
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "TailwindPatch":
        """Create from dictionary."""
        return cls(
            selector=data["selector"],
            add_classes=data.get("add", []),
            remove_classes=data.get("remove", []),
            reason=data.get("reason"),
        )

    def describe(self) -> str:
        """Generate human-readable description of the patch."""
        parts = []
        if self.add_classes:
            parts.append(f"Add: {' '.join(self.add_classes)}")
        if self.remove_classes:
            parts.append(f"Remove: {' '.join(self.remove_classes)}")
        description = f"{self.selector} → {', '.join(parts)}"
        if self.reason:
            description += f" ({self.reason})"
        return description

    def is_additive(self) -> bool:
        """Check if patch only adds classes (no removals)."""
        return len(self.add_classes) > 0 and len(self.remove_classes) == 0

    def is_removal(self) -> bool:
        """Check if patch only removes classes (no additions)."""
        return len(self.remove_classes) > 0 and len(self.add_classes) == 0

    def is_replacement(self) -> bool:
        """Check if patch both adds and removes classes."""
        return len(self.add_classes) > 0 and len(self.remove_classes) > 0

    def merge_with(self, other: "TailwindPatch") -> "TailwindPatch":
        """
        Merge with another patch for the same selector.

        Later additions override earlier removals and vice versa.
        """
        if self.selector != other.selector:
            raise ValueError("Cannot merge patches with different selectors")

        # Combine classes, with other taking precedence
        new_add = list(set(self.add_classes) | set(other.add_classes))
        new_remove = list(set(self.remove_classes) | set(other.remove_classes))

        # Remove conflicts: if we're adding a class, don't remove it
        new_remove = [c for c in new_remove if c not in new_add]

        return TailwindPatch(
            selector=self.selector,
            add_classes=new_add,
            remove_classes=new_remove,
            reason=other.reason or self.reason,
        )


@dataclass
class PatchSet:
    """
    A collection of patches to apply together.

    Provides utilities for merging, validation, and application tracking.
    """

    patches: List[TailwindPatch] = field(default_factory=list)
    """List of patches in this set."""

    source: str = "unknown"
    """Source of these patches (e.g., 'deterministic', 'llm', 'manual')."""

    def add(self, patch: TailwindPatch) -> None:
        """Add a patch, merging if same selector exists."""
        for i, existing in enumerate(self.patches):
            if existing.selector == patch.selector:
                self.patches[i] = existing.merge_with(patch)
                return
        self.patches.append(patch)

    def get_for_selector(self, selector: str) -> Optional[TailwindPatch]:
        """Get patch for a specific selector."""
        for patch in self.patches:
            if patch.selector == selector:
                return patch
        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "patches": [p.to_dict() for p in self.patches],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PatchSet":
        """Create from dictionary."""
        return cls(
            source=data.get("source", "unknown"),
            patches=[TailwindPatch.from_dict(p) for p in data.get("patches", [])],
        )

    def describe(self) -> str:
        """Generate human-readable description of all patches."""
        lines = [f"PatchSet ({self.source}): {len(self.patches)} patches"]
        for i, patch in enumerate(self.patches, 1):
            lines.append(f"  {i}. {patch.describe()}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.patches)

    def __iter__(self):
        return iter(self.patches)
