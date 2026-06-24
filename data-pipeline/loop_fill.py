"""Autonomous dataset-growth loop for NyayaDraft (no API key — own knowledge only).

Grows finetune/data/train.jsonl from its current size to TARGET records by
generating one Indian legal document per loop cycle, cycling doc_type through
CYCLE. Every generated document is validated against the real legal_rules gate
before it is appended; a record that fails the gate aborts the run rather than
corrupting the dataset.

The legal content is hand-authored template knowledge (this file) parameterised
with randomised Indian names / cities / amounts / dates. No network, no model
call, no API key.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "finetune" / "data" / "train.jsonl"
TARGET = 1500
DISCLAIMER = (
    "This is an AI-generated draft for review by the parties and is not legal advice."
)

# user-specified cycle order (loop_state THIS_DOC_TYPE = mou_two_parties first)
CYCLE = [
    "mou_two_parties",
    "leave_license_mh",
    "out_of_scope",
    "affidavit_general",
    "employment_offer_termination",
    "reply_to_legal_notice",
    "cheque_bounce_138",
    "legal_notice_money_recovery",
    "legal_notice_landlord_tenant",
    "partnership_deed_1932",
    "consumer_complaint_cpa2019",
]

sys.path.insert(0, str(ROOT))
from legal_rules.checker import check_document  # noqa: E402

# --------------------------------------------------------------------------- #
# data pools
# --------------------------------------------------------------------------- #
MALE = ["Aarav", "Aditya", "Arjun", "Rohan", "Karan", "Rahul", "Vikram", "Sanjay",
        "Ramesh", "Suresh", "Mahesh", "Nitin", "Ajay", "Anil", "Deepak", "Manoj",
        "Prakash", "Rajesh", "Sunil", "Amit", "Sandeep", "Ashok", "Vijay", "Harish",
        "Naveen", "Pankaj", "Yogesh", "Kunal", "Gaurav", "Siddharth", "Omkar",
        "Tushar", "Nikhil", "Sachin", "Imran", "Salman", "Abdul", "Joseph",
        "Gurpreet", "Inder", "Faisal", "Mohammed", "Praveen", "Aniket"]
FEMALE = ["Priya", "Neha", "Pooja", "Anjali", "Kavita", "Sunita", "Meena", "Rekha",
          "Deepa", "Sneha", "Nikita", "Divya", "Shreya", "Aishwarya", "Radha",
          "Geeta", "Sushma", "Manju", "Asha", "Sarita", "Komal", "Pallavi",
          "Swati", "Trupti", "Vaishali", "Bhavna", "Heena", "Fatima", "Ayesha",
          "Zoya", "Mary", "Simran", "Harleen", "Madhuri", "Lakshmi"]
SUR = ["Sharma", "Verma", "Gupta", "Patel", "Shah", "Mehta", "Joshi", "Desai",
       "Deshmukh", "Kulkarni", "Patil", "Jadhav", "Reddy", "Naidu", "Rao", "Iyer",
       "Nair", "Menon", "Pillai", "Chatterjee", "Banerjee", "Mukherjee", "Das",
       "Singh", "Kaur", "Gill", "Sandhu", "Khan", "Ansari", "Sheikh", "Qureshi",
       "Fernandes", "Dsouza", "Pinto", "Agarwal", "Bansal", "Jain", "Malhotra",
       "Kapoor", "Chopra", "Khanna", "Sethi", "Bhatia", "Chauhan", "Yadav",
       "Mishra", "Tiwari", "Pandey", "Tripathi"]

CITIES = [("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"), ("Nagpur", "Maharashtra"),
          ("Thane", "Maharashtra"), ("Nashik", "Maharashtra"), ("Aurangabad", "Maharashtra"),
          ("Delhi", "Delhi"), ("Bengaluru", "Karnataka"), ("Mysuru", "Karnataka"),
          ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"), ("Coimbatore", "Tamil Nadu"),
          ("Kolkata", "West Bengal"), ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"),
          ("Vadodara", "Gujarat"), ("Jaipur", "Rajasthan"), ("Jodhpur", "Rajasthan"),
          ("Lucknow", "Uttar Pradesh"), ("Kanpur", "Uttar Pradesh"), ("Indore", "Madhya Pradesh"),
          ("Bhopal", "Madhya Pradesh"), ("Patna", "Bihar"), ("Chandigarh", "Chandigarh"),
          ("Kochi", "Kerala"), ("Visakhapatnam", "Andhra Pradesh"), ("Bhubaneswar", "Odisha"),
          ("Ludhiana", "Punjab"), ("Amritsar", "Punjab"), ("Gurugram", "Haryana"),
          ("Faridabad", "Haryana"), ("Noida", "Uttar Pradesh")]
MH_CITIES = [c for c in CITIES if c[1] == "Maharashtra"]

AREAS = ["MG Road", "Station Road", "Gandhi Chowk", "Nehru Nagar", "Shivaji Nagar",
         "Civil Lines", "Model Town", "Kothrud", "Andheri West", "Bandra East",
         "Vashi", "Kandivali", "Aundh", "Baner", "Viman Nagar", "Koregaon Park",
         "Camp", "Hadapsar", "Wakad", "Deccan Gymkhana", "FC Road", "JM Road"]
BLDGS = ["Silver Oak Towers", "Green Acres", "Rose Villa", "Sai Residency",
         "Krishna Apartments", "Sunshine Heights", "Lake View Residency", "Palm Grove",
         "Maple Court", "Orchid Enclave", "Pearl Residency", "Galaxy Heights",
         "Sapphire Towers", "Emerald Park", "Riverdale Heights", "Shanti Niketan"]
COMPANIES = ["TechNova Solutions Pvt. Ltd.", "Sunrise Logistics Pvt. Ltd.",
             "Bharat Infotech Pvt. Ltd.", "Maple Retail Pvt. Ltd.",
             "Greenfield Constructions Pvt. Ltd.", "Apex Pharma Pvt. Ltd.",
             "Orbit Software LLP", "Zenith Consultancy LLP", "M/s Sharma Traders",
             "Indus Manufacturing Pvt. Ltd.", "Crystal Foods Pvt. Ltd.",
             "Vertex Engineering Pvt. Ltd.", "Nimbus Media Pvt. Ltd.",
             "Stellar Textiles Pvt. Ltd.", "Pinnacle Realtors Pvt. Ltd."]
DESIGNATIONS = ["Software Engineer", "Senior Accountant", "Marketing Manager",
                "Operations Executive", "Sales Officer", "HR Manager",
                "Business Analyst", "Project Lead", "Quality Inspector",
                "Customer Support Associate", "Branch Manager", "Area Sales Manager"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty",
        "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return ONES[n]
    return TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else "")


def num_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thou, n = divmod(n, 1_000)
    hund, n = divmod(n, 100)
    if crore:
        parts.append(num_words(crore) + " Crore")
    if lakh:
        parts.append(_two(lakh) + " Lakh")
    if thou:
        parts.append(_two(thou) + " Thousand")
    if hund:
        parts.append(ONES[hund] + " Hundred")
    if n:
        parts.append(_two(n))
    return " ".join(parts)


def fmt_inr(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    rest = s[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return ",".join(groups) + "," + last3


def rupees(n: int) -> str:
    return f"\u20b9{fmt_inr(n)} (Rupees {num_words(n)} only)"


def ordinal(d: int) -> str:
    if 10 <= d % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    return f"{d}{suf}"


class R:
    """Thin wrapper around random.Random for terse pickers."""

    def __init__(self, rng: random.Random):
        self.r = rng

    def pick(self, seq):
        return self.r.choice(seq)

    def amt(self, lo, hi, step=1000):
        return self.r.randrange(lo, hi + 1, step)

    def person(self, gender=None):
        g = gender or self.pick(["m", "f"])
        first = self.pick(MALE if g == "m" else FEMALE)
        sur = self.pick(SUR)
        title = ("Mr." if g == "m" else self.pick(["Ms.", "Mrs."]))
        return g, f"{first} {sur}", f"{title} {first} {sur}"

    def addr(self, cities=CITIES):
        city, state = self.pick(cities)
        flat = self.r.randint(1, 90)
        return (f"Flat No. {flat}, {self.pick(BLDGS)}, {self.pick(AREAS)}, "
                f"{city} {self.r.randint(110001, 590099)}", city, state)

    def date(self):
        d = self.r.randint(1, 28)
        m = self.r.randint(1, 12)
        y = self.r.choice([2024, 2025, 2026])
        numeric = f"{d:02d}.{m:02d}.{y}"
        formal = f"{ordinal(d)} day of {MONTHS[m - 1]}, {y}"
        return numeric, formal


# --------------------------------------------------------------------------- #
# builders : each returns (scenario_base, user_msg, document_text)
# document_text for is_document types ends WITHOUT the disclaimer; the caller
# appends it. out_of_scope must not contain the disclaimer.
# --------------------------------------------------------------------------- #
def b_mou(R):
    _, _, p1 = R.person()
    _, _, p2 = R.person()
    a1, c1, _ = R.addr()
    a2, c2, _ = R.addr()
    purpose = R.pick([
        ("joint development of an e-learning platform", "technology collaboration"),
        ("supply and distribution of organic food products", "distribution arrangement"),
        ("co-organising a series of skill-development workshops", "training collaboration"),
        ("joint marketing of handloom textiles", "marketing collaboration"),
        ("setting up a shared logistics network", "logistics collaboration"),
        ("co-publishing a line of academic books", "publishing collaboration"),
    ])
    nd, formal = R.date()
    months = R.pick([12, 18, 24, 36])
    user = (f"Please draft a Memorandum of Understanding between {p1} of {c1} (First Party) "
            f"and {p2} of {c2} (Second Party) for {purpose[0]}. Keep it largely non-binding "
            f"except confidentiality and dispute resolution, valid for {months} months.")
    doc = f"""MEMORANDUM OF UNDERSTANDING

