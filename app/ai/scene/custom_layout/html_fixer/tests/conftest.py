"""
Pytest configuration for html_fixer tests.

Sets up the Python path to allow imports of html_fixer modules.
"""

import sys
from pathlib import Path

# Add custom_layout directory to path (parent of html_fixer)
custom_layout_dir = Path(__file__).resolve().parent.parent.parent
if str(custom_layout_dir) not in sys.path:
    sys.path.insert(0, str(custom_layout_dir))
