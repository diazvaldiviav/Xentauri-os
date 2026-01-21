"""
CustomLayoutPipeline - Main orchestrator for HTML generation and validation.

Coordinates:
1. HTMLGenerator (Gemini 3 Pro + thinking HIGH) for HTML generation
2. html_fixer/Orchestrator (Gemini 3 Flash) for validation and repair

This is the main entry point for the custom layout system.
"""

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from .generator import HTMLGenerator, PipelineResult, GenerationContext
from .html_fixer.orchestrator import Orchestrator
from .html_fixer.fixers.llm import LLMFixer

if TYPE_CHECKING:
    from app.ai.providers.gemini import GeminiProvider

logger = logging.getLogger("jarvis.ai.html_fixer.pipeline")


class CustomLayoutPipeline:
    """
    Pipeline completo: Generate -> Validate -> Repair.

    Generates HTML directly from user_request using Gemini 3 Pro,
    then validates and repairs using html_fixer with Gemini 3 Flash.

    Usage:
        pipeline = CustomLayoutPipeline()
        result = await pipeline.process(
            user_request="Show me trivia about world capitals",
            info_type="trivia",
        )

        if result.success:
            html = result.html
            print(f"Score: {result.final_score:.0%}")
    """

    def __init__(
        self,
        generator: Optional[HTMLGenerator] = None,
        fixer: Optional[Orchestrator] = None,
        max_repair_cycles: int = 2,
        skip_validation: bool = False,
    ):
        """
        Initialize the pipeline.

        Args:
            generator: HTMLGenerator instance (creates default if not provided)
            fixer: Orchestrator instance (creates default if not provided)
            max_repair_cycles: Maximum validation/repair cycles
            skip_validation: If True, skip validation (for testing)
        """
        self._generator = generator
        self._fixer = fixer
        self._max_cycles = max_repair_cycles
        self._skip_validation = skip_validation

        # Lazy initialization flags
        self._generator_initialized = generator is not None
        self._fixer_initialized = fixer is not None

    def _get_generator(self) -> HTMLGenerator:
        """Get or create the HTML generator."""
        if not self._generator_initialized:
            self._generator = HTMLGenerator()
            self._generator_initialized = True
        return self._generator

    def _get_fixer(self) -> Orchestrator:
        """Get or create the orchestrator/fixer."""
        if not self._fixer_initialized:
            # Create LLMFixer with Gemini 3 Flash for repairs
            try:
                from app.ai.providers.gemini import GeminiProvider
                llm_provider = GeminiProvider(model="gemini-3-flash-preview")
                llm_fixer = LLMFixer(provider=llm_provider)
            except ImportError:
                llm_fixer = LLMFixer()

            self._fixer = Orchestrator(
                llm_fixer=llm_fixer,
                max_llm_attempts=1,  # Single attempt, user feedback loop handles iterations
            )
            self._fixer_initialized = True
        return self._fixer

    async def process(
        self,
        user_request: str,
        info_type: str = "custom",
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        human_feedback_mode: bool = False,
    ) -> PipelineResult:
        """
        Execute the complete pipeline.

        Args:
            user_request: Original user request (e.g., "Show me trivia")
            info_type: Type of content (trivia, dashboard, game, etc.)
            title: Optional title for the content
            data: Optional data to include (e.g., calendar events)
            context: Additional context dictionary

        Returns:
            PipelineResult with final HTML and metrics

        Flow:
            1. Generate HTML with Gemini 3 Pro (thinking HIGH)
            2. Validate with Sandbox (Playwright)
            3. Repair with html_fixer if needed (Gemini 3 Flash, 1 attempt)
            4. Return best result
        """
        start_time = time.time()
        total_tokens = 0

        logger.info(f"Pipeline started: {user_request[:50]}...")

        # Build generation context
        gen_context = GenerationContext(
            user_request=user_request,
            info_type=info_type,
            title=title,
            data=data,
            additional_context=str(context) if context else None,
        )

        # ===== PHASE 1: Generate HTML =====
        generator = self._get_generator()
        logger.info(f"Phase 1: Generating HTML with {generator._model} (thinking={generator._use_thinking})")

        gen_result = await generator.generate(context=gen_context)
        total_tokens += gen_result.tokens_used

        if not gen_result.success:
            logger.error(f"Generation failed: {gen_result.error}")
            return PipelineResult(
                success=False,
                html=None,
                generation_result=gen_result,
                validation_result=None,
                total_latency_ms=(time.time() - start_time) * 1000,
                tokens_used=total_tokens,
                final_score=0.0,
                error=f"Generation failed: {gen_result.error}",
            )

        logger.info(f"Generated {len(gen_result.html)} chars in {gen_result.latency_ms:.0f}ms")

        # Human Feedback Mode: JS-only validation + fix loop, skip CSS/Tailwind fixes
        if human_feedback_mode:
            logger.info("Human Feedback Mode: Running JS validation + fix loop (no CSS fixes)")
            fixed_html, js_errors = await self._validate_and_fix_js_only(gen_result.html)

            return PipelineResult(
                success=True,
                html=fixed_html,
                generation_result=gen_result,
                validation_result=None,
                total_latency_ms=(time.time() - start_time) * 1000,
                tokens_used=total_tokens,
                final_score=1.0 if not js_errors else 0.8,  # Lower score if JS errors remain
                js_errors=js_errors,
            )

        # Skip validation if requested (for testing)
        if self._skip_validation:
            return PipelineResult(
                success=True,
                html=gen_result.html,
                generation_result=gen_result,
                validation_result=None,
                total_latency_ms=(time.time() - start_time) * 1000,
                tokens_used=total_tokens,
                final_score=1.0,
            )

        # ===== PHASE 2: Validate + Repair =====
        logger.info("Phase 2: Validating and repairing with html_fixer")

        fix_result = await self._get_fixer().fix(gen_result.html)

        # Add LLM tokens from repair phase
        if fix_result.metrics:
            total_tokens += fix_result.metrics.llm_tokens_used

        # Determine success
        # Success if: validation passed OR we have HTML (user can provide feedback)
        # Changed: Always return HTML if generated, user feedback loop handles iterations
        success = fix_result.fixed_html is not None

        result = PipelineResult(
            success=success,
            html=fix_result.fixed_html,
            generation_result=gen_result,
            validation_result=fix_result,
            total_latency_ms=(time.time() - start_time) * 1000,
            tokens_used=total_tokens,
            final_score=fix_result.final_score,
        )

        logger.info(result.describe())
        return result

    async def generate_only(
        self,
        user_request: str,
        info_type: str = "custom",
        **kwargs,
    ) -> PipelineResult:
        """
        Generate HTML without validation (for quick testing).

        Args:
            user_request: User request
            info_type: Content type
            **kwargs: Additional arguments

        Returns:
            PipelineResult with generated HTML (no validation)
        """
        start_time = time.time()

        gen_result = await self._get_generator().generate(
            user_request=user_request,
            info_type=info_type,
            **kwargs,
        )

        return PipelineResult(
            success=gen_result.success,
            html=gen_result.html,
            generation_result=gen_result,
            validation_result=None,
            total_latency_ms=(time.time() - start_time) * 1000,
            tokens_used=gen_result.tokens_used,
            final_score=1.0 if gen_result.success else 0.0,
            error=gen_result.error,
        )

    async def validate_only(
        self,
        html: str,
    ) -> PipelineResult:
        """
        Validate and repair existing HTML (for testing).

        Args:
            html: HTML content to validate

        Returns:
            PipelineResult with validation results
        """
        start_time = time.time()

        fix_result = await self._get_fixer().fix(html)

        tokens_used = fix_result.metrics.llm_tokens_used if fix_result.metrics else 0

        return PipelineResult(
            success=fix_result.validation_passed or fix_result.final_score > 0.5,
            html=fix_result.fixed_html,
            generation_result=None,
            validation_result=fix_result,
            total_latency_ms=(time.time() - start_time) * 1000,
            tokens_used=tokens_used,
            final_score=fix_result.final_score,
        )

    def __repr__(self) -> str:
        return f"CustomLayoutPipeline(max_cycles={self._max_cycles})"

    async def _validate_and_fix_js_only(self, html: str, max_attempts: int = 2) -> tuple:
        """
        Validate JS and fix errors until they pass or max attempts reached.

        Human Feedback Mode: Only fixes JS errors, skips CSS/visual fixes.
        Returns (fixed_html, remaining_js_errors).
        """
        from .html_fixer.sandbox import Sandbox
        from .html_fixer.fixers.llm import LLMFixer
        from .html_fixer.contracts.errors import ErrorType
        from .html_fixer.contracts.validation import ClassifiedError, TailwindInfo

        sandbox = Sandbox()
        current_html = html
        js_errors = []

        for attempt in range(max_attempts):
            logger.info(f"JS validation attempt {attempt + 1}/{max_attempts}")

            # Validate with Sandbox (js_only=True skips element testing)
            try:
                val_result = await sandbox.validate(current_html, js_only=True)
            except Exception as e:
                logger.warning(f"Sandbox validation failed: {e}")
                return current_html, [{"type": "validation_error", "message": str(e)}]

            # Check for JS errors
            if not val_result.js_errors:
                logger.info("No JS errors found, HTML passes validation")
                return current_html, []

            # Convert JS errors to ClassifiedError format for LLM fixer
            classified_errors = []
            for js_err in val_result.js_errors:
                classified_errors.append(
                    ClassifiedError(
                        error_type=ErrorType.JS_RUNTIME_ERROR,
                        selector="script",
                        element_tag="script",
                        tailwind_info=TailwindInfo(),
                        confidence=1.0,
                        raw_error={"message": js_err},
                    )
                )

            js_errors = self._serialize_sandbox_js_errors(val_result.js_errors)
            logger.info(f"Found {len(js_errors)} JS errors, attempting fix")

            # Last attempt? Return errors without fixing
            if attempt == max_attempts - 1:
                logger.info("Max attempts reached, returning remaining errors")
                return current_html, js_errors

            # Fix with LLM
            try:
                llm_fixer = self._get_fixer()._get_llm_fixer()
                fix_result = await llm_fixer.fix(classified_errors, current_html)

                if fix_result.success and fix_result.fixed_html:
                    current_html = fix_result.fixed_html
                    logger.info("LLM fix applied, rechecking...")
                else:
                    logger.warning(f"LLM fix failed: {fix_result.error_message}")
                    return current_html, js_errors
            except Exception as e:
                logger.warning(f"LLM fix error: {e}")
                return current_html, js_errors

        return current_html, js_errors

    def _serialize_sandbox_js_errors(self, js_errors: list) -> list:
        """Convert Sandbox JS errors to serializable format."""
        return [
            {
                "type": "js_runtime_error",
                "message": err if isinstance(err, str) else str(err),
            }
            for err in js_errors
        ]


# Singleton for easy import
_pipeline_instance: Optional[CustomLayoutPipeline] = None


def get_pipeline() -> CustomLayoutPipeline:
    """Get or create the singleton pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = CustomLayoutPipeline()
    return _pipeline_instance


# Convenience alias
custom_layout_pipeline = get_pipeline
