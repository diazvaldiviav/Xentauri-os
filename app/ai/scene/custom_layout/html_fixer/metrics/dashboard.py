"""
Metrics Dashboard - CLI dashboard for viewing metrics.

Sprint 8: Provides a visual ASCII dashboard for quick metrics overview.
"""

from datetime import datetime
from typing import Optional

from .collector import MetricsCollector
from .reporter import MetricsReporter


class MetricsDashboard:
    """CLI dashboard for viewing html_fixer metrics."""

    def __init__(self, collector: MetricsCollector):
        """
        Initialize dashboard with a metrics collector.

        Args:
            collector: MetricsCollector with recorded runs.
        """
        self._collector = collector

    def display(self, width: int = 80) -> str:
        """
        Generate ASCII dashboard display.

        Args:
            width: Width of the dashboard in characters.

        Returns:
            Formatted ASCII dashboard string.
        """
        reporter = MetricsReporter(self._collector.runs)
        summary = reporter.summary()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build the dashboard
        lines = []
        lines.append(self._box_top(width))
        lines.append(self._centered("HTML FIXER METRICS DASHBOARD v1.0", width))
        lines.append(self._centered(now, width))
        lines.append(self._separator(width))

        if summary.total_runs == 0:
            lines.append(self._centered("No metrics recorded yet", width))
            lines.append(self._box_bottom(width))
            return "\n".join(lines)

        # Key metrics
        lines.append(self._metric_row("Pass Rate (golden set)", f"{summary.pass_rate:.1%}", width))
        lines.append(self._metric_row("Avg Fix Rate", f"{summary.avg_fix_rate:.1%}", width))
        lines.append(self._metric_row("Avg Score", f"{summary.avg_score:.1%}", width))
        lines.append(self._metric_row("Avg Duration", f"{summary.avg_duration_ms:.0f}ms", width))
        lines.append(self._metric_row("Deterministic Ratio", f"{summary.deterministic_ratio:.1%}", width))
        lines.append(self._metric_row("Total Runs", str(summary.total_runs), width))

        lines.append(self._separator(width))

        # Performance bar
        lines.append(self._progress_bar("Pass Rate", summary.pass_rate, width))
        lines.append(self._progress_bar("Fix Rate", summary.avg_fix_rate, width))
        lines.append(self._progress_bar("Det. Ratio", summary.deterministic_ratio, width))

        lines.append(self._separator(width))

        # Stats
        lines.append(self._metric_row("Total Errors Fixed", str(summary.total_errors_fixed), width))
        lines.append(self._metric_row("Total LLM Tokens", f"{summary.total_llm_tokens:,}", width))
        lines.append(self._metric_row("Total Rollbacks", str(summary.total_rollbacks), width))

        # Recent failures if any
        failed = self._collector.get_failed()
        if failed:
            lines.append(self._separator(width))
            lines.append(self._centered(f"RECENT FAILURES ({len(failed)})", width))
            for run in sorted(failed, key=lambda r: r.timestamp, reverse=True)[:3]:
                name = run.fixture_name[:20] if len(run.fixture_name) > 20 else run.fixture_name
                lines.append(self._metric_row(name, f"score={run.score:.1%}", width))

        lines.append(self._box_bottom(width))
        return "\n".join(lines)

    def display_compact(self) -> str:
        """
        Generate compact single-line status.

        Returns:
            Single-line status string.
        """
        reporter = MetricsReporter(self._collector.runs)
        summary = reporter.summary()

        if summary.total_runs == 0:
            return "[html_fixer] No metrics"

        status = "OK" if summary.pass_rate >= 0.9 else "WARN" if summary.pass_rate >= 0.7 else "FAIL"
        return (
            f"[html_fixer] {status} | "
            f"pass={summary.pass_rate:.0%} | "
            f"fix={summary.avg_fix_rate:.0%} | "
            f"det={summary.deterministic_ratio:.0%} | "
            f"runs={summary.total_runs}"
        )

    def display_json(self) -> str:
        """
        Generate JSON output for programmatic consumption.

        Returns:
            JSON string with metrics.
        """
        import json
        reporter = MetricsReporter(self._collector.runs)
        return json.dumps(reporter.to_dict(), indent=2)

    # =========================================================================
    # Private helper methods
    # =========================================================================

    def _box_top(self, width: int) -> str:
        """Generate top border of box."""
        return "+" + "-" * (width - 2) + "+"

    def _box_bottom(self, width: int) -> str:
        """Generate bottom border of box."""
        return "+" + "-" * (width - 2) + "+"

    def _separator(self, width: int) -> str:
        """Generate separator line."""
        return "|" + "-" * (width - 2) + "|"

    def _centered(self, text: str, width: int) -> str:
        """Generate centered text line."""
        inner_width = width - 4  # Account for "| " and " |"
        centered = text.center(inner_width)
        return f"| {centered} |"

    def _metric_row(self, label: str, value: str, width: int) -> str:
        """Generate a metric row with label and value."""
        inner_width = width - 4
        label_width = inner_width // 2
        value_width = inner_width - label_width - 3  # 3 for " : "

        label_formatted = label[:label_width].ljust(label_width)
        value_formatted = value[:value_width].rjust(value_width)

        return f"| {label_formatted} : {value_formatted} |"

    def _progress_bar(self, label: str, value: float, width: int) -> str:
        """Generate a progress bar."""
        inner_width = width - 4
        label_width = 12
        bar_width = inner_width - label_width - 10  # Space for percentage

        filled = int(bar_width * min(value, 1.0))
        empty = bar_width - filled

        bar = "[" + "#" * filled + "-" * empty + "]"
        pct = f"{value:.0%}".rjust(5)

        label_formatted = label[:label_width].ljust(label_width)
        return f"| {label_formatted} {bar} {pct} |"


def main():
    """CLI entry point for dashboard."""
    import sys

    # Create a collector with default storage
    storage_path = "html_fixer_metrics.jsonl"
    collector = MetricsCollector(storage_path)

    dashboard = MetricsDashboard(collector)

    if "--json" in sys.argv:
        print(dashboard.display_json())
    elif "--compact" in sys.argv:
        print(dashboard.display_compact())
    else:
        print(dashboard.display())


if __name__ == "__main__":
    main()
