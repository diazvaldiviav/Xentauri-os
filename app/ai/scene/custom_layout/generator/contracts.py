"""
Contracts for the HTML Generator module.

Dataclasses for generation results and pipeline output.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..html_fixer.orchestrator.contracts import OrchestratorResult


@dataclass
class HTMLGenerationResult:
    """Result of HTML generation using Gemini 3 Pro."""

    success: bool
    """Whether generation succeeded."""

    html: Optional[str] = None
    """Generated HTML content."""

    error: Optional[str] = None
    """Error message if generation failed."""

    tokens_used: int = 0
    """Total tokens consumed (input + output)."""

    latency_ms: float = 0.0
    """Time taken for generation in milliseconds."""

    thinking_used: bool = False
    """Whether extended thinking was used."""

    model: str = ""
    """Model used for generation."""

    def describe(self) -> str:
        """Human-readable description."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"HTMLGenerationResult: {status}",
            f"  Model: {self.model}",
            f"  Tokens: {self.tokens_used}",
            f"  Latency: {self.latency_ms:.0f}ms",
            f"  Thinking: {self.thinking_used}",
        ]
        if self.error:
            lines.append(f"  Error: {self.error}")
        if self.html:
            lines.append(f"  HTML length: {len(self.html)} chars")
        return "\n".join(lines)


@dataclass
class PipelineResult:
    """
    Result of the complete CustomLayoutPipeline.

    Combines generation and validation/repair results.
    """

    success: bool
    """Whether the pipeline succeeded (HTML generated and validated)."""

    html: Optional[str] = None
    """Final HTML after generation and optional repairs."""

    generation_result: Optional[HTMLGenerationResult] = None
    """Result from HTML generation phase."""

    validation_result: Optional["OrchestratorResult"] = None
    """Result from validation/repair phase."""

    total_latency_ms: float = 0.0
    """Total time for entire pipeline in milliseconds."""

    tokens_used: int = 0
    """Total tokens used across all LLM calls."""

    final_score: float = 0.0
    """Final validation score (0.0 - 1.0)."""

    error: Optional[str] = None
    """Error message if pipeline failed."""

    def describe(self) -> str:
        """Human-readable description."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"PipelineResult: {status}",
            f"  Final Score: {self.final_score:.1%}",
            f"  Total Latency: {self.total_latency_ms:.0f}ms",
            f"  Total Tokens: {self.tokens_used}",
        ]

        if self.generation_result:
            lines.append(f"  Generation: {'OK' if self.generation_result.success else 'FAILED'}")

        if self.validation_result:
            lines.append(f"  Validation: {'PASSED' if self.validation_result.validation_passed else 'FAILED'}")
            lines.append(f"  Repairs: {self.validation_result.metrics.patches_applied}")

        if self.error:
            lines.append(f"  Error: {self.error}")

        if self.html:
            lines.append(f"  HTML length: {len(self.html)} chars")

        return "\n".join(lines)


@dataclass
class GenerationContext:
    """
    Context for HTML generation.

    Provides all information needed to generate appropriate HTML.
    """

    user_request: str
    """Original user request (e.g., 'Show me trivia about history')."""

    info_type: str = "custom"
    """Type of content (trivia, dashboard, game, calendar, weather, etc.)."""

    title: Optional[str] = None
    """Optional title for the content."""

    data: Optional[Dict[str, Any]] = None
    """Optional data to include (e.g., calendar events, weather data)."""

    theme: str = "dark"
    """Color theme (dark or light)."""

    viewport_width: int = 1920
    """Target viewport width."""

    viewport_height: int = 1080
    """Target viewport height."""

    additional_context: Optional[str] = None
    """Any additional context for generation."""
