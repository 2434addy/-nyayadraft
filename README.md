# NyayaDraft

NyayaDraft fine-tunes a small open-weight model (Qwen 2.5 7B Instruct primary, Llama 3.1 8B fallback; QLoRA via Unsloth) to draft 10 common Indian legal document types. Vanilla LLMs are unreliable for Indian legal drafting: they hallucinate statutory citations and silently invent names, amounts, and dates. NyayaDraft trains specifically for the opposite behavior — missing facts become explicit ALL-CAPS bracketed placeholders, uncertain citations become `[VERIFY: Act/section]` markers for lawyer review, and every draft carries a fixed not-legal-advice disclaimer. The end goal is a forms-only web app where users fill in known facts and receive a structured draft for review.

> **Status:** Work in progress — Workstream 1 (data pipeline) under construction. No trained model has been released yet.

## Supported document types

| # | Doc type id | Document |
|---|-------------|----------|
| 1 | `leave_license_mh` | Leave & License Agreement (Maharashtra) |
| 2 | `legal_notice_money_recovery` | Legal notice for recovery of money |
| 3 | `legal_notice_landlord_tenant` | Landlord ↔ tenant legal notice |
| 4 | `cheque_bounce_138` | Cheque bounce demand notice (Section 138, Negotiable Instruments Act, 1881) |
| 5 | `consumer_complaint_cpa2019` | Consumer complaint (Consumer Protection Act, 2019) |
| 6 | `affidavit_general` | General affidavit |
| 7 | `employment_offer_termination` | Employment offer letter + termination letter |
| 8 | `mou_two_parties` | Memorandum of Understanding (two parties) |
| 9 | `partnership_deed_1932` | Partnership deed (Indian Partnership Act, 1932) |
| 10 | `reply_to_legal_notice` | Reply to a legal notice |
| — | `out_of_scope` | Refusal training category: legal-advice requests, unsupported document types, and outcome predictions are politely declined |

## Architecture: five workstreams

| Workstream | Directory | What it does |
|------------|-----------|--------------|
| W1 — Data pipeline | `data-pipeline/` | Generates synthetic instruction→document training pairs via the Anthropic API, gated by statutory regex checks |
| W3 — Evals | `evals/` (planned) | LLM-as-judge scoring plus deterministic statutory checks |
| W2 — Training | `training/` (planned) | Unsloth QLoRA fine-tuning on a rented 24 GB GPU |
| W4 — App | `app/` (planned) | FastAPI + vLLM backend, Next.js forms-only UI |
| W5 — Cost docs | `docs/` (planned) | Cost tracking and documentation in ₹ |

Build order: **W1 → W3 → W2 → W4**, with W5 maintained throughout. Evals are built before training so every checkpoint can be measured from day one.

## Repository layout

```
.
├── LICENSE
├── README.md
├── .env.example               # required env vars (Anthropic API key, optional W&B)
├── .gitignore
├── data-pipeline/             # W1
│   ├── config.yaml            # central pipeline config: model, counts, pricing, splits, dedup
│   ├── system_prompt.txt      # the system prompt every training pair is built around
│   ├── meta_prompts/          # per-doc-type generation specs
│   │   ├── base.txt           # shared meta-prompt template for documents
│   │   ├── base_out_of_scope.txt  # shared template for refusal pairs
│   │   └── <doc_type>.json    # structure, statutory requirements, field policies per type
│   └── seeds/                 # variation-engine seed data (names, cities, scenarios)
├── legal_rules/               # JSON-driven statutory/structural rule engine
│   ├── checker.py             # compiles rules/<doc_type>.json and checks generated documents
│   └── rules/                 # per-doc-type required/forbidden regex patterns, length bounds
├── evals/      (planned)      # W3
├── training/   (planned)      # W2
├── app/        (planned)      # W4
└── docs/       (planned)      # W5, incl. CLAIM_AUDIT.md
```

Meta-prompt specs and rule files currently exist for 2 of the 11 categories (`cheque_bounce_138`, `out_of_scope`); the remaining 9 are in progress.

## How the data pipeline works

1. **Meta-prompt spec per doc type** (`data-pipeline/meta_prompts/<doc_type>.json`): structural summary, statutory requirements, and a field list where each field is `always` given, `withholdable`, or `optional`.
2. **Variation engine**: seed names/cities/scenarios are combined with a register mix (casual / semi-formal / detailed user instructions). Withholdable fields are dropped from the user request with a per-register probability, so the model learns to emit bracketed placeholders instead of inventing facts.
3. **Statutory regex gates** (`legal_rules/`): every generated document must match the required patterns for its type (e.g. for the Sec 138 notice: the 15-day demand, the 30-day notice window, the cheque particulars), must not match forbidden patterns, and must end with the exact disclaimer footer. Failures are rejected.
4. **Generation via the Anthropic Batches API** (50% cheaper than sync). Any run larger than `sample_max` (10 requests) hits a hard cost guard: the estimated cost in ₹ is printed and the run aborts unless the operator types `YES`.
5. **Scenario-held-out splits**: 90/5/5 train/val/test, split **by scenario** so no scenario leaks across splits. Near-duplicate instructions are removed by fuzzy matching.
6. **Lawyer-review gates**: a 5-sample gate first, then a pilot run (30 pairs per type) reviewed in full by a lawyer, and only then the full run — from which a random 5% is exported to CSV for lawyer review.

## Safety and legal-accuracy rules

These are non-negotiable and enforced in the system prompt and the rule engine (`data-pipeline/system_prompt.txt` is the authoritative wording):

1. **No invented facts.** The model never invents names, addresses, amounts, dates, or ID/cheque numbers. Every missing fact becomes an ALL-CAPS bracketed placeholder, e.g. `[FULL NAME OF LANDLORD]`, `[CHEQUE NUMBER]`, `[AMOUNT IN ₹]`.
2. **No invented citations.** An Act, section, or rule is cited only when correct and applicable. Where a citation is customary but uncertain, the model writes `[VERIFY: Act/section]` for lawyer review.
3. **Mandatory disclaimer footer.** Every generated document ends with the exact line: *"This is an AI-generated draft for review by the parties and is not legal advice."* The rule engine rejects documents missing it (and rejects refusal texts that carry it).
4. **Claim audit.** Every statutory claim encoded in the rule files is tagged `CONFIDENT` or `VERIFY` (`legal_basis` field); the `VERIFY` items are collected in `docs/CLAIM_AUDIT.md` (planned) for lawyer review.

## Disclaimer

**This software, the datasets it produces, and any model trained with it generate AI drafts — not legal advice.** Outputs are first drafts intended for review by the parties and, where appropriate, a qualified advocate. Nothing in this repository creates an advocate–client relationship, and it is not a substitute for consulting a qualified advocate licensed to practice in India. Use at your own risk.

## License

[MIT](LICENSE) — Copyright (c) 2026 Aditya Pandey.
