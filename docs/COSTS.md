# NyayaDraft — Generation Costs (W5)

Cost of generating the W1 synthetic training data with the Anthropic API.
All figures are computed from the single source of truth in
[`data-pipeline/config.yaml`](../data-pipeline/config.yaml); the generation
pipeline's cost guard (`generate.estimate_cost`) uses the same arithmetic and
requires an explicit `YES` before any non-trivial spend.

_Last updated: 2026-06-12 · Model: Claude Sonnet 4.6 · FX: ₹88.00 / USD_

## Headline

| Run | Pairs | Batches API | Synchronous API |
|---|---|---|---|
| **Per document** | 1 | **$0.0201** (₹1.77) | $0.0402 (₹3.54) |
| **Pilot** | 330 | **$6.63** (₹584) | $13.27 (₹1,167) |
| **Full run** | 5,250 | **$105.53** (₹9,286) | $211.05 (₹18,572) |

> Use the **Batches API** (the pipeline default for `pilot`/`full`; 50 % cheaper).
> The synchronous column applies only to `--mode sample` and `--retry`, which
> always run sync.

The user-facing round numbers: a **300-pair** pilot is **$6.03 (₹531)** and a
**5,000-pair** full run is **$100.50 (₹8,844)**, both on the Batches API.

## Pricing basis

Claude Sonnet 4.6 list price (≤ 200 K context), from `config.yaml › pricing`:

| | per 1M tokens | Batches API (−50 %) |
|---|---|---|
| Input | $3.00 | $1.50 |
| Output | $15.00 | $7.50 |

Per-request cost = `(input_tokens × $3 + output_tokens × $15) / 1e6`, then ×0.5
for Batches.

## Token assumptions

From `config.yaml › generation` (`est_input_tokens`, `est_output_tokens`):

- **Input ≈ 1,900 tokens/request** — system prompt + filled meta-prompt template
  (structure, statutory requirements, given facts, register).
- **Output ≈ 2,300 tokens/request** — the generated instruction **and** document,
  plus the small block-format markers.

These are averages across all 11 doc types. The per-type estimate below (built
from **observed** document lengths in the sample audit) totals **$103.48** for
the full run — within ~2 % of the flat $105.53 — so the flat estimate is
realistic, not optimistic.

## Per-document cost by type (Batches API)

Output tokens estimated from observed average document length
(`chars / 3.8` + ~1,000 instruction + markers); input held at 1,900.

| Doc type | Count | ~Output tok | $/doc | Subtotal |
|---|---:|---:|---:|---:|
| leave_license_mh | 500 | 4,265 | $0.0348 | $17.42 |
| mou_two_parties | 500 | 3,495 | $0.0291 | $14.53 |
| partnership_deed_1932 † | 500 | 3,431 | $0.0286 | $14.29 |
| consumer_complaint_cpa2019 | 500 | 2,826 | $0.0240 | $12.02 |
| employment_offer_termination | 500 | 2,265 | $0.0198 | $9.92 |
| legal_notice_landlord_tenant | 500 | 1,745 | $0.0159 | $7.97 |
| reply_to_legal_notice † | 500 | 1,589 | $0.0148 | $7.38 |
| legal_notice_money_recovery | 500 | 1,380 | $0.0132 | $6.60 |
| cheque_bounce_138 | 500 | 1,341 | $0.0129 | $6.45 |
| affidavit_general | 500 | 1,123 | $0.0113 | $5.64 |
| out_of_scope | 250 | 289 | $0.0050 | $1.25 |
| **Total** | **5,250** | | | **$103.48** (₹9,106) |

† `partnership_deed_1932` and `reply_to_legal_notice` output sizes are
**estimated** — they have no samples yet (the API usage limit was hit during the
audit; access returns 2026-07-01). Re-measure after sampling them.

## Dataset sizes

From `config.yaml › counts` (asserted by the test suite):

- **Pilot** = `pilot_per_type` (30) × 11 types = **330 pairs**.
- **Full** = `default_per_type` (500) × 10 types + `out_of_scope` (250) =
  **5,250 pairs**.

## Planning caveats

- **Yield / retries.** The cost above is per *request*. Some requests are
  rejected by the statutory gate or fail to parse and must be regenerated to
  reach a target of *accepted* pairs. After the W1 harness fixes (delimited
  output format, calibrated gates) yield is high, but budget a **~5–10 %
  buffer**: a 5,250-accepted-pair target ≈ **$110–116** on Batches.
- **Prompt caching** could cut input cost further (the system prompt and
  template boilerplate repeat across requests); not modelled here, so the
  estimates are conservative on input.
- **`max_tokens` is a cap, not a charge.** It was raised to 8,192 so long deeds
  finish; billing is per *generated* token, so short docs are unaffected.
- **Cost guard.** `generate.py` prints this estimate and blocks on an explicit
  `YES` for any run larger than `sample_max` (10), so no large spend happens
  unattended.

## How to update

Change `config.yaml › pricing` / `generation` / `counts` and recompute; the
numbers here are exactly `generate.estimate_cost(n, config, use_batch=…)`. If
Sonnet pricing or the token estimates change, refresh the headline and per-type
tables from a fresh run of that function.
