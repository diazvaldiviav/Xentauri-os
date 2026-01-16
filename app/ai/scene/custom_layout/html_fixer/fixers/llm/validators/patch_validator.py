"""
PatchValidator - Orchestrates validation of LLM-generated patches.

Sprint 6: Routes patches to appropriate validators based on type.
"""

import logging
from typing import List, Union

from ....contracts.patches import TailwindPatch
from ..contracts.js_patch import JSPatch
from .tailwind_validator import TailwindPatchValidator
from .js_validator import JSPatchValidator

logger = logging.getLogger(__name__)


class PatchValidator:
    """
    Orchestrates validation of LLM-generated patches.

    Routes patches to the appropriate specialized validator
    based on their type.
    """

    def __init__(
        self,
        tailwind_validator: TailwindPatchValidator = None,
        js_validator: JSPatchValidator = None,
    ):
        """
        Initialize the patch validator.

        Args:
            tailwind_validator: Optional custom Tailwind validator
            js_validator: Optional custom JS validator
        """
        self._tailwind_validator = tailwind_validator or TailwindPatchValidator()
        self._js_validator = js_validator or JSPatchValidator()

    def validate(
        self,
        patch: Union[TailwindPatch, JSPatch],
        html: str,
    ) -> bool:
        """
        Validate a single patch.

        Args:
            patch: The patch to validate
            html: Original HTML content

        Returns:
            True if patch is valid, False otherwise
        """
        if isinstance(patch, TailwindPatch):
            return self._tailwind_validator.validate(patch, html)
        elif isinstance(patch, JSPatch):
            return self._js_validator.validate(patch, html)
        else:
            logger.warning(f"Unknown patch type: {type(patch)}")
            return False

    def validate_batch(
        self,
        patches: List[Union[TailwindPatch, JSPatch]],
        html: str,
        domain: str = None,
    ) -> List[Union[TailwindPatch, JSPatch]]:
        """
        Validate multiple patches and return only valid ones.

        Args:
            patches: List of patches to validate
            html: Original HTML content
            domain: Optional domain filter ('tailwind' or 'js')

        Returns:
            List of valid patches
        """
        valid = []

        for patch in patches:
            # Filter by domain if specified
            if domain:
                if domain == "tailwind" and not isinstance(patch, TailwindPatch):
                    continue
                if domain == "js" and not isinstance(patch, JSPatch):
                    continue

            if self.validate(patch, html):
                valid.append(patch)
            else:
                patch_desc = patch.describe() if hasattr(patch, 'describe') else str(patch)
                logger.info(f"Rejected invalid patch: {patch_desc}")

        return valid

    def validate_tailwind_patches(
        self,
        patches: List[TailwindPatch],
        html: str,
    ) -> List[TailwindPatch]:
        """
        Validate Tailwind patches only.

        Args:
            patches: List of TailwindPatch objects
            html: Original HTML content

        Returns:
            List of valid TailwindPatch objects
        """
        return self._tailwind_validator.validate_batch(patches, html)

    def validate_js_patches(
        self,
        patches: List[JSPatch],
        html: str,
    ) -> List[JSPatch]:
        """
        Validate JavaScript patches only.

        Args:
            patches: List of JSPatch objects
            html: Original HTML content

        Returns:
            List of valid JSPatch objects
        """
        valid = []
        for patch in patches:
            if self._js_validator.validate(patch, html):
                valid.append(patch)
        return valid
