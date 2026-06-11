"""Tests for prompts.py — template selection, filling, and the unfilled-placeholder guard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import prompts

PIPELINE_DIR = Path(__file__).resolve().parents[1]
META_DIR = PIPELINE_DIR / "meta_prompts"

SYSTEM_PROMPT = "You are NyayaDraft, a test system prompt."

DISPLAY_NAMES = {
    "cheque_bounce_138": "Cheque Bounce Demand Notice (Section 138)",
    "consumer_complaint_cpa2019": "Consumer Complaint (CPA 2019)",
    "leave_license_mh": "Leave and License Agreement (Maharashtra)",
    "out_of_scope": "Out-of-Scope Request (polite refusal)",
}

BASE_SPEC = {
    "doc_type": "cheque_bounce_138",
    "display_name": "Cheque Bounce Demand Notice (Section 138)",
    "structural_summary": "Demand notice structure summary.",
    "statutory_requirements": "- identify the cheque precisely",
    "fields": [],
}

OOS_SPEC = {
    "doc_type": "out_of_scope",
    "display_name": "Out-of-Scope Request (polite refusal)",
    "template": "out_of_scope",
    "no_withhold": True,
    "structural_summary": "Not a document.",
    "statutory_requirements": "- no citations",
    "fields": [],
}


def base_variation(**overrides):
    var = {
        "doc_type": "cheque_bounce_138",
        "index": 0,
        "scenario_id": "friendly_loan_repayment",
        "scenario_summary": "A cheque repaying a friendly loan bounced.",
        "register": "casual",
        "given_facts": {"sender_name": "Aarti Deshmukh", "cheque_amount": 250000},
        "withheld_fields": [
            {"name": "cheque_number", "placeholder": "[CHEQUE NUMBER]"}
        ],
        "nearest_supported": None,
    }
    return {**var, **overrides}


def oos_variation(**overrides):
    var = {
        "doc_type": "out_of_scope",
        "index": 0,
        "scenario_id": "should_i_sue_builder",
        "scenario_summary": "User asks whether they should sue their builder.",
        "register": "semi_formal",
        "given_facts": {"user_name": "Rohan Patil", "city": "Pune"},
        "withheld_fields": [],
        "nearest_supported": "consumer_complaint_cpa2019",
    }
    return {**var, **overrides}


class TestBaseTemplate:
    def test_renders_without_leftover_placeholders(self):
        rendered = prompts.render_prompt(
            BASE_SPEC, base_variation(), SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "<<" not in rendered
        assert ">>" not in rendered

    def test_contains_expected_content(self):
        rendered = prompts.render_prompt(
            BASE_SPEC, base_variation(), SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "Cheque Bounce Demand Notice (Section 138)" in rendered
        assert "A cheque repaying a friendly loan bounced." in rendered
        assert "Aarti Deshmukh" in rendered
        assert "[CHEQUE NUMBER]" in rendered
        assert "casual" in rendered
        assert SYSTEM_PROMPT in rendered
        assert "identify the cheque precisely" in rendered

    def test_given_facts_rendered_as_utf8_json(self):
        var = base_variation(given_facts={"amount": "₹2,50,000"})
        rendered = prompts.render_prompt(
            BASE_SPEC, var, SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "₹2,50,000" in rendered  # not escaped to ₹

    def test_no_withheld_fields_renders_placeholder_note(self):
        var = base_variation(withheld_fields=[])
        rendered = prompts.render_prompt(
            BASE_SPEC, var, SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "<<" not in rendered
        assert "none" in rendered.lower()


class TestOutOfScopeTemplate:
    def test_selected_by_template_discriminator(self):
        rendered = prompts.render_prompt(
            OOS_SPEC, oos_variation(), SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "REFUSE" in rendered
        assert "<<" not in rendered

    def test_lists_supported_types_not_out_of_scope(self):
        rendered = prompts.render_prompt(
            OOS_SPEC, oos_variation(), SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "Leave and License Agreement (Maharashtra)" in rendered
        assert "Out-of-Scope Request (polite refusal)" not in rendered

    def test_nearest_supported_display_name(self):
        rendered = prompts.render_prompt(
            OOS_SPEC, oos_variation(), SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert "Consumer Complaint (CPA 2019)" in rendered

    def test_nearest_supported_none_renders_none(self):
        var = oos_variation(nearest_supported=None)
        rendered = prompts.render_prompt(
            OOS_SPEC, var, SYSTEM_PROMPT, display_names=DISPLAY_NAMES
        )
        assert 'NEAREST SUPPORTED DOCUMENT TYPE (offer it if not "none"): none' in rendered


class TestPlaceholderGuard:
    def test_unfilled_placeholder_raises(self, tmp_path):
        doctored = (META_DIR / "base.txt").read_text(encoding="utf-8")
        doctored += "\nEXTRA: <<BOGUS_PLACEHOLDER>>\n"
        (tmp_path / "base.txt").write_text(doctored, encoding="utf-8")
        with pytest.raises(prompts.PromptRenderError, match="BOGUS_PLACEHOLDER"):
            prompts.render_prompt(
                BASE_SPEC,
                base_variation(),
                SYSTEM_PROMPT,
                meta_dir=tmp_path,
                display_names=DISPLAY_NAMES,
            )

    def test_unknown_template_name_raises(self):
        spec = {**BASE_SPEC, "template": "no_such_template"}
        with pytest.raises(prompts.PromptRenderError, match="no_such_template"):
            prompts.render_prompt(
                spec, base_variation(), SYSTEM_PROMPT, display_names=DISPLAY_NAMES
            )

    def test_missing_template_file_raises(self, tmp_path):
        with pytest.raises(prompts.PromptRenderError, match="base.txt"):
            prompts.render_prompt(
                BASE_SPEC,
                base_variation(),
                SYSTEM_PROMPT,
                meta_dir=tmp_path,
                display_names=DISPLAY_NAMES,
            )

    def test_oos_requires_display_names(self):
        with pytest.raises(prompts.PromptRenderError, match="display_names"):
            prompts.render_prompt(OOS_SPEC, oos_variation(), SYSTEM_PROMPT)


class TestRealSpecsRoundTrip:
    """Every real meta_prompt spec must render cleanly with a minimal variation."""

    def test_all_real_specs_render(self):
        display = {}
        specs = {}
        for path in sorted(META_DIR.glob("*.json")):
            spec = json.loads(path.read_text(encoding="utf-8"))
            specs[spec["doc_type"]] = spec
            display[spec["doc_type"]] = spec["display_name"]
        for doc_type, spec in specs.items():
            var = {
                "doc_type": doc_type,
                "index": 0,
                "scenario_id": "s",
                "scenario_summary": "A plausible scenario.",
                "register": "semi_formal",
                "given_facts": {"some_fact": "some value"},
                "withheld_fields": [],
                "nearest_supported": None,
            }
            rendered = prompts.render_prompt(
                spec, var, SYSTEM_PROMPT, display_names=display
            )
            assert "<<" not in rendered, f"{doc_type} left placeholders"
