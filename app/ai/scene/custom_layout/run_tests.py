#!/usr/bin/env python
"""
Test runner for custom_layout module.

This script runs the tests while preventing imports from the parent app.ai package.
"""

import sys
import os
from pathlib import Path
from types import ModuleType

# Get the custom_layout directory
CUSTOM_LAYOUT_DIR = Path(__file__).parent.resolve()

# Add custom_layout to the start of sys.path
sys.path.insert(0, str(CUSTOM_LAYOUT_DIR))

# Create stub modules to prevent loading the real app.ai package
# This intercepts imports to app.ai.* and returns empty modules
class StubModule(ModuleType):
    def __getattr__(self, name):
        return StubModule(f"{self.__name__}.{name}")

# Pre-populate sys.modules with stubs for the parent packages
for pkg in ["app", "app.ai", "app.ai.router", "app.ai.providers",
            "app.ai.scene", "app.ai.scene.custom_layout"]:
    if pkg not in sys.modules:
        sys.modules[pkg] = StubModule(pkg)

# Now we can safely import pytest and run
if __name__ == "__main__":
    import subprocess

    # Change to custom_layout directory
    os.chdir(CUSTOM_LAYOUT_DIR)

    # Build pytest command
    args = sys.argv[1:] if len(sys.argv) > 1 else ["-v"]
    cmd = [sys.executable, "-m", "pytest", "tests/unit"] + args

    # Run pytest as subprocess to avoid import issues
    result = subprocess.run(cmd, cwd=CUSTOM_LAYOUT_DIR)
    sys.exit(result.returncode)
