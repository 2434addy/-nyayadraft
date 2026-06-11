"""Split authored doc-type packages into the repo layout.

A "package" is the structured object produced by the author-doctype-packages
workflow: meta-prompt spec + statutory rules + scenarios + claim audit in one
JSON object per document type. This tool splits each package into:

  data-pipeline/meta_prompts/<doc_type>.json   spec consumed by the generator
  legal_rules/rules/<doc_type>.json            regex gates for legal_rules.checker
  data-pipeline/seeds/scenarios.json           scenarios merged under the doc_type key
  docs/claim_audit.json + docs/CLAIM_AUDIT.md  lawyer-review target list

Re-runnable: an existing doc_type entry is replaced, all others are preserved.
Finishes by running legal_rules.checker.lint_all_rules() and exits non-zero on
any validation or lint problem.

Usage:
    python data-pipeline/split_packages.py <packages.json>

<packages.json> is either {"packages": [...]} (the workflow return value) or a
bare JSON array of package objects.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
META_DIR = REPO_ROOT / "data-pipeline" / "meta_prompts"
RULES_DIR = REPO_ROOT / "legal_rules" / "rules"
SCENARIOS_PATH = REPO_ROOT / "data-pipeline" / "seeds" / "scenarios.json"
AUDIT_JSON_PATH = REPO_ROOT / "docs" / "claim_audit.json"
AUDIT_MD_PATH = REPO_ROOT / "docs" / "CLAIM_AUDIT.md"

META_KEYS = (
    "doc_type",
    "display_name",
    "structural_summary",
    "statutory_requirements",
    "fields",
)
PKG_KEYS = META_KEYS + ("scenarios", "rules", "claim_audit")
RULES_KEYS = ("min_chars", "max_chars", "required_patterns", "forbidden_patterns")
DOC_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]+$")

log = logging.getLogger("split_packages")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def validate_package(pkg: dict) -> list[str]:
    missing = [k for k in PKG_KEYS if k not in pkg]
    if missing:
        return [f"missing keys: {missing}"]

    problems: list[str] = []
    if not DOC_TYPE_RE.match(pkg["doc_type"]):
        problems.append(f"doc_type '{pkg['doc_type']}' is not snake_case")
    if len(pkg["fields"]) < 6:
        problems.append(f"only {len(pkg['fields'])} fields (minimum 6)")
    if len(pkg["scenarios"]) < 10:
        problems.append(f"only {len(pkg['scenarios'])} scenarios (minimum 10)")
    if len(pkg["claim_audit"]) < 1:
        problems.append("claim_audit is empty")

    scenario_ids = [s.get("id") for s in pkg["scenarios"]]
    if len(scenario_ids) != len(set(scenario_ids)):
        problems.append("duplicate scenario ids")
    if any(not s.get("id") or not s.get("summary") for s in pkg["scenarios"]):
        problems.append("scenario missing id or summary")

    rules = pkg["rules"]
    missing_rules = [k for k in RULES_KEYS if k not in rules]
    if missing_rules:
        problems.append(f"rules missing keys: {missing_rules}")
        return problems
    if len(rules["required_patterns"]) < 5:
        problems.append(
            f"only {len(rules['required_patterns'])} required_patterns (minimum 5)"
        )
    for pat in rules["required_patterns"] + rules["forbidden_patterns"]:
        try:
            re.compile(pat["regex"])
        except (re.error, KeyError, TypeError) as exc:
            problems.append(f"pattern '{pat.get('id', '?')}' does not compile: {exc}")
    for claim in pkg["claim_audit"]:
        if claim.get("status") not in ("CONFIDENT", "VERIFY"):
            problems.append(f"claim has invalid status: {claim.get('status')!r}")
    return problems


def split_package(pkg: dict) -> tuple[dict, dict]:
    """Return (meta_prompt_spec, rules_spec) shaped like the on-disk files."""
    meta = {key: pkg[key] for key in META_KEYS}
    src = pkg["rules"]
    rules = {
        "doc_type": pkg["doc_type"],
        "min_chars": src["min_chars"],
        "max_chars": src["max_chars"],
        "require_disclaimer": src.get("require_disclaimer", True),
        "is_document": src.get("is_document", True),
        "required_patterns": src["required_patterns"],
        "forbidden_patterns": src["forbidden_patterns"],
    }
    return meta, rules


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_audit_md(audit: dict[str, dict]) -> str:
    lines = [
        "# Claim Audit — Lawyer Review Target List",
        "",
        "Every legal claim made anywhere in a doc-type package (statutory requirements,",
        "regex gates, structural summaries) is listed here. `CONFIDENT` means the author",
        "is certain the claim is correct and current. `VERIFY` means it must be confirmed",
        "by a qualified advocate before the full dataset generation run.",
        "",
        "Generated by `data-pipeline/split_packages.py` from `docs/claim_audit.json`;",
        "do not edit this file by hand.",
        "",
    ]
    for doc_type in sorted(audit):
        entry = audit[doc_type]
        lines.append(f"## {doc_type} — {entry['display_name']}")
        lines.append("")
        if not entry["claims"]:
            lines.append(
                "_No legal claims made — refusal texts contain no statutory"
                " citations by design._"
            )
            lines.append("")
            continue
        lines.append("| Status | Claim | Note |")
        lines.append("|--------|-------|------|")
        for claim in entry["claims"]:
            lines.append(
                f"| {claim['status']} | {_md_cell(claim['claim'])} |"
                f" {_md_cell(claim.get('note', ''))} |"
            )
        lines.append("")
    total = sum(len(e["claims"]) for e in audit.values())
    verify = sum(
        1 for e in audit.values() for c in e["claims"] if c["status"] == "VERIFY"
    )
    lines.append(
        f"_{total} claims across {len(audit)} document types;"
        f" {verify} marked VERIFY for lawyer review._"
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("packages_json", type=Path, help="workflow output JSON")
    args = parser.parse_args(argv)

    raw = json.loads(args.packages_json.read_text(encoding="utf-8"))
    packages = raw.get("packages") if isinstance(raw, dict) else raw
    if not isinstance(packages, list) or not packages:
        log.error("No packages found in %s", args.packages_json)
        return 1

    invalid = [
        f"{pkg.get('doc_type', '<unknown>')}: {problem}"
        for pkg in packages
        for problem in validate_package(pkg)
    ]
    if invalid:
        for line in invalid:
            log.error("INVALID %s", line)
        return 1

    scenarios = read_json(SCENARIOS_PATH, {})
    audit = read_json(AUDIT_JSON_PATH, {})
    for pkg in packages:
        doc_type = pkg["doc_type"]
        meta, rules = split_package(pkg)
        write_json(META_DIR / f"{doc_type}.json", meta)
        write_json(RULES_DIR / f"{doc_type}.json", rules)
        scenarios = {**scenarios, doc_type: pkg["scenarios"]}
        audit = {
            **audit,
            doc_type: {
                "display_name": pkg["display_name"],
                "claims": pkg["claim_audit"],
            },
        }
        log.info(
            "wrote %s (fields=%d scenarios=%d required_patterns=%d claims=%d)",
            doc_type,
            len(pkg["fields"]),
            len(pkg["scenarios"]),
            len(pkg["rules"]["required_patterns"]),
            len(pkg["claim_audit"]),
        )

    write_json(SCENARIOS_PATH, scenarios)
    write_json(AUDIT_JSON_PATH, audit)
    AUDIT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD_PATH.write_text(render_audit_md(audit), encoding="utf-8")

    sys.path.insert(0, str(REPO_ROOT))
    from legal_rules.checker import lint_all_rules, list_doc_types

    lint_problems = lint_all_rules()
    if lint_problems:
        for line in lint_problems:
            log.error("LINT %s", line)
        return 1
    log.info("lint_all_rules: OK (%d doc types on disk)", len(list_doc_types()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
