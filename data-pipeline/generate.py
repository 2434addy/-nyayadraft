"""NyayaDraft generation pipeline orchestrator.

This module turns the central config + meta-prompt specs into Anthropic API
requests, parses the responses into chat-format training pairs, validates each
draft against the statutory ``legal_rules`` gate, and writes JSONL outputs with
checkpoint/resume support. A mandatory cost guard estimates spend BEFORE any
generation and requires explicit ``YES`` confirmation for non-trivial runs.

Public API (exercised by the test suite):

  Task                      -- frozen record describing one unit of work
  RunContext                -- immutable bundle of loaded config + assets
  ResponseParseError        -- raised when a model response is unusable
  plan_tasks                -- build the deterministic task list for a mode
  parse_response_text       -- extract {instruction, document} from raw text
  load_completed_ids        -- read finished record ids from output files
  remaining_tasks           -- filter a task list against completed ids
  estimate_cost             -- pure cost math (USD + INR) for the cost guard
  format_cost_guard         -- human-readable cost-guard message
  confirm_or_abort          -- YES/abort confirmation gate
  get_api_key               -- read ANTHROPIC_API_KEY or exit with guidance
  review_flag               -- deterministic per-record lawyer-review sampling
  check_document            -- thin re-export of legal_rules.checker
  run_sample                -- sync run that writes approval samples
  run_batch                 -- Batches API run that writes records + rejects

No function here ever contacts the real Anthropic API; the API client is always
injected, so the whole module is unit-testable offline with mocks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Protocol, Sequence

from legal_rules.checker import CheckResult
from legal_rules.checker import check_document as _check_document

if TYPE_CHECKING:  # imported lazily at call time so cost-guard/planning work alone
    import prompts as _prompts_mod
    import variation as _variation_mod

log = logging.getLogger("generate")

DISCLAIMER = (
    "This is an AI-generated draft for review by the parties and is not legal advice."
)
RECORDS_FILE = "records.jsonl"
REJECTS_FILE = "rejects.jsonl"
SAMPLES_FILE = "samples.jsonl"
OUT_OF_SCOPE = "out_of_scope"
VALID_MODES = ("full", "pilot", "sample")
ENDED_STATUSES = frozenset({"ended", "completed"})


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Task:
    """One unit of generation work: a single (doc_type, index) draft."""

    doc_type: str
    index: int
    record_id: str


@dataclass(frozen=True)
class RunContext:
    """Immutable bundle of everything a run needs beyond the task list."""

    config: Mapping[str, Any]
    specs: Mapping[str, Mapping[str, Any]]
    scenarios: Mapping[str, Sequence[Mapping[str, Any]]]
    seeds: Mapping[str, Any]
    system_prompt: str
    display_names: Mapping[str, str]
    out_dir: Path
    today: dt.date


class ResponseParseError(ValueError):
    """Raised when a model response cannot be parsed into a training pair."""


class _Messages(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _SyncClient(Protocol):
    messages: _Messages


# --------------------------------------------------------------------------- #
# Validation re-export (monkeypatched in tests, so keep it a module attribute)
# --------------------------------------------------------------------------- #
def check_document(doc_type: str, text: str) -> CheckResult:
    """Run the statutory/structural gate for one draft. See legal_rules.checker."""
    return _check_document(doc_type, text)


# --------------------------------------------------------------------------- #
# Task planning
# --------------------------------------------------------------------------- #
def _record_id(doc_type: str, index: int) -> str:
    """Stable, unique id for a (doc_type, index) pair, e.g. 'cheque_bounce_138-00001'."""
    return f"{doc_type}-{index:05d}"


def _doc_types(config: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(config["doc_types"])


def _full_counts(config: Mapping[str, Any]) -> dict[str, int]:
    counts = config["counts"]
    default = int(counts["default_per_type"])
    oos = int(counts["out_of_scope"])
    return {
        doc_type: oos if doc_type == OUT_OF_SCOPE else default
        for doc_type in _doc_types(config)
    }


def _pilot_counts(config: Mapping[str, Any]) -> dict[str, int]:
    pilot = int(config["counts"]["pilot_per_type"])
    return {doc_type: pilot for doc_type in _doc_types(config)}


def _validate_types(config: Mapping[str, Any], types: Sequence[str] | None) -> None:
    if not types:
        return
    known = set(_doc_types(config))
    unknown = [t for t in types if t not in known]
    if unknown:
        raise ValueError(f"unknown doc_type(s): {', '.join(unknown)}")


def plan_tasks(
    config: Mapping[str, Any],
    *,
    mode: str,
    sample_n: int = 5,
    types: Sequence[str] | None = None,
) -> tuple[Task, ...]:
    """Build the deterministic, stably-ordered task list for ``mode``.

    full   -> default_per_type for every type, out_of_scope count for OOS.
    pilot  -> pilot_per_type for EVERY type (incl. out_of_scope).
    sample -> first ``min(sample_n, sample_max)`` tasks of the full plan.
    ``types`` restricts (and validates) which doc types are planned.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode '{mode}' (expected one of {VALID_MODES})")
    _validate_types(config, types)

    counts = _pilot_counts(config) if mode == "pilot" else _full_counts(config)
    selected = list(types) if types else list(_doc_types(config))

    tasks = tuple(
        Task(doc_type, index, _record_id(doc_type, index))
        for doc_type in selected
        for index in range(counts[doc_type])
    )

    if mode == "sample":
        limit = min(int(sample_n), int(config["sample_max"]))
        return tasks[:limit]
    return tasks


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #
def _extract_json_object(text: str) -> str:
    """Find the first balanced top-level JSON object in ``text``."""
    fenced = text
    if "```" in fenced:
        # Drop language hints and fences; keep the inner content.
        parts = fenced.split("```")
        # Odd indices are fenced blocks; prefer the first that looks like JSON.
        for block in parts[1::2]:
            stripped = block.lstrip()
            if stripped.startswith("json"):
                stripped = stripped[len("json"):]
            if "{" in stripped:
                fenced = stripped
                break

    start = fenced.find("{")
    if start == -1:
        raise ResponseParseError("no JSON object found in response")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(fenced)):
        char = fenced[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return fenced[start : i + 1]
    raise ResponseParseError("unbalanced JSON object in response")


def parse_response_text(text: str) -> tuple[str, str]:
    """Parse a raw model response into ``(instruction, document)`` strings.

    Tolerates surrounding prose and ```json fenced blocks. Raises
    ``ResponseParseError`` on invalid JSON, missing keys, or non-string values.
    """
    candidate = _extract_json_object(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ResponseParseError("response JSON is not an object")
    missing = [key for key in ("instruction", "document") if key not in data]
    if missing:
        raise ResponseParseError(f"missing keys: {', '.join(missing)}")
    instruction = data["instruction"]
    document = data["document"]
    if not isinstance(instruction, str) or not isinstance(document, str):
        raise ResponseParseError("instruction and document must be strings")
    return instruction, document


def _message_text(message: Any) -> str:
    """Concatenate the text blocks of an Anthropic message object."""
    blocks = getattr(message, "content", None)
    if not blocks:
        raise ResponseParseError("message has no content blocks")
    parts = [
        block.text
        for block in blocks
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    if not parts:
        raise ResponseParseError("message has no text content")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Checkpoint / resume
# --------------------------------------------------------------------------- #
def _ids_from_file(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log.warning("skipping malformed line in %s", path.name)
                continue
            record_id = record.get("id")
            if isinstance(record_id, str):
                ids.add(record_id)
    return ids


def load_completed_ids(out_dir: Path) -> frozenset[str]:
    """Return ids already present in records.jsonl and rejects.jsonl."""
    completed: set[str] = set()
    completed |= _ids_from_file(out_dir / RECORDS_FILE)
    completed |= _ids_from_file(out_dir / REJECTS_FILE)
    return frozenset(completed)


def remaining_tasks(
    tasks: Sequence[Task], completed: frozenset[str]
) -> tuple[Task, ...]:
    """Return tasks whose record_id is not already completed (order preserved)."""
    return tuple(task for task in tasks if task.record_id not in completed)


# --------------------------------------------------------------------------- #
# Cost guard
# --------------------------------------------------------------------------- #
def estimate_cost(
    n_requests: int, config: Mapping[str, Any], *, use_batch: bool
) -> dict[str, Any]:
    """Estimate API spend for ``n_requests`` generations (pure math)."""
    gen = config["generation"]
    pricing = config["pricing"]
    in_tokens = float(gen["est_input_tokens"])
    out_tokens = float(gen["est_output_tokens"])
    per_request_usd = (
        in_tokens * float(pricing["usd_per_mtok_input"])
        + out_tokens * float(pricing["usd_per_mtok_output"])
    ) / 1_000_000
    discount = float(pricing["batch_discount"]) if use_batch else 1.0
    usd = per_request_usd * int(n_requests) * discount
    inr = usd * float(pricing["usd_to_inr"])
    return {
        "n_requests": int(n_requests),
        "use_batch": bool(use_batch),
        "usd": usd,
        "inr": inr,
    }


def format_cost_guard(est: Mapping[str, Any], *, use_batch: bool) -> str:
    """Build the human-readable cost-guard message shown before spending."""
    mode = "Batches API (50% discount)" if use_batch else "synchronous API"
    return (
        "COST GUARD\n"
        f"  Requests : {est['n_requests']}\n"
        f"  Mode     : {mode}\n"
        f"  Estimated: USD ${est['usd']:.2f}  /  ₹{est['inr']:.2f}\n"
    )


def confirm_or_abort(
    *,
    prompt: str = "Type YES to proceed with generation: ",
    input_fn: Callable[[str], str] = input,
) -> None:
    """Require an exact uppercase ``YES`` (surrounding whitespace ok) or exit."""
    answer = input_fn(prompt)
    if answer.strip() != "YES":
        raise SystemExit("Aborted: confirmation not given (expected exactly 'YES').")


def get_api_key(env: Mapping[str, str] | None = None) -> str:
    """Read ANTHROPIC_API_KEY from ``env`` (defaults to os.environ) or exit."""
    environment = os.environ if env is None else env
    key = environment.get("ANTHROPIC_API_KEY", "")
    if not key.strip():
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Export it before running generation, "
            "e.g.  set ANTHROPIC_API_KEY=sk-...  (it is never read from code)."
        )
    return key


# --------------------------------------------------------------------------- #
# Review sampling
# --------------------------------------------------------------------------- #
def review_flag(seed: int, fraction: float, record_id: str) -> bool:
    """Deterministically decide whether ``record_id`` is flagged for review.

    Stable across runs for a given (seed, fraction, record_id). ``fraction``
    1.0 always flags, 0.0 never flags.
    """
    if fraction <= 0.0:
        return False
    if fraction >= 1.0:
        return True
    digest = hashlib.sha256(f"{seed}:{record_id}".encode("utf-8")).hexdigest()
    # Map the first 8 hex digits to [0, 1).
    bucket = int(digest[:8], 16) / 0x1_0000_0000
    return bucket < fraction


# --------------------------------------------------------------------------- #
# Request building + record assembly
# --------------------------------------------------------------------------- #
def _build_variation(task: Task, ctx: RunContext) -> dict[str, Any]:
    import variation  # lazy: sibling module, only needed for real generation

    spec = ctx.specs[task.doc_type]
    scenarios = ctx.scenarios[task.doc_type]
    return variation.build_variation(
        spec,
        scenarios,
        ctx.seeds,
        ctx.config,
        task.index,
        today=ctx.today,
    )


def _render_user_prompt(var: Mapping[str, Any], ctx: RunContext) -> str:
    import prompts  # lazy: sibling module, only needed for real generation

    spec = ctx.specs[var["doc_type"]]
    return prompts.render_prompt(
        spec,
        var,
        ctx.system_prompt,
        display_names=ctx.display_names,
    )


def _model_params(ctx: RunContext) -> dict[str, Any]:
    gen = ctx.config["generation"]
    return {
        "model": gen["model"],
        "max_tokens": int(gen["max_tokens"]),
        "temperature": float(gen["temperature"]),
    }


def _chat_record(
    task: Task,
    var: Mapping[str, Any],
    instruction: str,
    document: str,
    check: CheckResult,
    ctx: RunContext,
) -> dict[str, Any]:
    """Assemble a chat-format training record for one accepted draft."""
    fraction = float(ctx.config.get("review_sample_fraction", 0.0))
    seed = int(ctx.config.get("seed", 0))
    return {
        "id": task.record_id,
        "doc_type": task.doc_type,
        "scenario_id": var.get("scenario_id"),
        "register": var.get("register"),
        "messages": [
            {"role": "system", "content": ctx.system_prompt},
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": document},
        ],
        "check": {
            "ok": check.ok,
            "warnings": list(check.warnings),
        },
        "flagged_for_review": review_flag(seed, fraction, task.record_id),
    }


def _reject_record(
    task: Task, error_kind: str, detail: str, failures: Iterable[str] = ()
) -> dict[str, Any]:
    return {
        "id": task.record_id,
        "doc_type": task.doc_type,
        "error_kind": error_kind,
        "detail": detail,
        "failures": list(failures),
    }


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _process_text(
    task: Task, var: Mapping[str, Any], text: str, ctx: RunContext
) -> tuple[str, dict[str, Any]]:
    """Parse + validate one response. Returns (outcome, record).

    outcome is 'ok' (record is a chat record) or 'rejected' (record is a reject).
    """
    try:
        instruction, document = parse_response_text(text)
    except ResponseParseError as exc:
        return "rejected", _reject_record(task, "parse_error", str(exc))
    check = check_document(task.doc_type, document)
    if not check.ok:
        return "rejected", _reject_record(
            task, "check_failed", "statutory/structural gate failed", check.failures
        )
    return "ok", _chat_record(task, var, instruction, document, check, ctx)


# --------------------------------------------------------------------------- #
# Sample run (synchronous; writes approval samples, never records)
# --------------------------------------------------------------------------- #
def run_sample(
    client: _SyncClient, tasks: Sequence[Task], ctx: RunContext
) -> dict[str, Any]:
    """Generate a handful of pairs synchronously and write them to samples.jsonl.

    Prints each parsed instruction/document for human approval. Does NOT write
    records.jsonl -- samples are for the pre-mass-generation approval gate.
    """
    params = _model_params(ctx)
    summary = {"ok": 0, "rejected": 0}
    samples_path = ctx.out_dir / SAMPLES_FILE
    for task in tasks:
        var = _build_variation(task, ctx)
        user_prompt = _render_user_prompt(var, ctx)
        message = client.messages.create(
            system=ctx.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            **params,
        )
        text = _message_text(message)
        outcome, record = _process_text(task, var, text, ctx)
        summary[outcome] += 1
        if outcome == "ok":
            _append_jsonl(samples_path, record)
            print(f"\n=== SAMPLE {record['id']} ({record['doc_type']}) ===")
            print(f"INSTRUCTION: {record['messages'][1]['content']}")
            print(f"DOCUMENT:\n{record['messages'][2]['content']}")
        else:
            print(f"\n=== REJECTED {record['id']}: {record['error_kind']} ===")
    return summary


# --------------------------------------------------------------------------- #
# Batch run (Batches API; writes records + rejects with resume support)
# --------------------------------------------------------------------------- #
def _batch_request(task: Task, ctx: RunContext) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build (request_payload, variation) for one task."""
    var = _build_variation(task, ctx)
    user_prompt = _render_user_prompt(var, ctx)
    params = {
        **_model_params(ctx),
        "system": ctx.system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    request = {"custom_id": task.record_id, "params": params}
    return request, var


def _poll_batch(batches: Any, batch_id: str, poll_interval: float) -> None:
    """Block until the batch finishes, polling at ``poll_interval`` seconds."""
    while True:
        info = batches.retrieve(batch_id)
        status = getattr(info, "processing_status", None)
        if status in ENDED_STATUSES:
            return
        if poll_interval > 0:
            time.sleep(poll_interval)
        else:
            # poll_interval == 0 is the test fast-path: one retrieve, then stop.
            return


def _result_text(entry: Any) -> tuple[bool, str]:
    """Return (succeeded, text_or_error) for one batch result entry."""
    result = entry.result
    if getattr(result, "type", None) != "succeeded":
        error = getattr(result, "error", None)
        message = getattr(error, "message", "unknown batch error")
        return False, message
    return True, _message_text(result.message)


def run_batch(
    client: Any,
    tasks: Sequence[Task],
    ctx: RunContext,
    *,
    poll_interval: float = 30.0,
) -> dict[str, Any]:
    """Run the Batches API flow: submit, poll, route results to records/rejects."""
    by_id = {task.record_id: task for task in tasks}
    variations: dict[str, dict[str, Any]] = {}
    requests: list[dict[str, Any]] = []
    for task in tasks:
        request, var = _batch_request(task, ctx)
        requests.append(request)
        variations[task.record_id] = var

    batches = client.messages.batches
    batch = batches.create(requests=requests)
    _poll_batch(batches, batch.id, poll_interval)

    records_path = ctx.out_dir / RECORDS_FILE
    rejects_path = ctx.out_dir / REJECTS_FILE
    summary = {"ok": 0, "rejected": 0}
    for entry in batches.results(batch.id):
        task = by_id.get(entry.custom_id)
        if task is None:
            log.warning("batch returned unknown custom_id %s", entry.custom_id)
            continue
        succeeded, payload = _result_text(entry)
        if not succeeded:
            summary["rejected"] += 1
            _append_jsonl(rejects_path, _reject_record(task, "api_error", payload))
            continue
        outcome, record = _process_text(task, variations[task.record_id], payload, ctx)
        summary[outcome] += 1
        target = records_path if outcome == "ok" else rejects_path
        _append_jsonl(target, record)
    return summary


# --------------------------------------------------------------------------- #
# CLI entry point (the only place print() and real I/O wiring live)
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NyayaDraft generation pipeline")
    parser.add_argument(
        "--mode", choices=VALID_MODES, default="sample", help="generation mode"
    )
    parser.add_argument("--sample-n", type=int, default=5, help="sample size")
    parser.add_argument(
        "--types", nargs="*", default=None, help="restrict to these doc types"
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("out"), help="output directory"
    )
    parser.add_argument(
        "--yes", action="store_true", help="skip the interactive cost-guard prompt"
    )
    return parser


def _load_context(out_dir: Path) -> RunContext:
    import pipeline_config

    specs = pipeline_config.load_specs()
    return RunContext(
        config=pipeline_config.load_config(),
        specs=specs,
        scenarios=pipeline_config.load_scenarios(),
        seeds=pipeline_config.load_seeds(),
        system_prompt=pipeline_config.load_system_prompt(),
        display_names=pipeline_config.display_names(specs),
        out_dir=out_dir,
        today=dt.date.today(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: plan, cost-guard, confirm, then run (sync or batch)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_arg_parser().parse_args(argv)

    api_key = get_api_key()
    # Canonicalize the output directory up front so relative traversal segments
    # (e.g. ../) are resolved before any file I/O. resolve() is idempotent on
    # absolute paths, so tmp_path-based callers are unaffected.
    out_dir = args.out_dir.resolve()
    ctx = _load_context(out_dir)
    use_batch = args.mode != "sample" and bool(ctx.config["generation"]["use_batch_api"])

    tasks = plan_tasks(
        ctx.config, mode=args.mode, sample_n=args.sample_n, types=args.types
    )
    completed = load_completed_ids(ctx.out_dir)
    pending = remaining_tasks(tasks, completed)
    if not pending:
        print("Nothing to do: all planned tasks are already completed.")
        return 0

    est = estimate_cost(len(pending), ctx.config, use_batch=use_batch)
    cost_guard_text = format_cost_guard(est, use_batch=use_batch)
    print(cost_guard_text)
    log.info(cost_guard_text)
    requires_confirmation = len(pending) > int(ctx.config["sample_max"])
    if requires_confirmation and not args.yes:
        confirm_or_abort()
    elif requires_confirmation and args.yes:
        # --yes bypassed the interactive gate for a non-trivial run; leave a
        # durable trace of the estimated spend that was authorized unattended.
        log.warning(
            "Cost-guard confirmation skipped via --yes for %s requests "
            "(estimated USD $%.2f / INR %.2f).",
            est["n_requests"],
            est["usd"],
            est["inr"],
        )

    try:
        import anthropic
    except ImportError:  # pragma: no cover - exercised only with the SDK absent
        raise SystemExit(
            "The 'anthropic' package is required to run generation. "
            "Install it with: pip install anthropic"
        )
    client = anthropic.Anthropic(api_key=api_key)

    if args.mode == "sample":
        summary = run_sample(client, pending, ctx)
    else:
        summary = run_batch(client, pending, ctx)
    print(f"\nDone. ok={summary['ok']} rejected={summary['rejected']}")
    log.info("Done. ok=%s rejected=%s", summary["ok"], summary["rejected"])
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI shim
    sys.exit(main())
