"""
Metrics Module - Collecting, reporting, and visualizing html_fixer metrics.

Sprint 8: Dashboard for tracking fix rates, performance, and LLM usage.

Usage:
    from ..metrics import MetricsCollector, MetricsReporter, MetricsDashboard

    # Collect metrics from orchestrator runs
    collector = MetricsCollector()
    collector.record(result, fixture_name="my_fixture")

    # Generate reports
    reporter = MetricsReporter(collector.runs)
    print(reporter.to_markdown())

    # Display CLI dashboard
    dashboard = MetricsDashboard(collector)
    print(dashboard.display())
"""

from .collector import MetricsCollector, RunMetrics
from .reporter import MetricsReporter
from .dashboard import MetricsDashboard

__all__ = ["MetricsCollector", "MetricsReporter", "MetricsDashboard", "RunMetrics"]