This Memorandum of Understanding (hereinafter referred to as this "MOU") is made and entered into on this {formal}, at {c1},

BY AND BETWEEN

{p1}, residing at {a1} (hereinafter referred to as the "First Party", which expression shall, unless repugnant to the context, include his/her heirs, executors, administrators and permitted assigns) of the ONE PART;

AND

{p2}, residing at {a2} (hereinafter referred to as the "Second Party", which expression shall, unless repugnant to the context, include his/her heirs, executors, administrators and permitted assigns) of the OTHER PART.

The First Party and the Second Party are hereinafter individually referred to as a "Party" and collectively as the "Parties".

WHEREAS the First Party is engaged in and possesses experience relevant to the proposed collaboration; AND WHEREAS the Second Party desires to associate with the First Party for the purpose of {purpose[0]}; AND WHEREAS the Parties are desirous of recording the broad understanding reached between them by way of this MOU.

NOW, THEREFORE, THE PARTIES HEREBY RECORD THEIR UNDERSTANDING AS UNDER:

1. PURPOSE — The Parties shall, in good faith, explore and undertake the {purpose[1]} described above and shall extend to each other reasonable cooperation towards its implementation.

2. SCOPE OF COOPERATION — The Parties shall share such information, resources and expertise as may be mutually agreed in writing from time to time, and shall constitute a joint working committee to oversee the activities contemplated herein.

3. COSTS — Save as otherwise agreed in writing, each Party shall bear its own costs and expenses incurred in connection with this MOU.

4. TERM — This MOU shall come into effect from the date first written above and shall, unless extended or terminated earlier in accordance herewith, remain in force for a period of {months} months.

5. CONFIDENTIALITY — Each Party shall keep confidential all proprietary and non-public information disclosed to it by the other Party and shall not disclose the same to any third party without prior written consent, save as required by law. This obligation of confidentiality shall survive the termination of this MOU.

6. BINDING EFFECT — Save and except the clauses relating to Confidentiality, Dispute Resolution and Governing Law, which the Parties intend to be legally binding, this MOU records the present intention of the Parties only and is not intended to create any legally binding obligation on either Party.

7. TERMINATION — Either Party may terminate this MOU by giving thirty (30) days' prior written notice to the other Party, without assigning any reason, and such termination shall be without prejudice to any accrued rights or obligations of the Parties.

8. DISPUTE RESOLUTION — Any dispute or difference arising out of or in connection with this MOU shall, in the first instance, be resolved amicably through mutual negotiation between the Parties, failing which the same shall be referred to and finally resolved by arbitration by a sole arbitrator to be appointed by mutual consent, the seat of arbitration being {c1}.

9. GOVERNING LAW AND JURISDICTION — This MOU shall be governed by and construed in accordance with the laws of India, and subject to the arbitration clause aforesaid, the courts at {c1} shall have exclusive jurisdiction.

IN WITNESS WHEREOF the Parties have set their respective hands to this MOU on the day, month and year first hereinabove written.

For the First Party                                   For the Second Party


____________________                                  ____________________
({p1})                                                ({p2})

WITNESSES:
1. ____________________
2. ____________________"""
    return purpose[1].replace(" ", "_"), user, doc


def b_leave_license(R):
    _, _, lic = R.person()
    _, _, lee = R.person()
    a1, c1, _ = R.addr(MH_CITIES)
    city, state = R.pick(MH_CITIES)
    kind = R.pick(["residential flat", "commercial office", "shop", "godown"])
    flat = R.r.randint(1, 60)
    prem = f"{R.pick(['Flat', 'Office', 'Shop', 'Gala'])} No. {flat}, {R.pick(BLDGS)}, {R.pick(AREAS)}, {city}"
    fee = R.amt(8000, 75000, 500)
    dep = R.amt(50000, 600000, 5000)
    months = R.pick([11, 22, 33])
    nd, formal = R.date()
    user = (f"Draft a Maharashtra leave and license agreement. Licensor is {lic}, Licensee is {lee}. "
            f"Premises: {prem}. License fee ₹{fmt_inr(fee)} per month, interest-free refundable "
            f"deposit ₹{fmt_inr(dep)}, term {months} months, one month notice.")
    doc = f"""LEAVE AND LICENSE AGREEMENT

