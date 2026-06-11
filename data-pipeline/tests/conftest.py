"""Pytest path bootstrap for the data-pipeline test suite.

`data-pipeline` contains a hyphen, so it cannot be imported as a package.
The pipeline modules are therefore written as top-level modules and tests
import them after inserting both the repo root (for `legal_rules`) and the
data-pipeline directory (for `variation`, `prompts`, ...) into sys.path.
"""
from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_DIR.parent

for _path in (str(REPO_ROOT), str(PIPELINE_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
