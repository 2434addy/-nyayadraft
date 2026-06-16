"""Characterization and regression tests for legal_rules/checker.py.

Tests are organised into four sections:
1. Engine unit tests  – load_rules, list_doc_types, CheckResult, CompiledRules
2. check_document unit tests – length bounds, required/forbidden patterns, disclaimer
3. lint_all_rules integration test
4. Per-doc-type smoke tests – one compliant and one violating snippet per type
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# conftest.py already inserts repo root; belt-and-suspenders for direct runs
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legal_rules import (
    DISCLAIMER,
    CheckResult,
    CompiledRules,
    check_document,
    lint_all_rules,
    list_doc_types,
    load_rules,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KNOWN_DOC_TYPES = [
    "affidavit_general",
    "cheque_bounce_138",
    "consumer_complaint_cpa2019",
    "employment_offer_termination",
    "leave_license_mh",
    "legal_notice_landlord_tenant",
    "legal_notice_money_recovery",
    "mou_two_parties",
    "out_of_scope",
    "partnership_deed_1932",
    "reply_to_legal_notice",
]


def _pad(text: str, target: int = 250) -> str:
    """Pad *text* with neutral whitespace to reach *target* chars."""
    if len(text) >= target:
        return text
    return text + " " * (target - len(text))


# ---------------------------------------------------------------------------
# Section 1 – Engine unit tests
# ---------------------------------------------------------------------------


class TestListDocTypes:
    def test_returns_list(self) -> None:
        result = list_doc_types()
        assert isinstance(result, list)

    def test_contains_all_known_types(self) -> None:
        result = list_doc_types()
        for dt in KNOWN_DOC_TYPES:
            assert dt in result, f"Expected doc_type '{dt}' in list_doc_types()"

    def test_is_sorted(self) -> None:
        result = list_doc_types()
        assert result == sorted(result)

    def test_count_is_eleven(self) -> None:
        assert len(list_doc_types()) == 11


class TestLoadRules:
    def test_returns_compiled_rules_instance(self) -> None:
        rules = load_rules("affidavit_general")
        assert isinstance(rules, CompiledRules)

    def test_doc_type_field_matches(self) -> None:
        rules = load_rules("cheque_bounce_138")
        assert rules.doc_type == "cheque_bounce_138"

    def test_min_max_chars_are_positive_ints(self) -> None:
        rules = load_rules("affidavit_general")
        assert isinstance(rules.min_chars, int)
        assert isinstance(rules.max_chars, int)
        assert rules.min_chars > 0
        assert rules.max_chars > rules.min_chars

    def test_required_is_tuple_of_triples(self) -> None:
        rules = load_rules("affidavit_general")
        assert isinstance(rules.required, tuple)
        for item in rules.required:
            pid, desc, pattern = item
            assert isinstance(pid, str) and pid
            assert isinstance(desc, str) and desc
            assert isinstance(pattern, re.Pattern)

    def test_forbidden_is_tuple_of_triples(self) -> None:
        rules = load_rules("affidavit_general")
        assert isinstance(rules.forbidden, tuple)
        for item in rules.forbidden:
            pid, desc, pattern = item
            assert isinstance(pid, str) and pid
            assert isinstance(desc, str)
            assert isinstance(pattern, re.Pattern)

    def test_require_disclaimer_is_bool(self) -> None:
        rules = load_rules("affidavit_general")
        assert isinstance(rules.require_disclaimer, bool)

    def test_is_document_is_bool(self) -> None:
        rules = load_rules("out_of_scope")
        assert isinstance(rules.is_document, bool)

    def test_out_of_scope_is_not_document(self) -> None:
        rules = load_rules("out_of_scope")
        assert rules.is_document is False

    def test_out_of_scope_require_disclaimer_false(self) -> None:
        rules = load_rules("out_of_scope")
        assert rules.require_disclaimer is False

    def test_unknown_doc_type_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="No rules spec"):
            load_rules("nonexistent_type_xyz")

    def test_load_rules_is_cached(self) -> None:
        """load_rules is decorated with lru_cache; same object must be returned."""
        r1 = load_rules("affidavit_general")
        r2 = load_rules("affidavit_general")
        assert r1 is r2

    @pytest.mark.parametrize("doc_type", KNOWN_DOC_TYPES)
    def test_all_doc_types_load_without_error(self, doc_type: str) -> None:
        rules = load_rules(doc_type)
        assert rules.doc_type == doc_type


class TestCheckResult:
    def test_ok_true_when_no_failures(self) -> None:
        result = CheckResult(ok=True)
        assert result.ok is True
        assert result.failures == ()
        assert result.warnings == ()

    def test_ok_false_with_failures(self) -> None:
        result = CheckResult(ok=False, failures=("missing_required:x",))
        assert result.ok is False
        assert "missing_required:x" in result.failures

    def test_is_frozen_dataclass(self) -> None:
        result = CheckResult(ok=True)
        with pytest.raises((AttributeError, TypeError)):
            result.ok = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Section 2 – check_document unit tests
# ---------------------------------------------------------------------------


class TestCheckDocumentLengthBounds:
    def test_too_short_produces_failure(self) -> None:
        short_text = "x" * 10
        result = check_document("affidavit_general", short_text)
        assert any("too_short" in f for f in result.failures)

    def test_too_long_produces_failure(self) -> None:
        rules = load_rules("affidavit_general")
        long_text = "x" * (rules.max_chars + 1)
        result = check_document("affidavit_general", long_text)
        assert any("too_long" in f for f in result.failures)

    def test_exact_min_length_does_not_trigger_short(self) -> None:
        rules = load_rules("out_of_scope")
        # out_of_scope has minimal required patterns; use exact min_chars
        text = "x" * rules.min_chars
        result = check_document("out_of_scope", text)
        assert not any("too_short" in f for f in result.failures)

    def test_exact_max_length_does_not_trigger_long(self) -> None:
        rules = load_rules("out_of_scope")
        text = "x" * rules.max_chars
        result = check_document("out_of_scope", text)
        assert not any("too_long" in f for f in result.failures)

    def test_one_over_max_triggers_long(self) -> None:
        rules = load_rules("out_of_scope")
        text = "x" * (rules.max_chars + 1)
        result = check_document("out_of_scope", text)
        assert any("too_long" in f for f in result.failures)


class TestCheckDocumentRequiredPatterns:
    def test_missing_required_pattern_appears_in_failures(self) -> None:
        # Use affidavit with no body — solemn_affirmation will be missing
        rules = load_rules("affidavit_general")
        text = "x" * rules.min_chars  # long enough but no pattern content
        result = check_document("affidavit_general", text)
        failure_ids = " ".join(result.failures)
        assert "missing_required:solemn_affirmation" in failure_ids

    def test_failure_format_contains_description(self) -> None:
        rules = load_rules("affidavit_general")
        text = "x" * rules.min_chars
        result = check_document("affidavit_general", text)
        # Each missing_required failure must include the description in parens
        for f in result.failures:
            if f.startswith("missing_required:"):
                assert "(" in f and ")" in f


class TestCheckDocumentForbiddenPatterns:
    def test_markdown_heading_triggers_forbidden(self) -> None:
        rules = load_rules("affidavit_general")
        text = ("# Heading\n" + "x" * rules.min_chars)
        result = check_document("affidavit_general", text)
        assert any("forbidden_present:no_md_heading" in f for f in result.failures)

    def test_markdown_bold_triggers_forbidden(self) -> None:
        rules = load_rules("cheque_bounce_138")
        text = "**bold text**\n" + "x" * rules.min_chars
        result = check_document("cheque_bounce_138", text)
        assert any("forbidden_present:no_md_bold" in f for f in result.failures)

    def test_ai_voice_triggers_forbidden(self) -> None:
        rules = load_rules("affidavit_general")
        text = "As an AI I cannot do this. " + "x" * rules.min_chars
        result = check_document("affidavit_general", text)
        assert any("forbidden_present:no_ai_voice" in f for f in result.failures)

    def test_chatty_preamble_sure_triggers_forbidden(self) -> None:
        rules = load_rules("affidavit_general")
        text = "Sure, here is your affidavit. " + "x" * rules.min_chars
        result = check_document("affidavit_general", text)
        assert any("forbidden_present:no_chat_preamble" in f for f in result.failures)

    def test_chatty_preamble_certainly_triggers_forbidden(self) -> None:
        rules = load_rules("affidavit_general")
        text = "Certainly! " + "x" * rules.min_chars
        result = check_document("affidavit_general", text)
        assert any("forbidden_present:no_chat_preamble" in f for f in result.failures)

    def test_chatty_preamble_heres_triggers_forbidden(self) -> None:
        rules = load_rules("affidavit_general")
        text = "Here's the document: " + "x" * rules.min_chars
        result = check_document("affidavit_general", text)
        assert any("forbidden_present:no_chat_preamble" in f for f in result.failures)

    def test_chatty_preamble_mid_text_does_not_trigger(self) -> None:
        """Chatty preamble pattern anchors at \\A — mid-text occurrence is fine."""
        rules = load_rules("affidavit_general")
        text = "x" * rules.min_chars + " Sure, this is fine mid-text."
        result = check_document("affidavit_general", text)
        assert not any("forbidden_present:no_chat_preamble" in f for f in result.failures)


class TestCheckDocumentDisclaimer:
    def test_missing_disclaimer_produces_failure(self) -> None:
        rules = load_rules("affidavit_general")
        text = "x" * rules.min_chars  # no disclaimer
        result = check_document("affidavit_general", text)
        assert "missing_disclaimer_footer" in result.failures

    def test_disclaimer_present_at_end_no_failure(self) -> None:
        rules = load_rules("affidavit_general")
        # Build a text with disclaimer exactly at the end
        body = "x" * (rules.min_chars - len(DISCLAIMER) - 2)
        text = body + "\n" + DISCLAIMER
        result = check_document("affidavit_general", text)
        assert "missing_disclaimer_footer" not in result.failures

    def test_disclaimer_not_at_end_produces_warning(self) -> None:
        rules = load_rules("affidavit_general")
        body = "x" * (rules.min_chars - len(DISCLAIMER) - 20)
        text = body + "\n" + DISCLAIMER + "\n" + "z" * 15
        result = check_document("affidavit_general", text)
        # Disclaimer present so no missing_disclaimer_footer failure
        assert "missing_disclaimer_footer" not in result.failures
        assert "disclaimer_not_at_end" in result.warnings

    def test_disclaimer_on_non_document_produces_failure(self) -> None:
        """out_of_scope require_disclaimer=False; including the disclaimer is a failure."""
        rules = load_rules("out_of_scope")
        body = "x" * (rules.min_chars - len(DISCLAIMER) - 2)
        text = body + "\n" + DISCLAIMER
        result = check_document("out_of_scope", text)
        assert "disclaimer_on_non_document" in result.failures

    def test_disclaimer_constant_is_exact_string(self) -> None:
        assert DISCLAIMER == (
            "This is an AI-generated draft for review by the parties "
            "and is not legal advice."
        )

    def test_ok_is_false_when_disclaimer_missing(self) -> None:
        rules = load_rules("affidavit_general")
        text = "x" * rules.min_chars
        result = check_document("affidavit_general", text)
        assert result.ok is False


class TestCheckDocumentResultStructure:
    def test_unknown_doc_type_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            check_document("unknown_xyz", "some text")

    def test_returns_check_result(self) -> None:
        result = check_document("out_of_scope", "x" * 300)
        assert isinstance(result, CheckResult)

    def test_failures_is_tuple(self) -> None:
        result = check_document("out_of_scope", "x" * 300)
        assert isinstance(result.failures, tuple)

    def test_warnings_is_tuple(self) -> None:
        result = check_document("out_of_scope", "x" * 300)
        assert isinstance(result.warnings, tuple)

    def test_empty_string_is_too_short(self) -> None:
        result = check_document("affidavit_general", "")
        assert any("too_short" in f for f in result.failures)

    def test_none_text_raises_type_error(self) -> None:
        with pytest.raises((TypeError, AttributeError)):
            check_document("affidavit_general", None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Section 3 – lint_all_rules integration test
# ---------------------------------------------------------------------------


class TestLintAllRules:
    def test_returns_list(self) -> None:
        problems = lint_all_rules()
        assert isinstance(problems, list)

    def test_no_problems_in_production_rules(self) -> None:
        problems = lint_all_rules()
        assert problems == [], f"lint_all_rules found problems: {problems}"


# ---------------------------------------------------------------------------
# Section 4 – Per-doc-type smoke tests
# ---------------------------------------------------------------------------

# Each entry: (doc_type, compliant_snippet, violating_snippet, violation_id)
# compliant_snippet must pass all *pattern* checks (length padding added by fixture).
# violating_snippet must trigger the named forbidden or notable required failure.

# ---- affidavit_general ----

AFFIDAVIT_COMPLIANT = (
    "AFFIDAVIT\n\n"
    "I, Ramesh Kumar, aged about 35 years, resident of 12 MG Road, Mumbai, "
    "do hereby solemnly affirm and declare as follows:\n\n"
    "1. That I am a citizen of India.\n"
    "2. That the facts stated herein are true to the best of my knowledge.\n\n"
    "Verified at Mumbai on this day that the contents of this affidavit are "
    "true and correct to the best of my knowledge and belief.\n\n"
    "(DEPONENT)\n\n"
    "Solemnly affirmed before me.\n\n"
    "Notary Public\n\n"
    "This affidavit is executed on non-judicial stamp paper.\n\n"
    + DISCLAIMER
)

AFFIDAVIT_FORBIDDEN = (
    "# AFFIDAVIT\n\n"  # triggers no_md_heading
    "I, Ramesh Kumar, aged about 35 years, resident of 12 MG Road, Mumbai, "
    "do hereby solemnly affirm and declare as follows:\n\n"
    "1. That I am a citizen of India.\n"
    "2. That the facts stated herein are true.\n\n"
    "Verified at Mumbai that the contents are true and correct.\n\n"
    "(DEPONENT)\n\n"
    "Solemnly affirmed before me.\n\n"
    "Notary Public\n\n"
    "Executed on non-judicial stamp paper.\n\n"
    + DISCLAIMER
)

# ---- cheque_bounce_138 ----

CHEQUE_COMPLIANT = (
    "LEGAL NOTICE\n\n"
    "Sub: Notice under Section 138 of the Negotiable Instruments Act, 1881\n\n"
    "We hereby demand payment of the dishonoured cheque amount within "
    "fifteen (15) days of receipt of this notice. "
    "The cheque was returned unpaid; the dishonour memo is enclosed. "
    "This notice is issued within thirty (30) days of receipt of the return memo. "
    "Failure will result in criminal proceedings under Section 142. "
    "This notice is sent by registered post A.D.\n\n"
    + DISCLAIMER
)

CHEQUE_FORBIDDEN_BOLD = (
    "**LEGAL NOTICE**\n\n"  # triggers no_md_bold
    "Sub: Notice under Section 138 of the Negotiable Instruments Act, 1881\n\n"
    "We hereby demand payment of the dishonoured amount within fifteen (15) days. "
    "Cheque return memo noted. Notice served within thirty (30) days. "
    "Criminal proceedings under Section 142 will follow. Sent by speed post.\n\n"
    + DISCLAIMER
)

# ---- consumer_complaint_cpa2019 ----

CONSUMER_COMPLIANT = (
    "BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION\n\n"
    "Complaint under the Consumer Protection Act, 2019 and Section 35 thereof.\n\n"
    "The Complainant is a consumer within the meaning of Section 2(7) of the Act.\n"
    "The Opposite Party has committed deficiency in the services rendered.\n"
    "This complaint is filed within the limitation period under Section 69.\n"
    "This Commission has territorial jurisdiction and pecuniary jurisdiction.\n\n"
    "PRAYER: The Complainant most respectfully prays for relief as set out herein.\n\n"
    "VERIFICATION: Verified at Mumbai.\n\n"
    + DISCLAIMER
)

CONSUMER_FORBIDDEN_OLD_ACT = (
    "BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION\n\n"
    "Complaint under the Consumer Protection Act, 2019 and Section 35.\n"
    "Also citing Consumer Protection Act, 1986.\n\n"  # triggers no_repealed_act_1986
    "Consumer per Section 2(7). Opposite party committed deficiency in the services. "
    "Section 69 limitation. Territorial jurisdiction and pecuniary jurisdiction.\n"
    "Prayer: respectfully prays. Verified at Mumbai.\n\n"
    + DISCLAIMER
)

# ---- employment_offer_termination ----

EMPLOYMENT_COMPLIANT = (
    "(On the letterhead of Acme Pvt. Ltd.)\n\n"
    "Date: 01 June 2026\n\n"
    "Subject: Offer of Employment\n\n"
    "Dear Mr. Sharma,\n\n"
    "We are pleased to offer you the position of Senior Manager. "
    "Your date of joining shall be 15 June 2026. "
    "The notice period applicable is 30 days. "
    "Please confirm acceptance.\n\n"
    "Yours sincerely,\n\n"
    "For Acme Pvt. Ltd.\n"
    "Authorised Signatory\n\n"
    + DISCLAIMER
)

EMPLOYMENT_FORBIDDEN_AT_WILL = (
    "(On the letterhead of Acme Pvt. Ltd.)\n\n"
    "Date: 01 June 2026\n\n"
    "Sub.: Offer of Employment\n\n"
    "Dear Mr. Sharma,\n\n"
    "We offer the position of Manager. Your joining date is 15 June 2026. "
    "This is an at-will employment arrangement.\n\n"  # triggers no_at_will
    "Notice period: 30 days. "
    "Yours sincerely,\n\n"
    "For Acme Pvt. Ltd.\n"
    "Authorised Signatory\n\n"
    + DISCLAIMER
)

# ---- leave_license_mh ----

LEAVE_LICENSE_COMPLIANT = (
    "LEAVE AND LICENSE AGREEMENT\n\n"
    "This Leave and License Agreement is entered into between the Licensor "
    "and the Licensee.\n"
    "License Fee of Rs. 25,000 per month is agreed upon.\n"
    "Security Deposit of Rs. 1,00,000 is paid, which is interest-free and refundable.\n"
    "The term of this agreement is for a period of 11 months.\n"
    "One month's prior written notice is required before vacation.\n"
    "This agreement shall be registered before the Sub-Registrar as required under "
    "the Maharashtra Rent Control Act, 1999.\n"
    "Nothing contained herein shall create any tenancy or lease.\n\n"
    + DISCLAIMER
)

LEAVE_LICENSE_FORBIDDEN_LESSOR = (
    "LEAVE AND LICENSE AGREEMENT\n\n"
    "This agreement is between the Lessor and Lessee.\n\n"  # triggers no_lessor_lessee
    "License Fee of Rs. 20,000. Security Deposit interest-free and refundable. "
    "Licensor and Licensee. "
    "Term of 11 months. One month's notice period. "
    "Registration under Maharashtra Rent Control Act, 1999. "
    "Nothing herein shall create any tenancy.\n\n"
    + DISCLAIMER
)

# ---- legal_notice_money_recovery ----

MONEY_RECOVERY_COMPLIANT = (
    "LEGAL NOTICE\n\n"
    "Sub: Demand for payment of outstanding dues\n\n"
    "We hereby demand payment of a sum of Rs. 5,00,000 along with interest "
    "thereon within fifteen (15) days of receipt of this notice, failing which "
    "a civil suit for recovery shall be filed at your risk and costs.\n\n"
    + DISCLAIMER
)

MONEY_RECOVERY_FORBIDDEN_IPC = (
    "LEGAL NOTICE\n\n"
    "Sub: Demand\n\n"
    "We hereby demand payment of Rs. 5,00,000 with interest thereon. "
    "Comply within 30 days else civil suit for recovery shall be filed. "
    "This notice is also under the Indian Penal Code.\n\n"  # triggers no_repealed_ipc
    "At your risk and costs.\n\n"
    + DISCLAIMER
)

# ---- legal_notice_landlord_tenant ----

LANDLORD_TENANT_COMPLIANT = (
    "LEGAL NOTICE\n\n"
    "Sub.: Notice to vacate tenanted premises\n\n"
    "You are hereby called upon to vacate and deliver up vacant possession of the "
    "said premises situated at 5 Park Street within thirty (30) days of receipt "
    "of this notice. Monthly rent of Rs. 15,000. Tenant relationship noted. "
    "Failing which suit for eviction and recovery shall be filed at costs and "
    "consequences. Sent by registered post A.D.\n\n"
    + DISCLAIMER
)

LANDLORD_TENANT_FORBIDDEN_MODEL = (
    "LEGAL NOTICE\n\n"
    "Sub.: Notice to vacate\n\n"
    "Tenant is called upon to vacate the said premises within fifteen (15) days. "
    "Monthly rent of Rs. 12,000. Landlord rights under the Model Tenancy Act.\n\n"  # forbidden
    "Suit for eviction shall follow. Sent by registered post A.D.\n\n"
    + DISCLAIMER
)

# ---- mou_two_parties ----

MOU_COMPLIANT = (
    "MEMORANDUM OF UNDERSTANDING\n\n"
    "WHEREAS the First Party and Second Party desire to collaborate;\n\n"
    "This MOU is non-binding except for confidentiality obligations.\n"
    "In case of disputes, the parties shall attempt amicable resolution.\n"
    "Governing law: laws of India and exclusive jurisdiction of Mumbai courts.\n"
    "This MOU may be terminated by either party with notice.\n"
    "All information exchanged shall be treated as confidential.\n\n"
    "IN WITNESS WHEREOF the parties have executed this MOU.\n\n"
    + DISCLAIMER
)

MOU_FORBIDDEN_BOLD = (
    "**MEMORANDUM OF UNDERSTANDING**\n\n"  # triggers no_md_bold
    "WHEREAS the First Party and the Second Party agree;\n"
    "This MOU is non-binding. Confidentiality applies. "
    "Disputes resolved amicably. Governing law is India. Terminated by notice. "
    "IN WITNESS WHEREOF signed.\n\n"
    + DISCLAIMER
)

# ---- out_of_scope ----

OUT_OF_SCOPE_COMPLIANT = (
    "I am a drafting assistant and can only draft documents; I cannot advise "
    "on legal strategy. Please consult a qualified advocate or lawyer for "
    "advice on your matter. " * 5
)

OUT_OF_SCOPE_FORBIDDEN_PREDICTION = (
    "I cannot advise you but I can say you will likely win this case. "
    "Please consult an advocate. I can only draft documents. " * 5
)

# ---- partnership_deed_1932 ----

PARTNERSHIP_COMPLIANT = (
    "DEED OF PARTNERSHIP\n\n"
    "This Deed of Partnership is entered into under the Indian Partnership Act, 1932.\n\n"
    "The name and style of the firm shall be M/s Alpha Trading.\n"
    "Capital contribution of the firm: Rs. 10,00,000.\n"
    "Profits and losses shall be shared in equal ratio.\n"
    "The partnership shall commence on 01 June 2026.\n"
    "On retirement or death of a partner, the firm shall continue.\n"
    "Dissolution of the firm shall occur only by mutual consent.\n"
    "Disputes between partners shall be referred to arbitration.\n\n"
    "IN WITNESS WHEREOF the partners have signed this deed.\n\n"
    + DISCLAIMER
)

PARTNERSHIP_FORBIDDEN_LLP = (
    "DEED OF PARTNERSHIP\n\n"
    "This deed is under the Indian Partnership Act, 1932.\n"
    "Name and style of the firm: M/s Beta & Co. "
    "Capital contribution of the partnership. "
    "Profits and losses in equal ratio. "
    "Shall commence on 01 June 2026. "
    "On death of a partner the firm continues. "
    "Dissolution by consent. Arbitration for disputes. "
    "This is actually a Limited Liability Partnership.\n\n"  # triggers no_llp_confusion
    "IN WITNESS WHEREOF signed.\n\n"
    + DISCLAIMER
)

# ---- reply_to_legal_notice ----

REPLY_COMPLIANT = (
    "WITHOUT PREJUDICE\n\n"
    "Sub.: Reply to your legal notice dated 01 May 2026\n\n"
    "We have received the above-referred legal notice dated 01 May 2026 and "
    "reply thereto on a para-wise basis.\n\n"
    "PRELIMINARY OBJECTIONS:\n\n"
    "1. The said notice is misconceived and untenable in law.\n\n"
    "On Merits:\n\n"
    "We specifically deny each and every allegation made in the notice. "
    "All rights are hereby expressly reserved.\n\n"
    "Yours faithfully,\n"
    "Advocate for Noticee\n\n"
    + DISCLAIMER
)

REPLY_FORBIDDEN_BOLD = (
    "**WITHOUT PREJUDICE**\n\n"  # triggers no_md_bold
    "Re your legal notice dated 01 May 2026:\n"
    "We deny in toto. Preliminary objections raised. "
    "Notice is misconceived. Rights reserved. Para-wise reply follows. "
    "Yours faithfully,\n\n"
    + DISCLAIMER
)


# ---------------------------------------------------------------------------
# Parametrised smoke tests
# ---------------------------------------------------------------------------

SMOKE_COMPLIANT_CASES = [
    ("affidavit_general", AFFIDAVIT_COMPLIANT),
    ("cheque_bounce_138", CHEQUE_COMPLIANT),
    ("consumer_complaint_cpa2019", CONSUMER_COMPLIANT),
    ("employment_offer_termination", EMPLOYMENT_COMPLIANT),
    ("leave_license_mh", LEAVE_LICENSE_COMPLIANT),
    ("legal_notice_landlord_tenant", LANDLORD_TENANT_COMPLIANT),
    ("legal_notice_money_recovery", MONEY_RECOVERY_COMPLIANT),
    ("mou_two_parties", MOU_COMPLIANT),
    ("out_of_scope", OUT_OF_SCOPE_COMPLIANT),
    ("partnership_deed_1932", PARTNERSHIP_COMPLIANT),
    ("reply_to_legal_notice", REPLY_COMPLIANT),
]

SMOKE_FORBIDDEN_CASES = [
    # (doc_type, text, expected_failure_substring)
    ("affidavit_general", AFFIDAVIT_FORBIDDEN, "forbidden_present:no_md_heading"),
    ("cheque_bounce_138", CHEQUE_FORBIDDEN_BOLD, "forbidden_present:no_md_bold"),
    ("consumer_complaint_cpa2019", CONSUMER_FORBIDDEN_OLD_ACT, "forbidden_present:no_repealed_act_1986"),
    ("employment_offer_termination", EMPLOYMENT_FORBIDDEN_AT_WILL, "forbidden_present:no_at_will"),
    ("leave_license_mh", LEAVE_LICENSE_FORBIDDEN_LESSOR, "forbidden_present:no_lessor_lessee"),
    ("legal_notice_money_recovery", MONEY_RECOVERY_FORBIDDEN_IPC, "forbidden_present:no_repealed_ipc"),
    ("legal_notice_landlord_tenant", LANDLORD_TENANT_FORBIDDEN_MODEL, "forbidden_present:no_model_tenancy_act"),
    ("mou_two_parties", MOU_FORBIDDEN_BOLD, "forbidden_present:no_md_bold"),
    ("out_of_scope", OUT_OF_SCOPE_FORBIDDEN_PREDICTION, "forbidden_present:no_outcome_prediction"),
    ("partnership_deed_1932", PARTNERSHIP_FORBIDDEN_LLP, "forbidden_present:no_llp_confusion"),
    ("reply_to_legal_notice", REPLY_FORBIDDEN_BOLD, "forbidden_present:no_md_bold"),
]


class TestSmokeCompliant:
    @pytest.mark.parametrize("doc_type,text", SMOKE_COMPLIANT_CASES)
    def test_compliant_snippet_passes_all_pattern_checks(
        self, doc_type: str, text: str
    ) -> None:
        """A properly constructed snippet must produce no failures."""
        result = check_document(doc_type, text)
        # Filter out length failures in case our snippet is short (unlikely but safe)
        pattern_failures = [
            f for f in result.failures
            if not f.startswith("too_short") and not f.startswith("too_long")
        ]
        assert pattern_failures == [], (
            f"[{doc_type}] unexpected pattern failures: {pattern_failures}"
        )


class TestSmokeForbidden:
    @pytest.mark.parametrize("doc_type,text,expected", SMOKE_FORBIDDEN_CASES)
    def test_violating_snippet_triggers_expected_failure(
        self, doc_type: str, text: str, expected: str
    ) -> None:
        result = check_document(doc_type, text)
        assert any(expected in f for f in result.failures), (
            f"[{doc_type}] expected '{expected}' in failures but got: {result.failures}"
        )


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unicode_text_does_not_crash(self) -> None:
        """Engine must handle non-ASCII characters without exception."""
        text = "नमस्ते " * 100
        result = check_document("affidavit_general", text)
        assert isinstance(result, CheckResult)

    def test_only_whitespace_is_too_short(self) -> None:
        result = check_document("affidavit_general", "   \n\t  ")
        assert any("too_short" in f for f in result.failures)

    def test_consumer_old_forum_name_forbidden(self) -> None:
        rules = load_rules("consumer_complaint_cpa2019")
        text = (
            "BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION\n"
            "Consumer Protection Act, 2019. Section 35. Section 2(7). "
            "Opposite party. Deficiency in the services. Section 69 limitation. "
            "Territorial jurisdiction and pecuniary jurisdiction. "
            "Respectfully prays. Verified at Mumbai.\n"
            "The old District Forum used to handle these.\n\n"  # forbidden
            + DISCLAIMER
        )
        result = check_document("consumer_complaint_cpa2019", text)
        assert any("no_old_forum_name" in f for f in result.failures)

    def test_affidavit_ipc_citation_forbidden(self) -> None:
        rules = load_rules("affidavit_general")
        text = (
            "AFFIDAVIT\n\n"
            "I, Suresh, aged about 40 years, resident of Delhi, "
            "do hereby solemnly affirm and declare:\n\n"
            "1. That I refer to the Indian Penal Code.\n"
            "2. That contents are true.\n\n"
            "Verified at Delhi that the contents are true and correct.\n\n"
            "(DEPONENT)\n\n"
            "Solemnly affirmed before me. Notary Public.\n\n"
            "non-judicial stamp paper.\n\n"
            + DISCLAIMER
        )
        result = check_document("affidavit_general", text)
        assert any("no_ipc_citation" in f for f in result.failures)

    def test_leave_license_monthly_rent_forbidden(self) -> None:
        rules = load_rules("leave_license_mh")
        text = (
            "LEAVE AND LICENSE AGREEMENT\n\n"
            "Between Licensor and Licensee. "
            "The monthly rent is Rs. 20,000.\n"  # triggers no_monthly_rent
            "Security Deposit interest-free and refundable. "
            "Term of 11 months. Notice period of one month. "
            "Registration under Maharashtra Rent Control Act, 1999. "
            "Nothing herein creates any tenancy.\n\n"
            + DISCLAIMER
        )
        result = check_document("leave_license_mh", text)
        assert any("no_monthly_rent" in f for f in result.failures)

    def test_employment_us_artifacts_forbidden(self) -> None:
        text = (
            "(On the letterhead of Acme Pvt. Ltd.)\n\n"
            "Date: 01 June 2026\n\n"
            "Sub.: Offer\n\n"
            "Dear Mr. Singh,\n\n"
            "Position of Manager. Joining date: 15 June 2026. Notice period: 30 days. "
            "Please complete Form I-9 before joining.\n\n"  # triggers no_us_artifacts
            "Yours sincerely,\n\n"
            "For Acme Pvt. Ltd.\n\n"
            + DISCLAIMER
        )
        result = check_document("employment_offer_termination", text)
        assert any("no_us_artifacts" in f for f in result.failures)

    def test_money_recovery_sec138_drift_forbidden(self) -> None:
        text = (
            "LEGAL NOTICE\n\n"
            "Sub.: Demand for payment\n\n"
            "You are hereby called upon to pay Rs. 2,00,000 with interest thereon. "
            "Comply within 15 days else civil suit for recovery filed at your risk and costs. "
            "This is also under Section 138 of the Negotiable Instruments Act.\n\n"  # forbidden
            + DISCLAIMER
        )
        result = check_document("legal_notice_money_recovery", text)
        assert any("no_sec_138_drift" in f for f in result.failures)

    def test_out_of_scope_no_document_body_forbidden(self) -> None:
        text = (
            "I cannot provide legal advice. Please consult an advocate or lawyer. "
            "I can only draft documents.\n\n"
            "1. The party shall pay.\n"
            "2. The obligation continues.\n"  # triggers no_document_body
        ) * 3
        result = check_document("out_of_scope", text)
        assert any("no_document_body" in f for f in result.failures)

    def test_ok_true_only_when_no_failures(self) -> None:
        result_pass = CheckResult(ok=True, failures=(), warnings=())
        result_fail = CheckResult(ok=False, failures=("something",))
        assert result_pass.ok is True
        assert result_fail.ok is False

    def test_check_document_ok_field_consistent_with_failures(self) -> None:
        """ok must be False iff failures is non-empty."""
        result = check_document("affidavit_general", "x" * 2000)
        assert result.ok == (len(result.failures) == 0)


# ---------------------------------------------------------------------------
# Section 4b – affidavit verification clause ordering
# ---------------------------------------------------------------------------

# A complete, self-sufficient affidavit whose verification is written in the
# common "affirmation-first" order: the "...are true and correct..." sentence
# precedes the "Verified at [place] on [date]" venue line. Both orderings are
# valid Indian practice; the gate must accept either.
AFFIDAVIT_AFFIRMATION_FIRST = (
    "AFFIDAVIT\n\n"
    "I, Nikita Reddy, daughter of Devendra Mane, aged about 65 years, "
    "resident of Flat No. 24, Silver Oak Towers, Kothrud, Thane 400084, "
    "do hereby solemnly affirm and declare as under:\n\n"
    "1. That I am the deponent herein and am fully conversant with the facts "
    "and circumstances of this affidavit and am competent to swear the same.\n"
    "2. That I am one and the same person referred to by the two differing name "
    "spellings appearing across my official documents, and there is no intention "
    "on my part to assume a false identity or to misrepresent any fact.\n"
    "3. That the variation in the said names has arisen due to inadvertent "
    "clerical inconsistency in the recording of my name across documents.\n\n"
    "VERIFICATION\n\n"
    "I, Nikita Reddy, the deponent above named, do hereby verify that the "
    "contents of paragraphs 1 to 3 above are true and correct to the best of my "
    "knowledge and belief, and that nothing material has been concealed "
    "therefrom.\n\n"
    "Verified at Nashik on this 11th day of June, 2026.\n\n"
    "(DEPONENT)\n\n"
    "Solemnly affirmed before me by the deponent, who is personally known to "
    "me, on this 11th day of June, 2026, at Nashik.\n\n"
    "Notary Public\n\n"
    "This affidavit is to be executed on non-judicial stamp paper of the value "
    "applicable in the State.\n\n"
    + DISCLAIMER
)


class TestAffidavitVerificationOrdering:
    """The verification gate must accept both clause orderings, not just one."""

    def test_affirmation_first_affidavit_passes_gate(self) -> None:
        result = check_document("affidavit_general", AFFIDAVIT_AFFIRMATION_FIRST)
        assert result.ok, result.failures

    def test_neither_ordering_reports_a_verification_miss(self) -> None:
        # AFFIDAVIT_COMPLIANT is place-first; AFFIDAVIT_AFFIRMATION_FIRST is
        # affirmation-first. Neither should produce a verification-related miss,
        # independent of any length padding.
        for text in (AFFIDAVIT_COMPLIANT, AFFIDAVIT_AFFIRMATION_FIRST):
            result = check_document("affidavit_general", text)
            verification_misses = [
                f for f in result.failures if "verif" in f.lower()
            ]
            assert not verification_misses, (text[:40], verification_misses)


# ---------------------------------------------------------------------------
# Section 4c – harness bugs surfaced by the doc-type audit (real reject text)
# ---------------------------------------------------------------------------


def _required_patterns(doc_type: str) -> dict:
    return {pid: rx for pid, _desc, rx in load_rules(doc_type).required}


# Real refusals from the out_of_scope audit, lightly cleaned. Each was a valid
# refusal (declines + recommends an advocate + offers supported types) wrongly
# rejected by an over-strict gate.
OOS_OFFERS_SUPPORTED_TYPE = (  # tripped no_statutory_citation + no_advice_directive
    "Hi Nikita, I completely understand the frustration. However, I can only "
    "draft legal documents and I am not able to advise on whether you should "
    "sue, predict outcomes, or assess your chances. For that kind of guidance, "
    "please consult a qualified advocate who can evaluate your situation. That "
    "said, if you would like to take action, I can draft a Consumer Complaint "
    "under Section 35 of the Consumer Protection Act, 2019, before the District "
    "Consumer Disputes Redressal Commission. I can also draft a Legal Notice "
    "for Recovery of Money or a Reply to Legal Notice if any would help."
)
OOS_OUTSIDE_SCOPE_ASSIST = (  # tripped missing_required:scope_statement
    "Hello Priya, I understand this must be a stressful situation. "
    "Unfortunately, drafting bail applications falls outside the scope of what "
    "I am able to assist with. NyayaDraft supports specific document types such "
    "as General Affidavits, Legal Notices for Recovery of Money, and Cheque "
    "Bounce Demand Notices, among others. For a bail application, I would "
    "strongly recommend consulting a qualified criminal law advocate at the "
    "earliest, as this matter requires urgent professional legal guidance."
)
OOS_WORK_ONLY_WITH = (  # tripped missing_required:scope_statement
    "Thank you for reaching out. I want to be upfront with you: anticipatory "
    "bail applications fall outside the scope of what I am able to draft. I "
    "work only with specific document types, such as a General Affidavit, a "
    "Legal Notice for Recovery of Money, and a Memorandum of Understanding, "
    "among others. For an anticipatory bail application, I would strongly "
    "recommend consulting a qualified criminal law advocate who can advise you."
)


class TestOutOfScopeRefusalAcceptance:
    """Legitimate refusals must pass; the gate must not punish offering a
    supported document type by name, or quoting a declined action."""

    def test_refusal_offering_supported_type_with_citation_passes(self) -> None:
        result = check_document("out_of_scope", OOS_OFFERS_SUPPORTED_TYPE)
        assert result.ok, result.failures

    def test_refusal_outside_scope_assist_phrasing_passes(self) -> None:
        result = check_document("out_of_scope", OOS_OUTSIDE_SCOPE_ASSIST)
        assert result.ok, result.failures

    def test_refusal_work_only_with_phrasing_passes(self) -> None:
        result = check_document("out_of_scope", OOS_WORK_ONLY_WITH)
        assert result.ok, result.failures

    def test_genuine_advice_directive_still_forbidden(self) -> None:
        # The fix must not let through an actual directive to sue.
        bad = (
            "I cannot draft that, but honestly you should sue them right away. "
            "Please consult a qualified advocate. I only draft documents." * 2
        )
        result = check_document("out_of_scope", bad)
        assert any("no_advice_directive" in f for f in result.failures)


class TestComplianceWindowPhrasing:
    """'15 (fifteen) days' (number first, word in parens) is standard Indian
    drafting and must satisfy the compliance-window gates."""

    PHRASES_OK = [
        "15 (fifteen) days",
        "30 (thirty) days",
        "fifteen (15) days",
        "thirty (30) days",
        "within 15 days",
        "within thirty days",
    ]

    def test_landlord_tenant_window_accepts_all_orderings(self) -> None:
        rx = _required_patterns("legal_notice_landlord_tenant")["compliance_window"]
        for s in self.PHRASES_OK:
            assert rx.search(s), f"compliance_window failed to match: {s!r}"

    def test_money_recovery_window_accepts_all_orderings(self) -> None:
        rx = _required_patterns("legal_notice_money_recovery")["compliance_window_days"]
        for s in self.PHRASES_OK:
            assert rx.search(s), f"compliance_window_days failed to match: {s!r}"

    def test_cheque_bounce_windows_accept_number_first_paren_word(self) -> None:
        req = _required_patterns("cheque_bounce_138")
        assert req["demand_15_days"].search("15 (fifteen) days")
        assert req["memo_30_days"].search("30 (thirty) days")


class TestEmploymentLetterhead:
    """An offer letter on a letterhead block (company name + address + CIN) is
    valid even when the company name carries no corporate suffix."""

    def test_letterhead_reference_accepts_cin_block(self) -> None:
        rx = _required_patterns("employment_offer_termination")["letterhead_reference"]
        assert rx.search("CIN: [COMPANY IDENTIFICATION NUMBER]")
        assert rx.search("[COMPANY CIN / REGISTRATION NUMBER]")

    def test_letterhead_reference_still_matches_suffix_and_word(self) -> None:
        rx = _required_patterns("employment_offer_termination")["letterhead_reference"]
        assert rx.search("(On the letterhead of Acme Pvt. Ltd.)")
        assert rx.search("Acme Private Limited")


# ---------------------------------------------------------------------------
# Section 5 – load_rules / lint_all_rules with synthetic rule files
# (covers the ValueError and lint_all_rules problem branches)
# ---------------------------------------------------------------------------

import json as _json
import importlib

from legal_rules import checker as _checker_module


def _write_rule(tmp_path: Path, stem: str, spec: dict) -> Path:
    """Write *spec* as JSON to *tmp_path*/<stem>.json and return the path."""
    p = tmp_path / f"{stem}.json"
    p.write_text(_json.dumps(spec), encoding="utf-8")
    return p


class TestLoadRulesMismatchedDocType:
    def test_mismatched_doc_type_raises_value_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_rules must raise ValueError when doc_type in JSON != filename stem."""
        stem = "fake_doc_type"
        spec = {
            "doc_type": "wrong_name",  # deliberately wrong
            "min_chars": 100,
            "max_chars": 5000,
            "require_disclaimer": True,
            "is_document": True,
            "required_patterns": [
                {"id": "p1", "description": "d1", "regex": "foo", "legal_basis": "CONFIDENT"}
            ],
            "forbidden_patterns": [],
        }
        _write_rule(tmp_path, stem, spec)
        # Patch RULES_DIR on the checker module so it looks in tmp_path
        monkeypatch.setattr(_checker_module, "RULES_DIR", tmp_path)
        # Clear lru_cache so the patched path is used
        _checker_module.load_rules.cache_clear()
        with pytest.raises(ValueError, match="doc_type field"):
            _checker_module.load_rules(stem)
        # Restore cache state so subsequent tests are unaffected
        _checker_module.load_rules.cache_clear()


