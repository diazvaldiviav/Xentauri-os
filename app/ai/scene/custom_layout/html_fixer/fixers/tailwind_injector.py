"""
TailwindInjector - Applies TailwindPatch to HTML.

Uses BeautifulSoup to modify class attributes based on patches.
Unlike CSS injection, this modifies the class attribute directly,
which is more predictable and easier to rollback.

Usage:
    from html_fixer.fixers import TailwindInjector
    from html_fixer.contracts.patches import TailwindPatch, PatchSet

    injector = TailwindInjector()
    result = injector.inject(html, patch_set)
    if result.success:
        fixed_html = result.html
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import logging

from bs4 import BeautifulSoup, Tag

from ..contracts.patches import TailwindPatch, PatchSet


logger = logging.getLogger(__name__)


@dataclass
class InjectionResult:
    """
    Result of applying patches to HTML.

    Attributes:
        success: Whether at least one patch was applied successfully
        html: Modified HTML string
        applied: List of successfully applied patches
        failed: List of (patch, error_message) tuples for failed patches
    """

    success: bool
    html: str
    applied: List[TailwindPatch] = field(default_factory=list)
    failed: List[Tuple[TailwindPatch, str]] = field(default_factory=list)

    @property
    def all_applied(self) -> bool:
        """Check if all patches were applied."""
        return len(self.failed) == 0

    @property
    def applied_count(self) -> int:
        """Number of patches applied."""
        return len(self.applied)

    @property
    def failed_count(self) -> int:
        """Number of patches that failed."""
        return len(self.failed)

    def describe(self) -> str:
        """Generate human-readable summary."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"InjectionResult: {status}",
            f"  Applied: {len(self.applied)} patches",
        ]
        if self.failed:
            lines.append(f"  Failed: {len(self.failed)} patches")
            for patch, error in self.failed[:5]:
                lines.append(f"    - {patch.selector}: {error}")
            if len(self.failed) > 5:
                lines.append(f"    ... and {len(self.failed) - 5} more")
        return "\n".join(lines)


