"""Membership by evidence rather than substring."""
import categories
import label

B6 = categories.CATEGORIES["excl_b6_quality_care"].regex
B7 = categories.CATEGORIES["excl_b7_fraud_kickback"].regex
HEAD_START = categories.CATEGORIES["head_start"].regex
BODY = "Procedural history and findings of fact. " * 220


def test_strips_a_precedent_citation():
    text = ("a fundamental principle of grant management. (Head Start of New "
            "Hanover County, Inc., Decision No. 65, September 26, 1979.) In the "
            "instant case the grantee submitted no contemporaneous records.")
    assert label.citation_spans(label.normalize(text))
    assert label.evidence(text, HEAD_START)["n_matches"] == 0


def test_does_not_strip_a_real_program_reference():
    text = ("William Smith, Sr. Tri-County Child Development Council, Inc. (the "
            "Council), a nonprofit corporation, operates Head Start and Early "
            "Head Start programs in Texas.")
    assert label.evidence(text, HEAD_START)["n_matches"] >= 1


def test_matches_across_a_line_break():
    # clean() keeps line structure for the header parser, so matching has to
    # normalize. Not doing so dropped Topeka Public Schools (DAB No. 47).
    text = "children previously enrolled in Head\nStart or similar programs"
    assert label.evidence(text, HEAD_START)["n_matches"] == 1


def test_matches_a_hyphenated_statutory_break():
    text = "permanently excluded under 42 U.S.C. § 1320a-\n7(b) (7) for the conduct"
    assert label.evidence(text, B7)["n_matches"] == 1


def test_a_losing_argument_deep_in_the_body_is_not_membership():
    # Chang, DAB No. 1198: a 1128(a) conviction case in which the petitioner
    # argued for 1128(b)(6) and lost.
    text = BODY + ("Petitioner contended that such a finding should invoke the "
                   "permissive provisions of section 1128(b)(6) of the Act. We "
                   "find no merit in Petitioner's arguments.")
    assert not label.label(text, B6)[0]


def test_an_enumeration_deep_in_the_body_is_not_membership():
    # Friedman, DAB No. 1281: a 1128(b)(4) licence case listing the IG's powers.
    text = BODY + ("or (B) to make an independent determination of improper "
                   "conduct (sections 1128(b)(6), (7), (8)).")
    assert not label.label(text, B6)[0]


def test_the_operative_basis_in_the_opening_is_membership():
    # Godreau, DAB No. 1300.
    text = ("determination to exclude Petitioner for a period of ten years "
            "pursuant to section 1128(b)(6)(B) of the Social Security Act.")
    assert label.label(text, B6)[0]


def test_recurrence_carries_a_late_first_mention():
    text = BODY + "section 1128(b)(6) " * label.MIN_RECURRENCE
    assert label.label(text, B6)[0]


def test_citation_only_matches_are_reported_separately():
    text = ("quoted in Keith Michael Everman, D.C., DAB No. 1880, at 7 (2003), "
            "construing section 1128(b)(7).")
    ev = label.evidence(text, B7)
    assert ev["n_in_citation"] + ev["n_matches"] >= 1


def test_prepared_matches_the_plain_string_path():
    text = BODY + "section 1128(b)(6) of the Act"
    assert label.evidence(text, B6) == label.evidence(label.Prepared(text), B6)
