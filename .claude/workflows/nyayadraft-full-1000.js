export const meta = {
  name: 'nyayadraft-full-1000',
  description: 'Draft the remaining ~890 NyayaDraft legal docs to complete the 1,000-doc distribution (local agent inference, validated centrally after)',
  phases: [{ title: 'Draft', detail: '63 chunks of ~15 docs each, drafted into out/full/raw' }],
}

const CHUNK = 15
const PER_TYPE = {
  partnership_deed_1932: 120, consumer_complaint_cpa2019: 120,
  cheque_bounce_138: 100, legal_notice_money_recovery: 100, legal_notice_landlord_tenant: 100,
  reply_to_legal_notice: 95, leave_license_mh: 90, employment_offer_termination: 80,
  mou_two_parties: 75, affidavit_general: 70, out_of_scope: 50,
}

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
    start: { type: 'integer' },
    end: { type: 'integer' },
    written: { type: 'integer', description: 'count of raw files successfully written' },
    missing: { type: 'array', items: { type: 'integer' }, description: 'indices NOT completed' },
    self_check: { type: 'string', description: 'one line: how drafts were verified' },
  },
  required: ['doc_type', 'start', 'end', 'written'],
}

const chunks = []
for (const [t, total] of Object.entries(PER_TYPE)) {
  for (let s = 10; s < total; s += CHUNK) {
    chunks.push({ doc_type: t, start: s, end: Math.min(s + CHUNK, total) })
  }
}
const totalNew = chunks.reduce((a, c) => a + (c.end - c.start), 0)
log(`Drafting ${chunks.length} chunks covering ${totalNew} new docs (indices 10..N-1 per type)`)

function prompt(c) {
  const n = c.end - c.start
  return [
`You are drafting synthetic Indian legal documents for the NyayaDraft fine-tuning dataset.`,
`TYPE: ${c.doc_type}. Draft documents for indices ${c.start} through ${c.end - 1} inclusive (${n} documents).`,
``,
`WORKING DIR: C:\\Users\\aarti\\Documents\\nyayadraft (absolute base for all paths).`,
``,
`READ FIRST:`,
`1. Variations: out/full/vars/${c.doc_type}.json - a JSON array; the element at position i is the variation for index i. Use ONLY positions ${c.start}..${c.end - 1}. Each has: index, register, scenario_summary, given_facts, withheld_fields (name+placeholder), nearest_supported.`,
`2. Rules: legal_rules/rules/${c.doc_type}.json - required_patterns (your DOCUMENT must match EVERY regex), forbidden_patterns (must match NONE), min_chars/max_chars, require_disclaimer, is_document.`,
`3. Reference passing examples (already validated - match their structure, depth, legal phrasing): out/full/raw/${c.doc_type}-00000.txt, -00001.txt, -00002.txt.`,
``,
`OUTPUT: for each index N in ${c.start}..${c.end - 1}, write a file out/full/raw/${c.doc_type}-NNNNN.txt where NNNNN is N zero-padded to 5 digits (e.g. 7 -> 00007, 113 -> 00113), in EXACTLY this format:`,
`[[[INSTRUCTION]]]`,
`<user request>`,
`[[[DOCUMENT]]]`,
`<full drafted document>`,
`[[[END]]]`,
``,
`CONTRACT:`,
`- INSTRUCTION: a realistic user request in the variation's register (casual = short/informal, semi_formal = moderate, detailed = thorough); weave in the given_facts a real user would supply; NEVER mention any withheld_fields.`,
`- DOCUMENT: use given_facts EXACTLY (names/amounts/addresses verbatim; convert ISO dates to DD.MM.YYYY); render each withheld field as its exact placeholder; use [VERIFY: ...] for genuinely unknowable specifics; if require_disclaimer is true, end with the exact disclaimer footer used in the references; satisfy EVERY required_pattern; avoid every forbidden_pattern; keep length within [min_chars, max_chars]; never invent a future date.`,
`- DIVERSITY: every one of your ${n} drafts must differ genuinely in wording, clause order, and structure (a downstream dedup pass drops instructions with >=92 similarity). Vary openings, phrasing, paragraphing.`,
``,
`TYPE-SPECIFIC: ${CAUTION[c.doc_type]}`,
``,
`SELF-CHECK: after writing each file, if you can run a shell command, run:  python out/full/check_one.py out/full/raw/${c.doc_type}-NNNNN.txt  and fix any REJECT (read the failing gate id) then re-run until it prints OK. If shell is unavailable, instead use Grep to confirm your DOCUMENT text matches each required_pattern regex and matches NO forbidden_pattern regex from the rules file, and fix any mismatch.`,
``,
`Return the structured manifest: doc_type, start, end, written (count of files written), missing (indices you could not complete), self_check (one line on how you verified). Do not finish until every index ${c.start}..${c.end - 1} has a file.`,
  ].join('\n')
}

phase('Draft')
const results = await parallel(chunks.map((c) => () =>
  agent(prompt(c), {
    label: `${c.doc_type}:${c.start}-${c.end - 1}`,
    phase: 'Draft',
    schema: DRAFT_SCHEMA,
    agentType: 'general-purpose',
  })
))

const ok = results.filter(Boolean)
const totalWritten = ok.reduce((a, r) => a + (r.written || 0), 0)
const missing = ok.flatMap((r) => (r.missing || []).map((i) => `${r.doc_type}-${i}`))
const deadAgents = results.length - ok.length
log(`Drafting done: ${ok.length}/${chunks.length} chunk-agents returned, ${totalWritten}/${totalNew} files written, ${missing.length} indices reported missing, ${deadAgents} dead agents`)
return { chunks: chunks.length, agents_ok: ok.length, dead_agents: deadAgents, total_written: totalWritten, target: totalNew, missing }
