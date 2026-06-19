"""Local (no-API) ingest harness for the first-batch throughput test.

Reads each hand-drafted raw bracket file in raw/<doc_type>-<index>.txt, rebuilds
the SAME deterministic variation generate.py would (same today), runs the REAL
parse_response_text + legal_rules checker via generate._process_text, and writes
the production-schema chat record to dataset.jsonl (pass) or a reject record to
rejects.jsonl (fail). Prints a per-type pass/fail summary.
"""
from __future__ import annotations

import collections
import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "data-pipeline"))

import generate  # noqa: E402
import pipeline_config  # noqa: E402

BASE = Path(__file__).resolve().parent
RAW_DIR = BASE / "raw"
DATASET = BASE / "dataset.jsonl"
REJECTS = BASE / "rejects.jsonl"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (DATASET, REJECTS):
        if path.exists():
            path.unlink()

    cfg = pipeline_config.load_config()
    specs = pipeline_config.load_specs()
    ctx = generate.RunContext(
        config=cfg,
        specs=specs,
        scenarios=pipeline_config.load_scenarios(),
        seeds=pipeline_config.load_seeds(),
        system_prompt=pipeline_config.load_system_prompt(),
        display_names=pipeline_config.display_names(specs),
        out_dir=BASE,
        today=dt.date.today(),
    )

    order = list(cfg["doc_types"])
    stats = {dt_: {"ok": 0, "rej": 0, "rejects": []} for dt_ in order}

    for raw_file in sorted(RAW_DIR.glob("*.txt")):
        doc_type, idx_s = raw_file.stem.rsplit("-", 1)
        idx = int(idx_s)
        task = generate.Task(doc_type, idx, generate._record_id(doc_type, idx))
        var = generate._build_variation(task, ctx)
        text = raw_file.read_text(encoding="utf-8")
        outcome, record = generate._process_text(task, var, text, ctx)
        bucket = stats.setdefault(doc_type, {"ok": 0, "rej": 0, "rejects": []})
        if outcome == "ok":
            generate._append_jsonl(DATASET, record)
            bucket["ok"] += 1
        else:
            generate._append_jsonl(REJECTS, record)
            bucket["rej"] += 1
            bucket["rejects"].append(
                (record["id"], record["error_kind"], tuple(record.get("failures") or ()))
            )

    total_ok = sum(b["ok"] for b in stats.values())
    total_rej = sum(b["rej"] for b in stats.values())
    print("=" * 72)
    print(f"PER-TYPE RESULTS  (dataset={DATASET.name}, rejects={REJECTS.name})")
    print("=" * 72)
    for dt_ in order:
        b = stats[dt_]
        seen = b["ok"] + b["rej"]
        if not seen:
            print(f"  {dt_:32s}  (no raw files yet)")
            continue
        print(f"  {dt_:32s}  passed {b['ok']}/{seen}")
        for rid, kind, failures in b["rejects"]:
            detail = ", ".join(failures) if failures else kind
            print(f"        REJECT {rid}: {kind} -> {detail}")
    print("-" * 72)
    print(f"  TOTAL passed {total_ok}, rejected {total_rej}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