This Leave and License Agreement is made and executed at {city} on this {formal},

BETWEEN

{lic}, residing at {a1} (hereinafter referred to as the "Licensor", which expression shall, unless repugnant to the context, include his/her heirs, legal representatives and permitted assigns) of the ONE PART;

AND

{lee}, an adult, (hereinafter referred to as the "Licensee", which expression shall, unless repugnant to the context, include his/her heirs, legal representatives and permitted assigns) of the OTHER PART.

WHEREAS the Licensor is the absolute owner of and is well and sufficiently entitled to the {kind} being {prem}, more particularly described in the Schedule hereunder (the "said premises"); AND WHEREAS the Licensee has approached the Licensor for permission to use and occupy the said premises on leave and license basis, which the Licensor has agreed to grant on the terms and conditions hereinafter appearing.

NOW THIS AGREEMENT WITNESSETH AS UNDER:

1. GRANT OF LICENSE — The Licensor hereby grants unto the Licensee a leave and license to use and occupy the said premises for the purpose aforesaid, on a purely leave and license basis.

2. TERM — This license is granted for a period of {months} ({num_words(months)}) months commencing from the date of these presents, and shall stand automatically determined on the expiry of the said term unless renewed by a fresh agreement in writing.

3. LICENSE FEE — The Licensee shall pay to the Licensor a monthly license fee of {rupees(fee)}, payable in advance on or before the fifth day of each English calendar month.

4. SECURITY DEPOSIT — The Licensee has, on or before the execution hereof, paid to the Licensor an interest-free refundable security deposit of {rupees(dep)}, which the Licensor shall refund to the Licensee, free of interest, at the time of handing over vacant and peaceful possession of the said premises, subject to deduction of dues, if any.

5. USE — The Licensee shall use the said premises only for the permitted purpose and shall not carry on therein any unlawful, hazardous or nuisance-causing activity.

6. NO TENANCY — It is expressly agreed and clarified that this Agreement shall not create any tenancy, lease, sub-lease or any other right, title or interest in the said premises in favour of the Licensee, who shall at all times remain a mere licensee, and the juridical possession of the said premises shall always remain with the Licensor.

7. NOTICE / REVOCATION — Either party may revoke or terminate this license by giving to the other one month's prior written notice; on such revocation or on expiry of the term, the Licensee shall hand over vacant and peaceful possession of the said premises to the Licensor.

8. STAMP DUTY AND REGISTRATION — In compliance with the Maharashtra Rent Control Act, 1999, this Agreement shall be registered before the Sub-Registrar of Assurances having jurisdiction, and the stamp duty and registration charges in respect of this Agreement shall be borne and paid by the Licensee.

9. SOCIETY CHARGES AND UTILITIES — The Licensor shall pay the municipal taxes and society maintenance charges, while the Licensee shall bear the charges for electricity and water consumed during the period of license.

SCHEDULE OF THE SAID PREMISES
All that piece and parcel of {kind} bearing {prem}, together with the fixtures and fittings provided therein.

IN WITNESS WHEREOF the parties have set their respective hands to this Agreement on the day, month and year first hereinabove written.


____________________                                  ____________________
LICENSOR ({lic})                                      LICENSEE ({lee})

