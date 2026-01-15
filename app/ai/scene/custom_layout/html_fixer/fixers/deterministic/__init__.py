"""
Deterministic Fixers - Rule-based HTML repairs.

This module provides deterministic (non-LLM) fixes for HTML issues
using predefined rules that generate Tailwind class patches.

Components:
- FixRule: Abstract base class for all fix rules
- RuleEngine: Orchestrates rule execution
- Concrete Rules: ZIndexFixRule, PointerEventsFixRule, etc.

Usage:
    from html_fixer.fixers.deterministic import create_default_engine

    engine = create_default_engine()
    patches = engine.apply_rules(classified_errors)
"""

from .base_rule import FixRule
from .rule_engine import RuleEngine, create_default_engine
from .visibility_rule import VisibilityRestoreRule
from .zindex_rule import ZIndexFixRule
from .pointer_events_rule import PointerEventsFixRule
from .passthrough_rule import PassthroughRule
from .transform_3d_rule import Transform3DFixRule


__all__ = [
    # Base
    "FixRule",
    "RuleEngine",
    "create_default_engine",
    # Rules
    "VisibilityRestoreRule",
    "ZIndexFixRule",
    "PointerEventsFixRule",
    "PassthroughRule",
    "Transform3DFixRule",
]
