"""
Pytest configuration for custom_layout HTML fixer tests.

Provides fixtures for:
- Loading HTML test files
- Playwright browser automation
- Tailwind class analysis
"""

import sys
from pathlib import Path

# Add custom_layout to path for imports
_custom_layout_path = Path(__file__).parent.parent
if str(_custom_layout_path) not in sys.path:
    sys.path.insert(0, str(_custom_layout_path))

import asyncio
import logging
from typing import List, Optional

import pytest


# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("custom_layout.tests")


# ============================================================================
# PATH FIXTURES
# ============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return FIXTURES_DIR


@pytest.fixture
def trivia_dir() -> Path:
    """Return the trivia fixtures directory."""
    return FIXTURES_DIR / "trivia"


@pytest.fixture
def dashboard_dir() -> Path:
    """Return the dashboard fixtures directory."""
    return FIXTURES_DIR / "dashboard"


@pytest.fixture
def modals_dir() -> Path:
    """Return the modals fixtures directory."""
    return FIXTURES_DIR / "modals"


# ============================================================================
# HTML FILE FIXTURES
# ============================================================================

@pytest.fixture
def trivia_fixtures(trivia_dir: Path) -> List[Path]:
    """Return list of all trivia HTML fixtures."""
    return sorted(trivia_dir.glob("*.html"))


@pytest.fixture
def dashboard_fixtures(dashboard_dir: Path) -> List[Path]:
    """Return list of all dashboard HTML fixtures."""
    return sorted(dashboard_dir.glob("*.html"))


@pytest.fixture
def modal_fixtures(modals_dir: Path) -> List[Path]:
    """Return list of all modal HTML fixtures."""
    return sorted(modals_dir.glob("*.html"))


@pytest.fixture
def all_fixtures(fixtures_dir: Path) -> List[Path]:
    """Return list of all HTML fixtures across all categories."""
    return sorted(fixtures_dir.rglob("*.html"))


@pytest.fixture
def broken_fixtures(fixtures_dir: Path) -> List[Path]:
    """Return list of all *_broken.html fixtures."""
    return sorted(fixtures_dir.rglob("*_broken.html"))


@pytest.fixture
def expected_fixtures(fixtures_dir: Path) -> List[Path]:
    """Return list of all *_expected.html fixtures."""
    return sorted(fixtures_dir.rglob("*_expected.html"))


# ============================================================================
# HTML LOADING UTILITIES
# ============================================================================

def load_html(path: Path) -> str:
    """Load HTML content from file."""
    return path.read_text(encoding="utf-8")


@pytest.fixture
def load_fixture():
    """Return a function to load HTML fixtures by name."""
    def _load(category: str, name: str) -> str:
        path = FIXTURES_DIR / category / f"{name}.html"
        if not path.exists():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return load_html(path)
    return _load


# ============================================================================
# PLAYWRIGHT FIXTURES
# ============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def browser():
    """
    Playwright browser fixture.

    Usage:
        async def test_something(browser):
            page = await browser.new_page()
            ...
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed: pip install playwright && playwright install chromium")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser):
    """
    Playwright page fixture with 1920x1080 viewport.

    Usage:
        async def test_click(page):
            await page.set_content(html)
            await page.click("button")
    """
    page = await browser.new_page(viewport={"width": 1920, "height": 1080})
    yield page
    await page.close()


@pytest.fixture
async def page_with_html(page):
    """
    Return a function to load HTML into the page.

    Usage:
        async def test_render(page_with_html):
            page = await page_with_html("<html>...</html>")
            # page is now loaded with the HTML
    """
    async def _load_html(html: str):
        await page.set_content(html, wait_until="networkidle")
        return page
    return _load_html


# ============================================================================
# SCREENSHOT UTILITIES
# ============================================================================

@pytest.fixture
async def take_screenshot(page):
    """
    Return a function to take screenshots.

    Usage:
        async def test_visual(take_screenshot):
            before = await take_screenshot()
            await page.click("button")
            after = await take_screenshot()
    """
    async def _screenshot(path: Optional[str] = None) -> bytes:
        screenshot = await page.screenshot(full_page=False)
        if path:
            Path(path).write_bytes(screenshot)
        return screenshot
    return _screenshot


# ============================================================================
# ELEMENT INTERACTION UTILITIES
# ============================================================================

@pytest.fixture
async def click_and_compare(page, take_screenshot):
    """
    Return a function that clicks an element and compares screenshots.

    Returns tuple of (before_bytes, after_bytes, pixel_diff_ratio).

    Usage:
        async def test_button(click_and_compare):
            before, after, diff = await click_and_compare("button.my-btn")
            assert diff > 0.02  # At least 2% change
    """
    async def _click_compare(selector: str) -> tuple:
        before = await take_screenshot()
        await page.click(selector)
        await page.wait_for_timeout(200)  # Wait for animations
        after = await take_screenshot()

        # Simple pixel comparison
        diff_ratio = _compare_screenshots(before, after)
        return before, after, diff_ratio

    return _click_compare


def _compare_screenshots(before: bytes, after: bytes) -> float:
    """
    Compare two screenshots and return pixel difference ratio.

    Returns float between 0.0 (identical) and 1.0 (completely different).
    """
    try:
        from PIL import Image
        import io

        img1 = Image.open(io.BytesIO(before)).convert("RGB")
        img2 = Image.open(io.BytesIO(after)).convert("RGB")

        if img1.size != img2.size:
            return 1.0  # Different sizes = completely different

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        diff_count = sum(1 for p1, p2 in zip(pixels1, pixels2) if _pixels_differ(p1, p2))
        return diff_count / len(pixels1)

    except ImportError:
        logger.warning("PIL not installed, skipping screenshot comparison")
        return 0.0


def _pixels_differ(p1: tuple, p2: tuple, threshold: int = 20) -> bool:
    """Check if two RGB pixels differ by more than threshold."""
    return any(abs(c1 - c2) > threshold for c1, c2 in zip(p1, p2))


# ============================================================================
# TAILWIND ANALYSIS FIXTURES
# ============================================================================

@pytest.fixture
def extract_classes():
    """
    Return a function to extract Tailwind classes from HTML.

    Usage:
        def test_classes(extract_classes):
            classes = extract_classes(html, ".my-button")
            assert "z-10" in classes
    """
    def _extract(html: str, selector: str) -> set:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        element = soup.select_one(selector)

        if not element:
            return set()

        classes = element.get("class", [])
        return set(classes) if isinstance(classes, list) else set()

    return _extract


# ============================================================================
# TEST MARKERS
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "playwright: marks tests that require Playwright"
    )
    config.addinivalue_line(
        "markers", "visual: marks tests that compare screenshots"
    )


# ============================================================================
# ASYNC PLUGIN CONFIGURATION
# ============================================================================

@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"
