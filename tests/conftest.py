"""Test configuration.

Adds the project root to ``sys.path`` so ``main.py`` (which lives at the
repository root, not inside the ``src`` package) can be imported by the
end-to-end test.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
