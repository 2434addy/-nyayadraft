"""Document-level verification that bugs #1/#2/#3 do not appear in the GENERATED
dataset (out/batch10/dataset.jsonl) — not just in the variation builder.

For each kept record we rebuild the deterministic given_facts and inspect the
actual assistant-drafted document text:

#1  partnership firm: the M/s firm_name fact appears verbatim in the deed and the
    deed contains no 'LLP' / 'Limited Liability Partnership' / 'Pvt Ltd' styling.
#2  future dates: every DD.MM.YYYY (and long-form) date written in the document
    that is AFTER today must be the value of a future_ok field (employment
    joining/last-working-day, partnership commencement, licence start). Any other
    future date is a drafter-introduced regression.
#3  affidavit names: where name_variant_a/b are given, variant_a == deponent and
    variant_b shares the deponent's given name; both appear in the document.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "data-pipeline"))

import generate  # noqa: E402
import pipeline_config  # noqa: E402

BASE = Path(__file__).resolve().parent
DATASET = BASE / "dataset.jsonl"
TODAY = dt.date.today()

# --- #2 future-date tolerance -------------------------------------------------
# future_ok dates (joining / last-working / commencement / licence start) are
# anchored on the GENERATION date, but this script recomputes them at TODAY. When
# verification runs days after the data was drafted, the recomputed value drifts
# forward, so an EXACT match against today's value spuriously flags a legitimate
# forward-looking date. A genuine future_ok value can never land AFTER today's
# recomputed value (the data was generated on or before today) — only up to the
# generation lag BEFORE it. Raw-file mtime is NOT a trustworthy generation date
# (files get re-touched without regenerating content), so we accept a future doc
# date when it sits within this many days before a future_ok field's today-value
# rather than anchoring to an unreliable stored date.
MAX_DRAFT_LAG_DAYS = 45

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
NUM_DATE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b")
LONG_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(20\d{2})\b")
ENTITY = ("limited liability partnership", "llp", "pvt. ltd", "pvt ltd",
          "private limited")

cfg = pipeline_config.load_config()
specs = pipeline_config.load_specs()
ctx = generate.RunContext(
    config=cfg, specs=specs,
    scenarios=pipeline_config.load_scenarios(),
    seeds=pipeline_config.load_seeds(),
    system_prompt=pipeline_config.load_system_prompt(),
    display_names=pipeline_config.display_names(specs),
    out_dir=BASE, today=TODAY,
)


def doc_dates(text: str):
    out = []
    for d, m, y in NUM_DATE.findall(text):
        try:
            out.append(dt.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, mon, y in LONG_DATE.findall(text):
        mi = MONTHS.get(mon.lower())
        if mi:
            try:
                out.append(dt.date(int(y), mi, int(d)))
            except ValueError:
                pass
    return out


def future_ok_values(spec, facts):
    """ISO date values of future_ok fields present in facts, as date objects."""
    vals = set()
    for f in spec.get("fields", []):
        if f.get("kind") == "date" and f.get("future_ok") and f["name"] in facts:
            try:
                vals.add(dt.date.fromisoformat(facts[f["name"]]))
            except ValueError:
                pass
    return vals


fails = []
counts = {"records": 0, "future_dates_seen": 0, "partnership": 0,
          "affidavit_va": 0, "affidavit_vb": 0}

with open(DATASET, encoding="utf-8") as fh:
    for line in fh:
        rec = json.loads(line)
        counts["records"] += 1
        dtype, idx = rec["doc_type"], int(rec["id"].rsplit("-", 1)[-1])
        spec = specs[dtype]
        task = generate.Task(dtype, idx, rec["id"])
        facts = generate._build_variation(task, ctx)["given_facts"]
        doc = rec["messages"][-1]["content"]

        # --- #2 future dates ---
        allowed = future_ok_values(spec, facts)
        for d in doc_dates(doc):
            if d > TODAY:
                counts["future_dates_seen"] += 1
                if not any(0 <= (val - d).days <= MAX_DRAFT_LAG_DAYS
                           for val in allowed):
                    fails.append(
                        f"[#2 future-date] {rec['id']}: document date {d:%d.%m.%Y} is "
                        f"after today and not within {MAX_DRAFT_LAG_DAYS}d of any "
                        f"future_ok field (future_ok values={sorted(allowed)})"
                    )

        # --- #1 partnership firm ---
        if dtype == "partnership_deed_1932":
            counts["partnership"] += 1
            low = doc.lower()
            for marker in ENTITY:
                if marker in low:
                    fails.append(f"[#1 firm] {rec['id']}: deed contains entity marker {marker!r}")
            firm = facts.get("firm_name")
            if firm and firm not in doc:
                fails.append(f"[#1 firm] {rec['id']}: firm_name {firm!r} not present verbatim in deed")

        # --- #3 affidavit name variants ---
        if dtype == "affidavit_general":
            dep = facts.get("deponent_name")
            if "name_variant_a" in facts:
                counts["affidavit_va"] += 1
                if facts["name_variant_a"] != dep:
                    fails.append(f"[#3 variant_a] {rec['id']}: variant_a != deponent")
                if facts["name_variant_a"] not in doc:
                    fails.append(f"[#3 variant_a] {rec['id']}: variant_a {facts['name_variant_a']!r} not in document")
            if "name_variant_b" in facts and dep:
                counts["affidavit_vb"] += 1
                if facts["name_variant_b"].split()[0] != dep.split()[0]:
                    fails.append(f"[#3 variant_b] {rec['id']}: variant_b given name differs from deponent")
                if facts["name_variant_b"] not in doc:
                    fails.append(f"[#3 variant_b] {rec['id']}: variant_b {facts['name_variant_b']!r} not in document")

print("=" * 72)
print(f"DATASET-LEVEL BUG VERIFICATION  (today={TODAY})")
print("=" * 72)
for k, v in counts.items():
    print(f"  {k:22s} {v}")
print("-" * 72)
if fails:
    print(f"  FAILURES: {len(fails)}")
    for f in fails:
        print("    " + f)
    sys.exit(1)
print("  CLEAN — bugs #1, #2, #3 do not appear in any of the 110 generated documents.")
