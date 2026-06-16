"""Deterministic, seeded variation sampling for NyayaDraft training pairs.

A *variation* is the fully-resolved set of choices that drives one generated
training example: which scenario, which instruction register, which facts are
given to the user vs. withheld as placeholders, and the synthesised values for
the given facts.

Determinism contract
---------------------
``build_variation`` is a pure function of its inputs. The same
``(config["seed"], index)`` pair always yields the same variation, and the
inputs are never mutated. Randomness is confined to a per-index
``random.Random`` instance so that callers can reproduce any example by index.

The register may be sampled from the configured mix or pinned by the caller.
To keep the field-level draws at a stable position in the RNG stream, the
register is *always* drawn from the RNG first; an explicit ``register``
argument then overrides the drawn value without disturbing later draws.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from typing import Any, Mapping, Protocol, Sequence


class _Synthesiser(Protocol):
    """Callable contract for every ``_synth_*`` value synthesizer.

    ``given`` is the partially-built map of facts already synthesised for this
    variation (in field-declaration order). Most synthesizers ignore it; date
    fields use it to chain off an earlier field's value (see ``_synth_date``).
    """

    def __call__(
        self,
        field: Mapping[str, Any],
        params: Mapping[str, Any],
        seeds: Mapping[str, Any],
        rng: random.Random,
        today: dt.date,
        given: Mapping[str, Any],
    ) -> Any: ...

# Field policies governing whether a field's value is shown to the user.
POLICY_ALWAYS = "always"
POLICY_WITHHOLDABLE = "withholdable"
POLICY_OPTIONAL = "optional"
VALID_POLICIES = frozenset({POLICY_ALWAYS, POLICY_WITHHOLDABLE, POLICY_OPTIONAL})

# Supported synthesis kinds. Unknown kinds are rejected so that meta-prompt
# specs cannot silently produce empty or invalid facts.
VALID_KINDS = frozenset(
    {
        "person_name",
        "company_name",
        "partnership_firm_name",
        "city",
        "address",
        "inr_amount",
        "duration_months",
        "date",
        "choice",
        "profession",
        "bank_name",
        "cheque_number",
        "id_number",
        "number",
        "percentage",
    }
)

# Probability that an ``optional`` field is volunteered by the user.
OPTIONAL_GIVEN_PROBABILITY = 0.5


class VariationError(ValueError):
    """Raised when a spec field is structurally invalid."""


def build_variation(
    spec: Mapping[str, Any],
    scenarios: Sequence[Mapping[str, Any]],
    seeds: Mapping[str, Any],
    config: Mapping[str, Any],
    index: int,
    *,
    today: dt.date,
    register: str | None = None,
) -> dict[str, Any]:
    """Build one deterministic variation for ``index`` without mutating inputs.

    Args:
        spec: A meta-prompt document-type spec (``doc_type``, ``fields`` ...).
        scenarios: Scenarios for this doc type; one is chosen by ``index``.
        seeds: Loaded seed pools (``names``, ``cities`` ...).
        config: Pipeline config (``seed``, ``registers``, ``withhold_probability``).
        index: Stable example index; drives both scenario and RNG state.
        today: Reference date for relative date synthesis.
        register: Pin the instruction register; otherwise sampled from config.

    Returns:
        A new variation dict. Inputs are never mutated.

    Raises:
        VariationError: If a field declares an unknown policy or kind.
    """
    rng = random.Random(_derive_seed(int(config["seed"]), int(index)))

    drawn_register = _choose_register(rng, config["registers"])
    chosen_register = register if register is not None else drawn_register

    scenario = _choose_scenario(rng, scenarios, index)
    params: Mapping[str, Any] = scenario.get("params") or {}

    no_withhold = bool(spec.get("no_withhold"))
    given_facts, withheld_fields = _resolve_fields(
        spec, params, seeds, config, rng, chosen_register, today, no_withhold
    )

    variation: dict[str, Any] = {
        "doc_type": spec["doc_type"],
        "index": int(index),
        "scenario_id": scenario.get("id"),
        "scenario_summary": scenario.get("summary"),
        "register": chosen_register,
        "given_facts": given_facts,
        "withheld_fields": withheld_fields,
        "nearest_supported": scenario.get("nearest_supported"),
    }
    return variation


def _derive_seed(seed: int, index: int) -> int:
    """Combine a base seed and example index into one stable integer seed.

    Mixing avoids collisions between adjacent indices while keeping the result
    a plain ``int`` (the only portable seed type across Python versions).
    """
    return (seed * 1_000_003) ^ (index * 0x9E3779B1)


def _choose_register(rng: random.Random, registers: Mapping[str, float]) -> str:
    """Pick a register name from the configured weighted mix."""
    names = list(registers.keys())
    weights = [float(registers[name]) for name in names]
    return rng.choices(names, weights=weights, k=1)[0]


def _choose_scenario(
    rng: random.Random, scenarios: Sequence[Mapping[str, Any]], index: int
) -> Mapping[str, Any]:
    """Select a scenario deterministically; empty lists yield a blank scenario."""
    if not scenarios:
        return {}
    return scenarios[index % len(scenarios)]


def _resolve_fields(
    spec: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    config: Mapping[str, Any],
    rng: random.Random,
    register: str,
    today: dt.date,
    no_withhold: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Decide visibility and synthesise values for every active field."""
    fields = list(spec.get("fields") or [])
    active = [f for f in fields if _condition_met(f.get("when"), params)]

    decisions = _decide_visibility(active, config, rng, register, no_withhold)
    decisions = _apply_implies_given(active, decisions)

    given_facts: dict[str, Any] = {}
    withheld_fields: list[dict[str, str]] = []
    for field in active:
        name = field["name"]
        if decisions[name] == "given":
            # Pass the facts decided so far so a ``relative_to`` date field can
            # chain off an earlier field (declaration order guarantees the base
            # is already present when it was itself given).
            given_facts[name] = _synthesise_value(
                field, params, seeds, rng, today, given_facts
            )
        elif decisions[name] == "withheld":
            withheld_fields.append(
                {"name": name, "placeholder": field["placeholder"]}
            )
    return given_facts, withheld_fields


