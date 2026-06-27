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

type Template = (d: Details) => string;

const TEMPLATES: Record<string, Template> = {
  affidavit_general: (d) =>
    `Draft a general affidavit under Indian law.\n` +
    `Deponent: ${field(d, "name")}\n` +
    `Address: ${field(d, "address")}\n` +
    `Purpose of the affidavit: ${field(d, "purpose")}\n\n` +
    `Use a formal first-person style ("I, ${field(d, "name")}, do hereby solemnly affirm and declare as under"), number the averments, and close with the standard verification clause and a signature/notary block.`,

  cheque_bounce_138: (d) =>
    `Draft a statutory legal demand notice under Section 138 of the Negotiable Instruments Act, 1881 for a dishonoured cheque.\n` +
    `Drawer (accused): ${field(d, "drawer")}\n` +
    `Payee (complainant): ${field(d, "payee")}\n` +
    `Cheque No.: ${field(d, "cheque_no")} drawn on ${field(d, "bank")}\n` +
    `Amount: Rs. ${field(d, "amount")}\n\n` +
    `Recite the dishonour, demand payment of the cheque amount within 15 days of receipt, and warn that criminal proceedings under Section 138 will follow on default.`,

  mou_two_parties: (d) =>
    `Draft a Memorandum of Understanding governed by Indian law.\n` +
    `First Party: ${field(d, "party_a")}\n` +
    `Second Party: ${field(d, "party_b")}\n` +
    `Purpose: ${field(d, "purpose")}\n` +
    `Term / duration: ${field(d, "duration")}\n` +
    `Consideration / value: Rs. ${field(d, "value")}\n\n` +
    `Include recitals, scope of cooperation, roles and responsibilities, confidentiality, term and termination, and a governing-law and dispute-resolution clause.`,

  leave_license_mh: (d) =>
    `Draft a Leave and License Agreement for residential premises in Maharashtra, consistent with the Maharashtra Rent Control Act, 1999.\n` +
    `Premises: ${field(d, "address")}\n` +
    `Licensor (owner): ${field(d, "licensor")}\n` +
    `Licensee (occupant): ${field(d, "licensee")}\n` +
    `Monthly license fee: Rs. ${field(d, "rent")}\n` +
    `License period: ${field(d, "duration")}\n\n` +
    `Include security deposit, permitted use, maintenance, registration, and termination clauses.`,

  consumer_complaint_cpa2019: (d) =>
    `Draft a consumer complaint under the Consumer Protection Act, 2019 to be filed before the appropriate District Consumer Disputes Redressal Commission.\n` +
    `Complainant: ${field(d, "complainant")}, residing at ${field(d, "address")}\n` +
    `Opposite Party: ${field(d, "opposite_party")}\n` +
    `Grievance: ${field(d, "grievance")}\n\n` +
    `Set out the parties, jurisdiction, facts, the deficiency in service / unfair trade practice, the prayer for relief (refund, replacement, or compensation), and a verification clause.`,

  partnership_deed_1932: (d) =>
    `Draft a Partnership Deed under the Indian Partnership Act, 1932.\n` +
    `First Partner: ${field(d, "partner_a")}\n` +
    `Second Partner: ${field(d, "partner_b")}\n` +
    `Nature of business: ${field(d, "business")}\n` +
    `Profit and loss sharing ratio: ${field(d, "profit_ratio")}\n\n` +
    `Include the firm name and place of business, capital contribution, duties of partners, banking and accounts, admission/retirement, dissolution, and an arbitration clause.`,

  reply_to_legal_notice: (d) =>
    `Draft a reply to a legal notice on behalf of the recipient.\n` +
    `Sender of this reply: ${field(d, "sender")}, of ${field(d, "address")}\n` +
    `Addressed to: ${field(d, "recipient")}\n` +
    `Amount demanded in the original notice: Rs. ${field(d, "amount")}\n` +
    `Grounds / defence: ${field(d, "reason")}\n\n` +
    `Deny the allegations point by point on the stated grounds, assert the client's position, and reserve the right to take further legal action.`,

  legal_notice_landlord_tenant: (d) =>
    `Draft a legal notice from a landlord to a tenant demanding arrears of rent and possession.\n` +
    `Landlord: ${field(d, "landlord")}\n` +
    `Tenant: ${field(d, "tenant")}\n` +
    `Premises: ${field(d, "address")}\n` +
    `Outstanding rent: Rs. ${field(d, "amount")} for ${field(d, "months")} month(s)\n\n` +
    `Demand payment of the arrears and vacant possession within 15 days, failing which eviction and recovery proceedings will be initiated.`,

  employment_offer_termination: (d) =>
    `Draft a formal employment termination letter.\n` +
    `Company: ${field(d, "company")}\n` +
    `Employee: ${field(d, "employee")}\n` +
    `Reason for termination: ${field(d, "reason")}\n` +
    `Last working day: ${field(d, "last_day")}\n\n` +
    `State the effective date, settlement of dues and notice period, return of company property, and continuing confidentiality obligations.`,

  legal_notice_money_recovery: (d) =>
    `Draft a legal notice for recovery of money lent.\n` +
    `Lender (sender): ${field(d, "lender")}\n` +
    `Borrower (recipient): ${field(d, "borrower")}, residing at ${field(d, "address")}\n` +
    `Outstanding principal: Rs. ${field(d, "amount")}\n` +
    `Interest: ${field(d, "interest_rate")}% per annum\n\n` +
    `Recite the loan and default, demand repayment of principal with interest within 15 days, and warn that a recovery suit will be filed on default.`,

  legal_notice_general: (d) =>
    `Draft a general legal notice.\n` +
    `Sender: ${field(d, "sender")}\n` +
    `Recipient: ${field(d, "recipient")}, at ${field(d, "address")}\n` +
    `Subject: ${field(d, "subject")}\n` +
    `Facts and grievance: ${field(d, "details")}\n\n` +
    `Set out the facts, state the legal grievance and demand clearly, and allow 15 days for compliance before further legal action.`,
};

export function buildPrompt(docType: string, details: Details): string {
  const template = TEMPLATES[docType];
  if (!template) {
    throw new Error(`Unknown document type: ${docType}`);
  }
  return template(details);
}
