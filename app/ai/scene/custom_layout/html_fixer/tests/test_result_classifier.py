"""
Tests for ResultClassifier (Sprint 5).

Tests the semantic classification of interaction results.
"""

import pytest
from html_fixer.sandbox.result_classifier import (
    ResultClassifier,
    InteractionClassification,
    ClassificationResult,
)
from html_fixer.sandbox.diff_engine import DiffResult, RegionDiff, ComparisonScale
from html_fixer.sandbox.contracts import ElementInfo


class TestResultClassifier:
    """Unit tests for ResultClassifier."""

    def _make_diff_result(
        self,
        tight: float = 0.0,
        local: float = 0.0,
        global_: float = 0.0,
    ) -> DiffResult:
        """Helper to create DiffResult with given ratios."""
        return DiffResult(
            tight=RegionDiff(ComparisonScale.TIGHT, tight, int(tight * 1000), 1000),
            local=RegionDiff(ComparisonScale.LOCAL, local, int(local * 5000), 5000),
            global_=RegionDiff(ComparisonScale.GLOBAL, global_, int(global_ * 50000), 50000),
            element_box={"x": 50, "y": 50, "width": 100, "height": 50},
            has_significant_change=(tight >= 0.02 or local >= 0.02 or global_ >= 0.02),
            primary_change_location=ComparisonScale.TIGHT,
        )

    def _make_element(self) -> ElementInfo:
        """Helper to create test ElementInfo."""
        return ElementInfo(
            selector=".test-btn",
            tag="button",
            bounding_box={"x": 50, "y": 50, "width": 100, "height": 50},
        )

    def test_classify_responsive(self):
        """Test RESPONSIVE classification."""
        classifier = ResultClassifier()
        diff = self._make_diff_result(tight=0.05)  # 5% tight change
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.RESPONSIVE
        assert result.confidence >= 1.0
        assert "feedback" in result.reasoning.lower()

    def test_classify_no_response(self):
        """Test NO_RESPONSE classification."""
        classifier = ResultClassifier()
        diff = self._make_diff_result(tight=0.0, local=0.0, global_=0.0)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.NO_RESPONSE
        assert "no visual change" in result.reasoning.lower()

    def test_classify_weak_feedback(self):
        """Test WEAK_FEEDBACK classification."""
        classifier = ResultClassifier()
        # 1% - above weak threshold (0.5%), below responsive (2%)
        diff = self._make_diff_result(tight=0.01)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.WEAK_FEEDBACK
        assert "subtle" in result.reasoning.lower()

    def test_classify_cascade_effect_local(self):
        """Test CASCADE_EFFECT classification from local change."""
        classifier = ResultClassifier()
        # Change in local but not tight
        diff = self._make_diff_result(tight=0.001, local=0.03, global_=0.02)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.CASCADE_EFFECT
        assert "outside element" in result.reasoning.lower()

    def test_classify_cascade_effect_global(self):
        """Test CASCADE_EFFECT classification from global change."""
        classifier = ResultClassifier()
        # Global change without tight change, but not enough for navigation
        diff = self._make_diff_result(tight=0.001, local=0.008, global_=0.02)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.CASCADE_EFFECT

    def test_classify_navigation(self):
        """Test NAVIGATION classification."""
        classifier = ResultClassifier()
        # Large global change relative to local (ratio > 5)
        diff = self._make_diff_result(tight=0.001, local=0.01, global_=0.50)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.NAVIGATION
        assert "navigation" in result.reasoning.lower()

    def test_is_passing_responsive(self):
        """Test is_passing for RESPONSIVE."""
        classifier = ResultClassifier()
        assert classifier.is_passing(InteractionClassification.RESPONSIVE)

    def test_is_passing_navigation(self):
        """Test is_passing for NAVIGATION."""
        classifier = ResultClassifier()
        assert classifier.is_passing(InteractionClassification.NAVIGATION)

    def test_is_passing_cascade(self):
        """Test is_passing for CASCADE_EFFECT."""
        classifier = ResultClassifier()
        assert classifier.is_passing(InteractionClassification.CASCADE_EFFECT)

    def test_is_not_passing_weak_feedback(self):
        """Test is_passing returns False for WEAK_FEEDBACK."""
        classifier = ResultClassifier()
        assert not classifier.is_passing(InteractionClassification.WEAK_FEEDBACK)

    def test_is_not_passing_no_response(self):
        """Test is_passing returns False for NO_RESPONSE."""
        classifier = ResultClassifier()
        assert not classifier.is_passing(InteractionClassification.NO_RESPONSE)

    def test_custom_thresholds(self):
        """Test classifier with custom thresholds."""
        classifier = ResultClassifier(
            responsive_threshold=0.05,
            weak_threshold=0.01,
        )

        # 3% would be responsive with default (2%) but not with 5%
        diff = self._make_diff_result(tight=0.03)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.classification == InteractionClassification.WEAK_FEEDBACK

    def test_classify_without_element(self):
        """Test classification works without ElementInfo."""
        classifier = ResultClassifier()
        diff = self._make_diff_result(tight=0.05)

        result = classifier.classify(diff, element=None)

        assert result.classification == InteractionClassification.RESPONSIVE

    def test_classify_from_ratios(self):
        """Test convenience method classify_from_ratios."""
        classifier = ResultClassifier()

        result = classifier.classify_from_ratios(
            tight=0.05,
            local=0.03,
            global_=0.02,
        )

        assert result.classification == InteractionClassification.RESPONSIVE

    def test_diff_ratios_in_result(self):
        """Test that diff_ratios are included in result."""
        classifier = ResultClassifier()
        diff = self._make_diff_result(tight=0.05, local=0.03, global_=0.01)
        element = self._make_element()

        result = classifier.classify(diff, element)

        assert result.diff_ratios["tight"] == 0.05
        assert result.diff_ratios["local"] == 0.03
        assert result.diff_ratios["global"] == 0.01


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_to_dict(self):
        """Test serialization."""
        result = ClassificationResult(
            classification=InteractionClassification.RESPONSIVE,
            confidence=0.95,
            reasoning="Clear feedback detected",
            primary_scale=ComparisonScale.TIGHT,
            diff_ratios={"tight": 0.05, "local": 0.02, "global": 0.01},
        )

        d = result.to_dict()
        assert d["classification"] == "responsive"
        assert d["confidence"] == 0.95
        assert d["reasoning"] == "Clear feedback detected"
        assert d["primary_scale"] == "tight"
        assert d["diff_ratios"]["tight"] == 0.05


class TestInteractionClassification:
    """Tests for InteractionClassification enum."""

    def test_all_classifications_exist(self):
        """Test all expected classifications are defined."""
        assert InteractionClassification.RESPONSIVE.value == "responsive"
        assert InteractionClassification.NAVIGATION.value == "navigation"
        assert InteractionClassification.CASCADE_EFFECT.value == "cascade_effect"
        assert InteractionClassification.WEAK_FEEDBACK.value == "weak_feedback"
        assert InteractionClassification.NO_RESPONSE.value == "no_response"
