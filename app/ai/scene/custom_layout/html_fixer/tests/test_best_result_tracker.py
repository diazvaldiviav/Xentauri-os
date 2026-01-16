"""
Tests for BestResultTracker (Sprint 7).

Tests tracking the best HTML result during fixing.
"""

import pytest
from html_fixer.orchestrator.contracts import FixPhase
from html_fixer.orchestrator.best_result_tracker import BestResultTracker


class TestBestResultTracker:
    """Tests for BestResultTracker."""

    def test_initial_state(self):
        """Test initial state with original HTML."""
        tracker = BestResultTracker("<div>original</div>")

        assert tracker.best_html == "<div>original</div>"
        assert tracker.best_score == 0.0
        assert tracker.best_phase == FixPhase.INITIAL
        assert tracker.improved is False

    def test_update_improves(self):
        """Test update when score improves."""
        tracker = BestResultTracker("<div>original</div>")

        # First update with improvement
        result = tracker.update(
            "<div>fixed</div>",
            score=0.7,
            phase=FixPhase.DETERMINISTIC,
            errors_remaining=2
        )

        assert result is True  # Became new best
        assert tracker.best_html == "<div>fixed</div>"
        assert tracker.best_score == 0.7
        assert tracker.best_phase == FixPhase.DETERMINISTIC
        assert tracker.best_errors == 2

    def test_update_no_improvement(self):
        """Test update when score doesn't improve."""
        tracker = BestResultTracker("<div>original</div>")

        # First update
        tracker.update("<div>fixed</div>", score=0.8, phase=FixPhase.DETERMINISTIC)

        # Second update with lower score
        result = tracker.update("<div>worse</div>", score=0.5, phase=FixPhase.LLM_FIX)

        assert result is False  # Did not become new best
        assert tracker.best_html == "<div>fixed</div>"  # Still the first
        assert tracker.best_score == 0.8

    def test_update_equal_score(self):
        """Test update with equal score doesn't replace."""
        tracker = BestResultTracker("<div>original</div>")

        tracker.update("<div>first</div>", score=0.7, phase=FixPhase.DETERMINISTIC)
        result = tracker.update("<div>second</div>", score=0.7, phase=FixPhase.LLM_FIX)

        assert result is False  # Equal doesn't replace
        assert tracker.best_html == "<div>first</div>"

    def test_improved_property(self):
        """Test improved property."""
        tracker = BestResultTracker("<div>original</div>")

        # Initially not improved
        assert tracker.improved is False

        # After update with score > 0
        tracker.update("<div>fixed</div>", score=0.5, phase=FixPhase.DETERMINISTIC)
        assert tracker.improved is True

    def test_improved_false_when_same_html(self):
        """Test improved is False when HTML unchanged."""
        tracker = BestResultTracker("<div>original</div>")

        # Update with same HTML
        tracker.update("<div>original</div>", score=0.5, phase=FixPhase.DETERMINISTIC)

        assert tracker.improved is False  # Same HTML

    def test_improved_false_when_zero_score(self):
        """Test improved is False when score is 0."""
        tracker = BestResultTracker("<div>original</div>")

        # Score stays 0
        assert tracker.improved is False

    def test_original_property(self):
        """Test original property returns initial HTML."""
        tracker = BestResultTracker("<div>original</div>")

        tracker.update("<div>fixed</div>", score=0.9, phase=FixPhase.LLM_FIX)

        assert tracker.original == "<div>original</div>"

    def test_updates_count(self):
        """Test updates_count tracks update calls."""
        tracker = BestResultTracker("<div>original</div>")

        assert tracker.updates_count == 0

        tracker.update("<div>1</div>", score=0.5, phase=FixPhase.DETERMINISTIC)
        assert tracker.updates_count == 1

        tracker.update("<div>2</div>", score=0.3, phase=FixPhase.LLM_FIX)  # Won't improve
        assert tracker.updates_count == 2  # Still counted

    def test_multiple_updates_track_best(self):
        """Test multiple updates always track the best."""
        tracker = BestResultTracker("<div>original</div>")

        tracker.update("<div>1</div>", score=0.3, phase=FixPhase.DETERMINISTIC)
        tracker.update("<div>2</div>", score=0.8, phase=FixPhase.LLM_FIX)
        tracker.update("<div>3</div>", score=0.5, phase=FixPhase.LLM_FIX)
        tracker.update("<div>4</div>", score=0.6, phase=FixPhase.LLM_FIX)

        # Best should be #2 with score 0.8
        assert tracker.best_html == "<div>2</div>"
        assert tracker.best_score == 0.8
        assert tracker.best_phase == FixPhase.LLM_FIX

    def test_describe(self):
        """Test describe generates summary."""
        tracker = BestResultTracker("<div>original</div>")

        tracker.update("<div>fixed</div>", score=0.85, phase=FixPhase.DETERMINISTIC, errors_remaining=2)

        desc = tracker.describe()

        assert "IMPROVED" in desc
        assert "85" in desc or "0.85" in desc  # Score
        assert "deterministic" in desc.lower()
        assert "2" in desc  # Errors

    def test_describe_unchanged(self):
        """Test describe shows UNCHANGED when not improved."""
        tracker = BestResultTracker("<div>original</div>")

        desc = tracker.describe()

        assert "UNCHANGED" in desc

    def test_repr(self):
        """Test string representation."""
        tracker = BestResultTracker("<div>original</div>")
        tracker.update("<div>fixed</div>", score=0.75, phase=FixPhase.DETERMINISTIC)

        repr_str = repr(tracker)

        assert "75" in repr_str or "0.75" in repr_str
        assert "deterministic" in repr_str.lower()

    def test_best_errors_tracking(self):
        """Test best_errors is tracked correctly."""
        tracker = BestResultTracker("<div>original</div>")

        tracker.update("<div>1</div>", score=0.5, phase=FixPhase.DETERMINISTIC, errors_remaining=5)
        assert tracker.best_errors == 5

        tracker.update("<div>2</div>", score=0.8, phase=FixPhase.LLM_FIX, errors_remaining=2)
        assert tracker.best_errors == 2  # Updated with new best

        tracker.update("<div>3</div>", score=0.6, phase=FixPhase.LLM_FIX, errors_remaining=3)
        assert tracker.best_errors == 2  # Still from the best result
