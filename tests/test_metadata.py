"""Header parsing across the four template generations the corpus spans."""
import metadata

GRANT_APPEALS_1978 = (
    "DEPARTI1ENTAL GRANT APPEALS BOARD\nDepartment of Health, Education, and "
    "Welfare\nSUBJECT: Topeka Public Schools, Topeka, Kansas\nDocket Nos. 77-7, "
    "77-8, and 77-9\nDecision No. 47\nDATE~ SEP. 28, 1978\nDECISION")
APPELLATE_1993 = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Appellate Division\nIn the Case of:\nTajammul H. Bhatti, M.D.,\nPetitioner,\n"
    "- v. -\nThe Inspector General.\nDATE: June 1, 1993\nDocket No. C-92-045\n"
    "Decision No. 1415\n")
CIVIL_REMEDIES_2008 = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Civil Remedies Division\nIn the Case of:\nDaniel M. Stewart,\nPetitioner,\n"
    "- v. -\nCenters for Medicare & Medicaid Services.\nDate: January 9, 2008\n"
    "Docket No. C-07-429\nDecision No. CR1723\n")
BARE_DATE_2015 = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Appellate Division\nWilliam Smith, Sr. Tri-County Child Development "
    "Council, Inc.\nDocket No. A-15-44\nDecision No. 2647\nJune 30, 2015\nDECISION")


def test_grant_appeals_board():
    m = metadata.parse(GRANT_APPEALS_1978)
    assert m["decision_no"] == "47"
    assert m["decision_date"] == "1978-09-28"       # "DATE~ SEP. 28, 1978"
    assert m["tribunal"] == "Grant Appeals Board"
    assert m["docket_nos"] == ["77-7", "77-8", "77-9"]


def test_appellate_division():
    m = metadata.parse(APPELLATE_1993)
    assert (m["decision_no"], m["decision_date"]) == ("1415", "1993-06-01")
    assert m["tribunal"] == "Appellate Division"
    assert m["respondent"] == "Inspector General"


def test_civil_remedies_division():
    m = metadata.parse(CIVIL_REMEDIES_2008)
    assert (m["decision_no"], m["decision_date"]) == ("CR1723", "2008-01-09")
    assert m["tribunal"] == "Civil Remedies Division"
    assert m["respondent"] == "CMS"


def test_bare_date_line():
    m = metadata.parse(BARE_DATE_2015)
    assert (m["decision_no"], m["decision_date"]) == ("2647", "2015-06-30")


def test_year_comes_from_the_text_not_the_filename():
    # Filenames are hand-typed and carry real typos: "0980.02.25DAB083".
    m = metadata.parse("Decision No. 83\nDATE: February 25, 1980\n",
                       "0980.02.25DAB083 New Mexico Human Services Department")
    assert m["year"] == 1980
    assert m["filename_year"] == 980


def test_filename_year_is_the_fallback_when_no_date_parses():
    m = metadata.parse("A decision with no parseable date line.",
                       "1994.05.02DAB1450 Some Grantee")
    assert m["decision_date"] is None
    assert m["year"] == 1994


def test_missing_fields_come_back_none_not_empty_string():
    m = metadata.parse("Nothing resembling a decision header.")
    assert m["decision_no"] is None
    assert m["tribunal"] is None
    assert m["docket_nos"] == []


def test_ig_abbreviation_does_not_match_the_bare_word_ig():
    # "\\bI\\.?G\\.?\\b" under IGNORECASE matches "ig" in ordinary text.
    m = metadata.parse("Civil Remedies Division\nThe petitioner ran a big rig "
                       "repair shop and ig is not an abbreviation here.\n")
    assert m["respondent"] != "Inspector General"


def test_docket_separator_is_case_insensitive():
    # re.split does not inherit the pattern's IGNORECASE flag.
    m = metadata.parse("Civil Remedies Division\nDocket Nos. 84-228 AND 84-229\n")
    assert m["docket_nos"] == ["84-228", "84-229"]