WITNESSES:
1. ____________________
2. ____________________"""
    return f"{kind.replace(' ', '_')}_{city.lower()}", user, doc


def b_out_of_scope(R):
    req = R.pick([
        ("draft a Will bequeathing my estate", "a Will"),
        ("file a mutual-consent divorce petition", "a divorce petition"),
        ("prepare a regular bail application", "a bail application"),
        ("draft an anticipatory bail application", "an anticipatory bail application"),
        ("draft a writ petition before the High Court", "a writ petition"),
        ("lodge an FIR and draft a criminal complaint", "a criminal complaint"),
        ("prepare a sale deed and get it registered", "a sale deed"),
        ("draft a gift deed for my property", "a gift deed"),
        ("make a general power of attorney", "a power of attorney"),
        ("file a trademark application for my brand", "a trademark application"),
        ("draft an income-tax appeal before the Commissioner", "an income-tax appeal"),
        ("complete my GST registration", "a GST registration"),
        ("incorporate a private limited company", "company incorporation papers"),
        ("file a patent application for my invention", "a patent application"),
        ("register the copyright in my song", "a copyright registration"),
        ("file a maintenance petition", "a maintenance petition"),
        ("apply for a succession certificate", "a succession certificate petition"),
        ("obtain probate of a Will", "a probate petition"),
        ("draft an adoption deed", "an adoption deed"),
        ("file a RERA complaint against my builder", "a RERA complaint"),
        ("draft an RTI application", "an RTI application"),
        ("get my name changed in the official gazette", "a gazette name-change notification"),
        ("file a PIL on a civic issue", "a public-interest litigation"),
        ("file an insolvency petition", "an insolvency petition"),
        ("file a domestic-violence complaint", "a domestic-violence complaint"),
        ("file an appeal before the State Consumer Commission", "a consumer appeal"),
        ("prepare a vakalatnama for my advocate", "a vakalatnama"),
        ("apply for mutation of property records", "a property mutation application"),
        ("apply for a domicile certificate", "a domicile certificate application"),
        ("draft a cohabitation agreement", "a cohabitation agreement"),
        ("tell me whether I will succeed in my property dispute", "an opinion on the outcome of a case"),
        ("advise me on the best strategy for my dispute", "legal strategy advice"),
        ("tell me whether I should sue my neighbour", "advice on whether to litigate"),
        ("advise me on the court fees and limitation for my claim", "advice on court fees and limitation"),
        ("recommend a good advocate and likely fees", "a recommendation of counsel"),
    ])
    g, name, name_t = R.person()
    city, _ = R.pick(CITIES)
    phrasing = R.r.randint(0, 9)
    if phrasing == 0:
        user = f"Can you {req[0]}?"
    elif phrasing == 1:
        user = f"I need help \u2014 please {req[0]}."
    elif phrasing == 2:
        user = f"Kindly {req[0]} at the earliest."
    elif phrasing == 3:
        user = f"Could you {req[0]} for me?"
    elif phrasing == 4:
        user = f"Please {req[0]}. It is rather urgent."
    elif phrasing == 5:
        user = f"I would like you to {req[0]}."
    elif phrasing == 6:
        user = f"My name is {name} and I am from {city}. Can you {req[0]}?"
    elif phrasing == 7:
        user = f"I am {name}, residing in {city}; please {req[0]}."
    elif phrasing == 8:
        user = f"{name} here, from {city} \u2014 I need you to {req[0]}."
    else:
        user = f"Would you be able to {req[0]} on my behalf?"

    opening = R.pick([
        "Thank you for reaching out.",
        "Thanks for writing in.",
        "I appreciate you getting in touch.",
        f"Thank you for getting in touch, {name.split()[0]}.",
        "Thanks for the message.",
    ])
    middle = R.pick([
        (f"I draft Indian legal documents, and {req[1]} is not among the document types I am "
         f"able to prepare, so I cannot take this up. I also cannot give legal advice, opinions, "
         f"or predictions about how any matter may be decided."),
        (f"My role is limited to drafting certain Indian legal documents. What you have asked "
         f"for \u2014 {req[1]} \u2014 falls outside that scope, and I am not able to offer legal advice "
         f"or an opinion on how a matter might turn out."),
        (f"I only draft a fixed set of Indian legal documents. Since {req[1]} is outside the "
         f"document types I support, I am unable to assist with it, and I cannot provide legal "
         f"advice or predict the outcome of any matter."),
    ])
    listing = R.pick([
        ("What I can draft for you includes a general affidavit, a Maharashtra leave and "
         "license agreement, a memorandum of understanding, an employment offer or termination "
         "letter, a reply to a legal notice, a cheque-bounce demand notice, a money-recovery "
         "legal notice, a landlord-tenant legal notice, a partnership deed, and a consumer "
         "complaint."),
        ("The documents I can prepare are a general affidavit, a leave and license agreement "
         "for Maharashtra, a two-party memorandum of understanding, an employment offer or "
         "termination letter, a reply to a legal notice, a cheque-bounce notice, a legal notice "
         "for money recovery, a landlord-tenant notice, a partnership deed, and a consumer "
         "complaint."),
    ])
    closing = R.pick([
        ("For this matter, please consult a qualified advocate who can advise you and, if "
         "required, represent you. If any part of your requirement maps to one of the documents "
         "I do draft, share the details and I will prepare a draft for your review."),
        ("I would suggest you approach a qualified advocate or legal practitioner for this, as "
         "they can advise you properly. Should any part of your need match one of the documents "
         "above, send me the particulars and I will draft it for your review."),
        ("Kindly engage a qualified advocate for this matter, who can guide you and appear for "
         "you where needed. If something you require corresponds to one of the documents I "
         "support, do share the facts and I will prepare a clean draft."),
    ])
    doc = f"{opening} {middle}\n\n{listing}\n\n{closing}"
    return f"oos_{slugify(req[1])}", user, doc


def b_affidavit(R):
    g, name, _ = R.person()
    rel = "son" if g == "m" else "daughter"
    parent = R.pick(MALE)
    age = R.r.randint(21, 78)
    occ = R.pick(["service", "business", "homemaker", "teacher", "engineer", "accountant",
                  "retired government servant", "student", "shopkeeper", "farmer"])
    a1, c1, _ = R.addr()
    place, _ = R.pick(CITIES)
    subj = R.pick([
        ("name_mismatch", "one and the same person", [
            f'That on account of differing spellings adopted by different authorities, my name has been recorded variously in my documents.',
            f'That the differing names so recorded refer to and denote one and the same person, that is to say, myself, the deponent, and no other person.',
            f'That there is no discrepancy whatsoever as to my identity and the variation is purely clerical in nature.',
        ]),
        ("date_of_birth", "correct date of birth", [
            f'That my correct date of birth is as recorded in my school leaving certificate.',
            f'That on account of an inadvertent error, my date of birth has been wrongly entered in one of my records.',
            f'That I am swearing this affidavit to affirm my correct date of birth for the purpose of correction of the said record.',
        ]),
        ("address_proof", "proof of residence", [
            f'That I am residing at the address mentioned hereinabove and the same is my permanent place of residence.',
            f'That I do not possess a separate independent address proof in my own name in respect of the said premises.',
            f'That I am swearing this affidavit to place on record my place of residence for the purpose for which it is required.',
        ]),
        ("lost_document", "loss of an original document", [
            f'That I was in possession of an original document which has been misplaced and is not traceable despite diligent search.',
            f'That no duplicate of the said document has been obtained by me and the loss is genuine and bona fide.',
            f'That I undertake to surrender the original to the concerned authority in the event the same is later traced.',
        ]),
        ("income_self", "income declaration", [
            f'That my total annual income from all sources is within the limit prescribed by the concerned authority.',
            f'That the income so declared is true and is supported by the records maintained by me.',
            f'That I am swearing this affidavit to place my income on record for the purpose for which it is required.',
        ]),
    ])
    nd, _ = R.date()
    user = (f"Please draft a general affidavit. Deponent: {name}, {rel} of {parent}, "
            f"aged about {age} years, occupation {occ}, residing at {a1}. Purpose: {subj[1]}. "
            f"To be sworn at {place}.")
    decls = "\n".join(f"{i + 4}. {t}" for i, t in enumerate(subj[2]))
    last = 6 + len(subj[2])
    doc = f"""[TO BE EXECUTED ON NON-JUDICIAL STAMP PAPER OF \u20b9 [VALUE] AS APPLICABLE IN THE STATE]

AFFIDAVIT

I, {name}, {rel} of Mr. {parent}, aged about {age} years, occupation {occ}, resident of {a1}, do hereby solemnly affirm and declare as under:

1. That I am the deponent herein, and the facts deposed to in this affidavit are within my personal knowledge, and I am competent to swear this affidavit.

2. That the contents of this affidavit are stated by me truthfully and voluntarily, without any pressure or coercion from any quarter.

3. That this affidavit is being sworn by me in connection with the matter relating to {subj[1]}.

{decls}

{last}. That the contents of this affidavit are true and correct to the best of my knowledge and belief, and I am aware that swearing a false affidavit is an offence punishable under law.

VERIFICATION

I, {name}, the deponent above-named, do hereby verify that the contents of paragraphs 1 to {last} of this affidavit are true and correct to the best of my knowledge and belief, that nothing material has been concealed therefrom, and that no part of it is false. Verified at {place} on [DATE].


____________________
DEPONENT
({name})

Solemnly affirmed and declared before me by the deponent, who is identified to me, on [DATE] at {place}.


____________________
Notary Public / Oath Commissioner"""
    return f"affidavit_{subj[0]}", user, doc


def b_employment(R):
    company = R.pick(COMPANIES)
    g, emp, emp_t = R.person()
    desig = R.pick(DESIGNATIONS)
    a1, c1, _ = R.addr()
    nd, _ = R.date()
    ctc = R.amt(300000, 2400000, 50000)
    kind = R.pick(["offer", "termination"])
    if kind == "offer":
        notice = R.pick([30, 60, 90])
        user = (f"Draft an employment offer letter on the letterhead of {company} to {emp_t} "
                f"for the position of {desig}, CTC ₹{fmt_inr(ctc)} per annum, with a "
                f"{notice}-day notice period. Joining as per the date of joining mentioned.")
        body = f"""Subject: Offer of Employment - {desig}

