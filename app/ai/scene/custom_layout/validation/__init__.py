"""
Visual Validation Module - Eliminate false positives with screenshot comparison.

Sprint 6: Visual-based validation system.

This module provides a 7-phase validation pipeline:
1. Sandbox (Render check)
2. Visual Analysis (Screenshot + blank detection)
3. Scene Graph (DOM geometry extraction)
4. Input Detection (Find clickable elements)
5. Interaction Validation (Click + visual delta)
6. Aggregation (Decision logic)
7. Fixer (Direct Codex-Max repair)

Usage:
    from app.ai.scene.custom_layout.validation import (
        VisualValidator,
        ValidationContract,
        SandboxResult,
    )

    validator = VisualValidator()
    contract = ValidationContract(html=my_html, layout_type="trivia")
    result = await validator.validate(contract)

    if not result.valid:
        # Repair with Codex-Max
        repaired = await validator.repair(my_html, result, user_request)
"""

import logging
import time
from typing import Optional

from .contracts import (
    # Core types
    ValidationContract,
    SandboxResult,
    PhaseResult,
    # Geometric types
    BoundingBox,
    SceneNode,
    ObservedSceneGraph,
    # Visual types
    VisualSnapshot,
    VisualDelta,
    # Interaction types
    InputCandidate,
    InteractionResult,
)
from .sandbox import sandbox_renderer, RenderContext
from .visual_analyzer import visual_analyzer
from .scene_graph import scene_graph_extractor
from .input_detector import input_detector
from .interaction_validator import interaction_validator
from .aggregator import validation_aggregator
from .fixer import direct_fixer

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation")


# ---------------------------------------------------------------------------
# VISUAL VALIDATOR (Main Orchestrator)
# ---------------------------------------------------------------------------

class VisualValidator:
    """
    Main orchestrator for the 7-phase visual validation pipeline.

    Coordinates all phases and produces final SandboxResult.
    """

    async def validate(
        self,
        contract: ValidationContract,
    ) -> SandboxResult:
        """
        Run full validation pipeline on HTML.

        Args:
            contract: Validation contract with HTML and settings

        Returns:
            SandboxResult with validation decision
        """
        start_time = time.time()
        phases = []
        render_ctx: Optional[RenderContext] = None

        try:
            # =========================================================
            # PHASE 1: Sandbox Render
            # =========================================================
            phase1_result, render_ctx = await sandbox_renderer.render(contract)
            phases.append(phase1_result)

            if not phase1_result.passed or render_ctx is None:
                return self._build_failed_result(
                    phases=phases,
                    layout_type=contract.layout_type or "unknown",
                    start_time=start_time,
                )

            page = render_ctx.page

            # =========================================================
            # PHASE 2: Visual Analysis
            # =========================================================
            phase2_result, visual_snapshot = await visual_analyzer.analyze(page, contract)
            phases.append(phase2_result)

            if not phase2_result.passed:
                await render_ctx.close()
                return self._build_failed_result(
                    phases=phases,
                    layout_type=contract.layout_type or "unknown",
                    start_time=start_time,
                )

            # =========================================================
            # PHASE 3: Scene Graph Extraction
            # =========================================================
            phase3_result, scene_graph = await scene_graph_extractor.extract(page)
            phases.append(phase3_result)

            if not phase3_result.passed or scene_graph is None:
                await render_ctx.close()
                return self._build_failed_result(
                    phases=phases,
                    layout_type=contract.layout_type or "unknown",
                    start_time=start_time,
                )

            # =========================================================
            # PHASE 4: Input Detection
            # =========================================================
            phase4_result, inputs = await input_detector.detect(page, scene_graph, contract)
            phases.append(phase4_result)

            # Phase 4 always passes (no inputs = static content)

            # =========================================================
            # PHASE 5: Interaction Validation
            # =========================================================
            phase5_result, interaction_results = await interaction_validator.validate(
                page, inputs, contract
            )
            phases.append(phase5_result)

            # =========================================================
            # PHASE 6: Aggregation
            # =========================================================
            layout_type = contract.layout_type or self._detect_layout_type(scene_graph)

            result = validation_aggregator.aggregate(
                phases=phases,
                interaction_results=interaction_results,
                layout_type=layout_type,
            )

            # Update total duration
            result.total_duration_ms = (time.time() - start_time) * 1000

            return result

        except Exception as e:
            logger.error(f"Validation pipeline error: {e}", exc_info=True)
            phases.append(PhaseResult(
                phase=0,
                phase_name="pipeline",
                passed=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            ))
            return self._build_failed_result(
                phases=phases,
                layout_type=contract.layout_type or "unknown",
                start_time=start_time,
            )

        finally:
            # Always close browser
            if render_ctx:
                await render_ctx.close()

    async def repair(
        self,
        html: str,
        sandbox_result: SandboxResult,
        user_request: str,
        use_reasoning: bool = False,
    ) -> Optional[str]:
        """
        Repair HTML that failed validation.

        Args:
            html: HTML that failed validation
            sandbox_result: Validation result with failure details
            user_request: Original user request
            use_reasoning: Use extended reasoning (more expensive)

        Returns:
            Repaired HTML or None if repair failed
        """
        if use_reasoning:
            return await direct_fixer.repair_with_reasoning(
                html=html,
                sandbox_result=sandbox_result,
                user_request=user_request,
            )
        else:
            return await direct_fixer.repair(
                html=html,
                sandbox_result=sandbox_result,
                user_request=user_request,
            )

    def _build_failed_result(
        self,
        phases: list,
        layout_type: str,
        start_time: float,
    ) -> SandboxResult:
        """Build a failed SandboxResult."""
        failed_phase = next((p for p in phases if not p.passed), None)
        failure_summary = (
            f"Phase {failed_phase.phase} ({failed_phase.phase_name}) failed: {failed_phase.error}"
            if failed_phase else "Unknown failure"
        )

        return SandboxResult(
            valid=False,
            phases=phases,
            inputs_tested=0,
            inputs_responsive=0,
            confidence=0.0,
            layout_type=layout_type,
            total_duration_ms=(time.time() - start_time) * 1000,
            failure_summary=failure_summary,
        )

    def _detect_layout_type(self, scene_graph: ObservedSceneGraph) -> str:
        """
        Detect layout type from scene graph.

        Simple heuristics based on node attributes.
        """
        # Check for data attributes
        for node in scene_graph.nodes:
            if "data-trivia" in node.attributes or "data-question" in node.attributes:
                return "trivia"
            if "data-game" in node.attributes:
                return "mini_game"
            if "data-dashboard" in node.attributes:
                return "dashboard"

        # Check for interactive elements
        interactive_count = len(scene_graph.interactive_nodes())
        if interactive_count == 0:
            return "static"
        elif interactive_count > 5:
            return "dashboard"
        else:
            return "unknown"


# ---------------------------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------------------------

# Main validator
visual_validator = VisualValidator()

# Export all types
__all__ = [
    # Main orchestrator
    "VisualValidator",
    "visual_validator",
    # Contracts
    "ValidationContract",
    "SandboxResult",
    "PhaseResult",
    # Geometric types
    "BoundingBox",
    "SceneNode",
    "ObservedSceneGraph",
    # Visual types
    "VisualSnapshot",
    "VisualDelta",
    # Interaction types
    "InputCandidate",
    "InteractionResult",
    # Render context
    "RenderContext",
    # Individual components (for advanced usage)
    "sandbox_renderer",
    "visual_analyzer",
    "scene_graph_extractor",
    "input_detector",
    "interaction_validator",
    "validation_aggregator",
    "direct_fixer",
]
