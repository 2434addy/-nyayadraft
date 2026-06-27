export type FieldType = "text" | "number" | "textarea";

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  placeholder?: string;
}

export interface DocTypeDef {
  value: string;
  label: string;
  description: string;
  fields: FieldDef[];
}

/**
 * Single source of truth for the document catalogue used by the form.
 * `value` matches the keys in lib/prompt-templates.ts; `key`s match the
 * placeholders each template interpolates.
 */
export const DOC_TYPES: DocTypeDef[] = [
  {
    value: "affidavit_general",
    label: "General Affidavit",
    description: "A sworn statement of facts for general purposes.",
    fields: [
      { key: "name", label: "Deponent name", type: "text" },
      { key: "address", label: "Deponent address", type: "textarea" },
      { key: "purpose", label: "Purpose of affidavit", type: "textarea" },
    ],
  },
  {
    value: "cheque_bounce_138",
    label: "Cheque Bounce Notice (S.138 NI Act)",
    description: "Statutory demand notice for a dishonoured cheque.",
    fields: [
      { key: "drawer", label: "Drawer (cheque issuer)", type: "text" },
      { key: "payee", label: "Payee (you)", type: "text" },
      { key: "amount", label: "Cheque amount (Rs.)", type: "number" },
      { key: "bank", label: "Bank name", type: "text" },
      { key: "cheque_no", label: "Cheque number", type: "text" },
    ],
  },
  {
    value: "mou_two_parties",
    label: "Memorandum of Understanding",
    description: "An MoU between two parties.",
    fields: [
      { key: "party_a", label: "First party", type: "text" },
      { key: "party_b", label: "Second party", type: "text" },
      { key: "purpose", label: "Purpose of the MoU", type: "textarea" },
      { key: "duration", label: "Duration / term", type: "text" },
      { key: "value", label: "Consideration value (Rs.)", type: "number" },
    ],
  },
  {
    value: "leave_license_mh",
    label: "Leave & License Agreement (Maharashtra)",
    description: "Leave and license agreement under Maharashtra law.",
    fields: [
      { key: "address", label: "Premises address", type: "textarea" },
      { key: "licensor", label: "Licensor (owner)", type: "text" },
      { key: "licensee", label: "Licensee (occupant)", type: "text" },
      { key: "rent", label: "Monthly license fee (Rs.)", type: "number" },
      { key: "duration", label: "License period", type: "text" },
    ],
  },
  {
    value: "consumer_complaint_cpa2019",
    label: "Consumer Complaint (CPA 2019)",
    description: "Complaint before a Consumer Disputes Redressal Commission.",
    fields: [
      { key: "complainant", label: "Complainant name", type: "text" },
      { key: "address", label: "Complainant address", type: "textarea" },
      { key: "opposite_party", label: "Opposite party", type: "text" },
      { key: "grievance", label: "Grievance / complaint", type: "textarea" },
    ],
  },
  {
    value: "partnership_deed_1932",
    label: "Partnership Deed (1932 Act)",
    description: "Deed under the Indian Partnership Act, 1932.",
    fields: [
      { key: "partner_a", label: "First partner", type: "text" },
      { key: "partner_b", label: "Second partner", type: "text" },
      { key: "business", label: "Nature of business", type: "text" },
      { key: "profit_ratio", label: "Profit-sharing ratio (e.g. 50:50)", type: "text" },
    ],
  },
  {
    value: "reply_to_legal_notice",
    label: "Reply to a Legal Notice",
    description: "A response refuting the claims in a received notice.",
    fields: [
      { key: "sender", label: "Sender (you)", type: "text" },
      { key: "recipient", label: "Recipient (original notice sender)", type: "text" },
      { key: "address", label: "Your address", type: "textarea" },
      { key: "amount", label: "Amount demanded (Rs.)", type: "number" },
      { key: "reason", label: "Grounds for reply / defence", type: "textarea" },
    ],
  },
  {
    value: "legal_notice_landlord_tenant",
    label: "Legal Notice — Landlord to Tenant",
    description: "Notice for unpaid rent and possession.",
    fields: [
      { key: "landlord", label: "Landlord", type: "text" },
      { key: "tenant", label: "Tenant", type: "text" },
      { key: "amount", label: "Outstanding rent (Rs.)", type: "number" },
      { key: "months", label: "Months overdue", type: "number" },
      { key: "address", label: "Premises address", type: "textarea" },
    ],
  },
  {
    value: "employment_offer_termination",
    label: "Employment Termination Letter",
    description: "Termination of an employment relationship.",
    fields: [
      { key: "company", label: "Company", type: "text" },
      { key: "employee", label: "Employee", type: "text" },
      { key: "reason", label: "Reason for termination", type: "textarea" },
      { key: "last_day", label: "Last working day", type: "text" },
    ],
  },
  {
    value: "legal_notice_money_recovery",
    label: "Legal Notice — Money Recovery",
    description: "Demand for repayment of a loan or dues.",
    fields: [
      { key: "lender", label: "Lender (you)", type: "text" },
      { key: "borrower", label: "Borrower", type: "text" },
      { key: "address", label: "Borrower address", type: "textarea" },
      { key: "amount", label: "Principal amount (Rs.)", type: "number" },
      { key: "interest_rate", label: "Interest rate (% p.a.)", type: "number" },
    ],
  },
  {
    value: "legal_notice_general",
    label: "Legal Notice — General",
    description: "A general-purpose legal notice.",
    fields: [
      { key: "sender", label: "Sender (you)", type: "text" },
      { key: "recipient", label: "Recipient", type: "text" },
      { key: "address", label: "Recipient address", type: "textarea" },
      { key: "subject", label: "Subject", type: "text" },
      { key: "details", label: "Details / facts", type: "textarea" },
    ],
  },
];
