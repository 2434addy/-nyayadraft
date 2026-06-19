"""Ingest harness for the 10/type proving batch, with a dedup pass.

Same contract as out/firstbatch/run_ingest.py: for each raw/<doc_type>-<idx>.txt
it rebuilds the deterministic variation generate.py would, runs the REAL
parse_response_text + legal_rules checker via generate._process_text, and writes
the production-schema chat record. THEN it applies the config dedup pass
(rapidfuzz token_set_ratio on normalized instructions, threshold from
config['dedup']['similarity_threshold']) that generate.py never wired up — near
-duplicate instructions are dropped to dedup_rejects.jsonl rather than kept.

Outputs (in this dir):
  dataset.jsonl        gate-passed AND dedup-unique records (production schema)
  rejects.jsonl        gate failures (parse_error / forbidden / missing / length)
  dedup_rejects.jsonl  gate-passed but near-duplicate of an earlier kept record
Prints a per-type summary: drafted / gate-passed / dedup-dropped / kept.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

from rapidfuzz import fuzz

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "data-pipeline"))

import generate  # noqa: E402
import pipeline_config  # noqa: E402

BASE = Path(__file__).resolve().parent
RAW_DIR = BASE / "raw"
DATASET = BASE / "dataset.jsonl"
REJECTS = BASE / "rejects.jsonl"
DEDUP_REJECTS = BASE / "dedup_rejects.jsonl"

_WS = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace."""
    return _WS.sub(" ", text.lower()).strip()


def _user_instruction(record: dict) -> str:
    for m in record.get("messages", []):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (DATASET, REJECTS, DEDUP_REJECTS):
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
    threshold = float(cfg.get("dedup", {}).get("similarity_threshold", 92))

    order = list(cfg["doc_types"])
    stats = {dt_: {"drafted": 0, "gate_ok": 0, "dedup_drop": 0, "kept": 0,
                   "rejects": [], "dups": []} for dt_ in order}

    kept_norm: list[tuple[str, str]] = []  # (record_id, normalized_instruction)

    for raw_file in sorted(RAW_DIR.glob("*.txt")):
        doc_type, idx_s = raw_file.stem.rsplit("-", 1)
        idx = int(idx_s)
        bucket = stats.setdefault(
            doc_type,
            {"drafted": 0, "gate_ok": 0, "dedup_drop": 0, "kept": 0, "rejects": [], "dups": []},
        )
        bucket["drafted"] += 1
        task = generate.Task(doc_type, idx, generate._record_id(doc_type, idx))
        var = generate._build_variation(task, ctx)
        text = raw_file.read_text(encoding="utf-8")
        outcome, record = generate._process_text(task, var, text, ctx)

        if outcome != "ok":
            generate._append_jsonl(REJECTS, record)
            bucket["rejects"].append(
                (record["id"], record.get("error_kind"), tuple(record.get("failures") or ()))
            )
            continue

        bucket["gate_ok"] += 1
        norm = _normalize(_user_instruction(record))
        dup_of = None
        for rid, prev in kept_norm:
            if fuzz.token_set_ratio(norm, prev) >= threshold:
                dup_of = rid
                break
        if dup_of is not None:
            record["dedup_near"] = dup_of
            generate._append_jsonl(DEDUP_REJECTS, record)
            bucket["dedup_drop"] += 1
            bucket["dups"].append((record["id"], dup_of))
        else:
            kept_norm.append((record["id"], norm))
            generate._append_jsonl(DATASET, record)
            bucket["kept"] += 1

    tot = {k: sum(b[k] for b in stats.values()) for k in ("drafted", "gate_ok", "dedup_drop", "kept")}
    print("=" * 78)
    print(f"BATCH-10 INGEST  (dedup threshold={threshold}, today={ctx.today})")
    print("=" * 78)
    print(f"  {'doc_type':34s} draft  gateOK  dedupDrop  KEPT")
    for dt_ in order:
        b = stats[dt_]
        if not b["drafted"]:
            print(f"  {dt_:34s}  (no raw files)")
            continue
        print(f"  {dt_:34s} {b['drafted']:5d}  {b['gate_ok']:6d}  {b['dedup_drop']:9d}  {b['kept']:4d}")
        for rid, kind, failures in b["rejects"]:
            detail = ", ".join(failures) if failures else kind
            print(f"        GATE-REJECT {rid}: {kind} -> {detail}")
        for rid, dup_of in b["dups"]:
            print(f"        DEDUP-DROP  {rid}: near-duplicate of {dup_of}")
    print("-" * 78)
    print(f"  TOTAL drafted {tot['drafted']}, gate-passed {tot['gate_ok']}, "
          f"dedup-dropped {tot['dedup_drop']}, KEPT {tot['kept']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
