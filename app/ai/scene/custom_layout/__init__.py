"""
Custom Layout Module - HTML Generation, Validation, and Repair.

This module provides:
1. HTMLGenerator: Generate HTML using Gemini 3 Pro with thinking
2. html_fixer: Validate and repair HTML using Playwright + Gemini 3 Flash
3. CustomLayoutPipeline: Complete pipeline combining generation and repair

Usage:
======
    # Full pipeline (recommended)
    from app.ai.scene.custom_layout import custom_layout_pipeline

    pipeline = custom_layout_pipeline()
    result = await pipeline.process(
        user_request="Show me trivia about history",
        info_type="trivia",
    )

    if result.success:
        html = result.html

    # Generator only
    from app.ai.scene.custom_layout.generator import HTMLGenerator

    generator = HTMLGenerator()
    result = await generator.generate(user_request="Show me trivia")

    # Validator only
    from app.ai.scene.custom_layout.html_fixer.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    result = await orchestrator.fix(html)
"""

# New pipeline (primary interface)
from app.ai.scene.custom_layout.pipeline import (
    CustomLayoutPipeline,
    custom_layout_pipeline,
    get_pipeline,
)
from app.ai.scene.custom_layout.generator import (
    HTMLGenerator,
    HTMLGenerationResult,
    PipelineResult,
    GenerationContext,
)

# html_fixer components
from app.ai.scene.custom_layout.html_fixer import (
    TailwindFixes,
    ErrorType,
    TailwindPatch,
)

# =============================================================================
# CustomLayoutService - Adapter for intent_service.py compatibility
# =============================================================================
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

_service_logger = logging.getLogger(__name__)


@dataclass
class CustomLayoutResult:
    """
    Result object compatible with intent_service.py expectations.

    Maps PipelineResult attributes to the expected interface.
    """
    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    final_score: float = 0.0
    js_errors: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_pipeline_result(cls, result: PipelineResult) -> "CustomLayoutResult":
        """Convert PipelineResult to CustomLayoutResult."""
        return cls(
            success=result.success,
            html=result.html,
            error=result.error,
            latency_ms=result.total_latency_ms,
            tokens_used=result.tokens_used,
            final_score=result.final_score,
            js_errors=result.js_errors,
        )


class CustomLayoutService:
    """
    Service adapter that wraps CustomLayoutPipeline for intent_service.py.

    Provides the expected interface:
    - generate_and_validate_html_from_data(content_data, user_request, ...)
    - generate_and_validate_html(scene, user_request, ...)

    Usage:
        from app.ai.scene.custom_layout import custom_layout_service

        result = await custom_layout_service.generate_and_validate_html_from_data(
            content_data={"content_type": "trivia", "title": "History Quiz"},
            user_request="Show me trivia about history",
        )

        if result.success:
            html = result.html
    """

    def __init__(self):
        self._pipeline: Optional[CustomLayoutPipeline] = None

    def _get_pipeline(self) -> CustomLayoutPipeline:
        """Lazy initialization of the pipeline."""
        if self._pipeline is None:
            self._pipeline = get_pipeline()
        return self._pipeline

    async def generate_and_validate_html_from_data(
        self,
        content_data: Dict[str, Any],
        user_request: str,
        layout_hints: Optional[str] = None,
        layout_type: Optional[str] = None,
        human_feedback_mode: bool = False,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> CustomLayoutResult:
        """
        Generate and validate HTML from content data.

        This is the main entry point for the direct flow in intent_service.py.

        Args:
            content_data: Dict with content_type, title, data, etc.
            user_request: Original user request string
            layout_hints: Optional layout hints string
            layout_type: Optional explicit layout type
            human_feedback_mode: If True, skip CSS validation and return JS errors only

        Returns:
            CustomLayoutResult with success, html, error, latency_ms
        """
        _service_logger.info(f"generate_and_validate_html_from_data: {user_request[:50]}...")

        try:
            # Extract info from content_data
            info_type = layout_type or content_data.get("content_type", "custom")
            title = content_data.get("title")
            data = content_data.get("data")

            # Build context dict if there's extra info
            context = {}
            if layout_hints:
                context["layout_hints"] = layout_hints
            if conversation_context:
                context["conversation"] = conversation_context
            # Only pass context if it has content
            context = context if context else None

            # Call the pipeline
            pipeline_result = await self._get_pipeline().process(
                user_request=user_request,
                info_type=info_type,
                title=title,
                data=data,
                context=context,
                human_feedback_mode=human_feedback_mode,
            )

            return CustomLayoutResult.from_pipeline_result(pipeline_result)

        except Exception as e:
            _service_logger.error(f"generate_and_validate_html_from_data error: {e}", exc_info=True)
            return CustomLayoutResult(
                success=False,
                error=str(e),
                latency_ms=0.0,
            )

    async def generate_and_validate_html(
        self,
        scene: Dict[str, Any],
        user_request: str,
        layout_type: Optional[str] = None,
        human_feedback_mode: bool = False,
    ) -> CustomLayoutResult:
        """
        Generate and validate HTML from a SceneGraph dict.

        This is used by the SceneGraph flow in intent_service.py.

        Args:
            scene: SceneGraph dictionary
            user_request: Original user request string
            layout_type: Optional explicit layout type
            human_feedback_mode: If True, skip CSS validation and return JS errors only

        Returns:
            CustomLayoutResult with success, html, error, latency_ms
        """
        _service_logger.info(f"generate_and_validate_html: {user_request[:50]}...")

        try:
            # Extract layout intent from scene
            layout = scene.get("layout", {})
            info_type = layout_type or layout.get("intent", "custom")

            # Extract components data
            components = scene.get("components", [])
            data = {"scene": scene, "components": components}

            # Get metadata
            metadata = scene.get("metadata", {})

            # Build context
            context = {
                "scene_id": scene.get("scene_id"),
                "layout_intent": layout.get("intent"),
                "layout_engine": layout.get("engine"),
            }

            # Call the pipeline
            pipeline_result = await self._get_pipeline().process(
                user_request=user_request,
                info_type=info_type,
                data=data,
                context=context,
                human_feedback_mode=human_feedback_mode,
            )

            return CustomLayoutResult.from_pipeline_result(pipeline_result)

        except Exception as e:
            _service_logger.error(f"generate_and_validate_html error: {e}", exc_info=True)
            return CustomLayoutResult(
                success=False,
                error=str(e),
                latency_ms=0.0,
            )


# Singleton service instance
custom_layout_service = CustomLayoutService()


__all__ = [
    # Primary pipeline
    "CustomLayoutPipeline",
    "custom_layout_pipeline",
    "get_pipeline",
    # Service adapter (for intent_service.py)
    "CustomLayoutService",
    "CustomLayoutResult",
    "custom_layout_service",
    # Generator
    "HTMLGenerator",
    "HTMLGenerationResult",
    "PipelineResult",
    "GenerationContext",
    # html_fixer (legacy compatibility)
    "TailwindFixes",
    "ErrorType",
    "TailwindPatch",
]
