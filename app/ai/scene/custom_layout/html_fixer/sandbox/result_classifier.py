"""
ResultClassifier - Classify interaction results semantically.

Sprint 5: Intelligent classification of visual changes based on
multi-scale diff analysis.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .diff_engine import DiffResult, ComparisonScale
from .contracts import ElementInfo


class InteractionClassification(Enum):
    """Semantic classification of interaction results."""

    RESPONSIVE = "responsive"
    """Click worked, clear visual feedback visible in element region."""

    NAVIGATION = "navigation"
    """Click triggered navigation (global change, new content)."""

    CASCADE_EFFECT = "cascade_effect"
    """Change detected elsewhere on page, not at element."""

    WEAK_FEEDBACK = "weak_feedback"
    """Some change detected but below threshold (too subtle)."""

    NO_RESPONSE = "no_response"
    """No visual change detected at any scale."""


@dataclass
class ClassificationResult:
    """Detailed classification with reasoning."""

    classification: InteractionClassification
    confidence: float  # 0.0-1.0
    reasoning: str
    primary_scale: ComparisonScale
    diff_ratios: Dict[str, float]  # {tight, local, global}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for reporting."""
        return {
            "classification": self.classification.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "primary_scale": self.primary_scale.value,
            "diff_ratios": self.diff_ratios,
        }


