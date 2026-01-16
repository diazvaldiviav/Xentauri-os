"""
Benchmark fixtures and configuration.

Sprint 8: Provides common fixtures for performance benchmarks.
"""

import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def benchmark_html_simple():
    """Simple HTML for fast benchmarking."""
    return """<!DOCTYPE html>
<html>
<head><title>Simple</title><script src="https://cdn.tailwindcss.com"></script></head>
<body>
    <div class="container mx-auto p-4">
        <button onclick="handleClick()" class="btn opacity-0 bg-blue-500 text-white px-4 py-2 rounded">
            Click Me
        </button>
    </div>
</body>
</html>"""


@pytest.fixture
def benchmark_html_medium():
    """Medium complexity HTML for benchmarking."""
    return """<!DOCTYPE html>
<html>
<head><title>Medium</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto p-4">
        <div class="relative">
            <button onclick="handleClick()" class="btn opacity-0 bg-blue-500 text-white px-4 py-2 rounded">
                Invisible Button
            </button>
            <div class="overlay absolute inset-0 z-50 bg-black/50"></div>
        </div>

        <div class="card mt-4 transform rotate-y-180 [backface-visibility:hidden]">
            <h2 class="text-xl font-bold">Card Title</h2>
            <button class="action-btn px-4 py-2 bg-green-500 text-white rounded">
                Action
            </button>
        </div>

        <div class="hidden mt-4">
            <button class="hidden-btn px-4 py-2 bg-red-500 text-white rounded">
                Hidden Action
            </button>
        </div>
    </div>
</body>
</html>"""


@pytest.fixture
def benchmark_html_complex():
    """Complex HTML with multiple error types for benchmarking."""
    return """<!DOCTYPE html>
<html>
<head><title>Complex</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-100 min-h-screen p-8">
    <div class="max-w-4xl mx-auto space-y-8">
        <!-- Section 1: Visibility issues -->
        <section class="bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Quiz Section</h2>
            <div class="space-y-4">
                <button class="option-btn w-full p-4 opacity-0 bg-blue-100 rounded">Option A</button>
                <button class="option-btn w-full p-4 invisible bg-blue-100 rounded">Option B</button>
                <button class="option-btn w-full p-4 hidden bg-blue-100 rounded">Option C</button>
                <button class="option-btn w-full p-4 bg-blue-100 rounded">Option D</button>
            </div>
        </section>

        <!-- Section 2: Z-index conflicts -->
        <section class="relative bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Layered Content</h2>
            <button class="action-btn z-10 relative px-4 py-2 bg-green-500 text-white rounded">
                Background Action
            </button>
            <div class="overlay absolute inset-0 z-50 bg-gradient-to-r from-transparent to-black/20"></div>
        </section>

        <!-- Section 3: 3D transforms -->
        <section class="bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Flashcard</h2>
            <div class="flashcard-container perspective-1000">
                <div class="flashcard transform rotate-y-180 [backface-visibility:hidden]">
                    <div class="front absolute inset-0 bg-blue-500 text-white p-4 rounded">
                        <p>Question</p>
                    </div>
                    <div class="back absolute inset-0 bg-green-500 text-white p-4 rounded transform rotate-y-180">
                        <p>Answer</p>
                        <button class="flip-btn mt-2 px-4 py-2 bg-white/20 rounded">Flip</button>
                    </div>
                </div>
            </div>
        </section>

        <!-- Section 4: Pointer events -->
        <section class="relative bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Blocked Content</h2>
            <div class="flex gap-4">
                <button class="btn-1 px-4 py-2 bg-purple-500 text-white rounded">Button 1</button>
                <button class="btn-2 px-4 py-2 bg-purple-500 text-white rounded">Button 2</button>
                <button class="btn-3 px-4 py-2 bg-purple-500 text-white rounded">Button 3</button>
            </div>
            <div class="blocker absolute inset-0 pointer-events-auto"></div>
        </section>

        <!-- Section 5: Subtle feedback -->
        <section class="bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Actions</h2>
            <div class="flex gap-4">
                <button class="submit-btn px-6 py-3 bg-blue-500 text-white rounded-lg">Submit</button>
                <button class="cancel-btn px-6 py-3 border-2 border-gray-300 rounded-lg">Cancel</button>
            </div>
        </section>
    </div>
</body>
</html>"""


@pytest.fixture
def benchmark_errors():
    """Pre-classified errors for deterministic benchmark."""
    from html_fixer.contracts.errors import ErrorType
    from html_fixer.contracts.validation import ClassifiedError, TailwindInfo

    return [
        ClassifiedError(
            error_type=ErrorType.INVISIBLE_OPACITY,
            selector=".option-btn:nth-child(1)",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"opacity-0", "w-full", "p-4", "bg-blue-100", "rounded"}),
        ),
        ClassifiedError(
            error_type=ErrorType.INVISIBLE_VISIBILITY,
            selector=".option-btn:nth-child(2)",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"invisible", "w-full", "p-4", "bg-blue-100", "rounded"}),
        ),
        ClassifiedError(
            error_type=ErrorType.INVISIBLE_DISPLAY,
            selector=".option-btn:nth-child(3)",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"hidden", "w-full", "p-4", "bg-blue-100", "rounded"}),
        ),
        ClassifiedError(
            error_type=ErrorType.ZINDEX_CONFLICT,
            selector=".action-btn",
            element_tag="button",
            tailwind_info=TailwindInfo(
                all_classes={"z-10", "relative", "px-4", "py-2", "bg-green-500"},
                z_index=10,
                has_relative=True,
            ),
            confidence=0.85,
        ),
        ClassifiedError(
            error_type=ErrorType.TRANSFORM_3D_HIDDEN,
            selector=".flashcard .back",
            element_tag="div",
            tailwind_info=TailwindInfo(
                all_classes={"transform", "rotate-y-180", "[backface-visibility:hidden]"},
                has_backface_hidden=True,
            ),
        ),
        ClassifiedError(
            error_type=ErrorType.POINTER_BLOCKED,
            selector=".btn-1",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"px-4", "py-2", "bg-purple-500"}),
            blocking_element=".blocker",
        ),
        ClassifiedError(
            error_type=ErrorType.FEEDBACK_TOO_SUBTLE,
            selector=".submit-btn",
            element_tag="button",
            tailwind_info=TailwindInfo(all_classes={"px-6", "py-3", "bg-blue-500", "rounded-lg"}),
        ),
    ]


@pytest.fixture
def sample_fixture_path():
    """Path to a real fixture for integration benchmarks."""
    trivia_path = FIXTURES_DIR / "trivia" / "flashcard_3d.html"
    if trivia_path.exists():
        return trivia_path
    # Fallback to any existing fixture
    for html_file in FIXTURES_DIR.rglob("*.html"):
        return html_file
    return None