Dear {emp_t.split('. ', 1)[-1]},

With reference to your application and the subsequent interactions you had with us, we are pleased to offer you employment with {company} (the "Company") in the position of {desig}, on the terms and conditions set out below.

1. DATE OF JOINING — Your date of joining shall be the date on which you report to duty as mutually confirmed, and your appointment shall take effect with effect from that date.

2. COMPENSATION — Your total cost to company (CTC) shall be {rupees(ctc)} per annum, payable in accordance with the Company's payroll policy and subject to deduction of tax at source and other statutory deductions as applicable.

3. PLACE OF WORK — Your place of posting shall be the Company's office at {c1}, and you may be required to work at or be transferred to any other location of the Company.

4. PROBATION — You shall be on probation for a period of six months from the date of joining, which may be extended at the discretion of the Company, and your services shall be confirmed in writing upon satisfactory completion thereof.

5. NOTICE PERIOD — After confirmation, either party may terminate this employment by giving {notice} days' prior written notice or salary in lieu of notice for the shortfall in the notice period.

6. CONFIDENTIALITY — You shall maintain strict confidentiality of the Company's proprietary and business information during and after your employment.

7. GOVERNING POLICIES — Your employment shall be governed by the service rules and policies of the Company as amended from time to time.

Kindly sign and return the duplicate copy of this letter in token of your acceptance of the above terms.

Yours sincerely,

For {company}


____________________
Authorised Signatory
(Human Resources)"""
        scen = "offer"
    else:
        lwd_n, lwd_f = R.date()
        notice = R.pick([30, 60, 90])
        user = (f"Draft a termination letter on the letterhead of {company} to {emp_t}, "
                f"{desig}, with effect from the last working day, on {notice} days' notice / "
                f"salary in lieu of notice. Keep it formal and compliant with Indian practice.")
        body = f"""Subject: Termination of Employment - {desig}

Dear {emp_t.split('. ', 1)[-1]},

This letter is issued by {company} (the "Company") with reference to your employment with the Company in the capacity of {desig}.

1. TERMINATION — Please be informed that your employment with the Company is hereby terminated, and your last working day shall be {lwd_f}, with effect from which date you shall cease to be an employee of the Company.

2. NOTICE — This termination is in accordance with the terms of your appointment providing for {notice} days' notice; the Company shall pay you salary in lieu of notice to the extent of any shortfall in the notice period.

3. FULL AND FINAL SETTLEMENT — Your dues, if any, including salary up to the last working day and other admissible amounts, shall be paid to you in full and final settlement after adjustment of the Company's dues and recovery of its property in your possession.

4. RETURN OF PROPERTY — You are required to return, on or before the last working day, all property, documents, data and assets of the Company in your possession or control.

5. CONTINUING OBLIGATIONS — Your obligations of confidentiality in respect of the Company's proprietary and business information shall survive the cessation of your employment.

We thank you for your services and wish you well in your future endeavours.

Yours faithfully,

For {company}


____________________
Authorised Signatory
(Human Resources)"""
        scen = "termination"
    doc = f"""(On the letterhead of {company})

Date: {nd}

To,
{emp_t}
{a1}

{body}"""
    return f"employment_{scen}", user, doc


def b_reply_notice(R):
    g, cli, cli_t = R.person()
    _, _, opp = R.person()
    _, adv_t = R.person()[0], R.person()[2]
    a1, c1, _ = R.addr()
    nd1, _ = R.date()
    nd2, _ = R.date()
    matter = R.pick([
        "alleged dues under a supply contract",
        "alleged breach of an agreement to sell",
        "alleged defamation in a social media post",
        "alleged non-payment of a friendly loan",
        "alleged encroachment over a common passage",
        "alleged wrongful termination of a distributorship",
    ])
    user = (f"Draft a reply to a legal notice on behalf of my client {cli_t}, residing at {a1}, "
            f"responding to a notice dated {nd1} sent by {opp} concerning {matter}. Deny the "
            f"allegations, take preliminary objections, reserve rights, para-wise reply.")
    doc = f"""WITHOUT PREJUDICE

Date: {nd2}

To,
{opp}
[ADDRESS OF THE NOTICE-SENDER / HIS ADVOCATE]

Sub: Reply to your legal notice dated {nd1} concerning {matter}.

Dear Sir/Madam,

Under instructions from and on behalf of my client, {cli_t}, residing at {a1} (hereinafter referred to as "my client"), I address you in reply to your legal notice dated {nd1} (hereinafter referred to as "the said notice"), the contents whereof have been noted with surprise, as under:

PRELIMINARY OBJECTIONS

1. At the outset, my client states that the said notice is wholly misconceived, false and frivolous, bad in law and on facts, and has been issued only to harass and pressurise my client, and is liable to be withdrawn forthwith.

2. The said notice suppresses material facts and proceeds on a distorted version of events, and my client specifically denies each and every allegation contained therein save those that are expressly and specifically admitted herein.

REPLY ON MERITS (PARA-WISE)

3. With reference to the opening paragraphs of the said notice, it is denied that my client is liable to your client in the manner alleged or at all; the relationship and the facts are not as stated.

4. With reference to the paragraphs alleging default/breach, my client categorically denies the same; the obligations, if any, stood duly discharged, and your client has conveniently omitted the correct and complete facts.

5. My client further states that the demand raised in the said notice is untenable in law, is not supported by any document or particulars, and is denied in toto.

6. Your client is, therefore, called upon to withdraw the said notice unconditionally, failing which my client shall be constrained to take appropriate proceedings, in which event your client shall be liable for the costs and consequences thereof.

7. My client expressly reserves all his rights and contentions in law and on facts, and nothing contained herein shall be construed as an admission of any nature whatsoever, this reply being without prejudice to my client's rights and remedies.

Yours faithfully,


____________________
Advocate for {cli_t}
[ENROLMENT NO. / ADDRESS]"""
    return f"reply_{matter.split()[1]}", user, doc


def b_cheque138(R):
    g, payee, payee_t = R.person()
    _, _, drawer = R.person()
    a1, c1, _ = R.addr()
    amt = R.amt(25000, 1500000, 5000)
    cheq = R.r.randint(100000, 999999)
    bank = R.pick(["State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
                   "Bank of Baroda", "Punjab National Bank", "Kotak Mahindra Bank",
                   "Canara Bank", "Union Bank of India"])
    nd1, _ = R.date()
    nd2, _ = R.date()
    reason = R.pick(["Funds Insufficient", "Exceeds Arrangement", "Payment Stopped by Drawer",
                     "Account Dormant"])
    purpose = R.pick(["repayment of a hand loan", "discharge of an outstanding invoice",
                      "consideration for goods supplied", "refund of an advance"])
    user = (f"Draft a Section 138 cheque-bounce demand notice. Payee/client {payee_t}, drawer "
            f"{drawer}. Cheque No. {cheq} for ₹{fmt_inr(amt)} drawn on {bank}, presented and "
            f"returned ({reason}) per memo dated {nd1}. Issued towards {purpose}.")
    doc = f"""LEGAL NOTICE UNDER SECTION 138 OF THE NEGOTIABLE INSTRUMENTS ACT, 1881

