"""Validate a single drafted raw bracket file against the REAL pipeline.

Usage:  python out/batch10/check_one.py out/batch10/raw/<doc_type>-<idx>.txt

Rebuilds the deterministic variation generate.py would for (doc_type, idx),
runs parse_response_text + the legal_rules checker via generate._process_text,
and prints OK or REJECT with the failing gate ids. Exit 0 on OK, 1 on REJECT.
Use this to self-check each draft before finishing; fix any REJECT and re-run.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "data-pipeline"))

import generate  # noqa: E402
import pipeline_config  # noqa: E402


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print("usage: check_one.py <raw_file.txt>")
        return 2
    raw_file = Path(argv[0])
    doc_type, idx_s = raw_file.stem.rsplit("-", 1)
    idx = int(idx_s)

    cfg = pipeline_config.load_config()
    specs = pipeline_config.load_specs()
    ctx = generate.RunContext(
        config=cfg,
        specs=specs,
        scenarios=pipeline_config.load_scenarios(),
        seeds=pipeline_config.load_seeds(),
        system_prompt=pipeline_config.load_system_prompt(),
        display_names=pipeline_config.display_names(specs),
        out_dir=raw_file.parent,
        today=dt.date.today(),
    )
    task = generate.Task(doc_type, idx, generate._record_id(doc_type, idx))
    var = generate._build_variation(task, ctx)
    text = raw_file.read_text(encoding="utf-8")
    outcome, record = generate._process_text(task, var, text, ctx)
    if outcome == "ok":
        n = len(record["messages"][-1]["content"])
        print(f"OK    {raw_file.name}  (assistant chars={n}, flagged={record.get('flagged_for_review')})")
        return 0
    kind = record.get("error_kind")
    failures = record.get("failures") or ()
    print(f"REJECT {raw_file.name}: {kind} -> {', '.join(failures) if failures else kind}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
