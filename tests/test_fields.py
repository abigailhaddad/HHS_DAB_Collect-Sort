"""Body-derived fields. Each is scoped; the tests pin the scoping."""
import fields


def test_reviewed_decision_is_the_one_under_review():
    text = ("The Inspector General appealed a December 14, 1992 decision by "
            "Administrative Law Judge Charles E. Stratton modifying an exclusion. "
            "Tajammul H. Bhatti, M.D., DAB CR245 (1992) (ALJ Decision). In his "
            "decision, the ALJ concluded that although the I.G. had authority")
    assert fields.reviews_decision_no(text) == "CR245"


def test_a_precedent_citation_is_not_a_review():
    # Matching "DAB CR\\d+" anywhere hits 53% of ALJ decisions, which do not
    # review each other at all -- every one of those is precedent.
    text = ("We have held the same in other cases. See Mark Zweig, M.D., DAB "
            "CR563 (1999); see also Some Other Petitioner, DAB CR700 (2001). "
            "The record here supports the revocation.")
    assert fields.reviews_decision_no(text) is None


def test_provider_identifiers():
    text = ("In the Case of: Daniel M. Stewart, (CLIA ID #23D0363803), "
            "Petitioner, - v. - Centers for Medicare & Medicaid Services.")
    assert fields.provider_ids(text) == ["CLIA:23D0363803"]
    text2 = ("William S. Strauss, M.D., (PTAN: R159348 / NPI: 1831247147) "
             "Petitioner, v. CMS. Rochelle Gardens (CCN: 14-6152)")
    got = fields.provider_ids(text2)
    assert "NPI:1831247147" in got and "PTAN:R159348" in got and "CCN:146152" in got


def test_provider_identifiers_are_deduplicated():
    text = "CCN: 14-6152 ... the facility (CCN 146152) was surveyed"
    assert fields.provider_ids(text) == ["CCN:146152"]


def test_no_identifiers_is_an_empty_list_not_none():
    assert fields.provider_ids("A grant disallowance appeal.") == []


def test_disposition_text_is_the_conclusion_verbatim():
    text = ("Analysis\n\nThe record supports the revocation.\n\nConclusion\n\n"
            "For the reasons stated above, we affirm the ALJ Decision.\n")
    assert fields.disposition_text(text) == \
        "For the reasons stated above, we affirm the ALJ Decision."


def test_disposition_text_is_none_without_a_conclusion_heading():
    # Falling back to the tail would return a signature block that reads like a
    # conclusion without being one.
    text = "We consider the arguments.\n\n/s/ Francis D. DeGeorge\nPanel Chairman\n"
    assert fields.disposition_text(text) is None


def test_disposition_text_is_not_a_label():
    # "asks us to affirm" is not an affirmance; the field carries the sentence,
    # and nothing here decides what it means.
    text = ("Conclusion\n\nPetitioner asks us to affirm the ALJ Decision. We "
            "decline to do so and reverse.\n")
    out = fields.disposition_text(text)
    assert "asks us to affirm" in out and "reverse" in out


def test_judges_from_each_sign_off_shape():
    assert fields.judges("I order this complaint\ndismissed.\n/s/\nBill Thomas\n"
                         "Administrative Law Judge\n") == ["Bill Thomas"]
    assert fields.judges("a decision by Administrative Law Judge Charles E. "
                         "Stratton modifying an exclusion") == ["Charles E. Stratton"]
    assert fields.judges("A decision with no signature block.") == []


def test_an_appellate_panel_returns_every_member():
    # Only the last name carries a title, so matching titles alone returned one
    # member of three.
    text = ("...reduction of the CMP.\n ________/s/__________\n Judith A. Ballard\n"
            " ________/s/__________\n Donald F. Garrett\n ________/s/__________ \n"
            "Marc R. Hillson\n Presiding Board Member")
    got = fields.judges(text)
    assert set(got) == {"Judith A. Ballard", "Donald F. Garrett", "Marc R. Hillson"}
