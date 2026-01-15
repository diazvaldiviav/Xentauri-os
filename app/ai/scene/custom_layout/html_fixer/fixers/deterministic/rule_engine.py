"""
RuleEngine - Orchestrates fix rule execution.

Maintains a registry of rules and applies them to classified errors
to generate a PatchSet.

Usage:
    from html_fixer.fixers.deterministic import RuleEngine, create_default_engine

    # Use default engine with all rules
    engine = create_default_engine()
    patches = engine.apply_rules(errors)

    # Or build custom engine
    engine = RuleEngine()
    engine.register(ZIndexFixRule())
    engine.register(PointerEventsFixRule())
    patches = engine.apply_rules(errors)
"""

from typing import List, Optional, Dict, Type
import logging

from ...contracts.errors import ErrorType
from ...contracts.patches import TailwindPatch, PatchSet
from ...contracts.validation import ClassifiedError

from .base_rule import FixRule


logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Orchestrates deterministic fix rule execution.

    The engine maintains a registry of FixRule instances, indexed by
    the ErrorTypes they handle. When applying rules, it:
    1. Iterates through errors
    2. Finds applicable rules for each error type
    3. Invokes rules in priority order
    4. Collects generated patches into a PatchSet

    Features:
    - Priority-based rule execution
    - Error type indexing for fast lookup
    - Skip LLM-required errors
    - Detailed logging
    """

    def __init__(self):
        """Initialize the rule engine."""
        self._rules: List[FixRule] = []
        self._type_index: Dict[ErrorType, List[FixRule]] = {}

    def register(self, rule: FixRule) -> None:
        """
        Register a fix rule.

        Args:
            rule: FixRule instance to register
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        self._rebuild_index()
        logger.debug(f"Registered rule: {rule.name}")

    def register_all(self, rules: List[FixRule]) -> None:
        """
        Register multiple rules at once.

        Args:
            rules: List of FixRule instances
        """
        for rule in rules:
            self.register(rule)

    def unregister(self, rule_class: Type[FixRule]) -> bool:
        """
        Unregister a rule by class.

        Args:
            rule_class: Class of rule to remove

        Returns:
            True if rule was found and removed
        """
        original_count = len(self._rules)
        self._rules = [r for r in self._rules if not isinstance(r, rule_class)]
        self._rebuild_index()
        removed = len(self._rules) < original_count
        if removed:
            logger.debug(f"Unregistered rule: {rule_class.__name__}")
        return removed

    def get_rules_for_type(self, error_type: ErrorType) -> List[FixRule]:
        """
        Get all rules that handle a specific error type.

        Args:
            error_type: ErrorType to look up

        Returns:
            List of rules sorted by priority
        """
        return self._type_index.get(error_type, [])

    def apply_rules(
        self,
        errors: List[ClassifiedError],
        stop_on_first_fix: bool = False,
    ) -> PatchSet:
        """
        Apply all applicable rules to generate patches.

        Args:
            errors: List of classified errors
            stop_on_first_fix: If True, stop after first rule matches each error

        Returns:
            PatchSet with source="deterministic"
        """
        patch_set = PatchSet(source="deterministic")
        fixed_count = 0
        skipped_llm = 0

        for error in errors:
            # Skip errors marked as requiring LLM
            if error.requires_llm:
                skipped_llm += 1
                logger.debug(f"Skipping LLM-required error: {error.selector}")
                continue

            # Find applicable rules
            applicable_rules = self.get_rules_for_type(error.error_type)

            for rule in applicable_rules:
                if not rule.can_fix(error):
                    continue

                try:
                    result = rule.generate_fix(error)
                    patches = result if isinstance(result, list) else [result]

                    for patch in patches:
                        patch_set.add(patch)

                    fixed_count += 1
                    logger.info(
                        f"Rule {rule.name} generated {len(patches)} patch(es) "
                        f"for {error.selector}"
                    )

                    if stop_on_first_fix:
                        break

                except Exception as e:
                    logger.error(f"Rule {rule.name} failed on {error.selector}: {e}")

        logger.info(
            f"Applied rules: {fixed_count}/{len(errors)} errors addressed, "
            f"{len(patch_set)} patches generated"
            + (f", {skipped_llm} skipped (LLM)" if skipped_llm else "")
        )

        return patch_set

    def apply_single(
        self, error: ClassifiedError
    ) -> Optional[List[TailwindPatch]]:
        """
        Apply rules to a single error.

        Args:
            error: Single classified error

        Returns:
            List of patches or None if no rule applies
        """
        result = self.apply_rules([error])
        return list(result.patches) if result.patches else None

    def _rebuild_index(self) -> None:
        """Rebuild the error type index."""
        self._type_index.clear()
        for rule in self._rules:
            for error_type in rule.handles:
                if error_type not in self._type_index:
                    self._type_index[error_type] = []
                self._type_index[error_type].append(rule)

    @property
    def rules(self) -> List[FixRule]:
        """Get all registered rules (sorted by priority)."""
        return self._rules.copy()

    @property
    def handled_types(self) -> List[ErrorType]:
        """Get all error types that have at least one rule."""
        return list(self._type_index.keys())

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"RuleEngine({len(self._rules)} rules)"


def create_default_engine() -> RuleEngine:
    """
    Create a RuleEngine with all default rules registered.

    Returns:
        Configured RuleEngine ready to use
    """
    from .visibility_rule import VisibilityRestoreRule
    from .zindex_rule import ZIndexFixRule
    from .pointer_events_rule import PointerEventsFixRule
    from .passthrough_rule import PassthroughRule
    from .transform_3d_rule import Transform3DFixRule

    engine = RuleEngine()
    engine.register_all([
        VisibilityRestoreRule(),   # Priority 5 - Fix visibility first
        ZIndexFixRule(),           # Priority 15 - Then z-index
        PointerEventsFixRule(),    # Priority 25 - Then pointer events
        PassthroughRule(),         # Priority 26 - Related to pointer events
        Transform3DFixRule(),      # Priority 35 - Transform fixes
    ])

    logger.info(f"Created default engine with {len(engine)} rules")
    return engine