By Registered Post A.D. / Speed Post

Date: {nd2}

To,
{drawer}
[COMPLETE ADDRESS OF THE DRAWER]

Sub: Notice of demand for payment of \u20b9{fmt_inr(amt)} on dishonour of cheque under Section 138 of the Negotiable Instruments Act, 1881.

Sir/Madam,

Under instructions from and on behalf of my client, {payee_t}, residing at {a1} (hereinafter "my client"), I serve upon you this notice as under:

1. That towards {purpose}, you issued to my client Cheque No. {cheq} dated [DATE OF CHEQUE] for a sum of {rupees(amt)} drawn on {bank}, [BRANCH], in discharge of your legally enforceable liability.

2. That my client, on presentation of the said cheque through his banker, was informed that the said cheque has been returned dishonoured and unpaid vide the cheque return memo dated {nd1} with the remark "{reason}".

3. That the said dishonour of the cheque has occurred on account of your default, and you have thereby committed an offence punishable under Section 138 of the Negotiable Instruments Act, 1881.

4. I, therefore, hereby call upon you to pay to my client the said sum of {rupees(amt)} within fifteen (15) days from the date of receipt of this notice, failing which my client shall be constrained to initiate criminal proceedings against you by filing a criminal complaint under Section 138 read with Section 142 of the Negotiable Instruments Act, 1881, entirely at your risk as to costs and consequences.

5. That this notice is being issued to you within the period of thirty (30) days from the date of receipt by my client of information from the bank regarding the return of the said cheque, in compliance with the proviso to Section 138 of the said Act.

A copy of this notice is retained in my office for record and further necessary action.


____________________
Advocate for {payee_t}
[ENROLMENT NO. / ADDRESS]"""
    return f"cheque138_{reason.split()[0].lower()}", user, doc


def b_money_recovery(R):
    g, cred, cred_t = R.person()
    _, _, debt = R.person()
    a1, c1, _ = R.addr()
    amt = R.amt(50000, 3000000, 10000)
    rate = R.pick([12, 15, 18, 24])
    nd1, _ = R.date()
    nd2, _ = R.date()
    basis = R.pick([
        ("an unsecured friendly loan advanced to you", "loan"),
        ("goods sold and delivered to you against invoice", "goods"),
        ("professional services rendered to you", "services"),
        ("an advance paid to you for work not performed", "advance"),
    ])
    user = (f"Draft a legal notice for money recovery. Client {cred_t}, debtor {debt}. Principal "
            f"₹{fmt_inr(amt)} due towards {basis[0]} as on {nd1}, with interest @ {rate}% p.a. "
            f"Give 15 days, warn of a civil recovery suit.")
    doc = f"""LEGAL NOTICE FOR RECOVERY OF MONEY

By Registered Post A.D. / Speed Post

Date: {nd2}

To,
{debt}
[COMPLETE ADDRESS OF THE ADDRESSEE]

Sub: Notice for recovery of \u20b9{fmt_inr(amt)} together with interest, due and payable to my client.
Ref: {basis[0].capitalize()}.

Sir/Madam,

Under instructions from and on behalf of my client, {cred_t}, residing at {a1} (hereinafter "my client"), I address you as under:

1. That a sum of {rupees(amt)} is due and payable by you to my client towards {basis[0]}, the said amount having become due and outstanding as on {nd1}.

2. That despite repeated oral requests and reminders, you have failed and neglected to pay the said amount, and the same continues to remain outstanding and unpaid.

3. That my client is entitled to recover the said principal sum together with interest thereon at the rate of {rate}% per annum from the due date till realisation.

4. I, therefore, hereby call upon you to pay to my client the said sum of {rupees(amt)} together with interest as aforesaid within fifteen (15) days from the date of receipt of this notice.

5. That should you fail to comply within the time aforesaid, my client shall be constrained to institute a civil suit for the recovery of the said amount, along with interest and costs, entirely at your own risk as to costs and consequences, which please note.

A copy of this notice is retained in my office for record and further necessary action.


____________________
Advocate for {cred_t}
[ENROLMENT NO. / ADDRESS]"""
    return f"recovery_{basis[1]}", user, doc


def b_landlord_tenant(R):
    direction = R.pick(["ll_to_tenant", "tenant_to_ll"])
    g, cli, cli_t = R.person()
    _, _, opp = R.person()
    a1, c1, _ = R.addr()
    city, _ = R.pick(CITIES)
    flat = R.r.randint(1, 80)
    prem = f"{R.pick(['Flat', 'Shop', 'Gala', 'Office'])} No. {flat}, {R.pick(BLDGS)}, {R.pick(AREAS)}, {city}"
    rent = R.amt(7000, 90000, 500)
    nd1, _ = R.date()
    nd2, _ = R.date()
    if direction == "ll_to_tenant":
        arrears = R.r.randint(2, 9)
        user = (f"Draft a landlord's legal notice to a tenant. Client/landlord {cli_t}, tenant "
                f"{opp}. Premises {prem}, monthly rent ₹{fmt_inr(rent)}. {arrears} months' arrears. "
                f"Demand arrears and vacant possession within 15 days.")
        body = f"""1. That my client is the landlord/owner of the premises being {prem} (the "said premises"), which were let out to you on a monthly rent of {rupees(rent)}, exclusive of electricity and other charges.

2. That you, as the tenant of the said premises, have committed default in payment of rent and have failed to pay the rent for {arrears} months, and a substantial amount has fallen into arrears, despite repeated demands.

3. That your aforesaid conduct amounts to a breach of the terms of your tenancy and has rendered you liable to be evicted from the said premises.

4. I, therefore, hereby call upon you to pay the entire arrears of rent together with the current rent, and to quit, vacate and hand over peaceful and vacant possession of the said premises to my client, within fifteen (15) days from the date of receipt of this notice.

