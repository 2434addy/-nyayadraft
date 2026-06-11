"""Schema and integrity tests for every JSON rule file in legal_rules/rules/.

These tests guard against:
- JSON parse errors
- Missing or mismatched doc_type fields
- Empty required_patterns on is_document types
- Non-compiling regexes
- Malformed min/max_chars
- Missing mandatory keys per pattern entry
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RULES_DIR = REPO_ROOT / "legal_rules" / "rules"

ALL_JSON_FILES = sorted(RULES_DIR.glob("*.json"))
ALL_DOC_TYPE_STEMS = [p.stem for p in ALL_JSON_FILES]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# File-level integrity: parametrised over every JSON file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("json_path", ALL_JSON_FILES, ids=[p.name for p in ALL_JSON_FILES])
class TestEachRuleFile:
    def test_valid_json(self, json_path: Path) -> None:
        """File must parse as valid JSON without exception."""
        spec = load_json(json_path)
        assert isinstance(spec, dict)

    def test_doc_type_field_present(self, json_path: Path) -> None:
        spec = load_json(json_path)
        assert "doc_type" in spec, f"{json_path.name}: missing 'doc_type' key"

    def test_doc_type_matches_filename(self, json_path: Path) -> None:
        spec = load_json(json_path)
        assert spec["doc_type"] == json_path.stem, (
            f"{json_path.name}: doc_type '{spec['doc_type']}' != stem '{json_path.stem}'"
        )

    def test_min_chars_is_positive_int(self, json_path: Path) -> None:
        spec = load_json(json_path)
        min_chars = int(spec.get("min_chars", 200))
        assert min_chars > 0

    def test_max_chars_is_positive_int(self, json_path: Path) -> None:
        spec = load_json(json_path)
        max_chars = int(spec.get("max_chars", 20000))
        assert max_chars > 0

    def test_min_chars_less_than_max_chars(self, json_path: Path) -> None:
        spec = load_json(json_path)
        min_chars = int(spec.get("min_chars", 200))
        max_chars = int(spec.get("max_chars", 20000))
        assert min_chars < max_chars, (
            f"{json_path.name}: min_chars ({min_chars}) >= max_chars ({max_chars})"
        )

    def test_require_disclaimer_is_bool(self, json_path: Path) -> None:
        spec = load_json(json_path)
        val = spec.get("require_disclaimer", True)
        assert isinstance(val, bool), (
            f"{json_path.name}: require_disclaimer should be bool, got {type(val)}"
        )

    def test_is_document_is_bool_if_present(self, json_path: Path) -> None:
        spec = load_json(json_path)
        if "is_document" in spec:
            assert isinstance(spec["is_document"], bool)

    def test_required_patterns_is_list(self, json_path: Path) -> None:
        spec = load_json(json_path)
        assert isinstance(spec.get("required_patterns", []), list)

    def test_forbidden_patterns_is_list(self, json_path: Path) -> None:
        spec = load_json(json_path)
        assert isinstance(spec.get("forbidden_patterns", []), list)

    def test_is_document_type_has_required_patterns(self, json_path: Path) -> None:
        spec = load_json(json_path)
        is_document = spec.get("is_document", True)
        if is_document:
            patterns = spec.get("required_patterns", [])
            assert len(patterns) > 0, (
                f"{json_path.name}: is_document=true but required_patterns is empty"
            )

    def test_all_required_pattern_entries_have_id(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for i, p in enumerate(spec.get("required_patterns", [])):
            assert "id" in p, f"{json_path.name}: required_patterns[{i}] missing 'id'"
            assert p["id"], f"{json_path.name}: required_patterns[{i}] has empty 'id'"

    def test_all_required_pattern_entries_have_regex(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for i, p in enumerate(spec.get("required_patterns", [])):
            assert "regex" in p, f"{json_path.name}: required_patterns[{i}] missing 'regex'"
            assert p["regex"], f"{json_path.name}: required_patterns[{i}] has empty 'regex'"

    def test_all_required_pattern_entries_have_description(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for i, p in enumerate(spec.get("required_patterns", [])):
            assert "description" in p, (
                f"{json_path.name}: required_patterns[{i}] missing 'description'"
            )

    def test_all_required_regexes_compile(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for p in spec.get("required_patterns", []):
            try:
                re.compile(p["regex"])
            except re.error as exc:
                pytest.fail(
                    f"{json_path.name}: required pattern '{p['id']}' "
                    f"regex does not compile: {exc}"
                )

    def test_all_forbidden_pattern_entries_have_id(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for i, p in enumerate(spec.get("forbidden_patterns", [])):
            assert "id" in p, f"{json_path.name}: forbidden_patterns[{i}] missing 'id'"
            assert p["id"], f"{json_path.name}: forbidden_patterns[{i}] has empty 'id'"

    def test_all_forbidden_pattern_entries_have_regex(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for i, p in enumerate(spec.get("forbidden_patterns", [])):
            assert "regex" in p, f"{json_path.name}: forbidden_patterns[{i}] missing 'regex'"
            assert p["regex"], f"{json_path.name}: forbidden_patterns[{i}] has empty 'regex'"

    def test_all_forbidden_regexes_compile(self, json_path: Path) -> None:
        spec = load_json(json_path)
        for p in spec.get("forbidden_patterns", []):
            try:
                re.compile(p["regex"])
            except re.error as exc:
                pytest.fail(
                    f"{json_path.name}: forbidden pattern '{p['id']}' "
                    f"regex does not compile: {exc}"
                )

    def test_no_duplicate_pattern_ids(self, json_path: Path) -> None:
        spec = load_json(json_path)
        all_ids: list[str] = []
        for p in spec.get("required_patterns", []):
            all_ids.append(p.get("id", ""))
        for p in spec.get("forbidden_patterns", []):
            all_ids.append(p.get("id", ""))
        seen: set[str] = set()
        duplicates: list[str] = []
        for pid in all_ids:
            if pid in seen:
                duplicates.append(pid)
            seen.add(pid)
        assert not duplicates, (
            f"{json_path.name}: duplicate pattern ids: {duplicates}"
        )


# ---------------------------------------------------------------------------
# Cross-file / catalogue tests
# ---------------------------------------------------------------------------


class TestRulesCatalogue:
    def test_exactly_eleven_rule_files_exist(self) -> None:
        assert len(ALL_JSON_FILES) == 11

    def test_out_of_scope_file_exists(self) -> None:
        stems = [p.stem for p in ALL_JSON_FILES]
        assert "out_of_scope" in stems

    def test_out_of_scope_is_not_document(self) -> None:
        spec = load_json(RULES_DIR / "out_of_scope.json")
        assert spec.get("is_document") is False

    def test_out_of_scope_require_disclaimer_is_false(self) -> None:
        spec = load_json(RULES_DIR / "out_of_scope.json")
        assert spec.get("require_disclaimer") is False

    def test_all_document_types_require_disclaimer(self) -> None:
        """Every is_document=true type must have require_disclaimer=true."""
        for json_path in ALL_JSON_FILES:
            spec = load_json(json_path)
            if spec.get("is_document", True):
                assert spec.get("require_disclaimer", True) is True, (
                    f"{json_path.name}: is_document but require_disclaimer is not true"
                )

    def test_common_forbidden_patterns_present_in_all_files(self) -> None:
        """Every rule file (document or refusal) must ban the four universal anti-patterns."""
        universal_ids = {"no_md_heading", "no_md_bold", "no_ai_voice", "no_chat_preamble"}
        for json_path in ALL_JSON_FILES:
            spec = load_json(json_path)
            forbidden_ids = {p["id"] for p in spec.get("forbidden_patterns", [])}
            missing = universal_ids - forbidden_ids
            assert not missing, (
                f"{json_path.name}: missing universal forbidden pattern ids: {missing}"
            )

    def test_no_rule_file_has_empty_max_chars(self) -> None:
        for json_path in ALL_JSON_FILES:
            spec = load_json(json_path)
            assert "max_chars" in spec, f"{json_path.name}: 'max_chars' key absent"

    def test_no_rule_file_has_empty_min_chars(self) -> None:
        for json_path in ALL_JSON_FILES:
            spec = load_json(json_path)
            assert "min_chars" in spec, f"{json_path.name}: 'min_chars' key absent"

    @pytest.mark.parametrize("stem", ALL_DOC_TYPE_STEMS)
    def test_doc_type_loadable_via_engine(self, stem: str) -> None:
        """Every file must load cleanly through the engine's load_rules()."""
        from legal_rules import load_rules
        rules = load_rules(stem)
        assert rules.doc_type == stem