def test_docket_run_with_oxford_comma():
    m = metadata.parse("Docket Nos. 77-7, 77-8, and 77-9\n")
    assert m["docket_nos"] == ["77-7", "77-8", "77-9"]


def test_garbled_date_label_yields_none_not_a_fact_date():
    # DAB No. 33: "DATE: ~E.rch 3, 1977" would not parse, and the fall-through
    # picked "Feburary 1, 1969" out of the statement of facts.
    text = ("DEPARTMENTAL GRANT APPEALS BOARD\nDecision No. 33\n"
            "DATE: @@@@ 3, 1977\nDECISION\nThis is a review of expenditure "
            "disallowances for the period from February 1, 1969 through 1973.")
    m = metadata.parse(text, "1977.03.03 DAB033 Lane County")
    assert m["decision_date"] != "1969-02-01"
    assert m["year"] == 1977           # from the filename, which is right here


def test_ocr_damaged_month_names_still_parse():
    for raw, want in (("Nay 29, 1981", "1981-05-29"),
                      ("Harch 14, 1977", "1977-03-14"),
                      ("August 14 I 1978", "1978-08-14"),
                      ("October 31 1978", "1978-10-31")):
        m = metadata.parse(f"Appellate Division\nDATE: {raw}\n")
        assert m["decision_date"] == want, raw


def test_a_dangling_connective_is_not_a_docket():
    # DAB No. 628: "...$11,881,983 in Docket No.\n84-228, and $1,032,130 in
    # Docket No. 85-25." The run ended on "and", which became a docket number.
    m = metadata.parse("HCFA disallowed $11,881,983 in Docket No.\n84-228, and "
                       "$1,032,130 in Docket No. 85-25.\n")
    assert m["docket_nos"] == ["84-228"]


def test_header_words_do_not_fuzzy_match_a_month():
    # difflib scored "Decision" against "December", so an unlabelled header
    # reading "Decision 3 1978" parsed as 3 December 1978.
    assert metadata._month("Decision") is None
    assert metadata._month("Department") is None
    assert metadata.parse("Appellate Division\nDecision 3 1978\n")["decision_date"] is None
    # Real OCR damage must still resolve.
    assert metadata._month("Nay") == 5
    assert metadata._month("Harch") == 3


def test_filename_numbers():
    f = metadata.decision_no_from_id
    assert f("1990.10.15DAB1200 Sumter County Opportunity, Inc.") == "1200"
    assert f("2016.08.17 CR4685 Rochelle Gardens Care Center, v. CMS") == "CR4685"
    # The trailing R is the decision on reconsideration -- a different document.
    assert f("1987.07.02CR10 Inspector General v. Frank P. Silver, M.D.") == "CR10"
    assert f("1988.05.02 CR10R The Inspector General v. Frank P. Silver") == "CR10R"
    # "No." between the word and the number; without it these fell through to
    # the header parse and four rulings came back as 1771.
    assert f("2016.07.25 ALJ Ruling No. 2016-14 Great Lakes Healthcare") == "RULING2016-14"
    assert f("2005.01.25RUL2005-1 Oklahoma Health Care Authority") == "RULING2005-1"
    assert f("2012.07.17ALJRUL 2012-1 Douglas L. Clore v. CMS") == "RULING2012-1"
    assert f("a caption with no number") is None


def test_the_council_is_recognised_before_the_divisions():
    # Council decisions carry the Board's letterhead too, so a division match
    # would otherwise win on them.
    m = metadata.parse("Department of Health and Human Services\n"
                       "DEPARTMENTAL APPEALS BOARD\nMedicare Appeals Council\n"
                       "In the case of W.K.\nDocket No. M-11-2450\n")
    assert m["tribunal"] == "Medicare Appeals Council"