class TailwindInjector:
    """
    Applies Tailwind class patches to HTML.

    This class modifies HTML by adding/removing Tailwind classes
    from elements' class attributes using BeautifulSoup.

    Features:
    - Apply single or multiple patches
    - Automatic z-index deduplication
    - Preview changes before applying
    - Detailed result tracking
    """

    def __init__(self, preserve_formatting: bool = False):
        """
        Initialize the injector.

        Args:
            preserve_formatting: If True, use prettify() for output
                                 (may change whitespace)
        """
        self._preserve_formatting = preserve_formatting

    def inject(
        self,
        html: str,
        patches: PatchSet,
    ) -> InjectionResult:
        """
        Apply all patches to HTML.

        Args:
            html: Original HTML string
            patches: PatchSet to apply

        Returns:
            InjectionResult with modified HTML and status
        """
        soup = BeautifulSoup(html, "html.parser")
        applied: List[TailwindPatch] = []
        failed: List[Tuple[TailwindPatch, str]] = []

        for patch in patches:
            try:
                count = self._apply_patch(soup, patch)
                if count > 0:
                    applied.append(patch)
                    logger.debug(
                        f"Applied patch to {count} element(s): {patch.selector}"
                    )
                else:
                    failed.append((patch, "No matching elements found"))
            except Exception as e:
                failed.append((patch, str(e)))
                logger.warning(f"Failed to apply patch {patch.selector}: {e}")

        # Generate output HTML
        if self._preserve_formatting:
            output_html = soup.prettify()
        else:
            output_html = str(soup)

        # Success if at least one patch applied or no patches to apply
        success = len(applied) > 0 or len(patches) == 0

        return InjectionResult(
            success=success,
            html=output_html,
            applied=applied,
            failed=failed,
        )

    def inject_single(
        self,
        html: str,
        patch: TailwindPatch,
    ) -> InjectionResult:
        """
        Apply a single patch to HTML.

        Args:
            html: Original HTML string
            patch: Single TailwindPatch to apply

        Returns:
            InjectionResult
        """
        patch_set = PatchSet(patches=[patch], source="single")
        return self.inject(html, patch_set)

    def _apply_patch(self, soup: BeautifulSoup, patch: TailwindPatch) -> int:
        """
        Apply a single patch to the soup.

        Args:
            soup: BeautifulSoup instance to modify
            patch: Patch to apply

        Returns:
            Number of elements modified
        """
        try:
            elements = soup.select(patch.selector)
        except Exception as e:
            logger.error(f"Invalid selector '{patch.selector}': {e}")
            return 0

        if not elements:
            logger.debug(f"No elements found for selector: {patch.selector}")
            return 0

        for element in elements:
            self._modify_classes(element, patch)

        return len(elements)

    def _modify_classes(self, element: Tag, patch: TailwindPatch) -> None:
        """
        Modify classes on a single element.

        Args:
            element: BeautifulSoup Tag to modify
            patch: Patch with add/remove classes
        """
        # Get current classes
        current_classes = element.get("class", [])
        if isinstance(current_classes, str):
            current_classes = current_classes.split()

        # Create mutable list
        new_classes = list(current_classes)

        # Remove classes
        for cls in patch.remove_classes:
            while cls in new_classes:
                new_classes.remove(cls)

        # Handle z-index replacement (remove old z-* when adding new)
        if any(cls.startswith("z-") for cls in patch.add_classes):
            new_classes = self._deduplicate_zindex(new_classes, patch.add_classes)

        # Add classes (avoid duplicates)
        for cls in patch.add_classes:
            if cls not in new_classes:
                new_classes.append(cls)

        # Update element
        if new_classes:
            element["class"] = new_classes
        elif "class" in element.attrs:
            del element["class"]

    def _deduplicate_zindex(
        self,
        classes: List[str],
        added: List[str],
    ) -> List[str]:
        """
        Remove old z-index classes when new ones are added.

        Args:
            classes: Current class list
            added: Classes being added

        Returns:
            Deduplicated class list
        """
        added_z = [c for c in added if c.startswith("z-")]
        if not added_z:
            return classes

        # Keep only the newly added z-index classes
        result = []
        for cls in classes:
            if cls.startswith("z-") and cls not in added_z:
                continue  # Remove old z-index
            result.append(cls)

        return result

    def preview_changes(
        self,
        html: str,
        patches: PatchSet,
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Preview changes without modifying HTML.

        Args:
            html: Original HTML
            patches: Patches to preview

        Returns:
            Dict mapping selector to {before: [...], after: [...], add: [...], remove: [...]}
        """
        soup = BeautifulSoup(html, "html.parser")
        preview: Dict[str, Dict[str, List[str]]] = {}

        for patch in patches:
            try:
                elements = soup.select(patch.selector)
            except Exception:
                continue

            if not elements:
                preview[patch.selector] = {
                    "before": [],
                    "after": [],
                    "add": patch.add_classes,
                    "remove": patch.remove_classes,
                    "error": "No matching elements",
                }
                continue

            element = elements[0]  # Preview first match
            current = list(element.get("class", []))

            after = list(current)
            for cls in patch.remove_classes:
                while cls in after:
                    after.remove(cls)

            # Handle z-index deduplication in preview
            if any(cls.startswith("z-") for cls in patch.add_classes):
                after = self._deduplicate_zindex(after, patch.add_classes)

            for cls in patch.add_classes:
                if cls not in after:
                    after.append(cls)

            preview[patch.selector] = {
                "before": current,
                "after": after,
                "add": patch.add_classes,
                "remove": patch.remove_classes,
            }

        return preview

    def __repr__(self) -> str:
        return f"TailwindInjector(preserve_formatting={self._preserve_formatting})"