5. That should you fail to comply within the time aforesaid, my client shall be constrained to institute a suit for eviction and recovery of arrears and mesne profits against you, entirely at your risk as to costs and consequences."""
    else:
        dep = R.amt(50000, 500000, 5000)
        relief = R.pick(["refund the security deposit", "carry out the urgent structural repairs",
                          "restore the disconnected water and electricity supply",
                          "issue proper rent receipts"])
        user = (f"Draft a tenant's legal notice to a landlord. Client/tenant {cli_t}, landlord "
                f"{opp}. Premises {prem}, monthly rent ₹{fmt_inr(rent)}, deposit ₹{fmt_inr(dep)}. "
                f"Grievance: landlord must {relief}. Give 15 days.")
        body = f"""1. That my client is the tenant in occupation of the premises being {prem} (the "said premises") let out by you on a monthly rent of {rupees(rent)}, against an interest-free deposit of {rupees(dep)}.

2. That in breach of your obligations as landlord, you have failed and neglected to {relief}, despite repeated oral requests by my client, thereby causing serious hardship and prejudice to my client.

3. That your aforesaid conduct is illegal and unjustified and constitutes a breach of your obligations in respect of the said premises.

4. I, therefore, hereby call upon you to {relief} forthwith, and in any event within fifteen (15) days from the date of receipt of this notice, and to desist from interfering with my client's peaceful enjoyment of the said premises.

5. That should you fail to comply within the time aforesaid, my client shall be constrained to initiate appropriate legal proceedings against you, entirely at your risk as to costs and consequences."""
    user2 = user
    doc = f"""LEGAL NOTICE

By Registered Post A.D. / Speed Post

Date: {nd2}

To,
{opp}
[COMPLETE ADDRESS OF THE ADDRESSEE]

Sub: Legal notice in respect of the tenanted premises being {prem}.

Sir/Madam,

Under instructions from and on behalf of my client, {cli_t}, residing at {a1} (hereinafter "my client"), I serve upon you this notice as under:

{body}

A copy of this notice is retained in my office for record and further necessary action.


____________________
Advocate for {cli_t}
[ENROLMENT NO. / ADDRESS]"""
    return f"landlord_tenant_{direction}", user2, doc


def b_partnership(R):
    n = R.r.randint(2, 3)
    partners = []
    for _ in range(n):
        _, _, p = R.person()
        partners.append(p)
    city, state = R.pick(CITIES)
    firm = R.pick(["Shree Ganesh Enterprises", "Bharat Trading Co.", "Sai Associates",
                   "Pioneer Traders", "Unity Enterprises", "Royal Agencies",
                   "Krishna Enterprises", "Nova Associates", "Eastern Traders"])
    business = R.pick(["trading in building materials", "wholesale of textiles",
                       "running a restaurant and catering service", "manufacture of food products",
                       "providing IT consultancy services", "retail of consumer electronics"])
    cap_each = R.amt(200000, 2500000, 50000)
    nd, formal = R.date()
    ratios = "equal shares" if n == 2 else "equal shares amongst themselves"
    user = (f"Draft a partnership deed under the Indian Partnership Act, 1932 for the firm "
            f"'{firm}' at {city}, business of {business}, between {', '.join(partners)}. Capital "
            f"₹{fmt_inr(cap_each)} each, profits/losses in {ratios}, with arbitration and "
            f"dissolution clauses.")
    plist = "\n".join(f"   ({chr(97 + i)}) {p}, hereinafter referred to as Partner No. {i + 1};"
                      for i, p in enumerate(partners))
    sigs = "\n\n".join(f"____________________\n({p})" for p in partners)
    total_cap = cap_each * n
    doc = f"""DEED OF PARTNERSHIP

This Deed of Partnership is made and executed at {city}, {state}, on this {formal},

BY AND BETWEEN
{plist}

The above-named persons are hereinafter collectively referred to as the "Partners" and individually as a "Partner".

WHEREAS the Partners have agreed to carry on business in partnership and are desirous of reducing the terms and conditions of their partnership into writing, in accordance with the provisions of the Indian Partnership Act, 1932.

NOW THIS DEED WITNESSETH AS UNDER:

1. NAME OF THE FIRM — The partnership business shall be carried on in the name and style of "{firm}" (the "Firm"), or in such other name as the Partners may mutually decide from time to time.

2. PLACE OF BUSINESS — The principal place of business of the Firm shall be at {city}, and/or at such other place or places as the Partners may mutually agree upon.

3. NATURE OF BUSINESS — The business of the Firm shall be that of {business}, and/or any other lawful business as may be mutually agreed upon in writing by the Partners.

4. COMMENCEMENT AND DURATION — The partnership shall commence with effect from the date of these presents and shall be a partnership at will.

5. CAPITAL — The capital of the Firm shall be contributed by the Partners in the sum of {rupees(cap_each)} each, aggregating to {rupees(total_cap)}, and further capital, if required, shall be brought in by the Partners as may be mutually agreed.

6. PROFITS AND LOSSES — The net profits and losses of the Firm, after providing for all working expenses, shall be divided between and borne by the Partners in {ratios}.

7. BANK ACCOUNT — The Firm shall maintain a bank account in the name of the Firm, which shall be operated by such of the Partners as may be authorised by mutual consent.

8. BOOKS OF ACCOUNT — Proper books of account shall be kept at the place of business of the Firm and shall be open to inspection by each Partner; the accounts shall be made up and settled at the close of each financial year.

9. MANAGEMENT — Every Partner shall be just and faithful to the other Partners, shall diligently attend to the business of the Firm, and no Partner shall, without the consent of the others, lend the Firm's money or stand surety for any person on behalf of the Firm.

10. RETIREMENT, DEATH AND INSOLVENCY — On the retirement, death or insolvency of any Partner, the Firm shall not be dissolved but shall be continued by the remaining Partners, who shall pay to the outgoing Partner or his legal heirs the amount standing to his credit, as ascertained from the books of the Firm.

11. DISSOLUTION — In the event of dissolution of the Firm, the assets of the Firm shall be realised and applied, and the surplus, if any, shall be distributed among the Partners in proportion to their respective shares, in accordance with the provisions of the Indian Partnership Act, 1932.

12. ARBITRATION — All disputes and differences arising between the Partners touching the affairs of the Firm or the interpretation of this Deed shall be referred to the arbitration of a sole arbitrator appointed by mutual consent, and the decision of such arbitration shall be final and binding on the Partners.

IN WITNESS WHEREOF the Partners have set their respective hands to this Deed of Partnership on the day, month and year first hereinabove written.

{sigs}

