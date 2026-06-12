"""Tests for variation.py — deterministic seeded variation sampling."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import pytest

import variation

PIPELINE_DIR = Path(__file__).resolve().parents[1]
SEEDS_DIR = PIPELINE_DIR / "seeds"
META_DIR = PIPELINE_DIR / "meta_prompts"

TODAY = dt.date(2026, 6, 11)

CONFIG = {
    "seed": 20260610,
    "registers": {"casual": 0.40, "semi_formal": 0.35, "detailed": 0.25},
    "withhold_probability": {"casual": 0.70, "semi_formal": 0.50, "detailed": 0.30},
}

SYNTH_SPEC = {
    "doc_type": "synthetic_doc",
    "display_name": "Synthetic Document",
    "structural_summary": "A synthetic structure.",
    "statutory_requirements": "- none",
    "fields": [
        {
            "name": "party_name",
            "placeholder": "[PARTY NAME]",
            "given_policy": "always",
            "kind": "person_name",
        },
        {
            "name": "amount",
            "placeholder": "[AMOUNT IN ₹]",
            "given_policy": "withholdable",
            "kind": "inr_amount",
            "range": [10000, 50000],
        },
        {
            "name": "city",
            "placeholder": "[CITY]",
            "given_policy": "withholdable",
            "kind": "city",
        },
        {
            "name": "witness",
            "placeholder": "[WITNESS NAME]",
            "given_policy": "optional",
            "kind": "person_name",
        },
    ],
}

SYNTH_SCENARIOS = [
    {"id": f"scenario_{i}", "summary": f"Synthetic scenario number {i}."}
    for i in range(6)
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seeds():
    return {
        "names": load_json(SEEDS_DIR / "names.json"),
        "cities": load_json(SEEDS_DIR / "cities.json"),
    }


@pytest.fixture(scope="module")
def real_spec():
    return load_json(META_DIR / "leave_license_mh.json")


@pytest.fixture(scope="module")
def real_scenarios():
    return load_json(SEEDS_DIR / "scenarios.json")


@pytest.fixture(scope="module")
def oos_spec():
    return load_json(META_DIR / "out_of_scope.json")


def build(spec, scenarios, seeds, index, register=None):
    return variation.build_variation(
        spec, scenarios, seeds, CONFIG, index, today=TODAY, register=register
    )


class TestDeterminism:
    def test_same_inputs_same_variation(self, real_spec, real_scenarios, seeds):
        scenarios = real_scenarios["leave_license_mh"]
        first = build(real_spec, scenarios, seeds, 7)
        second = build(real_spec, scenarios, seeds, 7)
        assert first == second

    def test_different_index_changes_variation(self, real_spec, real_scenarios, seeds):
        scenarios = real_scenarios["leave_license_mh"]
        variations = [build(real_spec, scenarios, seeds, i) for i in range(5)]
        assert any(v != variations[0] for v in variations[1:])

    def test_synthetic_determinism(self, seeds):
        first = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, 3)
        second = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, 3)
        assert first == second


class TestImmutability:
    def test_inputs_not_mutated(self, seeds):
        spec_before = copy.deepcopy(SYNTH_SPEC)
        scenarios_before = copy.deepcopy(SYNTH_SCENARIOS)
        seeds_before = copy.deepcopy(seeds)
        config_before = copy.deepcopy(CONFIG)

        build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, 0)

        assert SYNTH_SPEC == spec_before
        assert SYNTH_SCENARIOS == scenarios_before
        assert seeds == seeds_before
        assert CONFIG == config_before


class TestVariationShape:
    def test_required_keys(self, seeds):
        var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, 1)
        for key in (
            "doc_type",
            "index",
            "scenario_id",
            "scenario_summary",
            "register",
            "given_facts",
            "withheld_fields",
        ):
            assert key in var, f"missing key {key}"
        assert var["doc_type"] == "synthetic_doc"
        assert var["register"] in ("casual", "semi_formal", "detailed")

    def test_always_fields_always_given(self, seeds):
        for i in range(50):
            var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, i)
            assert "party_name" in var["given_facts"]

    def test_withheld_fields_carry_exact_placeholder(self, seeds):
        seen = False
        for i in range(50):
            var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, i)
            for wf in var["withheld_fields"]:
                if wf["name"] == "amount":
                    assert wf["placeholder"] == "[AMOUNT IN ₹]"
                    seen = True
        assert seen, "amount was never withheld in 50 draws"

    def test_field_never_both_given_and_withheld(self, seeds):
        for i in range(50):
            var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, i)
            withheld_names = {wf["name"] for wf in var["withheld_fields"]}
            assert not withheld_names & set(var["given_facts"])


class TestWithholdProbability:
    N = 600

    def fraction_withheld(self, seeds, register, field="amount"):
        count = 0
        for i in range(self.N):
            var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, i, register=register)
            if any(wf["name"] == field for wf in var["withheld_fields"]):
                count += 1
        return count / self.N

    def test_casual_withhold_rate(self, seeds):
        frac = self.fraction_withheld(seeds, "casual")
        assert 0.62 <= frac <= 0.78, f"casual withhold rate {frac} outside bounds"

    def test_detailed_withhold_rate(self, seeds):
        frac = self.fraction_withheld(seeds, "detailed")
        assert 0.22 <= frac <= 0.38, f"detailed withhold rate {frac} outside bounds"


class TestOutOfScope:
    def test_never_withholds(self, oos_spec, real_scenarios, seeds):
        scenarios = real_scenarios["out_of_scope"]
        for i in range(200):
            var = build(oos_spec, scenarios, seeds, i)
            assert var["withheld_fields"] == []

    def test_nearest_supported_propagated(self, oos_spec, real_scenarios, seeds):
        scenarios = real_scenarios["out_of_scope"]
        seen_values = {
            build(oos_spec, scenarios, seeds, i).get("nearest_supported")
            for i in range(200)
        }
        # scenarios.json contains both null and concrete nearest_supported values
        assert None in seen_values
        assert any(v for v in seen_values)


class TestConditionalFields:
    SPEC = {
        "doc_type": "cond_doc",
        "display_name": "Conditional",
        "structural_summary": "s",
        "statutory_requirements": "r",
        "fields": [
            {
                "name": "licensee_name",
                "placeholder": "[L]",
                "given_policy": "always",
                "kind": "person_name",
            },
            {
                "name": "licensee_company",
                "placeholder": "[CO]",
                "given_policy": "always",
                "kind": "company_name",
                "when": {"licensee_kind": "company"},
            },
        ],
    }

    def test_when_condition_respected(self, seeds):
        company = [{"id": "c", "summary": "co", "params": {"licensee_kind": "company"}}]
        individual = [
            {"id": "i", "summary": "ind", "params": {"licensee_kind": "individual"}}
        ]
        var_co = build(self.SPEC, company, seeds, 0)
        var_ind = build(self.SPEC, individual, seeds, 0)
        assert "licensee_company" in var_co["given_facts"]
        assert "licensee_company" not in var_ind["given_facts"]
        assert all(
            wf["name"] != "licensee_company" for wf in var_ind["withheld_fields"]
        )


class TestImpliesGiven:
    SPEC = {
        "doc_type": "implies_doc",
        "display_name": "Implies",
        "structural_summary": "s",
        "statutory_requirements": "r",
        "fields": [
            {
                "name": "city",
                "placeholder": "[CITY]",
                "given_policy": "withholdable",
                "kind": "city",
            },
            {
                "name": "address",
                "placeholder": "[ADDRESS]",
                "given_policy": "withholdable",
                "kind": "address",
                "implies_given": ["city"],
            },
        ],
    }

    def test_given_address_forces_city_given(self, seeds):
        scenarios = [{"id": "s", "summary": "x"}]
        for i in range(120):
            var = build(self.SPEC, scenarios, seeds, i)
            if "address" in var["given_facts"]:
                assert "city" in var["given_facts"], (
                    f"index {i}: address given but city not given"
                )


class TestScenarioAmountOverride:
    SPEC = {
        "doc_type": "amount_doc",
        "display_name": "Amount",
        "structural_summary": "s",
        "statutory_requirements": "r",
        "fields": [
            {
                "name": "claim_amount",
                "placeholder": "[AMT]",
                "given_policy": "always",
                "kind": "inr_amount",
                "range": [1000, 2000],
            },
        ],
    }

    def test_scenario_range_overrides_field_range(self, seeds):
        scenarios = [
            {
                "id": "big",
                "summary": "big amounts",
                "params": {"amount_range_inr": [900000, 1000000]},
            }
        ]
        for i in range(20):
            var = build(self.SPEC, scenarios, seeds, i)
            amount = var["given_facts"]["claim_amount"]
            assert 900000 <= amount <= 1000000


class TestRegisterDistribution:
    def test_registers_follow_config_mix(self, seeds):
        counts = {"casual": 0, "semi_formal": 0, "detailed": 0}
        n = 900
        for i in range(n):
            var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, i)
            counts[var["register"]] += 1
        assert 0.32 <= counts["casual"] / n <= 0.48
        assert 0.27 <= counts["semi_formal"] / n <= 0.43
        assert 0.17 <= counts["detailed"] / n <= 0.33


class TestValueSynthesis:
    def test_inr_amount_within_field_range(self, seeds):
        for i in range(40):
            var = build(SYNTH_SPEC, SYNTH_SCENARIOS, seeds, i)
            if "amount" in var["given_facts"]:
                assert 10000 <= var["given_facts"]["amount"] <= 50000

    def test_unknown_policy_rejected(self, seeds):
        bad = {
            **SYNTH_SPEC,
            "fields": [
                {
                    "name": "x",
                    "placeholder": "[X]",
                    "given_policy": "sometimes",
                    "kind": "city",
                }
            ],
        }
        with pytest.raises(ValueError, match="given_policy"):
            build(bad, SYNTH_SCENARIOS, seeds, 0)

    def test_unknown_kind_rejected(self, seeds):
        bad = {
            **SYNTH_SPEC,
            "fields": [
                {
                    "name": "x",
                    "placeholder": "[X]",
                    "given_policy": "always",
                    "kind": "quantum_flux",
                }
            ],
        }
        with pytest.raises(ValueError, match="kind"):
            build(bad, SYNTH_SCENARIOS, seeds, 0)


class TestDateChaining:
    """A ``relative_to`` date field is offset from its base field's date, not today.

    For cheque_bounce_138 this enforces the real-world timeline: the cheque is
    presented within the 3-month (90-day) validity window, and the bank's return
    memo follows the presentation. Drawn-from-today dates broke both invariants.
    """

    N = 300

    @pytest.fixture(scope="class")
    def cheque_spec(self):
        return load_json(META_DIR / "cheque_bounce_138.json")

    def _facts_with(self, cheque_spec, real_scenarios, seeds, *names):
        """Given-facts dicts (across N indices) where every ``name`` was given."""
        scenarios = real_scenarios["cheque_bounce_138"]
        rows = []
        for i in range(self.N):
            facts = build(cheque_spec, scenarios, seeds, i)["given_facts"]
            if all(name in facts for name in names):
                rows.append(facts)
        return rows

    def test_presentation_within_validity_of_cheque(
        self, cheque_spec, real_scenarios, seeds
    ):
        rows = self._facts_with(
            cheque_spec, real_scenarios, seeds, "cheque_date", "presentation_date"
        )
        assert rows, "no variation gave both cheque_date and presentation_date"
        for facts in rows:
            cheque = dt.date.fromisoformat(facts["cheque_date"])
            presentation = dt.date.fromisoformat(facts["presentation_date"])
            gap = (presentation - cheque).days
            assert 0 < gap <= 90, (
                f"cheque {cheque} -> presentation {presentation}: gap {gap} days "
                f"violates 0 < gap <= 90 (cheque validity)"
            )

    def test_memo_follows_presentation(self, cheque_spec, real_scenarios, seeds):
        rows = self._facts_with(
            cheque_spec, real_scenarios, seeds, "presentation_date", "memo_date"
        )
        assert rows, "no variation gave both presentation_date and memo_date"
        for facts in rows:
            presentation = dt.date.fromisoformat(facts["presentation_date"])
            memo = dt.date.fromisoformat(facts["memo_date"])
            gap = (memo - presentation).days
            assert 0 <= gap <= 3, (
                f"presentation {presentation} -> memo {memo}: gap {gap} days "
                f"violates 0 <= gap <= 3 (memo follows presentation)"
            )

    def test_full_chain_ordering_when_all_given(
        self, cheque_spec, real_scenarios, seeds
    ):
        rows = self._facts_with(
            cheque_spec,
            real_scenarios,
            seeds,
            "cheque_date",
            "presentation_date",
            "memo_date",
        )
        assert rows, "no variation gave all three date fields"
        for facts in rows:
            cheque = dt.date.fromisoformat(facts["cheque_date"])
            presentation = dt.date.fromisoformat(facts["presentation_date"])
            memo = dt.date.fromisoformat(facts["memo_date"])
            assert cheque < presentation <= memo, (
                f"timeline out of order: cheque {cheque}, "
                f"presentation {presentation}, memo {memo}"
            )

    def test_chaining_is_deterministic(self, cheque_spec, real_scenarios, seeds):
        scenarios = real_scenarios["cheque_bounce_138"]
        first = build(cheque_spec, scenarios, seeds, 11)
        second = build(cheque_spec, scenarios, seeds, 11)
        assert first == second


class TestMoneyRecoveryComplianceWindow:
    """The 15/30-day compliance window is a drafting convention, not a
    user-specific fact, so it must always be stated concretely — never withheld
    as a '[NUMBER OF DAYS TO COMPLY]' placeholder the gate then rejects."""

    @pytest.fixture(scope="class")
    def money_recovery_spec(self):
        return load_json(META_DIR / "legal_notice_money_recovery.json")

    def _scenarios(self, real_scenarios):
        return real_scenarios.get("legal_notice_money_recovery") or [
            {"id": "s", "summary": "An outstanding-dues scenario."}
        ]

    def test_compliance_days_always_given_concretely(
        self, money_recovery_spec, real_scenarios, seeds
    ):
        scenarios = self._scenarios(real_scenarios)
        for i in range(150):
            facts = build(money_recovery_spec, scenarios, seeds, i)["given_facts"]
            assert "compliance_days" in facts, (
                f"index {i}: compliance_days was withheld (would render as a "
                f"[NUMBER OF DAYS TO COMPLY] placeholder)"
            )
            assert facts["compliance_days"] in (15, 30)

    def test_compliance_days_never_appears_as_withheld(
        self, money_recovery_spec, real_scenarios, seeds
    ):
        scenarios = self._scenarios(real_scenarios)
        for i in range(150):
            var = build(money_recovery_spec, scenarios, seeds, i)
            withheld = {wf["name"] for wf in var["withheld_fields"]}
            assert "compliance_days" not in withheld