def _decide_visibility(
    fields: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    rng: random.Random,
    register: str,
    no_withhold: bool,
) -> dict[str, str]:
    """Map each field name to 'given', 'withheld', or 'absent'."""
    withhold_prob = float(config["withhold_probability"][register])
    decisions: dict[str, str] = {}
    for field in fields:
        policy = field.get("given_policy")
        if policy not in VALID_POLICIES:
            raise VariationError(
                f"field {field.get('name')!r} has unknown given_policy "
                f"{policy!r}"
            )
        decisions[field["name"]] = _decide_one(
            policy, rng, withhold_prob, no_withhold
        )
    return decisions


def _decide_one(
    policy: str, rng: random.Random, withhold_prob: float, no_withhold: bool
) -> str:
    """Decide a single field's visibility from its policy."""
    if policy == POLICY_ALWAYS:
        return "given"
    if policy == POLICY_WITHHOLDABLE:
        if not no_withhold and rng.random() < withhold_prob:
            return "withheld"
        return "given"
    # optional: volunteered or simply absent, never a placeholder.
    return "given" if rng.random() < OPTIONAL_GIVEN_PROBABILITY else "absent"


def _apply_implies_given(
    fields: Sequence[Mapping[str, Any]], decisions: Mapping[str, str]
) -> dict[str, str]:
    """Return a new decisions map with implied fields forced to 'given'.

    The input ``decisions`` mapping is never mutated; a fresh dict is returned
    so callers own an independent, immutable-by-convention result.
    """
    updated = dict(decisions)
    by_name = {f["name"]: f for f in fields}
    for field in fields:
        if updated.get(field["name"]) != "given":
            continue
        for implied in field.get("implies_given") or []:
            if implied in by_name:
                updated[implied] = "given"
    return updated


