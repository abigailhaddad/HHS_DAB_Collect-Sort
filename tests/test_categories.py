"""The category table is the single source of truth; it has to be intact."""
import re

import categories


def test_every_category_is_complete():
    # categorize_counts.py once had a samhsa_otp_cert pattern with no
    # description in build_manifests.py; the slice would have shipped with a
    # blank legal basis.
    for name, cat in categories.CATEGORIES.items():
        assert cat.name == name
        assert cat.description.strip()
        assert cat.citation.strip()
        assert isinstance(cat.pattern, re.Pattern)


def test_patterns_match_their_canonical_citation():
    canonical = {
        "excl_b3_controlled_substance": "section 1128(b)(3) of the Act",
        "excl_b4_license_revocation": "42 U.S.C. 1320a-7(b)(4)",
        "excl_b6_quality_care": "section 1128(b)(6)(B)",
        "excl_b7_fraud_kickback": "42 U.S.C. § 1320a-7(b)(7)",
        "excl_b14_loan_default": "section 1128(b)(14)",
        "enroll_a3_felony": "42 C.F.R. § 424.535(a)(3)",
        "enroll_a5_nonoperational": "424.535(a)(5)",
        "enroll_a8_billing_abuse": "424.535(a)(8)",
        "head_start": "operates a Head Start program",
        "clia_lab_sanctions": "revoke the CLIA certificate",
    }
    for name, text in canonical.items():
        assert categories.CATEGORIES[name].regex.search(text), name


def test_subsection_patterns_do_not_match_each_other():
    # (b)(4) must not match (b)(14): "1128(b)(14)" contains no "(b)(4)", but a
    # sloppy pattern that allows digits either side would catch it.
    b4 = categories.CATEGORIES["excl_b4_license_revocation"].regex
    assert not b4.search("excluded under section 1128(b)(14) of the Act")
    b14 = categories.CATEGORIES["excl_b14_loan_default"].regex
    assert not b14.search("excluded under section 1128(b)(4) of the Act")


def test_statutory_patterns_survive_a_hyphenated_line_break():
    # PDF extraction yields "1320a-\n7(b)(7)", which normalizes to a hyphen AND
    # a space. Allowing only one separator character lost these.
    b7 = categories.CATEGORIES["excl_b7_fraud_kickback"].regex
    assert b7.search("42 U.S.C. § 1320a- 7(b) (7)")
    assert b7.search("42 U.S.C. § 1320a-7(b)(7)")
