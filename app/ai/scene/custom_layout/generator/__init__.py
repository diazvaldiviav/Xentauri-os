"""
HTML Generator Module.

Generates HTML layouts using Gemini 3 Pro with extended thinking.

Usage:
    from app.ai.scene.custom_layout.generator import HTMLGenerator

    generator = HTMLGenerator()
    result = await generator.generate(
        user_request="Show me trivia about world history",
        info_type="trivia",
    )

    if result.success:
        html = result.html
"""

from .contracts import (
    HTMLGenerationResult,
    PipelineResult,
    GenerationContext,
)
from .html_generator import HTMLGenerator
from .prompts import (
    SYSTEM_PROMPT,
    GENERATION_RULES,
    build_user_prompt,
    get_content_type_hint,
)

__all__ = [
    # Main generator
    "HTMLGenerator",
    # Contracts
    "HTMLGenerationResult",
    "PipelineResult",
    "GenerationContext",
    # Prompts
    "SYSTEM_PROMPT",
    "GENERATION_RULES",
    "build_user_prompt",
    "get_content_type_hint",
]
