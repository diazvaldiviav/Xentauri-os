"""
Orchestrator - Main coordinator for the HTML repair pipeline.

Sprint 7: Coordinates error classification, deterministic fixes,
LLM fixes, validation, and rollback to produce the best result.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ..contracts.validation import ClassifiedError
from ..contracts.patches import TailwindPatch, PatchSet
from ..validators.classification_pipeline import ErrorClassificationPipeline
from ..fixers.deterministic.rule_engine import RuleEngine, create_default_engine
from ..fixers.llm import LLMFixer
from ..fixers.tailwind_injector import TailwindInjector
from ..sandbox.sandbox import Sandbox

from .contracts import FixPhase, OrchestratorMetrics, OrchestratorResult
from .history_manager import HistoryManager
from .decision_engine import DecisionEngine
from .best_result_tracker import BestResultTracker

if TYPE_CHECKING:
    from playwright.async_api import Page
    from ..sandbox.contracts import ValidationResult


logger = logging.getLogger("jarvis.ai.html_fixer.orchestrator")


class Orchestrator:
    """
    Main orchestrator for the HTML repair pipeline.

    Coordinates:
    1. Error classification
    2. Deterministic fixes (RuleEngine)
    3. LLM fixes (LLMFixer)
    4. Validation (Sandbox)
    5. Rollback if needed
    6. Return best result

    Usage:
        orchestrator = Orchestrator()
        result = await orchestrator.fix(html)

        if result.success:
            print(f"Fixed! Score: {result.final_score:.0%}")
            fixed_html = result.fixed_html
    """

    def __init__(
        self,
        # Components (use defaults if not provided)
        classifier: Optional[ErrorClassificationPipeline] = None,
        rule_engine: Optional[RuleEngine] = None,
        llm_fixer: Optional[LLMFixer] = None,
        sandbox: Optional[Sandbox] = None,
        decision_engine: Optional[DecisionEngine] = None,
        # Configuration
        max_llm_attempts: int = 1,  # Single attempt, user feedback loop handles iterations
        global_timeout_seconds: float = 120.0,
        validate_after_deterministic: bool = True,
        validate_after_llm: bool = True,
        enable_rollback: bool = True,
    ):
        """
        Initialize the orchestrator.

        Args:
            classifier: ErrorClassificationPipeline instance
            rule_engine: RuleEngine instance
            llm_fixer: LLMFixer instance
            sandbox: Sandbox instance
            decision_engine: DecisionEngine instance
            max_llm_attempts: Maximum LLM retry attempts
            global_timeout_seconds: Total timeout for fix operation
            validate_after_deterministic: Run validation after deterministic fixes
            validate_after_llm: Run validation after LLM fixes
            enable_rollback: Enable rollback on score degradation
        """
        # Initialize components lazily to avoid import issues in tests
        self._classifier = classifier
        self._rule_engine = rule_engine
        self._llm_fixer = llm_fixer
        self._sandbox = sandbox
        self._decision = decision_engine or DecisionEngine(
            max_llm_attempts=max_llm_attempts
        )

        # Injector for applying patches
        self._injector = TailwindInjector()

        # Configuration
        self._max_llm_attempts = max_llm_attempts
        self._global_timeout = global_timeout_seconds
        self._validate_deterministic = validate_after_deterministic
        self._validate_llm = validate_after_llm
        self._enable_rollback = enable_rollback

    def _get_classifier(self) -> ErrorClassificationPipeline:
        """Get or create classifier."""
        if self._classifier is None:
            self._classifier = ErrorClassificationPipeline()
        return self._classifier

    def _get_rule_engine(self) -> RuleEngine:
        """Get or create rule engine."""
        if self._rule_engine is None:
            self._rule_engine = create_default_engine()
        return self._rule_engine

    def _get_llm_fixer(self) -> LLMFixer:
        """Get or create LLM fixer."""
        if self._llm_fixer is None:
            self._llm_fixer = LLMFixer()
        return self._llm_fixer

    def _get_sandbox(self) -> Sandbox:
        """Get or create sandbox."""
        if self._sandbox is None:
            self._sandbox = Sandbox()
        return self._sandbox

    async def fix(
        self,
        html: str,
        page: Optional["Page"] = None,
        screenshots: Optional[Dict[str, bytes]] = None,
    ) -> OrchestratorResult:
        """
        Execute the full repair pipeline.

        Args:
            html: HTML content to fix
            page: Optional Playwright page for dynamic analysis
            screenshots: Optional before/after screenshots for LLM context

        Returns:
            OrchestratorResult with best HTML and metrics
        """
        start_time = time.time()

        # Initialize tracking
        history = HistoryManager()
        tracker = BestResultTracker(html)
        metrics = OrchestratorMetrics()
        phases_completed: List[FixPhase] = []

        history.push(html, FixPhase.INITIAL, errors_count=0)

        try:
            # Wrap in timeout
            return await asyncio.wait_for(
                self._fix_pipeline(
                    html=html,
                    page=page,
                    screenshots=screenshots,
                    history=history,
                    tracker=tracker,
                    metrics=metrics,
                    phases_completed=phases_completed,
                    start_time=start_time,
                ),
                timeout=self._global_timeout,
            )

        except asyncio.TimeoutError:
            logger.warning("Global timeout reached")
            metrics.total_duration_ms = (time.time() - start_time) * 1000
            return self._build_result(
                success=tracker.improved,
                original_html=html,
                tracker=tracker,
                metrics=metrics,
                phases=phases_completed,
                history=history,
                error="Global timeout reached",
            )

        except Exception as e:
            logger.exception(f"Orchestration failed: {e}")
            metrics.total_duration_ms = (time.time() - start_time) * 1000
            return self._build_result(
                success=False,
                original_html=html,
                tracker=tracker,
                metrics=metrics,
                phases=phases_completed,
                history=history,
                error=str(e),
            )

    async def _fix_pipeline(
        self,
        html: str,
        page: Optional["Page"],
        screenshots: Optional[Dict[str, bytes]],
        history: HistoryManager,
        tracker: BestResultTracker,
        metrics: OrchestratorMetrics,
        phases_completed: List[FixPhase],
        start_time: float,
    ) -> OrchestratorResult:
        """Internal pipeline execution."""

        # PHASE 1: Classify errors
        logger.info("Phase 1: Classifying errors")
        classify_start = time.time()
        report = await self._get_classifier().classify(html, page)
        metrics.classification_time_ms = (time.time() - classify_start) * 1000
        metrics.errors_initial = len(report.errors)

        phases_completed.append(FixPhase.CLASSIFY)

        if not report.errors:
            # Even if classification finds nothing, we still need to validate:
            # the Sandbox can detect feedback failures (NO_VISUAL_CHANGE) that
            # static analyzers won't flag.
            logger.info("No classified errors; validating for feedback issues")
            val_start = time.time()
            initial_val = await self._get_sandbox().validate(html)
            metrics.validation_time_ms += (time.time() - val_start) * 1000

            initial_score = self._calculate_score(initial_val)
            history.update_score(initial_score, initial_val.passed)
            tracker.update(html, initial_score, FixPhase.CLASSIFY, 0)

            if initial_val.passed:
                logger.info("Validation passed with no classified errors")
                phases_completed.append(FixPhase.COMPLETE)
                metrics.total_duration_ms = (time.time() - start_time) * 1000
                return self._build_result(
                    success=True,
                    original_html=html,
                    tracker=tracker,
                    metrics=metrics,
                    phases=phases_completed,
                    history=history,
                )

            # Derive feedback/interception errors from Sandbox results so the
            # pipeline can attempt deterministic/LLM fixes.
            derived_errors = self._derive_errors_from_validation(html, initial_val)
            if derived_errors:
                report.errors = derived_errors
                metrics.errors_initial = len(derived_errors)
            else:
                logger.info("Validation failed but no actionable derived errors")
                phases_completed.append(FixPhase.COMPLETE)
                metrics.total_duration_ms = (time.time() - start_time) * 1000
                return self._build_result(
                    success=False,
                    original_html=html,
                    tracker=tracker,
                    metrics=metrics,
                    phases=phases_completed,
                    history=history,
                )

        logger.info(f"Found {len(report.errors)} errors")

        # Partition errors
        det_errors, llm_errors = self._decision.partition_errors(report.errors)
        current_html = html
        current_errors = report.errors

        # PHASE 2: Deterministic fixes
        if det_errors:
            logger.info(f"Phase 2: Applying deterministic fixes for {len(det_errors)} errors")
            det_start = time.time()

            current_html, current_errors = await self._apply_deterministic(
                current_html, det_errors, history, tracker, metrics
            )

            metrics.deterministic_time_ms = (time.time() - det_start) * 1000
            phases_completed.append(FixPhase.DETERMINISTIC)

            # Validate if enabled
            if self._validate_deterministic:
                val_result = await self._validate_and_track(
                    current_html,
                    FixPhase.VALIDATE_DETERMINISTIC,
                    history,
                    tracker,
                    metrics,
                )
                phases_completed.append(FixPhase.VALIDATE_DETERMINISTIC)

                if val_result.passed:
                    logger.info("Validation passed after deterministic fixes")
                    phases_completed.append(FixPhase.COMPLETE)
                    metrics.total_duration_ms = (time.time() - start_time) * 1000
                    return self._build_result(
                        success=True,
                        original_html=html,
                        tracker=tracker,
                        metrics=metrics,
                        phases=phases_completed,
                        history=history,
                    )

                # If we're still failing due to weak/no feedback, derive
                # feedback errors from Sandbox and run one additional
                # deterministic pass (e.g. add focus rings).
                feedback_errors = self._derive_errors_from_validation(current_html, val_result)
                feedback_det = [
                    e for e in feedback_errors
                    if not e.error_type.requires_llm
                ]

                if feedback_det:
                    logger.info(f"Applying feedback fixes for {len(feedback_det)} elements")
                    current_html, _ = await self._apply_deterministic(
                        current_html, feedback_det, history, tracker, metrics
                    )

                    val_result = await self._validate_and_track(
                        current_html,
                        FixPhase.VALIDATE_DETERMINISTIC,
                        history,
                        tracker,
                        metrics,
                    )

                    if val_result.passed:
                        logger.info("Validation passed after feedback fixes")
                        phases_completed.append(FixPhase.COMPLETE)
                        metrics.total_duration_ms = (time.time() - start_time) * 1000
                        return self._build_result(
                            success=True,
                            original_html=html,
                            tracker=tracker,
                            metrics=metrics,
                            phases=phases_completed,
                            history=history,
                        )

                # Re-classify to update error list
                report = await self._get_classifier().classify_static(current_html)
                _, llm_errors = self._decision.partition_errors(report.errors)

        # PHASE 3: LLM fixes (single attempt, user provides feedback for iterations)
        time_remaining = self._global_timeout - (time.time() - start_time)

        if llm_errors and time_remaining > 30:
            logger.info(f"Phase 3: LLM fixes for {len(llm_errors)} errors")
            llm_start = time.time()

            current_html = await self._apply_llm_fixes(
                current_html,
                llm_errors,
                history,
                tracker,
                metrics,
                screenshots=screenshots,
            )

            metrics.llm_time_ms = (time.time() - llm_start) * 1000
            phases_completed.append(FixPhase.LLM_FIX)

            # Validate
            if self._validate_llm:
                await self._validate_and_track(
                    current_html,
                    FixPhase.VALIDATE_LLM,
                    history,
                    tracker,
                    metrics,
                )
                phases_completed.append(FixPhase.VALIDATE_LLM)

        phases_completed.append(FixPhase.COMPLETE)
        metrics.total_duration_ms = (time.time() - start_time) * 1000

        return self._build_result(
            success=tracker.improved,
            original_html=html,
            tracker=tracker,
            metrics=metrics,
            phases=phases_completed,
            history=history,
        )

    def _derive_errors_from_validation(
        self,
        html: str,
        validation_result: "ValidationResult",
    ) -> List[ClassifiedError]:
        """
        Convert Sandbox validation failures into ClassifiedErrors.

        This is primarily used when static/dynamic classification finds no
        errors but the Sandbox detects interaction failures (e.g. missing/weak
        visual feedback).
        """
        from bs4 import BeautifulSoup

        from ..analyzers.tailwind_analyzer import TailwindAnalyzer
        from ..contracts.errors import ErrorType
        from ..contracts.validation import TailwindInfo
        from ..sandbox.contracts import ElementStatus

        soup = BeautifulSoup(html, "html.parser")
        analyzer = TailwindAnalyzer()

        derived: List[ClassifiedError] = []
        seen: set[tuple[str, ErrorType]] = set()

        for element_result in validation_result.element_results:
            error_type: Optional[ErrorType] = None

            if element_result.status == ElementStatus.NO_VISUAL_CHANGE:
                # Treat both weak feedback and no-response as feedback problems.
                # Deterministic fixes (e.g. focus rings) can often solve both.
                error_type = ErrorType.FEEDBACK_TOO_SUBTLE

            elif element_result.status == ElementStatus.INTERCEPTED:
                error_type = ErrorType.POINTER_BLOCKED

            if error_type is None:
                continue

            key = (element_result.selector, error_type)
            if key in seen:
                continue
            seen.add(key)

            element_tag = "unknown"
            tailwind_info: TailwindInfo = TailwindInfo()

            try:
                el = soup.select_one(element_result.selector)
            except Exception:
                el = None

            if el is not None:
                element_tag = el.name
                tailwind_info = analyzer.analyze_element(el)

            derived.append(
                ClassifiedError(
                    error_type=error_type,
                    selector=element_result.selector,
                    element_tag=element_tag,
                    tailwind_info=tailwind_info,
                    blocking_element=element_result.blocking_element,
                    confidence=0.9,
                )
            )

        return derived

    async def _apply_deterministic(
        self,
        html: str,
        errors: List[ClassifiedError],
        history: HistoryManager,
        tracker: BestResultTracker,
        metrics: OrchestratorMetrics,
    ) -> Tuple[str, List[ClassifiedError]]:
        """Apply deterministic fixes using RuleEngine."""
        patches = self._get_rule_engine().apply_rules(errors)

        if not patches:
            logger.debug("No patches generated by RuleEngine")
            return html, errors

        result = self._injector.inject(html, patches)

        if result.success:
            metrics.patches_applied += len(result.applied)
            history.push(
                result.html,
                FixPhase.DETERMINISTIC,
                patches_applied=result.applied,
                errors_count=len(errors) - len(result.applied),
            )

            logger.info(f"Applied {len(result.applied)} deterministic patches")

            # Filter out addressed errors
            remaining = [
                e for e in errors
                if not self._error_addressed(e, result.applied)
            ]
            return result.html, remaining

        logger.warning(f"Injection failed: {len(result.failed)} patches failed")
        return html, errors

    async def _apply_llm_fixes(
        self,
        html: str,
        errors: List[ClassifiedError],
        history: HistoryManager,
        tracker: BestResultTracker,
        metrics: OrchestratorMetrics,
        screenshots: Optional[Dict[str, bytes]] = None,
    ) -> str:
        """Apply LLM fixes with retry and rollback."""
        current_html = html
        best_llm_html = html
        best_llm_score = tracker.best_score

        for attempt in range(self._max_llm_attempts):
            logger.info(f"LLM attempt {attempt + 1}/{self._max_llm_attempts}")

            # Select errors for this attempt
            selected = self._decision.select_errors_for_llm(errors)

            if not selected:
                logger.debug("No errors selected for LLM")
                break

            # Call LLM fixer
            llm_result = await self._get_llm_fixer().fix(
                selected, current_html, screenshots
            )

            metrics.llm_calls_made += llm_result.llm_calls_made
            metrics.llm_tokens_used += llm_result.tokens_used

            if not llm_result.success or not llm_result.fixed_html:
                logger.warning("LLM fix failed or produced no HTML")
                continue

            candidate = llm_result.fixed_html
            patch_count = len(llm_result.tailwind_patches) + len(llm_result.js_patches)
            metrics.patches_applied += patch_count

            # Validate candidate
            val_result = await self._get_sandbox().validate(candidate)
            score = self._calculate_score(val_result)

            history.push(
                candidate,
                FixPhase.LLM_FIX,
                score=score,
                patches_applied=llm_result.tailwind_patches + llm_result.js_patches,
                errors_count=len(errors),
                attempt=attempt + 1,
            )

            logger.info(f"LLM attempt {attempt + 1} score: {score:.2%}")

            # Check for rollback
            if self._enable_rollback and self._decision.should_rollback(score, best_llm_score):
                logger.info("Score degraded, rolling back")
                metrics.rollbacks_performed += 1
                continue  # Don't use this result

            # Track best LLM result
            if score > best_llm_score:
                best_llm_score = score
                best_llm_html = candidate
                tracker.update(candidate, score, FixPhase.LLM_FIX, len(errors))

            if val_result.passed:
                logger.info("Validation passed after LLM fix")
                return candidate

            # Decide whether to continue
            if not self._decision.should_continue_fixing(
                score, best_llm_score, len(errors), attempt + 1
            ):
                logger.info("Stopping LLM attempts")
                break

            # Update for next iteration
            current_html = candidate

            # Re-classify errors
            report = await self._get_classifier().classify_static(current_html)
            errors = [e for e in report.errors if e.error_type.requires_llm]

        return best_llm_html

    async def _validate_and_track(
        self,
        html: str,
        phase: FixPhase,
        history: HistoryManager,
        tracker: BestResultTracker,
        metrics: OrchestratorMetrics,
    ) -> "ValidationResult":
        """Validate HTML and track result."""
        val_start = time.time()
        result = await self._get_sandbox().validate(html)
        metrics.validation_time_ms += (time.time() - val_start) * 1000

        score = self._calculate_score(result)
        history.update_score(score, result.passed)

        # Re-classify to get error count
        report = await self._get_classifier().classify_static(html)
        error_count = len(report.errors)

        tracker.update(html, score, phase, error_count)

        logger.info(f"Validation: score={score:.2%}, passed={result.passed}, errors={error_count}")

        return result

    def _calculate_score(self, result: "ValidationResult") -> float:
        """Calculate validation score (0.0-1.0)."""
        if not result.element_results:
            return 1.0 if not result.js_errors else 0.5

        from ..sandbox.contracts import ElementStatus

        responsive = sum(
            1 for e in result.element_results
            if e.status == ElementStatus.RESPONSIVE
        )
        ratio = responsive / len(result.element_results)

        # Penalize JS errors
        if result.js_errors:
            ratio *= 0.9

        return ratio

    def _error_addressed(
        self, error: ClassifiedError, patches: List[TailwindPatch]
    ) -> bool:
        """Check if error was addressed by patches."""
        for patch in patches:
            if patch.selector == error.selector:
                return True
        return False

    def _build_result(
        self,
        success: bool,
        original_html: str,
        tracker: BestResultTracker,
        metrics: OrchestratorMetrics,
        phases: List[FixPhase],
        history: HistoryManager,
        error: Optional[str] = None,
    ) -> OrchestratorResult:
        """Build final result."""
        metrics.errors_final = tracker.best_errors

        result = OrchestratorResult(
            success=success,
            original_html=original_html,
            fixed_html=tracker.best_html,
            final_score=tracker.best_score,
            phases_completed=phases,
            errors_fixed=metrics.errors_initial - metrics.errors_final,
            errors_remaining=metrics.errors_final,
            validation_passed=tracker.best_score >= 0.9,
            metrics=metrics,
            error_message=error,
            history=history.get_all(),
        )

        logger.info(result.describe())
        return result

    def __repr__(self) -> str:
        return (
            f"Orchestrator("
            f"max_llm={self._max_llm_attempts}, "
            f"timeout={self._global_timeout}s)"
        )
