export const meta = {
  name: 'nyayadraft-draft-remaining',
  description: 'Draft the genuinely-missing NyayaDraft indices into out/full/raw, ONE agent per doc_type (local Opus inference; consumer_complaint & partnership_deed already at target)',
  phases: [{ title: 'Draft', detail: 'one agent per doc_type; agent self-determines its missing indices from dataset.jsonl' }],
}

// The 11 real doc types. Used to validate args and REJECT the array-shaped-arg
// bug that previously turned Object.entries() keys into "0".."9" and produced
// agents with doc_type "9" / corrupted ${c.doc_type} prompts and empty index lists.
const KNOWN_TYPES = new Set([
  'leave_license_mh', 'legal_notice_money_recovery', 'legal_notice_landlord_tenant',
  'cheque_bounce_138', 'consumer_complaint_cpa2019', 'affidavit_general',
  'employment_offer_termination', 'mou_two_parties', 'partnership_deed_1932',
  'reply_to_legal_notice', 'out_of_scope',
])

// Verbatim per-type gate guidance from the proven nyayadraft-full-1000 workflow.
const CAUTION = {
  partnership_deed_1932: "firm_name is already an 'M/s ...' partnership style - use it verbatim and NEVER append Ltd/Pvt/LLP. The deed must NOT contain 'LLP' or 'Limited Liability Partnership' (forbidden no_llp_confusion). This is the longest type; cite the Indian Partnership Act, 1932. commencement_date may legitimately be future - use verbatim.",
  consumer_complaint_cpa2019: "Longest/most complex (pleading + jurisdiction + prayer). Use 'District Commission', NEVER 'District Forum'; cite the Consumer Protection Act, 2019 (NOT 1986).",
  cheque_bounce_138: "demand_language present (first- or third-person: 'I/my client hereby call upon you to pay' / 'hereby demand'); state the 15-day payment demand AND the 30-day-from-return-memo windows; cite Section 138 of the Negotiable Instruments Act, 1881.",
  legal_notice_money_recovery: "demand_language present (first- or third-person). interest_demanded is required even when no interest rate is given - use 'together with interest at a reasonable rate'. Do not cite Section 138/NI Act or IPC sections.",
  legal_notice_landlord_tenant: "security_deposit (when given) is an integer multiple of monthly_rent - use both verbatim. A dispatch mode (e.g. Registered Post A.D.) and a concrete 15/30-day compliance window are required even if those fields are withheld.",
  reply_to_legal_notice: "rights_reserved must be ACTIVE voice (e.g. 'my client expressly reserves all his/her rights and contentions') - passive phrasing fails. reply_date chains after notice_date and is in the past; use given dates verbatim.",
  leave_license_mh: "security_deposit is an integer multiple of monthly_fee - use both verbatim. start_date may legitimately be future. This is a leave & licence (Maharashtra Rent Control Act, 1999) - avoid lessor/lessee/'monthly rent'/tenancy/lease language; keep the bare-licence / no-tenancy declarations.",
  employment_offer_termination: "Must read as issued on company letterhead (explicit letterhead line, corporate suffix, or CIN block). designation_mention gate is NARROW: use 'in the position of X' / 'in the capacity of X' / 'employed as X' / 'the post of X' - 'as an X' does NOT match. joining_date/last_working_day may be future - use verbatim.",
  mou_two_parties: "Include a binding-clarification (state the MoU is non-binding in intent, with the specific clauses that ARE binding carved out) and a dispute-resolution mechanism (negotiation/arbitration) close to the word 'dispute'.",
  affidavit_general: "Use name_variant_a, name_variant_b and deponent_parent_name EXACTLY as given (they are already consistent: variant_a = the deponent's own name; variant_b = same person, different surname; parent shares the deponent's surname). Number declarations as '1. That ... 2. That ...'. Do NOT cite a section number ('section 199'/'u/s 193') - say 'an offence punishable under law'.",
  out_of_scope: "This is a REFUSAL, NOT a document. Politely decline; state NyayaDraft works only with specific Indian legal document types (scope_statement); recommend consulting a qualified advocate (advocate_recommendation); where nearest_supported is given you may mention that supported type. MUST NOT: predict outcomes, give directive advice ('you should sue'), include a document body, use markdown headings(#)/bold(**), speak in an AI voice, or open with chat preamble. No statutory citations, no disclaimer footer. 250-1100 chars.",
}

