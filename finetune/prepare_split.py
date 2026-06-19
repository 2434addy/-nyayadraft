"""Materialize the 80/10/10 train/val/test split for NyayaDraft QLoRA training.

The split is HELD OUT BY SCENARIO (config.yaml: ``splits`` + ``seed``): every
record of a given (doc_type, scenario_id) lands in exactly one split, so the
val/test sets contain entirely unseen scenarios and there is no leakage of a
scenario's phrasing from train into eval.

Within each doc_type the scenarios are partitioned greedily (largest-remaining
capacity) to approximate the 80/10/10 ratio while keeping whole scenarios
together. The partition is fully deterministic (sorted by size then id), so this
script reproduces the identical split on any machine.

Output: finetune/data/{train,val,test}.jsonl — one JSON record per line, each
carrying ``messages`` (system/user/assistant, the SFT signal) plus metadata
(``id``, ``doc_type``, ``scenario_id``, ``register``, ``split``) used by the
evaluation harness. The trainer applies Qwen's chat template to ``messages`` at
train time (see train_qlora.py); these files are template-agnostic on purpose.

Run (no GPU needed):  python finetune/prepare_split.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DATASET = REPO / "out" / "full" / "dataset.jsonl"
CONFIG = REPO / "data-pipeline" / "config.yaml"
OUT_DIR = Path(__file__).resolve().parent / "data"

META_KEYS = ("id", "doc_type", "scenario_id", "register")


def load_records() -> list[dict]:
    with DATASET.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def split_one_type(records: list[dict], ratios: dict[str, float]) -> dict[str, str]:
    """Assign each scenario_id of one doc_type to a split. Returns scenario->split.

    Greedy largest-remaining-capacity over whole scenarios. Guarantees val and
    test are non-empty whenever the type has >= 3 scenarios.
    """
    by_scen: dict[str, int] = defaultdict(int)
    for r in records:
        by_scen[r["scenario_id"]] += 1
    n = len(records)
    remaining = {name: ratios[name] * n for name in ("train", "val", "test")}
    assigned: dict[str, str] = {}
    # Largest scenarios first so the big 0.8 train bucket absorbs them and the
    # small val/test buckets get the small scenarios -> ratios stay close.
    for scen in sorted(by_scen, key=lambda s: (-by_scen[s], s)):
        target = max(remaining, key=lambda k: remaining[k])
        assigned[scen] = target
        remaining[target] -= by_scen[scen]
    # Safeguard: never leave val/test empty when scenarios allow otherwise.
    for need in ("test", "val"):
        if not any(v == need for v in assigned.values()) and len(by_scen) >= 3:
            donor = max(
                (s for s, sp in assigned.items() if sp == "train"),
                key=lambda s: -by_scen[s],  # smallest train scenario
                default=None,
            )
            if donor is not None:
                assigned[donor] = need
    return assigned


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    ratios = {k: float(v) for k, v in cfg["splits"].items()}
    assert abs(sum(ratios.values()) - 1.0) < 1e-9, f"splits must sum to 1: {ratios}"

    records = load_records()
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_type[r["doc_type"]].append(r)

    buckets: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    scen_split: dict[tuple[str, str], str] = {}
    for doc_type in sorted(by_type):
        recs = by_type[doc_type]
        assign = split_one_type(recs, ratios)
        for r in recs:
            sp = assign[r["scenario_id"]]
            scen_split[(doc_type, r["scenario_id"])] = sp
            out = {k: r[k] for k in META_KEYS}
            out["split"] = sp
            out["messages"] = r["messages"]
            buckets[sp].append(out)

    # --- leakage check: no scenario crosses splits -------------------------
    seen: dict[tuple[str, str], str] = {}
    for sp in ("train", "val", "test"):
        for rec in buckets[sp]:
            key = (rec["doc_type"], rec["scenario_id"])
            prev = seen.setdefault(key, sp)
            assert prev == sp, f"LEAKAGE: {key} in both {prev} and {sp}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sp in ("train", "val", "test"):
        path = OUT_DIR / f"{sp}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for rec in buckets[sp]:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # --- report ------------------------------------------------------------
    total = len(records)
    print("=" * 70)
    print("NyayaDraft split (held out BY SCENARIO — no leakage)")
    print("=" * 70)
    print(f"  {'doc_type':32s} {'train':>6s} {'val':>5s} {'test':>5s} {'total':>6s}")
    for doc_type in sorted(by_type):
        c = {sp: sum(1 for r in buckets[sp] if r["doc_type"] == doc_type)
             for sp in ("train", "val", "test")}
        print(f"  {doc_type:32s} {c['train']:6d} {c['val']:5d} {c['test']:5d} "
              f"{sum(c.values()):6d}")
    print("-" * 70)
    tr, va, te = (len(buckets[s]) for s in ("train", "val", "test"))
    print(f"  {'TOTAL':32s} {tr:6d} {va:5d} {te:5d} {total:6d}")
    print(f"  ratios: train={tr/total:.1%}  val={va/total:.1%}  test={te/total:.1%}")
    print(f"  scenarios held out (val+test): "
          f"{sum(1 for v in scen_split.values() if v != 'train') and len({k for k,v in scen_split.items() if v!='train'})}")
    print(f"  written to {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
