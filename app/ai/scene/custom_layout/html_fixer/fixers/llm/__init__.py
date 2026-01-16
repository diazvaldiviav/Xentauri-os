"""
LLM Fixers - AI-powered surgical HTML repairs.

Sprint 6: LLM-based repairs for JavaScript errors and visual feedback issues.

Uses GeminiProvider with Gemini 3 Flash for generating:
- Tailwind CSS classes for visual feedback
- JavaScript code fixes for runtime errors

Usage:
    from html_fixer.fixers.llm import LLMFixer

    fixer = LLMFixer()
    result = await fixer.fix(errors, html)

    if result.success:
        print(f"Applied {len(result.tailwind_patches)} Tailwind patches")
        print(f"Applied {len(result.js_patches)} JS patches")
        fixed_html = result.fixed_html
"""

# Main orchestrator
from .llm_fixer import LLMFixer, LLMFixResult

# Contracts
from .contracts import JSPatch, JSPatchType, JSPatchSet

# Prompt builders
from .prompt_builders import (
    PromptBuilder,
    FixContext,
    TailwindPromptBuilder,
    JSPromptBuilder,
)

# Validators
from .validators import (
    PatchValidator,
    TailwindPatchValidator,
    JSPatchValidator,
)

# Appliers
from .js_patch_applier import JSPatchApplier, ApplyResult

__all__ = [
    # Main class
    "LLMFixer",
    "LLMFixResult",
    # Contracts
    "JSPatch",
    "JSPatchType",
    "JSPatchSet",
    # Prompt builders
    "PromptBuilder",
    "FixContext",
    "TailwindPromptBuilder",
    "JSPromptBuilder",
    # Validators
    "PatchValidator",
    "TailwindPatchValidator",
    "JSPatchValidator",
    # Appliers
    "JSPatchApplier",
    "ApplyResult",
]