def test_docket_number_spelled_out():
    # The Council writes "Docket Number:"; requiring "No." parsed 1 of 224.
    m = metadata.parse("DECISION OF MEDICARE APPEALS COUNCIL\n"
                       "Docket Number: M-10-1171\nIn the case of Montefiore\n")
    assert m["docket_nos"] == ["M-10-1171"]


# --- undated decisions: three causes, and the guard that keeps "null rather than wrong" ---

def test_year_first_date_label_parses():
    # The 1999 CR format: "Date: 1999 October 12". Month-first patterns missed it.
    text = ("DEPARTMENTAL APPEALS BOARD\nCivil Remedies Division\nDate: 1999 "
            "October 12\nDocket No. C-98-438\nDecision No. CR621\n")
    assert metadata.parse(text, "1999_CR621")["decision_date"] == "1999-10-12"


def test_nul_between_every_character_is_read_through():
    # Some extractions yield "\x00D\x00a\x00t\x00e..." and no pattern matched.
    plain = "DEPARTMENTAL APPEALS BOARD\nDATE: June 1, 1993\nDecision No. 1415\n"
    spaced = "\x00".join(plain)
    assert metadata.parse(spaced, "1993.06.01DAB1415 X")["decision_date"] == "1993-06-01"


def test_a_sentence_ending_in_date_no_longer_blocks_the_fallback():
    # "received on that date." has "date" and a period, which used to be taken
    # for a DATE: label and switch the fallback off. With a record-id date that
    # agrees, the bare header date is trusted again.
    text = ("DEPARTMENTAL APPEALS BOARD\nCivil Remedies Division\nJuly 2, 2019\n"
            "Docket No. C-19-1\nThe request was received on that date.\n"
            "Decision No. CR5361\n")
    assert metadata.parse(text, "2019.07.02 CR5361 Wesley J. Nord")["decision_date"] == "2019-07-02"


def test_that_fallback_is_refused_when_it_disagrees_with_the_record_id():
    # Same shape, but the only date in the header is from the facts. Without an
    # agreeing record-id date it stays null -- null rather than wrong.
    text = ("DEPARTMENTAL APPEALS BOARD\nPeriod audited: March 3, 2007\n"
            "The request was received on that date.\nDecision No. CR1762\n")
    assert metadata.parse(text, "2008.03.20 CR1762 Feole")["decision_date"] is None
    assert metadata.parse(text, "CR1762")["decision_date"] is None   # no id date at all


def test_nul_text_gets_the_same_guard_on_its_unlabelled_dates():
    plain = ("DEPARTMENTAL APPEALS BOARD\nStatement of facts: October 1, 1986\n"
             "Decision No. 1539\n")
    spaced = "\x00".join(plain)
    assert metadata.parse(spaced, "1995.10.06DAB1539 California")["decision_date"] is None


def test_the_original_fallback_is_unchanged_when_there_is_no_label_at_all():
    # No "date" anywhere: behaves exactly as before, id date or not.
    text = "DEPARTMENTAL APPEALS BOARD\nJune 30, 2015\nDecision No. 2647\n"
    assert metadata.parse(text, "2015.06.30 DAB2647 X")["decision_date"] == "2015-06-30"
    assert metadata.parse(text, "DAB2647")["decision_date"] == "2015-06-30"


def test_a_ruling_the_board_typed_as_dab_is_a_ruling():
    # "2026.08.13; DAB2026-19, ..." (URL: board-ruling-2026-19) came back as
    # decision 2026, which also names a real 2006 decision.
    assert metadata.decision_no_from_text("2026.08.13; DAB2026-19, O D Inc.") == "RULING2026-19"
    assert metadata.decision_no_from_text("2026.08.10; RUL2026-18; Mega Hospice") == "RULING2026-18"
    # ...and real four-digit DAB numbers are untouched.
    assert metadata.decision_no_from_text("2003.12.04 DAB1900 Franklin Care") == "1900"
    assert metadata.decision_no_from_text("2026.09.22 DAB3241 X") == "3241"
