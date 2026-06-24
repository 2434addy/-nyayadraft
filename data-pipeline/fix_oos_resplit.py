"""Fix out_of_scope content duplication, then stratified re-split.

Fix #1: every out_of_scope record must have a UNIQUE user prompt AND a unique
assistant body. We keep every out_of_scope record whose user_content is already
unique (first occurrence, ordered by id) and regenerate only the redundant
duplicates with fresh, gate-passing, unique content (expanded generator).

Fix #2: re-split stratified BY doc_type so every doc_type has a healthy floor in
val and test (no thin cells), keeping whole scenarios in one split (no leakage),
shuffled deterministically, hitting exactly 1200/150/150.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import shutil
import tempfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "finetune", "data")
SEED = 20260610
CRLF = b"\r\n"

# import the (upgraded) generator
spec = importlib.util.spec_from_file_location(
    "loop_fill", os.path.join(ROOT, "data-pipeline", "loop_fill.py"))
lf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lf)
from legal_rules.checker import check_document  # noqa: E402


def read_file(sp):
    raw = open(os.path.join(DATA, f"{sp}.jsonl"), "rb").read()
    return [json.loads(l.decode("utf-8")) for l in raw.split(CRLF) if l.strip()]


def hamilton(ns, total):
    s = sum(ns)
    raw = [n * total / s for n in ns]
    floor = [int(x) for x in raw]
    rem = total - sum(floor)
    order = sorted(range(len(ns)), key=lambda i: (raw[i] - floor[i], ns[i]), reverse=True)
    for i in order[:rem]:
        floor[i] += 1
    return floor


def main():
    # --- backup ---
    for sp in ("train", "val", "test"):
        shutil.copy2(os.path.join(DATA, f"{sp}.jsonl"),
                     os.path.join(tempfile.gettempdir(), f"{sp}_prefix3_backup.jsonl"))
    print("backups ->", tempfile.gettempdir(), "(*_prefix3_backup.jsonl)")

    # --- load combined ---
    pool = []
    for sp in ("train", "val", "test"):
        pool.extend(read_file(sp))
    assert len(pool) == 1500, len(pool)

    oos = sorted((r for r in pool if r["doc_type"] == "out_of_scope"),
                 key=lambda r: r["id"])
    rest = [r for r in pool if r["doc_type"] != "out_of_scope"]
    print(f"out_of_scope={len(oos)} rest={len(rest)}")

    # --- Fix #1: dedupe out_of_scope by user_content; regenerate the redundant ---
    seen_user = set()
    seen_body = set()
    seen_scen = {r["scenario_id"] for r in pool}
    kept, to_replace = [], []
    for r in oos:
        u = r["messages"][1]["content"]
        b = r["messages"][2]["content"]
        if u in seen_user or b in seen_body:
            to_replace.append(r)
        else:
            seen_user.add(u)
            seen_body.add(b)
            kept.append(r)
    print(f"kept_unique={len(kept)} to_regenerate={len(to_replace)}")

    rng = random.Random(SEED)
    regen = 0
    for r in to_replace:
        for _ in range(10000):
            base, user, body = lf.b_out_of_scope(lf.R(rng))
            if user in seen_user or body in seen_body:
                continue
            if not check_document("out_of_scope", body).ok:
                continue
            break
        else:
            raise SystemExit("could not regenerate a unique out_of_scope record")
        seen_user.add(user)
        seen_body.add(body)
        # unique scenario_id
        sid = base
        k = 1
        while sid in seen_scen:
            sid = f"{base}_{k:03d}"
            k += 1
        seen_scen.add(sid)
        r["scenario_id"] = sid
        r["messages"][1]["content"] = user
        r["messages"][2]["content"] = body
        r["register"] = rng.choice(lf.REGISTERS)
        regen += 1
    print(f"regenerated={regen}")

    pool = rest + kept + to_replace
    assert len(pool) == 1500

    # --- integrity: zero duplicate (doc_type+user) and (doc_type+assistant) pairs ---
    du = defaultdict(int)
    da = defaultdict(int)
    for r in pool:
        du[(r["doc_type"], r["messages"][1]["content"])] += 1
        da[(r["doc_type"], r["messages"][2]["content"])] += 1
    dup_u = sum(1 for v in du.values() if v > 1)
    dup_a = sum(1 for v in da.values() if v > 1)
    print(f"dup(doc_type,user) pairs={dup_u}  dup(doc_type,assistant) pairs={dup_a}")
    assert dup_u == 0 and dup_a == 0, "content duplicates remain"

    # --- Fix #2: stratified re-split by doc_type ---
    by_type = defaultdict(list)
    for r in pool:
        by_type[r["doc_type"]].append(r)
    types = sorted(by_type)
    n_t = [len(by_type[t]) for t in types]
    val_t = hamilton(n_t, 150)
    test_t = hamilton(n_t, 150)
    assert sum(val_t) == 150 and sum(test_t) == 150
    assert min(val_t) >= 5 and min(test_t) >= 5, (val_t, test_t)

    buckets = {"train": [], "val": [], "test": []}
    rng2 = random.Random(SEED)
    for ti, t in enumerate(types):
        recs = by_type[t]
        groups = defaultdict(list)
        for r in recs:
            groups[r["scenario_id"]].append(r)
        order = sorted(groups)
        rng2.shuffle(order)
        assigned = {}
        for bucket, target in (("test", test_t[ti]), ("val", val_t[ti])):
            cap = target
            for sid in order:
                if sid in assigned:
                    continue
                if len(groups[sid]) <= cap:
                    assigned[sid] = bucket
                    cap -= len(groups[sid])
                    if cap == 0:
                        break
            assert cap == 0, f"{t}/{bucket} short by {cap}"
        for sid in order:
            sp = assigned.get(sid, "train")
            for r in groups[sid]:
                r["split"] = sp
                buckets[sp].append(r)

    counts = {k: len(v) for k, v in buckets.items()}
    assert counts == {"train": 1200, "val": 150, "test": 150}, counts
    print("split counts:", counts)

    # leakage check
    seen = {}
    for sp in ("train", "val", "test"):
        for r in buckets[sp]:
            prev = seen.setdefault(r["scenario_id"], sp)
            assert prev == sp, f"LEAKAGE {r['scenario_id']}"

    # --- write ---
    for sp in ("train", "val", "test"):
        payload = "\r\n".join(json.dumps(r, ensure_ascii=False) for r in buckets[sp])
        open(os.path.join(DATA, f"{sp}.jsonl"), "wb").write(payload.encode("utf-8") + CRLF)
    print("written.")


if __name__ == "__main__":
    main()
