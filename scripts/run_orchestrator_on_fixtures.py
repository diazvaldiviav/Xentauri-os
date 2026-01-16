#!/usr/bin/env python3
"""
Run the full Orchestrator pipeline (deterministic + LLM) on selected fixtures.
This script is for testing only; it doesn't modify repository files.
"""
import asyncio
import logging
from pathlib import Path

# Adjust path so imports resolve when running from project root
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

# Ensure the html_fixer package (located under app/ai/scene/custom_layout) is importable
sys.path.insert(0, str(ROOT / "app" / "ai" / "scene" / "custom_layout"))

from html_fixer.orchestrator import Orchestrator

FIXTURES = [
    "app/ai/scene/custom_layout/html_fixer/tests/fixtures/edge_cases/animation_conflict.html",
    "app/ai/scene/custom_layout/html_fixer/tests/fixtures/edge_cases/iframe_embedded.html",
    "app/ai/scene/custom_layout/html_fixer/tests/fixtures/edge_cases/pseudo_elements.html",
]

OUTPUT_DIR = Path("/tmp/jarvis_fixer_runs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_orchestrator")

async def run_one(path: str):
    p = Path(path)
    html = p.read_text(encoding="utf-8")
    orchestrator = Orchestrator()

    logger.info(f"Running orchestrator on {p.name}")
    result = await orchestrator.fix(html)

    out = {
        "fixture": p.name,
        "success": result.success,
        "final_score": getattr(result, 'final_score', None),
        "phases_completed": [ph.value for ph in getattr(result, 'phases_completed', [])],
        "metrics": result.metrics.__dict__ if result.metrics else None,
        "errors_fixed": getattr(result, 'errors_fixed', None),
        "errors_remaining": getattr(result, 'errors_remaining', None),
        "validation_passed": getattr(result, 'validation_passed', None),
    }

    # Save result html if available
    out_dir = OUTPUT_DIR / p.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(str(out), encoding="utf-8")

    if getattr(result, "fixed_html", None):
        (out_dir / "fixed.html").write_text(result.fixed_html, encoding="utf-8")

    logger.info(f"Fixture {p.name}: success={result.success}, phases={out['phases_completed']}")
    return result

async def main():
    results = []
    for f in FIXTURES:
        try:
            r = await run_one(f)
            results.append((f, r))
        except Exception as e:
            logger.exception(f"Failed on {f}: {e}")
    return results

if __name__ == '__main__':
    asyncio.run(main())
