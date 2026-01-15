"""
Transform Detector - Detect 3D transform and backface visibility issues.

Identifies elements hidden by CSS transforms including:
- Backface-visibility with rotation > 90deg
- Scale(0) or very small scale
- Translate off-screen
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union

from ..contracts.errors import ErrorType


@dataclass
class BackfaceIssue:
    """Information about a backface visibility issue."""

    selector: str
    rotation_x: float
    rotation_y: float
    is_hidden: bool
    parent_has_preserve_3d: bool
    error_type: ErrorType = field(default=ErrorType.TRANSFORM_3D_HIDDEN)

    @property
    def suggested_fix(self) -> List[str]:
        """Get suggested Tailwind classes to fix this issue."""
        fixes = []
        if not self.parent_has_preserve_3d:
            fixes.append("[transform-style:preserve-3d]")  # For parent
        fixes.append("[backface-visibility:visible]")
        return fixes

    def describe(self) -> str:
        """Generate human-readable description."""
        return (
            f"Backface hidden at {self.selector}: "
            f"rotX={self.rotation_x:.1f}° rotY={self.rotation_y:.1f}° "
            f"(preserve-3d: {self.parent_has_preserve_3d})"
        )


@dataclass
class TransformIssue:
    """Information about a transform-based visibility issue."""

    selector: str
    transform: str
    is_offscreen: bool
    has_zero_scale: bool
    has_zero_dimensions: bool
    error_type: ErrorType = field(default=ErrorType.TRANSFORM_OFFSCREEN)

    @property
    def suggested_fix(self) -> List[str]:
        """Get suggested Tailwind classes to fix this issue."""
        if self.has_zero_scale:
            return ["scale-100"]
        if self.is_offscreen:
            return ["translate-x-0", "translate-y-0"]
        return []

    def describe(self) -> str:
        """Generate human-readable description."""
        issues = []
        if self.is_offscreen:
            issues.append("offscreen")
        if self.has_zero_scale:
            issues.append("scale(0)")
        if self.has_zero_dimensions:
            issues.append("zero dimensions")
        return f"Transform issue at {self.selector}: {', '.join(issues)}"


class TransformDetector:
    """
    Detects transform-related visibility issues.

    Uses Playwright to check actual computed transform values
    and determine if they cause visibility issues.
    """

    async def check_backface_visibility(
        self, page, selector: str
    ) -> Optional[BackfaceIssue]:
        """
        Check if element is hidden due to backface-visibility.

        Args:
            page: Playwright Page instance
            selector: CSS selector for target element

        Returns:
            BackfaceIssue if issue found, None otherwise
        """
        from .js_evaluators import JSEvaluators

        result = await page.evaluate(JSEvaluators.CHECK_BACKFACE_VISIBILITY, selector)

        if not result.get("found"):
            return None

        if result.get("hiddenByBackface"):
            return BackfaceIssue(
                selector=selector,
                rotation_x=result.get("rotationX", 0),
                rotation_y=result.get("rotationY", 0),
                is_hidden=True,
                parent_has_preserve_3d=result.get("parentHasPreserve3d", False),
            )

        return None

    async def check_transform_offscreen(
        self, page, selector: str
    ) -> Optional[TransformIssue]:
        """
        Check if element is hidden due to transform.

        Args:
            page: Playwright Page instance
            selector: CSS selector for target element

        Returns:
            TransformIssue if issue found, None otherwise
        """
        from .js_evaluators import JSEvaluators

        result = await page.evaluate(JSEvaluators.CHECK_TRANSFORM_OFFSCREEN, selector)

        if not result.get("found"):
            return None

        if result.get("isHiddenByTransform"):
            return TransformIssue(
                selector=selector,
                transform=result.get("transform", "none"),
                is_offscreen=result.get("offScreen", False),
                has_zero_scale=result.get("hasZeroScale", False),
                has_zero_dimensions=result.get("hasZeroDimensions", False),
            )

        return None

    async def detect_transform_issues(
        self, page, selectors: List[str]
    ) -> List[Union[BackfaceIssue, TransformIssue]]:
        """
        Check multiple elements for transform issues.

        Args:
            page: Playwright Page instance
            selectors: List of CSS selectors

        Returns:
            List of found issues
        """
        issues: List[Union[BackfaceIssue, TransformIssue]] = []

        for selector in selectors:
            # Check backface first
            backface = await self.check_backface_visibility(page, selector)
            if backface:
                issues.append(backface)
                continue

            # Check transform offscreen
            transform = await self.check_transform_offscreen(page, selector)
            if transform:
                issues.append(transform)

        return issues

    async def has_transform_issue(self, page, selector: str) -> bool:
        """
        Quick check if element has any transform issue.

        Args:
            page: Playwright Page instance
            selector: CSS selector for target element

        Returns:
            True if any transform issue found
        """
        backface = await self.check_backface_visibility(page, selector)
        if backface:
            return True

        transform = await self.check_transform_offscreen(page, selector)
        if transform:
            return True

        return False
