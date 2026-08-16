"""Make ``pytest`` work in a fresh checkout without installing anything first.

If codecard is installed (``pip install -e .``) that copy is used. If it is not,
``src`` is put on the path so the suite still runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

try:  # pragma: no cover - depends on how the checkout was set up
    import codecard  # noqa: F401
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(SRC))
