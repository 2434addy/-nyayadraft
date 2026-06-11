"""Shared statutory/structural rule engine for NyayaDraft.

Used by the data pipeline (W1 quality gates) and the eval harness (W3 hard checks)
so both measure documents against identical rules.
"""
from .checker import (
    DISCLAIMER,
    CheckResult,
    CompiledRules,
    check_document,
    lint_all_rules,
    list_doc_types,
    load_rules,
)

__all__ = [
    "DISCLAIMER",
    "CheckResult",
    "CompiledRules",
    "check_document",
    "lint_all_rules",
    "list_doc_types",
    "load_rules",
]
