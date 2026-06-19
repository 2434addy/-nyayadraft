"""Local drafting helper for NyayaDraft dataset completion (NO API).

Two jobs, both pure-local (never touches the Anthropic API):

  brief <doc_type> <idx> [end_idx]
      Print the fully-rendered drafting brief (the meta-prompt that the teacher
      model receives) for one index, or for a range idx..end_idx inclusive.
      The agent reads this brief and drafts the response itself in the
      [[[INSTRUCTION]]]/[[[DOCUMENT]]]/[[[END]]] bracket format, writing it to
      out/full/raw/<doc_type>-<idx>.txt (idx zero-padded to 5 digits).

  check <doc_type> [idx]
      Run the REAL gate (generate.parse_response_text + legal_rules.check_document
      via generate._process_text) over raw/<doc_type>-*.txt — or just one idx —
      and print per-file OK/REJECT with failures, plus a summary. This is exactly
      the per-doc gate run_ingest.py applies (dedup is global and happens only at
      final ingest, not here).

  plan <doc_type> <target>
      Print existing raw indices for the type and the recommended contiguous
      block of NEW indices to draft to reach <target> gate-passing files.

Usage (run from repo root or anywhere):
  python out/full/draft_helper.py brief cheque_bounce_138 54 99
  python out/full/draft_helper.py check cheque_bounce_138
  python out/full/draft_helper.py plan  cheque_bounce_138 100
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent          # out/full
REPO = BASE.parents[1]                            # repo root
for p in (str(REPO), str(REPO / "data-pipeline")):
    if p not in sys.path:
        sys.path.insert(0, p)

import generate          # noqa: E402
import pipeline_config   # noqa: E402

RAW = BASE / "raw"
SEP = "=" * 78


def _ctx() -> "generate.RunContext":
    cfg = pipeline_config.load_config()
    specs = pipeline_config.load_specs()
    return generate.RunContext(
        config=cfg,
        specs=specs,
        scenarios=pipeline_config.load_scenarios(),
        seeds=pipeline_config.load_seeds(),
        system_prompt=pipeline_config.load_system_prompt(),
        display_names=pipeline_config.display_names(specs),
        out_dir=BASE,
        today=dt.date.today(),
    )


def _raw_path(doc_type: str, idx: int) -> Path:
    return RAW / f"{generate._record_id(doc_type, idx)}.txt"


def cmd_brief(doc_type: str, start: int, end: int) -> int:
    ctx = _ctx()
    if doc_type not in ctx.specs:
        print(f"unknown doc_type: {doc_type}", file=sys.stderr)
        return 2
    for idx in range(start, end + 1):
        task = generate.Task(doc_type, idx, generate._record_id(doc_type, idx))
        var = generate._build_variation(task, ctx)
        prompt = generate._render_user_prompt(var, ctx)
        exists = _raw_path(doc_type, idx).exists()
        print(SEP)
        print(f"BRIEF doc_type={doc_type} idx={idx} record_id={task.record_id} "
              f"raw_exists={exists} write_to=raw/{task.record_id}.txt")
        print(SEP)
        print(prompt)
        print()
    return 0


def cmd_check(doc_type: str, only_idx: int | None) -> int:
    ctx = _ctx()
    if only_idx is not None:
        files = [_raw_path(doc_type, only_idx)]
    else:
        files = sorted(RAW.glob(f"{doc_type}-*.txt"))
    if not files:
        print(f"no raw files for {doc_type}")
        return 0
    ok = bad = 0
    for f in files:
        if not f.exists():
            print(f"MISSING {f.name}")
            bad += 1
            continue
        idx = int(f.stem.rsplit("-", 1)[1])
        task = generate.Task(doc_type, idx, f.stem)
        var = generate._build_variation(task, ctx)
        outcome, record = generate._process_text(
            task, var, f.read_text(encoding="utf-8"), ctx
        )
        if outcome == "ok":
            ok += 1
            warn = record["check"].get("warnings") or []
            tag = f"  warnings={list(warn)}" if warn else ""
            print(f"OK      {f.name}{tag}")
        else:
            bad += 1
            kind = record.get("error_kind")
            fails = record.get("failures") or [record.get("detail")]
            print(f"REJECT  {f.name}  {kind}: {fails}")
    print("-" * 78)
    print(f"{doc_type}: {ok} OK, {bad} REJECT, {len(files)} total")
    return 0


def cmd_plan(doc_type: str, target: int) -> int:
    existing = sorted(
        int(f.stem.rsplit("-", 1)[1]) for f in RAW.glob(f"{doc_type}-*.txt")
    )
    have = len(existing)
    need = max(0, target - have)
    start = (existing[-1] + 1) if existing else 0
    print(f"doc_type={doc_type} target={target}")
    print(f"existing_raw_files={have} indices={existing}")
    print(f"need={need} new files")
    if need:
        print(f"DRAFT new indices: {start}..{start + need - 1} "
              f"(inclusive, {need} files)")
    else:
        print("DRAFT new indices: none (already at/over target)")
    return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "brief":
        doc_type = argv[1]
        start = int(argv[2])
        end = int(argv[3]) if len(argv) > 3 else start
        return cmd_brief(doc_type, start, end)
    if cmd == "check":
        doc_type = argv[1]
        only = int(argv[2]) if len(argv) > 2 else None
        return cmd_check(doc_type, only)
    if cmd == "plan":
        return cmd_plan(argv[1], int(argv[2]))
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
