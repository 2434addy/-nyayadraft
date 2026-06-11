"""Make the repo root importable so `import legal_rules` works regardless of
how pytest is invoked (`python -m pytest legal_rules`, `pytest legal_rules`, ...).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