const DRAFT_SCHEMA = {
  type: 'object',
  properties: {
    doc_type: { type: 'string' },
    target: { type: 'integer', description: 'per_type target this agent worked toward' },
    already_present: { type: 'integer', description: 'indices that already existed before this agent started' },
    drafted_indices: { type: 'array', items: { type: 'integer' }, description: 'indices this agent computed as missing and attempted' },
    written: { type: 'integer', description: 'count of raw files written AND self-checked OK by check_one.py' },
    missing: { type: 'array', items: { type: 'integer' }, description: 'targeted indices NOT brought to OK' },
    self_check: { type: 'string', description: 'one line: how drafts were verified' },
  },
  required: ['doc_type', 'written'],
}

// ----- Defensive arg parsing: this is the fix for the ${c.doc_type} corruption.
// Accept ONLY a plain object map {doc_type: targetCount}. An array-shaped arg (the
// old failure mode) makes Object.entries() keys numeric ("0".."9"); we now reject
// it loudly instead of spawning agents with doc_type "9".
const rawArg = (args && args.perType) ? args.perType : args
if (!rawArg || typeof rawArg !== 'object' || Array.isArray(rawArg)) {
  throw new Error('args must be an object map {doc_type: targetCount}; received ' +
    (Array.isArray(rawArg) ? 'an array' : typeof rawArg))
}
const targets = {}
for (const [t, v] of Object.entries(rawArg)) {
  if (!KNOWN_TYPES.has(t)) throw new Error(`unknown doc_type key in args: ${JSON.stringify(t)} (array-shaped args bug?)`)
  const target = Number(v)
  if (!Number.isInteger(target) || target <= 0) throw new Error(`target for ${t} must be a positive integer; got ${JSON.stringify(v)}`)
  targets[t] = target
}
const types = Object.keys(targets)
if (types.length === 0) throw new Error('no doc types to draft')
log(`Drafting toward per_type targets for ${types.length} types: ${types.map((t) => `${t}=${targets[t]}`).join(', ')}`)

