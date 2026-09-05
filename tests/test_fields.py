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


def test_disposition_text_is_none_with_neither_heading_nor_sign_off():
    assert fields.disposition_text("We consider the arguments at length.") is None


def test_the_passage_before_a_sign_off_is_offered_but_not_labelled():
    # disposition_text widened to the passage before the signature block, so
    # that Council decisions -- which state the holding in running text and
    # never write "Conclusion" -- are covered at all. The passage is offered
    # verbatim; it is dispositions() that decides whether it says anything
    # operative, and here it does not.
    text = "We consider the arguments.\n\n/s/ Francis D. DeGeorge\nPanel Chairman\n"
    assert "We consider the arguments." in fields.disposition_text(text)
    assert fields.dispositions(text) == []


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


def test_dispositions_read_the_operative_phrasing():
    assert fields.dispositions("Conclusion\n\nFor all of the foregoing reasons, "
                               "we affirm the ALJ Decision.\n") == ["affirmed"]
    assert fields.dispositions("Conclusion\n\nI sustain CMS's determination that "
                               "Petitioner was not in substantial compliance.\n") == ["sustained"]


def test_a_compound_disposition_keeps_both_parts():
    # "we reverse ... and remand" is both. A single-value field drops half of it.
    got = fields.dispositions(
        "Conclusion\n\nFor the foregoing reasons, we reverse the ALJ's dismissal "
        "with prejudice and remand the case to the ALJ for further proceedings.\n")
    assert set(got) == {"reversed", "remanded"}


def test_asking_to_affirm_is_not_an_affirmance():
    # A disposition verb appears somewhere in 90% of Appellate decisions.
    assert fields.dispositions(
        "Conclusion\n\nPetitioner asks us to affirm the ALJ Decision. We decline.\n") == []


def test_no_conclusion_means_no_disposition():
    assert fields.dispositions("We consider the arguments.\n\n/s/ A Judge\n") == []


def test_council_judges_sign_as_administrative_appeals_judges():
    text = ("The ALJ's decision is reversed.\nMEDICARE APPEALS COUNCIL\n"
            "/s/ Clausen J. Krzywicki\nAdministrative Appeals Judge\n"
            "/s/ Gilde B. Morrisson\nAdministrative Appeals Judge\nDate: April 22, 2011")
    got = fields.judges(text)
    assert set(got) == {"Clausen J. Krzywicki", "Gilde B. Morrisson"}


def test_a_holding_stated_before_the_signature_block_is_found():
    # Council decisions have no conclusion heading; they state the holding in
    # running text and sign off. The signature block bounds it.
    text = ("The ALJ found the services non-covered. We disagree.\n"
            "The ALJ's decision is reversed.\nMEDICARE APPEALS COUNCIL\n"
            "/s/ Clausen J. Krzywicki\nAdministrative Appeals Judge\n")
    assert "decision is reversed" in fields.disposition_text(text)
    assert fields.dispositions(text) == ["reversed"]


def test_a_signature_block_alone_is_still_no_disposition():
    assert fields.dispositions("We consider the arguments at length.\n"
                               "/s/ A Judge\nAdministrative Law Judge\n") == []
