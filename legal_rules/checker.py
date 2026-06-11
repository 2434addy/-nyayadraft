"""Statutory/structural rule engine.

Each document type has a JSON spec in legal_rules/rules/<doc_type>.json defining
required regex patterns (statutory elements), forbidden patterns, length bounds,
and whether the mandatory disclaimer footer applies. Pattern `legal_basis` is either
"CONFIDENT" or "VERIFY" — VERIFY items are listed in docs/CLAIM_AUDIT.md for the
lawyer reviewer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent / "rules"
DISCLAIMER = (
    "This is an AI-generated draft for review by the parties and is not legal advice."
)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    failures: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledRules:
    doc_type: str
    min_chars: int
    max_chars: int
    require_disclaimer: bool
    is_document: bool
    required: tuple[tuple[str, str, re.Pattern], ...]
    forbidden: tuple[tuple[str, str, re.Pattern], ...]


def list_doc_types() -> list[str]:
    return sorted(p.stem for p in RULES_DIR.glob("*.json"))


@lru_cache(maxsize=None)
def load_rules(doc_type: str) -> CompiledRules:
    path = RULES_DIR / f"{doc_type}.json"
    if not path.exists():
        raise FileNotFoundError(f"No rules spec for doc_type '{doc_type}' at {path}")
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("doc_type") != doc_type:
        raise ValueError(
            f"{path.name}: doc_type field '{spec.get('doc_type')}' != filename stem"
        )
    required = tuple(
        (p["id"], p["description"], re.compile(p["regex"]))
        for p in spec.get("required_patterns", [])
    )
    forbidden = tuple(
        (p["id"], p.get("description", p["id"]), re.compile(p["regex"]))
        for p in spec.get("forbidden_patterns", [])
    )
    return CompiledRules(
        doc_type=doc_type,
        min_chars=int(spec.get("min_chars", 200)),
        max_chars=int(spec.get("max_chars", 20000)),
        require_disclaimer=bool(spec.get("require_disclaimer", True)),
        is_document=bool(spec.get("is_document", True)),
        required=required,
        forbidden=forbidden,
    )


def check_document(doc_type: str, text: str) -> CheckResult:
    """Run all statutory/structural checks for one document (or refusal) text."""
    rules = load_rules(doc_type)
    failures: list[str] = []
    warnings: list[str] = []

    n = len(text)
    if n < rules.min_chars:
        failures.append(f"too_short: {n} chars < min {rules.min_chars}")
    if n > rules.max_chars:
        failures.append(f"too_long: {n} chars > max {rules.max_chars}")

    for pid, desc, pattern in rules.required:
        if not pattern.search(text):
            failures.append(f"missing_required:{pid} ({desc})")
    for pid, desc, pattern in rules.forbidden:
        if pattern.search(text):
            failures.append(f"forbidden_present:{pid} ({desc})")

    if rules.require_disclaimer:
        if DISCLAIMER not in text:
            failures.append("missing_disclaimer_footer")
        else:
            tail = text.rstrip().rstrip('"').rstrip("'").rstrip()
            if not tail.endswith(DISCLAIMER):
                warnings.append("disclaimer_not_at_end")
    elif DISCLAIMER in text:
        failures.append("disclaimer_on_non_document")

    return CheckResult(ok=not failures, failures=tuple(failures), warnings=tuple(warnings))


def lint_all_rules() -> list[str]:
    """Validate every rules file loads, compiles, and is sane. Returns problems."""
    problems: list[str] = []
    for doc_type in list_doc_types():
        try:
            rules = load_rules(doc_type)
        except Exception as exc:  # noqa: BLE001 — lint surface: report everything
            problems.append(f"{doc_type}: {exc}")
            continue
        if rules.is_document and not rules.required:
            problems.append(f"{doc_type}: no required_patterns")
        if rules.min_chars >= rules.max_chars:
            problems.append(f"{doc_type}: min_chars >= max_chars")
    return problems
