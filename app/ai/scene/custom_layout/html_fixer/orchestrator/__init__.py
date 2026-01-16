"""
Orchestrator module - Coordinates the HTML repair pipeline.

Sprint 7: Provides the main Orchestrator class along with
supporting components for history management, decision making,
and result tracking.

Usage:
    from html_fixer.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    result = await orchestrator.fix(html)

    if result.success:
        fixed_html = result.fixed_html
        print(f"Score: {result.final_score:.0%}")
"""

from .contracts import (
    FixPhase,
    HistoryEntry,
    OrchestratorMetrics,
    OrchestratorResult,
)
from .history_manager import HistoryManager
from .decision_engine import DecisionEngine
from .best_result_tracker import BestResultTracker
from .orchestrator import Orchestrator


__all__ = [
    # Contracts
    "FixPhase",
    "HistoryEntry",
    "OrchestratorMetrics",
    "OrchestratorResult",
    # Components
    "HistoryManager",
    "DecisionEngine",
    "BestResultTracker",
    # Main
    "Orchestrator",
]
