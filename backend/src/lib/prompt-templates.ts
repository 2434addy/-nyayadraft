/**
 * Server-side prompt builder for the NyayaDraft model.
 *
 * Each entry maps a document type to an instruction prompt. The fine-tuned
 * model was trained to draft Indian legal documents from such instructions.
 */

type Details = Record<string, string>;

// Lockstep accessor used at ~40 call sites below: every placeholder must be
// coerced to a trimmed string with the same empty-value fallback.
function field(details: Details, key: string): string {
  const value = details[key];
  return typeof value === "string" ? value.trim() : "";
}

// Appended to drafting instructions to suppress unfilled bracketed
// placeholders: blank signature/witness lines are rendered as underscores.
const NO_PLACEHOLDERS =
  "Do not leave any bracketed placeholder anywhere in the output. Render signature, witness and attestation lines as blank underscore lines (e.g. \"____________________\") followed by the printed name where known, never as a bracketed field.";

type Template = (d: Details) => string;

const TEMPLATES: Record<string, Template> = {
  affidavit_general: (d) =>
    `Draft a general affidavit under Indian law.\n` +
    `Deponent: ${field(d, "name")}, ${field(d, "parentage")}\n` +
    `Age: ${field(d, "age")} years; Occupation: ${field(d, "occupation")}\n` +
    `Residential address: ${field(d, "address")}\n` +
    `City (residence and place of swearing): ${field(d, "city")}\n` +
    `Purpose of the affidavit: ${field(d, "purpose")}\n` +
    `Date of affirmation: ${field(d, "date")}\n\n` +
    `Use exactly the name, parentage, age, occupation, address, city, purpose and date supplied above — do not invent them or leave bracketed placeholders for any provided value. Open in the first person ("I, ${field(d, "name")}, do hereby solemnly affirm and declare as under"), recite the deponent's parentage, age, occupation and residence, number the averments, state the purpose and the authority before which it is produced, and close with a verification clause recording the city and date and a DEPONENT signature block. Do not cite any Act or section in the body and do not wrap any statutory reference in brackets; the notary's seal and attestation are affixed by the notary. ${NO_PLACEHOLDERS}`,

  cheque_bounce_138: (d) =>
    `Draft a statutory legal demand notice under Section 138 of the Negotiable Instruments Act, 1881 for a dishonoured cheque.\n` +
    `Drawer (accused): ${field(d, "drawer")}\n` +
    `Drawer's address: ${field(d, "drawer_address")}\n` +
    `Payee (complainant): ${field(d, "payee")}\n` +
    `Payee's address: ${field(d, "payee_address")}\n` +
    `Cheque No.: ${field(d, "cheque_no")} dated ${field(d, "cheque_date")}, drawn on ${field(d, "bank")}\n` +
    `Amount: Rs. ${field(d, "amount")}\n` +
    `Cheque presented for payment on: ${field(d, "presentation_date")}\n` +
    `Returned unpaid vide bank return memo dated ${field(d, "return_memo_date")} for the reason: ${field(d, "dishonour_reason")}\n` +
    `Place / city of issue: ${field(d, "city")}\n` +
    `Notice dated: ${field(d, "notice_date")}\n\n` +
    `Use exactly the names, addresses, dates, amounts, and cheque/bank details supplied above — do not invent them or substitute bracketed placeholders for any value that has been provided. This notice is sent by the payee in the payee's own name and signed by the payee; state dispatch by Registered Post A.D. Recite the issuance and dishonour of the cheque, demand payment of the cheque amount within 15 days of receipt of this notice, and warn that criminal proceedings under Section 138 will follow on default. ${NO_PLACEHOLDERS}`,

  mou_two_parties: (d) =>
    `Draft a Memorandum of Understanding governed by the Indian Contract Act, 1872.\n` +
    `First Party: ${field(d, "party_a")}, of ${field(d, "party_a_address")}\n` +
    `Second Party: ${field(d, "party_b")}, of ${field(d, "party_b_address")}\n` +
    `Purpose / scope: ${field(d, "purpose")}\n` +
    `Term: ${field(d, "term")}\n` +
    `Consideration / financial contribution: Rs. ${field(d, "value")}\n` +
    `Place of execution (city): ${field(d, "city")}\n` +
    `City of exclusive jurisdiction: ${field(d, "jurisdiction_city")}\n` +
    `Date of execution: ${field(d, "signing_date")}\n\n` +
    `Use exactly the parties, addresses, term, amount, cities and date supplied above — do not invent them or leave bracketed placeholders for any provided value. Include the title, date-and-place block, WHEREAS recitals, purpose and scope, roles and responsibilities, the financial arrangement, term and termination, confidentiality, a binding/non-binding clarification, dispute resolution, and governing-law and jurisdiction (at the named city) clauses. End with this exact signature format and no other: a blank underscore line, then "For ${field(d, "party_a")}" and on the next line the word "Authorised Signatory"; then a blank underscore line, then "For ${field(d, "party_b")}" and on the next line the word "Authorised Signatory"; then two blank underscore witness lines. Never write the literal phrase "Name of Authorised Signatory" and never output any text enclosed in square brackets. ${NO_PLACEHOLDERS}`,

  leave_license_mh: (d) =>
    `Draft a Leave and License Agreement for premises in Maharashtra (a bare licence under Section 52, Indian Easements Act, 1882; registrable under Section 55, Maharashtra Rent Control Act, 1999).\n` +
    `Licensor (owner): ${field(d, "licensor")}, of ${field(d, "licensor_address")}\n` +
    `Licensee (occupant): ${field(d, "licensee")}, of ${field(d, "licensee_address")}\n` +
    `Licensed premises: ${field(d, "address")}\n` +
    `City: ${field(d, "city")}\n` +
    `Monthly license fee: Rs. ${field(d, "rent")}\n` +
    `Interest-free refundable security deposit: Rs. ${field(d, "security_deposit")}\n` +
    `License period: ${field(d, "duration")}; Commencement date: ${field(d, "start_date")}\n` +
    `Notice period for revocation: ${field(d, "notice_period")} month(s)\n\n` +
    `Use exactly the names, addresses, premises, city, amounts, term, date and notice period supplied above — do not invent them or leave bracketed placeholders for any provided value. Style the parties as Licensor and Licensee, and include grant and term, the fee and payment day, the refundable deposit, permitted use, maintenance, the no-tenancy declaration, registration and stamp-duty clauses, a Schedule of the premises, and signature blocks for the parties over two blank witness lines. ${NO_PLACEHOLDERS}`,

  consumer_complaint_cpa2019: (d) =>
    `Draft a consumer complaint under Section 35 of the Consumer Protection Act, 2019, to be filed before the District Consumer Disputes Redressal Commission.\n` +
    `Complainant: ${field(d, "complainant")}, residing at ${field(d, "address")}\n` +
    `Opposite Party: ${field(d, "opposite_party")}, of ${field(d, "opposite_party_address")}\n` +
    `Product / service: ${field(d, "product_service")}; Invoice/order no.: ${field(d, "invoice_number")}\n` +
    `Amount paid: Rs. ${field(d, "purchase_amount")} on ${field(d, "purchase_date")}\n` +
    `Defect / deficiency arose on: ${field(d, "trigger_date")}\n` +
    `Grievance: ${field(d, "grievance")}\n` +
    `Compensation claimed: Rs. ${field(d, "compensation_sought")}\n` +
    `District / city: ${field(d, "city")}\n` +
    `Date of filing / verification: ${field(d, "filing_date")}\n\n` +
    `Use exactly the names, addresses, product/service, invoice number, amounts, dates, city and grievance supplied above — do not invent them or leave bracketed placeholders for any provided value. Set out the forum heading and cause title, plead that the complainant is a "consumer", recite the transaction with its dates and amounts, the deficiency in service / unfair trade practice, the territorial and pecuniary jurisdiction paragraphs, a limitation paragraph, a prayer for refund/replacement/compensation/costs, and a verification clause stating "Verified at ${field(d, "city")} on ${field(d, "filing_date")}". ${NO_PLACEHOLDERS}`,

  partnership_deed_1932: (d) =>
    `Draft a Partnership Deed under the Indian Partnership Act, 1932.\n` +
    `First Partner: ${field(d, "partner_a")}; capital contribution Rs. ${field(d, "capital_a")}\n` +
    `Second Partner: ${field(d, "partner_b")}; capital contribution Rs. ${field(d, "capital_b")}\n` +
    `Firm name: ${field(d, "firm_name")}\n` +
    `Nature of business: ${field(d, "business")}\n` +
    `Principal place of business: ${field(d, "business_address")}, ${field(d, "city")}\n` +
    `Profit and loss sharing ratio: ${field(d, "profit_ratio")}\n` +
    `City of execution / place of signing: ${field(d, "city")}\n` +
    `Date of commencement: ${field(d, "commencement_date")}\n\n` +
    `Use exactly the partners, capital amounts, firm name, business, address, city, ratio and date supplied above — do not invent them or leave bracketed placeholders for any provided value. The deed is made and executed at ${field(d, "city")} on the date of commencement. Include the firm name and style, the principal place and nature of business, the commencement date, each partner's capital, the profit/loss ratio, banking and accounts, duties and restrictions, admission/retirement/dissolution, an arbitration clause, and signature blocks for the partners over two blank witness lines. ${NO_PLACEHOLDERS}`,

  reply_to_legal_notice: (d) =>
    `Draft a reply to a legal notice on behalf of the noticee, marked WITHOUT PREJUDICE.\n` +
    `Sender of this reply (noticee): ${field(d, "sender")}, of ${field(d, "address")}\n` +
    `Addressed to (original notice sender): ${field(d, "recipient")}, of ${field(d, "recipient_address")}\n` +
    `Date of the notice under reply: ${field(d, "notice_date")}\n` +
    `Date of this reply: ${field(d, "reply_date")}\n` +
    `Amount demanded in the original notice: Rs. ${field(d, "amount")}\n` +
    `Grounds / defence: ${field(d, "reason")}\n` +
    `Mode of dispatch: ${field(d, "dispatch_mode")}; City: ${field(d, "city")}\n\n` +
    `Use exactly the names, addresses, dates, amount, dispatch mode and city supplied above — do not invent them or leave bracketed placeholders for any provided value. This reply is sent by the noticee in the noticee's own name and signed by the noticee. Open by recording receipt of the notice, raise preliminary objections, reply para-wise denying each adverse allegation specifically, set out the noticee's true version on the stated grounds, make counter-demands, reserve all rights civil and criminal, and close with the signature block. ${NO_PLACEHOLDERS}`,

  legal_notice_landlord_tenant: (d) =>
    `Draft a legal notice from a landlord to a tenant demanding arrears of rent and vacant possession (15 days' notice under Section 106, Transfer of Property Act, 1882, where applicable).\n` +
    `Landlord: ${field(d, "landlord")}, of ${field(d, "landlord_address")}\n` +
    `Tenant: ${field(d, "tenant")}, of ${field(d, "tenant_address")}\n` +
    `Tenanted premises: ${field(d, "address")}, ${field(d, "city")}\n` +
    `Monthly rent: Rs. ${field(d, "monthly_rent")}\n` +
    `Rent in arrears: ${field(d, "arrears_months")} month(s)\n` +
    `Tenancy commencement date: ${field(d, "tenancy_start_date")}\n` +
    `Compliance period demanded: ${field(d, "notice_period")} days\n` +
    `Notice dated: ${field(d, "notice_date")}\n\n` +
    `Use exactly the names, addresses, premises, city, rent, arrears, dates and notice period supplied above — do not invent them or leave bracketed placeholders for any provided value. This notice is sent by the landlord PERSONALLY and the word "advocate" must not appear anywhere. Head it "From: ${field(d, "landlord")}, ${field(d, "landlord_address")}"; address it "To: ${field(d, "tenant")}, ${field(d, "tenant_address")}"; and close with a blank underscore line followed by "${field(d, "landlord")}" as the signatory. State dispatch by Registered Post A.D. Recite the tenancy and the default with dates, demand payment of the arrears and vacant possession within the stated period, warn of eviction and recovery proceedings on default, and reserve rights. Never output any text enclosed in square brackets. ${NO_PLACEHOLDERS}`,

  employment_offer_termination: (d) =>
    `Draft a formal employment termination letter on company letterhead (Indian private sector; never describe the employment as "at-will").\n` +
    `Company: ${field(d, "company")}\n` +
    `Employee: ${field(d, "employee")}; Designation: ${field(d, "designation")}\n` +
    `Employee address: ${field(d, "employee_address")}\n` +
    `Reason for termination: ${field(d, "reason")}\n` +
    `Last working day: ${field(d, "last_day")}\n` +
    `Notice: ${field(d, "notice_disposition")}\n` +
    `Letter dated: ${field(d, "letter_date")}\n\n` +
    `Use exactly the company, employee, designation, address, reason, dates and notice disposition supplied above — do not invent them or leave bracketed placeholders for any provided value. Include the date line and addressee block, a subject line, recite the employment and the reason, state the last working day and whether notice is served or paid in lieu, the full and final settlement and the return of company property, and close with "Yours sincerely", "For ${field(d, "company")}", a blank signature line, and "Authorised Signatory, Human Resources" (do not leave a bracketed name). ${NO_PLACEHOLDERS}`,

  legal_notice_money_recovery: (d) =>
    `Draft a legal notice for recovery of money / outstanding dues.\n` +
    `Claimant (sender): ${field(d, "lender")}, of ${field(d, "lender_address")}\n` +
    `Debtor (recipient): ${field(d, "borrower")}, of ${field(d, "address")}\n` +
    `Nature of the dues / transaction: ${field(d, "debt_nature")}\n` +
    `Principal amount due: Rs. ${field(d, "amount")}\n` +
    `Interest: ${field(d, "interest_rate")}% per annum\n` +
    `Date the debt arose: ${field(d, "debt_origin_date")}; Date payment fell due: ${field(d, "payment_due_date")}\n` +
    `Compliance window: ${field(d, "compliance_days")} days; City: ${field(d, "city")}\n` +
    `Notice dated: ${field(d, "notice_date")}\n\n` +
    `Use exactly the names, addresses, amount, interest rate, dates, nature of dues, compliance window and city supplied above — do not invent them or leave bracketed placeholders for any provided value, and state the compliance window as a concrete number of days. This notice is sent by the claimant PERSONALLY and the word "advocate" must not appear anywhere. Head it "From: ${field(d, "lender")}, ${field(d, "lender_address")}"; address it "To: ${field(d, "borrower")}, ${field(d, "address")}"; and close with a blank underscore line followed by "${field(d, "lender")}" as the signatory. State dispatch by Registered Post A.D. Describe the transaction (${field(d, "debt_nature")}) and the default with dates, demand the principal together with interest within the stated days of receipt, warn of a civil recovery suit with interest and costs on default, and reserve rights. Never output any text enclosed in square brackets. ${NO_PLACEHOLDERS}`,

  legal_notice_general: (d) =>
    `Draft a general legal notice.\n` +
    `Sender: ${field(d, "sender")}, of ${field(d, "sender_address")}\n` +
    `Recipient: ${field(d, "recipient")}, of ${field(d, "address")}\n` +
    `Subject: ${field(d, "subject")}\n` +
    `Facts and grievance: ${field(d, "details")}\n` +
    `Relief / demand sought: ${field(d, "demand")}\n` +
    `Compliance window: ${field(d, "compliance_days")} days; City: ${field(d, "city")}\n` +
    `Notice dated: ${field(d, "notice_date")}\n\n` +
    `Use exactly the names, addresses, subject, facts, demand, compliance window, city and date supplied above — do not invent them or leave bracketed placeholders for any provided value, and state the compliance window as a concrete number of days. This notice is sent by the sender personally in the sender's own name (not through an advocate): begin directly with the notice (no bracketed labels or headings), sign in the sender's own name, and state dispatch by Registered Post A.D. — do NOT insert any advocate name, address or registration-number. Set out the facts and the legal grievance, state the demand clearly, allow the stated number of days for compliance, warn of further legal action on default, and reserve rights. ${NO_PLACEHOLDERS}`,
};

export function buildPrompt(docType: string, details: Details): string {
  const template = TEMPLATES[docType];
  if (!template) {
    throw new Error(`Unknown document type: ${docType}`);
  }
  return template(details);
}
