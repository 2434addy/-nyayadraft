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
      { key: "parentage", label: "Father's / husband's name", type: "text" },
      { key: "age", label: "Deponent age (years)", type: "number" },
      { key: "occupation", label: "Deponent occupation", type: "text" },
      { key: "address", label: "Deponent address", type: "textarea" },
      { key: "city", label: "City", type: "text" },
      { key: "purpose", label: "Purpose of affidavit", type: "textarea" },
      { key: "date", label: "Date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "cheque_bounce_138",
    label: "Cheque Bounce Notice (S.138 NI Act)",
    description: "Statutory demand notice for a dishonoured cheque.",
    fields: [
      { key: "drawer", label: "Drawer (cheque issuer)", type: "text" },
      { key: "drawer_address", label: "Drawer address", type: "textarea" },
      { key: "payee", label: "Payee (you)", type: "text" },
      { key: "payee_address", label: "Payee address", type: "textarea" },
      { key: "amount", label: "Cheque amount (Rs.)", type: "number" },
      { key: "bank", label: "Bank name", type: "text" },
      { key: "cheque_no", label: "Cheque number", type: "text" },
      { key: "cheque_date", label: "Cheque date", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "presentation_date", label: "Date of presentation", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "return_memo_date", label: "Return memo date", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "dishonour_reason", label: "Reason for dishonour", type: "text", placeholder: "e.g. Insufficient funds" },
      { key: "city", label: "City", type: "text" },
      { key: "notice_date", label: "Notice date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "mou_two_parties",
    label: "Memorandum of Understanding",
    description: "An MoU between two parties.",
    fields: [
      { key: "party_a", label: "First party", type: "text" },
      { key: "party_a_address", label: "First party address", type: "textarea" },
      { key: "party_b", label: "Second party", type: "text" },
      { key: "party_b_address", label: "Second party address", type: "textarea" },
      { key: "purpose", label: "Purpose / scope of the MoU", type: "textarea" },
      { key: "term", label: "Term (e.g. 12 months)", type: "text" },
      { key: "value", label: "Consideration value (Rs.)", type: "number" },
      { key: "city", label: "Place of execution (city)", type: "text" },
      { key: "jurisdiction_city", label: "Jurisdiction city", type: "text" },
      { key: "signing_date", label: "Date of execution", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "leave_license_mh",
    label: "Leave & License Agreement (Maharashtra)",
    description: "Leave and license agreement under Maharashtra law.",
    fields: [
      { key: "licensor", label: "Licensor (owner)", type: "text" },
      { key: "licensor_address", label: "Licensor address", type: "textarea" },
      { key: "licensee", label: "Licensee (occupant)", type: "text" },
      { key: "licensee_address", label: "Licensee address", type: "textarea" },
      { key: "address", label: "Premises address", type: "textarea" },
      { key: "city", label: "City (in Maharashtra)", type: "text" },
      { key: "rent", label: "Monthly license fee (Rs.)", type: "number" },
      { key: "security_deposit", label: "Security deposit (Rs.)", type: "number" },
      { key: "duration", label: "License period (e.g. 11 months)", type: "text" },
      { key: "start_date", label: "Commencement date", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "notice_period", label: "Notice period (months)", type: "text" },
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
      { key: "opposite_party_address", label: "Opposite party address", type: "textarea" },
      { key: "product_service", label: "Product / service complained of", type: "text" },
      { key: "purchase_amount", label: "Purchase amount (Rs.)", type: "number" },
      { key: "purchase_date", label: "Date of purchase / payment", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "trigger_date", label: "Date defect / deficiency arose", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "grievance", label: "Grievance / deficiency", type: "textarea" },
      { key: "compensation_sought", label: "Compensation claimed (Rs.)", type: "number" },
      { key: "invoice_number", label: "Invoice / order number", type: "text" },
      { key: "city", label: "City (district)", type: "text" },
      { key: "filing_date", label: "Filing / verification date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "partnership_deed_1932",
    label: "Partnership Deed (1932 Act)",
    description: "Deed under the Indian Partnership Act, 1932.",
    fields: [
      { key: "partner_a", label: "First partner", type: "text" },
      { key: "capital_a", label: "First partner capital (Rs.)", type: "number" },
      { key: "partner_b", label: "Second partner", type: "text" },
      { key: "capital_b", label: "Second partner capital (Rs.)", type: "number" },
      { key: "firm_name", label: "Firm name", type: "text" },
      { key: "business", label: "Nature of business", type: "text" },
      { key: "business_address", label: "Principal place of business", type: "textarea" },
      { key: "city", label: "City", type: "text" },
      { key: "profit_ratio", label: "Profit-sharing ratio (e.g. 50:50)", type: "text" },
      { key: "commencement_date", label: "Commencement date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "reply_to_legal_notice",
    label: "Reply to a Legal Notice",
    description: "A response refuting the claims in a received notice.",
    fields: [
      { key: "sender", label: "Sender (you)", type: "text" },
      { key: "address", label: "Your address", type: "textarea" },
      { key: "recipient", label: "Recipient (original notice sender)", type: "text" },
      { key: "recipient_address", label: "Recipient address", type: "textarea" },
      { key: "amount", label: "Amount demanded (Rs.)", type: "number" },
      { key: "reason", label: "Grounds for reply / defence", type: "textarea" },
      { key: "notice_date", label: "Date of notice under reply", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "reply_date", label: "Date of this reply", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "dispatch_mode", label: "Mode of dispatch", type: "text", placeholder: "e.g. Registered Post A.D." },
      { key: "city", label: "City", type: "text" },
    ],
  },
  {
    value: "legal_notice_landlord_tenant",
    label: "Legal Notice — Landlord to Tenant",
    description: "Notice for unpaid rent and possession.",
    fields: [
      { key: "landlord", label: "Landlord", type: "text" },
      { key: "landlord_address", label: "Landlord address", type: "textarea" },
      { key: "tenant", label: "Tenant", type: "text" },
      { key: "tenant_address", label: "Tenant address", type: "textarea" },
      { key: "address", label: "Premises address", type: "textarea" },
      { key: "city", label: "City", type: "text" },
      { key: "monthly_rent", label: "Monthly rent (Rs.)", type: "number" },
      { key: "arrears_months", label: "Months of rent in arrears", type: "number" },
      { key: "tenancy_start_date", label: "Tenancy commencement date", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "notice_period", label: "Notice period (days, 15 or 30)", type: "text" },
      { key: "notice_date", label: "Notice date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "employment_offer_termination",
    label: "Employment Termination Letter",
    description: "Termination of an employment relationship.",
    fields: [
      { key: "company", label: "Company", type: "text" },
      { key: "employee", label: "Employee", type: "text" },
      { key: "designation", label: "Designation", type: "text" },
      { key: "employee_address", label: "Employee address", type: "textarea" },
      { key: "reason", label: "Reason for termination", type: "textarea" },
      { key: "last_day", label: "Last working day", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "notice_disposition", label: "Notice served or pay in lieu", type: "text", placeholder: "e.g. Notice served until last day" },
      { key: "letter_date", label: "Letter date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "legal_notice_money_recovery",
    label: "Legal Notice — Money Recovery",
    description: "Demand for repayment of a loan or dues.",
    fields: [
      { key: "lender", label: "Lender (you)", type: "text" },
      { key: "lender_address", label: "Lender address", type: "textarea" },
      { key: "borrower", label: "Borrower", type: "text" },
      { key: "address", label: "Borrower address", type: "textarea" },
      { key: "debt_nature", label: "Nature of debt / transaction", type: "text", placeholder: "e.g. friendly loan, unpaid invoice" },
      { key: "amount", label: "Principal amount (Rs.)", type: "number" },
      { key: "interest_rate", label: "Interest rate (% p.a.)", type: "number" },
      { key: "debt_origin_date", label: "Date the debt arose", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "payment_due_date", label: "Date payment fell due", type: "text", placeholder: "DD/MM/YYYY" },
      { key: "compliance_days", label: "Days to comply (15 or 30)", type: "text" },
      { key: "city", label: "City", type: "text" },
      { key: "notice_date", label: "Notice date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
  {
    value: "legal_notice_general",
    label: "Legal Notice — General",
    description: "A general-purpose legal notice.",
    fields: [
      { key: "sender", label: "Sender (you)", type: "text" },
      { key: "sender_address", label: "Sender address", type: "textarea" },
      { key: "recipient", label: "Recipient", type: "text" },
      { key: "address", label: "Recipient address", type: "textarea" },
      { key: "subject", label: "Subject", type: "text" },
      { key: "details", label: "Details / facts", type: "textarea" },
      { key: "demand", label: "Relief / demand sought", type: "textarea" },
      { key: "compliance_days", label: "Days to comply (15 or 30)", type: "text" },
      { key: "city", label: "City", type: "text" },
      { key: "notice_date", label: "Notice date", type: "text", placeholder: "DD/MM/YYYY" },
    ],
  },
];
