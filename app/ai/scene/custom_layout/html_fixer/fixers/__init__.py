"""
Fixers - HTML repair implementations.

Contains:
- deterministic/: Rule-based fixes (Sprint 3)
- llm/: LLM-powered surgical fixes (Sprint 6)
- TailwindInjector: Applies patches to HTML

Usage:
    from html_fixer.fixers import TailwindInjector, create_default_engine
    from html_fixer.contracts.patches import PatchSet

    # Create engine and generate patches
    engine = create_default_engine()
    patches = engine.apply_rules(errors)

    # Apply patches to HTML
    injector = TailwindInjector()
    result = injector.inject(html, patches)
"""

from .tailwind_injector import TailwindInjector, InjectionResult
from .deterministic import (
    FixRule,
    RuleEngine,
    create_default_engine,
    VisibilityRestoreRule,
    ZIndexFixRule,
    PointerEventsFixRule,
    PassthroughRule,
    Transform3DFixRule,
)


__all__ = [
    # Injector
    "TailwindInjector",
    "InjectionResult",
    # Deterministic
    "FixRule",
    "RuleEngine",
    "create_default_engine",
    "VisibilityRestoreRule",
    "ZIndexFixRule",
    "PointerEventsFixRule",
    "PassthroughRule",
    "Transform3DFixRule",
]
