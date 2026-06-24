"""Tests for generate.py — task planning, parsing, checkpoint/resume, and mocked API flows.

No test in this file ever touches the real Anthropic API.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import generate
import pipeline_config
from legal_rules.checker import CheckResult

TODAY = dt.date(2026, 6, 11)


@pytest.fixture(scope="module")
def config():
    return pipeline_config.load_config()


@pytest.fixture(scope="module")
def specs():
    return pipeline_config.load_specs()


@pytest.fixture()
def ctx(config, specs, tmp_path):
    return generate.RunContext(
        config=config,
        specs=specs,
        scenarios=pipeline_config.load_scenarios(),
        seeds=pipeline_config.load_seeds(),
        system_prompt="You are NyayaDraft (test).",
        display_names=pipeline_config.display_names(specs),
        out_dir=tmp_path,
        today=TODAY,
    )


def good_payload(instruction="please draft the notice", document="THE DOCUMENT TEXT"):
    return json.dumps({"instruction": instruction, "document": document})


def delimited_payload(instruction="please draft the notice", document="THE DOCUMENT TEXT"):
    return f"[[[INSTRUCTION]]]\n{instruction}\n[[[DOCUMENT]]]\n{document}\n[[[END]]]"


def fake_sync_client(payloads):
    class FakeMessages:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            text = payloads[len(self.calls) - 1]
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])

    return SimpleNamespace(messages=FakeMessages())


def batch_entry(custom_id, text=None, errored=False):
    if errored:
        result = SimpleNamespace(type="errored", error=SimpleNamespace(message="boom"))
    else:
        message = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)]
        )
        result = SimpleNamespace(type="succeeded", message=message)
    return SimpleNamespace(custom_id=custom_id, result=result)


def fake_batch_client(entries):
    class FakeBatches:
        def __init__(self):
            self.created_requests = None
            self.retrieve_calls = 0

        def create(self, requests):
            self.created_requests = list(requests)
            return SimpleNamespace(id="batch_test_1", processing_status="in_progress")

        def retrieve(self, batch_id):
            self.retrieve_calls += 1
            return SimpleNamespace(id=batch_id, processing_status="ended")

        def results(self, batch_id):
            return iter(entries)

    batches = FakeBatches()
    return SimpleNamespace(messages=SimpleNamespace(batches=batches)), batches


class TestPlanTasks:
    def test_full_run_counts(self, config):
        tasks = generate.plan_tasks(config, mode="full")
        assert len(tasks) == 920  # complexity-weighted 920-doc distribution
        counts = {
            doc_type: sum(1 for t in tasks if t.doc_type == doc_type)
            for doc_type in (
                "partnership_deed_1932",
                "consumer_complaint_cpa2019",
                "affidavit_general",
                "out_of_scope",
            )
        }
        assert counts == {
            "partnership_deed_1932": 120,
            "consumer_complaint_cpa2019": 120,
            "affidavit_general": 70,
            "out_of_scope": 50,
        }

    def test_full_run_honors_per_type_override(self):
        cfg = {
            "doc_types": ["alpha", "beta", "out_of_scope"],
            "counts": {
                "default_per_type": 500,
                "out_of_scope": 250,
                "pilot_per_type": 30,
                "per_type": {"alpha": 7, "out_of_scope": 3},
            },
            "sample_max": 10,
        }
        tasks = generate.plan_tasks(cfg, mode="full")
        counts = {
            doc_type: sum(1 for t in tasks if t.doc_type == doc_type)
            for doc_type in ("alpha", "beta", "out_of_scope")
        }
        # listed types use per_type; unlisted fall back (beta -> default,
        # out_of_scope override beats its dedicated fallback count).
        assert counts == {"alpha": 7, "beta": 500, "out_of_scope": 3}

    def test_pilot_counts(self, config):
        tasks = generate.plan_tasks(config, mode="pilot")
        assert len(tasks) == 30 * 11

    def test_sample_respects_n(self, config):
        tasks = generate.plan_tasks(config, mode="sample", sample_n=4)
        assert len(tasks) == 4

    def test_sample_capped_at_sample_max(self, config):
        tasks = generate.plan_tasks(config, mode="sample", sample_n=50)
        assert len(tasks) == config["sample_max"]

    def test_types_filter(self, config):
        tasks = generate.plan_tasks(
            config, mode="sample", sample_n=4, types=["cheque_bounce_138"]
        )
        assert len(tasks) == 4
        assert all(t.doc_type == "cheque_bounce_138" for t in tasks)

    def test_unknown_type_rejected(self, config):
        with pytest.raises(ValueError, match="nonexistent_type"):
            generate.plan_tasks(
                config, mode="sample", sample_n=2, types=["nonexistent_type"]
            )

    def test_record_ids_unique_and_stable(self, config):
        tasks = generate.plan_tasks(config, mode="pilot")
        ids = [t.record_id for t in tasks]
        assert len(ids) == len(set(ids))
        again = generate.plan_tasks(config, mode="pilot")
        assert ids == [t.record_id for t in again]


class TestParseResponse:
    def test_plain_json(self):
        instr, doc = generate.parse_response_text(good_payload("ask", "doc body"))
        assert instr == "ask"
        assert doc == "doc body"

    def test_fenced_json(self):
        text = "```json\n" + good_payload() + "\n```"
        instr, doc = generate.parse_response_text(text)
        assert instr == "please draft the notice"

    def test_surrounding_prose(self):
        text = "Here is the example:\n" + good_payload() + "\nDone."
        instr, doc = generate.parse_response_text(text)
        assert doc == "THE DOCUMENT TEXT"

    def test_invalid_json_raises(self):
        with pytest.raises(generate.ResponseParseError):
            generate.parse_response_text("not json at all")

    def test_missing_keys_raise(self):
        with pytest.raises(generate.ResponseParseError):
            generate.parse_response_text(json.dumps({"instruction": "x"}))

    def test_non_string_values_raise(self):
        with pytest.raises(generate.ResponseParseError):
            generate.parse_response_text(
                json.dumps({"instruction": "x", "document": 42})
            )

    def test_unicode_round_trip(self):
        payload = good_payload("draft for ₹5,00,000", "Deposit of ₹5,00,000 by Aarti")
        instr, doc = generate.parse_response_text(payload)
        assert "₹5,00,000" in instr
        assert "₹5,00,000" in doc


class TestParseDelimited:
    """The delimited block format needs no escaping — the fix for documents whose
    quotes/braces broke the old JSON envelope (e.g. consumer_complaint)."""

    def test_basic_round_trip(self):
        instr, doc = generate.parse_response_text(delimited_payload("ask", "body"))
        assert instr == "ask"
        assert doc == "body"

    def test_end_marker_optional(self):
        text = "[[[INSTRUCTION]]]\nask\n[[[DOCUMENT]]]\nbody text here"
        instr, doc = generate.parse_response_text(text)
        assert instr == "ask"
        assert doc == "body text here"

    def test_unescaped_quotes_and_braces_survive(self):
        # The exact shape that broke consumer_complaint under JSON: an inner
        # quote (and a brace) inside the document. No escaping under delimiters.
        doc = 'hereinafter referred to as the "Act"), having availed of {service}'
        _instr, parsed = generate.parse_response_text(delimited_payload("draft", doc))
        assert parsed == doc

    def test_surrounding_prose_tolerated(self):
        text = "Here you go:\n" + delimited_payload("ask", "body") + "\nHope that helps."
        instr, doc = generate.parse_response_text(text)
        assert instr == "ask"
        assert doc == "body"

    def test_marker_whitespace_and_case_tolerated(self):
        text = "[[[ instruction ]]]\nask\n[[[ Document ]]]\nbody"
        instr, doc = generate.parse_response_text(text)
        assert instr == "ask"
        assert doc == "body"

    def test_multiline_document_preserved(self):
        document = "LINE ONE\n\nLINE TWO\nLINE THREE"
        _instr, doc = generate.parse_response_text(delimited_payload("ask", document))
        assert doc == document

    def test_falls_back_to_json_when_no_markers(self):
        instr, doc = generate.parse_response_text(good_payload("j-ask", "j-doc"))
        assert instr == "j-ask"
        assert doc == "j-doc"

    def test_empty_document_between_markers_raises(self):
        text = "[[[INSTRUCTION]]]\nask\n[[[DOCUMENT]]]\n   \n[[[END]]]"
        with pytest.raises(generate.ResponseParseError):
            generate.parse_response_text(text)


class TestCheckpointResume:
    def test_completed_ids_from_both_files(self, tmp_path):
        (tmp_path / "records.jsonl").write_text(
            json.dumps({"id": "a-00001"}) + "\n", encoding="utf-8"
        )
        (tmp_path / "rejects.jsonl").write_text(
            json.dumps({"id": "b-00002"}) + "\n", encoding="utf-8"
        )
        assert generate.load_completed_ids(tmp_path) == frozenset(
            {"a-00001", "b-00002"}
        )

    def test_empty_dir_no_completed(self, tmp_path):
        assert generate.load_completed_ids(tmp_path) == frozenset()

    def test_remaining_tasks_skips_completed(self, config):
        tasks = generate.plan_tasks(
            config, mode="sample", sample_n=4, types=["cheque_bounce_138"]
        )
        done = frozenset({tasks[0].record_id, tasks[2].record_id})
        remaining = generate.remaining_tasks(tasks, done)
        assert [t.record_id for t in remaining] == [
            tasks[1].record_id,
            tasks[3].record_id,
        ]


class TestSampleRun:
    def test_sample_writes_samples_not_records(self, ctx, monkeypatch, capsys):
        monkeypatch.setattr(
            generate, "check_document", lambda doc_type, text: CheckResult(ok=True)
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=2, types=["cheque_bounce_138"]
        )
        client = fake_sync_client([good_payload(), good_payload("second ask")])
        summary = generate.run_sample(client, tasks, ctx)

        assert summary["ok"] == 2
        samples = (ctx.out_dir / "samples.jsonl").read_text(encoding="utf-8")
        assert len(samples.strip().splitlines()) == 2
        assert not (ctx.out_dir / "records.jsonl").exists()
        printed = capsys.readouterr().out
        assert "please draft the notice" in printed

    def test_sample_uses_config_model_params(self, ctx, monkeypatch):
        monkeypatch.setattr(
            generate, "check_document", lambda doc_type, text: CheckResult(ok=True)
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["cheque_bounce_138"]
        )
        client = fake_sync_client([good_payload()])
        generate.run_sample(client, tasks, ctx)
        call = client.messages.calls[0]
        assert call["model"] == ctx.config["generation"]["model"]
        assert call["temperature"] == ctx.config["generation"]["temperature"]
        assert call["max_tokens"] == ctx.config["generation"]["max_tokens"]

    def test_sample_run_parses_delimited_output(self, ctx, monkeypatch):
        monkeypatch.setattr(
            generate, "check_document", lambda doc_type, text: CheckResult(ok=True)
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["cheque_bounce_138"]
        )
        client = fake_sync_client([delimited_payload("delim ask", "delim doc body")])
        summary = generate.run_sample(client, tasks, ctx)
        assert summary["ok"] == 1
        record = json.loads(
            (ctx.out_dir / "samples.jsonl").read_text(encoding="utf-8").strip()
        )
        assert record["messages"][1]["content"] == "delim ask"
        assert record["messages"][2]["content"] == "delim doc body"

    def test_sample_saves_check_failure_with_content(self, ctx, monkeypatch):
        monkeypatch.setattr(
            generate,
            "check_document",
            lambda doc_type, text: CheckResult(ok=False, failures=("missing_x",)),
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["cheque_bounce_138"]
        )
        client = fake_sync_client([good_payload("ask", "THE FULL DRAFT TEXT")])
        summary = generate.run_sample(client, tasks, ctx)

        assert summary["rejected"] == 1
        assert not (ctx.out_dir / "samples.jsonl").exists()
        rejects = [
            json.loads(line)
            for line in (ctx.out_dir / "rejects.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        ]
        assert len(rejects) == 1
        rej = rejects[0]
        assert rej["error_kind"] == "check_failed"
        assert rej["failures"] == ["missing_x"]
        assert rej["document"] == "THE FULL DRAFT TEXT"
        assert "THE FULL DRAFT TEXT" in rej["raw"]

    def test_sample_saves_parse_error_raw_text(self, ctx):
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["cheque_bounce_138"]
        )
        client = fake_sync_client(["this is not valid json at all"])
        summary = generate.run_sample(client, tasks, ctx)

        assert summary["rejected"] == 1
        rejects = [
            json.loads(line)
            for line in (ctx.out_dir / "rejects.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        ]
        assert len(rejects) == 1
        rej = rejects[0]
        assert rej["error_kind"] == "parse_error"
        assert rej["raw"] == "this is not valid json at all"
        assert rej["document"] is None


class TestBatchRun:
    def test_batch_flow_routes_records_and_rejects(self, ctx, monkeypatch):
        def fake_check(doc_type, text):
            ok = "BAD" not in text
            return CheckResult(ok=ok, failures=() if ok else ("forced_failure",))

        monkeypatch.setattr(generate, "check_document", fake_check)
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=3, types=["cheque_bounce_138"]
        )
        entries = [
            batch_entry(tasks[0].record_id, good_payload("a", "GOOD DOC")),
            batch_entry(tasks[1].record_id, good_payload("b", "BAD DOC")),
            batch_entry(tasks[2].record_id, errored=True),
        ]
        client, batches = fake_batch_client(entries)
        summary = generate.run_batch(client, tasks, ctx, poll_interval=0)

        assert summary["ok"] == 1
        assert summary["rejected"] == 2
        records = [
            json.loads(line)
            for line in (ctx.out_dir / "records.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        ]
        rejects = [
            json.loads(line)
            for line in (ctx.out_dir / "rejects.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        ]
        assert len(records) == 1
        assert len(rejects) == 2
        assert records[0]["id"] == tasks[0].record_id
        assert records[0]["check"]["ok"] is True
        kinds = {r["error_kind"] for r in rejects}
        assert kinds == {"check_failed", "api_error"}

        # requests sent with custom ids + config params
        sent = batches.created_requests
        assert [r["custom_id"] for r in sent] == [t.record_id for t in tasks]
        assert all(
            r["params"]["model"] == ctx.config["generation"]["model"] for r in sent
        )

    def test_batch_rejects_carry_content_for_triage(self, ctx, monkeypatch):
        def fake_check(doc_type, text):
            ok = "BAD" not in text
            return CheckResult(ok=ok, failures=() if ok else ("forced_failure",))

        monkeypatch.setattr(generate, "check_document", fake_check)
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=2, types=["cheque_bounce_138"]
        )
        entries = [
            batch_entry(tasks[0].record_id, good_payload("b", "BAD DOC BODY")),
            batch_entry(tasks[1].record_id, errored=True),
        ]
        client, _ = fake_batch_client(entries)
        generate.run_batch(client, tasks, ctx, poll_interval=0)

        rejects = {
            json.loads(line)["error_kind"]: json.loads(line)
            for line in (ctx.out_dir / "rejects.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        }
        # check_failed reject keeps both the raw output and the parsed document
        assert rejects["check_failed"]["document"] == "BAD DOC BODY"
        assert "BAD DOC BODY" in rejects["check_failed"]["raw"]
        # api_error has no model output at all
        assert rejects["api_error"]["raw"] is None
        assert rejects["api_error"]["document"] is None

    def test_rerun_skips_completed(self, ctx, monkeypatch):
        monkeypatch.setattr(
            generate, "check_document", lambda doc_type, text: CheckResult(ok=True)
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=2, types=["cheque_bounce_138"]
        )
        entries = [
            batch_entry(t.record_id, good_payload(f"i{n}", f"d{n}"))
            for n, t in enumerate(tasks)
        ]
        client, _ = fake_batch_client(entries)
        generate.run_batch(client, tasks, ctx, poll_interval=0)

        completed = generate.load_completed_ids(ctx.out_dir)
        assert generate.remaining_tasks(tasks, completed) == ()


class TestRecordFormat:
    def test_chat_format_roles(self, ctx, monkeypatch):
        monkeypatch.setattr(
            generate, "check_document", lambda doc_type, text: CheckResult(ok=True)
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["leave_license_mh"]
        )
        entries = [batch_entry(tasks[0].record_id, good_payload("ask me", "doc out"))]
        client, _ = fake_batch_client(entries)
        generate.run_batch(client, tasks, ctx, poll_interval=0)
        record = json.loads(
            (ctx.out_dir / "records.jsonl").read_text(encoding="utf-8").strip()
        )
        roles = [m["role"] for m in record["messages"]]
        assert roles == ["system", "user", "assistant"]
        assert record["messages"][0]["content"] == ctx.system_prompt
        assert record["messages"][1]["content"] == "ask me"
        assert record["messages"][2]["content"] == "doc out"
        assert record["doc_type"] == "leave_license_mh"
        assert "scenario_id" in record
        assert "register" in record

    def test_real_checker_wired_for_out_of_scope(self, ctx):
        """Integration: a well-formed refusal passes the real legal_rules gate."""
        refusal = (
            "I am sorry, but I cannot tell you whether to take your builder to "
            "court or what the outcome might be, as I do not give legal advice "
            "or predictions. I can only draft documents. If it would help, I can "
            "draft a consumer complaint or a demand notice for you once you share "
            "the basic facts. For guidance on the merits of the matter itself, "
            "please consult a qualified advocate who can review your papers."
        )
        result = generate.check_document("out_of_scope", refusal)
        assert result.ok, result.failures


class TestUtf8Stdio:
    """The CLI must be able to print ₹ and other non-cp1252 chars on Windows."""

    def test_reconfigures_stdout_and_stderr_to_utf8(self, monkeypatch):
        calls = {}

        class FakeStream:
            def __init__(self, name):
                self.name = name

            def reconfigure(self, **kwargs):
                calls[self.name] = kwargs

        monkeypatch.setattr(generate.sys, "stdout", FakeStream("out"))
        monkeypatch.setattr(generate.sys, "stderr", FakeStream("err"))
        generate._force_utf8_stdio()
        assert calls["out"]["encoding"] == "utf-8"
        assert calls["err"]["encoding"] == "utf-8"

    def test_tolerates_streams_without_reconfigure(self, monkeypatch):
        # e.g. a stream replaced by a plain object; must not raise.
        monkeypatch.setattr(generate.sys, "stdout", object())
        monkeypatch.setattr(generate.sys, "stderr", object())
        generate._force_utf8_stdio()  # no exception == pass

    def test_tolerates_reconfigure_raising(self, monkeypatch):
        class Stubborn:
            def reconfigure(self, **kwargs):
                raise ValueError("cannot reconfigure a detached buffer")

        monkeypatch.setattr(generate.sys, "stdout", Stubborn())
        monkeypatch.setattr(generate.sys, "stderr", Stubborn())
        generate._force_utf8_stdio()  # swallowed == pass


class TestReviewFlag:
    def test_deterministic(self):
        a = generate.review_flag(20260610, 0.05, "cheque_bounce_138-00001")
        b = generate.review_flag(20260610, 0.05, "cheque_bounce_138-00001")
        assert a == b

    def test_fraction_extremes(self):
        assert generate.review_flag(1, 1.0, "any-id") is True
        assert generate.review_flag(1, 0.0, "any-id") is False


class TestTruncation:
    """A max_tokens-truncated reply must be rejected, never silently accepted as
    a (partial) training pair — see generate._is_truncated."""

    def test_sync_truncated_response_rejected(self, ctx, monkeypatch):
        monkeypatch.setattr(
            generate, "check_document", lambda doc_type, text: CheckResult(ok=True)
        )
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["cheque_bounce_138"]
        )

        class FakeMessages:
            def create(self, **kwargs):
                return SimpleNamespace(
                    content=[SimpleNamespace(type="text", text=delimited_payload("ask", "PARTIAL"))],
                    stop_reason="max_tokens",
                )

        client = SimpleNamespace(messages=FakeMessages())
        summary = generate.run_sample(client, tasks, ctx)

        assert summary == {"ok": 0, "rejected": 1}
        assert not (ctx.out_dir / "samples.jsonl").exists()
        rejects = [
            json.loads(line)
            for line in (ctx.out_dir / "rejects.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rejects[0]["error_kind"] == "truncated"

    def test_batch_truncated_response_rejected(self, ctx):
        tasks = generate.plan_tasks(
            ctx.config, mode="sample", sample_n=1, types=["cheque_bounce_138"]
        )
        entry = batch_entry(tasks[0].record_id, text=delimited_payload("ask", "PARTIAL"))
        entry.result.message.stop_reason = "max_tokens"
        client, _ = fake_batch_client([entry])
        summary = generate.run_batch(client, tasks, ctx, poll_interval=0)

        assert summary["rejected"] == 1
        assert not (ctx.out_dir / "records.jsonl").exists()
        rejects = [
            json.loads(line)
            for line in (ctx.out_dir / "rejects.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rejects[0]["error_kind"] == "truncated"
