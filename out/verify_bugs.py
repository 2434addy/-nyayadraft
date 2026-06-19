"""Empirical verification sweep for the 3 data-bug classes, run against the
REAL drafting date (today) and the REAL config/scenarios/seeds the generation
pipeline uses. 400 variations per doc type.

Bug #1  partnership firm_name carries no incorporated-entity suffix, is M/s-style.
Bug #2  no given date field is in the future unless its spec declares future_ok.
Bug #3  affidavit name variants are the same person (right name, surname, gender),
        parentage shares the surname & is male, and security deposits are integer
        multiples of the periodic rent/fee.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "data-pipeline"))

import pipeline_config  # noqa: E402
import variation  # noqa: E402

TODAY = dt.date.today()
N = 400
ENTITY_MARKERS = ("private limited", "pvt", "ltd", "limited", "llp")

cfg = pipeline_config.load_config()
specs = pipeline_config.load_specs()
scenarios_all = pipeline_config.load_scenarios()
seeds = pipeline_config.load_seeds()
doc_types = list(cfg["doc_types"])


def build(spec, scen, i):
    return variation.build_variation(spec, scen, seeds, cfg, i, today=TODAY)


fails: list[str] = []
stats = {}

# ---- Bug #2: no future dates (all 11 types) ----
future_date_checked = 0
for dtype in doc_types:
    spec = specs[dtype]
    scen = scenarios_all.get(dtype, [])
    date_fields = {f["name"] for f in spec.get("fields", []) if f.get("kind") == "date"}
    future_ok = {
        f["name"]
        for f in spec.get("fields", [])
        if f.get("kind") == "date" and f.get("future_ok")
    }
    checkable = date_fields - future_ok
    hits = 0
    for i in range(N):
        facts = build(spec, scen, i)["given_facts"]
        for name in checkable:
            if name in facts:
                hits += 1
                d = dt.date.fromisoformat(facts[name])
                if d > TODAY:
                    fails.append(
                        f"[#2 future-date] {dtype}/{name}={d} > today {TODAY} (idx {i})"
                    )
    future_date_checked += hits
    stats[f"dates::{dtype}"] = f"{len(checkable)} non-future_ok date field(s), {hits} instances checked"

# ---- Bug #1: partnership firm_name ----
pspec = specs["partnership_deed_1932"]
pscen = scenarios_all.get("partnership_deed_1932", [])
firm_checked = 0
for i in range(N):
    firm = build(pspec, pscen, i)["given_facts"].get("firm_name")
    if firm is None:
        fails.append(f"[#1 firm] idx {i}: firm_name absent (declared always-given)")
        continue
    firm_checked += 1
    if not firm.startswith("M/s "):
        fails.append(f"[#1 firm] idx {i}: {firm!r} not M/s-prefixed")
    low = firm.lower()
    for m in ENTITY_MARKERS:
        if m in low:
            fails.append(f"[#1 firm] idx {i}: {firm!r} carries entity suffix {m!r}")
stats["firm::partnership"] = f"{firm_checked} firm_name values checked, M/s-style, no entity suffix"

# ---- Bug #3: affidavit related fields + deposits ----
aspec = specs["affidavit_general"]
ascen_all = scenarios_all.get("affidavit_general", [])
male = set(seeds["names"]["male_first"])
female = set(seeds["names"]["female_first"])
va_seen = vb_seen = par_seen = 0
for i in range(N):
    facts = build(aspec, ascen_all, i)["given_facts"]
    dep = facts.get("deponent_name")
    if "name_variant_a" in facts:
        va_seen += 1
        if facts["name_variant_a"] != dep:
            fails.append(
                f"[#3 variant_a] idx {i}: variant_a {facts['name_variant_a']!r} != deponent {dep!r}"
            )
    if "name_variant_b" in facts and dep:
        vb_seen += 1
        d, b = dep.split(), facts["name_variant_b"].split()
        if b[0] != d[0]:
            fails.append(f"[#3 variant_b] idx {i}: given name {b[0]!r} != deponent {d[0]!r}")
        if b[-1] == d[-1]:
            fails.append(f"[#3 variant_b] idx {i}: surname {b[-1]!r} not changed vs deponent")
    # gender preserved across both variants
    if dep:
        dep_first = dep.split()[0]
        for key in ("name_variant_a", "name_variant_b"):
            if key in facts:
                vf = facts[key].split()[0]
                if dep_first in male and vf in female:
                    fails.append(f"[#3 gender] idx {i}: {key} {vf!r} crossed to female")
                if dep_first in female and vf in male:
                    fails.append(f"[#3 gender] idx {i}: {key} {vf!r} crossed to male")
    if "deponent_parent_name" in facts and dep:
        par_seen += 1
        d, p = dep.split(), facts["deponent_parent_name"].split()
        if p[-1] != d[-1]:
            fails.append(f"[#3 parent] idx {i}: parent surname {p[-1]!r} != deponent {d[-1]!r}")
        if p[0] not in male:
            fails.append(f"[#3 parent] idx {i}: parent given {p[0]!r} not male")
stats["affidavit::variants"] = (
    f"variant_a seen {va_seen}, variant_b seen {vb_seen}, parentage seen {par_seen}"
)

# deposits = integer multiple of periodic amount
for dtype, dep_field, base_field, lo, hi in [
    ("leave_license_mh", "security_deposit", "monthly_fee", 3, 10),
    ("legal_notice_landlord_tenant", "security_deposit", "monthly_rent", 2, 10),
]:
    spec = specs[dtype]
    scen = scenarios_all.get(dtype, [])
    seen = 0
    for i in range(N):
        facts = build(spec, scen, i)["given_facts"]
        if dep_field in facts and base_field in facts:
            seen += 1
            ratio = facts[dep_field] / facts[base_field]
            if ratio != int(ratio) or not (lo <= int(ratio) <= hi):
                fails.append(
                    f"[#3 deposit] {dtype} idx {i}: {facts[dep_field]}/{facts[base_field]}"
                    f"={ratio} not integer in [{lo},{hi}]"
                )
    stats[f"deposit::{dtype}"] = f"{seen} deposit/{base_field} pairs checked"

print("=" * 72)
print(f"EMPIRICAL BUG-FIX SWEEP  (today={TODAY}, N={N}/type, {len(doc_types)} types)")
print("=" * 72)
for k, v in stats.items():
    print(f"  {k:34s} {v}")
print("-" * 72)
print(f"  future-date instances checked across all types: {future_date_checked}")
print("-" * 72)
if fails:
    print(f"  FAILURES: {len(fails)}")
    for f in fails[:40]:
        print("    " + f)
    sys.exit(1)
print("  ALL INVARIANTS HOLD — bugs #1, #2, #3 do not appear in any sampled variation.")