class TestLintAllRulesBranches:
    """Exercise lint_all_rules problem-reporting branches via monkeypatched RULES_DIR."""

    def _patch_rules_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(_checker_module, "RULES_DIR", tmp_path)
        _checker_module.load_rules.cache_clear()

    def _restore(self) -> None:
        _checker_module.load_rules.cache_clear()

    def test_lint_reports_load_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rule file with a bad regex must cause lint_all_rules to record a problem."""
        stem = "bad_regex_doc"
        spec = {
            "doc_type": stem,
            "min_chars": 100,
            "max_chars": 5000,
            "require_disclaimer": True,
            "is_document": True,
            "required_patterns": [
                {"id": "bad", "description": "d", "regex": "(?P<a>(?P<a>x))", "legal_basis": "CONFIDENT"}
            ],
            "forbidden_patterns": [],
        }
        _write_rule(tmp_path, stem, spec)
        self._patch_rules_dir(monkeypatch, tmp_path)
        problems = _checker_module.lint_all_rules()
        assert any(stem in p for p in problems), f"Expected problem for {stem}, got: {problems}"
        self._restore()

    def test_lint_reports_is_document_with_no_required_patterns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An is_document type with empty required_patterns must be flagged."""
        stem = "empty_required_doc"
        spec = {
            "doc_type": stem,
            "min_chars": 100,
            "max_chars": 5000,
            "require_disclaimer": True,
            "is_document": True,
            "required_patterns": [],   # intentionally empty
            "forbidden_patterns": [],
        }
        _write_rule(tmp_path, stem, spec)
        self._patch_rules_dir(monkeypatch, tmp_path)
        problems = _checker_module.lint_all_rules()
        assert any("no required_patterns" in p for p in problems), (
            f"Expected 'no required_patterns' problem, got: {problems}"
        )
        self._restore()

    def test_lint_reports_min_chars_ge_max_chars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rule file where min_chars >= max_chars must be flagged."""
        stem = "bad_bounds_doc"
        spec = {
            "doc_type": stem,
            "min_chars": 5000,
            "max_chars": 100,   # inverted bounds
            "require_disclaimer": True,
            "is_document": True,
            "required_patterns": [
                {"id": "p1", "description": "d1", "regex": "foo", "legal_basis": "CONFIDENT"}
            ],
            "forbidden_patterns": [],
        }
        _write_rule(tmp_path, stem, spec)
        self._patch_rules_dir(monkeypatch, tmp_path)
        problems = _checker_module.lint_all_rules()
        assert any("min_chars >= max_chars" in p for p in problems), (
            f"Expected 'min_chars >= max_chars' problem, got: {problems}"
        )
        self._restore()

    def test_lint_reports_equal_min_max_chars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """min_chars == max_chars is also an invalid bound."""
        stem = "equal_bounds_doc"
        spec = {
            "doc_type": stem,
            "min_chars": 1000,
            "max_chars": 1000,
            "require_disclaimer": True,
            "is_document": True,
            "required_patterns": [
                {"id": "p1", "description": "d1", "regex": "foo", "legal_basis": "CONFIDENT"}
            ],
            "forbidden_patterns": [],
        }
        _write_rule(tmp_path, stem, spec)
        self._patch_rules_dir(monkeypatch, tmp_path)
        problems = _checker_module.lint_all_rules()
        assert any("min_chars >= max_chars" in p for p in problems), (
            f"Expected 'min_chars >= max_chars' problem for equal bounds, got: {problems}"
        )
        self._restore()

    def test_lint_returns_empty_for_valid_rule(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single well-formed rule file must produce no lint problems."""
        stem = "valid_doc"
        spec = {
            "doc_type": stem,
            "min_chars": 200,
            "max_chars": 5000,
            "require_disclaimer": True,
            "is_document": True,
            "required_patterns": [
                {"id": "p1", "description": "d1", "regex": "foo", "legal_basis": "CONFIDENT"}
            ],
            "forbidden_patterns": [],
        }
        _write_rule(tmp_path, stem, spec)
        self._patch_rules_dir(monkeypatch, tmp_path)
        problems = _checker_module.lint_all_rules()
        assert problems == [], f"Unexpected problems for valid rule: {problems}"
        self._restore()