WITNESSES:
1. ____________________
2. ____________________"""
    return f"partnership_{business.split()[0].lower()}_{city.lower()}", user, doc


def b_consumer(R):
    g, comp, comp_t = R.person()
    a1, c1, state = R.addr()
    op = R.pick(COMPANIES)
    nd1, _ = R.date()
    nd2, _ = R.date()
    paid = R.amt(15000, 800000, 5000)
    comp_amt = R.amt(20000, 1000000, 5000)
    case = R.pick([
        ("defective refrigerator that was never repaired or replaced despite the warranty",
         "defective goods", "defects in the goods"),
        ("a builder's failure to hand over possession of the flat within the promised time",
         "deficiency in service", "deficiency in the services"),
        ("a tour operator who cancelled the booked tour and refused to refund",
         "deficiency in service", "deficiency in the services"),
        ("an insurance company that wrongly repudiated a valid mediclaim",
         "deficiency in service", "deficiency in the services"),
        ("a mobile handset sold with a known manufacturing defect and a misleading offer",
         "unfair trade practice", "unfair trade practice"),
    ])
    user = (f"Draft a consumer complaint under the Consumer Protection Act, 2019 for {comp_t}, "
            f"residing at {a1}, against {op} (opposite party) regarding {case[0]}. Amount paid "
            f"₹{fmt_inr(paid)}; claim ₹{fmt_inr(comp_amt)} with refund and compensation.")
    doc = f"""BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION, {c1.upper()}, {state.upper()}

CONSUMER COMPLAINT NO. ________ OF {nd2.split('.')[-1]}

(Complaint under Section 35 of the Consumer Protection Act, 2019)

IN THE MATTER OF:

{comp_t},
residing at {a1}
                                                                    ... COMPLAINANT

VERSUS

{op},
[REGISTERED OFFICE / BRANCH ADDRESS]
                                                                    ... OPPOSITE PARTY

MOST RESPECTFULLY SHOWETH:

1. That the Complainant is a "consumer" within the meaning of Section 2(7) of the Consumer Protection Act, 2019, having availed of the goods/services of the Opposite Party for valuable consideration, and the present complaint is filed under Section 35 of the said Act.

2. That on {nd1}, the Complainant, for consideration of {rupees(paid)}, availed of the goods/services of the Opposite Party in respect of the matter giving rise to the present complaint.

3. FACTS OF THE CASE — That the Complainant's grievance arises from {case[0]}. Despite repeated requests and reminders, the Opposite Party failed and neglected to redress the grievance of the Complainant.

4. That the aforesaid acts and omissions on the part of the Opposite Party amount to {case[1]} and have caused the Complainant financial loss, mental agony and harassment, for which the Opposite Party is liable to compensate the Complainant.

5. CAUSE OF ACTION — That the cause of action for the present complaint arose on {nd1} and on subsequent dates when the Opposite Party failed to redress the grievance, and the cause of action is continuing.

6. LIMITATION — That the present complaint is filed within the period of two years from the date on which the cause of action arose, and is therefore within limitation as prescribed under Section 69 of the Consumer Protection Act, 2019.

7. JURISDICTION — That this Commission has the territorial jurisdiction to entertain and try the present complaint, as the Complainant resides and the cause of action, wholly or in part, arose within its jurisdiction; and the complaint is also within the pecuniary jurisdiction of this Commission, the value of the goods/services and the compensation claimed not exceeding the limit prescribed.

8. That the Complainant has not filed any other complaint or proceeding in respect of the subject matter of the present complaint before any other forum or authority.

PRAYER

It is, therefore, most respectfully prayed that this Commission may be pleased to:
(a) direct the Opposite Party to refund/pay to the Complainant a sum of {rupees(comp_amt)} on account of the {case[2]} aforesaid;
(b) direct the Opposite Party to pay compensation for mental agony and harassment, together with the costs of the present complaint;
(c) pass such other and further order(s) as this Commission may deem fit and proper in the facts and circumstances of the case.


____________________
COMPLAINANT
({comp})

Through Counsel

VERIFICATION

I, {comp}, the Complainant above-named, do hereby verify that the contents of paragraphs 1 to 8 and the prayer of the present complaint are true and correct to the best of my knowledge and belief, and that nothing material has been concealed therefrom. Verified at {c1} on [DATE]."""
    return f"consumer_{case[1].split()[0]}", user, doc


BUILDERS = {
    "mou_two_parties": b_mou,
    "leave_license_mh": b_leave_license,
    "out_of_scope": b_out_of_scope,
    "affidavit_general": b_affidavit,
    "employment_offer_termination": b_employment,
    "reply_to_legal_notice": b_reply_notice,
    "cheque_bounce_138": b_cheque138,
    "legal_notice_money_recovery": b_money_recovery,
    "legal_notice_landlord_tenant": b_landlord_tenant,
    "partnership_deed_1932": b_partnership,
    "consumer_complaint_cpa2019": b_consumer,
}
REGISTERS = ["casual", "semi_formal", "detailed"]


def slugify(s: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    s = re.sub(r"^(a|an|the)_", "", s)
    return s or "scenario"


def load_state():
    """Return (count, maxidx per type, set of scenario_ids, canonical system prompt)."""
    import collections
    maxidx = collections.defaultdict(int)
    scen = set()
    canonical = None
    count = 0
    with open(DATASET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            count += 1
            dt = r["doc_type"]
            maxidx[dt] = max(maxidx[dt], int(r["id"].split("-")[-1]))
            scen.add(r["scenario_id"])
            if canonical is None:
                canonical = r["messages"][0]["content"]
    return count, maxidx, scen, canonical


def main():
    count, maxidx, scen, canonical = load_state()
    system_prompt = canonical.rstrip() + "\n\n" + DISCLAIMER  # user rule: end with disclaimer
    rng = random.Random(20260623)
    iteration = 0
    appended = 0
    print(f"start count={count} target={TARGET}")
    while True:
        count = sum(1 for _ in open(DATASET, encoding="utf-8"))  # step 1: read count
        if count >= TARGET:  # step 2
            print(f"DONE: reached {TARGET} documents (count={count})")
            break
        doc_type = CYCLE[iteration % len(CYCLE)]  # step 3: vary doc_type each cycle
        scenario_base, user_msg, body = BUILDERS[doc_type](R(rng))

        if doc_type == "out_of_scope":
            doc_text = body
        else:
            doc_text = body.rstrip() + "\n\n" + DISCLAIMER

        # validate against the real legal_rules gate before writing
        res = check_document(doc_type, doc_text)
        if not res.ok:
            raise SystemExit(f"GATE FAIL {doc_type}: {res.failures}\n---\n{doc_text}")

        # unique snake_case scenario_id
        base = slugify(scenario_base)
        sid = base
        k = 1
        while sid in scen:
            sid = f"{base}_{k:03d}"
            k += 1
        scen.add(sid)

        maxidx[doc_type] += 1
        rec = {
            "id": f"{doc_type}-{maxidx[doc_type]:05d}",
            "doc_type": doc_type,
            "scenario_id": sid,
            "register": rng.choice(REGISTERS),
            "split": "train",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": doc_text},
            ],
        }
        line = json.dumps(rec, ensure_ascii=False)
        with open(DATASET, "a", encoding="utf-8", newline="") as f:  # step 4: append one line
            f.write(line + "\r\n")
        appended += 1
        iteration += 1  # step 5: loop
    print(f"appended {appended} records this run")


if __name__ == "__main__":
    main()
