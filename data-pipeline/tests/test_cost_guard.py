"""Tests for the mandatory cost guard in generate.py — pure math + confirmation gate."""
from __future__ import annotations

import pytest

import generate

CONFIG = {
    "generation": {
        "model": "claude-sonnet-4-6",
        "temperature": 0.9,
        "max_tokens": 4096,
        "use_batch_api": True,
        "est_input_tokens": 1900,
        "est_output_tokens": 2300,
    },
    "pricing": {
        "usd_per_mtok_input": 3.0,
        "usd_per_mtok_output": 15.0,
        "batch_discount": 0.5,
        "usd_to_inr": 88.0,
    },
}


class TestCostMath:
    def test_sync_cost_per_request(self):
        est = generate.estimate_cost(1, CONFIG, use_batch=False)
        # (1900 * 3.0 + 2300 * 15.0) / 1e6 = 0.0402
        assert est["usd"] == pytest.approx(0.0402)
        assert est["inr"] == pytest.approx(0.0402 * 88.0)

    def test_batch_cost_applies_discount(self):
        est = generate.estimate_cost(100, CONFIG, use_batch=True)
        assert est["usd"] == pytest.approx(2.01)
        assert est["inr"] == pytest.approx(176.88)

    def test_sync_cost_no_discount(self):
        est = generate.estimate_cost(100, CONFIG, use_batch=False)
        assert est["usd"] == pytest.approx(4.02)
        assert est["inr"] == pytest.approx(353.76)

    def test_full_run_scale(self):
        # 10 types x 500 + 250 out_of_scope = 5250 requests batched
        est = generate.estimate_cost(5250, CONFIG, use_batch=True)
        assert est["usd"] == pytest.approx(105.525)
        assert est["n_requests"] == 5250

    def test_zero_requests(self):
        est = generate.estimate_cost(0, CONFIG, use_batch=True)
        assert est["usd"] == 0.0
        assert est["inr"] == 0.0


class TestCostGuardMessage:
    def test_message_shows_usd_and_inr(self):
        est = generate.estimate_cost(100, CONFIG, use_batch=True)
        text = generate.format_cost_guard(est, use_batch=True)
        assert "USD" in text or "$" in text
        assert "₹" in text
        assert "2.01" in text
        assert "176.88" in text
        assert "100" in text

    def test_message_mentions_batch_mode(self):
        est = generate.estimate_cost(10, CONFIG, use_batch=True)
        text = generate.format_cost_guard(est, use_batch=True)
        assert "batch" in text.lower()


class TestConfirmation:
    def test_exact_yes_proceeds(self):
        generate.confirm_or_abort(input_fn=lambda _: "YES")  # must not raise

    def test_lowercase_yes_aborts(self):
        with pytest.raises(SystemExit):
            generate.confirm_or_abort(input_fn=lambda _: "yes")

    def test_empty_aborts(self):
        with pytest.raises(SystemExit):
            generate.confirm_or_abort(input_fn=lambda _: "")

    def test_no_aborts(self):
        with pytest.raises(SystemExit):
            generate.confirm_or_abort(input_fn=lambda _: "no")

    def test_whitespace_around_yes_accepted(self):
        generate.confirm_or_abort(input_fn=lambda _: "  YES  ")


class TestApiKey:
    def test_missing_key_is_friendly_exit(self):
        with pytest.raises(SystemExit) as excinfo:
            generate.get_api_key(env={})
        assert "ANTHROPIC_API_KEY" in str(excinfo.value)

    def test_empty_key_is_friendly_exit(self):
        with pytest.raises(SystemExit):
            generate.get_api_key(env={"ANTHROPIC_API_KEY": "  "})

    def test_present_key_returned(self):
        assert generate.get_api_key(env={"ANTHROPIC_API_KEY": "sk-test"}) == "sk-test"