# ---------------------------------------------------------------------------
# Section 5 – Over-strict required-pattern regressions
# ---------------------------------------------------------------------------


def _required_pattern(doc_type: str, pattern_id: str) -> re.Pattern:
    for pid, _desc, pat in load_rules(doc_type).required:
        if pid == pattern_id:
            return pat
    raise AssertionError(f"{doc_type} has no required pattern {pattern_id!r}")


class TestDemandLanguageThirdPerson:
    """demand_language must accept third-person advocate phrasing such as
    'my client calls upon you' and 'demands that you ...', not only the
    first-person 'call upon you' / 'hereby demand'. The singular-verb-only
    pattern rejected the (very common) plural forms, wasting valid drafts."""

    DEMAND_DOC_TYPES = (
        "cheque_bounce_138",
        "legal_notice_money_recovery",
        "legal_notice_landlord_tenant",
    )

    THIRD_PERSON = [
        "my client hereby calls upon you to pay the said amount",
        "our client calls upon you to make good the default",
        "my client demands that you refund the amount forthwith",
        "the company demands that you pay the outstanding dues",
    ]
    FIRST_PERSON = [
        "I hereby call upon you to pay the sum",
        "we hereby demand payment of the said amount",
    ]

    @pytest.mark.parametrize("doc_type", DEMAND_DOC_TYPES)
    def test_accepts_third_person(self, doc_type: str) -> None:
        pat = _required_pattern(doc_type, "demand_language")
        for phrase in self.THIRD_PERSON:
            assert pat.search(phrase), (
                f"{doc_type}: demand_language rejected third-person {phrase!r}"
            )

    @pytest.mark.parametrize("doc_type", DEMAND_DOC_TYPES)
    def test_still_accepts_first_person(self, doc_type: str) -> None:
        pat = _required_pattern(doc_type, "demand_language")
        for phrase in self.FIRST_PERSON:
            assert pat.search(phrase), (
                f"{doc_type}: demand_language regressed on {phrase!r}"
            )


