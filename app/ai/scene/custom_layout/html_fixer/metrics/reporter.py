"""
Metrics Reporter - Generates reports from collected metrics.

Sprint 8: Provides summary statistics and formatted reports.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from statistics import mean, stdev

from .collector import RunMetrics


@dataclass
class MetricsSummary:
    """Summary statistics from collected metrics."""

    total_runs: int
    """Total number of runs analyzed."""

    passed_runs: int
    """Number of runs that passed validation."""

    pass_rate: float
    """Percentage of runs that passed (0.0-1.0)."""

    avg_fix_rate: float
    """Average fix rate across all runs."""

    avg_duration_ms: float
    """Average duration in milliseconds."""

    avg_score: float
    """Average validation score."""

    deterministic_ratio: float
    """Ratio of deterministic to total fixes."""

    total_errors_fixed: int
    """Total errors fixed across all runs."""

    total_llm_tokens: int
    """Total LLM tokens consumed."""

    total_rollbacks: int
    """Total rollbacks performed."""

    # Optional variability metrics
    fix_rate_std: Optional[float] = None
    """Standard deviation of fix rates."""

    duration_std: Optional[float] = None
    """Standard deviation of durations."""


class MetricsReporter:
    """Generates reports from collected metrics."""

    def __init__(self, metrics: List[RunMetrics]):
        """
        Initialize reporter with metrics data.

        Args:
            metrics: List of RunMetrics to analyze.
        """
        self._metrics = metrics

    def summary(self) -> MetricsSummary:
        """
        Generate summary statistics.

        Returns:
            MetricsSummary with aggregate statistics.
        """
        if not self._metrics:
            return MetricsSummary(
                total_runs=0,
                passed_runs=0,
                pass_rate=0.0,
                avg_fix_rate=0.0,
                avg_duration_ms=0.0,
                avg_score=0.0,
                deterministic_ratio=0.0,
                total_errors_fixed=0,
                total_llm_tokens=0,
                total_rollbacks=0,
            )

        passed_runs = sum(1 for m in self._metrics if m.passed)
        pass_rate = passed_runs / len(self._metrics)

        fix_rates = [m.fix_rate for m in self._metrics]
        durations = [m.duration_ms for m in self._metrics]
        scores = [m.score for m in self._metrics]

        # Calculate deterministic ratio
        total_det = sum(m.deterministic_fixes for m in self._metrics)
        total_llm = sum(m.llm_fixes for m in self._metrics)
        total_fixes = total_det + total_llm
        det_ratio = total_det / total_fixes if total_fixes > 0 else 1.0

        # Calculate errors fixed
        total_errors_fixed = sum(
            m.initial_errors - m.final_errors
            for m in self._metrics
        )

        # Standard deviations (require at least 2 data points)
        fix_rate_std = stdev(fix_rates) if len(fix_rates) >= 2 else None
        duration_std = stdev(durations) if len(durations) >= 2 else None

        return MetricsSummary(
            total_runs=len(self._metrics),
            passed_runs=passed_runs,
            pass_rate=pass_rate,
            avg_fix_rate=mean(fix_rates),
            avg_duration_ms=mean(durations),
            avg_score=mean(scores),
            deterministic_ratio=det_ratio,
            total_errors_fixed=total_errors_fixed,
            total_llm_tokens=sum(m.llm_tokens for m in self._metrics),
            total_rollbacks=sum(m.rollbacks for m in self._metrics),
            fix_rate_std=fix_rate_std,
            duration_std=duration_std,
        )

    def by_fixture(self) -> Dict[str, MetricsSummary]:
        """
        Generate per-fixture summaries.

        Returns:
            Dictionary mapping fixture names to their summaries.
        """
        fixtures: Dict[str, List[RunMetrics]] = {}
        for m in self._metrics:
            if m.fixture_name not in fixtures:
                fixtures[m.fixture_name] = []
            fixtures[m.fixture_name].append(m)

        return {
            name: MetricsReporter(metrics).summary()
            for name, metrics in fixtures.items()
        }

    def trend(self, window_size: int = 10) -> List[MetricsSummary]:
        """
        Calculate metrics trends over time.

        Args:
            window_size: Number of runs per window.

        Returns:
            List of summaries, one per window.
        """
        if len(self._metrics) < window_size:
            return [self.summary()]

        sorted_metrics = sorted(self._metrics, key=lambda m: m.timestamp)
        summaries = []

        for i in range(0, len(sorted_metrics), window_size):
            window = sorted_metrics[i:i + window_size]
            summaries.append(MetricsReporter(window).summary())

        return summaries

    def to_markdown(self) -> str:
        """
        Generate a markdown report.

        Returns:
            Formatted markdown string.
        """
        summary = self.summary()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        report = f"""# HTML Fixer Metrics Report

Generated: {now}

## Summary

| Metric | Value |
|--------|-------|
| Total Runs | {summary.total_runs} |
| Passed Runs | {summary.passed_runs} |
| Pass Rate | {summary.pass_rate:.1%} |
| Avg Fix Rate | {summary.avg_fix_rate:.1%} |
| Avg Score | {summary.avg_score:.1%} |
| Avg Duration | {summary.avg_duration_ms:.0f}ms |
| Deterministic Ratio | {summary.deterministic_ratio:.1%} |
| Total Errors Fixed | {summary.total_errors_fixed} |
| Total LLM Tokens | {summary.total_llm_tokens:,} |
| Total Rollbacks | {summary.total_rollbacks} |

"""

        # Add per-fixture breakdown if multiple fixtures
        fixture_summaries = self.by_fixture()
        if len(fixture_summaries) > 1:
            report += """## By Fixture

| Fixture | Runs | Pass Rate | Avg Score | Avg Duration |
|---------|------|-----------|-----------|--------------|
"""
            for name, s in sorted(fixture_summaries.items()):
                report += f"| {name} | {s.total_runs} | {s.pass_rate:.1%} | {s.avg_score:.1%} | {s.avg_duration_ms:.0f}ms |\n"

        # Add recent runs
        if self._metrics:
            report += """
## Recent Runs

| Timestamp | Fixture | Score | Fix Rate | Duration | Status |
|-----------|---------|-------|----------|----------|--------|
"""
            recent = sorted(self._metrics, key=lambda m: m.timestamp, reverse=True)[:10]
            for m in recent:
                ts = m.timestamp.strftime("%Y-%m-%d %H:%M")
                status = "PASS" if m.passed else "FAIL"
                report += f"| {ts} | {m.fixture_name} | {m.score:.1%} | {m.fix_rate:.1%} | {m.duration_ms:.0f}ms | {status} |\n"

        return report

    def to_dict(self) -> Dict:
        """
        Export summary as dictionary.

        Returns:
            Dictionary with all summary metrics.
        """
        s = self.summary()
        return {
            "total_runs": s.total_runs,
            "passed_runs": s.passed_runs,
            "pass_rate": s.pass_rate,
            "avg_fix_rate": s.avg_fix_rate,
            "avg_duration_ms": s.avg_duration_ms,
            "avg_score": s.avg_score,
            "deterministic_ratio": s.deterministic_ratio,
            "total_errors_fixed": s.total_errors_fixed,
            "total_llm_tokens": s.total_llm_tokens,
            "total_rollbacks": s.total_rollbacks,
            "fixtures": {
                name: {
                    "runs": fs.total_runs,
                    "pass_rate": fs.pass_rate,
                    "avg_score": fs.avg_score,
                }
                for name, fs in self.by_fixture().items()
            },
        }