class ResultClassifier:
    """
    Classifies interaction results based on multi-scale diff analysis.

    Classification logic:
    1. RESPONSIVE: tight diff >= threshold (element changed visually)
    2. NAVIGATION: global diff >> local diff (page-wide change)
    3. CASCADE_EFFECT: local or global changed but NOT tight
    4. WEAK_FEEDBACK: tight > 0 but < threshold
    5. NO_RESPONSE: all diffs near zero

    Usage:
        classifier = ResultClassifier()
        result = classifier.classify(diff_result, element_info)
        print(result.classification, result.reasoning)
    """

    # Default thresholds
    RESPONSIVE_THRESHOLD = 0.02      # 2% tight change = responsive
    WEAK_THRESHOLD = 0.005           # 0.5% = weak but detected
    CASCADE_THRESHOLD = 0.01         # 1% change elsewhere
    NAVIGATION_THRESHOLD = 0.02      # 2% global for navigation check
    NAVIGATION_RATIO = 5.0           # global/local > 5 suggests navigation

    def __init__(
        self,
        responsive_threshold: float = RESPONSIVE_THRESHOLD,
        weak_threshold: float = WEAK_THRESHOLD,
        cascade_threshold: float = CASCADE_THRESHOLD,
        navigation_threshold: float = NAVIGATION_THRESHOLD,
        navigation_ratio: float = NAVIGATION_RATIO,
    ):
        """
        Initialize the classifier.

        Args:
            responsive_threshold: Min tight diff for RESPONSIVE
            weak_threshold: Min tight diff for WEAK_FEEDBACK
            cascade_threshold: Min local/global diff for CASCADE_EFFECT
            navigation_threshold: Min global diff for NAVIGATION check
            navigation_ratio: global/local ratio threshold for NAVIGATION
        """
        self.responsive_threshold = responsive_threshold
        self.weak_threshold = weak_threshold
        self.cascade_threshold = cascade_threshold
        self.navigation_threshold = navigation_threshold
        self.navigation_ratio = navigation_ratio

    def classify(
        self,
        diff_result: DiffResult,
        element: Optional[ElementInfo] = None,
    ) -> ClassificationResult:
        """
        Classify the interaction result.

        Args:
            diff_result: Multi-scale diff from DiffEngine
            element: Element that was clicked (optional, for context)

        Returns:
            ClassificationResult with semantic label and reasoning
        """
        tight = diff_result.tight.diff_ratio
        local = diff_result.local.diff_ratio
        global_ = diff_result.global_.diff_ratio

        diff_ratios = {
            "tight": tight,
            "local": local,
            "global": global_,
        }

        # 1. Check for RESPONSIVE (direct element feedback)
        if tight >= self.responsive_threshold:
            return ClassificationResult(
                classification=InteractionClassification.RESPONSIVE,
                confidence=min(1.0, tight / self.responsive_threshold),
                reasoning=(
                    f"Element showed clear visual feedback "
                    f"({tight:.1%} change in tight region)"
                ),
                primary_scale=ComparisonScale.TIGHT,
                diff_ratios=diff_ratios,
            )

        # 2. Check for NAVIGATION (page-wide change)
        if global_ >= self.navigation_threshold:
            # Is it disproportionately global vs local?
            ratio = global_ / local if local > 0 else float('inf')
            if ratio > self.navigation_ratio:
                return ClassificationResult(
                    classification=InteractionClassification.NAVIGATION,
                    confidence=0.8,
                    reasoning=(
                        f"Page-wide change detected ({global_:.1%}), "
                        f"likely navigation or major state change"
                    ),
                    primary_scale=ComparisonScale.GLOBAL,
                    diff_ratios=diff_ratios,
                )

        # 3. Check for CASCADE_EFFECT (change elsewhere)
        if local >= self.cascade_threshold and tight < self.weak_threshold:
            return ClassificationResult(
                classification=InteractionClassification.CASCADE_EFFECT,
                confidence=0.7,
                reasoning=(
                    f"Change detected outside element "
                    f"({local:.1%} local, {tight:.1%} tight)"
                ),
                primary_scale=ComparisonScale.LOCAL,
                diff_ratios=diff_ratios,
            )

        if global_ >= self.cascade_threshold and tight < self.weak_threshold:
            return ClassificationResult(
                classification=InteractionClassification.CASCADE_EFFECT,
                confidence=0.6,
                reasoning=(
                    f"Global change without element change ({global_:.1%})"
                ),
                primary_scale=ComparisonScale.GLOBAL,
                diff_ratios=diff_ratios,
            )

        # 4. Check for WEAK_FEEDBACK
        if tight >= self.weak_threshold:
            return ClassificationResult(
                classification=InteractionClassification.WEAK_FEEDBACK,
                confidence=tight / self.responsive_threshold,
                reasoning=(
                    f"Subtle feedback detected ({tight:.1%}) but below "
                    f"{self.responsive_threshold:.1%} threshold"
                ),
                primary_scale=ComparisonScale.TIGHT,
                diff_ratios=diff_ratios,
            )

        # 5. NO_RESPONSE - nothing detected
        return ClassificationResult(
            classification=InteractionClassification.NO_RESPONSE,
            confidence=1.0 - max(tight, local, global_),
            reasoning=(
                f"No visual change detected "
                f"(tight={tight:.3%}, local={local:.3%}, global={global_:.3%})"
            ),
            primary_scale=ComparisonScale.TIGHT,
            diff_ratios=diff_ratios,
        )

    def is_passing(self, classification: InteractionClassification) -> bool:
        """
        Check if a classification counts as passing validation.

        RESPONSIVE, NAVIGATION, and CASCADE_EFFECT are considered passing
        because they indicate the element triggered some visual response.

        Args:
            classification: The classification to check

        Returns:
            True if the classification is considered passing
        """
        return classification in (
            InteractionClassification.RESPONSIVE,
            InteractionClassification.NAVIGATION,
            InteractionClassification.CASCADE_EFFECT,
        )

    def classify_from_ratios(
        self,
        tight: float,
        local: float,
        global_: float,
    ) -> ClassificationResult:
        """
        Convenience method to classify from raw diff ratios.

        Useful for testing or when you don't have a full DiffResult.

        Args:
            tight: Tight region diff ratio
            local: Local region diff ratio
            global_: Global diff ratio

        Returns:
            ClassificationResult
        """
        # Create a minimal DiffResult
        from .diff_engine import RegionDiff

        diff_result = DiffResult(
            tight=RegionDiff(
                ComparisonScale.TIGHT, tight, int(tight * 1000), 1000
            ),
            local=RegionDiff(
                ComparisonScale.LOCAL, local, int(local * 5000), 5000
            ),
            global_=RegionDiff(
                ComparisonScale.GLOBAL, global_, int(global_ * 50000), 50000
            ),
            element_box={"x": 0, "y": 0, "width": 100, "height": 50},
            has_significant_change=(
                tight >= self.responsive_threshold or
                local >= self.responsive_threshold or
                global_ >= self.responsive_threshold
            ),
            primary_change_location=ComparisonScale.TIGHT,
        )

        return self.classify(diff_result)