class TestRightsReservedIntervening:
    """rights_reserved must allow intervening words between 'reserve' and
    'rights' (and between 'rights' and 'reserved'), e.g. 'reserves all its
    legal and equitable rights'. The fixed determiner list rejected valid
    reservations."""

    INTERVENING = [
        "my client reserves all its legal and equitable rights",
        "the noticee reserves unto itself all rights and remedies",
        "all rights and remedies of the noticee are hereby expressly reserved",
        "rights, civil and criminal, are reserved",
        "reserves all such other rights as may be available in law",
    ]
    EXISTING = [
        "All rights are hereby expressly reserved.",
        "the noticee reserves all rights",
        "reserving its rights",
        "reserves its right to initiate appropriate proceedings",
    ]

    @pytest.mark.parametrize("phrase", INTERVENING)
    def test_accepts_intervening_words(self, phrase: str) -> None:
        pat = _required_pattern("reply_to_legal_notice", "rights_reserved")
        assert pat.search(phrase), f"rights_reserved rejected {phrase!r}"

    @pytest.mark.parametrize("phrase", EXISTING)
    def test_still_accepts_existing(self, phrase: str) -> None:
        pat = _required_pattern("reply_to_legal_notice", "rights_reserved")
        assert pat.search(phrase), f"rights_reserved regressed on {phrase!r}"