def _condition_met(when: Mapping[str, Any] | None, params: Mapping[str, Any]) -> bool:
    """Return True when every key in ``when`` matches the scenario params."""
    if not when:
        return True
    return all(params.get(key) == value for key, value in when.items())


def _synthesise_value(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> Any:
    """Synthesise a deterministic value for a given field by its kind."""
    kind = field.get("kind")
    if kind not in VALID_KINDS:
        raise VariationError(
            f"field {field.get('name')!r} has unknown kind {kind!r}"
        )
    synthesiser = _SYNTHESISERS[kind]
    # Always run the synthesiser so its RNG draw happens on every path; the
    # scenario pin (if any) then overrides the drawn value. Keeping the draw
    # leaves the seeded stream — and every later field's value — unchanged.
    value = synthesiser(field, params, seeds, rng, today, given)
    return _apply_field_pin(field, params, value)


def _apply_field_pin(
    field: Mapping[str, Any], params: Mapping[str, Any], value: Any
) -> Any:
    """Override ``value`` when the scenario pins this field to a fixed value.

    Some facts are determined by the scenario rather than drawn independently:
    the consumer product complained of, a firm's line of business, the ground
    for a termination. A scenario expresses this by carrying a param keyed by
    the field's own name (e.g. ``"product_service": "washing machine"``). The
    pin replaces the drawn value so the given fact agrees with the scenario
    summary that is shown to the model alongside it. For a ``choice`` field the
    pin must be one of the declared choices, so a typo in the scenario bank
    fails fast at build time rather than silently producing an off-list value.
    """
    name = field.get("name")
    if name not in params:
        return value
    pinned = params[name]
    if field.get("kind") == "choice":
        choices = field.get("choices") or []
        if choices and pinned not in choices:
            raise VariationError(
                f"scenario pins field {name!r} to {pinned!r}, which is not among "
                f"its declared choices {list(choices)}"
            )
    return pinned


def _names(seeds: Mapping[str, Any]) -> Mapping[str, Any]:
    return seeds.get("names") or {}


def _cities(seeds: Mapping[str, Any]) -> Mapping[str, Any]:
    return seeds.get("cities") or {}


def _synth_person_name(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    names = _names(seeds)
    pool = list(names.get("male_first", [])) + list(names.get("female_first", []))
    surnames = list(names.get("surnames_maharashtra", [])) + list(
        names.get("surnames_other", [])
    )
    first = rng.choice(pool) if pool else "Aarti"
    last = rng.choice(surnames) if surnames else "Deshmukh"
    return f"{first} {last}"


def _synth_company_name(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    names = _names(seeds)
    surnames = list(names.get("surnames_maharashtra", [])) + list(
        names.get("surnames_other", [])
    )
    suffixes = list(names.get("company_suffixes", []))
    stem = rng.choice(surnames) if surnames else "Patil"
    suffix = rng.choice(suffixes) if suffixes else "Enterprises"
    return f"{stem} {suffix}"


def _synth_partnership_firm_name(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    """Synthesise an unincorporated partnership firm name (e.g. 'M/s Patil & Co.').

    An Indian Partnership Act, 1932 firm has no separate legal personality, so it
    is never styled 'Pvt Ltd', 'Limited' or 'LLP'. We draw a surname stem and a
    partnership-appropriate suffix (``& Co.``, ``Enterprises``, ``Traders`` ...),
    all of which deliberately exclude every entity marker. The ``M/s`` honorific
    is the conventional prefix for a firm name in Indian deeds.
    """
    names = _names(seeds)
    surnames = list(names.get("surnames_maharashtra", [])) + list(
        names.get("surnames_other", [])
    )
    suffixes = list(names.get("partnership_suffixes", [])) or [
        "& Co.",
        "Enterprises",
        "Traders",
    ]
    stem = rng.choice(surnames) if surnames else "Patil"
    suffix = rng.choice(suffixes)
    return f"M/s {stem} {suffix}"


def _synth_city(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    return _pick_city(seeds, rng)["name"]


def _pick_city(seeds: Mapping[str, Any], rng: random.Random) -> Mapping[str, Any]:
    cities = list(_cities(seeds).get("cities", []))
    if not cities:
        return {"name": "Mumbai", "pincode_prefix": "400"}
    weights = [float(c.get("weight", 1)) for c in cities]
    return rng.choices(cities, weights=weights, k=1)[0]


def _synth_address(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    cities = _cities(seeds)
    buildings = list(cities.get("buildings", []))
    roads = list(cities.get("roads", []))
    localities = list(cities.get("localities", []))
    city = _pick_city(seeds, rng)
    flat = rng.randint(1, 40)
    building = rng.choice(buildings) if buildings else "Shree Ganesh Apartments"
    road = rng.choice(roads) if roads else "M.G. Road"
    locality = rng.choice(localities) if localities else "Andheri West"
    prefix = str(city.get("pincode_prefix", "400"))
    pincode = f"{prefix}{rng.randint(1, 99):02d}"
    return (
        f"Flat No. {flat}, {building}, {road}, {locality}, "
        f"{city['name']} {pincode}"
    )


def _amount_range(
    field: Mapping[str, Any], params: Mapping[str, Any]
) -> tuple[int, int]:
    """Scenario ``amount_range_inr`` overrides the field's own range."""
    rng_bounds = params.get("amount_range_inr") or field.get("range") or [10000, 100000]
    return int(rng_bounds[0]), int(rng_bounds[1])


def _synth_inr_amount(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> int:
    low, high = _amount_range(field, params)
    step = 500 if high - low >= 500 else 1
    raw = rng.randint(low, high)
    rounded = (raw // step) * step
    return max(low, min(rounded, high))


def _synth_duration_months(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> int:
    choices = field.get("choices")
    if choices:
        return int(rng.choice(list(choices)))
    low, high = (field.get("range") or [11, 60])[:2]
    return rng.randint(int(low), int(high))


def _synth_date(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    """Synthesise an ISO date, anchored on ``today`` or chained off another field.

    A field with ``anchor_days_range`` is offset from ``today``. A field with
    ``relative_to`` + ``offset_days_range`` is offset from that base field's
    already-synthesised date, keeping chained dates (cheque -> presentation ->
    return memo) correctly ordered and inside their legal windows. If the base
    field was withheld (so it is absent from ``given``), it falls back to a
    ``today`` anchor. Exactly one RNG draw happens on every path, so the seeded
    stream — and thus determinism for later fields — is unaffected.
    """
    relative_to = field.get("relative_to")
    offset = field.get("offset_days_range")
    base = today
    span = field.get("anchor_days_range") or offset or [10, 60]
    if relative_to and offset is not None:
        base_value = given.get(relative_to)
        if isinstance(base_value, str):
            try:
                base = dt.date.fromisoformat(base_value)
                span = offset
            except ValueError:
                base = today  # base field wasn't a date; keep the today anchor
    low, high = int(span[0]), int(span[1])
    delta = rng.randint(min(low, high), max(low, high))
    return (base + dt.timedelta(days=delta)).isoformat()


def _synth_choice(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    choices = list(field.get("choices") or [])
    return rng.choice(choices) if choices else ""


def _synth_profession(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    professions = list(_names(seeds).get("professions", []))
    return rng.choice(professions) if professions else "shop owner"


def _synth_bank_name(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    banks = list(_names(seeds).get("banks", []))
    bank = rng.choice(banks) if banks else "State Bank of India"
    branch = _pick_city(seeds, rng)["name"]
    return f"{bank}, {branch} Branch"


def _synth_cheque_number(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    return f"{rng.randint(100000, 999999)}"


def _synth_id_number(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> str:
    # PAN-style identifier; synthetic, never a real document number.
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    head = "".join(rng.choice(letters) for _ in range(5))
    digits = f"{rng.randint(0, 9999):04d}"
    tail = rng.choice(letters)
    return f"{head}{digits}{tail}"


def _synth_number(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> int:
    low, high = (field.get("range") or [1, 100])[:2]
    return rng.randint(int(low), int(high))


def _synth_percentage(
    field: Mapping[str, Any],
    params: Mapping[str, Any],
    seeds: Mapping[str, Any],
    rng: random.Random,
    today: dt.date,
    given: Mapping[str, Any],
) -> int:
    low, high = (field.get("range") or [1, 100])[:2]
    return rng.randint(int(low), int(high))


_SYNTHESISERS: dict[str, _Synthesiser] = {
    "person_name": _synth_person_name,
    "company_name": _synth_company_name,
    "partnership_firm_name": _synth_partnership_firm_name,
    "city": _synth_city,
    "address": _synth_address,
    "inr_amount": _synth_inr_amount,
    "duration_months": _synth_duration_months,
    "date": _synth_date,
    "choice": _synth_choice,
    "profession": _synth_profession,
    "bank_name": _synth_bank_name,
    "cheque_number": _synth_cheque_number,
    "id_number": _synth_id_number,
    "number": _synth_number,
    "percentage": _synth_percentage,
}


# --------------------------------------------------------------------------- #
# Dump CLI — inspect deterministic variations without running generation.
# --------------------------------------------------------------------------- #
def _force_utf8_stdio() -> None:
    """Make stdout/stderr encode UTF-8 so the dump can print ₹ and other non-ASCII.

    On Windows the console defaults to a legacy code page (cp1252) that cannot
    encode characters like ₹ (U+20B9). A dumped variation whose withheld fields
    carry a ``[... ₹]`` placeholder would then raise UnicodeEncodeError on
    ``print``. Reconfiguring the streams to UTF-8 in-process is the fix (no
    PYTHONIOENCODING env var required); this mirrors generate.py's CLI. Streams
    that cannot be reconfigured (already detached, or replaced by a plain object
    in tests) are left untouched.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass  # best-effort: nothing safe to do if reconfigure refuses


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dump deterministic NyayaDraft variations as UTF-8 JSON."
    )
    parser.add_argument(
        "--types",
        nargs="*",
        default=None,
        help="doc types to dump (default: every configured type)",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=3,
        help="variations to emit per doc type (default: 3)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: dump ``count`` deterministic variations per doc type as JSON.

    Mirrors generate.py's UTF-8 stdio guard so ₹ placeholders print on Windows.
    The output is keyed by doc type; each value is the list of variations.
    """
    _force_utf8_stdio()
    # Lazy import keeps variation.py importable as a pure library (no config I/O
    # at import time) and avoids a hard dependency for callers that only need
    # build_variation.
    import pipeline_config

    args = _build_arg_parser().parse_args(argv)
    config = pipeline_config.load_config()
    specs = pipeline_config.load_specs()
    scenarios = pipeline_config.load_scenarios()
    seeds = pipeline_config.load_seeds()
    today = dt.date.today()

    doc_types = list(args.types) if args.types else list(config["doc_types"])
    unknown = [doc_type for doc_type in doc_types if doc_type not in specs]
    if unknown:
        raise SystemExit(f"unknown doc_type(s): {', '.join(unknown)}")

    count = max(0, int(args.count))
    dump = {
        doc_type: [
            build_variation(
                specs[doc_type],
                scenarios.get(doc_type, []),
                seeds,
                config,
                index,
                today=today,
            )
            for index in range(count)
        ]
        for doc_type in doc_types
    }
    print(json.dumps(dump, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI shim
    raise SystemExit(main())