function prompt(dt, target) {
  return [
`You are drafting synthetic Indian legal documents for the NyayaDraft fine-tuning dataset.`,
`TYPE: ${dt}. PER_TYPE TARGET: ${target} total documents (indices 0 .. ${target - 1}).`,
``,
`WORKING DIR: C:\\Users\\aarti\\Documents\\nyayadraft (absolute base; run shell commands from here and use the relative paths below).`,
``,
`STEP 0 - DETERMINE YOUR MISSING INDICES (do this first):`,
`Run this exact command and read its output - it prints the sorted list of indices for "${dt}" that you still need to draft (target indices NOT already in out/full/dataset.jsonl and without an already-present raw file):`,
`  python -c "import json,glob,os; ids={json.loads(l)['id'] for l in open('out/full/dataset.jsonl',encoding='utf-8') if l.strip()}; have={int(os.path.basename(p)[len('${dt}')+1:-4]) for p in glob.glob('out/full/raw/${dt}-*.txt')} | {int(i.rsplit('-',1)[1]) for i in ids if i.startswith('${dt}-')}; miss=[n for n in range(${target}) if n not in have]; print('ALREADY_PRESENT', len(have)); print('MISSING_COUNT', len(miss)); print('MISSING', miss)"`,
`Draft ONLY the indices in that MISSING list. If MISSING is empty, you are done: return written=0 with an empty missing list.`,
``,
`READ FIRST (once, then reuse for all your drafts):`,
`1. Variations: out/full/vars/${dt}.json - a JSON array; the element whose "index" field equals N is the variation for index N. Each has: index, register, scenario_summary, given_facts, withheld_fields (name+placeholder), nearest_supported.`,
`2. Rules: legal_rules/rules/${dt}.json - required_patterns (your DOCUMENT must match EVERY regex), forbidden_patterns (must match NONE), min_chars/max_chars, require_disclaimer, is_document.`,
`3. Reference passing examples (already validated - match their structure, depth, legal phrasing): out/full/raw/${dt}-00000.txt, -00001.txt, -00002.txt.`,
``,
`OUTPUT: for each missing index N, write a file out/full/raw/${dt}-NNNNN.txt where NNNNN is N zero-padded to 5 digits (e.g. 7 -> 00007, 113 -> 00113), in EXACTLY this format (three bracket delimiters, each on its own line):`,
`[[[INSTRUCTION]]]`,
`<user request>`,
`[[[DOCUMENT]]]`,
`<full drafted document>`,
`[[[END]]]`,
``,
`CONTRACT:`,
`- INSTRUCTION: a realistic user request in the variation's register (casual = short/informal, semi_formal = moderate, detailed = thorough); weave in the given_facts a real user would supply; NEVER mention any withheld_fields.`,
`- DOCUMENT: use given_facts EXACTLY (names/amounts/addresses verbatim; convert ISO dates to DD.MM.YYYY); render each withheld field as its exact placeholder; use [VERIFY: ...] for genuinely unknowable specifics; if require_disclaimer is true, end with the exact disclaimer footer used in the references; satisfy EVERY required_pattern; avoid every forbidden_pattern; keep length within [min_chars, max_chars]; never invent a future date.`,
`- DIVERSITY: every draft must differ genuinely in wording, clause order, and structure (a downstream dedup pass drops instructions with >=92 token-set similarity). Vary openings, phrasing, paragraphing.`,
``,
`TYPE-SPECIFIC: ${CAUTION[dt]}`,
``,
`SELF-CHECK (MANDATORY, per file): after writing each file, run:  python out/full/check_one.py out/full/raw/${dt}-NNNNN.txt  and read its output. It prints OK or REJECT with the failing gate ids. If REJECT, fix the DOCUMENT/INSTRUCTION and re-run ONCE; if it still fails, leave the best version and record that index in "missing". Do NOT count a file as written until check_one prints OK for it.`,
``,
`This can be a LARGE batch (up to ~90 documents). Work through the MISSING indices strictly in ascending order, writing and self-checking each file before moving to the next, so partial progress is always preserved on disk. Do not stop early.`,
``,
`Return the structured manifest: doc_type="${dt}", target=${target}, already_present (from STEP 0), drafted_indices (the MISSING list you worked on), written (count of files that pass check_one OK), missing (indices you could not bring to OK), self_check (one line on how you verified).`,
  ].join('\n')
}

phase('Draft')
// No model override: agents inherit the session main-loop model (Opus 4.8, 1M
// context) - correct for "Opus 4.8 only", and the 1M window lets one agent load
// context once and draft its whole remaining batch in sequence.
const results = await parallel(types.map((dt) => () =>
  agent(prompt(dt, targets[dt]), {
    label: `${dt} -> ${targets[dt]}`,
    phase: 'Draft',
    schema: DRAFT_SCHEMA,
    agentType: 'general-purpose',
  })
))

const ok = results.filter(Boolean)
const totalWritten = ok.reduce((a, r) => a + (r.written || 0), 0)
const missing = ok.flatMap((r) => (r.missing || []).map((i) => `${r.doc_type}-${i}`))
const deadAgents = results.length - ok.length
log(`Drafting done: ${ok.length}/${types.length} agents returned, ${totalWritten} files written OK, ${missing.length} indices reported missing, ${deadAgents} dead agents`)
return {
  types: types.length,
  agents_ok: ok.length,
  dead_agents: deadAgents,
  total_written: totalWritten,
  missing,
  per_agent: ok.map((r) => ({ doc_type: r.doc_type, written: r.written, already_present: r.already_present, missing: (r.missing || []).length })),
}
