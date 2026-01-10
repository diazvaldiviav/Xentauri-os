"""
Validation Aggregator - Phase 6: Decision logic.

Sprint 6: Visual-based validation system.

This module aggregates all phase results into a final decision.

Decision Policy:
- Phases 1-4 must pass (render, visual, scene_graph, input_detection)
- Phase 5 (interaction): At least 1 responsive input for interactive types
- Static content: Phase 5 not required

Confidence calculation:
- Based on % of responsive inputs
- Adjusted by phase warnings
"""

import logging
from typing import List

from .contracts import (
    InteractionResult,
    PhaseResult,
    SandboxResult,
)

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.aggregator")


# ---------------------------------------------------------------------------
# LAYOUT TYPE CLASSIFICATION
# ---------------------------------------------------------------------------

# Layout types that don't require interactive elements
# (Phase 5 is skipped entirely for these in __init__.py)
STATIC_LAYOUT_TYPES = {"static", "info", "display", "content"}

# Minimum ratio of responsive inputs to pass validation
# 70% of tested inputs must respond to clicks
MIN_RESPONSIVE_RATIO = 0.70


# ---------------------------------------------------------------------------
# VALIDATION AGGREGATOR
# ---------------------------------------------------------------------------

class ValidationAggregator:
    """
    Phase 6: Aggregate all phase results into final decision.

    Uses simple, deterministic logic:
    - All critical phases must pass
    - Interactive layouts need at least 1 working input
    - Static layouts don't need interaction validation
    """

    def aggregate(
        self,
        phases: List[PhaseResult],
        interaction_results: List[InteractionResult],
        layout_type: str,
    ) -> SandboxResult:
        """
        Aggregate phase results into final SandboxResult.

        Args:
            phases: Results from phases 1-4
            interaction_results: Results from phase 5
            layout_type: Detected layout type

        Returns:
            SandboxResult with final decision
        """
        total_duration = sum(p.duration_ms for p in phases)

        # Count interaction metrics
        inputs_tested = len(interaction_results)
        inputs_responsive = sum(1 for r in interaction_results if r.responsive)

        # Check critical phases (1-4)
        critical_phases = [p for p in phases if p.phase <= 4]
        failed_critical = [p for p in critical_phases if not p.passed]

        if failed_critical:
            # Critical phase failed
            first_failure = failed_critical[0]
            logger.warning(
                f"Validation FAILED at Phase {first_failure.phase} ({first_failure.phase_name}): "
                f"{first_failure.error}"
            )

            return SandboxResult(
                valid=False,
                phases=phases,
                inputs_tested=inputs_tested,
                inputs_responsive=inputs_responsive,
                confidence=0.0,
                layout_type=layout_type,
                total_duration_ms=total_duration,
                failure_summary=f"Phase {first_failure.phase} ({first_failure.phase_name}) failed: {first_failure.error}",
                interaction_results=interaction_results,
            )

        # Check interaction phase for any layout with detected inputs
        # ─────────────────────────────────────────────────────────────
        # "Si el sistema vio un botón, ese botón debe responder.
        #  Ningún nombre lo exime de funcionar."
        # ─────────────────────────────────────────────────────────────
        # Sprint 6.1 Fix: The layout type name is irrelevant.
        # If inputs were detected and tested, they must work.
        if inputs_tested > 0:
            responsive_ratio = inputs_responsive / inputs_tested

            if inputs_responsive == 0:
                # No inputs respond at all
                logger.warning(
                    f"Validation FAILED: Interactive layout '{layout_type}' "
                    f"has no responsive inputs ({inputs_tested} tested)"
                )

                return SandboxResult(
                    valid=False,
                    phases=phases,
                    inputs_tested=inputs_tested,
                    inputs_responsive=inputs_responsive,
                    confidence=0.0,
                    layout_type=layout_type,
                    total_duration_ms=total_duration,
                    failure_summary=f"No inputs responded to interaction ({inputs_tested} tested)",
                    interaction_results=interaction_results,
                )

            if responsive_ratio < MIN_RESPONSIVE_RATIO:
                # Not enough inputs respond (need at least 70%)
                logger.warning(
                    f"Validation FAILED: Only {responsive_ratio:.0%} inputs responsive "
                    f"({inputs_responsive}/{inputs_tested}), need {MIN_RESPONSIVE_RATIO:.0%}"
                )

                return SandboxResult(
                    valid=False,
                    phases=phases,
                    inputs_tested=inputs_tested,
                    inputs_responsive=inputs_responsive,
                    confidence=responsive_ratio,
                    layout_type=layout_type,
                    total_duration_ms=total_duration,
                    failure_summary=f"Only {inputs_responsive}/{inputs_tested} inputs responsive ({responsive_ratio:.0%}), need {MIN_RESPONSIVE_RATIO:.0%}",
                    interaction_results=interaction_results,
                )

        # Calculate confidence
        confidence = self._calculate_confidence(
            phases=phases,
            inputs_tested=inputs_tested,
            inputs_responsive=inputs_responsive,
            layout_type=layout_type,
        )

        # Determine if there are any warnings
        warnings = []
        for p in phases:
            if p.details.get("warnings"):
                warnings.extend(p.details["warnings"])

        # All checks passed
        logger.info(
            f"Validation PASSED - "
            f"layout={layout_type}, "
            f"inputs={inputs_responsive}/{inputs_tested}, "
            f"confidence={confidence:.2f}"
        )

        return SandboxResult(
            valid=True,
            phases=phases,
            inputs_tested=inputs_tested,
            inputs_responsive=inputs_responsive,
            confidence=confidence,
            layout_type=layout_type,
            total_duration_ms=total_duration,
            interaction_results=interaction_results,
        )

    def _calculate_confidence(
        self,
        phases: List[PhaseResult],
        inputs_tested: int,
        inputs_responsive: int,
        layout_type: str,
    ) -> float:
        """
        Calculate confidence score (0.0 - 1.0).

        Factors:
        - Percentage of responsive inputs
        - Phase warnings (reduce confidence)
        - Layout type expectations
        """
        base_confidence = 1.0

        # Adjust for input responsiveness
        if inputs_tested > 0:
            input_ratio = inputs_responsive / inputs_tested
            # Weight: 50% of confidence based on input ratio
            base_confidence = 0.5 + (0.5 * input_ratio)
        else:
            # No inputs tested
            if layout_type.lower() in STATIC_LAYOUT_TYPES:
                # Static content - high confidence is fine
                base_confidence = 0.9
            else:
                # Non-static with no inputs - moderate confidence
                base_confidence = 0.6

        # Reduce for phase warnings
        warning_count = sum(
            len(p.details.get("warnings", [])) for p in phases
        )
        if warning_count > 0:
            # Each warning reduces confidence by 5%, max 20% reduction
            warning_penalty = min(warning_count * 0.05, 0.20)
            base_confidence -= warning_penalty

        # Ensure confidence is in valid range
        return max(0.0, min(1.0, base_confidence))


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

validation_aggregator = ValidationAggregator()
