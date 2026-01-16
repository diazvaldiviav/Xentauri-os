"""
JSPatchApplier - Applies JavaScript patches to HTML.

Sprint 6: Modifies <script> tags and event handlers based on JSPatch objects.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from .contracts.js_patch import JSPatch, JSPatchType

logger = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    """Result of applying JavaScript patches."""

    success: bool
    """True if at least one patch was applied."""

    html: str
    """The modified HTML (or original if no patches applied)."""

    applied: List[JSPatch] = field(default_factory=list)
    """Patches that were successfully applied."""

    failed: List[Tuple[JSPatch, str]] = field(default_factory=list)
    """Patches that failed, with error messages."""

    def describe(self) -> str:
        """Generate human-readable description."""
        lines = [f"Applied: {len(self.applied)}, Failed: {len(self.failed)}"]

        if self.applied:
            lines.append("Applied patches:")
            for patch in self.applied:
                lines.append(f"  - {patch.describe()}")

        if self.failed:
            lines.append("Failed patches:")
            for patch, error in self.failed:
                lines.append(f"  - {patch.describe()}: {error}")

        return "\n".join(lines)


class JSPatchApplier:
    """
    Applies JavaScript patches to HTML.

    Handles different patch types:
    - ADD_FUNCTION: Add new function to <script> block
    - REPLACE_FUNCTION: Replace existing function code
    - FIX_DOM_REFERENCE: Update getElementById calls
    - MODIFY_HANDLER: Change onclick attributes
    - FIX_SYNTAX: Replace specific lines in scripts
    - ADD_VARIABLE: Add variable declaration
    """

    def apply(self, html: str, patches: List[JSPatch]) -> ApplyResult:
        """
        Apply all JavaScript patches to HTML.

        Args:
            html: Original HTML content
            patches: List of JSPatch objects to apply

        Returns:
            ApplyResult with modified HTML and status
        """
        current_html = html
        applied = []
        failed = []

        for patch in patches:
            try:
                result = self._apply_single(current_html, patch)
                if result:
                    current_html = result
                    applied.append(patch)
                    logger.debug(f"Applied patch: {patch.describe()}")
                else:
                    failed.append((patch, "No changes made"))
                    logger.warning(f"Patch made no changes: {patch.describe()}")
            except Exception as e:
                failed.append((patch, str(e)))
                logger.error(f"Failed to apply patch: {patch.describe()}, error: {e}")

        return ApplyResult(
            success=len(applied) > 0,
            html=current_html,
            applied=applied,
            failed=failed,
        )

    def _apply_single(self, html: str, patch: JSPatch) -> Optional[str]:
        """
        Apply a single patch to HTML.

        Args:
            html: Current HTML content
            patch: The patch to apply

        Returns:
            Modified HTML or None if patch couldn't be applied
        """
        soup = BeautifulSoup(html, "html.parser")

        if patch.patch_type == JSPatchType.ADD_FUNCTION:
            return self._add_function(soup, patch)

        elif patch.patch_type == JSPatchType.REPLACE_FUNCTION:
            return self._replace_function(soup, patch)

        elif patch.patch_type == JSPatchType.FIX_DOM_REFERENCE:
            return self._fix_dom_reference(soup, patch)

        elif patch.patch_type == JSPatchType.MODIFY_HANDLER:
            return self._modify_handler(soup, patch)

        elif patch.patch_type == JSPatchType.FIX_SYNTAX:
            return self._fix_syntax(soup, patch)

        elif patch.patch_type == JSPatchType.ADD_VARIABLE:
            return self._add_variable(soup, patch)

        logger.warning(f"Unknown patch type: {patch.patch_type}")
        return None

    def _add_function(self, soup: BeautifulSoup, patch: JSPatch) -> Optional[str]:
        """
        Add a new function to the last script block.

        If no inline script exists, creates a new <script> tag.
        """
        scripts = soup.find_all("script")

        # Find first inline script (no src attribute)
        inline_scripts = [s for s in scripts if not s.get("src")]

        if inline_scripts:
            # Add to last inline script
            target_script = inline_scripts[-1]
            current_content = target_script.string or ""

            # Add newlines for formatting
            new_content = f"{current_content}\n\n{patch.function_code}"
            target_script.string = new_content

        else:
            # Create new script block
            new_script = soup.new_tag("script")
            new_script.string = f"\n{patch.function_code}\n"

            # Add before </body> or at end
            if soup.body:
                soup.body.append(new_script)
            elif soup.html:
                soup.html.append(new_script)
            else:
                soup.append(new_script)

        return str(soup)

    def _replace_function(self, soup: BeautifulSoup, patch: JSPatch) -> Optional[str]:
        """
        Replace an existing function definition.

        Searches all inline scripts for the function and replaces it.
        """
        if not patch.function_name:
            return None

        # Pattern to match function definition
        # Handles: function name(), const name = function(), const name = () =>
        patterns = [
            rf"function\s+{re.escape(patch.function_name)}\s*\([^)]*\)\s*\{{[^}}]*\}}",
            rf"(const|let|var)\s+{re.escape(patch.function_name)}\s*=\s*function\s*\([^)]*\)\s*\{{[^}}]*\}}",
            rf"(const|let|var)\s+{re.escape(patch.function_name)}\s*=\s*\([^)]*\)\s*=>\s*\{{[^}}]*\}}",
        ]

        modified = False
        for script in soup.find_all("script"):
            if script.get("src"):
                continue

            content = script.string
            if not content:
                continue

            for pattern in patterns:
                if re.search(pattern, content, re.DOTALL):
                    new_content = re.sub(pattern, patch.function_code, content, flags=re.DOTALL)
                    if new_content != content:
                        script.string = new_content
                        modified = True
                        break

            if modified:
                break

        if modified:
            return str(soup)

        # Function not found - fall back to adding it
        logger.info(f"Function '{patch.function_name}' not found, adding instead")
        return self._add_function(soup, patch)

    def _fix_dom_reference(self, soup: BeautifulSoup, patch: JSPatch) -> Optional[str]:
        """
        Replace old DOM ID reference with new one in all scripts.

        Handles getElementById, querySelector, etc.
        """
        if not patch.old_reference or not patch.new_reference:
            return None

        modified = False

        # Patterns to replace
        replacements = [
            # getElementById
            (f"getElementById('{patch.old_reference}')",
             f"getElementById('{patch.new_reference}')"),
            (f'getElementById("{patch.old_reference}")',
             f'getElementById("{patch.new_reference}")'),

            # querySelector with ID
            (f"querySelector('#{patch.old_reference}')",
             f"querySelector('#{patch.new_reference}')"),
            (f'querySelector("#{patch.old_reference}")',
             f'querySelector("#{patch.new_reference}")'),
        ]

        for script in soup.find_all("script"):
            if script.get("src"):
                continue

            content = script.string
            if not content:
                continue

            new_content = content
            for old, new in replacements:
                if old in new_content:
                    new_content = new_content.replace(old, new)
                    modified = True

            if new_content != content:
                script.string = new_content

        if modified:
            return str(soup)

        return None

    def _modify_handler(self, soup: BeautifulSoup, patch: JSPatch) -> Optional[str]:
        """
        Modify an onclick/onchange/etc. attribute on an element.
        """
        if not patch.selector or not patch.new_handler:
            return None

        try:
            elements = soup.select(patch.selector)
            if not elements:
                logger.warning(f"Selector '{patch.selector}' not found")
                return None

            element = elements[0]

            # Find the handler attribute (onclick, onchange, etc.)
            handler_attrs = ["onclick", "onchange", "onsubmit", "onmouseover", "onkeydown"]
            for attr in handler_attrs:
                if element.has_attr(attr):
                    # If old_handler specified, check it matches
                    if patch.old_handler and element[attr] != patch.old_handler:
                        continue

                    element[attr] = patch.new_handler
                    return str(soup)

            # No existing handler found - add onclick
            element["onclick"] = patch.new_handler
            return str(soup)

        except Exception as e:
            logger.error(f"Error modifying handler: {e}")
            return None

    def _fix_syntax(self, soup: BeautifulSoup, patch: JSPatch) -> Optional[str]:
        """
        Fix syntax error at specific line in a script.

        Replaces lines from line_start to line_end with replacement_code.
        """
        if patch.script_index is None or patch.line_start is None:
            return None

        scripts = soup.find_all("script")
        inline_scripts = [s for s in scripts if not s.get("src")]

        if patch.script_index >= len(inline_scripts):
            logger.warning(f"Script index {patch.script_index} out of range")
            return None

        script = inline_scripts[patch.script_index]
        content = script.string
        if not content:
            return None

        lines = content.split("\n")
        line_end = patch.line_end if patch.line_end is not None else patch.line_start

        if patch.line_start < 1 or patch.line_start > len(lines):
            logger.warning(f"Line {patch.line_start} out of range")
            return None

        # Replace lines (1-indexed in patch, 0-indexed in list)
        start_idx = patch.line_start - 1
        end_idx = min(line_end, len(lines))

        new_lines = lines[:start_idx] + [patch.replacement_code] + lines[end_idx:]
        script.string = "\n".join(new_lines)

        return str(soup)

    def _add_variable(self, soup: BeautifulSoup, patch: JSPatch) -> Optional[str]:
        """
        Add a variable declaration to the beginning of the first script.
        """
        if not patch.function_code:
            return None

        scripts = soup.find_all("script")
        inline_scripts = [s for s in scripts if not s.get("src")]

        if inline_scripts:
            # Add to first inline script
            target_script = inline_scripts[0]
            current_content = target_script.string or ""

            # Add at the beginning
            new_content = f"{patch.function_code}\n{current_content}"
            target_script.string = new_content

        else:
            # Create new script block
            new_script = soup.new_tag("script")
            new_script.string = f"\n{patch.function_code}\n"

            if soup.body:
                # Insert at beginning of body
                soup.body.insert(0, new_script)
            else:
                soup.append(new_script)

        return str(soup)
