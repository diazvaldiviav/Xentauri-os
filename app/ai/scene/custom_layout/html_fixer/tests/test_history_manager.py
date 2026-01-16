"""
Tests for HistoryManager (Sprint 7).

Tests the history tracking and rollback functionality.
"""

import pytest
from html_fixer.orchestrator.contracts import FixPhase, HistoryEntry
from html_fixer.orchestrator.history_manager import HistoryManager


class TestHistoryManager:
    """Tests for HistoryManager."""

    def test_push_and_get_latest(self):
        """Test pushing entries and getting latest."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)

        latest = history.latest
        assert latest is not None
        assert latest.html == "<div>2</div>"
        assert latest.phase == FixPhase.DETERMINISTIC

    def test_update_score(self):
        """Test updating score of latest entry."""
        history = HistoryManager()

        history.push("<div>test</div>", FixPhase.INITIAL)
        assert history.latest.score is None

        history.update_score(0.85, validation_passed=True)
        assert history.latest.score == 0.85
        assert history.latest.validation_passed is True

    def test_update_score_empty_history(self):
        """Test update_score does nothing on empty history."""
        history = HistoryManager()
        history.update_score(0.9)  # Should not raise

    def test_get_best(self):
        """Test getting entry with highest score."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL, score=0.3)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC, score=0.8)
        history.push("<div>3</div>", FixPhase.LLM_FIX, score=0.6)

        best = history.get_best()
        assert best is not None
        assert best.html == "<div>2</div>"
        assert best.score == 0.8

    def test_get_best_no_scores(self):
        """Test get_best returns first entry if nothing scored."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)

        best = history.get_best()
        assert best is not None
        assert best.phase == FixPhase.INITIAL

    def test_get_best_empty_history(self):
        """Test get_best returns None on empty history."""
        history = HistoryManager()
        assert history.get_best() is None

    def test_get_by_phase(self):
        """Test getting entry by phase."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)
        history.push("<div>3</div>", FixPhase.LLM_FIX)

        det = history.get_by_phase(FixPhase.DETERMINISTIC)
        assert det is not None
        assert det.html == "<div>2</div>"

    def test_get_by_phase_not_found(self):
        """Test get_by_phase returns None if phase not in history."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)

        assert history.get_by_phase(FixPhase.LLM_FIX) is None

    def test_get_by_phase_returns_most_recent(self):
        """Test get_by_phase returns most recent entry for phase."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.LLM_FIX, attempt=1)
        history.push("<div>2</div>", FixPhase.LLM_FIX, attempt=2)
        history.push("<div>3</div>", FixPhase.LLM_FIX, attempt=3)

        llm = history.get_by_phase(FixPhase.LLM_FIX)
        assert llm is not None
        assert llm.metadata.get("attempt") == 3

    def test_rollback_steps(self):
        """Test rolling back N steps."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)
        history.push("<div>3</div>", FixPhase.LLM_FIX)

        # Rollback 1 step (to DETERMINISTIC)
        prev = history.rollback(steps=1)
        assert prev is not None
        assert prev.html == "<div>2</div>"

        # Rollback 2 steps (to INITIAL)
        prev = history.rollback(steps=2)
        assert prev is not None
        assert prev.html == "<div>1</div>"

    def test_rollback_too_many_steps(self):
        """Test rollback with too many steps returns first entry."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)

        # Rollback 10 steps, should return first
        prev = history.rollback(steps=10)
        assert prev is not None
        assert prev.html == "<div>1</div>"

    def test_rollback_empty_history(self):
        """Test rollback returns None on empty history."""
        history = HistoryManager()
        assert history.rollback(steps=1) is None

    def test_rollback_to_phase(self):
        """Test rolling back to a specific phase."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)
        history.push("<div>3</div>", FixPhase.LLM_FIX)

        rollback = history.rollback_to_phase(FixPhase.DETERMINISTIC)
        assert rollback is not None
        assert rollback.html == "<div>2</div>"

    def test_rollback_to_phase_not_found(self):
        """Test rollback_to_phase returns None if phase not found."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)

        assert history.rollback_to_phase(FixPhase.LLM_FIX) is None

    def test_max_entries_limit(self):
        """Test that history respects max_entries limit."""
        history = HistoryManager(max_entries=3)

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)
        history.push("<div>3</div>", FixPhase.LLM_FIX)
        history.push("<div>4</div>", FixPhase.LLM_FIX)

        assert len(history) == 3

        # First entry should be removed
        assert history.original.html == "<div>2</div>"

    def test_get_score_delta(self):
        """Test calculating score delta between phases."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL, score=0.3)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC, score=0.7)

        delta = history.get_score_delta(FixPhase.INITIAL, FixPhase.DETERMINISTIC)
        assert delta is not None
        assert delta == pytest.approx(0.4)

    def test_get_score_delta_negative(self):
        """Test score delta can be negative (regression)."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.DETERMINISTIC, score=0.8)
        history.push("<div>2</div>", FixPhase.LLM_FIX, score=0.5)

        delta = history.get_score_delta(FixPhase.DETERMINISTIC, FixPhase.LLM_FIX)
        assert delta is not None
        assert delta == pytest.approx(-0.3)

    def test_get_score_delta_missing_phase(self):
        """Test get_score_delta returns None if phase not found."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL, score=0.5)

        assert history.get_score_delta(FixPhase.INITIAL, FixPhase.LLM_FIX) is None

    def test_get_score_delta_no_scores(self):
        """Test get_score_delta returns None if no scores."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)

        assert history.get_score_delta(FixPhase.INITIAL, FixPhase.DETERMINISTIC) is None

    def test_get_all(self):
        """Test get_all returns copy of history."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)

        all_entries = history.get_all()
        assert len(all_entries) == 2

        # Should be a copy
        all_entries.append(HistoryEntry(html="<div>3</div>", phase=FixPhase.LLM_FIX))
        assert len(history) == 2  # Original unchanged

    def test_original_property(self):
        """Test original property returns first entry."""
        history = HistoryManager()

        history.push("<div>original</div>", FixPhase.INITIAL)
        history.push("<div>modified</div>", FixPhase.DETERMINISTIC)

        assert history.original.html == "<div>original</div>"

    def test_original_empty_history(self):
        """Test original returns None on empty history."""
        history = HistoryManager()
        assert history.original is None

    def test_clear(self):
        """Test clearing history."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC)

        history.clear()
        assert len(history) == 0
        assert history.latest is None

    def test_describe(self):
        """Test describe generates summary."""
        history = HistoryManager()

        history.push("<div>1</div>", FixPhase.INITIAL, score=0.5)
        history.push("<div>2</div>", FixPhase.DETERMINISTIC, score=0.8)

        desc = history.describe()
        assert "2 entries" in desc
        assert "initial" in desc.lower()
        assert "deterministic" in desc.lower()

    def test_len(self):
        """Test __len__ returns entry count."""
        history = HistoryManager()

        assert len(history) == 0

        history.push("<div>1</div>", FixPhase.INITIAL)
        assert len(history) == 1

        history.push("<div>2</div>", FixPhase.DETERMINISTIC)
        assert len(history) == 2

    def test_metadata_stored(self):
        """Test that metadata is stored correctly."""
        history = HistoryManager()

        history.push(
            "<div>test</div>",
            FixPhase.LLM_FIX,
            attempt=2,
            model="gemini-flash"
        )

        latest = history.latest
        assert latest.metadata.get("attempt") == 2
        assert latest.metadata.get("model") == "gemini-flash"

    def test_patches_applied_stored(self):
        """Test that patches_applied is stored."""
        history = HistoryManager()

        patches = ["patch1", "patch2"]
        history.push("<div>test</div>", FixPhase.DETERMINISTIC, patches_applied=patches)

        latest = history.latest
        assert latest.patches_applied == patches
